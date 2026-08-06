from abc import ABC, abstractmethod
from typing import Dict, Optional

class BaseAIProvider(ABC):
    """
    Abstract base class for all AI providers.
    """
    @abstractmethod
    def generate_solution(self, slug: str, title: str, difficulty: str, description: str) -> Optional[Dict]:
        """
        Generate a complete solution JSON containing all fields and languages.
        Must return a validated dictionary or None on failure.
        """
        pass
