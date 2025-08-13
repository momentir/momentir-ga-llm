from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost/dbname"
    DATABASE_HOST: str = "localhost"
    DATABASE_PORT: str = "5432"
    DATABASE_USERNAME: str = "postgres"
    DATABASE_PASSWORD: str = "password"
    DATABASE_DEFAULT_SCHEMA: str = "momentir_auth"
    
    # JWT
    JWT_SECRET_KEY: str = "your-secret-key-here"
    
    # AWS SES
    AWS_REGION: str = "ap-northeast-2"
    AWS_SES_ACCESS_KEY: str = ""
    AWS_SES_SECRET_ACCESS_KEY: str = ""
    AWS_SES_FROM_EMAIL: str = "noreply@yourdomain.com"
    
    # Server
    SERVER_PORT: str = "8000"
    
    # Skip migration for testing
    SKIP_MIGRATION: bool = False
    
    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_API_TYPE: str = "openai"
    
    # Azure OpenAI
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_API_VERSION: str = ""
    AZURE_OPENAI_CHAT_DEPLOYMENT_NAME: str = ""
    
    # Azure Embedding
    AZURE_EMBEDDING_ENDPOINT: str = ""
    AZURE_EMBEDDING_API_KEY: str = ""
    AZURE_EMBEDDING_API_VERSION: str = ""
    AZURE_EMBEDDING_DEPLOYMENT_NAME: str = ""
    
    # LangSmith
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_TRACING: str = "false"
    LANGSMITH_PROJECT: str = ""
    LANGCHAIN_TRACING_V2: str = "false" 
    LANGCHAIN_ENDPOINT: str = ""
    
    # Environment settings
    SQL_ECHO: str = "false"
    AUTO_CREATE_TABLES: str = "false"
    ENVIRONMENT: str = "local"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"  # Allow extra fields that aren't defined


@lru_cache()
def get_settings():
    return Settings()