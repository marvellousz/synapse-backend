#!/usr/bin/env python3
"""
Quick check that Gemini API key is set and the API responds.
Run from synapse-backend with: ./venv/bin/python check_gemini.py
"""
import sys

# Load .env via config
from app.config import GEMINI_API_KEY
from app.services.extraction.gemini_client import GEMINI_MODEL, get_client


def main():
    if not GEMINI_API_KEY:
        print("FAIL: GEMINI_API_KEY is not set (check .env)")
        sys.exit(1)
    print(f"GEMINI_API_KEY: set ({GEMINI_API_KEY[:8]}...)")
    print(f"Model: {GEMINI_MODEL}")

    client = get_client()
    if not client:
        print("FAIL: Could not create Gemini client")
        sys.exit(1)
    print("Client: OK")

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents="Reply with exactly: Gemini is working.",
        )
        text = getattr(response, "text", None) if response else None
        if text:
            print(f"Response: {text.strip()}")
            print("OK: Gemini is working.")
        else:
            print("FAIL: No text in response (maybe blocked or wrong model)")
            if response:
                print("Raw response:", response)
            sys.exit(1)
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
