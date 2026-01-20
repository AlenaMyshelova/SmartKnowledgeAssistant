import React, { useState, useEffect } from "react";
import { useReactMediaRecorder } from "react-media-recorder";
import { motion, AnimatePresence } from "framer-motion";
import {
  Box,
  IconButton,
  Tooltip,
  CircularProgress,
  Typography,
  Paper,
  Chip,
  Fade,
  Zoom,
} from "@mui/material";
import MicIcon from "@mui/icons-material/Mic";
import StopIcon from "@mui/icons-material/Stop";
import DeleteIcon from "@mui/icons-material/Delete";
import SendIcon from "@mui/icons-material/Send";
import GraphicEqIcon from "@mui/icons-material/GraphicEq";
import MicOffIcon from "@mui/icons-material/MicOff";
import { red, green, blue, orange } from "@mui/material/colors";

const AudioRecorder = ({
  onTranscriptionComplete,
  isProcessing,
  setIsProcessing,
}) => {
  const [error, setError] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  const [recordingDuration, setRecordingDuration] = useState(0);
  const [showControls, setShowControls] = useState(false);

  // Media recorder setup
  const { status, startRecording, stopRecording, mediaBlobUrl, clearBlobUrl } =
    useReactMediaRecorder({
      audio: true,
      video: false,
      mediaRecorderOptions: {
        mimeType: "audio/webm",
      },
      onStart: () => {
        setShowControls(true);
        setError(null);
      },
      onStop: () => {
        setRecordingDuration(0);
      },
      onError: (err) => {
        setError(`Recording error: ${err.message}`);
        setIsProcessing(false);
        setShowControls(false);
      },
    });

  // Timer for recording duration
  useEffect(() => {
    let interval;
    if (status === "recording") {
      interval = setInterval(() => {
        setRecordingDuration((prev) => prev + 1);
      }, 1000);
    } else {
      setRecordingDuration(0);
    }
    return () => clearInterval(interval);
  }, [status]);

  // Format duration display
  const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  // Handle audio transcription
  const handleSubmitAudio = async () => {
    if (!mediaBlobUrl || isUploading) return;

    try {
      setIsUploading(true);
      setIsProcessing(true);
      setError(null);

      // Get audio blob
      const response = await fetch(mediaBlobUrl);
      const audioBlob = await response.blob();

      // Create form data
      const formData = new FormData();
      formData.append("audio", audioBlob, "recording.webm");

      // Send to backend
      const transcriptionResponse = await fetch(
        "http://localhost:8000/api/v1/speech/transcribe",
        {
          method: "POST",
          body: formData,
        },
      );

      if (!transcriptionResponse.ok) {
        const errorData = await transcriptionResponse.json();
        throw new Error(errorData.detail || "Failed to transcribe audio");
      }

      const result = await transcriptionResponse.json();

      // Pass transcribed text to parent
      if (result.text && onTranscriptionComplete) {
        onTranscriptionComplete(result.text);
        setShowControls(false);
      } else {
        setError("No text was transcribed from your audio");
      }

      // Clear recording
      clearBlobUrl();
    } catch (err) {
      console.error("Transcription error:", err);
      setError(`Failed: ${err.message}`);
    } finally {
      setIsUploading(false);
      setIsProcessing(false);
    }
  };

  // Reset recording
  const handleReset = () => {
    clearBlobUrl();
    setError(null);
    setShowControls(false);
    setRecordingDuration(0);
  };

  // Pulse animation for recording
  const pulseAnimation = {
    scale: [1, 1.2, 1],
    transition: {
      duration: 1.5,
      repeat: Infinity,
      ease: "easeInOut",
    },
  };

  // Wave animation for visualizer
  const waveAnimation = {
    scale: [1, 1.3, 1],
    opacity: [0.7, 1, 0.7],
    transition: {
      duration: 1,
      repeat: Infinity,
      ease: "easeInOut",
      repeatType: "reverse",
    },
  };

  return (
    <Box sx={{ display: "flex", alignItems: "center", position: "relative" }}>
      {/* Main mic button with animation */}
      <AnimatePresence>
        {!showControls && (
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            exit={{ scale: 0 }}
            transition={{ type: "spring", stiffness: 200 }}
          >
            <Tooltip title="Start voice recording" placement="top">
              <IconButton
                onClick={startRecording}
                disabled={isProcessing}
                sx={{
                  position: "relative",
                  color: blue[600],
                  "&:hover": {
                    bgcolor: blue[50],
                    transform: "scale(1.1)",
                  },
                  transition: "all 0.3s ease",
                }}
              >
                <MicIcon fontSize="medium" />
              </IconButton>
            </Tooltip>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Recording controls panel */}
      <AnimatePresence>
        {showControls && (
          <motion.div
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: "auto", opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.3 }}
          >
            <Paper
              elevation={3}
              sx={{
                display: "flex",
                alignItems: "center",
                gap: 1,
                p: 1,
                borderRadius: 3,
                background:
                  status === "recording"
                    ? `linear-gradient(135deg, ${red[50]} 0%, ${orange[50]} 100%)`
                    : "background.paper",
                border:
                  status === "recording" ? `2px solid ${red[300]}` : "none",
              }}
            >
              {/* Recording indicator */}
              {status === "recording" && (
                <Box sx={{ display: "flex", alignItems: "center", mr: 1 }}>
                  <motion.div animate={pulseAnimation}>
                    <Box
                      sx={{
                        width: 12,
                        height: 12,
                        borderRadius: "50%",
                        bgcolor: red[500],
                        mr: 1,
                      }}
                    />
                  </motion.div>

                  {/* Visualizer bars */}
                  <Box sx={{ display: "flex", gap: 0.3, mr: 1 }}>
                    {[1, 2, 3, 4, 5].map((i) => (
                      <motion.div
                        key={i}
                        animate={waveAnimation}
                        transition={{ delay: i * 0.1 }}
                      >
                        <Box
                          sx={{
                            width: 3,
                            height: 20,
                            bgcolor: red[400],
                            borderRadius: 1,
                          }}
                        />
                      </motion.div>
                    ))}
                  </Box>

                  {/* Duration display */}
                  <Chip
                    label={formatDuration(recordingDuration)}
                    size="small"
                    color="error"
                    variant="outlined"
                  />
                </Box>
              )}

              {/* Stop button */}
              {status === "recording" && (
                <Zoom in={true}>
                  <Tooltip title="Stop recording">
                    <IconButton
                      onClick={stopRecording}
                      sx={{
                        color: red[600],
                        "&:hover": {
                          bgcolor: red[100],
                        },
                      }}
                    >
                      <StopIcon />
                    </IconButton>
                  </Tooltip>
                </Zoom>
              )}

              {/* Delete button */}
              {mediaBlobUrl && status !== "recording" && (
                <Zoom in={true} style={{ transitionDelay: "100ms" }}>
                  <Tooltip title="Delete recording">
                    <IconButton
                      onClick={handleReset}
                      disabled={isUploading}
                      sx={{
                        color: orange[600],
                        "&:hover": {
                          bgcolor: orange[100],
                        },
                      }}
                    >
                      <DeleteIcon />
                    </IconButton>
                  </Tooltip>
                </Zoom>
              )}

              {/* Send button */}
              {mediaBlobUrl && status !== "recording" && (
                <Zoom in={true} style={{ transitionDelay: "200ms" }}>
                  <Tooltip title="Send for transcription">
                    <IconButton
                      onClick={handleSubmitAudio}
                      disabled={isUploading}
                      sx={{
                        color: green[600],
                        "&:hover": {
                          bgcolor: green[100],
                        },
                      }}
                    >
                      {isUploading ? (
                        <CircularProgress size={24} color="inherit" />
                      ) : (
                        <SendIcon />
                      )}
                    </IconButton>
                  </Tooltip>
                </Zoom>
              )}

              {/* Status text */}
              {(isUploading || mediaBlobUrl) && status !== "recording" && (
                <Fade in={true}>
                  <Typography
                    variant="caption"
                    sx={{
                      ml: 1,
                      color: isUploading ? blue[600] : green[600],
                      fontWeight: 500,
                    }}
                  >
                    {isUploading ? "Transcribing..." : "Ready to send"}
                  </Typography>
                </Fade>
              )}
            </Paper>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Error display */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            style={{
              position: "absolute",
              bottom: "100%",
              left: "50%",
              transform: "translateX(-50%)",
              marginBottom: 8,
            }}
          >
            <Paper
              elevation={2}
              sx={{
                px: 2,
                py: 1,
                bgcolor: red[50],
                border: `1px solid ${red[200]}`,
                borderRadius: 2,
              }}
            >
              <Typography variant="caption" color="error">
                {error}
              </Typography>
            </Paper>
          </motion.div>
        )}
      </AnimatePresence>
    </Box>
  );
};

export default AudioRecorder;
