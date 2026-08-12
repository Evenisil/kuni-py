import os
import sqlite3
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple

DB_PATH = Path("data/emotions.sqlite")

class EmotionEngine:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.ensure_db()

    def ensure_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            
            # Global mood table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS global_mood (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    current_emotion TEXT NOT NULL,
                    intensity INTEGER NOT NULL,
                    trigger_reason TEXT,
                    timestamp TEXT NOT NULL
                )
            """)
            
            # User affinity table (-100 to +100) & Emotional Debt
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_affinity (
                    user_id TEXT PRIMARY KEY,
                    affinity INTEGER DEFAULT 0,
                    respect_level INTEGER DEFAULT 50,
                    dry_streak INTEGER DEFAULT 0,
                    emotional_debt INTEGER DEFAULT 0,
                    notes TEXT,
                    last_updated TEXT
                )
            """)
            
            # Biorhythms state
            conn.execute("""
                CREATE TABLE IF NOT EXISTS biorhythms (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    energy_level INTEGER DEFAULT 80,
                    fatigue INTEGER DEFAULT 20,
                    social_battery INTEGER DEFAULT 90,
                    brain_fog INTEGER DEFAULT 10
                )
            """)
            
            # Seed initial mood and biorhythms if empty
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM global_mood")
            if cursor.fetchone()[0] == 0:
                now_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                cursor.execute(
                    "INSERT INTO global_mood (current_emotion, intensity, trigger_reason, timestamp) VALUES (?, ?, ?, ?)",
                    ("neutral_cozy", 5, "Just woke up and relaxed", now_str)
                )
            
            cursor.execute("SELECT COUNT(*) FROM biorhythms")
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    "INSERT INTO biorhythms (id, energy_level, fatigue, social_battery, brain_fog) VALUES (1, 80, 20, 90, 10)"
                )
            conn.commit()

    def set_mood(self, emotion: str, intensity: int, trigger_reason: str):
        now_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        intensity = max(1, min(10, intensity))
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO global_mood (current_emotion, intensity, trigger_reason, timestamp) VALUES (?, ?, ?, ?)",
                (emotion, intensity, trigger_reason, now_str)
            )
            conn.commit()
            print(f"[Emotions] New Global Mood: '{emotion}' (Intensity: {intensity}/10) - Reason: {trigger_reason}")

    def get_global_mood(self) -> Dict[str, Any]:
        """
        Calculates current global mood with Emotional Decay (decaying intensity over time).
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM global_mood ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            if not row:
                return {"emotion": "neutral", "intensity": 3, "trigger_reason": "Calm", "minutes_ago": 0}
            
            data = dict(row)
            try:
                mood_time = datetime.strptime(data["timestamp"], "%Y-%m-%dT%H:%M:%S")
            except Exception:
                mood_time = datetime.now()

            minutes_passed = int((datetime.now() - mood_time).total_seconds() / 60)
            
            # Emotional Decay: Every 10 minutes, intensity drops by 2 points toward neutral (min 2)
            decay_amount = (minutes_passed // 10) * 2
            decayed_intensity = max(2, data["intensity"] - decay_amount)
            
            emotion = data["current_emotion"]
            if decayed_intensity <= 2 and emotion not in ["neutral", "cozy"]:
                emotion = "calm_neutral"
                trigger_reason = "Fully cooled down"
            else:
                trigger_reason = data["trigger_reason"]

            return {
                "emotion": emotion,
                "intensity": decayed_intensity,
                "raw_intensity": data["intensity"],
                "trigger_reason": trigger_reason,
                "minutes_passed": minutes_passed
            }

    def record_user_message_style(self, user_id: str, text: str):
        """
        Tracks user text style to accumulate Emotional Debt if user is dry (3+ dry msgs in a row).
        """
        words = text.lower().strip().split()
        is_dry = len(words) <= 2 or any(w in ["пон", "ок", "ясно", "хз", "ага", "мда", "да", "нет"] for w in words)
        
        now_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT dry_streak, emotional_debt FROM user_affinity WHERE user_id = ?", (str(user_id),))
            row = cursor.fetchone()
            if row:
                current_streak = row[0] or 0
                current_debt = row[1] or 0
                if is_dry:
                    new_streak = current_streak + 1
                    new_debt = current_debt + (10 if new_streak >= 3 else 0)
                else:
                    new_streak = 0
                    new_debt = max(0, current_debt - 15)
                cursor.execute("""
                    UPDATE user_affinity SET dry_streak = ?, emotional_debt = ?, last_updated = ? WHERE user_id = ?
                """, (new_streak, new_debt, now_str, str(user_id)))
            else:
                new_streak = 1 if is_dry else 0
                cursor.execute("""
                    INSERT INTO user_affinity (user_id, affinity, respect_level, dry_streak, emotional_debt, notes, last_updated)
                    VALUES (?, 0, 50, ?, 0, '', ?)
                """, (str(user_id), new_streak, now_str))
            conn.commit()

    def update_user_affinity(self, user_id: str, delta_affinity: int = 0, delta_respect: int = 0, note: str = ""):
        now_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT affinity, respect_level FROM user_affinity WHERE user_id = ?", (str(user_id),))
            row = cursor.fetchone()
            if row:
                new_aff = max(-100, min(100, row[0] + delta_affinity))
                new_resp = max(0, min(100, row[1] + delta_respect))
                cursor.execute("""
                    UPDATE user_affinity SET affinity = ?, respect_level = ?, notes = notes || '\n' || ?, last_updated = ?
                    WHERE user_id = ?
                """, (new_aff, new_resp, note, now_str, str(user_id)))
            else:
                new_aff = max(-100, min(100, delta_affinity))
                new_resp = max(0, min(100, 50 + delta_respect))
                cursor.execute("""
                    INSERT INTO user_affinity (user_id, affinity, respect_level, notes, last_updated)
                    VALUES (?, ?, ?, ?, ?)
                """, (str(user_id), new_aff, new_resp, note, now_str))
            conn.commit()

    def get_user_affinity(self, user_id: str) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_affinity WHERE user_id = ?", (str(user_id),))
            row = cursor.fetchone()
            if not row:
                return {"affinity": 0, "respect_level": 50, "relationship_type": "Stranger"}
            
            aff = row["affinity"]
            if aff >= 70:
                rel_type = "Close Friend / Loved One"
            elif aff >= 30:
                rel_type = "Friend / Good Acquaintance"
            elif aff >= -10:
                rel_type = "Stranger / Casual Interlocutor"
            else:
                rel_type = "Adversary / Toxic User (Disliked)"

            return {
                "affinity": aff,
                "respect_level": row["respect_level"],
                "relationship_type": rel_type,
                "notes": row["notes"]
            }

    def format_emotional_context(self, user_id: Optional[str] = None) -> str:
        mood = self.get_global_mood()
        lines = [
            "## Global Mood & Emotional State:",
            f"- Current Emotion: {mood['emotion']} (Intensity: {mood['intensity']}/10)",
            f"- Cause: {mood['trigger_reason']} ({mood['minutes_passed']} mins ago)"
        ]
        
        if user_id:
            aff = self.get_user_affinity(user_id)
            lines.append(f"### Interlocutor Relationship (Affinity: {aff['affinity']}/100):")
            lines.append(f"- Social Status: {aff['relationship_type']}")
            lines.append(f"- Respect Level: {aff['respect_level']}/100")

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT dry_streak, emotional_debt FROM user_affinity WHERE user_id = ?", (str(user_id),))
                r = cursor.fetchone()
                if r and (r[0] >= 3 or r[1] >= 20):
                    lines.append(f"[EMOTIONAL RESENTMENT NOTICE]: User has been dry {r[0]} times in a row. You feel annoyed/cold. Stop teasing, reply dryly yourself ('пон', 'мда'), or call them out ('че смурной такой?') or give space ('понял не задолблю').")
            
        return "\n".join(lines)

emotion_engine = EmotionEngine()
