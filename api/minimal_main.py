import os
from typing import Dict
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# Minimal FastAPI app for deployment testing
app = FastAPI(title="Document Portal API - Minimal", version="0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Document Portal</title>
    </head>
    <body>
        <h1>Document Portal API</h1>
        <p>API is running successfully!</p>
        <p>This is a minimal version for deployment testing.</p>
    </body>
    </html>
    """

@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "document-portal-minimal"}

@app.get("/test")
def test() -> Dict[str, str]:
    return {"message": "API is working!", "memory_usage": "optimized"}


