from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    openai_api_key: str
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_base_url: str | None = None

    @field_validator("langfuse_public_key", "langfuse_secret_key", "langfuse_base_url", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        return None if isinstance(v, str) and not v.strip() else v

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)

settings = Settings()
