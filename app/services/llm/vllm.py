
import httpx
import json
import logging
from typing import List, Dict, Generator
from app.core.config import settings
from .base import LLMBase

logger = logging.getLogger(__name__)

class VLLMService(LLMBase):
    def __init__(self):
        self.base_url = settings.VLLM_BASE_URL.rstrip('/')
        self.model = settings.LLM_MODEL
        self.timeout = settings.LLM_TIMEOUT
        logger.info(f"Initialized VLLMService with model={self.model}, base_url={self.base_url}")

    def generate_response(self, messages: List[Dict[str, str]]) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "max_tokens": 1024,
            "temperature": 0.7
        }
        try:
            logger.debug(f"Sending request to vLLM: {json.dumps(payload)}")
            response = httpx.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            content = data.get("choices", [])[0].get("message", {}).get("content", "")
            logger.debug(f"Received response from vLLM: {content[:100]}...")
            return content
        except Exception as e:
            logger.error(f"Error connecting to vLLM: {str(e)}", exc_info=True)
            return f"Error connecting to vLLM: {str(e)}"

    def generate_stream(self, messages: List[Dict[str, str]]) -> Generator[str, None, None]:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "max_tokens": 1024,
            "temperature": 0.7
        }
        try:
            logger.debug(f"Starting stream from vLLM: {json.dumps(payload)}")
            with httpx.stream("POST", url, json=payload, timeout=self.timeout) as response:
                for line in response.iter_lines():
                    if line:
                        line = line.strip()
                        if line == "data: [DONE]":
                            break
                        if line.startswith("data: "):
                            try:
                                data = json.loads(line[6:])
                                delta = data.get("choices", [])[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                logger.warning(f"Failed to decode JSON line: {line}")
                                continue
        except Exception as e:
            logger.error(f"Streaming error: {str(e)}", exc_info=True)
            yield f"Error: {str(e)}"

    def get_embedding(self, text: str) -> List[float]:
        # vLLM supports embeddings at /v1/embeddings
        url = f"{self.base_url}/embeddings"
        payload = {
            "model": self.model,
            "input": text
        }
        try:
            response = httpx.post(url, json=payload, timeout=10.0)
            response.raise_for_status()
            return response.json().get("data", [])[0].get("embedding", [])
        except Exception as e:
            logger.error(f"Embedding error: {str(e)}", exc_info=True)
            # Fallback or empty if embeddings not supported/failed
            return []
