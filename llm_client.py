import os
import asyncio
from typing import List, Dict, Any, Optional, AsyncGenerator
import httpx
from openai import AsyncOpenAI
from config import config_instance
from metrics import track_llm_usage

class LLMClient:
    def __init__(self):
        self.reload_client()

    def reload_client(self):
        base_url = config_instance.get("api", "base_url", "https://api.openai.com/v1")
        api_key = config_instance.get("api", "api_key", "YOUR_API_KEY_HERE")
        # High performance HTTPX async client with connection pooling
        http_client = httpx.AsyncClient(
            limits=httpx.Limits(max_keepalive_connections=100, max_connections=200),
            timeout=httpx.Timeout(60.0, connect=10.0)
        )
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key, http_client=http_client)

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Any] = None,
        temperature: float = 0.7,
        chat_label: str = "general",
        function_label: str = "chat",
        stream: bool = False
    ):
        model_name = model or config_instance.get("models", "chat_model", "YOUR_CHAT_VISION_MODEL_HERE")
        try:
            kwargs = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
            }
            if tools:
                kwargs["tools"] = tools
            if tool_choice:
                kwargs["tool_choice"] = tool_choice

            if stream:
                kwargs["stream"] = True
                response = await self.client.chat.completions.create(**kwargs)
                return response
            else:
                response = await self.client.chat.completions.create(**kwargs)
                
                # Track token metrics
                if hasattr(response, "usage") and response.usage:
                    input_tokens = response.usage.prompt_tokens or 0
                    output_tokens = response.usage.completion_tokens or 0
                    cache_hit = 0
                    if hasattr(response.usage, "prompt_tokens_details") and response.usage.prompt_tokens_details:
                        cache_hit = getattr(response.usage.prompt_tokens_details, "cached_tokens", 0) or 0
                    track_llm_usage(
                        model=model_name,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        cache_hit=cache_hit,
                        chat=chat_label,
                        function=function_label
                    )
                return response
        except Exception as e:
            print(f"[LLMClient] Error calling chat model '{model_name}': {e}")
            # Try fallback model if configured
            fallback = config_instance.get("models", "chat_fallback_model", "YOUR_FALLBACK_MODEL_HERE")
            if model_name != fallback:
                print(f"[LLMClient] Attempting fallback model '{fallback}'...")
                return await self.chat_completion(
                    messages=messages,
                    model=fallback,
                    tools=tools,
                    tool_choice=tool_choice,
                    temperature=temperature,
                    chat_label=chat_label,
                    function_label=function_label,
                    stream=stream
                )
            raise e

    async def generate_image(self, prompt: str) -> Optional[str]:
        """
        Generates image using configured image model.
        Returns URL or base64 data string.
        """
        image_model = config_instance.get("models", "image_model", "YOUR_IMAGE_MODEL_HERE")
        try:
            res = await self.client.images.generate(
                model=image_model,
                prompt=prompt,
                n=1,
                size="1024x1024"
            )
            if res.data and len(res.data) > 0:
                return res.data[0].url or res.data[0].b64_json
        except Exception as e:
            print(f"[LLMClient] Error generating image with '{image_model}': {e}")
        return None

    async def transcribe_audio(self, audio_file_path: str) -> str:
        """
        Transcribes voice message using configured ASR model.
        """
        asr_model = config_instance.get("models", "asr_model", "YOUR_ASR_MODEL_HERE")
        try:
            with open(audio_file_path, "rb") as audio_file:
                res = await self.client.audio.transcriptions.create(
                    model=asr_model,
                    file=audio_file
                )
                return res.text or ""
        except Exception as e:
            print(f"[LLMClient] Error transcribing audio with '{asr_model}': {e}")
            return ""

llm_client_instance = LLMClient()
