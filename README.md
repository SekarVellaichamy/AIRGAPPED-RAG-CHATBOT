# 🛡️ Isolated AI Chatbot

A secure, air-gapped capable conversational AI system that leverages local Large Language Models (LLMs) and RAG (Retrieval Augmented Generation) to let you chat with your private documents.

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🔒 **Air-Gapped Ready** | Runs completely offline - no data leaves your network |
| 📚 **Document Chat (RAG)** | Upload PDFs, DOCX, TXT files and ask questions about them |
| 🧠 **Local LLM** | Uses Ollama or vLLM for on-premise inference |
| 👥 **Multi-User** | Session-based authentication with admin controls |
| 🔐 **LDAP Support** | Optional enterprise LDAP/Active Directory integration |
| 📊 **Hierarchical Chunking** | Advanced document processing for better retrieval accuracy |
| 🛡️ **Security Hardened** | CSP headers, CSRF protection, rate limiting, secure cookies |

---

## 🚀 Quick Start

### Prerequisites
- **Docker & Docker Compose** (required)
- **[Ollama](https://ollama.com/)** running locally with models pulled:
  ```bash
  ollama pull llama3
  ollama pull nomic-embed-text
  ```

### Step 1: Clone & Configure
```bash
git clone <repo_url>
cd chatbot
cp .env.example .env

# Generate a secure secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Add the generated key to .env as SECRET_KEY=<your_key>
```

### Step 2: Launch
```bash
docker-compose up --build
```

### Step 3: Access
Open **[http://localhost:5000](http://localhost:5000)** in your browser.

- **Default Admin Login**: `admin` / `admin123`

> ⚠️ **Security**: Change the default admin password immediately after first login!

---

## 📚 Documentation

Detailed documentation is available in the [`docs/`](docs/) directory:

| Document | Description |
|----------|-------------|
| 📖 [User Guide](docs/USER_GUIDE.md) | How to use the chat, upload documents, and manage sessions |
| 🔧 [Developer Manual](docs/DEVELOPER_MANUAL.md) | Setup, configuration, and **Air-Gapped Deployment** |
| 🏗️ [Architecture](docs/ARCHITECTURE.md) | System overview and component diagrams |
| 🔄 [Data Flow](docs/DATA_FLOW.md) | Document processing and RAG retrieval pipelines |
| 📐 [Detailed Design](docs/DETAILED_DESIGN.md) | Database schema and API specifications |

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| **Backend** | FastAPI (Python 3.10+) |
| **Database** | PostgreSQL 16 + pgvector |
| **AI/LLM** | Ollama or vLLM (Llama 3, Nomic Embed) |
| **Document Parsing** | Microsoft MarkItDown |
| **Frontend** | Vanilla JS/CSS (No build step required) |

---

## 🤝 Support

For issues or questions, please check the [Developer Manual](docs/DEVELOPER_MANUAL.md) troubleshooting section first.
