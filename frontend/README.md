# Smart Knowledge Assistant - Frontend

React frontend for Smart Knowledge Assistant - AI-powered knowledge assistant.

## 🚀 Quick Start

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Lint code
npm run lint
```

## 📁 Project Structure

```
src/
├── components/     # React components
│   ├── auth/       # Authentication (Login, ProtectedRoute)
│   ├── chat/       # Chat interface components
│   └── layout/     # Layout components (MainLayout, Sidebar)
├── contexts/       # React contexts (Auth, Chat)
├── services/       # API client
└── assets/         # Static assets
```

## 🔧 Environment Variables

Create `.env` file in the frontend directory:

```env
VITE_API_URL=http://localhost:8000/api/v1
```

## 🛠️ Tech Stack

- **React 18** - UI library
- **Vite** - Build tool with HMR
- **Material-UI (MUI)** - Component library
- **React Router v6** - Navigation
- **Axios** - HTTP client
- **Notistack** - Snackbar notifications
- **date-fns** - Date formatting

## 📝 Available Scripts

| Script            | Description                           |
| ----------------- | ------------------------------------- |
| `npm run dev`     | Start development server on port 5173 |
| `npm run build`   | Create production build               |
| `npm run preview` | Preview production build locally      |
| `npm run lint`    | Run ESLint                            |

## 🔗 API Connection

The frontend connects to the backend API at the URL specified in `VITE_API_URL`.

Default: `http://localhost:8000/api/v1`

## 📱 Features

- OAuth authentication (Google, GitHub)
- Real-time chat interface
- Voice input with audio recording
- Incognito mode
- Chat history with search
- Responsive design
