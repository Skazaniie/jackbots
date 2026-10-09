"""Languages: game-language detection, Latin-only text for the English game and localized messages.

The English jackbox.tv client accepts only Latin-1 characters (sanitizeInput: [\\u0020-\\u007E\\u00A1\\u00BF-\\u00FF’])
and silently drops everything else, so Cyrillic answers never reach the game — fit them with latin_safe().
Panel messages are written in English and translated with ui() when the panel language is Russian.
"""
import re

from . import store

_CYR = re.compile(r"[А-Яа-яЁё]")
_LAT = re.compile(r"[A-Za-z]")
_NOT_GAME_SAFE = re.compile(r"[^\u0020-\u007E\u00A1\u00BF-\u00FF’]")
_NOT_NAME_SAFE = re.compile(r"[^A-Z0-9\u00A1\u0020-\u002F\u00BF-\u00FF!?*$+\-'_.,]")
_TRANSLIT = dict(zip(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
    ["a", "b", "v", "g", "d", "e", "yo", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u",
     "f", "kh", "ts", "ch", "sh", "shch", "", "y", "", "e", "yu", "ya"]))
_PUNCT = {"«": '"', "»": '"', "“": '"', "”": '"', "„": '"', "‘": "'", "—": "-", "–": "-", "−": "-", "…": "...",
          "№": "#", "\u00a0": " "}


def detect(*texts, default=None):
    """'ru' if the text is mostly Cyrillic, 'en' if Latin, otherwise default."""
    s = " ".join(str(t or "") for t in texts)
    cyr, lat = len(_CYR.findall(s)), len(_LAT.findall(s))
    if cyr >= 3 or cyr > lat:
        return "ru"
    return "en" if lat else default


def transliterate(text):
    out = []
    for ch in str(text or ""):
        low = ch.lower()
        if low in _TRANSLIT:
            t = _TRANSLIT[low]
            out.append(t.capitalize() if ch != low else t)
        else:
            out.append(_PUNCT.get(ch, ch))
    return "".join(out)


def latin_safe(text):
    """Text the English game accepts: Cyrillic is transliterated, other unsupported characters are dropped."""
    return re.sub(r"\s+", " ", _NOT_GAME_SAFE.sub("", transliterate(text))).strip()


def latin_name(name, fallback="BOT"):
    """Nickname for jackbox.tv (sanitizeName: upper-case Latin, digits and a few symbols), up to 12 characters."""
    return _NOT_NAME_SAFE.sub("", latin_safe(name).upper()).strip()[:12] or fallback


GAME_TITLES = {
    "en": {"quiplash2": "Quiplash 2", "pollposition": "Guesspionage", "triviadeath2": "Trivia Murder Party 2",
           "survivetheinternet": "Survive the Internet"},
    "ru": {"quiplash2": "Смехлыст 2", "pollposition": "Нашшпионаж", "triviadeath2": "Смертельная вечеринка 2",
           "survivetheinternet": "Выжить в интернете"},
}

# phrases that go into prompts and bot memory — in the language of the game
TEXT = {
    "en": {
        "history_empty": "(nothing yet)",
        "persona_default": "an ordinary player",
        "duplicate": " (another player already gave this answer — come up with a different one)",
        "comic_missing": "the comic picture is unavailable — come up with a universal funny line",
        "mem_answer": "\"{q}\" → you answered \"{a}\"",
        "mem_vote": "voted in \"{q}\" for \"{a}\"",
        "mem_pick": "\"{q}\" → {a}",
        "mem_final": "final \"{q}\" → {a}",
        "mem_pct": "\"{q}\": you guessed {n}%",
        "mem_pct_result": "\"{q}\": you {n}%, real {v}% ({tag})",
        "pct_high": "too high", "pct_low": "too low", "pct_close": "almost exact",
        "their_number_unknown": "their number (see the game screen)",
        "updown": {"higher": "Higher", "lower": "Lower", "much_higher": "Much higher", "much_lower": "Much lower"},
        "nothing": "nothing",
        "hint_final": "final round — the escape; get it wrong and you'll be caught",
        "hint_math": "\"Math\" mini-game: solve the problem",
        "hint_rules": "\"Rules\" mini-game: follow every rule of the task literally",
        "hint_trivia": "a trivia question or a mini-game choice",
        "text_mindmeld": ("Mind Meld: name ONE real example from the category, one or two words. If your answer "
                          "matches someone else's, you die, so don't pick the most obvious one."),
        "text_mirror": "A ghost wrote one word on the mirror. You can't see it — guess it, answer with one word.",
        "text_password": "You need a password — one real 4-letter word.",
        "text_funny": "If a funny answer is asked for, be sarcastic and down-to-earth.",
        "num_donation": ("Donations: everyone has $500 at risk and gives part of it to another player. If someone "
                         "ends up with $800+ ($1000+ with 4+ players), everyone who gave to them dies; otherwise the "
                         "richest player dies, on a tie all the richest die. IMPORTANT: 0 or pennies is almost certain "
                         "death: you stay the richest, and if everyone gives 0, everyone dies. Too much overfeeds the "
                         "receiver and you die. Players usually survive by giving about 100–300."),
        "num_greed": ("Greed: the players who took the least and the most die. Aim for the middle, "
                      "but avoid obvious round numbers."),
        "num_default": "Pick a reasonable number.",
        "retry_number": " Your previous number \"{prev}\" was rejected ({error}) — give another one, digits only.",
        "retry_text": " Your previous answer \"{prev}\" was rejected ({error}) — give another one.",
        "mirror_question": "You are a ghost writing one word on a mirror. Which word?",
        "mirror_hint": "Answer with one word up to 10 letters, no explanations.",
        "creepy_words": ["DEATH", "BLOOD", "COFFIN", "RUN", "HELP", "GRAVE", "KILLER", "GHOST", "DECAY", "POISON"],
        "photo_unknown": "unknown photo",
        "vision_on": "The picture is attached — look at it.",
        "vision_off": "You can't see the picture, here is its description.",
        "photo_task": "Photo caption",
        "photo_label": " [photo: {desc}]",
        "option_n": "option {n}",
        "no_photo": "none",
    },
    "ru": {
        "history_empty": "(пока ничего)",
        "persona_default": "обычный игрок",
        "duplicate": " (такой ответ уже дал другой игрок — придумай другой)",
        "comic_missing": "картинка комикса недоступна — придумай универсальную смешную реплику",
        "mem_answer": "«{q}» → ты ответил «{a}»",
        "mem_vote": "голосовал в «{q}» за «{a}»",
        "mem_pick": "«{q}» → {a}",
        "mem_final": "финал «{q}» → {a}",
        "mem_pct": "«{q}»: ты поставил {n}%",
        "mem_pct_result": "«{q}»: ты {n}%, было {v}% ({tag})",
        "pct_high": "завысил", "pct_low": "занизил", "pct_close": "почти точно",
        "their_number_unknown": "своё число (смотри на экран игры)",
        "updown": {"higher": "Больше", "lower": "Меньше", "much_higher": "Намного больше", "much_lower": "Намного меньше"},
        "nothing": "ничего",
        "hint_final": "финальный раунд — побег, ошибёшься и тебя догонят",
        "hint_math": "мини-игра «Математика»: реши пример",
        "hint_rules": "мини-игра «Правила»: выполни все правила из задания буквально",
        "hint_trivia": "вопрос викторины или выбор в мини-игре",
        "text_mindmeld": ("Слияние разумов: назови ОДИН реальный пример из категории, одно-два слова. Если твой ответ "
                          "совпадёт с чужим — смерть, поэтому не бери самый очевидный вариант."),
        "text_mirror": "Призрак написал на зеркале одно слово. Ты его не видишь — угадай его, ответь одним словом.",
        "text_password": "Нужен пароль — одно настоящее слово из 4 букв.",
        "text_funny": "Если просят смешной ответ — шути саркастично и приземлённо.",
        "num_donation": ("Пожертвования: у каждого в опасности $500, отдаёшь часть другому игроку. Если у кого-то станет "
                         "$800+ (при 4+ игроках — $1000+), все, кто ему дарил, умирают; иначе умирает самый богатый, "
                         "при ничьей — все самые богатые. ВАЖНО: 0 или копейки — почти верная смерть: ты останешься "
                         "самым богатым, а если все отдадут 0, умрут все. Слишком много — перекормишь получателя и умрёшь. "
                         "Обычно выживают, отдав примерно 100–300."),
        "num_greed": ("Жадность: умирают те, кто взял меньше всех и больше всех. Целься в середину, "
                      "но не в очевидные круглые числа."),
        "num_default": "Выбери разумное число.",
        "retry_number": " Твоё прошлое число «{prev}» не приняли ({error}) — дай другое, только цифрами.",
        "retry_text": " Твой прошлый ответ «{prev}» не приняли ({error}) — дай другой.",
        "mirror_question": "Ты призрак и пишешь на зеркале одно слово. Какое?",
        "mirror_hint": "Ответь одним словом до 10 букв, без пояснений.",
        "creepy_words": ["СМЕРТЬ", "КРОВЬ", "ГРОБ", "БЕГИ", "ПОМОГИ", "МОГИЛА", "УБИЙЦА", "ПРИЗРАК", "ТЛЕН", "ЯД"],
        "photo_unknown": "неизвестное фото",
        "vision_on": "Картинка приложена — смотри на неё.",
        "vision_off": "Картинку ты не видишь, вот её описание.",
        "photo_task": "Подпись к фото",
        "photo_label": " [фото: {desc}]",
        "option_n": "вариант {n}",
        "no_photo": "нет",
    },
}

# panel messages: English source text → Russian
UI_RU = {
    "Round {n}": "Раунд {n}",
    "model didn't answer: {e}": "модель не ответила: {e}",
    "(the game's safety answer)": "(запасной ответ игры)",
    "random vote: {e}": "голос наугад: {e}",
    "gold": "золото", "silver": "серебро", "bronze": "бронза",
    "topic choice": "выбор темы",
    "topic: {t}": "тема: {t}",
    "model didn't answer, guessing 50: {e}": "модель не ответила, ставлю 50: {e}",
    "model didn't answer, picking at random: {e}": "модель не ответила, выбираю наугад: {e}",
    "model didn't answer, random vote: {e}": "модель не ответила, голосую наугад: {e}",
    "model didn't answer, picking a random number: {e}": "модель не ответила, беру случайное число: {e}",
    "model refused to answer: {t}": "модель отказалась отвечать: {t}",
    "model couldn't come up with a word: {e}": "модель не придумала слово: {e}",
    "picture rejected, answering from the description: {e}": "картинку не принял, отвечаю по описанию: {e}",
    "wrote {w} on the mirror": "написал на зеркале {w}",
    "wrote {w}": "написал {w}",
    "drew a doodle": "нарисовал каракули",
    "hiding: row {y}, cell {x}": "прячусь: ряд {y}, клетка {x}",
    "stabbing: row {y}, cell {x}": "бью: ряд {y}, клетка {x}",
    "scratched 3 cells": "стёр 3 клетки",
    "dialed {num}": "набрал {num}",
    "couldn't get through: the numbers are only on the game screen":
        "не смог дозвониться: номера видны только на экране игры",
    "dropped the chip at {v}%": "бросил фишку в {v}%",
    "final: photo caption": "финал: подпись к фото",
    "provider {p} not found": "провайдер {p} не найден",
    "provider not found": "провайдер не найден",
    "no such provider": "нет такого провайдера",
    "no such bot": "нет такого бота",
    "couldn't reconnect": "не удалось переподключиться",
    "connection closed, reconnecting": "соединение закрыто, переподключаюсь",
    "Room not found. Check the code on the game screen.": "Комната не найдена. Проверь код на экране игры.",
    "network: {e}": "сеть: {e}",
    "timed out": "не успели",
    "The game “{tag}” isn't supported yet. Supported: {games}.": "Игра «{tag}» пока не поддерживается. Есть: {games}.",
    "The game has already started — new players can't join. Start the bots in the lobby.":
        "Игра уже идёт — новые игроки не могут войти. Запусти ботов в лобби.",
    "No enabled bots for this game.": "Нет включённых ботов для этой игры.",
    "Paste the token or the whole address of the page Twitch sent you to.":
        "Вставь токен или весь адрес страницы, на которую тебя вернул Twitch.",
    "Twitch rejected the token: it is wrong or expired. Get a new one.":
        "Twitch не принял токен: он неверный или истёк. Получи новый.",
    "This token was issued to another app; the game only accepts tokens from the “get token” link.":
        "Этот токен выдан другому приложению — игра примет только токен из ссылки «получить токен».",
    "This room requires Twitch sign-in. Add a Twitch token to the bots (Bots → Twitch account).":
        "Комната пускает только с входом через Twitch. Добавь ботам токен (Боты → Аккаунт Twitch).",
    "The room requires Twitch sign-in, bots without a token stay out: {names}":
        "Комната требует вход через Twitch, боты без токена не заходят: {names}",
    "Room {code}: {game}. Starting bots: {n}": "Комната {code}: {game}. Запускаю ботов: {n}",
    "Bots stopped": "Боты остановлены",
    "{name} pressed “Everybody's in”": "{name} нажал «Все в сборе»",
    "No bot can start the game (VIP is the first player to join, and the minimum number of players is needed).":
        "Ни один бот не может начать игру (VIP — первый вошедший, нужно минимум игроков).",
}


def ui_lang():
    try:
        return store.load("settings").get("ui_language", "en")
    except (OSError, ValueError):
        return "en"


def ui(text, **kw):
    """Panel message in the panel language; text is the English original (key of UI_RU)."""
    if ui_lang() == "ru":
        text = UI_RU.get(text, text)
    return text.format(**kw) if kw else text
