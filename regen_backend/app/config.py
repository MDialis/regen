# app/config.py
from typing import Dict, List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "REGEN - Legacy Modernization & Architecture Scaffolder"
    APP_VERSION: str = "0.2.0"
    DEBUG: bool = True

    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Optional Cloud Fallback
    OPENAI_API_KEY: str = ""
    OPENAI_REASONING_MODEL: str = "gpt-4o"

    # Local Ollama Configuration
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    # If True, forces ALL tasks to use `phi4-mini` (~2.5GB VRAM/RAM) for low-end PCs
    LOW_VRAM_MODE: bool = True

    # Task-Specific Local Model Dispatcher (used when LOW_VRAM_MODE = False)
    LLM_TASK_MODELS: Dict[str, str] = {
        "requirement_extraction": "phi4-mini",  # Step 1: Fast JSON entity/rule inference
        "architecture_advisor": "deepseek-r1:8b",  # Step 3: Stack & pattern trade-off reasoning
    }

    # Phase 1: Deterministic Token Saver Thresholds
    MIN_CYCLOMATIC_COMPLEXITY_FOR_LLM: int = 4
    MAX_CHUNK_TOKENS: int = 2000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def get_model_for_task(self, task: str) -> str:
        if self.LOW_VRAM_MODE:
            return "phi4-mini"
        return self.LLM_TASK_MODELS.get(task, "phi4-mini")


settings = Settings()
