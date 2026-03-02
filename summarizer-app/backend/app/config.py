"""
Application configuration loaded from environment variables.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root (summarizer-app/) regardless of CWD
_project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=_project_root / ".env")

# Azure OpenAI settings
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")

# JWT Authentication
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRATION_MINUTES = int(os.getenv("JWT_EXPIRATION_MINUTES", "60"))

# App settings
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
MAX_BATCH_FILES = int(os.getenv("MAX_BATCH_FILES", "10"))
DEFAULT_SUMMARY_LENGTH = os.getenv("DEFAULT_SUMMARY_LENGTH", "medium")
ALLOWED_SUMMARY_LENGTHS = ["short", "medium", "long"]

# Retry settings for Azure OpenAI calls
RETRY_MAX_ATTEMPTS = int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))
RETRY_BASE_DELAY_SECONDS = float(os.getenv("RETRY_BASE_DELAY_SECONDS", "1.0"))
RETRY_MAX_DELAY_SECONDS = float(os.getenv("RETRY_MAX_DELAY_SECONDS", "10.0"))

# Server settings
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

# Summary length prompt mapping
SUMMARY_LENGTH_PROMPTS = {
    "short": "Provide a very concise summary in 2-3 sentences.",
    "medium": "Provide a summary in 1-2 paragraphs covering key points.",
    "long": "Provide a detailed summary covering all major points and supporting details.",
}


def validate_azure_openai_config() -> tuple[bool, str]:
    """Check whether Azure OpenAI credentials are configured.

    Returns (is_valid, message).
    """
    missing = []
    if not AZURE_OPENAI_API_KEY or AZURE_OPENAI_API_KEY == "your-azure-openai-api-key":
        missing.append("AZURE_OPENAI_API_KEY")
    if not AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_ENDPOINT == "https://your-resource.openai.azure.com/":
        missing.append("AZURE_OPENAI_ENDPOINT")
    if not AZURE_OPENAI_DEPLOYMENT:
        missing.append("AZURE_OPENAI_DEPLOYMENT")
    if missing:
        return False, f"Missing Azure OpenAI env vars: {', '.join(missing)}"
    return True, "Azure OpenAI configuration OK."
