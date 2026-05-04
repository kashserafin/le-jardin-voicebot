from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str
    langfuse_public_key: str
    langfuse_secret_key: str
    langfuse_base_url: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
