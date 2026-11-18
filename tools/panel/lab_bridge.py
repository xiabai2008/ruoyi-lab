r"""靶场脚本桥接层。

职责边界
--------
- **只读复用**：用 importlib 按路径加载 `scripts/lab.py` 与 `scripts/labenv.py`，
  拿注册表、探针和 PID 工具；不修改靶场脚本。
- **启停 shell out**：`lab.py up/down` 会阻塞、打印、spawn 子进程，且有退出码
  不可靠的问题，所以面板只把它们当子进程调用，不在 FastAPI 事件循环里直接执行。
- **补齐 lab.py 没有的能力**：Y1 不在注册表里；C5 没有 PID 文件；R12 没有独立
  进程；Y1/R12 需要切换 nginx conf。这些特殊逻辑集中在这里。

注意：`lab.py` import 时会把 stdout/stderr 重配成 UTF-8，并读取一次
`LAB_MYSQLD` / `LAB_REDIS_DIR` 等环境变量；面板在 import 前先把 `labenv`
解析出的值写回环境，避免 `lab.py` 不读 `lab.local.json` 导致路径不一致。
"""

from __future__ import annotations

import base64
import ctypes
import importlib.util
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

# ── 路径 ──
LAB_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = LAB_ROOT / "scripts"
NGINX_DIR = LAB_ROOT / "nginx"
CONF_DIR = NGINX_DIR / "conf.d"
STATE_DIR = LAB_ROOT / ".state"

# 靶场脚本用 urllib 探针；如果不绕过代理，127.0.0.1 可能被 HTTP_PROXY 劫持。
for _k in ("NO_PROXY", "no_proxy"):
    os.environ.setdefault(_k, "127.0.0.1,localhost")


def _load_module(name: str, path: Path):
    """按文件路径加载模块，避免与 ruoyi-scan 的 lab 包重名。"""
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载模块: {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


LABENV = _load_module("ruoyi_labenv", SCRIPTS / "labenv.py")

# 先对齐环境，再加载 lab.py：lab.py 在 import 时就会读取这些变量。
os.environ.setdefault("LAB_MYSQLD", LABENV.MYSQLD)
os.environ.setdefault("LAB_MYSQL_INI", LABENV.MYSQL_INI)
os.environ.setdefault("LAB_REDIS_DIR", LABENV.REDIS_DIR)

LAB = _load_module("ruoyi_lab_cli", SCRIPTS / "lab.py")

# 面板启动时用 lab.local.json 里配置的 Python 跑子进程；找不到再退回当前解释器。
PYTHON = LABENV.PYTHON if os.path.isfile(LABENV.PYTHON) else sys.executable

_CREATION_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0

# 需要靠 nginx conf 启停的目标（Y1/R12 由面板切换，其它由各自脚本切换）。
CONF_NAMES: dict[str, str] = {
    "R12": "R12",
    "R13": "R13",
    "A2": "A2",
    "D1": "D1",
    "C5": "C5",
    "Y1": "Y1",
}

Y1_ENTRY = 19115
Y1_BACKEND = 19251
Y1_PROBE = "/admin-api/system/tenant/simple-list"
C5_ENTRY = 19351
C5_BACKEND = 19312
C5_PROBE = "/actuator/env"


# ── 基础网络 / PID ──

def port_open(port: int, host: str = "127.0.0.1", timeout: float = 1.0) -> bool:
    if not port:
        return True
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        return bool(LAB.pid_alive(pid))
    except Exception:
        return False


def _read_pid_file(name: str) -> int | None:
    p = STATE_DIR / name
    try:
        return int(p.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def read_pid(tid: str) -> int | None:
    if tid == "Y1":
        return _read_pid_file("Y1.pid")
    try:
        return LAB.read_pid(tid)
    except Exception:
        return None


# ── nginx conf 切换 ──

def conf_active_path(name: str) -> Path:
    return CONF_DIR / f"{name}.conf"


def conf_disabled_path(name: str) -> Path:
    return CONF_DIR / f"{name}.conf.disabled"


def conf_enabled(name: str | None) -> bool:
    return bool(name) and conf_active_path(name).is_file()


def conf_present(name: str | None) -> bool:
    return bool(name) and (conf_active_path(name).is_file() or conf_disabled_path(name).is_file())


def nginx_pid() -> int | None:
    return _nginx_pid_file()


def _nginx_pid_file() -> int | None:
    p = NGINX_DIR / "logs" / "nginx.pid"
    try:
        return int(p.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def nginx_running() -> bool:
    pid = _nginx_pid_file()
    if pid and pid_alive(pid):
        return True
    # pid 文件可能被清掉 / 进程被外部拉起；用入口端口兜底。
    # 19101/19109/19111 是默认启用的 R1/R9/R11 入口，Nginx 在跑时至少有一个通。
    for port in (19101, 19109, 19111):
        if port_open(port, timeout=0.25):
            return True
    return False


def _child_env() -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "NO_PROXY": "127.0.0.1,localhost",
            "no_proxy": "127.0.0.1,localhost",
            # 让子进程里的 labenv 与面板解析结果一致，而不是再次读文件。
            "LAB_PYTHON": PYTHON,
            "LAB_JDK8": LABENV.JDK8_HOME,
            "LAB_JDK17": LABENV.JDK17_HOME,
            "LAB_MVN": LABENV.MVN_HOME,
            "LAB_MYSQLD": LABENV.MYSQLD,
            "LAB_MYSQL_INI": LABENV.MYSQL_INI,
            "LAB_REDIS_DIR": LABENV.REDIS_DIR,
        }
    )
    return env


def run_capture(cmd: list[str | Path], cwd: Path = LAB_ROOT, timeout: int = 60) -> tuple[int, str]:
    try:
        p = subprocess.run(
            [str(x) for x in cmd],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=_child_env(),
        )
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as exc:  # noqa: BLE001 - 统一转成可读错误
        return -1, str(exc)


def nginx_test() -> tuple[int, str]:
    exe = NGINX_DIR / "nginx.exe"
    if not exe.is_file():
        return -1, f"找不到 {exe}"
    return run_capture([exe, "-t"], cwd=NGINX_DIR)


def nginx_reload() -> tuple[int, str]:
    exe = NGINX_DIR / "nginx.exe"
    if not exe.is_file():
        return -1, f"找不到 {exe}"
    if not nginx_running():
        return 0, "nginx 未运行，跳过 reload"
    return run_capture([exe, "-s", "reload"], cwd=NGINX_DIR)


def enable_conf(name: str, enable: bool) -> str:
    """启用/停用 nginx conf，并在 nginx 运行时校验 + reload。

    失败时尽量回滚，避免留下一个“配置启用但 nginx 起不来”的入口。
    """
    active = conf_active_path(name)
    disabled = conf_disabled_path(name)

    if enable:
        if active.is_file():
            msg = f"{name}.conf 已启用"
        elif disabled.is_file():
            os.replace(disabled, active)
            msg = f"启用 {name}.conf"
        else:
            raise FileNotFoundError(f"找不到 {active} 或 {disabled}")
    else:
        if active.is_file():
            os.replace(active, disabled)
            msg = f"停用 {name}.conf"
        else:
            msg = f"{name}.conf 已停用"

    rc, out = nginx_test()
    if rc != 0:
        if enable and active.is_file() and disabled.parent.is_dir():
            os.replace(active, disabled)
        raise RuntimeError(f"nginx 配置校验失败：{out.strip()}")

    if nginx_running():
        rc, out = nginx_reload()
        if rc != 0:
            raise RuntimeError(f"nginx reload 失败：{out.strip()}")
        msg += "，nginx 已 reload"
    else:
        msg += "（nginx 未运行，启动时生效）"
    return msg


# ── 子进程执行 ──

def run_stream(
    args: list[str | Path],
    cwd: Path = LAB_ROOT,
    on_line=None,
    timeout: int = 900,
) -> int:
    """逐行执行命令并回调日志；超时会 kill 子进程。"""
    cmd = [str(x) for x in args]
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=_child_env(),
            creationflags=_CREATION_FLAGS,
        )
    except Exception as exc:  # noqa: BLE001
        if on_line:
            on_line(f"[panel] 启动命令失败: {exc}")
        return -1

    timed_out = threading.Event()

    def _kill() -> None:
        timed_out.set()
        try:
            proc.kill()
        except Exception:
            pass

    timer = threading.Timer(timeout, _kill) if timeout else None
    if timer:
        timer.daemon = True
        timer.start()

    try:
        assert proc.stdout is not None
        for raw_line in proc.stdout:
            line = raw_line.rstrip("\r\n")
            if on_line:
                try:
                    on_line(line)
                except Exception:
                    pass
        proc.wait()
    finally:
        if timer:
            timer.cancel()

    if timed_out.is_set():
        if on_line:
            on_line(f"[panel] 命令超时（{timeout}s），已终止")
        return -9
    return proc.returncode if proc.returncode is not None else -1


# ── HTTP 探针（不跟随重定向、不走代理）──

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())


def http_code(url: str, headers: dict[str, str] | None = None, timeout: float = 4.0) -> int:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with _OPENER.open(req, timeout=timeout) as resp:
            return int(resp.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except Exception:
        return 0


def wait_port(port: int, timeout: float = 90.0, interval: float = 1.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_open(port):
            return True
        time.sleep(interval)
    return port_open(port)


def wait_http(url: str, expect: tuple[int, ...] | set[int], timeout: float = 30.0) -> int:
    deadline = time.time() + timeout
    code = 0
    while time.time() < deadline:
        code = http_code(url, timeout=4.0)
        if code in expect:
            return code
        time.sleep(1.0)
    return code


# ── 运行状态 ──

def check_y1() -> dict:
    backend = port_open(Y1_BACKEND, timeout=0.35)
    entry = port_open(Y1_ENTRY, timeout=0.35)
    code = http_code(f"http://127.0.0.1:{Y1_ENTRY}{Y1_PROBE}", timeout=4.0) if entry else 0
    if backend and entry and code == 200:
        state, detail = "UP", f"后端{Y1_BACKEND}=ok 入口{Y1_ENTRY}=ok {Y1_PROBE}=200"
    elif backend and entry:
        state = "DEGRADED"
        detail = f"后端{Y1_BACKEND}=ok 入口{Y1_ENTRY}=ok 探针{Y1_PROBE}={code}（期望200）"
    elif backend:
        state, detail = "DEGRADED", f"后端{Y1_BACKEND}=ok 入口{Y1_ENTRY}未监听"
    elif entry:
        state, detail = "DEGRADED", f"入口{Y1_ENTRY}=ok 后端{Y1_BACKEND}未监听"
    else:
        state, detail = "DOWN", f"入口 {Y1_ENTRY} 未监听"

    pid = read_pid("Y1")
    return {
        "name": "Y1",
        "state": state,
        "detail": detail,
        "pid": pid,
        "pid_alive": pid_alive(pid),
        "backend_up": backend,
        "entry_up": entry,
        "probe_code": code,
        "conf_name": "Y1",
        "conf_enabled": conf_enabled("Y1"),
    }


def _c5_auth_header() -> dict[str, str]:
    token = base64.b64encode(b"c5ops:Ops_2026_Letmein").decode("ascii")
    return {"Authorization": f"Basic {token}"}


def check_c5() -> dict:
    entry = port_open(C5_ENTRY, timeout=0.35)
    backend = port_open(C5_BACKEND, timeout=0.35)
    anon = http_code(f"http://127.0.0.1:{C5_ENTRY}{C5_PROBE}", timeout=4.0) if entry else 0
    auth = http_code(
        f"http://127.0.0.1:{C5_ENTRY}{C5_PROBE}", headers=_c5_auth_header(), timeout=4.0
    ) if entry else 0

    if entry and anon == 401 and backend:
        state, detail = "UP", f"入口{C5_ENTRY}=ok 后端{C5_BACKEND}=ok {C5_PROBE}=401"
    elif entry and anon == 401:
        state, detail = "DEGRADED", f"入口{C5_ENTRY}=ok 401，但后端{C5_BACKEND}未监听"
    elif entry:
        state = "DEGRADED"
        detail = f"入口{C5_ENTRY}=ok 探针{C5_PROBE}={anon}（期望401）"
    elif backend:
        state, detail = "DEGRADED", f"后端{C5_BACKEND}=ok 入口{C5_ENTRY}未监听"
    else:
        state, detail = "DOWN", f"入口 {C5_ENTRY} 未监听"

    warning = ""
    if auth not in (0, 200):
        warning = f"带 Basic 认证访问返回 {auth}（期望200，C2-1b 可能是 safe 模式）"
    elif entry and anon == 401 and auth == 200:
        warning = ""

    return {
        "name": "C5",
        "state": state,
        "detail": detail,
        "pid": None,
        "pid_alive": False,
        "anonymous_code": anon,
        "auth_code": auth,
        "backend_up": backend,
        "entry_up": entry,
        "warning": warning,
        "conf_name": "C5",
        "conf_enabled": conf_enabled("C5"),
    }


def _enrich(tid: str, raw: dict) -> dict:
    raw = dict(raw)
    if "pid" not in raw:
        raw["pid"] = read_pid(tid)
    raw["pid_alive"] = bool(raw.get("pid") and pid_alive(raw.get("pid")))
    conf_name = CONF_NAMES.get(tid)
    raw["conf_name"] = conf_name
    raw["conf_enabled"] = conf_enabled(conf_name) if conf_name else None
    raw.setdefault("state", "DOWN")
    return raw


def check_runtime(tid: str) -> dict:
    if tid == "Y1":
        raw = check_y1()
    elif tid == "C5":
        raw = check_c5()
    elif tid == "infra:nginx":
        up = nginx_running()
        pid = _nginx_pid_file()
        raw = {
            "name": tid,
            "state": "UP" if up else "DOWN",
            "detail": "Nginx 进程在运行" if up else "Nginx 未运行",
            "pid": pid,
            "pid_alive": pid_alive(pid),
        }
    else:
        cfg = LAB.SITES.get(tid)
        # 快路径：入口都没监听时，lab.check 必然返回 DOWN；先快速判掉，
        # 避免每个 DOWN 目标都等两次 1s 的 TCP 超时（Windows 上实测会等满）。
        if cfg and not port_open(cfg["entry"], timeout=0.35):
            raw = {"name": tid, "state": "DOWN", "detail": f"入口 {cfg['entry']} 未监听", "pid": None}
            return _enrich(tid, raw)
        try:
            raw = dict(LAB.check(tid))
        except Exception as exc:  # noqa: BLE001
            raw = {"name": tid, "state": "DOWN", "detail": f"检查异常: {exc}", "pid": None}
        cfg = LAB.SITES.get(tid)
        if cfg and cfg.get("backend"):
            # 供派生状态区分「后端已停、Nginx 入口还在 502」与真正的探针异常。
            raw["backend_up"] = port_open(cfg["backend"], timeout=0.35)
    return _enrich(tid, raw)


def target_ready(tid: str) -> bool:
    if tid in ("C2-1a", "C2-1b"):
        return (
            check_runtime("C2-1a").get("state") == "UP"
            and check_runtime("C2-1b").get("state") == "UP"
        )
    return check_runtime(tid).get("state") == "UP"


def target_stopped(tid: str) -> bool:
    if tid in ("C2-1a", "C2-1b"):
        return (
            check_runtime("C2-1a").get("state") == "DOWN"
            and check_runtime("C2-1b").get("state") == "DOWN"
        )
    if tid == "infra:nginx":
        return not nginx_running()
    if tid == "Y1":
        return (not port_open(Y1_BACKEND)) and (not conf_enabled("Y1"))
    if tid == "C5":
        return (not port_open(C5_ENTRY)) and (not conf_enabled("C5"))
    if tid == "R12":
        return (not port_open(19112)) and (not conf_enabled("R12"))

    cfg = LAB.SITES.get(tid) if hasattr(LAB, "SITES") else None
    conf_name = CONF_NAMES.get(tid)
    if conf_name:
        # 配置还开着就不算“已停止”：允许用户点停止把 conf 禁用掉，
        # 避免 nginx 没运行时看起来已停、实际配置还处于启用状态。
        return not conf_enabled(conf_name)
    if cfg:
        backend = cfg.get("backend") or cfg["entry"]
        raw = check_runtime(tid)
        return (not port_open(backend)) and (not raw.get("pid_alive"))
    raw = check_runtime(tid)
    return raw.get("state") == "DOWN" and not raw.get("pid_alive")


def dependency_ready(tid: str) -> bool:
    if tid == "infra:mysql":
        return port_open(13307, timeout=0.35)
    if tid == "infra:redis":
        return port_open(6379, timeout=0.35)
    if tid == "infra:nginx":
        return nginx_running()
    if tid == "C4-1":
        return port_open(16379, timeout=0.35)
    if tid == "C2-1b":
        return port_open(C5_BACKEND, timeout=0.35)
    return target_ready(tid)


# ── 内存 / 日志 ──

class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def available_memory_mb() -> int | None:
    if os.name != "nt":
        return None
    try:
        stat = _MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            return None
        return int(stat.ullAvailPhys // (1024 * 1024))
    except Exception:
        return None


def tail_logs(paths: list[str], lines: int = 200, max_bytes: int = 256 * 1024) -> list[dict]:
    out: list[dict] = []
    for rel in paths:
        p = Path(rel)
        if not p.is_absolute():
            p = LAB_ROOT / p
        item = {"path": str(p), "exists": p.is_file(), "lines": [], "truncated": False}
        if p.is_file():
            try:
                size = p.stat().st_size
                with p.open("rb") as fh:
                    if size > max_bytes:
                        fh.seek(size - max_bytes)
                        item["truncated"] = True
                    data = fh.read()
                text = data.decode("utf-8", errors="replace")
                item["lines"] = text.splitlines()[-lines:]
                if item["truncated"] and item["lines"]:
                    item["lines"] = item["lines"][1:]
            except OSError as exc:
                item["error"] = str(exc)
        out.append(item)
    return out
