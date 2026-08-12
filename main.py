import os
import sys
import asyncio
import signal
import threading
import uvicorn
from pathlib import Path

from config import config_instance
from character import character_instance
from metrics import start_metrics_server
from diary import diary_instance
from working_memory import working_memory_instance
from long_term_memory import long_term_memory_instance
from autonomy import autonomy_engine
from proxy_server import app as proxy_app
from telegram_client import kuni_telegram_bot

from self_learning import self_learning_instance

async def sleep_cycle_worker():
    """
    Background worker that runs memory sleep consolidation & nightly self-learning reflexion.
    """
    while True:
        try:
            sleep_enabled = config_instance.get("misc", "sleep_enabled", True)
            interval_hours = config_instance.get("misc", "sleep_interval_hours", 24)
            if sleep_enabled:
                print("[Main] Running scheduled sleep memory consolidation & reflexion loop...")
                await diary_instance.run_sleep_consolidation()
                await self_learning_instance.run_nightly_reflexion()
            await asyncio.sleep(interval_hours * 3600)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Main Sleep Worker] Error: {e}")
            await asyncio.sleep(3600)

def run_proxy_in_thread(host: str, port: int):
    uvicorn.run(proxy_app, host=host, port=port, log_level="warning")

async def main():
    print("=" * 60)
    print("      KUNI - Independent LLM Character AI (Python Edition)")
    print("=" * 60)
    
    # 1. Start Prometheus Exporter on port 9464
    start_metrics_server()

    # 2. Start Proxy Server on port 10434 in a separate thread if proxy_enabled
    proxy_enabled = config_instance.get("general", "proxy_enabled", True)
    proxy_port = config_instance.get("general", "proxy_port", 10434)
    if proxy_enabled:
        proxy_thread = threading.Thread(
            target=run_proxy_in_thread, 
            args=("0.0.0.0", proxy_port), 
            daemon=True
        )
        proxy_thread.start()
        print(f"[Main] Proxy Server running at http://localhost:{proxy_port}/v1")

    # 3. Start Nightly Sleep Consolidation worker & Autonomous initiative loop
    sleep_task = asyncio.create_task(sleep_cycle_worker())
    autonomy_task = asyncio.create_task(autonomy_engine.start_loop())

    # 4. Start Telegram Userbot (if enabled)
    telegram_enabled = config_instance.get("general", "telegram_enabled", True)
    if telegram_enabled:
        await kuni_telegram_bot.start()
    else:
        print("[Main] Standalone mode active (telegram_enabled = false). Press Ctrl+C to stop.")

    # 5. Keep main event loop running
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n[Main] Shutting down Kuni...")
    finally:
        sleep_task.cancel()
        autonomy_task.cancel()
        if telegram_enabled:
            await kuni_telegram_bot.stop()
        print("[Main] Goodbye!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
