import os
import json
import base64
import asyncio
import tempfile
import random
from pathlib import Path
from typing import Dict, List, Any, Tuple
import io
from PIL import Image
from pyrogram import Client, filters, enums
from pyrogram.types import Message

from config import config_instance
from character import character_instance
from working_memory import working_memory_instance
from diary import diary_instance
from long_term_memory import long_term_memory_instance
from emotions import emotion_engine
from goals import goal_engine
from self_learning import self_learning_instance
from llm_client import llm_client_instance
from web_search import format_search_results
from metrics import log_event

DATA_DIR = Path("data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

class KuniTelegramBot:
    def __init__(self):
        self.app = None
        self.chat_histories: Dict[int, List[Dict[str, Any]]] = {}
        self.message_buffers: Dict[int, List[Tuple[Message, Client]]] = {}
        self.debounce_tasks: Dict[int, asyncio.Task] = {}

    def init_client(self) -> bool:
        api_id = config_instance.get("general", "telegram_api_id", 0)
        api_hash = config_instance.get("general", "telegram_api_hash", "")
        
        if not api_id or not api_hash:
            print("[Telegram] telegram_api_id or telegram_api_hash not configured in config.toml!")
            print("[Telegram] Set telegram_enabled = false if running proxy standalone without Telegram.")
            return False

        self.app = Client(
            "kuni_session",
            api_id=api_id,
            api_hash=api_hash,
            workdir="data"
        )
        self.setup_handlers()
        return True

    def setup_handlers(self):
        @self.app.on_message(filters.private)
        async def handle_private_message(client: Client, message: Message):
            if not message.outgoing:
                await self.enqueue_message(client, message)

        @self.app.on_message(filters.group)
        async def handle_group_message(client: Client, message: Message):
            if not message.outgoing:
                await self.enqueue_message(client, message)

    async def send_sticker_tool(self, emotion_or_emoji: str) -> str:
        print(f"[Telegram] Expressed sticker body language for '{emotion_or_emoji}'")
        return f"Expressed sticker gesture '{emotion_or_emoji}'"

    async def send_reaction_tool(self, emoji: str) -> str:
        print(f"[Telegram] Expressed reaction body language '{emoji}'")
        return f"Added reaction '{emoji}'"

    async def execute_tg_api(self, method_name: str, kwargs: dict) -> str:
        """
        Executes ANY Pyrogram method on behalf of Kuni's Telegram account.
        """
        if not self.app or not self.app.is_connected:
            return "Telegram client is not active."
        if not hasattr(self.app, method_name):
            return f"Pyrogram API has no method named '{method_name}'."
        try:
            func = getattr(self.app, method_name)
            res = await func(**kwargs)
            return f"Telegram API '{method_name}' executed successfully: {str(res)[:300]}"
        except Exception as e:
            return f"Error executing Telegram API '{method_name}': {e}"

    async def join_chat_by_link(self, link_or_username: str) -> str:
        if not self.app or not self.app.is_connected:
            return "Telegram userbot is not connected."
        try:
            chat = await self.app.join_chat(link_or_username)
            title = getattr(chat, "title", str(chat.id))
            print(f"[Telegram] Joined chat/channel successfully: '{title}' ({link_or_username})")
            diary_instance.add_entry(text=f"Joined new Telegram chat/channel: {title}", emotion="curious")
            return f"Successfully joined Telegram chat: '{title}'"
        except Exception as e:
            print(f"[Telegram] Error joining chat '{link_or_username}': {e}")
            return f"Failed to join chat '{link_or_username}': {e}"

    async def enqueue_message(self, client: Client, message: Message):
        try:
            chat_id = message.chat.id
            user_name = message.from_user.first_name if message.from_user else "User"
            text_preview = message.text or message.caption or ("[Media/Sticker]" if message.sticker or message.photo else "")
            
            log_event("BOT", f"Incoming message from {user_name} (chat {chat_id}): '{text_preview}'")

            # Mark as read immediately
            try:
                await client.read_chat_history(chat_id)
            except Exception:
                pass

            if chat_id not in self.message_buffers:
                self.message_buffers[chat_id] = []
            self.message_buffers[chat_id].append((message, client))

            # Cancel pending debounce task to wait for user to finish their "ladder"
            if chat_id in self.debounce_tasks and not self.debounce_tasks[chat_id].done():
                self.debounce_tasks[chat_id].cancel()

            self.debounce_tasks[chat_id] = asyncio.create_task(
                self.debounce_timer(client, chat_id, delay=2.0)
            )
        except Exception as e:
            log_event("BOT", f"Enqueue error: {e}")

    async def debounce_timer(self, client: Client, chat_id: int, delay: float = 2.0):
        try:
            await asyncio.sleep(delay)
            # User finished typing their ladder, process accumulated messages
            buffered = self.message_buffers.pop(chat_id, [])
            if buffered:
                await self.process_message_batch(client, chat_id, buffered)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log_event("BOT", f"Debounce timer error for chat {chat_id}: {e}")

    async def process_message_batch(self, client: Client, chat_id: int, batch: List[Tuple[Message, Client]]):
        last_message = batch[-1][0]
        user_id = str(last_message.from_user.id) if last_message.from_user else str(chat_id)
        user_name = last_message.from_user.first_name if last_message.from_user else "User"

        long_term_memory_instance.update_user_profile(
            user_id=user_id,
            name=user_name,
            username=last_message.from_user.username if last_message.from_user else "",
            notes=f"Last interaction in chat {chat_id}"
        )

        # Collect text/voice/photos/stickers from batch
        extracted_texts = []
        user_msg_content = None

        for msg, _ in batch:
            if msg.photo:
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                    tmp_path = tmp.name
                try:
                    await msg.download(file_name=tmp_path)
                    with open(tmp_path, "rb") as img_f:
                        b64_img = base64.b64encode(img_f.read()).decode("utf-8")
                    caption_text = msg.caption or "Опиши, что на фото?"
                    user_msg_content = [
                        {"type": "text", "text": caption_text},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                    ]
                    extracted_texts.append(caption_text)
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
            elif msg.sticker:
                emoji_str = msg.sticker.emoji or "😊"
                pack_name = msg.sticker.set_name or "sticker"
                extracted_texts.append(f"[Прислал стикер {emoji_str}]")

                # Download sticker file and convert to PNG base64 for Vision multimodal perception
                with tempfile.NamedTemporaryFile(suffix=".webp", delete=False) as tmp:
                    tmp_path = tmp.name
                try:
                    await msg.download(file_name=tmp_path)
                    if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                        with Image.open(tmp_path) as img:
                            buffered = io.BytesIO()
                            img.save(buffered, format="PNG")
                            b64_sticker = base64.b64encode(buffered.getvalue()).decode("utf-8")
                            user_msg_content = [
                                {"type": "text", "text": f"[Прислал стикер в Telegram с эмодзи '{emoji_str}']"},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_sticker}"}}
                            ]
                except Exception as sticker_err:
                    print(f"[Telegram] Error processing sticker image: {sticker_err}")
                    if not user_msg_content:
                        user_msg_content = f"[Прислал стикер {emoji_str} из пака {pack_name}]"
                finally:
                    if os.path.exists(tmp_path):
                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass
            elif msg.text:
                extracted_texts.append(msg.text)
            elif msg.caption:
                extracted_texts.append(msg.caption)
            elif msg.voice or msg.audio:
                with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
                    tmp_path = tmp.name
                try:
                    await msg.download(file_name=tmp_path)
                    transcription = await llm_client_instance.transcribe_audio(tmp_path)
                    if transcription:
                        extracted_texts.append(transcription)
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)

        combined_text = "\n".join(extracted_texts).strip()
        if not combined_text:
            return

        # Record user text style for Emotional Debt / Resentment tracking
        emotion_engine.record_user_message_style(user_id, combined_text)

        # Group Chat Decision Pipeline (Sieve Pipeline & Cool-down)
        if last_message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            from group_engine import group_chat_engine
            is_mention = last_message.mentioned or any(name in combined_text.lower() for name in ["куни", "мила", "kuni"])
            is_reply_to_kuni = bool(last_message.reply_to_message and last_message.reply_to_message.from_user and last_message.reply_to_message.from_user.is_self)
            
            action, reaction_emoji = await group_chat_engine.evaluate_message_engagement(
                chat_id=chat_id,
                combined_text=combined_text,
                is_direct_mention=is_mention,
                is_reply_to_kuni=is_reply_to_kuni,
                recent_messages=self.chat_histories.get(chat_id, [])
            )

            if action == "ignore":
                print(f"[Telegram Group] Action: IGNORE in group {chat_id}. Keeping silence.")
                return
            elif action == "reaction" and reaction_emoji:
                print(f"[Telegram Group] Action: REACTION '{reaction_emoji}' in group {chat_id}.")
                try:
                    await client.send_reaction(chat_id, last_message.id, reaction_emoji)
                except Exception as e:
                    print(f"[Telegram Group] Reaction error: {e}")
                return

        # Check for photo generation or voice note request
        lowered = combined_text.lower()
        
        # 1. Voice note request check
        if any(kw in lowered for kw in ["голосовое", "голосовуху", "гс", "запиши голос", "voice note", "скажи в гс", "записать голосовое"]):
            print(f"[Telegram] Generating voice note for chat {chat_id}...")
            from voice_generator import generate_and_send_voice
            voice_prompt = combined_text.replace("запиши голосовое", "").replace("голосовое", "").replace("гс", "").strip() or "привет! записываю тебе голосовое сообщение"
            await generate_and_send_voice(self, chat_id, voice_prompt)
            return

        # 2. Image generation request check
        if any(kw in lowered for kw in ["нарисуй", "сгенерируй", "картинку", "картинка", "фото", "сделай аватарку", "draw", "generate image", "send photo"]):
            await client.send_chat_action(chat_id, enums.ChatAction.UPLOAD_PHOTO)
            image_url = await llm_client_instance.generate_image(combined_text)
            if image_url:
                await last_message.reply_photo(photo=image_url, caption="вот держи 😊")
                return

        # Typing indicator
        await client.send_chat_action(chat_id, enums.ChatAction.TYPING)

        # Retrieve RAG & Memories, Emotions, Goals & Self-Learned Rules
        thoughts_entries = diary_instance.search_memories(combined_text, limit=3)
        thoughts_str = diary_instance.format_thoughts(thoughts_entries)
        working_mem_str = working_memory_instance.load()
        long_term_str = long_term_memory_instance.format_long_term_context(query=combined_text, user_id=user_id)
        emotional_str = emotion_engine.format_emotional_context(user_id=user_id)
        goals_str = goal_engine.format_goals_context()
        self_rules_str = self_learning_instance.format_self_rules_context()

        system_prompt = character_instance.build_system_prompt(
            thoughts=thoughts_str,
            working_memory=working_mem_str,
            long_term_memory=long_term_str,
            emotional_context=emotional_str,
            goals_context=goals_str,
            self_rules_context=self_rules_str
        )

        if chat_id not in self.chat_histories:
            self.chat_histories[chat_id] = []

        history = self.chat_histories[chat_id]
        history.append({"role": "user", "content": user_msg_content or combined_text})

        if len(history) > 20:
            history = history[-20:]

        messages_for_llm = [{"role": "system", "content": system_prompt}] + history

        from proxy_server import KUNI_TOOLS, execute_local_tool

        try:
            response_text = ""
            for iteration in range(5):
                res = await llm_client_instance.chat_completion(
                    messages=messages_for_llm,
                    tools=KUNI_TOOLS,
                    chat_label=str(chat_id),
                    function_label="telegram_reply"
                )
                msg_obj = res.choices[0].message
                if hasattr(msg_obj, "tool_calls") and msg_obj.tool_calls:
                    tool_calls_data = []
                    for tc in msg_obj.tool_calls:
                        tool_calls_data.append({
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                        })
                    messages_for_llm.append({"role": "assistant", "content": msg_obj.content or "", "tool_calls": tool_calls_data})
                    for tc in msg_obj.tool_calls:
                        try:
                            args = json.loads(tc.function.arguments)
                        except Exception:
                            args = {}
                        tool_output = await execute_local_tool(tc.function.name, args)
                        messages_for_llm.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": tool_output
                        })
                    continue
                else:
                    response_text = msg_obj.content.strip() if msg_obj.content else ""
                    break

            if response_text:
                log_event("AI", f"LLM generated response for chat {chat_id}: '{response_text[:120]}...'")
                history.append({"role": "assistant", "content": response_text})
                self.chat_histories[chat_id] = history
                
                # Log action & reaction for Reflexion Self-Learning Loop
                self_learning_instance.log_action(
                    action_type="telegram_reply",
                    kuni_text=response_text,
                    user_id=user_id,
                    user_reaction=combined_text
                )

                # Send response in short human ladder messages
                await self.send_response_ladder(client, chat_id, response_text)

                total_tokens = sum(len(m.get("content", "")) for m in history) // 4
                trigger_limit = config_instance.get("misc", "diary_token_count_trigger", 20000)
                if total_tokens > trigger_limit or len(history) >= 20:
                    print(f"[Telegram] Context trigger reached for chat {chat_id}. Updating working memory & diary...")
                    await working_memory_instance.dump_context_and_update(history)
                    diary_instance.add_entry(
                        text=f"Chat interaction with {user_name}: {response_text[:100]}",
                        emotion="content"
                    )

        except Exception as e:
            print(f"[Telegram] Error sending reply: {e}")
            await client.send_message(chat_id, "ой у меня чтото зависло немного...")

    async def send_response_ladder(self, client: Client, chat_id: int, full_text: str):
        """
        Splits response into short natural Telegram ladder messages sent sequentially.
        Supports 2% Typo probability with instant human self-correction (edit message).
        """
        lines = [line.strip() for line in full_text.split("\n") if line.strip()]
        if not lines:
            lines = [full_text]

        # Further split long lines if needed
        chunks = []
        for line in lines:
            if len(line) > 100:
                parts = [p.strip() for p in line.replace(". ", ".\n").split("\n") if p.strip()]
                chunks.extend(parts)
            else:
                chunks.append(line)

        for chunk in chunks:
            clean_chunk = chunk.rstrip(".")
            await client.send_chat_action(chat_id, enums.ChatAction.TYPING)
            typing_delay = min(1.2, max(0.4, len(clean_chunk) * 0.02))
            await asyncio.sleep(typing_delay)

            # 2% Typo Probability & Self-Correction
            if random.random() < 0.02 and len(clean_chunk) > 6:
                words = clean_chunk.split()
                target_idx = random.randint(0, len(words) - 1)
                word = words[target_idx]
                if len(word) > 3:
                    # Introduce subtle typo
                    typo_word = word[:-2] + word[-1] + word[-2]
                    words_typo = list(words)
                    words_typo[target_idx] = typo_word
                    typo_chunk = " ".join(words_typo)

                    sent_msg = await client.send_message(chat_id, typo_chunk)
                    await asyncio.sleep(1.5)
                    await client.edit_message_text(chat_id, sent_msg.id, clean_chunk)
                    continue

            log_event("BOT", f"Sent ladder message to chat {chat_id}: '{clean_chunk}'")
            await client.send_message(chat_id, clean_chunk)

    async def start(self):
        enabled = config_instance.get("general", "telegram_enabled", True)
        if not enabled:
            print("[Telegram] telegram_enabled = false in config.toml. Skipping Telegram userbot startup.")
            return

        if self.init_client():
            print("[Telegram] Starting Telegram Userbot...")
            await self.app.start()
            print("[Telegram] Telegram Userbot is active and listening!")

            # Automatically generate and apply initial profile identity (Avatar, Name, Bio)
            from profile_generator import generate_and_apply_profile
            asyncio.create_task(generate_and_apply_profile(self))

    async def stop(self):
        if self.app and self.app.is_connected:
            await self.app.stop()
            print("[Telegram] Telegram Userbot stopped.")

kuni_telegram_bot = KuniTelegramBot()
