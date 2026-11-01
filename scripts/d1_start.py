r"""D1 邕江物流运输管理系统 独立启停（含漏洞演示模式开关）。

用法：
    python scripts\d1_start.py start [safe|vuln]     # 默认 safe
    python scripts\d1_start.py start --lab-mode vuln
    python scripts\d1_start.py stop|status

lab.mode=vuln 时以 -Dlab.mode=vuln 启动后端，开启 D1 漏洞演示模块
（/openapi/** 进 Shiro anon 白名单 + 开放接口模板求值）；默认 safe 为官方行为。
也可用环境变量 LAB_MODE=safe|vuln 指定（python scripts\lab.py up D1 --lab-mode vuln
即通过 LAB_MODE 透传到本脚本）。

只操作 D1：后端 19221、Nginx 19321、PID .state\D1.pid。
Nginx 采用按站点启停：start 启用 conf.d\D1.conf 并 reload，
stop 停用（改名为 D1.conf.disabled）并 reload，19321 随即释放，不影响其他站点。
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
RUN_DIR = os.path.join(ROOT, "runtime", "D1")
LOG_DIR = os.path.join(RUN_DIR, "logs")
STATE_DIR = os.path.join(ROOT, ".state")
BUILD_DIR = os.path.join(ROOT, "build", "D1")
JAR = os.path.join(BUILD_DIR, "ruoyi-admin.jar")
PIDFILE = os.path.join(STATE_DIR, "D1.pid")
JDK8_HOME = __import__("labenv").JDK8_HOME
JAVA = os.path.join(JDK8_HOME, "bin", "java.exe")
BACKEND_PORT = 19221
NGINX_PORT = 19321
NGINX_DIR = os.path.join(ROOT, "nginx")
NGINX_EXE = os.path.join(NGINX_DIR, "nginx.exe")
CONF_ACTIVE = os.path.join(NGINX_DIR, "conf.d", "D1.conf")
CONF_DISABLED = os.path.join(NGINX_DIR, "conf.d", "D1.conf.disabled")
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


def wait_closed(port, seconds=40):
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


def http_code(url, timeout=5):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except Exception:
        return None


MODES = ("safe", "vuln")


def parse_mode(args):
    """解析 start 的模式参数：位置参数 safe|vuln 或 --lab-mode safe|vuln；缺省读 LAB_MODE。"""
    mode = ""
    index = 0
    while index < len(args):
        item = args[index]
        if item == "--lab-mode":
            if index + 1 >= len(args):
                print("[FAIL] --lab-mode 缺少取值（safe|vuln）")
                return None
            mode = args[index + 1].strip().lower()
            index += 2
            continue
        if item.lower() in MODES:
            mode = item.lower()
            index += 1
            continue
        print("[FAIL] 无法识别的参数: %s" % item)
        return None
    if not mode:
        mode = (os.environ.get("LAB_MODE") or "safe").strip().lower()
    if mode not in MODES:
        print("[FAIL] lab.mode 只能是 safe 或 vuln，实际: %s" % mode)
        return None
    return mode


def lab_mode():
    """从后端 /portal/lab/status 读取当前运行模式；读不到返回 unknown。"""
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:%d/portal/lab/status" % BACKEND_PORT, timeout=3
        ) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body.get("labMode") or "unknown"
    except Exception:
        return "unknown"


def wait_http(url, timeout, label, expect=200):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = http_code(url)
        if last == expect:
            print("[OK] %s -> %s" % (label, url))
            return True
        time.sleep(1)
    print("[FAIL] %s 未就绪: %s (last=%s)" % (label, url, last))
    return False


def nginx_running():
    pid = read_pid(os.path.join(NGINX_DIR, "logs", "nginx.pid"))
    return pid_alive(pid)


def nginx_test():
    proc = subprocess.run(
        [NGINX_EXE, "-t"],
        cwd=NGINX_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode == 0, (proc.stdout or "") + (proc.stderr or "")


def nginx_reload(label):
    ok, out = nginx_test()
    if not ok:
        print("[FAIL] Nginx 配置校验失败，拒绝 reload：\n%s" % out.strip())
        return False
    if not nginx_running():
        print("[..] Nginx 未运行，启动中")
        with open(os.path.join(NGINX_DIR, "logs", "boot_d1.log"), "ab") as out_f:
            subprocess.Popen(
                [NGINX_EXE],
                cwd=NGINX_DIR,
                stdin=subprocess.DEVNULL,
                stdout=out_f,
                stderr=out_f,
                close_fds=True,
                creationflags=FLAGS,
            )
        time.sleep(2)
        return nginx_running()
    proc = subprocess.run(
        [NGINX_EXE, "-s", "reload"],
        cwd=NGINX_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        print("[FAIL] Nginx reload 失败：%s" % ((proc.stdout or "") + (proc.stderr or "")).strip())
        return False
    print("[OK] Nginx reload（%s）" % label)
    return True


def enable_conf():
    if os.path.exists(CONF_DISABLED) and not os.path.exists(CONF_ACTIVE):
        os.replace(CONF_DISABLED, CONF_ACTIVE)
        print("[..] 启用 conf.d/D1.conf")
    return nginx_reload("启用 D1.conf")


def disable_conf():
    if os.path.exists(CONF_ACTIVE):
        os.replace(CONF_ACTIVE, CONF_DISABLED)
        print("[..] 停用 conf.d/D1.conf")
    if nginx_running():
        return nginx_reload("停用 D1.conf")
    return True


def fail_cleanup(pid=None):
    if pid and pid_alive(pid):
        subprocess.call(["taskkill", "/PID", str(pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        wait_closed(BACKEND_PORT, 20)
    try:
        os.remove(PIDFILE)
    except OSError:
        pass


def start(mode="safe"):
    print("[..] D1 漏洞演示模式: %s（启动参数 -Dlab.mode=%s）" % (mode, mode))
    if not os.path.exists(JAR):
        print("[FAIL] 缺少 %s，请先构建 src/D1 并复制到 build/D1" % JAR)
        return 1
    if port_open(BACKEND_PORT):
        pid = read_pid(PIDFILE)
        if pid and pid_alive(pid):
            print("[SKIP] D1 后端已在运行，端口 %d（当前 lab.mode=%s）" % (BACKEND_PORT, lab_mode()))
            if not port_open(NGINX_PORT):
                if not enable_conf() or not wait_http(
                    "http://127.0.0.1:%d/portal/auth/signin" % NGINX_PORT, 30, "D1 Nginx 入口"
                ):
                    return 1
            return 0
        print("[FAIL] 端口 %d 被其他进程占用，拒绝启动" % BACKEND_PORT)
        return 1
    stale = read_pid(PIDFILE)
    if stale and pid_alive(stale):
        print("[FAIL] PID %s 存活但端口 %d 未监听" % (stale, BACKEND_PORT))
        fail_cleanup(stale)
        return 1

    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(STATE_DIR, exist_ok=True)
    env = dict(os.environ)
    # C2b 教训：宿主 SERVER_PORT / SERVER__PORT 会被 Spring relaxed binding 当成 server.port
    for key in ("SERVER_PORT", "SERVER__PORT"):
        env.pop(key, None)
    env["JAVA_HOME"] = JDK8_HOME
    env["PATH"] = os.path.join(JDK8_HOME, "bin") + os.pathsep + env.get("PATH", "")

    log = os.path.join(LOG_DIR, "run.log")
    err = os.path.join(LOG_DIR, "run.err.log")
    with open(log, "ab") as out, open(err, "ab") as err_out:
        proc = subprocess.Popen(
            [
                JAVA,
                "-Xms256m",
                "-Xmx512m",
                "-Dfile.encoding=UTF-8",
                "-Dlab.mode=%s" % mode,
                "-jar",
                JAR,
                "--server.port=%d" % BACKEND_PORT,
                "--spring.profiles.active=druid,prod",
            ],
            cwd=RUN_DIR,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err_out,
            env=env,
            close_fds=True,
            creationflags=FLAGS,
        )
    with open(PIDFILE, "w") as f:
        f.write(str(proc.pid))
    print("[..] D1 后端启动 pid=%s port=%d lab.mode=%s" % (proc.pid, BACKEND_PORT, mode))

    deadline = time.time() + 180
    last = None
    while time.time() < deadline:
        last = http_code("http://127.0.0.1:%d/portal/auth/signin" % BACKEND_PORT)
        if last == 200:
            break
        if not pid_alive(proc.pid):
            print("[FAIL] 后端进程提前退出，见 %s / %s" % (log, err))
            fail_cleanup(proc.pid)
            return 1
        time.sleep(1)
    else:
        print("[FAIL] 后端 180 秒未就绪 last=%s" % last)
        fail_cleanup(proc.pid)
        return 1
    print("[OK] D1 后端就绪: http://127.0.0.1:%d/portal/auth/signin" % BACKEND_PORT)

    if not enable_conf():
        fail_cleanup(proc.pid)
        return 1
    if not wait_http("http://127.0.0.1:%d/portal/auth/signin" % NGINX_PORT, 40, "D1 Nginx 入口"):
        fail_cleanup(proc.pid)
        disable_conf()
        return 1
    print("[OK] D1 就绪: http://127.0.0.1:%d/portal/auth/signin" % NGINX_PORT)
    return 0


def stop():
    pid = read_pid(PIDFILE)
    ok = True
    if not pid:
        if port_open(BACKEND_PORT):
            print("[FAIL] 端口 %d 占用但无 PID 文件" % BACKEND_PORT)
            ok = False
        else:
            print("[SKIP] D1 后端未运行")
    else:
        if pid_alive(pid):
            subprocess.call(["taskkill", "/PID", str(pid), "/T", "/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if wait_closed(BACKEND_PORT):
            print("[OK] D1 后端已停止，端口 %d 已释放" % BACKEND_PORT)
        else:
            print("[FAIL] D1 后端停止未完成 pid=%s port=%d" % (pid, BACKEND_PORT))
            ok = False
        try:
            os.remove(PIDFILE)
        except OSError:
            pass

    if disable_conf():
        if wait_closed(NGINX_PORT):
            print("[OK] D1 Nginx 入口已下线，端口 %d 已释放" % NGINX_PORT)
        else:
            print("[FAIL] 端口 %d 未释放" % NGINX_PORT)
            ok = False
    else:
        ok = False
    return 0 if ok else 1


def status():
    pid = read_pid(PIDFILE)
    backend_http = http_code("http://127.0.0.1:%d/portal/auth/signin" % BACKEND_PORT)
    nginx_http = http_code("http://127.0.0.1:%d/portal/auth/signin" % NGINX_PORT)
    conf_state = "enabled" if os.path.exists(CONF_ACTIVE) else (
        "disabled" if os.path.exists(CONF_DISABLED) else "missing"
    )
    print("D1 邕江物流运输管理系统")
    print("  lab.mode    %s" % lab_mode())
    print(
        "  backend     pid=%-7s alive=%-5s port=%-5d listening=%-5s http=%s"
        % (pid, pid_alive(pid), BACKEND_PORT, port_open(BACKEND_PORT), backend_http)
    )
    print(
        "  nginx       conf=%-8s port=%-5d listening=%-5s http=%s"
        % (conf_state, NGINX_PORT, port_open(NGINX_PORT), nginx_http)
    )
    return 0


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] not in ("start", "stop", "status"):
        print("usage: d1_start.py start [safe|vuln] | stop | status")
        print("       d1_start.py start --lab-mode safe|vuln（默认 safe，也可用环境变量 LAB_MODE）")
        return 2
    command, rest = argv[0], argv[1:]
    if command != "start":
        if rest:
            print("[FAIL] %s 不接受参数: %s" % (command, " ".join(rest)))
            return 2
        return {"stop": stop, "status": status}[command]()
    mode = parse_mode(rest)
    if mode is None:
        return 2
    return start(mode)


if __name__ == "__main__":
    sys.exit(main())
