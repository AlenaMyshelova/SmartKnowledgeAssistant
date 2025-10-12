import { useState, useEffect } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useSearchParams,
  useNavigate,
} from "react-router-dom";
import { ThemeProvider, createTheme, CssBaseline } from "@mui/material";
import {
  Container,
  Box,
  Typography,
  CircularProgress,
  AppBar,
  Toolbar,
  Button,
} from "@mui/material";
import SmartToyIcon from "@mui/icons-material/SmartToy";
import LogoutIcon from "@mui/icons-material/Logout";

// Import components
import Login from "./components/auth/Login";
import ProtectedRoute from "./components/auth/ProtectedRoute";
import ChatInterface from "./components/chat/ChatInterface";
import { chatApi, authApi } from "./services/api";

// Create Material UI theme
const theme = createTheme({
  palette: {
    mode: "light",
    primary: {
      main: "#1976d2",
    },
    secondary: {
      main: "#dc004e",
    },
    background: {
      default: "#f5f5f5",
    },
  },
  typography: {
    fontFamily: '"Roboto", "Helvetica", "Arial", sans-serif',
  },
});

// OAuth Callback компонент
function AuthCallback() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  useEffect(() => {
    const handleCallback = async () => {
      const token = searchParams.get("token");
      const error = searchParams.get("error");

      if (error) {
        navigate(`/login?error=${error}`);
        return;
      }

      if (token) {
        localStorage.setItem("token", token);
        // Используем window.location для полной перезагрузки приложения
        window.location.href = "/";
      } else {
        navigate("/login");
      }
    };

    handleCallback();
  }, [navigate, searchParams]);

  return (
    <Box
      sx={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        height: "100vh",
      }}
    >
      <CircularProgress />
      <Typography sx={{ ml: 2 }}>Completing sign in...</Typography>
    </Box>
  );
}

function App() {
  const [apiStatus, setApiStatus] = useState("checking");
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Check API health
  useEffect(() => {
    const checkApi = async () => {
      try {
        const health = await chatApi.healthCheck();
        setApiStatus(health.status === "healthy" ? "online" : "offline");
      } catch (error) {
        console.error("API health check failed:", error);
        setApiStatus("offline");
      }
    };

    checkApi();
    const interval = setInterval(checkApi, 30000);
    return () => clearInterval(interval);
  }, []);

  // Check authentication on mount
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const token = localStorage.getItem("token");

        if (token) {
          const userData = await authApi.getCurrentUser();
          if (userData) {
            setUser(userData);
          } else {
            localStorage.removeItem("token");
          }
        }
      } catch (error) {
        console.error("Auth check failed:", error);
        localStorage.removeItem("token");
      } finally {
        setLoading(false);
      }
    };

    checkAuth();
  }, []);

  // Handle logout
  const handleLogout = async () => {
    try {
      await authApi.logout();
    } catch (error) {
      console.error("Logout failed:", error);
    } finally {
      localStorage.removeItem("token");
      setUser(null);
      window.location.href = "/login";
    }
  };

  if (loading) {
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
        <Routes>
          {/* Auth callback route - должен быть первым */}
          <Route path="/auth/callback" element={<AuthCallback />} />

          {/* Login route */}
          <Route
            path="/login"
            element={user ? <Navigate to="/" /> : <Login />}
          />

          {/* Protected routes with ProtectedRoute wrapper */}
          <Route element={<ProtectedRoute />}>
            <Route
              path="/"
              element={
                <Box
                  sx={{
                    display: "flex",
                    flexDirection: "column",
                    height: "100vh",
                  }}
                >
                  {/* Header with logout button */}
                  <AppBar position="static" elevation={1}>
                    <Toolbar>
                      <SmartToyIcon sx={{ mr: 2 }} />
                      <Typography
                        variant="h6"
                        component="div"
                        sx={{ flexGrow: 1 }}
                      >
                        TechNova Knowledge Assistant
                      </Typography>

                      {user && (
                        <>
                          <Typography sx={{ mr: 2 }}>
                            {user.email || user.name}
                          </Typography>
                          <Button
                            color="inherit"
                            startIcon={<LogoutIcon />}
                            onClick={handleLogout}
                          >
                            Logout
                          </Button>
                        </>
                      )}

                      <Box
                        sx={{
                          display: "flex",
                          alignItems: "center",
                          backgroundColor:
                            apiStatus === "online"
                              ? "success.main"
                              : "error.main",
                          color: "white",
                          borderRadius: 1,
                          px: 1,
                          py: 0.5,
                          fontSize: "0.75rem",
                          ml: 2,
                        }}
                      >
                        API: {apiStatus}
                      </Box>
                    </Toolbar>
                  </AppBar>

                  {/* Chat interface */}
                  <Box sx={{ flexGrow: 1, overflow: "hidden" }}>
                    {apiStatus === "offline" ? (
                      <Container maxWidth="sm" sx={{ mt: 4 }}>
                        <Box sx={{ textAlign: "center" }}>
                          <Typography variant="h5" color="error" gutterBottom>
                            API недоступен
                          </Typography>
                          <Typography>
                            Пожалуйста, убедитесь, что бэкенд запущен на
                            http://localhost:8001
                          </Typography>
                        </Box>
                      </Container>
                    ) : (
                      <ChatInterface />
                    )}
                  </Box>
                </Box>
              }
            />
          </Route>

          {/* Catch all */}
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
