# AI Novelist — Autonomous Literary Novel Generator (25+ Genres)

**Bilingual project (RU/EN).** The interface language switches between Russian
and English with one click — the **en | ru** buttons in the header, next to the
logo. Every label on every page is translated: navigation, buttons, wizards,
dialogs, toasts, pipeline logs, validator messages, and the built-in Help.

The **book language** — Russian or English — is chosen when the project is
created and uses a dedicated 21-prompt set (world stages, characters, chapters,
clarifying questions, audit). English books are written with English dramaturgy
rules and dialogue typography, not translated instructions. One person can keep
a Russian project and an English project side by side.

A local FastAPI web application that **autonomously writes a complete
15–20-chapter novel** through a local or cloud LLM.

The user fills in **five fields** — theme, genre, setting and era, central
conflict, tone — and picks the book language. Everything else the app builds
itself:

- **World** — core, rules, history, institutions, geography, economy, society,
  culture, conflicts, secrets. With a consistency audit.
- **Characters** — 3–7 characters tied to the central conflict, a relationship
  network, plot structure, and a chapter outline.
- **Chapters** — generated one by one, streamed, ~3,000 words each.

After every chapter the app extracts a **canon patch** (what changed in the
world) — review the diff, then apply it or roll it back.

- **Export** — the whole book to .md, .txt, .docx. Headings and metadata follow
  the book language (`Chapter N.` / `Глава N.`).

## The principle

The LLM is a processor. Memory is external, in SQLite. Every model call is
stateless; the entire context is assembled programmatically. This keeps the
story consistent across 400,000+ characters without relying on the model's
"memory."

## Requirements

- **Python** 3.10+
- **LLM** — any OpenAI-compatible one:
  - Local via [Unsloth](https://github.com/unslothai/unsloth),
    [vLLM](https://github.com/vllm-project/vllm), [Ollama](https://ollama.com)
  - Or cloud: OpenAI, DeepSeek, OpenRouter, Groq, Mistral, Google Gemini
- **RAM** — from 8 GB (for a local 7B model)
- **OS** — Windows, Linux, macOS

### Model recommendations
Not all models are equally suited for literary prose. Tested in practice:

| Model | For the pipeline (JSON) | For chapters (prose) |
|---|---|---|
| Gemma-4-31B + Claude-Opus-distill | ✅ | ✅✅✅ good prose |
| Qwen3.6-35B-A3B (MoE) | ✅ | ⚠️ prone to loops and repetition |
| Gemma-4-26B-A4B (MoE) | ✅ | ⚠️ prone to loops and repetition |
| **DeepSeek-V4.1** (cloud) | ✅✅✅ | ✅✅ average prose |
| Claude Sonnet 5.5 (via OpenRouter) | ✅✅✅ | ✅✅✅ excellent prose |

**Why MoE models don't work for chapters:**
They are Mixture-of-Experts models with ~3B active parameters. Computationally
efficient, but when generating long texts they tend to loop — repeating the
same phrase, losing the narrative thread, producing a short fragment instead of
a full chapter. They degrade on long contexts (3,000+ words).

**Why Gemma + Opus-distill writes well:**
It is a distillation of Claude Opus — a model trained on Anthropic's literary
texts. Even compressed to 31B, it keeps its distinctive "voice": dense prose,
natural dialogue, no filler, no loops.

**Practical advice:**
For the pipeline stages (world_core … chapter_outline) — a fast model with
reliable JSON: Qwen 32B, DeepSeek.
For chapter generation — a model with a literary specialization:
Gemma-Opus-distill, Claude Sonnet, Claude Opus — expert level.
Do not use MoE models for prose generation — they produce short fragments and
loops.

**How to test a model before a big project:**
Create a short story (1–3 chapters, ~15 minutes) — that's the quick test. If
the model stumbles on a short story, don't waste two hours of your time on a
novel with it.

## Changelog

### v0.5.6 — 2026-10-27
**Bilingual interface.** The en | ru switch in the header translates about 800
strings across the whole app — including validator messages (translated via
template matching), server errors, wizard dialogs, and the full Help page. The
choice is global and independent of the book language.

**English books.** A dedicated set of 22 English prompts with English dialogue
typography (double quotes, inline attribution) and a contemporary
commercial-fiction style benchmark. Continuation requests, default chapter
titles, and export headings follow the book language.

**Reliability.** Cache-busting for static assets (`?v=`), a
`/api/debug/build` diagnostic endpoint, and a build stamp in the footer — you
always know which version of the code is running.

### v0.1.5 — 2026-10-06
**Save the Cat dramaturgy.** The global novel structure is now built from 15
beats (opening image, midpoint, all is lost, finale, etc.). Every chapter knows
which function it carries.

Previously the model could stretch the story over 18 chapters and deliver three
endings in a row. Now it has a rigid skeleton.

**Bridge to external models**
On the /pipeline page, next to the story_structure and chapter_outline stages,
two buttons appeared:

- 📋 **Prompt** — opens the stage's ready-made prompt with the full context of
  the world, characters, and structure. Copied in one click, pasted into a chat
  with a powerful model (Sonnet 5.5, GPT-5, DeepSeek-R3, any OpenAI-compatible
  one).
- 📥 **Paste JSON** — takes the model's response, runs it through the
  validator, and saves it to the DB. If the JSON fails validation, it shows the
  list of errors to fix.

This allows you to do the planning in a strong model and the chapter generation
in a local one — or do everything in a strong model (recommended). No CLI, no
scripts — straight from the browser.


<img width="3766" height="2010" alt="Снимок экрана 2026-10-25 200106" src="https://github.com/user-attachments/assets/2a2dfa30-97f1-44ea-81f9-71d4fe991987" />

## Quick Start

git clone https://github.com/petrashkevichalsketch/Writer-AI-studio.git

cd ai-novelist


python -m venv .venv \&\& source .venv/bin/activate

pip install -r requirements.txt

python -m uvicorn app:app --host 127.0.0.1 --port 8013




## Support the Project 
* **USDT (TRC-20):** TP3cZ85VLW5SpM3WiUsXK8avEHNLZ41Wdq
* 
* 4916 9897 2122 5562  9112 3801 3710 1608

