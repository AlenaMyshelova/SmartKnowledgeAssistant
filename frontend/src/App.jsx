import { useState, useEffect } from "react";
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
} from "@mui/material";
import ChatInterface from "./components/chat/ChatInterface";
import { chatApi } from "./services/api";
import SmartToyIcon from "@mui/icons-material/SmartToy";

// Создаем тему Material UI
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

  // Проверяем доступность API при загрузке
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

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />

      {/* Шапка приложения */}
      <AppBar position="static" color="primary">
        <Toolbar>
          <SmartToyIcon sx={{ mr: 2 }} />
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            TechNova Knowledge Assistant
          </Typography>
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
              Пожалуйста, убедитесь, что бэкенд запущен на http://localhost:8001
            </Typography>
          </Box>
        ) : (
          <ChatInterface />
        )}
      </Container>
    </ThemeProvider>
  );
}

export default App;
