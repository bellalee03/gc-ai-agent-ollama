"""
inputs/base.py
──────────────────────────────────────────────────────────────────────────────
Abstract base class for all input sources.

Every input source (Outlook, Google Docs, manual text) must implement:
    fetch() → list[RawRequest]

This ensures that no matter where the request comes from, it exits as a
normalized RawRequest before touching Claude or any downstream service.
The rest of the pipeline never needs to know the original source type.
"""

from abc import ABC, abstractmethod
from core.models import RawRequest


class BaseInputSource(ABC):

    @abstractmethod
    def fetch(self) -> list[RawRequest]:
        """
        Retrieve one or more raw requests from this source.
        Returns a list of RawRequest objects ready for Claude parsing.
        """
        ...
