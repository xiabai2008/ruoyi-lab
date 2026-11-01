r"""C2-2 Spring4Shell 独立 Tomcat 启停。

用法：
    python scripts\c2_s4s.py start|stop|status
"""
import ctypes
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_DIR = os.path.join(ROOT, "runtime", "C2", "s4s")
LOG_DIR = os.path.join(RUN_DIR, "logs")
STATE_DIR = os.path.join(ROOT, ".state")
TOMCAT = os.path.join(ROOT, "tools", "tomcat-9.0.58-s4s")
CATALINA = os.path.join(TOMCAT, "bin", "catalina.bat")
JDK17 = r"D:\develop\jdk-17.0.0.1"
PORT = 19313
WAR_SRC = os.path.join(RUN_DIR, "ROOT.war")
WAR_DST = os.path.join(TOMCAT, "webapps", "ROOT.war")
PIDFILE = os.path.join(STATE_DIR, "C2-s4s.pid")
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


def prepare_war():
    if not os.path.exists(WAR_SRC):
        raise RuntimeError("缺少 %s，请先构建 src/C2/s4s" % WAR_SRC)
    need_copy = not os.path.exists(WAR_DST) or os.path.getmtime(WAR_SRC) > os.path.getmtime(WAR_DST)
    if need_copy:
        exploded = os.path.join(TOMCAT, "webapps", "ROOT")
        if os.path.exists(exploded):
            backup = exploded + "_prev_" + time.strftime("%Y%m%d%H%M%S")
            os.replace(exploded, backup)
        shutil.copy2(WAR_SRC, WAR_DST)
        print("[..] 已部署 ROOT.war 到 %s" % WAR_DST)


def start():
    if port_open(PORT):
        print("[SKIP] Spring4Shell 已在运行，端口 %d" % PORT)
        return 0
    pid = read_pid(PIDFILE)
    if pid and pid_alive(pid):
        print("[FAIL] PID %s 存活但端口 %d 未监听" % (pid, PORT))
        fail_cleanup(PIDFILE, pid)
        return 1
    try:
        prepare_war()
    except RuntimeError as exc:
        print("[FAIL] %s" % exc)
        return 1
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(STATE_DIR, exist_ok=True)
    env = dict(os.environ)
    # 宿主环境可能带 SERVER_PORT / SERVER__PORT（Spring relaxed binding 会当成 server.port），
    # 不清掉会劫持端口，导致启动到随机端口或直接 PortInUse。
    for key in ("SERVER_PORT", "SERVER__PORT"):
        env.pop(key, None)
    env["JAVA_HOME"] = JDK17
    env["CATALINA_HOME"] = TOMCAT
    env["CATALINA_BASE"] = TOMCAT
    env["PATH"] = os.path.join(JDK17, "bin") + os.pathsep + env.get("PATH", "")
    log = os.path.join(LOG_DIR, "tomcat-console.log")
    with open(log, "ab") as out:
        proc = subprocess.Popen(
            ["cmd", "/c", CATALINA, "run"],
            cwd=TOMCAT,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=out,
            env=env,
            close_fds=True,
            creationflags=FLAGS,
        )
    with open(PIDFILE, "w") as f:
        f.write(str(proc.pid))
    print("[..] Tomcat 启动 pid=%s port=%d" % (proc.pid, PORT))
    deadline = time.time() + 120
    last = None
    while time.time() < deadline:
        status, body = http("http://127.0.0.1:%d/" % PORT)
        last = status
        if status == 200 and "园区设备登记" in body:
            print("[OK] Spring4Shell 就绪: http://127.0.0.1:%d/" % PORT)
            return 0
        if not pid_alive(proc.pid):
            print("[FAIL] Tomcat 进程提前退出，见 %s" % log)
            fail_cleanup(PIDFILE, proc.pid)
            return 1
        time.sleep(1)
    print("[FAIL] Spring4Shell 120 秒未就绪 last=%s" % last)
    fail_cleanup(PIDFILE, proc.pid)
    return 1


def stop():
    pid = read_pid(PIDFILE)
    if not pid:
        if port_open(PORT):
            print("[FAIL] 端口 %d 占用但无 PID 文件" % PORT)
            return 1
        print("[SKIP] Spring4Shell 未运行")
        return 0
    if pid_alive(pid):
        subprocess.call(["taskkill", "/PID", str(pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        if not pid_alive(pid) and not port_open(PORT):
            break
        time.sleep(0.5)
    try:
        os.remove(PIDFILE)
    except OSError:
        pass
    if pid_alive(pid) or port_open(PORT):
        print("[FAIL] Spring4Shell 停止未完成 pid=%s port=%d" % (pid, PORT))
        return 1
    print("[OK] Spring4Shell 已停止，端口 %d 已释放" % PORT)
    return 0


def status():
    pid = read_pid(PIDFILE)
    print("C2-2 Spring4Shell")
    print("  s4s          pid=%-7s alive=%-5s port=%-5d listening=%s" % (pid, pid_alive(pid), PORT, port_open(PORT)))
    return 0


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("start", "stop", "status"):
        print("usage: c2_s4s.py start|stop|status")
        return 1
    return {"start": start, "stop": stop, "status": status}[sys.argv[1]]()


if __name__ == "__main__":
    sys.exit(main())
