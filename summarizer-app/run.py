"""
CLI entry point to start the GenAIsummarizer web server.
Host defaults to 127.0.0.1 for local development.
Port is read from the PORT environment variable, falling back to 8000.
"""

import os
import uvicorn

if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    print(f"=== Starting GenAIsummarizer on {host}:{port} ===")
    uvicorn.run("backend.app.main:app", host=host, port=port, reload=True)
