from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    openai_api_key: str
    langfuse_public_key: str
    langfuse_secret_key: str
    langfuse_base_url: str

settings = Settings()
