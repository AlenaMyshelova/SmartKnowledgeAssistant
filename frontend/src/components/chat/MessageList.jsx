import React, { useRef, useEffect } from "react";
import { Box, CircularProgress, Typography } from "@mui/material";
import Message from "./Message";

// Компонент для отображения списка сообщений
const MessageList = ({ messages, loading }) => {
  // Ref для автоматической прокрутки вниз при новых сообщениях
  const messagesEndRef = useRef(null);

  // Автоматическая прокрутка при получении новых сообщений
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  return (
    <Box
      sx={{
        flexGrow: 1,
        overflowY: "auto",
        p: 2,
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Если нет сообщений, показываем приветствие */}
      {messages.length === 0 && !loading && (
        <Box
          sx={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            height: "100%",
            opacity: 0.7,
          }}
        >
          <Typography variant="h6" color="textSecondary" align="center">
            Hi! Я Smart Knowledge Assistant.
          </Typography>
          <Typography variant="body1" color="textSecondary" align="center">
            Задайте мне вопрос о компании TechNova.
          </Typography>
        </Box>
      )}

      {/* Отображаем все сообщения */}
      {messages.map((msg, index) => (
        <Message key={index} message={msg.text} isUser={msg.isUser} />
      ))}

      {/* Индикатор загрузки при ожидании ответа */}
      {loading && (
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            my: 2,
          }}
        >
          <CircularProgress size={20} sx={{ mr: 2 }} />
          <Typography variant="body2" color="textSecondary">
            Генерирую ответ...
          </Typography>
        </Box>
      )}

      {/* Элемент для автоматической прокрутки */}
      <div ref={messagesEndRef} />
    </Box>
  );
};

export default MessageList;
