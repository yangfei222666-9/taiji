"""
OpenAI-compatible request/response schemas (Pydantic v2).
"""
import time
import uuid
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


# ── Request models ───────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: Union[str, List[Any]]
    name: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: bool = False
    top_p: Optional[float] = None
    stop: Optional[Union[str, List[str]]] = None
    # Gateway extensions
    x_caller: Optional[str] = Field(None, alias="x-caller")
    x_task_id: Optional[str] = Field(None, alias="x-task-id")
    x_session_id: Optional[str] = Field(None, alias="x-session-id")

    model_config = {"populate_by_name": True}


# ── Response models ──────────────────────────────────────────────

class UsageInfo(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChoiceMessage(BaseModel):
    role: str = "assistant"
    content: str = ""


class ChatCompletionChoice(BaseModel):
    index: int = 0
    message: ChoiceMessage
    finish_reason: Optional[str] = "stop"


class ChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:12]}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = ""
    choices: List[ChatCompletionChoice] = []
    usage: UsageInfo = Field(default_factory=UsageInfo)


# ── Streaming chunk models ───────────────────────────────────────

class DeltaMessage(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None


class StreamChoice(BaseModel):
    index: int = 0
    delta: DeltaMessage
    finish_reason: Optional[str] = None


class ChatCompletionChunk(BaseModel):
    id: str = ""
    object: str = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = ""
    choices: List[StreamChoice] = []


# ── Model list ───────────────────────────────────────────────────

class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int = 0
    owned_by: str = "taijios"


class ModelListResponse(BaseModel):
    object: str = "list"
    data: List[ModelInfo] = []


# ── Error ────────────────────────────────────────────────────────

class ErrorDetail(BaseModel):
    message: str
    type: str = "error"
    code: Optional[str] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
