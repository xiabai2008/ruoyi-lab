r"""D1 邕江物流运输管理系统 13 项自检。"""
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
BASE = "http://127.0.0.1:19321"
BACKEND = "http://127.0.0.1:19221"
PIDFILE = ROOT / ".state" / "D1.pid"
FAVICON = ROOT / "src/D1/ruoyi-admin/src/main/resources/static/favicon.ico"
TEMPLATES = ROOT / "src/D1/ruoyi-admin/src/main/resources/templates"
OFFICIAL_MD5 = "e49fd30ea870c7a820464ca56a113e6e"

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def run(action):
    proc = subprocess.run(
        [PY, str(ROOT / "scripts" / "d1_start.py"), action],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def start_ok(label):
    rc, out = run("start")
    if rc != 0:
        raise AssertionError("%s start 失败 rc=%s\n%s" % (label, rc, out[-1200:]))


def stop_ok(label):
    rc, out = run("stop")
    if rc != 0:
        raise AssertionError("%s stop 失败 rc=%s\n%s" % (label, rc, out[-1200:]))


def port_open(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def wait_closed(port, seconds=40):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if not port_open(port):
            return True
        time.sleep(0.5)
    return not port_open(port)


def login_session():
    session = requests.Session()
    resp = session.post(
        BASE + "/portal/auth/signin",
        data={"username": "admin", "password": "admin123"},
        timeout=20,
    )
    resp.raise_for_status()
    return session


def visible_text(html):
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text)


def listen_pid(port):
    try:
        import psutil

        for conn in psutil.net_connections(kind="tcp"):
            if conn.status == psutil.CONN_LISTEN and conn.laddr and conn.laddr.port == port:
                return conn.pid
    except Exception:
        pass
    return None


def nginx_master():
    try:
        return int((ROOT / "nginx/logs/nginx.pid").read_text().strip())
    except (OSError, ValueError):
        return None


def alive(pid):
    if not pid:
        return False
    try:
        import psutil

        return psutil.pid_exists(int(pid))
    except Exception:
        return False


OTHER_SNAPSHOT = {}


def take_other_snapshot():
    OTHER_SNAPSHOT.clear()
    OTHER_SNAPSHOT.update(
        {
            "nginx_master": nginx_master(),
            "r2": port_open(19102),
            "r2_backend": port_open(19202),
            "c1": port_open(19301),
        }
    )


def check(name, func):
    try:
        detail = func()
        print("PASS %s%s" % (name, (" | " + str(detail)) if detail else ""))
        return True
    except Exception as exc:
        print("FAIL %s: %s" % (name, exc))
        return False


def test_start_and_login_page():
    start_ok("D1")
    resp = requests.get(BASE + "/portal/auth/signin", timeout=20)
    assert resp.status_code == 200, resp.status_code
    assert "邕江物流" in resp.text, "登录页缺少邕江物流"
    return "19321 /portal/auth/signin 200"


def test_old_login_404():
    a = requests.get(BASE + "/portal/login", timeout=20, allow_redirects=False)
    b = requests.get(BASE + "/login", timeout=20, allow_redirects=False)
    assert a.status_code == 404, "/portal/login=%s" % a.status_code
    assert b.status_code == 404, "/login=%s" % b.status_code
    return "/portal/login=404, /login=404"


def test_login_api():
    resp = requests.post(
        BASE + "/portal/auth/signin",
        data={"username": "admin", "password": "admin123"},
        timeout=20,
    )
    assert resp.status_code == 200, resp.status_code
    data = resp.json()
    assert data.get("success") is True, data
    assert data.get("message") == "登录成功", data
    return "success=true, message=登录成功"


def test_list_api():
    session = login_session()
    resp = session.post(BASE + "/portal/system/user/list", timeout=20)
    assert resp.status_code == 200, resp.status_code
    data = resp.json()
    assert data.get("code") == 0, data
    assert int(data.get("total", 0)) > 0, data
    assert isinstance(data.get("rows"), list) and data["rows"], "rows 为空"
    get_resp = session.get(BASE + "/portal/system/user/list", timeout=20)
    get_body = get_resp.json() if "json" in get_resp.headers.get("Content-Type", "") else {}
    assert get_body.get("code") != 0, "GET 不应再返回列表数据: %s" % get_body
    return "POST code=0, total=%s；GET 已回退（HTTP %s，code=%s）" % (
        data["total"],
        get_resp.status_code,
        get_body.get("code"),
    )


def test_favicon():
    assert FAVICON.exists(), "favicon 不存在"
    md5 = hashlib.md5(FAVICON.read_bytes()).hexdigest()
    assert md5 != OFFICIAL_MD5, "favicon 仍是官方文件"
    resp = requests.get(BASE + "/portal/favicon.ico", timeout=20)
    assert resp.status_code == 200, resp.status_code
    served = hashlib.md5(resp.content).hexdigest()
    assert served == md5, "线上 favicon 与文件不一致"
    return "md5=%s" % md5


def test_no_version_param():
    hits = 0
    for path in TEMPLATES.rglob("*.html"):
        hits += path.read_text(encoding="utf-8").count("v=4.6.2")
    assert hits == 0, "仍有 %d 处 v=4.6.2" % hits
    return "模板 v=4.6.2 数量=0"


def test_visible_branding():
    session = login_session()
    pages = {
        "登录页": requests.get(BASE + "/portal/auth/signin", timeout=20).text,
        "框架页": session.get(BASE + "/portal/index", timeout=20).text,
        "404页": session.get(BASE + "/portal/d1-not-exist", timeout=20).text,
        "403页": session.get(BASE + "/portal/unauth", timeout=20).text,
    }
    for label, html in pages.items():
        text = visible_text(html)
        assert "若依" not in text, "%s 出现「若依」" % label
        assert "RuoYi" not in text, "%s 出现 RuoYi" % label
    assert "邕江物流" in visible_text(pages["登录页"])
    assert "邕江物流" in visible_text(pages["框架页"])
    return "登录/框架/404/403 可见文案干净"


def test_stop_ports():
    stop_ok("D1")
    assert wait_closed(19321), "19321 未释放"
    assert wait_closed(19221), "19221 未释放"
    assert not PIDFILE.exists(), "PID 文件残留"
    return "19321/19221 已释放"


def test_two_rounds():
    for round_no in (1, 2):
        start_ok("D1 第 %d 轮" % round_no)
        resp = requests.get(BASE + "/portal/auth/signin", timeout=20)
        assert resp.status_code == 200, "第 %d 轮登录页 %s" % (round_no, resp.status_code)
        stop_ok("D1 第 %d 轮" % round_no)
        assert wait_closed(19221), "第 %d 轮 19221 未释放" % round_no
        assert wait_closed(19321), "第 %d 轮 19321 未释放" % round_no
        assert not PIDFILE.exists(), "第 %d 轮 PID 残留" % round_no
    return "start→stop 连续两轮成功，无残留 PID"


def test_other_sites():
    now_master = nginx_master()
    assert now_master == OTHER_SNAPSHOT["nginx_master"], "Nginx master 变了: %s -> %s" % (
        OTHER_SNAPSHOT["nginx_master"],
        now_master,
    )
    assert alive(now_master), "Nginx master 不存活"
    assert port_open(19102) == OTHER_SNAPSHOT["r2"], "R2 19102 状态变化"
    assert port_open(19202) == OTHER_SNAPSHOT["r2_backend"], "R2 后端 19202 状态变化"
    assert port_open(19301) == OTHER_SNAPSHOT["c1"], "C1 19301 状态变化"
    assert port_open(19102), "R2 19102 不再监听"
    return "Nginx master=%s、R2 19102、C1 19301 未受影响" % now_master


REPORT_V2 = ROOT / "reports_d1/anon_v2/report.json"


def test_root_redirect():
    if not port_open(19321):
        start_ok("D1 根路径检查")
    root = requests.get(BASE + "/", timeout=20, allow_redirects=False)
    portal = requests.get(BASE + "/portal", timeout=20, allow_redirects=False)
    assert root.status_code == 302, "GET / = %s" % root.status_code
    assert "/portal/" in root.headers.get("Location", ""), root.headers.get("Location")
    assert portal.status_code == 302, "GET /portal = %s" % portal.status_code
    return "GET / -> 302 %s；GET /portal -> 302" % root.headers.get("Location")


def test_unauth_list_redirect():
    resp = requests.get(BASE + "/portal/system/user/list", timeout=20, allow_redirects=False)
    assert resp.status_code == 302, "未登录列表应 302，实际 %s" % resp.status_code
    loc = resp.headers.get("Location", "")
    assert "/portal/auth/signin" in loc, "跳转目标不对: %s" % loc
    return "302 -> %s" % loc


def test_baseline_target():
    assert REPORT_V2.exists(), "缺少 %s，请先跑基线" % REPORT_V2
    data = json.loads(REPORT_V2.read_text(encoding="utf-8"))
    target = data.get("target", "")
    assert target.rstrip("/") == "http://127.0.0.1:19321", "target=%s" % target
    assert int(data.get("request_count", 0)) > 0, "request_count=%s" % data.get("request_count")
    return "target=%s, request_count=%s" % (target, data.get("request_count"))


CHECKS = [
    ("start 后 /portal/auth/signin 200 且含邕江物流", test_start_and_login_page),
    ("旧登录地址 /portal/login 与 /login 均 404", test_old_login_404),
    ("POST /portal/auth/signin 返回 success=true", test_login_api),
    ("会话 POST /portal/system/user/list 返回 code=0 且 total>0", test_list_api),
    ("favicon md5 非官方", test_favicon),
    ("模板 ?v=4.6.2 数量为 0", test_no_version_param),
    ("登录/框架/错误页可见文案无若依/RuoYi", test_visible_branding),
    ("stop 后 19321/19221 释放", test_stop_ports),
    ("start→stop 连续两轮成功、无残留 PID", test_two_rounds),
    ("R2 19102、C1 19301 未受影响", test_other_sites),
    ("GET / 返回 302 到 /portal/", test_root_redirect),
    ("未登录 GET 列表 302 到登录页", test_unauth_list_redirect),
    ("基线报告 target 为根地址且请求数>0", test_baseline_target),
]


def cleanup():
    run("stop")
    for port in (19221, 19321):
        wait_closed(port, 20)


def main():
    print("D1 邕江物流运输管理系统自检")
    cleanup()
    take_other_snapshot()
    passed = 0
    try:
        for idx, (name, func) in enumerate(CHECKS, 1):
            print("[%d/%d] %s" % (idx, len(CHECKS), name))
            if check(name, func):
                passed += 1
    finally:
        run("stop")
        for port in (19221, 19321):
            wait_closed(port, 20)
    print("实际执行 %d 项，通过 %d 项" % (len(CHECKS), passed))
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
