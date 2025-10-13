import React from "react";
import { ThemeProvider, createTheme, CssBaseline } from "@mui/material";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";
import { SnackbarProvider } from "notistack";
import Login from "./components/auth/Login";
import ProtectedRoute from "./components/auth/ProtectedRoute";
import MainLayout from "./components/layout/MainLayout";
import ChatInterface from "./components/chat/ChatInterface";
import { AuthProvider } from "./contexts/AuthContext";
import { ChatProvider } from "./contexts/ChatContext";

const theme = createTheme({
  palette: {
    mode: "light",
    primary: {
      main: "#10a37f",
      dark: "#0d8f6f",
      light: "#42b899",
    },
    secondary: {
      main: "#666",
    },
    background: {
      default: "#f7f7f8",
      paper: "#ffffff",
    },
  },
  typography: {
    fontFamily: '"Inter", "SF Pro Display", -apple-system, sans-serif',
  },
  shape: {
    borderRadius: 8,
  },
});

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <SnackbarProvider
        maxSnack={3}
        anchorOrigin={{
          vertical: "bottom",
          horizontal: "left",
        }}
      >
        <Router>
          <AuthProvider>
            <Routes>
              <Route path="/login" element={<Login />} />

              {/* Protected routes with Outlet pattern */}
              <Route element={<ProtectedRoute />}>
                <Route path="/" element={<Navigate to="/chat" replace />} />
                <Route
                  element={
                    <ChatProvider>
                      <MainLayout />
                    </ChatProvider>
                  }
                >
                  <Route path="/chat" element={<ChatInterface />} />
                  <Route path="/chat/:chatId" element={<ChatInterface />} />
                </Route>
              </Route>
            </Routes>
          </AuthProvider>
        </Router>
      </SnackbarProvider>
    </ThemeProvider>
  );
}

export default App;
