"""CLI interface for controlling WhisperType daemon."""

import json
from pathlib import Path
import socket
import sys
from whispertype.config import DEFAULT_CONFIG_PATH
from whispertype.daemon import get_socket_path


def send_command(cmd: str) -> dict:
    sock_path = get_socket_path()
    if not sock_path.exists():
        print(f"[WhisperType] Error: Daemon is not running (socket not found at {sock_path}).", file=sys.stderr)
        sys.exit(1)

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(str(sock_path))
        s.sendall(cmd.encode("utf-8"))
        data = s.recv(4096).decode("utf-8")
        if data:
            return json.loads(data)
        return {}
    except Exception as e:
        print(f"[WhisperType] Failed to communicate with daemon: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        s.close()


def print_help():
    print("""WhisperType - Instant Voice Dictation CLI

Usage:
  whispertype <command> [args]

Commands:
  status               Check daemon status (state, model, hotkeys, styles)
  hold [style]         Start dictation recording (e.g. 'hold', 'hold code', 'hold raw')
  release              Stop recording and transcribe
  toggle [style]       Toggle recording state (optional style)
  config               Show configuration file path and contents
  stop-daemon          Gracefully terminate background daemon
  help                 Show this help message
""")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print_help()
        return

    cmd = sys.argv[1].lower()
    arg = sys.argv[2] if len(sys.argv) > 2 else ""

    if cmd == "status":
        res = send_command("status")
        print("WhisperType Daemon:")
        print(f"  State:         {res.get('state', 'UNKNOWN')}")
        print(f"  Model:         {res.get('model', 'UNKNOWN')}")
        print(f"  Device:        {res.get('device', 'UNKNOWN')}")
        print(f"  Triggers:      {res.get('triggers', {})}")
        print(f"  Styles:        {', '.join(res.get('styles', []))}")
        print(f"  Noise Reduct:  {res.get('noise_suppression', False)}")
        print(f"  Verbal Macros: {res.get('macros', False)}")
        print(f"  Polish Mode:   {res.get('polish_mode', False)}")
    elif cmd in ("hold", "record", "start"):
        full_cmd = f"hold {arg}".strip()
        res = send_command(full_cmd)
        print(f"Action: {res.get('action')}")
    elif cmd in ("release", "stop"):
        res = send_command("release")
        print(f"Action: {res.get('action')}")
    elif cmd == "toggle":
        full_cmd = f"toggle {arg}".strip()
        res = send_command(full_cmd)
        print(f"Action: {res.get('action')}")
    elif cmd in ("stop-daemon", "kill", "exit"):
        res = send_command("stop-daemon")
        print(f"Action: {res.get('action')}")
    elif cmd == "config":
        print(f"Config path: {DEFAULT_CONFIG_PATH}")
        if DEFAULT_CONFIG_PATH.exists():
            print("\n" + DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
        else:
            print("No config file found (daemon will generate defaults on first run).")
    else:
        print(f"Unknown command: '{cmd}'. Run 'whispertype help' for usage.")
        sys.exit(1)


if __name__ == "__main__":
    main()
