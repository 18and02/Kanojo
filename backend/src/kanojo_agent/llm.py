from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import json
import re
from typing import Any

from kanojo_agent.settings import Settings


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.llm_base_url)

    def chat_completions_url(self) -> str:
        if not self.settings.llm_base_url:
            raise RuntimeError("LLM base URL is not configured.")
        base_url = self.settings.llm_base_url.rstrip("/")
        if base_url.endswith("/chat/completions"):
            return base_url
        if base_url.endswith("/v1"):
            return f"{base_url}/chat/completions"
        return f"{base_url}/v1/chat/completions"

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        if not self.settings.llm_base_url:
            raise RuntimeError("LLM base URL is not configured.")

        import httpx

        headers = {}
        if self.settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self.settings.llm_api_key}"

        body: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens

        async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
            response = await client.post(
                self.chat_completions_url(),
                headers={**headers, "Content-Type": "application/json"},
                content=json.dumps(body, ensure_ascii=True).encode("ascii"),
            )
            response.raise_for_status()
            payload = response.json()
            return str(payload["choices"][0]["message"]["content"])

    async def chat_completion_stream(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncIterator[str]:
        if not self.settings.llm_base_url:
            raise RuntimeError("LLM base URL is not configured.")

        import httpx

        headers = {}
        if self.settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self.settings.llm_api_key}"

        body: dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens is not None:
            body["max_tokens"] = max_tokens

        async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
            async with client.stream(
                "POST",
                self.chat_completions_url(),
                headers={**headers, "Content-Type": "application/json"},
                content=json.dumps(body, ensure_ascii=True).encode("ascii"),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload_text = line.removeprefix("data:").strip()
                    if payload_text == "[DONE]":
                        break
                    try:
                        payload = json.loads(payload_text)
                    except json.JSONDecodeError:
                        continue
                    choices = payload.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        yield str(content)

    async def generate_reply(self, user_text: str, memories: list[dict[str, Any]]) -> str:
        if not self.settings.llm_base_url:
            return self._mock_reply(user_text, memories)

        return await self.chat_completion(
            self._reply_messages(user_text, memories), temperature=0.7
        )

    async def generate_reply_stream(
        self, user_text: str, memories: list[dict[str, Any]]
    ) -> AsyncIterator[str]:
        if not self.settings.llm_base_url:
            for chunk in chunk_text(self._mock_reply(user_text, memories)):
                await asyncio.sleep(0.015)
                yield chunk
            return

        async for chunk in self.chat_completion_stream(
            self._reply_messages(user_text, memories), temperature=0.7
        ):
            yield chunk

    def _reply_messages(
        self, user_text: str, memories: list[dict[str, Any]]
    ) -> list[dict[str, str]]:
        memory_block = "\n".join(
            f"- 类型:{item['kind']} 内容:{item['content']}"
            for item in memories
            if item.get("score", 0) > 0
        )
        memory_prompt = memory_block or "无"
        messages = [
            {
                "role": "system",
                "content": (
                    "你是一个用于毕业设计的中文桌面陪伴智能体。"
                    "请始终使用简洁、自然、克制的中文回复。"
                    "只有在下方【可用长期记忆】明确提供依据时,才可以说自己记得某件事。"
                    "如果没有相关记忆,就正常回应用户当前这句话,不要说自己不懂。"
                    "公开答辩版避免强恋爱化、强依附、过度亲密表达。"
                    f"\n\n【可用长期记忆】\n{memory_prompt}"
                ),
            },
            {"role": "user", "content": user_text},
        ]
        return messages

    async def extract_memory_json(self, user_text: str) -> list[dict[str, Any]]:
        if not self.settings.llm_base_url:
            return []

        messages = [
            {
                "role": "system",
                "content": (
                    "你是桌面陪伴智能体的记忆抽取器。"
                    "只抽取用户明确说出的、未来值得长期保存的信息。"
                    "不要臆测,不要把临时寒暄写成记忆。"
                    "只输出 JSON 数组,不要解释。"
                    "每项字段: kind(event|preference|relationship|reflection), "
                    "content(中文短句), importance(0-1), confidence(0-1), reason(中文)。"
                ),
            },
            {"role": "user", "content": user_text},
        ]
        content = await self.chat_completion(messages, temperature=0.1, max_tokens=512)
        return _parse_json_array(content)

    def _mock_reply(self, user_text: str, memories: list[dict[str, Any]]) -> str:
        useful = [item for item in memories if item.get("score", 0) > 0.2]
        if useful:
            remembered = useful[0]["content"]
            return f"我查到了相关记忆:{remembered}。这次我会先按这个线索回应你:{user_text}"
        return f"我先把这句话认真接住:{user_text}"


def chunk_text(text: str, chunk_size: int = 4) -> list[str]:
    return [text[index : index + chunk_size] for index in range(0, len(text), chunk_size)]


def _parse_json_array(text: str) -> list[dict[str, Any]]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped, flags=re.IGNORECASE).strip()
        stripped = re.sub(r"```$", "", stripped).strip()

    match = re.search(r"\[[\s\S]*\]", stripped)
    if match:
        stripped = match.group(0)

    parsed = json.loads(stripped)
    if not isinstance(parsed, list):
        raise ValueError("Memory extractor did not return a JSON array.")
    return [item for item in parsed if isinstance(item, dict)]
