import os
import sqlite3
import json
import random
import time
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import numpy as np
from llm_client import llm_client_instance

DB_PATH = Path("data/diary.sqlite")

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

class DiaryManager:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.ensure_db()

    def ensure_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA cache_size=-64000;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS diary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    tags TEXT,
                    emotion TEXT,
                    timestamp TEXT NOT NULL,
                    consolidated INTEGER DEFAULT 0
                )
            """)
            conn.commit()

    def add_entry(self, text: str, emotion: str = "", tags: str = "") -> int:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO diary (text, tags, emotion, timestamp) VALUES (?, ?, ?, ?)",
                (text, tags, emotion, now_str)
            )
            conn.commit()
            print(f"[Diary] Added new entry #{cursor.lastrowid}: '{text[:50]}...'")
            return cursor.lastrowid

    def get_all_entries(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM diary ORDER BY id DESC")
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def search_memories(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        entries = self.get_all_entries()
        if not entries:
            return []

        query_tokens = set(simple_tokenize(query))
        if not query_tokens:
            return entries[:limit]

        # Build vocabulary from entries + query
        all_texts = [e["text"] for e in entries] + [query]
        vocab = {}
        for t in all_texts:
            for tok in simple_tokenize(t):
                if tok not in vocab:
                    vocab[tok] = len(vocab)

        q_vec = text_to_vector(query, vocab)
        
        scored = []
        for e in entries:
            e_vec = text_to_vector(e["text"], vocab)
            score = np.dot(q_vec, e_vec)
            # Bonus score for matching emotion/tags
            if e.get("emotion") and e["emotion"].lower() in query.lower():
                score += 0.2
            scored.append((score, e))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [item[1] for item in scored[:limit] if item[0] > 0.05]
        # If no similarity threshold met, return recent entries
        if not results and entries:
            results = entries[:limit]
        return results

    def format_thoughts(self, memories: List[Dict[str, Any]]) -> str:
        if not memories:
            return ""
        lines = []
        for m in memories:
            emotion_str = f" (Feeling: {m['emotion']})" if m.get("emotion") else ""
            lines.append(f"- [{m['timestamp']}] {m['text']}{emotion_str}")
        return "\n".join(lines)

    async def run_sleep_consolidation(self):
        """
        Mimics human sleep: reorganizes diary memory, groups related items,
        compresses/rewrites redundant memories via LLM, and replaces old fragments.
        """
        entries = self.get_all_entries()
        if len(entries) < 3:
            print("[Diary Sleep] Not enough entries to consolidate.")
            return

        print(f"[Diary Sleep] Starting memory consolidation on {len(entries)} diary entries...")
        
        # Pick sample chunk (recent entries + random older entries)
        recent = entries[:5]
        older = entries[5:]
        sample = recent + (random.sample(older, min(len(older), 5)) if older else [])

        formatted_memories = "\n".join([f"ID #{e['id']} [{e['timestamp']}]: {e['text']}" for e in sample])

        prompt = f"""You are processing Kuni's memory during her nightly sleep cycle.

Below are diary entries to consolidate and clean up:
{formatted_memories}

Instructions:
1. Identify duplicate, weak, or redundant memory fragments.
2. Merge related memories into clear, emotional, and factual summaries.
3. Keep important events, relationships, and feelings intact.
4. Output 1 to 3 consolidated diary entries in markdown list format:
   - Summary memory text...
"""

        try:
            res = await llm_client_instance.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                function_label="sleep_consolidation"
            )
            consolidated_text = res.choices[0].message.content.strip()
            if consolidated_text:
                # Delete processed sample IDs and insert consolidated entry
                sample_ids = [e["id"] for e in sample]
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute(f"DELETE FROM diary WHERE id IN ({','.join(['?']*len(sample_ids))})", sample_ids)
                    cursor.execute(
                        "INSERT INTO diary (text, emotion, timestamp, consolidated) VALUES (?, ?, ?, 1)",
                        (f"[Consolidated Memory] {consolidated_text}", "Reflective", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    )
                    conn.commit()
                print("[Diary Sleep] Consolidation completed successfully.")
        except Exception as e:
            print(f"[Diary Sleep] Error during sleep consolidation: {e}")

diary_instance = DiaryManager()
