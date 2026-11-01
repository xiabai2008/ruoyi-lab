r"""站点后端启动器。

用 Python subprocess 启动 jar 而不是 bat 的 `start /B`：
`start /B`（以及 PowerShell 的 Start-Process）会让 java 继承父进程的标准句柄，
bat 本身执行完毕但调用方的管道始终不关闭，实测一次 4 站点循环会挂住 15 分钟以上。
Python 的 subprocess 默认 close_fds=True，句柄不继承，调用方能立刻拿到退出码。

用法：python scripts\launch.py R4
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# site -> (port, jdk_home)
SITES = {
    "R1": (19201, r"D:\develop\java-se-8u44-ri"),
    "R2": (19202, r"D:\develop\java-se-8u44-ri"),
    "R3": (19203, r"D:\develop\java-se-8u44-ri"),
    "R4": (19204, r"D:\develop\java-se-8u44-ri"),
    "R5": (19205, r"D:\develop\jdk-17.0.0.1"),
    # RuoYi-Vue v3.9.2 / v3.8.9 的 tag 已于 2026-03-26 被若依重新发布到 Spring Boot 4.0.3，
    # 编译与运行都需要 JDK 17（不再是 2023 年的 Spring Boot 2.5 + JDK 8）
    "R6": (19206, r"D:\develop\jdk-17.0.0.1"),
    # R7 tag v3.8.9 是 2024-12-30 的原版（Spring Boot 2.5.15 / Java 8），不是 2026 重发布版，用 JDK8
    "R7": (19207, r"D:\develop\java-se-8u44-ri"),
    "R8": (19208, r"D:\develop\jdk-17.0.0.1"),
    "R9": (19209, r"D:\develop\jdk-17.0.0.1"),
    "R10": (19210, r"D:\develop\java-se-8u44-ri"),
    "R11": (19211, r"D:\develop\jdk-17.0.0.1"),
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
    print("[OK] %s launched pid=%s port=%s" % (site, proc.pid, port))
    print("[OK] logs: %s / %s" % (log, err))
    return 0


if __name__ == "__main__":
    sys.exit(main())
