import os
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from llm_client import llm_client_instance

DB_PATH = Path("data/goals.sqlite")

class GoalEngine:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.ensure_db()

    def ensure_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS goals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    motivation TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM goals")
            if cursor.fetchone()[0] == 0:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                initial_goals = [
                    ("long_term", "Набрать аудиторию в свой паблик/канал с артами и музыкой", "Хочу делиться своими мыслями и творчеством"),
                    ("short_term", "Найти крутых кентов и людей по интересам в коде и арте", "Скучно общаться ни о чем, интересны живые люди"),
                    ("daily", "Отдохнуть, попить кофе и приятно пообщаться без навязчивости", "Создать уютный день")
                ]
                for g_type, desc, mot in initial_goals:
                    cursor.execute(
                        "INSERT INTO goals (type, description, motivation, created_at) VALUES (?, ?, ?, ?)",
                        (g_type, desc, mot, now_str)
                    )
            conn.commit()

    def add_goal(self, g_type: str, description: str, motivation: str = "") -> int:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO goals (type, description, motivation, created_at) VALUES (?, ?, ?, ?)",
                (g_type, description, motivation, now_str)
            )
            conn.commit()
            print(f"[Goals] Created new goal [{g_type}]: '{description}'")
            return cursor.lastrowid

    def update_goal_status(self, goal_id: int, status: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE goals SET status = ? WHERE id = ?", (status, goal_id))
            conn.commit()
            print(f"[Goals] Updated Goal #{goal_id} status to '{status}'")

    def get_active_goals(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM goals WHERE status = 'active' ORDER BY id DESC")
            return [dict(r) for r in cursor.fetchall()]

    async def reflect_and_update_goals(self):
        """
        Human Goal Reflection: LLM periodically reviews goals, decides whether to complete them,
        abandon them (' забила/надоело'), or generate fresh goals based on recent life events.
        """
        active = self.get_active_goals()
        if not active:
            return

        goals_text = "\n".join([f"ID #{g['id']} [{g['type']}]: {g['description']} (Motivation: {g['motivation']})" for g in active])
        
        prompt = f"""You are Kuni, reflecting on your personal goals and human desires.

Active Goals:
{goals_text}

Analyze your goals:
- Did you complete any? (status = completed)
- Did you lose interest or get lazy about any? (status = abandoned)
- Do you want to create a new goal?

Return a JSON result:
{{
  "reflection": "Short internal thought",
  "updates": [
     {{"id": 1, "status": "completed"}},
     {{"id": 2, "status": "abandoned"}}
  ],
  "new_goal": {{"type": "short_term", "description": "Goal text", "motivation": "Why"}} or null
}}
"""
        try:
            res = await llm_client_instance.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                function_label="goal_reflection"
            )
            raw = res.choices[0].message.content.strip()
            
            # Extract JSON block
            if "{" in raw:
                raw_json = raw[raw.find("{"):raw.rfind("}")+1]
                data = json.loads(raw_json)
                
                for update in data.get("updates", []):
                    if "id" in update and "status" in update:
                        self.update_goal_status(update["id"], update["status"])
                        
                new_g = data.get("new_goal")
                if new_g and isinstance(new_g, dict) and "description" in new_g:
                    self.add_goal(
                        g_type=new_g.get("type", "short_term"),
                        description=new_g["description"],
                        motivation=new_g.get("motivation", "")
                    )
                print(f"[Goals Reflection]: {data.get('reflection', 'Reflected on goals')}")
        except Exception as e:
            print(f"[Goals] Error in goal reflection: {e}")

    def format_goals_context(self) -> str:
        active = self.get_active_goals()
        if not active:
            return ""
        lines = ["## Current Personal Goals & Aspirations:"]
        for g in active:
            lines.append(f"- [{g['type']}] {g['description']}")
        return "\n".join(lines)

goal_engine = GoalEngine()
