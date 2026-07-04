"""Application configuration via pydantic-settings.

Every value comes from environment variables / the .env file — no secret is ever
hardcoded. `get_settings()` is cached so .env is parsed once per process.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- LLM provider selection (the single switch; see providers/factory.py) ---
    llm_provider: str = "deepseek"

    # --- DeepSeek (primary dev provider) ---
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"

    # --- Gemini (secondary dev provider + LLM-as-judge) ---
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # --- LLM-as-judge (MUST differ from the generation model to avoid identity bias) ---
    judge_provider: str = "gemini"
    judge_model: str = "gemini-2.5-flash"

    # --- Cloud stubs (prod-ready adapters, never actually called) ---
    bedrock_model: str = "anthropic.claude-3-5-sonnet"
    aws_region: str = "us-east-1"
    azure_model: str = "gpt-4o"
    azure_endpoint: str = ""

    # --- Infrastructure ---
    qdrant_url: str = "http://localhost:6333"
    postgres_dsn: str = "postgresql://raas:raas@localhost:5432/raas"

    # --- Observability (Langfuse) ---
    langfuse_host: str = "http://localhost:3000"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    # --- Embeddings (local sentence-transformers, free) ---
    embedding_model: str = "intfloat/multilingual-e5-base"

    # --- RAG / retrieval defaults (tuned against the eval harness) ---
    chunk_size: int = 800
    chunk_overlap: int = 120
    retrieval_top_k: int = 5
    # Cross-encoder reranking (before/after measured in eval/, see eval_report).
    rerank_enabled: bool = False

    # --- Guardrails ---
    # Hard cap on grounded-generation context (token-bomb protection).
    max_context_chars: int = 12000

    # --- Auth (JWT) ---
    # OFF by default so the demo/`docker compose up` needs no tokens. When ON,
    # tenant-scoped endpoints require a valid Bearer JWT whose tenant_id claim
    # must match the requested tenant. Supabase-compatible (HS256). See D14.
    auth_enabled: bool = False
    jwt_secret: str = ""
    # Demo credential for POST /auth/token (stand-in for a real IdP; see D14).
    auth_demo_password: str = ""

    # --- App ---
    app_env: str = "dev"
    api_port: int = 8000


@lru_cache
def get_settings() -> Settings:
    return Settings()
