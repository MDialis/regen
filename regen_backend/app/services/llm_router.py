# app/services/llm_router.py
import json
import re
from typing import Optional, Type, TypeVar
import httpx
from pydantic import BaseModel

from app.config import settings

T = TypeVar("T", bound=BaseModel)


class LocalLLMRouter:
    """
    Task-specific LLM router that calls local Ollama with structured JSON schemas.
    Automatically falls back to `phi4-mini` on low-VRAM PCs or if a larger model is missing.
    """

    async def generate_structured(
        self,
        task: str,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
        force_low_vram: Optional[bool] = None,
    ) -> Optional[T]:
        model_name = (
            "phi4-mini" if force_low_vram else settings.get_model_for_task(task)
        )

        result = await self._call_ollama_structured(
            model_name, system_prompt, user_prompt, response_model
        )
        # Automatic fallback to phi4-mini if a heavier specialist model isn't pulled locally
        if result is None and model_name != "phi4-mini":
            result = await self._call_ollama_structured(
                "phi4-mini", system_prompt, user_prompt, response_model
            )
        return result

    async def _call_ollama_structured(
        self,
        model_name: str,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[T],
    ) -> Optional[T]:
        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat"
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "format": response_model.model_json_schema(),
            "stream": False,
            "options": {"temperature": 0.1},
        }

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code != 200:
                    return None
                data = resp.json()
                raw_content = data.get("message", {}).get("content", "")
                # Strip <think>...</think> blocks if deepseek-r1 is used
                cleaned = re.sub(
                    r"<think>.*?</think>", "", raw_content, flags=re.DOTALL
                ).strip()
                return response_model.model_validate_json(cleaned)
        except Exception:
            return None


llm_router = LocalLLMRouter()
