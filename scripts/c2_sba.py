r"""C2-1 Spring Boot Admin server/client 独立启停。

用法：
    python scripts\c2_sba.py start|stop|status
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_DIR = os.path.join(ROOT, "runtime", "C2", "sba")
LOG_DIR = os.path.join(RUN_DIR, "logs")
STATE_DIR = os.path.join(ROOT, ".state")
JDK17 = r"D:\develop\jdk-17.0.0.1"
JAVA = os.path.join(JDK17, "bin", "java.exe")
SERVER_PORT = 19311
CLIENT_PORT = 19312
SERVER_JAR = os.path.join(RUN_DIR, "sba-server.jar")
CLIENT_JAR = os.path.join(RUN_DIR, "sba-client.jar")
SERVER_PID = os.path.join(STATE_DIR, "C2-sba-server.pid")
CLIENT_PID = os.path.join(STATE_DIR, "C2-sba-client.pid")
FLAGS = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def pid_alive(pid):
    if not pid:
        return False
    k = ctypes.windll.kernel32
    k.OpenProcess.restype = ctypes.c_void_p
    k.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong]
    k.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    k.CloseHandle.argtypes = [ctypes.c_void_p]
    h = k.OpenProcess(0x1000, False, int(pid))
    if not h:
        return False
    try:
        code = ctypes.c_ulong()
        return bool(k.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == 259
    finally:
        k.CloseHandle(h)


def port_open(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def read_pid(path):
    try:
        with open(path, "r") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def http(url, timeout=3):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except Exception as exc:
        return None, str(exc)


def wait_http(url, timeout, label, contains=None):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        status, body = http(url)
        last = status
        if status == 200 and (contains is None or contains in body):
            print("[OK] %s -> %s" % (label, url))
            return True
        time.sleep(1)
    print("[FAIL] %s 未就绪: %s (last=%s)" % (label, url, last))
    return False


def fail_cleanup(pidfile, pid=None):
    """启动失败时清掉自己的 PID 文件；进程若还活着先按 PID 结束，避免游离占端口。"""
    if pid and pid_alive(pid):
        subprocess.call(["taskkill", "/PID", str(pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(20):
            if not pid_alive(pid):
                break
            time.sleep(0.5)
    try:
        os.remove(pidfile)
    except OSError:
        pass


def spawn(jar, port, pidfile, logname):
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(STATE_DIR, exist_ok=True)
    log = os.path.join(LOG_DIR, logname)
    env = dict(os.environ)
    # 宿主环境可能带 SERVER_PORT / SERVER__PORT（Spring relaxed binding 会当成 server.port），
    # 不清掉会劫持端口，导致启动到随机端口或直接 PortInUse。
    for key in ("SERVER_PORT", "SERVER__PORT"):
        env.pop(key, None)
    env["JAVA_HOME"] = JDK17
    env["PATH"] = os.path.join(JDK17, "bin") + os.pathsep + env.get("PATH", "")
    with open(log, "ab") as out:
        proc = subprocess.Popen(
            [JAVA, "-Xms128m", "-Xmx384m", "-Dfile.encoding=UTF-8", "-jar", jar, "--server.port=%d" % port],
            cwd=RUN_DIR,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=out,
            env=env,
            close_fds=True,
            creationflags=FLAGS,
        )
    with open(pidfile, "w") as f:
        f.write(str(proc.pid))
    print("[..] 启动 %s pid=%s port=%d" % (os.path.basename(jar), proc.pid, port))
    return proc.pid


def start():
    if not os.path.exists(SERVER_JAR) or not os.path.exists(CLIENT_JAR):
        print("[FAIL] 缺少 jar，请先构建 src/C2/sba")
        return 1
    if port_open(SERVER_PORT) and port_open(CLIENT_PORT):
        print("[SKIP] SBA server/client 已在运行")
        return 0
    server_pid = None
    client_pid = None
    if not port_open(SERVER_PORT):
        stale = read_pid(SERVER_PID)
        if pid_alive(stale):
            print("[FAIL] SBA server PID 存活但端口未监听")
            fail_cleanup(SERVER_PID, stale)
            return 1
        server_pid = spawn(SERVER_JAR, SERVER_PORT, SERVER_PID, "sba-server-console.log")
    if not wait_http("http://127.0.0.1:%d/applications" % SERVER_PORT, 120, "SBA server /applications"):
        fail_cleanup(SERVER_PID, server_pid)
        return 1
    if not port_open(CLIENT_PORT):
        stale = read_pid(CLIENT_PID)
        if pid_alive(stale):
            print("[FAIL] SBA client PID 存活但端口未监听")
            fail_cleanup(CLIENT_PID, stale)
            return 1
        client_pid = spawn(CLIENT_JAR, CLIENT_PORT, CLIENT_PID, "sba-client-console.log")
    if not wait_http("http://127.0.0.1:%d/actuator/health" % CLIENT_PORT, 120, "SBA client /actuator/health"):
        fail_cleanup(CLIENT_PID, client_pid)
        return 1
    if not wait_http(
        "http://127.0.0.1:%d/applications" % SERVER_PORT,
        90,
        "SBA server 注册实例",
        contains="parking-gateway-service",
    ):
        if server_pid or client_pid:
            fail_cleanup(CLIENT_PID, client_pid)
            fail_cleanup(SERVER_PID, server_pid)
        return 1
    print("[OK] SBA 就绪: server 19311 + client 19312")
    return 0


def stop_pid(pidfile, port, label):
    pid = read_pid(pidfile)
    if not pid:
        if port_open(port):
            print("[FAIL] %s 端口 %d 占用但无 PID 文件" % (label, port))
            return False
        print("[SKIP] %s 未运行" % label)
        return True
    if pid_alive(pid):
        subprocess.call(["taskkill", "/PID", str(pid), "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        if not pid_alive(pid) and not port_open(port):
            break
        time.sleep(0.5)
    try:
        os.remove(pidfile)
    except OSError:
        pass
    if pid_alive(pid) or port_open(port):
        print("[FAIL] %s 停止未完成 pid=%s port=%d" % (label, pid, port))
        return False
    print("[OK] %s 已停止，端口 %d 已释放" % (label, port))
    return True


def stop():
    ok1 = stop_pid(CLIENT_PID, CLIENT_PORT, "SBA client")
    ok2 = stop_pid(SERVER_PID, SERVER_PORT, "SBA server")
    return 0 if ok1 and ok2 else 1


def status():
    print("C2-1 Spring Boot Admin")
    for label, pidfile, port in (
        ("sba-server", SERVER_PID, SERVER_PORT),
        ("sba-client", CLIENT_PID, CLIENT_PORT),
    ):
        pid = read_pid(pidfile)
        print("  %-12s pid=%-7s alive=%-5s port=%-5d listening=%s" % (label, pid, pid_alive(pid), port, port_open(port)))
    return 0


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("start", "stop", "status"):
        print("usage: c2_sba.py start|stop|status")
        return 1
    return {"start": start, "stop": stop, "status": status}[sys.argv[1]]()


if __name__ == "__main__":
    sys.exit(main())
