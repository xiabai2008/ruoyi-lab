r"""README 展示截图 —— 用 Playwright 打开代表性靶场，拍真实运行画面。

    python scripts\shots.py

为什么要有这个脚本
==================
README 里的截图如果靠人手截，改一次站点就得重拍一遍，且没人记得当时拍了哪几张。
这里把「拍谁、拍什么、存到哪」固化下来，随时可重现。

选站原则：**每个测什么维度，就选一个代表**
- R1  版本曲线起点（若依官方原版形态，保留原版 favicon 作基线）
- R10 变体识别（JeecgBoot 品牌化后台，界面差异最大）
- D1  二开变形（context-path 改写 + 换皮，官方特征全无）
- C3  假漏洞蜜罐（诱饵页面长得像漏洞）

输出：docs/shots/*.png，同时生成 docs/shots/INDEX.md 记录来源与拍摄时间。
"""

from __future__ import annotations

import datetime as _dt
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "shots")

# README 会被整包 clone，图太大 clone 就慢。1280px 宽在 README 里已经足够看清表单，
# 再宽对阅读没有收益，只多花流量。
MAX_WIDTH = 1280
# 超过这个尺寸就改用有损编码。登录页是对角渐变的照片型内容，
# PNG 压不动（实测 1280px 无损仍 950KB），JPEG q85 只要 115KB 且看不出差别。
PHOTO_BYTES = 300 * 1024

# (文件名, URL, 说明, 是否需要整页)
SHOTS: list[tuple[str, str, str, bool]] = [
    ("r1-login.png",       "http://127.0.0.1:19101/login",                    "R1 若依 4.5.1 单机版登录页（藤县人民医院）", False),
    ("r10-login.png",      "http://127.0.0.1:19110/jeecg-boot/",               "R10 JeecgBoot 3.6.3 登录页（星图报表）", False),
    ("d1-login.png",       "http://127.0.0.1:19321/portal/auth/signin",        "D1 若依 4.6.2 二开登录页（改写 context-path 与登录路径）", False),
    ("c3-index.png",       "http://127.0.0.1:19331/",                          "C3 蜜罐首页", False),
    ("c3-git-config.png",  "http://127.0.0.1:19331/.git/config",               "C3 假 .git/config —— 返回 200，内容是编造的", False),
    ("c3-druid.png",       "http://127.0.0.1:19331/druid/index.html",          "C3 假 Druid 监控台 —— 看着像未授权访问", False),
    ("c3-env.png",         "http://127.0.0.1:19331/actuator/env",              "C3 假 actuator/env —— 诱饵属性", False),
]


def _shrink(path: str) -> tuple[str, int]:
    """把截图压到 README 尺寸，返回 (最终路径, 原始字节数)。

    分两步：先缩宽到 MAX_WIDTH；仍超 PHOTO_BYTES 的说明是渐变/照片型内容，
    PNG 压不动，转 JPEG。纯色块的表格/代码截图留着 PNG 更清晰也更小。
    """
    size = os.path.getsize(path)
    try:
        from PIL import Image
    except ImportError:
        return path, size  # 没装 Pillow 就保留原图，不影响流程

    im = Image.open(path).convert("RGB")
    if im.width > MAX_WIDTH:
        h = round(im.height * MAX_WIDTH / im.width)
        im = im.resize((MAX_WIDTH, h), Image.LANCZOS)

    im.save(path, "PNG", optimize=True)
    if os.path.getsize(path) > PHOTO_BYTES:
        jpg = os.path.splitext(path)[0] + ".jpg"
        im.save(jpg, "JPEG", quality=85, optimize=True)
        os.remove(path)
        return jpg, size
    return path, size


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[!] 需要 playwright：pip install playwright && playwright install chromium")
        return 1

    os.makedirs(OUT, exist_ok=True)
    ok, fail = 0, []
    shot_files: list[tuple[str, str, str]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        # 2x 采样再缩回 1280，中文字形比 1x 干净得多
        ctx = browser.new_context(viewport={"width": 1280, "height": 800},
                                  device_scale_factor=2,
                                  locale="zh-CN")
        for name, url, desc, full in SHOTS:
            page = ctx.new_page()
            try:
                resp = page.goto(url, wait_until="networkidle", timeout=20000)
                code = resp.status if resp else 0
                page.wait_for_timeout(700)  # 等字体/动画落定
                path = os.path.join(OUT, name)
                page.screenshot(path=path, full_page=full)
                path, raw = _shrink(path)
                final = os.path.getsize(path)
                print(f"  [OK] {os.path.basename(path):<22} {code}  {raw // 1024}KB -> {final // 1024}KB  {desc}")
                shot_files.append((os.path.basename(path), url, desc))
                ok += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  [!!] {name:<22} {type(exc).__name__}: {exc}")
                fail.append(name)
            finally:
                page.close()
        browser.close()

    stamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(os.path.join(OUT, "INDEX.md"), "w", encoding="utf-8") as fh:
        fh.write("# 截图索引\n\n")
        fh.write(f"拍摄时间：{stamp}  \n拍摄方式：`python scripts\\shots.py`（Playwright + Chromium）\n\n")
        fh.write("| 文件 | 站点 | 说明 |\n|---|---|---|\n")
        for actual, url, desc in shot_files:
            fh.write(f"| `{actual}` | `{url}` | {desc} |\n")

    print(f"\n合计 {ok} 张成功 / {len(fail)} 张失败 -> {OUT}")
    return 0 if not fail else 1


if __name__ == "__main__":
    sys.exit(main())
