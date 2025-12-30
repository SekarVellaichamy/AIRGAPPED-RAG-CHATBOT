"""
Fallback LLM Service that automatically switches between vLLM and Ollama.
Provides runtime resilience by catching vLLM failures and falling back to Ollama.
"""

import logging
from typing import List, Dict, Generator
from .base import LLMBase
from .vllm import VLLMService
from .ollama import OllamaService
from app.core.config import settings

logger = logging.getLogger(__name__)


class FallbackLLMService(LLMBase):
    """
    A resilient LLM service that tries vLLM first and falls back to Ollama on failure.
    This provides runtime fallback, not just startup-time checking.
    """
    
    def __init__(self):
        self.vllm_service = VLLMService()
        self.ollama_service = OllamaService(model_name=settings.OLLAMA_MODEL)
        self._current_service = "vllm"
        logger.info("Initialized FallbackLLMService with vLLM primary, Ollama fallback")
    
    def _is_error_response(self, response: str) -> bool:
        """Check if the response indicates an error."""
        error_indicators = [
            "Error connecting to vLLM:",
            "Error:",
            "404 Not Found",
            "Connection refused",
            "timeout",
        ]
        return any(indicator.lower() in response.lower() for indicator in error_indicators)
    
    def generate_response(self, messages: List[Dict[str, str]]) -> str:
        """
        Generate a response, trying vLLM first and falling back to Ollama on failure.
        """
        # Try vLLM first
        try:
            logger.debug("Attempting to generate response with vLLM...")
            response = self.vllm_service.generate_response(messages)
            
            # Check if response indicates an error
            if self._is_error_response(response):
                logger.warning(f"vLLM returned an error response: {response[:100]}...")
                raise Exception("vLLM error response detected")
            
            self._current_service = "vllm"
            return response
            
        except Exception as e:
            logger.warning(f"vLLM failed: {e}. Falling back to Ollama...")
            
            # Fallback to Ollama
            try:
                response = self.ollama_service.generate_response(messages)
                self._current_service = "ollama"
                logger.info("Successfully generated response using Ollama fallback")
                return response
            except Exception as ollama_error:
                logger.error(f"Both vLLM and Ollama failed. Ollama error: {ollama_error}")
                return f"Error: Both LLM services are unavailable. vLLM: {e}, Ollama: {ollama_error}"
    
    def generate_stream(self, messages: List[Dict[str, str]]) -> Generator[str, None, None]:
        """
        Generate a streaming response, trying vLLM first and falling back to Ollama on failure.
        """
        try:
            logger.debug("Attempting to stream with vLLM...")
            first_chunk_received = False
            
            for chunk in self.vllm_service.generate_stream(messages):
                # Check first chunk for error indicators
                if not first_chunk_received:
                    if self._is_error_response(chunk):
                        logger.warning(f"vLLM stream returned error: {chunk}")
                        raise Exception("vLLM stream error detected")
                    first_chunk_received = True
                
                self._current_service = "vllm"
                yield chunk
                
        except Exception as e:
            logger.warning(f"vLLM streaming failed: {e}. Falling back to Ollama...")
            
            try:
                for chunk in self.ollama_service.generate_stream(messages):
                    self._current_service = "ollama"
                    yield chunk
                logger.info("Successfully streamed response using Ollama fallback")
            except Exception as ollama_error:
                logger.error(f"Both vLLM and Ollama streaming failed. Ollama error: {ollama_error}")
                yield f"Error: Both LLM services are unavailable."
    
    def get_embedding(self, text: str) -> List[float]:
        """
        Get embeddings, using Ollama by default as it's configured for embeddings.
        """
        # For embeddings, we typically use Ollama's nomic-embed-text model
        # vLLM embedding support can vary, so prefer Ollama for consistency
        return self.ollama_service.get_embedding(text)
    
    @property
    def current_service(self) -> str:
        """Return the name of the currently active service."""
        return self._current_service
