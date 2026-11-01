r"""R8 智谷园区运营平台（RuoYi-Cloud v3.6.8）微服务一键启动器。

R8 与 R1~R7 的区别：
  * 后端不是一个 ruoyi-admin.jar，而是 6 个 Spring Cloud 服务：
    gateway(19208) / auth(9200) / system(9201) / gen(9202) / job(9203) / file(9300)
  * 依赖 Nacos 8848(+9848 gRPC) 做注册中心 + 配置中心（官方 compose 用 nacos/nacos-server:v3.0.2，
    控制台在 8080，8848 只做 API）；配置不在本地 yml，
    而在 Nacos 配置库 ry_config（MySQL 127.0.0.1:13307）里。
  * 启动顺序：MySQL(13307) -> Nacos(8848) -> 各微服务注册 -> gateway。
  * gateway 的官方 bootstrap.yml 写死 8080，启动时用 --server.port=19208 覆盖，
    不改官方源码 yml（官方部署方式也是改 Nacos 外部配置/启动参数）。

用法：
  python scripts\start_r8_cloud.py start        # Nacos + 6 服务，等就绪，写 .state\R8.pid
  python scripts\start_r8_cloud.py stop         # 停全部（含 Nacos 容器/进程）
  python scripts\start_r8_cloud.py status       # 查看状态
  python scripts\start_r8_cloud.py _supervise   # 内部：守护进程（不要手动调）

守护进程用 Windows Job Object（KILL_ON_JOB_CLOSE）持有所有 java 子进程：
04_stop.bat 杀掉 .state\R8.supervisor.pid 时，job 句柄关闭，6 个服务一并退出。
"""
import ctypes
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(ROOT, ".state")
RUN_DIR = os.path.join(ROOT, "runtime", "R8")
LOG_DIR = os.path.join(RUN_DIR, "logs")
BUILD_DIR = os.path.join(ROOT, "build", "R8")
TOOLS_DIR = os.path.join(ROOT, "tools")

JDK17_HOME = r"D:\develop\jdk-17.0.0.1"
JDK8_HOME = r"D:\develop\java-se-8u44-ri"
JAVA17 = os.path.join(JDK17_HOME, "bin", "java.exe")
JAVA8 = os.path.join(JDK8_HOME, "bin", "java.exe")

NACOS_CONTAINER = "nacos-ruoyi-r8"
# 官方 tag v3.6.8（2026-03-30 重发）的 docker/docker-compose.yml 指定 nacos/nacos-server:v3.0.2，
# 对应 JDK17 / Spring Boot 4.0.3 / SCA 2025.1.0.0（nacos-client 3.1.1）。Nacos 3.x 控制台在 8080，8848 只做 API。
NACOS_IMAGE = "nacos/nacos-server:v3.0.2"
NACOS_HOME = os.path.join(TOOLS_DIR, "nacos")
NACOS_ZIP_CANDIDATES = [
    os.path.join(TOOLS_DIR, "nacos-server-3.0.2.zip"),
    r"C:\temp\nacosdl3\nacos-server-3.0.2.zip",
]

SUPERVISOR_PID = os.path.join(STATE_DIR, "R8.supervisor.pid")
STATUS_FILE = os.path.join(STATE_DIR, "R8.status.json")
SITE_PID = os.path.join(STATE_DIR, "R8.pid")

GATEWAY_PORT = 19208

# (service name, jar 文件名, 端口, 额外启动参数)
SERVICES = [
    ("ruoyi-auth", "ruoyi-auth.jar", 9200, []),
    ("ruoyi-modules-system", "ruoyi-modules-system.jar", 9201, []),
    ("ruoyi-modules-gen", "ruoyi-modules-gen.jar", 9202, []),
    ("ruoyi-modules-job", "ruoyi-modules-job.jar", 9203, []),
    ("ruoyi-modules-file", "ruoyi-modules-file.jar", 9300, []),
    ("ruoyi-gateway", "ruoyi-gateway.jar", GATEWAY_PORT, ["--server.port=%d" % GATEWAY_PORT]),
]

# 本机空闲内存偏紧（宿主 16G，多个靶场进程常驻），给每个 JVM 限堆，避免互相踩踏。
JVM_ARGS = {
    "ruoyi-auth":            ["-Xms128m", "-Xmx384m", "-XX:MaxMetaspaceSize=192m"],
    "ruoyi-modules-system":  ["-Xms192m", "-Xmx512m", "-XX:MaxMetaspaceSize=224m"],
    "ruoyi-modules-gen":     ["-Xms128m", "-Xmx384m", "-XX:MaxMetaspaceSize=192m"],
    "ruoyi-modules-job":     ["-Xms128m", "-Xmx384m", "-XX:MaxMetaspaceSize=192m"],
    "ruoyi-modules-file":    ["-Xms128m", "-Xmx384m", "-XX:MaxMetaspaceSize=192m"],
    "ruoyi-gateway":         ["-Xms128m", "-Xmx448m", "-XX:MaxMetaspaceSize=224m"],
}

DETACHED = 0
DETACHED |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
DETACHED |= getattr(subprocess, "DETACHED_PROCESS", 0)


# ---------------------------------------------------------------- 基础工具
def log(msg):
    print("[%s] %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg), flush=True)


def ensure_dirs():
    for d in (STATE_DIR, RUN_DIR, LOG_DIR, os.path.join(RUN_DIR, "profile"), os.path.join(RUN_DIR, "uploadPath")):
        os.makedirs(d, exist_ok=True)


def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def write_text(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return ""


def pid_alive(pid):
    try:
        pid = int(pid)
    except Exception:
        return False
    if pid <= 0:
        return False
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return False
    k32.CloseHandle(h)
    return True


def port_open(port, host="127.0.0.1", timeout=0.5):
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except Exception:
        return False


def http_status(url, timeout=3):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "r8-startup-probe"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode()
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return None


def wait_port(port, timeout=120, label=None):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_open(port):
            return True
        time.sleep(1)
    return False


def kill_pid(pid, tree=True):
    if not pid_alive(pid):
        return
    # 注意参数顺序：taskkill /PID <pid> /T /F（/T 必须放在 PID 值之后，否则 taskkill 直接报用法错误）
    cmd = ["taskkill", "/PID", str(pid), "/T", "/F"] if tree else ["taskkill", "/PID", str(pid), "/F"]
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def docker_run(args, timeout=120):
    try:
        return subprocess.run(["docker"] + args, capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        return None


def docker_available():
    r = docker_run(["version", "--format", "{{.Server.Version}}"], timeout=20)
    return bool(r and r.returncode == 0)


def docker_image_exists(image):
    r = docker_run(["image", "inspect", image], timeout=20)
    return bool(r and r.returncode == 0)


def docker_container_exists(name):
    r = docker_run(["container", "inspect", name], timeout=20)
    return bool(r and r.returncode == 0)


# ---------------------------------------------------------------- Nacos
def nacos_ready():
    if not port_open(8848):
        return False
    # Nacos 3.x：8848 只做 HTTP API（控制台独立在 8080）；v1/console/health/readiness 已返回 410，
    # 用命名服务列表 API 探活（匿名可访问，200 即 API 就绪）。
    if http_status("http://127.0.0.1:8848/nacos/v1/ns/service/list?pageNo=1&pageSize=1") == 200:
        return True
    return http_status("http://127.0.0.1:8080/") == 200


def wait_nacos(timeout=180):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if nacos_ready():
            return True
        time.sleep(2)
    return False


def ensure_nacos():
    """返回 Nacos 启动方式描述；失败抛 RuntimeError。8848 已被占用则直接复用。"""
    if port_open(8848):
        if wait_nacos(60):
            log("Nacos 已在监听 8848，直接复用（控制台 http://127.0.0.1:8080/）")
            return "existing"
        raise RuntimeError("8848 端口被占用但 HTTP 不是可用的 Nacos 控制台")
    if docker_available() and docker_image_exists(NACOS_IMAGE):
        return start_nacos_docker()
    if ensure_nacos_zip():
        return start_nacos_zip()
    raise RuntimeError(
        "没有可用的 Nacos：docker 镜像 %s 不存在，且找不到 nacos-server-2.2.3.zip / 解压目录 %s"
        % (NACOS_IMAGE, NACOS_HOME)
    )


def start_nacos_docker():
    if docker_container_exists(NACOS_CONTAINER):
        log("docker 容器 %s 已存在，启动它" % NACOS_CONTAINER)
        docker_run(["start", NACOS_CONTAINER], timeout=60)
    else:
        log("docker run %s" % NACOS_IMAGE)
        db_param = (
            "characterEncoding=utf8&connectTimeout=1000&socketTimeout=3000&autoReconnect=true"
            "&useUnicode=true&useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true"
        )
        args = [
            "run", "-d", "--name", NACOS_CONTAINER,
            "-e", "MODE=standalone",
            "-e", "SPRING_DATASOURCE_PLATFORM=mysql",
            "-e", "MYSQL_SERVICE_HOST=host.docker.internal",
            "-e", "MYSQL_SERVICE_PORT=13307",
            "-e", "MYSQL_SERVICE_DB_NAME=ry_config",
            "-e", "MYSQL_SERVICE_USER=root",
            "-e", "MYSQL_SERVICE_PASSWORD=",
            "-e", "MYSQL_SERVICE_DB_PARAM=" + db_param,
            "-e", "NACOS_AUTH_ENABLE=false",
            # Nacos 3.0.2 镜像 entrypoint 强制要求这三个 env 非空（否则 exit 255），
            # 值取 Nacos 官方默认（conf/application.properties 里注释的默认 token + 默认 identity），
            # 与官方 compose 的用法一致；auth 本身未启用（历史状态：Nacos 无鉴权）。
            "-e", "NACOS_AUTH_TOKEN=VGhpc0lzTXlDdXN0b21TZWNyZXRLZXkwMTIzNDU2Nzg=",
            "-e", "NACOS_AUTH_IDENTITY_KEY=serverIdentity",
            "-e", "NACOS_AUTH_IDENTITY_VALUE=security",
            "-e", "JVM_XMS=512m", "-e", "JVM_XMX=768m", "-e", "JVM_XMN=256m",
            # Nacos 3.x：8848=HTTP API，9848/9849=gRPC，8080=独立控制台
            "-p", "8848:8848", "-p", "9848:9848", "-p", "9849:9849", "-p", "8080:8080",
            NACOS_IMAGE,
        ]
        r = docker_run(args, timeout=180)
        if not r or r.returncode != 0:
            raise RuntimeError("docker run Nacos 失败: %s" % ((r.stderr or r.stdout) if r else "docker 不可用"))
    if not wait_nacos(240):
        tail = ""
        r = docker_run(["logs", "--tail", "80", NACOS_CONTAINER], timeout=30)
        if r:
            tail = (r.stdout or "") + (r.stderr or "")
        raise RuntimeError("Nacos 容器启动后 8848 未就绪。docker logs 末尾:\n" + tail[-4000:])
    log("Nacos(docker) 已就绪: 控制台 http://127.0.0.1:8080/  API http://127.0.0.1:8848/nacos/")
    return "docker"


def ensure_nacos_zip():
    if os.path.isfile(os.path.join(NACOS_HOME, "bin", "startup.cmd")):
        return True
    for z in NACOS_ZIP_CANDIDATES:
        try:
            if os.path.isfile(z) and os.path.getsize(z) > 100 * 1024 * 1024:
                log("解压 %s -> %s" % (z, TOOLS_DIR))
                os.makedirs(TOOLS_DIR, exist_ok=True)
                with zipfile.ZipFile(z) as zf:
                    zf.extractall(TOOLS_DIR)
                if os.path.isfile(os.path.join(NACOS_HOME, "bin", "startup.cmd")):
                    return True
        except Exception as e:
            log("解压 %s 失败: %s" % (z, e))
    return False


def patch_nacos_properties():
    conf = os.path.join(NACOS_HOME, "conf", "application.properties")
    marker = "# ---- R8 lab override (start_r8_cloud.py) ----"
    content = read_text(conf)
    if marker in content:
        return
    # Nacos 3.0.2 的配置键与 2.x 不同：
    #   * 数据库开关是 spring.sql.init.platform=mysql（不是 spring.datasource.platform）
    #   * 主端口是 nacos.server.main.port（默认 8848），控制台是独立端口 nacos.console.port（默认 8080）
    #   * startup.cmd 会对三个 auth required key 做交互式补全（值为空时会 set /p 卡住），
    #     所以必须显式写入 Nacos 的官方默认值（Docker 镜像默认值相同），既避免卡住也保持"默认 secret"这一历史状态。
    default_secret = "SecretKey012345678901234567890123456789012345678901234567890123456789"
    block = "\n".join([
        "",
        marker,
        "spring.sql.init.platform=mysql",
        "db.num=1",
        "db.url.0=jdbc:mysql://127.0.0.1:13307/ry_config?characterEncoding=utf8&connectTimeout=1000&socketTimeout=3000&autoReconnect=true&useUnicode=true&useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true",
        "db.user=root",
        "db.password=",
        "nacos.server.main.port=8848",
        "nacos.console.port=8080",
        "nacos.core.auth.enabled=false",
        "nacos.core.auth.server.identity.key=serverIdentity",
        "nacos.core.auth.server.identity.value=security",
        "nacos.core.auth.plugin.nacos.token.secret.key=" + default_secret,
        "nacos.core.auth.default.token.secret.key=" + default_secret,
        "",
    ])
    with open(conf, "a", encoding="utf-8") as f:
        f.write(block)


def start_nacos_zip():
    if not os.path.isfile(JAVA17):
        raise RuntimeError("找不到 JDK17: %s（Nacos 3.x 需要 JDK17）" % JAVA17)
    patch_nacos_properties()
    out = open(os.path.join(LOG_DIR, "nacos.out.log"), "ab")
    err = open(os.path.join(LOG_DIR, "nacos.err.log"), "ab")
    # 必须复用 build_env()：宿主可能带 SERVER__PORT（Spring relaxed binding 会当成
    # server.port），Nacos 3.x 控制台端口会被劫持到随机端口并 PortInUse。
    env = build_env()
    cmd = ["cmd.exe", "/c", os.path.join(NACOS_HOME, "bin", "startup.cmd"), "-m", "standalone"]
    proc = subprocess.Popen(
        cmd, cwd=os.path.join(NACOS_HOME, "bin"), stdin=subprocess.DEVNULL,
        stdout=out, stderr=err, close_fds=True, env=env, creationflags=DETACHED,
    )
    st = read_json(STATUS_FILE)
    st["nacos_mode"] = "zip"
    st["nacos_pid"] = proc.pid
    write_json(STATUS_FILE, st)
    log("Nacos(zip) 启动中 pid=%s，等待 8848 ..." % proc.pid)
    if not wait_nacos(240):
        raise RuntimeError("Nacos(zip) 启动后 8848 未就绪，见 runtime\\R8\\logs\\nacos.out.log / %s\\logs" % NACOS_HOME)
    log("Nacos(zip) 已就绪: 控制台 http://127.0.0.1:8080/  API http://127.0.0.1:8848/nacos/")
    return "zip"


# ---------------------------------------------------------------- Job Object
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JobObjectExtendedLimitInformation = 9


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", ctypes.c_uint32),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", ctypes.c_uint32),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", ctypes.c_uint32),
        ("SchedulingClass", ctypes.c_uint32),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def create_kill_on_close_job():
    try:
        k32 = ctypes.windll.kernel32
        job = k32.CreateJobObjectW(None, None)
        if not job:
            return None
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ok = k32.SetInformationJobObject(job, JobObjectExtendedLimitInformation,
                                         ctypes.byref(info), ctypes.sizeof(info))
        if not ok:
            return None
        return job
    except Exception:
        return None


def assign_to_job(job, proc):
    if not job:
        return False
    try:
        return bool(ctypes.windll.kernel32.AssignProcessToJobObject(job, int(proc._handle)))
    except Exception:
        return False


# ---------------------------------------------------------------- 子进程启动
def build_env():
    env = os.environ.copy()
    env["JAVA_HOME"] = JDK17_HOME
    env["PATH"] = os.path.join(JDK17_HOME, "bin") + os.pathsep + env.get("PATH", "")
    # 清除而不是置空：SERVER_PORT="" 会被 Spring Boot 当作有效值，Integer 转换失败回落 8080
    env.pop("SERVER_PORT", None)
    env.pop("SERVER__PORT", None)
    env.pop("SPRING_PROFILES_ACTIVE", None)
    return env


def spawn_service(name, jar_name, extra, log_dir):
    jar = os.path.join(BUILD_DIR, jar_name)
    if not os.path.isfile(jar):
        raise RuntimeError("jar 不存在: %s（先跑 scripts\\01_build_R8.bat）" % jar)
    out = open(os.path.join(log_dir, name + ".log"), "ab")
    err = open(os.path.join(log_dir, name + ".err.log"), "ab")
    cmd = [JAVA17] + JVM_ARGS.get(name, []) + [
        "-Dfile.encoding=UTF-8", "-jar", jar, "--spring.profiles.active=dev",
    ] + extra
    proc = subprocess.Popen(
        cmd, cwd=RUN_DIR, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
        close_fds=True, env=build_env(), creationflags=DETACHED,
    )
    return proc


# ---------------------------------------------------------------- 守护进程
def cmd_supervise():
    ensure_dirs()
    status = {
        "supervisor_pid": os.getpid(),
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pids": {},
        "started": [],
        "ready": [],
        "failed": {},
        "gateway_ready": False,
    }
    write_json(STATUS_FILE, status)
    job = create_kill_on_close_job()
    job_ok = job is not None
    procs = {}

    for name, jar_name, port, extra in SERVICES:
        if port_open(port):
            status["failed"][name] = "端口 %d 已被其它进程占用" % port
            write_json(STATUS_FILE, status)
            continue
        try:
            proc = spawn_service(name, jar_name, extra, LOG_DIR)
        except Exception as e:
            status["failed"][name] = str(e)
            write_json(STATUS_FILE, status)
            continue
        assign_to_job(job, proc)
        procs[name] = proc
        status["pids"][name] = proc.pid
        status["started"].append(name)
        write_json(STATUS_FILE, status)
        log("启动 %s pid=%s port=%d" % (name, proc.pid, port))
        time.sleep(2)  # 错开 2 秒，避免 6 个 JVM 同时抢内存

    ports = {name: port for name, _jar, port, _extra in SERVICES}
    pending = set(status["started"])
    deadline = time.time() + 300
    while pending and time.time() < deadline:
        for name in list(pending):
            if port_open(ports[name]):
                pending.discard(name)
                if name not in status["ready"]:
                    status["ready"].append(name)
                write_json(STATUS_FILE, status)
                log("就绪 %s(port=%d)" % (name, ports[name]))
        if not pending:
            break
        time.sleep(2)
    for name in pending:
        status["failed"][name] = "300 秒内端口 %d 未监听" % ports[name]
    status["gateway_ready"] = port_open(GATEWAY_PORT)
    status["job_object"] = job_ok
    write_json(STATUS_FILE, status)
    log("守护进程就绪检查完成: ready=%s failed=%s" % (status["ready"], status["failed"]))

    # 常驻：持有 job 句柄；被 04_stop.bat/stop 杀掉时句柄关闭，子进程全部退出。
    while True:
        time.sleep(5)
        alive = {name: pid_alive(p.pid) for name, p in procs.items()}
        if not any(alive.values()) and not port_open(GATEWAY_PORT):
            log("所有子进程已退出，守护进程结束")
            return 0


# ---------------------------------------------------------------- 内存预检
def available_memory_mb():
    """当前可用物理内存（MB）。优先 psutil，失败时用 GlobalMemoryStatusEx。"""
    try:
        import psutil

        return int(psutil.virtual_memory().available / (1024 * 1024))
    except Exception:
        pass
    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        state = MEMORYSTATUSEX()
        state.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state))
        return int(state.ullAvailPhys / (1024 * 1024))
    except Exception:
        return 0


def _pid_site_map():
    """把 .state/*.pid 映射成站点名，供低内存提示使用（绝不据此杀进程）。"""
    mapping = {}
    try:
        names = os.listdir(STATE_DIR)
    except OSError:
        return mapping
    for name in names:
        if not name.endswith(".pid"):
            continue
        site = name[:-4]
        try:
            with open(os.path.join(STATE_DIR, name), "r", encoding="utf-8") as f:
                pid = int(f.read().strip())
            mapping[pid] = site
        except Exception:
            continue
    return mapping


def top_java_processes(limit=8):
    """返回 RSS 最高的 java 进程 [(pid, rss_mb, site, is_lab)]；仅用于提示。

    is_lab 区分「靶场进程」与「外部 java」（VS Code 语言服务器 / IDEA / 其他服务）。
    这个区分很重要：预检失败时如果只笼统说「内存不足」，用户会去停靶场，
    而真正的大户可能是 IDE —— 实测本机 VS Code Java 语言服务器常驻 1.2GB，
    比任何一个靶场站点都大。
    """
    try:
        import psutil
    except Exception:
        return []
    sites = _pid_site_map()
    rows = []
    for proc in psutil.process_iter(["pid", "name", "memory_info", "cmdline"]):
        try:
            name = (proc.info.get("name") or "").lower()
            if "java" not in name:
                continue
            rss = proc.info["memory_info"].rss / (1024 * 1024)
            pid = proc.info["pid"]
            site = sites.get(pid, "")
            if not site:
                # 没在 .state/*.pid 里 → 不是由靶场脚本拉起的
                cmd = " ".join(proc.info.get("cmdline") or [])[:200].lower()
                site = "外部 java（非靶场）" if "ruoyi" not in cmd and "c4-" not in cmd else "未登记靶场进程"
            rows.append((pid, rss, site, bool(sites.get(pid))))
        except Exception:
            continue
    rows.sort(key=lambda item: item[1], reverse=True)
    return rows[:limit]


def memory_precheck(required_mb=3200, available_mb=None):
    """内存不足时打印原因并返回 2；不启动、不杀任何进程。

    R8 是 RuoYi-Cloud：Nacos + 6 个 Spring Cloud 服务，共 7 个 JVM。
    堆上限合计 2496MB + Metaspace 1216MB + Nacos 约 512MB ≈ 4.2GB，
    所以它**无法与其他靶场共存**（本机 16GB，典型靶场占用 1.5–2GB）。

    因此 R8 走独占模式：需要时停掉其他站点单独拉起，用完即停。
    """
    required_mb = int(os.environ.get("R8_MIN_FREE_MB", required_mb))
    avail = available_memory_mb() if available_mb is None else int(available_mb)
    if avail >= required_mb:
        return 0
    log("[FAIL] 可用内存 %.1fGB，R8 需要 ≥%.1fGB。" % (avail / 1024.0, required_mb / 1024.0))
    log("       R8 = Nacos + 6 个 Spring Cloud 服务（共 7 个 JVM），约 4.2GB，")
    log("       无法与其他靶场共存。走独占模式：")
    log("         python scripts\\lab.py down site component middleware special")
    log("         python scripts\\start_r8_cloud.py start")
    rows = top_java_processes()
    if rows:
        log("       当前占用最高的 java：")
        log("       PID  RSS(MB)  站点")
        for pid, rss, site, is_lab in rows:
            log("       %-4s %-8.1f %s" % (pid, rss, site))
        lab_mb = sum(r for _p, r, _s, is_lab in rows if is_lab)
        ext_mb = sum(r for _p, r, _s, is_lab in rows if not is_lab)
        if ext_mb > 0:
            log("")
            log("       [提示] 其中有 %.0fMB 是**非靶场 java**（IDE 语言服务器等）。" % ext_mb)
            log("              停靶场腾不出来这部分；需要的话请关掉对应 IDE 窗口。")
            log("              靶场进程合计 %.0fMB。" % lab_mb)
    return 2


# ---------------------------------------------------------------- 命令实现
def cmd_start():
    rc = memory_precheck()
    if rc:
        return rc
    ensure_dirs()
    if not port_open(13307):
        log("[ERROR] MySQL 13307 未监听，先起 MySQL 实例")
        return 1
    st = read_json(STATUS_FILE)
    sup = read_pid_file(SUPERVISOR_PID)
    if port_open(GATEWAY_PORT) and pid_alive(sup):
        log("R8 已在运行（gateway 19208 监听中，supervisor pid=%s）" % sup)
        if st.get("pids", {}).get("ruoyi-gateway"):
            write_text(SITE_PID, str(st["pids"]["ruoyi-gateway"]))
        return 0
    busy = [p for p in (9200, 9201, 9202, 9203, 9300, GATEWAY_PORT) if port_open(p)]
    if busy:
        log("[ERROR] 以下 R8 端口已被占用，拒绝启动: %s" % busy)
        return 1
    try:
        nacos_mode = ensure_nacos()
    except RuntimeError as e:
        log("[ERROR] %s" % e)
        return 1
    log("Nacos 就绪（mode=%s），启动 6 个微服务 ..." % nacos_mode)

    sup_log = open(os.path.join(LOG_DIR, "supervisor.log"), "ab")
    proc = subprocess.Popen(
        [sys.executable, os.path.abspath(__file__), "_supervise"],
        cwd=ROOT, stdin=subprocess.DEVNULL, stdout=sup_log, stderr=subprocess.STDOUT,
        close_fds=True, creationflags=DETACHED,
    )
    write_text(SUPERVISOR_PID, str(proc.pid))
    log("supervisor pid=%s，等待 6 个服务就绪（最多 330 秒）..." % proc.pid)

    deadline = time.time() + 330
    last = {}
    while time.time() < deadline:
        last = read_json(STATUS_FILE)
        if last.get("failed"):
            break
        if last.get("gateway_ready") and len(last.get("ready", [])) >= len(SERVICES):
            gw = last.get("pids", {}).get("ruoyi-gateway")
            if gw:
                write_text(SITE_PID, str(gw))
            log("R8 全部就绪: %s" % last.get("ready"))
            log("gateway pid=%s -> http://127.0.0.1:%d/  (nginx: http://127.0.0.1:19108/)" % (gw, GATEWAY_PORT))
            return 0
        if not pid_alive(proc.pid):
            log("[ERROR] supervisor 提前退出，见 runtime\\R8\\logs\\supervisor.log")
            return 1
        time.sleep(2)

    log("[ERROR] R8 启动失败/超时，status=%s" % json.dumps(last, ensure_ascii=False))
    for name in last.get("failed", {}):
        tail = read_text(os.path.join(LOG_DIR, name + ".log"))[-2500:]
        log("---- %s 日志末尾 ----\n%s" % (name, tail))
    return 1


def cmd_stop():
    ensure_dirs()
    st = read_json(STATUS_FILE)
    sup = read_pid_file(SUPERVISOR_PID)
    stopped = []
    if pid_alive(sup):
        kill_pid(sup, tree=True)
        stopped.append("supervisor(%s)" % sup)
    for name, pid in (st.get("pids") or {}).items():
        if pid_alive(pid):
            kill_pid(pid, tree=True)
            stopped.append("%s(%s)" % (name, pid))
    # 兜底：按已知端口找残留 PID（绝不动其它站点进程：只处理 R8 自己的端口段）
    for port in (9200, 9201, 9202, 9203, 9300, GATEWAY_PORT):
        pid = pid_on_port(port)
        if pid and pid not in stopped:
            kill_pid(pid, tree=True)
            stopped.append("port%d(%s)" % (port, pid))
    # Nacos：优先停本脚本创建的容器，其次 zip 模式 pid
    nacos_stopped = ""
    if docker_container_exists(NACOS_CONTAINER):
        r = docker_run(["stop", NACOS_CONTAINER], timeout=90)
        if r and r.returncode == 0:
            nacos_stopped = "docker:%s" % NACOS_CONTAINER
    elif st.get("nacos_mode") == "zip" and st.get("nacos_pid"):
        kill_pid(st["nacos_pid"], tree=True)
        nacos_stopped = "zip:%s" % st["nacos_pid"]

    for p in (SITE_PID, SUPERVISOR_PID):
        try:
            os.remove(p)
        except OSError:
            pass
    try:
        os.remove(STATUS_FILE)
    except OSError:
        pass

    # 等待端口释放
    deadline = time.time() + 30
    while time.time() < deadline:
        if not any(port_open(p) for p in (9200, 9201, 9202, 9203, 9300, GATEWAY_PORT)):
            break
        time.sleep(1)

    left = [p for p in (9200, 9201, 9202, 9203, 9300, GATEWAY_PORT) if port_open(p)]
    if nacos_stopped:
        log("Nacos 已停止 (%s)" % nacos_stopped)
    log("R8 已停止: %s" % (", ".join(stopped) if stopped else "无运行中进程"))
    if left:
        log("[WARN] 仍有端口在监听: %s" % left)
        return 1
    return 0


def port_pid_map():
    """netstat 解析 端口 -> LISTENING pid（仅本机 IPv4）"""
    result = {}
    try:
        proc = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True, timeout=20)
        out = proc.stdout or ""
    except Exception:
        return result
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[3] != "LISTENING":
            continue
        local = parts[1]
        if ":" not in local:
            continue
        port = local.rsplit(":", 1)[1]
        try:
            result.setdefault(int(port), int(parts[4]))
        except ValueError:
            pass
    return result


def pid_on_port(port):
    return port_pid_map().get(int(port))


def read_pid_file(path):
    try:
        return int(read_text(path).strip())
    except Exception:
        return 0


def cmd_status():
    st = read_json(STATUS_FILE)
    sup = read_pid_file(SUPERVISOR_PID)
    log("R8 智谷园区运营平台（RuoYi-Cloud v3.6.8）")
    log("supervisor pid=%s alive=%s" % (sup, pid_alive(sup)))
    pids = st.get("pids") or {}
    for name, _jar, port, _extra in SERVICES:
        pid = pids.get(name, "")
        log("  %-22s port=%-5d pid=%-7s listening=%-5s ready=%s"
            % (name, port, pid, port_open(port), name in st.get("ready", [])))
    log("  Nacos 8848(API) listening=%s 8080(console)=%s 8848-readiness=%s"
        % (port_open(8848), http_status("http://127.0.0.1:8080/"), http_status("http://127.0.0.1:8848/nacos/v1/console/health/readiness")))
    log("  gateway actuator health=%s" % http_status("http://127.0.0.1:%d/actuator/health" % GATEWAY_PORT))
    if st.get("failed"):
        log("  failed=%s" % st["failed"])
    return 0


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    action = sys.argv[1].lower()
    if action == "start":
        return cmd_start()
    if action == "stop":
        return cmd_stop()
    if action == "status":
        return cmd_status()
    if action == "_supervise":
        return cmd_supervise()
    print("unknown action: %s" % action)
    return 1


if __name__ == "__main__":
    sys.exit(main())
