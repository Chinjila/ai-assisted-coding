# Copilot Instructions – GenAIsummarizer

## Architecture Overview

This is a **monorepo** with the application code under `summarizer-app/`. The app is a FastAPI Python web app that summarizes text, PDFs, DOCX files, and URLs using **Azure OpenAI**. It serves both a Jinja2 web UI and a REST API from a single process.

**Key layers** (request flow top-down):
1. `backend/app/main.py` – FastAPI entry point; mounts routers and error handlers
2. `backend/app/ui.py` (web UI) / `backend/app/api.py` (REST API) – routing only; delegate all logic to the service layer
3. `backend/app/summarizer/service.py` – **central orchestrator**: validation, text extraction, AI calls, history management
4. `backend/app/summarizer/engine.py` – Azure OpenAI client with async retry + exponential backoff
5. `backend/app/summarizer/utils.py` – file/URL text extraction (PDF, DOCX, HTML)

**Never put business logic in `api.py` or `ui.py`** – those are routing-only. All logic goes through `service.py`.

## Running Locally

```bash
cd summarizer-app
python -m venv venv
# Windows: venv\Scripts\activate | Linux: source venv/bin/activate
pip install -r requirements.txt
python run.py  # starts on http://127.0.0.1:8000
```

- `run.py` defaults to `HOST=127.0.0.1` for local dev. Use `HOST=0.0.0.0` only for deployment.
- `.env` must exist in `summarizer-app/` with Azure OpenAI credentials. See `config.py` for all vars.

## Configuration (`backend/app/config.py`)

All config is via env vars loaded from `summarizer-app/.env` using `python-dotenv`. Key groups:
- **Azure OpenAI**: `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION`
- **JWT Auth**: `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_EXPIRATION_MINUTES`
- **App Limits**: `MAX_FILE_SIZE_MB` (10), `MAX_BATCH_FILES` (10), `DEFAULT_SUMMARY_LENGTH` (medium)
- **Retry**: `RETRY_MAX_ATTEMPTS` (3), `RETRY_BASE_DELAY_SECONDS`, `RETRY_MAX_DELAY_SECONDS`

## Error Handling Pattern

All custom exceptions inherit from `SummarizerError` in `backend/app/errors.py`. Each carries a `message` and `status_code`. Specific subclasses: `FileFormatError`, `FileSizeError`, `BatchLimitError`, `SummarizationError`, `AuthenticationError`, `URLFetchError`. Global handlers in `main.py` catch these and return structured JSON.

## Testing

```bash
cd summarizer-app
pytest backend/tests/ -v --cov=backend
```

- Tests use `unittest.mock.patch` and `AsyncMock` to mock `service.py` methods
- `TestClient(app)` from FastAPI for endpoint tests
- `service.clear_history()` resets in-memory history between tests

## Requirements & Dependencies

`requirements.txt` must exactly match the package list in `architecture.md`. When updating, copy the full list — do not add/remove packages without updating both files.

## Deployment (Azure Web App)

- **CI/CD**: `.github/workflows/deploy.yml` deploys on push to `main` or manual trigger
- **Startup**: `summarizer-app/startup.sh` runs on Azure — it `cd`s to `/home/site/wwwroot/summarizer-app`, installs deps, then runs `python run.py`
- **Runtime**: Linux, Python 3.12, Basic B1 App Service Plan
- **App Settings**: Set via Azure Portal or `az webapp config appsettings set` (all `.env` vars)

## Key Conventions

- **Imports use full package paths**: `from backend.app.summarizer.engine import summarize_text` (not relative)
- **Async throughout**: engine and service methods are `async`; use `await` consistently
- **Summary lengths**: only `"short"`, `"medium"`, `"long"` — mapped to prompts in `config.SUMMARY_LENGTH_PROMPTS`
- **History is in-memory** (`service._summary_history` dict) — not persisted across restarts
- **Logging**: use `from backend.app.logger import get_logger` — Loguru-based, not stdlib
