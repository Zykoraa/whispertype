"""Text injection engine for Linux / Hyprland via direct kernel uinput and Wayland."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
from typing import Dict, Optional, Tuple
import evdev

KEY = evdev.ecodes

# Standard US QWERTY mapping: character -> (evdev_keycode, shift_required)
CHAR_MAP: Dict[str, Tuple[int, bool]] = {
    'a': (KEY.KEY_A, False), 'b': (KEY.KEY_B, False), 'c': (KEY.KEY_C, False),
    'd': (KEY.KEY_D, False), 'e': (KEY.KEY_E, False), 'f': (KEY.KEY_F, False),
    'g': (KEY.KEY_G, False), 'h': (KEY.KEY_H, False), 'i': (KEY.KEY_I, False),
    'j': (KEY.KEY_J, False), 'k': (KEY.KEY_K, False), 'l': (KEY.KEY_L, False),
    'm': (KEY.KEY_M, False), 'n': (KEY.KEY_N, False), 'o': (KEY.KEY_O, False),
    'p': (KEY.KEY_P, False), 'q': (KEY.KEY_Q, False), 'r': (KEY.KEY_R, False),
    's': (KEY.KEY_S, False), 't': (KEY.KEY_T, False), 'u': (KEY.KEY_U, False),
    'v': (KEY.KEY_V, False), 'w': (KEY.KEY_W, False), 'x': (KEY.KEY_X, False),
    'y': (KEY.KEY_Y, False), 'z': (KEY.KEY_Z, False),
    'A': (KEY.KEY_A, True),  'B': (KEY.KEY_B, True),  'C': (KEY.KEY_C, True),
    'D': (KEY.KEY_D, True),  'E': (KEY.KEY_E, True),  'F': (KEY.KEY_F, True),
    'G': (KEY.KEY_G, True),  'H': (KEY.KEY_H, True),  'I': (KEY.KEY_I, True),
    'J': (KEY.KEY_J, True),  'K': (KEY.KEY_K, True),  'L': (KEY.KEY_L, True),
    'M': (KEY.KEY_M, True),  'N': (KEY.KEY_N, True),  'O': (KEY.KEY_O, True),
    'P': (KEY.KEY_P, True),  'Q': (KEY.KEY_Q, True),  'R': (KEY.KEY_R, True),
    'S': (KEY.KEY_S, True),  'T': (KEY.KEY_T, True),  'U': (KEY.KEY_U, True),
    'V': (KEY.KEY_V, True),  'W': (KEY.KEY_W, True),  'X': (KEY.KEY_X, True),
    'Y': (KEY.KEY_Y, True),  'Z': (KEY.KEY_Z, True),
    '0': (KEY.KEY_0, False), '1': (KEY.KEY_1, False), '2': (KEY.KEY_2, False),
    '3': (KEY.KEY_3, False), '4': (KEY.KEY_4, False), '5': (KEY.KEY_5, False),
    '6': (KEY.KEY_6, False), '7': (KEY.KEY_7, False), '8': (KEY.KEY_8, False),
    '9': (KEY.KEY_9, False),
    '!': (KEY.KEY_1, True),  '@': (KEY.KEY_2, True),  '#': (KEY.KEY_3, True),
    '$': (KEY.KEY_4, True),  '%': (KEY.KEY_5, True),  '^': (KEY.KEY_6, True),
    '&': (KEY.KEY_7, True),  '*': (KEY.KEY_8, True),  '(': (KEY.KEY_9, True),
    ')': (KEY.KEY_0, True),  '-': (KEY.KEY_MINUS, False), '_': (KEY.KEY_MINUS, True),
    '=': (KEY.KEY_EQUAL, False), '+': (KEY.KEY_EQUAL, True),
    '[': (KEY.KEY_LEFTBRACE, False), '{': (KEY.KEY_LEFTBRACE, True),
    ']': (KEY.KEY_RIGHTBRACE, False), '}': (KEY.KEY_RIGHTBRACE, True),
    '\\': (KEY.KEY_BACKSLASH, False), '|': (KEY.KEY_BACKSLASH, True),
    ';': (KEY.KEY_SEMICOLON, False), ':': (KEY.KEY_SEMICOLON, True),
    "'": (KEY.KEY_APOSTROPHE, False), '"': (KEY.KEY_APOSTROPHE, True),
    ',': (KEY.KEY_COMMA, False), '<': (KEY.KEY_COMMA, True),
    '.': (KEY.KEY_DOT, False),   '>': (KEY.KEY_DOT, True),
    '/': (KEY.KEY_SLASH, False), '?': (KEY.KEY_SLASH, True),
    ' ': (KEY.KEY_SPACE, False),
    '\t': (KEY.KEY_TAB, False),
    '\n': (KEY.KEY_ENTER, False),
    '`': (KEY.KEY_GRAVE, False), '~': (KEY.KEY_GRAVE, True),
}

TERMINAL_CLASSES = {
    "kitty",
    "alacritty",
    "foot",
    "wezterm",
    "ghostty",
    "konsole",
    "gnome-terminal",
    "xfce4-terminal",
    "xterm",
    "urxvt",
}


def _get_wayland_env() -> Dict[str, str]:
    """Ensure WAYLAND_DISPLAY and XDG_RUNTIME_DIR are populated for compositor tools."""
    env = dict(os.environ)
    uid = os.getuid()
    runtime_dir = Path(env.get("XDG_RUNTIME_DIR", f"/run/user/{uid}"))
    env["XDG_RUNTIME_DIR"] = str(runtime_dir)

    if "WAYLAND_DISPLAY" not in env or not env["WAYLAND_DISPLAY"]:
        if runtime_dir.exists():
            for sock in sorted(runtime_dir.glob("wayland-*")):
                if sock.is_socket() and not sock.name.endswith(".lock"):
                    env["WAYLAND_DISPLAY"] = sock.name
                    break
    return env


def _get_active_window_class() -> str:
    """Query Hyprland for currently focused window class."""
    try:
        env = _get_wayland_env()
        res = subprocess.run(
            ["hyprctl", "activewindow", "-j"],
            capture_output=True,
            text=True,
            timeout=0.1,
            env=env,
        )
        if res.returncode == 0 and res.stdout:
            data = json.loads(res.stdout)
            return (data.get("class") or data.get("initialClass") or "").lower()
    except Exception:
        pass
    return ""


class TextInjector:
    def __init__(
        self,
        method: str = "uinput",
        wtype_delay_ms: int = 0,
        paste_threshold: int = 120,
        restore_clipboard: bool = True,
    ):
        self.method = method
        self.wtype_delay_ms = max(0, wtype_delay_ms)
        self.paste_threshold = paste_threshold
        self.restore_clipboard = restore_clipboard
        self._has_wl_copy = shutil.which("wl-copy") is not None
        self._uinput: Optional[evdev.UInput] = None
        self._last_injected_length: int = 0
        self._init_uinput()

    def _init_uinput(self):
        try:
            capabilities = {
                evdev.ecodes.EV_KEY: list(range(1, 255))
            }
            self._uinput = evdev.UInput(
                events=capabilities,
                name="WhisperType Virtual Keyboard",
            )
            time.sleep(0.1)
        except Exception as e:
            print(f"[WhisperType] UInput initialization error: {e}")
            self._uinput = None

    def delete_last(self):
        """Emit backspaces to erase the last dictated phrase."""
        if not self._uinput or self._last_injected_length <= 0:
            return
        count = min(self._last_injected_length, 500)
        for _ in range(count):
            self._uinput.write(evdev.ecodes.EV_KEY, KEY.KEY_BACKSPACE, 1)
            self._uinput.syn()
            self._uinput.write(evdev.ecodes.EV_KEY, KEY.KEY_BACKSPACE, 0)
            self._uinput.syn()
            time.sleep(0.0005)
        self._last_injected_length = 0

    def inject(self, text: str):
        if not text:
            return

        if text == "__ACTION_SCRATCH_THAT__":
            self.delete_last()
            return

        if not text.endswith(" "):
            text = text + " "

        active_class = _get_active_window_class()
        is_terminal = any(term in active_class for term in TERMINAL_CLASSES)
        can_type_ascii = all(c in CHAR_MAP for c in text)

        injected = False

        # For long prompts above threshold, attempt fast clipboard paste first
        if len(text) > self.paste_threshold and self._has_wl_copy:
            injected = self._paste_text(text, is_terminal=is_terminal)

        # Fallback to direct kernel uinput keystrokes (never drops text)
        if not injected:
            if self.method in ("uinput", "type") and self._uinput and can_type_ascii:
                self._type_uinput(text)
                injected = True
            elif self.method == "wtype" and shutil.which("wtype"):
                self._type_wtype(text, is_terminal=is_terminal)
                injected = True
            elif self._has_wl_copy:
                injected = self._paste_text(text, is_terminal=is_terminal)
            elif self._uinput and can_type_ascii:
                self._type_uinput(text)
                injected = True

        if injected:
            self._last_injected_length = len(text)
        else:
            print(f"[WhisperType] Could not find suitable text injection method.")

    def _type_uinput(self, text: str):
        """Type characters via kernel uinput device (zero offset bugs, native keycodes)."""
        if not self._uinput:
            return

        for ch in text:
            if ch not in CHAR_MAP:
                continue
            code, shift = CHAR_MAP[ch]

            if shift:
                self._uinput.write(evdev.ecodes.EV_KEY, KEY.KEY_LEFTSHIFT, 1)

            self._uinput.write(evdev.ecodes.EV_KEY, code, 1)
            self._uinput.syn()

            self._uinput.write(evdev.ecodes.EV_KEY, code, 0)
            if shift:
                self._uinput.write(evdev.ecodes.EV_KEY, KEY.KEY_LEFTSHIFT, 0)
            self._uinput.syn()
            time.sleep(0.0003)

    def _paste_text(self, text: str, is_terminal: bool = False) -> bool:
        """Fast clipboard paste using wl-copy and synthetic Ctrl+V / Ctrl+Shift+V."""
        env = _get_wayland_env()
        old_clipboard = None
        if self.restore_clipboard:
            try:
                res = subprocess.run(["wl-paste", "--no-newline"], capture_output=True, text=True, timeout=0.1, env=env)
                if res.returncode == 0:
                    old_clipboard = res.stdout
            except Exception:
                pass

        try:
            # Copy text to clipboard
            subprocess.run(["wl-copy"], input=text.encode("utf-8"), check=True, timeout=0.5, env=env)

            # Send paste keystroke via uinput if available, else wtype
            if self._uinput:
                self._uinput.write(evdev.ecodes.EV_KEY, KEY.KEY_LEFTCTRL, 1)
                if is_terminal:
                    self._uinput.write(evdev.ecodes.EV_KEY, KEY.KEY_LEFTSHIFT, 1)
                self._uinput.write(evdev.ecodes.EV_KEY, KEY.KEY_V, 1)
                self._uinput.syn()
                time.sleep(0.005)

                self._uinput.write(evdev.ecodes.EV_KEY, KEY.KEY_V, 0)
                if is_terminal:
                    self._uinput.write(evdev.ecodes.EV_KEY, KEY.KEY_LEFTSHIFT, 0)
                self._uinput.write(evdev.ecodes.EV_KEY, KEY.KEY_LEFTCTRL, 0)
                self._uinput.syn()
            elif shutil.which("wtype"):
                if is_terminal:
                    subprocess.run(["wtype", "-M", "ctrl", "-M", "shift", "-k", "v"], timeout=0.5, env=env)
                else:
                    subprocess.run(["wtype", "-M", "ctrl", "-k", "v"], timeout=0.5, env=env)

            # Restore original clipboard asynchronously after paste registers
            if old_clipboard is not None:
                def restore():
                    time.sleep(0.3)
                    try:
                        subprocess.run(["wl-copy"], input=old_clipboard.encode("utf-8"), timeout=0.5, env=env)
                    except Exception:
                        pass
                threading.Thread(target=restore, daemon=True).start()

            return True

        except Exception as e:
            print(f"[WhisperType] Paste injection warning: {e}, falling back to keystroke synthesis...")
            return False

    def _type_wtype(self, text: str, is_terminal: bool = False):
        try:
            cmd = ["wtype"]
            if self.wtype_delay_ms > 0:
                cmd.extend(["-d", str(self.wtype_delay_ms)])
            cmd.append("-")
            subprocess.run(cmd, input=text.encode("utf-8"), check=True, timeout=5.0)
        except Exception as e:
            print(f"[WhisperType] wtype injection error: {e}")
            if self._has_wl_copy:
                self._paste_text(text, is_terminal=is_terminal)

    def close(self):
        if self._uinput:
            try:
                self._uinput.close()
            except Exception:
                pass
            self._uinput = None
