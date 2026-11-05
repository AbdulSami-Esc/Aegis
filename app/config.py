from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

"""
WHAT WE DID: Created a centralized, memory-cached configuration manager that auto-loads .env variables and dynamically calculates audio frame sizes.

VOICE AGENT IMPACT: Eliminates disk-read latency during live streaming. Because settings (like audio chunk sizes and API keys) are cached in memory, the agent can access them instantly. 
This prevents the real-time audio pipeline from stuttering or delaying while trying to repeatedly read configuration files.
"""
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    # Audio
    sample_rate: int = 16000
    channels: int = 1
    chunk_ms: int = 20

    # API keys (empty for now, used in later phases)
    deepgram_api_key: str = ""
    groq_api_key: str = ""

    @property
    def chunk_frames(self) -> int:
        return self.sample_rate * self.chunk_ms // 1000


@lru_cache
def get_settings() -> Settings:
    return Settings()