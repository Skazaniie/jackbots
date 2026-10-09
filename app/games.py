"""Game logic. A bot reacts to the room state (bc:room) and its own phone state (bc:customer:<id>).

Message formats are taken from the official jackbox.tv client (pp3-quiplash2, pp3-pollposition, pp6-triviadeath2).
Game files with correct answers are not used: the model knows exactly what a player sees.
"""
import asyncio
import json
import random
import re
import time

from . import store
from .jackbox import EcastClient, stable_user_id
from .lang import GAME_TITLES as TITLES, TEXT, detect, latin_name, latin_safe, ui
from .llm import LLMError
from .prompts import LANGS, VAR_ALIASES

_TAG = re.compile(r"<[^>]+>|\[/?[a-zA-Z]+[^\]]*\]")


def clean(text):
    text = str(text or "").replace("<BLANK>", "___").replace("<blank>", "___")
    return re.sub(r"\s+", " ", _TAG.sub("", text)).strip()


def render(tpl, vars_):
    """Fills in {variables}; English names ({question}) are aliases of the Russian keys (VAR_ALIASES)."""
    def sub(m):
        k = m.group(1)
        k = k if k in vars_ else VAR_ALIASES.get(k, k)
        return str(vars_.get(k, m.group(0)))
    return re.sub(r"\{([^{}\s]+)\}", sub, tpl)


def numbered(items):
    return "\n".join(f"{i + 1}. {t}" for i, t in enumerate(items))


def parse_index(text, n):
    for m in re.findall(r"\d+", text or ""):
        i = int(m)
        if 1 <= i <= n:
            return i - 1
    return None


def parse_ranking(text, n):
    seen = []
    for m in re.findall(r"\d+", text or ""):
        i = int(m) - 1
        if 0 <= i < n and i not in seen:
            seen.append(i)
    return seen + [i for i in range(n) if i not in seen]


def cut(text, limit=45):
    text = text.strip()
    if len(text) <= limit:
        return text
    short = text[:limit].rsplit(" ", 1)[0]
    return (short if len(short) > limit * 0.5 else text[:limit]).rstrip(" ,.;:-—")


class BotPlayer:
    tag = ""
    title = ""
    start_body = {"start": True}

    def __init__(self, session, cfg):
        self.s = session
        self.cfg = cfg
        self.room, self.me = {}, {}
        self.memory = []
        self.done = set()
        self.tasks = set()
        self.status = "connecting"  # status code; labels live in the panel
        self.thinking = 0           # how many model requests are running right now
        self.last_ms = None
        self.stats = {"calls": 0, "ms": 0, "errors": 0}
        mode = getattr(session, "game_language", "auto")
        self.lang = mode if mode in LANGS else "en"
        # the English client accepts only Latin letters in a nickname, otherwise the name becomes empty/"????"
        nick = latin_name(cfg["name"]) if mode == "en" else cfg["name"]
        self.client = EcastClient(session.code, nick, session.host, self.on_entity, self.on_status,
                                  session.traffic, user_id=stable_user_id(session.code, cfg["id"]))

    # ---------- connection ----------
    @property
    def name(self):
        return self.cfg["name"]

    async def on_status(self, status, detail):
        self.status = status
        self.s.emit("status", bot=self.cfg["id"], name=self.name, status=self.status, detail=detail)

    async def on_entity(self, key, val):
        if not isinstance(val, dict):
            return
        pid = self.client.pid
        if key in ("bc:room", "room", "roomBlob"):
            self.room = val
            self._safe(self.on_room)
        elif key in (f"bc:customer:{self.client.user_id}", f"bc:customer:{pid}", f"player:{pid}", "player"):
            self.me = val
            self._safe(self.on_me)

    def _safe(self, fn):
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            self.s.emit("error", bot=self.cfg["id"], name=self.name, text=f"{type(e).__name__}: {e}")

    def spawn(self, key, coro_fn, *args):
        """Runs an action once per key without blocking message handling."""
        if key in self.done:
            return
        self.done.add(key)

        async def wrap():
            try:
                await coro_fn(*args)
            except Exception as e:  # noqa: BLE001
                self.stats["errors"] += 1
                self.s.emit("error", bot=self.cfg["id"], name=self.name, text=f"{type(e).__name__}: {e}"[:300])

        t = asyncio.create_task(wrap())
        self.tasks.add(t)
        t.add_done_callback(self.tasks.discard)

    async def send(self, body, label=None):
        lo, hi = store.load("settings").get("answer_delay_ms", [0, 0])
        if hi:
            await asyncio.sleep(random.uniform(lo, hi) / 1000)
        await self.client.send(body)

    # ---------- language ----------
    def use_lang(self, *texts):
        """Answer language: from settings or (auto mode) by the game text; remembered for the next screens."""
        mode = getattr(self.s, "game_language", "auto")
        self.lang = mode if mode in LANGS else detect(*texts, default=self.lang)
        return self.lang

    def t(self, key, **kw):
        """A phrase for the prompt/memory in the game language."""
        text = TEXT[self.lang][key]
        return text.format(**kw) if kw else text

    def fit(self, text, limit=45):
        """An answer the game will accept: the English version drops Cyrillic and emoji, so transliterate to Latin."""
        return cut(latin_safe(text) if self.lang == "en" else text, limit)

    # ---------- memory and requests ----------
    def remember(self, line):
        self.memory.append(line)
        self.memory = self.memory[-50:]

    def history(self):
        n = int(store.load("settings").get("memory_rounds", 6))
        items = self.memory[-n:] if n > 0 else []
        return "\n".join(f"- {x}" for x in items) or self.t("history_empty")

    def build_messages(self, phase, vars_):
        prompts = store.prompts(self.lang)
        ph = prompts[self.tag][phase]
        base = {"игра": TITLES[self.lang].get(self.tag, self.tag), "имя": self.name,
                "персонаж": self.cfg.get("persona") or self.t("persona_default"),
                "история": self.history(), "раунд": self.room.get("round", "")}
        base.update(vars_)
        return [{"role": "system", "content": render(prompts["system"], base)},
                {"role": "user", "content": render(ph["text"], base)}], ph

    async def ask(self, phase, vars_, show=None, image=None):
        msgs, ph = self.build_messages(phase, vars_)
        if image:  # image data: URL, OpenAI-compatible content-part format
            msgs[-1]["content"] = [{"type": "text", "text": msgs[-1]["content"]},
                                   {"type": "image_url", "image_url": {"url": image}}]
        prov = store.provider(self.cfg["provider"])
        if not prov:
            raise LLMError(ui("provider {p} not found", p=self.cfg["provider"]))
        self.s.emit("think", bot=self.cfg["id"], name=self.name, phase=ph.get("title", phase),
                    question=show or vars_.get("вопрос", ""))
        self.thinking += 1
        try:
            r = await self.s.llm.chat(prov, self.cfg["model"], msgs, self.cfg.get("temperature", 0.9),
                                      # thinking models need spare tokens for reasoning: min_tokens in the bot settings
                                      max(ph.get("max_tokens", 60), int(self.cfg.get("min_tokens") or 0)),
                                      one_line=ph.get("format") != "ranking",
                                      extra_body=self.cfg.get("extra_body"))
        except LLMError:
            self.stats["errors"] += 1
            raise
        finally:
            self.thinking -= 1
        self.last_ms = r["ms"]
        self.stats["calls"] += 1
        self.stats["ms"] += r["ms"]
        return r

    def say(self, kind, text, ms=None, **extra):
        self.s.emit(kind, bot=self.cfg["id"], name=self.name, text=text, ms=ms, **extra)

    # ---------- overridden in games ----------
    def on_room(self):
        pass

    def on_me(self):
        pass

    @property
    def can_start(self):
        return bool(self.me.get("isAllowedToStartGame"))


# =====================================================================
class Quiplash2(BotPlayer):
    tag = "quiplash2"
    start_body = {"start": True}
    _comics = None

    def __init__(self, *a):
        super().__init__(*a)
        self.my_answers = set()
        self.err_count = 0
        self.r3_rank = {}
        self.r3_voted = {}

    def on_me(self):
        st = self.me.get("state")
        q = self.me.get("question")
        if st == "Gameplay_AnswerQuestion" and isinstance(q, dict):
            if self.me.get("showError"):
                self.err_count += 1
            self.spawn(("ans", q.get("id"), self.err_count if self.me.get("showError") else 0), self.answer, q,
                       bool(self.me.get("showError")))
        elif st == "Gameplay_R3Vote" and not self.me.get("doneVoting"):
            qid = (self.room.get("question") or {}).get("id")
            self.spawn(("r3", qid, self.me.get("currentVote"), self.me.get("votesLeft")), self.r3vote, qid)
        elif st == "Gameplay_Vote":
            self.maybe_vote()

    def on_room(self):
        st = self.room.get("state")
        if st == "Gameplay_Vote":
            self.maybe_vote()
        elif st == "Gameplay_Round":
            self.spawn(("round", self.room.get("round")), self._note_round)

    async def _note_round(self):
        self.s.emit("info", text=ui("Round {n}", n=self.room.get("round", "?")), once=f"round{self.room.get('round')}")

    # --- answers ---
    @staticmethod
    def _kind(q):
        t = q.get("type")
        if isinstance(t, str):
            t = t.lower()
            return "wordlash" if "word" in t else "acrolash" if "acro" in t else "comiclash" if "comic" in t else "answer"
        return {1: "wordlash", 2: "acrolash", 3: "comiclash"}.get(t, "answer")

    def _comic(self, qid):
        if Quiplash2._comics is None:
            p = store.DATA / "ql2_comic_descriptions.json"
            Quiplash2._comics = json.loads(p.read_text("utf-8")) if p.exists() else {}
        return Quiplash2._comics.get(str(qid)) or self.t("comic_missing")

    async def answer(self, q, dup):
        kind = self._kind(q)
        qid = q.get("id")
        prompt = clean(q.get("prompt"))
        self.use_lang(prompt, clean(q.get("quip")))
        vars_ = {"вопрос": prompt}
        if kind == "wordlash":
            vars_ = {"вопрос": clean(q.get("quip")), "слово": prompt}
        elif kind == "comiclash":
            vars_ = {"вопрос": self._comic(qid)}
        if dup:
            vars_["вопрос"] += self.t("duplicate")
        text, ms = "", None
        for attempt in range(2):
            try:
                r = await self.ask(kind, vars_, show=prompt)
            except LLMError as e:
                self.say("error", ui("model didn't answer: {e}", e=e)[:300])
                break
            text, ms = self.fit(r["text"]), r["ms"]
            if kind == "wordlash" and prompt and prompt.lower() not in text.lower():
                if attempt == 0:
                    continue
                text = self.fit(f"{text} {prompt}")
            if kind == "acrolash" and not _acro_ok(prompt, text) and attempt == 0:
                continue
            break
        if not text:
            await self.send({"safetyQuip": True, "questionId": qid})
            self.say("answer", ui("(the game's safety answer)"), ms, question=prompt)
            return
        await self.send({"answer": text, "questionId": qid})
        self.my_answers.add(text.lower())
        self.remember(self.t("mem_answer", q=prompt, a=text))
        self.say("answer", text, ms, question=prompt)

    # --- voting ---
    def maybe_vote(self):
        if self.me.get("doneVoting") or self.me.get("state") not in (None, "Gameplay_Vote"):
            return
        choices = self.room.get("choices")
        if not isinstance(choices, dict) or len(choices) < 2:
            return
        order = self.room.get("order") or list(choices.keys())
        ignore = {str(x) for x in (self.me.get("ignore") or [])}
        opts = []
        for k in order:
            k = str(k)
            if k in ignore or k not in choices:
                continue
            opts.append((k, clean(choices[k])))
        if any(t.lower() in self.my_answers for _, t in opts) or len(opts) < 2:
            return  # this is our matchup, don't vote for ourselves
        prompt = clean((self.room.get("question") or {}).get("prompt"))
        self.spawn(("vote", prompt, tuple(k for k, _ in opts)), self.vote, prompt, opts)

    async def vote(self, prompt, opts):
        self.use_lang(prompt, *(t for _, t in opts))
        try:
            r = await self.ask("vote", {"вопрос": prompt, "варианты": numbered([t for _, t in opts])})
            i, ms = parse_index(r["text"], len(opts)), r["ms"]
        except LLMError as e:
            self.say("error", ui("random vote: {e}", e=e)[:200])
            i, ms = None, None
        if i is None:
            i = random.randrange(len(opts))
        key = opts[i][0]
        await self.send({"vote": int(key) if key.isdigit() else key})
        self.remember(self.t("mem_vote", q=prompt, a=opts[i][1]))
        self.say("vote", opts[i][1], ms, question=prompt)

    async def r3vote(self, qid):
        votes = self.me.get("votes") or []
        mine = self.me.get("playerIndex")
        opts = [v for v in votes if isinstance(v, dict) and v.get("playerIndex") != mine
                and clean(v.get("answer")).lower() not in self.my_answers]
        if not opts:
            return
        q = self.room.get("question") or {}
        prompt = clean(q.get("quip") or "") + " " + clean(q.get("prompt"))
        if qid not in self.r3_rank:
            self.r3_rank[qid] = None
            self.use_lang(prompt, *(clean(v.get("answer")) for v in opts))
            try:
                r = await self.ask("r3vote", {"вопрос": prompt.strip(),
                                              "варианты": numbered([clean(v.get("answer")) for v in opts])})
                order = parse_ranking(r["text"], len(opts))
            except LLMError:
                order = list(range(len(opts)))
                random.shuffle(order)
            self.r3_rank[qid] = [opts[i].get("playerIndex") for i in order]
        while self.r3_rank.get(qid) is None:
            await asyncio.sleep(0.05)
        used = self.r3_voted.setdefault(qid, [])
        avail = {v.get("playerIndex"): v for v in opts}
        pick = next((p for p in self.r3_rank[qid] if p in avail and p not in used), None)
        if pick is None:
            pick = next((p for p in self.r3_rank[qid] if p in avail), None)
        if pick is None:
            return
        used.append(pick)
        await self.send({"vote": pick})
        medal = ui(["gold", "silver", "bronze"][min(len(used) - 1, 2)])
        self.say("vote", f"{medal}: {clean(avail[pick].get('answer'))}", None, question=prompt.strip())


def _acro_ok(acro, text):
    letters = [c for c in acro.upper() if c.isalpha()]
    words = text.upper().split()
    return len(letters) == len(words) and all(w.startswith(l) for w, l in zip(words, letters))


# =====================================================================
class PollPosition(BotPlayer):
    tag = "pollposition"
    start_body = {"startGame": True}

    def __init__(self, *a):
        super().__init__(*a)
        self.pending = None  # (question, our estimate)
        self.seen_results = set()
        self.topic = ""  # poll title: in ChooseUpOrDown the survey field already holds the question itself

    def on_room(self):
        self.step()
        self._check_result()

    def on_me(self):
        self.step()

    def step(self):
        r, i = self.room.get("state"), self.me.get("state")
        q = clean(self.room.get("question") or self.me.get("question") or "")
        if r in ("Gameplay_ShowQuestion", "Gameplay_EnterPercentage") and self.room.get("survey"):
            self.topic = clean(self.room["survey"])
        if i == "Lobby_ChooseCharacter" and not self.me.get("character") and self.room.get("characters"):
            # the key changes with the set of taken characters: if ours was taken, choose again
            taken = tuple(sorted(str(c.get("id")) for c in self.room["characters"] if isinstance(c, dict) and c.get("isSelected")))
            self.spawn(("char", taken), self.pick_character)
        elif i == "Gameplay_PickCategory" and self.me.get("choices"):
            self.spawn(("cat", json.dumps(self.me.get("choices"), ensure_ascii=False)), self.pick_category)
        elif i == "Gameplay_EnterPercentage" and r == "Gameplay_EnterPercentage" and q:
            self.spawn(("pct", q), self.guess, q)
        elif i == "Gameplay_ChooseUpOrDown" and r == "Gameplay_ChooseUpOrDown" and q:
            self.spawn(("ud", q), self.updown, q)
        elif i == "Gameplay_ChooseMultiple" and self.me.get("choices"):
            picked = sum(1 for c in self.me["choices"] if isinstance(c, dict) and c.get("picked"))
            self.spawn(("multi", q, picked), self.multiple, q)

    async def pick_character(self):
        chars = [c for c in (self.room.get("characters") or []) if isinstance(c, dict) and c.get("isSelected") is None]
        if chars:
            await asyncio.sleep(random.uniform(0.2, 1.2))
            await self.send({"character": random.choice(chars).get("id")})

    async def pick_category(self):
        ch = [c for c in self.me.get("choices") if isinstance(c, dict)]
        self.use_lang(*(clean(c.get("text")) for c in ch))
        try:
            r = await self.ask("category", {"варианты": numbered([clean(c.get("text")) for c in ch])},
                               show=ui("topic choice"))
            i, ms = parse_index(r["text"], len(ch)), r["ms"]
        except LLMError:
            i, ms = None, None
        i = random.randrange(len(ch)) if i is None else i
        await self.send({"category": ch[i].get("id")})
        self.say("answer", ui("topic: {t}", t=clean(ch[i].get("text"))), ms)

    async def guess(self, q):
        self.use_lang(q)
        try:
            r = await self.ask("guess", {"вопрос": q})
            nums = [int(x) for x in re.findall(r"\d+", r["text"]) if 0 <= int(x) <= 100]
            n, ms = (nums[0] if nums else 50), r["ms"]
        except LLMError as e:
            self.say("error", ui("model didn't answer, guessing 50: {e}", e=e)[:200])
            n, ms = 50, None
        await self.send({"percentageUpdate": n})
        await self.send({"percentageEntered": n})
        self.finish_round_without_result()
        self.pending = (q, n)
        self.say("answer", f"{n}%", ms, question=q)

    def _their_number(self):
        # the game sends the number only as text: "Professor answered 25%"
        m = re.search(r"(\d{1,3})\s*%", str(self.room.get("question") or ""))
        if m and 0 <= int(m.group(1)) <= 100:
            return f"{int(m.group(1))}%"
        for k in ("percentage", "percent", "guess", "playerPercentage", "percentageEntered", "value"):
            v = self.room.get(k)
            if isinstance(v, (int, float)) and 0 <= v <= 100:
                return f"{int(v)}%"
        return self.t("their_number_unknown")

    async def updown(self, q):
        ch = [c for c in (self.room.get("choices") or []) if isinstance(c, dict)]
        if not ch:
            return
        question = clean(self.room.get("survey") or "") or q  # here survey is the question itself, question is "X answered N%"
        self.use_lang(question, q)
        labels = [clean(c.get("text")) or self.t("updown").get(str(c.get("id")).lower(), str(c.get("id")).replace("_", " "))
                  for c in ch]
        try:
            r = await self.ask("updown", {"вопрос": question, "опрос": self.topic,
                                          "число": self._their_number(), "варианты": numbered(labels)})
            i, ms = parse_index(r["text"], len(ch)), r["ms"]
        except LLMError:
            i, ms = None, None
        i = random.randrange(len(ch)) if i is None else i
        await self.send({"choice": ch[i].get("id")})
        self.say("vote", labels[i], ms, question=q)

    async def multiple(self, q):
        ch = self.me.get("choices") or []
        free = [(idx, clean(c.get("text"))) for idx, c in enumerate(ch) if isinstance(c, dict) and not c.get("picked")]
        if not free:
            return
        self.use_lang(q, *(t for _, t in free))
        try:
            r = await self.ask("multiple", {"вопрос": q, "инструкция": clean(self.me.get("selection") or ""),
                                            "варианты": numbered([t for _, t in free])})
            i, ms = parse_index(r["text"], len(free)), r["ms"]
        except LLMError:
            i, ms = None, None
        i = random.randrange(len(free)) if i is None else i
        await self.send({"choice": free[i][0]})
        self.say("vote", free[i][1], ms, question=q)

    def _check_result(self):
        """When the game shows the correct percentage to everyone, remember it for the next rounds."""
        if not self.pending:
            return
        q, n = self.pending
        if self.room.get("state") in ("Gameplay_EnterPercentage", "Gameplay_ChooseUpOrDown", "Gameplay_ShowQuestion"):
            return
        for k in ("answer", "actualPercentage", "correctPercentage", "result", "percentage"):
            v = self.room.get(k)
            if isinstance(v, (int, float)) and 0 <= v <= 100 and q not in self.seen_results:
                self.seen_results.add(q)
                v = int(v)
                tag = self.t("pct_high" if n > v + 5 else "pct_low" if n < v - 5 else "pct_close")
                self.remember(self.t("mem_pct_result", q=q, n=n, v=v, tag=tag))
                self.pending = None
                return

    def finish_round_without_result(self):
        if self.pending:
            q, n = self.pending
            self.remember(self.t("mem_pct", q=q, n=n))
            self.pending = None


# =====================================================================
# Trivia Murder Party 2 (pp6-triviadeath2). The client builds a "blob" = room without audience + the player's
# own state; the screen is chosen by blob.state. "Madness" distortions (Scramble/BTTF) are done by the
# client itself; the bot gets clean text.
TAG_ALIASES = {"triviadeath2-tjsp": "triviadeath2"}  # the same game in Party Starter
_MATH = re.compile(r"(-?\d+)\s*([+\-−–*×x/÷:])\s*(-?\d+)")


def solve_math(text):
    """'7 + 12' -> 19; None if the expression isn't recognized."""
    m = _MATH.search(clean(text))
    if not m:
        return None
    a, op, b = int(m.group(1)), m.group(2), int(m.group(3))
    if op == "+":
        return a + b
    if op in "-−–":
        return a - b
    if op in "*×x":
        return a * b
    return a / b if b else None


def _num(text):
    try:
        return float(clean(text).replace("−", "-").replace("–", "-").replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def doodle(color="#000000", n=4, w=300, h=300):
    """Scribbles for drawing minigames: a few polylines in the client format (x,y|x,y)."""
    lines = []
    for _ in range(n):
        x, y = random.randint(w // 6, w * 5 // 6), random.randint(h // 6, h * 5 // 6)
        pts = []
        for _ in range(random.randint(6, 14)):
            x = min(w - 10, max(10, x + random.randint(-35, 35)))
            y = min(h - 10, max(10, y + random.randint(-35, 35)))
            pts.append(f"{x},{y}")
        lines.append({"thickness": 6, "color": color, "points": "|".join(pts)})
    return lines


def text_lines(word, w, h, color="#000000", step=5):
    """A word drawn with strokes: render the text with a font into an image and trace pixel rows with horizontal lines.
    Returns [] without Pillow or a font; scribbles are used then."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return []
    img = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(img)
    name = next((n for n in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf",
                                  "/system/fonts/Roboto-Bold.ttf", "/system/fonts/Roboto-Regular.ttf")  # Roboto — Android
                 if _font_ok(ImageFont, n)), None)
    if not name:
        return []
    size = int(h * 0.75)
    while True:
        font = ImageFont.truetype(name, size)
        box = d.textbbox((0, 0), word, font=font)
        if box[2] - box[0] <= w * 0.92 or size <= 12:
            break
        size -= 4
    d.text(((w - box[2] - box[0]) // 2, (h - box[3] - box[1]) // 2), word, fill=255, font=font)
    px, lines = img.load(), []
    for y in range(step // 2, h, step):
        x = 0
        while x < w:
            if px[x, y] > 128:
                x0 = x
                while x < w and px[x, y] > 128:
                    x += 1
                lines.append({"thickness": step + 1, "color": color, "points": f"{x0},{y}|{max(x0 + 1, x - 1)},{y}"})
            x += 1
    return lines


def _font_ok(ImageFont, name):
    try:
        ImageFont.truetype(name, 10)
        return True
    except OSError:
        return False


_NUM_WORDS = {"одно": 1, "двух": 2, "трёх": 3, "трех": 3, "четырёх": 4, "четырех": 4, "пяти": 5, "шести": 6,
              "семи": 7, "восьми": 8, "девяти": 9, "десяти": 10, "одиннадцати": 11, "двенадцати": 12,
              "тринадцати": 13, "четырнадцати": 14, "пятнадцати": 15}


def letter_rule(prompt):
    """'Ten-letter words' / '7-letter words' / '5-letter words' -> 10 / 7 / 5. Models are bad at counting letters,
    so such categories are checked in code."""
    p = clean(prompt).lower()
    m = re.search(r"(\d+)\s*-?\s*(?:буквенн|letter)", p) or re.search(r"из\s+(\d+)\s+букв", p)
    if m:
        return int(m.group(1))
    m = re.search(r"([а-яё]+?)буквенн", p)
    return _NUM_WORDS.get(m.group(1)) if m else None


_REFUSAL = re.compile(r"I'?m Claude|I am Claude|I appreciate|I need to be (direct|straight|honest)|"
                      r"I can'?t|I cannot|I won'?t|as an AI|I'?m not going to|не могу помочь с этим|я ИИ|как ИИ", re.I)


class TriviaDeath2(BotPlayer):
    tag = "triviadeath2"
    SPEED = 1.0  # multiplier for pauses between "taps" (selftest sets 0)
    HANDLERS = {"MakeSingleChoice": "choice", "EnterSingleText": "text", "Draw": "draw", "Grid": "grid",
                "Scratch": "scratch", "Dial": "dial", "Drop": "drop"}

    def __init__(self, *a):
        super().__init__(*a)
        self.sig, self.seq = None, 0
        self.last_entry = ""

    async def ask(self, phase, vars_, show=None, image=None):
        r = await super().ask(phase, vars_, show, image)
        if _REFUSAL.search(r.get("text") or ""):  # the model broke character, treat it as no answer
            self.stats["errors"] += 1
            raise LLMError(ui("model refused to answer: {t}", t=r["text"][:60]))
        return r

    # ---------- state ----------
    @property
    def blob(self):
        room = {k: v for k, v in self.room.items() if k != "audience"}
        return {**room, **self.me} if self.me else room

    @property
    def can_start(self):
        b = self.blob
        return bool(b.get("state") == "Lobby" and b.get("playerCanStartGame") and b.get("gameCanStart")
                    and not b.get("gameIsStarting"))

    @property
    def start_body(self):
        return {"action": "PostGame_Continue" if self.blob.get("gameFinished") else "start"}

    @staticmethod
    def _prompt(b):
        p = b.get("prompt")
        return clean(p.get("text") or p.get("html") or "") if isinstance(p, dict) else clean(p)

    @staticmethod
    def _done(b):
        """Like parseBlob(): the choice is already made (chosen is set) or the game shows doneText."""
        dt = b.get("doneText")
        if b.get("state") == "EnterSingleText" and b.get("entry") is True:  # answer accepted
            return True
        if isinstance(dt, dict) and (dt.get("html") or dt.get("text")) or isinstance(dt, str) and dt:
            return True
        return b.get("state") == "MakeSingleChoice" and "chosen" in b and (b["chosen"] is not None or dt is None)

    async def _pause(self, lo, hi):
        if self.SPEED:
            await asyncio.sleep(random.uniform(lo, hi) * self.SPEED)

    def on_room(self):
        self.step()

    def on_me(self):
        self.step()

    def step(self):
        b = self.blob
        st = b.get("state")
        if st == "Lobby":
            self._lobby(b)
        handler = self.HANDLERS.get(st)
        if not handler or self._done(b) or (st == "MakeSingleChoice" and self._prompt(b) == "What do you want to do?"):
            self.sig = None  # the screen changed, the next identical question counts as new
            return
        # key without choices: the game may disable options on the fly, answering twice is not allowed
        # error means the game rejected the answer ("Invalid input!"), so answer again
        sig = json.dumps([st, b.get("prompt"), b.get("choiceId"), b.get("entryId"), b.get("error")], ensure_ascii=False,
                         sort_keys=True, default=str)
        if sig != self.sig:
            self.sig, self.seq = sig, self.seq + 1
        self.spawn(("tmp", self.seq), getattr(self, handler), b)

    def _lobby(self, b):
        chars = [c for c in (b.get("characters") or []) if isinstance(c, dict)]
        if chars and not (b.get("playerInfo") or {}).get("avatar"):
            free = tuple(sorted(str(c.get("name")) for c in chars if c.get("available") and not c.get("selected")))
            if free:
                self.spawn(("avatar", free), self.pick_avatar, free)

    async def pick_avatar(self, free):
        await self._pause(0.2, 1.2)
        await self.send({"action": "avatar", "name": random.choice(free)})

    @staticmethod
    def _options(b):
        """[(value for choice, action, text)]: the option key or its position, as in the client."""
        out = []
        for pos, c in enumerate(b.get("choices") or []):
            if not isinstance(c, dict) or c.get("disabled") or c.get("action") not in (None, "choose"):
                continue
            out.append((c["key"] if c.get("key") is not None else pos, c.get("action") or "choose",
                        clean(c.get("text") or c.get("html") or "")))
        return out

    def _hint(self, b):
        if b.get("roundType") == "FinalRound":
            return self.t("hint_final")
        if b.get("choiceType") == "Math":
            return self.t("hint_math")
        if b.get("choiceType") == "Rules":
            return self.t("hint_rules")
        return self.t("hint_trivia")

    # ---------- screens ----------
    async def choice(self, b):
        if any(isinstance(c, dict) and c.get("className") in ("selected", "unselected", "submit")
               for c in b.get("choices") or []):
            return await self.final(b)
        opts = self._options(b)
        if not opts:
            return
        prompt = self._prompt(b)
        self.use_lang(prompt, *(o[2] for o in opts))
        if b.get("type") == "multiple":
            return await self.multiple(b, opts)
        i, ms = None, None
        if b.get("choiceType") == "Math":
            v = solve_math(prompt)
            i = next((n for n, o in enumerate(opts) if v is not None and _num(o[2]) == v), None)
        if i is None:
            try:
                r = await self.ask("choice", {"вопрос": prompt, "варианты": numbered([o[2] for o in opts]),
                                              "подсказка": self._hint(b)})
                i, ms = parse_index(r["text"], len(opts)), r["ms"]
            except LLMError as e:
                self.say("error", ui("model didn't answer, picking at random: {e}", e=e)[:200])
        i = random.randrange(len(opts)) if i is None else i
        key, action, text = opts[i]
        await self.send({"action": action, "choice": key})
        self.remember(self.t("mem_pick", q=cut(prompt, 80), a=text))
        self.say("answer", text, ms, question=prompt)

    async def multiple(self, b, opts):
        prompt = self._prompt(b)
        picked, ms = [], None
        try:
            r = await self.ask("multiple", {"вопрос": prompt, "варианты": numbered([o[2] for o in opts]),
                                            "подсказка": self._hint(b)})
            picked = sorted({int(x) - 1 for x in re.findall(r"\d+", r["text"]) if 1 <= int(x) <= len(opts)})
            ms = r["ms"]
        except LLMError as e:
            self.say("error", ui("model didn't answer, picking at random: {e}", e=e)[:200])
        picked = picked or [random.randrange(len(opts))]
        await self.send({"action": "submit", "choice": ",".join(str(opts[i][0]) for i in picked)})
        self.say("answer", ", ".join(opts[i][2] for i in picked), ms, question=prompt)

    async def final(self, b):
        """Escape finale: options are toggled (selected/unselected) one by one, then the Submit button."""
        prompt = self._prompt(b)
        ch = b.get("choices") or []
        items = [(pos, clean(c.get("text") or c.get("html") or ""), c.get("className") == "selected")
                 for pos, c in enumerate(ch) if isinstance(c, dict) and c.get("className") in ("selected", "unselected")]
        submit = next((pos for pos, c in enumerate(ch) if isinstance(c, dict) and c.get("className") == "submit"), None)
        if not items:
            return
        self.use_lang(prompt, *(it[1] for it in items))
        picked, ms, n = None, None, letter_rule(prompt)
        if n:
            picked = {i for i, it in enumerate(items) if sum(ch_.isalpha() for ch_ in it[1]) == n}
        else:
            try:
                r = await self.ask("multiple", {"вопрос": prompt, "варианты": numbered([it[1] for it in items]),
                                                "подсказка": self._hint(b)})
                picked = {int(x) - 1 for x in re.findall(r"\d+", r["text"]) if 1 <= int(x) <= len(items)}
                ms = r["ms"]
            except LLMError as e:
                self.say("error", ui("model didn't answer, picking at random: {e}", e=e)[:200])
            picked = picked or {random.randrange(len(items))}
        for i, (pos, _, selected) in enumerate(items):
            if (i in picked) != selected:  # each tap toggles an option
                await self.send({"action": "choose", "choice": pos})
                await self._pause(0.2, 0.4)
        if submit is not None:
            await self.send({"action": "choose", "choice": submit})
        text = ", ".join(items[i][1] for i in sorted(picked)) or self.t("nothing")
        self.remember(self.t("mem_final", q=cut(prompt, 60), a=text))
        self.say("answer", text, ms, question=prompt)

    def _text_hint(self, b, prompt):
        eid, p = str(b.get("entryId") or "").lower(), prompt.lower()
        if "mindmeld" in eid:
            return self.t("text_mindmeld")
        if "mirror" in eid:
            return self.t("text_mirror")
        if "password" in eid or "парол" in p or "password" in p:
            return self.t("text_password")
        return self.t("text_funny")

    def _number_hint(self, b, prompt):
        eid, p = str(b.get("entryId") or "").lower(), prompt.lower()
        if "donation" in eid or "отдать" in p or "donat" in p:
            return self.t("num_donation")
        if "greed" in eid or "жадн" in p or "сколько денег ты возьм" in p or "greed" in p:
            return self.t("num_greed")
        return self.t("num_default")

    @staticmethod
    def _number_rule(b, prompt, lo, hi):
        eid, p = str(b.get("entryId") or "").lower(), prompt.lower()
        if "donation" in eid or "отдать" in p:
            # 0 = stay the richest (death), 300+ over someone else = overfeed (death for the donor)
            return random.randint(max(lo, 120), min(hi, 290))
        if "greed" in eid or "жадн" in p or "возьм" in p:
            return random.choice([n for n in range(int(lo + (hi - lo) * 0.35), int(lo + (hi - lo) * 0.65)) if n % 50])
        return None

    async def number(self, b, prompt):
        lo, hi = 0, 1000
        m = re.search(r"(\d+)\s*[-–—]\s*(\d+)", f"{b.get('placeholder') or ''} {prompt}")
        if m:
            lo, hi = sorted((int(m.group(1)), int(m.group(2))))
        self.use_lang(prompt)
        nums, ms, hint = [], None, self._number_hint(b, prompt)
        if b.get("error") and self.last_entry:
            hint += self.t("retry_number", prev=self.last_entry, error=clean(b["error"]))
        try:
            r = await self.ask("number", {"вопрос": prompt, "диапазон": f"{lo}–{hi}", "подсказка": hint})
            nums, ms = [int(x) for x in re.findall(r"\d+", r["text"]) if lo <= int(x) <= hi], r["ms"]
        except LLMError as e:
            self.say("error", ui("model didn't answer, picking a random number: {e}", e=e)[:200])
        if not nums:  # the model gave no number in range: minigame default strategy or random
            nums = [self._number_rule(b, prompt, lo, hi) or random.randint(lo, hi)]
        n = str(nums[0])
        self.last_entry = n
        await self.send({"action": "write", "entry": n})
        self.remember(self.t("mem_pick", q=cut(prompt, 80), a=n))
        self.say("answer", n, ms, question=prompt)

    async def text(self, b):
        prompt = self._prompt(b)
        if b.get("inputType") == "number":  # donations, greed: the game accepts only a number
            return await self.number(b, prompt)
        limit = int(b.get("maxLength") or 45)
        self.use_lang(prompt)
        hint = self._text_hint(b, prompt)
        funny = hint == self.t("text_funny")
        if b.get("error") and self.last_entry:
            hint += self.t("retry_text", prev=self.last_entry, error=clean(b["error"]))
        try:
            r = await self.ask("text", {"вопрос": prompt, "лимит": limit, "подсказка": hint})
            entry, ms = r["text"], r["ms"]
        except LLMError as e:
            self.say("error", ui("model didn't answer: {e}", e=e)[:200])
            return
        if not funny:  # a word is needed, not a joke: cut off "Scorpion, because..."
            entry = re.split(r"[,.;:!?(—–]| - ", entry)[0]
        entry = self.fit(entry.strip(" «»\"'"), limit)
        if not entry:
            return
        self.last_entry = entry
        if b.get("textKey"):  # in this case the client updates a text entity instead of messaging the host
            await self.client.update_text(b["textKey"], entry)
        else:
            await self.send({"action": "write", "entry": entry})
        self.remember(self.t("mem_pick", q=cut(prompt, 80), a=entry))
        self.say("answer", entry, ms, question=prompt)

    async def draw(self, b):
        colors = b.get("colors") or []
        c = colors[0] if colors else "#000000"
        color = c.get("hex", "#000000") if isinstance(c, dict) else str(c)
        size = b.get("size") or {}
        w, h = int(size.get("width") or 300), int(size.get("height") or 300)
        self.use_lang(self._prompt(b))
        word = await self._mirror_word() if b.get("roundType") == "Mirror" else None
        lines = (text_lines(word, w, h, color) if word else []) or doodle(color, 4, w, h)
        await self._pause(1, 3)
        if b.get("live"):
            # "Mirror": the game shows strokes live and has no submit button, so send lines one by one like the client
            for ln in lines:
                if self.blob.get("state") != "Draw":
                    break
                await self.client.send({"action": "line", "line": ln, "highlighter": False})
                await self._pause(0.02, 0.05)
            if b.get("hideSubmit"):
                self.say("answer", ui("wrote {w} on the mirror", w=word) if word else ui("drew a doodle"), None)
                return
        if b.get("objectKey"):
            await self.client.update_object(b["objectKey"], {"lines": lines, "submit": True})
        else:
            await self.send({"action": "submit", "lines": lines})
        self.say("answer", ui("wrote {w}", w=word) if word else ui("drew a doodle"), None, question=self._prompt(b))

    async def _mirror_word(self):
        """The model comes up with the word for the mirror; if it doesn't answer, take one from the fallback list."""
        try:
            r = await self.ask("text", {"вопрос": self.t("mirror_question"), "лимит": 10,
                                        "подсказка": self.t("mirror_hint")})
            word = re.split(r"[\s,.;:!?]+", r["text"].strip(" «»\"'"))[0]
            if self.lang == "en":
                word = latin_safe(word)
            word = re.sub(r"[^A-Za-zА-Яа-яЁё]", "", word)[:10]
        except LLMError as e:
            self.say("error", ui("model couldn't come up with a word: {e}", e=e)[:200])
            word = ""
        return (word or random.choice(self.t("creepy_words"))).upper()

    async def grid(self, b):
        cells = [(y, x, c.get("type")) for y, row in enumerate(b.get("grid") or []) if isinstance(row, list)
                 for x, c in enumerate(row) if isinstance(c, dict) and c.get("type") in ("Stab", "Hide")]
        if not cells:
            return
        await self._pause(0.5, 2)
        y, x, kind = random.choice(cells)
        await self.send({"action": "click", "position": f"{y}-{x}"})
        self.say("answer", ui("hiding: row {y}, cell {x}" if kind == "Hide" else "stabbing: row {y}, cell {x}",
                              y=y + 1, x=x + 1), None)

    async def scratch(self, b):
        # 7 dollars and 2 skulls: three dollars are enough to survive, no point risking more
        for idx in random.sample(range(len(b.get("choices") or []) or 9), 3):
            await self._pause(0.6, 1.2)
            if self.blob.get("state") != "Scratch":
                return
            await self.send({"action": "scratch", "index": idx})
        self.say("answer", ui("scratched 3 cells"), None)

    @staticmethod
    def _phone_numbers(b):
        texts = [TriviaDeath2._prompt(b), clean(b.get("instructions") or "")]
        for c in b.get("choices") or []:
            texts.append(clean(c.get("text") or c.get("html") or "") if isinstance(c, dict) else clean(c))
        nums = []
        for t in texts:
            for m in re.findall(r"\d[\d\s\-]{5,}\d", t):
                d = re.sub(r"\D", "", m)
                if len(d) == 7 and d not in nums:
                    nums.append(d)
        return nums

    async def dial(self, b):
        tried = []
        for _ in range(4):
            nums = [n for n in self._phone_numbers(self.blob) if n not in tried]
            num = random.choice(nums) if nums else "666" + "".join(random.choices("0123456789", k=4))
            tried.append(num)
            for d in num:
                if self.blob.get("state") != "Dial":
                    return
                await self.send({"action": "dial", "num": int(d)})
                await self._pause(0.4, 0.7)
            await self._pause(1.5, 1.5)
            if str(self.blob.get("status") or "").lower() == "connected" or self.blob.get("state") != "Dial":
                self.say("answer", ui("dialed {num}", num=num), None)
                return
            await self.send({"action": "hangup"})
            await self._pause(0.3, 0.6)
        self.say("error", ui("couldn't get through: the numbers are only on the game screen"))

    async def drop(self, b):
        await self._pause(1, 3)
        v = random.randint(5, 95)
        await self.send({"action": "drop", "value": v})
        self.say("answer", ui("dropped the chip at {v}%", v=v), None)


# =====================================================================
_STI_PHOTO = re.compile(r"photos/([A-Za-z]+)(?:-thumb)?\.jpg")
_photo_cache = {}


def sti_photos():
    """Finale photos: file name -> description (jackbox.tv client alt texts) and image URL."""
    if "list" not in _photo_cache:
        p = store.DATA / "sti_photos.json"
        _photo_cache["list"] = json.loads(p.read_text("utf-8")) if p.exists() else {}
    return _photo_cache["list"]


async def photo_data_url(url):
    """Image for a vision model as a data: URL (the provider may not be able to download it). None on failure."""
    if url in _photo_cache:
        return _photo_cache[url]
    import base64
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(url)
            r.raise_for_status()
    except httpx.HTTPError:
        return None
    data = f"data:image/jpeg;base64,{base64.b64encode(r.content).decode()}"
    _photo_cache[url] = data
    return data


class SurviveTheInternet(TriviaDeath2):
    """Survive the Internet (pp4): answer a question -> twist someone else's answer -> vote; finale is a photo caption."""
    tag = "survivetheinternet"
    HANDLERS = {"EnterSingleText": "write", "Voting": "vote_post", "MakeSingleChoice": "pick"}

    @property
    def can_start(self):
        # raw lobby blob: isAllowedToStartGame + lobbyState (the client turns them into playerCanStartGame/gameCanStart itself)
        b = self.blob
        return bool(b.get("state") == "Lobby" and (b.get("isAllowedToStartGame") or b.get("playerCanStartGame"))
                    and (b.get("lobbyState") in ("CanStart", "PostGame") or b.get("gameCanStart")))

    @property
    def start_body(self):
        return {"action": "PostGame_Continue" if self.blob.get("lobbyState") == "PostGame" else "start"}

    @staticmethod
    def _done(b):
        st = b.get("state")
        if st == "EnterSingleText":
            return b.get("entry") not in (None, False, "")
        return st in ("Voting", "MakeSingleChoice") and b.get("chosen") not in (None, "")

    @staticmethod
    def _text(b):
        """Task parts (above/in/below the black bar) and the finale photo name, if any."""
        t = b.get("text")
        t = {"blackBox": t} if isinstance(t, str) else t if isinstance(t, dict) else {}
        raw = " ".join(str(t.get(k) or "") for k in ("aboveBlackBox", "blackBox", "belowBlackBox", "thumbnail"))
        m = _STI_PHOTO.search(raw)
        parts = {k: clean(t.get(k)) for k in ("prefix", "aboveBlackBox", "blackBox", "belowBlackBox")}
        return parts, (m.group(1) if m else None)

    def _prompt(self, b):
        parts, _ = self._text(b)
        return " / ".join(v for v in parts.values() if v) or clean(b.get("prompt"))

    def step(self):
        b = self.blob
        st = b.get("state")
        handler = self.HANDLERS.get(st)
        if not handler or self._done(b):
            self.sig = None
            return
        sig = json.dumps([st, b.get("text"), b.get("entryId"), b.get("choices"), b.get("error")],
                         ensure_ascii=False, sort_keys=True, default=str)
        if sig != self.sig:
            self.sig, self.seq = sig, self.seq + 1
        self.spawn(("sti", self.seq), getattr(self, handler), b)

    async def _photo(self, name):
        """(description, image for vision or None)."""
        info = sti_photos().get(name or "") or {}
        desc = info.get("desc") or self.t("photo_unknown")
        image = await photo_data_url(info["url"]) if self.cfg.get("vision") and info.get("url") else None
        return desc, image

    async def _ask_photo(self, phase, vars_, name, show):
        desc, image = await self._photo(name)
        vars_ = {**vars_, "фото": desc}
        if image:
            try:
                return await self.ask(phase, {**vars_, "зрение": self.t("vision_on")}, show, image)
            except LLMError as e:  # the model doesn't accept images, the description is enough
                self.say("error", ui("picture rejected, answering from the description: {e}", e=e)[:200])
        return await self.ask(phase, {**vars_, "зрение": self.t("vision_off")}, show)

    async def write(self, b):
        parts, photo = self._text(b)
        limit = int(b.get("maxLength") or 80)
        task = " ".join(v for v in (parts["prefix"], parts["blackBox"], parts["belowBlackBox"]) if v)
        self.use_lang(task, parts["aboveBlackBox"], clean(b.get("prompt")))
        hint = ""
        if b.get("error") and self.last_entry:
            hint = self.t("retry_text", prev=self.last_entry, error=clean(b["error"]))
        try:
            if photo:
                r = await self._ask_photo("photo", {"вопрос": (task or self.t("photo_task")) + hint, "лимит": limit},
                                          photo, task or ui("final: photo caption"))
            elif b.get("entryId") == "twist" or parts["blackBox"] and parts["belowBlackBox"]:
                r = await self.ask("twist", {"ответ": parts["blackBox"],
                                             "вопрос": " ".join(v for v in (parts["prefix"], parts["aboveBlackBox"],
                                                                            parts["belowBlackBox"]) if v) + hint,
                                             "лимит": limit}, task)
            else:
                r = await self.ask("response", {"вопрос": (task or self._prompt(b)) + hint, "лимит": limit})
        except LLMError as e:
            self.say("error", ui("model didn't answer: {e}", e=e)[:200])
            return
        entry = self.fit(r["text"].strip(" «»\"'"), limit)
        if not entry:
            return
        self.last_entry = entry
        body = {"action": "write", "entry": entry}
        if b.get("textKey"):  # the pp4 client does this: the text key goes in the same message
            body.update(textKey=b["textKey"], val=entry)
        await self.send(body)
        self.remember(self.t("mem_pick", q=cut(task, 80), a=entry))
        self.say("answer", entry, r["ms"], question=task)

    @staticmethod
    def _post(c):
        return " | ".join(clean(c.get(k)) for k in ("header", "body", "footer", "text", "html") if clean(c.get(k)))

    async def vote_post(self, b):
        opts = [(pos, c) for pos, c in enumerate(b.get("choices") or []) if isinstance(c, dict) and not c.get("disabled")]
        if not opts:
            return
        own = [o for o in opts if self.last_entry and self.last_entry in self._post(o[1])]
        if len(opts) - len(own) >= 1:  # don't vote for our own post
            opts = [o for o in opts if o not in own]
        self.use_lang(self._prompt(b), *(self._post(c) for _, c in opts))
        texts = []
        for _, c in opts:
            m = _STI_PHOTO.search(str(c.get("thumbnail") or ""))
            photo = self.t("photo_label", desc=sti_photos().get(m.group(1), {}).get("desc", "")) if m else ""
            texts.append(self._post(c) + photo)
        idx, ms = random.randrange(len(opts)), None
        if len(opts) > 1:
            try:
                r = await self.ask("vote", {"вопрос": self._prompt(b), "варианты": numbered(texts)})
                n = re.search(r"\d+", r["text"])
                if n and 1 <= int(n.group()) <= len(opts):
                    idx, ms = int(n.group()) - 1, r["ms"]
            except LLMError as e:
                self.say("error", ui("model didn't answer, random vote: {e}", e=e)[:200])
        pos, c = opts[idx]
        await self._pause(0.3, 1.0)
        await self.send({"action": c.get("action") or "choose", "choice": pos})
        self.say("vote", cut(texts[idx], 90), ms, question=self._prompt(b))

    async def pick(self, b):
        opts = [(pos, c) for pos, c in enumerate(b.get("choices") or []) if isinstance(c, dict) and not c.get("disabled")]
        if not opts:
            return
        parts, photo = self._text(b)
        self.use_lang(self._prompt(b), *(clean(c.get("text") or c.get("html")) for _, c in opts))
        texts = [clean(c.get("text") or c.get("html")) or self.t("option_n", n=i + 1) for i, (_, c) in enumerate(opts)]
        idx, ms = random.randrange(len(opts)), None
        if len(opts) > 1:
            try:
                r = await self._ask_photo("choice", {"вопрос": self._prompt(b), "варианты": numbered(texts)}, photo,
                                          self._prompt(b)) if photo else \
                    await self.ask("choice", {"вопрос": self._prompt(b), "варианты": numbered(texts), "фото": self.t("no_photo"),
                                              "зрение": ""})
                n = re.search(r"\d+", r["text"])
                if n and 1 <= int(n.group()) <= len(opts):
                    idx, ms = int(n.group()) - 1, r["ms"]
            except LLMError as e:
                self.say("error", ui("model didn't answer, picking at random: {e}", e=e)[:200])
        pos, c = opts[idx]
        await self.send({"action": c.get("action") or "choose", "choice": pos})
        self.say("answer", texts[idx], ms, question=self._prompt(b))


GAMES = {"quiplash2": Quiplash2, "pollposition": PollPosition, "triviadeath2": TriviaDeath2,
         "survivetheinternet": SurviveTheInternet}
