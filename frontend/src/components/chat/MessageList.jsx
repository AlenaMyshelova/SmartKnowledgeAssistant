import React, { useRef, useEffect } from "react";
import { Box, CircularProgress, Typography } from "@mui/material";
import Message from "./Message";

// Component for displaying the list of messages in the chat
const MessageList = ({ messages, loading }) => {
  // Ref for automatic scrolling to the bottom when new messages arrive
  const messagesEndRef = useRef(null);

  // Automatic scrolling when new messages arrive
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
      {/* If there are no messages, show a greeting */}
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
            Hi! I'm Smart Knowledge Assistant.
          </Typography>
          <Typography variant="body1" color="textSecondary" align="center">
            Ask me questions about TechNova.
          </Typography>
        </Box>
      )}

      {/* Display all messages */}
      {messages.map((msg, index) => (
        <Message key={index} message={msg.text} isUser={msg.isUser} />
      ))}

      {/* Loading indicator while waiting for a response */}
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

      {/* Element for automatic scrolling */}
      <div ref={messagesEndRef} />
    </Box>
  );
};

export default MessageList;
