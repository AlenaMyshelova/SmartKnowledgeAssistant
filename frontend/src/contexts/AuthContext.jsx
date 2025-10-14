import React, { createContext, useState, useContext, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { authApi } from "../services/api";

const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState(() => localStorage.getItem("token"));

  // Обработка OAuth callback и проверка токена
  useEffect(() => {
    const handleAuth = async () => {
      // Проверяем токен в URL (OAuth callback)
      const urlParams = new URLSearchParams(location.search);
      const tokenFromUrl = urlParams.get("token");

      if (tokenFromUrl) {
        console.log("OAuth token received:", tokenFromUrl);
        localStorage.setItem("token", tokenFromUrl);
        setToken(tokenFromUrl);

        // Получаем информацию о пользователе
        try {
          const userInfo = await authApi.getCurrentUser();
          setUser(userInfo);
          localStorage.setItem("user", JSON.stringify(userInfo));

          // Убираем токен из URL и перенаправляем
          navigate("/chat", { replace: true });
        } catch (error) {
          console.error("Failed to get user info after OAuth:", error);
          localStorage.removeItem("token");
          setToken(null);
        } finally {
          setLoading(false);
        }
        return; // Важно! Выходим после обработки OAuth
      }

      // Проверяем сохраненный токен
      const savedToken = localStorage.getItem("token");
      const savedUser = localStorage.getItem("user");

      if (savedToken) {
        setToken(savedToken);

        try {
          // Проверяем валидность токена
          const userInfo = await authApi.getCurrentUser();
          setUser(userInfo);
          localStorage.setItem("user", JSON.stringify(userInfo));
        } catch (error) {
          console.error("Token invalid, clearing auth:", error);
          if (error.response?.status === 401) {
            localStorage.removeItem("token");
            localStorage.removeItem("user");
            setToken(null);
            setUser(null);
          }
        }
      } else if (savedUser) {
        // Если есть сохраненный пользователь но нет токена - очищаем
        localStorage.removeItem("user");
      }

      setLoading(false);
    };

    handleAuth();
  }, [location.search, navigate]);

  // Следим за изменением токена и загружаем пользователя
  useEffect(() => {
    if (token && !user) {
      fetchUser();
    }
  }, [token]);

  const fetchUser = async () => {
    try {
      const userData = await authApi.getCurrentUser();
      setUser(userData);
      localStorage.setItem("user", JSON.stringify(userData));
    } catch (error) {
      console.error("Error fetching user:", error);
      if (error.response?.status === 401) {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        setToken(null);
        setUser(null);
      }
    }
  };

  const login = (tokenValue, userData) => {
    localStorage.setItem("token", tokenValue);
    setToken(tokenValue);
    setUser(userData);
    localStorage.setItem("user", JSON.stringify(userData));
    navigate("/chat");
  };

  const logout = async () => {
    try {
      await authApi.logout();
    } catch (error) {
      console.error("Logout error:", error);
    }

    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setToken(null);
    setUser(null);
    navigate("/login");
  };

  const value = {
    user,
    token,
    loading,
    login,
    logout,
    isAuthenticated: !!token && !!user,
    fetchUser,
  };

  // Показываем загрузку пока проверяем аутентификацию
  if (loading) {
    return (
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          height: "100vh",
        }}
      >
        <div>Loading...</div>
      </div>
    );
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
