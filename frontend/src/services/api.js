import axios from "axios";

// Базовый URL нашего API, берется из переменных окружения Vite
const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8001/api/v1";

// Создаем экземпляр axios с базовыми настройками
const api = axios.create({
  baseURL: BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  withCredentials: true, // Важно для отправки и получения cookies
});

// Перехватчик запросов: добавляет токен в заголовок Authorization
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("token");
    if (token) {
      config.headers["Authorization"] = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Перехватчик ответов: обрабатывает ошибки 401
api.interceptors.response.use(
  (response) => {
    return response;
  },
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      // Если получили 401, удаляем токен и перенаправляем на логин
      localStorage.removeItem("token");
      window.location.href = "/login";
    }

    return Promise.reject(error);
  }
);

// API для работы с чатом
export const chatApi = {
  // Отправка сообщения и получение ответа
  sendMessage: async (message, dataSource = "company_faqs") => {
    try {
      const response = await api.post("/chat", {
        message,
        data_source: dataSource,
      });
      return response.data;
    } catch (error) {
      console.error("Error sending message:", error);
      throw error;
    }
  },

  // Получение истории чата
  getChatHistory: async (limit = 20) => {
    try {
      const response = await api.get(`/chat/history?limit=${limit}`);
      return response.data.history;
    } catch (error) {
      console.error("Error getting chat history:", error);
      throw error;
    }
  },

  // Получение доступных источников данных
  getDataSources: async () => {
    try {
      const response = await api.get("/data-sources");
      return response.data;
    } catch (error) {
      console.error("Error getting data sources:", error);
      throw error;
    }
  },

  // Получение категорий FAQ
  getCategories: async () => {
    try {
      const response = await api.get("/categories");
      return response.data.categories;
    } catch (error) {
      console.error("Error getting categories:", error);
      throw error;
    }
  },

  // Проверка работоспособности API
  healthCheck: async () => {
    try {
      const response = await api.get("/health");
      return response.data;
    } catch (error) {
      console.error("API health check failed:", error);
      throw error;
    }
  },
};

// API для работы с аутентификацией
export const authApi = {
  // Получение списка OAuth провайдеров
  getProviders: async () => {
    try {
      const response = await api.get("/auth/providers");
      return response;
    } catch (error) {
      console.error("Error fetching providers:", error);
      throw error;
    }
  },

  // Получение данных текущего пользователя
  getCurrentUser: async () => {
    try {
      const response = await api.get("/auth/me");
      return response.data;
    } catch (error) {
      console.error("Error fetching current user:", error);
      throw error;
    }
  },

  // Выход из системы
  logout: async () => {
    try {
      await api.post("/auth/logout");
      localStorage.removeItem("token");
      window.location.href = "/login";
    } catch (error) {
      console.error("Error during logout:", error);
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
  },

  // Проверка, истек ли токен
  isTokenExpired: () => {
    const token = localStorage.getItem("token");
    if (!token) return true;

    try {
      // Декодируем JWT токен
      const base64Url = token.split(".")[1];
      const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split("")
          .map(function (c) {
            return "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2);
          })
          .join("")
      );

      const payload = JSON.parse(jsonPayload);
      const currentTime = Date.now() / 1000;

      return payload.exp < currentTime;
    } catch (error) {
      return true;
    }
  },

  // Обновление токена
  refreshToken: async () => {
    try {
      const response = await api.post("/auth/refresh-token");
      const { access_token } = response.data;
      localStorage.setItem("token", access_token);
      return response.data;
    } catch (error) {
      console.error("Error refreshing token:", error);
      throw error;
    }
  },
};

// Экспортируем экземпляр axios по умолчанию
export default api;
