r"""把 lab_assets/ 里的「真实感资产」铺到 runtime/ 下。

为什么需要这一层
----------------
靶场里有一类文件不是构建产物、也不是配置，而是**人为造的历史遗留**：
R1 的遗留建库脚本、R7 web 目录里漏删的 .git。它们必须能版本控制（否则重建靶场就没了），
但又不能直接放进 runtime/：

1. R7 的诱饵就是个 `.git` 目录，放进 runtime/ 会被外层仓库当成 submodule
   （实测报 `adding embedded git repository` / `fatal: bad object HEAD`）；
2. runtime/ 是"可由构建脚本重建"的产物目录，往里掺人为资产会让"重建"语义变模糊。

所以资产统一放顶层 `lab_assets/`，由本脚本铺过去。`lab.py up` 会自动调用，
单独重铺也可以：

    python scripts\lab_assets.py           # 铺全部
    python scripts\lab_assets.py R1 R7     # 只铺指定站
    python scripts\lab_assets.py --check   # 只检查是否已就位，不写盘（供 verify 用）

映射关系写在 ASSETS 表里，加新资产只改这里。
"""

from __future__ import annotations

import os
import shutil
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_ROOT = os.path.join(ROOT, "lab_assets")

# site -> [(资产子目录, 目标相对 runtime/site 的路径, 说明)]
ASSETS: dict[str, list[tuple[str, str, str]]] = {
    "R1": [
        (
            "R1-static-extra",
            "static-extra",
            "运维遗留的建库脚本（/docs/** 在 Shiro 匿名清单里，所以真实可匿名下载）",
        ),
    ],
    "R7": [
        (
            "R7-ui-dotgit",
            os.path.join("ui", ".git"),
            "前端构建时漏删的 .git（Nginx 根路径直出静态文件，匿名可读）",
        ),
    ],
}


def _walk_files(src: str) -> list[str]:
    out = []
    for base, _dirs, files in os.walk(src):
        for f in files:
            full = os.path.join(base, f)
            out.append(os.path.relpath(full, src))
    return out


def _copy_tree(src: str, dst: str) -> int:
    """把 src 整棵树覆盖到 dst，返回复制的文件数。"""
    n = 0
    for rel in _walk_files(src):
        s = os.path.join(src, rel)
        d = os.path.join(dst, rel)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copy2(s, d)
        n += 1
    return n


def is_ready(site: str) -> bool:
    """资产是否已铺好（文件齐全 + 大小一致）。"""
    for sub, rel, _desc in ASSETS.get(site, []):
        src = os.path.join(ASSETS_ROOT, sub)
        dst = os.path.join(ROOT, "runtime", site, rel)
        if not os.path.isdir(src):
            return False
        for rel_f in _walk_files(src):
            s = os.path.join(src, rel_f)
            d = os.path.join(dst, rel_f)
            if not os.path.exists(d) or os.path.getsize(s) != os.path.getsize(d):
                return False
    return True


def apply(site: str, verbose: bool = True) -> bool:
    items = ASSETS.get(site)
    if not items:
        if verbose:
            print(f"[SKIP] {site} 无真实感资产")
        return True
    for sub, rel, desc in items:
        src = os.path.join(ASSETS_ROOT, sub)
        dst = os.path.join(ROOT, "runtime", site, rel)
        if not os.path.isdir(src):
            print(f"[FAIL] {site}: 资产目录不存在 {src}")
            return False
        n = _copy_tree(src, dst)
        if verbose:
            print(f"[OK] {site}: {n} 个文件 → runtime/{site}/{rel}  （{desc}）")
    return True


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    check_only = "--check" in sys.argv

    sites = [a.upper() for a in args] or list(ASSETS)

    unknown = [s for s in sites if s not in ASSETS]
    if unknown:
        print(f"[ERROR] 未知站点: {', '.join(unknown)}")
        print(f"        可用: {', '.join(ASSETS)}")
        return 1

    if check_only:
        bad = [s for s in sites if not is_ready(s)]
        if bad:
            for s in bad:
                print(f"[MISS] {s} 真实感资产未就位，跑 `python scripts\\lab_assets.py {s}`")
            return 1
        print(f"[OK] {len(sites)} 座站的真实感资产已就位")
        return 0

    failed = [s for s in sites if not apply(s)]
    if failed:
        print(f"[FAIL] 铺设失败: {', '.join(failed)}")
        return 1
    print(f"[OK] 完成（{len(sites)} 座站）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
