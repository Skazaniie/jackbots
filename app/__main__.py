"""Starts the JackBOTS panel: `python -m app [--no-browser]` or the built JackBOTS.exe."""
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
    # The app object, not the string "app.main:app": this also works in the exe (PyInstaller doesn't see string imports).
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
