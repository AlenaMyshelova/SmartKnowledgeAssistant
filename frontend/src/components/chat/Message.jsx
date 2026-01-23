import React from "react";
import { Paper, Typography, Box, Chip } from "@mui/material";
import PersonIcon from "@mui/icons-material/Person";
import SmartToyIcon from "@mui/icons-material/SmartToy";

// component for displaying a single message
const Message = ({ message, isUser }) => {
  return (
    <Box
      sx={{
        display: "flex",
        justifyContent: isUser ? "flex-end" : "flex-start",
        mb: 2,
      }}
    >
      {/* Avatar (icon) */}
      <Box
        sx={{
          display: "flex",
          alignItems: "flex-start",
          mr: isUser ? 1 : 0,
          ml: isUser ? 0 : 1,
          order: isUser ? 1 : 0,
        }}
      >
        <Chip
          icon={isUser ? <PersonIcon /> : <SmartToyIcon />}
          label={isUser ? "You" : "Assistant"}
          color={isUser ? "primary" : "secondary"}
          size="small"
          sx={{ height: 24 }}
        />
      </Box>

      {/* Сообщение */}
      <Paper
        elevation={1}
        sx={{
          p: 2,
          maxWidth: "70%",
          backgroundColor: isUser ? "#e3f2fd" : "#f5f5f5",
          borderRadius: 2,
        }}
      >
        <Typography variant="body1">{message}</Typography>
      </Paper>
    </Box>
  );
};

export default Message;
