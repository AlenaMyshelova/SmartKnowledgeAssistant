import { useEffect, useState } from "react";
import { useNavigate, useLocation, useSearchParams } from "react-router-dom"; // Добавили useSearchParams
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
  const [searchParams] = useSearchParams(); // Добавили для более удобной работы с query params

  // Handle OAuth callback and errors from URL
  useEffect(() => {
    // Проверяем токен
    const token = searchParams.get("token");
    if (token) {
      // Save token and redirect to protected route
      localStorage.setItem("token", token);
      const from = location.state?.from?.pathname || "/";
      navigate(from, { replace: true });
      return;
    }

    // Проверяем ошибку
    const errorParam = searchParams.get("error");
    if (errorParam) {
      setError(decodeURIComponent(errorParam));
      // Очищаем URL от параметра error для чистоты
      searchParams.delete("error");
      navigate({ search: searchParams.toString() }, { replace: true });
    }
  }, [searchParams, location.state, navigate]);

  // Load OAuth providers
  useEffect(() => {
    const loadProviders = async () => {
      try {
        setLoading(true);
        const response = await authApi.getProviders();
        const providersList =
          response.data?.providers || response?.providers || [];

        // Логирование для отладки
        console.log("Loaded providers:", providersList);

        setProviders(providersList);
      } catch (err) {
        console.error("Failed to load providers:", err);
        setError("Failed to load authentication providers");
      } finally {
        setLoading(false);
      }
    };

    loadProviders();
  }, []);

  // Handle OAuth login - упрощенная версия с прямым редиректом
  const handleOAuthLogin = (provider) => {
    try {
      setError(null); // Очищаем предыдущие ошибки
      setLoading(true); // Показываем индикатор загрузки

      const baseUrl =
        import.meta.env.VITE_API_URL || "http://localhost:8001/api/v1";

      // Логирование для отладки
      console.log(`Redirecting to OAuth provider: ${provider}`);
      console.log(`OAuth URL: ${baseUrl}/auth/login/${provider}`);

      window.location.href = `${baseUrl}/auth/login/${provider}`;
    } catch (err) {
      console.error("OAuth login error:", err);
      setError(`Failed to login with ${provider}`);
      setLoading(false); // Убираем индикатор загрузки при ошибке
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

  // Clear error after 10 seconds
  useEffect(() => {
    if (error) {
      const timer = setTimeout(() => {
        setError(null);
      }, 10000);
      return () => clearTimeout(timer);
    }
  }, [error]);

  return (
    <Box
      sx={{
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        minHeight: "100vh",
        background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",

        //        // 2. Закат:
        //   // background: "linear-gradient(135deg, #ff9a9e 0%, #fecfef 50%, #fecfef 100%)",

        //   // 3. Северное сияние:
        //   // background: "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)",

        //   // 4. Космос:
        //   // background: "linear-gradient(135deg, #1e3c72 0%, #2a5298 100%)",

        //   // 5. Элегантный серый:
        //   // background: "linear-gradient(135deg, #8e9eab 0%, #eef2f3 100%)",

        //   // 6. Фоновое изображение:
        //   // backgroundImage: "url('/path/to/your/image.jpg')",
        //   // backgroundSize: "cover",
        //   // backgroundPosition: "center",
      }}
    >
      <Card sx={{ maxWidth: 400, width: "100%", m: 2 }}>
        <CardContent sx={{ p: 4 }}>
          <Box sx={{ textAlign: "center", mb: 3 }}>
            <Typography
              variant="h4"
              component="h1"
              gutterBottom
              fontWeight="bold"
            >
              Welcome
            </Typography>
            <Typography variant="body1" color="text.secondary">
              Please sign in to access the Knowledge Assistant
            </Typography>
          </Box>

          {error && (
            <Alert
              severity="error"
              sx={{ mb: 2 }}
              onClose={() => setError(null)}
            >
              {error}
            </Alert>
          )}

          {loading ? (
            <Box sx={{ display: "flex", justifyContent: "center", py: 3 }}>
              <CircularProgress />
            </Box>
          ) : providers.length > 0 ? (
            <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
              {providers.map((provider) => (
                <Button
                  key={provider.name}
                  variant="contained"
                  fullWidth
                  size="large"
                  startIcon={getProviderIcon(provider.name)}
                  onClick={() => handleOAuthLogin(provider.name)}
                  sx={{
                    py: 1.5,
                    textTransform: "none",
                    fontSize: "1rem",
                    fontWeight: 500,
                    ...(provider.name.toLowerCase() === "google" && {
                      backgroundColor: "#4285f4",
                      "&:hover": {
                        backgroundColor: "#357ae8",
                      },
                    }),
                    ...(provider.name.toLowerCase() === "github" && {
                      backgroundColor: "#24292e",
                      "&:hover": {
                        backgroundColor: "#1a1d21",
                      },
                    }),
                  }}
                >
                  Sign in with {provider.display_name || provider.name}
                </Button>
              ))}
            </Box>
          ) : (
            <Alert severity="warning">
              No authentication providers available. Please check the backend
              configuration.
            </Alert>
          )}

          <Typography
            variant="caption"
            color="text.secondary"
            align="center"
            sx={{ mt: 3, display: "block" }}
          >
            By signing in, you agree to our Terms of Service and Privacy Policy
          </Typography>
        </CardContent>
      </Card>
    </Box>
  );
}

//        // 2. Закат:
//   // background: "linear-gradient(135deg, #ff9a9e 0%, #fecfef 50%, #fecfef 100%)",

//   // 3. Северное сияние:
//   // background: "linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)",

//   // 4. Космос:
//   // background: "linear-gradient(135deg, #1e3c72 0%, #2a5298 100%)",

//   // 5. Элегантный серый:
//   // background: "linear-gradient(135deg, #8e9eab 0%, #eef2f3 100%)",

//   // 6. Фоновое изображение:
//   // backgroundImage: "url('/path/to/your/image.jpg')",
//   // backgroundSize: "cover",
//   // backgroundPosition: "center",
