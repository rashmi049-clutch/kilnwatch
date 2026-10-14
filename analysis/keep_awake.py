"""
Keep Windows from idle-sleeping while long jobs run, then let go.

Uses SetThreadExecutionState, the per-process request media players use.
It changes no power settings, lapses automatically when this script exits,
and does not stop sleep from a closed lid or the Start menu.

Usage:
    python analysis/keep_awake.py <pattern> [<pattern> ...]
Stays awake while any running process command line contains a pattern
(checked every 60 s), then exits.
"""

import ctypes
import subprocess
import sys
import time

ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001


def running(patterns: list[str]) -> bool:
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Select-Object -ExpandProperty CommandLine"],
        capture_output=True, text=True).stdout
    # ignore keep_awake itself: its own command line contains the patterns
    lines = [l for l in out.splitlines() if "keep_awake" not in l]
    return any(p in l for l in lines for p in patterns)


def main() -> None:
    patterns = sys.argv[1:]
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    print(f"Holding the system awake while jobs matching {patterns} run", flush=True)
    try:
        while running(patterns):
            time.sleep(60)
    finally:
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        print("Jobs finished; sleep allowed again", flush=True)


if __name__ == "__main__":
    main()
