"""The one place that talks to the LLM. Swap providers by changing only this file."""

import json
import os
import sys
from functools import lru_cache

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")


@lru_cache
def get_client() -> genai.Client:
    """Create one Gemini client from the key in .env and reuse it.

    Cached so the client stays alive: a throwaway client gets garbage-collected,
    which closes its connection mid-request.
    """
    key = os.getenv("GEMINI_API_KEY", "")
    if not key or key == "paste-your-key-here":
        raise RuntimeError("Put your Gemini API key in .env as GEMINI_API_KEY=...")
    return genai.Client(api_key=key)


def ask_json(system: str, prompt: str) -> dict:
    """Send a prompt and get back parsed JSON. Low temperature keeps it factual."""
    response = get_client().models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    return json.loads(response.text)


if __name__ == "__main__":
    if sys.argv[1:] == ["models"]:
        for model in get_client().models.list():
            if "generateContent" in (model.supported_actions or []):
                print(model.name)
    else:
        print(ask_json("Reply in JSON.", 'Return {"status": "ok", "model": "<your model name>"}'))
