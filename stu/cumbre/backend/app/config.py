import logging
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

_DEFAULT_JWT_SECRET = "cumbre-dev-secret-change-in-production"


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./cumbre.db"
    jwt_secret: str = _DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expire_days: int = 2

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def model_post_init(self, __context):
        if self.jwt_secret == _DEFAULT_JWT_SECRET:
            logger.warning(
                "JWT_SECRET is using the default value. "
                "Set JWT_SECRET in .env for production environments."
            )


settings = Settings()
