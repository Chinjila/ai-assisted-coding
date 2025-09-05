I want to build a GenAIsummarizer app that will include the following:

- Accepts input as plain text, PDF, DOCX, and web URLs
- Generates concise summaries (configurable length)
- Provides REST API endpoints for integration
- Offers a simple web UI for manual summarization
- Allows batch processing of files
- Logging and error handling

It should be in one app

The directory tree for the GenAIsummarizer App:

summarizer-app/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                # Application entry point, starts web server
│   │   ├── api.py                 # REST API endpoints (summarize, batch, history)
│   │   ├── ui.py                  # Web UI backend logic (Python)
│   │   ├── summarizer/
│   │   │   ├── __init__.py
│   │   │   ├── utils.py           # Text extraction, format parsing (PDF, DOCX, URL)
│   │   │   └── engine.py          # Summarization logic, configurable length
│   │   ├── config.py              # App configuration (env vars, summary length)
│   │   ├── logger.py              # Logging setup (actions, errors)
│   │   └── errors.py              # Custom error handling
│   ├── tests/
│   │   ├── test_api.py             # Unit tests for API endpoints
│   │   ├── test_summarizer.py      # Unit tests for summarization logic
│   │   ├── test_auth.py            # Unit tests for authentication
│   │   └── test_history.py         # Unit tests for history tracking
├── frontend/
│   ├── templates/                 # Jinja2 Python templates for UI
│   └── __init__.py                # Python module for frontend logic
└── requirements.txt               # Python dependencies
├── README.md                      # Setup and usage documentation
├── run.py                         # CLI to start app (web server, batch jobs)
└── .env                           # Environment variables (not in version control)
└── startup.sh                     # Startup script for deployment

The files should be organized and created in the above provided directory structure.

The use and function of each file is as follows:
- backend/app/main.py: starts the app, loads config, initializes logger, and mounts API/UI.
- backend/app/api.py: exposes endpoints for summarization, batch processing, and history. Calls summarizer/engine.py for summary generation and history.py for storing/retrieving summaries.
- backend/app/ui.py: serves the dashboard, upload forms, and history views. Communicates with api.py via Python.
- backend/app/summarizer/utils.py: extracts text from PDF, DOCX, or URLs. Used by both API and UI.
- backend/app/summarizer/engine.py: generates summaries based on configurable length. Called by API/UI.
- backend/app/config.py: loads environment variables and settings (e.g., summary length, auth tokens).
- backend/app/logger.py: logs all actions and errors for audit/debugging. Used throughout the app.
- backend/app/errors.py: defines custom error classes and handlers for API/UI.
- frontend/templates/: Jinja2 Python templates for dashboard, upload, history, etc.
- requirements.txt: Python dependencies for backend.
- run.py: CLI to start app (web server, batch jobs).
- .env: Environment variables (not in version control).
- startup.sh: Startup script for deployment (e.g., Azure Web App).


Create a requirements.txt file with the following Python required packages:
fastapi
uvicorn
pydantic
python-docx
PyPDF2
requests
beautifulsoup4
openai
jinja2
python-jose
aiofiles
loguru
python-multipart
python-dotenv

When generating or updating requirements.txt, always copy the full list of Python packages exactly as specified in architecture.md. Do not omit, add, or modify any package names. If requirements.txt already exists, replace its contents with the complete, exact list from architecture.md. Double-check that every package from architecture.md is present in requirements.txt.

When generating or updating run.py, always set the host to "127.0.0.1" for local development. Do not use "0.0.0.0" unless explicitly requested for deployment. The default port should be read from the PORT environment variable, falling back to 8000 if not set.

When generating or updating startup.sh, always use the exact commands and structure as shown below. Do not add, remove, or modify any commands unless explicitly requested. The script must:

- Upgrade pip
- Install dependencies from requirements.txt if it exists
- Start the app using python run.py
- Exit immediately if any command fails
- Print clear status messages for each step
- Example startup.sh:

#!/bin/bash
set -e
echo "=== Installing Python dependencies ==="
if [ -f requirements.txt ]; then
  pip install --upgrade pip
  pip install -r requirements.txt
else
  echo "No requirements.txt found, skipping pip install."
fi
echo "=== Starting the app ==="
python run.py


All the packages listed in requirements.txt file should be installed in the Python environment.

All of the backend app will be in summarizer-app/backend and all frontend files in summarizer-app/frontend.

Both backend and frontend are implemented in Python only.

Use a Python virtual environment and install all python dependencies from backend/requirements.txt in this workspace. To run tests, use pytest from the backend/tests/ directory. Aim for at least 80% code coverage. Store secrets and configuration in environment variables, not in code.

Follow this structure and instructions to avoid errors and ensure a smooth deployment.

Let's think about this step by step.