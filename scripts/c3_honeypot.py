r"""C3 邕江云服务门户 独立启停。

用法：
    python scripts\c3_honeypot.py start|stop|status

只操作 C3：127.0.0.1:19331、PID .state\C3.pid。
"""
import ctypes
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "src", "C3", "honeypot.py")
RUN_DIR = os.path.join(ROOT, "runtime", "C3")
LOG_DIR = os.path.join(RUN_DIR, "logs")
STATE_DIR = os.path.join(ROOT, ".state")
PIDFILE = os.path.join(STATE_DIR, "C3.pid")
PYTHON = r"D:\tools\Python 3.12.9\python.exe"
PORT = 19331
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


def wait_closed(port, seconds=30):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if not port_open(port):
            return True
        time.sleep(0.5)
    return not port_open(port)


def read_pid(path):
    try:
        with open(path, "r") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def http_code(url, timeout=3):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except Exception:
        return None


def fail_cleanup(pid=None):
    if pid and pid_alive(pid):
        subprocess.call(["taskkill", "/PID", str(pid), "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        wait_closed(PORT, 15)
    try:
        os.remove(PIDFILE)
    except OSError:
        pass


def start(strict=False):
    if not os.path.exists(PYTHON):
        print("[FAIL] 缺少 Python: %s" % PYTHON)
        return 1
    if port_open(PORT):
        pid = read_pid(PIDFILE)
        if pid and pid_alive(pid):
            print("[SKIP] C3 已在运行，端口 %d" % PORT)
            return 0
        print("[FAIL] 端口 %d 被其他进程占用，拒绝启动" % PORT)
        return 1
    stale = read_pid(PIDFILE)
    if stale and pid_alive(stale):
        print("[FAIL] PID %s 存活但端口 %d 未监听" % (stale, PORT))
        fail_cleanup(stale)
        return 1

    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(STATE_DIR, exist_ok=True)
    env = dict(os.environ)
    # C2b 教训：清掉宿主端口变量，避免被下游框架当成 server.port
    for key in ("SERVER_PORT", "SERVER__PORT"):
        env.pop(key, None)
    # 默认关闭限速（用于误报基线）；--strict 才注入 80 次/60 秒
    env["C3_RATE_LIMIT"] = "80" if strict else "0"

    console = os.path.join(LOG_DIR, "console.log")
    with open(console, "ab") as out:
        proc = subprocess.Popen(
            [PYTHON, APP],
            cwd=RUN_DIR,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=out,
            env=env,
            close_fds=True,
            creationflags=FLAGS,
        )
    with open(PIDFILE, "w") as f:
        f.write(str(proc.pid))
    print("[..] C3 启动 pid=%s port=%d rate_limit=%s" % (proc.pid, PORT, env["C3_RATE_LIMIT"]))

    deadline = time.time() + 60
    last = None
    while time.time() < deadline:
        last = http_code("http://127.0.0.1:%d/" % PORT)
        if last == 200:
            print("[OK] C3 就绪: http://127.0.0.1:%d/" % PORT)
            return 0
        if not pid_alive(proc.pid):
            print("[FAIL] 进程提前退出，见 %s" % console)
            fail_cleanup(proc.pid)
            return 1
        time.sleep(0.5)
    print("[FAIL] 60 秒未就绪 last=%s" % last)
    fail_cleanup(proc.pid)
    return 1


def stop():
    pid = read_pid(PIDFILE)
    if not pid:
        if port_open(PORT):
            print("[FAIL] 端口 %d 占用但无 PID 文件" % PORT)
            return 1
        print("[SKIP] C3 未运行")
        return 0
    if pid_alive(pid):
        subprocess.call(["taskkill", "/PID", str(pid), "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not wait_closed(PORT):
        print("[FAIL] C3 停止未完成 pid=%s port=%d" % (pid, PORT))
        return 1
    try:
        os.remove(PIDFILE)
    except OSError:
        pass
    print("[OK] C3 已停止，端口 %d 已释放" % PORT)
    return 0


def status():
    pid = read_pid(PIDFILE)
    code = http_code("http://127.0.0.1:%d/" % PORT)
    print("C3 邕江云服务门户")
    print(
        "  honeypot    pid=%-7s alive=%-5s port=%-5d listening=%-5s http=%s"
        % (pid, pid_alive(pid), PORT, port_open(PORT), code)
    )
    return 0


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("start", "stop", "status"):
        print("usage: c3_honeypot.py start [--strict]|stop|status")
        return 1
    if args[0] == "start":
        if len(args) > 2 or (len(args) == 2 and args[1] != "--strict"):
            print("usage: c3_honeypot.py start [--strict]|stop|status")
            return 1
        return start(strict=(len(args) == 2 and args[1] == "--strict"))
    if len(args) != 1:
        print("usage: c3_honeypot.py start [--strict]|stop|status")
        return 1
    return {"stop": stop, "status": status}[args[0]]()


if __name__ == "__main__":
    sys.exit(main())
