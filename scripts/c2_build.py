r"""C2 组件靶场构建器：把 src/C2 下的真实应用构建并投放到 runtime/C2。

为什么需要它
------------
按 docs/靶场总览.md 的目录约定，src/ 与 runtime/ 都不进 git（可重建产物），
C2 的 jar/war 原先靠手工 ``mvn package`` + 复制，换台机器无法复现。
本脚本把「源码 → 可启动产物」收口成一条命令：

    python scripts\c2_build.py              # 构建全部（sba / s4s / scf，含 safe 对照产物）
    python scripts\c2_build.py sba scf      # 只构建指定组件
    python scripts\c2_build.py --deploy-only sba   # 跳过 mvn，只复制现有 target 产物

构建参数与 docs/部署与技术规格.md 保持一致：

    mvn -s maven-settings.xml -Dmaven.repo.local=.m2 clean package -DskipTests

漏洞/安全两套产物（用于盲测「修复后不误报」对拍）：

    C2-1b：sba-client.jar      = gateway 3.1.0（CVE-2022-22947 受影响）
           sba-client-safe.jar = gateway 3.1.1（修复版，配 profile=safe 收敛端点）
    C2-3 ：scf.jar             = spring-cloud-function 3.2.2（CVE-2022-22963 受影响）
           scf-safe.jar        = spring-cloud-function 3.2.5（修复版）
    C2-2 ：ROOT.war            = Spring 5.3.17 原始应用；
           安全模式靠 -Ds4s.hardened=true 打开 @InitBinder 字段黑名单（无需第二份 war）。

构建/部署完成后用 lab 启停脚本拉起对应靶场（c2_sba.py / c2_s4s.py / c2_scf.py）。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import labenv  # noqa: E402

MVN = labenv.MVN_CMD
JDK17_HOME = labenv.JDK17_HOME
REPO_LOCAL = os.path.join(ROOT, ".m2")
SETTINGS = os.path.join(ROOT, "maven-settings.xml")


def _rel(*parts):
    return os.path.join(*parts)


# 组件 -> desc + 构建批次。每个批次 = (pom, 额外 mvn 参数, [(target 产物, runtime 目标)])
COMPONENTS = {
    "sba": {
        "desc": "C2-1 SBA server + 停车网关 client（vuln/safe 两套 jar）",
        "pom": _rel("src", "C2", "sba", "pom.xml"),
        "builds": [
            {
                "args": [],
                "artifacts": [
                    (_rel("src", "C2", "sba", "server", "target", "sba-server.jar"),
                     _rel("runtime", "C2", "sba", "sba-server.jar")),
                    (_rel("src", "C2", "sba", "client", "target", "sba-client.jar"),
                     _rel("runtime", "C2", "sba", "sba-client.jar")),
                ],
            },
            {
                "args": ["-Psafe"],
                "artifacts": [
                    (_rel("src", "C2", "sba", "client", "target", "sba-client-safe.jar"),
                     _rel("runtime", "C2", "sba", "sba-client-safe.jar")),
                ],
            },
        ],
    },
    "s4s": {
        "desc": "C2-2 Spring4Shell（Tomcat 9 + Spring 5.3.17 war）",
        "pom": _rel("src", "C2", "s4s", "pom.xml"),
        "builds": [
            {
                "args": [],
                "artifacts": [
                    (_rel("src", "C2", "s4s", "target", "ROOT.war"),
                     _rel("runtime", "C2", "s4s", "ROOT.war")),
                ],
            },
        ],
    },
    "scf": {
        "desc": "C2-3 Spring Cloud Function（vuln 3.2.2 / safe 3.2.5）",
        "pom": _rel("src", "C2", "scf", "pom.xml"),
        "builds": [
            {
                "args": [],
                "artifacts": [
                    (_rel("src", "C2", "scf", "target", "scf.jar"),
                     _rel("runtime", "C2", "scf", "scf.jar")),
                ],
            },
            {
                "args": ["-Psafe"],
                "artifacts": [
                    (_rel("src", "C2", "scf", "target", "scf-safe.jar"),
                     _rel("runtime", "C2", "scf", "scf-safe.jar")),
                ],
            },
        ],
    },
}

ALIASES = {"C2-1": "sba", "C2-2": "s4s", "C2-3": "scf"}


def build(name, extra_args=None):
    cfg = COMPONENTS[name]
    pom = os.path.join(ROOT, cfg["pom"])
    if not os.path.exists(pom):
        print("[FAIL] %s 源码缺少 pom: %s" % (name, pom))
        return False
    env = dict(os.environ)
    env["JAVA_HOME"] = JDK17_HOME
    env["PATH"] = os.path.join(JDK17_HOME, "bin") + os.pathsep + env.get("PATH", "")
    cmd = [
        MVN,
        "-s", SETTINGS,
        "-Dmaven.repo.local=" + REPO_LOCAL,
        "-f", pom,
    ]
    cmd.extend(extra_args or [])
    cmd.extend(["clean", "package", "-DskipTests", "-B"])
    print("[..] 构建 %s%s" % (name, (" " + " ".join(extra_args)) if extra_args else ""))
    proc = subprocess.run(cmd, cwd=ROOT, env=env)
    if proc.returncode != 0:
        print("[FAIL] %s 构建失败 rc=%s" % (name, proc.returncode))
        return False
    return True


def deploy_artifacts(name, artifacts):
    ok = True
    for src_rel, dst_rel in artifacts:
        src = os.path.join(ROOT, src_rel)
        dst = os.path.join(ROOT, dst_rel)
        if not os.path.exists(src):
            print("[FAIL] %s 构建产物不存在: %s" % (name, src))
            ok = False
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        print("[OK] %s -> %s" % (src_rel, dst_rel))
    return ok


def main():
    args = sys.argv[1:]
    deploy_only = "--deploy-only" in args
    args = [a for a in args if not a.startswith("--")]
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        return 0
    names = []
    for raw in args or list(COMPONENTS):
        key = raw.strip().lower()
        key = ALIASES.get(key.upper(), key)
        if key not in COMPONENTS:
            print("[ERROR] 未知组件: %s（可用: %s）" % (raw, ", ".join(COMPONENTS)))
            return 2
        if key not in names:
            names.append(key)

    failures = []
    for name in names:
        cfg = COMPONENTS[name]
        for build_spec in cfg["builds"]:
            extra = build_spec.get("args") or []
            if not deploy_only and not build(name, extra):
                failures.append(name)
                break
            if not deploy_artifacts(name, build_spec["artifacts"]):
                failures.append(name)
    if failures:
        print("[FAIL] 构建/部署失败: %s" % ", ".join(sorted(set(failures))))
        return 1
    print("[OK] 构建/部署完成: %s" % ", ".join(names))
    return 0


if __name__ == "__main__":
    sys.exit(main())
