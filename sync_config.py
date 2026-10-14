"""config.json'a EKSIK varsayilanlari ekler, mevcut degerlere DOKUNMAZ.

Yeni bir ayar eklendiginde config.json'u silip yeniden uretmek kullanicinin
kendi degisikliklerini (favoriler, kelime setleri, ses seviyesi) siliyordu.
Bu script sadece eksikleri tamamlar.

    ./.venv/bin/python sync_config.py
"""
from __future__ import annotations

import json
import sys

from claudevoice.config import CONFIG_PATH, DEFAULTS


def merge(base: dict, cur: dict, path: str = "") -> tuple[dict, list[str]]:
    """Eksik anahtarlari varsayilandan ekler; var olanlari korur."""
    out = dict(cur)
    added: list[str] = []
    for k, v in base.items():
        where = f"{path}.{k}" if path else k
        if k not in out:
            out[k] = v
            added.append(where)
        elif isinstance(v, dict) and isinstance(out[k], dict):
            out[k], sub = merge(v, out[k], where)
            added += sub
    return out, added


def main() -> int:
    try:
        with open(CONFIG_PATH, encoding="utf-8") as fh:
            cur = json.load(fh)
    except FileNotFoundError:
        cur = {}
    except Exception as exc:
        print(f"config.json okunamadı: {exc}")
        return 1
    merged, added = merge(DEFAULTS, cur)
    if not added and cur:
        print("config.json güncel, değişiklik yok")
        return 0
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, ensure_ascii=False, indent=2)
    import os
    os.replace(tmp, CONFIG_PATH)
    print(f"{len(added)} eksik ayar eklendi:" if added else "oluşturuldu")
    for a in added[:20]:
        print(f"  + {a}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
