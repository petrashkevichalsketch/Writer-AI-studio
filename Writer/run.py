"""Точка входа WriterAIStudio.

Поведение при повторном запуске: если сервер уже слушает порт,
не поднимать второй экземпляр — просто открыть браузер и выйти.
"""

import logging
import logging.handlers
import os
import socket
import sys
import threading
import time
import webbrowser

import uvicorn

import config
from app import app

HOST = config.HOST
PORT = config.PORT
URL = f"http://{HOST}:{PORT}"


def _setup_logging() -> None:
    """Логи в DATA_DIR/logs/app.log с ротацией — не зависят от .bat-обёрток,
    которых нет у собранного exe."""
    try:
        config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            config.LOG_DIR / "app.log",
            maxBytes=1_000_000, backupCount=3, encoding="utf-8",
        )
    except OSError:
        handler = logging.StreamHandler()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[handler],
    )


def _port_in_use(port: int) -> bool:
    """True, если порт уже занят (значит, приложение уже запущено)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((HOST, port)) == 0


def _open_browser(delay: float = 3.0) -> None:
    time.sleep(delay)
    webbrowser.open(URL)


def _tray_loop() -> None:
    """Иконка в трее: виден факт работы приложения + пункт «Выйти».

    При console-mode=disable у exe нет окна, которое можно закрыть,
    поэтому без трея пользователь не сможет остановить сервер иначе,
    чем через диспетчер задач.
    """
    try:
        import pystray
        from PIL import Image
    except Exception:  # noqa: BLE001 — трей не критичен, без него тоже работаем
        return

    try:
        icon_image = Image.open(os.path.join(os.path.dirname(__file__), "Book.ico"))
    except Exception:  # noqa: BLE001 — нет иконки рядом с exe
        return

    def _quit(icon, item):  # noqa: ANN001
        icon.stop()
        os._exit(0)

    try:
        pystray.Icon(
            "WriterAIStudio",
            icon_image,
            "Writer AI Studio",
            menu=pystray.Menu(pystray.MenuItem("Выход", _quit)),
        ).run()
    except Exception:  # noqa: BLE001 — трей не критичен
        pass


if __name__ == "__main__":
    _setup_logging()

    if _port_in_use(PORT):
        # Уже запущено: не дублируем процесс, просто показываем UI.
        _open_browser(delay=0)
        sys.exit(0)

    threading.Thread(target=_open_browser, daemon=True).start()
    threading.Thread(target=_tray_loop, daemon=True).start()

    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="warning",
        log_config=None,  # не перезаписывать наш RotatingFileHandler
    )
