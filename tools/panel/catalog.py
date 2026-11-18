r"""35 个靶场对象的元数据、构建检查与依赖计划。

数据来源分三层：
1. `lab.py` 的 SITES：端口、探针、PID 文件、依赖、R8 独占标记；
2. 本文件的 META：展示名、业务描述、凭据、备注、日志路径；
3. BUILD_CHECKS：真正启动用的 runtime 产物（不是 src/target）。

“构建存在情况”只看 runtime 产物：C2 的 safe 构建会把 target 里的另一份 jar
清掉，但 runtime 下两份都保留；用 src/target 判断会误报“缺 jar”。
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from . import lab_bridge as lb

LAB_ROOT = lb.LAB_ROOT

# UI 分组（与 lab.py 的 GROUPS 不同：component 不包含 C3/C5）
GROUP_ORDER = ["site", "holdout", "component", "middleware", "special", "infra", "extra"]
GROUP_LABELS = {
    "site": "若依站点",
    "holdout": "留出集",
    "component": "组件",
    "middleware": "中间件",
    "special": "特殊形态",
    "infra": "基础设施",
    "extra": "非若依",
}

C1_COMP = {
    "C1-1": "jolokia",
    "C1-2": "h2-console",
    "C1-3": "data-service",
    "C1-4": "config-server",
}
C4_COMP = {
    "C4-1": "redis",
    "C4-2": "minio",
    "C4-3": "rocketmq",
    "C4-4": "jmreport",
    "C4-5": "gen",
    "C4-6": "thymeleaf",
}


@dataclass
class CheckSpec:
    label: str
    kind: str  # file / dir / glob
    path: str = ""
    optional: bool = False
    hint: str = ""


@dataclass
class TargetDef:
    id: str
    name: str
    business: str
    group: str
    entry: int
    backend: int
    url: str | None
    probe: tuple[str, set[int]] | None
    pidfile: str | None
    lifecycle: str
    conf_name: str | None = None
    credentials: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    dependents: list[str] = field(default_factory=list)
    exclusive: bool = False
    pair_id: str | None = None
    cloud: bool = False
    java: str | None = None
    log_paths: list[str] = field(default_factory=list)
    build_checks: list[CheckSpec] = field(default_factory=list)
    source_checks: list[CheckSpec] = field(default_factory=list)
    build_hint: str = ""


# ── 元数据 ──

def _cred(label: str, username: str, password: str = "", note: str = "") -> dict:
    return {"label": label, "username": username, "password": password, "note": note}


def M(
    name: str,
    business: str,
    java: str | None = None,
    creds: list[dict] | None = None,
    notes: list[str] | None = None,
    deps: list[str] | None = None,
    logs: list[str] | None = None,
    hint: str = "",
    exclusive: bool = False,
) -> dict:
    return {
        "name": name,
        "business": business,
        "java": java,
        "creds": creds or [],
        "notes": notes or [],
        "deps": deps or [],
        "logs": logs or [],
        "hint": hint,
        "exclusive": exclusive,
    }


R_COMMON_CREDS = [
    _cred("管理员", "admin", "admin123"),
    _cred("低权限", "scanner_low", "LowPriv_2026"),
]

META: dict[str, dict] = {
    # ── R1–R13 ──
    "R1": M("藤县人民医院 · 门诊挂号", "RuoYi 4.5.1 单机版", "8", R_COMMON_CREDS,
            ["官方原版登录页与 favicon，版本曲线基线"], logs=["runtime/R1/run.log", "runtime/R1/run.err.log"]),
    "R2": M("广西顺捷物流 · 运单", "RuoYi 4.6.2 单机版", "8", R_COMMON_CREDS,
            ["R12 / R13 复用本后端"], logs=["runtime/R2/run.log", "runtime/R2/run.err.log"]),
    "R3": M("梧州自来水 · 抄表", "RuoYi 4.7.8 单机版", "8", R_COMMON_CREDS,
            ["/logs/ 静态别名依赖 runtime/R3/logs"], logs=["runtime/R3/run.log", "runtime/R3/run.err.log"]),
    "R4": M("长洲区教育局 · 学籍", "RuoYi 4.8.0 单机版", "8", R_COMMON_CREDS,
            ["若依 4.8 版本曲线"], logs=["runtime/R4/run.log", "runtime/R4/run.err.log"]),
    "R5": M("华投财务共享 · 报销", "RuoYi 4.8.3 单机版", "17", R_COMMON_CREDS,
            ["版本曲线终点；JDK17"], logs=["runtime/R5/run.log", "runtime/R5/run.err.log"]),
    "R6": M("深圳跨境通 · 订单", "RuoYi Vue 3.9.2", "17", R_COMMON_CREDS,
            ["前后端分离；前端 runtime/R6/ui"], logs=["runtime/R6/run.log", "runtime/R6/run.err.log"]),
    "R7": M("明德职院 · 选课", "RuoYi Vue 3.8.9", "8", R_COMMON_CREDS,
            ["前后端分离；前端 runtime/R7/ui", "含 .git/.svn 等真实感诱饵"], logs=["runtime/R7/run.log", "runtime/R7/run.err.log"]),
    "R8": M("南宁智谷 · 园区运营", "RuoYi Cloud 3.6.8", "17", [_cred("管理员", "admin", "admin123"), _cred("Nacos", "nacos", "nacos")],
            ["独占型：Nacos + 6 个服务共 7 个 JVM，约 4.2GB", "启动前会检查其他靶场并确认可用内存"],
            logs=["runtime/R8/run.log", "runtime/R8/run.err.log", ".state/R8.status.json"], exclusive=True),
    "R9": M("华电巡检", "RuoYi Plus 5.6.2", "17", [_cred("管理员", "admin", "admin123")],
            ["前后端分离；前端 runtime/R9/ui"], logs=["runtime/R9/run.log", "runtime/R9/run.err.log"]),
    "R10": M("星图报表", "JeecgBoot 3.6.3", "8", [_cred("管理员", "admin", "123456")],
            ["前后端分离；API 前缀 /jeecg-boot/", "默认 safe 模式，vuln 需命令行启动"],
            logs=["runtime/R10/run.log", "runtime/R10/run.err.log"]),
    "R11": M("负样本（非若依）", "自建 Spring Boot 3.4.1", "17", [],
            ["负样本：不是若依，预期扫描器全 SAFE"], logs=["runtime/R11/run.log", "runtime/R11/run.err.log"]),
    "R12": M("R2 + 简单 WAF", "RuoYi 4.6.2 变体", "8", R_COMMON_CREDS,
            ["复用 R2 后端；停止只禁用 19112 入口，不影响 R2"], deps=["R2"],
            logs=["runtime/R2/run.log", "runtime/R2/run.err.log"]),
    "R13": M("R13 留出集", "RuoYi 4.6.2 加固版", "8", R_COMMON_CREDS,
            ["hold-out，不参与日常回归", "复用 R2 后端；启动时自动启用 R13.conf"], deps=["R2"],
            logs=["runtime/R2/run.log", "runtime/R2/run.err.log"]),

    # ── 特殊形态 ──
    "A2": M("A2 双因子", "RuoYi 4.6.2 + TOTP", "8", [_cred("管理员", "admin", "admin123")],
            ["TOTP 密钥 JBSWY3DPEHPK3PXP", "5 次错误锁定；登录路径 /login"], logs=["runtime/A2/logs/run.log", "runtime/A2/logs/run.err.log"]),
    "D1": M("D1 二开变形", "RuoYi 4.6.2 换皮", "8", [_cred("管理员", "admin", "admin123")],
            ["登录路径 /portal/auth/signin；context-path /portal", "默认 safe 模式"],
            logs=["runtime/D1/logs/run.log", "runtime/D1/logs/run.err.log"]),
    "C3": M("C3 蜜罐", "假漏洞诱饵", None, [],
            ["假 .git/.env/备份/Druid/Swagger 页面；用于测误报", "任意未知路径也返回 200"],
            logs=["runtime/C3/logs/console.log"]),
    "C5": M("C5 暴露但需认证", "C2-1b + Nginx Basic Auth", "17",
            [_cred("Basic Auth", "c5ops", "Ops_2026_Letmein")],
            ["C2-1b 必须 vuln 模式；safe 模式下 /actuator/env 不暴露", "匿名 401 是健康状态"],
            deps=["C2-1b"], logs=["nginx/logs/error.log", "nginx/logs/access.log"]),

    # ── C1 组件 ──
    "C1-1": M("Jolokia", "Actuator 全开", "17", [], ["运维组件；/actuator/health"],
              logs=["runtime/C1/jolokia/logs/console.log", "runtime/C1/jolokia/logs/console.err.log"]),
    "C1-2": M("H2 Console", "H2 控制台", "17", [_cred("H2", "sa", "", "空密码")],
              ["内存 H2；/h2-console"], logs=["runtime/C1/h2-console/logs/console.log", "runtime/C1/h2-console/logs/console.err.log"]),
    "C1-3": M("Spring Data REST", "数据服务", "17", [_cred("H2", "sa", "", "空密码")],
              ["内存 H2；/api"], logs=["runtime/C1/data-service/logs/console.log", "runtime/C1/data-service/logs/console.err.log"]),
    "C1-4": M("Spring Cloud Config", "配置中心", "17", [], ["/application/default"],
              logs=["runtime/C1/config-server/logs/console.log", "runtime/C1/config-server/logs/console.err.log"]),

    # ── C2 组件 ──
    "C2-1a": M("Spring Boot Admin Server", "SBA 服务端", "17", [],
               ["与 C2-1b 同生命周期；启动/停止会同时影响两者"], logs=["runtime/C2/sba/logs/sba-server-console.log"]),
    "C2-1b": M("Spring Boot Admin Client", "SBA 客户端", "17", [],
               ["与 C2-1a 同生命周期", "C5 依赖本目标，且必须是 vuln 模式"],
               logs=["runtime/C2/sba/logs/sba-client-console.log"]),
    "C2-2": M("Spring4Shell", "Tomcat 9 + Spring 5.3.17", "17", [], ["依赖 tools/tomcat-9.0.58-s4s"],
              logs=["runtime/C2/s4s/logs/tomcat-console.log"]),
    "C2-3": M("Spring Cloud Function", "函数式 RCE", "17", [], ["/ 返回 JSON"],
              logs=["runtime/C2/scf/logs/scf-console.log"]),

    # ── C4 中间件 ──
    "C4-1": M("Redis 未授权", "空密码 + bind 0.0.0.0", None, [],
              ["Y1 依赖此 Redis（16379）", "无 HTTP 入口"], logs=["runtime/C4/redis-unauth/run.log", "runtime/C4/redis-unauth/redis.log"]),
    "C4-2": M("MinIO / S3 未授权", "真实 S3 协议复刻", None, [_cred("S3", "minioadmin", "minioadmin")],
              ["/minio/health/live 恒 200；真正的未授权证据在 GET /"], logs=["runtime/C4/minio/run.log"]),
    "C4-3": M("RocketMQ Dashboard 未授权", "Dashboard", None, [], ["入口在 /，不是 /rocketmq/"],
              logs=["runtime/C4/rocketmq/run.log"]),
    "C4-4": M("jmreport SSTI", "Freemarker 真实求值", None, [], ["无 GET 根路径，端口通即视为 UP"],
              logs=["runtime/C4/jmreport/run.log"]),
    "C4-5": M("若依代码生成 SSTI", "Gen 预览真实求值", None, [], ["/tool/gen"],
              logs=["runtime/C4/gen/run.log"]),
    "C4-6": M("Thymeleaf / SpEL SSTI", "视图名注入", None, [], ["/ 与 /__${7*7}__::.x"],
              logs=["runtime/C4/thymeleaf/run.log"]),

    # ── 基础设施 ──
    "infra:mysql": M("MySQL", "基础设施 13307", None, [_cred("root", "root", "", "空密码")],
                     ["MySQL 8.0；datadir 在 lab.local.json / my.ini 中配置", "面板不提供停止按钮"]),
    "infra:redis": M("Redis", "基础设施 6379", None, [_cred("密码", "", "ruoyi123")],
                     ["宿主 Redis；C4-1 是另一个无密码实例（16379）", "面板不提供停止按钮"]),
    "infra:nginx": M("Nginx", "入口网关 191xx / 193xx", None, [], ["停止会关闭所有入口；MySQL/Redis 不受影响"]),

    # ── 非若依 overlay ──
    "Y1": M("芋道 yudao", "yudao 2026.10-jdk8-SNAPSHOT", "8", [_cred("管理员", "admin", "admin123")],
            ["不在 lab.py 注册表里", "后端 19251 / 入口 19115", "需要 C4-1 的无密码 Redis 16379",
             "y1_start.py 硬编码 JDK8 路径 D:/develop/java-se-8u44-ri"],
            deps=["C4-1"], logs=["runtime/Y1/run.log", "runtime/Y1/run.err.log"]),
}


# ── 构建检查 ──

def _f(path: str, label: str, hint: str = "", optional: bool = False) -> CheckSpec:
    return CheckSpec(label, "file", path, optional, hint)


def _d(path: str, label: str, hint: str = "", optional: bool = False) -> CheckSpec:
    return CheckSpec(label, "dir", path, optional, hint)


def _g(pattern: str, label: str, hint: str = "", optional: bool = False) -> CheckSpec:
    return CheckSpec(label, "glob", pattern, optional, hint)


def _jar(tid: str, jar: str, label: str | None = None) -> CheckSpec:
    return _f(f"build/{tid}/{jar}", label or f"{tid} 后端 jar")


def _runtime(tid: str) -> list[CheckSpec]:
    return [
        _f(f"runtime/{tid}/application-prod.yml", f"{tid} 运行配置"),
        _f(f"runtime/{tid}/logback.xml", f"{tid} 日志配置"),
    ]


def _conf(name: str) -> CheckSpec:
    return _g(f"nginx/conf.d/{name}.conf*", f"{name} Nginx 配置")


def _build_checks(tid: str) -> list[CheckSpec]:
    if tid in ("R1", "R2", "R4", "R5"):
        return [_jar(tid, "ruoyi-admin.jar"), *_runtime(tid), _conf(tid)]
    if tid == "R3":
        return [_jar("R3", "ruoyi-admin.jar"), *_runtime("R3"), _d("runtime/R3/logs", "R3 日志目录（/logs/ 别名）", optional=True), _conf("R3")]
    if tid in ("R6", "R7"):
        return [_jar(tid, "ruoyi-admin.jar"), *_runtime(tid), _f(f"runtime/{tid}/ui/index.html", f"{tid} 前端 dist"), _conf(tid)]
    if tid == "R8":
        return [
            _jar("R8", "ruoyi-auth.jar"),
            _jar("R8", "ruoyi-gateway.jar"),
            _jar("R8", "ruoyi-modules-system.jar"),
            _jar("R8", "ruoyi-modules-gen.jar"),
            _jar("R8", "ruoyi-modules-job.jar"),
            _jar("R8", "ruoyi-modules-file.jar"),
            _f("runtime/R8/ui/index.html", "R8 前端 dist"),
            _conf("R8"),
            _d("tools/nacos", "本地 Nacos", optional=True),
            _g("tools/nacos-server-*.zip", "Nacos 压缩包", optional=True),
        ]
    if tid == "R9":
        return [_jar("R9", "ruoyi-admin.jar"), _f("runtime/R9/ui/index.html", "R9 前端 dist"), _conf("R9")]
    if tid == "R10":
        return [
            _jar("R10", "jeecg-system-start-3.6.3.jar", "R10 后端 jar"),
            _f("runtime/R10/ui/index.html", "R10 前端 dist"),
            _conf("R10"),
        ]
    if tid == "R11":
        return [_jar("R11", "internal-api.jar", "R11 后端 jar"), _conf("R11")]
    if tid == "R12":
        return [_jar("R2", "ruoyi-admin.jar", "R2 后端 jar（R12 复用）"), *_runtime("R2"), _conf("R12")]
    if tid == "R13":
        return [_jar("R2", "ruoyi-admin.jar", "R2 后端 jar（R13 复用）"), *_runtime("R2"), _conf("R13")]
    if tid in ("A2", "D1"):
        return [_jar(tid, "ruoyi-admin.jar"), *_runtime(tid), _conf(tid)]
    if tid == "Y1":
        return [
            _jar("Y1", "yudao-server.jar", "Y1 后端 jar"),
            _conf("Y1"),
            _f(lb.LABENV.REDIS_EXE, "redis-server（Y1 依赖）"),
        ]
    if tid == "C1-1":
        return [_f("runtime/C1/jolokia/jolokia.jar", "Jolokia jar")]
    if tid == "C1-2":
        return [_f("runtime/C1/h2-console/h2-console.jar", "H2 Console jar")]
    if tid == "C1-3":
        return [_f("runtime/C1/data-service/data-service.jar", "Data REST jar")]
    if tid == "C1-4":
        return [
            _f("runtime/C1/config-server/config-server.jar", "Config Server jar"),
            _d("runtime/C1/config-server/config", "Config Server 配置目录"),
        ]
    if tid == "C2-1a":
        return [_f("runtime/C2/sba/sba-server.jar", "SBA Server jar")]
    if tid == "C2-1b":
        return [
            _f("runtime/C2/sba/sba-client.jar", "SBA Client jar（vuln）"),
            _f("runtime/C2/sba/sba-client-safe.jar", "SBA Client jar（safe）"),
        ]
    if tid == "C2-2":
        return [
            _f("runtime/C2/s4s/ROOT.war", "Spring4Shell WAR"),
            _d("tools/tomcat-9.0.58-s4s", "Tomcat 9 目录"),
            _f("tools/tomcat-9.0.58-s4s/bin/catalina.bat", "Tomcat catalina.bat"),
        ]
    if tid == "C2-3":
        return [
            _f("runtime/C2/scf/scf.jar", "SCF jar（vuln）"),
            _f("runtime/C2/scf/scf-safe.jar", "SCF jar（safe）"),
        ]
    if tid == "C3":
        return [_f("src/C3/honeypot.py", "蜜罐脚本")]
    if tid == "C4-1":
        return [_f("runtime/C4/redis-unauth/redis.conf", "Redis 未授权配置"), _f(lb.LABENV.REDIS_EXE, "redis-server")]
    if tid == "C4-2":
        return [_f("src/C4/minio-s3/server.py", "MinIO/S3 复刻脚本")]
    if tid == "C4-3":
        return [_f("runtime/C4/rocketmq/c4-rocketmq-dashboard-1.0.0.jar", "RocketMQ Dashboard jar")]
    if tid == "C4-4":
        return [_f("runtime/C4/jmreport/c4-jmreport-ssti-1.0.0.jar", "jmreport SSTI jar")]
    if tid == "C4-5":
        return [_f("runtime/C4/gen/c4-ruoyi-gen-ssti-1.0.0.jar", "Gen SSTI jar")]
    if tid == "C4-6":
        return [_f("runtime/C4/thymeleaf/c4-thymeleaf-ssti-1.0.0.jar", "Thymeleaf SSTI jar")]
    if tid == "C5":
        return [
            _conf("C5"),
            _f("nginx/nginx.exe", "nginx.exe"),
            _f("nginx/c5.htpasswd", "C5 Basic Auth 凭据", optional=True),
        ]
    if tid == "infra:mysql":
        return [_f(lb.LABENV.MYSQL_INI, "MySQL my.ini"), _f(lb.LABENV.MYSQLD, "mysqld.exe")]
    if tid == "infra:redis":
        return [_f(lb.LABENV.REDIS_EXE, "redis-server.exe"), _f("tools/redis/redis.windows.conf", "Redis 配置")]
    if tid == "infra:nginx":
        return [_f("nginx/nginx.exe", "nginx.exe"), _f("nginx/conf/nginx.conf", "nginx.conf")]
    return []


def _source_checks(tid: str) -> list[CheckSpec]:
    if tid.startswith("R") and tid[1:].isdigit():
        if tid in ("R12", "R13"):
            return [_d("src/R2", "R2 源码")]
        return [_d(f"src/{tid}", f"{tid} 源码")]
    if tid in ("A2", "D1"):
        return [_d(f"src/{tid}", f"{tid} 源码")]
    if tid == "Y1":
        return [_d("src/Y1", "Y1 源码（可能未检出）")]
    if tid in C1_COMP:
        return [_d(f"src/C1/{C1_COMP[tid]}", f"{C1_COMP[tid]} 源码")]
    if tid in ("C2-1a", "C2-1b"):
        return [_d("src/C2/sba", "SBA 源码")]
    if tid == "C2-2":
        return [_d("src/C2/s4s", "S4S 源码")]
    if tid == "C2-3":
        return [_d("src/C2/scf", "SCF 源码")]
    if tid == "C3":
        return [_d("src/C3", "蜜罐源码")]
    if tid == "C4-2":
        return [_d("src/C4/minio-s3", "MinIO/S3 源码")]
    if tid == "C4-3":
        return [_d("src/C4/rocketmq-dashboard", "RocketMQ Dashboard 源码")]
    if tid == "C4-4":
        return [_d("src/C4/jmreport-ssti", "jmreport SSTI 源码")]
    if tid == "C4-5":
        return [_d("src/C4/ruoyi-gen-ssti", "Gen SSTI 源码")]
    if tid == "C4-6":
        return [_d("src/C4/thymeleaf-ssti", "Thymeleaf SSTI 源码")]
    return []


BUILD_HINTS = {
    "site": "按 docs/打包到另一台电脑.md 重新构建，或从打包件复制 build/ 与 runtime/ 产物",
    "component": "C1 见 docs/C1/<组件>/部署说明.md；C2 用 python scripts\\c2_build.py",
    "middleware": "C4 Java 组件用 python scripts\\c4_start.py build <comp>；Redis/MinIO 检查配置与脚本",
    "special": "D1/A2 见各自部署说明；C3 检查 src\\C3\\honeypot.py；C5 检查 nginx conf 与 nginx.exe",
    "holdout": "先准备 R2 的 jar 和 runtime 配置",
    "extra": "cd src\\Y1 && mvn -DskipTests package，再复制到 build\\Y1\\",
    "infra": "检查 lab.local.json 或对应 LAB_* 环境变量",
}


def _group(tid: str) -> str:
    if tid.startswith("infra:"):
        return "infra"
    if tid == "Y1":
        return "extra"
    if tid == "R13":
        return "holdout"
    if tid.startswith("C4-"):
        return "middleware"
    if tid in ("C3", "D1", "A2", "C5"):
        return "special"
    if tid.startswith("C1-") or tid.startswith("C2-"):
        return "component"
    return "site"


def _lifecycle(tid: str) -> str:
    if tid == "Y1":
        return "y1"
    if tid in C1_COMP:
        return "c1"
    if tid in ("C2-1a", "C2-1b"):
        return "c2_sba"
    if tid == "C2-2":
        return "c2_s4s"
    if tid == "C2-3":
        return "c2_scf"
    if tid == "C3":
        return "c3"
    if tid in C4_COMP:
        return "c4"
    if tid == "C5":
        return "c5"
    if tid == "R12":
        return "r12"
    return "lab"


def _java_for(tid: str, meta: dict) -> str | None:
    if meta.get("java"):
        return meta["java"]
    if tid in ("R1", "R2", "R3", "R4", "R7", "R10", "R12", "R13", "A2", "D1", "Y1"):
        return "8"
    if tid.startswith("C") or tid in ("R5", "R6", "R8", "R9", "R11"):
        return "17"
    return None


def _default_logs(tid: str) -> list[str]:
    if tid.startswith("R") and tid[1:].isdigit():
        if tid in ("R12", "R13"):
            return ["runtime/R2/run.log", "runtime/R2/run.err.log"]
        return [f"runtime/{tid}/run.log", f"runtime/{tid}/run.err.log"]
    if tid in C4_COMP:
        return [f"runtime/C4/{ {'C4-1':'redis-unauth','C4-2':'minio','C4-3':'rocketmq','C4-4':'jmreport','C4-5':'gen','C4-6':'thymeleaf'}[tid] }/run.log"]
    return []


def _build_target(tid: str) -> TargetDef:
    cfg = lb.LAB.SITES.get(tid, {})
    meta = META.get(tid, M(tid, cfg.get("group", "target")))
    group = _group(tid)
    entry = int(cfg.get("entry") or (19115 if tid == "Y1" else 0))
    backend = int(cfg.get("backend") or (19251 if tid == "Y1" else 0))
    probe = cfg.get("probe")
    if tid == "Y1":
        probe = (lb.Y1_PROBE, {200})
    if tid == "C5":
        probe = (lb.C5_PROBE, {401})
    if tid == "C4-1":
        url = "redis://127.0.0.1:16379"
    elif group == "infra":
        url = None
    else:
        url = f"http://127.0.0.1:{entry}"
    deps = list(meta.get("deps") or cfg.get("depends") or [])
    if tid == "C5" and "C2-1b" not in deps:
        deps.append("C2-1b")
    if tid == "Y1" and "C4-1" not in deps:
        deps.append("C4-1")
    return TargetDef(
        id=tid,
        name=meta["name"],
        business=meta["business"],
        group=group,
        entry=entry,
        backend=backend,
        url=url,
        probe=probe,
        pidfile=cfg.get("pidfile") or ("Y1.pid" if tid == "Y1" else None),
        lifecycle=_lifecycle(tid),
        conf_name=lb.CONF_NAMES.get(tid),
        credentials=meta.get("creds", []),
        notes=meta.get("notes", []),
        dependencies=deps,
        exclusive=bool(meta.get("exclusive") or cfg.get("exclusive")),
        pair_id="C2-1" if tid in ("C2-1a", "C2-1b") else None,
        cloud=bool(cfg.get("cloud")),
        java=_java_for(tid, meta),
        log_paths=meta.get("logs") or _default_logs(tid),
        build_checks=_build_checks(tid),
        source_checks=_source_checks(tid),
        build_hint=meta.get("hint") or BUILD_HINTS.get(group, "检查 runtime 产物"),
    )


TARGETS: dict[str, TargetDef] = {}
for _tid in list(lb.LAB.ALL) + ["Y1"]:
    TARGETS[_tid] = _build_target(_tid)
for _tid, _t in TARGETS.items():
    for _dep in _t.dependencies:
        if _dep in TARGETS and _tid not in TARGETS[_dep].dependents:
            TARGETS[_dep].dependents.append(_tid)


UI_GROUPS: dict[str, list[str]] = {
    "site": [f"R{i}" for i in range(1, 13)],
    "holdout": ["R13"],
    "component": ["C1-1", "C1-2", "C1-3", "C1-4", "C2-1a", "C2-1b", "C2-2", "C2-3"],
    "middleware": [f"C4-{i}" for i in range(1, 7)],
    "special": ["C3", "D1", "A2", "C5"],
    "infra": ["infra:mysql", "infra:redis", "infra:nginx"],
    "extra": ["Y1"],
}

GROUP_NOTES = {
    "site": "R8 为独占型，分组启动自动跳过；R13 在留出集",
    "holdout": "R13 只在阶段验证时启用，不参与日常回归",
    "component": "C2-1a/1b 同生命周期，分组启动只起一次；C5 在特殊形态",
    "middleware": "C4-1 同时是 Y1 的 Redis 依赖；C4-4 无 GET 根路径，端口通即 UP",
    "special": "C5 会自动带起 C2-1b（vuln 模式）；D1/A2 默认 safe 模式",
    "infra": "停止只关闭 Nginx；MySQL/Redis 保持运行，面板不提供停止按钮",
    "extra": "Y1 会自动带起 C4-1 Redis（16379）",
}

GROUP_START: dict[str, list[str]] = {
    "site": [f"R{i}" for i in range(1, 8)] + [f"R{i}" for i in range(9, 13)],
    "holdout": ["R13"],
    "component": ["C1-1", "C1-2", "C1-3", "C1-4", "C2-1a", "C2-2", "C2-3"],
    "middleware": [f"C4-{i}" for i in range(1, 7)],
    "special": ["C3", "D1", "A2", "C5"],
    "infra": ["infra:mysql", "infra:redis", "infra:nginx"],
    "extra": ["Y1"],
}

# 停止顺序：先停下游/上层组件，最后停 Nginx；MySQL/Redis 不在列表里。
STOP_RANK = {
    "R8": 0,
    "Y1": 1,
    "C5": 2,
    "C2-3": 3,
    "C2-2": 4,
    "C2-1a": 5,
    "C2-1b": 5,
    "C4-6": 6,
    "C4-5": 7,
    "C4-4": 8,
    "C4-3": 9,
    "C4-2": 10,
    "C4-1": 11,
    "C3": 12,
    "D1": 13,
    "A2": 14,
    "R13": 15,
    "R12": 16,
    "R11": 17,
    "R10": 18,
    "R9": 19,
    "R7": 20,
    "R6": 21,
    "R5": 22,
    "R4": 23,
    "R3": 24,
    "R2": 25,
    "R1": 26,
    "infra:nginx": 90,
    "infra:redis": 100,
    "infra:mysql": 101,
}


def _dedupe_pair(ids: list[str]) -> list[str]:
    out: list[str] = []
    for x in ids:
        if x not in out:
            out.append(x)
    if "C2-1a" in out and "C2-1b" in out:
        out.remove("C2-1b")
    return out


def start_plan(tid: str) -> list[str]:
    """启动某目标前需要先确保的目标（不含 lab.py 自己会带起的基础设施）。"""
    plan: list[str] = []
    if tid == "C5":
        if not lb.port_open(lb.C5_BACKEND, timeout=0.35):
            plan.append("C2-1b")
        if not lb.nginx_running():
            plan.append("infra:nginx")
    elif tid == "Y1":
        if not lb.port_open(13307, timeout=0.35):
            plan.append("infra:mysql")
        if not lb.port_open(16379, timeout=0.35):
            plan.append("C4-1")
        if not lb.nginx_running():
            plan.append("infra:nginx")
    plan.append(tid)
    return _dedupe_pair(plan)


def group_start_plan(group: str) -> list[str]:
    plan: list[str] = []
    for tid in GROUP_START.get(group, []):
        for x in start_plan(tid):
            if x not in plan:
                plan.append(x)
    return _dedupe_pair(plan)


def stop_order(ids: list[str]) -> list[str]:
    protected = {"infra:mysql", "infra:redis"}
    filtered = [x for x in _dedupe_pair(list(ids)) if x not in protected]
    return sorted(filtered, key=lambda x: STOP_RANK.get(x, 50))


def stop_all_plan() -> list[str]:
    ids = ["R8", "Y1", "C5", "C2-3", "C2-2", "C2-1a"]
    ids += [f"C4-{i}" for i in range(6, 0, -1)]
    ids += ["C3", "D1", "A2", "R13", "R12"]
    ids += [f"R{i}" for i in range(11, 0, -1)]
    ids += ["infra:nginx"]
    return _dedupe_pair(ids)


def command_for(tid: str, action: str) -> list[str]:
    py = lb.PYTHON
    t = TARGETS[tid]
    if t.lifecycle == "c1":
        script = "components_start.py" if action == "start" else "components_stop.py"
        return [py, f"scripts/{script}", C1_COMP[tid]]
    if t.lifecycle == "c2_sba":
        return [py, "scripts/c2_sba.py", action]
    if t.lifecycle == "c2_s4s":
        return [py, "scripts/c2_s4s.py", action]
    if t.lifecycle == "c2_scf":
        return [py, "scripts/c2_scf.py", action]
    if t.lifecycle == "c3":
        return [py, "scripts/c3_honeypot.py", action]
    if t.lifecycle == "c4":
        return [py, "scripts/c4_start.py", action, C4_COMP[tid]]
    if t.lifecycle == "c5":
        return [py, "scripts/c5_start.py", action]
    if t.lifecycle == "y1":
        return [py, "scripts/y1_start.py", action]
    # lab.py 的子命令是 up/down，不是 start/stop。
    sub = "up" if action == "start" else "down"
    return [py, "scripts/lab.py", sub, tid]


def command_display(tid: str, action: str) -> str:
    t = TARGETS[tid]
    if t.lifecycle == "r12":
        if action == "start":
            return "启用 R12.conf → python scripts\\lab.py up R12"
        return "禁用 R12.conf → nginx -s reload"
    if t.lifecycle == "y1":
        if action == "start":
            return "python scripts\\y1_start.py start（自动 C4-1 + 启用 Y1.conf）"
        return "python scripts\\y1_start.py stop → 禁用 Y1.conf"
    cmd = command_for(tid, action)
    parts = []
    for x in cmd:
        if x == lb.PYTHON or str(x).lower().endswith("python.exe"):
            parts.append("python")
        elif "\\" in str(x) or "/" in str(x):
            parts.append(str(x).replace("/", "\\"))
        else:
            parts.append(str(x))
    return " ".join(parts)


def _resolve(rel: str) -> Path:
    p = Path(rel)
    return p if p.is_absolute() else LAB_ROOT / p


def _eval_check(spec: CheckSpec) -> dict:
    p = _resolve(spec.path)
    ok = False
    detail = ""
    try:
        if spec.kind == "file":
            ok = p.is_file() and p.stat().st_size > 0
        elif spec.kind == "dir":
            ok = p.is_dir()
        elif spec.kind == "glob":
            parent = p.parent
            ok = parent.is_dir() and any(x.is_file() or x.is_dir() for x in parent.glob(p.name))
        else:
            detail = f"未知检查类型: {spec.kind}"
    except OSError as exc:
        detail = str(exc)
    return {
        "label": spec.label,
        "kind": spec.kind,
        "path": str(p),
        "ok": bool(ok),
        "optional": spec.optional,
        "hint": spec.hint,
        "detail": detail,
    }


_BUILD_CACHE: dict[str, dict] = {}
_BUILD_LOCK = threading.Lock()
_SCAN_AT: str | None = None


def scan_target(tid: str) -> dict:
    t = TARGETS[tid]
    checks = [_eval_check(x) for x in t.build_checks]
    source_checks = [_eval_check(x) for x in t.source_checks]
    source_present = bool(source_checks) and all(x["ok"] for x in source_checks)
    required = [x for x in checks if not x["optional"]]
    required_ok = [x for x in required if x["ok"]]
    missing = [x for x in required if not x["ok"]]
    warnings = [f"{x['label']} 缺失（可选）：{x['path']}" for x in checks if x["optional"] and not x["ok"]]

    if required and len(required_ok) == len(required):
        state = "ready"
    elif required_ok:
        state = "partial"
    elif source_present:
        state = "unbuilt"
    else:
        state = "absent"

    # 工具链提示：不让全局 JDK 缺失把每座靶场都标成 unbuilt，只给 warning。
    if t.java == "8" and lb.LABENV.JAVA8 and not Path(lb.LABENV.JAVA8).is_file():
        warnings.append(f"JDK8 不可用：{lb.LABENV.JAVA8}")
    if t.java == "17" and lb.LABENV.JAVA17 and not Path(lb.LABENV.JAVA17).is_file():
        warnings.append(f"JDK17 不可用：{lb.LABENV.JAVA17}")
    if t.lifecycle == "c4" and not Path("D:/develop/jdk-17.0.0.1/bin/java.exe").is_file():
        warnings.append("C4 脚本硬编码 JDK17 路径 D:/develop/jdk-17.0.0.1，当前不存在")

    if tid == "R8":
        warnings.append("R8 独占约 4.2GB，启动前需停止其他靶场")
        if not any(x["ok"] for x in checks if x["label"] in ("本地 Nacos", "Nacos 压缩包")):
            warnings.append("本地未发现 Nacos（tools/nacos 或 zip）；若用 Docker 可忽略")
    if tid in ("R12", "R13"):
        warnings.append("复用 R2 后端；R2 不在时会先启动 R2")
    if tid == "Y1":
        warnings.append("y1_start.py 硬编码 JDK8 路径 D:/develop/java-se-8u44-ri")
    if tid == "C5":
        warnings.append("需要 C2-1b 在 vuln 模式；safe 模式下 /actuator/env 不暴露")
    if tid in ("C2-1a", "C2-1b"):
        warnings.append("C2-1a/1b 同生命周期，启动/停止会同时影响两者")
    if tid == "C4-1":
        warnings.append("Y1 依赖本 Redis（16379）")
    if tid in ("R9", "R10", "D1"):
        warnings.append("默认 safe 模式；vuln 模式需从命令行启动")

    return {
        "state": state,
        "source_present": source_present,
        "checks": checks,
        "source_checks": source_checks,
        "missing": missing,
        "warnings": warnings,
        "required_total": len(required),
        "required_ok": len(required_ok),
        "hint": t.build_hint,
    }


def rescan_build() -> dict[str, dict]:
    global _SCAN_AT
    with _BUILD_LOCK:
        for tid in TARGETS:
            _BUILD_CACHE[tid] = scan_target(tid)
        _SCAN_AT = datetime.now().isoformat(timespec="seconds")
        return dict(_BUILD_CACHE)


def build_info(tid: str) -> dict:
    if tid not in _BUILD_CACHE:
        _BUILD_CACHE[tid] = scan_target(tid)
    return _BUILD_CACHE[tid]


def scan_time() -> str | None:
    return _SCAN_AT


def environment_checks() -> list[dict]:
    items = [
        ("python", "Python", lb.PYTHON, True),
        ("jdk8", "JDK 8", lb.LABENV.JAVA8, True),
        ("jdk17", "JDK 17", lb.LABENV.JAVA17, True),
        ("maven", "Maven", lb.LABENV.MVN_CMD, True),
        ("mysqld", "MySQL", lb.LABENV.MYSQLD, True),
        ("redis", "Redis", lb.LABENV.REDIS_EXE, True),
        ("nginx", "Nginx", str(LAB_ROOT / "nginx" / "nginx.exe"), True),
        ("lab_local", "lab.local.json", str(LAB_ROOT / "lab.local.json"), False),
    ]
    out = []
    for key, label, path, required in items:
        p = Path(path) if path else Path("")
        out.append({
            "key": key,
            "label": label,
            "path": path,
            "ok": bool(path) and p.is_file(),
            "required": required,
        })
    return out


def target_dict(tid: str) -> dict:
    t = TARGETS[tid]
    return {
        "id": t.id,
        "name": t.name,
        "business": t.business,
        "group": t.group,
        "group_label": GROUP_LABELS.get(t.group, t.group),
        "entry": t.entry,
        "backend": t.backend,
        "url": t.url,
        "probe": {"path": t.probe[0], "expect": sorted(t.probe[1])} if t.probe else None,
        "pidfile": t.pidfile,
        "conf_name": t.conf_name,
        "lifecycle": t.lifecycle,
        "exclusive": t.exclusive,
        "pair_id": t.pair_id,
        "cloud": t.cloud,
        "java": t.java,
        "credentials": t.credentials,
        "notes": t.notes,
        "dependencies": t.dependencies,
        "dependents": t.dependents,
        "log_paths": t.log_paths,
        "start_command": command_display(tid, "start"),
        "stop_command": command_display(tid, "stop"),
        "stop_enabled": tid not in ("infra:mysql", "infra:redis"),
        "build": build_info(tid),
    }


def list_targets() -> list[dict]:
    return [target_dict(tid) for tid in TARGETS]


def groups() -> list[dict]:
    out = []
    for key in GROUP_ORDER:
        ids = UI_GROUPS.get(key, [])
        start_ids = GROUP_START.get(key, [])
        out.append({
            "key": key,
            "label": GROUP_LABELS[key],
            "targets": ids,
            "start_targets": start_ids,
            "stop_targets": stop_order(ids),
            "note": GROUP_NOTES.get(key, ""),
        })
    return out


def target_running_quick(tid: str) -> bool:
    t = TARGETS[tid]
    if t.group == "infra":
        return False
    if tid == "Y1":
        return lb.port_open(19251, timeout=0.35) or lb.port_open(19115, timeout=0.35)
    if tid == "C5":
        return lb.port_open(19351, timeout=0.35)
    pid = lb.read_pid(tid)
    if pid and lb.pid_alive(pid):
        return True
    if t.conf_name:
        return lb.conf_enabled(t.conf_name) and lb.port_open(t.entry, timeout=0.35)
    port = t.backend or t.entry
    return lb.port_open(port, timeout=0.35) if port else False


def running_conflicts_for_r8() -> list[str]:
    candidates = [tid for tid in TARGETS if tid != "R8" and not tid.startswith("infra:")]

    def one(tid: str) -> str | None:
        try:
            return tid if target_running_quick(tid) else None
        except Exception:
            return None

    # 串行扫 35 个端口在 Windows 上要十几秒，UI 会以为按钮没反应。
    # 端口探测彼此独立，并行后约 1 秒内返回。
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(one, candidates))
    return [x for x in results if x]


def can_start_build(tid: str) -> bool:
    return build_info(tid).get("state") in ("ready", "partial")


def log_paths_for(tid: str) -> list[str]:
    return TARGETS[tid].log_paths
