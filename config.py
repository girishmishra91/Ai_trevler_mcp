import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Groq API
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    MODEL_NAME = os.getenv("MODEL_NAME", "llama-3.3-70b-versatile")
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))

    # Browser MCP
    BROWSER_MCP_URL = os.getenv("BROWSER_MCP_URL", "http://127.0.0.1:8089/mcp")

    # ChromaDB
    CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")

    # OpenWeatherMap API
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

    # AviationStack — live flight tracking
    AVIATIONSTACK_API_KEY = os.getenv("AVIATIONSTACK_API_KEY", "")

    # ExchangeRate API
    EXCHANGERATE_API_KEY = os.getenv("EXCHANGERATE_API_KEY", "")

    # Twilio / WhatsApp
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
    TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "")

    # Email
    EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
    EMERGENCY_EMAIL = os.getenv("EMERGENCY_EMAIL", "")
    EMERGENCY_PHONE = os.getenv("EMERGENCY_PHONE", "")  # renamed from EMERGENCY_CONTACTS