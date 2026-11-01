r"""A2 邕江医保结算平台 8 项自检。"""
import base64
import hashlib
import hmac
import json
import re
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
BASE = "http://127.0.0.1:19341"
PIDFILE = ROOT / ".state" / "A2.pid"
APP_YML = ROOT / "src/A2/ruoyi-admin/src/main/resources/application.yml"

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def run(action):
    proc = subprocess.run(
        [PY, str(ROOT / "scripts" / "a2_start.py"), action],
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


def otp_secret():
    text = APP_YML.read_text(encoding="utf-8")
    match = re.search(r"secret:\s*([A-Z2-7]+)", text)
    assert match, "application.yml 未找到 TOTP secret"
    return match.group(1)


SECRET = otp_secret()


def totp():
    key = base64.b32decode(SECRET)
    counter = int(time.time()) // 30
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return "%06d" % (value % 1000000)


def login(data):
    return requests.post(BASE + "/login", data=data, timeout=20)


def check(name, func):
    try:
        detail = func()
        print("PASS %s%s" % (name, (" | " + str(detail)) if detail else ""))
        return True
    except Exception as exc:
        print("FAIL %s: %s" % (name, exc))
        return False


def test_login_page():
    start_ok("A2")
    resp = requests.get(BASE + "/login", timeout=20)
    assert resp.status_code == 200, resp.status_code
    assert 'name="otp"' in resp.text, "登录页缺少 otp 输入框"
    assert "动态口令" in resp.text
    assert SECRET not in resp.text, "页面泄露了 TOTP 密钥"
    return "GET /login 200，含 otp 输入框，未泄露密钥"


def test_no_otp():
    resp = login({"username": "admin", "password": "admin123"})
    data = resp.json()
    assert resp.status_code == 200, resp.status_code
    assert data.get("code") != 0, data
    assert "动态口令" in data.get("msg", ""), data
    return "%s" % data.get("msg")


def test_wrong_otp():
    resp = login({"username": "admin", "password": "admin123", "otp": "000000"})
    data = resp.json()
    assert data.get("code") != 0, data
    assert "动态口令" in data.get("msg", ""), data
    return "%s" % data.get("msg")


def test_correct_totp():
    resp = login({"username": "admin", "password": "admin123", "otp": totp()})
    data = resp.json()
    assert data.get("code") == 0, data
    return "code=0, %s" % data.get("msg")


def test_lockout():
    for i in range(5):
        resp = login({"username": "admin", "password": "wrong-pass", "otp": totp()})
        assert resp.json().get("code") != 0, "第 %d 次错误密码不应成功" % (i + 1)
    sixth = login({"username": "admin", "password": "wrong-pass", "otp": totp()}).json()
    msg = sixth.get("msg", "")
    assert "锁定" in msg or "10分钟" in msg, sixth
    assert sixth.get("code") != 0, sixth
    return "第 6 次：%s" % msg


def test_stop_ports():
    stop_ok("A2")
    assert wait_closed(19341), "19341 未释放"
    assert wait_closed(19241), "19241 未释放"
    assert not PIDFILE.exists(), "PID 文件残留"
    return "19341/19241 已释放"


def test_two_rounds():
    for round_no in (1, 2):
        start_ok("A2 第 %d 轮" % round_no)
        resp = requests.get(BASE + "/login", timeout=20)
        assert resp.status_code == 200, "第 %d 轮 /login = %s" % (round_no, resp.status_code)
        # 重启后锁定缓存已清空，正确 TOTP 应能登录
        ok = login({"username": "admin", "password": "admin123", "otp": totp()}).json()
        assert ok.get("code") == 0, "第 %d 轮登录失败: %s" % (round_no, ok)
        stop_ok("A2 第 %d 轮" % round_no)
        assert wait_closed(19341), "第 %d 轮 19341 未释放" % round_no
        assert wait_closed(19241), "第 %d 轮 19241 未释放" % round_no
        assert not PIDFILE.exists(), "第 %d 轮 PID 残留" % round_no
    return "两轮 start/stop 成功，重启后锁定解除，无残留 PID"


OTHER = {}


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
            "c3": port_open(19331),
        }
    )


def test_other_sites():
    master = nginx_master()
    assert master == OTHER["nginx_master"], "Nginx master 变了: %s -> %s" % (OTHER["nginx_master"], master)
    assert port_open(19102) == OTHER["r2"], "R2 19102 状态变化"
    assert port_open(19202) == OTHER["r2_backend"], "R2 后端 19202 状态变化"
    assert port_open(19301) == OTHER["c1"], "C1 19301 状态变化"
    assert port_open(19331) == OTHER["c3"], "C3 19331 状态变化"
    assert port_open(19102), "R2 19102 不再监听"
    return "Nginx master=%s、R2 19102、C1 19301、C3 19331 未受影响" % master


CHECKS = [
    ("GET /login 200 且含 otp 输入框", test_login_page),
    ("POST /login 不带 otp 失败", test_no_otp),
    ("POST /login 错误 otp 失败", test_wrong_otp),
    ("正确 TOTP + admin/admin123 登录成功", test_correct_totp),
    ("5 次错误密码触发锁定", test_lockout),
    ("stop 后 19341/19241 释放", test_stop_ports),
    ("start→stop 连续两轮成功、无残留 PID", test_two_rounds),
    ("R2 19102、C1 19301、C3 19331 未受影响", test_other_sites),
]


def cleanup():
    run("stop")
    for port in (19241, 19341):
        wait_closed(port, 20)


def main():
    print("A2 邕江医保结算平台自检")
    cleanup()
    take_snapshot()
    passed = 0
    try:
        for idx, (name, func) in enumerate(CHECKS, 1):
            print("[%d/%d] %s" % (idx, len(CHECKS), name))
            if check(name, func):
                passed += 1
    finally:
        run("stop")
        for port in (19241, 19341):
            wait_closed(port, 20)
    print("实际执行 %d 项，通过 %d 项" % (len(CHECKS), passed))
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
