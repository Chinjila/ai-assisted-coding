"""
Summarisation engine – calls Azure OpenAI to generate summaries.
Supports configurable length: short, medium, long.
"""

from __future__ import annotations

from openai import AsyncAzureOpenAI

from backend.app import config
from backend.app.errors import SummarizationError
from backend.app.logger import get_logger

logger = get_logger()


def _get_client() -> AsyncAzureOpenAI:
    """Create an Azure OpenAI async client from config.

    Raises SummarizationError if credentials are not configured.
    """
    is_valid, msg = config.validate_azure_openai_config()
    if not is_valid:
        raise SummarizationError(
            f"Azure OpenAI is not configured. {msg}. "
            "Set the required environment variables in your .env file and restart the app."
        )
    return AsyncAzureOpenAI(
        api_key=config.AZURE_OPENAI_API_KEY,
        api_version=config.AZURE_OPENAI_API_VERSION,
        azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
    )


async def summarize_text(text: str, summary_length: str = "medium") -> str:
    """
    Summarise *text* using Azure OpenAI.

    Parameters
    ----------
    text : str
        The input text to summarise.
    summary_length : str
        One of 'short', 'medium', or 'long'.

    Returns
    -------
    str
        The generated summary.
    """
    if not text or not text.strip():
        raise SummarizationError("No text provided for summarisation.")

    length_prompt = config.SUMMARY_LENGTH_PROMPTS.get(
        summary_length, config.SUMMARY_LENGTH_PROMPTS["medium"]
    )

    system_message = (
        "You are a helpful assistant that summarises documents. "
        f"{length_prompt}"
    )

    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model=config.AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": f"Please summarise the following text:\n\n{text}"},
            ],
            temperature=0.3,
            max_tokens=_max_tokens_for_length(summary_length),
        )
        summary = response.choices[0].message.content.strip()
        logger.info(f"Summary generated – length={summary_length}, chars={len(summary)}")
        return summary
    except Exception as exc:
        logger.error(f"Summarisation failed: {exc}")
        raise SummarizationError(f"Summarisation failed: {exc}")


def _max_tokens_for_length(summary_length: str) -> int:
    """Return appropriate max_tokens for the requested summary length."""
    return {"short": 150, "medium": 400, "long": 1000}.get(summary_length, 400)
