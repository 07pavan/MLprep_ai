import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # API Keys
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    
    # LLM Configuration - UPDATED MODELS
    PRIMARY_MODEL = "llama-3.3-70b-versatile"
    BACKUP_MODEL = "gemini-1.5-flash"
    TEMPERATURE = 0.1
    MAX_TOKENS = 2000
    
    # App Configuration
    MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", 100))
    ENABLE_CACHE = os.getenv("ENABLE_CACHE", "true").lower() == "true"
    
    # LangSmith - DISABLED BY DEFAULT
    LANGCHAIN_TRACING_V2 = "false"
    LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY", "")
    LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "data-analyst-agent")

settings = Settings()