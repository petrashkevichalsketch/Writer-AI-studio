"""FastAPI-каркас. Этап 1-2: index, создание проекта, пайплайн + SSE."""

import json
from pathlib import Path

import pipeline_bridge
from fastapi.responses import PlainTextResponse

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse
from fastapi.responses import Response
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile

import config
import os
import shutil
import tempfile
from datetime import datetime
from starlette.background import BackgroundTask
import db
import llm
import chapter_engine
import analyzer
import state_manager
import validator
import exporter
from pipeline import run_stage

app = FastAPI(title="Autonomous AI Novelist")

BASE = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")

# ────────────────────────────────────────────────────────────────
# Старт
# ────────────────────────────────────────────────────────────────

@app.on_event("startup")
def _startup():
    db.init()


def ctx(**kw) -> dict:
    base = {
        "project":         db.get_project(),
        "settings":        db.get_settings(),
        "genres":          config.GENRES,
        "genre_labels":    config.GENRE_LABELS,
        "autonomy_levels": config.AUTONOMY_LEVELS,
        "book_formats":    config.BOOK_FORMATS,
        "default_format":  config.DEFAULT_BOOK_FORMAT,
    }
    base.update(kw)
    return base


# ────────────────────────────────────────────────────────────────
# Index / создание проекта
# ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", ctx())


@app.post("/api/project")
def api_create_project(
    theme: str = Form(...),
    genre: str = Form(...),
    setting: str = Form(...),
    conflict: str = Form(...),
    tone: str = Form(""),
    book_format: str = Form("novel"),
):
    if book_format not in config.BOOK_FORMATS:
        book_format = config.DEFAULT_BOOK_FORMAT

    db.create_project(
        theme=theme.strip(),
        genre=genre.strip(),
        setting=setting.strip(),
        conflict=conflict.strip(),
        tone=tone.strip(),
        autonomy=db.get_setting("autonomy_level", "supervised"),
        book_format=book_format,
    )
    return RedirectResponse(url="/pipeline", status_code=303)


@app.post("/api/project/reset")
def api_reset_project():
    db.wipe()
    return RedirectResponse(url="/", status_code=303)


# ────────────────────────────────────────────────────────────────
# Экраны (заглушки, наполняются по мере этапов)
# ────────────────────────────────────────────────────────────────

@app.get("/pipeline", response_class=HTMLResponse)
def pipeline(request: Request):
    return templates.TemplateResponse(
        request,
        "pipeline.html",
        ctx(
            stages=config.STAGES_PHASE1,
            stages_phase2=config.STAGES_PHASE2,
            pipeline=db.get_pipeline(),
        ),
    )


@app.get("/world", response_class=HTMLResponse)
def world(request: Request):
    bible = db.get_full_bible()
    audit = bible.get("consistency_audit")
    approved = db.get_setting("world_approved", "0") == "1"

    pipeline_map = {r["stage_name"]: r["status"] for r in db.get_pipeline()}

    stages_data = []
    for s in config.STAGES_PHASE1:
        content = bible.get(s)
        stages_data.append({
            "key":         s,
            "label":       config.STAGE_LABELS.get(s, s),
            "status":      pipeline_map.get(s, "pending"),
            "has_content": bool(content),
            "content":     json.dumps(content, ensure_ascii=False, indent=2)
                           if content is not None else "",
        })

    all_done = all(
        pipeline_map.get(s) == "done"
        for s in config.STAGES_PHASE1
    )

    return templates.TemplateResponse(
        request,
        "world.html",
        ctx(stages=stages_data, audit=audit, approved=approved, all_done=all_done),
    )


@app.post("/api/world/approve")
def api_world_approve():
    db.set_setting("world_approved", "1")
    db.set_setting("world_approved_at", db.now())
    return RedirectResponse(url="/world", status_code=303)


@app.post("/api/world/unapprove")
def api_world_unapprove():
    db.set_setting("world_approved", "0")
    return RedirectResponse(url="/world", status_code=303)


@app.post("/api/world/reset/{stage}")
def api_world_reset(stage: str):
    if stage not in config.STAGES_PHASE1:
        raise HTTPException(status_code=404, detail=f"Unknown stage {stage}")
    idx = config.ALL_STAGES.index(stage)
    to_reset = config.ALL_STAGES[idx:]
    db.reset_stages(to_reset)
    db.set_setting("world_approved", "0")
    return RedirectResponse(url="/world", status_code=303)

@app.post("/api/phase2/reset/{stage}")
def api_phase2_reset(stage: str):
    if stage not in config.STAGES_PHASE2:
        raise HTTPException(status_code=404, detail=f"Unknown phase2 stage {stage}")
    idx = config.STAGES_PHASE2.index(stage)
    to_reset = config.STAGES_PHASE2[idx:]
    db.reset_stages(to_reset)

    # Снять approve-флаги, если они касаются сбрасываемого хвоста
    if "characters" in to_reset:
        db.set_setting("characters_approved", "0")
    if "chapter_outline" in to_reset:
        db.set_setting("outline_approved", "0")

    # Куда вернуть пользователя
    if stage in ("characters", "relations"):
        return RedirectResponse(url="/characters", status_code=303)
    return RedirectResponse(url="/outline", status_code=303)


@app.get("/characters", response_class=HTMLResponse)
def characters(request: Request):
    bible = db.get_full_bible()
    chars = (bible.get("characters") or {}).get("characters") or []
    rels = (bible.get("relations") or {}).get("relations") or []
    approved = db.get_setting("characters_approved", "0") == "1"
    all_done = bool(chars) and bool(rels)
    return templates.TemplateResponse(
        request, "characters.html",
        ctx(characters=chars, relations=rels,
            approved=approved, all_done=all_done),
    )


@app.post("/api/characters/approve")
def api_characters_approve():
    db.set_setting("characters_approved", "1")
    db.set_setting("characters_approved_at", db.now())
    return RedirectResponse(url="/characters", status_code=303)


@app.post("/api/characters/unapprove")
def api_characters_unapprove():
    db.set_setting("characters_approved", "0")
    return RedirectResponse(url="/characters", status_code=303)


@app.get("/structure", response_class=HTMLResponse)
def structure(request: Request):
    bible = db.get_full_bible()
    ss = bible.get("story_structure") or {}
    return templates.TemplateResponse(
        request, "structure.html", ctx(structure=ss),
    )


@app.get("/outline", response_class=HTMLResponse)
def outline(request: Request):
    bible = db.get_full_bible()
    chapters = (bible.get("chapter_outline") or {}).get("chapters") or []
    approved = db.get_setting("outline_approved", "0") == "1"
    all_done = bool(chapters)
    return templates.TemplateResponse(
        request, "outline.html",
        ctx(chapters=chapters, approved=approved, all_done=all_done),
    )


@app.post("/api/outline/approve")
def api_outline_approve():
    db.set_setting("outline_approved", "1")
    db.set_setting("outline_approved_at", db.now())
    return RedirectResponse(url="/outline", status_code=303)


@app.post("/api/outline/unapprove")
def api_outline_unapprove():
    db.set_setting("outline_approved", "0")
    return RedirectResponse(url="/outline", status_code=303)


@app.get("/chapter/{num}", response_class=HTMLResponse)
def chapter(request: Request, num: int):
    bible = db.get_full_bible()
    outline = (bible.get("chapter_outline") or {}).get("chapters") or []
    plan = next((c for c in outline if c.get("num") == num), None)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Глава {num} не найдена в плане.")

    # карта персонажей и локаций для правой панели
    chars_map = {
        c.get("id"): c.get("name")
        for c in (bible.get("characters") or {}).get("characters", [])
    }
    locs_map = {
        l.get("id"): l.get("name")
        for l in (bible.get("geography") or {}).get("locations", [])
    }
    secrets_map = {
        s.get("id"): (s.get("truth") or "")[:160]
        for s in (bible.get("secrets") or {}).get("secrets", [])
    }

    ch = db.get_chapter(num) or {}

    patch_row = db.get_patch(num) or {}
    applied_at = patch_row.get("applied_at") if patch_row.get("accepted") else None

    return templates.TemplateResponse(
        request, "chapter.html",
        ctx(
            num=num,
            plan=plan,
            chapters=outline,
            text=ch.get("text") or "",
            status=ch.get("status") or "pending",
            word_count=ch.get("word_count") or 0,
            applied_at=applied_at,          # ← добавить
            chars_map=chars_map,
            locs_map=locs_map,
            secrets_map=secrets_map,
        ),
    )


@app.post("/api/chapter/{num}/generate")
async def api_chapter_generate(num: int):
    async def _gen():
        async for ev in chapter_engine.generate_chapter(num):
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        yield 'data: {"type":"end"}\n\n'

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/chapter/{num}/save")
async def api_chapter_save(num: int, request: Request):
    form = await request.form()
    text = form.get("text") or ""
    wc = chapter_engine.save_manual_text(num, text)
    return {"ok": True, "word_count": wc}


# ────────────────────────────────────────────────────────────────
# Settings
# ────────────────────────────────────────────────────────────────

@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    return templates.TemplateResponse(request, "settings.html", ctx())


@app.get("/help", response_class=HTMLResponse)
def help_page(request: Request):
    return templates.TemplateResponse(request, "help.html", ctx())


@app.post("/api/settings")
async def api_save_settings(request: Request):
    form = await request.form()
    allowed = set(config.DEFAULTS.keys())
    payload = {k: v for k, v in form.items() if k in allowed}
    db.save_settings(payload)
    return RedirectResponse(url="/settings", status_code=303)


# ────────────────────────────────────────────────────────────────
# Pipeline: запуск и SSE
# ────────────────────────────────────────────────────────────────

@app.post("/api/pipeline/run/{stage}")
async def api_run_stage(stage: str):
    async def _gen():
        async for ev in run_stage(stage):
            yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
        yield 'data: {"type":"end"}\n\n'

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/pipeline/state")
def api_pipeline_state():
    return {"pipeline": db.get_pipeline()}

# ────────────────────────────────────────────────────────────────
# Chapter: analyze / patch / apply / rollback
# ────────────────────────────────────────────────────────────────

@app.post("/api/chapter/{num}/analyze")
def api_chapter_analyze(num: int):
    ch = db.get_chapter(num)
    if not ch or not ch.get("text"):
        raise HTTPException(status_code=400, detail="Глава не сгенерирована.")

    bible = db.get_full_bible()
    plan = json.loads(ch.get("plan_json") or "{}")

    # 1. Вызов анализатора
    try:
        patch = analyzer.analyze(num, ch["text"], plan, bible)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analyzer error: {e}")

    # 2. Sanitize — отбрасываем несовместимые записи
    patch, warnings = analyzer.sanitize_patch(patch, bible)

    # 3. Валидатор
    raw = validator.validate_state_patch(patch, bible, num)
    errors = [x for x in raw if not x.startswith("WARN:")]
    warn2 = [x[len("WARN:"):].strip() for x in raw if x.startswith("WARN:")]
    all_warnings = (warnings or []) + warn2

    # 4. Сохраняем патч в БД В ЛЮБОМ СЛУЧАЕ — пусть пользователь решает
    db.save_patch(num, patch, applied=False)
    db.set_chapter_status(num, "analyzed")

    return {
        "ok":       len(errors) == 0,
        "patch":    patch,
        "errors":   errors,
        "warnings": all_warnings,
    }


@app.get("/api/chapter/{num}/patch")
def api_chapter_get_patch(num: int):
    p = db.get_patch(num)
    if not p:
        raise HTTPException(status_code=404, detail="Патч не найден.")
    return {
        "chapter_num": num,
        "patch":       p["patch"],
        "accepted":    bool(p["accepted"]),
        "applied_at":  p["applied_at"],
    }


@app.post("/api/chapter/{num}/apply")
def api_chapter_apply(num: int):
    p = db.get_patch(num)
    if not p:
        raise HTTPException(status_code=400, detail="Сначала запустите Analyze.")

    bible = db.get_full_bible()

    # Инициализация канона из bible — при первом apply
    latest_n, _ = db.get_latest_canon_snapshot()
    if latest_n is None:
        state_manager.init_canon_from_bible(bible)

    stats = state_manager.apply_patch(num, p["patch"])
    db.save_patch(num, p["patch"], applied=True)
    return {"ok": True, "stats": stats}


@app.post("/api/chapter/{num}/rollback")
def api_chapter_rollback(num: int):
    try:
        state_manager.rollback_to(num)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}

# ────────────────────────────────────────────────────────────────
# Book: просмотр и экспорт
# ────────────────────────────────────────────────────────────────

@app.get("/book", response_class=HTMLResponse)
def book(request: Request):
    chapters = exporter._chapters()
    stats = exporter._stats(chapters)
    meta = exporter._meta()
    return templates.TemplateResponse(
        request, "book.html",
        ctx(chapters=chapters, stats=stats, meta=meta),
    )


@app.get("/api/book/export/{fmt}")
def api_book_export(fmt: str):
    if fmt == "md":
        text = exporter.to_markdown()
        path = exporter.EXPORT_DIR / (exporter._safe_name(exporter._meta()["title"]) + ".md")
        path.write_text(text, encoding="utf-8")
        return FileResponse(path, media_type="text/markdown",
                            filename=path.name)
    if fmt == "txt":
        text = exporter.to_txt()
        path = exporter.EXPORT_DIR / (exporter._safe_name(exporter._meta()["title"]) + ".txt")
        path.write_text(text, encoding="utf-8")
        return FileResponse(path, media_type="text/plain",
                            filename=path.name)
    if fmt == "docx":
        data = exporter.to_docx_bytes()
        path = exporter.EXPORT_DIR / (exporter._safe_name(exporter._meta()["title"]) + ".docx")
        path.write_bytes(data)
        return FileResponse(
            path,
            media_type=("application/vnd.openxmlformats-officedocument"
                        ".wordprocessingml.document"),
            filename=path.name,
        )
    raise HTTPException(status_code=400, detail=f"Неизвестный формат: {fmt}")

# ────────────────────────────────────────────────────────────────
# Chapter: prompt для внешней модели + вставка текста
# ────────────────────────────────────────────────────────────────

@app.get("/api/chapter/{num}/prompt")
def api_chapter_prompt(num: int):
    try:
        return chapter_engine.build_prompt_text(num)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/chapter/{num}/prompt.txt")
def api_chapter_prompt_txt(num: int):
    try:
        data = chapter_engine.build_prompt_text(num)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return Response(
        content=data["combined"],
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition":
                f'attachment; filename="chapter_{num}_prompt.txt"',
        },
    )


@app.post("/api/chapter/{num}/paste")
async def api_chapter_paste(num: int, request: Request):
    form = await request.form()
    text = (form.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Пустой текст.")
    wc = chapter_engine.paste_external_text(num, text)
    return {"ok": True, "word_count": wc}

# ────────────────────────────────────────────────────────────────
# Backup: скачать / загрузить book.db
# ────────────────────────────────────────────────────────────────

@app.get("/api/backup/download")
def api_backup_download():
    # VACUUM INTO требует, чтобы файл-назначение не существовал.
    fd, tmp_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(tmp_path)

    try:
        with db.conn() as c:
            # Атомарный консистентный снапшот даже при активной работе.
            c.execute(f"VACUUM INTO '{tmp_path.replace(chr(92), '/')}'")
    except Exception as e:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise HTTPException(status_code=500,
                            detail=f"Не удалось создать снапшот: {e}")

    fname = f"book_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.db"
    return FileResponse(
        tmp_path,
        media_type="application/octet-stream",
        filename=fname,
        background=BackgroundTask(lambda: os.unlink(tmp_path)),
    )


@app.post("/api/backup/upload")
async def api_backup_upload(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".db"):
        raise HTTPException(status_code=400, detail="Ожидается файл .db")

    data = await file.read()
    if len(data) < 1024:
        raise HTTPException(status_code=400,
                            detail="Файл слишком мал, чтобы быть базой.")
    if not data.startswith(b"SQLite format 3\x00"):
        raise HTTPException(status_code=400,
                            detail="Файл не является SQLite-базой.")

    # Проверяем целостность и схему через временный файл
    fd, tmp_path = tempfile.mkstemp(suffix=".db")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)

        import sqlite3
        try:
            c = sqlite3.connect(tmp_path)
            res = c.execute("PRAGMA integrity_check").fetchone()
            if not res or res[0] != "ok":
                raise HTTPException(
                    status_code=400,
                    detail=f"База повреждена: {res[0] if res else 'unknown'}"
                )
            # Минимальная проверка схемы
            try:
                c.execute("SELECT COUNT(*) FROM pipeline_state").fetchone()
            except sqlite3.OperationalError:
                raise HTTPException(
                    status_code=400,
                    detail="В файле нет таблицы pipeline_state — "
                           "это не база AI-Романиста."
                )
            c.close()
        except sqlite3.DatabaseError as e:
            raise HTTPException(status_code=400,
                                detail=f"Не удалось прочитать БД: {e}")

        # Резервная копия текущей БД
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = db.DB_PATH.parent / f"book_before_restore_{ts}.db"
        if db.DB_PATH.exists():
            shutil.copy2(db.DB_PATH, backup_path)

        # Подменяем
        shutil.copy2(tmp_path, db.DB_PATH)

        return {
            "ok": True,
            "backup_path": str(backup_path),
            "message": "База восстановлена. Остановите uvicorn (Ctrl+C) "
                       "и запустите start.bat заново.",
        }
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

# ────────────────────────────────────────────────────────────────
# Pipeline bridge: промпт для внешней LLM и импорт JSON
# ────────────────────────────────────────────────────────────────

@app.get("/api/pipeline/{stage}/prompt")
def api_pipeline_prompt(stage: str):
    try:
        return pipeline_bridge.build_prompt(stage)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/pipeline/{stage}/prompt.txt")
def api_pipeline_prompt_txt(stage: str):
    try:
        data = pipeline_bridge.build_prompt(stage)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return PlainTextResponse(
        content=data["combined"],
        headers={
            "Content-Disposition":
                f'attachment; filename="{stage}_prompt.txt"',
        },
    )


@app.post("/api/pipeline/{stage}/paste")
async def api_pipeline_paste(stage: str, request: Request):
    form = await request.form()
    text = (form.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Пустой текст.")
    return pipeline_bridge.import_payload(stage, text)

# ────────────────────────────────────────────────────────────────
# LLM info
# ────────────────────────────────────────────────────────────────

@app.get("/api/llm_models")
def api_llm_models():
    return {"models": llm.list_models()}
