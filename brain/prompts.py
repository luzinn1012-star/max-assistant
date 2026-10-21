from pathlib import Path

PERSONALITY_PATH = Path(__file__).with_name("personality.txt")
SYSTEM_PROMPT = PERSONALITY_PATH.read_text(encoding="utf-8").strip()
