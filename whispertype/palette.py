"""Compact Wayland floating candidate selection & preview popover for WhisperType."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QGuiApplication, QCursor
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


def get_hyprland_target_pos(pill_w: int, pill_h: int) -> Tuple[int, int]:
    """Calculate target position anchored to the active window input field or cursor."""
    cursor_x, cursor_y = 960, 540
    try:
        res = subprocess.run(["hyprctl", "cursorpos"], capture_output=True, text=True, timeout=0.2)
        if res.returncode == 0 and res.stdout.strip():
            parts = [p.strip() for p in res.stdout.strip().split(",")]
            if len(parts) == 2:
                cursor_x, cursor_y = int(parts[0]), int(parts[1])
    except Exception:
        pass

    try:
        win_res = subprocess.run(["hyprctl", "activewindow", "-j"], capture_output=True, text=True, timeout=0.2)
        if win_res.returncode == 0 and win_res.stdout.strip():
            win = json.loads(win_res.stdout)
            wx, wy = win.get("at", [0, 0])
            ww, wh = win.get("size", [1920, 1080])

            # Check if cursor is inside active window
            if wx <= cursor_x <= wx + ww and wy <= cursor_y <= wy + wh:
                tx = max(wx + 10, min(cursor_x - (pill_w // 2), wx + ww - pill_w - 10))
                ty = max(wy + 10, min(cursor_y - pill_h - 15, wy + wh - pill_h - 10))
                return tx, ty
            else:
                # Anchor above the bottom text box of active window
                tx = max(wx + 10, min(wx + (ww - pill_w) // 2, wx + ww - pill_w - 10))
                ty = max(wy + 10, wy + wh - pill_h - 25)
                return tx, ty
    except Exception:
        pass

    return max(20, cursor_x - (pill_w // 2)), max(20, cursor_y - pill_h - 15)


class CandidateRow(QFrame):
    def __init__(self, key_label: str, name: str, color: str, style_key: str, text: str, on_click_callback):
        super().__init__()
        self.style_key = style_key
        self.color = color
        self.on_click_callback = on_click_callback
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self.badge = QLabel(f"[{key_label}]", self)
        self.badge.setStyleSheet(f"""
            color: #1e1e2e;
            background-color: {color};
            font-size: 10px;
            font-weight: bold;
            border-radius: 4px;
            padding: 1px 5px;
        """)
        self.badge.setFixedWidth(46)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.name_lbl = QLabel(name, self)
        self.name_lbl.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: bold;")
        self.name_lbl.setFixedWidth(72)

        display_text = text.replace("\n", " ").strip()
        if len(display_text) > 75:
            display_text = display_text[:72] + "..."

        self.text_lbl = QLabel(f'"{display_text}"', self)
        self.text_lbl.setStyleSheet("color: #cdd6f4; font-size: 11px;")
        self.setToolTip(text)

        layout.addWidget(self.badge)
        layout.addWidget(self.name_lbl)
        layout.addWidget(self.text_lbl, 1)

        self.set_active(False)

    def set_active(self, active: bool):
        if active:
            self.setStyleSheet(f"""
                QFrame {{
                    background-color: rgba(49, 50, 68, 0.85);
                    border: 1px solid {self.color};
                    border-radius: 6px;
                }}
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: transparent;
                    border: 1px solid transparent;
                    border-radius: 6px;
                }
                QFrame:hover {
                    background-color: rgba(49, 50, 68, 0.4);
                }
            """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.on_click_callback(self.style_key)


class CandidatePreviewPalette(QWidget):
    def __init__(
        self,
        candidates: Dict[str, str],
        timeout_sec: float = 0.0,
        auto_default: bool = False,
    ):
        super().__init__()
        self.candidates = candidates
        self.timeout_sec = timeout_sec
        self.auto_default = auto_default
        self.selected_style: Optional[str] = None

        self.setObjectName("whispertype-palette")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.items_def = [
            ("1", "Brainrot", "#cba6f7", "brainrot"),
            ("2", "UwU", "#f5c2e7", "uwu"),
            ("3", "Schizo", "#f38ba8", "schizo"),
            ("4", "Trump", "#fab387", "trump"),
            ("5", "Default", "#89b4fa", "default"),
        ]
        self.rows: List[CandidateRow] = []
        # Initially highlight default
        self.current_idx = 4

        self.setMouseTracking(True)
        self._timer: Optional[QTimer] = None
        if self.timeout_sec > 0:
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.timeout.connect(self._on_timeout)
            self._timer.start(int(self.timeout_sec * 1000))

        self._init_ui()
        self._position_window()

    def _reset_timer(self):
        if self._timer and self.timeout_sec > 0:
            self._timer.start(int(self.timeout_sec * 1000))

    def mouseMoveEvent(self, event):
        self._reset_timer()
        super().mouseMoveEvent(event)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        card = QFrame(self)
        card.setObjectName("paletteCard")
        card.setStyleSheet("""
            #paletteCard {
                background-color: rgba(24, 24, 37, 0.95);
                border: 1px solid rgba(203, 166, 247, 0.5);
                border-radius: 12px;
            }
        """)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 8, 10, 8)
        card_layout.setSpacing(3)

        header = QLabel("PREVIEW & SELECT (↑/↓ to browse • Enter to paste • 1-5 quick-select • Esc to cancel)", card)
        header.setStyleSheet("color: #6c7086; font-size: 9px; font-weight: bold; letter-spacing: 0.5px; margin-bottom: 2px;")
        card_layout.addWidget(header)

        for i, (key_label, name, color, style_key) in enumerate(self.items_def):
            row_widget = CandidateRow(
                key_label=key_label,
                name=name,
                color=color,
                style_key=style_key,
                text=self.candidates.get(style_key, ""),
                on_click_callback=self._select_and_close,
            )
            self.rows.append(row_widget)
            card_layout.addWidget(row_widget)

        self.rows[self.current_idx].set_active(True)
        main_layout.addWidget(card)

    def _set_active_row(self, new_idx: int):
        if 0 <= new_idx < len(self.rows):
            self.rows[self.current_idx].set_active(False)
            self.current_idx = new_idx
            self.rows[self.current_idx].set_active(True)

    def _position_window(self):
        self.adjustSize()
        w = max(640, self.sizeHint().width())
        h = max(165, self.sizeHint().height())
        tx, ty = get_hyprland_target_pos(w, h)
        self.setGeometry(tx, ty, w, h)

    def keyPressEvent(self, event):
        self._reset_timer()
        key = event.key()

        if key in (Qt.Key.Key_Up, Qt.Key.Key_K):
            self._set_active_row((self.current_idx - 1) % len(self.rows))
        elif key in (Qt.Key.Key_Down, Qt.Key.Key_J, Qt.Key.Key_Tab):
            self._set_active_row((self.current_idx + 1) % len(self.rows))
        elif key == Qt.Key.Key_1:
            if self.current_idx == 0:
                self._select_and_close("brainrot")
            else:
                self._set_active_row(0)
        elif key == Qt.Key.Key_2:
            if self.current_idx == 1:
                self._select_and_close("uwu")
            else:
                self._set_active_row(1)
        elif key == Qt.Key.Key_3:
            if self.current_idx == 2:
                self._select_and_close("schizo")
            else:
                self._set_active_row(2)
        elif key == Qt.Key.Key_4:
            if self.current_idx == 3:
                self._select_and_close("trump")
            else:
                self._set_active_row(3)
        elif key in (Qt.Key.Key_5, Qt.Key.Key_0):
            if self.current_idx == 4:
                self._select_and_close("default")
            else:
                self._set_active_row(4)
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            chosen = self.items_def[self.current_idx][3]
            self._select_and_close(chosen)
        elif key == Qt.Key.Key_Escape:
            self._select_and_close("cancel")
        else:
            super().keyPressEvent(event)

    def _select_and_close(self, style: str):
        self.selected_style = style
        print(style)
        sys.stdout.flush()
        self.close()
        QApplication.quit()

    def _on_timeout(self):
        if not self.selected_style:
            res = "default" if self.auto_default else "cancel"
            self._select_and_close(res)


def main():
    parser = argparse.ArgumentParser(description="WhisperType Candidate Preview Palette")
    parser.add_argument("--choices", type=str, default="{}", help="JSON dictionary of candidate styles and texts")
    parser.add_argument("--timeout", type=float, default=0.0, help="Timeout in seconds (0.0 = no timeout)")
    parser.add_argument("--auto-default", action="store_true", help="Auto inject default on timeout")

    args = parser.parse_args()

    try:
        candidates = json.loads(args.choices)
    except Exception:
        candidates = {}

    app = QApplication([sys.argv[0], "-platform", "wayland"])
    app.setApplicationName("whispertype-palette")
    app.setDesktopFileName("whispertype-palette")

    palette = CandidatePreviewPalette(
        candidates=candidates,
        timeout_sec=args.timeout,
        auto_default=args.auto_default,
    )
    palette.show()
    palette.raise_()
    palette.activateWindow()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
