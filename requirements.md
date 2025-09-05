GenAIsummarizer app is a self-hosted Python application that summarizes text documents, web pages, and user input. The application should be easy to deploy on-premises or in a cloud web app. It is implemented entirely in Python, including the web UI and REST API. Both the backend and frontend will be in Python only.

The Functional Requirements of this app is:
- Accepts input as plain text, PDF, DOCX, and web URLs
- Maximum file size for uploads is 10MB
- Generates concise summaries (configurable length: short, medium, long)
- Provides REST API endpoints for integration
- Offers a simple, responsive web UI for manual summarization (Python/Jinja2 templates)
- Allows batch processing of up to 10 files per request
- Logging and error handling with user-friendly messages
- API authentication via JWT tokens
- History of previous summaries per user

The Non-Functional Requirements of this app is:
- Self-hosted: runs on Windows or Linux servers
- Python 3.8+ compatibility
- Minimal external dependencies, all listed in requirements.txt
- Easy installation using pip and virtual environment
- Responsive and accessible web UI (Python/Jinja2 templates, keyboard navigation, screen reader support)
- Configured with Azure OpenAI model using environment variables for keys and endpoints
- Scalable for large document sets (horizontal scaling supported)
- Documentation for setup, usage, and troubleshooting
- Error messages are clear and actionable for users
- All configuration and secrets are managed via environment variables

Setup Checklist:
1. Create and activate a Python virtual environment.
2. Install dependencies from requirements.txt.
3. Run the app using run.py.
4. Access the web UI and REST API.
5. When the app is successfully running, set environment variables for Azure OpenAI keys and endpoints.
6. Access the web UI and REST API and test the features.
5. Review documentation in README.md for usage and troubleshooting.

Note: Both backend and frontend are implemented in Python only.