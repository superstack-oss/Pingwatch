from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "pingwatch"
    mysql_password: str = "pingwatch"
    mysql_database: str = "pingwatch"
    ping_interval: int = 30
    ping_timeout: float = 2.0
    ping_concurrency: int = 40
    history_keep_days: int = 31
    warning_rtt_ms: float = 200.0
    dns_cache_ttl: int = 300
    sparkline_points: int = 24
    secret_key: str = "pingwatch-dev-secret-change-me"
    default_admin_username: str = "admin"
    default_admin_password: str = "Password@123"
    upload_dir: str = "data/incident-attachments"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def database_url(self) -> str:
        user = quote_plus(self.mysql_user)
        password = quote_plus(self.mysql_password)
        return (
            f"mysql+aiomysql://{user}:{password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
        )


settings = Settings()
