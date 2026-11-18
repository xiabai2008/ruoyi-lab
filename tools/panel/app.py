r"""FastAPI 应用：状态、构建扫描、启停操作、SSE 日志。

默认只监听 127.0.0.1。所有写操作要求 `X-Lab-Panel: 1` 请求头：
本地浏览器同源请求会带，跨站表单/fetch 不带；配合不启用 CORS，
可以挡住“恶意网页偷偷启动靶场”这类本地 CSRF。
"""

from __future__ import annotations

import json
import mimetypes
import queue
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import __version__, catalog
from . import lab_bridge as lb
from .operations import OperationConflict, OperationManager
from .status_poller import StatusPoller

STATIC_DIR = Path(__file__).resolve().parent / "static"
STARTED_AT = time.time()

# Windows 注册表经常把 .js 映射成 text/plain，浏览器会拒绝执行并报
# “strict MIME type checking is enabled”。这里显式覆盖。
_MEDIA_TYPES = {
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
}
for _ext, _mime in _MEDIA_TYPES.items():
    mimetypes.add_type(_mime.split(";")[0], _ext)


class _PanelStaticFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if isinstance(response, FileResponse):
            media = _MEDIA_TYPES.get(Path(path).suffix.lower())
            if media:
                response.media_type = media
                response.headers["content-type"] = media
        return response


poller = StatusPoller()
manager = OperationManager(poller)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    catalog.rescan_build()
    poller.start()
    manager.start()
    try:
        yield
    finally:
        poller.stop()
        manager.stop()


app = FastAPI(
    title="若依靶场管理平台",
    version=__version__,
    description="本地靶场构建扫描、运行状态与启停控制",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
)


@app.middleware("http")
async def _security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    return response


def require_panel(x_lab_panel: str | None = Header(default=None, alias="X-Lab-Panel")) -> None:
    if x_lab_panel != "1":
        raise HTTPException(status_code=403, detail="缺少 X-Lab-Panel 请求头")


class ConfirmBody(BaseModel):
    confirm: bool = False


def _submit_or_409(fn):
    try:
        return fn()
    except OperationConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _target_views() -> tuple[list[dict], dict, dict[str, str]]:
    views = catalog.list_targets()
    snap = poller.snapshot()
    states = snap.get("states", {})
    active = manager.active_map()
    for target in views:
        status = dict(states.get(target["id"], {}))
        op_state = active.get(target["id"])
        if op_state:
            status["operation_state"] = op_state
            status["display_state"] = op_state
            status["display_reason"] = {
                "QUEUED": "排队中",
                "STARTING": "启动中",
                "STOPPING": "停止中",
            }.get(op_state, op_state)
        target["status"] = status
    return views, snap, active


def _targets_payload() -> dict:
    views, snap, active = _target_views()
    return {
        "lab_root": str(lb.LAB_ROOT),
        "version": __version__,
        "scanned_at": catalog.scan_time(),
        "status_at": snap.get("generated_at"),
        "status_duration_ms": snap.get("duration_ms"),
        "groups": catalog.groups(),
        "environment": catalog.environment_checks(),
        "targets": views,
        "operations": manager.recent(),
        "active": active,
        "server_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


# ── 页面 ──

@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html", media_type="text/html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


app.mount("/static", _PanelStaticFiles(directory=str(STATIC_DIR)), name="static")


# ── 基础 ──

@app.get("/api/health")
def api_health():
    return {
        "ok": True,
        "version": __version__,
        "lab_root": str(lb.LAB_ROOT),
        "python": lb.PYTHON,
        "uptime_seconds": int(time.time() - STARTED_AT),
    }


@app.get("/api/targets")
def api_targets():
    return _targets_payload()


@app.get("/api/status")
def api_status():
    return {
        "snapshot": poller.snapshot(),
        "active": manager.active_map(),
        "operations": manager.recent(),
    }


@app.post("/api/scan", dependencies=[Depends(require_panel)])
def api_scan():
    catalog.rescan_build()
    poller.refresh_now()
    return _targets_payload()


@app.post("/api/clean", dependencies=[Depends(require_panel)])
def api_clean():
    op = _submit_or_409(lambda: manager.submit_clean())
    return {"operation": op.public()}


# ── 单站 ──

@app.post("/api/targets/{tid}/start", dependencies=[Depends(require_panel)])
def api_start(
    tid: str,
    stop_conflicts: bool = Query(default=False),
    ignore_memory: bool = Query(default=False),
):
    if tid not in catalog.TARGETS:
        raise HTTPException(status_code=404, detail=f"未知靶场: {tid}")
    if tid in manager.active_map():
        raise HTTPException(status_code=409, detail=f"{tid} 已有操作排队/执行中")
    if not catalog.can_start_build(tid):
        raise HTTPException(
            status_code=409,
            detail={"message": f"{tid} 构建产物不完整，无法启动", "build": catalog.build_info(tid)},
        )
    if lb.target_ready(tid):
        raise HTTPException(status_code=409, detail=f"{tid} 已在运行")

    if tid == "R8":
        conflicts = catalog.running_conflicts_for_r8()
        if conflicts and not stop_conflicts:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "R8 是独占型靶场，以下靶场还在运行，需要先停止",
                    "conflicts": conflicts,
                    "code": "r8_conflicts",
                },
            )
        mem = lb.available_memory_mb()
        if mem is not None and mem < 3200 and not ignore_memory and not (conflicts and stop_conflicts):
            raise HTTPException(
                status_code=409,
                detail={
                    "message": f"可用物理内存不足（{mem} MB < 3200 MB）",
                    "available_mb": mem,
                    "code": "r8_memory",
                },
            )
        op = _submit_or_409(
            lambda: manager.submit_r8(conflicts) if conflicts else manager.submit_start("R8")
        )
        return {"operation": op.public()}

    op = _submit_or_409(lambda: manager.submit_start(tid))
    return {"operation": op.public()}


@app.post("/api/targets/{tid}/stop", dependencies=[Depends(require_panel)])
def api_stop(tid: str):
    if tid not in catalog.TARGETS:
        raise HTTPException(status_code=404, detail=f"未知靶场: {tid}")
    if tid in manager.active_map():
        raise HTTPException(status_code=409, detail=f"{tid} 已有操作排队/执行中")
    if tid in ("infra:mysql", "infra:redis"):
        raise HTTPException(
            status_code=409,
            detail=f"{tid} 由 lab.py 保守管理，面板不提供停止；避免误停后影响其他靶场",
        )
    if lb.target_stopped(tid):
        raise HTTPException(status_code=409, detail=f"{tid} 已停止")
    op = _submit_or_409(lambda: manager.submit_stop(tid))
    return {"operation": op.public()}


@app.get("/api/targets/{tid}/log")
def api_target_log(tid: str, lines: int = Query(default=200, ge=20, le=1000)):
    if tid not in catalog.TARGETS:
        raise HTTPException(status_code=404, detail=f"未知靶场: {tid}")
    paths = catalog.log_paths_for(tid)
    if not paths:
        return {"id": tid, "files": [], "note": "该目标没有映射的运行日志，请查看操作日志"}
    return {"id": tid, "files": lb.tail_logs(paths, lines=lines)}


# ── 分组 / 批量 ──

@app.post("/api/groups/{group}/start", dependencies=[Depends(require_panel)])
def api_group_start(group: str):
    if group not in catalog.UI_GROUPS:
        raise HTTPException(status_code=404, detail=f"未知分组: {group}")
    ids = catalog.group_start_plan(group)
    if not ids:
        raise HTTPException(status_code=400, detail="该分组没有可启动的目标")
    op = _submit_or_409(lambda: manager.submit_group(group, "start"))
    return {"operation": op.public(), "targets": ids}


@app.post("/api/groups/{group}/stop", dependencies=[Depends(require_panel)])
def api_group_stop(group: str):
    if group not in catalog.UI_GROUPS:
        raise HTTPException(status_code=404, detail=f"未知分组: {group}")
    ids = catalog.stop_order(catalog.UI_GROUPS.get(group, []))
    op = _submit_or_409(lambda: manager.submit_group(group, "stop"))
    return {"operation": op.public(), "targets": ids}


@app.post("/api/actions/stop-all", dependencies=[Depends(require_panel)])
def api_stop_all(body: ConfirmBody):
    if not body.confirm:
        raise HTTPException(status_code=400, detail="需要 confirm=true")
    op = _submit_or_409(lambda: manager.submit_stop_all())
    return {"operation": op.public(), "targets": catalog.stop_all_plan()}


# ── 操作查询 ──

@app.get("/api/operations")
def api_operations():
    return {"operations": manager.recent()}


@app.get("/api/operations/{op_id}")
def api_operation(op_id: str):
    op = manager.get(op_id)
    if not op:
        raise HTTPException(status_code=404, detail="操作不存在")
    return op


@app.post("/api/operations/{op_id}/cancel", dependencies=[Depends(require_panel)])
def api_cancel_operation(op_id: str):
    if not manager.cancel(op_id):
        raise HTTPException(status_code=409, detail="只能取消排队中的操作")
    return {"ok": True}


# ── SSE ──

def _sse_stream(q: queue.Queue, op_filter: str | None = None):
    try:
        yield "retry: 3000\n\n"
        yield f"data: {json.dumps({'type': 'hello', 'interval': 5}, ensure_ascii=False)}\n\n"
        while True:
            try:
                item = q.get(timeout=15)
            except queue.Empty:
                yield ": ping\n\n"
                continue
            if op_filter:
                if item.get("type") == "log" and item.get("op_id") != op_filter:
                    continue
                if item.get("type") == "op" and (item.get("op") or {}).get("id") != op_filter:
                    continue
                if item.get("type") in ("toast", "hello"):
                    continue
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"
    finally:
        manager.unsubscribe(q)


def _sse_response(q: queue.Queue, op_filter: str | None = None) -> StreamingResponse:
    return StreamingResponse(
        _sse_stream(q, op_filter),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/events")
def api_events():
    q = manager.subscribe()
    return _sse_response(q)


@app.get("/api/operations/{op_id}/events")
def api_operation_events(op_id: str):
    if not manager.get(op_id):
        raise HTTPException(status_code=404, detail="操作不存在")
    q = manager.subscribe()
    return _sse_response(q, op_filter=op_id)
