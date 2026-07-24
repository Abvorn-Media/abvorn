import json, logging, threading, time, sqlite3
from datetime import datetime
from collections import defaultdict
from contextlib import contextmanager

logger = logging.getLogger("abvorn.bus")

TOPIC_PATTERNS = {
    "content.researched": "research_complete",
    "content.drafted": "draft_complete",
    "content.published": "publish_complete",
    "analytics.updated": "analytics_refresh",
    "system.error": "error_occurred",
    "system.heartbeat": "agent_alive",
    "brain.refreshed": "brain_update",
    "agent.spawned": "new_agent",
}

class AgentBus:
    """SQLite-backed event bus for inter-agent communication."""

    def __init__(self, db_path):
        self._db_path = db_path
        self._local = threading.local()
        self._subscribers = defaultdict(list)
        self._running = False
        self._lock = threading.Lock()
        self._init_db()

    @contextmanager
    def _cursor(self):
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self._db_path))
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA busy_timeout=5000")
        yield self._local.conn.cursor()
        self._local.conn.commit()

    def _init_db(self):
        with self._cursor() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    processed INTEGER DEFAULT 0
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_events_topic ON events(topic)")

    def publish(self, topic: str, message: dict):
        """Publish an event to the bus. All subscribers to this topic receive it."""
        with self._cursor() as c:
            c.execute("INSERT INTO events (topic, message, created_at) VALUES (?, ?, ?)",
                      (topic, json.dumps(message), datetime.now().isoformat()))
        logger.debug(f"[BUS] Published: {topic}")
        with self._lock:
            for callback in self._subscribers.get(topic, []):
                try:
                    callback(message)
                except Exception as e:
                    logger.error(f"[BUS] Subscriber error on {topic}: {e}")

    def subscribe(self, topic: str, callback):
        """Register a callback for a topic. Callback receives the message dict."""
        with self._lock:
            self._subscribers[topic].append(callback)
        logger.debug(f"[BUS] Subscribed: {topic}")

    def unsubscribe(self, topic: str, callback):
        with self._lock:
            if callback in self._subscribers[topic]:
                self._subscribers[topic].remove(callback)

    def get_recent_events(self, topic: str = None, limit: int = 20) -> list:
        with self._cursor() as c:
            if topic:
                c.execute("SELECT * FROM events WHERE topic=? ORDER BY id DESC LIMIT ?", (topic, limit))
            else:
                c.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))
            return [{"id": r[0], "topic": r[1], "message": json.loads(r[2]), "created_at": r[3]} for r in c.fetchall()]

    def run_forever(self, poll_interval: float = 0.5):
        """Run the bus event loop (for future async agents to process persisted events)."""
        self._running = True
        last_id = 0
        while self._running:
            with self._cursor() as c:
                c.execute("SELECT * FROM events WHERE id > ? AND processed=0 ORDER BY id", (last_id,))
                for row in c.fetchall():
                    event = {"id": row[0], "topic": row[1], "message": json.loads(row[2]), "created_at": row[3]}
                    with self._lock:
                        for callback in self._subscribers.get(event["topic"], []):
                            try:
                                callback(event["message"])
                            except Exception as e:
                                logger.error(f"[BUS] Subscriber error on {event['topic']}: {e}")
                    c.execute("UPDATE events SET processed=1 WHERE id=?", (event["id"],))
                    last_id = event["id"]
            time.sleep(poll_interval)

    def stop(self):
        self._running = False