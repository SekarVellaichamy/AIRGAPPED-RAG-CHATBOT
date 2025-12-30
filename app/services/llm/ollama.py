import httpx
import json
from typing import List, Dict, Generator
from app.core.config import settings
from .base import LLMBase

import logging

logger = logging.getLogger(__name__)

class OllamaService(LLMBase):
    def __init__(self, model_name: str = None):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = model_name if model_name else settings.LLM_MODEL
        self.timeout = settings.LLM_TIMEOUT
        self.embed_model = "nomic-embed-text" 
        logger.info(f"Initialized OllamaService with model={self.model}, base_url={self.base_url}") 

    def generate_response(self, messages: List[Dict[str, str]]) -> str:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_ctx": settings.OLLAMA_NUM_CTX
            }
        }
        try:
            logger.debug(f"Sending request to Ollama: {json.dumps(payload)}")
            response = httpx.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            content = response.json().get("message", {}).get("content", "")
            logger.debug(f"Received response from Ollama: {content[:100]}...")
            return content
        except Exception as e:
            logger.error(f"Error connecting to Ollama: {str(e)}", exc_info=True)
            return f"Error connecting to Ollama: {str(e)}"

    def generate_stream(self, messages: List[Dict[str, str]]) -> Generator[str, None, None]:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "num_ctx": settings.OLLAMA_NUM_CTX
            }
        }
        try:
            logger.debug(f"Starting stream from Ollama: {json.dumps(payload)}")
            with httpx.stream("POST", url, json=payload, timeout=self.timeout) as response:
                for line in response.iter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to decode JSON line: {line}")
                            continue
        except Exception as e:
            logger.error(f"Streaming error: {str(e)}", exc_info=True)
            yield f"Error: {str(e)}"

    def get_embedding(self, text: str) -> List[float]:
        url = f"{self.base_url}/api/embeddings"
        payload = {
            "model": self.embed_model,
            "prompt": text
        }
        try:
            response = httpx.post(url, json=payload, timeout=10.0)
            response.raise_for_status()
            return response.json().get("embedding", [])
        except Exception as e:
            print(f"Embedding error: {e}")
            return []
