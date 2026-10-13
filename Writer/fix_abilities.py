"""Одноразовая правка: дополнить descriptions у способностей в characters."""

import json
import db


FIXES = {
    "CH1": {
        "визуализация кода": {
            "description": "видит структуру заклинаний как код на ментальном экране",
        },
    },
}


def fix():
    with db.conn() as c:
        for cid, abilities_fix in FIXES.items():
            row = c.execute(
                "SELECT current_state_json FROM characters WHERE id = ?",
                (cid,),
            ).fetchone()
            if not row:
                print(f"{cid}: не найден в БД, пропуск.")
                continue

            try:
                state = json.loads(row["current_state_json"] or "{}")
            except Exception:
                state = {}

            abilities = state.get("abilities") or {}
            for name, patch in abilities_fix.items():
                if name not in abilities:
                    print(f"{cid}.{name}: способность не найдена, пропуск.")
                    continue
                for k, v in patch.items():
                    abilities[name][k] = v
                print(f"{cid}.{name}: обновлено {list(patch.keys())}.")

            state["abilities"] = abilities
            c.execute(
                "UPDATE characters SET current_state_json = ? WHERE id = ?",
                (json.dumps(state, ensure_ascii=False), cid),
            )

    print("\nГотово. Перезапусти uvicorn.")


if __name__ == "__main__":
    fix()