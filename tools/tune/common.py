"""Durable files, process isolation and resource guards (no game imports)."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

ARENA_SHA = "8b893461c0d020ae8ed9c78aed298cd698e025a0"
RULES = {"stack": 2000, "small_blind": 10, "big_blind": 20,
         "move_timeout": 1.0, "think_budget_per_deal": 0.2, "max_faults": 20,
         "max_pickle_bytes": 25 * 1024 * 1024, "python": [3, 14]}
SITE = "https://poker-arena-site.vercel.app"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def seed_for(root, phase, block):
    # No dependence on candidate or opponent: common deals, disjoint phase namespaces.
    namespace = {"search": 1, "validation": 2, "test": 3, "proposal": 4}.get(
        phase, 5 + int(digest(phase)[:4], 16))
    return (namespace << 60) | int(digest([root, phase, block])[:15], 16)


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def tree_hash(root):
    root = Path(root)
    h = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            h.update(path.relative_to(root).as_posix().encode() + b"\0")
            h.update(path.read_bytes())
    return h.hexdigest()


def python_guard():
    if sys.version_info[:2] != (3, 14):
        raise RuntimeError("Use Python 3.14 and a dedicated arena-only venv.")
    import importlib.util
    for name in ("numpy", "eval7"):
        if importlib.util.find_spec(name) is not None:
            raise RuntimeError(f"{name} is installed: use a clean arena-only venv for runtime fidelity")
    import cloudpickle
    if cloudpickle.__version__ != "3.1.2":
        raise RuntimeError("Install the pinned arena requirements (cloudpickle==3.1.2).")


def cpu_budget(requested=None):
    try:
        cores = len(os.sched_getaffinity(0))
    except AttributeError:
        cores = os.cpu_count() or 2
    budget = max(1, cores - 1)
    if requested is not None:
        if requested < 1:
            raise ValueError("workers must be positive")
        budget = min(budget, requested)
    # Leave at least 2GB for OS; copied sub-1MB policies reserve 0.35GB per simultaneous pairing.
    available = available_memory()
    if available:
        budget = min(budget, max(1, int((available - 2 * 1024**3) / (0.35 * 1024**3))))
    return budget


def available_memory():
    if sys.platform.startswith("linux"):
        try:
            values = Path("/proc/meminfo").read_text().splitlines()
            return int(next(s.split()[1] for s in values if s.startswith("MemAvailable:"))) * 1024
        except (OSError, StopIteration, ValueError):
            return None
    if os.name == "nt":
        import ctypes
        class Status(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong) for name in
                ("total", "available", "page_total", "page_available", "virtual", "virtual_available", "extended")]
        value = Status()
        value.length = ctypes.sizeof(value)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):
            return value.available
    return None


def ensure_disk(path, minimum_gb=4):
    if shutil.disk_usage(path).free < minimum_gb * 1024**3:
        raise RuntimeError(f"Less than {minimum_gb}GB free; stopping safely without deleting results")


def ensure_memory():
    available = available_memory()
    if available is not None and available < 1024**3:
        raise RuntimeError("Less than 1GB available RAM; stopping safely before memory exhaustion")


def stop_tree(proc):
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        pass


def linux_process_identity(pid):
    if not sys.platform.startswith("linux"):
        return None
    try:
        stat = Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1].split()
        return [Path("/proc/sys/kernel/random/boot_id").read_text().strip(), stat[19]]
    except (OSError, IndexError):
        return None


def reap_orphans(run):
    """Recover from coordinator SIGKILL without trusting a reused Linux PID."""
    if not sys.platform.startswith("linux"):
        return 0
    count = 0
    for path in Path(run).glob("jobs/*/attempt-*/process.json"):
        old = read_json(path)
        identity = linux_process_identity(old["pid"])
        if old.get("linux_identity") and identity == old["linux_identity"]:
            try:
                if os.getpgid(old["pid"]) != old["pid"]:
                    raise RuntimeError("Registered worker no longer owns its process group")
                os.killpg(old["pid"], signal.SIGKILL)
                count += 1
            except ProcessLookupError:
                pass
    return count


def run_process(command, *, cwd, timeout, log, stop_event=None):
    """Own a whole match process group; logs go to disk, never an unbounded pipe."""
    if timeout <= 0:
        return {"returncode": None, "timeout": True, "elapsed": 0.0}
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.update({"PYTHONHASHSEED": "0", "PYTHONUNBUFFERED": "1", "PYTHONDONTWRITEBYTECODE": "1",
                "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
    log = Path(log)
    log.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {
        "start_new_session": True}
    with log.open("ab") as output:
        proc = subprocess.Popen(command, cwd=cwd, env=env, stdout=output, stderr=output, **options)
        try:
            atomic_json(log.parent / "process.json", {"pid": proc.pid,
                        "linux_identity": linux_process_identity(proc.pid)})
            while proc.poll() is None:
                if time.monotonic() - started >= timeout or (stop_event and stop_event.is_set()):
                    stop_tree(proc)
                    return {"returncode": proc.poll(), "timeout": True,
                            "elapsed": time.monotonic() - started}
                time.sleep(0.15)
            return {"returncode": proc.returncode, "timeout": False,
                    "elapsed": time.monotonic() - started}
        finally:
            if proc.poll() is None:
                stop_tree(proc)
