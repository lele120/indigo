from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Authentication
    OPENAI_API_KEY: str
    MCP_API_KEY: str
    SECRET_KEY: str

    # Database
    DATABASE_URL: str = "postgresql://indigo:password@postgres:5432/indigo"
    DB_PASSWORD: str = "password"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Qdrant
    QDRANT_HOST: str = "qdrant"
    QDRANT_HTTP_PORT: int = 6333
    QDRANT_GRPC_PORT: int = 6334
    QDRANT_COLLECTION_NAME: str = "documents"

    # Celery
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"

    # Chunking & Embedding
    CHUNK_SIZE: int = 1000  # tokens
    CHUNK_OVERLAP: int = 200  # tokens
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_BATCH_SIZE: int = 100

    # File Upload
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    ALLOWED_MIME_TYPES: List[str] = ["application/pdf", "text/plain"]
    ALLOWED_EXTENSIONS: List[str] = [".pdf", ".txt"]

    # Feature Flags
    ENABLE_HYBRID_SEARCH: bool = True
    ENABLE_RERANKING: bool = False
    ENABLE_RATE_LIMITING: bool = True

    # Search
    BM25_CACHE_TTL: int = 3600  # seconds
    SEARCH_CACHE_TTL: int = 1800  # seconds

    # Logging
    LOG_LEVEL: str = "INFO"
    STRUCTLOG_ENABLED: bool = True

    # Monitoring
    PROMETHEUS_ENABLED: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
