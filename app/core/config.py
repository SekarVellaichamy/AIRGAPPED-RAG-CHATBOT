from typing import Literal
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Multi-Agent Chatbot"
    DATABASE_URL: str
    
    # Server Configuration
    BASE_URL: str = "https://chat.afro.iaf.in"
    SSL_ENABLED: bool = True
    SSL_CERTFILE: str = "ssl/cert.pem"
    SSL_KEYFILE: str = "ssl/key.pem"
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8080
    
    # Security Configuration
    SECRET_KEY: str  # Required - must be set in .env
    DEBUG: bool = False  # Set to True in development only
    SECURE_COOKIES: bool = True  # Set to False for local development without HTTPS
    
    # LLM Configuration
    LLM_PROVIDER: Literal["ollama", "vllm"] = "vllm"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "Qwen/Qwen3-0.6B"
    LLM_TIMEOUT: float = 60.0
    VLLM_BASE_URL: str = "http://localhost:8000/v1"
    
    # Optional Ollama specific model (for fallback)
    OLLAMA_MODEL: str = "llama3"
    OLLAMA_NUM_CTX: int = 8192
    
    # RAG Configuration
    RAG_CHUNK_SIZE: int = 500
    RAG_CHUNK_OVERLAP: int = 50
    RAG_TOP_K: int = 5
    
    # OCR Configuration
    OCR_ENABLED: bool = True
    
    # Storage Configuration
    UPLOAD_DIR: str = "uploaded_files"

    # Logging Configuration
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    LOG_TO_FILE: bool = False
    LOG_FILE_PATH: str = "app.log"
    
    # LDAP Configuration (Optional)
    LDAP_ENABLED: bool = False
    LDAP_SERVER: str = ""
    LDAP_PORT: int = 389  # 389 for LDAP, 636 for LDAPS
    LDAP_USE_SSL: bool = False  # True for LDAPS
    LDAP_BIND_DN: str = ""  # e.g., "cn=admin,dc=example,dc=com"
    LDAP_BIND_PASSWORD: str = ""
    LDAP_USER_SEARCH_BASE: str = ""  # e.g., "ou=users,dc=example,dc=com"
    LDAP_USER_SEARCH_FILTER: str = "(uid={username})"
    LDAP_START_TLS: bool = False  # Use STARTTLS on non-SSL connection
    LDAP_SKIP_CERTIFICATE_VERIFY: bool = False  # For self-signed certs
    
    # Feature Flags
    ENABLE_STREAMING: bool = True
    ENABLE_THINKING: bool = False
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
