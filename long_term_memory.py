import os
import sqlite3
import json
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import numpy as np

DB_PATH = Path("data/long_term_memory.sqlite")

def simple_tokenize(text: str) -> List[str]:
    return re.findall(r'\w+', text.lower())

def text_to_vector(text: str, vocab: Dict[str, int]) -> np.ndarray:
    tokens = simple_tokenize(text)
    vec = np.zeros(len(vocab))
    for t in tokens:
        if t in vocab:
            vec[vocab[t]] += 1
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec

class LongTermMemoryManager:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.ensure_db()

    def ensure_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA cache_size=-64000;")
            # Lifelong facts and core knowledge
            conn.execute("""
                CREATE TABLE IF NOT EXISTS lifelong_facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject TEXT NOT NULL,
                    category TEXT NOT NULL,
                    fact TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    importance REAL DEFAULT 1.0
                )
            """)
            # People profiles and relationships
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT PRIMARY KEY,
                    username TEXT,
                    name TEXT,
                    relationship_status TEXT,
                    trust_level REAL DEFAULT 0.5,
                    notes TEXT,
                    last_seen TEXT
                )
            """)
            # Self identity history (names, bios, avatars generated)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS self_identity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    first_name TEXT NOT NULL,
                    bio TEXT,
                    avatar_url TEXT,
                    timestamp TEXT NOT NULL
                )
            """)
            conn.commit()

    def save_profile_identity(self, first_name: str, bio: str, avatar_url: str = "") -> int:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO self_identity (first_name, bio, avatar_url, timestamp) VALUES (?, ?, ?, ?)",
                (first_name, bio, avatar_url, now_str)
            )
            conn.commit()
            print(f"[LongTermMemory] Saved new profile identity: Name='{first_name}', Bio='{bio}'")
            return cursor.lastrowid

    def get_latest_profile_identity(self) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM self_identity ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            return dict(row) if row else None

    def add_fact(self, subject: str, category: str, fact: str, importance: float = 1.0) -> int:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO lifelong_facts (subject, category, fact, timestamp, importance) VALUES (?, ?, ?, ?, ?)",
                (subject, category, fact, now_str, importance)
            )
            conn.commit()
            print(f"[LongTermMemory] Added fact: [{category}] {subject} - {fact}")
            return cursor.lastrowid

    def update_user_profile(self, user_id: str, name: str, notes: str, relationship_status: str = "Friend", trust_level: float = 0.5, username: str = ""):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO user_profiles (user_id, username, name, relationship_status, trust_level, notes, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username=excluded.username,
                    name=excluded.name,
                    relationship_status=excluded.relationship_status,
                    trust_level=excluded.trust_level,
                    notes=user_profiles.notes || '\n' || excluded.notes,
                    last_seen=excluded.last_seen
            """, (str(user_id), username, name, relationship_status, trust_level, notes, now_str))
            conn.commit()
            print(f"[LongTermMemory] Updated user profile for {name} ({user_id})")

    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_profiles WHERE user_id = ?", (str(user_id),))
            row = cursor.fetchone()
            return dict(row) if row else None

    def search_memories(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM lifelong_facts ORDER BY id DESC")
            rows = cursor.fetchall()
            facts = [dict(r) for r in rows]

        if not facts:
            return []

        query_tokens = set(simple_tokenize(query))
        if not query_tokens:
            return facts[:limit]

        all_texts = [f"{f['subject']} {f['category']} {f['fact']}" for f in facts] + [query]
        vocab = {}
        for t in all_texts:
            for tok in simple_tokenize(t):
                if tok not in vocab:
                    vocab[tok] = len(vocab)

        q_vec = text_to_vector(query, vocab)
        scored = []
        for f in facts:
            f_text = f"{f['subject']} {f['category']} {f['fact']}"
            f_vec = text_to_vector(f_text, vocab)
            score = np.dot(q_vec, f_vec) * f.get("importance", 1.0)
            scored.append((score, f))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:limit] if item[0] > 0.05]

    def format_long_term_context(self, query: str = "", user_id: Optional[str] = None) -> str:
        lines = ["## Permanent Lifelong Memories:"]
        
        # User profile if available
        if user_id:
            profile = self.get_user_profile(user_id)
            if profile:
                lines.append(f"### Interlocutor Profile:")
                lines.append(f"- Name: {profile['name']} (@{profile['username'] or 'N/A'})")
                lines.append(f"- Relationship Status: {profile['relationship_status']} (Trust: {profile['trust_level']}/1.0)")
                lines.append(f"- Known Details:\n  {profile['notes']}")

        # Relevant facts
        facts = self.search_memories(query, limit=5)
        if facts:
            lines.append("### Key Permanent Facts & Opinions:")
            for f in facts:
                lines.append(f"- [{f['category']}] {f['subject']}: {f['fact']}")

        return "\n".join(lines) if len(lines) > 1 else ""

long_term_memory_instance = LongTermMemoryManager()
