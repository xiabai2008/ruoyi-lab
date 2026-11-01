# -*- coding: utf-8 -*-
r"""把 D1（RuoYi 4.6.2 二开）漏洞演示模块铺进 src/D1 源码树。

为什么要有这个脚本
==================
本仓库 .gitignore 把 src/*（各站点上游源码检出，4.9G）排除在版本控制之外，
D1 的二开源码因此不随仓库发布。为了让「漏洞版 / safe 双模式」可复现，
Java 实现跟踪在 lab_src/D1_ruoyi_vuln/ 下，由本脚本安装到：

  src/D1/ruoyi-framework/src/main/java/com/ruoyi/framework/lab/LabMode.java
  src/D1/ruoyi-admin/src/main/java/com/ruoyi/web/lab/Lab*Controller.java

同时给 src/D1/ruoyi-framework/.../config/ShiroConfig.java 打一个 3 处的小补丁：
  1) 注入 LabMode；
  2) /lab/status 固定 anon（运行模式自检端点）；
  3) lab.mode=vuln 时把 /openapi/** 加进 Shiro anon 白名单（复刻二开配置疏漏）。

用法：
  python scripts\d1_vuln_install.py            # 安装 / 覆盖
  python scripts\d1_vuln_install.py --check    # 只比对，不修改（CI/验收用）
  python scripts\d1_vuln_install.py --uninstall # 还原源码树（删新增文件 + 恢复 ShiroConfig）
"""
import argparse
import hashlib
import os
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_ROOT = os.path.join(ROOT, "lab_src", "D1_ruoyi_vuln")
D1_ROOT = os.path.join(ROOT, "src", "D1")

# lab_src/java 下的相对路径 -> src/D1 下的目标目录
TARGETS = [
    (os.path.join("com", "ruoyi", "framework", "lab"),
     os.path.join(D1_ROOT, "ruoyi-framework", "src", "main", "java", "com", "ruoyi", "framework", "lab")),
    (os.path.join("com", "ruoyi", "web", "lab"),
     os.path.join(D1_ROOT, "ruoyi-admin", "src", "main", "java", "com", "ruoyi", "web", "lab")),
]

SHIRO_CONFIG = os.path.join(
    D1_ROOT, "ruoyi-framework", "src", "main", "java", "com", "ruoyi", "framework", "config", "ShiroConfig.java"
)
SHIRO_BACKUP = SHIRO_CONFIG + ".lab-orig"

MARK = "[LAB-D1]"
IMPORT_ANCHOR = "import com.ruoyi.framework.shiro.realm.UserRealm;"
IMPORT_LINE = "import com.ruoyi.framework.lab.LabMode;"
SIGNATURE_OLD = "public ShiroFilterFactoryBean shiroFilterFactoryBean(SecurityManager securityManager)"
SIGNATURE_NEW = "public ShiroFilterFactoryBean shiroFilterFactoryBean(SecurityManager securityManager, LabMode labMode)"
CHAIN_ANCHOR = 'filterChainDefinitionMap.put("/register", "anon,captchaValidate");'
CHAIN_BLOCK = """// [LAB-D1] 漏洞演示模块状态端点：只返回运行模式，不涉及业务数据
        filterChainDefinitionMap.put("/lab/status", "anon");
        // [LAB-D1] 二开「内部运维开放接口」：内部运维平台免登录调用。
        //   safe（默认）：不添加任何规则，接口仍走 /** = user 鉴权拦截；
        //   vuln（-Dlab.mode=vuln）：/openapi/** 进 anon 白名单 —— 复刻真实项目
        //   为「免登录对接」把接口路径加进 Shiro 白名单的配置疏漏。
        if (labMode.isVuln())
        {
            filterChainDefinitionMap.put("/openapi/**", "anon");
        }
"""


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def planned_files():
    """返回 [(源文件, 目标文件)]"""
    rows = []
    for rel_src, dst_dir in TARGETS:
        source_dir = os.path.join(SRC_ROOT, "java", rel_src)
        if not os.path.isdir(source_dir):
            continue
        for name in sorted(os.listdir(source_dir)):
            if not name.endswith(".java"):
                continue
            rows.append((os.path.join(source_dir, name), os.path.join(dst_dir, name)))
    return rows


def patch_shiro(text):
    """返回 (新文本, 需要变更的说明列表)；已打过补丁则原样返回。"""
    if MARK in text and SIGNATURE_NEW in text:
        return text, []
    changes = []
    newline = "\r\n" if "\r\n" in text else "\n"
    if IMPORT_LINE not in text:
        if IMPORT_ANCHOR not in text:
            raise RuntimeError("ShiroConfig: 找不到 import 锚点，源码可能已被改动")
        text = text.replace(IMPORT_ANCHOR, IMPORT_LINE + newline + IMPORT_ANCHOR, 1)
        changes.append("import LabMode")
    if SIGNATURE_OLD in text:
        text = text.replace(SIGNATURE_OLD, SIGNATURE_NEW, 1)
        changes.append("inject LabMode")
    if CHAIN_ANCHOR not in text:
        raise RuntimeError("ShiroConfig: 找不到 filterChainDefinitionMap 锚点，源码可能已被改动")
    if MARK not in text:
        # 锚点行后插入（保留文件原有换行风格）
        pos = text.index(CHAIN_ANCHOR) + len(CHAIN_ANCHOR)
        block = newline + CHAIN_BLOCK.replace("\n", newline).rstrip(newline)
        text = text[:pos] + block + text[pos:]
        changes.append("anon whitelist block")
    return text, changes


def read_text(path):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return handle.read()


def write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def main():
    parser = argparse.ArgumentParser(description="安装 D1 RuoYi 漏洞演示模块")
    parser.add_argument("--check", action="store_true", help="只比对差异，不写文件")
    parser.add_argument("--uninstall", action="store_true", help="删除新增 Java 文件并恢复 ShiroConfig")
    args = parser.parse_args()

    if not os.path.isdir(D1_ROOT):
        print("[ERROR] D1 源码树不存在: %s" % D1_ROOT)
        return 1
    if not os.path.isfile(SHIRO_CONFIG):
        print("[ERROR] ShiroConfig 不存在: %s" % SHIRO_CONFIG)
        return 1

    print("=" * 70)
    print("D1 RuoYi 漏洞演示模块安装器")
    print("=" * 70)

    if args.uninstall:
        removed = []
        for _, target in planned_files():
            if os.path.isfile(target):
                os.remove(target)
                removed.append(os.path.relpath(target, ROOT))
        if os.path.isfile(SHIRO_BACKUP):
            shutil.copyfile(SHIRO_BACKUP, SHIRO_CONFIG)
            print("[OK] 已从备份恢复 ShiroConfig: %s" % os.path.relpath(SHIRO_BACKUP, ROOT))
        else:
            print("[WARN] 未找到 ShiroConfig 备份，ShiroConfig 保持现状（可手工去掉 [LAB-D1] 块）")
        for path in removed:
            print("[OK] 已删除 %s" % path)
        return 0

    installed, same, missing = [], [], []
    for source, target in planned_files():
        if os.path.isfile(target) and sha256(target) == sha256(source):
            same.append(os.path.relpath(target, ROOT))
            continue
        if args.check:
            missing.append(os.path.relpath(target, ROOT))
            continue
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copyfile(source, target)
        installed.append(os.path.relpath(target, ROOT))

    original = read_text(SHIRO_CONFIG)
    patched, changes = patch_shiro(original)
    if args.check:
        if missing or patched != original:
            if missing:
                print("[FAIL] 以下 Java 文件未安装/内容不一致：")
                for path in missing:
                    print("   - %s" % path)
            if patched != original:
                print("[FAIL] ShiroConfig 未打补丁或补丁不完整（期望变更：%s）"
                      % (", ".join(changes) if changes else "补丁标记缺失"))
            return 1
        print("[OK] %d 个 Java 文件已就位且内容一致，ShiroConfig 补丁完整" % len(same))
        return 0

    for path in installed:
        print("[OK] 已安装 %s" % path)
    if not installed:
        print("[OK] 所有 Java 文件已是最新（%d 个）" % len(same))
    if patched != original:
        if not os.path.isfile(SHIRO_BACKUP):
            with open(SHIRO_BACKUP, "w", encoding="utf-8", newline="") as handle:
                handle.write(original)
            print("[OK] 已备份原始 ShiroConfig -> %s" % os.path.relpath(SHIRO_BACKUP, ROOT))
        write_text(SHIRO_CONFIG, patched)
        print("[OK] 已给 ShiroConfig 打补丁：%s" % ", ".join(changes))
    else:
        print("[OK] ShiroConfig 补丁已存在")
    print("-" * 70)
    print("下一步：重新构建 D1（在仓库根执行，工作目录 src\\D1）")
    print("  ..\\..\\mvn.cmd -s ..\\..\\maven-settings.xml -Dmaven.repo.local=..\\..\\.m2 "
          "clean package -DskipTests")
    print("  产物 ruoyi-admin/target/ruoyi-admin.jar 复制到 build\\D1\\")
    return 0


if __name__ == "__main__":
    sys.exit(main())
