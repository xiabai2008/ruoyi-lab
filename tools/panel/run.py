r"""面板启动入口。

    python -m tools.panel.run
    python -m tools.panel.run --port 19500 --no-browser

也可以直接 `python tools\panel\run.py`。默认只绑定 127.0.0.1。
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[2]
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

for _k in ("NO_PROXY", "no_proxy"):
    os.environ.setdefault(_k, "127.0.0.1,localhost")


def _open_browser(url: str, port: int) -> None:
    """等 uvicorn 开始监听后再开浏览器，避免打开一个连接失败页。"""
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.4)
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="若依靶场 Web 管理平台")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址，默认 127.0.0.1")
    parser.add_argument("--port", type=int, default=19500, help="监听端口，默认 19500")
    parser.add_argument("--no-browser", action="store_true", help="启动后不自动打开浏览器")
    parser.add_argument("--reload", action="store_true", help="开发模式：文件变化自动重载")
    args = parser.parse_args(argv)

    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print("[!] 警告：面板默认设计为仅本机使用；当前监听地址不是回环地址。")
        print("[!]       靶场本身包含故意漏洞，不建议把管理入口暴露到局域网。")

    url = f"http://127.0.0.1:{args.port}"
    print("=" * 64)
    print("  若依靶场 Web 管理平台")
    print("=" * 64)
    print(f"  靶场根目录 : {LAB_ROOT}")
    print(f"  访问地址   : {url}")
    print(f"  API 文档   : {url}/api/docs")
    print("  关闭本窗口不会停止已启动的靶场。")
    print("=" * 64)

    if not args.no_browser:
        threading.Thread(target=_open_browser, args=(url, args.port), daemon=True).start()

    try:
        import uvicorn
    except ImportError:
        print("[FAIL] 缺少 uvicorn，请先安装：")
        print(f'       "{sys.executable}" -m pip install -r tools\\panel\\requirements.txt')
        return 1

    uvicorn.run(
        "tools.panel.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
