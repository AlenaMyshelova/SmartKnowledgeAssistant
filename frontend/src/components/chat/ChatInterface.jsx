import React, { useState, useEffect } from "react";
import {
  Container,
  Paper,
  Typography,
  Box,
  Snackbar,
  Alert,
  Divider,
} from "@mui/material";
import MessageList from "./MessageList";
import MessageInput from "./MessageInput";
import { chatApi } from "../../services/api";

// Главный компонент чат-интерфейса
const ChatInterface = () => {
  // Состояния
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [dataSources, setDataSources] = useState(["company_faqs"]);
  const [error, setError] = useState(null);

  // Загружаем доступные источники данных при первом рендере
  useEffect(() => {
    const fetchDataSources = async () => {
      try {
        const sources = await chatApi.getDataSources();
        if (sources) {
          // Извлекаем названия источников данных
          const sourceNames = Object.keys(sources);
          setDataSources(
            sourceNames.length > 0 ? sourceNames : ["company_faqs"]
          );
        }
      } catch (err) {
        console.error("Failed to fetch data sources:", err);
        // В случае ошибки используем значение по умолчанию
      }
    };

    fetchDataSources();
  }, []);

  // Обработчик отправки сообщения
  const handleSendMessage = async (text, dataSource) => {
    // Добавляем сообщение пользователя в список
    const userMessage = { text, isUser: true };
    setMessages((prevMessages) => [...prevMessages, userMessage]);

    // Устанавливаем состояние загрузки
    setLoading(true);

    try {
      // Отправляем запрос к API
      const response = await chatApi.sendMessage(text, dataSource);

      // Добавляем ответ ассистента в список сообщений
      const assistantMessage = {
        text: response.response,
        isUser: false,
        data: response.relevant_data,
      };

      setMessages((prevMessages) => [...prevMessages, assistantMessage]);
    } catch (err) {
      console.error("Error sending message:", err);
      setError(
        "Ошибка при отправке сообщения. Пожалуйста, попробуйте еще раз."
      );
    } finally {
      // Снимаем состояние загрузки
      setLoading(false);
    }
  };

  // Закрытие уведомления об ошибке
  const handleCloseError = () => {
    setError(null);
  };

  return (
    <Container maxWidth="md" sx={{ mt: 4, mb: 4 }}>
      <Paper
        elevation={3}
        sx={{
          height: "80vh",
          display: "flex",
          flexDirection: "column",
          borderRadius: 2,
          overflow: "hidden",
        }}
      >
        {/* Заголовок */}
        <Box
          sx={{
            p: 2,
            backgroundColor: "primary.main",
            color: "white",
          }}
        >
          <Typography variant="h6">Smart Knowledge Assistant</Typography>
          <Typography variant="caption">
            Задайте вопрос о компании TechNova
          </Typography>
        </Box>

        <Divider />

        {/* Список сообщений */}
        <MessageList messages={messages} loading={loading} />

        <Divider />

        {/* Поле ввода сообщения */}
        <Box sx={{ p: 2, backgroundColor: "background.default" }}>
          <MessageInput
            onSendMessage={handleSendMessage}
            dataSources={dataSources}
          />
        </Box>
      </Paper>

      {/* Уведомление об ошибке */}
      <Snackbar
        open={!!error}
        autoHideDuration={6000}
        onClose={handleCloseError}
      >
        <Alert
          onClose={handleCloseError}
          severity="error"
          sx={{ width: "100%" }}
        >
          {error}
        </Alert>
      </Snackbar>
    </Container>
  );
};

export default ChatInterface;
