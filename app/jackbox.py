"""Jackbox ecast client (api/v2). PP3/PP4 games also go through it with bc:room / bc:customer:<id> keys.

The bot sees only what the game sends to a regular player's phone: the same data as jackbox.tv.
"""
import asyncio
import json
import time
import uuid
from urllib.parse import urlencode

import httpx
from websockets.asyncio.client import connect

from . import store
from .lang import ui


class RoomError(Exception):
    pass


async def room_info(code, host):
    async with httpx.AsyncClient(timeout=8) as c:
        r = await c.get(f"https://{host}/api/v2/rooms/{code.upper()}")
    if r.status_code == 404:
        raise RoomError(ui("Room not found. Check the code on the game screen."))
    r.raise_for_status()
    body = r.json().get("body") or {}
    return body


def stable_user_id(code, bot_id):
    """The same user-id for a bot in the room: on restart the game reconnects
    the previous player (with their VIP and character) instead of creating a "ghost" with a new name."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"jackbox-ai:{code.upper()}:{bot_id}"))


class EcastClient:
    def __init__(self, code, name, host, on_entity, on_status, traffic_log=None, user_id=None):
        self.code = code.upper()
        self.name = name[:12]
        self.host = host
        self.on_entity = on_entity   # async (key, value)
        self.on_status = on_status   # async (status, detail)
        self.user_id = user_id or str(uuid.uuid4())
        self.pid = None
        self.seq = 0
        self.ws = None
        self.closing = False
        self.welcomed = False
        self.log = traffic_log

    def _url(self):
        q = urlencode({"role": "player", "name": self.name, "format": "json", "user-id": self.user_id})
        return f"wss://{self.host}/api/v2/rooms/{self.code}/play?{q}"

    async def run(self):
        tries = 0
        while not self.closing:
            try:
                async with connect(self._url(), subprotocols=["ecast-v0"], open_timeout=10,
                                   additional_headers={"Origin": "https://jackbox.tv"},
                                   ping_interval=20, max_size=8 * 2 ** 20) as ws:
                    self.ws = ws
                    self.welcomed = False
                    async for raw in ws:
                        await self._handle(raw)
                        if self.welcomed:
                            # reset the counter only after a real join: otherwise a server that
                            # lets you in and kicks you right away (full room) would give endless retries
                            tries = 0
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                if self.closing:
                    break
                tries += 1
                await self.on_status("error", f"{type(e).__name__}: {e}"[:200])
                if tries > 5:
                    await self.on_status("gone", ui("couldn't reconnect"))
                    return
                await asyncio.sleep(min(5, tries))
                continue
            if self.closing:
                break
            await self.on_status("reconnect", ui("connection closed, reconnecting"))
            await asyncio.sleep(1)
            tries += 1
            if tries > 5:
                await self.on_status("gone", ui("couldn't reconnect"))
                return
        self.ws = None

    async def close(self):
        self.closing = True
        if self.ws:
            try:
                await self.ws.close()
            except Exception:  # noqa: BLE001
                pass

    def _trace(self, direction, payload):
        if self.log:
            self.log.write(json.dumps({"t": round(time.time(), 3), "who": self.name, "dir": direction,
                                       "msg": payload}, ensure_ascii=False) + "\n")
            self.log.flush()

    async def _handle(self, raw):
        try:
            msg = json.loads(raw)
        except ValueError:
            return
        self._trace("in", msg)
        op, res = msg.get("opcode"), msg.get("result") or {}
        if op == "client/welcome":
            self.pid = res.get("id")
            self.welcomed = True
            await self.on_status("joined", f"id {self.pid}")
            ents = res.get("entities") or {}
            for key, ent in ents.items():
                val = _entity_value(ent)
                if val is not None:
                    await self.on_entity(key, val)
        elif op in ("object", "text"):
            val = res.get("val", res.get("text"))  # text entities come in the text field
            if isinstance(val, str):
                try:
                    val = json.loads(val)
                except ValueError:
                    pass
            await self.on_entity(res.get("key", ""), val)
        elif op == "error":
            await self.on_status("error", str(res.get("msg") or res)[:200])
        elif op in ("client/kicked", "room/exit"):
            await self.on_status("gone", op)
            self.closing = True

    async def send(self, body):
        """Same as client.send('SendMessageToRoomOwner', body) in jackbox.tv."""
        if self.pid is None:
            return False
        return await self._op("client/send", {"from": self.pid, "to": 1, "body": body})

    async def update_text(self, key, val):
        """Same as client.updateText(): the game reads the answer from a text entity (textKey in the state)."""
        return await self._op("text/update", {"key": key, "val": val})

    async def update_object(self, key, val):
        """Same as client.updateObject() (objectKey in the state, e.g. a drawing)."""
        return await self._op("object/update", {"key": key, "val": val})

    async def _op(self, opcode, params):
        if not self.ws or self.pid is None:
            return False
        self.seq += 1
        msg = {"seq": self.seq, "opcode": opcode, "params": params}
        self._trace("out", msg)
        await self.ws.send(json.dumps(msg, ensure_ascii=False))
        return True


def _entity_value(ent):
    # format: ["object", {"key":..., "val":..., "version":...}, {...}] or a dict right away
    if isinstance(ent, list):
        ent = next((x for x in ent if isinstance(x, dict) and ("val" in x or "text" in x)), None)
    if isinstance(ent, dict) and ("val" in ent or "text" in ent):
        v = ent["val"] if "val" in ent else ent["text"]
        if isinstance(v, str):
            try:
                return json.loads(v)
            except ValueError:
                return v
        return v
    return None


def open_traffic_log(code):
    store.LOGS.mkdir(parents=True, exist_ok=True)
    return open(store.LOGS / f"traffic-{time.strftime('%Y%m%d-%H%M%S')}-{code}.jsonl", "a", encoding="utf-8")
