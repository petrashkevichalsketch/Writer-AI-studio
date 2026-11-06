"""Точка входа Writer AI Studio под Android (Chaquopy).

Вызывается из ServerService.java: callAttr("start_server", filesDir, port).

Порядок важен: WRITER_DATA_DIR выставляется ДО первого импорта config —
он фиксирует DATA_DIR (SQLite, экспорты, логи) в файловом хранилище
приложения. Трей/браузер десктопного run.py здесь не нужны: их роль
играют foreground-сервис и уведомление Android.
"""

import os
import threading

_started = threading.Event()


def start_server(data_dir: str, port: int = 8013) -> bool:
    """Поднимает uvicorn с приложением в фоновом потоке.

    Возвращает True сразу (Kotlin-поток не блокируем); готовность
    сервера Service определяет сам, опрашивая порт.
    """
    os.environ["WRITER_DATA_DIR"] = data_dir

    # Импорты внутри функции: config читает переменную окружения при
    # первом импорте, поэтому ставить её нужно раньше.
    import uvicorn

    from app import app

    if _started.is_set():
        return True

    # На Android нет uvloop/httptools — uvicorn сам откатится на
    # чистые asyncio/h11, если их не устанавливать.
    threading.Thread(
        target=uvicorn.run,
        kwargs={
            "app": app,
            "host": "127.0.0.1",
            "port": port,
            "log_level": "warning",
        },
        daemon=True,
        name="uvicorn-server",
    ).start()
    _started.set()
    return True


def stop_server() -> None:
    """Полный останов процесса — по кнопке «Выход» в уведомлении."""
    os._exit(0)
