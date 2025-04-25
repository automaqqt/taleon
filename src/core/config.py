import os
from dotenv import load_dotenv
from pydantic import BaseSettings

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    """Application settings"""
    
    # Database
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./fairy_tales.db")
    
    # LLM API
    llm_type: str = os.getenv("LLM_TYPE", "openrouter")
    llm_api_url: str = os.getenv("LLM_API_URL", "https://openrouter.ai/api/v1/chat/completions")
    llm_model_name: str = os.getenv("LLM_MODEL_NAME", "google/gemini-2.5-pro-exp-03-25:free")
    openai_api_url: str = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")
    
    # RAG settings
    embedding_model_name: str = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
    chroma_db_path: str = os.getenv("CHROMA_DB_PATH", "./chroma_db")
    chroma_collection_name: str = os.getenv("CHROMA_COLLECTION_NAME", "fairy_tales")
    tale_metadata_path: str = os.getenv("TALE_METADATA_PATH", "./data/tale_metadata.json")
    
    # API settings
    cors_origins: list = [
        "https://edudash.vidsoft.net",
    ]
    
    # Development settings
    debug: bool = os.getenv("DEBUG", "False").lower() in ["true", "1", "yes"]
    
    class Config:
        env_file = ".env"

# Create settings instance

settings = Settings()
print(settings)