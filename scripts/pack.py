r"""打包最小演示集，拷到另一台电脑也能跑。

    python scripts\\pack.py                 # 打包 R1（默认，演示最常用的那座）
    python scripts\\pack.py R1 R11 C3       # 打包多座
    python scripts\\pack.py --out E:\\lab    # 指定输出目录

为什么不能直接复制整个文件夹
============================
工程有 11G（src 5.2G / build 2.2G / runtime 1.9G），而且有两处**复制不过去**的
东西 —— 这两条都是实测出来的，不是推测：

1. **MySQL 数据目录不在文件夹里。** `mysql/my.ini` 写的
   `datadir=C:/Users/HZR/ry_r2_mysql/data`，而 `C:/Users/HZR/ry_r2_mysql`
   是一个 junction（目录联接）指向工程内的 `mysql/`。复制文件夹时 junction
   不会被复制 —— 新机器上 MySQL 起不来，所有业务表全丢。

2. **JDK / Maven / mysqld 装在工程外面。** `lab.local.json` 里全是本机绝对路径
   （`D:/develop/java-se-8u44-ri`、`D:/tools/Python 3.12.9/python.exe`）。
   新机器上这些路径不存在，lab.py 直接报「找不到」。

所以本脚本做三件事：**只挑运行必需的文件**、**把路径改写成相对/可推导的**、
**现场生成一份新的 lab.local.json**。

包里的 save/load 两个命令负责「到了新机器再自愈一次」
====================================================
路径改写不能只在本机做 —— 新机器的工程根路径必然不同。
所以打包时写入一个 `pack_manifest.json` 记录每个文件的原始绝对路径，
到新机器上跑 `python scripts\pack.py --unpack` 时按新根路径重新算一遍。

输出
====
    <out>/lab-demo/
    ├─ START-HERE.bat        双击：自愈路径 + 启动 + 开浏览器
    ├─ pack_manifest.json    打包清单与原始路径（--unpack 用）
    ├─ scripts/              lab.py 等启停脚本
    ├─ build/<site>/         jar
    ├─ runtime/<site>/       配置与静态资源（剔除日志）
    ├─ nginx/                exe + conf + html（剔除 logs）
    ├─ tools/redis/          redis-server.exe
    └─ README-打包说明.md
"""

from __future__ import annotations

import json
import os
import shutil
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 每座站点运行必需的文件（相对工程根）。
# jar 在 build/，配置与静态资源在 runtime/，nginx 一个站一个 conf。
SITE_FILES: dict[str, list[str]] = {
    "R1": [
        "build/R1/ruoyi-admin.jar",
        "runtime/R1/application-prod.yml",
        "runtime/R1/logback.xml",
        "nginx/conf.d/R1.conf",
    ],
    "R11": [
        "build/R11/internal-api.jar",
        "nginx/conf.d/R11.conf",
    ],
    "C3": [
        "nginx/conf.d/C3.conf",
    ],
}

# 整目录拷贝（剔除日志与构建中间产物）
DIR_INCLUDES = [
    "scripts",            # 启停脚本，全部按 ROOT 相对定位
    "nginx/conf",         # nginx 主配置
    "nginx/html",         # 错误页
    "nginx/contrib",      # nginx.exe 依赖
    "nginx/docs",
    "tools/redis",        # Redis 自带，不用另装
    "lab_assets",         # 真实感诱饵（遗留 SQL、漏删的 .git）
    "seed",
    "db",
]

# 逐文件包含（体积可控、缺了就跑不起来的）
FILE_INCLUDES = [
    # nginx.exe 是单文件、无额外 dll，但**必须**打包 —— 漏了它 lab.py 起不来入口。
    # 首版只包含了 nginx/conf、conf.d、html、contrib、docs，恰恰漏了本体。
    "nginx/nginx.exe",
    "lab.local.json.example",
    "README.md",
    "LICENSE",
]

# 这些后缀/目录名不打包
EXCLUDE_DIRS = {"__pycache__", ".git", ".state", "node_modules", ".pytest_cache"}
EXCLUDE_SUFFIX = {".log", ".pyc", ".pyo", ".tmp", ".bak", ".bak2"}
# 日志目录整个剔除（runtime/R1/logs 实测 1.1G、nginx/logs 572M，全是历史日志）
EXCLUDE_DIR_NAMES = {"logs"}


def _skip(path: str) -> bool:
    parts = path.replace("\\", "/").split("/")
    if any(p in EXCLUDE_DIRS for p in parts):
        return True
    if any(p in EXCLUDE_DIR_NAMES for p in parts):
        return True
    return os.path.splitext(path)[1].lower() in EXCLUDE_SUFFIX


def _copy_tree(src: str, dst: str, copied: list, skipped: list) -> None:
    for base, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and d not in EXCLUDE_DIR_NAMES]
        for fn in files:
            sp = os.path.join(base, fn)
            rel = os.path.relpath(sp, ROOT).replace("\\", "/")
            if _skip(rel):
                skipped.append(rel)
                continue
            dp = os.path.join(dst, rel)
            os.makedirs(os.path.dirname(dp), exist_ok=True)
            shutil.copy2(sp, dp)
            copied.append(rel)


def _write_portable_my_ini(pack: str) -> str:
    """生成 portable my.ini：datadir 用绝对路径但指向包内，basedir 留空由系统推导。

    为什么要生成新的而不是复制：原 my.ini 写死了 C:/Users/HZR 和
    C:/Program Files/MySQL/MySQL Server 8.0。新机器上用户名可能不同、
    MySQL 安装路径也可能不同 —— 两者都会让 mysqld 起不来。
    """
    mysql_dir = os.path.join(pack, "mysql")
    data_dir = os.path.join(mysql_dir, "data").replace("\\", "/")
    ini = f"""[mysqld]
# 由 scripts/pack.py 生成：datadir 指向包内，不依赖原机器路径。
# basedir 刻意不写 —— 让 mysqld 用自己所在的安装目录推导，换机器不用改。
datadir={data_dir}
port=13307
character-set-server=utf8mb4
collation-server=utf8mb4_general_ci
pid-file={mysql_dir.replace(chr(92), "/")}/mysql.pid
log-error={mysql_dir.replace(chr(92), "/")}/mysql-error.log

[client]
port=13307
default-character-set=utf8mb4
"""
    os.makedirs(mysql_dir, exist_ok=True)
    p = os.path.join(mysql_dir, "my.ini")
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(ini)
    return p


def build(sites: list[str], out_dir: str) -> int:
    pack = os.path.join(out_dir, "lab-demo")
    if os.path.exists(pack):
        print(f"[!] {pack} 已存在，先删除再打包（避免新旧文件混在一起）")
        shutil.rmtree(pack)
    os.makedirs(pack, exist_ok=True)

    copied: list[str] = []
    skipped: list[str] = []
    missing: list[str] = []

    # 1. 站点必需文件
    for site in sites:
        for rel in SITE_FILES.get(site, []):
            sp = os.path.join(ROOT, rel.replace("/", os.sep))
            if not os.path.exists(sp):
                missing.append(rel)
                continue
            dp = os.path.join(pack, rel.replace("/", os.sep))
            os.makedirs(os.path.dirname(dp), exist_ok=True)
            shutil.copy2(sp, dp)
            copied.append(rel)

    # 2. 整目录
    for rel in DIR_INCLUDES:
        sp = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.isdir(sp):
            missing.append(rel + "/")
            continue
        _copy_tree(sp, pack, copied, skipped)

    # 3. 单文件
    for rel in FILE_INCLUDES:
        sp = os.path.join(ROOT, rel)
        if os.path.exists(sp):
            shutil.copy2(sp, os.path.join(pack, rel))
            copied.append(rel)

    # 4. MySQL 数据（业务表在这里，缺了整个演示就空了）
    src_data = os.path.join(ROOT, "mysql", "data")
    if os.path.isdir(src_data):
        _copy_tree(src_data, pack, copied, skipped)
    else:
        missing.append("mysql/data/")

    # 5. portable my.ini
    _write_portable_my_ini(pack)
    copied.append("mysql/my.ini")

    # 6. nginx 启动前必须存在的空目录。它们的**内容**是日志（已剔除），
    #    但目录本身缺了 nginx 会启动失败 —— 所以现场建空目录。
    for d in ("nginx/logs", "nginx/temp", "nginx/temp/client_body_temp"):
        os.makedirs(os.path.join(pack, d), exist_ok=True)

    # 7. 清单（记录原始根路径，供 --unpack 重算）
    manifest = {
        "generated_from": ROOT.replace("\\", "/"),
        "sites": sites,
        "file_count": len(copied),
        "files": copied,
        "missing": missing,
        "skipped_count": len(skipped),
    }
    with open(os.path.join(pack, "pack_manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)

    total = sum(
        os.path.getsize(os.path.join(b, f))
        for b, _, fs in os.walk(pack) for f in fs
        if os.path.exists(os.path.join(b, f))
    )
    # 8. 生成新机器上的启动入口（先自愈路径，再起站）
    _write_bootstrap(pack)

    print(f"\n[OK] 打包完成: {pack}")
    print(f"     站点: {', '.join(sites)}")
    print(f"     文件: {len(copied)} 个 | 体积: {total / 1024 / 1024:.0f} MB")
    if missing:
        print(f"     [警告] 缺失 {len(missing)} 项: {', '.join(missing[:5])}")
    if skipped:
        print(f"     已剔除 {len(skipped)} 个日志/临时文件（不含在体积内）")
    print("\n     拷到新电脑后，双击 START-HERE.bat 即可。")
    return 0


def _write_bootstrap(pack: str) -> None:
    """生成 START-HERE.bat：第一次运行时自愈路径，然后启动。"""
    bat = r"""@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title R1 lab

echo ============================================================
echo   R1 lab - first run will fix paths for this machine
echo ============================================================
echo.

REM 自愈：把 my.ini 的 datadir、lab.local.json 的外部依赖路径
REM 按这台机器的实际位置重写一遍。破折号不写注释，用 REM。
if not exist ".packed-ok" (
    echo [1/2] Fixing paths for this machine...
    python scripts\pack.py --unpack
    if errorlevel 1 (
        echo.
        echo [FAIL] Path fix failed. Is Python installed and on PATH?
        echo        Try:  python --version
        pause
        exit /b 1
    )
    > .packed-ok echo ok
) else (
    echo [1/2] Paths already fixed.
)

echo.
echo [2/2] Starting R1...
python scripts\lab.py up R1
if errorlevel 1 (
    echo.
    echo [FAIL] Start failed - see output above.
    pause
    exit /b 1
)

echo.
echo   R1 is ready: http://127.0.0.1:19101   (admin / admin123)
start "" "http://127.0.0.1:19101"
echo.
echo   Closing this window does NOT stop the lab.
echo   To stop: python scripts\lab.py down R1
pause
"""
    p = os.path.join(pack, "START-HERE.bat")
    with open(p, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write(bat)


def unpack() -> int:
    """在目标机器上重算路径。由 START-HERE.bat 首次运行时调用。

    要修两处：
      1. mysql/my.ini 的 datadir/pid-file/log-error —— 指向本包实际位置
      2. lab.local.json —— JDK/Maven/Python/mysqld 按本机常见位置探测

    为什么必须在新机器上重算而不是打包时写死：包被拷到哪里事先不知道，
    用户可能放在 D:\\、E:\\、桌面或任意子目录。
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ok = True

    # 1) my.ini
    ini = os.path.join(root, "mysql", "my.ini")
    mysql_dir = os.path.join(root, "mysql").replace("\\", "/")
    with open(ini, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(
            "[mysqld]\n"
            "# 由 pack.py --unpack 按本机位置重写\n"
            f"datadir={mysql_dir}/data\n"
            "port=13307\n"
            "character-set-server=utf8mb4\n"
            "collation-server=utf8mb4_general_ci\n"
            f"pid-file={mysql_dir}/mysql.pid\n"
            f"log-error={mysql_dir}/mysql-error.log\n"
            "\n[client]\nport=13307\ndefault-character-set=utf8mb4\n"
        )
    print(f"  [OK] mysql/my.ini -> {mysql_dir}/data")

    # 2) lab.local.json —— 探测本机常见安装位置
    def find(cands: list[str], verify=None) -> str:
        for c in cands:
            if c and os.path.exists(c) and (verify is None or verify(c)):
                return c.replace("\\", "/")
        return ""

    def is_java8(home: str) -> bool:
        """必须是 Java 8，不能是 17/21/25 之类。

        为什么要校验：JAVA_HOME 经常指向任意版本（实测本机指向 VS Code 自带的
        JDK 25）。R1 是若依 4.5.1，只能跑 JDK8 —— 用高版本启动会直接失败，
        而错误信息（UnsupportedClassVersionError 或诡异的启动异常）很难让人
        联想到"JDK 版本选错了"。所以这里读 release 文件确认版本号。
        """
        rel = os.path.join(home, "release")
        try:
            with open(rel, encoding="utf-8", errors="replace") as fh:
                txt = fh.read()
        except OSError:
            return False
        return 'JAVA_VERSION="1.8' in txt or '"1.8.0' in txt

    jdk8 = find([
        r"D:\develop\java-se-8u44-ri",
        r"C:\Program Files\Java\jdk1.8.0_202",
        r"C:\Program Files\Java\jdk1.8.0_201",
        r"C:\Program Files\Java\jdk-8",
        r"C:\Java\jdk8",
        # 环境变量放最后，且必须验版本 —— 它可能指向任何 JDK
        os.environ.get("JAVA_HOME", ""),
    ], verify=is_java8)
    mysqld = find([
        r"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqld.exe",
        r"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqld.exe",
        r"D:\Program Files\MySQL\MySQL Server 8.0\bin\mysqld.exe",
    ])
    # 找真正的系统 Python：sys.executable 可能指向某个项目的 venv
    # （实测会指到别的仓库的 .venv），换机器后那个 venv 不存在，脚本就崩。
    def find_python() -> str:
        import glob

        cands: list[str] = []
        la = os.environ.get("LOCALAPPDATA", "")
        if la:
            # python.org 安装器默认装到 %LOCALAPPDATA%\Programs\Python\Python3XX
            cands.extend(sorted(glob.glob(os.path.join(la, "Programs", "Python", "Python3*", "python.exe")),
                                reverse=True))
        cands.extend(sorted(glob.glob(r"C:\Python3*\python.exe"), reverse=True))
        for c in cands:
            # 只排除 venv/virtualenv（换机器必失效），不排除用户目录 ——
            # python.org 默认就装在 C:\Users\<user>\AppData\Local 下，
            # 之前误把 USERPROFILE 前缀当排除条件，把正常安装也排掉了。
            low = c.lower()
            if f"{os.sep}venv{os.sep}" in low or f"{os.sep}.venv{os.sep}" in low:
                continue
            return c.replace("\\", "/")
        # 兜底：当前解释器。若它在 venv 里，换机器后可能失效。
        return sys.executable.replace("\\", "/")

    conf = {
        "_comment": "由 pack.py --unpack 按本机位置生成。缺的项请手工补齐。",
        "JDK8": jdk8,
        "MYSQLD": mysqld,
        "PYTHON": find_python(),
    }
    with open(os.path.join(root, "lab.local.json"), "w", encoding="utf-8") as fh:
        json.dump(conf, fh, ensure_ascii=False, indent=2)
    print(f"  [OK] lab.local.json -> JDK8={jdk8 or '未找到'}")

    if not jdk8:
        print("  [警告] 没找到 JDK8，R1 无法启动。请安装 JDK8 后手工填 lab.local.json")
        ok = False
    if not mysqld:
        print("  [警告] 没找到 mysqld，MySQL 无法启动。请安装 MySQL 8 后手工填")
        ok = False
    return 0 if ok else 1


def main() -> int:
    if "--unpack" in sys.argv:
        return unpack()

    # 手写解析：--out 的值是路径，不能被当成站点名
    out_dir = os.path.dirname(ROOT)
    positional: list[str] = []
    raw = sys.argv[1:]
    i = 0
    while i < len(raw):
        if raw[i] == "--out" and i + 1 < len(raw):
            out_dir = raw[i + 1]
            i += 2
            continue
        if not raw[i].startswith("--"):
            positional.append(raw[i])
        i += 1

    sites = [a.upper() for a in positional] or ["R1"]
    unknown = [s for s in sites if s not in SITE_FILES]
    if unknown:
        print(f"[ERROR] 未知站点: {', '.join(unknown)}")
        print(f"        可用: {', '.join(SITE_FILES)}")
        return 2
    return build(sites, out_dir)


if __name__ == "__main__":
    sys.exit(main())
