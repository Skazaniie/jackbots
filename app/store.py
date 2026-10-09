"""Конфиги приложения: config/*.json. Создаются из значений по умолчанию при первом запуске."""
import copy
import json
import sys
import threading
from pathlib import Path

from .prompts import LANGS, PROMPTS

if getattr(sys, "frozen", False):
    # Собранный exe (PyInstaller): ресурсы распакованы во временную папку,
    # а настройки и логи лежат рядом с exe — так они переживают обновление программы.
    RESOURCES = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    ROOT = Path(sys.executable).resolve().parent
else:
    RESOURCES = ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "config"           # изменяемые настройки (ключи API — только здесь)
LOGS = ROOT / "logs"
DATA = RESOURCES / "data"       # справочные данные игр, только чтение
WEB = RESOURCES / "web"
ASSETS = RESOURCES / "assets"
_lock = threading.Lock()

DEFAULT_PROVIDERS = [
    {"id": "openai", "name": "OpenAI", "icon": "openai.svg", "color": "#10a37f",
     "base_url": "https://api.openai.com/v1", "models": ["gpt-4.1-mini", "gpt-4.1-nano", "gpt-4o-mini", "gpt-5-mini"]},
    {"id": "anthropic", "name": "Anthropic", "icon": "claude-color.svg", "color": "#d97757",
     "base_url": "https://api.anthropic.com/v1", "models": ["claude-haiku-4-5", "claude-sonnet-4-5"]},
    {"id": "gemini", "name": "Google Gemini", "icon": "gemini-color.svg", "color": "#4285f4",
     "base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "models": ["gemini-2.5-flash", "gemini-2.5-flash-lite"]},
    {"id": "deepseek", "name": "DeepSeek", "icon": "deepseek-color.svg", "color": "#4d6bfe",
     "base_url": "https://api.deepseek.com/v1", "models": ["deepseek-chat"]},
    {"id": "openrouter", "name": "OpenRouter", "icon": "openrouter.svg", "color": "#6467f2",
     "base_url": "https://openrouter.ai/api/v1", "models": ["x-ai/grok-4-fast", "meta-llama/llama-4-scout"]},
    {"id": "ollama", "name": "Ollama", "icon": "ollama.svg", "color": "#8a8f98",
     "base_url": "http://localhost:11434/v1", "models": ["qwen3:8b"]},
]
PROVIDER_FIELDS = {"api_key": "", "timeout": 15, "max_tokens": 0, "stream": True, "retry": True,
                   "extra_body": {}, "headers": {}, "status": "new", "last_ms": 0}

DEFAULT_BOTS = [
    {"id": "b1", "name": "Qirtx", "color": "#10a37f", "provider": "openai", "model": "gpt-4.1-mini",
     "persona": "cheeky stand-up comic who loves the absurd", "temperature": 1.0},
    {"id": "b2", "name": "Mavlo", "color": "#d97757", "provider": "anthropic", "model": "claude-haiku-4-5",
     "persona": "know-it-all nerd who loves puns", "temperature": 0.9},
    {"id": "b3", "name": "Zenkoo", "color": "#4285f4", "provider": "gemini", "model": "gemini-2.5-flash",
     "persona": "good-natured dreamer with unexpected answers", "temperature": 1.0},
    {"id": "b4", "name": "Brisk", "color": "#4d6bfe", "provider": "deepseek", "model": "deepseek-chat",
     "persona": "competitive player who likes simple everyday jokes", "temperature": 1.1},
]
BOT_FIELDS = {"enabled": True, "games": {"quiplash2": True, "pollposition": True, "triviadeath2": True}}

# ui_language — язык панели; game_language — версия игры: "auto" (по тексту игры), "en" (jackbox.tv), "ru" (jackbox.fun)
DEFAULT_SETTINGS = {"ui_language": "en", "game_language": "auto", "ecast_host": "ecast.jackboxgames.com",
                    "memory_rounds": 6,
                    "answer_delay_ms": [0, 0], "log_traffic": True}
LANGUAGE_MODES = ("auto", *LANGS)

# промты каждой версии игры — в своём файле: prompts.json (русская) и prompts_en.json (английская)
PROMPT_FILES = {"ru": "prompts", "en": "prompts_en"}
DEFAULTS = {"providers": DEFAULT_PROVIDERS, "bots": DEFAULT_BOTS, "settings": DEFAULT_SETTINGS,
            **{name: PROMPTS[lang] for lang, name in PROMPT_FILES.items()}}


def _normalize(name, data):
    if name == "providers":
        for p in data:
            for k, v in PROVIDER_FIELDS.items():
                p.setdefault(k, copy.deepcopy(v))
            p.setdefault("models", [])
            p.setdefault("icon", "openai.svg")
            p.setdefault("color", "#8a8f98")
    elif name == "bots":
        for b in data:
            for k, v in BOT_FIELDS.items():
                b.setdefault(k, copy.deepcopy(v))
    elif name in DEFAULTS and name.startswith("prompts"):
        for game, phases in DEFAULTS[name].items():
            if isinstance(phases, dict):
                g = data.setdefault(game, {})
                for ph, val in phases.items():
                    cur = g.setdefault(ph, copy.deepcopy(val))
                    for k, v in val.items():
                        cur.setdefault(k, v)
            else:
                data.setdefault(game, phases)
    elif name == "settings":
        for k, v in DEFAULT_SETTINGS.items():
            data.setdefault(k, copy.deepcopy(v))
        if data["game_language"] not in LANGUAGE_MODES:
            data["game_language"] = "auto"
        if data["ui_language"] not in LANGS:
            data["ui_language"] = "en"
    return data


def load(name):
    path = CFG / f"{name}.json"
    with _lock:
        if not path.exists():
            CFG.mkdir(parents=True, exist_ok=True)
            data = copy.deepcopy(DEFAULTS[name])
            path.write_text(json.dumps(_normalize(name, data), ensure_ascii=False, indent=2), "utf-8")
            return data
        return _normalize(name, json.loads(path.read_text("utf-8")))


def save(name, data):
    CFG.mkdir(parents=True, exist_ok=True)
    path = CFG / f"{name}.json"
    tmp = path.with_suffix(".tmp")
    with _lock:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
        tmp.replace(path)


def prompts(lang):
    """Промты версии игры lang ("ru" / "en")."""
    return load(PROMPT_FILES.get(lang, "prompts"))


def default_prompt(lang, game, phase):
    """Промт по умолчанию: phase "system" — общий системный, иначе фаза игры."""
    base = PROMPTS.get(lang, PROMPTS["ru"])
    return copy.deepcopy(base["system"] if game == "system" or phase == "system" else base.get(game, {}).get(phase))


def provider(pid):
    return next((p for p in load("providers") if p["id"] == pid), None)
