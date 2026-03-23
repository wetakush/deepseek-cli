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
    allow_client_thinking_override: bool
    allow_client_search_override: bool
    stream_chunk_size: int
    node_command: str
    headers: DeepSeekHeaders = field(default_factory=DeepSeekHeaders)


@dataclass(frozen=True, slots=True)
class DeepSeekModelProfile:
    id: str
    display_name: str
    thinking_enabled: bool
    search_enabled: bool
    aliases: tuple[str, ...] = ()

    def matches(self, requested_model: str) -> bool:
        model = requested_model.strip().lower()
        if not model:
            return False
        if model == self.id.lower():
            return True
        return model in {alias.lower() for alias in self.aliases}


@dataclass(slots=True)
class ProxyConfig:
    host: str
    port: int
    log_level: str
    api_key: str
    default_model: str
    deepseek: DeepSeekConfig
    model_catalog: tuple[DeepSeekModelProfile, ...]

    def default_model_profile(self) -> DeepSeekModelProfile:
        return self.resolve_model(self.default_model)

    def resolve_model(self, requested_model: str | None) -> DeepSeekModelProfile:
        candidate = (requested_model or "").strip()
        if candidate:
            for profile in self.model_catalog:
                if profile.matches(candidate):
                    return profile
        return self.model_catalog[0]

    def resolve_model_by_flags(
        self,
        *,
        thinking_enabled: bool,
        search_enabled: bool,
        fallback: DeepSeekModelProfile | None = None,
    ) -> DeepSeekModelProfile:
        for profile in self.model_catalog:
            if (
                profile.thinking_enabled == thinking_enabled
                and profile.search_enabled == search_enabled
            ):
                return profile
        return fallback or self.default_model_profile()


def _build_model_catalog(
    *,
    default_model: str,
    thinking_enabled: bool,
    search_enabled: bool,
) -> tuple[DeepSeekModelProfile, ...]:
    profiles = [
        DeepSeekModelProfile(
            id="deepseek-chat",
            display_name="deepseek chat",
            thinking_enabled=False,
            search_enabled=False,
            aliases=(
                "claude-sonnet-4-20250514",
                "claude-3-7-sonnet-20250219",
                "claude-3-5-sonnet-20241022",
                "sonnet",
                "claude-haiku-4-5-20251001",
                "claude-3-5-haiku-20241022",
                "haiku",
            ),
        ),
        DeepSeekModelProfile(
            id="deepseek-reasoner",
            display_name="deepseek reasoner",
            thinking_enabled=True,
            search_enabled=False,
            aliases=(
                "claude-opus-4-1-20250805",
                "claude-opus-4-20250514",
                "claude-opus-3-20240229",
                "opus",
            ),
        ),
        DeepSeekModelProfile(
            id="deepseek-chat-search",
            display_name="deepseek chat + search",
            thinking_enabled=False,
            search_enabled=True,
        ),
        DeepSeekModelProfile(
            id="deepseek-reasoner-search",
            display_name="deepseek reasoner + search",
            thinking_enabled=True,
            search_enabled=True,
        ),
    ]

    custom_default = default_model.strip()
    has_explicit_default = any(profile.matches(custom_default) for profile in profiles)
    if custom_default and not has_explicit_default:
        profiles.insert(
            0,
            DeepSeekModelProfile(
                id=custom_default,
                display_name=f"{custom_default} (custom)",
                thinking_enabled=thinking_enabled,
                search_enabled=search_enabled,
                aliases=("deepseek-chat-web",) if custom_default != "deepseek-chat-web" else (),
            ),
        )
    elif custom_default == "deepseek-chat-web":
        profiles.insert(
            0,
            DeepSeekModelProfile(
                id="deepseek-chat-web",
                display_name="deepseek web (legacy)",
                thinking_enabled=thinking_enabled,
                search_enabled=search_enabled,
            ),
        )

    return tuple(profiles)


def load_config() -> ProxyConfig:
    default_model = os.getenv("DEEPAPI_MODEL", "deepseek-reasoner").strip() or "deepseek-reasoner"
    deepseek = DeepSeekConfig(
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://chat.deepseek.com").rstrip("/"),
        token=os.getenv("DEEPSEEK_TOKEN", "").strip(),
        cookie=os.getenv("DEEPSEEK_COOKIE", "").strip(),
        timeout_seconds=_env_int("DEEPSEEK_TIMEOUT_SECONDS", 180),
        thinking_enabled=_env_bool("DEEPAPI_THINKING_ENABLED", True),
        search_enabled=_env_bool("DEEPAPI_SEARCH_ENABLED", True),
        allow_client_thinking_override=_env_bool(
            "DEEPAPI_ALLOW_CLIENT_THINKING_OVERRIDE", False
        ),
        allow_client_search_override=_env_bool("DEEPAPI_ALLOW_CLIENT_SEARCH_OVERRIDE", False),
        stream_chunk_size=max(24, _env_int("DEEPAPI_STREAM_CHUNK_SIZE", 96)),
        node_command=os.getenv("DEEPAPI_NODE_COMMAND", "node").strip() or "node",
    )
    return ProxyConfig(
        host=os.getenv("DEEPAPI_HOST", "127.0.0.1").strip() or "127.0.0.1",
        port=_env_int("DEEPAPI_PORT", 8080),
        log_level=os.getenv("DEEPAPI_LOG_LEVEL", "info").strip() or "info",
        api_key=os.getenv("DEEPAPI_API_KEY", "deepapi-local").strip() or "deepapi-local",
        default_model=default_model,
        deepseek=deepseek,
        model_catalog=_build_model_catalog(
            default_model=default_model,
            thinking_enabled=deepseek.thinking_enabled,
            search_enabled=deepseek.search_enabled,
        ),
    )
