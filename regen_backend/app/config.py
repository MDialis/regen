# app/config.py
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App Metadata
    APP_NAME: str = "REGEN - Legacy Modernization & Architecture Scaffolder"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # CORS (Next.js Frontend)
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Hybrid LLM Configuration
    OPENAI_API_KEY: str = ""
    OPENAI_REASONING_MODEL: str = "gpt-4o"
    OPENAI_VISION_MODEL: str = "gpt-4o"

    # Local Fallback / Boilerplate Generator (Ollama)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_CODER_MODEL: str = "qwen2.5-coder:7b"

    # Phase 1: Deterministic Token Saver Thresholds
    # AST nodes below min complexity are parsed deterministically without LLM calls
    MIN_CYCLOMATIC_COMPLEXITY_FOR_LLM: int = 4
    MAX_CHUNK_TOKENS: int = 2000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
