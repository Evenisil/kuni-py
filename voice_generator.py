import os
import asyncio
import tempfile
import edge_tts
from pyrogram import Client, enums

async def generate_and_send_voice(bot_instance, chat_id: int, text: str, voice_name: str = "ru-RU-SvetlanaNeural") -> bool:
    """
    Generates a realistic neural voice note for Kuni and sends it via Telegram.
    """
    print(f"[VoiceGenerator] Recording voice note for chat {chat_id}: '{text[:40]}...'")
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        voice_path = tmp.name

    try:
        # Show RECORD_AUDIO chat action in Telegram
        if bot_instance.app and bot_instance.app.is_connected:
            try:
                await bot_instance.app.send_chat_action(chat_id, enums.ChatAction.RECORD_AUDIO)
            except Exception:
                pass

        communicate = edge_tts.Communicate(text, voice_name)
        await communicate.save(voice_path)

        if bot_instance.app and bot_instance.app.is_connected:
            await bot_instance.app.send_voice(chat_id, voice=voice_path, caption="")
            print(f"[VoiceGenerator] Voice message successfully sent to chat {chat_id}!")
            return True
    except Exception as e:
        print(f"[VoiceGenerator] Error generating/sending voice note: {e}")
    finally:
        if os.path.exists(voice_path):
            try:
                os.remove(voice_path)
            except Exception:
                pass
    return False
