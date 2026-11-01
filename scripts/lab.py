r"""靶场统一入口：一键启停 + 真健康检查。

为什么需要它
------------
1. `launch.py` 只负责把 java 进程拉起来，**一行健康检查都没有**。2026-11-01 凌晨踩过：
   19102 的 Nginx 入口在 LISTENING，后端 19202 已经死了，扫描器卡 17 分钟一直重试，
   而 `netstat` 看起来一切正常。
2. 21 座靶场分散在 8 个脚本里（launch / components_start / c2_sba / c2_s4s / c2_scf /
   c3_honeypot / d1_start / a2_start），起全量要点十几次、记十几个端口。
3. 盲测要求「入口码 + 后端端口 + 业务接口」三者一致才算 UP，只看端口会把死掉的站点
   当成活的扫。

判定口径
--------
| 状态       | 含义                                                        |
|------------|-------------------------------------------------------------|
| UP         | 入口可访问 + 后端端口监听 + 业务探针返回预期码              |
| DEGRADED   | 入口在，但后端端口没监听 / 探针失败（典型：Nginx 502）      |
| DOWN       | 入口不在                                                      |
| STOPPED    | 用户没让它起（同期不存在 pid 文件）                          |

用法
----
    python scripts\lab.py status              # 全量状态
    python scripts\lab.py status R1 R2 C1-1   # 只看指定目标
    python scripts\lab.py up R1 R2            # 按依赖顺序启动（自动带上基础设施）
    python scripts\lab.py up infra            # 只起 MySQL + Redis + Nginx
    python scripts\lab.py up site             # 起 R1–R12（含 R12 的 R2 依赖）
    python scripts\lab.py down R1             # 停止
    python scripts\lab.py verify R1           # 断言全 UP，任一不健康即退出码 1
    python scripts\lab.py clean               # 清掉「PID 在但进程已死」的残留
    python scripts\lab.py manifest            # JSON 清单（含 git tag/commit/dirty），供盲测冻结版本
    python scripts\lab.py urls site           # 只输出 HTTP 入口 URL，一行一个

盲测前置校验（坏了就拒绝开扫）：
    python scripts\lab.py verify <目标组> || exit 1
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

# Windows 控制台默认 cp936（GBK），箱线/对勾这类字符会直接 UnicodeEncodeError。
# 统一成 UTF-8 + replace 兜底：宁可显示成 '?' 也不能让状态查询崩掉。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(ROOT, ".state")
SCRIPTS = os.path.join(ROOT, "scripts")
NGINX_DIR = os.path.join(ROOT, "nginx")

MYSQLD = r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqld.exe"
MYSQL_INI = r"C:/Users/HZR/ry_r2_mysql/my.ini"
REDIS_DIR = os.path.join(ROOT, "tools", "redis")

FLAGS = 0
if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
    FLAGS = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

# ── 每座靶场的完整定义 ──
# entry:   对外入口端口（扫描器打这个）
# backend: 后端端口；0 表示后端与入口同端口（如 C1/C3，无 Nginx 前置）
# probe:   (路径, 期望状态码集合)；None 表示只探入口
# pidfile: 相对 .state/ 的 PID 文件名；None 表示无独立 PID（R12 复用 R2 后端）
# start:   启动命令；stop: 停止命令（None 走通用 PID 结束）
SITES: dict[str, dict] = {
    # ── 基础设施 ──
    "infra:mysql": {
        "group": "infra", "entry": 13307, "backend": 0, "probe": None,
        "pidfile": None, "desc": "MySQL（13307）",
    },
    "infra:redis": {
        "group": "infra", "entry": 6379, "backend": 0, "probe": None,
        "pidfile": None, "desc": "Redis（6379）",
    },
    "infra:nginx": {
        "group": "infra", "entry": 19101, "backend": 0, "probe": None,
        "pidfile": None, "desc": "Nginx 入口（191xx）",
    },

    # ── 若依官方形态 R1–R11 ──
    # 单机版（R1–R5/R11）根路径直连后端，未登录多返 302 → /login
    # 分离版（R6/R7/R9/R10）根路径是 SPA 200，真正探针要打 /prod-api 或 /jeecg-boot
    "R1":  {"group": "site", "entry": 19101, "backend": 19201, "probe": ("/login", {200, 302}), "pidfile": "R1.pid"},
    "R2":  {"group": "site", "entry": 19102, "backend": 19202, "probe": ("/login", {200, 302}), "pidfile": "R2.pid"},
    "R3":  {"group": "site", "entry": 19103, "backend": 19203, "probe": ("/login", {200, 302}), "pidfile": "R3.pid"},
    "R4":  {"group": "site", "entry": 19104, "backend": 19204, "probe": ("/login", {200, 302}), "pidfile": "R4.pid"},
    "R5":  {"group": "site", "entry": 19105, "backend": 19205, "probe": ("/login", {200, 302}), "pidfile": "R5.pid"},
    # 分离版：必须探 /prod-api/ 前缀下的接口，根路径是 SPA 兜底（200 + index.html）。
    # 2026-11-01 移除了 R6 的「运维便利映射」后，根路径 /captchaImage 也走 SPA 兜底，
    # 探它会拿到 200 假阳性 —— 这正是"看着 UP 实际没连到后端"的坑。
    "R6":  {"group": "site", "entry": 19106, "backend": 19206, "probe": ("/prod-api/captchaImage", {200}), "pidfile": "R6.pid"},
    "R7":  {"group": "site", "entry": 19107, "backend": 19207, "probe": ("/prod-api/captchaImage", {200}), "pidfile": "R7.pid"},
    "R8":  {"group": "site", "entry": 19108, "backend": 19208, "probe": ("/", {200, 302, 401}), "pidfile": "R8.pid",
            "cloud": True},
    "R9":  {"group": "site", "entry": 19109, "backend": 19209, "probe": ("/prod-api/auth/code", {200}), "pidfile": "R9.pid"},
    "R10": {"group": "site", "entry": 19110, "backend": 19210, "probe": ("/jeecg-boot/sys/randomImage/probe", {200}), "pidfile": "R10.pid"},
    "R11": {"group": "site", "entry": 19111, "backend": 19211, "probe": ("/api/v1/health", {200}), "pidfile": "R11.pid"},
    # R12 复用 R2 后端（19202），只多一层 Nginx WAF；无独立进程
    "R12": {"group": "site", "entry": 19112, "backend": 19202, "probe": ("/login", {200, 302}), "pidfile": None,
            "depends": ["R2"]},

    # ── C1 组件靶场（无 Nginx 前置，入口即后端）──
    "C1-1": {"group": "component", "entry": 19301, "backend": 0, "probe": ("/actuator/health", {200}), "pidfile": "C1-1-jolokia.pid"},
    "C1-2": {"group": "component", "entry": 19302, "backend": 0, "probe": ("/h2-console", {200, 302}), "pidfile": "C1-2-h2-console.pid"},
    "C1-3": {"group": "component", "entry": 19303, "backend": 0, "probe": ("/api", {200}), "pidfile": "C1-3-data-service.pid"},
    "C1-4": {"group": "component", "entry": 19304, "backend": 0, "probe": ("/application/default", {200}), "pidfile": "C1-4-config-server.pid"},

    # ── C2 组件靶场 ──
    "C2-1a": {"group": "component", "entry": 19311, "backend": 0, "probe": ("/applications", {200}), "pidfile": "C2-sba-server.pid"},
    "C2-1b": {"group": "component", "entry": 19312, "backend": 0, "probe": ("/actuator/health", {200}), "pidfile": "C2-sba-client.pid"},
    "C2-2":  {"group": "component", "entry": 19313, "backend": 0, "probe": ("/", {200, 302, 404}), "pidfile": "C2-s4s.pid"},
    "C2-3":  {"group": "component", "entry": 19314, "backend": 0, "probe": ("/", {200, 404}), "pidfile": "C2-scf.pid"},

    # ── 特殊形态 ──
    "C3":  {"group": "special", "entry": 19331, "backend": 0, "probe": ("/", {200}), "pidfile": "C3.pid"},
    "D1":  {"group": "special", "entry": 19321, "backend": 19221, "probe": ("/portal/auth/signin", {200}), "pidfile": "D1.pid"},
    "A2":  {"group": "special", "entry": 19341, "backend": 19241, "probe": ("/login", {200, 302}), "pidfile": "A2.pid"},
}

GROUPS = {
    "infra": ["infra:mysql", "infra:redis", "infra:nginx"],
    "site": [f"R{i}" for i in range(1, 13)],
    "component": [k for k in SITES if k.startswith("C")],
    "special": ["C3", "D1", "A2"],
    "r1-r5": ["R1", "R2", "R3", "R4", "R5"],
    "vue": ["R6", "R7", "R9", "R10"],
}

# 启动顺序：基础设施 → 后端 → Nginx（launch.py 内已处理到具体 jar）
START_ORDER_HINT = ["infra:mysql", "infra:redis", "infra:nginx"]

ALL = list(SITES)


# ── 基础探测 ──

def port_open(port: int, host: str = "127.0.0.1", timeout: float = 1.0) -> bool:
    if not port:
        return True
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def http_code(url: str, timeout: float = 4.0) -> int:
    """返回 HTTP 状态码；连不上返回 0。不跟随重定向，302 也是有效证据。"""
    req = urllib.request.Request(url, headers={"User-Agent": "ruoyi-lab/1.0"})

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **kw):  # noqa: D102 - 故意不跟随
            return None

    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(req, timeout=timeout) as resp:
            resp.read(64)
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except Exception:
        return 0


def http_probe(url: str, timeout: float = 4.0) -> tuple[int, str, bytes]:
    """返回 (状态码, Content-Type, 响应体前 256 字节)。

    比 http_code 多返回内容 —— 分离版站点的 SPA 兜底对任意路径都返 200 HTML，
    只看状态码无法区分「真连到后端」和「打到了前端页面」。
    """
    req = urllib.request.Request(url, headers={"User-Agent": "ruoyi-lab/1.0"})

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **kw):  # noqa: D102 - 故意不跟随
            return None

    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(req, timeout=timeout) as resp:
            body = resp.read(256)
            return resp.status, (resp.headers.get("Content-Type") or "").lower(), body
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read(256)
        except Exception:
            body = b""
        return exc.code, (exc.headers.get("Content-Type") or "").lower(), body
    except Exception:
        return 0, "", b""


def read_pid(name: str) -> int | None:
    pf = SITES.get(name, {}).get("pidfile")
    if not pf:
        return None
    try:
        with open(os.path.join(STATE_DIR, pf), "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def pid_alive(pid: int | None) -> bool:
    """Windows 下用 OpenProcess 判活；不用 tasklist（GBK 输出会解码失败）。"""
    if not pid:
        return False
    try:
        import ctypes

        k = ctypes.windll.kernel32
        k.OpenProcess.restype = ctypes.c_void_p
        k.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong]
        handle = k.OpenProcess(0x1000, False, int(pid))
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not k.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code)):
                return False
            return code.value == 259  # STILL_ACTIVE
        finally:
            k.CloseHandle(ctypes.c_void_p(handle))
    except Exception:
        return False


# ── 状态判定 ──

def check(name: str) -> dict:
    """返回 {'name','state','detail','pid'}。

    判定链：入口端口 → 后端端口 → 业务探针。三者齐 UP，缺一 DEGRADED，入口都不在 DOWN。
    """
    cfg = SITES[name]
    entry = cfg["entry"]
    backend = cfg.get("backend") or 0
    probe = cfg.get("probe")
    pid = read_pid(name)

    entry_up = port_open(entry)
    backend_up = port_open(backend) if backend else entry_up

    detail_parts = []
    if not entry_up:
        return {"name": name, "state": "DOWN", "detail": f"入口 {entry} 未监听", "pid": pid}

    detail_parts.append(f"入口{entry}=ok")
    if backend and not backend_up:
        return {
            "name": name, "state": "DEGRADED",
            "detail": f"入口{entry}=ok 后端{backend}=未监听（典型：Nginx 502）", "pid": pid,
        }
    if backend:
        detail_parts.append(f"后端{backend}=ok")

    if probe:
        path, expect = probe
        code, ctype, body = http_probe(f"http://127.0.0.1:{entry}{path}")
        if code not in expect:
            return {
                "name": name, "state": "DEGRADED",
                "detail": f"{' '.join(detail_parts)} 探针{path}={code}（期望{sorted(expect)}）", "pid": pid,
            }
        # 分离版站点（探针走 /prod-api、/jeecg-boot 这类 API 前缀）如果返回 HTML，
        # 说明打到的不是后端，而是 SPA 的 try_files 兜底页 —— 那只证明 Nginx 活着。
        # 单机版（探针是 /login）本来就该返回 HTML 登录页，不能套同一个判据。
        is_api_probe = any(path.startswith(p) for p in ("/prod-api", "/jeecg-boot", "/api/"))
        if is_api_probe and "json" not in ctype and b"<html" in body[:200].lower():
            return {
                "name": name, "state": "DEGRADED",
                "detail": f"{' '.join(detail_parts)} 探针{path}={code} 但返回 HTML（SPA 兜底，未连到后端）",
                "pid": pid,
            }
        detail_parts.append(f"{path}={code}")

    return {"name": name, "state": "UP", "detail": " ".join(detail_parts), "pid": pid}


def resolve(names: list[str]) -> list[str]:
    """把组名/别名展开成具体目标名，去重保序。"""
    out: list[str] = []
    for raw in names:
        key = raw.strip()
        low = key.lower()
        if low in GROUPS:
            cand = GROUPS[low]
        elif key.upper() in SITES:
            cand = [key.upper()]
        elif key in SITES:
            cand = [key]
        elif key.upper().replace("_", "-") in SITES:
            cand = [key.upper().replace("_", "-")]
        elif key in ("all", "ALL"):
            cand = ALL
        else:
            print(f"[ERROR] 未知目标: {raw}")
            print(f"        可用站点: {' '.join(ALL)}")
            print(f"        可用分组: {' '.join(GROUPS)}")
            raise SystemExit(1)
        for c in cand:
            if c not in out:
                out.append(c)
    return out


# ── 各状态输出 ──

ICON = {"UP": "[OK]  ", "DEGRADED": "[WARN]", "DOWN": "[DOWN]"}


def cmd_status(names: list[str]) -> int:
    targets = resolve(names) if names else ALL
    rows = [check(n) for n in targets]

    width = max(len(n) for n in targets) + 2
    print()
    print(f"{'目标':<{width}} {'状态':<9} {'PID':<8} 明细")
    print("-" * (width + 60))
    for r in rows:
        icon = ICON.get(r["state"], "  ?   ")
        pid = str(r["pid"]) if r["pid"] else "-"
        alive = "" if not r["pid"] else ("" if pid_alive(r["pid"]) else " (僵尸PID)")
        print(f"{r['name']:<{width}} {icon}    {pid:<8} {r['detail']}{alive}")

    up = sum(1 for r in rows if r["state"] == "UP")
    deg = sum(1 for r in rows if r["state"] == "DEGRADED")
    down = sum(1 for r in rows if r["state"] == "DOWN")
    print("-" * (width + 60))
    print(f"合计 {len(rows)}：UP {up} / DEGRADED {deg} / DOWN {down}")

    # 僵尸 PID：pid 文件在、进程已死、端口也没监听 → 残留状态，会误导后续启停
    zombie = [r["name"] for r in rows if r["pid"] and not pid_alive(r["pid"]) and r["state"] == "DOWN"]
    if zombie:
        print(f"[提示] 以下站点 PID 文件残留但进程已退出，可跑 `lab.py clean` 清理: {', '.join(zombie)}")
    return 0 if down == 0 and deg == 0 else 1


def cmd_verify(names: list[str]) -> int:
    """严格断言模式：任一非 UP 即失败，供盲测脚本前置校验。"""
    targets = resolve(names) if names else ALL
    bad = []
    for n in targets:
        r = check(n)
        if r["state"] != "UP":
            bad.append(r)
            print(f"[FAIL] {n}: {r['state']} — {r['detail']}")
    if bad:
        print(f"\n[FAIL] {len(bad)}/{len(targets)} 座靶场不健康，拒绝在坏尺子上盲测")
        return 1
    print(f"[OK] {len(targets)} 座靶场全部 UP")
    return 0


# ── 启停 ──

def _spawn(cmd: list[str], cwd: str, logname: str) -> int:
    os.makedirs(os.path.dirname(os.path.join(cwd, logname)), exist_ok=True)
    log = open(os.path.join(cwd, logname), "ab")
    p = subprocess.Popen(
        cmd, cwd=cwd, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
        close_fds=True, creationflags=FLAGS,
    )
    return p.pid


def _wait(pred, timeout: float, label: str) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if pred():
            return True
        time.sleep(1)
    print(f"[FAIL] {label} 超时（{timeout:.0f}s）")
    return False


def start_infra(name: str) -> bool:
    if name == "infra:mysql":
        if port_open(13307):
            print("[SKIP] MySQL 已在 13307")
            return True
        if not os.path.exists(MYSQL_INI):
            print(f"[FAIL] 找不到 {MYSQL_INI}")
            return False
        pid = _spawn([MYSQLD, f"--defaults-file={MYSQL_INI}"], ROOT, "mysql/boot.log")
        print(f"[..] MySQL 启动中 pid={pid}")
        return _wait(lambda: port_open(13307), 60, "MySQL")

    if name == "infra:redis":
        if port_open(6379):
            print("[SKIP] Redis 已在 6379")
            return True
        exe = os.path.join(REDIS_DIR, "redis-server.exe")
        if not os.path.exists(exe):
            print(f"[FAIL] 找不到 {exe}")
            return False
        pid = _spawn([exe, "redis.windows.conf"], REDIS_DIR, "redis.log")
        print(f"[..] Redis 启动中 pid={pid}")
        return _wait(lambda: port_open(6379), 20, "Redis")

    if name == "infra:nginx":
        # 判据用 nginx 自己持有的任意入口，而不是单一 19109（R9 可能没起）
        if any(port_open(p) for p in (19101, 19109, 19111)):
            print("[SKIP] Nginx 已有入口在监听")
            return True
        exe = os.path.join(NGINX_DIR, "nginx.exe")
        if not os.path.exists(exe):
            print(f"[FAIL] 找不到 {exe}")
            return False
        _spawn([exe], NGINX_DIR, "logs/boot.log")
        print("[..] Nginx 启动中")
        return _wait(lambda: any(port_open(p) for p in (19101, 19109, 19111)), 20, "Nginx")

    print(f"[ERROR] 未知基础设施: {name}")
    return False


def start_site(name: str) -> bool:
    cfg = SITES[name]

    # 先满足依赖（R12 需要 R2 后端）
    for dep in cfg.get("depends", []):
        print(f"[..] {name} 依赖 {dep}，先启动")
        if not start_site(dep):
            return False

    # 真实感资产（遗留 SQL、漏删的 .git）在启动前铺好。
    # 放在启动前而不是启动后：R7 的 .git 是 Nginx 直接读的静态文件，不需要重启就生效；
    # 而 R1 的 static-extra 由 Spring 挂载，启动时扫描目录，必须提前就位。
    try:
        if SCRIPTS not in sys.path:
            sys.path.insert(0, SCRIPTS)
        import lab_assets

        lab_assets.apply(name, verbose=False)
    except Exception as exc:  # 资产铺设失败不该阻断站点启动
        print(f"[WARN] {name} 真实感资产铺设失败: {exc}")

    # 云站点交给专用脚本
    if cfg.get("cloud"):
        print(f"[..] {name} 是微服务站点，交给 start_r8_cloud.py")
        rc = subprocess.call([sys.executable, os.path.join(SCRIPTS, "start_r8_cloud.py"), "start"], cwd=ROOT)
        return rc == 0

    # C1 组件
    if name.startswith("C1-"):
        comp = {"C1-1": "jolokia", "C1-2": "h2-console", "C1-3": "data-service", "C1-4": "config-server"}[name]
        return subprocess.call([sys.executable, os.path.join(SCRIPTS, "components_start.py"), comp], cwd=ROOT) == 0

    # C2 / C3 / D1 / A2
    special = {
        "C2-1a": ("c2_sba.py", "start"), "C2-1b": ("c2_sba.py", "start"),
        "C2-2": ("c2_s4s.py", "start"), "C2-3": ("c2_scf.py", "start"),
        "C3": ("c3_honeypot.py", "start"), "D1": ("d1_start.py", "start"), "A2": ("a2_start.py", "start"),
    }
    if name in special:
        script, sub = special[name]
        return subprocess.call([sys.executable, os.path.join(SCRIPTS, script), sub], cwd=ROOT) == 0

    # R1–R11 普通站点：先确保后端起来，再由 launch.py 落 pid
    if cfg.get("backend") and not port_open(cfg["backend"]):
        rc = subprocess.call([sys.executable, os.path.join(SCRIPTS, "launch.py"), name], cwd=ROOT)
        if rc != 0:
            return False
        ok = _wait(lambda: port_open(cfg["backend"]), 180, f"{name} 后端 {cfg['backend']}")
        if not ok:
            return False
    else:
        print(f"[SKIP] {name} 后端已在 {cfg.get('backend')}")

    # R12 无独立进程，只要 Nginx 起了、R2 后端活着即可
    if name == "R12" and not port_open(19112):
        print("[FAIL] R12 入口 19112 未监听：确认 nginx/conf.d/R12.conf 已启用且 Nginx 在跑")
        return False
    return True


def cmd_up(names: list[str]) -> int:
    targets = resolve(names) if names else ALL
    # 先基础设施，再站点（顺序由 START_ORDER_HINT + SITES 定义保证）
    infra = [t for t in targets if t.startswith("infra:")]
    rest = [t for t in targets if not t.startswith("infra:")]

    # 只要起站点就隐含需要基础设施
    if rest:
        for i in START_ORDER_HINT:
            if i not in infra:
                infra.insert(0, i) if i == "infra:mysql" else infra.append(i)
        infra = [i for i in START_ORDER_HINT if i in infra] + [i for i in infra if i not in START_ORDER_HINT]

    failed: list[str] = []
    for n in infra:
        print(f"\n=== {n} ===")
        if not start_infra(n):
            failed.append(n)

    # Nginx 必须在后端之前起？不：Nginx 起得来但会 502。反之 Nginx 后起更稳。
    # 这里按「MySQL → Redis → 各站后端 → （Nginx 已在上面）」，launch.py 不依赖 Nginx。
    for n in rest:
        print(f"\n=== {n} ===")
        if not start_site(n):
            failed.append(n)

    print("\n" + "=" * 60)
    if failed:
        print(f"[FAIL] 启动失败: {', '.join(failed)}")
        cmd_status(targets)
        return 1
    print("[OK] 全部目标已启动，复核状态：")
    return cmd_status(targets)


def cmd_down(names: list[str]) -> int:
    targets = resolve(names) if names else ALL

    # 依赖反转：R12 没有独立进程，跳过；先停站点再停基础设施
    infra = [t for t in targets if t.startswith("infra:")]
    rest = [t for t in targets if not t.startswith("infra:")]

    failed: list[str] = []
    for n in rest:
        print(f"\n=== {n} ===")
        cfg = SITES[n]
        if n.startswith("C1-"):
            comp = {"C1-1": "jolokia", "C1-2": "h2-console", "C1-3": "data-service", "C1-4": "config-server"}[n]
            subprocess.call([sys.executable, os.path.join(SCRIPTS, "components_stop.py"), comp], cwd=ROOT)
        elif n == "R8":
            subprocess.call([sys.executable, os.path.join(SCRIPTS, "start_r8_cloud.py"), "stop"], cwd=ROOT)
        elif n in ("C2-1a", "C2-1b"):
            subprocess.call([sys.executable, os.path.join(SCRIPTS, "c2_sba.py"), "stop"], cwd=ROOT)
        elif n == "C2-2":
            subprocess.call([sys.executable, os.path.join(SCRIPTS, "c2_s4s.py"), "stop"], cwd=ROOT)
        elif n == "C2-3":
            subprocess.call([sys.executable, os.path.join(SCRIPTS, "c2_scf.py"), "stop"], cwd=ROOT)
        elif n == "C3":
            subprocess.call([sys.executable, os.path.join(SCRIPTS, "c3_honeypot.py"), "stop"], cwd=ROOT)
        elif n == "D1":
            subprocess.call([sys.executable, os.path.join(SCRIPTS, "d1_start.py"), "stop"], cwd=ROOT)
        elif n == "A2":
            subprocess.call([sys.executable, os.path.join(SCRIPTS, "a2_start.py"), "stop"], cwd=ROOT)
        elif cfg.get("pidfile") is None:
            print(f"[SKIP] {n} 无独立进程（复用 {cfg.get('backend') or '其他站点'}）")
        else:
            pid = read_pid(n)
            if not pid or not pid_alive(pid):
                print(f"[SKIP] {n} 未运行")
                try:
                    os.remove(os.path.join(STATE_DIR, cfg["pidfile"]))
                except OSError:
                    pass
                continue
            subprocess.call(["taskkill", "/PID", str(pid), "/T", "/F"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            _wait(lambda: not port_open(cfg["backend"] or cfg["entry"]), 20, f"{n} 端口释放")
            try:
                os.remove(os.path.join(STATE_DIR, cfg["pidfile"]))
            except OSError:
                pass
            print(f"[OK] {n} 已停止（pid {pid}）")

    for n in infra:
        print(f"\n=== {n} ===")
        if n == "infra:nginx":
            exe = os.path.join(NGINX_DIR, "nginx.exe")
            if os.path.exists(exe):
                subprocess.call([exe, "-s", "stop"], cwd=NGINX_DIR,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print("[OK] Nginx 已停止")
        else:
            port = 13307 if n == "infra:mysql" else 6379
            print(f"[提示] {n} 的进程不按 PID 文件管理，如需停止请手工处理（端口 {port}）")

    # 清理僵尸 PID 文件
    cmd_clean(quiet=True)
    return 0 if not failed else 1


# run.log 是 stdout 全量重定向，没有 logback 滚动策略保护。
# 实测 R1 累积到 649MB、R5 到 336MB —— 若依 4.5.1 的 Druid statViewServlet 在
# login-username 为空时（官方默认配置）每个 /druid/* 请求都抛 NPE，单次目录扫描
# 能打出 8 万个栈。超过这个阈值就该清理，否则会撑爆磁盘并淹没真问题。
LOG_WARN_MB = 100


def cmd_logs(names: list[str]) -> int:
    """报告各站 run.log 体积，超过阈值给出清理建议。"""
    targets = resolve(names) if names else [n for n in ALL if not n.startswith("infra:")]
    rows = []
    for n in targets:
        path = os.path.join(ROOT, "runtime", n, "run.log")
        if not os.path.exists(path):
            continue
        mb = os.path.getsize(path) / (1024 * 1024)
        rows.append((n, mb, path))
    if not rows:
        print("[OK] 没有找到任何 run.log")
        return 0

    rows.sort(key=lambda r: -r[1])
    total = sum(r[1] for r in rows)
    print()
    print(f"{'站点':<8} {'run.log':>10}")
    print("-" * 40)
    over = []
    for n, mb, path in rows:
        flag = "  << 超阈值" if mb > LOG_WARN_MB else ""
        if mb > LOG_WARN_MB:
            over.append((n, path))
        print(f"{n:<8} {mb:>8.1f} MB{flag}")
    print("-" * 40)
    print(f"合计 {total:.1f} MB")

    if over:
        print(f"\n[提示] {len(over)} 座站超过 {LOG_WARN_MB}MB。清理：")
        print("       python scripts\\lab.py clean-logs")
        return 1
    return 0


def cmd_clean_logs(names: list[str]) -> int:
    """清空超阈值的 run.log（保留 .prev 一份供回溯）。"""
    targets = resolve(names) if names else [n for n in ALL if not n.startswith("infra:")]
    freed = 0.0
    for n in targets:
        path = os.path.join(ROOT, "runtime", n, "run.log")
        if not os.path.exists(path):
            continue
        mb = os.path.getsize(path) / (1024 * 1024)
        if mb <= LOG_WARN_MB:
            continue
        try:
            os.replace(path, path + ".prev")
        except OSError:
            pass
        try:
            with open(path, "wb"):
                pass
        except OSError as exc:
            print(f"[FAIL] {n}: {exc}")
            continue
        freed += mb
        print(f"[OK] {n}: 清空 {mb:.1f} MB（上一轮留在 run.log.prev）")
    print(f"\n[OK] 共释放 {freed:.1f} MB" if freed else "[OK] 无需清理")
    return 0


def cmd_clean(quiet: bool = False) -> int:
    """删除「PID 文件在但进程已死」的残留，避免后续误判站点在跑。"""
    removed = []
    for name in ALL:
        pf = SITES[name].get("pidfile")
        if not pf:
            continue
        path = os.path.join(STATE_DIR, pf)
        if not os.path.exists(path):
            continue
        pid = read_pid(name)
        if pid and pid_alive(pid):
            continue
        try:
            os.remove(path)
            removed.append(f"{name}(pid {pid})")
        except OSError:
            pass
    if not quiet:
        print(f"[OK] 清理 {len(removed)} 个残留 PID 文件" if removed else "[OK] 无残留 PID 文件")
        for r in removed:
            print(f"     {r}")
    return 0


def cmd_manifest() -> int:
    """输出机器可读的靶场清单，供盲测脚本冻结版本。"""
    rows = []
    for name in ALL:
        cfg = SITES[name]
        r = check(name)
        rows.append({
            "target": name,
            "group": cfg["group"],
            "entry_port": cfg["entry"],
            # 基础设施不是 HTTP 服务（MySQL/Redis 直接连端口），不给 url 免得盲测脚本误打
            "url": None if cfg["group"] == "infra" else f"http://127.0.0.1:{cfg['entry']}",
            "backend_port": cfg.get("backend") or None,
            "state": r["state"],
            "detail": r["detail"],
        })
    git = {}
    for key, cmd in (
        ("commit", ["git", "rev-parse", "HEAD"]),
        ("tag", ["git", "describe", "--tags", "--always"]),
        ("dirty", ["git", "status", "--porcelain"]),
    ):
        try:
            out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=10)
            git[key] = (out.stdout or "").strip() or None
        except Exception:
            git[key] = None
    print(json.dumps({"git": git, "targets": rows}, ensure_ascii=False, indent=2))
    return 0


def cmd_urls(names: list[str]) -> int:
    """只输出可扫描的 HTTP 入口（一行一个），方便 `for u in $(lab.py urls site)`。"""
    targets = resolve(names) if names else [n for n in ALL if SITES[n]["group"] != "infra"]
    for n in targets:
        cfg = SITES[n]
        if cfg["group"] == "infra":
            continue
        print(f"http://127.0.0.1:{cfg['entry']}")
    return 0


def usage() -> int:
    print(__doc__)
    return 2


def main() -> int:
    argv = sys.argv[1:]
    if not argv:
        return usage()
    cmd, names = argv[0].lower(), argv[1:]

    if cmd == "status":
        return cmd_status(names)
    if cmd == "verify":
        return cmd_verify(names)
    if cmd == "up":
        return cmd_up(names)
    if cmd == "down":
        return cmd_down(names)
    if cmd == "clean":
        return cmd_clean()
    if cmd == "logs":
        return cmd_logs(names)
    if cmd == "clean-logs":
        return cmd_clean_logs(names)
    if cmd == "manifest":
        return cmd_manifest()
    if cmd == "urls":
        return cmd_urls(names)
    return usage()


if __name__ == "__main__":
    sys.exit(main())
