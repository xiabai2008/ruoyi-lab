r"""演示靶场一键启停 —— 给 ruoyi-scan 现场演示用的最小组合。

    python scripts/demo.py up      # 起 3 座演示站（约 60 秒）
    python scripts/demo.py status  # 看状态 + 打印演示命令
    python scripts/demo.py down    # 全部停掉

为什么单独做一个脚本
====================
`lab.py up` 已经很好用，但演示有它自己的约束：

1. **不能全量起。** 32 座靶场全起要十几 GB 内存、好几分钟，而且演示时大部分用不上。
2. **要能讲出故事。** 光有"存在漏洞"不够，得能同时展示"判定为安全"和"诚实说不知道"，
   否则观众分不清这是扫描器还是 grep。
3. **启动顺序有坑。** 忘了先起 infra 就直接 up 站点，会得到一堆 DEGRADED。

所以这里固定选 3 座，各代表一种判定结果：

| 站点 | 演示什么 | 预期输出 |
|---|---|---|
| R1    | 真实若依 4.5.1，6 条真漏洞 | 6 × CONFIRMED |
| R11   | 自建 Spring Boot，非若依目标 | 全 SAFE（负样本，零误报） |
| C3    | 蜜罐，假文件真实存在 | 2 × CONFIRMED（A 类诱饵，正确判定） |

R1 那 6 条是重点，因为里面包含两条**诚实降级**：
「部门树越权访问」判 UNKNOWN 而不是 SAFE —— 低权账号登录成功、业务层确实执行了，
但没返回任何部门数据行，空列表证明不了越权，所以不判。
这一条比任何 CONFIRMED 都更能说明三态判定的价值。

前置：扫描器侧需要 ddddocr 才能过 R1 的验证码
=============================================
R1 登录页有图形验证码。没装 ddddocr 时 `--auth-login` 会失败，6 条 CONFIRMED 全变成
UNKNOWN（"低权账号登录失败：captcha_infra 识别失败"）。这不是靶场的问题，装一下即可：

    pip install ddddocr

靶场侧不需要任何额外依赖 —— 靶场只负责把验证码正常发出来。
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAB = os.path.join(ROOT, "scripts", "lab.py")

# (站点, 演示角色, 预期输出)
DEMO_SITES = [
    ("R1",  "真实若依 4.5.1，6 条真漏洞", "6 × CONFIRMED + 2 × UNKNOWN（诚实降级）"),
    ("R11", "自建 Spring Boot，非若依目标", "全 SAFE（负样本，证明不瞎报）"),
    ("C3",  "蜜罐，假文件真实存在", "2 × CONFIRMED（A 类诱饵，判定正确）"),
]

SCANNER_HINT = r"""
============================================================
 靶场已就绪，可以演示了
============================================================

用另一个终端，在扫描器目录（ruoyi-scan）执行：

  # ① 主力演示：R1 认证扫描，6 条真漏洞 + 2 条诚实降级
  python main.py -u http://127.0.0.1:19101 ^
      --auth-login admin:admin123 ^
      --surface-account scanner_low:LowPriv_2026 ^
      --report artifacts/demo/R1 --no-pause --no-cta

  # ② 对照：R11 是自建系统，不是若依 —— 应该零 CONFIRMED
  python main.py -u http://127.0.0.1:19111 --no-pause --no-cta

  # ③ 对照：C3 蜜罐 —— 2 条"存在"是正确判定，因为假文件真的在
  python main.py -u http://127.0.0.1:19331 --no-pause --no-cta

讲解要点（按这个顺序讲最有说服力）：

  1. R1 先跑「未认证扫描」，满屏 UNKNOWN —— 说明它不会假装知道。
  2. 加上 --auth-login 再跑，6 条 CONFIRMED 出现。
  3. 重点指「部门树越权访问」那条 UNKNOWN：低权账号登录成功了、接口也执行了，
     但没返回数据，空列表证明不了越权，所以不判。三态判定的价值就在这。
  4. 跑 R11 对照：不是若依就不报，证明插件不是靠关键字瞎匹配。

R1 的验证码需要 ddddocr（扫描器侧依赖，靶场不需要）：

  pip install ddddocr

没装的话 --auth-login 会失败，6 条 CONFIRMED 会全部退化成 UNKNOWN。
"""


def _run(args: list[str]) -> int:
    return subprocess.call([sys.executable, LAB] + args, cwd=ROOT)


def _port_open(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def up() -> int:
    print("[..] 启动演示靶场（R1 / R11 / C3，约 60 秒）")
    print("     依赖会自动带上 MySQL + Redis + Nginx\n")
    rc = _run(["up"] + [s for s, _, _ in DEMO_SITES])
    if rc != 0:
        return rc
    print(SCANNER_HINT)
    return 0


def status() -> int:
    rc = _run(["status"] + [s for s, _, _ in DEMO_SITES])
    print()
    print(f"{'站点':<6} {'演示角色':<28} 预期输出")
    print("-" * 78)
    for site, role, expect in DEMO_SITES:
        print(f"{site:<6} {role:<28} {expect}")
    print()
    print("用 `python scripts/demo.py up` 启动；`down` 全部停止。")
    return rc


def down() -> int:
    # 基础设施也一起停：演示结束后没有站点在跑，留着 MySQL/Redis/Nginx 只是占内存。
    # 注意这会影响同时运行的其它站点 —— 所以先确认演示站都停了再停 infra。
    rc = _run(["down"] + [s for s, _, _ in DEMO_SITES])
    _run(["down", "infra"])

    # nginx -s stop 是异步的，端口不会立刻释放。不等的话紧接着 status 会看到
    # 「入口还在、后端已死」的 DEGRADED，看起来像没停干净。
    for _ in range(20):
        if not any(_port_open(p) for p in (19101, 19111, 19331)):
            break
        time.sleep(0.5)

    left = [s for s, p in zip([x[0] for x in DEMO_SITES], (19101, 19111, 19331)) if _port_open(p)]
    if left:
        print(f"[!] 以下站点端口仍被占用，可能需手工确认：{', '.join(left)}")
        return 1
    print("[OK] 演示靶场已全部停止（MySQL/Redis 仍在跑，需要的话手工停）")
    return rc


def main() -> int:
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "status").lower()
    return {"up": up, "status": status, "down": down}.get(cmd, status)()


if __name__ == "__main__":
    sys.exit(main())
