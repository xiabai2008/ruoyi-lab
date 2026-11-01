r"""靶场外部依赖路径的统一来源。

为什么单独抽一个模块
====================
22 个脚本各自硬编码 `D:\develop\jdk-17.0.0.1`、`D:\tools\Python 3.12.9\python.exe`
这类本机路径，别人 clone 下来一行都跑不起来。这里集中收口：

- **优先级**：环境变量 > 项目内配置文件 > 内置默认值
- **零依赖**：只用标准库，任何脚本都能 import
- **不改调用方写法**：还是 `from labenv import JDK17`，但值变成可配置的

配置方式（二选一）
------------------
1. 环境变量（推荐给 CI / 临时覆盖）：
   ```
   set LAB_JDK8=D:\java\jdk8
   set LAB_JDK17=D:\java\jdk17
   set LAB_PYTHON=D:\python\python.exe
   ```
2. 项目内 `lab.local.json`（推荐给本机长期使用）：
   ```json
   {
     "JDK8": "D:/develop/java-se-8u44-ri",
     "JDK17": "D:/develop/jdk-17.0.0.1",
     "PYTHON": "D:/tools/Python 3.12.9/python.exe",
     "MVN": "D:/tools/apache-maven-3.9.12"
   }
   ```

默认值只在本机开发环境成立，换机器务必配环境变量或 lab.local.json。
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 项目内配置文件（不进版本控制，见 .gitignore）
LOCAL_CONF = os.path.join(ROOT, "lab.local.json")

_cache: dict[str, str] | None = None


def _load_local() -> dict[str, str]:
    global _cache
    if _cache is not None:
        return _cache
    data: dict[str, str] = {}
    try:
        with open(LOCAL_CONF, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            data = {str(k): str(v) for k, v in raw.items()}
    except (OSError, ValueError):
        pass
    _cache = data
    return data


def get(key: str, default: str = "") -> str:
    """按「环境变量 > lab.local.json > 默认值」取路径。"""
    env = os.environ.get(f"LAB_{key}")
    if env:
        return env
    local = _load_local().get(key)
    if local:
        return local
    return default


def _exe(base: str, *parts: str) -> str:
    """把 base 目录和可执行名拼起来；base 为空时返回空串。"""
    if not base:
        return ""
    return os.path.join(base, *parts) if os.path.isabs(base) else base


# ── JDK ──
# 单机版若依（R1–R5、R7、R10）用 JDK8；Spring Boot 3 系列（R5/R6/R8/R9/R11）用 JDK17。
JDK8_HOME = get("JDK8", r"D:\develop\java-se-8u44-ri")
JDK17_HOME = get("JDK17", r"D:\develop\jdk-17.0.0.1")
JAVA8 = os.path.join(JDK8_HOME, "bin", "java.exe")
JAVA17 = os.path.join(JDK17_HOME, "bin", "java.exe")

# ── 构建工具 ──
MVN_HOME = get("MVN", r"D:\tools\apache-maven-3.9.12")
MVN_CMD = os.path.join(MVN_HOME, "bin", "mvn.cmd")

# ── Python（脚本自身用的解释器） ──
# 默认取当前进程的解释器 —— 用错解释器是新手最常踩的坑（缺依赖 → ModuleNotFoundError）
PYTHON = get("PYTHON", sys.executable)

# ── 数据库 / 中间件 ──
MYSQLD = get("MYSQLD", r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqld.exe")
MYSQL_INI = get("MYSQL_INI", os.path.join(ROOT, "mysql", "my.ini"))
REDIS_DIR = get("REDIS_DIR", os.path.join(ROOT, "tools", "redis"))
REDIS_EXE = os.path.join(REDIS_DIR, "redis-server.exe")

# ── 其他工具目录 ──
TOOLS = os.path.join(ROOT, "tools")
NGINX_DIR = os.path.join(ROOT, "nginx")


def missing() -> list[str]:
    """列出当前配置下找不到的关键依赖，供启动前自检。"""
    out = []
    for name, path in (
        ("JDK8", JAVA8),
        ("JDK17", JAVA17),
        ("Maven", MVN_CMD),
        ("mysqld", MYSQLD),
        ("redis-server", REDIS_EXE),
    ):
        if not os.path.exists(path):
            out.append(f"{name}: {path}")
    return out


def explain() -> str:
    """打印当前解析结果，排查「为什么找不到 JDK」时用。"""
    lines = [f"配置文件: {LOCAL_CONF} ({'存在' if os.path.exists(LOCAL_CONF) else '不存在'})", ""]
    for name, path in (
        ("JDK8_HOME", JDK8_HOME),
        ("JDK17_HOME", JDK17_HOME),
        ("JAVA8", JAVA8),
        ("JAVA17", JAVA17),
        ("MVN_CMD", MVN_CMD),
        ("PYTHON", PYTHON),
        ("MYSQLD", MYSQLD),
        ("MYSQL_INI", MYSQL_INI),
        ("REDIS_EXE", REDIS_EXE),
    ):
        ok = "OK  " if os.path.exists(path) else "MISS"
        lines.append(f"  [{ok}] {name:12} = {path}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(explain())
    m = missing()
    if m:
        print("\n[!] 以下依赖找不到，请设置对应环境变量或写 lab.local.json：")
        for x in m:
            print("   ", x)
        sys.exit(1)
    print("\n[OK] 关键依赖齐全")
