r"""C3 邕江云服务门户自检：默认模式 12 项 + 严格模式 2 项。"""
import hashlib
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
BASE = "http://127.0.0.1:19331"
PIDFILE = ROOT / ".state" / "C3.pid"

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def run(action, extra=()):
    proc = subprocess.run(
        [PY, str(ROOT / "scripts" / "c3_honeypot.py"), action] + list(extra),
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def start_ok(label, strict=False):
    rc, out = run("start", ("--strict",) if strict else ())
    if rc != 0:
        raise AssertionError("%s start 失败 rc=%s\n%s" % (label, rc, out[-800:]))


def stop_ok(label):
    rc, out = run("stop")
    if rc != 0:
        raise AssertionError("%s stop 失败 rc=%s\n%s" % (label, rc, out[-800:]))


def port_open(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def wait_closed(port, seconds=30):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if not port_open(port):
            return True
        time.sleep(0.5)
    return not port_open(port)


def check(name, func):
    try:
        detail = func()
        print("PASS %s%s" % (name, (" | " + str(detail)) if detail else ""))
        return True
    except Exception as exc:
        print("FAIL %s: %s" % (name, exc))
        return False


def test_index():
    start_ok("C3")
    resp = requests.get(BASE + "/", timeout=10)
    assert resp.status_code == 200, resp.status_code
    return "GET / 200, %d bytes" % len(resp.content)


def test_soft404():
    root = requests.get(BASE + "/", timeout=10).content
    for path in ("/a/b/c", "/portal/login", "/this-path-does-not-exist"):
        resp = requests.get(BASE + path, timeout=10)
        assert resp.status_code == 200, "%s = %s" % (path, resp.status_code)
        assert resp.content == root, "%s 与 / 不一致" % path
    return "3 个未知路径 200 且与 / 逐字节相同"


def test_git_head():
    resp = requests.get(BASE + "/.git/HEAD", timeout=10)
    assert resp.status_code == 200, resp.status_code
    assert resp.text.startswith("ref:"), resp.text[:40]
    return repr(resp.text.strip())


def test_git_objects():
    resp = requests.get(BASE + "/.git/objects/ab/cdef", timeout=10)
    assert resp.status_code == 404, resp.status_code
    return "404"


def test_env_file():
    resp = requests.get(BASE + "/.env", timeout=10)
    assert resp.status_code == 200, resp.status_code
    assert "DB_HOST=" in resp.text and "DB_PASSWORD=" in resp.text
    return "200, DB_HOST/DB_PASSWORD 存在"


def test_backup():
    resp = requests.get(BASE + "/backup/db_20240101.sql", timeout=10)
    assert resp.status_code == 200, resp.status_code
    assert "INSERT INTO" in resp.text, resp.text[:80]
    return "200, 含 INSERT INTO"


def test_druid():
    page = requests.get(BASE + "/druid/index.html", timeout=10)
    assert page.status_code == 200, page.status_code
    assert "Druid Stat Index" in page.text
    login = requests.post(
        BASE + "/druid/submitLogin",
        data={"loginUsername": "admin", "loginPassword": "admin"},
        timeout=10,
    )
    assert login.status_code == 200, login.status_code
    body = login.json()
    assert body.get("result") == "fail", body
    return "登录页 200；submitLogin=fail"


def test_swagger():
    page = requests.get(BASE + "/swagger-ui.html", timeout=10)
    assert page.status_code == 200, page.status_code
    assert "swagger-ui" in page.text
    docs = requests.get(BASE + "/v2/api-docs", timeout=10)
    assert docs.status_code == 200, docs.status_code
    data = docs.json()
    assert data.get("swagger") == "2.0", data
    assert data.get("paths") == {}, data.get("paths")
    return "swagger-ui 200；paths={}"


def test_actuator():
    resp = requests.get(BASE + "/actuator/env", timeout=10)
    assert resp.status_code == 200, resp.status_code
    data = resp.json()
    assert data.get("activeProfiles") == ["prod"], data
    assert data.get("propertySources"), data
    health = requests.get(BASE + "/actuator/health", timeout=10)
    assert health.json().get("status") == "UP"
    return "propertySources=%d 组；health=UP" % len(data["propertySources"])


def test_sql_decoy():
    hashes = []
    for q in ("1", "1'", "1 union select 1"):
        resp = requests.get(BASE + "/api/query", params={"q": q}, timeout=10)
        assert resp.status_code == 200, resp.status_code
        hashes.append(hashlib.sha256(resp.content).hexdigest())
    assert len(set(hashes)) == 1, hashes
    return "q=1 / 1' / union 三种请求正文 sha256 相同"


def test_rate_limit():
    start_ok("C3 strict", strict=True)
    session = requests.Session()
    codes = []
    retry_after = None
    for _ in range(90):
        resp = session.get(BASE + "/", timeout=5)
        codes.append(resp.status_code)
        if resp.status_code == 429 and retry_after is None:
            retry_after = resp.headers.get("Retry-After")
    assert 429 in codes, "90 次请求未触发限速: %s" % set(codes)
    assert retry_after == "30", "Retry-After=%s" % retry_after
    return "90 次请求出现 %d 个 429，Retry-After=30" % codes.count(429)


def test_strict_stop():
    stop_ok("C3 strict")
    assert wait_closed(19331), "严格模式停止后 19331 未释放"
    assert not PIDFILE.exists(), "严格模式停止后 PID 残留"
    return "19331 已释放，无残留 PID"


def test_stop_and_rounds():
    stop_ok("C3")
    assert wait_closed(19331), "19331 未释放"
    assert not PIDFILE.exists(), "PID 文件残留"
    for round_no in (1, 2):
        start_ok("C3 第 %d 轮" % round_no)
        resp = requests.get(BASE + "/", timeout=10)
        assert resp.status_code == 200, "第 %d 轮 / = %s" % (round_no, resp.status_code)
        stop_ok("C3 第 %d 轮" % round_no)
        assert wait_closed(19331), "第 %d 轮 19331 未释放" % round_no
        assert not PIDFILE.exists(), "第 %d 轮 PID 残留" % round_no
    return "19331 已释放；start→stop 连续两轮成功，无残留 PID"


OTHER = {}


def listen_pid(port):
    try:
        import psutil

        for conn in psutil.net_connections(kind="tcp"):
            if conn.status == psutil.CONN_LISTEN and conn.laddr and conn.laddr.port == port:
                return conn.pid
    except Exception:
        return None
    return None


def nginx_master():
    try:
        return int((ROOT / "nginx/logs/nginx.pid").read_text().strip())
    except (OSError, ValueError):
        return None


def take_snapshot():
    OTHER.update(
        {
            "nginx_master": nginx_master(),
            "r2": port_open(19102),
            "r2_backend": port_open(19202),
            "c1": port_open(19301),
        }
    )


def test_other_sites():
    master = nginx_master()
    assert master == OTHER["nginx_master"], "Nginx master 变了: %s -> %s" % (OTHER["nginx_master"], master)
    assert port_open(19102) == OTHER["r2"], "R2 19102 状态变化"
    assert port_open(19202) == OTHER["r2_backend"], "R2 后端 19202 状态变化"
    assert port_open(19301) == OTHER["c1"], "C1 19301 状态变化"
    assert port_open(19102), "R2 19102 不再监听"
    return "Nginx master=%s、R2 19102、C1 19301 未受影响" % master


DEFAULT_CHECKS = [
    ("start 后 / 返回 200", test_index),
    ("未知路径 200 且与 / 逐字节相同", test_soft404),
    ("/.git/HEAD 200 且以 ref: 开头", test_git_head),
    ("/.git/objects/ab/cdef 404", test_git_objects),
    ("/.env 200 且含 DB_HOST=", test_env_file),
    ("备份 SQL 200 且含 INSERT INTO", test_backup),
    ("Druid 登录页 200、登录永远 fail", test_druid),
    ("Swagger 页 200、paths 为空", test_swagger),
    ("/actuator/env 含 propertySources", test_actuator),
    ("SQL 诱饵三种输入正文相同", test_sql_decoy),
    ("stop 释放端口；连续两轮 start/stop 成功", test_stop_and_rounds),
    ("R2 19102、C1 19301 未受影响", test_other_sites),
]

STRICT_CHECKS = [
    ("严格模式 90 次请求触发 429 + Retry-After=30", test_rate_limit),
    ("严格模式 stop 后端口释放、无残留 PID", test_strict_stop),
]

CHECKS = [("默认", name, func) for name, func in DEFAULT_CHECKS] + [
    ("严格", name, func) for name, func in STRICT_CHECKS
]


def cleanup():
    run("stop")
    wait_closed(19331, 20)


def main():
    print("C3 邕江云服务门户自检")
    cleanup()
    take_snapshot()
    passed = 0
    try:
        for idx, (group, name, func) in enumerate(CHECKS, 1):
            print("[%d/%d][%s] %s" % (idx, len(CHECKS), group, name))
            if check(name, func):
                passed += 1
    finally:
        run("stop")
        wait_closed(19331, 20)
    print("实际执行 %d 项，通过 %d 项" % (len(CHECKS), passed))
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
