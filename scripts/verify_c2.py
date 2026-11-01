r"""C2 三座独立靶场 14 项自检。"""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
SHOTS = ROOT / "runtime" / "C2"

import requests  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def run(script, action, extra_env=None):
    env = dict(os.environ)
    # 让自检本身不受宿主 SERVER_PORT / SERVER__PORT 影响，毒化用例再显式注入。
    for key in ("SERVER_PORT", "SERVER__PORT"):
        env.pop(key, None)
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        [PY, str(ROOT / "scripts" / script), action],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=240,
        env=env,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


POISON_ENV = {"SERVER_PORT": "62148", "SERVER__PORT": "62148"}
PID_FILES = (
    ROOT / ".state" / "C2-sba-server.pid",
    ROOT / ".state" / "C2-sba-client.pid",
    ROOT / ".state" / "C2-s4s.pid",
    ROOT / ".state" / "C2-scf.pid",
)


def pid_leftovers():
    return [p.name for p in PID_FILES if p.exists()]


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


def start_ok(script, label):
    rc, out = run(script, "start")
    if rc != 0:
        raise AssertionError("%s start 失败 rc=%s\n%s" % (label, rc, out[-1200:]))


def stop_ok(script, label):
    rc, out = run(script, "stop")
    if rc != 0:
        raise AssertionError("%s stop 失败 rc=%s\n%s" % (label, rc, out[-1200:]))


def test_sba_start():
    start_ok("c2_sba.py", "SBA")
    apps = requests.get("http://127.0.0.1:19311/applications", headers={"Accept": "application/json"}, timeout=15)
    apps.raise_for_status()
    data = apps.json()
    assert isinstance(data, list) and len(data) == 1, data
    assert data[0].get("instances"), data
    return "19311 /applications 1 instance"


def test_sba_wallboard():
    resp = requests.get("http://127.0.0.1:19311/wallboard", timeout=15)
    assert resp.status_code == 200, resp.status_code
    assert len(resp.content) > 1000, "wallboard 响应过短"
    return "19311 /wallboard 200"


def test_sba_client_trace():
    resp = requests.get("http://127.0.0.1:19312/actuator/httptrace", timeout=15)
    assert resp.status_code == 200, resp.status_code
    return "19312 /actuator/httptrace 200"


def test_sba_stop():
    stop_ok("c2_sba.py", "SBA")
    assert wait_closed(19311), "19311 未释放"
    assert wait_closed(19312), "19312 未释放"
    assert not port_open(19313) and not port_open(19314), "其他靶场端口被影响"
    return "19311/19312 已释放"


def test_s4s_start():
    start_ok("c2_s4s.py", "S4S")
    resp = requests.get("http://127.0.0.1:19313/", timeout=15)
    assert resp.status_code == 200, resp.status_code
    text = resp.content.decode("utf-8", errors="replace")
    assert "园区设备登记" in text and "<form" in text, "不是设备登记页"
    return "19313 GET / 设备登记页 200"


def test_s4s_post():
    resp = requests.post(
        "http://127.0.0.1:19313/device/add",
        data={"deviceName": "测试", "location": "A区东门"},
        timeout=15,
    )
    assert resp.status_code == 200, resp.status_code
    text = resp.content.decode("utf-8", errors="replace")
    assert '"code":200' in text, text[:200]
    return "POST /device/add 200"


def test_s4s_stop():
    stop_ok("c2_s4s.py", "S4S")
    assert wait_closed(19313), "19313 未释放"
    return "19313 已释放"


def test_scf_start():
    start_ok("c2_scf.py", "SCF")
    resp = requests.get("http://127.0.0.1:19314/", timeout=15)
    assert resp.status_code == 200, resp.status_code
    assert "uppercase" in resp.text, resp.text[:200]
    return "19314 GET / 200"


def test_scf_route():
    resp = requests.post(
        "http://127.0.0.1:19314/functionRouter",
        headers={"Content-Type": "text/plain", "spring.cloud.function.definition": "uppercase"},
        data="hello",
        timeout=15,
    )
    assert resp.status_code == 200, resp.status_code
    assert resp.text == "HELLO", resp.text
    noheader = requests.post(
        "http://127.0.0.1:19314/functionRouter",
        headers={"Content-Type": "text/plain"},
        data="hello",
        timeout=15,
    )
    assert 400 <= noheader.status_code < 500, "无头请求应 4xx，实际 %s" % noheader.status_code
    return "uppercase=HELLO；无头=%d" % noheader.status_code


def test_scf_stop():
    stop_ok("c2_scf.py", "SCF")
    assert wait_closed(19314), "19314 未释放"
    return "19314 已释放"


def test_scf_two_rounds():
    for round_no in (1, 2):
        start_ok("c2_scf.py", "SCF 第 %d 轮" % round_no)
        assert port_open(19314), "第 %d 轮 19314 未监听" % round_no
        stop_ok("c2_scf.py", "SCF 第 %d 轮" % round_no)
        assert wait_closed(19314), "第 %d 轮 19314 未释放" % round_no
        left = pid_leftovers()
        assert not left, "第 %d 轮残留 PID: %s" % (round_no, left)
    return "start→stop 连续两轮成功，无残留 PID"


def test_poisoned_env():
    cases = (
        ("c2_sba.py", (19311, 19312), "SBA"),
        ("c2_s4s.py", (19313,), "S4S"),
        ("c2_scf.py", (19314,), "SCF"),
    )
    all_ports = (19311, 19312, 19313, 19314)
    for script, ports, label in cases:
        rc, out = run(script, "start", extra_env=POISON_ENV)
        if rc != 0:
            raise AssertionError("%s 带毒启动失败 rc=%s\n%s" % (label, rc, out[-800:]))
        for port in ports:
            assert port_open(port), "%s 未监听 %d" % (label, port)
        for other in all_ports:
            if other not in ports:
                assert not port_open(other), "%s 启动了非本靶场端口 %d" % (label, other)
        stop_ok(script, label)
        for port in ports:
            assert wait_closed(port), "%s 端口 %d 未释放" % (label, port)
        left = pid_leftovers()
        assert not left, "%s 停后残留 PID: %s" % (label, left)
    log = (ROOT / "runtime" / "C2" / "scf" / "logs" / "scf-console.log").read_text(
        encoding="utf-8", errors="replace"
    )
    assert "port(s): 19314" in log[-8000:], "SCF 日志未见 port(s): 19314"
    return "SERVER__PORT=62148 下 SBA/S4S/SCF 仍绑 19311+19312/19313/19314"


def test_isolation():
    # SBA only
    start_ok("c2_sba.py", "SBA isolation")
    assert port_open(19311) and port_open(19312)
    assert not port_open(19313) and not port_open(19314), "SBA 启动时其他靶场端口被打开"
    stop_ok("c2_sba.py", "SBA isolation")
    # S4S only
    start_ok("c2_s4s.py", "S4S isolation")
    assert port_open(19313)
    assert not port_open(19311) and not port_open(19312) and not port_open(19314), "S4S 启动时其他靶场端口被打开"
    stop_ok("c2_s4s.py", "S4S isolation")
    # SCF only
    start_ok("c2_scf.py", "SCF isolation")
    assert port_open(19314)
    assert not port_open(19311) and not port_open(19312) and not port_open(19313), "SCF 启动时其他靶场端口被打开"
    stop_ok("c2_scf.py", "SCF isolation")
    return "三座靶场依次启动，互不拉起"


LOG_ROOTS = [ROOT / "runtime" / "C2", ROOT / "tools" / "tomcat-9.0.58-s4s" / "logs"]
LOG_BASELINE = {}


def snapshot_logs():
    """记录本轮自检开始时各日志长度，历史失败（如 19:20 那次）不算本轮问题。"""
    for base in LOG_ROOTS:
        if not base.exists():
            continue
        for path in base.rglob("*.log"):
            try:
                LOG_BASELINE[path] = path.stat().st_size
            except OSError:
                pass


def test_logs_clean():
    checked = 0
    bad = []
    for base in LOG_ROOTS:
        if not base.exists():
            continue
        for path in base.rglob("*.log"):
            checked += 1
            offset = LOG_BASELINE.get(path, 0)
            with open(path, "rb") as f:
                f.seek(offset)
                text = f.read().decode("utf-8", "replace")
            for marker in ("OutOfMemoryError", "APPLICATION FAILED TO START"):
                if marker in text:
                    bad.append("%s: %s" % (path, marker))
    assert not bad, bad[:5]
    return "本轮检查 %d 个日志，无 OOM/启动失败" % checked


CHECKS = [
    ("SBA start 后 /applications 含 1 个实例", test_sba_start),
    ("SBA /wallboard 200", test_sba_wallboard),
    ("SBA client /actuator/httptrace 200", test_sba_client_trace),
    ("SBA stop 后 19311/19312 释放且不影响其他端口", test_sba_stop),
    ("S4S start 后 19313 GET / 设备登记页", test_s4s_start),
    ("S4S POST /device/add 200", test_s4s_post),
    ("S4S stop 后 19313 释放", test_s4s_stop),
    ("SCF start 后 19314 根路径 200", test_scf_start),
    ("SCF /functionRouter 正常路由大写、无头 4xx", test_scf_route),
    ("SCF stop 后 19314 释放", test_scf_stop),
    ("SCF start→stop 连续两轮成功", test_scf_two_rounds),
    ("注入 SERVER__PORT=62148 后三座仍绑各自端口", test_poisoned_env),
    ("三座靶场互不影响", test_isolation),
    ("全部日志无 OOM/启动失败", test_logs_clean),
]


def cleanup():
    """自检前确保三座靶场都处于停止状态，避免上一轮残留影响隔离断言。"""
    for script in ("c2_sba.py", "c2_s4s.py", "c2_scf.py"):
        run(script, "stop")
    for port in (19311, 19312, 19313, 19314):
        wait_closed(port)
    snapshot_logs()


def main():
    print("C2 三座组件靶场自检")
    cleanup()
    passed = 0
    for idx, (name, func) in enumerate(CHECKS, 1):
        print("[%d/%d] %s" % (idx, len(CHECKS), name))
        if check(name, func):
            passed += 1
    print("实际执行 %d 项，通过 %d 项" % (len(CHECKS), passed))
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
