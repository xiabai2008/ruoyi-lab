# -*- coding: utf-8 -*-
"""把 R10（JeecgBoot 3.6.3）漏洞演示模块铺进 src/R10 源码树。

为什么要有这个脚本
==================
本仓库 .gitignore 把 src/*（上游源码检出，4.9G）排除在版本控制之外，
R10 的二开源码因此不随仓库发布。为了让新增的「漏洞演示模块」可复现，
Java 实现跟踪在 lab_src/R10_jeecg_vuln/ 下，由本脚本安装到：

  src/R10/jeecg-module-system/jeecg-system-biz/src/main/java/org/jeecg/modules/lab/
  src/R10/jeecg-module-system/jeecg-system-biz/src/main/resources/lab/

该模块会被打进 jeecg-system-start fat jar（system-biz 是 start 的依赖）。

用法：
  python scripts\r10_vuln_install.py           # 安装 / 覆盖
  python scripts\r10_vuln_install.py --check   # 只比对，不修改（CI/验收用）
"""
import argparse
import hashlib
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_ROOT = os.path.join(ROOT, "lab_src", "R10_jeecg_vuln")
DST_ROOT = os.path.join(
    ROOT, "src", "R10", "jeecg-module-system", "jeecg-system-biz", "src", "main"
)

# lab_src 下的子目录 -> src/R10 下 main 目录
TARGETS = [
    ("java", "java"),
    ("resources", "resources"),
]


def collect(source_dir):
    """返回 {相对路径: 绝对路径}"""
    files = {}
    for dirpath, _, filenames in os.walk(source_dir):
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, source_dir)
            files[rel] = full
    return files


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description="安装 R10 JeecgBoot 漏洞演示模块")
    parser.add_argument("--check", action="store_true", help="只比对差异，不写文件")
    args = parser.parse_args()

    if not os.path.isdir(SRC_ROOT):
        print("[ERROR] 模块源目录不存在: %s" % SRC_ROOT)
        return 1
    if not os.path.isdir(os.path.join(ROOT, "src", "R10")):
        print("[ERROR] R10 源码树不存在: %s" % os.path.join(ROOT, "src", "R10"))
        print("        先按 docs/部署与技术规格.md 拉取 JeecgBoot 3.6.3 到 src/R10")
        return 1

    installed, same, changed = [], [], []
    for src_name, dst_name in TARGETS:
        source_dir = os.path.join(SRC_ROOT, src_name)
        if not os.path.isdir(source_dir):
            continue
        for rel, source in sorted(collect(source_dir).items()):
            target = os.path.join(DST_ROOT, dst_name, rel)
            status_ok = os.path.isfile(target) and sha256(target) == sha256(source)
            if status_ok:
                same.append(os.path.relpath(target, ROOT))
                continue
            if args.check:
                changed.append(os.path.relpath(target, ROOT))
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(source, target)
            installed.append(os.path.relpath(target, ROOT))

    print("=" * 70)
    print("R10 JeecgBoot 漏洞演示模块安装器")
    print("=" * 70)
    if args.check:
        if changed:
            print("[FAIL] 以下文件与 lab_src 源不一致（需重新安装）:")
            for path in changed:
                print("   - %s" % path)
            return 1
        print("[OK] %d 个文件已就位且内容一致" % len(same))
        return 0

    for path in installed:
        print("[OK] 已安装 %s" % path)
    if not installed:
        print("[OK] 所有文件已是最新（%d 个）" % len(same))
    else:
        print("-" * 70)
        print("已更新 %d 个文件（其余 %d 个未变化）" % (len(installed), len(same)))
    print()
    print("下一步：重新构建 R10（在仓库根执行）")
    print("  mvn.cmd -s maven-settings.xml -Dmaven.repo.local=.m2 "
          "-pl jeecg-module-system/jeecg-system-start -am clean package -DskipTests")
    print("  （工作目录 src\\R10；产物 target\\jeecg-system-start-3.6.3.jar 复制到 build\\R10\\）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
