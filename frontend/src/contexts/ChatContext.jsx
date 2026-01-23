import React, {
  createContext,
  useState,
  useContext,
  useCallback,
  useEffect,
  useRef,
} from "react";
import { useNavigate } from "react-router-dom";
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
  const { token, user, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  // Chat states
  const [chats, setChats] = useState([]);
  const [currentChat, setCurrentChat] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isIncognito, setIsIncognito] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [deleteTimers, setDeleteTimers] = useState({});
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

  // Refs for deleted chats and timers to access latest state in callbacks
  const deletedChatsRef = useRef(deletedChats);
  const deleteTimersRef = useRef(deleteTimers);

  // update refs when states change
  useEffect(() => {
    deletedChatsRef.current = deletedChats;
  }, [deletedChats]);

  useEffect(() => {
    deleteTimersRef.current = deleteTimers;
  }, [deleteTimers]);

  const apiCall = async (endpoint, options = {}) => {
    if (!token) {
      throw new Error("No authentication token");
    }

    const response = await fetch(`http://localhost:8000/api/v1${endpoint}`, {
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

      console.log("Loading chats, user:", user, "page:", pageNum);

      try {
        setLoading(true);
        const params = new URLSearchParams({
          page: pageNum,
          page_size: 20,
          include_incognito: "false",
        });

        const data = await apiCall(`/chat/sessions?${params}`);

        console.log("Loaded chats data:", data);

        let regularChats = (data.chats || []).filter((chat) => chat.id > 0);

        //  Filter out chats that are in the process of being deleted
        const deletedChatIds = deletedChats.map((c) => c.id);
        regularChats = regularChats.filter(
          (chat) => !deletedChatIds.includes(chat.id),
        );

        if (append) {
          setChats((prev) => {
            // When appending, also filter out deleted chats
            const existingIds = prev.map((c) => c.id);
            const newChats = regularChats.filter(
              (c) => !existingIds.includes(c.id),
            );
            return [...prev, ...newChats];
          });
        } else {
          setChats(regularChats);
        }

        setTotalChats(regularChats.length);
        setHasMore(regularChats.length === 20);
        setPage(pageNum);
      } catch (err) {
        console.error("Error loading chats:", err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    },
    [token, user, deletedChats],
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
        // Clear messages before creating a new chat
        setMessages([]);

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

        if (!isIncognito) {
          setChats((prev) => [newChat, ...prev]);
        }

        setCurrentChat(newChat);
        setMessages([]);

        return data.chat_id;
      } catch (err) {
        console.error("Error creating chat:", err);
        setError(err.message);
        throw err;
      }
    },
    [token, isIncognito],
  );

  // Load chat history
  const loadChatHistory = useCallback(
    async (chatId) => {
      if (!chatId || !token) return;

      const isDeleted = deletedChats.some((c) => c.id === chatId);
      if (isDeleted) {
        console.log("Chat is deleted, skipping load:", chatId);
        return;
      }

      try {
        setLoading(true);
        const data = await apiCall(`/chat/sessions/${chatId}`);
        setCurrentChat(data.chat);
        setMessages(data.messages || []);
      } catch (err) {
        console.error("Error loading chat history:", err);
        if (err.message.includes("404") || err.message.includes("not found")) {
          setCurrentChat(null);
          setMessages([]);
        }
        setError(err.message);
      } finally {
        setLoading(false);
      }
    },
    [token, deletedChats],
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
        // Add user message to UI immediately
        const userMessage = {
          id: `temp-${Date.now()}`,
          role: "user",
          content: message,
          timestamp: new Date().toISOString(),
        };

        setMessages((prev) => [...prev, userMessage]);

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

        if (isIncognito) {
          // Update currentChat for incognito
          if (!currentChat && data.chat_id) {
            setCurrentChat({
              id: data.chat_id,
              title: "Incognito Chat",
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
              is_incognito: true,
              is_pinned: false,
              is_archived: false,
              message_count: 2,
              last_message: message.substring(0, 100),
            });
          }

          //  Only update messages for incognito
          setMessages((prev) => {
            const filtered = prev.filter((m) => !m.id.startsWith("temp-"));
            return [
              ...filtered,
              {
                id: `user-${Date.now()}`,
                role: "user",
                content: message,
                timestamp: new Date().toISOString(),
                chat_id: data.chat_id,
              },
              {
                id: `assistant-${Date.now()}`,
                role: "assistant",
                content: data.response,
                timestamp: new Date().toISOString(),
                sources: data.sources,
                chat_id: data.chat_id,
              },
            ];
          });

          // Do not update chat list for incognito
          return data;
        }

        // For regular chats - update
        if (!currentChat && data.chat_id) {
          const newChat = {
            id: data.chat_id,
            title:
              message.substring(0, 50) + (message.length > 50 ? "..." : ""),
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            is_incognito: false,
            is_pinned: false,
            is_archived: false,
            message_count: 2,
            last_message: message.substring(0, 100),
          };
          setCurrentChat(newChat);
          setChats((prev) => [newChat, ...prev]);

          // If a new chat is created, navigate to its URL
          if (window.location.pathname === "/chat") {
            navigate(`/chat/${data.chat_id}`, { replace: true });
          }
        }

        // Add assistant's response
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

        // Update messages
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

        // Update chat information in the list
        if (!isIncognito && (currentChat || data.chat_id)) {
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
                : chat,
            ),
          );
        }

        return data;
      } catch (err) {
        // Remove temporary message on error
        setMessages((prev) => prev.filter((m) => !m.id.startsWith("temp-")));

        const errorMessage =
          err.response?.data?.detail || err.message || "Failed to send message";
        console.error("Error sending message:", errorMessage);
        setError(errorMessage);

        if (window.enqueueSnackbar) {
          window.enqueueSnackbar(errorMessage, { variant: "error" });
        }

        throw err;
      }
    },
    [currentChat, isIncognito, loadChats, navigate],
  );

  // Toggle incognito mode
  const toggleIncognito = useCallback(() => {
    setIsIncognito((prev) => {
      const newValue = !prev;

      // When turning off incognito, clear current chat and messages
      if (prev === true && newValue === false) {
        setCurrentChat(null);
        setMessages([]);
        // Reload regular chats
        loadChats(1);
      }

      // When entering incognito, clear current chat
      if (prev === false && newValue === true) {
        setCurrentChat(null);
        setMessages([]);
      }

      return newValue;
    });
  }, [loadChats]);

  // Delete chat
  const deleteChat = useCallback(
    async (chatId) => {
      const chatToDelete = chats.find((c) => c.id === chatId);
      if (!chatToDelete) return null;

      // Immediately remove from UI
      setChats((prev) => prev.filter((c) => c.id !== chatId));

      // Add to deleted list
      setDeletedChats((prev) => [...prev, chatToDelete]);

      if (currentChat?.id === chatId) {
        setCurrentChat(null);
        setMessages([]);
        navigate("/chat");
      }

      // Create a timer for delayed deletion
      const timer = setTimeout(async () => {
        try {
          await apiCall(`/chat/sessions/${chatId}`, {
            method: "DELETE",
          });

          // After successful deletion, remove from deletedChats
          setDeletedChats((prev) => prev.filter((c) => c.id !== chatId));

          // Remove timer
          setDeleteTimers((prev) => {
            const newTimers = { ...prev };
            delete newTimers[chatId];
            return newTimers;
          });
        } catch (err) {
          // On error, restore chat
          setChats((prev) => {
            if (!prev.find((c) => c.id === chatId)) {
              return [...prev, chatToDelete].sort(
                (a, b) => new Date(b.updated_at) - new Date(a.updated_at),
              );
            }
            return prev;
          });
          setDeletedChats((prev) => prev.filter((c) => c.id !== chatId));
          console.error("Error deleting chat:", err);

          if (window.enqueueSnackbar) {
            window.enqueueSnackbar("Failed to delete chat", {
              variant: "error",
            });
          }
        }
      }, 5000); // 5 seconds to undo

      // Save timer
      setDeleteTimers((prev) => ({ ...prev, [chatId]: timer }));

      return chatToDelete;
    },
    [chats, currentChat, navigate],
  );

  // Undo delete - uses refs for current values
  const undoDelete = useCallback(
    (chatId) => {
      console.log("undoDelete called for chatId:", chatId);
      console.log("deletedChatsRef.current:", deletedChatsRef.current);
      console.log("deleteTimersRef.current:", deleteTimersRef.current);

      const chatToRestore = deletedChatsRef.current.find(
        (c) => c.id === chatId,
      );
      if (!chatToRestore) {
        console.log("Chat not found in deletedChats, cannot restore");
        return;
      }

      // Cancel delete timer
      const timer = deleteTimersRef.current[chatId];
      if (timer) {
        console.log("Clearing timer for chatId:", chatId);
        clearTimeout(timer);
        setDeleteTimers((prev) => {
          const newTimers = { ...prev };
          delete newTimers[chatId];
          return newTimers;
        });
      } else {
        console.log("No timer found for chatId:", chatId);
      }

      // Restore chat to list
      setChats((prev) => {
        if (prev.find((c) => c.id === chatId)) {
          console.log("Chat already in list, not adding");
          return prev;
        }
        console.log("Restoring chat to list");
        return [...prev, chatToRestore].sort(
          (a, b) => new Date(b.updated_at) - new Date(a.updated_at),
        );
      });

      // Remove from deleted list
      setDeletedChats((prev) => prev.filter((c) => c.id !== chatId));
      console.log("Chat restored successfully");
    },
    [], // Empty dependencies - using refs
  );

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      // Clear all timers on component unmount
      Object.values(deleteTimers).forEach((timer) => clearTimeout(timer));
    };
  }, [deleteTimers]);

  const updateChat = useCallback(
    async (chatId, updates) => {
      // Optimistic UI update
      setChats((prev) =>
        prev.map((chat) =>
          chat.id === chatId ? { ...chat, ...updates } : chat,
        ),
      );

      try {
        await apiCall(`/chat/sessions/${chatId}`, {
          method: "PATCH",
          body: JSON.stringify(updates),
        });
      } catch (err) {
        // Do not call loadChats on error if chat is deleted
        const isDeleted = deletedChats.some((c) => c.id === chatId);
        if (!isDeleted) {
          // Revert changes only if chat is not deleted
          loadChats(page);
        }
        console.error("Error updating chat:", err);
        setError(err.message);
      }
    },
    [page, loadChats, deletedChats],
  );

  const searchChats = useCallback(
    async (query) => {
      if (!query.trim()) {
        setSearchResults([]);
        setIsSearching(false);
        return;
      }

      try {
        setIsSearching(true);
        console.log("🔍 Searching for:", query, "with filters:", filters);

        const response = await chatApi.searchChats({
          query: query.trim(),
          include_archived: false,
          limit: 50,
        });

        let results = response.data.results || [];

        results = results.filter((r) => r && r.id > 0);

        if (filters.dateRange) {
          const now = new Date();
          let filterDate = new Date();

          if (filters.dateRange === "today") {
            filterDate.setHours(0, 0, 0, 0);
          } else if (filters.dateRange === "week") {
            filterDate.setDate(now.getDate() - 7);
          } else if (filters.dateRange === "month") {
            filterDate.setMonth(now.getMonth() - 1);
          }

          results = results.filter((chat) => {
            const chatDate = new Date(chat.updated_at);
            return chatDate >= filterDate;
          });
        }

        if (filters.dataSource) {
          results = results.filter(
            (chat) => chat.data_source === filters.dataSource,
          );
        }

        console.log("📊 Filtered results:", results.length, "items");
        setSearchResults(results);
      } catch (err) {
        console.error(" Error searching chats:", err);
        setSearchResults([]);
      } finally {
        setIsSearching(false);
      }
    },
    [filters],
  );

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
    [savedFilters],
  );

  const deleteSavedFilter = useCallback(
    (filterId) => {
      const updated = savedFilters.filter((f) => f.id !== filterId);
      setSavedFilters(updated);
      localStorage.setItem("savedFilters", JSON.stringify(updated));
    },
    [savedFilters],
  );

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

  // Load chats when user changes
  useEffect(() => {
    if (isAuthenticated && user?.id && token) {
      console.log("User authenticated, loading chats for:", user);
      loadChats(1);

      const saved = localStorage.getItem("savedFilters");
      if (saved) {
        try {
          setSavedFilters(JSON.parse(saved));
        } catch (err) {
          console.error("Error loading saved filters:", err);
        }
      }
    } else if (!isAuthenticated) {
      console.log("User not authenticated, clearing all data");
      setChats([]);
      setCurrentChat(null);
      setMessages([]);
      setSearchResults([]);
      setDeletedChats([]);
    }
  }, [isAuthenticated, user?.id, token]);

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

  // Aliases for compatibility
  const userChats = chats;
  const loadUserChats = loadChats;

  const value = {
    // States
    chats,
    userChats,
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
    loadUserChats,
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
