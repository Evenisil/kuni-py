import os
import random
from pathlib import Path
from typing import List, Dict, Any, Optional

MEDIA_DIR = Path("data/media_archive")
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
(MEDIA_DIR / "memes").mkdir(parents=True, exist_ok=True)
(MEDIA_DIR / "audio").mkdir(parents=True, exist_ok=True)

class MediaVaultManager:
    def __init__(self):
        # Kuni's 3 Signature Favorite Sticker Sets (Aesthetic anime/cat vibes)
        self.signature_sticker_packs = [
            "AestheticAnimeGirlVibe",
            "NekoMoodsPack",
            "CozyCatEmotions"
        ]
        
        # Emotion to signature sticker emoji/file mapping
        self.signature_stickers = {
            "smug": "😏",
            "laugh": "😂",
            "flustered": "😳",
            "crying": "😭",
            "skull": "💀",
            "angry": "👿",
            "cozy": "☕️",
            "moai": "🗿",
            "clown": "🤡"
        }

    def get_signature_sticker(self, emotion: str = "smug") -> Dict[str, str]:
        emoji = self.signature_stickers.get(emotion.lower(), "😏")
        pack = random.choice(self.signature_sticker_packs)
        return {
            "emoji": emoji,
            "pack": pack
        }

    def get_saved_memes(self) -> List[Path]:
        meme_dir = MEDIA_DIR / "memes"
        return [f for f in meme_dir.glob("*") if f.is_file()]

    def get_random_meme(self) -> Optional[Path]:
        memes = self.get_saved_memes()
        return random.choice(memes) if memes else None

media_vault_instance = MediaVaultManager()
