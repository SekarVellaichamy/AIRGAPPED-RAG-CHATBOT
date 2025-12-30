# Developer Manual

This manual covers development setup, configuration, and deployment instructions including air-gapped environments.

---

## 1. Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| **RAM** | 8 GB | 16+ GB (for LLM inference) |
| **Docker** | Docker Desktop or Engine + Compose | Latest stable |
| **Python** | 3.10+ (for local dev) | 3.10 |
| **Disk** | 10 GB | 50+ GB (for models) |

---

## 2. Configuration Reference

All configuration is done via environment variables in `.env`:

### Core Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | *required* | PostgreSQL connection string |
| `LLM_PROVIDER` | `vllm` | LLM backend: `ollama` or `vllm` |
| `LLM_MODEL` | `Qwen/Qwen3-0.6B` | Model name for inference |
| `LLM_TIMEOUT` | `60.0` | Request timeout in seconds |

### Ollama Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `llama3` | Ollama-specific model name |
| `OLLAMA_NUM_CTX` | `8192` | Context window size |

### vLLM Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `VLLM_BASE_URL` | `http://localhost:8000/v1` | vLLM OpenAI-compatible endpoint |

### RAG Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `RAG_CHUNK_SIZE` | `500` | Characters per chunk |
| `RAG_CHUNK_OVERLAP` | `50` | Overlap between chunks |
| `RAG_TOP_K` | `5` | Number of results to retrieve |

### Feature Flags

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_STREAMING` | `True` | Enable streaming responses |
| `ENABLE_THINKING` | `False` | Show AI reasoning in `<think>` blocks |
| `OCR_ENABLED` | `True` | Enable OCR for images/PDFs |

### Security Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | *required* | JWT signing key. Generate with: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `DEBUG` | `False` | Enable debug mode (exposes /docs endpoint) |
| `SECURE_COOKIES` | `True` | Set `Secure` flag on cookies (requires HTTPS). Set to `False` for local development. |

> ⚠️ **Security**: The application will not start without a valid `SECRET_KEY` in your `.env` file.

### LDAP Settings (Optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `LDAP_ENABLED` | `False` | Enable LDAP authentication |
| `LDAP_SERVER` | `""` | LDAP server hostname |
| `LDAP_PORT` | `389` | LDAP port (636 for LDAPS) |
| `LDAP_USE_SSL` | `False` | Use LDAPS |
| `LDAP_START_TLS` | `False` | Use STARTTLS |
| `LDAP_USER_SEARCH_FILTER` | `(uid={username})` | User search filter |

---

## 3. Quick Start (Connected Environment)

For developers with internet access:

```bash
# 1. Clone repository
git clone <repo_url>
cd chatbot

# 2. Copy environment file
cp .env.example .env

# 3. Start application
docker-compose up --build

# 4. Access at http://localhost:5000
```

---

## 4. Air-Gapped / Isolated Deployment

This requires a two-stage process: **Preparation** (with internet) and **Deployment** (isolated).

### Stage 1: Preparation (Internet Required)

Perform these steps on a machine with internet access.

#### Step 1: Pull & Save Docker Images

```bash
# Pull required images
docker pull python:3.10-slim
docker pull pgvector/pgvector:pg16

# Save to tarball files
docker save python:3.10-slim -o python-3.10-slim.tar
docker save pgvector/pgvector:pg16 -o pgvector.tar
```

#### Step 2: Download Ollama Models

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull required models
ollama pull llama3
ollama pull nomic-embed-text
```

**Model locations:**
- Linux/Mac: `~/.ollama`
- Windows: `C:\Users\<Username>\.ollama`

Copy the entire `.ollama` directory.

#### Step 3: Package Source Code

```bash
# Create archive (excluding unnecessary files)
tar --exclude='.git' --exclude='__pycache__' --exclude='.venv' \
    -czvf chatbot-source.tar.gz ./chatbot
```

### Stage 2: Deployment (Isolated Machine)

Transfer the `.tar` files, `.ollama` folder, and source archive to the isolated machine.

#### Step 1: Load Docker Images

```bash
docker load -i python-3.10-slim.tar
docker load -i pgvector.tar
```

#### Step 2: Setup Ollama

1. Place the `.ollama` directory in the target user's home folder
2. Ensure the Ollama binary is available and executable
3. Start Ollama service:
   ```bash
   ollama serve
   ```

#### Step 3: Configure Environment

Edit `.env` and ensure `OLLAMA_BASE_URL` points to the correct address:
- Same machine: `http://localhost:11434`
- Docker to host: `http://host.docker.internal:11434`
- Network IP: `http://<machine-ip>:11434`

#### Step 4: Launch Application

```bash
docker-compose up -d
```

---

## 5. Project Structure

```
chatbot/
├── app/
│   ├── api/           # REST API endpoints (FastAPI routers)
│   │   ├── routes.py  # Main chat routes
│   │   ├── admin.py   # Admin panel routes
│   │   ├── auth.py    # Authentication routes
│   │   └── deps.py    # Route dependencies
│   ├── core/          # Configuration, Database, Logging, Security
│   │   ├── config.py          # Environment configuration
│   │   ├── database.py        # Database connection
│   │   ├── security.py        # JWT and password utilities
│   │   ├── security_middleware.py  # CSP headers middleware
│   │   ├── csrf.py            # CSRF protection
│   │   ├── rate_limiter.py    # Rate limiting
│   │   └── logger.py          # Logging configuration
│   ├── models/        # SQLModel database models
│   ├── services/      # Business logic
│   │   ├── chat_service.py    # Chat handling
│   │   ├── admin_service.py   # Admin operations
│   │   ├── ldap_service.py    # LDAP integration
│   │   ├── ingestion/         # Document processing
│   │   │   ├── parser.py      # Document parsing
│   │   │   ├── chunker.py     # Text chunking
│   │   │   └── rag_service.py # RAG retrieval
│   │   └── llm/               # LLM providers
│   │       ├── ollama.py      # Ollama integration
│   │       └── vllm.py        # vLLM integration
│   ├── static/        # Frontend assets (CSS, JS)
│   └── templates/     # Jinja2 HTML templates
├── docs/              # Documentation
├── migrations/        # Database migrations
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## 6. Troubleshooting

| Issue | Solution |
|-------|----------|
| **DB Connection Failed** | Wait 30 seconds for DB to initialize. Check: `docker-compose logs db` |
| **LLM Connection Error** | Verify Ollama is running: `curl localhost:11434` |
| **"Type vector does not exist"** | Restart db container: `docker-compose restart db` |
| **Document parsing fails** | Check file format is supported. View logs: `docker-compose logs web` |
| **Slow responses** | Ensure adequate RAM (16GB+). Try smaller model. |
| **LDAP not working** | Verify `LDAP_ENABLED=True` and network connectivity to LDAP server |

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Just the web application
docker-compose logs -f web

# Just the database
docker-compose logs -f db
```

---

## 7. Development Tips

### Running Locally (Without Docker)

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Run application
uvicorn app.main:app --reload --host 0.0.0.0 --port 5000
```

### Hot Reload
The development server supports hot reload. Changes to Python files will automatically restart the server.

### Database Reset
To completely reset the database:
```bash
docker-compose down -v
docker-compose up --build
```

> ⚠️ This deletes all data including users and documents!
