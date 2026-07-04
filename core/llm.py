"""
core/llm.py

Thin wrapper around the AI backend. Keeping ALL AI calls behind this one
file means the rest of the app never needs to know which provider is used.

Currently supports:
  - Groq (free API, cloud) -- default
  - Ollama (free, fully local, no internet needed) -- optional fallback

To switch backend, change LLM_BACKEND below or set the environment
variable LLM_BACKEND to "groq" or "ollama".
"""

import os
import json

LLM_BACKEND = os.environ.get("LLM_BACKEND", "groq")


def _call_groq(prompt: str, json_mode: bool = False) -> str:
    from groq import Groq
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

    kwargs = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        **kwargs,
    )
    return response.choices[0].message.content


def _call_ollama(prompt: str, json_mode: bool = False) -> str:
    """Requires Ollama running locally (free, no API key, no internet)."""
    import requests
    payload = {
        "model": os.environ.get("OLLAMA_MODEL", "llama3.1"),
        "prompt": prompt,
        "stream": False,
    }
    if json_mode:
        payload["format"] = "json"

    resp = requests.post("http://localhost:11434/api/generate", json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()["response"]


def call_llm(prompt: str, json_mode: bool = False) -> str:
    """Route to whichever backend is configured."""
    if LLM_BACKEND == "ollama":
        return _call_ollama(prompt, json_mode=json_mode)
    return _call_groq(prompt, json_mode=json_mode)


def extract_json(prompt: str, retries: int = 2) -> dict:
    """
    Calls the LLM asking for JSON, parses it, and retries with a stricter
    instruction if the model returns something that isn't valid JSON.
    This is the "retry-until-valid loop" we discussed.
    """
    attempt_prompt = prompt
    last_error = None

    for attempt in range(retries + 1):
        raw = call_llm(attempt_prompt, json_mode=True)
        cleaned = raw.strip()
        # Strip markdown code fences if the model added them anyway
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:]
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            last_error = e
            attempt_prompt = (
                prompt
                + "\n\nIMPORTANT: Your previous reply was not valid JSON. "
                + "Reply with ONLY a valid JSON object, no explanation, no markdown."
            )

    raise ValueError(f"LLM did not return valid JSON after {retries + 1} attempts: {last_error}")
