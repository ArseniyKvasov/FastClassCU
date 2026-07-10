"""Single source of truth for task types.

Old monolith spread task-type knowledge across four places (model map,
serializer map, a hand-written if/elif in get_task_data, and the view
dispatch) that drifted out of sync. Here every task type is one registry
entry: a Pydantic schema that validates the write payload AND defines the
canonical read shape. Adding a type = adding one entry, nothing else.
"""

from __future__ import annotations

import html
import re
from typing import ClassVar

from pydantic import BaseModel, field_validator

_TAG_RE = re.compile(r"<[^>]+>")


def sanitize_rich_text(value: str) -> str:
    """One deliberate sanitization policy for all user rich text: strip tags
    and escape."""
    return html.escape(_TAG_RE.sub("", value)).strip()


class TaskSchema(BaseModel):
    """Base for every task-type payload schema. `has_file` marks types whose
    payload references a FileAsset (so services know to wire file_id).
    `allowed_mime_types` - non-empty only for has_file types - is enforced by
    Content Service's get_or_create_content before it lets a file be attached
    to a task of this type (e.g. an "image" task can't reference an mp3)."""

    task_type: ClassVar[str]
    has_file: ClassVar[bool] = False
    allowed_mime_types: ClassVar[tuple[str, ...]] = ()


class TextTaskSchema(TaskSchema):
    task_type: ClassVar[str] = "text"
    content: str

    @field_validator("content")
    @classmethod
    def _clean(cls, v: str) -> str:
        return sanitize_rich_text(v)


class TestQuestion(BaseModel):
    question: str
    options: list[str]
    correct_index: int


class TestTaskSchema(TaskSchema):
    # One task can hold several questions (matches the monolith's TestTask,
    # which is a single quiz block with a `questions` array) - Answers
    # Service's checker scores one Task's worth of questions per submission.
    task_type: ClassVar[str] = "test"
    questions: list[TestQuestion]

    @field_validator("questions")
    @classmethod
    def _clean(cls, questions: list[TestQuestion]) -> list[TestQuestion]:
        for q in questions:
            q.question = sanitize_rich_text(q.question)
        return questions


class TrueFalseStatement(BaseModel):
    text: str
    is_true: bool


class TrueFalseTaskSchema(TaskSchema):
    task_type: ClassVar[str] = "true_false"
    statements: list[TrueFalseStatement]

    @field_validator("statements")
    @classmethod
    def _clean(cls, statements: list[TrueFalseStatement]) -> list[TrueFalseStatement]:
        for s in statements:
            s.text = sanitize_rich_text(s.text)
        return statements


class FillGapsTaskSchema(TaskSchema):
    task_type: ClassVar[str] = "fill_gaps"
    text: str  # contains {{answer}} markers, one per entry in `answers`
    answers: list[str]

    @field_validator("text")
    @classmethod
    def _clean(cls, v: str) -> str:
        return sanitize_rich_text(v)


class MatchCard(BaseModel):
    left: str
    right: str


class MatchCardsTaskSchema(TaskSchema):
    task_type: ClassVar[str] = "match_cards"
    cards: list[MatchCard]


class ReorderSentence(BaseModel):
    words: list[str]


class ReorderTaskSchema(TaskSchema):
    task_type: ClassVar[str] = "reorder"
    sentences: list[ReorderSentence]


class SortingColumn(BaseModel):
    title: str
    items: list[str]


class SortingTaskSchema(TaskSchema):
    task_type: ClassVar[str] = "sorting"
    columns: list[SortingColumn]


class WritingTaskSchema(TaskSchema):
    task_type: ClassVar[str] = "writing_task"
    prompt: str
    default_text: str = ""

    @field_validator("prompt", "default_text")
    @classmethod
    def _clean(cls, v: str) -> str:
        return sanitize_rich_text(v)


class FileTaskSchema(TaskSchema):
    # Documents only - PDF and Word directly; presentations are accepted and
    # converted to PDF by the (not-yet-built) async processing pipeline, same
    # as the monolith's behavior. Images/audio are their own task types below,
    # not "file" - they render and are answered differently.
    task_type: ClassVar[str] = "file"
    has_file: ClassVar[bool] = True
    allowed_mime_types: ClassVar[tuple[str, ...]] = (
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
    description: str = ""

    @field_validator("description")
    @classmethod
    def _clean(cls, v: str) -> str:
        return sanitize_rich_text(v)


class ImageTaskSchema(TaskSchema):
    task_type: ClassVar[str] = "image"
    has_file: ClassVar[bool] = True
    allowed_mime_types: ClassVar[tuple[str, ...]] = (
        "image/png",
        "image/jpeg",
        "image/webp",
        "image/gif",
    )
    alt_text: str = ""

    @field_validator("alt_text")
    @classmethod
    def _clean(cls, v: str) -> str:
        return sanitize_rich_text(v)


class AudioTaskSchema(TaskSchema):
    task_type: ClassVar[str] = "audio"
    has_file: ClassVar[bool] = True
    allowed_mime_types: ClassVar[tuple[str, ...]] = (
        "audio/mpeg",
        "audio/wav",
        "audio/ogg",
        "audio/mp4",
        "audio/webm",
    )
    transcript: str = ""

    @field_validator("transcript")
    @classmethod
    def _clean(cls, v: str) -> str:
        return sanitize_rich_text(v)


class VoiceRecordingTaskSchema(TaskSchema):
    # Subjective/manual type - Answers Service never auto-checks this, only
    # stores the recording reference and lets a teacher set manual_score.
    # This is a STUDENT-recorded answer prompt, unlike "audio" (teacher-
    # supplied listening material) - kept as a separate type deliberately.
    task_type: ClassVar[str] = "voice_recording"
    prompt: str = ""

    @field_validator("prompt")
    @classmethod
    def _clean(cls, v: str) -> str:
        return sanitize_rich_text(v)


_INTEGRATION_ALLOWED_DOMAINS = (
    "wordwall.net",
    "miro.com",
    "quizlet.com",
    "learningapps.org",
    "rutube.ru",
    "sboard.online",
    "geogebra.org",
)


class IntegrationTaskSchema(TaskSchema):
    # Embeds a third-party interactive tool - allow-listed domains only
    # (same list the monolith enforced), since this renders in an iframe
    # with no sandboxing of the embedded origin itself.
    task_type: ClassVar[str] = "integration"
    embed_url: str

    @field_validator("embed_url")
    @classmethod
    def _validate_domain(cls, v: str) -> str:
        from urllib.parse import urlparse

        host = (urlparse(v).hostname or "").lower()
        if not any(host == d or host.endswith(f".{d}") for d in _INTEGRATION_ALLOWED_DOMAINS):
            raise ValueError(
                f"embed_url host '{host}' is not in the allowed domain list: "
                f"{', '.join(_INTEGRATION_ALLOWED_DOMAINS)}"
            )
        return v


class WordListWord(BaseModel):
    word: str
    translation: str = ""


class WordListTaskSchema(TaskSchema):
    task_type: ClassVar[str] = "word_list"
    words: list[WordListWord]


REGISTRY: dict[str, type[TaskSchema]] = {
    schema.task_type: schema
    for schema in (
        TextTaskSchema,
        TestTaskSchema,
        TrueFalseTaskSchema,
        FillGapsTaskSchema,
        MatchCardsTaskSchema,
        ReorderTaskSchema,
        SortingTaskSchema,
        WritingTaskSchema,
        FileTaskSchema,
        ImageTaskSchema,
        AudioTaskSchema,
        VoiceRecordingTaskSchema,
        IntegrationTaskSchema,
        WordListTaskSchema,
    )
}


def get_schema(task_type: str) -> type[TaskSchema]:
    schema = REGISTRY.get(task_type)
    if schema is None:
        raise ValueError(f"Unknown task_type '{task_type}'")
    return schema


def validate_payload(task_type: str, payload: dict) -> dict:
    """Validates and normalizes a write payload against its schema, returning
    the canonical dict that will be hashed and stored. task_type is a ClassVar,
    so it never appears in the dumped payload."""
    schema = get_schema(task_type)
    model = schema(**payload)
    return model.model_dump()
