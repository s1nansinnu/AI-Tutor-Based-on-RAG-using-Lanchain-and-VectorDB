# 🎓 AI Tutor - RAG-Powered Educational Assistant

An intelligent tutoring system using Retrieval-Augmented Generation (RAG) to help students learn from their uploaded documents.

## ✨ Features

### 🤖 AI-Powered Tutoring
- **Tutoring-Only Mode**: Designed exclusively for education - won't write essays or do homework
- **Document-Based Learning**: Upload PDFs, DOCX, HTML files for contextual tutoring
- **Smart RAG System**: Uses ChromaDB for semantic search and retrieval

### 🎤 Voice Features
- **Speech-to-Text**: Ask questions using your voice
- **Text-to-Speech**: Responses read aloud automatically
- **Adjustable Speech Rate**: 0.5x to 2.0x speed control

### 🎭 Animated Mascot
- 5 emotion states (happy, explaining, thinking, encouraging, neutral)
- Lip-sync animation when speaking
- Responsive to conversation context

### 💬 Session Management
- Multi-session support
- Session history with previews
- Persistent storage using localStorage

### 📊 Advanced Features
- Emotion detection in responses
- API quota management with countdown timer
- Error handling and recovery
- Rate limiting protection

## 🏗️ Architecture

### Backend (FastAPI)
- **Framework**: FastAPI with Python 3.11+
- **Vector Database**: ChromaDB for embeddings
- **LLM**: Google Gemini 2.5 Flash
- **Database**: SQLite for metadata
- **Embedding**: Google text-embedding-004

### Frontend (React)
- **Framework**: React.js
- **Voice**: Web Speech API
- **UI**: Custom CSS with animations
- **State**: React Hooks + localStorage

## 📦 Installation

### Prerequisites
- Python 3.11+
- Node.js 16+
- Google AI API Key

### Backend Setup
```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
echo "GOOGLE_API_KEY=your_api_key_here" > .env

# Run backend
python main.py
```

Backend runs on: `http://localhost:8000`

### Frontend Setup
```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Create .env file
echo "REACT_APP_API_URL=http://localhost:8000" > .env

# Run frontend
npm start
```

Frontend runs on: `http://localhost:3000`

## 🚀 Usage

1. **Upload Documents**: Click "Documents" tab and upload PDF/DOCX/HTML files
2. **Ask Questions**: Type or speak your questions
3. **Learn**: AI tutor explains concepts using your documents
4. **Voice Features**: Enable auto-speak for spoken responses
5. **Sessions**: Create new sessions to organize conversations

## 📚 Key Features Explained

### Tutoring-Only Mode
The AI is restricted to educational purposes:
- ✅ Explains concepts and theories
- ✅ Guides through problem-solving
- ✅ Answers questions about documents
- ❌ Won't write essays or emails
- ❌ Won't do homework for students
- ❌ Won't create content for submission

### RAG Pipeline
1. Document uploaded → Chunked → Embedded
2. User asks question → Semantic search
3. Relevant chunks retrieved → Context provided to LLM
4. LLM generates educational response

### Emotion Detection
Responses include emotion tags for mascot animation:
- `happy`: Enthusiastic responses
- `explaining`: Teaching mode
- `thinking`: Problem analysis
- `encouraging`: Motivational
- `neutral`: Factual responses

## 🛠️ Configuration

### Backend (`backend/config.py`)
```python
GOOGLE_API_KEY=your_key
DEFAULT_MODEL=gemini-2.5-flash
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
RETRIEVER_K=2
```

### Frontend
- Voice settings in chat interface
- Speech rate: 0.5x - 2.0x
- Auto-speak toggle
- Model selection

## 📊 Project Structure
ai-tutor-rag/
├── backend/
│   ├── main.py              # FastAPI app
│   ├── config.py            # Settings
│   ├── langchain_utils.py   # RAG chain
│   ├── chroma_utils.py      # Vector store
│   ├── db_utils.py          # SQLite ops
│   ├── file_utils.py        # File handling
│   └── models.py            # Pydantic models
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatInterface.js
│   │   │   ├── DocumentManager.js
│   │   │   ├── Mascot.js
│   │   │   └── ErrorBoundary.js
│   │   ├── api/
│   │   │   └── chatAPI.js
│   │   ├── App.js
│   │   └── index.js
│   └── public/
└── README.md

## 🔒 Security Features

- File validation and sanitization
- Hash-based deduplication
- Rate limiting (30 req/min)
- CORS protection
- Input validation
- SQL injection prevention

## 🐛 Troubleshooting

### Quota Exceeded
- Popup shows countdown to reset (midnight PT)
- Check quota at: https://ai.dev/rate-limit

### Voice Not Working
- Check browser supports Web Speech API
- Allow microphone permissions
- Use Chrome/Edge for best compatibility

### Backend Errors
- Check `.env` has valid API key
- Verify ChromaDB directory exists
- Check logs in `app.log`

## 📈 Future Enhancements

- [ ] Multiple document collections
- [ ] PDF annotation features
- [ ] Quiz generation
- [ ] Progress tracking
- [ ] Multi-language support
- [ ] Mobile app version

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create feature branch
3. Commit changes
4. Push to branch
5. Open pull request

## 📄 License

MIT License - feel free to use for educational purposes

## 👏 Acknowledgments

- Google Gemini API
- LangChain framework
- ChromaDB vector database
- FastAPI framework
- React.js library

## 📧 Contact

For questions or support, please open an issue on GitHub.

---

Made with ❤️ for education
