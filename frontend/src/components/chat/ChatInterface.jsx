import React, { useState, useEffect, useRef } from "react";
import {
  Box,
  Paper,
  Typography,
  IconButton,
  Chip,
  Tooltip,
  Fade,
  CircularProgress,
  Divider,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Stack,
  alpha,
} from "@mui/material";
import {
  VisibilityOff as IncognitoIcon,
  Visibility as NormalIcon,
  ContentCopy as CopyIcon,
  ThumbUp as ThumbUpIcon,
  ThumbDown as ThumbDownIcon,
  ExpandMore as ExpandMoreIcon,
  Source as SourceIcon,
  VolumeUp as VolumeUpIcon,
  Refresh as RefreshIcon,
} from "@mui/icons-material";
import { useParams, useNavigate } from "react-router-dom";
import { useChat } from "../../contexts/ChatContext";
import { useSnackbar } from "notistack";
import MessageInput from "./MessageInput";
import { format } from "date-fns";

const ChatInterface = () => {
  const { chatId } = useParams();
  const navigate = useNavigate();
  const { enqueueSnackbar } = useSnackbar();
  const {
    messages,
    currentChat,
    isIncognito,
    loading,
    sendMessage,
    loadChatHistory,
    createNewChat,
    setMessages,
    toggleIncognito,
  } = useChat();

  const [showSources, setShowSources] = useState({});
  const [isSending, setIsSending] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    if (chatId) {
      const parsedChatId = parseInt(chatId);
      // Загружаем историю только если это другой чат
      if (!currentChat || currentChat.id !== parsedChatId) {
        console.log("Loading chat history for:", parsedChatId);
        loadChatHistory(parsedChatId);
      }
    } else {
      // Если мы на /chat без ID
      if (currentChat && currentChat.id > 0 && !isIncognito) {
        // Есть текущий чат - переходим на него
        console.log("Redirecting to current chat:", currentChat.id);
        navigate(`/chat/${currentChat.id}`, { replace: true });
      } else {
        // Нет текущего чата - очищаем сообщения
        console.log("Clearing messages - no current chat");
        setMessages([]);
      }
    }
  }, [chatId]); // ВАЖНО: убираем лишние зависимости!

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const handleSendMessage = async (message, dataSource) => {
    setIsSending(true);

    try {
      // НЕ создаем новый чат здесь - sendMessage сделает это сам
      await sendMessage(message, dataSource);

      if (isIncognito) {
        enqueueSnackbar("🔒 Message sent in incognito mode (not saved)", {
          variant: "info",
        });
      }
    } catch (error) {
      enqueueSnackbar("Failed to send message. Please try again.", {
        variant: "error",
      });
    } finally {
      setIsSending(false);
    }
  };

  const handleCopyMessage = (content) => {
    navigator.clipboard.writeText(content);
    enqueueSnackbar("Message copied to clipboard", {
      variant: "success",
    });
  };

  const handleMessageAction = (action, message) => {
    switch (action) {
      case "copy":
        handleCopyMessage(message.content);
        break;
      case "feedback-positive":
        enqueueSnackbar("Thank you for your feedback!", {
          variant: "success",
        });
        break;
      case "feedback-negative":
        enqueueSnackbar("Thank you for your feedback. We'll improve!", {
          variant: "info",
        });
        break;
      case "regenerate":
        if (message.role === "assistant") {
          const lastUserMessage = messages
            .slice(0, messages.indexOf(message))
            .reverse()
            .find((m) => m.role === "user");
          if (lastUserMessage) {
            handleSendMessage(lastUserMessage.content, "company_faqs");
          }
        }
        break;
      case "tts":
        const utterance = new SpeechSynthesisUtterance(message.content);
        speechSynthesis.speak(utterance);
        break;
    }
  };

  const toggleSourcesForMessage = (messageId) => {
    setShowSources((prev) => ({
      ...prev,
      [messageId]: !prev[messageId],
    }));
  };

  const renderMessage = (message, index) => {
    const isUser = message.role === "user";
    const isShowingSources = showSources[message.id];

    return (
      <Fade in key={message.id || index} timeout={300}>
        <Box
          sx={{
            display: "flex",
            justifyContent: isUser ? "flex-end" : "flex-start",
            mb: 2,
            px: 2,
          }}
        >
          <Paper
            elevation={1}
            sx={{
              maxWidth: "70%",
              p: 2,
              backgroundColor: isUser ? "primary.main" : "background.paper",
              color: isUser ? "white" : "text.primary",
              borderRadius: 2,
              position: "relative",
            }}
          >
            {/* Message Header */}
            <Box sx={{ display: "flex", alignItems: "center", mb: 1 }}>
              <Typography variant="caption" sx={{ fontWeight: 600 }}>
                {isUser ? "You" : "Assistant"}
              </Typography>
              <Typography variant="caption" sx={{ ml: 1, opacity: 0.7 }}>
                {message.timestamp
                  ? format(new Date(message.timestamp), "HH:mm")
                  : ""}
              </Typography>

              {/* Action buttons */}
              <Box sx={{ ml: "auto", display: "flex", gap: 0.5 }}>
                <Tooltip title="Copy">
                  <IconButton
                    size="small"
                    onClick={() => handleCopyMessage(message.content)}
                    sx={{
                      color: isUser ? "white" : "text.secondary",
                      opacity: 0.7,
                      "&:hover": { opacity: 1 },
                    }}
                  >
                    <CopyIcon fontSize="small" />
                  </IconButton>
                </Tooltip>

                {!isUser && (
                  <>
                    <Tooltip title="Text to speech">
                      <IconButton
                        size="small"
                        onClick={() => handleMessageAction("tts", message)}
                        sx={{
                          color: "text.secondary",
                          opacity: 0.7,
                          "&:hover": { opacity: 1 },
                        }}
                      >
                        <VolumeUpIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Regenerate">
                      <IconButton
                        size="small"
                        onClick={() =>
                          handleMessageAction("regenerate", message)
                        }
                        sx={{
                          color: "text.secondary",
                          opacity: 0.7,
                          "&:hover": { opacity: 1 },
                        }}
                      >
                        <RefreshIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </>
                )}
              </Box>
            </Box>

            {/* Message Content */}
            <Typography
              variant="body1"
              sx={{
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
              }}
            >
              {message.content}
            </Typography>

            {/* Feedback buttons for assistant messages */}
            {!isUser && (
              <Box sx={{ display: "flex", gap: 1, mt: 1.5 }}>
                <Tooltip title="Helpful">
                  <IconButton
                    size="small"
                    onClick={() =>
                      handleMessageAction("feedback-positive", message)
                    }
                    sx={{ opacity: 0.6, "&:hover": { opacity: 1 } }}
                  >
                    <ThumbUpIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
                <Tooltip title="Not helpful">
                  <IconButton
                    size="small"
                    onClick={() =>
                      handleMessageAction("feedback-negative", message)
                    }
                    sx={{ opacity: 0.6, "&:hover": { opacity: 1 } }}
                  >
                    <ThumbDownIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              </Box>
            )}
          </Paper>
        </Box>
      </Fade>
    );
  };

  return (
    <Box sx={{ height: "100vh", display: "flex", flexDirection: "column" }}>
      {/* Chat Header */}
      <Paper
        elevation={0}
        sx={{
          p: 2,
          borderBottom: 1,
          borderColor: "divider",
          backgroundColor: "background.paper",
          flexShrink: 0,
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            {currentChat?.title || "New Chat"}
          </Typography>

          {/* Incognito Badge */}
          {isIncognito && (
            <Chip
              icon={<IncognitoIcon />}
              label="Incognito Mode"
              color="warning"
              variant="outlined"
              size="small"
            />
          )}

          {/* Message Count */}
          {currentChat && (
            <Chip
              label={`${messages.length} messages`}
              size="small"
              variant="outlined"
            />
          )}

          {/* Toggle Incognito */}
          <Tooltip
            title={
              isIncognito ? "Switch to normal mode" : "Switch to incognito mode"
            }
          >
            <IconButton
              onClick={toggleIncognito}
              color={isIncognito ? "warning" : "default"}
            >
              {isIncognito ? <IncognitoIcon /> : <NormalIcon />}
            </IconButton>
          </Tooltip>
        </Box>
      </Paper>

      {/* Messages Area */}
      <Box
        sx={{
          flexGrow: 1, // Занимает всё доступное пространство
          overflow: "auto",
          backgroundColor: "background.default",
          display: "flex",
          flexDirection: "column",
          minHeight: 0, // Важно для правильной работы flexbox
        }}
      >
        {/* Внутренний контейнер для контента */}
        <Box
          sx={{
            flexGrow: 1,
            display: "flex",
            flexDirection: "column",
            py: 2,
          }}
        >
          {loading && (
            <Box sx={{ display: "flex", justifyContent: "center", p: 3 }}>
              <CircularProgress />
            </Box>
          )}

          {!loading && messages.length === 0 && (
            <Box
              sx={{
                textAlign: "center",
                p: 4,
                flexGrow: 1, // Центрирует контент по вертикали
                display: "flex",
                flexDirection: "column",
                justifyContent: "center",
              }}
            >
              <Typography variant="h5" color="text.secondary" gutterBottom>
                Start a conversation
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {isIncognito
                  ? "🔒 Your messages won't be saved in incognito mode"
                  : "Ask me anything about your company policies and procedures"}
              </Typography>

              {/* Suggested prompts */}
              <Box
                sx={{
                  mt: 3,
                  display: "flex",
                  flexWrap: "wrap",
                  gap: 1,
                  justifyContent: "center",
                }}
              >
                {[
                  "What products does TechNova offer?",
                  "How do I reset my NovaCRM password?",
                  "How much is the NovaDocs Pro plan?",
                  "Does NovaMeet have mobile apps?",
                ].map((prompt) => (
                  <Chip
                    key={prompt}
                    label={prompt}
                    onClick={() => handleSendMessage(prompt, "company_faqs")}
                    sx={{ cursor: "pointer" }}
                  />
                ))}
              </Box>
            </Box>
          )}

          {/* Render Messages */}
          {messages.map((message, index) => renderMessage(message, index))}

          {/* Loading indicator for sending */}
          {isSending && (
            <Box
              sx={{
                display: "flex",
                justifyContent: "flex-start",
                px: 2,
                mb: 2,
              }}
            >
              <Paper
                elevation={1}
                sx={{ p: 2, backgroundColor: "background.paper" }}
              >
                <Box sx={{ display: "flex", gap: 1 }}>
                  <CircularProgress size={16} />
                  <Typography variant="body2" color="text.secondary">
                    Assistant is typing...
                  </Typography>
                </Box>
              </Paper>
            </Box>
          )}

          <div ref={messagesEndRef} />
        </Box>
      </Box>

      {/* Input Area - Using your existing MessageInput component */}
      <Paper
        elevation={3}
        sx={{
          p: 2,
          borderTop: 1,
          borderColor: "divider",
          backgroundColor: "background.paper",
          flexShrink: 0,
        }}
      >
        <MessageInput
          onSendMessage={handleSendMessage}
          dataSources={["company_faqs"]}
        />
      </Paper>
    </Box>
  );
};

export default ChatInterface;
