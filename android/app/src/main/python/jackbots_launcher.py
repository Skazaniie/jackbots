"""Запуск панели JackBOTS на Android: тот же app/ что и на ПК, но FastAPI заменён шимом на Starlette."""
import os
import sys
import traceback

_server = None


def run(root, port):
    """Блокирует поток, пока сервер работает. root — распакованная папка с app/, web/, assets/, config/."""
    global _server
    import uvicorn

    os.makedirs(os.path.join(root, "logs"), exist_ok=True)
    log = open(os.path.join(root, "logs", "server.log"), "a", encoding="utf-8", buffering=1)
    sys.stderr = log  # ошибки сервера пишем в файл: logcat на телефоне пользователю недоступен
    if root not in sys.path:
        sys.path.insert(0, root)
    os.chdir(root)
    try:
        _server = uvicorn.Server(uvicorn.Config("app.main:app", host="127.0.0.1", port=int(port),
                                                log_level="warning"))
        _server.run()
    except BaseException:
        traceback.print_exc(file=log)
        raise


def stop():
    if _server is not None:
        _server.should_exit = True
