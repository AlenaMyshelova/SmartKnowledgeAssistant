import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { CircularProgress, Box } from "@mui/material";
import { authApi } from "../../services/api";

export default function ProtectedRoute() {
  const [isAuthenticated, setIsAuthenticated] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const location = useLocation();

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const token = localStorage.getItem("token");
        if (!token) {
          setIsAuthenticated(false);
          return;
        }

        // Verify token is valid
        const user = await authApi.getCurrentUser();
        if (user) {
          setIsAuthenticated(true);
        } else {
          setIsAuthenticated(false);
          localStorage.removeItem("token");
        }
      } catch (error) {
        console.error("Auth check failed:", error);
        setIsAuthenticated(false);
        localStorage.removeItem("token");
      } finally {
        setIsLoading(false);
      }
    };

    checkAuth();
  }, []);

  // Show loading state
  if (isLoading) {
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
      </Box>
    );
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Render protected content
  return <Outlet />;
}
