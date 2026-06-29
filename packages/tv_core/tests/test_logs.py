import os

from tv_core.logs import prune_logs, read_log_tail


def _write(path, text):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def test_returns_empty_when_no_log_files(tmp_path):
    assert read_log_tail(str(tmp_path), 100) == ""


def test_returns_whole_log_when_shorter_than_limit(tmp_path):
    _write(tmp_path / "plugin.log", "a\nb\n")
    assert read_log_tail(str(tmp_path), 100) == "a\nb\n"


def test_keeps_only_the_last_lines(tmp_path):
    _write(tmp_path / "plugin.log", "1\n2\n3\n4\n")
    assert read_log_tail(str(tmp_path), 2) == "3\n4\n"


def test_reads_the_most_recently_modified_log(tmp_path):
    old, new = tmp_path / "old.log", tmp_path / "new.log"
    _write(old, "old\n")
    _write(new, "new\n")
    os.utime(old, (1, 1))
    os.utime(new, (2, 2))
    assert read_log_tail(str(tmp_path), 100) == "new\n"


def test_reads_a_non_log_file_when_no_dot_log_exists(tmp_path):
    _write(tmp_path / "plugin.txt", "hello\n")
    assert read_log_tail(str(tmp_path), 100) == "hello\n"


def test_prefers_dot_log_over_other_files(tmp_path):
    _write(tmp_path / "other.txt", "txt\n")
    _write(tmp_path / "plugin.log", "log\n")
    assert read_log_tail(str(tmp_path), 100) == "log\n"


def test_prune_keeps_only_the_newest_log(tmp_path):
    old, new = tmp_path / "old.log", tmp_path / "new.log"
    _write(old, "old\n")
    _write(new, "new\n")
    os.utime(old, (1, 1))
    os.utime(new, (2, 2))
    prune_logs(str(tmp_path))
    assert os.path.exists(new)
    assert not os.path.exists(old)


def test_prune_is_a_noop_for_a_single_log(tmp_path):
    only = tmp_path / "plugin.log"
    _write(only, "x\n")
    prune_logs(str(tmp_path))
    assert os.path.exists(only)


def test_prune_handles_empty_dir(tmp_path):
    prune_logs(str(tmp_path))
