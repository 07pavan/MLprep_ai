from __future__ import annotations
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class CreateThreadRequest(BaseModel):
    sessionId: str

class ThreadResponse(BaseModel):
    thread_id: str
    user_id: str
    dataset_id: str
    created_at: str
    updated_at: str
    messages: List[Dict[str, Any]] = []

class CopilotQueryRequest(BaseModel):
    sessionId: str
    question: str
    chatHistory: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    persona: Optional[str] = "general"
    debugMode: bool = False
    threadId: Optional[str] = None

class CopilotQueryResponse(BaseModel):
    success: bool
    answer: str
    data: Optional[Any] = None
    truncation_meta: Optional[Dict[str, Any]] = None
    execution_type: str
    execution_time_ms: int
    code: Optional[str] = None
    error: Optional[str] = None
