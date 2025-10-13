import React, { useState } from "react";
import {
  Paper,
  InputBase,
  IconButton,
  Divider,
  FormControl,
  Select,
  MenuItem,
  Box,
} from "@mui/material";
import SendIcon from "@mui/icons-material/Send";
import AudioRecorder from "./AudioRecorder";

// Component for message input with voice recording
const MessageInput = ({ onSendMessage, dataSources = ["company_faqs"] }) => {
  // Component states
  const [message, setMessage] = useState("");
  const [dataSource, setDataSource] = useState("company_faqs");
  const [isProcessing, setIsProcessing] = useState(false);

  // Handle message send
  const handleSend = () => {
    if (message.trim() && !isProcessing) {
      onSendMessage(message, dataSource);
      setMessage(""); // Clear input after sending
    }
  };

  // Handle Enter key press
  const handleKeyPress = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Handle transcription completion from voice input
  const handleTranscriptionComplete = (transcribedText) => {
    setMessage(transcribedText);
    // Auto-focus on text field after transcription
    setTimeout(() => {
      document.querySelector("#message-input-field")?.focus();
    }, 100);
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
        borderRadius: 2,
        bgcolor: "background.paper",
      }}
    >
      {/* Data source selector */}
      <FormControl variant="standard" sx={{ minWidth: 120, mx: 1 }}>
        <Select
          value={dataSource}
          onChange={(e) => setDataSource(e.target.value)}
          sx={{ fontSize: "0.875rem" }}
          disabled={isProcessing}
        >
          {dataSources.map((source) => (
            <MenuItem key={source} value={source}>
              {source}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      <Divider sx={{ height: 28, m: 0.5 }} orientation="vertical" />

      {/* Message input field */}
      <InputBase
        id="message-input-field"
        sx={{ ml: 1, flex: 1 }}
        placeholder={
          isProcessing
            ? "Processing voice..."
            : "Type your question or use voice..."
        }
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        onKeyPress={handleKeyPress}
        multiline
        maxRows={4}
        disabled={isProcessing}
      />

      {/* Voice recorder component */}
      <Box sx={{ display: "flex", alignItems: "center", mx: 1 }}>
        <AudioRecorder
          onTranscriptionComplete={handleTranscriptionComplete}
          isProcessing={isProcessing}
          setIsProcessing={setIsProcessing}
        />
      </Box>

      <Divider sx={{ height: 28, m: 0.5 }} orientation="vertical" />

      {/* Send button */}
      <IconButton
        color="primary"
        sx={{
          p: "10px",
          "&:hover": {
            bgcolor: "primary.light",
            color: "white",
          },
          transition: "all 0.3s ease",
        }}
        onClick={handleSend}
        disabled={!message.trim() || isProcessing}
      >
        <SendIcon />
      </IconButton>
    </Paper>
  );
};

export default MessageInput;
