"""Comprehensive test and audit suite for WhisperType power-user pipeline."""

import time
import numpy as np
from whispertype.audio import AudioRecorder
from whispertype.cleaner import clean_transcript
from whispertype.config import load_config
from whispertype.evdev_listener import EvdevListener
from whispertype.feedback import AudioFeedback
from whispertype.indicator import VisualIndicator
from whispertype.injector import TextInjector
from whispertype.llm import TextPolisher
from whispertype.macros import process_macros, SCRATCH_THAT_MARKER
from whispertype.model import WhisperEngine
from whispertype.noise import NoiseSuppressor
from whispertype.speculative import SpeculativeWorker


def test_config():
    cfg = load_config()
    assert cfg.model.name == "large-v3-turbo"
    assert cfg.audio.noise_suppression is True
    assert cfg.text.macros is True
    assert cfg.typing.method == "uinput"

    # Base trigger
    assert "KEY_RIGHTCTRL" in cfg.triggers
    assert cfg.triggers["KEY_RIGHTCTRL"] == "default"
    assert cfg.trigger.mode == "hybrid"

    # Multi-candidate palette trigger
    assert cfg.triggers.get("KEY_RIGHTCTRL+KEY_SPACE") == "palette"
    assert cfg.palette.enabled is True

    # 4-way arrow personality cluster
    assert cfg.triggers.get("KEY_RIGHTCTRL+KEY_DOWN") == "uwu"
    assert cfg.triggers.get("KEY_RIGHTCTRL+KEY_UP") == "brainrot"
    assert cfg.triggers.get("KEY_RIGHTCTRL+KEY_LEFT") == "schizo"
    assert cfg.triggers.get("KEY_RIGHTCTRL+KEY_RIGHT") == "trump"

    # Presets
    for p in ["default", "palette", "uwu", "brainrot", "schizo", "trump", "boomer", "corporate", "discord", "gangster", "victorian", "code", "raw"]:
        assert p in cfg.styles
    print("[PASS] test_config")


def test_noise_suppression():
    ns = NoiseSuppressor(enabled=True, prop_decrease=0.75)
    noise = np.random.uniform(-0.05, 0.05, 16000 * 2).astype(np.float32)
    cleaned = ns.process(noise)
    assert len(cleaned) == len(noise)
    # Energy should be reduced
    assert np.var(cleaned) < np.var(noise)
    print("[PASS] test_noise_suppression")


def test_macros():
    # Casing transforms
    s, _ = process_macros("make snake case user id")
    assert "user_id" in s

    c, _ = process_macros("function camel case parse json")
    assert "parseJson" in c

    p, _ = process_macros("class pascal case order item")
    assert "OrderItem" in p

    k, _ = process_macros("kebab case my cool package")
    assert "my-cool-package" in k

    # Operators & layout
    sym, _ = process_macros("if x is greater than or equal to 10 fat arrow new line return true")
    assert ">=" in sym
    assert "=>" in sym
    assert "\n" in sym

    # Scratch that action
    scratch, is_scratch = process_macros("scratch that")
    assert is_scratch is True
    assert scratch == SCRATCH_THAT_MARKER
    print("[PASS] test_macros")


def test_cleaner():
    raw = "Um, I think that, uh, we need to the the check the code, you know?"
    cleaned = clean_transcript(raw)
    assert "Um" not in cleaned
    assert "uh" not in cleaned
    # "you know" is a legitimate English phrase and must NEVER be stripped
    assert "you know" in cleaned
    assert "the the" not in cleaned
    assert cleaned.startswith("I think that")

    # Additional vocabulary tests
    test_etc = clean_transcript("The error code is 404, etc.")
    assert "error" in test_etc
    assert "etc" in test_etc

    test_raw = clean_transcript("um, like, uh", strip_fillers=False)
    assert "um" in test_raw.lower()
    assert "uh" in test_raw.lower()
    print(f"[PASS] test_cleaner: '{raw}' -> '{cleaned}'")


def test_styles_and_polisher():
    tp = TextPolisher(enabled=False)

    # 1. Code transforms
    code = tp.transform_code("let counter plus plus and return true")
    assert "counter++" in code
    assert "return true;" in code

    # 2. Gangster dialect transforms
    gangster = tp.transform_gangster("You know I am going to the store with my friend.")
    # 2. UwU Freak transforms (pure text, no emojis or symbols)
    uwu = tp.transform_uwu("The kernel had an error and crashed, please fix it.")
    assert "kewnew" in uwu
    assert "p-punish me" in uwu
    assert "p-pwease" in uwu
    assert "haah" in uwu
    assert "nya" not in uwu
    assert "(◕‿◕✿)" not in uwu
    assert not any(ord(c) > 127 for c in uwu)

    # 3. Boomer Facebook Dad transforms
    boomer = tp.transform_boomer("I will be late today, traffic is bad on the highway.")
    assert "..." in boomer
    assert "GOD BLESS... -BOB" in boomer
    assert boomer == boomer.upper()

    # 4. Schizo dialect transforms (pure text, no emojis)
    schizo = tp.transform_schizo("They are watching my computer and phone, error on the internet.")
    assert "glowies in the drywall" in schizo
    assert "airgapped terminal" in schizo
    assert "compromised baseband burner" in schizo
    assert "monitored DARPA frequency" in schizo
    assert "hardware implant telemetry breach" in schizo
    assert "flush the tlb and melt the drives" in schizo
    assert not any(ord(c) > 127 for c in schizo)

    # 5. Trump dialect transforms (pure text, no emojis)
    trump = tp.transform_trump("The code had an error, but it is great and we will fix it.")
    assert "Folks," in trump
    assert ("catastrophic mess" in trump or "disaster" in trump)
    assert "tremendous" in trump
    assert "believe me" in trump
    assert not any(ord(c) > 127 for c in trump)

    # 6. Corporate dialect transforms
    corp = tp.transform_corporate("As I already said, do your job and fix this bug.")
    assert "per my previous email" in corp
    assert "deliverables" in corp

    # 7. Discord minimalist transforms (pure text, no emojis)
    discord = tp.transform_discord("To be honest I do not know this is fire skull.")
    assert "tbh" in discord
    assert "idk" in discord
    assert "fire" in discord
    assert "dead" in discord
    assert not any(ord(c) > 127 for c in discord)
    assert discord == discord.lower()

    # 8. Gangster & Victorian dialect transforms (preserved)
    gangster = tp.transform_gangster("You know I am going to the store with my friend.")
    assert "homie" in gangster
    vic = tp.transform_victorian("Hello, I think you are wrong, sadly it is nonsense.")
    assert "thou art" in vic

    # 9. Brainrot dialect transform (pure text, no emojis)
    brainrot = tp.transform_brainrot("We are in trouble because the server had an error, friend.")
    assert "we are cooked chat" in brainrot.lower()
    assert "ohio glitch" in brainrot.lower()
    assert "blud" in brainrot.lower()
    assert "fr fr" in brainrot.lower()
    assert not any(ord(c) > 127 for c in brainrot)

    # 10. All candidates parallel generation
    cands = tp.generate_all_candidates("We have an error and need to fix it.")
    assert set(cands.keys()) == {"default", "brainrot", "uwu", "schizo", "trump"}
    for k, v in cands.items():
        assert len(v) > 0
        assert not any(ord(c) > 127 for c in v)

    print("[PASS] test_styles_and_polisher (Code, UwU Freak, Brainrot, Schizo, Trump, Boomer, Corporate, Discord, Gangster, Victorian, All Candidates)")


def test_speculative_worker():
    class MockEngine:
        def transcribe(self, audio, initial_prompt=None, strip_fillers=None):
            return "speculative prefix"

    mock_engine = MockEngine()
    sw = SpeculativeWorker(engine=mock_engine, threshold_sec=0.1, chunk_sec=0.05)
    sw.reset()

    audio = np.zeros(16000, dtype=np.float32)
    sw.pretranscribe(audio)
    time.sleep(0.05)

    prefix, tail = sw.get_result(audio)
    assert prefix == "speculative prefix"
    assert tail is not None
    assert len(tail) < len(audio)
    print("[PASS] test_speculative_worker")


def test_injector_scratch_that():
    inj = TextInjector(method="uinput")
    inj._last_injected_length = 5
    inj.inject(SCRATCH_THAT_MARKER)
    assert inj._last_injected_length == 0
    inj.close()
    print("[PASS] test_injector_scratch_that")


def test_listener_arrow_chords():
    # Verify EvdevListener parses all 4 arrow chords on Right Ctrl
    listener = EvdevListener(
        hotkey_map={
            "KEY_RIGHTCTRL": "default",
            "KEY_RIGHTCTRL+KEY_SPACE": "palette",
            "KEY_RIGHTCTRL+KEY_DOWN": "uwu",
            "KEY_RIGHTCTRL+KEY_UP": "brainrot",
            "KEY_RIGHTCTRL+KEY_LEFT": "schizo",
            "KEY_RIGHTCTRL+KEY_RIGHT": "trump",
            "KEY_RIGHTALT": "code",
            "BTN_EXTRA": "raw",
        }
    )
    # Base key
    assert 97 in listener.base_keys
    assert listener.base_keys[97] == "default"

    # Multi-candidate palette chord (Right Ctrl + Space)
    assert (97, 57) in listener.chords
    assert listener.chords[(97, 57)] == "palette"

    # All 4 arrow chords
    assert (97, 108) in listener.chords  # DOWN
    assert listener.chords[(97, 108)] == "uwu"
    assert (97, 103) in listener.chords  # UP
    assert listener.chords[(97, 103)] == "brainrot"
    assert (97, 105) in listener.chords  # LEFT
    assert listener.chords[(97, 105)] == "schizo"
    assert (97, 106) in listener.chords  # RIGHT
    assert listener.chords[(97, 106)] == "trump"

    # All keycodes tracked
    for c in [97, 57, 108, 103, 105, 106]:
        assert c in listener.all_target_codes

    print("[PASS] test_listener_arrow_chords")


def test_model_inference():
    cfg = load_config()
    engine = WhisperEngine(
        model_name=cfg.model.name,
        device=cfg.model.device,
        compute_type=cfg.model.compute_type,
        beam_size=cfg.model.beam_size,
    )
    t = np.linspace(0, 1.5, int(16000 * 1.5), endpoint=False)
    synthetic_audio = (0.2 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)

    t0 = time.perf_counter()
    _ = engine.transcribe(synthetic_audio)
    t1 = time.perf_counter()
    latency_ms = (t1 - t0) * 1000.0
    print(f"[PASS] test_model_inference: processed in {latency_ms:.2f} ms")


if __name__ == "__main__":
    test_config()
    test_noise_suppression()
    test_macros()
    test_cleaner()
    test_styles_and_polisher()
    test_speculative_worker()
    test_injector_scratch_that()
    test_listener_arrow_chords()
    test_model_inference()
    print("\nALL AUDIT TEST SUITES PASSED CLEANLY!")
