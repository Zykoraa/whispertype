"""Configuration management for WhisperType."""

from dataclasses import dataclass, field
import os
from pathlib import Path
import tomllib
from typing import Dict, Optional

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "whispertype" / "config.toml"

DEFAULT_CONFIG_CONTENT = """# WhisperType Configuration

[model]
# Model identifier or path. Cached models: "large-v3-turbo", "small.en", "base.en"
name = "large-v3-turbo"
device = "cuda"
compute_type = "float16"
beam_size = 2
language = "en"
initial_prompt = "Technical dictation, code, Linux, Hyprland, Git, Discord, terminal commands."

[trigger]
# Primary hotkey (for backwards compatibility)
hotkey = "KEY_RIGHTCTRL"
device_name = ""
device_path = ""
grab = false

# Multi-button & chord writing style mapping:
# - Right Ctrl alone:       default   (normal polished speech)
# - Right Ctrl + Space:     palette   (omni floating selection menu)
# - Right Ctrl + Down Arrow: uwu       (submissive freak girl)
# - Right Ctrl + Up Arrow:   brainrot  (Gen Alpha / TikTok meme dialect)
# - Right Ctrl + Left Arrow: discord   (minimalist chat, lowercase)
# - Right Ctrl + Right Arrow: corporate (passive-aggressive enterprise speak)
[triggers]
KEY_RIGHTCTRL = "default"
"KEY_RIGHTCTRL+KEY_SPACE" = "palette"
"KEY_RIGHTCTRL+KEY_DOWN" = "uwu"
"KEY_RIGHTCTRL+KEY_UP" = "brainrot"
"KEY_RIGHTCTRL+KEY_LEFT" = "discord"
"KEY_RIGHTCTRL+KEY_RIGHT" = "corporate"
KEY_RIGHTALT = "code"
BTN_EXTRA = "raw"

# Writing style presets:

[styles.default]
initial_prompt = "Technical dictation, code, Linux, Hyprland, Git, Discord, terminal commands."
strip_fillers = true
macros = true
code_transform = false
personality = ""
polish = false
casing = "normal"

[styles.uwu]
initial_prompt = "p-pwease be gentle y-yes sir haah i will do anything you want master use me sawwy"
strip_fillers = true
macros = false
code_transform = false
personality = "uwu"
polish = false
casing = "normal"

[styles.brainrot]
initial_prompt = "skibidi rizzler sigma gyatt fanum tax in ohio kai cenat baby gronk mewing streak grimace shake no cap on god fr fr we are cooked chat"
strip_fillers = true
macros = false
code_transform = false
personality = "brainrot"
polish = false
casing = "lower"

[styles.boomer]
initial_prompt = "HELLO... GLAD TO HEAR FROM YOU... HOPE THE KIDS ARE DOING WELL... GOD BLESS... -BOB"
strip_fillers = true
macros = true
code_transform = false
personality = "boomer"
polish = false
casing = "upper"

[styles.gangster]
initial_prompt = "Yo, what's good homie, street slang, nah'mean, fr fr, finna, boutta, straight up, ya feel me."
strip_fillers = true
macros = true
code_transform = false
personality = "gangster"
polish = false
casing = "normal"

[styles.corporate]
initial_prompt = "Per my previous email, let's touch base and circle back on key deliverables to ensure cross-functional alignment and maximize bandwidth."
strip_fillers = true
macros = true
code_transform = false
personality = "corporate"
polish = false
casing = "normal"

[styles.discord]
initial_prompt = "lmao tbh ngl idk fr no cap 💀 😭 afaik imo gg"
strip_fillers = true
macros = false
code_transform = false
personality = "discord"
polish = false
casing = "lower"

[styles.victorian]
initial_prompt = "Verily, methinks thou art mistaken, for 'tis a grand inquiry, alas, prithee tell, wherefore doth thou tarry."
strip_fillers = true
macros = true
code_transform = false
personality = "victorian"
polish = false
casing = "normal"

[styles.code]
initial_prompt = "C++, Rust, Python, Linux kernel, hypercalls, pointers, functions, return true, git, bash."
strip_fillers = true
macros = true
code_transform = true
personality = ""
polish = false
casing = "normal"

[styles.raw]
initial_prompt = ""
strip_fillers = false
macros = false
code_transform = false
personality = ""
polish = false
casing = "normal"

[audio]
# Sample rate in Hz (Whisper requires 16000)
sample_rate = 16000
channels = 1
# Audio feedback cues (soft clicks on start and stop)
cues = true
cue_volume = 0.25
# Spectral acoustic noise suppression (removes keyboard clicks and fan hum)
noise_suppression = true
prop_decrease = 0.75

[typing]
# Injection method: "uinput" (kernel device, recommended), "wtype", or "paste"
method = "uinput"
# Milliseconds between typed keystrokes (0 for instantaneous)
wtype_delay_ms = 0
# Switch to fast clipboard paste if text length exceeds this threshold
paste_threshold = 120
# Restore clipboard contents after pasting
restore_clipboard = true

[text]
# Strip hesitation sounds (um, uh, er, ah, hmm) and stuttered repeated words
strip_fillers = true
# Enable verbal syntax macros ("new line", "snake case", "scratch that")
macros = true

[llm]
# Optional local SLM text polish mode (requires local LLM server on endpoint)
polish_mode = false
api_url = "http://localhost:1234/v1/chat/completions"
model = "local-model"
timeout = 0.5

[ui]
# Visual feedback on dictation state: "hyprctl" or "none"
visual_indicator = "hyprctl"

[palette]
# Floating Wayland candidate selection palette (timeout_sec = 0 to keep open until Esc or Enter)
enabled = true
hotkey = "KEY_RIGHTCTRL+KEY_SPACE"
timeout_sec = 0.0
auto_inject_default = false
"""


@dataclass
class ModelConfig:
    name: str = "large-v3-turbo"
    device: str = "cuda"
    compute_type: str = "float16"
    beam_size: int = 2
    language: str = "en"
    initial_prompt: str = "Technical dictation, code, Linux, Hyprland, Git, Discord, terminal commands."


@dataclass
class TriggerConfig:
    hotkey: str = "KEY_RIGHTCTRL"
    device_name: str = ""
    device_path: str = ""
    grab: bool = False


@dataclass
class StyleConfig:
    name: str = "default"
    initial_prompt: str = "Technical dictation, code, Linux, Hyprland, Git, Discord, terminal commands."
    strip_fillers: bool = True
    macros: bool = True
    code_transform: bool = False
    personality: str = ""  # "gangster", "corporate", "discord", "victorian"
    gangster_transform: bool = False  # backwards compat
    polish: bool = False
    casing: str = "normal"  # "normal", "lower", "upper", "capitalize", "title"
    prefix: str = ""
    suffix: str = ""


def get_default_styles(base_prompt: str = "", base_strip_fillers: bool = True, base_macros: bool = True) -> Dict[str, StyleConfig]:
    prompt = base_prompt or "Technical dictation, code, Linux, Hyprland, Git, Discord, terminal commands."
    return {
        "default": StyleConfig(
            name="default",
            initial_prompt=prompt,
            strip_fillers=base_strip_fillers,
            macros=base_macros,
            code_transform=False,
            personality="",
            polish=False,
            casing="normal",
        ),
        "palette": StyleConfig(
            name="palette",
            initial_prompt="",
            strip_fillers=base_strip_fillers,
            macros=base_macros,
            code_transform=False,
            personality="palette",
            polish=False,
            casing="normal",
        ),
        "uwu": StyleConfig(
            name="uwu",
            initial_prompt="p-pwease be gentle y-yes sir haah i will do anything you want master use me sawwy",
            strip_fillers=True,
            macros=False,
            code_transform=False,
            personality="uwu",
            polish=False,
            casing="normal",
        ),
        "brainrot": StyleConfig(
            name="brainrot",
            initial_prompt="skibidi rizzler sigma gyatt fanum tax in ohio kai cenat baby gronk mewing streak grimace shake no cap on god fr fr we are cooked chat",
            strip_fillers=True,
            macros=False,
            code_transform=False,
            personality="brainrot",
            polish=False,
            casing="lower",
        ),
        "boomer": StyleConfig(
            name="boomer",
            initial_prompt="HELLO... GLAD TO HEAR FROM YOU... HOPE THE KIDS ARE DOING WELL... GOD BLESS... -BOB",
            strip_fillers=True,
            macros=True,
            code_transform=False,
            personality="boomer",
            polish=False,
            casing="upper",
        ),
        "gangster": StyleConfig(
            name="gangster",
            initial_prompt="Yo, what's good homie, street slang, nah'mean, fr fr, finna, boutta, straight up, ya feel me.",
            strip_fillers=True,
            macros=True,
            code_transform=False,
            personality="gangster",
            gangster_transform=True,
            polish=False,
            casing="normal",
        ),
        "corporate": StyleConfig(
            name="corporate",
            initial_prompt="Per my previous email, let's touch base and circle back on key deliverables to ensure cross-functional alignment and maximize bandwidth.",
            strip_fillers=True,
            macros=True,
            code_transform=False,
            personality="corporate",
            polish=False,
            casing="normal",
        ),
        "discord": StyleConfig(
            name="discord",
            initial_prompt="lmao tbh ngl idk fr no cap 💀 😭 afaik imo gg",
            strip_fillers=True,
            macros=False,
            code_transform=False,
            personality="discord",
            polish=False,
            casing="lower",
        ),
        "victorian": StyleConfig(
            name="victorian",
            initial_prompt="Verily, methinks thou art mistaken, for 'tis a grand inquiry, alas, prithee tell, wherefore doth thou tarry.",
            strip_fillers=True,
            macros=True,
            code_transform=False,
            personality="victorian",
            polish=False,
            casing="normal",
        ),
        "code": StyleConfig(
            name="code",
            initial_prompt="C++, Rust, Python, Linux kernel, hypercalls, pointers, functions, return true, git, bash.",
            strip_fillers=True,
            macros=True,
            code_transform=True,
            personality="",
            polish=False,
            casing="normal",
        ),
        "raw": StyleConfig(
            name="raw",
            initial_prompt="",
            strip_fillers=False,
            macros=False,
            code_transform=False,
            personality="",
            polish=False,
            casing="normal",
        ),
        "verbatim": StyleConfig(
            name="verbatim",
            initial_prompt="",
            strip_fillers=False,
            macros=False,
            code_transform=False,
            personality="",
            polish=False,
            casing="normal",
        ),
        "casual": StyleConfig(
            name="casual",
            initial_prompt="Casual conversation, messaging, chat.",
            strip_fillers=True,
            macros=False,
            code_transform=False,
            personality="",
            polish=False,
            casing="normal",
        ),
    }


@dataclass
class AudioConfig:
    sample_rate: int = 16000
    channels: int = 1
    cues: bool = True
    cue_volume: float = 0.25
    noise_suppression: bool = True
    prop_decrease: float = 0.75


@dataclass
class TypingConfig:
    method: str = "uinput"
    wtype_delay_ms: int = 0
    paste_threshold: int = 120
    restore_clipboard: bool = True


@dataclass
class TextConfig:
    strip_fillers: bool = True
    macros: bool = True


@dataclass
class LLMConfig:
    polish_mode: bool = False
    api_url: str = "http://localhost:1234/v1/chat/completions"
    model: str = "local-model"
    timeout: float = 0.5


@dataclass
class UIConfig:
    visual_indicator: str = "hyprctl"


@dataclass
class PaletteConfig:
    enabled: bool = True
    hotkey: str = "KEY_RIGHTCTRL+KEY_SPACE"
    timeout_sec: float = 0.0
    auto_inject_default: bool = False


@dataclass
class Config:
    model: ModelConfig = field(default_factory=ModelConfig)
    trigger: TriggerConfig = field(default_factory=TriggerConfig)
    triggers: Dict[str, str] = field(default_factory=lambda: {
        "KEY_RIGHTCTRL": "default",
        "KEY_RIGHTCTRL+KEY_SPACE": "palette",
        "KEY_RIGHTCTRL+KEY_DOWN": "uwu",
        "KEY_RIGHTCTRL+KEY_UP": "brainrot",
        "KEY_RIGHTCTRL+KEY_LEFT": "discord",
        "KEY_RIGHTCTRL+KEY_RIGHT": "corporate",
        "KEY_RIGHTALT": "code",
        "BTN_EXTRA": "raw",
    })
    styles: Dict[str, StyleConfig] = field(default_factory=get_default_styles)
    palette: PaletteConfig = field(default_factory=PaletteConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    typing: TypingConfig = field(default_factory=TypingConfig)
    text: TextConfig = field(default_factory=TextConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    ui: UIConfig = field(default_factory=UIConfig)


def load_config(path: Optional[Path] = None) -> Config:
    config_file = path or DEFAULT_CONFIG_PATH
    if not config_file.exists():
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text(DEFAULT_CONFIG_CONTENT, encoding="utf-8")
        return Config()

    try:
        with open(config_file, "rb") as f:
            data = tomllib.load(f)

        m = data.get("model", {})
        t = data.get("trigger", {})
        a = data.get("audio", {})
        typ = data.get("typing", {})
        txt = data.get("text", {})
        llm_cfg = data.get("llm", {})
        ui_cfg = data.get("ui", {})

        # Triggers map
        configured_triggers = data.get("triggers", {})
        triggers_map: Dict[str, str] = {}
        if isinstance(configured_triggers, dict) and configured_triggers:
            for k, v in configured_triggers.items():
                if isinstance(v, str):
                    triggers_map[k] = v
                elif isinstance(v, dict):
                    triggers_map[k] = v.get("style", "default")
        else:
            # Fallback to single trigger hotkey
            hotkey = t.get("hotkey", "KEY_RIGHTCTRL")
            triggers_map[hotkey] = "default"

        # Styles map
        strip_fillers = bool(txt.get("strip_fillers", True))
        macros = bool(txt.get("macros", True))
        styles_map = get_default_styles(
            base_prompt=m.get("initial_prompt", "Technical dictation, code, Linux, Hyprland, Git, Discord, terminal commands."),
            base_strip_fillers=strip_fillers,
            base_macros=macros,
        )

        user_styles = data.get("styles", {})
        if isinstance(user_styles, dict):
            for s_name, s_val in user_styles.items():
                if not isinstance(s_val, dict):
                    continue
                existing = styles_map.get(s_name, StyleConfig(name=s_name))
                personality_val = s_val.get("personality", existing.personality)
                gangster_tf = bool(s_val.get("gangster_transform", existing.gangster_transform or personality_val == "gangster"))
                styles_map[s_name] = StyleConfig(
                    name=s_name,
                    initial_prompt=s_val.get("initial_prompt", existing.initial_prompt),
                    strip_fillers=bool(s_val.get("strip_fillers", existing.strip_fillers)),
                    macros=bool(s_val.get("macros", existing.macros)),
                    code_transform=bool(s_val.get("code_transform", existing.code_transform)),
                    personality=personality_val,
                    gangster_transform=gangster_tf,
                    polish=bool(s_val.get("polish", existing.polish)),
                    casing=s_val.get("casing", existing.casing),
                    prefix=s_val.get("prefix", existing.prefix),
                    suffix=s_val.get("suffix", existing.suffix),
                )

        pal_cfg = data.get("palette", {})
        palette_config = PaletteConfig(
            enabled=bool(pal_cfg.get("enabled", True)),
            hotkey=pal_cfg.get("hotkey", "KEY_RIGHTCTRL+KEY_SPACE"),
            timeout_sec=float(pal_cfg.get("timeout_sec", 0.0)),
            auto_inject_default=bool(pal_cfg.get("auto_inject_default", False)),
        )

        return Config(
            model=ModelConfig(
                name=m.get("name", "large-v3-turbo"),
                device=m.get("device", "cuda"),
                compute_type=m.get("compute_type", "float16"),
                beam_size=int(m.get("beam_size", 2)),
                language=m.get("language", "en"),
                initial_prompt=m.get("initial_prompt", "Technical dictation, code, Linux, Hyprland, Git, Discord, terminal commands."),
            ),
            trigger=TriggerConfig(
                hotkey=t.get("hotkey", "KEY_RIGHTCTRL"),
                device_name=t.get("device_name", ""),
                device_path=t.get("device_path", ""),
                grab=bool(t.get("grab", False)),
            ),
            triggers=triggers_map,
            styles=styles_map,
            palette=palette_config,
            audio=AudioConfig(
                sample_rate=int(a.get("sample_rate", 16000)),
                channels=int(a.get("channels", 1)),
                cues=bool(a.get("cues", True)),
                cue_volume=float(a.get("cue_volume", 0.25)),
                noise_suppression=bool(a.get("noise_suppression", True)),
                prop_decrease=float(a.get("prop_decrease", 0.75)),
            ),
            typing=TypingConfig(
                method=typ.get("method", "uinput"),
                wtype_delay_ms=int(typ.get("wtype_delay_ms", 0)),
                paste_threshold=int(typ.get("paste_threshold", 120)),
                restore_clipboard=bool(typ.get("restore_clipboard", True)),
            ),
            text=TextConfig(
                strip_fillers=strip_fillers,
                macros=macros,
            ),
            llm=LLMConfig(
                polish_mode=bool(llm_cfg.get("polish_mode", False)),
                api_url=llm_cfg.get("api_url", "http://localhost:1234/v1/chat/completions"),
                model=llm_cfg.get("model", "local-model"),
                timeout=float(llm_cfg.get("timeout", 0.5)),
            ),
            ui=UIConfig(
                visual_indicator=ui_cfg.get("visual_indicator", "hyprctl"),
            ),
        )
    except Exception as e:
        print(f"[WhisperType] Warning: Failed to parse config from {config_file} ({e}), using defaults.")
        return Config()
