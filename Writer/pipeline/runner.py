"""Универсальный исполнитель стадий. Yield'ит события для SSE.
Соглашение: строки валидатора, начинающиеся с 'WARN:', — мягкие
предупреждения; они не вызывают retry и не роняют стадию."""

import asyncio
import json
import traceback
from typing import Any, AsyncIterator

import db
from config import BUDGETS

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


async def run_stage(name: str) -> AsyncIterator[dict]:
    spec = reg.get(name)
    if spec is None:
        yield {"type": "error", "stage": name,
               "message": f"Стадия '{name}' ещё не реализована."}
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
            "stage":       name,
            "attempt":     attempt,
            "project":     project,
            "bible":       bible,
            "prev_errors": prev_errors,
        }

        try:
            result = await _run_fn(spec, ctx)
            raw = spec.validator(ctx, result) if spec.validator else []
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
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: fn(ctx))


def _preview(result: Any) -> str:
    try:
        s = json.dumps(result, ensure_ascii=False)
    except Exception:
        s = str(result)
    return s[:500]