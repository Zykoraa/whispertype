"""WhisperType background resident daemon with full power-user feature pipeline."""

import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time
from typing import Optional

from whispertype.audio import AudioRecorder
from whispertype.config import Config, StyleConfig, load_config
from whispertype.evdev_listener import EvdevListener
from whispertype.feedback import AudioFeedback
from whispertype.indicator import VisualIndicator
from whispertype.injector import TextInjector
from whispertype.llm import TextPolisher
from whispertype.macros import process_macros, SCRATCH_THAT_MARKER
from whispertype.model import WhisperEngine
from whispertype.noise import NoiseSuppressor
from whispertype.speculative import SpeculativeWorker


def get_socket_path() -> Path:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir and Path(runtime_dir).exists():
        return Path(runtime_dir) / "whispertype.sock"
    return Path.home() / ".local" / "share" / "whispertype" / "whispertype.sock"


class WhisperDaemon:
    def __init__(self, config: Optional[Config] = None):
        self.config = config or load_config()
        self.state = "IDLE"
        self._lock = threading.Lock()
        self._running = False
        self._socket_path = get_socket_path()
        self._server_socket: Optional[socket.socket] = None
        self._current_style_name = "default"

        print("[WhisperType] Initializing audio subsystem...")
        self.recorder = AudioRecorder(
            sample_rate=self.config.audio.sample_rate,
            channels=self.config.audio.channels,
        )
        self.feedback = AudioFeedback(
            enabled=self.config.audio.cues,
            volume=self.config.audio.cue_volume,
        )
        self.indicator = VisualIndicator(
            method=self.config.ui.visual_indicator,
        )
        self.noise_suppressor = NoiseSuppressor(
            enabled=self.config.audio.noise_suppression,
            prop_decrease=self.config.audio.prop_decrease,
        )
        self.injector = TextInjector(
            method=self.config.typing.method,
            wtype_delay_ms=self.config.typing.wtype_delay_ms,
            paste_threshold=self.config.typing.paste_threshold,
            restore_clipboard=self.config.typing.restore_clipboard,
        )

        print("[WhisperType] Initializing NLP and text processing modules...")
        self.polisher = TextPolisher(
            enabled=self.config.llm.polish_mode,
            api_url=self.config.llm.api_url,
            model_name=self.config.llm.model,
            timeout=self.config.llm.timeout,
        )

        print(f"[WhisperType] Initializing CUDA Whisper model ('{self.config.model.name}')...")
        self.engine = WhisperEngine(
            model_name=self.config.model.name,
            device=self.config.model.device,
            compute_type=self.config.model.compute_type,
            beam_size=self.config.model.beam_size,
            language=self.config.model.language,
            initial_prompt=self.config.model.initial_prompt,
            strip_fillers=self.config.text.strip_fillers,
        )

        self.speculative = SpeculativeWorker(engine=self.engine)
        self.recorder.on_threshold_reached = self.speculative.pretranscribe

        print(f"[WhisperType] Initializing evdev listener with triggers: {self.config.triggers}...")
        self.listener = EvdevListener(
            hotkey_map=self.config.triggers,
            hotkey_name=self.config.trigger.hotkey,
            device_name=self.config.trigger.device_name,
            device_path=self.config.trigger.device_path,
            grab=self.config.trigger.grab,
            mode=self.config.trigger.mode,
            on_press=self.on_press,
            on_release=self.on_release,
            on_style_change=self.on_style_change,
        )

    def on_style_change(self, style: str):
        with self._lock:
            if self.state != "RECORDING":
                return
            self._current_style_name = style
            print(f"[WhisperType] Chord modifier engaged: style shifted to '{style}'.")
            self.indicator.show_recording(style=style)

    def on_press(self, style: str = "default"):
        with self._lock:
            if self.state != "IDLE":
                return
            self.state = "RECORDING"
            self._current_style_name = style
            print(f"[WhisperType] Trigger pressed: recording started [style: {style}].")
            self.feedback.play_start()
            self.indicator.show_recording(style=style)
            self.speculative.reset()
            self.recorder.start()

    def on_release(self, style: Optional[str] = None, is_polish: bool = False):
        with self._lock:
            if self.state != "RECORDING":
                return
            self.state = "PROCESSING"
            resolved_style = style or self._current_style_name or "default"
            mode_str = f" [style: {resolved_style}]" + (" (Polish Mode)" if is_polish else "")
            print(f"[WhisperType] Trigger released: processing audio{mode_str}...")
            self.feedback.play_stop()
            self.indicator.show_processing()
            audio = self.recorder.stop()

        # Run transcription in worker thread so evdev loop is non-blocking
        threading.Thread(
            target=self._process_audio,
            args=(audio, resolved_style, is_polish),
            daemon=True,
        ).start()

    def _process_audio(self, audio, style_name: str = "default", is_polish: bool = False):
        try:
            if audio is None:
                print("[WhisperType] Audio clip too short, ignoring.")
                return

            # Resolve style configuration
            style_cfg = self.config.styles.get(
                style_name,
                self.config.styles.get("default", StyleConfig(name=style_name))
            )

            # 1. Acoustic noise suppression (spectral noise gate)
            if self.config.audio.noise_suppression:
                audio = self.noise_suppressor.process(audio, sample_rate=self.config.audio.sample_rate)

            # 2. Vocabulary prompting from active style
            prompt = style_cfg.initial_prompt or self.config.model.initial_prompt

            # 3. Full-context transcription (preserves sentence continuity & grammar)
            full_text = self.engine.transcribe(
                audio,
                initial_prompt=prompt,
                strip_fillers=style_cfg.strip_fillers,
            )

            if not full_text:
                return

            # 4. Spoken macros and formatting ("new line", "snake case", "scratch that")
            text, is_scratch = process_macros(full_text, enabled=style_cfg.macros)

            if is_scratch:
                self.injector.inject(text)
                self.feedback.play_success()
                self.indicator.show_success("Deleted last phrase")
                return

            if style_name == "palette" or style_cfg.personality == "palette":
                # Compute all candidates simultaneously
                candidates = self.polisher.generate_all_candidates(text)
                chosen_style = self._prompt_palette(candidates)
                if not chosen_style or chosen_style == "cancel":
                    print("[WhisperType] Candidate palette canceled or timed out.")
                    return
                text = candidates.get(chosen_style, candidates.get("default", text))
                style_name = chosen_style
            else:
                # 5. Smart Polish / SLM code / dialect transforms
                personality = style_cfg.personality or (
                    "gangster" if (style_cfg.gangster_transform or style_name == "gangster") else (
                        style_name if style_name in ("uwu", "brainrot", "boomer", "corporate", "discord", "victorian") else ""
                    )
                )

                if is_polish or style_cfg.polish or self.config.llm.polish_mode:
                    text = self.polisher.polish(text, style=personality or style_name)
                elif personality == "uwu":
                    text = self.polisher.transform_uwu(text)
                elif personality == "brainrot":
                    text = self.polisher.transform_brainrot(text)
                elif personality == "boomer":
                    text = self.polisher.transform_boomer(text)
                elif personality == "gangster":
                    text = self.polisher.transform_gangster(text)
                elif personality == "corporate":
                    text = self.polisher.transform_corporate(text)
                elif personality == "discord":
                    text = self.polisher.transform_discord(text)
                elif personality == "victorian":
                    text = self.polisher.transform_victorian(text)
                elif style_cfg.code_transform:
                    text = self.polisher.transform_code(text)

                # Casing transforms
                if style_cfg.casing == "lower":
                    text = text.lower()
                elif style_cfg.casing == "upper":
                    text = text.upper()
                elif style_cfg.casing == "title":
                    text = text.title()

                # Custom prefix / suffix
                if style_cfg.prefix:
                    text = style_cfg.prefix + text
                if style_cfg.suffix:
                    text = text + style_cfg.suffix

            # 6. Keystroke injection
            self.injector.inject(text)

            # 7. Auditory & visual confirmation
            self.feedback.play_success()
            self.indicator.show_success(text if text != SCRATCH_THAT_MARKER else "Deleted last phrase")

        except Exception as e:
            print(f"[WhisperType] Error during processing pipeline: {e}")
        finally:
            with self._lock:
                self.state = "IDLE"

    def _prompt_palette(self, candidates: dict) -> str:
        """Launch the floating Wayland candidate selection palette and return selected style."""
        try:
            cmd = [
                "/usr/bin/python3",
                "-m",
                "whispertype.palette",
                "--choices",
                json.dumps(candidates),
                "--timeout",
                str(self.config.palette.timeout_sec),
            ]
            if self.config.palette.auto_inject_default:
                cmd.append("--auto-default")

            env = dict(os.environ)
            project_root = str(Path(__file__).resolve().parent.parent)
            env["PYTHONPATH"] = f"{project_root}:{env.get('PYTHONPATH', '')}"

            proc_timeout = (self.config.palette.timeout_sec + 2.0) if self.config.palette.timeout_sec > 0 else None
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
                timeout=proc_timeout,
            )
            choice = proc.stdout.strip().splitlines()
            if choice:
                return choice[-1].strip()
        except Exception as e:
            print(f"[WhisperType] Error running candidate palette: {e}")
        return "cancel"

    def toggle(self, style: str = "default"):
        with self._lock:
            current_state = self.state

        if current_state == "RECORDING":
            self.on_release()
        elif current_state == "IDLE":
            self.on_press(style=style)

    def _start_socket_server(self):
        if self._socket_path.exists():
            try:
                self._socket_path.unlink()
            except Exception:
                pass
        self._socket_path.parent.mkdir(parents=True, exist_ok=True)

        self._server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server_socket.bind(str(self._socket_path))
        self._server_socket.listen(5)
        self._server_socket.settimeout(0.5)

        print(f"[WhisperType] IPC socket active at {self._socket_path}")

        while self._running:
            try:
                conn, _ = self._server_socket.accept()
            except socket.timeout:
                continue
            except Exception:
                break

            threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()

    def _handle_client(self, conn: socket.socket):
        try:
            conn.settimeout(1.0)
            data = conn.recv(1024).decode("utf-8").strip()
            if not data:
                return

            parts = data.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else "default"

            response = {"status": "ok"}
            if cmd == "hold":
                self.on_press(style=arg)
                response["action"] = f"recording_started_{arg}"
            elif cmd == "release":
                self.on_release()
                response["action"] = "processing_started"
            elif cmd == "toggle":
                self.toggle(style=arg)
                response["action"] = "toggled"
            elif cmd == "status":
                response["state"] = self.state
                response["model"] = self.config.model.name
                response["device"] = self.config.model.device
                response["hotkey"] = self.config.trigger.hotkey
                response["triggers"] = self.config.triggers
                response["styles"] = list(self.config.styles.keys())
                response["noise_suppression"] = self.config.audio.noise_suppression
                response["macros"] = self.config.text.macros
                response["polish_mode"] = self.config.llm.polish_mode
            elif cmd == "stop-daemon":
                response["action"] = "stopping"
                conn.sendall(json.dumps(response).encode("utf-8"))
                conn.close()
                self._running = False
                return
            else:
                response = {"status": "error", "message": f"Unknown command: {data}"}

            conn.sendall(json.dumps(response).encode("utf-8"))
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def run(self):
        self._running = True

        def signal_handler(sig, frame):
            print("\n[WhisperType] Received termination signal. Exiting cleanly...")
            self._running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Start hardware input listener
        self.listener.start()

        print("[WhisperType] Daemon ready! Triggers mapped:")
        for key, style in self.config.triggers.items():
            print(f"  • {key:24s} -> style: {style}")

        # Start IPC socket thread
        socket_thread = threading.Thread(target=self._start_socket_server, daemon=True)
        socket_thread.start()

        while self._running:
            time.sleep(0.2)

        # Cleanup
        self.listener.stop()
        self.recorder.close()
        self.injector.close()
        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass
        if self._socket_path.exists():
            try:
                self._socket_path.unlink()
            except Exception:
                pass
        print("[WhisperType] Shutdown complete.")


def main():
    daemon = WhisperDaemon()
    daemon.run()


if __name__ == "__main__":
    main()
