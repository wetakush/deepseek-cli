from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable

import httpx

from .config import DeepSeekConfig
from .pow_solver import DeepSeekPowSolver


@dataclass(slots=True)
class DeepSeekChunk:
    kind: str
    content: str = ""
    message_id: int | None = None


@dataclass(slots=True)
class DeepSeekCompletion:
    session_id: str
    text: str
    message_id: int | None = None


class DeepSeekWebClient:
    def __init__(self, config: DeepSeekConfig) -> None:
        self.config = config
        self.pow_solver = DeepSeekPowSolver(node_command=config.node_command)
        self.client = httpx.Client(
            timeout=httpx.Timeout(config.timeout_seconds),
            follow_redirects=True,
        )

    def close(self) -> None:
        self.client.close()

    def complete(
        self,
        prompt: str,
        *,
        session_id: str | None = None,
        parent_message_id: int | None = None,
        thinking_enabled: bool | None = None,
        search_enabled: bool | None = None,
    ) -> DeepSeekCompletion:
        active_session_id = session_id or self.create_chat_session()
        parts: list[str] = []
        message_id: int | None = None
        for chunk in self.stream_completion(
            prompt,
            session_id=active_session_id,
            parent_message_id=parent_message_id,
            thinking_enabled=thinking_enabled,
            search_enabled=search_enabled,
        ):
            if chunk.message_id is not None:
                message_id = chunk.message_id
                continue
            if chunk.kind == "text" and chunk.content:
                parts.append(chunk.content)
        return DeepSeekCompletion(
            session_id=active_session_id,
            text="".join(parts).strip(),
            message_id=message_id,
        )

    def stream_completion(
        self,
        prompt: str,
        *,
        session_id: str,
        parent_message_id: int | None = None,
        thinking_enabled: bool | None = None,
        search_enabled: bool | None = None,
    ) -> Iterable[DeepSeekChunk]:
        target_path = "/api/v0/chat/completion"
        referer = f"{self.config.base_url}/a/chat/s/{session_id}"

        headers = self._base_headers(referer=referer)
        challenge = self.create_pow_challenge(target_path, referer=referer)
        headers["x-ds-pow-response"] = self.pow_solver.solve(challenge)

        payload = {
            "chat_session_id": session_id,
            "parent_message_id": parent_message_id,
            "prompt": prompt,
            "ref_file_ids": [],
            "thinking_enabled": self.config.thinking_enabled
            if thinking_enabled is None
            else bool(thinking_enabled),
            "search_enabled": self.config.search_enabled
            if search_enabled is None
            else bool(search_enabled),
            "preempt": False,
        }

        current_kind = "text"
        saw_any_event = False
        with self.client.stream(
            "POST",
            self._url(target_path),
            headers=headers,
            json=payload,
        ) as response:
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "text/event-stream" not in content_type.lower():
                body = response.read().decode("utf-8", errors="replace")[:4000]
                raise RuntimeError(
                    f"unexpected deepseek response content-type={content_type!r}: {body}"
                )

            for event_name, data in self._iter_sse(response.iter_lines()):
                saw_any_event = True
                if not data:
                    continue
                if event_name == "ready":
                    try:
                        meta = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    yield DeepSeekChunk(kind="meta", message_id=meta.get("response_message_id"))
                    continue

                try:
                    item = json.loads(data)
                except json.JSONDecodeError:
                    continue

                chunks, current_kind = self._parse_stream_item(item, current_kind)
                for chunk in chunks:
                    if chunk.kind == "thinking":
                        continue
                    yield chunk

        if not saw_any_event:
            raise RuntimeError("deepseek returned an empty event stream")

    def create_chat_session(self) -> str:
        response = self.client.post(
            self._url("/api/v0/chat_session/create"),
            headers=self._base_headers(),
            json={},
        )
        response.raise_for_status()
        payload = response.json()
        return payload["data"]["biz_data"]["chat_session"]["id"]

    def create_pow_challenge(self, target_path: str, referer: str | None = None) -> dict[str, Any]:
        response = self.client.post(
            self._url("/api/v0/chat/create_pow_challenge"),
            headers=self._base_headers(referer=referer),
            json={"target_path": target_path},
        )
        response.raise_for_status()
        payload = response.json()
        return payload["data"]["biz_data"]["challenge"]

    def _base_headers(self, *, referer: str | None = None) -> dict[str, str]:
        headers = self.config.headers.as_dict()
        if self.config.token:
            headers["authorization"] = (
                self.config.token
                if self.config.token.lower().startswith("bearer ")
                else f"Bearer {self.config.token}"
            )
        if self.config.cookie:
            headers["cookie"] = self.config.cookie
        headers["x-client-timezone-offset"] = str(self._timezone_offset_minutes())
        if referer:
            headers["referer"] = referer
        return headers

    def _timezone_offset_minutes(self) -> int:
        local = datetime.now().astimezone()
        delta = local.utcoffset()
        return 0 if delta is None else int(delta.total_seconds() // 60)

    def _url(self, path: str) -> str:
        return f"{self.config.base_url}{path}"

    def _iter_sse(self, lines: Iterable[str]) -> Iterable[tuple[str | None, str]]:
        event_name: str | None = None
        data_lines: list[str] = []
        for line in lines:
            if line == "":
                if data_lines:
                    yield event_name, "\n".join(data_lines)
                event_name = None
                data_lines = []
                continue
            if line.startswith("event:"):
                event_name = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].strip())
        if data_lines:
            yield event_name, "\n".join(data_lines)

    def _parse_stream_item(
        self,
        item: dict[str, Any],
        current_kind: str,
    ) -> tuple[list[DeepSeekChunk], str]:
        chunks: list[DeepSeekChunk] = []

        if isinstance(item.get("v"), dict):
            response = item["v"].get("response")
            if isinstance(response, dict):
                for fragment in response.get("fragments", []):
                    fragment_type = fragment.get("type", "")
                    current_kind = "thinking" if fragment_type == "THINK" else "text"
                    content = fragment.get("content", "")
                    if content:
                        chunks.append(DeepSeekChunk(kind=current_kind, content=content))

        path = item.get("p", "")
        operation = item.get("o", "")
        value = item.get("v")

        if path == "response/fragments" and operation == "APPEND" and isinstance(value, list):
            for fragment in value:
                fragment_type = fragment.get("type", "")
                current_kind = "thinking" if fragment_type == "THINK" else "text"
                content = fragment.get("content", "")
                if content:
                    chunks.append(DeepSeekChunk(kind=current_kind, content=content))
            return chunks, current_kind

        if path.endswith("/content") and operation in {"APPEND", "SET"} and isinstance(value, str):
            chunks.append(DeepSeekChunk(kind=current_kind, content=value))
            return chunks, current_kind

        if path == "" and isinstance(value, str):
            chunks.append(DeepSeekChunk(kind=current_kind, content=value))
            return chunks, current_kind

        return chunks, current_kind
