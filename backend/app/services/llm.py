from typing import Protocol

import google.generativeai as genai

from app.core.config import settings


class LlmProvider(Protocol):
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        ...


class GeminiProvider:
    def __init__(self, api_key: str, model_name: str) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required for Gemini.")
        genai.configure(api_key=api_key)
        self.model_name = model_name

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        model = genai.GenerativeModel(self.model_name, system_instruction=system_prompt)
        response = model.generate_content(
            user_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.2,
                max_output_tokens=900,
            ),
        )
        return getattr(response, "text", "") or ""


class LlmService:
    def __init__(self) -> None:
        provider = settings.llm_provider.lower()
        if provider == "gemini":
            self.provider: LlmProvider = GeminiProvider(
                settings.gemini_api_key,
                settings.llm_model,
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return self.provider.generate(system_prompt, user_prompt)


llm_service = LlmService()


def generate_answer(system_prompt: str, user_prompt: str) -> str:
    return llm_service.generate(system_prompt, user_prompt)
