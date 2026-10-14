"""Drops text into Claude.app's composer and presses Enter.

The route: write to the clipboard -> bring Claude to the front -> Cmd+V ->
Enter -> return to the previous app. Setting an Electron/React composer
directly through Accessibility is unreliable because it does not update React
state; the clipboard route works across versions.

Focus moves to Claude for about 250 ms and is then handed back.
"""
from __future__ import annotations

import subprocess
import time

from AppKit import (
    NSApplicationActivateIgnoringOtherApps, NSPasteboard, NSPasteboardItem,
    NSPasteboardTypeString, NSRunningApplication, NSWorkspace,
)
from ApplicationServices import (
    AXIsProcessTrusted, AXIsProcessTrustedWithOptions,
    AXUIElementCopyAttributeValue, AXUIElementCreateApplication,
    kAXTrustedCheckOptionPrompt,
)
from Quartz import (
    CGEventCreateKeyboardEvent, CGEventPost, CGEventPostToPid,
    CGEventSetFlags, CGEventSourceCreate, CGWindowListCopyWindowInfo,
    kCGEventSourceStateCombinedSessionState,
    kCGWindowListExcludeDesktopElements, kCGWindowListOptionOnScreenOnly,
    kCGNullWindowID,
    kCGEventFlagMaskAlternate, kCGEventFlagMaskCommand,
    kCGEventFlagMaskControl, kCGEventFlagMaskShift, kCGHIDEventTap,
)

MODIFIERS = {
    "cmd": kCGEventFlagMaskCommand, "command": kCGEventFlagMaskCommand,
    "shift": kCGEventFlagMaskShift,
    "alt": kCGEventFlagMaskAlternate, "option": kCGEventFlagMaskAlternate,
    "ctrl": kCGEventFlagMaskControl, "control": kCGEventFlagMaskControl,
}

# PHYSICAL key codes for the modifiers. Some apps (Electron ones especially)
# do not look at the event flag alone and expect real flagsChanged events, so
# modifiers are also sent as separate key down/up events.
MODIFIER_KEYS = {
    kCGEventFlagMaskCommand: 55,
    kCGEventFlagMaskShift: 56,
    kCGEventFlagMaskAlternate: 58,
    kCGEventFlagMaskControl: 59,
}

KEY_V = 9
KEY_RETURN = 36

# Physical key codes (US layout). Shortcut definitions name a letter or digit
# and it is translated to a code here.
KEYCODES = {
    "a": 0, "b": 11, "c": 8, "d": 2, "e": 14, "f": 3, "g": 5, "h": 4,
    "i": 34, "j": 38, "k": 40, "l": 37, "m": 46, "n": 45, "o": 31, "p": 35,
    "q": 12, "r": 15, "s": 1, "t": 17, "u": 32, "v": 9, "w": 13, "x": 7,
    "y": 16, "z": 6,
    "0": 29, "1": 18, "2": 19, "3": 20, "4": 21, "5": 23, "6": 22,
    "7": 26, "8": 28, "9": 25,
    "space": 49, "return": 36, "enter": 36, "escape": 53, "esc": 53,
    "tab": 48, "delete": 51, "left": 123, "right": 124, "down": 125, "up": 126,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97,
    "f7": 98, "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
    ".": 47, "period": 47, ",": 43, "comma": 43, "/": 44, "slash": 44,
    ";": 41, "'": 39, "-": 27, "=": 24, "[": 33, "]": 30, "\\": 42,
    "`": 50, "backtick": 50,
}
_TEXT_ROLES = {"AXTextArea", "AXTextField", "AXComboBox", "AXWebArea"}


def ax_trusted() -> bool:
    return bool(AXIsProcessTrusted())


def ax_request() -> bool:
    """Opens the system dialog when the Accessibility permission is missing."""
    return bool(AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True}))


def _key(code: int, down: bool, command: bool = False) -> None:
    ev = CGEventCreateKeyboardEvent(None, code, down)
    if command:
        CGEventSetFlags(ev, kCGEventFlagMaskCommand)
    CGEventPost(kCGHIDEventTap, ev)


def _tap(code: int, command: bool = False) -> None:
    _key(code, True, command)
    time.sleep(0.012)
    _key(code, False, command)


class Pasteboard:
    """Backs up the clipboard (images included) and restores it."""

    def __init__(self):
        self.pb = NSPasteboard.generalPasteboard()
        self._saved: list[list[tuple[str, object]]] = []

    def save(self) -> None:
        self._saved = []
        for item in (self.pb.pasteboardItems() or []):
            entry = []
            for t in (item.types() or []):
                data = item.dataForType_(t)
                if data is not None:
                    entry.append((t, data))
            if entry:
                self._saved.append(entry)

    def set_text(self, text: str) -> None:
        self.pb.clearContents()
        self.pb.setString_forType_(text, NSPasteboardTypeString)

    def restore(self) -> None:
        if not self._saved:
            self.pb.clearContents()
            return
        items = []
        for entry in self._saved:
            it = NSPasteboardItem.alloc().init()
            for t, data in entry:
                it.setData_forType_(data, t)
            items.append(it)
        self.pb.clearContents()
        self.pb.writeObjects_(items)


class Injector:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.bundle_id = cfg.get("bundle_id", "com.anthropic.claudefordesktop")
        self.last_error: str | None = None

    # --- find the application ---
    def find_app(self, bundle_id: str | None = None) -> NSRunningApplication | None:
        bundle_id = bundle_id or self.bundle_id
        apps = NSWorkspace.sharedWorkspace().runningApplications()
        for a in apps:
            if a.bundleIdentifier() == bundle_id:
                return a
        if bundle_id != self.bundle_id:
            return None
        # If the bundle id changes, match by name (regular windowed apps only)
        for a in apps:
            name = (a.localizedName() or "").lower()
            if name == "claude" and a.activationPolicy() == 0:
                return a
        return None

    def focused_role(self, pid: int) -> str | None:
        """What is focused inside Claude? Used to notice typing outside the
        composer."""
        try:
            app = AXUIElementCreateApplication(pid)
            err, el = AXUIElementCopyAttributeValue(app, "AXFocusedUIElement", None)
            if err != 0 or el is None:
                return None
            err, role = AXUIElementCopyAttributeValue(el, "AXRole", None)
            return str(role) if err == 0 else None
        except Exception:
            return None

    def send_hotkey(self, bundle_id: str, key: str,
                    modifiers: list[str]) -> tuple[bool, str]:
        """Sends a keyboard shortcut to another application.

        The app is brought to the front briefly (a shortcut only reaches the
        focused window), the key is pressed, and focus is handed back.
        """
        if not ax_trusted():
            return False, "Erişilebilirlik izni yok"
        code = KEYCODES.get(str(key).lower())
        if code is None:
            return False, f"bilinmeyen tuş: {key}"
        flags = 0
        for m in (modifiers or []):
            f = MODIFIERS.get(str(m).lower())
            if f is None:
                return False, f"bilinmeyen değiştirici: {m}"
            flags |= f

        target = self.find_app(bundle_id)
        if target is None:
            return False, f"{bundle_id} çalışmıyor"

        # Preferred route: post the event DIRECTLY to the target process.
        # Focus never moves and the screen does not flicker. Some apps ignore
        # these events, and then the bring-to-front route below is used.
        if self.cfg.get("direct_post", True):
            if self._post_to_pid(int(target.processIdentifier()), code, flags):
                return True, "doğrudan"

        ws = NSWorkspace.sharedWorkspace()
        previous = ws.frontmostApplication()
        already = (previous is not None
                   and previous.processIdentifier() == target.processIdentifier())
        try:
            if not already and not self._bring_to_front(target):
                # IMPORTANT: do NOT send the key if it did not come to the
                # front. Otherwise the shortcut lands on whatever is in front -
                # Shift+Cmd+A once opened a tab search panel in another window.
                return False, "uygulama öne getirilemedi"
            # The PLAIN route: the event flag only. Sending the modifiers as
            # SEPARATE events was tried and broke the shortcut. Events are also
            # created with a SOURCE; source-less (None) events are not
            # interpreted correctly with modifiers in some applications.
            src = CGEventSourceCreate(kCGEventSourceStateCombinedSessionState)
            for down in (True, False):
                ev = CGEventCreateKeyboardEvent(src, code, down)
                CGEventSetFlags(ev, flags)
                CGEventPost(kCGHIDEventTap, ev)
                time.sleep(0.03)
            time.sleep(0.06)
        finally:
            if not already and self.cfg.get("restore_focus", True) and previous:
                time.sleep(0.05)
                previous.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
        return True, ""

    def capture_front(self) -> int | None:
        """The pid of whatever is in front right now.

        NSWorkspace is asked first: when a WINDOWLESS app (Finder with no open
        window, for example) comes to the front, the window list answers
        wrongly. If NSWorkspace returns nothing, the window list is used.
        """
        try:
            app = NSWorkspace.sharedWorkspace().frontmostApplication()
            if app is not None:
                return int(app.processIdentifier())
        except Exception:
            pass
        return self.frontmost_pid()

    def restore_front(self, pid: int | None, delay: float = 0.7) -> bool:
        """Hands focus back to whatever was in front before.

        Switching conversations brings Claude forward; focus is returned here
        just as it is after sending a message, otherwise the screen stays on
        Claude while you work in another window.
        """
        if pid is None:
            return False
        time.sleep(delay)                     # let the switch settle
        if self.frontmost_pid() == pid:
            return True                       # already there
        for a in NSWorkspace.sharedWorkspace().runningApplications():
            if int(a.processIdentifier()) == int(pid):
                a.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
                return True
        return False

    def _applescript_front(self, pid: int, timeout: float = 2.0) -> bool:
        """Brings an app to the front through System Events.

        NSRunningApplication.activate(...) does nothing in some Electron-based
        apps; System Events asks through a different path and can work there.
        macOS asks for the one-time "Automation" permission on first use.
        """
        script = (f'tell application "System Events" to set frontmost of '
                  f'(first process whose unix id is {pid}) to true')
        try:
            r = subprocess.run(["osascript", "-e", script], timeout=8,
                               capture_output=True, text=True)
            if r.returncode != 0:
                err = (r.stderr or "").strip()
                if err:
                    print(f"[hotkey] AppleScript: {err[:140]}")
                return False
        except Exception as exc:
            print(f"[hotkey] AppleScript çalıştırılamadı: {exc}")
            return False
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.frontmost_pid() == pid:
                return True
            time.sleep(0.05)
        return False

    @staticmethod
    def frontmost_pid() -> int | None:
        """The pid of the frontmost app - read LIVE.

        NSRunningApplication.isActive() and NSWorkspace.frontmostApplication()
        are updated through the Cocoa event loop; without a running loop they
        never refresh and falsely report "it did not come forward". The window
        list, in contrast, is fetched fresh on every call: it is ordered front
        to back, and the first normal-layer window belongs to the front app.
        """
        try:
            wins = CGWindowListCopyWindowInfo(
                kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements,
                kCGNullWindowID) or []
        except Exception:
            return None
        for w in wins:
            if w.get("kCGWindowLayer") == 0:
                return w.get("kCGWindowOwnerPID")
        return None

    def _bring_to_front(self, target, timeout: float = 2.5) -> bool:
        """Brings the app forward and verifies that it REALLY came forward."""
        pid = int(target.processIdentifier())
        target.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.frontmost_pid() == pid:
                time.sleep(self.cfg.get("hotkey_settle_ms", 180) / 1000)
                return True
            time.sleep(0.05)
        # second attempt: LaunchServices
        try:
            url = target.bundleURL()
            if url is not None:
                subprocess.run(["open", "-a", url.path()], timeout=5,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        if self._applescript_front(pid):
            time.sleep(self.cfg.get("hotkey_settle_ms", 180) / 1000)
            return True
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.frontmost_pid() == pid:
                time.sleep(self.cfg.get("hotkey_settle_ms", 180) / 1000)
                return True
            time.sleep(0.05)
        return False

    @staticmethod
    def _post_to_pid(pid: int, code: int, flags: int) -> bool:
        """Posts a key event straight to a process without moving focus."""
        try:
            accum = 0
            order = [(m, c) for m, c in MODIFIER_KEYS.items() if flags & m]
            for m, c in order:
                accum |= m
                ev = CGEventCreateKeyboardEvent(None, c, True)
                CGEventSetFlags(ev, accum)
                CGEventPostToPid(pid, ev)
                time.sleep(0.012)
            for down in (True, False):
                ev = CGEventCreateKeyboardEvent(None, code, down)
                CGEventSetFlags(ev, flags)
                CGEventPostToPid(pid, ev)
                time.sleep(0.02)
            for m, c in reversed(order):
                accum &= ~m
                ev = CGEventCreateKeyboardEvent(None, c, False)
                CGEventSetFlags(ev, accum)
                CGEventPostToPid(pid, ev)
                time.sleep(0.012)
            return True
        except Exception as exc:
            print(f"[hotkey] doğrudan gönderim başarısız: {exc}")
            return False

    # --- main operation ---
    def send(self, text: str) -> tuple[bool, str]:
        text = (text or "").strip()
        if not text:
            return False, "bos metin"
        if not ax_trusted():
            self.last_error = "Erisilebilirlik izni yok"
            return False, self.last_error

        target = self.find_app()
        if target is None:
            self.last_error = "Claude.app calismiyor"
            return False, self.last_error

        ws = NSWorkspace.sharedWorkspace()
        previous = ws.frontmostApplication()
        already_front = (previous is not None
                         and previous.processIdentifier() == target.processIdentifier())

        pb = Pasteboard()
        if self.cfg.get("restore_clipboard", True):
            pb.save()
        pb.set_text(text)

        try:
            # VERIFY it came to the front. This used to be a flat 160 ms
            # wait; when activation lagged, Cmd+V landed on whatever was in
            # front and the message never arrived (with Claude unfocused).
            if not already_front and not self._bring_to_front(target):
                return False, "Claude öne getirilemedi"

            role = self.focused_role(target.processIdentifier())
            if role and role not in _TEXT_ROLES:
                note = f"odak metin alaninda degil ({role})"
            else:
                note = ""

            _tap(KEY_V, command=True)
            time.sleep(self.cfg.get("paste_delay_ms", 90) / 1000)
            if self.cfg.get("press_enter", True):
                _tap(KEY_RETURN)
                time.sleep(0.05)
        finally:
            if (not already_front and self.cfg.get("restore_focus", True)
                    and previous is not None):
                time.sleep(0.05)
                previous.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
            if self.cfg.get("restore_clipboard", True):
                time.sleep(0.25)
                pb.restore()

        self.last_error = None
        return True, note
