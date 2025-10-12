import React, { useState, useEffect } from "react";
import {
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
    <Box
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        p: 2,
      }}
    >
      <Paper
        elevation={3}
        sx={{
          flexGrow: 1,
          display: "flex",
          flexDirection: "column",
          borderRadius: 2,
          overflow: "hidden",
          maxWidth: "900px",
          width: "100%",
          mx: "auto",
        }}
      >
        {/* Мини-заголовок чата (опционально, можно удалить если не нужен) */}
        <Box
          sx={{
            p: 1.5,
            backgroundColor: "grey.50",
            borderBottom: "1px solid",
            borderColor: "divider",
          }}
        >
          <Typography variant="body2" color="text.secondary">
            Задайте вопрос о компании TechNova
          </Typography>
        </Box>

        {/* Список сообщений */}
        <Box sx={{ flexGrow: 1, overflow: "hidden" }}>
          <MessageList messages={messages} loading={loading} />
        </Box>

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
        anchorOrigin={{ vertical: "top", horizontal: "center" }}
      >
        <Alert
          onClose={handleCloseError}
          severity="error"
          sx={{ width: "100%" }}
        >
          {error}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default ChatInterface;
