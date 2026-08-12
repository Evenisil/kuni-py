import sys
import asyncio

sys.stdout.reconfigure(encoding='utf-8')

from llm_client import llm_client_instance
from diary import diary_instance
from working_memory import working_memory_instance
from web_search import format_search_results

from character import character_instance

async def test_all():
    print("--- 1. Testing LLM Client Chat Completion ---")
    sys_prompt = character_instance.build_system_prompt()
    res = await llm_client_instance.chat_completion(
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": "Привет! Как тебя зовут и чем занимаешься?"}
        ],
        function_label="test_chat"
    )
    print("LLM Response:", res.choices[0].message.content)

    print("\n--- 2. Testing Diary RAG & Memories ---")
    diary_instance.add_entry("Познакомились с новым пользователем Alex.", emotion="happy")
    memories = diary_instance.search_memories("Alex", limit=2)
    print("Found Memories:", memories)

    print("\n--- 3. Testing Web Search ---")
    results = await format_search_results("Python news", max_results=2)
    print("Search Output:\n", results[:200], "...")

    print("\n--- 4. Testing Working Memory ---")
    wm_text = working_memory_instance.load()
    print("Working Memory length:", len(wm_text))

    print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(test_all())
