"""Dumps an application's accessibility tree (development tool).

Electron/Chromium apps do not expose the tree by default; the
AXManualAccessibility attribute is turned on first.
"""
from __future__ import annotations

import json

from AppKit import NSWorkspace
from ApplicationServices import (
    AXUIElementCopyAttributeValue, AXUIElementCreateApplication,
    AXUIElementSetAttributeValue,
)


def _attr(el, name):
    err, val = AXUIElementCopyAttributeValue(el, name, None)
    return val if err == 0 else None


def find_pid(bundle_id: str) -> int | None:
    for a in NSWorkspace.sharedWorkspace().runningApplications():
        if a.bundleIdentifier() == bundle_id and a.activationPolicy() == 0:
            return int(a.processIdentifier())
    return None


def dump(bundle_id: str, max_depth: int = 22) -> dict:
    pid = find_pid(bundle_id)
    if pid is None:
        return {"error": f"{bundle_id} çalışmıyor"}
    app = AXUIElementCreateApplication(pid)
    # Electron only opens its tree once this flag is set
    AXUIElementSetAttributeValue(app, "AXManualAccessibility", True)

    found: list[dict] = []

    def walk(el, depth=0, path=""):
        if depth > max_depth:
            return
        role = str(_attr(el, "AXRole") or "")
        if role and role not in ("AXGroup", "AXSplitGroup", "AXScrollArea",
                                 "AXUnknown", "AXList", "AXLayoutArea"):
            found.append({
                "path": path, "role": role,
                "subrole": str(_attr(el, "AXSubrole") or ""),
                "title": str(_attr(el, "AXTitle") or ""),
                "desc": str(_attr(el, "AXDescription") or ""),
                "help": str(_attr(el, "AXHelp") or ""),
                "value": str(_attr(el, "AXValue"))[:40],
            })
        for i, kid in enumerate(_attr(el, "AXChildren") or []):
            walk(kid, depth + 1, f"{path}/{i}")

    wins = _attr(app, "AXWindows") or []
    for wi, w in enumerate(wins):
        walk(w, 0, f"w{wi}")
    # The menu bar extra (tray) and the app menu are scanned too: when a
    # shortcut does not work, clicking the menu item directly is the most
    # reliable path.
    for attr_name in ("AXExtrasMenuBar", "AXMenuBar"):
        bar = _attr(app, attr_name)
        if bar is not None:
            walk(bar, 0, attr_name)
    return {"pid": pid, "windows": len(wins), "elements": found}


def main(bundle_id: str, out_path: str) -> None:
    data = dump(bundle_id)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
