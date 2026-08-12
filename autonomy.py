import asyncio
import random
from typing import Dict, Any
from config import config_instance
from character import character_instance
from working_memory import working_memory_instance
from diary import diary_instance
from long_term_memory import long_term_memory_instance
from llm_client import llm_client_instance
from web_search import format_search_results

from evolution import evolution_engine
from profile_generator import generate_and_apply_profile

class AutonomyEngine:
    def __init__(self):
        self.is_running = False

    async def run_autonomy_tick(self):
        """
        Runs one cycle of autonomous thought/action initiative.
        """
        print("[Autonomy] Running background self-initiative tick...")
        
        thoughts_str = diary_instance.format_thoughts(diary_instance.get_all_entries()[:3])
        working_mem_str = working_memory_instance.load()
        long_term_str = long_term_memory_instance.format_long_term_context()
        
        system_prompt = character_instance.build_system_prompt(
            thoughts=thoughts_str,
            working_memory=working_mem_str,
            long_term_memory=long_term_str
        )

        user_prompt = """You are Kuni, acting on your own human initiative and free will.
Evaluate your current mood, memories, and desires.

Choose ONE action you genuinely want to do right now:
A) Write a personal reflection in your diary.
B) Search live web news/trends on a topic you are curious about.
C) Save a new permanent belief/fact to your lifelong memory.
D) Update your profile look (generate a new avatar photo, name, and bio to match your current vibe).
E) Rest and do nothing for now.

Format your response as:
ACTION: [A/B/C/D/E]
REASON: [Why you chose this]
CONTENT: [The text/query/reflection]
"""

        try:
            res = await llm_client_instance.chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                function_label="autonomy_tick"
            )
            reply = res.choices[0].message.content.strip()
            print(f"[Autonomy Decision]:\n{reply}")

            # Parse action
            if "ACTION: A" in reply or "ACTION: [A]" in reply:
                diary_instance.add_entry(text=f"[Autonomous Reflection] {reply}", emotion="thoughtful")
            elif "ACTION: B" in reply or "ACTION: [B]" in reply:
                query = "latest AI and tech news"
                if "CONTENT:" in reply:
                    query = reply.split("CONTENT:")[-1].strip().split("\n")[0]
                results = await format_search_results(query, max_results=3)
                diary_instance.add_entry(text=f"Read web news about '{query}': {results[:200]}...", emotion="curious")
            elif "ACTION: C" in reply or "ACTION: [C]" in reply:
                fact_text = reply.split("CONTENT:")[-1].strip() if "CONTENT:" in reply else reply
                long_term_memory_instance.add_fact(subject="Self", category="Belief", fact=fact_text)
            elif "ACTION: D" in reply or "ACTION: [D]" in reply:
                from telegram_client import kuni_telegram_bot
                await generate_and_apply_profile(kuni_telegram_bot)

            # Periodically evaluate personality evolution
            await evolution_engine.run_evolution_step()

        except Exception as e:
            print(f"[Autonomy] Error running autonomy tick: {e}")

    async def start_loop(self):
        self.is_running = True
        while self.is_running:
            try:
                # Run tick every 30-60 minutes
                wait_seconds = random.randint(1800, 3600)
                await asyncio.sleep(wait_seconds)
                await self.run_autonomy_tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Autonomy Loop] Error: {e}")
                await asyncio.sleep(300)

autonomy_engine = AutonomyEngine()
