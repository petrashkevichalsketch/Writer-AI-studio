"""Универсальный исполнитель стадий. Yield'ит события для SSE.
Соглашение: строки валидатора, начинающиеся с 'WARN:', — мягкие
предупреждения; они не вызывают retry и не роняют стадию."""

import asyncio
import json
import traceback
from typing import Any, AsyncIterator

import db
from config import BUDGETS
from translations import translate, trf as _t

from . import progress as stage_progress
from . import registry as reg

WARN_PREFIX = "WARN:"


def _split_warnings(items: list[str]) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    for x in items or []:
        if isinstance(x, str) and x.startswith(WARN_PREFIX):
            warnings.append(x[len(WARN_PREFIX):].strip())
        else:
            errors.append(x)
    return errors, warnings


async def run_stage(name: str,
                   qa_answers: list[dict] | None = None
                   ) -> AsyncIterator[dict]:
    spec = reg.get(name)
    if spec is None:
        yield {"type": "error", "stage": name,
               "message": _t("Стадия '{name}' ещё не реализована.", name=name)}
        return

    db.set_stage(name, "running")
    yield {"type": "stage_started", "stage": name}

    budget = BUDGETS.get(name, {"retry": 3})
    attempts = max(1, int(budget.get("retry", 3)))

    project = db.get_project()
    bible = db.get_full_bible()
    prev_errors: list[str] = []

    for attempt in range(1, attempts + 1):
        yield {"type": "attempt", "stage": name,
               "attempt": attempt, "max": attempts}

        ctx = {
            "stage":        name,
            "attempt":      attempt,
            "project":      project,
            "bible":        bible,
            "prev_errors":  prev_errors,
            "user_answers": qa_answers or [],
        }

        try:
            # fn исполняется фоном; пока она работает, опрашиваем
            # progress-store и отдаём «голографический экран» в SSE
            # (стадии, которые не пишут прогресс, событий не дают).
            exec_task = asyncio.ensure_future(_run_fn(spec, ctx))
            try:
                while not exec_task.done():
                    await asyncio.sleep(0.5)
                    snap = stage_progress.snapshot(name)
                    if not snap:
                        continue
                    est = snap.get("est_batch_chars") or 0
                    n_ch = snap.get("batch_chapters") or 0
                    done = snap.get("done_chapters", 0)
                    chars = snap.get("chars", 0)
                    if est > 0 and n_ch > 0:
                        value = done + min(chars / est, 1.0) * n_ch
                    else:
                        value = float(done)
                    params = snap.get("phase_params") or {}
                    yield {"type": "stage_progress", "stage": name,
                           "phase_key": snap.get("phase_key"),
                           "phase_params": params,
                           "chars": chars,
                           "value": round(value, 2),
                           "target": snap.get("total_chapters", 0),
                           "done_chapters": done,
                           "batch": params.get("i", 0),
                           "batches": params.get("n", 0),
                           "thinking_chars": snap.get("thinking_chars", 0),
                           "tail": snap.get("tail", "")}
            finally:
                stage_progress.finish(name)
            result = await exec_task
            raw = spec.validator(ctx, result) if spec.validator else []
            # Сообщения валидатора уходят клиенту на языке UI
            # (префикс "WARN: " сохраняется; prev_errors для retry — тоже UI).
            raw = [translate(x) if isinstance(x, str) else x for x in raw]
            errors, warnings = _split_warnings(raw)

            if warnings:
                yield {"type": "warning", "stage": name,
                       "attempt": attempt, "warnings": warnings}

            if errors:
                prev_errors = errors
                yield {"type": "validation_failed", "stage": name,
                       "attempt": attempt, "errors": errors}
                if attempt < attempts:
                    await asyncio.sleep(0.3)
                    continue
                db.set_stage(name, "failed", error="; ".join(errors))
                yield {"type": "stage_failed", "stage": name, "errors": errors}
                return

            db.save_bible_stage(name, result, validated=True)
            db.set_stage(name, "done")
            # Вариант «локальная модель» — для сравнения с сильной моделью.
            from pipeline_bridge import SUPPORTED_STAGES
            if name in SUPPORTED_STAGES:
                try:
                    db.save_stage_variant(name, "local", result,
                                          is_active=True)
                except Exception:
                    pass  # варианты — вспомогательная функциональность
            yield {"type": "stage_done", "stage": name,
                   "preview": _preview(result),
                   "warnings": warnings}
            return

        except Exception as e:
            yield {"type": "exception", "stage": name, "attempt": attempt,
                   "message": str(e), "traceback": traceback.format_exc()}
            if attempt < attempts:
                await asyncio.sleep(1)
                continue
            db.set_stage(name, "failed", error=str(e))
            yield {"type": "stage_failed", "stage": name, "errors": [str(e)]}
            return


async def _run_fn(spec: reg.StageSpec, ctx: dict) -> Any:
    fn = spec.fn
    if asyncio.iscoroutinefunction(fn):
        return await fn(ctx)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: fn(ctx))


def _preview(result: Any) -> str:
    try:
        s = json.dumps(result, ensure_ascii=False)
    except Exception:
        s = str(result)
    return s[:500]