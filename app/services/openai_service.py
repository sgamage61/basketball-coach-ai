from typing import Any

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class OpenAIService:
    """
    Abstraction layer over the OpenAI async client.

    Keeps all model/token/temperature config in one place so agents and
    services never import OpenAI directly — swap the provider here.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model
        self._max_tokens = settings.openai_max_tokens
        self._temperature = settings.openai_temperature

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, str] | None = None,
    ) -> str:
        """Send a single chat-completion request and return the response text."""
        kwargs: dict[str, Any] = {
            "model": self._model,
            "temperature": temperature if temperature is not None else self._temperature,
            "max_tokens": max_tokens or self._max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if response_format:
            kwargs["response_format"] = response_format

        logger.debug("OpenAI request", model=self._model)
        response: ChatCompletion = await self._client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content or ""
        logger.debug(
            "OpenAI response",
            model=self._model,
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=response.usage.completion_tokens if response.usage else 0,
        )
        return content

    async def generate_coaching_insight(self, context_json: str) -> str:
        """Specialised prompt for basketball coaching recommendations."""
        system = (
            "You are an elite NBA basketball analyst and head coach advisor. "
            "Analyse the provided game state JSON and return a concise, actionable coaching recommendation. "
            "Focus on exploitable matchups, momentum shifts, and high-leverage tactical adjustments. "
            "Be direct and specific — coaches need actionable intel, not commentary."
        )
        return await self.chat(system, context_json)
