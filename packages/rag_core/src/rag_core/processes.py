"""Platform-specific options for isolated worker child processes."""

import subprocess
import sys


def hidden_window_flags() -> int:
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW
    return 0
