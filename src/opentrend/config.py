import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    secret_key: str
    encryption_key: str
    github_client_id: str
    github_client_secret: str
    debug: bool = False
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> Settings:
        def require(key: str) -> str:
            val = os.environ.get(key)
            if not val:
                raise ValueError(f"{key} environment variable is required")
            return val

        return cls(
            database_url=require("DATABASE_URL"),
            secret_key=require("SECRET_KEY"),
            encryption_key=require("ENCRYPTION_KEY"),
            github_client_id=require("GITHUB_CLIENT_ID"),
            github_client_secret=require("GITHUB_CLIENT_SECRET"),
            debug=os.environ.get("DEBUG", "").lower() in ("1", "true", "yes"),
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
        )
