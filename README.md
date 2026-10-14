# WhisperType

Ultra-low-latency (<40 ms) push-to-talk voice dictation daemon for Linux Wayland / Hyprland powered by pinned CUDA FP16 CTranslate2 on NVIDIA RTX and `faster-whisper`.

---

## Highlights

- **Hardware Hold-to-Talk**: Direct `evdev` kernel input listener capturing physical key presses (`Right Ctrl`, `Right Alt`, mouse chords) without Wayland compositor focus capture.
- **Ultra-Fast GPU Inference**: Pinned CUDA `float16` inference using `large-v3-turbo` with automated model warmup (~19-37 ms latency).
- **Direct Kernel Keystroke Injection**: Sub-millisecond keystroke synthesis via `/dev/uinput` virtual keyboard device with clipboard fallback for long passages.
- **Omni-Style Multi-Candidate Palette (`Right Ctrl + Space`)**:
  - Computes candidate dialect transformations simultaneously.
  - Floating Wayland preview popover anchored right above your active text input field.
  - Live preview HUD showing what each personality will say before you inject.
  - `↑`/`↓` linear navigation, direct `1`–`5` hotkeys, mouse click, and zero timeout (`timeout_sec = 0.0`).
- **Verbal Formatting Macros**:
  - Spoken syntax commands: `"new line"`, `"comma"`, `"period"`, `"question mark"`, `"scratch that"` (backspaces previous dictation), `"make snake case"`, `"make camel case"`, `"make shouting"`.
- **Personality Transforms (Strict Text-Only, No Emojis/Symbols)**:
  - `uwu`: Submissive freak girl dialect.
  - `brainrot`: Gen Alpha / TikTok meme dialect.
  - `discord`: Minimalist, lowercase chat.
  - `corporate`: Passive-aggressive enterprise jargon.
  - `boomer`: All-caps Facebook grandma speak.
  - `code`: Syntactic code formatting.
- **Spectral Acoustic Noise Gate**: Real-time non-stationary noise suppression eliminating mechanical keyboard clicks and fan hum.
- **Speculative Audio Pipeline**: Background speculative slicing during speech for zero perceive-to-inject latency.

---

## Installation

### Prerequisites
- Python 3.10+
- NVIDIA GPU with CUDA drivers
- Wayland / Hyprland (or Sway / River)
- User in `input` group (for evdev / uinput access)

```bash
git clone https://github.com/Zykoraa/whispertype.git
cd whispertype
uv venv
uv pip install -e .
```

### Systemd User Service Setup
```bash
mkdir -p ~/.config/systemd/user
cp systemd/whispertype.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now whispertype.service
```

---

## Default Keybinds

| Hotkey Chord | Action |
|---|---|
| `Right Ctrl` | Instant Speech-to-Text (`default`) |
| `Right Ctrl + Space` | Multi-Candidate Floating Preview Palette |
| `Right Ctrl + Down` | Submissive Freak Girl (`uwu`) |
| `Right Ctrl + Up` | Gen Alpha Dialect (`brainrot`) |
| `Right Ctrl + Left` | Discord Lowercase (`discord`) |
| `Right Ctrl + Right` | Enterprise Jargon (`corporate`) |
| `Right Alt` | Code Syntactic Formatter (`code`) |
| Mouse `BTN_EXTRA` | Verbatim Unfiltered Transcription (`raw`) |

---

## CLI Management

```bash
whispertype status       # Check daemon state & active triggers
whispertype hold [style] # Manually trigger recording
whispertype release      # Finish and transcribe
whispertype toggle       # Toggle hold state
whispertype config       # Inspect active TOML configuration
whispertype stop-daemon  # Gracefully terminate daemon
```

---

## Configuration

Custom triggers, model parameters, noise gating, and dialect rules are configured in `~/.config/whispertype/config.toml`.
