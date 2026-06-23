from __future__ import annotations
import logging
import uuid
from datetime import datetime
from typing import Optional, Any, Dict, List

from config.settings import settings

logger = logging.getLogger(__name__)

class FirestoreChatService:
    """CRUD and persistence operations for Chat Threads on Google Cloud Firestore."""
    def __init__(self):
        from firebase_admin import firestore
        self.db = firestore.client()

    def create_thread(self, thread_id: str, user_id: str, dataset_id: str) -> dict[str, Any]:
        doc_ref = self.db.collection("users").document(user_id).collection("datasets").document(dataset_id).collection("threads").document(thread_id)
        now = datetime.utcnow().isoformat()
        thread_data = {
            "thread_id": thread_id,
            "user_id": user_id,
            "dataset_id": dataset_id,
            "created_at": now,
            "updated_at": now,
            "messages": []
        }
        doc_ref.set(thread_data)
        logger.info("Created Firestore chat thread %s for user %s", thread_id, user_id)
        return thread_data

    def _get_thread_doc(self, thread_id: str, user_id: str, dataset_id: Optional[str] = None):
        """Helper to safely retrieve the firestore document reference for a thread,
        supporting direct O(1) lookups and fallback scanning when index is missing.
        """
        # 1. Direct Lookup (O(1) time, index-free) if dataset_id (session_id) is provided
        if dataset_id:
            try:
                doc_ref = self.db.collection("users").document(user_id).collection("datasets").document(dataset_id).collection("threads").document(thread_id)
                doc = doc_ref.get()
                if doc.exists:
                    return doc
            except Exception as direct_exc:
                logger.warning("Direct lookup failed for thread %s under dataset %s: %s", thread_id, dataset_id, direct_exc)

        # 2. Try Collection Group query (standard)
        try:
            docs_stream = self.db.collection_group("threads").where("thread_id", "==", thread_id).stream()
            docs = list(docs_stream)
            for doc in docs:
                data = doc.to_dict()
                if data.get("user_id") == user_id:
                    return doc
        except Exception as e:
            err_str = str(e)
            if "FailedPrecondition" in err_str or "index" in err_str.lower():
                logger.warning(
                    "⚠️ Firestore Collection Group index missing for 'threads'. "
                    "Falling back to direct dataset/session scanning..."
                )
            else:
                logger.error("❌ Firestore error during collection group query: %s", err_str)
                raise RuntimeError("Failed to retrieve thread data due to a database error.")

        # 3. Index-free Fallback Scan: Search user's active session/dataset paths directly
        try:
            doc_refs = self.db.collection("users").document(user_id).collection("datasets").list_documents()
            for doc_ref in doc_refs:
                thread_ref = doc_ref.collection("threads").document(thread_id)
                thread_doc = thread_ref.get()
                if thread_doc.exists:
                    logger.info("Found thread %s via direct fallback scan.", thread_id)
                    return thread_doc
        except Exception as scan_exc:
            logger.error("❌ Failed direct fallback scan for thread %s: %s", thread_id, scan_exc)
            
        return None

    def get_thread(self, thread_id: str, user_id: str, dataset_id: Optional[str] = None) -> Optional[dict[str, Any]]:
        doc = self._get_thread_doc(thread_id, user_id, dataset_id)
        return doc.to_dict() if doc else None

    def delete_thread(self, thread_id: str, user_id: str, dataset_id: Optional[str] = None) -> bool:
        doc = self._get_thread_doc(thread_id, user_id, dataset_id)
        if doc:
            doc.reference.delete()
            logger.info("Deleted Firestore chat thread %s", thread_id)
            return True
        return False

    def add_message(self, thread_id: str, user_id: str, message: dict[str, Any], dataset_id: Optional[str] = None) -> bool:
        doc = self._get_thread_doc(thread_id, user_id, dataset_id)
        if doc:
            data = doc.to_dict()
            messages = data.get("messages", [])
            
            # Sanitize: Do not store raw dataset rows in the chat history database,
            # only the answer text and execution metadata.
            # Let's ensure the message does not carry the full data payload to preserve DB space.
            msg_copy = message.copy()
            if "metadata" in msg_copy and "had_data" in msg_copy["metadata"]:
                if "data" in msg_copy:
                    msg_copy.pop("data")

            messages.append(msg_copy)
            now = datetime.utcnow().isoformat()
            doc.reference.update({
                "messages": messages,
                "updated_at": now
            })
            return True
        return False



class PostgresChatService:
    """CRUD and persistence operations for Chat Threads on PostgreSQL."""
    def __init__(self, db_url: str):
        import psycopg_pool
        self.db_url = db_url
        self.pool = psycopg_pool.ConnectionPool(
            conninfo=db_url,
            open=True,
            min_size=1,
            max_size=5,
            kwargs={"autocommit": True}
        )
        self.init_db()

    def init_db(self):
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS chat_threads (
                        thread_id VARCHAR(255) PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        dataset_id VARCHAR(255) NOT NULL,
                        created_at VARCHAR(100) NOT NULL,
                        updated_at VARCHAR(100) NOT NULL,
                        messages JSONB NOT NULL DEFAULT '[]'
                    );
                """)

    def create_thread(self, thread_id: str, user_id: str, dataset_id: str) -> dict[str, Any]:
        import json
        now = datetime.utcnow().isoformat()
        thread_data = {
            "thread_id": thread_id,
            "user_id": user_id,
            "dataset_id": dataset_id,
            "created_at": now,
            "updated_at": now,
            "messages": []
        }
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO chat_threads (thread_id, user_id, dataset_id, created_at, updated_at, messages)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (thread_id, user_id, dataset_id, now, now, json.dumps([]))
                )
        logger.info("Created PostgreSQL chat thread %s for user %s", thread_id, user_id)
        return thread_data

    def get_thread(self, thread_id: str, user_id: str, dataset_id: Optional[str] = None) -> Optional[dict[str, Any]]:
        import json
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT thread_id, user_id, dataset_id, created_at, updated_at, messages FROM chat_threads WHERE thread_id = %s",
                    (thread_id,)
                )
                row = cur.fetchone()
                if not row:
                    return None
                
                # Enforce ownership check
                if row[1] != user_id:
                    return None
                
                msgs = row[5]
                if isinstance(msgs, str):
                    msgs = json.loads(msgs)
                
                return {
                    "thread_id": row[0],
                    "user_id": row[1],
                    "dataset_id": row[2],
                    "created_at": row[3],
                    "updated_at": row[4],
                    "messages": msgs
                }

    def delete_thread(self, thread_id: str, user_id: str, dataset_id: Optional[str] = None) -> bool:
        thread = self.get_thread(thread_id, user_id, dataset_id)
        if not thread:
            return False
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM chat_threads WHERE thread_id = %s", (thread_id,))
        logger.info("Deleted PostgreSQL chat thread %s", thread_id)
        return True

    def add_message(self, thread_id: str, user_id: str, message: dict[str, Any], dataset_id: Optional[str] = None) -> bool:
        import json
        thread = self.get_thread(thread_id, user_id, dataset_id)
        if not thread:
            return False
        
        messages = thread.get("messages", [])
        
        # Sanitize: Do not store raw dataset rows in the chat history database
        msg_copy = message.copy()
        if "metadata" in msg_copy and "had_data" in msg_copy["metadata"]:
            if "data" in msg_copy:
                msg_copy.pop("data")

        messages.append(msg_copy)
        now = datetime.utcnow().isoformat()
        
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE chat_threads SET messages = %s, updated_at = %s WHERE thread_id = %s",
                    (json.dumps(messages), now, thread_id)
                )
        return True


class InMemoryChatService:
    """Mock in-memory service for testing and development bypass."""
    def __init__(self):
        self.store: dict[str, dict[str, Any]] = {}

    def create_thread(self, thread_id: str, user_id: str, dataset_id: str) -> dict[str, Any]:
        now = datetime.utcnow().isoformat()
        thread_data = {
            "thread_id": thread_id,
            "user_id": user_id,
            "dataset_id": dataset_id,
            "created_at": now,
            "updated_at": now,
            "messages": []
        }
        self.store[thread_id] = thread_data
        logger.info("Created In-Memory chat thread %s for user %s", thread_id, user_id)
        return thread_data

    def get_thread(self, thread_id: str, user_id: str, dataset_id: Optional[str] = None) -> Optional[dict[str, Any]]:
        thread = self.store.get(thread_id)
        if thread and thread.get("user_id") == user_id:
            return thread
        return None

    def delete_thread(self, thread_id: str, user_id: str, dataset_id: Optional[str] = None) -> bool:
        thread = self.get_thread(thread_id, user_id, dataset_id)
        if thread:
            del self.store[thread_id]
            logger.info("Deleted In-Memory chat thread %s", thread_id)
            return True
        return False

    def add_message(self, thread_id: str, user_id: str, message: dict[str, Any], dataset_id: Optional[str] = None) -> bool:
        thread = self.get_thread(thread_id, user_id, dataset_id)
        if thread:
            messages = thread.get("messages", [])
            
            # Sanitize: Do not store raw dataset rows in the chat history database
            msg_copy = message.copy()
            if "metadata" in msg_copy and "had_data" in msg_copy["metadata"]:
                if "data" in msg_copy:
                    msg_copy.pop("data")

            messages.append(msg_copy)
            thread["messages"] = messages
            thread["updated_at"] = datetime.utcnow().isoformat()
            return True
        return False


# Singleton instance
_chat_service_instance = None

def get_chat_service():
    """Factory dependency resolver for chat persistence service layer."""
    global _chat_service_instance
    if _chat_service_instance is None:
        if settings.DATABASE_URL:
            logger.info("🔌 Initializing PostgreSQL chat service...")
            _chat_service_instance = PostgresChatService(settings.DATABASE_URL)
        elif settings.FIREBASE_PROJECT_ID:
            logger.info("🔌 Initializing Firestore chat service...")
            _chat_service_instance = FirestoreChatService()
        else:
            logger.info("ℹ️ Using fallback in-memory chat service...")
            _chat_service_instance = InMemoryChatService()
    return _chat_service_instance
