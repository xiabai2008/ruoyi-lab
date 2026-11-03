r"""Y1（芋道 yudao）真实站启停 —— v1.6 靶场。

    python scripts\y1_start.py start
    python scripts\y1_start.py stop
    python scripts\y1_start.py status

为什么要这座靶场
================
v1.6 计划要把扫描器扩到芋道，但**必须先有真实站验证两个前提**
（docs/_plan_v1.6_labs.md §P1）：

1. `/jmreport/**` 是否真的 `permitAll` —— 源码里是（SecurityConfiguration 第 23 行），
   但二开项目常收紧。若被收紧，4 个 jeecg jmreport 插件就只能「路径复用、判据重写」，
   而不是「直接复用」。
2. `/system/tenant/simple-list` 免鉴权探针是否可用 —— 它比验证码图片更稳，
   能把「前缀探测」从「必须找到验证码」解绑。

这与 v1.5.6 WP3（Plus 定时任务）的教训一致：**没有真实站就动手写插件，
计划会被实测推翻。**

实现要点（都是实测踩出来的）
============================
- **JDK8**：`2026.10-jdk8-SNAPSHOT` + Spring Boot 2.7.18，与 R1-R4 同代
- **数据库**：`ry_y1`（从 `sql/mysql/ruoyi-vue-pro.sql` 导入，49 张表 4 个租户）
- **MySQL 端口 13307**：宿主 3306 不动（与其它站点共用 lab 自带实例）
- **Redis 用 16379**：宿主 6379 **有密码**（实测 `-NOAUTH`），
  lab 的 C4-1 在 16379 无密码。芋道默认连 6379，不改配置会启动失败。
- **端口 19251**（后端）/ 19115（nginx 入口），避开已有站点
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, ".state")
PIDFILE = os.path.join(STATE, "Y1.pid")
LOGDIR = os.path.join(ROOT, "runtime", "Y1")
JAR = os.path.join(ROOT, "build", "Y1", "yudao-server.jar")
JDK8 = "D:/develop/java-se-8u44-ri"

PORT = 19251
MYSQL_PORT = 13307
REDIS_PORT = 16379  # 宿主 6379 有密码，用 C4-1 的无密码实例
DB = "ry_y1"


def _port_open(port: int, host: str = "127.0.0.1") -> bool:
    s = socket.socket()
    s.settimeout(1.5)
    try:
        s.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def _pid() -> int:
    try:
        with open(PIDFILE) as f:
            return int(f.read().strip())
    except Exception:
        return 0


def start() -> int:
    if not os.path.exists(JAR):
        print(f"[FAIL] 找不到 {JAR}")
        print("       先构建: cd src\\Y1 && mvn -DskipTests package，再复制到 build\\Y1\\")
        return 1
    if not _port_open(MYSQL_PORT):
        print(f"[FAIL] MySQL {MYSQL_PORT} 未监听，先: python scripts\\lab.py up infra:mysql")
        return 1
    if not _port_open(REDIS_PORT):
        print(f"[FAIL] Redis {REDIS_PORT} 未监听，先: python scripts\\lab.py up C4-1")
        return 1

    os.makedirs(LOGDIR, exist_ok=True)
    os.makedirs(STATE, exist_ok=True)
    java = os.path.join(JDK8, "bin", "java.exe")
    env = dict(os.environ)
    env["JAVA_HOME"] = JDK8
    env["PATH"] = os.path.join(JDK8, "bin") + os.pathsep + env.get("PATH", "")

    cmd = [
        java,
        "-Xmx1024m",
        "-jar",
        JAR,
        "--spring.profiles.active=local",
        f"--server.port={PORT}",
        f"--spring.datasource.dynamic.datasource.master.url=jdbc:mysql://127.0.0.1:{MYSQL_PORT}/{DB}"
        "?useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true"
        "&nullCatalogMeansCurrent=true&rewriteBatchedStatements=true",
        "--spring.datasource.dynamic.datasource.master.username=root",
        "--spring.datasource.dynamic.datasource.master.password=",
        f"--spring.redis.port={REDIS_PORT}",
        # 关掉本地才用到的能力，减少启动负担与端口占用
        "--spring.quartz.auto-startup=false",
    ]
    log = os.path.join(LOGDIR, "run.log")
    err = os.path.join(LOGDIR, "run.err.log")
    flags = 0
    flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    flags |= getattr(subprocess, "DETACHED_PROCESS", 0)
    with open(log, "ab") as fo, open(err, "ab") as fe:
        p = subprocess.Popen(
            cmd, cwd=LOGDIR, stdin=subprocess.DEVNULL, stdout=fo, stderr=fe, env=env,
            close_fds=True, creationflags=flags,
        )
    with open(PIDFILE, "w") as f:
        f.write(str(p.pid))
    print(f"[OK] Y1 启动中 pid={p.pid} port={PORT}（日志 runtime/Y1/run.log）")
    print("     首次启动约 40-60 秒，用 status 确认")
    return 0


def stop() -> int:
    pid = _pid()
    if not pid:
        print("[SKIP] Y1 未运行")
        return 0
    rc = subprocess.call(["taskkill", "/PID", str(pid), "/T", "/F"], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    try:
        os.remove(PIDFILE)
    except OSError:
        pass
    print(f"[OK] Y1 已停止（pid {pid}）" if rc == 0 else f"[!] taskkill 返回 {rc}")
    return 0


def status() -> int:
    up = _port_open(PORT)
    print(f"Y1  后端 {PORT}: {'OK' if up else 'DOWN'}   mysql={MYSQL_PORT} redis={REDIS_PORT}")
    return 0 if up else 1


def main() -> int:
    argv = sys.argv[1:]
    cmd = argv[0].lower() if argv else "status"
    return {"start": start, "stop": stop, "status": status}.get(cmd, status)()


if __name__ == "__main__":
    sys.exit(main())
