import logging
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, EmailStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR.parent / ".env"
ENV_TEMPLATE = BASE_DIR.parent / ".env.template"


class RuntimeSettings(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True


class LoggerSettings(BaseModel):
    LOG_DEFAULT_FORMAT: str = "[%(asctime)s.%(msecs)03d] %(module)10s:%(lineno)-3d %(levelname)-7s - %(message)s"
    level: int = logging.INFO
    datefmt: str = "%Y-%m-%d %H:%M:%S"


class AuthSettings(BaseModel):
    session_id_cookie_name: str = "session_id"
    session_id_expire_days: int = 1
    http_only: bool = True
    session_cookie_secure: bool = True
    samesite: Literal["strict", "lax", "none"] = "strict"

    @property
    def session_id_expire_minutes(self):
        """Время жизни сессии в минутах.

        Returns:
            int: session_id_expire_days, переведённое в минуты.
        """
        return 24 * 60 * self.session_id_expire_days
    

class RabbitMQSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ENV_TEMPLATE, ENV_FILE),
        case_sensitive=False,
        extra="ignore",  # Игнорировать другие переменные в .env
    )

    rabbit_protocol: str = "amqp"
    rabbit_host: Annotated[str, Field(alias="RABBITMQ_HOST")]
    rabbit_port: Annotated[str, Field(alias="RABBITMQ_PORT")]
    rabbit_user: Annotated[str, Field(alias="RABBITMQ_USER")]
    rabbit_password: Annotated[str, Field(alias="RABBITMQ_PASSWORD")]

    @property
    def rabbitmq_url(self):
        """URL подключения к RabbitMQ.

        Returns:
            str: URL вида amqp://user:password@host:port.
        """
        return (
            f"{self.rabbit_protocol}://{self.rabbit_user}:{self.rabbit_password}@" \
            f"{self.rabbit_host}:{self.rabbit_port}"
        )


class TaskIqSettings(BaseModel):
    cron_config: dict[str, Any] = {
        "cron": "30 11 * * 1,3,5,6" # минута час день_месяца месяц день_недели 
    }
    # cron_config: dict[str, Any] = {
    #     "cron": "*/5 * * * *"
    # }

    countdown_seconds: int = 10
    max_retries: int = 5


# Чтобы не указывать в .env параметры с начальным идентификатором, например, database как указано в Settings классе
# явно наследуемся от BaseSettings, а не BaseModel и прописываем model_config
class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ENV_TEMPLATE, ENV_FILE),
        case_sensitive=False,
        extra="ignore",  # Игнорировать другие переменные в .env
    )

    db_name: Annotated[str, Field(alias="POSTGRES_DB")]
    db_user: Annotated[str, Field(alias="POSTGRES_USER")]
    db_password: Annotated[str, Field(alias="POSTGRES_PASSWORD")]
    db_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    db_port: int = Field(default=6000, alias="PGPORT")
    db_echo: bool = False

    @property
    def db_url(self):
        """URL подключения к PostgreSQL через asyncpg.

        Returns:
            str: URL вида postgresql+asyncpg://user:password@host:port/db.
        """
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
    
class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ENV_TEMPLATE, ENV_FILE),
        case_sensitive=False,
        extra="ignore", # Игнорировать другие переменные в .env
    )

    host: Annotated[str, Field(alias="REDIS_HOST")]
    port: Annotated[int, Field(alias="REDIS_PORT")]

    results_ex_time_in_seconds: int = 1_728_000 

    @property
    def redis_url(self):
        """URL подключения к Redis.

        Returns:
            str: URL вида redis://host:port.
        """
        return f"redis://{self.host}:{self.port}"


class SmtpSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ENV_TEMPLATE, ENV_FILE),
        case_sensitive=False,
        extra="ignore",  # Игнорировать другие переменные в .env
    )

    host: str = Field(alias="SMTP_HOST")
    port: int = Field(alias="SMTP_PORT")

class MailingSettings(BaseModel):
    admin_email: EmailStr = "admin@site.com"
    prefix: str = "email_verify"
    ttl_minutes: int = 10

    @property
    def ttl_seconds(self):
        """Время жизни токена подтверждения email в секундах.

        Returns:
            int: ttl_minutes, переведённое в секунды.
        """
        return self.ttl_minutes * 60
    
    @property
    def user_prefix(self):
        """Префикс Redis-ключей вида user_id -> токен.

        Returns:
            str: Префикс вида "<prefix>:user".
        """
        return f"{self.prefix}:user"
    
    @property
    def token_prefix(self):
        """Префикс Redis-ключей вида токен -> user_id.

        Returns:
            str: Префикс вида "<prefix>:token".
        """
        return f"{self.prefix}:token"



class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(ENV_TEMPLATE, ENV_FILE),
        case_sensitive=False,
        env_nested_delimiter="__",
        extra="ignore",
    )

    runtime: RuntimeSettings = RuntimeSettings()

    database: DatabaseSettings = Field(
        default_factory=DatabaseSettings,
    )  # при создании класса Settings,
    # доходя до поля database будет вызываться конструктор DatabaseSettings (не путать с такой инициализацией = DatabaseSettings(), так поле будет хранить объект, вычесленный не динамически, а при определении класса Settings, не создании экземпляра)
    # и DatabaseSettings сам будет искать свои переменные ничего не зная о родительском классе Settings, который тоже ищет параметры в .env файлах
    redis: RedisSettings = Field(
        default_factory=RedisSettings,
    )
    auth: AuthSettings = AuthSettings()

    log: LoggerSettings = LoggerSettings()

    smtp: SmtpSettings = Field(default_factory=SmtpSettings)
    mailing: MailingSettings = MailingSettings()
    rabbitmq: RabbitMQSettings = Field(default_factory=RabbitMQSettings)
    taskiq: TaskIqSettings = TaskIqSettings()
    

settings = Settings()
