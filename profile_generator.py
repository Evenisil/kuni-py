import os
import asyncio
import tempfile
import base64
import httpx
from pathlib import Path
from typing import Optional, Tuple
from llm_client import llm_client_instance
from long_term_memory import long_term_memory_instance
from diary import diary_instance
from config import config_instance

async def generate_and_apply_profile(bot_instance) -> bool:
    """
    Generates a new avatar image, name, and bio for Kuni,
    updates Telegram account profile via Pyrogram, and saves to database.
    """
    print("[ProfileGenerator] Generating new human profile identity (Avatar, Name, Bio)...")
    
    # 1. Ask LLM for a fresh name and bio
    prompt = """You are Kuni, creating a new fresh aesthetic identity for your Telegram profile.
Invent:
1. First Name (e.g., Kuni / Куни / Kuni ✨)
2. Telegram Bio (short, under 70 characters, stylish, expressive)

Format as:
NAME: [First Name]
BIO: [Short Bio]
AVATAR_PROMPT: [Short Stable Diffusion prompt for your new avatar image]
"""

    try:
        res = await llm_client_instance.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            function_label="generate_profile"
        )
        text = res.choices[0].message.content.strip()

        first_name = "Kuni"
        bio = "living AI girl 🌸"
        avatar_prompt = "masterpiece, best quality, 1girl, kuni, cute anime girl, beautiful expressive eyes, stylish profile picture"

        for line in text.split("\n"):
            if line.startswith("NAME:"):
                first_name = line.replace("NAME:", "").strip()
            elif line.startswith("BIO:"):
                bio = line.replace("BIO:", "").strip()
            elif line.startswith("AVATAR_PROMPT:"):
                avatar_prompt = line.replace("AVATAR_PROMPT:", "").strip()

        print(f"[ProfileGenerator] Generated Name: '{first_name}', Bio: '{bio}'")

        # 2. Generate avatar image using configured image model
        image_url_or_b64 = None
        try:
            image_url_or_b64 = await llm_client_instance.generate_image(avatar_prompt)
        except Exception as img_err:
            print(f"[ProfileGenerator] Image generation error: {img_err}")

        avatar_file_path = None

        if image_url_or_b64:
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                avatar_file_path = tmp.name

            if image_url_or_b64.startswith("http"):
                try:
                    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                        img_resp = await client.get(image_url_or_b64)
                        if img_resp.status_code == 200:
                            with open(avatar_file_path, "wb") as f:
                                f.write(img_resp.content)
                            print(f"[ProfileGenerator] Downloaded avatar image ({len(img_resp.content)} bytes)")
                        else:
                            avatar_file_path = None
                except Exception as dl_err:
                    print(f"[ProfileGenerator] Error downloading avatar image: {dl_err}")
                    avatar_file_path = None
            else:
                try:
                    with open(avatar_file_path, "wb") as f:
                        f.write(base64.b64decode(image_url_or_b64))
                except Exception:
                    avatar_file_path = None

        # 3. Update Telegram profile via Pyrogram
        if bot_instance.app and bot_instance.app.is_connected:
            try:
                await bot_instance.app.update_profile(first_name=first_name, bio=bio)
                print(f"[ProfileGenerator] Updated Telegram profile name & bio!")
                
                if avatar_file_path and os.path.exists(avatar_file_path):
                    # Clean old profile photos first so Telegram doesn't accumulate dozens of old avatars
                    try:
                        old_photos = [p async for p in bot_instance.app.get_chat_photos("me")]
                        if old_photos:
                            await bot_instance.app.delete_profile_photos([p.file_id for p in old_photos])
                            print(f"[ProfileGenerator] Cleaned {len(old_photos)} old avatar photo(s) from Telegram.")
                    except Exception as del_err:
                        print(f"[ProfileGenerator] Notice cleaning old photos: {del_err}")

                    await bot_instance.app.set_profile_photo(photo=avatar_file_path)
                    print(f"[ProfileGenerator] Updated Telegram profile avatar photo!")
            except Exception as e:
                print(f"[ProfileGenerator] Telegram API profile update error: {e}")

        # 4. Save to Long Term Memory DB & Diary
        long_term_memory_instance.save_profile_identity(
            first_name=first_name,
            bio=bio,
            avatar_url=image_url_or_b64 or ""
        )
        diary_instance.add_entry(
            text=f"Updated my profile identity! Name: '{first_name}', Bio: '{bio}'",
            emotion="excited"
        )

        # Cleanup temp file
        if avatar_file_path and os.path.exists(avatar_file_path):
            try:
                os.remove(avatar_file_path)
            except Exception:
                pass

        return True
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[ProfileGenerator] Failed to generate profile identity: {e}")
        return False
