import { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
  Box,
  Button,
  Card,
  CardContent,
  Typography,
  Alert,
  CircularProgress,
} from "@mui/material";
import GoogleIcon from "@mui/icons-material/Google";
import GitHubIcon from "@mui/icons-material/GitHub";
import { authApi } from "../../services/api";

export default function Login() {
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();
  const location = useLocation();

  // Handle OAuth callback
  useEffect(() => {
    const searchParams = new URLSearchParams(location.search);
    const token = searchParams.get("token");
    const errorParam = searchParams.get("error");

    if (token) {
      // Save token and redirect to protected route
      localStorage.setItem("token", token);
      const from = location.state?.from?.pathname || "/chat";
      navigate(from, { replace: true });
      return;
    }

    if (errorParam) {
      setError(decodeURIComponent(errorParam));
    }
  }, [location, navigate]);

  // Load OAuth providers
  useEffect(() => {
    const loadProviders = async () => {
      try {
        setLoading(true);
        const response = await authApi.getProviders();
        setProviders(response.data?.providers || response?.providers || []);
      } catch (err) {
        console.error("Failed to load providers:", err);
        setError("Failed to load authentication providers");
      } finally {
        setLoading(false);
      }
    };

    loadProviders();
  }, []);

  // Handle OAuth login
  const handleOAuthLogin = async (provider) => {
    try {
      setError(null);
      setLoading(true);

      const baseUrl =
        import.meta.env.VITE_API_URL || "http://localhost:8001/api/v1";
      const response = await fetch(`${baseUrl}/auth/login/${provider}`, {
        method: "GET",
        credentials: "include",
        headers: { Accept: "application/json" },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const data = await response.json();
      if (data.auth_url) {
        window.location.href = data.auth_url;
      } else {
        throw new Error("Authorization URL not received");
      }
    } catch (err) {
      console.error("OAuth login error:", err);
      setError(`Failed to login with ${provider}`);
      setLoading(false);
    }
  };

  // Get icon for provider
  const getProviderIcon = (providerName) => {
    switch (providerName.toLowerCase()) {
      case "google":
        return <GoogleIcon />;
      case "github":
        return <GitHubIcon />;
      default:
        return null;
    }
  };

  return (
    <Box
      sx={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        minHeight: "70vh",
      }}
    >
      <Card sx={{ maxWidth: 400, width: "100%" }}>
        <CardContent>
          <Typography variant="h4" component="h1" gutterBottom align="center">
            Welcome
          </Typography>
          <Typography
            variant="body1"
            color="text.secondary"
            align="center"
            sx={{ mb: 3 }}
          >
            Please sign in to access the Knowledge Assistant
          </Typography>

          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          {loading ? (
            <Box sx={{ display: "flex", justifyContent: "center", py: 3 }}>
              <CircularProgress />
            </Box>
          ) : (
            <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
              {providers.map((provider) => (
                <Button
                  key={provider.name}
                  variant="contained"
                  fullWidth
                  size="large"
                  startIcon={getProviderIcon(provider.name)}
                  onClick={() => handleOAuthLogin(provider.name)}
                  disabled={loading}
                >
                  Sign in with {provider.display_name}
                </Button>
              ))}
            </Box>
          )}
        </CardContent>
      </Card>
    </Box>
  );
}
