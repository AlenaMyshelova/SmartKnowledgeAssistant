# 🤖 Smart Knowledge Assistant

My awesome assistant. The bestest in the Universe! Bow to your new evil overlord!

AI-powered knowledge assistant provides intelligent answers based on company FAQs using RAG (Retrieval-Augmented Generation) with OpenAI GPT.

## ✨ Features

- 🔐 **OAuth Authentication** - Google & GitHub login
- 💬 **AI Chat** - Intelligent responses based on company knowledge base
- 🔍 **Semantic Search** - Vector search using FAISS + OpenAI embeddings
- 🎤 **Voice Input** - Speech-to-text with OpenAI Whisper
- 🕶️ **Incognito Mode** - Private chats that aren't saved
- 📱 **Responsive Design** - Works on desktop and mobile

## 🛠️ Tech Stack

### Backend

- **FastAPI** - Python web framework
- **SQLAlchemy** - ORM for SQLite database
- **OpenAI API** - GPT-4o-mini for responses, Whisper for transcription
- **FAISS** - Vector similarity search
- **Alembic** - Database migrations

### Frontend

- **React 18** - UI library
- **Vite** - Build tool
- **Material-UI** - Component library
- **React Router** - Navigation
- **Axios** - HTTP client

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- OpenAI API key
- Google/GitHub OAuth credentials

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run server
python main.py
```

### Frontend Setup

```bash
cd frontend
npm install

# Configure environment
cp .env.example .env
# Edit .env if needed

# Run development server
npm run dev
```

## 📁 Project Structure

```
SmartKnowledgeAssistant/
├── backend/
│   ├── app/
│   │   ├── api/          # API endpoints
│   │   ├── auth/         # OAuth handlers
│   │   ├── core/         # Config, security
│   │   ├── database/     # DB connection, migrations
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── services/     # Business logic
│   │   └── middleware/   # Auth middleware
│   ├── data/             # FAQs, indexes, uploads
│   └── main.py           # Entry point
└── frontend/
    └── src/
        ├── components/   # React components
        ├── contexts/     # React contexts
        └── services/     # API client
```

## 🔧 Environment Variables

### Backend (.env)

```env
OPENAI_API_KEY=sk-...
SECRET_KEY=your-secret-key
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...
```

### Frontend (.env)

```env
VITE_API_URL=http://localhost:8000/api/v1
```

## 📚 API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
