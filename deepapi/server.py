from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Iterable

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from .bridge import AnthropicBlock, AnthropicBridge
from .config import ProxyConfig, load_config
from .deepseek_client import DeepSeekCompletion, DeepSeekWebClient


@dataclass(slots=True)
class ConversationState:
    state_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    chat_session_id: str | None = None
    parent_message_id: int | None = None
    history_entries: list[str] = field(default_factory=list)
    last_message: dict[str, Any] | None = None


@dataclass(slots=True)
class ConversationRegistry:
    states: dict[str, ConversationState] = field(default_factory=dict)
    active_state_id: str | None = None

    def create_state(self) -> ConversationState:
        state = ConversationState()
        self.states[state.state_id] = state
        self.active_state_id = state.state_id
        return state

    def activate(self, state: ConversationState) -> None:
        self.active_state_id = state.state_id

    def find_best(self, entries: list[str]) -> ConversationState | None:
        candidates: list[tuple[int, ConversationState]] = []
        for state in self.states.values():
            prefix = _common_prefix_len(state.history_entries, entries)
            if prefix == len(state.history_entries):
                candidates.append((len(state.history_entries), state))
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=True)
        state = candidates[0][1]
        self.active_state_id = state.state_id
        return state

    def active_state(self) -> ConversationState | None:
        if self.active_state_id is None:
            return None
        return self.states.get(self.active_state_id)


def build_app(config: ProxyConfig | None = None) -> FastAPI:
    runtime = config or load_config()
    bridge = AnthropicBridge()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        client = DeepSeekWebClient(runtime.deepseek)
        try:
            app.state.config = runtime
            app.state.bridge = bridge
            app.state.client = client
            app.state.registry = ConversationRegistry()
            yield
        finally:
            client.close()

    app = FastAPI(title="deepapi", version="0.1.0", lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, Any]:
        registry: ConversationRegistry = app.state.registry
        return {
            "ok": True,
            "provider": "chat.deepseek.com",
            "default_model": runtime.default_model,
            "tracked_conversations": len(registry.states),
        }

    @app.get("/v1/models")
    def list_models() -> dict[str, Any]:
        models = [
            {
                "id": runtime.default_model,
                "type": "model",
                "display_name": runtime.default_model,
            },
            {
                "id": "deepseek-chat-web",
                "type": "model",
                "display_name": "deepseek-chat-web",
            },
        ]
        return {
            "data": models,
            "has_more": False,
            "first_id": models[0]["id"],
            "last_id": models[-1]["id"],
        }

    @app.post("/v1/messages/count_tokens")
    async def count_tokens(
        request: Request,
        x_api_key: str | None = Header(default=None, alias="x-api-key"),
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        _check_api_key(runtime, x_api_key=x_api_key, authorization=authorization)
        payload = await request.json()
        return {"input_tokens": bridge.estimate_tokens(payload)}

    @app.post("/v1/messages")
    async def create_message(
        request: Request,
        x_api_key: str | None = Header(default=None, alias="x-api-key"),
        authorization: str | None = Header(default=None),
    ):
        _check_api_key(runtime, x_api_key=x_api_key, authorization=authorization)

        payload = await request.json()
        tools = payload.get("tools") or []
        model_name = payload.get("model") or runtime.default_model
        registry: ConversationRegistry = app.state.registry
        entries = bridge.render_entries(payload)

        if bridge.is_new_chat_request(payload):
            state = registry.create_state()
            try:
                state.chat_session_id = app.state.client.create_chat_session()
            except Exception as exc:
                return _error_response(502, f"deepseek request failed: {exc}")
            content_blocks = [AnthropicBlock(type="text", text="started a new deepseek chat")]
            message = _message_object(
                model_name=model_name,
                blocks=content_blocks,
                stop_reason="end_turn",
                usage={"input_tokens": 1, "output_tokens": 6},
            )
            state.history_entries = entries + [bridge.assistant_history_entry(content_blocks)]
            state.last_message = message
            return _response_for_request(payload, message)

        state = registry.find_best(entries)
        if state is None:
            state = registry.create_state()
        else:
            registry.activate(state)

        if state.chat_session_id is None:
            try:
                state.chat_session_id = app.state.client.create_chat_session()
            except Exception as exc:
                return _error_response(502, f"deepseek request failed: {exc}")

        common_prefix = _common_prefix_len(state.history_entries, entries)
        prompt_entries = entries[common_prefix:]
        continuation = bool(state.history_entries)

        if not prompt_entries and state.last_message is not None:
            return _response_for_request(payload, state.last_message)

        prompt = bridge.build_prompt(payload, entries=prompt_entries, continuation=continuation)

        try:
            completion: DeepSeekCompletion = app.state.client.complete(
                prompt,
                session_id=state.chat_session_id,
                parent_message_id=state.parent_message_id,
                thinking_enabled=runtime.deepseek.thinking_enabled,
                search_enabled=runtime.deepseek.search_enabled,
            )
        except Exception as exc:
            return _error_response(502, f"deepseek request failed: {exc}")

        content_blocks, stop_reason = bridge.parse_response(completion.text, tools=tools)
        usage = {
            "input_tokens": max(1, len(prompt) // 4),
            "output_tokens": max(1, len(completion.text) // 4) if completion.text else 1,
        }
        message = _message_object(
            model_name=model_name,
            blocks=content_blocks,
            stop_reason=stop_reason,
            usage=usage,
        )

        state.chat_session_id = completion.session_id
        state.parent_message_id = completion.message_id
        state.history_entries = entries + [bridge.assistant_history_entry(content_blocks)]
        state.last_message = message
        registry.activate(state)
        return _response_for_request(payload, message)

    return app


def _response_for_request(payload: dict[str, Any], message: dict[str, Any]):
    if payload.get("stream"):
        return StreamingResponse(
            _stream_message_events(message),
            media_type="text/event-stream",
            headers={"cache-control": "no-cache", "x-accel-buffering": "no"},
        )
    return JSONResponse(message)


def _common_prefix_len(left: list[str], right: list[str]) -> int:
    limit = min(len(left), len(right))
    index = 0
    while index < limit and left[index] == right[index]:
        index += 1
    return index


def _check_api_key(
    config: ProxyConfig,
    *,
    x_api_key: str | None,
    authorization: str | None,
) -> None:
    if not config.api_key:
        return
    bearer = ""
    if authorization:
        lower = authorization.lower()
        if lower.startswith("bearer "):
            bearer = authorization[7:].strip()
        else:
            bearer = authorization.strip()
    provided = (x_api_key or "").strip() or bearer
    if provided != config.api_key:
        raise HTTPException(
            status_code=401,
            detail={
                "type": "authentication_error",
                "message": "invalid api key",
            },
        )


def _message_object(
    *,
    model_name: str,
    blocks: list[AnthropicBlock],
    stop_reason: str,
    usage: dict[str, int],
) -> dict[str, Any]:
    return {
        "id": f"msg_{uuid.uuid4().hex}",
        "type": "message",
        "role": "assistant",
        "content": [block.as_dict() for block in blocks],
        "model": model_name,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": usage,
    }


def _stream_message_events(message: dict[str, Any]) -> Iterable[str]:
    initial_message = dict(message)
    initial_message["content"] = []
    yield _sse("message_start", {"type": "message_start", "message": initial_message})

    blocks = message.get("content", [])
    for index, block in enumerate(blocks):
        if block["type"] == "text":
            yield _sse(
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": index,
                    "content_block": {"type": "text", "text": ""},
                },
            )
            text = block.get("text", "")
            yield _sse(
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": index,
                    "delta": {"type": "text_delta", "text": text},
                },
            )
            yield _sse("content_block_stop", {"type": "content_block_stop", "index": index})
            continue

        if block["type"] == "tool_use":
            yield _sse(
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": index,
                    "content_block": {
                        "type": "tool_use",
                        "id": block["id"],
                        "name": block["name"],
                        "input": {},
                    },
                },
            )
            partial_json = json.dumps(block.get("input", {}), ensure_ascii=False)
            yield _sse(
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": index,
                    "delta": {
                        "type": "input_json_delta",
                        "partial_json": partial_json,
                    },
                },
            )
            yield _sse("content_block_stop", {"type": "content_block_stop", "index": index})

    yield _sse(
        "message_delta",
        {
            "type": "message_delta",
            "delta": {
                "stop_reason": message.get("stop_reason"),
                "stop_sequence": message.get("stop_sequence"),
            },
            "usage": {"output_tokens": message.get("usage", {}).get("output_tokens", 0)},
        },
    )
    yield _sse("message_stop", {"type": "message_stop"})


def _split_text(text: str, size: int = 160) -> Iterable[str]:
    if not text:
        return []
    return [text[index : index + size] for index in range(0, len(text), size)]


def _sse(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _error_response(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "type": "error",
            "error": {
                "type": "api_error",
                "message": message,
            },
        },
    )


def main() -> int:
    config = load_config()
    uvicorn.run(
        "deepapi.server:build_app",
        host=config.host,
        port=config.port,
        factory=True,
        reload=False,
        log_level=config.log_level,
    )
    return 0

