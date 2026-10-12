"""Process facts read without setuid ps: a pid's exec env, CPU time, children.

Darwin reads the kernel via sysctl(KERN_PROCARGS2) and proc_pidinfo; Linux
reads /proc. Every function fails toward None or [] and never raises.

Constants and struct proc_taskinfo layout verified 2026-10-13 against the
MacOSX SDK headers (sys/sysctl.h, sys/proc_info.h): CTL_KERN 1,
KERN_PROCARGS2 49, PROC_PIDTASKINFO 4, six uint64 then twelve int32 fields
(96 bytes), pti_total_user at offset 16, pti_total_system at offset 24.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import subprocess
import sys
from pathlib import Path

CTL_KERN = 1
KERN_PROCARGS2 = 49
PROC_PIDTASKINFO = 4
TASKINFO_SIZE = 96  # struct proc_taskinfo: 6 x uint64 + 12 x int32


def _split_env(entries: list[bytes]) -> dict[str, str]:
    env: dict[str, str] = {}
    for entry in entries:
        key, sep, value = entry.partition(b"=")
        if sep:
            env[os.fsdecode(key)] = os.fsdecode(value)
    return env


def _darwin_exec_env(pid: int) -> dict[str, str] | None:
    libc = ctypes.CDLL(ctypes.util.find_library("c"))
    mib = (ctypes.c_int * 3)(CTL_KERN, KERN_PROCARGS2, pid)
    size = ctypes.c_size_t(0)
    if libc.sysctl(mib, ctypes.c_uint(3), None, ctypes.byref(size), None, ctypes.c_size_t(0)) != 0:
        return None
    buf = ctypes.create_string_buffer(size.value)
    if libc.sysctl(mib, ctypes.c_uint(3), buf, ctypes.byref(size), None, ctypes.c_size_t(0)) != 0:
        return None
    raw = buf.raw[: size.value]
    argc = int.from_bytes(raw[:4], sys.byteorder)
    parts = raw[4:].split(b"\0")
    i = 1  # parts[0] is the exec path
    while i < len(parts) and parts[i] == b"":
        i += 1  # NUL padding after the exec path
    i += argc
    env_entries: list[bytes] = []
    for part in parts[i:]:
        if part == b"":
            break
        env_entries.append(part)
    return _split_env(env_entries)


def exec_env(pid: int) -> dict[str, str] | None:
    """The environment `pid` was exec'd with, or None if unreadable."""
    try:
        if sys.platform == "darwin":
            return _darwin_exec_env(pid)
        if sys.platform.startswith("linux"):
            entries = Path(f"/proc/{pid}/environ").read_bytes().split(b"\0")
            if entries and entries[-1] == b"":
                entries.pop()
            return _split_env(entries)
    except (OSError, ValueError):
        return None
    return None


def _darwin_cpu_seconds(pid: int) -> float | None:
    libproc = ctypes.CDLL(ctypes.util.find_library("proc"))
    buf = ctypes.create_string_buffer(TASKINFO_SIZE)
    n = libproc.proc_pidinfo(
        pid, PROC_PIDTASKINFO, ctypes.c_uint64(0), ctypes.byref(buf), TASKINFO_SIZE
    )
    if n != TASKINFO_SIZE:
        return None
    user = int.from_bytes(buf.raw[16:24], sys.byteorder)
    system = int.from_bytes(buf.raw[24:32], sys.byteorder)
    libc = ctypes.CDLL(ctypes.util.find_library("c"))
    timebase = (ctypes.c_uint32 * 2)(0, 0)  # struct mach_timebase_info {numer, denom}
    if libc.mach_timebase_info(ctypes.byref(timebase)) != 0 or timebase[1] == 0:
        return None
    numer, denom = timebase[0], timebase[1]
    return (user + system) * numer / denom / 1e9


def cpu_seconds(pid: int) -> float | None:
    """Total user + system CPU seconds of `pid`, or None if unreadable."""
    try:
        if sys.platform == "darwin":
            return _darwin_cpu_seconds(pid)
        if sys.platform.startswith("linux"):
            stat = Path(f"/proc/{pid}/stat").read_text()
            tail = stat[stat.rindex(")") + 1 :].split()
            return (int(tail[11]) + int(tail[12])) / os.sysconf("SC_CLK_TCK")
    except (OSError, ValueError, IndexError):
        return None
    return None


def child_names(pid: int) -> list[tuple[int, str]]:
    """(pid, short name) of each direct child of `pid`, via pgrep."""
    try:
        out = subprocess.run(
            ["pgrep", "-l", "-P", str(pid)],
            capture_output=True,
            text=True,
            errors="surrogateescape",
            timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    children: list[tuple[int, str]] = []
    for line in out.splitlines():
        pid_str, _, name = line.partition(" ")
        if pid_str.isdigit():
            children.append((int(pid_str), name))
    return children
