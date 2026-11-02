r"""站点后端启动器。

用 Python subprocess 启动 jar 而不是 bat 的 `start /B`：
`start /B`（以及 PowerShell 的 Start-Process）会让 java 继承父进程的标准句柄，
bat 本身执行完毕但调用方的管道始终不关闭，实测一次 4 站点循环会挂住 15 分钟以上。
Python 的 subprocess 默认 close_fds=True，句柄不继承，调用方能立刻拿到退出码。

用法：python scripts\launch.py R4
      python scripts\launch.py R10 --lab.mode=vuln   # R10 漏洞演示模式（透传 Spring 参数）

R10（JeecgBoot）支持两套运行模式，默认 safe：
  - safe：保持 JeecgBoot 3.6.3 官方已修复行为（默认）
  - vuln：开启「漏洞演示模块」的 8 个历史漏洞端点
    开启方式（二选一，优先级：命令行参数 > 环境变量）：
      python scripts\launch.py R10 --lab.mode=vuln
      set LAB_MODE=vuln && python scripts\launch.py R10
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 外部依赖路径统一由 labenv 解析（环境变量 LAB_* > lab.local.json > 默认值）
from labenv import JDK8_HOME, JDK17_HOME  # noqa: E402

# site -> (port, jdk_home)
SITES = {
    "R1": (19201, JDK8_HOME),
    "R2": (19202, JDK8_HOME),
    "R3": (19203, JDK8_HOME),
    "R4": (19204, JDK8_HOME),
    # R5 用 JDK17（4.8.3 起要求 Java 8+，但本机以 17 编译运行）
    "R5": (19205, JDK17_HOME),
    # RuoYi-Vue v3.9.2 的 tag 已于 2026-03-26 被若依重新发布到 Spring Boot 4.0.3，
    # 编译与运行都需要 JDK 17（不再是 2023 年的 Spring Boot 2.5 + JDK 8）
    "R6": (19206, JDK17_HOME),
    # R7 tag v3.8.9 是 2024-12-30 的原版（Spring Boot 2.5.15 / Java 8），不是 2026 重发布版，用 JDK8
    "R7": (19207, JDK8_HOME),
    "R8": (19208, JDK17_HOME),
    "R9": (19209, JDK17_HOME),
    "R10": (19210, JDK8_HOME),
    "R11": (19211, JDK17_HOME),
}

# 各站点产物名不同（R9 Plus / R10 JeecgBoot / R11 自建 Spring Boot）
JARS = {
    "R9": "ruoyi-admin.jar",
    "R10": "jeecg-system-start-3.6.3.jar",
    "R11": "internal-api.jar",
}
# R9 是 Plus 单机版，配置在 application-dev.yml；R10 是 JeecgBoot dev；R11 无 profile 需求
PROFILES = {"R9": "dev", "R10": "dev", "R11": ""}
# 内存偏紧：R9/R10 限堆，R11 是小服务
JAVA_OPTS = {"R9": ["-Xmx768m"], "R10": ["-Xmx768m"], "R11": ["-Xmx256m"]}


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: launch.py <site>")
        return 1
    site = sys.argv[1].upper()
    if site not in SITES:
        print("[ERROR] unknown site: %s" % site)
        return 1

    # 额外 Spring 参数透传（如 --lab.mode=vuln），也支持用 LAB_MODE 环境变量给 R10 切模式
    extra_args = sys.argv[2:]
    lab_mode = (os.environ.get("LAB_MODE") or "").strip().lower()
    if lab_mode and lab_mode not in ("safe", "vuln"):
        print("[ERROR] LAB_MODE 只能是 safe 或 vuln，实际: %s" % lab_mode)
        return 1

    if site == "R8":
        # R8 是 RuoYi-Cloud 微服务站点：后端不是一个 jar，而是 Nacos（注册/配置中心）
        # + gateway/auth/system/gen/job/file 六个 Spring Cloud 服务，由 start_r8_cloud.py 统一拉起。
        # （站点清单：微服务，Nacos 8848 + gateway 19208 + 5 个模块服务）
        cloud = os.path.join(ROOT, "scripts", "start_r8_cloud.py")
        return subprocess.call([sys.executable, cloud, "start"])

    port, jdk = SITES[site]
    jar = os.path.join(ROOT, "build", site, JARS.get(site, "ruoyi-admin.jar"))
    rundir = os.path.join(ROOT, "runtime", site)
    if not os.path.exists(jar):
        print("[ERROR] jar not found: %s" % jar)
        return 1
    for d in (rundir, os.path.join(rundir, "profile"), os.path.join(rundir, "logs")):
        os.makedirs(d, exist_ok=True)

    log = os.path.join(rundir, "run.log")
    err = os.path.join(rundir, "run.err.log")
    java = os.path.join(jdk, "bin", "java.exe")

    # 启动前截断 run.log：这里是 **stdout 全量重定向**，没有 logback 的滚动策略保护。
    # 实测 R1 累积到 649MB、R5 到 336MB —— 若依 4.5.1 的 Druid statViewServlet 在
    # login-username 为空时（官方默认配置）每个 /druid/* 请求都抛 NullPointerException，
    # 单次目录扫描能打出 8 万个栈。日志撑爆磁盘还会把真问题淹没。
    # 保留上一轮为 run.log.prev，方便回溯"上次为什么崩"，但不无限累积。
    if os.path.exists(log) and os.path.getsize(log) > 0:
        prev = log + ".prev"
        try:
            os.replace(log, prev)
        except OSError:
            pass  # 进程还占着句柄时删不掉，直接清空即可
    with open(log, "wb"):
        pass

    env = dict(os.environ)
    env["JAVA_HOME"] = jdk
    env["PATH"] = os.path.join(jdk, "bin") + os.pathsep + env.get("PATH", "")
    # 清除而不是置空：SERVER_PORT="" 不是「未设置」，Spring Boot 的 relaxed binding
    # 会把它当成有效值，server.port 转换 Integer 失败后静默回落默认 8080。
    env.pop("SERVER__PORT", None)
    env.pop("SERVER_PORT", None)

    flags = 0
    flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    flags |= getattr(subprocess, "DETACHED_PROCESS", 0)

    cmd = [java]
    cmd.extend(JAVA_OPTS.get(site, []))
    cmd.extend(["-jar", jar])
    cmd.append("--server.port=%d" % port)
    profile = PROFILES.get(site, "druid,prod")
    if profile:
        cmd.append("--spring.profiles.active=%s" % profile)
    # 单机版若依的 ruoyi.profile 默认是相对路径 ./profile；Tomcat 的
    # MultipartFile.transferTo(相对路径) 会按容器临时目录解析，上传目标目录不存在时
    # 直接 500（2026-11-02 R2 实测：FileNotFoundException ...tomcat.19202.xxx/work/...）。
    # 启动时显式传绝对路径，使上传/下载目录固定落在 runtime/<site>/profile。
    if site != "R8":
        cmd.append("--ruoyi.profile=%s" % os.path.join(rundir, "profile").replace(os.sep, "/"))
    # R10 漏洞演示模式：--lab.mode 既等价于 -Dlab.mode，走 Spring 环境属性，默认 safe
    if site == "R10" and lab_mode:
        cmd.append("--lab.mode=%s" % lab_mode)
    # R9（RuoYi-Vue-Plus）误配模式（v1.5.6 WP3）：
    #   safe（默认）= 生产规范配置，/monitor/** 在 Sa-Token 拦截范围内 → 插件判 SAFE 正确
    #   vuln        = 真实误配现场：把 /monitor/** 加进 security.excludes 白名单，
    #                 未登录即可访问定时任务管理接口
    #
    # 用环境变量注入 spring 配置（等价于运维在 application.yml 里写错），不改源码——
    # 「误配」本来就该以配置形态出现，改源码就成了另一个漏洞。
    #
    # 为什么不用 --security.excludes[9]=... ：该属性绑定为 String[]，
    # 命令行索引形式实测被拒（APPLICATION FAILED TO START: elements were left unbound）。
    # 而 --security.excludes=/monitor/** 会**整体替换**掉原有 8 条排除项，
    # 把静态资源也一起放开，靶场形态跑偏。
    # SPRING_APPLICATION_JSON 的数组是追加语义，只多一条 /monitor/**，其余不变。
    if site == "R9" and lab_mode == "vuln":
        env["SPRING_APPLICATION_JSON"] = '{"security":{"excludes":["/monitor/**"]}}'
    cmd.extend(extra_args)

    with open(log, "ab") as f_out, open(err, "ab") as f_err:
        proc = subprocess.Popen(
            cmd,
            cwd=rundir,
            stdin=subprocess.DEVNULL,
            stdout=f_out,
            stderr=f_err,
            env=env,
            close_fds=True,
            creationflags=flags,
        )

    pidfile = os.path.join(ROOT, ".state", "%s.pid" % site)
    os.makedirs(os.path.dirname(pidfile), exist_ok=True)
    with open(pidfile, "w") as f:
        f.write(str(proc.pid))
    # R9 用同一个 --lab-mode 开关，提示里也要标出来，否则运维看不出当前是误配版
    mode_site = site in ("R10", "R9")
    mode_note = (" lab.mode=%s" % lab_mode) if (mode_site and lab_mode) else ""
    print("[OK] %s launched pid=%s port=%s%s" % (site, proc.pid, port, mode_note))
    print("[OK] logs: %s / %s" % (log, err))
    return 0


if __name__ == "__main__":
    sys.exit(main())
