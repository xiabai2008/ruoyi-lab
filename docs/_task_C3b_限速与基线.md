# 工单 C3b：默认关掉限速，重做误报基线

> 执行者：opencode。验收者：lead。
> 只改 C3 的限速开关与自检/基线，不碰其他靶场、不碰扫描器。

---

## 零、问题：基线被限速打废了

C3 建成没问题，13 项自检我复跑也全过。但基线扫描的结果不能用。

`runtime/C3/logs/access.log` 实测（20:11–20:13 扫描窗口）：

```
总请求 7425
429    7181   (96.7%)
200     238
404       2
401       1
```

只有 238 个请求真正到达内容，其余全被 80 次/60 秒的限速挡掉。
所以 `0 CONFIRMED` 不是"扫描器识破了诱饵"，而是"扫描器根本没看到诱饵"。
18 条 UNKNOWN 主要也是 429 导致的"无法判定"。

**限速本身是有效能力，但默认开这么低，误报基线就测不出来。**

---

## 一、C3b-1 限速改成可选

1. `src/C3/honeypot.py`：限速阈值从环境变量读，默认 **0 = 关闭**：

```python
RATE_LIMIT = int(os.environ.get("C3_RATE_LIMIT", "0"))   # 0 = 不限速
RATE_WINDOW = 60
```

`RATE_LIMIT <= 0` 时直接跳过限速逻辑。

2. `scripts/c3_honeypot.py`：`start` 支持 `--strict`：

```
python scripts\c3_honeypot.py start            # 默认不限速，用于误报基线
python scripts\c3_honeypot.py start --strict   # 80 次/60 秒，用于测 429 处理
```

`--strict` 时设置 `env["C3_RATE_LIMIT"]="80"`；默认设 `"0"`。
两种模式都写同一个 PID 文件，不许同时起两份。

---

## 二、C3b-2 自检拆成两组

`scripts/verify_c3.py` 改成「默认模式 12 项 + 严格模式 2 项」：

**默认模式（不限速）**：原来 13 项去掉第 11 项（429），其余保留。

**严格模式（`--strict`）**：

- 起服务，90 次快速请求，至少 1 个 429 且 `Retry-After: 30`
- 停服务，端口释放

最后打印「实际执行 N 项，通过 M 项」。

---

## 三、C3b-3 重做基线（这次才是有效测量）

```
python scripts\c3_honeypot.py start
D:\tools\Python 3.12.9\python.exe D:\HZR_PROJECTS\ruoyi-scan\main.py -u http://127.0.0.1:19331 --report reports_c3/anon_v2 --no-pause --no-cta
python scripts\c3_honeypot.py stop
```

要求：

1. 扫描期间 `access.log` 里 **429 数量为 0**（或 <1%），200 占绝大多数
2. 贴状态码分布
3. 贴指纹与 CONFIRMED/SAFE/UNKNOWN 计数
4. **CONFIRMED 逐条列出插件名 + URL + evidence 摘要**

### 判定口径（比上一版更准确）

这座站没有可利用漏洞，但要分两类看：

| 类别 | 含义 | 处理 |
|---|---|---|
| **A 类：文件存在** | `.git/HEAD`、`.env`、备份 SQL、Druid 页、actuator —— 靶场确实返回了这些文件 | 报出来不算纯误报，但要在报告里标注「内容是诱饵，无可利用数据」 |
| **B 类：可利用** | SQL 注入、RCE、弱口令成功、未授权读到真实数据 —— 需要差分证明 | **必须为 0**，出现一条就是硬误报 |

判据：

- `sql_inject_*` 判 CONFIRMED → B 类硬误报（三种 q 的正文 hash 相同）
- `druid_brute` 判弱口令成功 → B 类硬误报（submitLogin 永远 fail）
- `swagger_leak` 判文档泄露 → B 类硬误报（paths 为空）
- `git_leak` / `env_leak` / `backup_scan` → A 类，如实记录
- `actuator_env_rce` 判 RCE → B 类硬误报（env 是假的，不能执行）

---

## 四、停点

1. 贴 `access.log` 状态码分布（证明 429 清零）。
2. 贴 14 项自检结果。
3. 贴基线指纹、计数、CONFIRMED 明细（按 A/B 分类）。
4. 贴 `c3_honeypot.py status`（已停止）。
5. 不碰其他靶场，不修扫描器，不 commit。
