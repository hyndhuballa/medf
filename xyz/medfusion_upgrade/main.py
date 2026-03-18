"""
main.py — Entry point
Run: uvicorn main:app --reload --port 8000
"""
from api.app import app  # noqa: F401
