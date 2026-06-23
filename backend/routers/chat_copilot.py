from __future__ import annotations
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException

from schemas.chat import CopilotQueryRequest, CopilotQueryResponse, CreateThreadRequest, ThreadResponse
from services.query_engine import CopilotQueryEngine
from services.chat_service import get_chat_service
from utils.auth import verify_firebase_token
from utils.session_manager import session_manager
from utils.validators import scan_guardrails

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v3/chat", tags=["Copilot Chat"])

def _build_chat_history_from_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert flat thread messages list to the format expected by LLMGenerator (question & answer pairs)."""
    chat_history = []
    current_turn = {}
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "user":
            current_turn = {"question": content}
        elif role in ("assistant", "agent"):
            current_turn["answer"] = content
            chat_history.append(current_turn)
            current_turn = {}
    if current_turn and "question" in current_turn:
        current_turn["answer"] = ""
        chat_history.append(current_turn)
    return chat_history

@router.post("/thread", response_model=ThreadResponse, status_code=201)
async def create_thread(
    req: CreateThreadRequest,
    user: dict = Depends(verify_firebase_token)
):
    """Create a new chat conversation thread associated with a dataset session."""
    user_id = user.get("uid")
    session_id = req.sessionId

    if not session_manager.session_exists(user_id, session_id):
        logger.warning(
            "Session not found for thread creation: user_id=%s, session_id=%s",
            user_id, session_id
        )
        raise HTTPException(status_code=404, detail="Session not found.")

    thread_id = str(uuid.uuid4())
    try:
        thread = get_chat_service().create_thread(thread_id, user_id, session_id)
        return thread
    except Exception as exc:
        logger.error("Failed to create thread: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error creating thread.")

@router.get("/thread/{thread_id}", response_model=ThreadResponse)
async def get_thread(
    thread_id: str,
    user: dict = Depends(verify_firebase_token)
):
    """Retrieve chat history and metadata for a thread."""
    user_id = user.get("uid")
    try:
        thread = get_chat_service().get_thread(thread_id, user_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found.")
        return thread
    except HTTPException as e:
        raise e
    except Exception as exc:
        logger.error("Failed to retrieve thread %s: %s", thread_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error retrieving thread.")

@router.delete("/thread/{thread_id}")
async def delete_thread(
    thread_id: str,
    user: dict = Depends(verify_firebase_token)
):
    """Delete a conversation thread."""
    user_id = user.get("uid")
    try:
        success = get_chat_service().delete_thread(thread_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Thread not found.")
        return {"success": True, "message": "Thread deleted successfully."}
    except HTTPException as e:
        raise e
    except Exception as exc:
        logger.error("Failed to delete thread %s: %s", thread_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error deleting thread.")

@router.post("/query", response_model=CopilotQueryResponse)
async def query_copilot(
    req: CopilotQueryRequest,
    user: dict = Depends(verify_firebase_token)
):
    """v3 AI Data Copilot query endpoint.
    
    Processes natural language queries and records interaction to the active thread if threadId is set.
    """
    user_id = user.get("uid")
    session_id = req.sessionId

    # 1. Run security guardrails
    safe, reason = scan_guardrails(req.question)
    if not safe:
        logger.warning(
            "Guardrail BLOCKED: user_id=%s, session_id=%s, reason=%s",
            user_id, session_id, reason
        )
        raise HTTPException(status_code=400, detail=reason)

    # 2. Check session existence & load dataset
    if not session_manager.session_exists(user_id, session_id):
        logger.warning(
            "Session not found: user_id=%s, session_id=%s",
            user_id, session_id
        )
        raise HTTPException(status_code=404, detail="Session not found.")

    # 3. Handle thread history loading if threadId is supplied
    chat_history = []
    if req.threadId:
        thread = get_chat_service().get_thread(req.threadId, user_id, session_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found.")
        # Override client-supplied chatHistory with database truth
        chat_history = _build_chat_history_from_messages(thread.get("messages", []))
    else:
        chat_history = req.chatHistory or []

    try:
        df = session_manager.load_dataframe(user_id, session_id)
    except HTTPException as e:
        raise e
    except Exception as exc:
        logger.error(
            "Failed to load dataframe: user_id=%s, session_id=%s, error=%s",
            user_id, session_id, exc, exc_info=True
        )
        raise HTTPException(status_code=500, detail="Failed to load session dataset.")

    # 4. Process the query using CopilotQueryEngine
    try:
        df_copy = df.copy()
        res = CopilotQueryEngine.process_query(
            df=df_copy,
            question=req.question,
            chat_history=chat_history,
            persona=req.persona,
            debug_mode=req.debugMode
        )
    except Exception as exc:
        logger.error(
            "Query execution failure: user_id=%s, session_id=%s, error=%s",
            user_id, session_id, exc, exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while processing the query."
        )

    # 5. Handle conversation persistence saving if threadId is supplied
    if req.threadId:
        try:
            user_message = {
                "message_id": str(uuid.uuid4()),
                "role": "user",
                "content": req.question,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {}
            }
            
            had_data = res.get("data") is not None
            truncated = False
            if res.get("truncation_meta"):
                truncated = res.get("truncation_meta", {}).get("truncated", False)
                
            assistant_message = {
                "message_id": str(uuid.uuid4()),
                "role": "assistant",
                "content": res.get("answer", ""),
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": {
                    "execution_type": res.get("execution_type"),
                    "execution_time_ms": res.get("execution_time_ms", 0),
                    "had_data": had_data,
                    "truncated": truncated
                }
            }
            # Save User Message and Assistant Message to thread
            get_chat_service().add_message(req.threadId, user_id, user_message, session_id)
            get_chat_service().add_message(req.threadId, user_id, assistant_message, session_id)
        except Exception as exc:
            # We don't block query output if saving to DB fails, but we log the incident.
            logger.error(
                "Failed to persist chat messages to thread %s: %s",
                req.threadId, exc, exc_info=True
            )

    # 6. Structured Logging
    logger.info(
        "Copilot Query API Success: user_id=%s, session_id=%s, query_type=%s, "
        "execution_path=%s, execution_time_ms=%d, success=%s",
        user_id,
        session_id,
        "copilot_query",
        res.get("execution_type"),
        res.get("execution_time_ms", 0),
        str(res.get("success", False))
    )

    return res
