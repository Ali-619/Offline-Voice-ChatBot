from typing import List, Dict
from uuid import uuid4
from datetime import datetime

class HistoryManager:
    def __init__(self):
        self.sessions: Dict[str, List[Dict]] = {}

    def new_session(self) -> str:
        sid = str(uuid4())
        self.sessions[sid] = []
        return sid

    def append(self, session_id: str, role: str, text: str):
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        self.sessions[session_id].append({
            "role": role,
            "text": text,
            "ts": datetime.utcnow().isoformat(),
        })

    def get(self, session_id: str):
        return self.sessions.get(session_id, [])

    def clear(self, session_id: str):
        self.sessions[session_id] = []

# singleton
history = HistoryManager()
