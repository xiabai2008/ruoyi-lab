#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C1 组件自检：逐项真实执行，打印 PASS/FAIL。

覆盖 8 项：
1. Jolokia 健康检查
2. Jolokia MBean 列表
3. H2 Console 页面
4. 数据服务根入口
5. 客户数据条数
6. 配置中心默认配置
7. 4 个 PID 与进程
8. 停止 4 个组件、确认端口释放、再重新拉起

任何一项失败都会继续执行后续项，最后汇总实际执行数与通过数。
"""
import ctypes
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = sys.executable
COMPONENTS = [
    ("C1-1", "jolokia", 19301, "/actuator/health"),
    ("C1-2", "h2-console", 19302, "/h2-console"),
    ("C1-3", "data-service", 19303, "/api"),
    ("C1-4", "config-server", 19304, "/application/default"),
]


def process_alive(pid):
    if not pid:
        return False
    k = ctypes.windll.kernel32
    k.OpenProcess.restype = ctypes.c_void_p
    k.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong]
    k.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    k.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = k.OpenProcess(0x1000, False, int(pid))
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        if not k.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False
        return code.value == 259
    finally:
        k.CloseHandle(handle)


def port_open(port, timeout=1.0):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def http_get(url, timeout=8.0):
    request = urllib.request.Request(url, headers={"User-Agent": "c1-verify/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        return exc.code, body
    except Exception as exc:
        return None, str(exc)


def wait_port_closed(port, seconds=30):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if not port_open(port):
            return True
        time.sleep(0.5)
    return not port_open(port)


def wait_http_ok(port, path, seconds=90):
    deadline = time.time() + seconds
    last = None
    while time.time() < deadline:
        status, _ = http_get("http://127.0.0.1:%d%s" % (port, path), timeout=3.0)
        last = status
        if status == 200:
            return True, last
        time.sleep(0.5)
    return False, last


def run_script(name):
    script = os.path.join(ROOT, "scripts", name)
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    proc = subprocess.run(
        [PYTHON, script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        env=env,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, output.strip()


def check_health_jolokia():
    status, body = http_get("http://127.0.0.1:19301/actuator/health")
    if status != 200:
        return False, "HTTP %s %s" % (status, body[:200])
    return True, "HTTP 200 %s" % body[:120]


def check_jolokia_list():
    status, body = http_get("http://127.0.0.1:19301/actuator/jolokia/list")
    if status != 200:
        return False, "HTTP %s" % status
    hits = [token for token in ("JMXConfigurator", "reloadByURL") if token in body]
    if not hits:
        return False, "HTTP 200 但未找到 JMXConfigurator/reloadByURL"
    return True, "HTTP 200 命中 %s" % ",".join(hits)


def check_h2_console():
    status, body = http_get("http://127.0.0.1:19302/h2-console")
    if status != 200:
        return False, "HTTP %s" % status
    if "H2 Console" not in body:
        return False, "HTTP 200 但页面不含 H2 Console"
    return True, "HTTP 200 页面含 H2 Console"


def check_api_root():
    status, body = http_get("http://127.0.0.1:19303/api")
    if status != 200:
        return False, "HTTP %s" % status
    if "_links" not in body:
        return False, "HTTP 200 但响应不含 _links"
    return True, "HTTP 200 响应含 _links"


def check_customers():
    status, body = http_get("http://127.0.0.1:19303/api/customers")
    if status != 200:
        return False, "HTTP %s" % status
    try:
        data = json.loads(body)
        customers = data["_embedded"]["customers"]
    except Exception as exc:
        return False, "JSON 解析失败: %s" % exc
    if len(customers) != 20:
        return False, "客户条数 %d，期望 20" % len(customers)
    return True, "客户条数 20"


def check_config_default():
    status, body = http_get("http://127.0.0.1:19304/application/default")
    if status != 200:
        return False, "HTTP %s" % status
    if "propertySources" not in body:
        return False, "HTTP 200 但响应不含 propertySources"
    try:
        data = json.loads(body)
        count = len(data.get("propertySources", []))
    except Exception:
        count = "?"
    return True, "HTTP 200 propertySources=%s" % count


def check_pids():
    details = []
    for cid, name, port, path in COMPONENTS:
        pidfile = os.path.join(ROOT, ".state", "%s-%s.pid" % (cid, name))
        if not os.path.exists(pidfile):
            details.append("%s PID文件缺失" % cid)
            continue
        try:
            with open(pidfile, "r") as f:
                pid = int(f.read().strip())
        except Exception:
            details.append("%s PID文件无效" % cid)
            continue
        alive = process_alive(pid)
        details.append("%s pid=%s alive=%s" % (cid, pid, alive))
        if not alive:
            return False, "; ".join(details)
    if any("缺失" in item or "无效" in item for item in details):
        return False, "; ".join(details)
    return True, "; ".join(details)


def check_restart_cycle():
    rc, output = run_script("components_stop.py")
    if rc != 0:
        return False, "components_stop.py 退出码 %s\n%s" % (rc, output[-1500:])

    released = []
    for cid, name, port, path in COMPONENTS:
        ok = wait_port_closed(port)
        released.append("%s:%s" % (port, "released" if ok else "LISTENING"))
        if not ok:
            return False, "停止后端口未释放: %s\n%s" % ("; ".join(released), output[-1000:])

    rc, output = run_script("components_start.py")
    if rc != 0:
        return False, "components_start.py 退出码 %s\n%s" % (rc, output[-2000:])

    for cid, name, port, path in COMPONENTS:
        ok, last = wait_http_ok(port, path, seconds=90)
        if not ok:
            return False, "重新拉起后 %s %s 探活失败 %s\n%s" % (cid, path, last, output[-1000:])

    return True, "停止后端口全部释放，重新拉起并探活通过"


CHECKS = [
    ("19301 /actuator/health = 200", check_health_jolokia),
    ("19301 /actuator/jolokia/list = 200 且含 JMXConfigurator/reloadByURL", check_jolokia_list),
    ("19302 /h2-console = 200 且含 H2 Console", check_h2_console),
    ("19303 /api = 200 且含 _links", check_api_root),
    ("19303 /api/customers = 200 且条数为 20", check_customers),
    ("19304 /application/default = 200 且含 propertySources", check_config_default),
    ("4 个 PID 文件存在且进程活着", check_pids),
    ("components_stop.py 停止 4 个进程后端口释放，components_start.py 重新拉起", check_restart_cycle),
]


def main():
    print("C1 组件自检开始，工作区: %s" % ROOT)
    print("Python: %s" % PYTHON)
    executed = 0
    passed = 0

    for index, (title, func) in enumerate(CHECKS, start=1):
        executed += 1
        try:
            ok, detail = func()
        except Exception as exc:
            ok, detail = False, "未预期异常: %s" % exc
        if ok:
            passed += 1
            print("[%d/%d] PASS  %s" % (index, len(CHECKS), title))
        else:
            print("[%d/%d] FAIL  %s" % (index, len(CHECKS), title))
        print("         %s" % detail)

    print("")
    print("实际执行 %d 项，通过 %d 项" % (executed, passed))
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
