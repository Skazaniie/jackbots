"""JackBOTS — ИИ-боты для Jackbox. Запуск: python -m app (или start.bat), панель http://127.0.0.1:4791"""
import asyncio
import contextlib
import time

from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import store
from .games import GAMES, TAG_ALIASES
from .jackbox import RoomError
from .lang import GAME_TITLES, detect, ui, ui_lang
from .llm import LLM, LLMError
from .prompts import LANGS, SAMPLES, VAR_ALIASES, VARS
from .session import Hub, Session

app = FastAPI(title="JackBOTS")
llm = LLM()
hub = Hub()
session = Session(hub, llm)

app.mount("/ui", StaticFiles(directory=store.WEB, html=True), name="ui")
app.mount("/assets", StaticFiles(directory=store.ASSETS), name="assets")


@app.get("/")
def index():
    return RedirectResponse("/ui/")


# ---------------- конфиги ----------------
def _samples(lang):
    """Примеры переменных для превью: и под внутренними (русскими), и под английскими именами."""
    out = {}
    for game, values in SAMPLES[lang].items():
        v = dict(values)
        v.update({en: values[ru] for en, ru in VAR_ALIASES.items() if ru in values})
        out[game] = v
    return out


@app.get("/api/meta")
def meta():
    ul = ui_lang()
    phases = {}
    for lang in LANGS:
        prompts = store.prompts(lang)
        phases[lang] = {t: [{"id": k, **{x: v[x] for x in ("title", "hint", "format")}} for k, v in prompts[t].items()]
                        for t in GAMES}
    return {"languages": LANGS, "ui_language": ul,
            "games": [{"tag": t, "title": GAME_TITLES[ul][t], "titles": {lang: GAME_TITLES[lang][t] for lang in LANGS},
                       "phases": phases[ul], "phases_by_lang": {lang: phases[lang][t] for lang in LANGS}}
                      for t in GAMES],
            "vars": VARS, "samples": {lang: _samples(lang) for lang in LANGS}}


for _name in ("providers", "bots", "prompts", "prompts_en", "settings"):
    def _mk(name):
        @app.get(f"/api/{name}", name=f"get_{name}")
        def _get():
            return store.load(name)

        @app.put(f"/api/{name}", name=f"put_{name}")
        def _put(data=Body(...)):
            store.save(name, data)
            return store.load(name)
    _mk(_name)


def _prompt_lang(lang):
    if lang not in LANGS:
        raise HTTPException(400, f"lang: {', '.join(LANGS)}")
    return lang


@app.post("/api/prompts/reset")
def reset_prompt(game: str = Body(...), phase: str = Body(...), lang: str = Body("ru")):
    name = store.PROMPT_FILES[_prompt_lang(lang)]
    p = store.load(name)
    d = store.default_prompt(lang, game, phase)
    if phase == "system":
        p["system"] = d
    elif d:
        p[game][phase] = d
    store.save(name, p)
    return p


@app.post("/api/providers/{pid}/test")
async def test_provider(pid: str, data: dict | None = Body(None)):
    p = data or store.provider(pid)
    if not p:
        raise HTTPException(404, ui("no such provider"))
    try:
        models, ms = await llm.list_models(p)
        ok, err = True, None
    except Exception as e:  # noqa: BLE001
        models, ms, ok, err = [], None, False, str(e)[:300]
    provs = store.load("providers")
    for x in provs:
        if x["id"] == pid:
            x["status"] = "ok" if ok else "bad"
            x["last_ms"] = ms or 0
    store.save("providers", provs)
    return {"ok": ok, "ms": ms, "models": models, "error": err}


def _fake_bot(bot_cfg, game, lang):
    cls = GAMES[game]
    b = cls.__new__(cls)
    b.cfg, b.memory, b.room, b.me, b.lang = bot_cfg, [], {}, {}, lang
    return b


def _bot(bot_id):
    b = next((x for x in store.load("bots") if x["id"] == bot_id), None)
    if not b:
        raise HTTPException(404, ui("no such bot"))
    return b


def _request(bot_id, game, phase, vars_, lang):
    """Сообщения для модели как в игре. lang не задан — версия игры из настроек (auto: по тексту задания)."""
    if game not in GAMES:
        raise HTTPException(400, f"game: {', '.join(GAMES)}")
    vars_ = {VAR_ALIASES.get(k, k): v for k, v in (vars_ or {}).items()}
    if lang is None:
        mode = store.load("settings").get("game_language", "auto")
        lang = mode if mode in LANGS else detect(vars_.get("вопрос"), vars_.get("варианты"), default=ui_lang())
    cfg = _bot(bot_id)
    fb = _fake_bot(cfg, game, _prompt_lang(lang))
    v = dict(SAMPLES[lang].get(game, {}))
    v.update(vars_)
    msgs, ph = fb.build_messages(phase, v)
    return cfg, msgs, ph, lang


@app.post("/api/preview")
def preview(bot_id: str = Body(...), game: str = Body(...), phase: str = Body(...), vars: dict | None = Body(None),
            lang: str | None = Body(None)):
    cfg, msgs, ph, lang = _request(bot_id, game, phase, vars, lang)
    return {"messages": msgs, "temperature": cfg.get("temperature"), "max_tokens": ph.get("max_tokens"), "lang": lang}


@app.post("/api/ask")
async def ask(bot_id: str = Body(...), game: str = Body(...), phase: str = Body(...), vars: dict | None = Body(None),
              lang: str | None = Body(None)):
    """Один запрос к модели бота — для «Теста моделей» и проверки промта."""
    cfg, msgs, ph, lang = _request(bot_id, game, phase, vars, lang)
    p = store.provider(cfg["provider"])
    if not p:
        return {"ok": False, "error": ui("provider not found")}
    try:
        r = await llm.chat(p, cfg["model"], msgs, cfg.get("temperature", 0.9), ph.get("max_tokens", 60),
                           one_line=ph.get("format") != "ranking", extra_body=cfg.get("extra_body"))
        return {"ok": True, "lang": lang, **r}
    except LLMError as e:
        return {"ok": False, "error": str(e)}


# ---------------- сессия ----------------
@app.get("/api/session")
def get_session():
    return session.status()


@app.get("/api/room/{code}")
async def room(code: str):
    from .jackbox import room_info
    try:
        info = await room_info(code, store.load("settings")["ecast_host"])
    except RoomError as e:
        raise HTTPException(404, str(e))
    tag = TAG_ALIASES.get(info.get("appTag"), info.get("appTag"))
    return {**info, "appTag": tag, "supported": tag in GAMES, "title": GAME_TITLES[ui_lang()].get(tag)}


@app.post("/api/session/start")
async def start(code: str = Body(...), bot_ids: list[str] | None = Body(None)):
    try:
        return await session.start(code, bot_ids)
    except RoomError as e:
        raise HTTPException(400, str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"{type(e).__name__}: {e}")


@app.post("/api/session/stop")
async def stop():
    await session.stop()
    return session.status()


@app.post("/api/session/startgame")
async def start_game():
    ok = await session.start_game()
    if not ok:
        raise HTTPException(400, ui("No bot can start the game (VIP is the first player to join, and the minimum number "
                                     "of players is needed)."))
    return {"ok": True}


@app.websocket("/ws")
async def ws(sock: WebSocket):
    await sock.accept()
    q = asyncio.Queue(maxsize=500)
    hub.queues.add(q)
    try:
        await sock.send_json({"type": "hello", "feed": list(hub.feed)[-60:], "session": session.status()})
        last = 0.0
        while True:
            with contextlib.suppress(asyncio.TimeoutError):
                ev = await asyncio.wait_for(q.get(), timeout=1.0)
                await sock.send_json(ev)
            if time.time() - last > 1.0:
                last = time.time()
                await sock.send_json({"type": "session", "session": session.status()})
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        hub.queues.discard(q)


@app.on_event("shutdown")
async def _shutdown():
    await session.stop()
    await llm.close()
