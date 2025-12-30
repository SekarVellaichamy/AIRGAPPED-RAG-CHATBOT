from abc import ABC, abstractmethod
from typing import List, Dict, Any, Generator

class LLMBase(ABC):
    @abstractmethod
    def generate_response(self, messages: List[Dict[str, str]]) -> str:
        """
        Generate a response based on a list of messages.
        Messages format: [{"role": "user", "content": "hello"}, ...]
        """
        pass

    @abstractmethod
    def generate_stream(self, messages: List[Dict[str, str]]) -> Generator[str, None, None]:
        """
        Generate a streaming response.
        """
        pass
    
    @abstractmethod
    def get_embedding(self, text: str) -> List[float]:
        """
        Get vector embedding for text.
        """
        pass
