"""配置管理模块

从 config.yaml 加载配置，支持环境变量替换
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseModel):
    """应用配置"""
    name: str = "aivo-backend"
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    cors_origins: list[str] = []


class DatabaseConfig(BaseModel):
    """数据库配置"""
    host: str = "localhost"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = "mainshi_agent"
    charset: str = "utf8mb4"
    pool_size: int = 10
    pool_recycle: int = 3600

    @property
    def url(self) -> str:
        """获取数据库连接 URL"""
        return (
            f"mysql+aiomysql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
            f"?charset={self.charset}"
        )

    @property
    def sync_url(self) -> str:
        """获取同步数据库连接 URL"""
        return (
            f"mysql+pymysql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
            f"?charset={self.charset}"
        )


class MongoDBConfig(BaseModel):
    """MongoDB 配置"""
    host: str = "localhost"
    port: int = 27017
    database: str = "xunzhi_agent"
    username: str = ""
    password: str = ""

    @property
    def uri(self) -> str:
        """获取 MongoDB 连接 URI"""
        if self.username and self.password:
            return f"mongodb://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"mongodb://{self.host}:{self.port}"


class RedisConfig(BaseModel):
    """Redis 配置"""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str = ""

    @property
    def url(self) -> str:
        """获取 Redis 连接 URL"""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class AIProviderConfig(BaseModel):
    """AI 模型提供商配置"""
    base_url: str = ""
    api_key: str = ""
    model: str = ""


class AIConfig(BaseModel):
    """AI 配置"""
    default_provider: str = "siliconflow"
    providers: dict[str, AIProviderConfig] = {}


class JWTConfig(BaseModel):
    """JWT 配置"""
    secret: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60


class Settings(BaseSettings):
    """全局配置"""
    app: AppConfig = AppConfig()
    database: DatabaseConfig = DatabaseConfig()
    mongodb: MongoDBConfig = MongoDBConfig()
    redis: RedisConfig = RedisConfig()
    ai: AIConfig = AIConfig()
    jwt: JWTConfig = JWTConfig()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore"
    )


def _get_project_root() -> Path:
    """获取项目根目录"""
    return Path(__file__).parent.parent.parent


def load_config_from_yaml(config_path: str | None = None) -> dict[str, Any]:
    """从 YAML 文件加载配置"""
    if config_path is None:
        config_path = os.environ.get(
            "CONFIG_PATH",
            str(_get_project_root() / "config.yaml")
        )

    config_file = Path(config_path)
    if not config_file.exists():
        return {}

    with open(config_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return _replace_env_vars(config) if config else {}


def _replace_env_vars(config: Any) -> Any:
    """递归替换配置中的环境变量"""
    if isinstance(config, dict):
        return {k: _replace_env_vars(v) for k, v in config.items()}
    elif isinstance(config, list):
        return [_replace_env_vars(item) for item in config]
    elif isinstance(config, str):
        if config.startswith("${") and config.endswith("}"):
            env_var = config[2:-1]
            default = None
            if ":" in env_var:
                env_var, default = env_var.split(":", 1)
            return os.environ.get(env_var, default or "")
        return config
    return config


@lru_cache()
def get_settings() -> Settings:
    """获取全局配置单例"""
    from dotenv import load_dotenv
    
    # 加载 .env 文件
    env_file = _get_project_root() / ".env"
    load_dotenv(env_file)
    
    config_data = load_config_from_yaml()

    return Settings(
        app=AppConfig(**config_data.get("app", {})),
        database=DatabaseConfig(**config_data.get("database", {})),
        mongodb=MongoDBConfig(**config_data.get("mongodb", {})),
        redis=RedisConfig(**config_data.get("redis", {})),
        ai=AIConfig(**config_data.get("ai", {})),
        jwt=JWTConfig(**config_data.get("jwt", {})),
    )


# 全局配置实例
settings = get_settings()
