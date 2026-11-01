r"""R13 hold-out 验证站启停。

R13 = R2 后端（19202）+ 加固版 WAF（19113）。
**唯一用途是阶段 4 的未污染验证**：盲测 v2 阶段 1 全程不碰它。

为什么要单独一个脚本
====================
R13 复用 R2 的后端与数据库，自身没有独立进程，启停只需：
1. 确保 R2 后端在跑
2. 启用/禁用 nginx 配置 + reload

与 D1/A2 的做法一致（它们也是靠 conf 改名 + reload 启停）。

用法：
    python scripts\r13_start.py start
    python scripts\r13_start.py stop
    python scripts\r13_start.py status
"""

from __future__ import annotations

import os
import subprocess
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NGINX_DIR = os.path.join(ROOT, "nginx")
CONF_DIR = os.path.join(NGINX_DIR, "conf.d")
NAME = "R13"

PORT = 19113
BACKEND = 19202  # 复用 R2 后端


def _paths() -> tuple[str, str]:
    active = os.path.join(CONF_DIR, f"{NAME}.conf")
    disabled = os.path.join(CONF_DIR, f"{NAME}.conf.disabled")
    return active, disabled


def _nginx(*args: str) -> tuple[int, str]:
    exe = os.path.join(NGINX_DIR, "nginx.exe")
    p = subprocess.run([exe] + list(args), cwd=NGINX_DIR, capture_output=True, text=True, timeout=60)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def _port_open(port: int) -> bool:
    import socket

    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1.5):
            return True
    except OSError:
        return False


def _http(url: str, expect: tuple[int, ...] = (200, 302)) -> int:
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(url, timeout=6) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def start() -> int:
    active, disabled = _paths()
    if not os.path.exists(active) and os.path.exists(disabled):
        os.replace(disabled, active)
        print(f"[OK] 启用 {NAME}.conf")
    elif not os.path.exists(active):
        print(f"[FAIL] 找不到 {active}")
        return 1
    else:
        print(f"[SKIP] {NAME}.conf 已启用")

    if not _port_open(BACKEND):
        print(f"[WARN] R2 后端 {BACKEND} 未监听 —— R13 会返回 502")
        print("       先起后端：python scripts\\lab.py up R2")

    rc, out = _nginx("-t")
    if rc != 0:
        print(f"[FAIL] nginx 配置校验失败：\n{out}")
        return 1
    _nginx("-s", "reload")
    print("[OK] nginx 已 reload")

    if _port_open(PORT):
        code = _http(f"http://127.0.0.1:{PORT}/login")
        print(f"[OK] R13 入口就绪 19113（/login -> {code}）")
        return 0
    print(f"[FAIL] {PORT} 未监听")
    return 1


def stop() -> int:
    active, disabled = _paths()
    if os.path.exists(active):
        os.replace(active, disabled)
        print(f"[OK] 停用 {NAME}.conf（改名 .disabled）")
        _nginx("-s", "reload")
    else:
        print(f"[SKIP] {NAME}.conf 未启用")
    return 0


def status() -> int:
    active, disabled = _paths()
    enabled = os.path.exists(active)
    listening = _port_open(PORT)
    backend = _port_open(BACKEND)
    print()
    print(f"  {NAME}")
    print(f"    配置      {'已启用' if enabled else '已停用'}")
    print(f"    入口      {PORT} {'监听中' if listening else '未监听'}")
    print(f"    后端      {BACKEND} {'监听中' if backend else '未监听'}")
    if listening:
        for path in ("/login", "/.git/HEAD", "/?id=1%20union%20select%201"):
            print(f"    {path:32} -> {_http(f'http://127.0.0.1:{PORT}{path}', (200, 302, 403))}")
    print()
    return 0 if enabled and listening else 1


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("start", "stop", "status"):
        print(__doc__)
        return 2
    return {"start": start, "stop": stop, "status": status}[sys.argv[1]]()


if __name__ == "__main__":
    sys.exit(main())
