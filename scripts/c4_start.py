r"""C4 中间件靶场启停：Redis 未授权 / MinIO 未授权 / RocketMQ Dashboard 未授权。

为什么需要这组靶场
------------------
盲测统计发现 54 个插件里只有 25 个在历史产物中 CONFIRMED 过。其中
`redis_unauth` / `minio_unauth` / `rocketmq_unauth` 三个**靶场里根本没有对应目标** ——
它们不是"测了没报"，而是**从来没有被验证过能不能检出**。这是「花架子」最具体的形态。

建站原则：按真实产品形态起，不照插件源码凑路径。
  - Redis：空密码 + bind 0.0.0.0 + protected-mode no（运维三个最常见错误操作）
  - MinIO：单节点 + 匿名读写 policy（企业内网常见"方便共享"配置）
  - RocketMQ：dashboard 不带登录（官方默认就是无鉴权）

用法：
    python scripts\c4_start.py build              # 先构建有源码的组件（RocketMQ）
    python scripts\c4_start.py start              # 启动全部
    python scripts\c4_start.py start redis        # 只起 Redis
    python scripts\c4_start.py status
    python scripts\c4_start.py stop

注意：src/C4/*/target/ 与 runtime/C4/*/*.jar 不入库（构建产物），
首次使用或改过源码后先跑 `build`。
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(ROOT, ".state")
TOOLS = os.path.join(ROOT, "tools")
# JDK17 解释器路径，统一收成一个常量。
# 用正斜杠：Windows API 同样接受，而且彻底避开反斜杠转义坑
# （写转义时 \b 会被解释成退格符，路径会静默变成 "jdk-17.0.0.1in\java.exe"）。
JAVA17 = "D:/develop/jdk-17.0.0.1/bin/java.exe"

FLAGS = 0
FLAGS |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
FLAGS |= getattr(subprocess, "DETACHED_PROCESS", 0)

# name -> 配置
#   port:    对外端口（Redis 用 16379 避开宿主 6379，扫描器默认探 6379）
#   pidfile: .state/ 下的文件名
#   start:   (可执行文件, 参数列表, 工作目录)
C4 = {
    "redis": {
        "id": "C4-1",
        "port": 16379,
        "pidfile": "C4-1-redis.pid",
        "exe": os.path.join(TOOLS, "redis", "redis-server.exe"),
        "args": ["redis.conf"],
        "cwd": os.path.join(ROOT, "runtime", "C4", "redis-unauth"),
        "desc": "Redis 未授权（空密码 + bind 0.0.0.0 + protected-mode no）",
        "probe": "redis",
    },
    "minio": {
        "id": "C4-2",
        "port": 19000,
        "pidfile": "C4-2-minio.pid",
        # 不是真 MinIO 二进制：社区版已被 MinIO 官方下架（所有 dl.min.io/server/... 返回 410），
        # 仅存的 AIStor 版需要商业 license，无 license 时连 ListBuckets 都拒绝，
        # 做不了「匿名可读」场景。改用按真实 S3 协议复刻的服务（响应头/XML 结构照抄）。
        "exe": sys.executable,
        "args": [os.path.join(ROOT, "src", "C4", "minio-s3", "server.py"), "--port", "19000"],
        "cwd": os.path.join(ROOT, "runtime", "C4", "minio"),
        "desc": "MinIO/S3 未授权（真实 S3 协议复刻，S3 根路径匿名可列举）",
        "probe": "minio_s3",
    },
    "rocketmq": {
        "id": "C4-3",
        "port": 19080,
        "pidfile": "C4-3-rocketmq.pid",
        "exe": JAVA17,
        "args": ["-jar", "c4-rocketmq-dashboard-1.0.0.jar"],
        "cwd": os.path.join(ROOT, "runtime", "C4", "rocketmq"),
        "desc": "RocketMQ Dashboard 未授权（官方默认无鉴权，控制台在根路径 /）",
        "probe": "http",
        "env": {"JAVA_HOME": r"D:\develop\jdk-17.0.0.1"},
    },
    "jmreport": {
        "id": "C4-4",
        "port": 19081,
        "pidfile": "C4-4-jmreport.pid",
        "exe": JAVA17,
        "args": ["-jar", "c4-jmreport-ssti-1.0.0.jar"],
        "cwd": os.path.join(ROOT, "runtime", "C4", "jmreport"),
        "desc": "JeecgBoot jmreport Freemarker SSTI（真实模板引擎求值，无鉴权）",
        "probe": "ssti",
        "env": {"JAVA_HOME": r"D:\develop\jdk-17.0.0.1"},
    },
    "gen": {
        "id": "C4-5",
        "port": 19082,
        "pidfile": "C4-5-gen.pid",
        "exe": JAVA17,
        "args": ["-jar", "c4-ruoyi-gen-ssti-1.0.0.jar"],
        "cwd": os.path.join(ROOT, "runtime", "C4", "gen"),
        "desc": "若依代码生成预览 SSTI（真实 Freemarker 渲染 tableName）",
        "probe": "ssti_gen",
        "env": {"JAVA_HOME": r"D:\develop\jdk-17.0.0.1"},
    },
    "thymeleaf": {
        "id": "C4-6",
        "port": 19083,
        "pidfile": "C4-6-thymeleaf.pid",
        "exe": JAVA17,
        "args": ["-jar", "c4-thymeleaf-ssti-1.0.0.jar"],
        "cwd": os.path.join(ROOT, "runtime", "C4", "thymeleaf"),
        "desc": "Thymeleaf/SpEL 视图名注入（真实 SpEL 求值 __${}__ ）",
        "probe": "ssti_thymeleaf",
        "env": {"JAVA_HOME": r"D:\develop\jdk-17.0.0.1"},
    },
}

ALL = list(C4)


def port_open(port: int, host: str = "127.0.0.1", timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def read_pid(path: str) -> int | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        import ctypes

        k = ctypes.windll.kernel32
        k.OpenProcess.restype = ctypes.c_void_p
        k.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong]
        h = k.OpenProcess(0x1000, False, int(pid))
        if not h:
            return False
        try:
            code = ctypes.c_ulong()
            if not k.GetExitCodeProcess(ctypes.c_void_p(h), ctypes.byref(code)):
                return False
            return code.value == 259
        finally:
            k.CloseHandle(ctypes.c_void_p(h))
    except Exception:
        return False


def probe_redis(port: int) -> str:
    """发送 INFO，返回 redis_version；无密码时能拿到。"""
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=3)
    except OSError as e:
        return f"连接失败: {e}"
    try:
        s.sendall(b"INFO\r\n")
        s.settimeout(3)
        data = b""
        try:
            while len(data) < 1024:
                c = s.recv(1024)
                if not c:
                    break
                data += c
        except socket.timeout:
            pass
        text = data.decode("utf-8", "replace")
        if "redis_version" in text:
            for line in text.splitlines():
                if line.startswith("redis_version:"):
                    return f"无密码可读 {line.strip()}"
            return "无密码可读 INFO"
        return f"已认证/异常响应: {text[:60]}"
    finally:
        s.close()


def probe_ssti(port: int) -> str:
    """对 jmreport SSTI 靶场做真实探针：确认模板引擎真的在求值。

    只检查端口不够 —— 服务起来了但模板引擎没接对（比如 Freemarker bean 没注入）
    时，接口会返回 200 + 错误 JSON，看起来"健康"其实靶场是坏的。
    所以这里直接发 ${7*7}，断言响应里出现 49。这是唯一能证明靶场有效的判据。
    """
    import urllib.error
    import urllib.request

    url = f"http://127.0.0.1:{port}/jeecg-boot/jmreport/testConnection"
    payload = (
        b'{"dbType":"MYSQL","dbName":"test","url":"jdbc:mysql://127.0.0.1:3306/test",'
        b'"userName":"root","password":"x","connUrl":"jdbc:mysql://127.0.0.1:3306/test?query=${7*7}"}'
    )
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            body = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}（接口异常）"
    except Exception as e:
        return f"不可达: {e}"
    if '"49"' in body or "=49" in body:
        return "模板引擎求值正常（${7*7}→49）"
    return f"未求值（靶场异常）：{body[:80]}"


def probe_ssti_gen(port: int) -> str:
    """对若依代码生成 SSTI 靶场做真实探针：确认 tableName 里的表达式真被求值。

    与 probe_ssti 同理：只检查端口会把「服务起了但模板引擎没接对」当成健康。
    这里直接发 URL 编码的 ${7*7}，断言响应出现 49 且不含原始表达式。
    """
    import urllib.error
    import urllib.request

    url = f"http://127.0.0.1:{port}/tool/gen/preview/1?tableName=sys_user_%24%7B7*7%7D"
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            body = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}（接口异常）"
    except Exception as e:
        return f"不可达: {e}"
    if "7*7" in body:
        return f"未求值（表达式被原样回显）：{body[:60]}"
    if "sys_user_49" in body or '"49"' in body:
        return "模板引擎求值正常（tableName ${7*7}→49）"
    return f"未求值（靶场异常）：{body[:80]}"


def probe_ssti_thymeleaf(port: int) -> str:
    """对 Thymeleaf/SpEL 视图名注入靶场做探针：确认 __${}__ 真被求值。

    断言两件事：响应出现求值结果 49，且带 org.thymeleaf 引擎异常特征。
    只有 49 不算 —— 普通页面也可能碰巧有 49（插件判定也是这个逻辑）。
    """
    import urllib.error
    import urllib.request

    url = f"http://127.0.0.1:{port}/__%24%7B7*7%7D__::.x"
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            body = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        # 靶场正常会返回 500 + 含引擎异常的报错页，所以 HTTPError 也要读 body
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            return f"HTTP {e.code}（无法读取响应体）"
    except Exception as e:
        return f"不可达: {e}"

    has_result = "49" in body
    has_engine = "org.thymeleaf" in body or "TemplateProcessingException" in body
    if has_result and has_engine:
        return "SpEL 求值正常（__${7*7}__ → 49 + Thymeleaf 异常特征）"
    if not has_engine:
        return f"缺引擎特征（靶场异常）：{body[:80]}"
    return f"未求值：{body[:80]}"


def probe_minio(port: int) -> str:
    """对 MinIO/S3 靶场做探针：确认 S3 根路径真的返回匿名桶列表。

    只检查端口不够 —— 服务起了但 S3 路由没接对时，根路径会返回 404，
    看起来"健康"其实靶场是坏的。真实判据是「根路径 200 + 含 S3 XML 元素」。
    """
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=8) as r:
            body = r.read().decode("utf-8", "replace")
            code = r.status
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}（匿名列举被拒，安全态）"
    except Exception as e:
        return f"不可达: {e}"
    if code == 200 and "<ListAllMyBucketsResult" in body:
        n = body.count("<Bucket>")
        return f"S3 匿名列举正常（根路径返回 {n} 个桶）"
    return f"未返回桶列表：{body[:80]}"


def probe_http(port: int, path: str = "/") -> str:
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=4) as r:
            return f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}"
    except Exception as e:
        return f"不可达: {e}"


def start_one(name: str) -> bool:
    cfg = C4[name]
    cid, port = cfg["id"], int(cfg["port"])
    pidfile = os.path.join(STATE_DIR, cfg["pidfile"])

    if port_open(port):
        print(f"[SKIP] {cid} {name} 已在 {port}")
        return True

    exe = cfg["exe"]
    if not os.path.exists(exe):
        print(f"[FAIL] {cid} {name} 可执行文件不存在: {exe}")
        print(f"       说明：{cfg['desc']}")
        return False

    os.makedirs(cfg["cwd"], exist_ok=True)
    os.makedirs(STATE_DIR, exist_ok=True)
    log = os.path.join(cfg["cwd"], "run.log")

    env = dict(os.environ)
    env.update(cfg.get("env") or {})
    # 与 launch.py 一致的端口劫持防护
    env.pop("SERVER_PORT", None)
    env.pop("SERVER__PORT", None)

    with open(log, "ab") as f_out:
        proc = subprocess.Popen(
            [exe] + list(cfg["args"]),
            cwd=cfg["cwd"],
            stdin=subprocess.DEVNULL,
            stdout=f_out,
            stderr=f_out,
            env=env,
            close_fds=True,
            creationflags=FLAGS,
        )
    with open(pidfile, "w", encoding="utf-8") as f:
        f.write(str(proc.pid))

    deadline = time.time() + 40
    while time.time() < deadline:
        if port_open(port):
            print(f"[OK] {cid} {name} 启动 pid={proc.pid} port={port}")
            return True
        time.sleep(1)
    print(f"[FAIL] {cid} {name} 端口 {port} 未监听；日志 {log}")
    return False


def stop_one(name: str) -> bool:
    cfg = C4[name]
    cid, port = cfg["id"], int(cfg["port"])
    pidfile = os.path.join(STATE_DIR, cfg["pidfile"])
    pid = read_pid(pidfile)
    if not pid or not pid_alive(pid):
        print(f"[SKIP] {cid} {name} 未运行")
        try:
            os.remove(pidfile)
        except OSError:
            pass
        return True
    subprocess.call(["taskkill", "/PID", str(pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(20):
        if not port_open(port):
            break
        time.sleep(0.5)
    try:
        os.remove(pidfile)
    except OSError:
        pass
    print(f"[OK] {cid} {name} 已停止")
    return True


def status_one(name: str) -> dict:
    cfg = C4[name]
    cid, port = cfg["id"], int(cfg["port"])
    pid = read_pid(os.path.join(STATE_DIR, cfg["pidfile"]))
    up = port_open(port)
    if not up:
        return {"id": cid, "name": name, "state": "DOWN", "detail": f"端口 {port} 未监听", "pid": pid}
    if cfg["probe"] == "redis":
        detail = probe_redis(port)
    elif cfg["probe"] == "ssti":
        detail = probe_ssti(port)
    elif cfg["probe"] == "ssti_gen":
        detail = probe_ssti_gen(port)
    elif cfg["probe"] == "ssti_thymeleaf":
        detail = probe_ssti_thymeleaf(port)
    elif cfg["probe"] == "minio_s3":
        detail = probe_minio(port)
    else:
        detail = probe_http(port)
    return {"id": cid, "name": name, "state": "UP", "detail": f"{port} · {detail}", "pid": pid}


def resolve(names: list[str]) -> list[str]:
    if not names:
        return ALL
    out = []
    for raw in names:
        key = raw.lower()
        if key in C4:
            out.append(key)
        elif key.startswith("c4-"):
            for k, v in C4.items():
                if v["id"].lower() == key:
                    out.append(k)
                    break
            else:
                print(f"[ERROR] 未知组件: {raw}")
                return ALL
        else:
            print(f"[ERROR] 未知组件: {raw}（可用: {', '.join(ALL)}）")
            return ALL
    return out


# name -> (源码目录, jar 文件名, runtime 子目录)
BUILDABLE = {
    "rocketmq": ("rocketmq-dashboard", "c4-rocketmq-dashboard-1.0.0.jar", "rocketmq"),
    "jmreport": ("jmreport-ssti", "c4-jmreport-ssti-1.0.0.jar", "jmreport"),
    "gen": ("ruoyi-gen-ssti", "c4-ruoyi-gen-ssti-1.0.0.jar", "gen"),
    "thymeleaf": ("thymeleaf-ssti", "c4-thymeleaf-ssti-1.0.0.jar", "thymeleaf"),
}


def build(name: str) -> bool:
    """重新构建 C4 靶场的 jar（Maven 产物不入库，只能现 build）。"""
    if name not in BUILDABLE:
        print(f"[SKIP] {name} 不需要构建（无源码）")
        return True
    src_name, jar_name, rt_name = BUILDABLE[name]
    src_dir = os.path.join(ROOT, "src", "C4", src_name)
    if not os.path.isdir(src_dir):
        print(f"[FAIL] 源码目录不存在: {src_dir}")
        return False
    mvn = os.path.join(ROOT, "mvn.cmd")
    if not os.path.exists(mvn):
        print(f"[FAIL] 找不到 {mvn}")
        return False
    print(f"[..] 构建 {name}（mvn package）")
    rc = subprocess.call([mvn, "-q", "-DskipTests", "package"], cwd=src_dir)
    if rc != 0:
        print(f"[FAIL] Maven 构建失败 rc={rc}")
        return False
    import shutil

    src_jar = os.path.join(src_dir, "target", jar_name)
    if not os.path.exists(src_jar):
        print(f"[FAIL] 构建成功但找不到产物: {src_jar}")
        return False
    dst_dir = os.path.join(ROOT, "runtime", "C4", rt_name)
    os.makedirs(dst_dir, exist_ok=True)
    shutil.copy2(src_jar, os.path.join(dst_dir, jar_name))
    print(f"[OK] 已复制到 runtime/C4/{rt_name}/")
    return True


def main() -> int:
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return 2
    sub, names = argv[0].lower(), argv[1:]
    targets = resolve(names)

    if sub == "build":
        return 0 if all(build(n) for n in targets) else 1

    if sub == "start":
        failed = [n for n in targets if not start_one(n)]
        if failed:
            print(f"[FAIL] {', '.join(failed)}")
            return 1
        return 0
    if sub == "stop":
        for n in targets:
            stop_one(n)
        return 0
    if sub == "status":
        rows = [status_one(n) for n in targets]
        width = 8
        print()
        print(f"{'编号':<{width}} {'组件':<10} {'状态':<6} 明细")
        print("-" * 70)
        for r in rows:
            print(f"{r['id']:<{width}} {r['name']:<10} {r['state']:<6} {r['detail']}")
        print("-" * 70)
        return 0 if all(r["state"] == "UP" for r in rows) else 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
