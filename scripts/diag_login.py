"""用 Playwright 诊断 R9 登录页，输出文本信息（不依赖截图）。"""
import sys
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:19109/"
logs = []


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.on("console", lambda m: logs.append("[console.%s] %s" % (m.type, m.text[:200])) if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: logs.append("[pageerror] %s" % str(e)[:300]))
        page.on("requestfailed", lambda r: logs.append("[reqfail] %s %s" % (r.url[:120], r.failure)))

        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print("打开首页失败:", e)
            browser.close()
            return
        page.wait_for_timeout(4000)

        print("=== 页面标题 ===")
        print(page.title())
        print("=== 登录页可见文本（前 400 字）===")
        try:
            txt = page.inner_text("body")[:400].replace("\n", " | ")
            print(txt)
        except Exception as e:
            print("读取失败:", e)

        # 是否有账号/密码输入框
        for sel, label in (("input[placeholder*='账号']", "账号框(placeholder=账号)"),
                           ("input[placeholder*='户名']", "账号框(placeholder=用户名)"),
                           ("input[type='password']", "密码框"),
                           ("button:has-text('登录')", "登录按钮")):
            print("%-24s 存在=%s" % (label, page.locator(sel).count()))

        # 尝试登录
        try:
            acct = page.locator("input[placeholder*='账号'], input[placeholder*='户名']").first
            acct.fill("admin")
            page.locator("input[type='password']").first.fill("admin123")
            page.locator("button:has-text('登录')").first.click()
            page.wait_for_timeout(5000)
        except Exception as e:
            print("填写/点击失败:", e)

        print("=== 登录后 ===")
        print("URL:", page.url)
        # 若依的错误提示一般在 .el-message
        for sel in (".el-message__content", ".el-form-item__error", ".el-notification__content"):
            n = page.locator(sel).count()
            if n:
                for i in range(min(n, 3)):
                    print("提示[%s]:" % sel, page.locator(sel).nth(i).inner_text()[:200])
        # 是否拿到 token
        token = page.evaluate("() => (window.localStorage.getItem('token') || localStorage.getItem('Admin-Token') || '')")
        print("localStorage token 长度:", len(token or ""))
        print("localStorage keys:", page.evaluate("() => Object.keys(localStorage).join(',')[:200]"))

        print("=== 收集到的错误日志 ===")
        for line in logs[:20]:
            print(line)
        browser.close()


if __name__ == "__main__":
    main()
