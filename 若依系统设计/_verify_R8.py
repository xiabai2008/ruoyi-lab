#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R8 智谷园区运营平台 12 项自检。"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import pymysql  # noqa: E402
import requests  # noqa: E402

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE = "http://127.0.0.1:19108"
DB = dict(host="127.0.0.1", port=13307, user="root", password="", database="ry_r8", charset="utf8mb4")
SHOTS = ROOT / "runtime" / "R8" / "screenshots"
PY = sys.executable


def db():
    return pymysql.connect(**DB)


def check(name, func):
    try:
        detail = func()
        print("PASS %s%s" % (name, (" | " + str(detail)) if detail else ""))
        return True
    except Exception as exc:
        print("FAIL %s: %s" % (name, exc))
        return False


def login_token():
    resp = requests.post(BASE + "/prod-api/auth/login", json={"username": "admin", "password": "admin123"}, timeout=15)
    resp.raise_for_status()
    token = (resp.json().get("data") or {}).get("access_token")
    if not token:
        raise AssertionError("登录响应无 access_token: %s" % resp.text[:200])
    return token


def test_memory_guard():
    import start_r8_cloud

    rc = start_r8_cloud.memory_precheck(available_mb=1800)
    assert rc == 2, "低内存应返回 2，实际 %s" % rc
    return "available_mb=1800 -> exit 2"


def test_home():
    resp = requests.get(BASE + "/", timeout=15)
    assert resp.status_code == 200, resp.status_code
    text = resp.content.decode("utf-8", errors="replace")
    assert "智谷园区" in text, "首页标题/文案未命中智谷园区"
    return "HTTP 200"


def test_login():
    token = login_token()
    return "access_token 长度 %d" % len(token)


def test_nacos_services():
    resp = requests.get(
        "http://127.0.0.1:8848/nacos/v1/ns/service/list",
        params={"pageNo": 1, "pageSize": 20, "namespaceId": "public"},
        timeout=15,
    )
    data = resp.json()
    assert data.get("count") == 6, data
    assert len(data.get("doms") or []) == 6, data
    return "count=6"


def test_nacos_console():
    resp = requests.get("http://127.0.0.1:8080/", timeout=15)
    assert resp.status_code == 200, resp.status_code
    return "HTTP 200"


def test_business_lists():
    token = login_token()
    headers = {"Authorization": "Bearer " + token}
    expected = {"enterprises": 180, "leases": 260, "energies": 1500, "visits": 800}
    got = {}
    for path, want in expected.items():
        resp = requests.get(
            BASE + "/prod-api/system/business/" + path,
            params={"pageNum": 1, "pageSize": 1}, headers=headers, timeout=20,
        )
        resp.raise_for_status()
        total = resp.json().get("data", {}).get("total")
        assert total == want, "%s total=%s want=%s" % (path, total, want)
        got[path] = total
    return got


def test_dashboard():
    token = login_token()
    headers = {"Authorization": "Bearer " + token}
    resp = requests.get(BASE + "/prod-api/system/business/dashboard", headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json().get("data") or {}
    conn = db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM biz_enterprise")
            enterprise = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM biz_lease")
            lease = cur.fetchone()[0]
            cur.execute("SELECT IFNULL(ROUND(SUM(cost),2),0) FROM biz_energy WHERE month=DATE_FORMAT(CURDATE(),'%Y-%m')")
            energy = float(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM biz_visit WHERE DATE_FORMAT(visit_time,'%Y-%m')=DATE_FORMAT(CURDATE(),'%Y-%m')")
            visits = cur.fetchone()[0]
    finally:
        conn.close()
    assert data.get("enterpriseCount") == enterprise, data
    assert data.get("leaseCount") == lease, data
    assert abs(float(data.get("energyCost") or 0) - energy) < 0.01, data
    assert data.get("visitCount") == visits, data
    return "企业=%s 租约=%s 本月能耗=%.2f 本月访客=%s" % (enterprise, lease, energy, visits)


def _playwright_pages():
    from playwright.sync_api import sync_playwright

    SHOTS.mkdir(parents=True, exist_ok=True)
    errors = []
    context = sync_playwright().start()
    browser = context.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(BASE + "/login", wait_until="networkidle", timeout=30000)
    page.screenshot(path=str(SHOTS / "login.png"), full_page=True)
    page.fill("input[placeholder='账号']", "admin")
    page.fill("input[placeholder='密码']", "admin123")
    page.click("button:has-text('登 录')")
    page.wait_for_timeout(4000)
    page.screenshot(path=str(SHOTS / "home.png"), full_page=True)
    canvases = page.locator("canvas").count()
    page.goto(BASE + "/business/enterprise", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2500)
    page.screenshot(path=str(SHOTS / "enterprise.png"), full_page=True)
    enterprise_ok = "企业名称" in page.content()
    browser.close()
    context.stop()
    return canvases, enterprise_ok, errors


def test_echarts():
    canvases, _enterprise_ok, _errors = _playwright_pages()
    assert canvases == 2, "首页 canvas 数量=%s" % canvases
    return "canvas=2"


def test_no_future_time():
    conn = db()
    try:
        with conn.cursor() as cur:
            for table in ("biz_enterprise", "biz_lease", "biz_energy", "biz_visit"):
                cur.execute("SELECT MAX(create_time), SUM(create_time > NOW()) FROM " + table)
                latest, future = cur.fetchone()
                assert not future, "%s 存在未来 create_time: %s" % (table, future)
                assert latest is not None, "%s 无数据" % table
    finally:
        conn.close()
    return "4 张业务表均无未来时间"


def test_menu_grants():
    conn = db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM sys_menu")
            menus = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM sys_role_menu WHERE role_id=1 AND menu_id BETWEEN 2000 AND 2007")
            new_rows = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM sys_role_menu WHERE role_id=2")
            original = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM sys_role_menu")
            role_rows = cur.fetchone()[0]
    finally:
        conn.close()
    assert menus == 92, "sys_menu=%s，期望 92（允许 ±1）" % menus
    assert new_rows == 8, "role_id=1 本次新增菜单=%s，期望 8（新增）" % new_rows
    assert original == 84, "role_id=2 原有行=%s，期望 84（原有，未被删）" % original
    assert role_rows == 92, "sys_role_menu 总数=%s，期望 92" % role_rows
    return "menu=92；role1=8（本次新增）；role2=84（原有，未删）；total=92"


def test_no_oom():
    logs = list((ROOT / "runtime" / "R8" / "logs").glob("*.log"))
    for path in logs:
        text = path.read_text(encoding="utf-8", errors="replace")
        assert "OutOfMemoryError" not in text, "发现 OOM: %s" % path
    return "检查 %d 个日志" % len(logs)


def test_screenshots():
    canvases, enterprise_ok, errors = _playwright_pages()
    assert (SHOTS / "login.png").exists(), "缺少 login.png"
    assert (SHOTS / "home.png").exists(), "缺少 home.png"
    assert (SHOTS / "enterprise.png").exists(), "缺少 enterprise.png"
    assert enterprise_ok, "企业列表页未渲染"
    assert not errors, "浏览器 console 错误: %s" % errors[:5]
    return "login/home/enterprise 三张截图，canvas=%s，console 错误=0" % canvases


CHECKS = [
    ("内存预检低内存 exit 2", test_memory_guard),
    ("19108 首页 200 且含智谷园区", test_home),
    ("admin/admin123 获取 access_token", test_login),
    ("Nacos 服务列表 count=6", test_nacos_services),
    ("Nacos 控制台 8080 可打开", test_nacos_console),
    ("四个业务列表 total=180/260/1500/800", test_business_lists),
    ("看板 4 卡片与 DB 一致", test_dashboard),
    ("首页 2 个 ECharts canvas", test_echarts),
    ("业务表无未来 create_time", test_no_future_time),
    ("sys_menu=92、role1 新增 8、role2 原有 84 未被删", test_menu_grants),
    ("runtime/R8/logs 无 OutOfMemoryError", test_no_oom),
    ("登录/首页/企业列表截图 + console 0 错误", test_screenshots),
]


def main():
    print("R8 智谷园区运营平台自检")
    passed = 0
    for idx, (name, func) in enumerate(CHECKS, 1):
        print("[%d/%d] %s" % (idx, len(CHECKS), name))
        if check(name, func):
            passed += 1
    print("实际执行 %d 项，通过 %d 项" % (len(CHECKS), passed))
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
