r"""C1 运维组件启动器。

风格与 scripts/launch.py 保持一致：使用 Python subprocess 启动 java，
close_fds=True + DETACHED_PROCESS，避免 java 继承调用方的 stdout 句柄。

用法：
    python scripts\components_start.py              # 启动全部 4 个组件
    python scripts\components_start.py jolokia      # 只启动一个
    python scripts\components_start.py C1-2         # 也支持编号

启动后按组件入口探活，探活失败会打印原因并以非 0 退出。
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
JDK17_HOME = __import__("labenv").JDK17_HOME
JAVA = os.path.join(JDK17_HOME, "bin", "java.exe")
STATE_DIR = os.path.join(ROOT, ".state")

FLAGS = 0
FLAGS |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
FLAGS |= getattr(subprocess, "DETACHED_PROCESS", 0)

# name -> 配置。端口固定，探活路径使用组件自身入口。
COMPONENTS = {
    "jolokia": {
        "id": "C1-1",
        "port": 19301,
        "jar": "jolokia.jar",
        "probe": "/actuator/health",
        "desc": "Jolokia JVM 指标端点",
    },
    "h2-console": {
        "id": "C1-2",
        "port": 19302,
        "jar": "h2-console.jar",
        "probe": "/h2-console",
        "desc": "H2 Console",
    },
    "data-service": {
        "id": "C1-3",
        "port": 19303,
        "jar": "data-service.jar",
        "probe": "/api",
        "desc": "内部数据服务",
    },
    "config-server": {
        "id": "C1-4",
        "port": 19304,
        "jar": "config-server.jar",
        "probe": "/application/default",
        "desc": "配置中心",
    },
}

ALIASES = {
    "c1-1": "jolokia", "c1_1": "jolokia", "1": "jolokia",
    "c1-2": "h2-console", "c1_2": "h2-console", "2": "h2-console",
    "c1-3": "data-service", "c1_3": "data-service", "3": "data-service",
    "c1-4": "config-server", "c1_4": "config-server", "4": "config-server",
}


def kernel32():
    k = ctypes.windll.kernel32
    k.OpenProcess.restype = ctypes.c_void_p
    k.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong]
    k.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    k.CloseHandle.argtypes = [ctypes.c_void_p]
    return k


def pid_alive(pid):
    if not pid:
        return False
    k = kernel32()
    handle = k.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        if not k.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False
        return code.value == 259  # STILL_ACTIVE
    finally:
        k.CloseHandle(handle)


def port_open(port, host="127.0.0.1"):
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


def read_pid(pidfile):
    try:
        with open(pidfile, "r") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def http_status(url, timeout=3.0):
    request = urllib.request.Request(url, headers={"User-Agent": "components-start/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read(256)
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except Exception as exc:  # 探活阶段需要拿到具体原因
        return "ERR: %s" % exc


def wait_http(port, path, seconds=90):
    url = "http://127.0.0.1:%d%s" % (port, path)
    deadline = time.time() + seconds
    last = None
    while time.time() < deadline:
        last = http_status(url)
        if last == 200:
            return True, url, last
        time.sleep(0.5)
    return False, url, last


def log_tail(path, lines=20):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            data = f.readlines()
        return "".join(data[-lines:]).strip()
    except OSError:
        return "(日志暂不可读)"


def normalize(name):
    key = name.strip().lower()
    return ALIASES.get(key, key)


def start_one(name):
    cfg = COMPONENTS[name]
    cid = cfg["id"]
    port = cfg["port"]
    rundir = os.path.join(ROOT, "runtime", "C1", name)
    jar = os.path.join(rundir, cfg["jar"])
    logdir = os.path.join(rundir, "logs")
    pidfile = os.path.join(STATE_DIR, "%s-%s.pid" % (cid, name))
    outlog = os.path.join(logdir, "console.log")
    errlog = os.path.join(logdir, "console.err.log")

    os.makedirs(logdir, exist_ok=True)
    os.makedirs(STATE_DIR, exist_ok=True)

    if not os.path.exists(jar):
        print("[FAIL] %s jar 不存在: %s" % (cid, jar))
        return False

    old_pid = read_pid(pidfile)
    if old_pid and pid_alive(old_pid):
        ok, url, status = wait_http(port, cfg["probe"], seconds=5)
        if ok:
            print("[SKIP] %s 已在运行 pid=%s %s" % (cid, old_pid, url))
            return True
        print("[FAIL] %s PID %s 存活但探活失败 (%s -> %s)" % (cid, old_pid, cfg["probe"], status))
        return False

    if old_pid and not pid_alive(old_pid):
        try:
            os.remove(pidfile)
        except OSError:
            pass

    if port_open(port):
        print("[FAIL] %s 端口 %d 已被其他进程占用，未启动" % (cid, port))
        return False

    env = dict(os.environ)
    env["JAVA_HOME"] = JDK17_HOME
    env["PATH"] = os.path.join(JDK17_HOME, "bin") + os.pathsep + env.get("PATH", "")
    env.pop("SERVER_PORT", None)
    env.pop("SERVER__PORT", None)

    cmd = [
        JAVA,
        "-Xms128m",
        "-Xmx384m",
        "-Dfile.encoding=UTF-8",
        "-jar",
        jar,
        "--server.port=%d" % port,
    ]

    with open(outlog, "ab") as f_out, open(errlog, "ab") as f_err:
        proc = subprocess.Popen(
            cmd,
            cwd=rundir,
            stdin=subprocess.DEVNULL,
            stdout=f_out,
            stderr=f_err,
            env=env,
            close_fds=True,
            creationflags=FLAGS,
        )

    with open(pidfile, "w") as f:
        f.write(str(proc.pid))
    print("[..] %s %s 启动中 pid=%s port=%d" % (cid, cfg["desc"], proc.pid, port))

    ok, url, status = wait_http(port, cfg["probe"], seconds=90)
    if ok:
        print("[OK] %s 探活通过 %s (pid=%s)" % (cid, url, proc.pid))
        return True

    print("[FAIL] %s 探活失败 %s -> %s" % (cid, url, status))
    print("[FAIL] 端口监听=%s 进程存活=%s" % (port_open(port), pid_alive(proc.pid)))
    print("[FAIL] console.log 末尾:")
    print(log_tail(outlog))
    print("[FAIL] console.err.log 末尾:")
    print(log_tail(errlog))
    subprocess.call(["taskkill", "/PID", str(proc.pid), "/F"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        os.remove(pidfile)
    except OSError:
        pass
    return False


def main():
    if len(sys.argv) <= 1:
        names = list(COMPONENTS)
    else:
        names = []
        for raw in sys.argv[1:]:
            name = normalize(raw)
            if name not in COMPONENTS:
                print("[ERROR] 未知组件: %s" % raw)
                print("可用组件: %s" % ", ".join(COMPONENTS))
                return 1
            if name not in names:
                names.append(name)

    print("[..] JDK17: %s" % JAVA)
    failures = []
    for name in names:
        if not start_one(name):
            failures.append(name)

    if failures:
        print("[FAIL] 本次启动失败: %s" % ", ".join(failures))
        return 1
    print("[OK] 全部组件探活通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
