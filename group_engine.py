import time
import json
import random
from typing import Dict, List, Any, Tuple, Optional
from llm_client import llm_client_instance
from config import config_instance

class GroupChatEngine:
    def __init__(self):
        # Activity counter: chat_id -> list of message timestamps sent by Kuni
        self.sent_timestamps: Dict[int, List[float]] = {}
        self.cooldown_until: Dict[int, float] = {}
        self.last_group_activity: Dict[int, float] = {}

    def is_in_cooldown(self, chat_id: int) -> bool:
        now = time.time()
        if chat_id in self.cooldown_until and now < self.cooldown_until[chat_id]:
            return True
        return False

    def record_kuni_group_message(self, chat_id: int):
        now = time.time()
        self.last_group_activity[chat_id] = now
        if chat_id not in self.sent_timestamps:
            self.sent_timestamps[chat_id] = []
        
        # Clean timestamps older than 5 mins (300s)
        self.sent_timestamps[chat_id] = [t for t in self.sent_timestamps[chat_id] if now - t < 300]
        self.sent_timestamps[chat_id].append(now)

        # Cool-down check: If 3+ messages sent in last 5 minutes, force 15-minute listener mode
        if len(self.sent_timestamps[chat_id]) >= 3:
            self.cooldown_until[chat_id] = now + 900  # 15 minutes cooldown
            print(f"[GroupEngine] Chat {chat_id} triggered Cool-down (sent 3 msgs in 5m). Listener mode for 15 mins.")

    async def evaluate_message_engagement(
        self,
        chat_id: int,
        combined_text: str,
        is_direct_mention: bool,
        is_reply_to_kuni: bool,
        recent_messages: List[Dict[str, Any]]
    ) -> Tuple[str, Optional[str]]:
        """
        Determines group chat action: 'reply', 'send_text', 'reaction', 'ignore', or 'wait_and_see'.
        Returns (action_type, emoji_if_reaction)
        """
        self.last_group_activity[chat_id] = time.time()

        # 1. Direct Mention or Reply -> 100% Priority Reply!
        if is_direct_mention or is_reply_to_kuni:
            return ("reply", None)

        # 2. Cool-down Check -> Forced listener mode unless directly addressed
        if self.is_in_cooldown(chat_id):
            return ("ignore", None)

        # 3. Random message between participants -> 5-15% evaluation or Engagement Score
        # Fast keyword check for memes/media/funny stuff -> 70% chance to put a reaction emoji
        lowered = combined_text.lower()

        # Random chance to put an emoji reaction on memes or funny lines without sending text
        if any(kw in lowered for kw in ["лол", "мем", "ахаха", "ппц", "ор", "треш", "согласен"]):
            if random.random() < 0.6:
                emoji = random.choice(["🔥", "💀", "😂", "🗿", "👍"])
                return ("reaction", emoji)

        # 4. LLM Engagement Score check for unmentioned group conversations
        history_formatted = "\n".join([f"- {m.get('role', 'user')}: {m.get('content', '')}" for m in recent_messages[-5:]])
        
        prompt = f"""You are Kuni, participating in a Telegram group chat.
Recent Group Chat Messages:
{history_formatted}

Current Message: "{combined_text}"

Evaluate if Kuni should participate.
Available actions:
- "ignore": Say nothing, stay silent.
- "reaction": Put a single emoji reaction (e.g. 🔥, 💀, 😂, 🗿) without text.
- "reply": Reply with a short comment because the topic is IT/memes/coding or interesting.

Format as JSON:
{{"action": "ignore" | "reaction" | "reply", "emoji": "💀" or null, "reason": "short explanation"}}
"""
        try:
            res = await llm_client_instance.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                function_label="group_engagement"
            )
            raw = res.choices[0].message.content.strip()
            if "{" in raw:
                raw_json = raw[raw.find("{"):raw.rfind("}")+1]
                data = json.loads(raw_json)
                action = data.get("action", "ignore")
                emoji = data.get("emoji")
                return (action, emoji)
        except Exception as e:
            print(f"[GroupEngine] Engagement evaluation error: {e}")

        # Default to silent ignore (100% realistic group silence)
        return ("ignore", None)

group_chat_engine = GroupChatEngine()
