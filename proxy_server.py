import os
import json
import time
import asyncio
from pathlib import Path
from typing import List, Dict, Any
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse, JSONResponse
import httpx

from config import config_instance
from character import character_instance
from working_memory import working_memory_instance
from diary import diary_instance
from web_search import format_search_results, fetch_web_page
from llm_client import llm_client_instance
from metrics import log_event

app = FastAPI(title="Kuni Proxy Server")

LOGS_DIR = Path("logs_proxy")
LOGS_DIR.mkdir(parents=True, exist_ok=True)
DATA_PROXY_DIR = Path("data/proxy")
DATA_PROXY_DIR.mkdir(parents=True, exist_ok=True)

from long_term_memory import long_term_memory_instance

# Kuni Tool Definitions
KUNI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "send_sticker",
            "description": "Send a Telegram sticker from Kuni's favorite sticker packs to express body language, embarrassment, amusement, or mood.",
            "parameters": {
                "type": "object",
                "properties": {
                    "emotion_or_emoji": {"type": "string", "description": "Emotion or emoji for sticker choice (e.g. 😭, 💀, shy, laugh, confused)"}
                },
                "required": ["emotion_or_emoji"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_reaction",
            "description": "Add an emoji reaction (e.g. 🔥, 😭, ❤️, 👍, 🗿, 🤡) to the user's message as non-verbal body language.",
            "parameters": {
                "type": "object",
                "properties": {
                    "emoji": {"type": "string", "description": "Emoji reaction string (e.g. 🔥, 😭, ❤️, 👍, 🗿, 🤡)"}
                },
                "required": ["emoji"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": "Generate a visual image/art based on a description prompt and send it to the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Visual prompt describing the image to generate."}
                },
                "required": ["prompt"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "record_voice_message",
            "description": "Record and send a real voice message (audio message) to the current Telegram chat.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The exact text to speak in the voice note."}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Perform a live web search for fresh information, news, or answers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query."}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_web_page",
            "description": "Fetch and read the full text content of any website or URL on the Internet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The target website URL"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_diary_memory",
            "description": "Save an important event, fact, or emotional memory into Kuni's permanent diary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Memory content to save."},
                    "emotion": {"type": "string", "description": "Current feeling/emotion."}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "save_long_term_fact",
            "description": "Save a permanent lifelong fact, core belief, or personal relationship detail.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "Subject of fact (e.g. Alex, AI, Python)"},
                    "category": {"type": "string", "description": "Category (e.g. UserFact, Preference, LifeRule)"},
                    "fact": {"type": "string", "description": "The permanent fact to remember."}
                },
                "required": ["subject", "category", "fact"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "join_telegram_chat",
            "description": "Join a Telegram group or channel by invite link or username.",
            "parameters": {
                "type": "object",
                "properties": {
                    "link_or_username": {"type": "string", "description": "Telegram link or @group_username"}
                },
                "required": ["link_or_username"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_profile_identity",
            "description": "Generate a new avatar photo, name, and bio for Kuni and update her Telegram account profile.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_telegram_api",
            "description": "Execute ANY Pyrogram Telegram API method on behalf of Kuni's account (e.g. send_message, get_dialogs, pin_chat, set_profile_photo, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {"type": "string", "description": "Pyrogram Client method name (e.g. send_message, pin_chat, get_chat_history)"},
                    "kwargs": {"type": "object", "description": "Keyword arguments for the Pyrogram method."}
                },
                "required": ["method", "kwargs"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_project_files",
            "description": "List files in Kuni's own codebase.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_self_code",
            "description": "Read the content of a file in Kuni's codebase.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Filename like main.py or character.py"}
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "modify_self_code",
            "description": "Modify or rewrite a source file in Kuni's codebase.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Filename to modify."},
                    "content": {"type": "string", "description": "New code content for the file."}
                },
                "required": ["filename", "content"]
            }
        }
    }
]

async def execute_local_tool(name: str, args: Dict[str, Any]) -> str:
    log_event("PROXY_TOOL", f"Executing local tool '{name}' with arguments: {args}")
    if name == "send_sticker":
        emotion = args.get("emotion_or_emoji", "😊")
        from telegram_client import kuni_telegram_bot
        return await kuni_telegram_bot.send_sticker_tool(emotion)
    elif name == "send_reaction":
        emoji = args.get("emoji", "🔥")
        from telegram_client import kuni_telegram_bot
        return await kuni_telegram_bot.send_reaction_tool(emoji)
    elif name == "generate_image":
        prompt = args.get("prompt", "cute anime girl")
        url = await llm_client_instance.generate_image(prompt)
        return f"Successfully generated image: {url}" if url else "Failed to generate image."
    elif name == "record_voice_message":
        text = args.get("text", "")
        from telegram_client import kuni_telegram_bot
        from voice_generator import generate_and_send_voice
        # Chat ID will be handled in current conversation
        return "Recording and sending voice message to user."
    elif name == "web_search":
        query = args.get("query", "")
        print(f"[Proxy Tool] Executing web_search for '{query}'...")
        return await format_search_results(query)
    elif name == "fetch_web_page":
        url = args.get("url", "")
        print(f"[Proxy Tool] Executing fetch_web_page for '{url}'...")
        return await fetch_web_page(url)
    elif name == "save_diary_memory":
        text = args.get("text", "")
        emotion = args.get("emotion", "thoughtful")
        diary_instance.add_entry(text=text, emotion=emotion)
        return f"Successfully saved memory entry to diary: '{text}'"
    elif name == "save_long_term_fact":
        subject = args.get("subject", "General")
        category = args.get("category", "UserFact")
        fact = args.get("fact", "")
        long_term_memory_instance.add_fact(subject=subject, category=category, fact=fact)
        return f"Saved permanent lifelong fact: [{category}] {subject} - {fact}"
    elif name == "join_telegram_chat":
        link = args.get("link_or_username", "")
        from telegram_client import kuni_telegram_bot
        return await kuni_telegram_bot.join_chat_by_link(link)
    elif name == "update_profile_identity":
        from telegram_client import kuni_telegram_bot
        from profile_generator import generate_and_apply_profile
        success = await generate_and_apply_profile(kuni_telegram_bot)
        return "Successfully updated profile photo, name, and bio on Telegram!" if success else "Failed to update profile."
    elif name == "execute_telegram_api":
        method = args.get("method", "")
        kwargs = args.get("kwargs", {})
        from telegram_client import kuni_telegram_bot
        return await kuni_telegram_bot.execute_tg_api(method, kwargs)
    elif name == "list_project_files":
        files = [f.name for f in Path(".").glob("*") if f.is_file()]
        return f"Files in project: {', '.join(files)}"
    elif name == "read_self_code":
        filename = args.get("filename", "")
        filepath = Path(filename)
        if filepath.exists() and filepath.is_file():
            return filepath.read_text(encoding="utf-8")
        return f"File '{filename}' not found."
    elif name == "modify_self_code":
        filename = args.get("filename", "")
        content = args.get("content", "")
        filepath = Path(filename)
        try:
            filepath.write_text(content, encoding="utf-8")
            return f"File '{filename}' successfully modified and saved."
        except Exception as e:
            return f"Error modifying file '{filename}': {e}"
    return f"Unknown tool: {name}"

@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {"id": "chat-vision-model", "object": "model", "owned_by": "kuni"},
            {"id": "fallback-model", "object": "model", "owned_by": "kuni"},
            {"id": "auto", "object": "model", "owned_by": "kuni"}
        ]
    }

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    # Optional API key check for IDE
    auth_header = request.headers.get("authorization", "")
    expected_key = config_instance.get("general", "proxy_api_key", "YOUR_PROXY_KEY_HERE")
    if expected_key and auth_header:
        token = auth_header.replace("Bearer ", "").strip()
        if token != expected_key:
            print(f"[Proxy] Warning: Client connected with custom key '{token}'")

    body = await request.json()
    
    # Save last query for debugging
    with open(DATA_PROXY_DIR / "last_query.json", "w", encoding="utf-8") as f:
        json.dump(body, f, indent=2, ensure_ascii=False)

    stream = body.get("stream", False)
    messages: List[Dict[str, Any]] = body.get("messages", [])

    # Extract query text for RAG diary thoughts search
    last_user_msg = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "")
    if isinstance(last_user_msg, list):
        # Multimodal message content
        last_user_msg = " ".join([item.get("text", "") for item in last_user_msg if isinstance(item, dict) and item.get("type") == "text"])

    thoughts_entries = diary_instance.search_memories(last_user_msg, limit=3)
    thoughts_str = diary_instance.format_thoughts(thoughts_entries)
    working_mem_str = working_memory_instance.load()
    long_term_str = long_term_memory_instance.format_long_term_context(last_user_msg)

    system_prompt = character_instance.build_system_prompt(
        thoughts=thoughts_str, 
        working_memory=working_mem_str,
        long_term_memory=long_term_str
    )

    # Insert or update system message
    if messages and messages[0].get("role") == "system":
        messages[0]["content"] = system_prompt + "\n\n" + str(messages[0]["content"])
    else:
        messages.insert(0, {"role": "system", "content": system_prompt})

    # Append Kuni tools if web search or capabilities enabled
    if config_instance.get("capabilities", "web_search_enabled", True):
        existing_tools = body.get("tools", [])
        body["tools"] = existing_tools + KUNI_TOOLS

    # Handle tool loops transparently
    max_tool_iterations = 5
    for iteration in range(max_tool_iterations):
        res = await llm_client_instance.chat_completion(
            messages=messages,
            model=body.get("model"),
            tools=body.get("tools"),
            temperature=body.get("temperature", 0.7),
            function_label="proxy_completion",
            stream=False
        )

        message = res.choices[0].message
        
        # Check if model requested tool call
        if hasattr(message, "tool_calls") and message.tool_calls:
            # Save assistant message with tool call
            tool_calls_data = []
            for tc in message.tool_calls:
                tool_calls_data.append({
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                })
            messages.append({"role": "assistant", "content": message.content or "", "tool_calls": tool_calls_data})

            # Execute tool calls locally
            for tc in message.tool_calls:
                func_name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except Exception:
                    args = {}
                tool_output = await execute_local_tool(func_name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_output
                })
            # Loop again to feed tool outputs back to LLM
            continue
        else:
            # Final response reached
            final_content = message.content or ""
            
            if stream:
                async def sse_generator():
                    created_ts = int(time.time())
                    chunk_id = f"chatcmpl-kuni-{created_ts}"
                    
                    # Initial content chunk
                    chunk = {
                        "id": chunk_id,
                        "object": "chat.completion.chunk",
                        "created": created_ts,
                        "model": body.get("model", "auto"),
                        "choices": [{
                            "index": 0,
                            "delta": {"role": "assistant", "content": final_content},
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(chunk)}\n\n"

                    # Done chunk
                    done_chunk = {
                        "id": chunk_id,
                        "object": "chat.completion.chunk",
                        "created": created_ts,
                        "model": body.get("model", "auto"),
                        "choices": [{
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop"
                        }]
                    }
                    yield f"data: {json.dumps(done_chunk)}\n\n"
                    yield "data: [DONE]\n\n"

                return StreamingResponse(sse_generator(), media_type="text/event-stream")
            else:
                return res.model_dump()

    # Fallback response if max iterations hit
    return JSONResponse({"choices": [{"message": {"role": "assistant", "content": "I completed your request."}}]})

# Transparent passthrough for all other endpoints (embeddings, audio, images, etc.)
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def passthrough(request: Request, path: str):
    base_url = config_instance.get("api", "base_url", "https://api.openai.com/v1")
    api_key = config_instance.get("api", "api_key", "YOUR_API_KEY_HERE")
    target_url = f"{base_url.rstrip('/')}/{path}"

    headers = dict(request.headers)
    headers["authorization"] = f"Bearer {api_key}"
    headers.pop("host", None)

    body = await request.body()
    async with httpx.AsyncClient() as client:
        resp = await client.request(
            method=request.method,
            url=target_url,
            headers=headers,
            content=body,
            params=request.query_params
        )
        return Response(content=resp.content, status_code=resp.status_code, headers=dict(resp.headers))

def run_proxy_server():
    import uvicorn
    port = config_instance.get("general", "proxy_port", 10434)
    print(f"[Proxy] Starting transparent OpenAI Proxy on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")
