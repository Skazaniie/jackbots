"""Игровая сессия: набор ботов в одной комнате + лента событий для панели."""
import asyncio
import collections
import itertools
import json
import time

from . import store
from .games import GAMES, TAG_ALIASES
from .jackbox import RoomError, open_traffic_log, room_info
from .lang import GAME_TITLES, ui, ui_lang


class Hub:
    """Рассылка событий во все открытые вкладки панели."""

    def __init__(self):
        self.feed = collections.deque(maxlen=300)
        self.queues = set()
        self.once = set()
        self._ids = itertools.count(1)  # id события — ключ для панели, чтобы не перерисовывать ленту

    def emit(self, kind, **data):
        once = data.pop("once", None)
        if once:
            if once in self.once:
                return
            self.once.add(once)
        ev = {"id": next(self._ids), "type": kind, "t": time.time(), **data}
        self.feed.append(ev)
        for q in list(self.queues):
            try:
                q.put_nowait(ev)
            except asyncio.QueueFull:
                pass


class Session:
    def __init__(self, hub, llm):
        self.hub = hub
        self.llm = llm
        self.code = None
        self.tag = None
        self.host = None
        self.bots = []
        self.tasks = []
        self.traffic = None
        self.started = None
        self.game_language = "auto"  # "auto" | "en" | "ru" — фиксируется при запуске ботов

    def emit(self, kind, **data):
        self.hub.emit(kind, **data)

    @property
    def running(self):
        return bool(self.bots)

    async def start(self, code, bot_ids=None):
        await self.stop()
        code = code.strip().upper()
        settings = store.load("settings")
        info = await room_info(code, settings["ecast_host"])
        tag = TAG_ALIASES.get(info.get("appTag", ""), info.get("appTag", ""))
        titles = GAME_TITLES[ui_lang()]
        if tag not in GAMES:
            raise RoomError(ui("The game “{tag}” isn't supported yet. Supported: {games}.", tag=tag,
                               games=", ".join(titles.values())))
        if info.get("locked"):
            raise RoomError(ui("The game has already started — new players can't join. Start the bots in the lobby."))
        bots = [b for b in store.load("bots") if b.get("enabled", True) and b.get("games", {}).get(tag, True)]
        if bot_ids:
            bots = [b for b in bots if b["id"] in bot_ids]
        if not bots:
            raise RoomError(ui("No enabled bots for this game."))
        self.code, self.tag = code, tag
        self.game_language = settings.get("game_language", "auto")
        self.host = info.get("host") or settings["ecast_host"]
        self.traffic = open_traffic_log(code) if settings.get("log_traffic", True) else None
        self.hub.once.clear()
        self.started = time.time()
        self.emit("info", text=ui("Room {code}: {game}. Starting bots: {n}", code=code, game=titles[tag], n=len(bots)))
        # прогрев соединений с провайдерами — параллельно с подключением к игре
        provs = {b["provider"] for b in bots}
        for pid in provs:
            p = store.provider(pid)
            if p:
                self.tasks.append(asyncio.create_task(self.llm.warmup(p)))
        cls = GAMES[tag]
        for b in bots:
            bot = cls(self, b)
            self.bots.append(bot)
            self.tasks.append(asyncio.create_task(bot.client.run()))
            await asyncio.sleep(0.35)  # порядок входа = порядок в списке
        return self.status()

    async def stop(self):
        for b in self.bots:
            await b.client.close()
            for t in list(b.tasks):
                t.cancel()
        for t in self.tasks:
            t.cancel()
        if self.bots:
            self.emit("info", text=ui("Bots stopped"))
        self.bots, self.tasks = [], []
        if self.traffic:
            self.traffic.close()
            self.traffic = None

    async def start_game(self):
        vip = next((b for b in self.bots if b.can_start), None)
        if not vip:
            return False
        await vip.client.send(vip.start_body)
        self.emit("info", text=ui("{name} pressed “Everybody's in”", name=vip.name))
        return True

    def status(self):
        return {
            "running": self.running, "code": self.code, "tag": self.tag,
            "game": GAME_TITLES[ui_lang()].get(self.tag), "game_language": self.game_language,
            "can_start": any(b.can_start for b in self.bots),
            "room_state": self.bots[0].room.get("state") if self.bots else None,
            "bots": [{"id": b.cfg["id"], "name": b.name, "status": b.status, "thinking": b.thinking > 0,
                      "lang": b.lang, "last_ms": b.last_ms,
                      "avg_ms": int(b.stats["ms"] / b.stats["calls"]) if b.stats["calls"] else None,
                      "calls": b.stats["calls"], "errors": b.stats["errors"], "memory": b.memory[-8:],
                      "state": b.me.get("state")} for b in self.bots],
        }
