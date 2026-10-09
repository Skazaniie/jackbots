"""Мини-замена FastAPI на Starlette для Android.

На Android нет сборки pydantic-core, поэтому настоящий FastAPI не ставится. Здесь только то
подмножество API, которое использует app/main.py: маршруты get/put/post/websocket, mount,
on_event("startup"/"shutdown"), параметры пути и Body (один Body — всё тело запроса,
несколько — ключи JSON-объекта, как в FastAPI), HTTPException с ответом {"detail": ...}.
"""
import contextlib
import inspect
import json

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.websockets import WebSocket, WebSocketDisconnect

__all__ = ["Body", "FastAPI", "HTTPException", "WebSocket", "WebSocketDisconnect"]

_REQUIRED = ...


class Body:
    def __init__(self, default=_REQUIRED):
        self.default = default


class _Invalid(Exception):
    pass


def _body_params(fn):
    return [(n, p.default) for n, p in inspect.signature(fn).parameters.items() if isinstance(p.default, Body)]


async def _read_json(request):
    raw = await request.body()
    if not raw.strip():
        return _REQUIRED
    try:
        return json.loads(raw)
    except ValueError as e:
        raise _Invalid(f"request body is not JSON: {e}") from e


async def _call_args(fn, request):
    sig = inspect.signature(fn)
    kwargs = {n: v for n, v in request.path_params.items() if n in sig.parameters}
    bodies = _body_params(fn)
    if not bodies:
        return kwargs
    data = await _read_json(request)
    if len(bodies) == 1:  # как в FastAPI: единственный Body-параметр получает всё тело
        name, b = bodies[0]
        if data is _REQUIRED:
            if b.default is _REQUIRED:
                raise _Invalid(f"request body is required ({name})")
            data = b.default
        kwargs[name] = data
        return kwargs
    if data is _REQUIRED:
        data = {}
    if not isinstance(data, dict):
        raise _Invalid("request body must be a JSON object")
    for name, b in bodies:
        if name in data:
            kwargs[name] = data[name]
        elif b.default is _REQUIRED:
            raise _Invalid(f"missing field {name}")
        else:
            kwargs[name] = b.default
    return kwargs


def _endpoint(fn):
    async def handler(request: Request):
        try:
            kwargs = await _call_args(fn, request)
        except _Invalid as e:
            return JSONResponse({"detail": str(e)}, status_code=422)
        if inspect.iscoroutinefunction(fn):
            result = await fn(**kwargs)
        else:  # синхронные обработчики FastAPI тоже выполняет в пуле потоков
            result = await run_in_threadpool(fn, **kwargs)
        return result if isinstance(result, Response) else JSONResponse(result)
    handler.__name__ = getattr(fn, "__name__", "handler")
    return handler


async def _http_error(request, exc):
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))


class FastAPI(Starlette):
    def __init__(self, title="", **kwargs):
        self.title = title
        self._handlers = {"startup": [], "shutdown": []}
        super().__init__(lifespan=self._lifespan, exception_handlers={HTTPException: _http_error}, **kwargs)

    @contextlib.asynccontextmanager
    async def _lifespan(self, app):
        for fn in self._handlers["startup"]:
            await _maybe_await(fn())
        try:
            yield
        finally:
            for fn in self._handlers["shutdown"]:
                await _maybe_await(fn())

    def on_event(self, event):
        def deco(fn):
            self._handlers[event].append(fn)
            return fn
        return deco

    def _route(self, path, method, name=None):
        def deco(fn):
            self.router.add_route(path, _endpoint(fn), methods=[method], name=name or fn.__name__)
            return fn
        return deco

    def get(self, path, name=None):
        return self._route(path, "GET", name)

    def post(self, path, name=None):
        return self._route(path, "POST", name)

    def put(self, path, name=None):
        return self._route(path, "PUT", name)

    def websocket(self, path, name=None):
        def deco(fn):
            self.router.add_websocket_route(path, fn, name=name or fn.__name__)
            return fn
        return deco


async def _maybe_await(x):
    if inspect.isawaitable(x):
        await x
