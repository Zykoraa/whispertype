"""Low-latency evdev hardware event listener with chord combination support."""

from pathlib import Path
import selectors
import threading
import time
from typing import Callable, Dict, List, Optional, Set, Tuple
import evdev


class EvdevListener:
    def __init__(
        self,
        hotkey_map: Optional[Dict[str, str]] = None,
        hotkey_name: str = "KEY_RIGHTCTRL",
        device_name: str = "",
        device_path: str = "",
        grab: bool = False,
        mode: str = "hybrid",
        on_press: Optional[Callable[..., None]] = None,
        on_release: Optional[Callable[..., None]] = None,
        on_style_change: Optional[Callable[[str], None]] = None,
    ):
        raw_map = hotkey_map if hotkey_map else {hotkey_name: "default"}
        self.base_keys: Dict[int, str] = {}
        # chords: {(base_code, mod_code): style_name}
        self.chords: Dict[Tuple[int, int], str] = {}
        self.all_target_codes: Set[int] = set()

        for key_str, style_name in raw_map.items():
            if "+" in key_str:
                parts = [p.strip() for p in key_str.split("+") if p.strip()]
                if len(parts) >= 2:
                    base_name, mod_name = parts[0], parts[1]
                    b_code = getattr(evdev.ecodes, base_name, None) or evdev.ecodes.ecodes.get(base_name)
                    m_code = getattr(evdev.ecodes, mod_name, None) or evdev.ecodes.ecodes.get(mod_name)
                    if b_code is not None and m_code is not None:
                        self.chords[(b_code, m_code)] = style_name
                        self.all_target_codes.add(b_code)
                        self.all_target_codes.add(m_code)
                    else:
                        print(f"[WhisperType] Warning: Could not resolve chord '{key_str}'.")
            else:
                code = getattr(evdev.ecodes, key_str, None) or evdev.ecodes.ecodes.get(key_str)
                if code is not None:
                    self.base_keys[code] = style_name
                    self.all_target_codes.add(code)
                else:
                    print(f"[WhisperType] Warning: Unknown evdev key code '{key_str}', ignoring.")

        if not self.base_keys:
            default_code = getattr(evdev.ecodes, "KEY_RIGHTCTRL", 97)
            self.base_keys[default_code] = "default"
            self.all_target_codes.add(default_code)

        self.device_name = device_name
        self.device_path = device_path
        self.grab = grab
        self.mode = mode
        self.on_press = on_press
        self.on_release = on_release
        self.on_style_change = on_style_change

        self._devices: List[evdev.InputDevice] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._selector = selectors.DefaultSelector()
        self._active_code: Optional[int] = None
        self._active_style: Optional[str] = None
        self._press_time: float = 0.0
        self._is_latched: bool = False
        self._latched_code: Optional[int] = None
        self._latched_style: Optional[str] = None

    def get_all_active_keys(self) -> Set[int]:
        active_set: Set[int] = set()
        for dev in self._devices:
            try:
                active_set.update(dev.active_keys())
            except Exception:
                pass
        return active_set

    def find_devices(self) -> List[evdev.InputDevice]:
        matched: List[evdev.InputDevice] = []

        if self.device_path and Path(self.device_path).exists():
            try:
                dev = evdev.InputDevice(self.device_path)
                matched.append(dev)
                return matched
            except Exception as e:
                print(f"[WhisperType] Failed to open explicit device {self.device_path}: {e}")

        for path in evdev.list_devices():
            try:
                dev = evdev.InputDevice(path)
                caps = dev.capabilities()
                if evdev.ecodes.EV_KEY not in caps:
                    continue

                # Filter out our own virtual keyboard device
                if "whispertype" in dev.name.lower():
                    continue

                supported_keys = set(caps[evdev.ecodes.EV_KEY])
                if self.all_target_codes & supported_keys:
                    matched.append(dev)
            except Exception:
                continue

        return matched

    def start(self):
        self._devices = self.find_devices()
        if not self._devices:
            key_names = [evdev.ecodes.KEY.get(c, evdev.ecodes.BTN.get(c, str(c))) for c in self.all_target_codes]
            print(f"[WhisperType] Warning: No input devices found supporting target keys: {key_names}.")
            return

        for dev in self._devices:
            print(f"[WhisperType] Listening to input device: {dev.name} ({dev.path})")
            if self.grab:
                try:
                    dev.grab()
                except Exception as e:
                    print(f"[WhisperType] Could not grab device {dev.path}: {e}")
            self._selector.register(dev, selectors.EVENT_READ)

        self._running = True
        self._thread = threading.Thread(target=self._event_loop, daemon=True)
        self._thread.start()

    def _event_loop(self):
        while self._running:
            events = self._selector.select(timeout=0.1)
            for key, mask in events:
                dev: evdev.InputDevice = key.fileobj
                try:
                    for ev in dev.read():
                        if ev.type != evdev.ecodes.EV_KEY:
                            continue
                        if ev.code not in self.all_target_codes:
                            continue

                        # Case 0: If currently latched in hands-free toggle mode, tapping hotkey stops recording
                        if self._is_latched and ev.value == 1 and ev.code in self.base_keys:
                            self._is_latched = False
                            active_style = self._latched_style or self.base_keys.get(ev.code, "default")
                            self._latched_code = None
                            self._latched_style = None
                            self._active_code = None
                            self._active_style = None
                            print(f"[WhisperType] Hands-free toggle stop triggered [style: {active_style}].")
                            if self.on_release:
                                self.on_release(active_style, is_polish=False)
                            continue

                        # Case 1: Base hotkey pressed down
                        if ev.code in self.base_keys and ev.value == 1 and self._active_code is None and not self._is_latched:
                            self._press_time = time.perf_counter()
                            active_held = self.get_all_active_keys()
                            resolved_style = self.base_keys[ev.code]
                            for (b, m), c_style in self.chords.items():
                                if b == ev.code and m in active_held:
                                    resolved_style = c_style
                                    break

                            self._active_code = ev.code
                            self._active_style = resolved_style

                            if self.on_press:
                                try:
                                    self.on_press(resolved_style)
                                except TypeError:
                                    self.on_press()

                        # Case 2: Modifier pressed WHILE base hotkey is held
                        elif (
                            self._active_code is not None
                            and ev.value == 1
                            and (self._active_code, ev.code) in self.chords
                        ):
                            chord_style = self.chords[(self._active_code, ev.code)]
                            if self._active_style != chord_style:
                                self._active_style = chord_style
                                if self.on_style_change:
                                    try:
                                        self.on_style_change(chord_style)
                                    except Exception:
                                        pass

                        # Case 3: Active base key released
                        elif ev.code == self._active_code and ev.value == 0:
                            duration = time.perf_counter() - self._press_time
                            active_style = self._active_style or self.base_keys.get(ev.code, "default")

                            if (self.mode == "hybrid" and duration < 0.28) or self.mode == "toggle":
                                # Quick tap: Latch ON for hands-free recording
                                self._is_latched = True
                                self._latched_code = ev.code
                                self._latched_style = active_style
                                self._active_code = None
                                self._active_style = None
                                print(f"[WhisperType] Quick tap detected ({duration*1000:.0f}ms): Hands-free recording latched ON [style: {active_style}]. Tap again to finish.")
                                continue

                            # Normal hold-to-talk release
                            self._active_code = None
                            self._active_style = None
                            self._is_latched = False

                            is_polish = False
                            try:
                                active = dev.active_keys()
                                if (
                                    evdev.ecodes.KEY_LEFTSHIFT in active
                                    or evdev.ecodes.KEY_RIGHTSHIFT in active
                                ):
                                    is_polish = True
                            except Exception:
                                pass

                            if self.on_release:
                                try:
                                    self.on_release(active_style, is_polish=is_polish)
                                except TypeError:
                                    try:
                                        self.on_release(is_polish=is_polish)
                                    except TypeError:
                                        self.on_release()

                except OSError:
                    pass
                except Exception as e:
                    print(f"[WhisperType] Evdev read error: {e}")

    def stop(self):
        self._running = False
        for dev in self._devices:
            try:
                self._selector.unregister(dev)
                if self.grab:
                    dev.ungrab()
                dev.close()
            except Exception:
                pass
        self._devices.clear()
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
