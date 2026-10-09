"""Запуск панели JackBOTS: `python -m app [--no-browser]` или собранный JackBOTS.exe."""
import sys
import threading
import webbrowser

import uvicorn

from app.main import app

HOST, PORT = "127.0.0.1", 4791


def main():
    if "--no-browser" not in sys.argv:
        threading.Timer(1.5, webbrowser.open, args=(f"http://{HOST}:{PORT}/",)).start()
    print(f"JackBOTS: panel at http://{HOST}:{PORT}/ (close this window to stop)", flush=True)
    # Объект app, а не строка "app.main:app": так работает и в exe (PyInstaller не видит строковых импортов).
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
