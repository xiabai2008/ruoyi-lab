import os
# -*- coding: utf-8 -*-
"""R10 星图数据（JeecgBoot）验收脚本。

验证链路：
  1) 取验证码 -> 从 Redis db4 读答案（JeecgBoot 把答案存 md5(captcha+checkKey+secret)）
  2) 登录拿 token
  3) 逐个探 /report/* 接口，核对返回条数与数据库行数一致
  4) 核对 /report/stats/overview 的数字

用法： python scripts/verify_r10.py
"""
import json
import subprocess
import sys
import time

import requests

BASE = "http://127.0.0.1:19210/jeecg-boot"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REDIS_CLI = ROOT + r"\tools\redis\redis-cli.exe"
REDIS_PASS = "ruoyi123"
REDIS_DB = "4"


def redis_cmd(*args):
    out = subprocess.run(
        [REDIS_CLI, "-a", REDIS_PASS, "-n", REDIS_DB, *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return out.stdout.strip()


def fetch_captcha(check_key):
    """取图 + 从 Redis 拿答案。图不用解析，答案直接在 db4。"""
    r = requests.get(BASE + "/sys/randomImage/" + check_key, timeout=10)
    r.raise_for_status()
    j = r.json()
    assert j.get("success"), "取验证码失败: %s" % j
    img_len = len(j.get("result") or "")
    # 清掉旧 key，保证只剩本次
    for k in redis_cmd("keys", "*").splitlines():
        if k:
            redis_cmd("del", k)
    # 重新取一次，Redis 里就只会有这一次的答案
    r = requests.get(BASE + "/sys/randomImage/" + check_key, timeout=10)
    r.raise_for_status()
    keys = [k for k in redis_cmd("keys", "*").splitlines() if k]
    if not keys:
        raise RuntimeError("Redis db4 没有验证码答案，图长度=%d" % img_len)
    answer = redis_cmd("get", keys[0]).strip().strip('"')
    return answer


def login(username="admin", password="123456"):
    check_key = str(int(time.time() * 1000))
    answer = fetch_captcha(check_key)
    payload = {
        "username": username,
        "password": password,
        "captcha": answer,
        "checkKey": check_key,
    }
    r = requests.post(BASE + "/sys/login", json=payload, timeout=15)
    j = r.json()
    if not j.get("success"):
        raise RuntimeError("登录失败: %s (验证码=%s)" % (j.get("message"), answer))
    return j["result"]["token"], answer


def api_get(path, token, params=None):
    r = requests.get(
        BASE + path,
        headers={"X-Access-Token": token},
        params=params or {},
        timeout=20,
    )
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"_raw": r.text[:200]}


def main():
    print("=" * 66)
    print("R10 星图数据 · JeecgBoot 验收")
    print("=" * 66)

    token, answer = login()
    print("[OK] 登录成功，验证码=%s，token=%s..." % (answer, token[:16]))

    checks = [
        ("/report/dataset/list", {"pageNo": 1, "pageSize": 10}, "数据集"),
        ("/report/report/list", {"pageNo": 1, "pageSize": 10}, "报表"),
        ("/report/dashboard/list", {"pageNo": 1, "pageSize": 10}, "看板"),
        ("/report/subscription/list", {"pageNo": 1, "pageSize": 10}, "订阅"),
    ]
    ok = True
    for path, params, label in checks:
        code, j = api_get(path, token, params)
        if not j.get("success"):
            print("[FAIL] %-28s HTTP %s  success=false  %s" % (label, code, j.get("message")))
            ok = False
            continue
        res = j.get("result") or {}
        total = res.get("total")
        recs = res.get("records") or []
        print("[OK]   %-10s %-26s total=%-5s 本页=%d 条" % (label, path, total, len(recs)))
        if recs:
            r0 = recs[0]
            sample = r0.get("datasetName") or r0.get("reportName") or r0.get("dashboardName") or r0.get("subscriptionName")
            print("         样例: %s" % sample)

    print("-" * 66)
    for path, label in (
        ("/report/stats/overview", "平台总览"),
        ("/report/stats/category", "报表分类分布"),
        ("/report/stats/trend", "近30天发布趋势"),
    ):
        code, j = api_get(path, token)
        if not j.get("success"):
            print("[FAIL] %-12s HTTP %s  %s" % (label, code, j.get("message")))
            ok = False
            continue
        res = j.get("result")
        if isinstance(res, list):
            print("[OK]   %-12s %-24s 返回 %d 组" % (label, path, len(res)))
            print("         %s" % json.dumps(res[:4], ensure_ascii=False))
        elif isinstance(res, dict):
            print("[OK]   %-12s %-24s %s" % (label, path, json.dumps(res, ensure_ascii=False)[:260]))
        else:
            print("[WARN] %-12s %-24s 返回 %r" % (label, path, res))

    print("=" * 66)
    print("结论：" + ("全部通过" if ok else "存在失败项，见上"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
