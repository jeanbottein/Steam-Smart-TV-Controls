"""Read and prune the plugin's own log files so the UI can display them.

Brand-agnostic: the log directory is whatever Decky hands the plugin.
"""

import glob
import os
from collections import deque


def _newest_first(paths):
    return sorted(paths, key=os.path.getmtime, reverse=True)


def _log_files(log_dir):
    return glob.glob(os.path.join(log_dir, "*.log"))


def _readable_files(log_dir):
    """Prefer *.log; fall back to any file so the viewer is never blank just from naming."""
    logs = _log_files(log_dir)
    if logs:
        return logs
    return [path for path in glob.glob(os.path.join(log_dir, "*")) if os.path.isfile(path)]


def _tail(path, max_lines):
    try:
        with open(path, encoding="utf-8", errors="ignore") as handle:
            return "".join(deque(handle, maxlen=max_lines))
    except OSError:
        return ""


def read_log_tail(log_dir, max_lines):
    """Return the last `max_lines` lines of the newest readable file, or ""."""
    files = _newest_first(_readable_files(log_dir))
    if not files:
        return ""
    return _tail(files[0], max_lines)


def prune_logs(log_dir, keep=1):
    """Delete all but the newest `keep` .log files (never touches other files)."""
    for path in _newest_first(_log_files(log_dir))[keep:]:
        try:
            os.remove(path)
        except OSError:
            pass
