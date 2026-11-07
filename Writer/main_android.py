"""Точка входа Writer AI Studio под Android (Chaquopy).

Вызывается из ServerService.java: callAttr("start_server", filesDir, port).

Остановка — callAttr("shutdown_server"): uvicorn допусчивает текущие
запросы и закрывает порт, сервис снимается штатно. os._exit() здесь
НЕ используется: Android видит внезапно умерший процесс и показывает
диалог «приложение закрылось с ошибкой».
"""

import os
import threading

_lock = threading.Lock()
_server = None      # uvicorn.Server — живой сервер
_thread = None      # поток, в котором он крутится


def start_server(data_dir: str, port: int = 8013) -> bool:
    """Поднимает uvicorn в фоновом потоке.

    Повторный вызов после shutdown_server() поднимает сервер заново
    (пользователь нажал «Выход» в уведомлении и снова открыл приложение).
    """
    global _server, _thread
    os.environ.setdefault("WRITER_DATA_DIR", data_dir)

    # Импорты внутри функции: config читает переменную окружения при
    # первом импорте, поэтому ставить её нужно раньше.
    import uvicorn

    from app import app

    with _lock:
        if _server is not None and not _server.should_exit:
            return True
        cfg = uvicorn.Config(app, host="127.0.0.1", port=port,
                             log_level="warning")
        _server = uvicorn.Server(cfg)
        _thread = threading.Thread(target=_server.run, daemon=True,
                                   name="uvicorn-server")
        _thread.start()
    return True


def shutdown_server() -> None:
    """Мягкая остановка: uvicorn допусчивает текущие запросы и закрывает
    порт; поток завершается сам. Процесс остаётся жить как пустой —
    Android добирает его без диалога об ошибке. Вызывается мгновенно
    (не блокирует поток, который его позвал)."""
    global _server, _thread
    with _lock:
        srv, _server = _server, None
        thr, _thread = _thread, None
    if srv is not None:
        srv.should_exit = True


def stop_server() -> None:
    """Аварийный жёсткий выход. Обычная остановка — shutdown_server()."""
    os._exit(0)
