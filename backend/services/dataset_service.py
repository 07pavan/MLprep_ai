from __future__ import annotations
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)

class FirestoreDatasetService:
    """CRUD operations for dataset registry on Google Cloud Firestore."""
    def __init__(self):
        from firebase_admin import firestore
        self.db = firestore.client()

    def create_dataset(self, data: dict[str, Any]):
        self.db.collection("datasets").document(data["dataset_id"]).set(data)

    def get_dataset(self, dataset_id: str) -> Optional[dict[str, Any]]:
        doc = self.db.collection("datasets").document(dataset_id).get()
        return doc.to_dict() if doc.exists else None

    def list_datasets(self, user_id: str) -> list[dict[str, Any]]:
        docs = self.db.collection("datasets").where("user_id", "==", user_id).stream()
        return [doc.to_dict() for doc in docs]

    def update_dataset(self, dataset_id: str, data: dict[str, Any]):
        self.db.collection("datasets").document(dataset_id).update(data)

    def delete_dataset(self, dataset_id: str):
        self.db.collection("datasets").document(dataset_id).delete()


class PostgresDatasetService:
    """CRUD operations for dataset registry on PostgreSQL."""
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
                # Create the datasets table if it does not exist.
                # Existing records are preserved across app startups/restarts.
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS datasets (
                        dataset_id VARCHAR(255) PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        dataset_name VARCHAR(255) NOT NULL,
                        original_file_type VARCHAR(50) NOT NULL,
                        source VARCHAR(50) NOT NULL,
                        upload_timestamp VARCHAR(100) NOT NULL,
                        row_count INTEGER NOT NULL,
                        column_count INTEGER NOT NULL,
                        memory_usage DOUBLE PRECISION NOT NULL,
                        parquet_path VARCHAR(500) NOT NULL,
                        ml_readiness_score INTEGER,
                        dataset_version INTEGER NOT NULL,
                        status VARCHAR(50) NOT NULL,
                        parent_dataset_id VARCHAR(255),
                        source_url VARCHAR(1000),
                        import_options JSON
                    );
                """)
                
                # Check and add source_url column (migration safety check)
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='datasets' AND column_name='source_url';
                """)
                if not cur.fetchone():
                    cur.execute("ALTER TABLE datasets ADD COLUMN source_url VARCHAR(1000);")
                    logger.info("Migrated datasets table: Added source_url column.")

                # Check and add import_options column (migration safety check)
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='datasets' AND column_name='import_options';
                """)
                if not cur.fetchone():
                    cur.execute("ALTER TABLE datasets ADD COLUMN import_options JSON;")
                    logger.info("Migrated datasets table: Added import_options column.")

    def create_dataset(self, data: dict[str, Any]):
        import json
        import_options_json = (
            json.dumps(data.get("import_options"))
            if data.get("import_options") is not None
            else None
        )
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO datasets (
                        dataset_id, user_id, dataset_name, original_file_type, source,
                        upload_timestamp, row_count, column_count, memory_usage,
                        parquet_path, ml_readiness_score, dataset_version, status,
                        parent_dataset_id, source_url, import_options
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        data["dataset_id"], data["user_id"], data["dataset_name"], data["original_file_type"], data["source"],
                        data["upload_timestamp"], data["row_count"], data["column_count"], data["memory_usage"],
                        data["parquet_path"], data["ml_readiness_score"], data["dataset_version"], data["status"],
                        data.get("parent_dataset_id"), data.get("source_url"), import_options_json
                    )
                )

    def _parse_row(self, colnames: list[str], row: tuple | None) -> Optional[dict[str, Any]]:
        if not row:
            return None
        res = dict(zip(colnames, row))
        
        # Deserialize import_options back into a dictionary if stored as a string
        if "import_options" in res and isinstance(res["import_options"], str):
            try:
                import json
                res["import_options"] = json.loads(res["import_options"])
            except Exception:
                pass
        return res

    def get_dataset(self, dataset_id: str) -> Optional[dict[str, Any]]:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM datasets WHERE dataset_id = %s", (dataset_id,))
                row = cur.fetchone()
                if not row:
                    return None
                colnames = [desc[0] for desc in cur.description]
                return self._parse_row(colnames, row)

    def list_datasets(self, user_id: str) -> list[dict[str, Any]]:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM datasets WHERE user_id = %s", (user_id,))
                rows = cur.fetchall()
                colnames = [desc[0] for desc in cur.description]
                return [r for r in (self._parse_row(colnames, row) for row in rows) if r is not None]

    def update_dataset(self, dataset_id: str, data: dict[str, Any]):
        if not data:
            return
        set_clauses = []
        values = []
        for k, v in data.items():
            set_clauses.append(f"{k} = %s")
            if k == "import_options" and v is not None:
                import json
                values.append(json.dumps(v))
            else:
                values.append(v)
        values.append(dataset_id)
        query = f"UPDATE datasets SET {', '.join(set_clauses)} WHERE dataset_id = %s"
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, tuple(values))

    def delete_dataset(self, dataset_id: str):
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM datasets WHERE dataset_id = %s", (dataset_id,))


class InMemoryDatasetService:
    """Mock in-memory service for testing and development bypass."""
    def __init__(self):
        self.store: dict[str, dict[str, Any]] = {}

    def create_dataset(self, data: dict[str, Any]):
        self.store[data["dataset_id"]] = data

    def get_dataset(self, dataset_id: str) -> Optional[dict[str, Any]]:
        return self.store.get(dataset_id)

    def list_datasets(self, user_id: str) -> list[dict[str, Any]]:
        return [d for d in self.store.values() if d["user_id"] == user_id]

    def update_dataset(self, dataset_id: str, data: dict[str, Any]):
        if dataset_id in self.store:
            self.store[dataset_id].update(data)

    def delete_dataset(self, dataset_id: str):
        if dataset_id in self.store:
            del self.store[dataset_id]


# Singleton instance
_service_instance = None

def get_dataset_service():
    """Factory dependency resolver for dataset service layer."""
    global _service_instance
    if _service_instance is None:
        from config.settings import settings
        if settings.DATABASE_URL:
            logger.info("🔌 Initializing PostgreSQL dataset service...")
            _service_instance = PostgresDatasetService(settings.DATABASE_URL)
        elif settings.FIREBASE_PROJECT_ID:
            logger.info("🔌 Initializing Firestore dataset service...")
            _service_instance = FirestoreDatasetService()
        else:
            logger.info("ℹ️ Using fallback in-memory dataset service...")
            _service_instance = InMemoryDatasetService()
    return _service_instance
