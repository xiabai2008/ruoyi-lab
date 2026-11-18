r"""运行状态轮询与派生展示状态。

`lab.check()` 只给 UP / DEGRADED / DOWN，无法区分“人为停止”和“坏了”：
- 共享 Nginx 时，停掉后端后入口仍在监听，`lab.py status` 会显示 DEGRADED；
- PID 文件残留时看起来像还在运行；
- R12/R13/A2/D1/C5/Y1 的启停靠 nginx conf，入口状态不等于配置状态。

这里叠加 PID 存活、conf 启用状态和构建状态，得到面板展示用的：
RUNNING / DEGRADED / STOPPED / BROKEN / NOT_READY。
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from . import catalog, lab_bridge as lb


def derive_display_state(tid: str, raw: dict, build_state: str, nginx_up: bool = True) -> tuple[str, str]:
    state = raw.get("state", "DOWN")

    if tid == "Y1":
        if state == "UP":
            return "RUNNING", "后端与入口探针通过"
        if raw.get("backend_up") and not raw.get("conf_enabled"):
            return "DEGRADED", "后端运行中，Y1.conf 未启用"
        if state == "DEGRADED":
            return "DEGRADED", raw.get("detail", "")
        if build_state in ("unbuilt", "absent"):
            return "NOT_READY", "构建产物不完整"
        if raw.get("conf_enabled"):
            if not nginx_up:
                return "STOPPED", "Nginx 未运行，入口未提供"
            return "BROKEN", "入口配置启用但后端未运行"
        return "STOPPED", "后端未运行"

    if state == "UP":
        return "RUNNING", "探针通过"

    if state == "DEGRADED":
        if raw.get("pid") and not raw.get("pid_alive"):
            return "STOPPED", "PID 文件残留，进程已退出"
        if raw.get("conf_name") and raw.get("conf_enabled") is False:
            return "STOPPED", "入口配置已禁用"
        if raw.get("backend_up") is False:
            if raw.get("pid_alive"):
                return "BROKEN", "进程存活但后端端口不通"
            if not raw.get("conf_name"):
                return "STOPPED", "后端已停止（Nginx 入口仍在，返回 502）"
        return "DEGRADED", raw.get("detail", "")

    # DOWN
    if raw.get("pid") and raw.get("pid_alive"):
        return "BROKEN", "进程存活但端口不通"
    if build_state in ("unbuilt", "absent"):
        return "NOT_READY", "构建产物不完整"
    if raw.get("conf_name") and raw.get("conf_enabled"):
        if not nginx_up:
            return "STOPPED", "Nginx 未运行，入口未提供"
        return "BROKEN", "入口配置启用但端口不通"
    return "STOPPED", "已停止"


class StatusPoller:
    def __init__(self, interval: float = 5.0, max_workers: int = 12) -> None:
        self.interval = interval
        self.max_workers = max_workers
        self._snapshot: dict[str, dict] = {}
        self._generated_at: str | None = None
        self._duration_ms: int | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self._cycles = 0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="panel-status", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=8)

    def refresh_now(self) -> None:
        """请求尽快刷新一次（操作结束后调用）。"""
        self._wake.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.refresh_once()
            except Exception:  # noqa: BLE001 - 轮询线程不能死
                pass
            self._wake.wait(self.interval)
            self._wake.clear()

    def refresh_once(self) -> None:
        started = time.time()
        tids = list(catalog.TARGETS)

        def one(tid: str) -> tuple[str, dict]:
            try:
                return tid, lb.check_runtime(tid)
            except Exception as exc:  # noqa: BLE001
                return tid, {"state": "DOWN", "detail": f"检查异常: {exc}"}

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            results = dict(pool.map(one, tids))

        checked_at = datetime.now().isoformat(timespec="seconds")
        nginx_up = lb.nginx_running()
        states: dict[str, dict] = {}
        for tid, raw in results.items():
            build_state = catalog.build_info(tid).get("state", "absent")
            display, reason = derive_display_state(tid, raw, build_state, nginx_up)
            item = dict(raw)
            item.update({
                "display_state": display,
                "display_reason": reason,
                "build_state": build_state,
                "checked_at": checked_at,
            })
            states[tid] = item

        with self._lock:
            self._snapshot = states
            self._generated_at = checked_at
            self._duration_ms = int((time.time() - started) * 1000)
            self._cycles += 1

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "states": dict(self._snapshot),
                "generated_at": self._generated_at,
                "duration_ms": self._duration_ms,
                "cycles": self._cycles,
                "interval": self.interval,
            }

    def get(self, tid: str) -> dict:
        with self._lock:
            return dict(self._snapshot.get(tid, {}))
