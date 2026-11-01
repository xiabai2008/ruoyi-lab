"""批量验证 R1-R5 单机版站点的真实化成果（登录后抓首页看板）。"""
import re
import sys

import requests

sys.path.insert(0, r"D:\HZR_PROJECTS\ruoyi-scan")
from core.captcha_solver import CaptchaSolver  # noqa: E402

SITES = [
    (19101, "R1 藤县人民医院", r"门诊|挂号|患者|住院"),
    (19102, "R2 顺捷物流", r"运单|车辆|司机|客户"),
    (19103, "R3 梧州自来水", r"用水户|抄表|缴费|水表"),
    (19104, "R4 长洲教育局", r"学生|班级|学校|成绩"),
    (19105, "R5 华投财务", r"报销|凭证|供应商|预算"),
]


def login(base: str) -> requests.Session:
    s = requests.Session()
    for _ in range(6):
        sv = CaptchaSolver(base, s)
        ok, code = sv.solve()
        # rememberMe 必须显式传：RuoYi 4.x 的 ajaxLogin(String, String, Boolean)
        # 用包装类型接收，缺这个字段会拆箱 NPE（表现为 {"msg":"运行时异常:null","code":500}）
        r = s.post(
            base + "/login",
            data={
                "username": "admin",
                "password": "admin123",
                "validateCode": code or "",
                "rememberMe": "false",
            },
            allow_redirects=False,
            timeout=15,
        )
        if r.status_code in (301, 302):
            return s
    return s


def main():
    for port, name, kw in SITES:
        base = "http://127.0.0.1:%d" % port
        print("=" * 62)
        print(name, base)
        try:
            s = login(base)
            # 单机版真正的看板在 /system/main（index 只是 iframe 框架）
            html = ""
            for path in ("/system/main", "/index"):
                r = s.get(base + path, timeout=15)
                if r.status_code == 200 and len(r.text) > 2000:
                    html = r.text
                    print("  看板路径:", path, "长度:", len(r.text))
                    break
            if not html:
                print("  !! 拿不到看板")
                continue
            hits = sorted(set(re.findall(kw, html)))
            print("  业务关键词:", " ".join(hits) if hits else "(无)")
            print("  ECharts 容器:", len(re.findall(r"echarts\.init", html)), "| canvas:", html.count("<canvas"))
            # 抓首页里出现的纯数字（4 位以内），看是否像统计值
            nums = re.findall(r">\s*(\d{2,5})\s*<", html)
            print("  页面数字样本:", " ".join(dict.fromkeys(nums[:10])))
            print("  含'若依'字样:", "若依" in html, "| 含 RuoYi:", "RuoYi" in html)
        except Exception as e:
            print("  !! 异常:", type(e).__name__, str(e)[:120])


if __name__ == "__main__":
    main()
