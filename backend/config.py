from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List
import logging

logger = logging.getLogger(__name__)

allowed_extensions: List[str] = ['.pdf', '.docx', '.html']

class Settings(BaseSettings):
    """Application configuration with validation"""
    
    # API Keys
    google_api_key: str 

    allowed_origins: List[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"
        case_sensitive = False
    
    # Database
    database_name: str = "rag_app.db"
    
    # File Upload Settings
    max_file_size_mb: int = 10
    allowed_extensions: list[str] = ['.pdf', '.docx', '.html']
    upload_dir: str = "uploads"
    
    # Vector Store Settings
    chroma_persist_dir: str = "./chroma_db"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    retriever_k: int = 2
    
    # Model Settings
    default_model: str = "gemini-2.5-flash"
    model_timeout: int = 30
    model_max_retries: int = 1
    model_temperature: float = 0.7
    
    # Chat Settings
    max_chat_history: int = 10
    max_query_length: int = 2000
    session_timeout_hours: int = 24


    # Rate Limiting
    enable_rate_limiting: bool = True
    requests_per_minute: int = 30
    rate_limit_storage_url: str = "memory://"
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "app.log"
    
    # Security
    enable_authentication: bool = False
    enable_file_content_validation: bool = True

    # Emotion Detection
    enable_emotion_detection: bool = True
    emotion_model: str = "gemini-2.5-flash"
    
    enable_metrics: bool = True
    metrics_port: int = 9001


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance"""
    return Settings()

try:
    _ = get_settings()
except Exception as e:
    logger.error(f"configuration error: {e}")
    raise
# Usage example:
# from config import get_settings
# settings = get_settings()
# api_key = settings.google_api_key