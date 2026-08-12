import os
import time
import tomllib
import tomli_w
from pathlib import Path

DEFAULT_CONFIG_PATH = Path("config.toml")

DEFAULT_CONFIG = {
    "general": {
        "character_name": "Kuni",
        "character_nickname": "@kunii_chan",
        "papik_name": "Alex2772",
        "papik_chat_id": 0,
        "telegram_enabled": True,
        "telegram_api_id": 0,
        "telegram_api_hash": "",
        "proxy_enabled": True,
        "proxy_port": 10434,
        "proxy_api_key": "YOUR_PROXY_KEY_HERE",
        "metrics_port": 9464,
    },
    "api": {
        "base_url": "https://api.openai.com/v1",
        "api_key": "YOUR_API_KEY_HERE",
    },
    "models": {
        # здесь модель с текстом и вижен
        "chat_model": "YOUR_CHAT_VISION_MODEL_HERE",
        # резервная модель
        "chat_fallback_model": "YOUR_FALLBACK_MODEL_HERE",
        # модель генерации картинок
        "image_model": "YOUR_IMAGE_MODEL_HERE",
        # модель распознавания речи (ASR)
        "asr_model": "YOUR_ASR_MODEL_HERE",
    },
    "capabilities": {
        "web_search_enabled": True,
        "image_gen_enabled": True,
        "tts_enabled": False,
    },
    "misc": {
        "diary_token_count_trigger": 20000,
        "sleep_enabled": True,
        "sleep_interval_hours": 24,
    }
}

class ConfigManager:
    def __init__(self, config_path: str = "config.toml"):
        self.config_path = Path(config_path)
        self._mtime = 0
        self.config = {}
        self.ensure_config_exists()
        self.load()

    def ensure_config_exists(self):
        if not self.config_path.exists():
            with open(self.config_path, "wb") as f:
                tomli_w.dump(DEFAULT_CONFIG, f)
            print(f"[Config] Created default {self.config_path}")

    def load(self):
        if not self.config_path.exists():
            self.ensure_config_exists()
        
        mtime = self.config_path.stat().st_mtime
        if mtime != self._mtime:
            try:
                with open(self.config_path, "rb") as f:
                    data = tomllib.load(f)
                
                # Merge defaults for any missing key
                merged = DEFAULT_CONFIG.copy()
                for section, values in data.items():
                    if section in merged and isinstance(merged[section], dict) and isinstance(values, dict):
                        merged[section].update(values)
                    else:
                        merged[section] = values
                
                self.config = merged
                self._mtime = mtime
                print(f"[Config] Loaded configuration from {self.config_path}")
            except Exception as e:
                print(f"[Config] Error reading {self.config_path}: {e}")

    def check_hot_reload(self):
        if self.config_path.exists():
            mtime = self.config_path.stat().st_mtime
            if mtime != self._mtime:
                self.load()

    def get(self, section: str, key: str, default=None):
        self.check_hot_reload()
        return self.config.get(section, {}).get(key, default)

config_instance = ConfigManager()
