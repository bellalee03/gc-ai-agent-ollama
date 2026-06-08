"""
core/config.py
All configuration is read from environment variables or a .env file.
Never put real credentials here.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Anthropic
    ANTHROPIC_API_KEY: str = ""

    # Google Sheets
    GOOGLE_SERVICE_ACCOUNT_JSON: str = "google_service_account.json"
    GOOGLE_SHEET_ID: str = ""
    RATE_MASTER_TAB: str = "Rate_Master"
    RFQ_OUTPUT_TAB: str = "RFQ_Output"
    RFQ_ARCHIVE_TAB: str = "RFQ_Database"

    # Microsoft Graph (Outlook source — leave blank if not using)
    AZURE_TENANT_ID: str = ""
    AZURE_CLIENT_ID: str = ""
    AZURE_CLIENT_SECRET: str = ""
    OUTLOOK_USER_ID: str = ""
    OUTLOOK_FOLDER_NAME: str = "RFQ_BOT"

    # Google Docs (optional source — leave blank if not using)
    GOOGLE_DOC_ID: str = ""


    # Ollama
    OLLAMA_BASE_URL: str = "http://10.86.203.21:11435"
    OLLAMA_REQUEST_TIMEOUT: float = 120.0
    OLLAMA_MODEL_EXTRACTOR: str = "qwen3.6:35b"

    # Pricing
    MIN_CONFIDENCE_FOR_PRICING: float = 0.5

    # Logging
    LOG_LEVEL: str = "INFO"


settings = Settings()
