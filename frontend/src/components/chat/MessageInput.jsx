import React, { useState } from "react";
import {
  Paper,
  InputBase,
  IconButton,
  Divider,
  FormControl,
  Select,
  MenuItem,
} from "@mui/material";
import SendIcon from "@mui/icons-material/Send";

// Компонент для ввода сообщений
const MessageInput = ({ onSendMessage, dataSources = ["company_faqs"] }) => {
  // Состояния компонента
  const [message, setMessage] = useState("");
  const [dataSource, setDataSource] = useState("company_faqs");

  // Обработчик отправки сообщения
  const handleSend = () => {
    if (message.trim()) {
      onSendMessage(message, dataSource);
      setMessage(""); // Очищаем поле ввода после отправки
    }
  };

  // Обработчик нажатия клавиши Enter
  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <Paper
      elevation={2}
      sx={{
        p: "2px 4px",
        display: "flex",
        alignItems: "center",
        width: "100%",
        mb: 2,
      }}
    >
      {/* Селектор источника данных */}
      <FormControl variant="standard" sx={{ minWidth: 120, mx: 1 }}>
        <Select
          value={dataSource}
          onChange={(e) => setDataSource(e.target.value)}
          sx={{ fontSize: "0.875rem" }}
        >
          {dataSources.map((source) => (
            <MenuItem key={source} value={source}>
              {source}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      <Divider sx={{ height: 28, m: 0.5 }} orientation="vertical" />

      {/* Поле ввода сообщения */}
      <InputBase
        sx={{ ml: 1, flex: 1 }}
        placeholder="Введите ваш вопрос..."
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        onKeyPress={handleKeyPress}
        multiline
        maxRows={4}
      />

      {/* Кнопка отправки */}
      <IconButton
        color="primary"
        sx={{ p: "10px" }}
        onClick={handleSend}
        disabled={!message.trim()}
      >
        <SendIcon />
      </IconButton>
    </Paper>
  );
};

export default MessageInput;
