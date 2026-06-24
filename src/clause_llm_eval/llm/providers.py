from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

import requests
from dotenv import load_dotenv


load_dotenv()


class LLMProvider(Protocol):
    def complete(self, prompt: str, model: str, temperature: float = 0.0) -> str:
        ...


@dataclass
class MockProvider:
    seed: int = 42

    def complete(self, prompt: str, model: str = "mock", temperature: float = 0.0) -> str:
        lower = prompt.lower()
        if 'reply with only "yes" or "no"' in lower:
            return "Yes" if any(w in lower for w in ["contradict", "discrepancy", "however"]) else "No"
        if "reply with only one label" in lower:
            if "law" in lower or "statute" in lower or "regulation" in lower:
                return "legal"
            return "in_text"
        return '{"has_discrepancy": true, "dimension": "in_text", "spans": [{"text": "mock span", "explanation": "mock explanation", "law_citation": null}]}'


@dataclass
class OpenAIProvider:
    def complete(self, prompt: str, model: str, temperature: float = 0.0) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content or ""


@dataclass
class GeminiProvider:
    def complete(self, prompt: str, model: str, temperature: float = 0.0) -> str:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
            ),
        )
        return response.text or ""


@dataclass
class OllamaProvider:
    base_url: str | None = None

    def complete(self, prompt: str, model: str, temperature: float = 0.0) -> str:
        base_url = self.base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        url = base_url.rstrip("/") + "/api/generate"

        response = requests.post(
            url,
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                },
            },
            timeout=300,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "")


def get_provider(name: str) -> LLMProvider:
    name = name.lower().strip()

    if name == "mock":
        return MockProvider()
    if name == "openai":
        return OpenAIProvider()
    if name == "gemini":
        return GeminiProvider()
    if name == "ollama":
        return OllamaProvider()

    raise ValueError(f"Provider desconhecido: {name}")
