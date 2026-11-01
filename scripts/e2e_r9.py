"""R9 演示站点 E2E 实测：登录 -> 首页看板 -> 四个业务页面 -> 搜索/分页。

只看 DOM 文本与元素数量，不依赖截图。
"""
import sys
import time
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:19109"
errors = []


def hook(pg):
    pg.on("pageerror", lambda e: errors.append("[pageerror] %s" % str(e)[:200]))
    pg.on("console", lambda m: errors.append("[console.%s] %s" % (m.type, m.text[:160])) if m.type == "error" else None)


def row_count(pg):
    return pg.locator(".el-table__body-wrapper tbody tr").count()


def total_text(pg):
    """分页组件的总条数文本"""
    loc = pg.locator(".el-pagination__total")
    return loc.inner_text() if loc.count() else "(无分页)"


def wait_table(pg, timeout=15000):
    try:
        pg.wait_for_selector(".el-table__row", timeout=timeout)
        return True
    except Exception:
        return False


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        pg = b.new_page(viewport={"width": 1600, "height": 950})
        hook(pg)

        # ---------- 登录 ----------
        pg.goto(BASE + "/", wait_until="domcontentloaded", timeout=30000)
        pg.wait_for_timeout(3000)
        print("登录页标题:", pg.title())
        pg.locator("input[placeholder='用户名']").first.fill("admin")
        pg.locator("input[placeholder='密码']").first.fill("admin123")
        [e for e in pg.locator("button").all() if "登" in (e.inner_text() or "")][0].click()
        pg.wait_for_timeout(6000)
        print("登录后 URL:", pg.url)
        if "/login" in pg.url:
            print("!! 登录失败，终止")
            for e in errors[:10]:
                print(" ", e)
            b.close()
            return

        # ---------- 首页看板 ----------
        print("\n=== 首页看板 ===")
        pg.wait_for_timeout(3000)
        cards = pg.locator(".stat-card, .el-card")
        print("卡片数:", cards.count())
        # 统计数字：找 28px 大字
        nums = pg.evaluate("""() => {
            const out = [];
            document.querySelectorAll('div,span').forEach(e => {
                const fs = parseFloat(getComputedStyle(e).fontSize);
                if (fs >= 24 && e.children.length === 0 && e.innerText && e.innerText.trim().length < 12) out.push(e.innerText.trim());
            });
            return out.slice(0, 8);
        }""")
        print("大号数字:", nums)
        canvases = pg.locator("canvas").count()
        print("图表 canvas 数量:", canvases, "(期望 >= 3)")
        print("首页是否含'运行看板':", "运行看板" in pg.inner_text("body"))

        # ---------- 四个业务页面 ----------
        pages = [
            ("设备台账", "/inspect/device", "设备编号", 68),
            ("巡检记录", "/inspect/record", "记录编号", 450),
            ("缺陷工单", "/inspect/defect", "工单号", 72),
            ("巡检计划", "/inspect/plan", "计划编号", 12),
        ]
        for name, path, keyword, expect_total in pages:
            print("\n=== %s (%s) ===" % (name, path))
            pg.goto(BASE + path, wait_until="domcontentloaded", timeout=30000)
            pg.wait_for_timeout(4000)
            ok = wait_table(pg)
            print("表格渲染:", ok, "| 当前页行数:", row_count(pg))
            print("分页总数:", total_text(pg))
            headers = pg.locator(".el-table__header-wrapper th").all_inner_texts()
            print("列头:", [h.strip() for h in headers if h.strip()][:9])
            print("页面是否含关键字 '%s':" % keyword, keyword in pg.inner_text("body"))

        # ---------- 缺陷工单：待处理筛选 + 红底 ----------
        print("\n=== 缺陷工单：只看待处理 ===")
        pg.goto(BASE + "/inspect/defect", wait_until="domcontentloaded", timeout=30000)
        pg.wait_for_timeout(3500)
        # 找到状态下拉（第三个 select 一般就是状态）
        sels = pg.locator(".el-select")
        print("下拉框数量:", sels.count())
        # 直接改 URL 带参数验证后端过滤
        pg.goto(BASE + "/inspect/defect?status=0", wait_until="domcontentloaded", timeout=30000)
        pg.wait_for_timeout(4000)
        print("带 status=0 时总条数:", total_text(pg))
        warn_rows = pg.locator(".el-table__row.warning-row").count()
        print("红底行数(warning-row):", warn_rows)

        # ---------- 设备台账搜索 ----------
        print("\n=== 设备台账搜索 '锅炉' ===")
        pg.goto(BASE + "/inspect/device", wait_until="domcontentloaded", timeout=30000)
        pg.wait_for_timeout(3500)
        inputs = pg.locator(".el-form input")
        print("搜索框数量:", inputs.count())
        if inputs.count() >= 2:
            inputs.nth(1).fill("锅炉")
            btn = pg.locator(".el-form button:has-text('搜索')")
            if btn.count():
                btn.first.click()
                pg.wait_for_timeout(3500)
                print("搜索后总条数:", total_text(pg), "| 行数:", row_count(pg))

        # ---------- 控制台错误 ----------
        print("\n=== 控制台错误 ===")
        if errors:
            for e in errors[:12]:
                print(" ", e)
        else:
            print("无")
        b.close()


if __name__ == "__main__":
    main()
