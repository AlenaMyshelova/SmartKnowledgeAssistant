import axios from "axios";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8001/api/v1";

const api = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    console.log(
      "API Request:",
      config.method.toUpperCase(),
      config.url,
      config.data
    );
    return config;
  },
  (error) => {
    console.error("API Request Error:", error);
    return Promise.reject(error);
  }
);

// Response interceptor
api.interceptors.response.use(
  (response) => {
    console.log("API Response:", response.status, response.data);
    return response;
  },
  (error) => {
    console.error("API Error:", error.response?.status, error.response?.data);
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

// Auth API
export const authApi = {
  getProviders: async () => {
    const response = await api.get("/auth/providers");
    return response.data;
  },
  getCurrentUser: async () => {
    const response = await api.get("/auth/me");
    return response.data;
  },
  logout: async () => {
    const response = await api.post("/auth/logout");
    return response.data;
  },
};

// Chat API - ПРАВИЛЬНЫЕ ENDPOINTS из вашего backend
export const chatApi = {
  // Messages
  sendMessage: (data) => api.post("/chat/send", data), // ✅ Правильный endpoint

  // Sessions
  getSessions: (params) => api.get("/chat/sessions", { params }),
  createSession: (data) => api.post("/chat/sessions", data),
  getSession: (id) => api.get(`/chat/sessions/${id}`),
  updateSession: (id, data) => api.patch(`/chat/sessions/${id}`, data),
  deleteSession: (id) => api.delete(`/chat/sessions/${id}`),

  // Search
  searchChats: (data) => api.post("/chat/search", data),

  // Mode
  getChatModeStatus: () => api.get("/chat/mode/status"),

  // Incognito
  clearIncognito: () => api.delete("/chat/incognito/clear"),
};

// Data Sources API
export const dataApi = {
  getSources: () => api.get("/data-sources"),
  uploadFile: (formData) =>
    api.post("/data-sources/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    }),
};

export default api;
