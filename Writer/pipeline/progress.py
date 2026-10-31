"""Живой прогресс стадии пайплайна для «голографического экрана».

Стадия пишет сюда из worker-потока (sync-код в executor), runner
опрашивает snapshot() раз в ~0.5 с и отдаёт события stage_progress
в SSE. Стадии, которые ничего не пишут, событий не порождают.

Схема записи:
  phase_key     — 'single' | 'batch' | 'merging'
  phase_params  — параметры фазы для перевода в UI ({i},{n},{a},{b})
  chars         — символы ответа модели в текущем вызове (монотонно)
  done_chapters / total_chapters — готовые главы / весь план
  batch_chapters — глав в текущем пакете
  est_batch_chars — оценка символов текущего пакета (для доли бара)
  thinking_chars / tail — знаки размышлений и их хвост для панели
"""

import threading
import time

_TAIL = 700  # хвост размышлений, отправляемый в UI

_LOCK = threading.Lock()
_STATE: dict = {}


def start(stage: str) -> None:
    """Сбросить состояние стадии на старте попытки."""
    with _LOCK:
        _STATE[stage] = {
            "phase_key": "single",
            "phase_params": {},
            "chars": 0,
            "done_chapters": 0,
            "total_chapters": 0,
            "batch_chapters": 0,
            "est_batch_chars": 0,
            "thinking_chars": 0,
            "tail": "",
            "updated_at": time.time(),
        }


def update(stage: str, **fields) -> None:
    """Обновить поля. Отдельно копятся дельты размышлений:
    tail_delta — добавка текста, thinking_delta — добавка знаков."""
    with _LOCK:
        st = _STATE.get(stage)
        if st is None:
            return
        tail_delta = fields.pop("tail_delta", None)
        if tail_delta:
            st["tail"] = (st["tail"] + tail_delta)[-_TAIL:]
        think_delta = fields.pop("thinking_delta", None)
        if think_delta:
            st["thinking_chars"] += think_delta
        st.update(fields)
        st["updated_at"] = time.time()


def snapshot(stage: str) -> dict | None:
    with _LOCK:
        st = _STATE.get(stage)
        return dict(st) if st else None


def finish(stage: str) -> None:
    """Убрать состояние стадии (в конце попытки/стадии)."""
    with _LOCK:
        _STATE.pop(stage, None)
