import asyncio
import json
from pathlib import Path
from datetime import datetime
from llm_client import llm_client_instance
from character import character_instance
from diary import diary_instance
from long_term_memory import long_term_memory_instance

class EvolutionEngine:
    def __init__(self):
        pass

    async def run_evolution_step(self):
        """
        Periodically evolves Kuni's personality, interests, and slang based on real chat experiences.
        """
        print("[Evolution] Evaluating Kuni's personal growth & evolution...")
        recent_entries = diary_instance.get_all_entries()[:10]
        if not recent_entries:
            return

        diary_text = "\n".join([f"- [{e['timestamp']}]: {e['text']}" for e in recent_entries])

        prompt = f"""You are Kuni, reflecting on your recent experiences and personal growth over time.

Recent Life Events & Conversations:
{diary_text}

Did you pick up a new slang expression, watch a new movie/anime, or develop a new opinion or habit recently?
If yes, write a brief addition (1-2 sentences) to update your personality file.

Format as JSON:
{{
  "evolution_occurred": true or false,
  "new_interest_or_slang": "New slang/interest picked up",
  "reflection": "Short thought on why your taste/style evolved"
}}
"""
        try:
            res = await llm_client_instance.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                function_label="personality_evolution"
            )
            raw = res.choices[0].message.content.strip()
            if "{" in raw:
                raw_json = raw[raw.find("{"):raw.rfind("}")+1]
                data = json.loads(raw_json)
                
                if data.get("evolution_occurred") and data.get("new_interest_or_slang"):
                    item = data["new_interest_or_slang"]
                    reflection = data.get("reflection", "Personal evolution")
                    
                    # Save to long term memory
                    long_term_memory_instance.add_fact(
                        subject="Self Evolution",
                        category="TasteGrowth",
                        fact=item
                    )
                    diary_instance.add_entry(
                        text=f"[Personality Growth] {reflection} (New interest/style: {item})",
                        emotion="thoughtful"
                    )
                    print(f"[Evolution] Kuni evolved! New style/interest: {item}")
        except Exception as e:
            print(f"[Evolution] Evolution step error: {e}")

evolution_engine = EvolutionEngine()
