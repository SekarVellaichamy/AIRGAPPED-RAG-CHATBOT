
import httpx
import logging
from app.core.config import settings
from .base import LLMBase
from .ollama import OllamaService
from .vllm import VLLMService
from .fallback import FallbackLLMService

logger = logging.getLogger(__name__)

def check_vllm_availability() -> bool:
    """Check if vLLM service is available."""
    url = f"{settings.VLLM_BASE_URL.rstrip('/')}/models"
    try:
        # Short timeout for availability check
        response = httpx.get(url, timeout=2.0)
        return response.status_code == 200
    except Exception as e:
        logger.debug(f"vLLM check failed: {e}")
        return False

def get_llm_service() -> LLMBase:
    # If config explicitly says ollama, respect that
    if settings.LLM_PROVIDER == "ollama":
        logger.info("LLM_PROVIDER is set to 'ollama'. Using OllamaService.")
        return OllamaService(model_name=settings.OLLAMA_MODEL)

    # If config says vllm (or default), try vLLM first with fallback
    if settings.LLM_PROVIDER == "vllm":
        logger.info("LLM_PROVIDER is set to 'vllm'. Checking for vLLM availability...")
        if check_vllm_availability():
            logger.info("vLLM is available. Using FallbackLLMService (vLLM primary, Ollama fallback).")
            return FallbackLLMService()
        
        logger.warning("vLLM is not available or connection failed. Using OllamaService directly as startup fallback.")
        return OllamaService(model_name=settings.OLLAMA_MODEL)
        
    # Default fallback (should not reach here with strict typing but good safety)
    return OllamaService(model_name=settings.OLLAMA_MODEL)
