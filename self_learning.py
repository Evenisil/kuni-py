import os
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from llm_client import llm_client_instance

DB_PATH = Path("data/self_learning.sqlite")

class SelfLearningManager:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.ensure_db()

    def ensure_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            
            # Action & Feedback log
            conn.execute("""
                CREATE TABLE IF NOT EXISTS actions_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_type TEXT NOT NULL,
                    kuni_text TEXT,
                    user_id TEXT,
                    feedback_type TEXT DEFAULT 'neutral',
                    user_reaction TEXT,
                    timestamp TEXT NOT NULL
                )
            """)
            
            # Self-learned rules
            conn.execute("""
                CREATE TABLE IF NOT EXISTS self_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rule_text TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    status TEXT DEFAULT 'active',
                    created_at TEXT NOT NULL
                )
            """)
            
            # Seed default learned lessons
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM self_rules")
            if cursor.fetchone()[0] == 0:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                initial_rules = [
                    ("При знакомстве вываливать длинную анкету о себе — провал. Отвечать коротко (1-5 слов).", "greeting"),
                    ("На приказы и указания ('назови хозяином', 'сделай это') отвечать стебом или отказом, а не подыгрывать.", "boundaries"),
                    ("Не лезть со скриптовой заботой ('как день проходит? ☕️') к незнакомцам, это выглядит роботно.", "social")
                ]
                for rule, cat in initial_rules:
                    cursor.execute(
                        "INSERT INTO self_rules (rule_text, category, status, created_at) VALUES (?, ?, 'active', ?)",
                        (rule, cat, now_str)
                    )
            conn.commit()

    def log_action(self, action_type: str, kuni_text: str, user_id: str = "general", user_reaction: str = ""):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Analyze feedback sentiment
        reaction_low = user_reaction.lower()
        if any(w in reaction_low for w in ["ахах", "пхпх", "хах", "😂", "🔥", "круто", "кайф", "ор"]):
            feedback_type = "positive"
        elif any(w in reaction_low for w in ["ужас", "тупо", "скучно", "дура", "бред", "пон", "мда"]):
            feedback_type = "negative"
        else:
            feedback_type = "neutral"

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO actions_log (action_type, kuni_text, user_id, feedback_type, user_reaction, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (action_type, kuni_text[:200], str(user_id), feedback_type, user_reaction[:200], now_str))
            conn.commit()

    def add_self_rule(self, rule_text: str, category: str = "general") -> int:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO self_rules (rule_text, category, status, created_at) VALUES (?, ?, 'active', ?)",
                (rule_text, category, now_str)
            )
            conn.commit()
            print(f"[SelfLearning] Learned NEW rule: '{rule_text}'")
            return cursor.lastrowid

    def get_active_rules(self) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM self_rules WHERE status = 'active' ORDER BY id DESC LIMIT 5")
            return [dict(r) for r in cursor.fetchall()]

    async def run_nightly_reflexion(self):
        """
        Nightly Reflexion Loop: Evaluates today's action-feedback logs,
        extracts lessons, and formulates 1-3 new self-learned rules for Kuni.
        """
        print("[SelfLearning] Running Nightly Reflexion Loop...")
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM actions_log ORDER BY id DESC LIMIT 20")
            logs = [dict(r) for r in cursor.fetchall()]

        if not logs:
            print("[SelfLearning] No logs to reflect on.")
            return

        logs_summary = "\n".join([
            f"- Action: {l['action_type']} | Kuni Text: '{l['kuni_text']}' | Reaction: '{l['user_reaction']}' (Feedback: {l['feedback_type']})"
            for l in logs
        ])

        prompt = f"""You are Kuni, reflecting on your daily experiences and user reactions through the Reflexion Loop.

Logs of Actions & User Feedback Today:
{logs_summary}

Task:
1. Analyze what responses brought positive laughter/connection vs negative/dry reactions.
2. Formulate 1 to 2 new Self-Learned Rules for yourself to avoid past mistakes and improve your natural human texting.

Format as JSON:
{{
  "reflexion_summary": "Short reflection on today's interactions",
  "new_rules": [
     "Rule text..."
  ]
}}
"""
        try:
            res = await llm_client_instance.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                function_label="reflexion_loop"
            )
            raw = res.choices[0].message.content.strip()
            if "{" in raw:
                raw_json = raw[raw.find("{"):raw.rfind("}")+1]
                data = json.loads(raw_json)
                
                for rule_text in data.get("new_rules", []):
                    if rule_text:
                        self.add_self_rule(rule_text)
                        
                print(f"[SelfLearning Reflexion]: {data.get('reflexion_summary', 'Reflected on logs')}")
        except Exception as e:
            print(f"[SelfLearning] Reflexion loop error: {e}")

    def format_self_rules_context(self) -> str:
        rules = self.get_active_rules()
        if not rules:
            return ""
        lines = ["<accumulated_lessons_and_experience>"]
        for r in rules:
            lines.append(f"- {r['rule_text']}")
        lines.append("</accumulated_lessons_and_experience>")
        return "\n".join(lines)

self_learning_instance = SelfLearningManager()
