import React, {
  useState,
  useEffect,
  useRef,
  useCallback,
  useMemo,
} from "react";
import {
  Box,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  IconButton,
  Typography,
  Button,
  Divider,
  TextField,
  InputAdornment,
  Chip,
  Menu,
  MenuItem,
  Switch,
  FormControlLabel,
  Tooltip,
  Collapse,
  Badge,
  Avatar,
  CircularProgress,
  Alert,
  AlertTitle,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Stack,
  alpha,
} from "@mui/material";
import {
  Add as AddIcon,
  Search as SearchIcon,
  ChatBubbleOutline as ChatIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  MoreVert as MoreIcon,
  Today as TodayIcon,
  DateRange as DateRangeIcon,
  History as HistoryIcon,
  Clear as ClearIcon,
  VisibilityOff as IncognitoIcon,
  Visibility as NormalIcon,
  FilterList as FilterIcon,
  ExpandLess,
  ExpandMore,
  Logout as LogoutIcon,
  BookmarkBorder as BookmarkIcon,
  Bookmark as BookmarkedIcon,
  FolderOpen as FolderIcon,
  Tag as TagIcon,
} from "@mui/icons-material";
import { useNavigate, useParams } from "react-router-dom";
import { useChat } from "../../contexts/ChatContext";
import { useAuth } from "../../contexts/AuthContext";
import {
  format,
  isToday,
  isYesterday,
  isThisWeek,
  parseISO,
  subDays,
} from "date-fns";
import { useSnackbar } from "notistack";
import InfiniteScroll from "react-infinite-scroll-component";

const Sidebar = ({ onClose }) => {
  const navigate = useNavigate();
  const { chatId } = useParams();
  const { user, logout } = useAuth();
  const { enqueueSnackbar, closeSnackbar } = useSnackbar();
  const {
    chats,
    loadChats,
    loadMoreChats,
    createNewChat,
    deleteChat,
    undoDelete,
    updateChat,
    searchQuery,
    setSearchQuery,
    searchResults,
    isSearching,
    isIncognito,
    toggleIncognito,
    clearIncognitoChats,
    hasMore,
    totalChats,
    filters,
    setFilters,
    savedFilters,
    saveFilter,
    deleteSavedFilter,
    applySavedFilter,
    deletedChats,
    loadChatHistory,
    currentChat,
    setCurrentChat,
    setMessages,
  } = useChat();

  const [selectedChat, setSelectedChat] = useState(null);
  const [anchorEl, setAnchorEl] = useState(null);
  const [filterMenuAnchor, setFilterMenuAnchor] = useState(null);
  const [expandedGroups, setExpandedGroups] = useState({
    pinned: true,
    today: true,
    yesterday: true,
    week: true,
    older: false,
  });
  const [renameDialog, setRenameDialog] = useState({
    open: false,
    chat: null,
    title: "",
  });
  const [filterDialog, setFilterDialog] = useState({
    open: false,
    name: "",
    config: {},
  });
  const scrollableNodeRef = useRef();

  // 🔥 ФИЛЬТРУЕМ incognito и пустые чаты
  const visibleChats = useMemo(() => {
    const chatList = searchQuery ? searchResults : chats;

    if (!chatList) return [];

    // Показываем только:
    // 1. Обычные чаты (НЕ incognito)
    // 2. С положительными ID
    // 3. С хотя бы одним сообщением
    return chatList.filter((chat) => {
      return (
        chat &&
        chat.id > 0 &&
        !chat.is_incognito &&
        chat.title !== "Incognito Chat" &&
        (chat.message_count > 0 || chat.last_message)
      );
    });
  }, [chats, searchResults, searchQuery]);

  // Handle chat deletion with undo
  const handleDeleteChat = async (chat) => {
    handleCloseMenu();

    const deleted = await deleteChat(chat.id);
    if (deleted) {
      const snackbarKey = enqueueSnackbar(
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <Typography variant="body2">Chat deleted</Typography>
          <Button
            size="small"
            color="inherit"
            onClick={() => {
              undoDelete(chat.id);
              closeSnackbar(snackbarKey);
              enqueueSnackbar("Chat restored", { variant: "success" });
            }}
          >
            UNDO
          </Button>
        </Box>,
        {
          variant: "info",
          autoHideDuration: 5000,
          action: (key) => (
            <IconButton size="small" onClick={() => closeSnackbar(key)}>
              <ClearIcon fontSize="small" />
            </IconButton>
          ),
        }
      );
    }

    if (chatId === String(chat.id)) {
      navigate("/chat");
    }
  };

  const handleRenameChat = async () => {
    if (renameDialog.title.trim() && renameDialog.chat) {
      await updateChat(renameDialog.chat.id, {
        title: renameDialog.title.trim(),
      });
      setRenameDialog({ open: false, chat: null, title: "" });
      enqueueSnackbar("Chat renamed", { variant: "success" });
    }
  };

  const handleNewChat = async () => {
    const newChatId = await createNewChat();
    navigate(`/chat/${newChatId}`);
    onClose?.();
  };

  const handleChatClick = (chat) => {
    // Загружаем историю чата при клике
    if (currentChat?.id !== chat.id) {
      setCurrentChat(chat);
      setMessages([]);
      loadChatHistory(chat.id);
    }
    navigate(`/chat/${chat.id}`);
    onClose?.();
  };

  const handleChatMenu = (event, chat) => {
    event.stopPropagation();
    setAnchorEl(event.currentTarget);
    setSelectedChat(chat);
  };

  const handleCloseMenu = () => {
    setAnchorEl(null);
    setSelectedChat(null);
  };

  const handleSaveFilter = () => {
    if (filterDialog.name.trim()) {
      saveFilter(filterDialog.name, {
        query: searchQuery,
        ...filters,
      });
      setFilterDialog({ open: false, name: "", config: {} });
      enqueueSnackbar("Filter saved", { variant: "success" });
    }
  };

  const toggleGroup = (group) => {
    setExpandedGroups((prev) => ({
      ...prev,
      [group]: !prev[group],
    }));
  };

  // Group chats by date - используем отфильтрованные чаты
  const groupChats = (chatList) => {
    const groups = {
      today: [],
      yesterday: [],
      week: [],
      older: [],
    };

    chatList.forEach((chat) => {
      try {
        const date = parseISO(chat.updated_at);
        if (isToday(date)) {
          groups.today.push(chat);
        } else if (isYesterday(date)) {
          groups.yesterday.push(chat);
        } else if (isThisWeek(date, { weekStartsOn: 1 })) {
          groups.week.push(chat);
        } else {
          groups.older.push(chat);
        }
      } catch {
        groups.older.push(chat);
      }
    });

    return groups;
  };

  const renderChatGroup = (title, chats, groupKey, icon) => {
    if (chats.length === 0) return null;

    return (
      <Box key={groupKey}>
        <ListItemButton
          onClick={() => toggleGroup(groupKey)}
          sx={{
            py: 0.5,
            px: 2,
            "&:hover": {
              backgroundColor: alpha("#fff", 0.05),
            },
          }}
        >
          <ListItemIcon sx={{ minWidth: 30, color: "inherit" }}>
            {icon}
          </ListItemIcon>
          <ListItemText
            primary={title}
            primaryTypographyProps={{
              variant: "caption",
              sx: { opacity: 0.7, fontWeight: 600 },
            }}
          />
          <Typography variant="caption" sx={{ opacity: 0.5 }}>
            {chats.length}
          </Typography>
          {expandedGroups[groupKey] ? <ExpandLess /> : <ExpandMore />}
        </ListItemButton>
        <Collapse in={expandedGroups[groupKey]} timeout="auto" unmountOnExit>
          <List disablePadding>
            {chats.map((chat) => (
              <ListItem
                key={chat.id}
                disablePadding
                secondaryAction={
                  <IconButton
                    edge="end"
                    size="small"
                    onClick={(e) => handleChatMenu(e, chat)}
                    sx={{
                      color: "inherit",
                      opacity: 0.5,
                      "&:hover": { opacity: 1 },
                    }}
                  >
                    <MoreIcon fontSize="small" />
                  </IconButton>
                }
                sx={{
                  backgroundColor:
                    chatId === String(chat.id) || currentChat?.id === chat.id
                      ? alpha("#fff", 0.1)
                      : "transparent",
                  "&:hover": {
                    backgroundColor: alpha("#fff", 0.05),
                  },
                }}
              >
                <ListItemButton
                  onClick={() => handleChatClick(chat)}
                  sx={{ py: 1, pl: 4 }}
                >
                  <ListItemIcon sx={{ minWidth: 30, color: "inherit" }}>
                    <ChatIcon fontSize="small" />
                  </ListItemIcon>
                  <ListItemText
                    primary={
                      <Box
                        sx={{ display: "flex", alignItems: "center", gap: 0.5 }}
                      >
                        <Typography variant="body2" noWrap sx={{ flex: 1 }}>
                          {chat.title}
                        </Typography>
                      </Box>
                    }
                    secondary={
                      chat.last_message && (
                        <Typography
                          variant="caption"
                          noWrap
                          sx={{ opacity: 0.5 }}
                        >
                          {chat.last_message}
                        </Typography>
                      )
                    }
                  />
                </ListItemButton>
              </ListItem>
            ))}
          </List>
        </Collapse>
      </Box>
    );
  };

  // Используем отфильтрованные чаты
  const groupedChats = groupChats(visibleChats);

  return (
    <Box
      sx={{
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        color: "white",
      }}
    >
      {/* Header */}
      <Box sx={{ p: 2 }}>
        <Button
          fullWidth
          variant="outlined"
          startIcon={<AddIcon />}
          onClick={handleNewChat}
          sx={{
            justifyContent: "flex-start",
            mb: 2,
            borderColor: alpha("#fff", 0.2),
            color: "white",
            "&:hover": {
              backgroundColor: alpha("#fff", 0.05),
              borderColor: alpha("#fff", 0.3),
            },
          }}
        >
          New chat
        </Button>

        {/* Incognito Toggle */}
        <FormControlLabel
          control={
            <Switch
              checked={isIncognito}
              onChange={toggleIncognito}
              size="small"
              sx={{
                "& .MuiSwitch-track": {
                  backgroundColor: alpha("#fff", 0.3),
                },
              }}
            />
          }
          label={
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
              {isIncognito ? (
                <IncognitoIcon fontSize="small" />
              ) : (
                <NormalIcon fontSize="small" />
              )}
              <Typography variant="body2">
                {isIncognito ? "Incognito" : "Normal"}
              </Typography>
            </Box>
          }
          sx={{ mb: 1 }}
        />

        {/* 🔥 Incognito Alert */}
        {isIncognito && (
          <Alert
            severity="info"
            sx={{
              mb: 2,
              backgroundColor: "rgba(33, 150, 243, 0.1)",
              color: "info.main",
            }}
          >
            <AlertTitle>Incognito Mode Active</AlertTitle>
            Messages will not be saved to history
          </Alert>
        )}

        {/* Search */}
        <TextField
          fullWidth
          size="small"
          placeholder="Search chats..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" />
              </InputAdornment>
            ),
            endAdornment: (
              <InputAdornment position="end">
                {searchQuery && (
                  <IconButton size="small" onClick={() => setSearchQuery("")}>
                    <ClearIcon fontSize="small" />
                  </IconButton>
                )}
                <IconButton
                  size="small"
                  onClick={(e) => setFilterMenuAnchor(e.currentTarget)}
                >
                  <FilterIcon fontSize="small" />
                </IconButton>
              </InputAdornment>
            ),
          }}
          sx={{
            "& .MuiOutlinedInput-root": {
              backgroundColor: alpha("#fff", 0.05),
              color: "white",
              "& fieldset": {
                borderColor: alpha("#fff", 0.2),
              },
              "&:hover fieldset": {
                borderColor: alpha("#fff", 0.3),
              },
            },
          }}
        />

        {/* Saved Filters */}
        {savedFilters.length > 0 && (
          <Box sx={{ mt: 1, display: "flex", gap: 0.5, flexWrap: "wrap" }}>
            {savedFilters.map((filter) => (
              <Chip
                key={filter.id}
                label={filter.name}
                size="small"
                onClick={() => applySavedFilter(filter)}
                onDelete={() => deleteSavedFilter(filter.id)}
                sx={{
                  backgroundColor: alpha("#fff", 0.1),
                  color: "white",
                  "&:hover": {
                    backgroundColor: alpha("#fff", 0.2),
                  },
                }}
              />
            ))}
          </Box>
        )}
      </Box>

      <Divider sx={{ borderColor: alpha("#fff", 0.1) }} />

      {/* Chat List with Infinite Scroll - ИСПРАВЛЕНО */}
      <Box
        ref={scrollableNodeRef}
        sx={{
          flexGrow: 1,
          overflow: "auto",
          "&::-webkit-scrollbar": {
            width: 8,
          },
          "&::-webkit-scrollbar-track": {
            backgroundColor: alpha("#fff", 0.05),
          },
          "&::-webkit-scrollbar-thumb": {
            backgroundColor: alpha("#fff", 0.2),
            borderRadius: 4,
          },
        }}
      >
        {isSearching ? (
          <Box sx={{ p: 3, textAlign: "center" }}>
            <CircularProgress size={30} sx={{ color: alpha("#fff", 0.5) }} />
          </Box>
        ) : (
          <>
            {visibleChats.length > 0 ? (
              <InfiniteScroll
                dataLength={visibleChats.length}
                next={loadMoreChats}
                hasMore={hasMore && !searchQuery && !isIncognito}
                loader={
                  hasMore && !searchQuery && !isIncognito ? (
                    <Box sx={{ p: 2, textAlign: "center" }}>
                      <CircularProgress
                        size={20}
                        sx={{ color: alpha("#fff", 0.5) }}
                      />
                    </Box>
                  ) : null
                }
                scrollableTarget={scrollableNodeRef.current}
                endMessage={
                  !hasMore && visibleChats.length > 0 ? (
                    <Box sx={{ p: 2, textAlign: "center" }}>
                      <Typography variant="caption" sx={{ opacity: 0.5 }}>
                        End of chat history
                      </Typography>
                    </Box>
                  ) : null
                }
              >
                <List disablePadding>
                  {renderChatGroup(
                    "Today",
                    groupedChats.today,
                    "today",
                    <TodayIcon fontSize="small" />
                  )}
                  {renderChatGroup(
                    "Yesterday",
                    groupedChats.yesterday,
                    "yesterday",
                    <DateRangeIcon fontSize="small" />
                  )}
                  {renderChatGroup(
                    "Last 7 days",
                    groupedChats.week,
                    "week",
                    <DateRangeIcon fontSize="small" />
                  )}
                  {renderChatGroup(
                    "Older",
                    groupedChats.older,
                    "older",
                    <HistoryIcon fontSize="small" />
                  )}
                </List>
              </InfiniteScroll>
            ) : (
              <Box sx={{ p: 3, textAlign: "center" }}>
                <Typography variant="body2" sx={{ opacity: 0.5 }}>
                  {searchQuery
                    ? "No results found"
                    : isIncognito
                    ? "Incognito chats are not saved"
                    : "No chats yet"}
                </Typography>
              </Box>
            )}
          </>
        )}

        {/* Deleted Chats Notice */}
        {deletedChats.length > 0 && (
          <Alert
            severity="info"
            sx={{ m: 2 }}
            action={
              <Button
                size="small"
                onClick={() =>
                  deletedChats.forEach((chat) => undoDelete(chat.id))
                }
              >
                Restore All
              </Button>
            }
          >
            {deletedChats.length} chat(s) pending deletion
          </Alert>
        )}
      </Box>

      <Divider sx={{ borderColor: alpha("#fff", 0.1) }} />

      {/* User Menu */}
      <Box sx={{ p: 2 }}>
        <ListItemButton
          sx={{
            borderRadius: 1,
            "&:hover": {
              backgroundColor: alpha("#fff", 0.05),
            },
          }}
        >
          <ListItemIcon>
            <Avatar src={user?.avatar_url} sx={{ width: 32, height: 32 }}>
              {user?.name?.[0]}
            </Avatar>
          </ListItemIcon>
          <ListItemText
            primary={user?.name}
            secondary={user?.email}
            primaryTypographyProps={{ fontSize: "0.875rem" }}
            secondaryTypographyProps={{
              fontSize: "0.75rem",
              sx: { opacity: 0.5 },
            }}
          />
          <IconButton size="small" onClick={logout} sx={{ color: "inherit" }}>
            <LogoutIcon fontSize="small" />
          </IconButton>
        </ListItemButton>

        {isIncognito && (
          <Button
            fullWidth
            size="small"
            onClick={clearIncognitoChats}
            sx={{
              mt: 1,
              color: "warning.main",
              "&:hover": {
                backgroundColor: alpha("#ff9800", 0.1),
              },
            }}
          >
            Clear Incognito Chats
          </Button>
        )}
      </Box>

      {/* Context Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleCloseMenu}
        PaperProps={{
          sx: {
            backgroundColor: "#2a2b32",
            color: "white",
          },
        }}
      >
        <MenuItem
          onClick={() => {
            setRenameDialog({
              open: true,
              chat: selectedChat,
              title: selectedChat?.title || "",
            });
            handleCloseMenu();
          }}
        >
          <ListItemIcon>
            <EditIcon fontSize="small" sx={{ color: "inherit" }} />
          </ListItemIcon>
          <ListItemText>Rename</ListItemText>
        </MenuItem>

        <Divider sx={{ borderColor: alpha("#fff", 0.1) }} />
        <MenuItem
          onClick={() => handleDeleteChat(selectedChat)}
          sx={{ color: "error.main" }}
        >
          <ListItemIcon>
            <DeleteIcon fontSize="small" color="error" />
          </ListItemIcon>
          <ListItemText>Delete</ListItemText>
        </MenuItem>
      </Menu>

      {/* Filter Menu */}
      <Menu
        anchorEl={filterMenuAnchor}
        open={Boolean(filterMenuAnchor)}
        onClose={() => setFilterMenuAnchor(null)}
        PaperProps={{
          sx: {
            backgroundColor: "#2a2b32",
            color: "white",
            minWidth: 200,
          },
        }}
      >
        <MenuItem
          onClick={() => {
            setFilterDialog({ open: true, name: "", config: filters });
            setFilterMenuAnchor(null);
          }}
        >
          <ListItemIcon>
            <BookmarkIcon fontSize="small" sx={{ color: "inherit" }} />
          </ListItemIcon>
          <ListItemText>Save Current Filter</ListItemText>
        </MenuItem>
        <Divider sx={{ borderColor: alpha("#fff", 0.1) }} />
        <MenuItem
          onClick={() => {
            setFilters({ dateRange: "today", dataSource: null, tags: [] });
            setFilterMenuAnchor(null);
          }}
        >
          Today
        </MenuItem>
        <MenuItem
          onClick={() => {
            setFilters({ dateRange: "week", dataSource: null, tags: [] });
            setFilterMenuAnchor(null);
          }}
        >
          Last 7 days
        </MenuItem>
        <MenuItem
          onClick={() => {
            setFilters({ dateRange: null, dataSource: null, tags: [] });
            setFilterMenuAnchor(null);
          }}
        >
          Clear Filters
        </MenuItem>
      </Menu>

      {/* Rename Dialog */}
      <Dialog
        open={renameDialog.open}
        onClose={() => setRenameDialog({ open: false, chat: null, title: "" })}
        PaperProps={{
          sx: {
            backgroundColor: "#2a2b32",
            color: "white",
          },
        }}
      >
        <DialogTitle>Rename Chat</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            value={renameDialog.title}
            onChange={(e) =>
              setRenameDialog({ ...renameDialog, title: e.target.value })
            }
            onKeyPress={(e) => e.key === "Enter" && handleRenameChat()}
            sx={{
              mt: 1,
              "& .MuiOutlinedInput-root": {
                color: "white",
                "& fieldset": {
                  borderColor: alpha("#fff", 0.2),
                },
              },
            }}
          />
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() =>
              setRenameDialog({ open: false, chat: null, title: "" })
            }
          >
            Cancel
          </Button>
          <Button onClick={handleRenameChat} variant="contained">
            Save
          </Button>
        </DialogActions>
      </Dialog>

      {/* Save Filter Dialog */}
      <Dialog
        open={filterDialog.open}
        onClose={() => setFilterDialog({ open: false, name: "", config: {} })}
        PaperProps={{
          sx: {
            backgroundColor: "#2a2b32",
            color: "white",
          },
        }}
      >
        <DialogTitle>Save Filter</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            label="Filter Name"
            value={filterDialog.name}
            onChange={(e) =>
              setFilterDialog({ ...filterDialog, name: e.target.value })
            }
            onKeyPress={(e) => e.key === "Enter" && handleSaveFilter()}
            sx={{
              mt: 1,
              "& .MuiOutlinedInput-root": {
                color: "white",
                "& fieldset": {
                  borderColor: alpha("#fff", 0.2),
                },
              },
              "& .MuiInputLabel-root": {
                color: alpha("#fff", 0.5),
              },
            }}
          />
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() =>
              setFilterDialog({ open: false, name: "", config: {} })
            }
          >
            Cancel
          </Button>
          <Button onClick={handleSaveFilter} variant="contained">
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Sidebar;
