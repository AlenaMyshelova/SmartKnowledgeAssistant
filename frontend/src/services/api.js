import axios from "axios";

// Базовый URL нашего API
const BASE_URL = "http://localhost:8001/api/v1";

// Создаем экземпляр axios с предустановленными настройками
const api = axios.create({
  baseURL: BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Функции для работы с API
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

export default api;
