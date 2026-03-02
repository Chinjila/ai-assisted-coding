"""
Summarisation engine – calls Azure OpenAI to generate summaries.
Supports configurable length: short, medium, long.

Includes retry logic with exponential backoff for transient failures.
"""

from __future__ import annotations

import asyncio

from openai import (
    AsyncAzureOpenAI,
    APIConnectionError,
    APITimeoutError,
    AuthenticationError as OpenAIAuthenticationError,
    RateLimitError,
    APIStatusError,
)

from backend.app import config
from backend.app.errors import SummarizationError
from backend.app.logger import get_logger

logger = get_logger()

# Transient error types that are safe to retry
_RETRYABLE_EXCEPTIONS = (APIConnectionError, APITimeoutError, RateLimitError)


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


def _build_messages(input_text: str, summary_length: str) -> list[dict]:
    """Build the chat messages list for the Azure OpenAI completion request.

    Encapsulates prompt construction so that `summarize_text` stays focused
    on the retry/call lifecycle.
    """
    length_prompt = config.SUMMARY_LENGTH_PROMPTS.get(
        summary_length, config.SUMMARY_LENGTH_PROMPTS["medium"]
    )
    system_message = (
        "You are a helpful assistant that summarises documents. "
        f"{length_prompt}"
    )
    return [
        {"role": "system", "content": system_message},
        {"role": "user", "content": f"Please summarise the following text:\n\n{input_text}"},
    ]


async def summarize_text(input_text: str, summary_length: str = "medium") -> str:
    """
    Summarise *input_text* using Azure OpenAI with retry + exponential backoff.

    Parameters
    ----------
    input_text : str
        The input text to summarise.
    summary_length : str
        One of 'short', 'medium', or 'long'.

    Returns
    -------
    str
        The generated summary.

    Raises
    ------
    SummarizationError
        With a user-friendly message describing what went wrong.
    """
    logger.info(
        f"Summarisation started – length={summary_length}, "
        f"input_chars={len(input_text)}"
    )

    if not input_text or not input_text.strip():
        raise SummarizationError("No text provided for summarisation.")

    messages = _build_messages(input_text, summary_length)
    client = _get_client()
    last_exception: Exception | None = None

    for attempt in range(1, config.RETRY_MAX_ATTEMPTS + 1):
        try:
            response = await client.chat.completions.create(
                model=config.AZURE_OPENAI_DEPLOYMENT,
                messages=messages,
                temperature=0.3,
                max_tokens=_max_tokens_for_length(summary_length),
            )
            summary_result = response.choices[0].message.content.strip()
            logger.info(
                f"Summarisation completed – length={summary_length}, "
                f"output_chars={len(summary_result)}"
                + (f" (after {attempt} attempt(s))" if attempt > 1 else "")
            )
            return summary_result

        except _RETRYABLE_EXCEPTIONS as exc:
            last_exception = exc
            delay = min(
                config.RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1)),
                config.RETRY_MAX_DELAY_SECONDS,
            )
            logger.warning(
                f"Azure OpenAI transient error (attempt {attempt}/{config.RETRY_MAX_ATTEMPTS}): "
                f"{type(exc).__name__}: {exc} – retrying in {delay:.1f}s"
            )
            if attempt < config.RETRY_MAX_ATTEMPTS:
                await asyncio.sleep(delay)

        except OpenAIAuthenticationError as exc:
            logger.error(f"Azure OpenAI authentication failed: {exc}")
            raise SummarizationError(
                "Authentication with Azure OpenAI failed. "
                "Please check your API key and endpoint configuration."
            )

        except APIStatusError as exc:
            # Non-retryable server errors (4xx other than 401/429, etc.)
            logger.error(f"Azure OpenAI API error ({exc.status_code}): {exc.message}")
            raise SummarizationError(
                f"The summarisation service returned an error (HTTP {exc.status_code}). "
                "Please try again later or contact support."
            )

        except Exception as exc:
            logger.error(
                f"Unexpected error during summarisation: {type(exc).__name__}: {exc}"
            )
            raise SummarizationError(
                "An unexpected error occurred while generating the summary. "
                "Please try again later."
            )

    # All retries exhausted
    logger.error(
        f"All {config.RETRY_MAX_ATTEMPTS} Azure OpenAI attempts failed. "
        f"Last error: {type(last_exception).__name__}: {last_exception}"
    )
    raise SummarizationError(
        f"The summarisation service is temporarily unavailable after "
        f"{config.RETRY_MAX_ATTEMPTS} attempts. Please try again in a few moments."
    )


def _max_tokens_for_length(summary_length: str) -> int:
    """Return appropriate max_tokens for the requested summary length."""
    return {"short": 150, "medium": 400, "long": 1000}.get(summary_length, 400)
