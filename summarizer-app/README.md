# GenAIsummarizer

A self-hosted Python application that summarises text documents, web pages, and user input using Azure OpenAI.

## Features

- **Multi-format input**: Plain text, PDF, DOCX, and web URLs
- **Configurable summary length**: Short, medium, or long
- **REST API**: Endpoints for programmatic integration with JWT authentication
- **Web UI**: Responsive Jinja2-based dashboard with accessibility support
- **Batch processing**: Summarise up to 10 files per request
- **History**: Track previous summaries per user
- **Logging**: Comprehensive audit and error logging

## Project Structure

```
summarizer-app/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # Application entry point
│   │   ├── api.py             # REST API endpoints
│   │   ├── ui.py              # Web UI routes
│   │   ├── config.py          # Configuration from env vars
│   │   ├── logger.py          # Logging setup
│   │   ├── errors.py          # Custom error handling
│   │   └── summarizer/
│   │       ├── __init__.py
│   │       ├── engine.py      # Azure OpenAI summarisation
│   │       └── utils.py       # Text extraction (PDF, DOCX, URL)
│   └── tests/
│       ├── test_api.py
│       ├── test_summarizer.py
│       ├── test_auth.py
│       └── test_history.py
├── frontend/
│   ├── __init__.py
│   └── templates/
│       ├── dashboard.html
│       └── history.html
├── requirements.txt
├── run.py                     # CLI entry point
├── startup.sh                 # Deployment startup script
├── .env                       # Environment variables (not in VCS)
└── README.md
```

## Setup

### 1. Create a virtual environment

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy `.env` and fill in your Azure OpenAI credentials:

| Variable | Description |
|---|---|
| `AZURE_OPENAI_API_KEY` | Your Azure OpenAI API key |
| `AZURE_OPENAI_ENDPOINT` | Your Azure OpenAI endpoint URL |
| `AZURE_OPENAI_DEPLOYMENT` | Model deployment name (default: `gpt-4`) |
| `JWT_SECRET_KEY` | Secret for JWT token signing |

### 4. Run the application

```bash
python run.py
```

The app starts at `http://127.0.0.1:8000`.

- **Web UI**: http://127.0.0.1:8000/
- **API docs**: http://127.0.0.1:8000/docs

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/token` | Get JWT token |
| POST | `/api/summarize/text` | Summarise plain text |
| POST | `/api/summarize/url` | Summarise a web URL |
| POST | `/api/summarize/file` | Summarise an uploaded file |
| POST | `/api/summarize/batch` | Batch summarise files (max 10) |
| GET  | `/api/history` | Get summary history |

## Running Tests

```bash
cd summarizer-app
pytest backend/tests/ -v --cov=backend/app --cov-report=term-missing
```

## Troubleshooting

- **Azure OpenAI errors**: Ensure `AZURE_OPENAI_API_KEY` and `AZURE_OPENAI_ENDPOINT` are set correctly.
- **File upload errors**: Check the file is PDF, DOCX, or TXT and under 10 MB.
- **JWT errors**: Ensure `JWT_SECRET_KEY` is set in your environment.
- **Port conflicts**: Change the `PORT` environment variable if 8000 is in use.
