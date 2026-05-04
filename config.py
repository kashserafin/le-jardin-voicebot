from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str
    langfuse_public_key: str
    langfuse_secret_key: str
    langfuse_base_url: str

settings = Settings()
