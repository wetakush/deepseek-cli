from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any


TOOL_RESPONSE_SCHEMA = '{"tool_uses":[{"name":"tool_name","input":{"arg":"value"}}]}'
JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)
NEW_CHAT_COMMANDS = {"new", "/new", "new chat", "новый чат", "новый", "нью"}
TOOL_PAYLOAD_KEYS = ("tool_uses", "_uses", "uses", "tools", "toolUses", "tool_calls", "calls")


@dataclass(slots=True)
class AnthropicBlock:
    type: str
    text: str | None = None
    name: str | None = None
    input: dict[str, Any] | None = None
    tool_use_id: str | None = None
    is_error: bool | None = None
    id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"type": self.type}
        if self.text is not None:
            payload["text"] = self.text
        if self.name is not None:
            payload["name"] = self.name
        if self.input is not None:
            payload["input"] = self.input
        if self.tool_use_id is not None:
            payload["tool_use_id"] = self.tool_use_id
        if self.is_error is not None:
            payload["is_error"] = self.is_error
        if self.id is not None:
            payload["id"] = self.id
        return payload


class AnthropicBridge:
    def render_entries(self, request: dict[str, Any]) -> list[str]:
        entries: list[str] = []
        system_text = self._flatten_system(request.get("system"))
        if system_text:
            entries.append(f"system\n{system_text}")
        for message in request.get("messages") or []:
            role = message.get("role", "user")
            content = self._flatten_content_blocks(message.get("content"))
            entries.append(f"{role}\n{content or '[empty]'}")
        return entries

    def build_prompt(
        self,
        request: dict[str, Any],
        *,
        entries: list[str] | None = None,
        continuation: bool = False,
    ) -> str:
        tools = request.get("tools") or []
        entries = entries if entries is not None else self.render_entries(request)

        parts = [
            "you are serving an anthropic messages api proxy for claude code",
            "follow the conversation exactly and stay consistent with earlier tool results",
            "for coding tasks, default to using tools to inspect files, create files, edit files, run commands, and save actual project changes",
            "if the user asks to build an app, script, site, calculator, bot, config, or any code artifact, do not just describe it, create or modify files through tools",
            "only send a plain final answer after the required tool calls are done",
        ]

        if tools:
            parts.extend(
                [
                    "if you need a tool, respond with json only and no surrounding prose",
                    f"use exactly this schema: {TOOL_RESPONSE_SCHEMA}",
                    'the top-level key must be exactly "tool_uses", never "_uses", "uses", "tools", or any other key',
                    "return compact valid json with double quotes",
                    "tool names must exactly match the provided list",
                    "tool input must be valid json and match the schema as closely as possible",
                    "if you do not need a tool, respond with plain text only",
                    "never invent tool results or say you executed a tool yourself",
                ]
            )
            parts.append(self._tool_choice_instruction(request.get("tool_choice")))
            tool_view = [
                {
                    "name": tool.get("name"),
                    "description": tool.get("description", ""),
                    "input_schema": tool.get("input_schema", {}),
                }
                for tool in tools
            ]
            parts.append("available tools json:")
            parts.append(json.dumps(tool_view, ensure_ascii=False, indent=2))
        else:
            parts.append("no tools are available in this turn, answer with plain text only")

        if continuation:
            parts.append("these are only the new conversation events since your last reply in the same chat:")
        else:
            parts.append("this is the full conversation transcript for the current chat:")

        for entry in entries:
            role, _, content = entry.partition("\n")
            parts.append(f"<{role}>")
            parts.append(content or "[empty]")
            parts.append(f"</{role}>")

        parts.append("reply now")
        return "\n\n".join(parts)

    def parse_response(
        self,
        text: str,
        *,
        tools: list[dict[str, Any]] | None = None,
    ) -> tuple[list[AnthropicBlock], str]:
        tools = tools or []
        parsed = self._extract_tool_payload(text)
        if parsed is not None:
            blocks: list[AnthropicBlock] = []
            allowed_names = {str(tool.get("name", "")): str(tool.get("name", "")) for tool in tools}
            lowered_names = {name.lower(): name for name in allowed_names if name}
            for item in parsed:
                name = str(item.get("name", "")).strip()
                tool_input = item.get("input")
                if not name or not isinstance(tool_input, dict):
                    return [AnthropicBlock(type="text", text=text.strip())], "end_turn"
                if tools:
                    canonical = allowed_names.get(name) or lowered_names.get(name.lower())
                    if not canonical:
                        return [AnthropicBlock(type="text", text=text.strip())], "end_turn"
                    name = canonical
                blocks.append(
                    AnthropicBlock(
                        type="tool_use",
                        id=f"toolu_{uuid.uuid4().hex}",
                        name=name,
                        input=tool_input,
                    )
                )
            if blocks:
                return blocks, "tool_use"
        return [AnthropicBlock(type="text", text=text.strip())], "end_turn"

    def estimate_tokens(self, request: dict[str, Any]) -> int:
        text = self.build_prompt(request)
        return max(1, len(text) // 4)

    def assistant_history_entry(self, blocks: list[AnthropicBlock]) -> str:
        content = self._flatten_content_blocks([block.as_dict() for block in blocks])
        return f"assistant\n{content or '[empty]'}"

    def latest_user_text(self, request: dict[str, Any]) -> str:
        messages = request.get("messages") or []
        for message in reversed(messages):
            if message.get("role") != "user":
                continue
            return self._flatten_content_blocks(message.get("content"))
        return ""

    def is_new_chat_request(self, request: dict[str, Any]) -> bool:
        text = self.latest_user_text(request).strip().lower()
        return text in NEW_CHAT_COMMANDS

    def _flatten_system(self, system: Any) -> str:
        if isinstance(system, str):
            return system.strip()
        if isinstance(system, list):
            return self._flatten_content_blocks(system)
        return ""

    def _flatten_content_blocks(self, content: Any) -> str:
        if isinstance(content, str):
            return content.strip()
        if not isinstance(content, list):
            return ""

        parts: list[str] = []
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text":
                value = str(block.get("text", "")).strip()
                if value:
                    parts.append(value)
                continue
            if block_type == "tool_use":
                parts.append(
                    "tool request\n"
                    f"name: {block.get('name', '')}\n"
                    f"id: {block.get('id', '')}\n"
                    f"input: {json.dumps(block.get('input', {}), ensure_ascii=False)}"
                )
                continue
            if block_type == "tool_result":
                result_text = self._flatten_tool_result_content(block.get("content"))
                parts.append(
                    "tool result\n"
                    f"tool_use_id: {block.get('tool_use_id', '')}\n"
                    f"is_error: {bool(block.get('is_error', False))}\n"
                    f"content:\n{result_text}"
                )
                continue
            if block_type in {"thinking", "redacted_thinking"}:
                continue
            parts.append(f"[unsupported content block: {block_type}]")
        return "\n\n".join(part for part in parts if part).strip()

    def _flatten_tool_result_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content.strip()
        if not isinstance(content, list):
            return json.dumps(content, ensure_ascii=False)
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block.strip())
                continue
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                parts.append(str(block.get("text", "")).strip())
            else:
                parts.append(json.dumps(block, ensure_ascii=False))
        return "\n".join(part for part in parts if part).strip()

    def _tool_choice_instruction(self, tool_choice: Any) -> str:
        if isinstance(tool_choice, dict):
            choice_type = tool_choice.get("type")
            if choice_type == "none":
                return "do not call tools in this turn"
            if choice_type == "any":
                return "you must call at least one tool in this turn"
            if choice_type == "tool":
                return f"you must call exactly this tool first: {tool_choice.get('name', '')}"
        return "call tools whenever they are needed to complete the task correctly"

    def _extract_tool_payload(self, text: str) -> list[dict[str, Any]] | None:
        candidate = text.strip()
        fence = JSON_BLOCK_RE.search(candidate)
        if fence:
            candidate = fence.group(1).strip()

        payload: Any
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            return None

        if isinstance(payload, dict):
            for key in TOOL_PAYLOAD_KEYS:
                value = payload.get(key)
                if isinstance(value, list):
                    normalized = [self._normalize_tool_call(item) for item in value]
                    normalized = [item for item in normalized if item is not None]
                    return normalized or None
            single = self._normalize_tool_call(payload)
            if single is not None:
                return [single]
            return None

        if isinstance(payload, list) and all(isinstance(item, dict) for item in payload):
            normalized = [self._normalize_tool_call(item) for item in payload]
            normalized = [item for item in normalized if item is not None]
            return normalized or None
        return None

    def _normalize_tool_call(self, item: dict[str, Any]) -> dict[str, Any] | None:
        name = item.get("name") or item.get("tool") or item.get("tool_name")
        tool_input = item.get("input")
        if tool_input is None:
            tool_input = item.get("arguments")
        if isinstance(tool_input, str):
            try:
                tool_input = json.loads(tool_input)
            except json.JSONDecodeError:
                return None
        if not name or not isinstance(tool_input, dict):
            return None
        return {"name": str(name), "input": tool_input}
