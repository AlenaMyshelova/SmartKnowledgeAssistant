import React, { createContext, useState, useContext, useEffect } from "react";
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
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState(() => localStorage.getItem("token"));

  useEffect(() => {
    // Check for token in URL params (OAuth callback)
    const urlParams = new URLSearchParams(window.location.search);
    const tokenFromUrl = urlParams.get("token");

    if (tokenFromUrl) {
      localStorage.setItem("token", tokenFromUrl);
      setToken(tokenFromUrl);
      // Clean URL and redirect
      window.history.replaceState({}, document.title, "/chat");
    }

    // Check if user is logged in
    if (token || tokenFromUrl) {
      fetchUser();
    } else {
      setLoading(false);
    }
  }, []);

  const fetchUser = async () => {
    try {
      const userData = await authApi.getCurrentUser();
      setUser(userData);
    } catch (error) {
      console.error("Error fetching user:", error);
      if (error.response?.status === 401) {
        localStorage.removeItem("token");
        setToken(null);
      }
    } finally {
      setLoading(false);
    }
  };

  const login = (token, userData) => {
    localStorage.setItem("token", token);
    setToken(token);
    setUser(userData);
  };

  const logout = async () => {
    try {
      await authApi.logout();
    } catch (error) {
      console.error("Logout error:", error);
    }
    localStorage.removeItem("token");
    setToken(null);
    setUser(null);
    window.location.href = "/login";
  };

  const value = {
    user,
    token,
    loading,
    login,
    logout,
    isAuthenticated: !!token,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
