from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value)


@dataclass(slots=True)
class DeepSeekHeaders:
    accept: str = "*/*"
    content_type: str = "application/json"
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36"
    )
    x_app_version: str = "20241129.1"
    x_client_locale: str = "en_US"
    x_client_platform: str = "web"
    x_client_version: str = "1.7.1"
    sec_ch_ua: str = '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"'
    sec_ch_ua_mobile: str = "?0"
    sec_ch_ua_platform: str = '"Windows"'

    def as_dict(self) -> dict[str, str]:
        return {
            "accept": self.accept,
            "content-type": self.content_type,
            "user-agent": self.user_agent,
            "x-app-version": self.x_app_version,
            "x-client-locale": self.x_client_locale,
            "x-client-platform": self.x_client_platform,
            "x-client-version": self.x_client_version,
            "sec-ch-ua": self.sec_ch_ua,
            "sec-ch-ua-mobile": self.sec_ch_ua_mobile,
            "sec-ch-ua-platform": self.sec_ch_ua_platform,
        }


@dataclass(slots=True)
class DeepSeekConfig:
    base_url: str
    token: str
    cookie: str
    timeout_seconds: int
    thinking_enabled: bool
    search_enabled: bool
    node_command: str
    headers: DeepSeekHeaders = field(default_factory=DeepSeekHeaders)


@dataclass(slots=True)
class ProxyConfig:
    host: str
    port: int
    log_level: str
    api_key: str
    default_model: str
    deepseek: DeepSeekConfig


def load_config() -> ProxyConfig:
    deepseek = DeepSeekConfig(
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://chat.deepseek.com").rstrip("/"),
        token=os.getenv("DEEPSEEK_TOKEN", "").strip(),
        cookie=os.getenv("DEEPSEEK_COOKIE", "").strip(),
        timeout_seconds=_env_int("DEEPSEEK_TIMEOUT_SECONDS", 180),
        thinking_enabled=_env_bool("DEEPAPI_THINKING_ENABLED", True),
        search_enabled=_env_bool("DEEPAPI_SEARCH_ENABLED", True),
        node_command=os.getenv("DEEPAPI_NODE_COMMAND", "node").strip() or "node",
    )
    return ProxyConfig(
        host=os.getenv("DEEPAPI_HOST", "127.0.0.1").strip() or "127.0.0.1",
        port=_env_int("DEEPAPI_PORT", 8080),
        log_level=os.getenv("DEEPAPI_LOG_LEVEL", "info").strip() or "info",
        api_key=os.getenv("DEEPAPI_API_KEY", "deepapi-local").strip() or "deepapi-local",
        default_model=os.getenv("DEEPAPI_MODEL", "deepseek-chat-web").strip()
        or "deepseek-chat-web",
        deepseek=deepseek,
    )
