import React, {
  createContext,
  useState,
  useContext,
  useCallback,
  useEffect,
} from "react";
import { useAuth } from "./AuthContext";
import { chatApi } from "../services/api";

const ChatContext = createContext();

export const useChat = () => {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error("useChat must be used within a ChatProvider");
  }
  return context;
};

export const ChatProvider = ({ children }) => {
  const { token, user, isAuthenticated } = useAuth(); // Добавили user и isAuthenticated

  // Chat states
  const [chats, setChats] = useState([]);
  const [currentChat, setCurrentChat] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isIncognito, setIsIncognito] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Pagination states
  const [hasMore, setHasMore] = useState(true);
  const [page, setPage] = useState(1);
  const [totalChats, setTotalChats] = useState(0);

  // Search and filter states
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [filters, setFilters] = useState({
    dateRange: null,
    dataSource: null,
    tags: [],
  });
  const [savedFilters, setSavedFilters] = useState([]);
  const [deletedChats, setDeletedChats] = useState([]);

  const apiCall = async (endpoint, options = {}) => {
    if (!token) {
      throw new Error("No authentication token");
    }

    const response = await fetch(`http://localhost:8001/api/v1${endpoint}`, {
      ...options,
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(error || `API call failed: ${response.statusText}`);
    }

    return response.json();
  };

  // Load chats with pagination
  const loadChats = useCallback(
    async (pageNum = 1, append = false) => {
      if (!token) return;

      console.log("Loading chats, user:", user, "page:", pageNum); // Для отладки

      try {
        setLoading(true);
        const params = new URLSearchParams({
          page: pageNum,
          page_size: 20,
          include_incognito: isIncognito,
        });

        const data = await apiCall(`/chat/sessions?${params}`);

        console.log("Loaded chats data:", data); // Для отладки

        if (append) {
          setChats((prev) => [...prev, ...(data.chats || [])]);
        } else {
          setChats(data.chats || []);
        }

        setTotalChats(data.total || 0);
        setHasMore((data.chats?.length || 0) === 20);
        setPage(pageNum);
      } catch (err) {
        console.error("Error loading chats:", err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    },
    [token, isIncognito, user] // Добавлен user в зависимости
  );

  // Load more chats for infinite scroll
  const loadMoreChats = useCallback(() => {
    if (!loading && hasMore) {
      loadChats(page + 1, true);
    }
  }, [loading, hasMore, page, loadChats]);

  // Create new chat
  const createNewChat = useCallback(
    async (title = null) => {
      try {
        const data = await apiCall("/chat/sessions", {
          method: "POST",
          body: JSON.stringify({
            is_incognito: isIncognito,
            title: title || (isIncognito ? "Incognito Chat" : "New Chat"),
          }),
        });

        const newChat = {
          id: data.chat_id,
          title: title || (isIncognito ? "Incognito Chat" : "New Chat"),
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          is_incognito: isIncognito,
          is_pinned: false,
          message_count: 0,
          last_message: null,
        };

        setChats((prev) => [newChat, ...prev]);
        setCurrentChat(newChat);

        return data.chat_id;
      } catch (err) {
        console.error("Error creating chat:", err);
        setError(err.message);
        throw err;
      }
    },
    [token, isIncognito]
  );

  // Load chat history
  const loadChatHistory = useCallback(
    async (chatId) => {
      if (!chatId || !token) return;

      try {
        setLoading(true);
        const data = await apiCall(`/chat/sessions/${chatId}`);
        setCurrentChat(data.chat);
        setMessages(data.messages || []);
      } catch (err) {
        console.error("Error loading chat history:", err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    },
    [token]
  );

  // Send message
  const sendMessage = useCallback(
    async (message, dataSource = "company_faqs") => {
      console.log("Sending message:", {
        message,
        dataSource,
        currentChat,
        isIncognito,
      });

      try {
        // Добавляем сообщение пользователя в UI сразу
        const userMessage = {
          id: `temp-${Date.now()}`,
          role: "user",
          content: message,
          timestamp: new Date().toISOString(),
        };

        setMessages((prev) => [...prev, userMessage]);

        // Формируем запрос ТОЧНО по модели backend
        const requestData = {
          message: message,
          chat_id: currentChat?.id || null,
          data_source: dataSource || "company_faqs",
          is_incognito: isIncognito,
        };

        console.log("Request data:", requestData);

        const response = await chatApi.sendMessage(requestData);
        console.log("Response:", response);

        const data = response.data;

        // Если backend создал новый чат, обновляем currentChat
        if (!currentChat && data.chat_id) {
          const newChat = {
            id: data.chat_id,
            title:
              message.substring(0, 50) + (message.length > 50 ? "..." : ""),
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            is_incognito: isIncognito,
            is_pinned: false,
            is_archived: false,
            message_count: 2,
            last_message: message.substring(0, 100),
          };
          setCurrentChat(newChat);
          setChats((prev) => [newChat, ...prev]);

          // Если создан новый чат, переходим на его URL
          if (window.location.pathname === "/chat") {
            window.history.pushState({}, "", `/chat/${data.chat_id}`);
          }
        }

        // Добавляем ответ ассистента
        const assistantMessage = {
          id: data.message_id || `assistant-${Date.now()}`,
          role: "assistant",
          content: data.response,
          timestamp: new Date().toISOString(),
          sources: data.sources,
          metadata: {
            is_incognito: data.is_incognito,
            ...data.metadata,
          },
        };

        // Обновляем сообщения
        setMessages((prev) => {
          const filtered = prev.filter((m) => m.id !== userMessage.id);
          return [
            ...filtered,
            {
              ...userMessage,
              id: data.user_message_id || `user-${Date.now()}`,
              chat_id: data.chat_id || currentChat?.id,
            },
            assistantMessage,
          ];
        });

        // Обновляем информацию о чате в списке
        if (currentChat || data.chat_id) {
          const chatIdToUpdate = currentChat?.id || data.chat_id;
          setChats((prev) =>
            prev.map((chat) =>
              chat.id === chatIdToUpdate
                ? {
                    ...chat,
                    last_message: message.substring(0, 100),
                    updated_at: new Date().toISOString(),
                    message_count: (chat.message_count || 0) + 2,
                  }
                : chat
            )
          );
        }

        // Перезагружаем список чатов если это не incognito
        if (!isIncognito) {
          loadChats(1); // Обновляем список чатов
        }

        return data;
      } catch (err) {
        // Удаляем временное сообщение при ошибке
        setMessages((prev) => prev.filter((m) => !m.id.startsWith("temp-")));

        // Обработка ошибок
        const errorMessage =
          err.response?.data?.detail || err.message || "Failed to send message";
        console.error("Error sending message:", errorMessage);
        setError(errorMessage);

        // Показываем уведомление об ошибке
        if (window.enqueueSnackbar) {
          window.enqueueSnackbar(errorMessage, { variant: "error" });
        }

        throw err;
      }
    },
    [currentChat, isIncognito, loadChats]
  );

  // Delete chat
  const deleteChat = useCallback(
    async (chatId) => {
      const chatToDelete = chats.find((c) => c.id === chatId);
      if (!chatToDelete) return;

      setChats((prev) => prev.filter((c) => c.id !== chatId));
      setDeletedChats((prev) => [...prev, chatToDelete]);

      if (currentChat?.id === chatId) {
        setCurrentChat(null);
        setMessages([]);
      }

      // Actually delete after 5 seconds
      setTimeout(async () => {
        try {
          await apiCall(`/chat/sessions/${chatId}`, {
            method: "DELETE",
          });
          setDeletedChats((prev) => prev.filter((c) => c.id !== chatId));
        } catch (err) {
          // Restore on error
          setChats((prev) => [...prev, chatToDelete]);
          setDeletedChats((prev) => prev.filter((c) => c.id !== chatId));
          console.error("Error deleting chat:", err);
        }
      }, 5000);

      return chatToDelete;
    },
    [chats, currentChat, token]
  );

  // Undo delete
  const undoDelete = useCallback(
    (chatId) => {
      const chatToRestore = deletedChats.find((c) => c.id === chatId);
      if (!chatToRestore) return;

      setChats((prev) =>
        [...prev, chatToRestore].sort(
          (a, b) => new Date(b.updated_at) - new Date(a.updated_at)
        )
      );
      setDeletedChats((prev) => prev.filter((c) => c.id !== chatId));
    },
    [deletedChats]
  );

  // Update chat
  const updateChat = useCallback(
    async (chatId, updates) => {
      setChats((prev) =>
        prev.map((chat) =>
          chat.id === chatId ? { ...chat, ...updates } : chat
        )
      );

      try {
        await apiCall(`/chat/sessions/${chatId}`, {
          method: "PATCH",
          body: JSON.stringify(updates),
        });
      } catch (err) {
        loadChats(page);
        console.error("Error updating chat:", err);
        setError(err.message);
      }
    },
    [token, page, loadChats]
  );

  // Search chats
  const searchChats = useCallback(
    async (query) => {
      if (!query.trim()) {
        setSearchResults([]);
        setIsSearching(false);
        return;
      }

      try {
        setIsSearching(true);
        const data = await apiCall("/chat/search", {
          method: "POST",
          body: JSON.stringify({
            query,
            filters,
            limit: 50,
          }),
        });

        setSearchResults(data.results || []);
      } catch (err) {
        console.error("Error searching chats:", err);
        setSearchResults([]);
      } finally {
        setIsSearching(false);
      }
    },
    [token, filters]
  );

  // Toggle incognito mode
  const toggleIncognito = useCallback(() => {
    setIsIncognito((prev) => !prev);
    setCurrentChat(null);
    setMessages([]);
  }, []);

  // Clear all incognito chats
  const clearIncognitoChats = useCallback(async () => {
    try {
      await apiCall("/chat/incognito/clear", {
        method: "DELETE",
      });

      setChats((prev) => prev.filter((c) => !c.is_incognito));

      if (currentChat?.is_incognito) {
        setCurrentChat(null);
        setMessages([]);
      }
    } catch (err) {
      console.error("Error clearing incognito chats:", err);
      setError(err.message);
    }
  }, [token, currentChat]);

  // Save filter preset
  const saveFilter = useCallback(
    (name, filterConfig) => {
      const newFilter = {
        id: Date.now(),
        name,
        ...filterConfig,
        created_at: new Date().toISOString(),
      };

      const updated = [...savedFilters, newFilter];
      setSavedFilters(updated);
      localStorage.setItem("savedFilters", JSON.stringify(updated));
    },
    [savedFilters]
  );

  // Delete saved filter
  const deleteSavedFilter = useCallback(
    (filterId) => {
      const updated = savedFilters.filter((f) => f.id !== filterId);
      setSavedFilters(updated);
      localStorage.setItem("savedFilters", JSON.stringify(updated));
    },
    [savedFilters]
  );

  // Apply saved filter
  const applySavedFilter = useCallback((filter) => {
    setFilters({
      dateRange: filter.dateRange,
      dataSource: filter.dataSource,
      tags: filter.tags,
    });

    if (filter.query) {
      setSearchQuery(filter.query);
    }
  }, []);

  // ВАЖНО: Загружаем чаты когда пользователь меняется
  useEffect(() => {
    if (isAuthenticated && user?.id && token) {
      console.log("User authenticated, loading chats for:", user);
      loadChats(1);

      // Load saved filters from localStorage
      const saved = localStorage.getItem("savedFilters");
      if (saved) {
        try {
          setSavedFilters(JSON.parse(saved));
        } catch (err) {
          console.error("Error loading saved filters:", err);
        }
      }
    } else if (!isAuthenticated) {
      // Очищаем все при выходе
      console.log("User not authenticated, clearing all data");
      setChats([]);
      setCurrentChat(null);
      setMessages([]);
      setSearchResults([]);
      setDeletedChats([]);
    }
  }, [isAuthenticated, user?.id, token]); // Следим за изменениями авторизации

  // Search effect with debounce
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchQuery) {
        searchChats(searchQuery);
      } else {
        setSearchResults([]);
        setIsSearching(false);
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [searchQuery, searchChats]);

  // Добавляем алиасы для совместимости с Sidebar
  const userChats = chats; // Алиас для совместимости
  const loadUserChats = loadChats; // Алиас для совместимости

  const value = {
    // States
    chats,
    userChats, // Добавлен алиас
    currentChat,
    messages,
    isIncognito,
    loading,
    error,
    hasMore,
    totalChats,
    searchQuery,
    searchResults,
    isSearching,
    filters,
    savedFilters,
    deletedChats,

    // Actions
    loadChats,
    loadUserChats, // Добавлен алиас
    loadMoreChats,
    createNewChat,
    loadChatHistory,
    sendMessage,
    deleteChat,
    undoDelete,
    updateChat,
    setSearchQuery,
    toggleIncognito,
    clearIncognitoChats,
    setFilters,
    saveFilter,
    deleteSavedFilter,
    applySavedFilter,
    setMessages,
    setCurrentChat,
  };

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
};
