"""Abstract base class for model interfaces (REQ-10.1)."""
from __future__ import annotations

from abc import ABC, abstractmethod


class ModelInterface(ABC):
    @abstractmethod
    def generate(self, prompt: str, parameters: dict) -> str:
        """Call the model and return the text response.

        Role-parameter overrides have already been merged into `parameters`
        by the caller before this method is invoked.
        """
        ...
