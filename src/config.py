from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", env_file_encoding="utf-8"
    )

    # --- Google API ---
    GOOGLE_API_KEY: str

    # --- Gemini LLM Configuration ---
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_TEMPERATURE: float = 0.1

    # --- OCR Engine Configuration ---
    OCR_DEVICE: str = "cpu"
    OCR_PRECISION: str = "fp16"
    OCR_DET_MODEL: str = "PP-OCRv5_mobile_det"
    OCR_REC_MODEL: str = "PP-OCRv5_mobile_rec"
    OCR_CPU_THREADS: int = 8
    OCR_Y_THRESHOLD: float = 15.0
    OCR_SAVE_VIZ: bool = True

    # --- Pipeline ---
    DPI: int = 300

settings = Settings()