r"""C1 运维组件停止器。

只按 .state/C1-<name>.pid 里的 PID 停止进程，不做按进程名的批量停止，
避免连带停止 R1-R12 站点。

用法：
    python scripts\components_stop.py              # 停止全部 4 个组件
    python scripts\components_stop.py jolokia      # 只停止一个
    python scripts\components_stop.py C1-3
"""
import ctypes
import os
import socket
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(ROOT, ".state")

COMPONENTS = {
    "jolokia": {"id": "C1-1", "port": 19301},
    "h2-console": {"id": "C1-2", "port": 19302},
    "data-service": {"id": "C1-3", "port": 19303},
    "config-server": {"id": "C1-4", "port": 19304},
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


def normalize(name):
    key = name.strip().lower()
    return ALIASES.get(key, key)


def stop_one(name):
    cfg = COMPONENTS[name]
    cid = cfg["id"]
    port = cfg["port"]
    pidfile = os.path.join(STATE_DIR, "%s-%s.pid" % (cid, name))
    pid = read_pid(pidfile)

    if not pid:
        if os.path.exists(pidfile):
            print("[WARN] %s PID 文件内容无效，已删除: %s" % (cid, pidfile))
            try:
                os.remove(pidfile)
            except OSError:
                pass
        else:
            print("[SKIP] %s 没有 PID 文件" % cid)
        if port_open(port):
            print("[FAIL] %s 端口 %d 仍在监听，但没有可用的 PID 文件" % (cid, port))
            return False
        return True

    if not pid_alive(pid):
        print("[SKIP] %s PID %s 已不存在，清理 PID 文件" % (cid, pid))
        try:
            os.remove(pidfile)
        except OSError:
            pass
        if port_open(port):
            print("[FAIL] %s 端口 %d 仍被占用（非 PID 文件记录的进程）" % (cid, port))
            return False
        return True

    print("[..] 停止 %s pid=%s port=%d" % (cid, pid, port))
    subprocess.call(
        ["taskkill", "/PID", str(pid), "/F"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    deadline = time.time() + 30
    while time.time() < deadline:
        if not pid_alive(pid) and not port_open(port):
            break
        # 进程已退出但端口处于 TIME_WAIT 时继续等待端口释放
        time.sleep(0.5)

    alive = pid_alive(pid)
    listening = port_open(port)
    if alive or listening:
        print("[FAIL] %s 停止未完成: 进程存活=%s 端口监听=%s" % (cid, alive, listening))
        return False

    try:
        os.remove(pidfile)
    except OSError:
        pass
    print("[OK] %s 已停止，端口 %d 已释放" % (cid, port))
    return True


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

    failures = []
    for name in names:
        if not stop_one(name):
            failures.append(name)

    if failures:
        print("[FAIL] 本次停止失败: %s" % ", ".join(failures))
        return 1
    print("[OK] 全部组件已停止")
    return 0


if __name__ == "__main__":
    sys.exit(main())
