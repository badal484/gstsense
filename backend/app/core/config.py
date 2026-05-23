from functools import lru_cache
from typing import Optional

from pydantic import field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
)


class Settings(BaseSettings):
    # ---- Application ----
    APP_NAME: str = "GSTSense"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str
    FRONTEND_URL: str = "http://localhost:3000"
    API_V1_PREFIX: str = "/api/v1"
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]

    # ---- Database ----
    DATABASE_URL: str
    DATABASE_SSL: bool = False
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 3600

    # ---- Redis ----
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_CACHE_TTL: int = 300

    # ---- AWS ----
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str = "ap-south-1"
    AWS_S3_BUCKET: str
    AWS_S3_PRESIGN_EXPIRY: int = 900

    # ---- JWT ----
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ---- AI ----
    ANTHROPIC_API_KEY: str
    OPENAI_API_KEY: str
    AI_MAX_TOKENS: int = 4096
    AI_TEMPERATURE: float = 0.1

    # ---- Payments ----
    RAZORPAY_KEY_ID: str
    RAZORPAY_KEY_SECRET: str
    RAZORPAY_WEBHOOK_SECRET: str
    RAZORPAY_PLAN_ID_SMB: str = ""
    RAZORPAY_PLAN_ID_GROWTH: str = ""
    RAZORPAY_PLAN_ID_CA_FIRM: str = ""

    # ---- Notifications ----
    RESEND_API_KEY: str
    INTERAKT_API_KEY: str

    # ---- GSTIN Validation ----
    FASTGST_API_KEY: Optional[str] = None

    # ---- Monitoring ----
    SENTRY_DSN: Optional[str] = None

    # ---- Rate Limiting ----
    RATE_LIMIT_UPLOAD_PER_HOUR: int = 10
    RATE_LIMIT_AUTH_PER_MINUTE: int = 5
    RATE_LIMIT_API_PER_MINUTE: int = 100

    # ---- File & Plan Limits ----
    MAX_FILE_SIZE_MB: int = 50
    MAX_INVOICES_FREE: int = 500
    MAX_INVOICES_SMB: int = 1500
    MAX_INVOICES_GROWTH: int = 5000
    MAX_INVOICES_CA_FIRM: int = 50000

    # ---- Validators ----

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        allowed = ["development", "staging", "production"]
        if v not in allowed:
            raise ValueError(
                f"ENVIRONMENT must be one of {allowed}, got '{v}'"
            )
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith(("postgresql", "postgres")):
            raise ValueError(
                "DATABASE_URL must be a PostgreSQL connection string"
            )
        # Ensure the asyncpg driver is always in the URL so SQLAlchemy async engine works.
        if v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        return v

    @field_validator("REDIS_URL")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        if not v.startswith(("redis://", "rediss://", "unix://")):
            raise ValueError(
                "REDIS_URL must start with redis://, rediss://, or unix://"
            )
        if v.startswith("rediss://") and "ssl_cert_reqs" not in v:
            separator = "&" if "?" in v else "?"
            v = f"{v}{separator}ssl_cert_reqs=none"
        return v

    @field_validator("SECRET_KEY", "JWT_SECRET_KEY")
    @classmethod
    def validate_secret_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError(
                "Secret keys must be at least 32 characters long. "
                "Generate with: openssl rand -hex 32"
            )
        return v

    @field_validator("AI_TEMPERATURE")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("AI_TEMPERATURE must be between 0.0 and 1.0")
        return v

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.ENVIRONMENT == "production":
            if self.DEBUG:
                raise ValueError("DEBUG must be False in production environment")
            if self.FRONTEND_URL == "http://localhost:3000":
                raise ValueError(
                    "FRONTEND_URL must be set to production URL in production"
                )
            if self.SENTRY_DSN is None:
                raise ValueError(
                    "SENTRY_DSN is required in production for error tracking"
                )
        return self

    # ---- Computed properties ----

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT == "development"

    @property
    def is_staging(self) -> bool:
        return self.ENVIRONMENT == "staging"

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def access_token_expire_seconds(self) -> int:
        return self.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60

    @property
    def refresh_token_expire_seconds(self) -> int:
        return self.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400

    def get_invoice_limit(self, plan: str) -> int:
        limits: dict[str, int] = {
            "free": self.MAX_INVOICES_FREE,
            "smb": self.MAX_INVOICES_SMB,
            "growth": self.MAX_INVOICES_GROWTH,
            "ca_firm": self.MAX_INVOICES_CA_FIRM,
        }
        return limits.get(plan, self.MAX_INVOICES_FREE)

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Prefer project .env over globally exported shell variables.
        return (
            init_settings,
            dotenv_settings,
            env_settings,
            file_secret_settings,
        )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
