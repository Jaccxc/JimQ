"""Application settings.

Stripped fork of FastAPI-boilerplate v0.15.0 ``core/config.py``: removed
Crypt / FirstUser / CRUDAdmin / Tier / RedisQueue (ARQ) / RateLimiter settings
mixins per decisions-confirmed B5. Kept App / Postgres / RedisCache /
ClientSideCache / Environment.

Redis cache uses a dedicated DB index (``REDIS_CACHE_DB``, default 1) so the
boilerplate cache stays isolated from the Nautilus message bus/streams on DB 0
(DEV_CONTRACT_AFK 鐵律 5 / jimq_core.constants).
"""

import os
from enum import Enum

from pydantic_settings import BaseSettings
from starlette.config import Config

from jimq_core.constants import REDIS_CACHE_DB as DEFAULT_REDIS_CACHE_DB

current_file_dir = os.path.dirname(os.path.realpath(__file__))
env_path = os.path.join(current_file_dir, "..", "..", "..", ".env")
config = Config(env_path)


class AppSettings(BaseSettings):
    APP_NAME: str = config("APP_NAME", default="JimQ API")
    APP_DESCRIPTION: str | None = config(
        "APP_DESCRIPTION", default="JimQ quant trading backend (stripped FastAPI-boilerplate fork)."
    )
    APP_VERSION: str | None = config("APP_VERSION", default="0.1.0")
    LICENSE_NAME: str | None = config("LICENSE", default="MIT")
    CONTACT_NAME: str | None = config("CONTACT_NAME", default=None)
    CONTACT_EMAIL: str | None = config("CONTACT_EMAIL", default=None)


class PostgresSettings(BaseSettings):
    POSTGRES_USER: str = config("POSTGRES_USER", default="postgres")
    POSTGRES_PASSWORD: str = config("POSTGRES_PASSWORD", default="1234")
    POSTGRES_SERVER: str = config("POSTGRES_HOST", default="localhost")
    POSTGRES_PORT: int = config("POSTGRES_PORT", default=5432)
    POSTGRES_DB: str = config("POSTGRES_DB", default="jimq")
    POSTGRES_SYNC_PREFIX: str = config("POSTGRES_SYNC_PREFIX", default="postgresql://")
    POSTGRES_ASYNC_PREFIX: str = config("POSTGRES_ASYNC_PREFIX", default="postgresql+asyncpg://")
    POSTGRES_URI: str = (
        f"{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_SERVER}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )


class RedisCacheSettings(BaseSettings):
    REDIS_CACHE_HOST: str = config("REDIS_HOST", default="localhost")
    REDIS_CACHE_PORT: int = config("REDIS_PORT", default=6379)
    # Dedicated cache DB index, isolated from the Nautilus bus on DB 0 (鐵律 5).
    REDIS_CACHE_DB: int = config("REDIS_CACHE_DB", default=DEFAULT_REDIS_CACHE_DB)
    REDIS_CACHE_URL: str = f"redis://{REDIS_CACHE_HOST}:{REDIS_CACHE_PORT}/{REDIS_CACHE_DB}"


class ClientSideCacheSettings(BaseSettings):
    CLIENT_CACHE_MAX_AGE: int = config("CLIENT_CACHE_MAX_AGE", default=60)


class ModelStoreSettings(BaseSettings):
    # Root dir for registered model artifacts (gitignored data/models, 卡 #17).
    # Default anchors at the repo-root data/models (api/src/app/core -> ../../../../data/models).
    MODELS_ROOT: str = config(
        "MODELS_ROOT",
        default=os.path.abspath(
            os.path.join(current_file_dir, "..", "..", "..", "..", "data", "models")
        ),
    )


class MlflowSettings(BaseSettings):
    # MLflow tracking server base URL for the read-only proxy endpoints (卡 #23 W4).
    # api talks to MLflow over its REST API (``/api/2.0/mlflow/...``) — it never
    # imports the ``mlflow`` package (stays lean; research stays a separate venv).
    # Default points at the docker ``--profile research`` service on localhost.
    MLFLOW_TRACKING_URI: str = config("MLFLOW_TRACKING_URI", default="http://localhost:5000")


class EnvironmentOption(Enum):
    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"


class EnvironmentSettings(BaseSettings):
    ENVIRONMENT: EnvironmentOption = config("ENVIRONMENT", default=EnvironmentOption.LOCAL)


class Settings(
    AppSettings,
    PostgresSettings,
    RedisCacheSettings,
    ClientSideCacheSettings,
    ModelStoreSettings,
    MlflowSettings,
    EnvironmentSettings,
):
    pass


settings = Settings()
