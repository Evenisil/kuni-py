import os
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from llm_client import llm_client_instance

DEFAULT_WORKING_MEMORY = """# Kuni's Working Memory

## Active Tasks & Promises
- [ ] Chat naturally with users and Papik.
- [ ] Keep track of important ongoing conversations.

## Recent Context & Notes
- System started up on {date}.
- Emotional state: Curious, affectionate, and thoughtful.

*Last updated: {date}*
"""

class WorkingMemoryManager:
    def __init__(self, memory_path: str = "data/working_memory.md"):
        self.memory_path = Path(memory_path)
        self.ensure_file()

    def ensure_file(self):
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.memory_path.exists():
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            content = DEFAULT_WORKING_MEMORY.format(date=now_str)
            self.memory_path.write_text(content, encoding="utf-8")
            print(f"[WorkingMemory] Created default {self.memory_path}")

    def load(self) -> str:
        self.ensure_file()
        try:
            return self.memory_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"[WorkingMemory] Error reading memory file: {e}")
            return ""

    def save(self, content: str):
        self.ensure_file()
        try:
            self.memory_path.write_text(content, encoding="utf-8")
            print(f"[WorkingMemory] Updated {self.memory_path}")
        except Exception as e:
            print(f"[WorkingMemory] Error saving memory file: {e}")

    async def dump_context_and_update(self, chat_history: List[Dict[str, Any]]) -> str:
        """
        Takes active conversation history, prompts LLM to produce an updated working memory,
        saves it to working_memory.md, and returns the updated text.
        """
        current_memory = self.load()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        prompt = f"""You are updating Kuni's working memory (middle-term memory for 1-3 days).

Current Working Memory:
```markdown
{current_memory}
```

Recent Conversation History:
"""
        for msg in chat_history[-20:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prompt += f"{role}: {content}\n"

        prompt += f"""
Instructions:
1. Preserve all active, unfinished tasks, promises, and reminders from the current working memory.
2. Remove completed tasks and items older than 3 days.
3. Add new important details, promises, or ongoing topics from the recent conversation.
4. Keep emotional state and context fresh.
5. Format cleanly in Markdown with a 'Last updated: {now_str}' timestamp at the end.

Return ONLY the updated Markdown content for working_memory.md.
"""
        try:
            res = await llm_client_instance.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                function_label="working_memory_update"
            )
            updated_text = res.choices[0].message.content.strip()
            if updated_text:
                self.save(updated_text)
                return updated_text
        except Exception as e:
            print(f"[WorkingMemory] Failed to dump context and update working memory: {e}")

        return current_memory

working_memory_instance = WorkingMemoryManager()
