r"""C5「暴露但需认证」启停（v1.6 靶场）。

    python scripts\c5_start.py start
    python scripts\c5_start.py stop

为什么要这座靶场
================
v1.6 给未授权类插件加了会话隔离（anonymous()）与 looks_authenticated 第二道防线，
但现有靶场没有一座能复现「接口存在但需认证」这个边界：
  - R1/R7 的相关端点根本不存在（登录后仍 302）
  - C1/C2 的 actuator 本来就未授权暴露，是正样本而非这一类
没有 C5，那条防线就是没被验证过的代码。

形态
====
C2-1b（真实 Spring Boot，/actuator/env 真实暴露 34KB）
  ↑ nginx basic auth
→ 接口真实存在，但必须认证才能访问。

判据（2026-11-02 实测确认）
--------------------------
  未认证扫描          → SAFE（401，拿不到暴露证据）
  **无防护的已认证扫描 → CONFIRMED（假！证据写着「可匿名访问」实际带着凭据）**
  有 A2 防护的已认证扫描 → SAFE（匿名克隆拿到 401，正确判定）

只操作 C5：启用/停用 conf.d\C5.conf 并重载 nginx，不动其它站点。
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
NGINX_EXE = os.path.join(NGINX_DIR, "nginx.exe")
CONF_ACTIVE = os.path.join(NGINX_DIR, "conf.d", "C5.conf")
CONF_DISABLED = os.path.join(NGINX_DIR, "conf.d", "C5.conf.disabled")
HTPASSWD = os.path.join(NGINX_DIR, "c5.htpasswd")
BACKEND_PORT = 19312  # C2-1b


def _reload() -> int:
    return subprocess.call([NGINX_EXE, "-s", "reload"], cwd=NGINX_DIR)


def _ensure_htpasswd() -> None:
    """basic auth 凭据文件。

    用 {PLAIN} 前缀：nginx 原生支持，无需 openssl/htpasswd 工具
    （Windows 靶场环境没有这些）。内容是演示用的固定账号，不是密钥。
    """
    if os.path.exists(HTPASSWD):
        return
    with open(HTPASSWD, "w", newline="\n") as f:
        f.write("c5ops:{PLAIN}Ops_2026_Letmein\n")


def _port_open(port: int) -> bool:
    import socket

    s = socket.socket()
    s.settimeout(1)
    try:
        s.connect(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def start() -> int:
    if not _port_open(BACKEND_PORT):
        print(f"[!] 后端 {BACKEND_PORT}（C2-1b）未启动，请先: python scripts\\lab.py up C2-1b")
        return 1
    _ensure_htpasswd()
    if not os.path.exists(CONF_ACTIVE) and os.path.exists(CONF_DISABLED):
        os.replace(CONF_DISABLED, CONF_ACTIVE)
    rc = _reload()
    if rc != 0:
        print("[FAIL] nginx reload 失败")
        return 1
    print("[OK] C5 已启用：http://127.0.0.1:19351（basic auth c5ops / Ops_2026_Letmein）")
    return 0


def stop() -> int:
    if os.path.exists(CONF_ACTIVE):
        os.replace(CONF_ACTIVE, CONF_DISABLED)
        _reload()
    print("[OK] C5 已停用（19351 释放）")
    return 0


def main() -> int:
    argv = sys.argv[1:]
    cmd = argv[0].lower() if argv else "start"
    if cmd == "start":
        return start()
    if cmd == "stop":
        return stop()
    print("用法: python scripts\\c5_start.py [start|stop]")
    return 2


if __name__ == "__main__":
    sys.exit(main())
