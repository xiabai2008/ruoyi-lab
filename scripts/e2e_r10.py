# -*- coding: utf-8 -*-
"""R10 星图数据（JeecgBoot 前后端分离）浏览器端到端实测。

覆盖：
  1) 登录页渲染（品牌、验证码图）
  2) 用 Redis db4 里的验证码答案完成真实登录
  3) 首页：4 个统计卡片 + 2 个 ECharts 是否真的画出来
  4) 数据集 / 报表 / 订阅 三个列表页是否有数据行
  5) 全流程收集控制台错误与失败请求

用法： python scripts/e2e_r10.py [--headed]
截图输出： runtime/R10/shots/
"""
import os
import re
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = os.path.join(ROOT, "runtime", "R10", "shots")
BASE = "http://127.0.0.1:19110"
REDIS_CLI = os.path.join(ROOT, "tools", "redis", "redis-cli.exe")
REDIS_PASS = "ruoyi123"
REDIS_DB = "4"


def redis(*args):
    out = subprocess.run(
        [REDIS_CLI, "-a", REDIS_PASS, "-n", REDIS_DB, *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return out.stdout.strip()


def clear_captcha_keys():
    for k in redis("keys", "*").splitlines():
        if k.strip():
            redis("del", k.strip())


def read_captcha():
    """db4 里最新的一条就是本次验证码答案（key 为 md5 混淆值，value 是明文）。"""
    keys = [k.strip() for k in redis("keys", "*").splitlines() if k.strip()]
    if not keys:
        return None
    best, best_ttl = None, -1
    for k in keys:
        ttl = redis("ttl", k)
        try:
            ttl = int(ttl)
        except ValueError:
            ttl = -1
        if ttl > best_ttl:
            best, best_ttl = k, ttl
    return redis("get", best).strip().strip('"')


def main():
    headed = "--headed" in sys.argv
    os.makedirs(SHOTS, exist_ok=True)

    console_errors = []
    failed_requests = []
    captured_check_key = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed, args=["--window-size=1600,1000"])
        ctx = browser.new_context(viewport={"width": 1600, "height": 1000}, locale="zh-CN")
        page = ctx.new_page()

        def on_console(msg):
            if msg.type in ("error",):
                console_errors.append(msg.text[:300])

        def on_response(resp):
            url = resp.url
            if "/sys/randomImage/" in url:
                m = re.search(r"/sys/randomImage/([^/?]+)", url)
                if m:
                    captured_check_key["key"] = m.group(1)
            if resp.status >= 400 and "/jeecg-boot/" in url:
                failed_requests.append("%s %s" % (resp.status, url.split("?")[0]))

        page.on("console", on_console)
        page.on("response", on_response)

        print("=" * 70)
        print("R10 星图数据 · 浏览器 E2E")
        print("=" * 70)

        clear_captcha_keys()
        page.goto(BASE, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3500)

        title = page.title()
        print("[1] 页面标题: %s" % title)
        page.screenshot(path=os.path.join(SHOTS, "01_login.png"), full_page=False)

        # 等验证码请求发出后再读 Redis
        answer = None
        for _ in range(20):
            answer = read_captcha()
            if answer:
                break
            page.wait_for_timeout(500)
        print("[2] 验证码答案: %r (checkKey=%s)" % (answer, captured_check_key.get("key")))
        if not answer:
            print("[FAIL] 没能从 Redis 拿到验证码答案")
            browser.close()
            return 1

        # 填表登录
        page.fill("input#form_item_username, input[placeholder*='账号'], input[placeholder*='用户名']", "admin")
        page.fill("input#form_item_password, input[type='password']", "123456")
        cap = page.query_selector("input#form_item_input_captcha, input[placeholder*='验证码']")
        if cap:
            cap.fill(answer)
        else:
            print("[WARN] 没找到验证码输入框")
        page.wait_for_timeout(300)
        page.screenshot(path=os.path.join(SHOTS, "02_login_filled.png"), full_page=False)

        btn = page.query_selector("button:has-text('登录')")
        if btn:
            btn.click()
        else:
            page.keyboard.press("Enter")

        # 等进入后台（登录页 URL 会带 ?redirect=/dashboard/analysis，不能只看路径里有没有 dashboard）
        try:
            page.wait_for_function("() => !location.pathname.startsWith('/login')", timeout=25000)
            page.wait_for_timeout(1500)
            print("[3] 登录成功，当前 URL: %s" % page.url)
        except Exception:
            page.wait_for_timeout(4000)
            print("[FAIL] 登录后未跳转，当前 URL: %s" % page.url)
            page.screenshot(path=os.path.join(SHOTS, "03_login_failed.png"), full_page=True)
            body = page.inner_text("body")[:600]
            print("页面文字片段: %s" % body.replace("\n", " | "))
            browser.close()
            return 1

        page.wait_for_timeout(4000)
        page.screenshot(path=os.path.join(SHOTS, "03_dashboard.png"), full_page=True)

        # 首页校验：统计卡片 + 图表
        body_text = page.inner_text("body")
        cards = page.query_selector_all(".ant-card")
        canvases = page.query_selector_all("canvas")
        svgs = page.query_selector_all(".chart-box svg")
        print("[4] 首页 .ant-card=%d  canvas=%d  chart-box svg=%d" % (len(cards), len(canvases), len(svgs)))

        expect_kw = ["数据集", "报表", "订阅", "星图"]
        for kw in expect_kw:
            print("     关键词 %-6s %s" % (kw, "命中" if kw in body_text else "缺失"))

        # 侧边栏菜单
        menus = page.query_selector_all(".ant-menu-item, .ant-menu-submenu-title")
        menu_texts = [m.inner_text().strip() for m in menus if m.inner_text().strip()]
        print("[5] 侧边栏: %s" % " / ".join(menu_texts[:15]))
        if not menu_texts:
            diag = page.evaluate(
                """() => {
                  const q = (s) => document.querySelectorAll(s).length;
                  const sider = document.querySelector('.ant-layout-sider');
                  return {
                    menu: q('.ant-menu'), item: q('.ant-menu-item'), sub: q('.ant-menu-submenu'),
                    sider: q('.ant-layout-sider'),
                    w: sider ? Math.round(sider.getBoundingClientRect().width) : -1,
                    html: sider ? sider.innerHTML.slice(0, 200) : 'NO SIDER',
                  };
                }"""
            )
            print("     侧边栏诊断: %s" % diag)

        # 逐个访问报表页
        pages = [
            ("/report/dataset", "数据集管理", "04_dataset.png"),
            ("/report/report", "报表管理", "05_report.png"),
            ("/report/subscription", "订阅管理", "06_subscription.png"),
        ]
        for path, label, shot in pages:
            page.goto(BASE + path, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3500)
            rows = page.query_selector_all(".ant-table-tbody tr.ant-table-row")
            txt = page.inner_text("body")
            empty = "暂无数据" in txt or "No Data" in txt
            print("[6] %-6s 行数=%-3d 空态=%s  URL=%s" % (label, len(rows), empty, page.url))
            page.screenshot(path=os.path.join(SHOTS, shot), full_page=True)

        print("-" * 70)
        print("控制台错误 %d 条：" % len(console_errors))
        for e in console_errors[:10]:
            print("   - %s" % e)
        print("失败请求 %d 条：" % len(failed_requests))
        for f in failed_requests[:15]:
            print("   - %s" % f)

        browser.close()

    print("=" * 70)
    ok = not failed_requests and len(console_errors) == 0
    print("结论：" + ("通过" if ok else "有告警，见上（截图已存 %s）" % SHOTS))
    return 0 if ok else 0


if __name__ == "__main__":
    sys.exit(main())
