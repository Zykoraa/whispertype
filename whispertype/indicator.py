"""Visual indicator and OSD feedback for Wayland / Hyprland."""

import shutil
import subprocess
import threading
from typing import Optional


class VisualIndicator:
    def __init__(self, method: str = "hyprctl"):
        self.method = method
        self._has_hyprctl = shutil.which("hyprctl") is not None

    def show_recording(self, style: str = ""):
        if self.method != "hyprctl" or not self._has_hyprctl:
            return

        def _run():
            try:
                if style == "code":
                    color = "rgb(8839ef)"  # Catppuccin Mauve
                    label = "WhisperType [code]: Listening..."
                elif style == "palette":
                    color = "rgb(cba6f7)"  # Catppuccin Mauve
                    label = "WhisperType [palette]: Listening..."
                elif style == "uwu":
                    color = "rgb(f5c2e7)"  # Sakura Pink
                    label = "WhisperType [uwu]: Listening..."
                elif style == "brainrot":
                    color = "rgb(cba6f7)"  # Toxic Purple / Gen Alpha
                    label = "WhisperType [brainrot]: Listening..."
                elif style == "boomer":
                    color = "rgb(89b4fa)"  # Facebook Blue
                    label = "WhisperType [boomer]: Listening..."
                elif style == "gangster":
                    color = "rgb(fab387)"  # Catppuccin Peach / Gold
                    label = "WhisperType [gangster]: Listening..."
                elif style == "corporate":
                    color = "rgb(7287fd)"  # Corporate Slate Blue
                    label = "WhisperType [corporate]: Listening..."
                elif style == "discord":
                    color = "rgb(a6e3a1)"  # Discord Green
                    label = "WhisperType [discord]: Listening..."
                elif style == "victorian":
                    color = "rgb(cba6f7)"  # Victorian Lavender
                    label = "WhisperType [victorian]: Listening..."
                elif style in ("raw", "verbatim"):
                    color = "rgb(1e66f5)"  # Catppuccin Sapphire
                    label = "WhisperType [raw]: Listening..."
                elif style and style != "default":
                    color = "rgb(e64553)"
                    label = f"WhisperType [{style}]: Listening..."
                else:
                    color = "rgb(e64553)"  # Catppuccin Red
                    label = "WhisperType: Listening..."

                subprocess.run(
                    ["hyprctl", "notify", "0", "2000", color, label],
                    capture_output=True,
                    timeout=0.2,
                )
            except Exception:
                pass

        threading.Thread(target=_run, daemon=True).start()

    def show_processing(self):
        if self.method != "hyprctl" or not self._has_hyprctl:
            return

        def _run():
            try:
                subprocess.run(
                    ["hyprctl", "notify", "0", "1500", "rgb(1e66f5)", "WhisperType: Transcribing..."],
                    capture_output=True,
                    timeout=0.2,
                )
            except Exception:
                pass

        threading.Thread(target=_run, daemon=True).start()

    def show_success(self, text: str = ""):
        if self.method != "hyprctl" or not self._has_hyprctl:
            return

        def _run():
            try:
                msg = f"WhisperType: \"{text[:40]}...\"" if len(text) > 40 else f"WhisperType: \"{text}\""
                subprocess.run(
                    ["hyprctl", "notify", "0", "1200", "rgb(40a02b)", msg],
                    capture_output=True,
                    timeout=0.2,
                )
            except Exception:
                pass

        threading.Thread(target=_run, daemon=True).start()
