r"""C2-3 Spring Cloud Function 独立启停。

默认（C2_SCF_MODE=vuln）跑真实受影响版 3.2.2（CVE-2022-22963 可 SpEL 求值执行命令）；
C2_SCF_MODE=safe 跑修复版 3.2.5（受限 SimpleEvaluationContext，T(...) 求值被拒），
用于验证扫描器在「已升级版本」上不误报：

    set C2_SCF_MODE=safe && python scripts\c2_scf.py start
    python scripts\c2_scf.py stop
    set C2_SCF_MODE=vuln && python scripts\c2_scf.py start

两个 jar 由 python scripts\c2_build.py scf 一次构建（scf.jar / scf-safe.jar）。

用法：
    python scripts\c2_scf.py start|stop|status
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
RUN_DIR = os.path.join(ROOT, "runtime", "C2", "scf")
LOG_DIR = os.path.join(RUN_DIR, "logs")
STATE_DIR = os.path.join(ROOT, ".state")
JDK17_HOME = __import__("labenv").JDK17_HOME
JAVA = os.path.join(JDK17_HOME, "bin", "java.exe")
JAR = os.path.join(RUN_DIR, "scf.jar")
# safe 模式跑修复版 3.2.5 的 jar（CVE-2022-22963 修复版本 >= 3.2.3）
JAR_SAFE = os.path.join(RUN_DIR, "scf-safe.jar")
PIDFILE = os.path.join(STATE_DIR, "C2-scf.pid")
# C2-3 漏洞 / 安全模式：只影响启动哪个 jar，需 stop -> start 才生效
MODE = (os.environ.get("C2_SCF_MODE") or "vuln").strip().lower()
if MODE not in ("vuln", "safe"):
    MODE = "vuln"
PORT = 19314
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


def start():
    jar = JAR_SAFE if MODE == "safe" else JAR
    if port_open(PORT):
        print("[SKIP] Spring Cloud Function 已在运行，端口 %d（如需切模式请先 stop）" % PORT)
        return 0
    pid = read_pid(PIDFILE)
    if pid and pid_alive(pid):
        print("[FAIL] PID %s 存活但端口 %d 未监听" % (pid, PORT))
        fail_cleanup(PIDFILE, pid)
        return 1
    if not os.path.exists(jar):
        print("[FAIL] 缺少 %s，请先运行 python scripts\\c2_build.py scf" % jar)
        return 1
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(STATE_DIR, exist_ok=True)
    env = dict(os.environ)
    # 宿主环境可能带 SERVER_PORT / SERVER__PORT（Spring relaxed binding 会当成 server.port），
    # 不清掉会劫持端口，导致启动到随机端口或直接 PortInUse。
    for key in ("SERVER_PORT", "SERVER__PORT"):
        env.pop(key, None)
    env["JAVA_HOME"] = JDK17_HOME
    env["PATH"] = os.path.join(JDK17_HOME, "bin") + os.pathsep + env.get("PATH", "")
    log = os.path.join(LOG_DIR, "scf-console.log")
    print("[..] C2-3 模式: %s（%s）" % (MODE, os.path.basename(jar)))
    with open(log, "ab") as out:
        proc = subprocess.Popen(
            [JAVA, "-Xms128m", "-Xmx320m", "-Dfile.encoding=UTF-8", "-jar", jar, "--server.port=%d" % PORT],
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
    print("[..] Spring Cloud Function 启动 pid=%s port=%d" % (proc.pid, PORT))
    deadline = time.time() + 90
    last = None
    while time.time() < deadline:
        status, _ = http("http://127.0.0.1:%d/" % PORT)
        last = status
        if status == 200:
            print("[OK] Spring Cloud Function 就绪: http://127.0.0.1:%d/" % PORT)
            return 0
        if not pid_alive(proc.pid):
            print("[FAIL] 进程提前退出，见 %s" % log)
            fail_cleanup(PIDFILE, proc.pid)
            return 1
        time.sleep(1)
    print("[FAIL] 90 秒未就绪 last=%s" % last)
    fail_cleanup(PIDFILE, proc.pid)
    return 1


def stop():
    pid = read_pid(PIDFILE)
    if not pid:
        if port_open(PORT):
            print("[FAIL] 端口 %d 占用但无 PID 文件" % PORT)
            return 1
        print("[SKIP] Spring Cloud Function 未运行")
        return 0
    if pid_alive(pid):
        subprocess.call(["taskkill", "/PID", str(pid), "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        if not pid_alive(pid) and not port_open(PORT):
            break
        time.sleep(0.5)
    try:
        os.remove(PIDFILE)
    except OSError:
        pass
    if pid_alive(pid) or port_open(PORT):
        print("[FAIL] Spring Cloud Function 停止未完成 pid=%s port=%d" % (pid, PORT))
        return 1
    print("[OK] Spring Cloud Function 已停止，端口 %d 已释放" % PORT)
    return 0


def status():
    pid = read_pid(PIDFILE)
    print("C2-3 Spring Cloud Function（模式: %s）" % MODE)
    print("  scf          pid=%-7s alive=%-5s port=%-5d listening=%s" % (pid, pid_alive(pid), PORT, port_open(PORT)))
    return 0


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("start", "stop", "status"):
        print("usage: c2_scf.py start|stop|status")
        return 1
    return {"start": start, "stop": stop, "status": status}[sys.argv[1]]()


if __name__ == "__main__":
    sys.exit(main())
