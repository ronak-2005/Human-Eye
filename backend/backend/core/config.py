from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me"

    # PostgreSQL
    DATABASE_URL: str = "postgresql+asyncpg://humaneye:humaneye_dev@postgres:5432/humaneye"

    # TimescaleDB
    TIMESCALE_URL: str = "postgresql+asyncpg://humaneye:humaneye_dev@timescaledb:5432/humaneye_signals"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/0"
    RATE_LIMIT_PER_MINUTE: int = 100

    # ML Engine — always set explicitly, never rely on default
    ML_ENGINE_URL: str = "http://ml_engine:8001"
    ML_TIMEOUT_MS: int = 5000

    # Security
    BCRYPT_ROUNDS: int = 12
    MAX_PAYLOAD_BYTES: int = 10 * 1024 * 1024
    API_KEY_PREFIX: str = "he_"

    # CORS — comma-separated string parsed into list
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    # Vault
    VAULT_ADDR: str = "http://vault:8200"
    VAULT_TOKEN: str = "dev-root-token"

    # Stripe (Week 3)
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # SendGrid (Week 3)
    SENDGRID_API_KEY: str = ""

    # Phase 2 External APIs
    PLAID_CLIENT_ID: str = ""
    PLAID_SECRET: str = ""
    MAXMIND_LICENSE_KEY: str = ""
    IPROOV_API_KEY: str = ""

    # Monitoring
    SENTRY_DSN: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
