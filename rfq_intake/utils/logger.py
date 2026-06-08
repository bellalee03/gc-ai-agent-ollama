"""
utils/logger.py
──────────────────────────────────────────────────────────────────────────────
Central logging setup. Call setup_logging() once at startup in main.py.
Any module can then use: logger = logging.getLogger(__name__)
"""

import logging
import sys
from core.config import settings


def setup_logging() -> None:
    """
    Configures the root logger for the whole application.
    Call this once at the top of main.py before anything else runs.
    """
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )
