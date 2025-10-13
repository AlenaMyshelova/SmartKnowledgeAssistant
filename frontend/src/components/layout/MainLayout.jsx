import React, { useState } from "react";
import {
  Box,
  Drawer,
  AppBar,
  Toolbar,
  IconButton,
  Typography,
  useTheme,
  useMediaQuery,
} from "@mui/material";
import { Menu as MenuIcon, Add as AddIcon } from "@mui/icons-material";
import { Outlet, useNavigate } from "react-router-dom";
import Sidebar from "./Sidebar";
import { useChat } from "../../contexts/ChatContext";

const drawerWidth = 280;

const MainLayout = () => {
  console.log("MainLayout rendered"); // Debug log

  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("md"));
  const [mobileOpen, setMobileOpen] = useState(false);
  const navigate = useNavigate();
  const { createNewChat } = useChat();

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  const handleNewChat = async () => {
    try {
      const chatId = await createNewChat();
      navigate(`/chat/${chatId}`);
      if (isMobile) {
        setMobileOpen(false);
      }
    } catch (error) {
      console.error("Error creating new chat:", error);
    }
  };

  return (
    <Box sx={{ display: "flex", height: "100vh" }}>
      {/* Mobile App Bar */}
      {isMobile && (
        <AppBar
          position="fixed"
          elevation={0}
          sx={{
            backgroundColor: "background.paper",
            color: "text.primary",
            borderBottom: 1,
            borderColor: "divider",
          }}
        >
          <Toolbar>
            <IconButton
              edge="start"
              onClick={handleDrawerToggle}
              sx={{ mr: 2 }}
            >
              <MenuIcon />
            </IconButton>
            <Typography variant="h6" sx={{ flexGrow: 1 }}>
              Smart Assistant
            </Typography>
            <IconButton onClick={handleNewChat} color="primary">
              <AddIcon />
            </IconButton>
          </Toolbar>
        </AppBar>
      )}

      {/* Sidebar */}
      <Box
        component="nav"
        sx={{ width: { md: drawerWidth }, flexShrink: { md: 0 } }}
      >
        <Drawer
          variant={isMobile ? "temporary" : "permanent"}
          open={isMobile ? mobileOpen : true}
          onClose={handleDrawerToggle}
          ModalProps={{ keepMounted: true }}
          sx={{
            "& .MuiDrawer-paper": {
              boxSizing: "border-box",
              width: drawerWidth,
              backgroundColor: "#202123",
              color: "white",
            },
          }}
        >
          <Sidebar onClose={isMobile ? handleDrawerToggle : undefined} />
        </Drawer>
      </Box>

      {/* Main Content */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          width: { md: `calc(100% - ${drawerWidth}px)` },
          height: "100vh",
          overflow: "hidden",
          backgroundColor: "background.default",
          pt: { xs: 8, md: 0 },
        }}
      >
        <Outlet />
      </Box>
    </Box>
  );
};

export default MainLayout;
