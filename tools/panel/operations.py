r"""操作队列：单工作线程串行执行靶场启停。

为什么串行
----------
`lab.py up` 会拉起 MySQL/Redis/Nginx，多个操作并发会抢端口、写同一个 PID 文件，
R8 还会和其他靶场抢内存。面板用一条队列串行执行，UI 显示“排队中”。

日志与事件
----------
每个操作保留最近 2000 行日志，通过 SSE 实时推送；HTTP 轮询作为兜底。
"""

from __future__ import annotations

import queue
import threading
import uuid
from collections import OrderedDict, deque
from datetime import datetime

from . import catalog
from . import lab_bridge as lb


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _clock() -> str:
    return datetime.now().strftime("%H:%M:%S")


class OperationConflict(Exception):
    """同一目标（或 C2 对）已有排队/执行中的操作。"""


class Operation:
    def __init__(
        self,
        action: str,
        units: list[dict],
        title: str,
        targets: list[str] | None = None,
        abort_on_failure: bool = False,
    ) -> None:
        self.id = "op_" + datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
        self.action = action
        self.title = title
        self.units = [dict(u) for u in units]
        self.targets = list(targets) if targets is not None else [u["target"] for u in self.units]
        self.abort_on_failure = abort_on_failure
        self.steps: list[dict] = []
        self.status = "queued"
        self.created_at = _now()
        self.started_at: str | None = None
        self.finished_at: str | None = None
        self.error = ""
        self.logs: deque[str] = deque(maxlen=2000)
        self.lock = threading.RLock()
        self.cancelled = False

    def add_step(self, target: str, action: str, role: str = "main", unit_target: str | None = None) -> dict:
        with self.lock:
            step = {
                "id": len(self.steps) + 1,
                "target": target,
                "action": action,
                "role": role,
                "unit_target": unit_target or target,
                "status": "queued",
                "message": "",
                "started_at": None,
                "finished_at": None,
            }
            self.steps.append(step)
            return step

    def log(self, line: str) -> None:
        line = (line or "").rstrip()
        if not line:
            return
        with self.lock:
            self.logs.append(f"[{_clock()}] {line}")

    def public(self) -> dict:
        with self.lock:
            steps = [dict(s) for s in self.steps]
            done = sum(1 for s in steps if s["status"] in ("success", "failed", "skipped"))
            total = len(steps)
            return {
                "id": self.id,
                "action": self.action,
                "title": self.title,
                "targets": list(self.targets),
                "units": [dict(u) for u in self.units],
                "status": self.status,
                "created_at": self.created_at,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "error": self.error,
                "steps": steps,
                "progress": int(done / total * 100) if total else 0,
                "step_done": done,
                "step_total": total,
                "log_count": len(self.logs),
                "cancellable": self.status == "queued",
            }

    def full(self) -> dict:
        data = self.public()
        with self.lock:
            data["logs"] = list(self.logs)
        return data


class OperationManager:
    def __init__(self, poller) -> None:
        self.poller = poller
        self._queue: queue.Queue = queue.Queue()
        self._ops: OrderedDict[str, Operation] = OrderedDict()
        self._lock = threading.RLock()
        self._subs: set[queue.Queue] = set()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ── 生命周期 ──

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="panel-ops", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._queue.put(None)
        if self._thread:
            self._thread.join(timeout=5)

    # ── 订阅 ──

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=2000)
        with self._lock:
            self._subs.add(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            self._subs.discard(q)

    def _publish(self, event: dict) -> None:
        with self._lock:
            subs = list(self._subs)
        for q in subs:
            try:
                q.put_nowait(event)
            except queue.Full:
                pass

    # ── 提交 ──

    def _register(self, op: Operation) -> None:
        with self._lock:
            active = set()
            for other in self._ops.values():
                if other.status in ("queued", "running"):
                    for unit in other.units:
                        active.add(self._lifecycle_key(unit["target"]))
            overlap = active & {self._lifecycle_key(u["target"]) for u in op.units}
            if overlap:
                raise OperationConflict(
                    "以下目标已有操作排队/执行中：" + "、".join(sorted(overlap))
                )
            self._ops[op.id] = op
            while len(self._ops) > 20:
                self._ops.popitem(last=False)
        self._publish({"type": "op", "op": op.public()})

    @staticmethod
    def _lifecycle_key(tid: str) -> str:
        # C2-1a/1b 共享 c2_sba.py 生命周期，不能只按目标名去重。
        return "C2-1" if tid in ("C2-1a", "C2-1b") else tid

    def submit(
        self,
        action: str,
        units: list[dict],
        title: str,
        targets: list[str] | None = None,
        abort_on_failure: bool = False,
    ) -> Operation:
        op = Operation(action, units, title, targets, abort_on_failure)
        self._register(op)
        self._queue.put(op)
        return op

    def submit_start(self, tid: str) -> Operation:
        return self.submit("start", [{"target": tid, "action": "start"}], f"启动 {tid}", [tid])

    def submit_stop(self, tid: str) -> Operation:
        return self.submit("stop", [{"target": tid, "action": "stop"}], f"停止 {tid}", [tid])

    def submit_group(self, group: str, action: str) -> Operation:
        label = catalog.GROUP_LABELS.get(group, group)
        if action == "start":
            ids = catalog.group_start_plan(group)
            units = [{"target": t, "action": "start"} for t in ids]
            title = f"启动分组：{label}"
        else:
            ids = catalog.stop_order(catalog.UI_GROUPS.get(group, []))
            units = [{"target": t, "action": "stop"} for t in ids]
            title = f"停止分组：{label}"
        return self.submit(action, units, title, ids)

    def submit_stop_all(self) -> Operation:
        ids = catalog.stop_all_plan()
        units = [{"target": t, "action": "stop"} for t in ids]
        return self.submit("stop", units, "全部停止（保留 MySQL / Redis）", ids)

    def submit_clean(self) -> Operation:
        return self.submit("clean", [{"target": "system", "action": "clean"}], "清理僵尸 PID", ["system"])

    def submit_r8(self, conflicts: list[str]) -> Operation:
        stop_ids = catalog.stop_order(conflicts)
        units = [{"target": t, "action": "stop"} for t in stop_ids]
        units.append({"target": "R8", "action": "start"})
        return self.submit(
            "start",
            units,
            "停止冲突靶场并启动 R8",
            stop_ids + ["R8"],
            abort_on_failure=True,
        )

    # ── 查询 ──

    def recent(self) -> list[dict]:
        with self._lock:
            ops = list(self._ops.values())
        return [op.public() for op in reversed(ops)]

    def get(self, op_id: str) -> dict | None:
        with self._lock:
            op = self._ops.get(op_id)
        return op.full() if op else None

    def active_map(self) -> dict[str, str]:
        """target -> QUEUED / STARTING / STOPPING，供前端覆盖展示状态。"""
        with self._lock:
            ops = list(self._ops.values())
        out: dict[str, str] = {}
        for op in ops:
            if op.status not in ("queued", "running"):
                continue
            for unit in op.units:
                state = "QUEUED" if op.status == "queued" else (
                    "STARTING" if unit["action"] == "start" else "STOPPING"
                )
                out.setdefault(unit["target"], state)
        return out

    def cancel(self, op_id: str) -> bool:
        with self._lock:
            op = self._ops.get(op_id)
            if not op or op.status != "queued":
                return False
            op.cancelled = True
            op.status = "cancelled"
            op.finished_at = _now()
        self._publish({"type": "op", "op": op.public()})
        return True

    # ── 执行 ──

    def _run(self) -> None:
        while not self._stop.is_set():
            op = self._queue.get()
            if op is None:
                break
            if op.cancelled:
                continue
            try:
                self._execute(op)
            except Exception as exc:  # noqa: BLE001 - worker 不能死
                with op.lock:
                    op.status = "failed"
                    op.error = f"未捕获异常: {exc}"
                    op.finished_at = _now()
                op.log(f"[panel] 未捕获异常: {exc}")
                self._publish({"type": "op", "op": op.public()})

    def _execute(self, op: Operation) -> None:
        with op.lock:
            op.status = "running"
            op.started_at = _now()
        self._publish({"type": "op", "op": op.public()})
        self._log(op, f"[panel] 开始操作：{op.title}")

        failed = 0
        total = len(op.units)
        aborted = False
        for unit in op.units:
            if self._stop.is_set():
                with op.lock:
                    op.status = "cancelled"
                break
            try:
                ok = self._run_unit(op, unit["target"], unit["action"])
            except Exception as exc:  # noqa: BLE001
                ok = False
                self._log(op, f"[panel] {unit['target']} 执行异常: {exc}")
            if not ok:
                failed += 1
                if op.abort_on_failure:
                    aborted = True
                    self._log(op, "[panel] 前置步骤失败，取消后续启动")
                    break

        with op.lock:
            if op.status != "cancelled":
                if aborted:
                    op.status = "failed"
                    op.error = "前置步骤失败，已取消后续启动"
                elif failed == 0:
                    op.status = "success"
                elif failed < total:
                    op.status = "partial"
                    op.error = f"{failed}/{total} 个目标未成功"
                else:
                    op.status = "failed"
                    op.error = f"{failed}/{total} 个目标未成功"
            op.finished_at = _now()

        self._log(op, f"[panel] 操作结束：{op.status}")
        self._publish({"type": "op", "op": op.public()})
        level = "success" if op.status == "success" else ("warning" if op.status == "partial" else "error")
        self._publish({"type": "toast", "level": level, "message": f"{op.title}：{op.status}"})
        self.poller.refresh_now()

    def _run_unit(self, op: Operation, tid: str, action: str) -> bool:
        if action == "clean":
            step = op.add_step("system", "clean", "main", "system")
            self._set_step(op, step, "running")
            self._log(op, "[panel] $ python scripts\\lab.py clean")
            rc = lb.run_stream([lb.PYTHON, "scripts/lab.py", "clean"], on_line=lambda x: self._log(op, x), timeout=120)
            if rc == 0:
                self._set_step(op, step, "success", "僵尸 PID 已清理")
                return True
            self._set_step(op, step, "failed", f"rc={rc}")
            return False

        if action == "start":
            if not catalog.can_start_build(tid):
                main = op.add_step(tid, "start", "main", tid)
                self._set_step(op, main, "failed", "构建不完整，无法启动")
                self._log(op, f"[panel] {tid} 构建不完整，跳过启动；{catalog.TARGETS[tid].build_hint}")
                return False
            plan = catalog.start_plan(tid)
            for dep in plan[:-1]:
                if self._stop.is_set():
                    return False
                if lb.dependency_ready(dep):
                    step = op.add_step(dep, "start", "dep", tid)
                    self._set_step(op, step, "skipped", "已在运行")
                    continue
                step = op.add_step(dep, "start", "dep", tid)
                self._set_step(op, step, "running")
                if not self._do_step(op, step, dep, "start"):
                    main = op.add_step(tid, "start", "main", tid)
                    self._set_step(op, main, "skipped", f"依赖 {dep} 启动失败")
                    return False

            main = op.add_step(tid, "start", "main", tid)
            if lb.target_ready(tid):
                self._set_step(op, main, "skipped", "已在运行")
                return True
            self._set_step(op, main, "running")
            return self._do_step(op, main, tid, "start")

        # stop
        step = op.add_step(tid, "stop", "main", tid)
        if lb.target_stopped(tid):
            self._set_step(op, step, "skipped", "已停止")
            return True
        self._set_step(op, step, "running")
        return self._do_step(op, step, tid, "stop")

    def _do_step(self, op: Operation, step: dict, tid: str, action: str) -> bool:
        self._log(op, f"[panel] === {action} {tid} ===")
        rc = -1
        try:
            rc = self._start_target(op, tid) if action == "start" else self._stop_target(op, tid)
        except Exception as exc:  # noqa: BLE001
            self._log(op, f"[panel] 执行异常: {exc}")

        if action == "start":
            ok = lb.target_ready(tid)
            detail = lb.check_runtime(tid).get("detail", "")
            if ok and rc != 0:
                self._log(op, f"[panel] 命令返回 {rc}，但探针已通过")
            if ok:
                self._set_step(op, step, "success", f"rc={rc}；{detail}"[:400])
                self._log(op, f"[panel] {action} {tid} 成功（rc={rc}）")
                return True
            self._set_step(op, step, "failed", f"rc={rc}；{detail}"[:400])
            self._log(op, f"[panel] {action} {tid} 失败（rc={rc}）：{detail}")
            return False

        ok = lb.target_stopped(tid)
        detail = lb.check_runtime(tid).get("detail", "")
        if ok and rc != 0:
            self._log(op, f"[panel] 命令返回 {rc}，但目标已停止")
        if ok:
            self._set_step(op, step, "success", f"rc={rc}；{detail}"[:400])
            self._log(op, f"[panel] {action} {tid} 成功（rc={rc}）")
            return True
        self._set_step(op, step, "failed", f"rc={rc}；{detail}"[:400])
        self._log(op, f"[panel] {action} {tid} 失败（rc={rc}）：{detail}")
        return False

    def _start_target(self, op: Operation, tid: str) -> int:
        log = lambda line: self._log(op, line)  # noqa: E731
        t = catalog.TARGETS[tid]

        if t.lifecycle == "r12":
            log("[panel] 启用 R12.conf ...")
            log("[panel] " + lb.enable_conf("R12", True))
            rc = lb.run_stream([lb.PYTHON, "scripts/lab.py", "up", "R12"], on_line=log, timeout=600)
            if not lb.target_ready("R12"):
                log("[panel] R12 未就绪，回滚 R12.conf")
                try:
                    log("[panel] " + lb.enable_conf("R12", False))
                except Exception as exc:  # noqa: BLE001
                    log(f"[panel] 回滚 R12.conf 失败: {exc}")
            return rc

        if t.lifecycle == "y1":
            # 后端已经在跑时，重复执行 y1_start.py start 会再 spawn 一个 JVM 抢 19251，
            # 并把 PID 文件覆盖成失败进程。这里只补齐 nginx 入口。
            if lb.port_open(19251, timeout=0.5):
                log("[panel] Y1 后端已在运行，只补齐入口 ...")
                try:
                    log("[panel] " + lb.enable_conf("Y1", True))
                except Exception as exc:  # noqa: BLE001
                    log(f"[panel] 启用 Y1.conf 失败: {exc}")
                    return -1
                _rc2, out = lb.nginx_reload()
                if out.strip():
                    log(f"[panel] {out.strip()}")
                code = lb.wait_http(f"http://127.0.0.1:{lb.Y1_ENTRY}{lb.Y1_PROBE}", (200,), timeout=60)
                log(f"[panel] Y1 入口探针返回 {code}")
                return 0

            log("[panel] 启用 Y1.conf ...")
            try:
                log("[panel] " + lb.enable_conf("Y1", True))
            except Exception as exc:  # noqa: BLE001
                log(f"[panel] 启用 Y1.conf 失败: {exc}")
                return -1
            rc = lb.run_stream([lb.PYTHON, "scripts/y1_start.py", "start"], on_line=log, timeout=600)
            log("[panel] 等待 Y1 后端 19251 就绪（最多 120s）...")
            if not lb.wait_port(19251, timeout=120):
                log("[panel] Y1 后端未就绪，回滚 Y1.conf")
                try:
                    log("[panel] " + lb.enable_conf("Y1", False))
                except Exception as exc:  # noqa: BLE001
                    log(f"[panel] 回滚 Y1.conf 失败: {exc}")
                return rc if rc != 0 else -1
            log("[panel] Y1 后端已就绪，reload nginx ...")
            _rc2, out = lb.nginx_reload()
            if out.strip():
                log(f"[panel] {out.strip()}")
            log("[panel] 等待 Y1 入口探针 ...")
            code = lb.wait_http(f"http://127.0.0.1:{lb.Y1_ENTRY}{lb.Y1_PROBE}", (200,), timeout=60)
            log(f"[panel] Y1 入口探针返回 {code}")
            return rc

        cmd = catalog.command_for(tid, "start")
        log("[panel] $ " + " ".join(str(x) for x in cmd))
        timeout = 900 if tid == "R8" else 600
        return lb.run_stream(cmd, on_line=log, timeout=timeout)

    def _stop_target(self, op: Operation, tid: str) -> int:
        log = lambda line: self._log(op, line)  # noqa: E731
        t = catalog.TARGETS[tid]

        if t.lifecycle == "r12":
            log("[panel] 禁用 R12.conf ...")
            log("[panel] " + lb.enable_conf("R12", False))
            return 0

        if t.lifecycle == "y1":
            log("[panel] $ python scripts\\y1_start.py stop")
            rc = lb.run_stream([lb.PYTHON, "scripts/y1_start.py", "stop"], on_line=log, timeout=300)
            log("[panel] 禁用 Y1.conf ...")
            try:
                log("[panel] " + lb.enable_conf("Y1", False))
            except Exception as exc:  # noqa: BLE001
                log(f"[panel] 禁用 Y1.conf 失败: {exc}")
            return rc

        cmd = catalog.command_for(tid, "stop")
        log("[panel] $ " + " ".join(str(x) for x in cmd))
        return lb.run_stream(cmd, on_line=log, timeout=300)

    def _set_step(self, op: Operation, step: dict, status: str, message: str = "") -> None:
        with op.lock:
            step["status"] = status
            step["message"] = message
            if status == "running":
                step["started_at"] = _now()
            if status in ("success", "failed", "skipped"):
                step["finished_at"] = _now()
        self._publish({"type": "op", "op": op.public()})

    def _log(self, op: Operation, line: str) -> None:
        if line is None:
            return
        line = str(line).rstrip()
        if not line:
            return
        op.log(line)
        self._publish({"type": "log", "op_id": op.id, "line": line, "ts": _now()})
