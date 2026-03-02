"""
Application entry point – starts the FastAPI web server,
loads config, initialises logger, and mounts API + UI routers.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.app import config
from backend.app.api import router as api_router
from backend.app.ui import router as ui_router
from backend.app.errors import SummarizerError, summarizer_error_handler, generic_error_handler
from backend.app.logger import get_logger

logger = get_logger()

# Validate Azure OpenAI config at startup
_az_ok, _az_msg = config.validate_azure_openai_config()
if _az_ok:
    logger.info(_az_msg)
else:
    logger.warning(_az_msg + " – summarisation will fail until credentials are provided.")

app = FastAPI(
    title="GenAIsummarizer",
    description="Self-hosted AI-powered document summariser",
    version="1.0.0",
)

# Register error handlers
app.add_exception_handler(SummarizerError, summarizer_error_handler)
app.add_exception_handler(Exception, generic_error_handler)

# Mount API and UI routers
app.include_router(api_router, prefix="/api", tags=["API"])
app.include_router(ui_router, tags=["UI"])

logger.info("GenAIsummarizer application started.")
