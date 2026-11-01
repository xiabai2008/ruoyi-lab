"""一键恢复演示环境（重启电脑后跑这个）。

启动顺序：MySQL(13307) -> Redis(6379) -> R9 后端(19209) -> Nginx(19109)

用法：
    python scripts\\restore_demo.py          # 恢复 R9 演示环境
    python scripts\\restore_demo.py R9 R2    # 恢复指定站点（R2 是 R12 的后端）

说明：
- MySQL 用项目 mysql\\my.ini（datadir 是 C:/Users/HZR/ry_r2_mysql，ASCII junction）
  --defaults-file 必须走 junction 路径，直接给项目路径会因中文失败
- Redis 用 tools\\redis 的原生版（Docker 版端口转发已损坏，不要再用），密码 ruoyi123
- Nginx 只在 19109 没监听时启动
"""
import os
import socket
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MYSQLD = r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqld.exe"
MYSQL_INI = r"C:/Users/HZR/ry_r2_mysql/my.ini"
REDIS_DIR = os.path.join(ROOT, "tools", "redis")
NGINX_DIR = os.path.join(ROOT, "nginx")

FLAGS = 0
if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
    FLAGS = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS


def port_open(port, host="127.0.0.1"):
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except Exception:
        return False


def wait_port(port, seconds, label):
    for _ in range(seconds):
        if port_open(port):
            print("[OK] %s 就绪 (%ds)" % (label, _ * 1))
            return True
        time.sleep(1)
    print("[FAIL] %s 端口 %d 未监听" % (label, port))
    return False


def spawn(cmd, cwd, logname):
    log = open(os.path.join(cwd, logname), "ab")
    p = subprocess.Popen(
        cmd, cwd=cwd, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
        close_fds=True, creationflags=FLAGS,
    )
    return p.pid


def start_mysql():
    if port_open(13307):
        print("[SKIP] MySQL 已在 13307")
        return True
    if not os.path.exists(MYSQL_INI):
        print("[FAIL] 找不到 %s" % MYSQL_INI)
        return False
    pid = spawn([MYSQLD, "--defaults-file=%s" % MYSQL_INI], ROOT, "mysql/boot.log")
    print("[..] MySQL 启动中 pid=%s" % pid)
    return wait_port(13307, 40, "MySQL")


def start_redis():
    if port_open(6379):
        print("[SKIP] Redis 已在 6379")
        return True
    exe = os.path.join(REDIS_DIR, "redis-server.exe")
    if not os.path.exists(exe):
        print("[FAIL] 找不到 %s" % exe)
        return False
    pid = spawn([exe, "redis.windows.conf"], REDIS_DIR, "redis.log")
    print("[..] Redis 启动中 pid=%s" % pid)
    return wait_port(6379, 15, "Redis")


def start_nginx():
    if port_open(19109):
        print("[SKIP] Nginx 已在 19109")
        return True
    exe = os.path.join(NGINX_DIR, "nginx.exe")
    if not os.path.exists(exe):
        print("[FAIL] 找不到 %s" % exe)
        return False
    spawn([exe], NGINX_DIR, "logs/boot.log")
    print("[..] Nginx 启动中")
    return wait_port(19109, 15, "Nginx")


def start_site(site, port):
    if port_open(port):
        print("[SKIP] %s 后端已在 %d" % (site, port))
        return True
    launch = os.path.join(ROOT, "scripts", "launch.py")
    subprocess.run([sys.executable, launch, site], cwd=ROOT, check=False)
    return wait_port(port, 180, "%s 后端" % site)


def main():
    sites = sys.argv[1:] or ["R9"]
    ports = {"R1": 19201, "R2": 19202, "R3": 19203, "R4": 19204, "R5": 19205,
             "R6": 19206, "R7": 19207, "R8": 19208, "R9": 19209, "R10": 19210, "R11": 19211}

    ok = True
    ok &= start_mysql()
    ok &= start_redis()
    for s in sites:
        s = s.upper()
        if s not in ports:
            print("[SKIP] 未知站点 %s" % s)
            continue
        ok &= start_site(s, ports[s])
    ok &= start_nginx()

    print()
    print("=== 结果 ===")
    for p, label in ((13307, "MySQL"), (6379, "Redis"), (19109, "Nginx")):
        print("  %-8s %s" % (label, "UP" if port_open(p) else "DOWN"))
    for s in sites:
        s = s.upper()
        if s in ports:
            print("  %-8s %s" % (s + " 后端", "UP" if port_open(ports[s]) else "DOWN"))
    print()
    print("访问: http://127.0.0.1:19109  (admin / admin123)")


if __name__ == "__main__":
    main()
