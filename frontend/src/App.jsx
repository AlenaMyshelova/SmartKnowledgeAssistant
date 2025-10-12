import { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import {
  CssBaseline,
  ThemeProvider,
  createTheme,
  AppBar,
  Toolbar,
  Typography,
  Container,
  Box,
  CircularProgress,
  Button,
} from "@mui/material";
import SmartToyIcon from "@mui/icons-material/SmartToy";
import LogoutIcon from "@mui/icons-material/Logout";

// Import components
import ChatInterface from "./components/chat/ChatInterface";
import Login from "./components/auth/Login";
import ProtectedRoute from "./components/auth/ProtectedRoute";
import { chatApi, authApi } from "./services/api";

// Create Material UI theme
const theme = createTheme({
  palette: {
    primary: {
      main: "#1976d2",
    },
    secondary: {
      main: "#9c27b0",
    },
  },
});

function App() {
  const [apiStatus, setApiStatus] = useState("checking");
  const [user, setUser] = useState(null);
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);

  // Check API availability on load
  useEffect(() => {
    const checkApiStatus = async () => {
      try {
        await chatApi.healthCheck();
        setApiStatus("online");
      } catch (error) {
        console.error("API health check failed:", error);
        setApiStatus("offline");
      }
    };

    checkApiStatus();
  }, []);

  // Check user authentication on mount
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const token = localStorage.getItem("token");
        if (token) {
          const userData = await authApi.getCurrentUser();
          setUser(userData);
        }
      } catch (error) {
        console.error("Auth check failed:", error);
        localStorage.removeItem("token");
      } finally {
        setIsCheckingAuth(false);
      }
    };

    checkAuth();
  }, []);

  // Handle logout
  const handleLogout = async () => {
    try {
      await authApi.logout();
      setUser(null);
    } catch (error) {
      console.error("Logout failed:", error);
    }
  };

  // Show loading spinner while checking authentication
  if (isCheckingAuth) {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Box
          sx={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            height: "100vh",
          }}
        >
          <CircularProgress />
        </Box>
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        {/* App header */}
        <AppBar position="static" color="primary">
          <Toolbar>
            <SmartToyIcon sx={{ mr: 2 }} />
            <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
              TechNova Knowledge Assistant
            </Typography>

            {/* Show user info and logout button if authenticated */}
            {user && (
              <>
                <Typography sx={{ mr: 2 }}>{user.email}</Typography>
                <Button
                  color="inherit"
                  startIcon={<LogoutIcon />}
                  onClick={handleLogout}
                >
                  Logout
                </Button>
              </>
            )}

            {/* API status indicator */}
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                backgroundColor:
                  apiStatus === "online" ? "success.main" : "error.main",
                color: "white",
                borderRadius: 1,
                px: 1,
                py: 0.5,
                fontSize: "0.75rem",
                ml: 2,
              }}
            >
              API:{" "}
              {apiStatus === "checking" ? (
                <CircularProgress size={14} color="inherit" sx={{ ml: 1 }} />
              ) : (
                apiStatus
              )}
            </Box>
          </Toolbar>
        </AppBar>

        <Container>
          {apiStatus === "offline" ? (
            <Box sx={{ mt: 4, textAlign: "center" }}>
              <Typography variant="h5" color="error" gutterBottom>
                API недоступен
              </Typography>
              <Typography>
                Пожалуйста, убедитесь, что бэкенд запущен на
                http://localhost:8001
              </Typography>
            </Box>
          ) : (
            <Routes>
              {/* Public routes */}
              <Route path="/login" element={<Login />} />
              <Route path="/auth/callback" element={<Login />} />

              {/* Protected routes */}
              <Route element={<ProtectedRoute />}>
                <Route path="/chat" element={<ChatInterface />} />
                <Route path="/" element={<Navigate to="/chat" replace />} />
              </Route>

              {/* Catch all - redirect to login or chat based on auth status */}
              <Route
                path="*"
                element={
                  user ? (
                    <Navigate to="/chat" replace />
                  ) : (
                    <Navigate to="/login" replace />
                  )
                }
              />
            </Routes>
          )}
        </Container>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
