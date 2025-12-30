"""
System Check Module for Application Boot Sequence.
Provides detailed status information in formatted tables.
"""

import sys
import platform
import logging
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    """Result of a system check."""
    name: str
    status: str  # "OK", "WARN", "FAIL", "INFO"
    value: str
    notes: str = ""


def format_table(title: str, rows: List[CheckResult], width: int = 80) -> str:
    """Format check results as an ASCII table."""
    # Calculate column widths
    max_name = max(len(r.name) for r in rows) if rows else 10
    name_width = min(max_name, 25)
    
    status_width = 8  # Header "Status" is 6, plus padding
    
    max_value = max(len(str(r.value)) for r in rows) if rows else 10
    value_width = min(max_value, 30)
    
    # Calculate notes width with a minimum to prevent negative values
    # width - name - status - value - approx padding (13)
    remaining_width = width - name_width - status_width - value_width - 13
    notes_width = max(remaining_width, 10)
    
    # If forced columns exceed width, we just let it overflow rather than crashing
    
    lines = []
    # Adjust separator to match actual table width if it overflows
    actual_width = name_width + status_width + value_width + notes_width + 13
    table_width = max(width, actual_width)
    
    separator = "+" + "-" * (table_width - 2) + "+"
    
    # Title
    lines.append(separator)
    lines.append(f"| {title.center(table_width - 4)} |")
    lines.append(separator)
    
    # Header
    # Use explicit width to avoid "Sign not allowed" error
    header = f"| {'Component':<{name_width}} | {'Status':<{status_width}} | {'Value':<{value_width}} | {'Notes':<{notes_width}} |"
    lines.append(header)
    lines.append(separator)
    
    # Rows
    for row in rows:
        status_icon = {
            "OK": "✓ OK",
            "WARN": "⚠ WARN",
            "FAIL": "✗ FAIL",
            "INFO": "ℹ INFO"
        }.get(row.status, row.status)
        
        # Truncate content to fit columns
        notes = row.notes
        if len(notes) > notes_width:
             notes = notes[:notes_width-3] + "..."
             
        val_str = str(row.value)
        if len(val_str) > value_width:
            val_str = val_str[:value_width-3] + "..."
        
        line = f"| {row.name:<{name_width}} | {status_icon:<{status_width}} | {val_str:<{value_width}} | {notes:<{notes_width}} |"
        lines.append(line)
    
    lines.append(separator)
    return "\n".join(lines)


def check_python_environment() -> List[CheckResult]:
    """Check Python environment."""
    results = []
    
    # Python version
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    results.append(CheckResult("Python Version", "OK", py_version, ""))
    
    # Platform
    results.append(CheckResult("Platform", "INFO", platform.system(), platform.release()))
    
    # Architecture
    results.append(CheckResult("Architecture", "INFO", platform.machine(), ""))
    
    return results


def check_document_parsing() -> List[CheckResult]:
    """Check document parsing libraries."""
    results = []
    
    # MarkItDown
    try:
        from markitdown import MarkItDown
        # Currently MarkItDown doesn't expose a clean version attribute at top level easily
        # checking pkg_resources or importlib.metadata is safer but simplified here
        try:
            from importlib.metadata import version
            ver = version("markitdown")
        except:
            ver = "installed"
        results.append(CheckResult("MarkItDown", "OK", ver, "Primary parser"))
    except ImportError:
        results.append(CheckResult("MarkItDown", "FAIL", "Not installed", "Install: markitdown[docx,pdf]"))
        
    # OpenAI (Required for MarkItDown in this app)
    try:
        import openai
        ver = getattr(openai, "__version__", "unknown")
        results.append(CheckResult("openai", "OK", ver, "LLM client"))
    except ImportError:
        results.append(CheckResult("openai", "FAIL", "Not installed", "Required dependency"))

    # pypdf
    try:
        import pypdf
        version = getattr(pypdf, '__version__', 'unknown')
        results.append(CheckResult("pypdf", "OK", version, "PDF text extraction"))
    except ImportError:
        results.append(CheckResult("pypdf", "FAIL", "Not installed", "Required for PDFs"))
    
    # python-docx
    try:
        import docx
        results.append(CheckResult("python-docx", "OK", "Installed", "DOCX parsing"))
    except ImportError:
        results.append(CheckResult("python-docx", "FAIL", "Not installed", "Required for DOCX"))
    
    # Tesseract OCR
    try:
        import pytesseract
        # Try to get version
        try:
            version = pytesseract.get_tesseract_version()
            results.append(CheckResult("Tesseract OCR", "OK", str(version), "OCR enabled"))
        except Exception:
            results.append(CheckResult("Tesseract OCR", "WARN", "pytesseract OK", "tesseract binary may be missing"))
    except ImportError:
        results.append(CheckResult("Tesseract OCR", "WARN", "Not installed", "OCR disabled"))
    
    return results


def check_llm_services() -> List[CheckResult]:
    """Check LLM service configuration."""
    from app.core.config import settings
    results = []
    
    # LLM Provider
    results.append(CheckResult("LLM Provider", "INFO", settings.LLM_PROVIDER, "Primary provider"))
    
    # Model
    results.append(CheckResult("LLM Model", "INFO", settings.LLM_MODEL, ""))
    
    # Streaming
    streaming_status = "Enabled" if settings.ENABLE_STREAMING else "Disabled"
    results.append(CheckResult("Streaming", "INFO", streaming_status, ""))
    
    # Ollama connection
    try:
        import httpx
        response = httpx.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=5.0)
        if response.status_code == 200:
            models = response.json().get("models", [])
            model_count = len(models)
            results.append(CheckResult("Ollama Server", "OK", f"{model_count} models", settings.OLLAMA_BASE_URL))
        else:
            results.append(CheckResult("Ollama Server", "WARN", f"HTTP {response.status_code}", settings.OLLAMA_BASE_URL))
    except Exception as e:
        results.append(CheckResult("Ollama Server", "WARN", "Unreachable", str(e)[:40]))
    
    # vLLM connection (if configured)
    if settings.VLLM_BASE_URL:
        try:
            import httpx
            response = httpx.get(f"{settings.VLLM_BASE_URL}/models", timeout=5.0)
            if response.status_code == 200:
                results.append(CheckResult("vLLM Server", "OK", "Connected", settings.VLLM_BASE_URL))
            else:
                results.append(CheckResult("vLLM Server", "WARN", f"HTTP {response.status_code}", settings.VLLM_BASE_URL))
        except Exception:
            results.append(CheckResult("vLLM Server", "WARN", "Unreachable", settings.VLLM_BASE_URL))
    
    return results


def check_database() -> List[CheckResult]:
    """Check database configuration."""
    from app.core.config import settings
    results = []
    
    # Parse database URL for display (hide password)
    db_url = settings.DATABASE_URL
    try:
        # Simple parsing - hide password
        if "@" in db_url:
            parts = db_url.split("@")
            host_part = parts[-1]
            results.append(CheckResult("Database Host", "INFO", host_part.split("/")[0], ""))
            results.append(CheckResult("Database Name", "INFO", host_part.split("/")[-1].split("?")[0], ""))
        
        # Test connection
        from app.core.database import engine
        from sqlalchemy import text
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            results.append(CheckResult("Database Connection", "OK", "Connected", "PostgreSQL"))
            
            # Check pgvector extension
            try:
                conn.execute(text("SELECT 'vector'::regtype"))
                results.append(CheckResult("pgvector Extension", "OK", "Enabled", "Vector search ready"))
            except Exception:
                results.append(CheckResult("pgvector Extension", "FAIL", "Not installed", "Required for RAG"))
    except Exception as e:
        results.append(CheckResult("Database Connection", "FAIL", "Failed", str(e)[:40]))
    
    return results


def check_rag_configuration() -> List[CheckResult]:
    """Check RAG system configuration."""
    results = []
    
    try:
        from app.services.ingestion.rag_service import RAGService
        rag = RAGService()
        
        results.append(CheckResult("Chunk Size", "INFO", str(rag.chunk_size), "characters"))
        results.append(CheckResult("Chunk Overlap", "INFO", str(rag.chunk_overlap), "characters"))
        results.append(CheckResult("Min Relevance", "INFO", str(rag.min_relevance_threshold), "threshold"))
        results.append(CheckResult("Embedding Model", "INFO", rag.llm_service.embed_model, "via Ollama"))
    except Exception as e:
        results.append(CheckResult("RAG Service", "FAIL", "Error", str(e)[:40]))
    
    return results


def check_ldap() -> List[CheckResult]:
    """Check LDAP configuration."""
    from app.core.config import settings
    results = []
    
    if settings.LDAP_ENABLED:
        results.append(CheckResult("LDAP Enabled", "INFO", "Yes", ""))
        results.append(CheckResult("LDAP Server", "INFO", settings.LDAP_SERVER or "Not set", ""))
        results.append(CheckResult("LDAP Protocol", "INFO", "LDAPS" if settings.LDAP_USE_SSL else "LDAP", ""))
        
        # Test connection
        try:
            from app.services.ldap_service import ldap_service
            if ldap_service.is_available():
                results.append(CheckResult("LDAP Connection", "OK", "Available", ""))
            else:
                results.append(CheckResult("LDAP Connection", "WARN", "Unavailable", "Check server"))
        except Exception as e:
            results.append(CheckResult("LDAP Connection", "WARN", "Error", str(e)[:40]))
    else:
        results.append(CheckResult("LDAP Enabled", "INFO", "No", "Local auth only"))
    
    return results


def run_system_check() -> str:
    """Run all system checks and return formatted output."""
    output_lines = []
    
    # Header
    output_lines.append("")
    output_lines.append("=" * 82)
    output_lines.append("                    SYSTEM CHECK - APPLICATION BOOT SEQUENCE")
    output_lines.append("=" * 82)
    output_lines.append("")
    
    # Python Environment
    output_lines.append(format_table("PYTHON ENVIRONMENT", check_python_environment()))
    output_lines.append("")
    
    # Document Parsing
    output_lines.append(format_table("DOCUMENT PARSING LIBRARIES", check_document_parsing()))
    output_lines.append("")
    
    # Database
    output_lines.append(format_table("DATABASE", check_database()))
    output_lines.append("")
    
    # LLM Services
    output_lines.append(format_table("LLM SERVICES", check_llm_services()))
    output_lines.append("")
    
    # RAG Configuration
    output_lines.append(format_table("RAG CONFIGURATION", check_rag_configuration()))
    output_lines.append("")
    
    # LDAP
    output_lines.append(format_table("AUTHENTICATION", check_ldap()))
    output_lines.append("")
    
    # Summary
    output_lines.append("=" * 82)
    output_lines.append("                         SYSTEM CHECK COMPLETE")
    output_lines.append("=" * 82)
    output_lines.append("")
    
    return "\n".join(output_lines)


def print_system_check():
    """Run system check and print to logger."""
    check_output = run_system_check()
    
    # Print each line to logger
    for line in check_output.split("\n"):
        logger.info(line)


if __name__ == "__main__":
    # Configure basic logging to stdout
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(run_system_check())
