import base64
import json
import random
import struct
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import GenerationJob, ProviderCall, ProviderCallStatus
from app.services.content_client import GeneratedBinary
from fastclass_shared.http import propagate_headers


class ProviderError(Exception):
    pass


@dataclass
class ProviderSelection:
    provider: str
    output: Any


def _wav_header(pcm_data: bytes, sample_rate: int = 24000) -> bytes:
    return struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + len(pcm_data),
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        sample_rate,
        sample_rate * 2,
        2,
        16,
        b"data",
        len(pcm_data),
    ) + pcm_data


def _sanitize_json_output(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        parts = [part for part in text.split("```") if part.strip()]
        if parts:
            text = parts[0]
            if text.lstrip().startswith("json"):
                text = text.split("\n", 1)[1] if "\n" in text else "{}"
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProviderError(f"invalid_json_from_provider: {exc}") from exc


def _gateway_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    if settings.ai_gateway_secret:
        headers["X-Gateway-Secret"] = settings.ai_gateway_secret
    return propagate_headers(headers)


def _attachment_bytes(attachment: dict[str, Any]) -> bytes | None:
    content_base64 = attachment.get("content_base64")
    if not content_base64:
        return None
    return base64.b64decode(content_base64)


def _attachment_prompt_block(attachments: list[dict[str, Any]]) -> str:
    if not attachments:
        return "No external source attachments."
    lines = ["Source attachments:"]
    for index, item in enumerate(attachments, start=1):
        text_excerpt = (item.get("content_text") or "")[:600]
        lines.append(
            f"{index}. {item.get('file_name')} ({item.get('mime_type')})"
            + (f" excerpt: {text_excerpt}" if text_excerpt else "")
        )
    return "\n".join(lines)


def _build_lesson_instruction(context_pack: dict[str, Any], *, mode: str) -> str:
    request = context_pack["request"]
    contract = {
        "title": "string",
        "description": "string|null",
        "sections": [
            {
                "title": "string",
                "tasks": [
                    {
                        "task_type": "one of task_registry.task_type",
                        "payload": "schema-compatible object for that task_type",
                    }
                ],
            }
        ],
    }
    return (
        "You are an educational content orchestrator. "
        "Return only valid JSON, no markdown, no explanations.\n\n"
        f"Mode: {mode}\n"
        f"Request: {json.dumps(request, ensure_ascii=False)}\n"
        f"Explicit profile: {json.dumps(context_pack.get('explicit_profile') or {}, ensure_ascii=False)}\n"
        f"Style profile: {json.dumps(context_pack.get('style_profile') or {}, ensure_ascii=False)}\n"
        f"Recent lessons: {json.dumps(context_pack.get('recent_lessons') or [], ensure_ascii=False)}\n"
        f"Recent feedback: {json.dumps(context_pack.get('recent_feedback') or [], ensure_ascii=False)}\n"
        f"Task registry: {json.dumps(context_pack.get('task_registry') or [], ensure_ascii=False)}\n"
        f"Source lesson: {json.dumps(context_pack.get('source_lesson'), ensure_ascii=False)}\n"
        f"{_attachment_prompt_block(request.get('source_attachments') or [])}\n"
        f"Response contract: {json.dumps(contract, ensure_ascii=False)}"
    )


def _mock_bundle(context_pack: dict[str, Any], *, mode: str) -> dict[str, Any]:
    request = context_pack["request"]
    style = context_pack["style_profile"]
    subject = request.get("subject") or "English"
    goal_text = ", ".join(request.get("goals") or ["practice"])
    title = request.get("title") or (
        f"Адаптированный урок: {context_pack['source_lesson']['title']}"
        if mode == "adapt" and context_pack.get("source_lesson")
        else f"{subject}: {goal_text}"
    )
    prompt = request.get("adaptation_goal") or goal_text
    primary_type = (style.get("top_task_types") or ["text"])[0]
    if primary_type not in {"text", "writing_task"}:
        primary_type = "text"
    return {
        "title": title,
        "description": request.get("description")
        or f"Черновик урока, собранный под стиль автора. Цель: {prompt}.",
        "sections": [
            {
                "title": "Разогрев",
                "tasks": [
                    {
                        "task_type": primary_type,
                        "payload": {"content": f"Короткое вступление по теме '{subject}' с акцентом на {prompt}."}
                        if primary_type == "text"
                        else {"prompt": f"Напиши 80-120 слов про {subject}.", "default_text": ""},
                    }
                ],
            },
            {
                "title": "Практика",
                "tasks": [
                    {
                        "task_type": "writing_task",
                        "payload": {
                            "prompt": f"Сформулируй ответ по теме '{subject}' и учти: {prompt}.",
                            "default_text": "",
                        },
                    }
                ],
            },
        ],
    }


class ProviderRouter:
    def __init__(self, db: AsyncSession, *, job: GenerationJob):
        self.db = db
        self.job = job

    async def _record_call(
        self,
        *,
        provider_name: str,
        operation: str,
        started_at: float,
        status: ProviderCallStatus,
        request_summary: dict[str, Any] | None = None,
        response_summary: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> None:
        self.db.add(
            ProviderCall(
                job_id=self.job.id,
                provider_name=provider_name,
                operation=operation,
                status=status,
                request_summary=request_summary,
                response_summary=response_summary,
                error_message=error_message,
                latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
            )
        )
        await self.db.flush()

    async def _call_chain(
        self,
        *,
        providers: tuple[str, ...],
        operation: str,
        request_summary: dict[str, Any],
        runner,
    ) -> ProviderSelection:
        last_error: Exception | None = None
        for provider_name in providers:
            started_at = time.perf_counter()
            try:
                result = await runner(provider_name)
                await self._record_call(
                    provider_name=provider_name,
                    operation=operation,
                    started_at=started_at,
                    status=ProviderCallStatus.succeeded,
                    request_summary=request_summary,
                    response_summary={"ok": True},
                )
                return ProviderSelection(provider=provider_name, output=result)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                await self._record_call(
                    provider_name=provider_name,
                    operation=operation,
                    started_at=started_at,
                    status=ProviderCallStatus.failed,
                    request_summary=request_summary,
                    error_message=str(exc),
                )
        raise ProviderError(str(last_error) if last_error else "provider_chain_failed")

    async def generate_lesson_bundle(
        self, *, context_pack: dict[str, Any], prefer_pdf: bool, mode: str
    ) -> ProviderSelection:
        providers = settings.pdf_provider_chain if prefer_pdf else settings.text_provider_chain
        request_summary = {"mode": mode, "prefer_pdf": prefer_pdf}

        async def runner(provider_name: str) -> dict[str, Any]:
            if settings.use_mock_providers:
                return _mock_bundle(context_pack, mode=mode)
            if provider_name in {"gemma", "gemini"}:
                return await self._generate_bundle_via_gemini_family(
                    provider_name, context_pack, mode=mode
                )
            if provider_name == "gigachat":
                return await self._generate_bundle_via_gigachat(context_pack, mode=mode)
            raise ProviderError(f"unsupported_text_provider:{provider_name}")

        return await self._call_chain(
            providers=providers,
            operation="generate_lesson_bundle",
            request_summary=request_summary,
            runner=runner,
        )

    async def generate_image(self, *, prompt: str, size: str, filename: str) -> ProviderSelection:
        async def runner(provider_name: str) -> GeneratedBinary:
            if settings.use_mock_providers:
                payload = f"Mock image for prompt: {prompt} ({provider_name}, {size})".encode()
                return GeneratedBinary(
                    data=payload,
                    mime_type=settings.default_image_mime_type,
                    filename=filename,
                )
            return await self._generate_image_via_http(
                provider_name, prompt=prompt, size=size, filename=filename
            )

        return await self._call_chain(
            providers=settings.image_provider_chain,
            operation="generate_image",
            request_summary={"size": size, "filename": filename},
            runner=runner,
        )

    async def generate_audio(
        self,
        *,
        script: str,
        voice_mapping: dict[str, str],
        sample_context: str | None,
        filename: str,
    ) -> ProviderSelection:
        started_at = time.perf_counter()
        try:
            if settings.use_mock_providers:
                data = _wav_header(f"Mock audio for {script}".encode())
                output = GeneratedBinary(
                    data=data,
                    mime_type=settings.default_audio_mime_type,
                    filename=filename,
                )
            else:
                output = await self._generate_tts_via_gemini(
                    script=script,
                    voice_mapping=voice_mapping,
                    sample_context=sample_context,
                    filename=filename,
                )
            await self._record_call(
                provider_name="gemini_tts",
                operation="generate_audio",
                started_at=started_at,
                status=ProviderCallStatus.succeeded,
                request_summary={"filename": filename, "script_length": len(script)},
                response_summary={"mime_type": output.mime_type},
            )
            return ProviderSelection(provider="gemini_tts", output=output)
        except Exception as exc:  # noqa: BLE001
            await self._record_call(
                provider_name="gemini_tts",
                operation="generate_audio",
                started_at=started_at,
                status=ProviderCallStatus.failed,
                request_summary={"filename": filename, "script_length": len(script)},
                error_message=str(exc),
            )
            raise

    async def _generate_bundle_via_gemini_family(
        self, provider_name: str, context_pack: dict[str, Any], *, mode: str
    ) -> dict[str, Any]:
        if not settings.ai_gateway_url:
            raise ProviderError(f"{provider_name}_gateway_not_configured")

        model = settings.gemma_model if provider_name == "gemma" else settings.gemini_pdf_model
        prompt = _build_lesson_instruction(context_pack, mode=mode)
        request = context_pack["request"]
        attachments = request.get("source_attachments") or []

        parts: list[dict[str, Any]] = [{"text": prompt}]
        for attachment in attachments:
            file_bytes = _attachment_bytes(attachment)
            if file_bytes:
                parts.append(
                    {
                        "inlineData": {
                            "mimeType": attachment["mime_type"],
                            "data": attachment["content_base64"],
                        }
                    }
                )
            elif attachment.get("content_text"):
                parts.append(
                    {
                        "text": f"Attachment {attachment['file_name']} content:\n{attachment['content_text']}"
                    }
                )

        payload = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.5,
            },
        }
        async with httpx.AsyncClient(timeout=settings.provider_timeout_seconds) as client:
            response = await client.post(
                f"{settings.ai_gateway_url.rstrip('/')}/gemini/v1beta/models/{model}:generateContent",
                headers=_gateway_headers(),
                json=payload,
            )
        response.raise_for_status()
        data = response.json()
        text_parts = []
        for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
            if "text" in part:
                text_parts.append(part["text"])
        if not text_parts:
            raise ProviderError("empty_text_response")
        return _sanitize_json_output("\n".join(text_parts))

    async def _generate_bundle_via_gigachat(
        self, context_pack: dict[str, Any], *, mode: str
    ) -> dict[str, Any]:
        if not settings.gigachat_client_secret:
            raise ProviderError("gigachat_not_configured")

        request = context_pack["request"]
        attachments = request.get("source_attachments") or []
        prompt = _build_lesson_instruction(context_pack, mode=mode)

        async with httpx.AsyncClient(
            timeout=settings.provider_timeout_seconds,
            verify=False,
        ) as client:
            token = await self._gigachat_access_token(client)
            uploaded_ids: list[str] = []
            attachment_texts: list[str] = []
            for attachment in attachments:
                file_bytes = _attachment_bytes(attachment)
                if file_bytes:
                    uploaded_id = await self._gigachat_upload_file(
                        client,
                        token=token,
                        file_bytes=file_bytes,
                        filename=attachment["file_name"],
                        mime_type=attachment["mime_type"],
                    )
                    if uploaded_id:
                        uploaded_ids.append(uploaded_id)
                elif attachment.get("content_text"):
                    attachment_texts.append(
                        f"{attachment['file_name']}:\n{attachment['content_text']}"
                    )

            user_content = prompt
            if attachment_texts:
                user_content += "\n\nAttachment text bodies:\n" + "\n\n".join(attachment_texts)

            payload: dict[str, Any] = {
                "model": settings.gigachat_model,
                "messages": [{"role": "user", "content": user_content}],
            }
            if uploaded_ids:
                payload["function_call"] = "auto"
                payload["messages"][0]["attachments"] = uploaded_ids

            response = await client.post(
                f"{settings.gigachat_api_url.rstrip('/')}/chat/completions",
                headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                },
                json=payload,
            )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return _sanitize_json_output(content)

    async def _gigachat_access_token(self, client: httpx.AsyncClient) -> str:
        response = await client.post(
            settings.gigachat_auth_url,
            headers={
                "RqUID": str(uuid.uuid4()),
                "Authorization": f"Basic {settings.gigachat_client_secret}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            data={"scope": "GIGACHAT_API_PERS"},
        )
        response.raise_for_status()
        data = response.json()
        token = data.get("access_token")
        if not token:
            raise ProviderError("gigachat_missing_access_token")
        return token

    async def _gigachat_upload_file(
        self,
        client: httpx.AsyncClient,
        *,
        token: str,
        file_bytes: bytes,
        filename: str,
        mime_type: str,
    ) -> str | None:
        response = await client.post(
            f"{settings.gigachat_api_url.rstrip('/')}/files",
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "FastClass/1.0",
            },
            files={"file": (filename, file_bytes, mime_type)},
            data={"purpose": "general"},
        )
        response.raise_for_status()
        return response.json().get("id")

    async def _generate_image_via_http(
        self, provider_name: str, *, prompt: str, size: str, filename: str
    ) -> GeneratedBinary:
        width, height = size.split("x")

        if provider_name == "pollinations":
            headers = {"Content-Type": "application/json"}
            if settings.pollinations_api_key:
                headers["Authorization"] = f"Bearer {settings.pollinations_api_key}"
            headers = propagate_headers(headers)
            payload = {
                "model": settings.pollinations_image_model,
                "prompt": prompt,
                "size": size,
                "quality": settings.default_image_quality,
                "n": 1,
            }
            async with httpx.AsyncClient(timeout=settings.provider_timeout_seconds) as client:
                response = await client.post(
                    f"{settings.pollinations_base_url.rstrip('/')}/v1/images/generations",
                    json=payload,
                    headers=headers,
                )
            response.raise_for_status()
            data = response.json()
            b64 = ((data.get("data") or [{}])[0]).get("b64_json")
            if not b64:
                raise ProviderError("pollinations_empty_image")
            return GeneratedBinary(
                data=base64.b64decode(b64),
                mime_type=settings.default_image_mime_type,
                filename=filename,
            )

        if provider_name == "openrouter":
            if settings.ai_gateway_url:
                url = f"{settings.ai_gateway_url.rstrip('/')}/openrouter/images"
                headers = {**_gateway_headers(), "Content-Type": "application/json"}
            else:
                if not settings.openrouter_api_key:
                    raise ProviderError("openrouter_not_configured")
                url = f"{settings.openrouter_base_url.rstrip('/')}/images/generations"
                headers = propagate_headers({
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                })
            payload = {
                "model": settings.openrouter_image_model,
                "prompt": prompt,
                "quality": settings.default_image_quality,
                "size": size,
            }
            async with httpx.AsyncClient(timeout=settings.provider_timeout_seconds) as client:
                response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            first = (data.get("data") or [{}])[0]
            if first.get("b64_json"):
                image_bytes = base64.b64decode(first["b64_json"])
            elif first.get("url"):
                async with httpx.AsyncClient(timeout=settings.provider_timeout_seconds) as client:
                    img_response = await client.get(first["url"])
                img_response.raise_for_status()
                image_bytes = img_response.content
            else:
                raise ProviderError("openrouter_empty_image")
            return GeneratedBinary(
                data=image_bytes,
                mime_type=settings.default_image_mime_type,
                filename=filename,
            )

        if provider_name == "flux":
            if settings.flux_base_url:
                url = settings.flux_base_url
                headers = {"Content-Type": "application/json"}
                if settings.flux_api_key:
                    headers["Authorization"] = f"Bearer {settings.flux_api_key}"
                headers = propagate_headers(headers)
            elif settings.ai_gateway_url:
                url = f"{settings.ai_gateway_url.rstrip('/')}/{settings.flux_gateway_path.lstrip('/')}"
                headers = {"Content-Type": "application/json", "Cache-Control": "no-cache", **_gateway_headers()}
            else:
                raise ProviderError("flux_not_configured")

            payload = {
                "prompt": prompt,
                "num_steps": 5,
                "seed": random.randint(1, 1_000_000),
                "height": int(height),
                "width": int(width),
            }
            async with httpx.AsyncClient(timeout=settings.provider_timeout_seconds) as client:
                response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            output = data.get("output", {})
            image_bytes: bytes | None = None
            if isinstance(output, dict) and output.get("media_url"):
                async with httpx.AsyncClient(timeout=settings.provider_timeout_seconds) as client:
                    img_response = await client.get(output["media_url"])
                img_response.raise_for_status()
                image_bytes = img_response.content
            elif isinstance(output, dict) and output.get("data_uri") and "base64," in output["data_uri"]:
                image_bytes = base64.b64decode(output["data_uri"].split("base64,")[1])
            elif isinstance(output, str) and output.startswith("http"):
                async with httpx.AsyncClient(timeout=settings.provider_timeout_seconds) as client:
                    img_response = await client.get(output)
                img_response.raise_for_status()
                image_bytes = img_response.content
            elif data.get("images"):
                first = data["images"][0]
                if str(first).startswith("http"):
                    async with httpx.AsyncClient(timeout=settings.provider_timeout_seconds) as client:
                        img_response = await client.get(first)
                    img_response.raise_for_status()
                    image_bytes = img_response.content
                else:
                    image_bytes = base64.b64decode(first)
            if not image_bytes:
                raise ProviderError("flux_empty_image")
            return GeneratedBinary(
                data=image_bytes,
                mime_type=settings.default_image_mime_type,
                filename=filename,
            )

        raise ProviderError(f"unsupported_image_provider:{provider_name}")

    async def _generate_tts_via_gemini(
        self,
        *,
        script: str,
        voice_mapping: dict[str, str],
        sample_context: str | None,
        filename: str,
    ) -> GeneratedBinary:
        if not settings.ai_gateway_url:
            raise ProviderError("gemini_tts_gateway_not_configured")

        selected_voice = (
            voice_mapping.get("default")
            or next(iter(voice_mapping.values()), None)
            or settings.default_tts_voice
        ).lower()
        if selected_voice not in {"aoede", "charon"}:
            if selected_voice in {"kore", "leda"}:
                selected_voice = "aoede"
            elif selected_voice in {"puck", "fenrir"}:
                selected_voice = "charon"
            else:
                selected_voice = settings.default_tts_voice

        prompt = f"Generate audio for this script:\n\n{script}"
        if sample_context:
            prompt = f"## Sample Context:\n{sample_context}\n\n## Transcript:\n{script}"

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": selected_voice,
                        }
                    }
                },
            },
        }
        async with httpx.AsyncClient(timeout=settings.provider_timeout_seconds) as client:
            response = await client.post(
                f"{settings.ai_gateway_url.rstrip('/')}/gemini/v1beta/models/{settings.gemini_tts_model}:generateContent",
                json=payload,
                headers=_gateway_headers(),
            )
        response.raise_for_status()
        data = response.json()
        audio_bytes: bytes | None = None
        for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
            inline = part.get("inlineData")
            if inline and str(inline.get("mimeType", "")).startswith("audio/"):
                audio_bytes = base64.b64decode(inline["data"])
                break
        if not audio_bytes:
            raise ProviderError("tts_empty_audio")
        if audio_bytes[:4] != b"RIFF":
            audio_bytes = _wav_header(audio_bytes)
        return GeneratedBinary(
            data=audio_bytes,
            mime_type=settings.default_audio_mime_type,
            filename=filename,
        )
