# 工单 C3：蜜罐/假漏洞站（专测误报）

> 执行者：opencode。验收者：lead。
> 工作区 `C:\Users\HZR\Desktop\若依系统`。新建独立靶场 C3，不碰 R1–R12、C1、C2、D1、扫描器。
> **C3 独立：自己的目录、端口、启停脚本，用到才起。**

---

## 零、这座站是干什么的

一座**没有任何真实漏洞**的站点，但到处是"看起来像漏洞"的东西：
假 `.git`、假 `.env`、假备份、假 Druid、假 Swagger、假 actuator、假 SQL 报错。

它的用途只有一个：**测误报**。扫描器在这座站上报出的每一个 CONFIRMED，都是假阳性。
正确结果是 0 条 CONFIRMED。

注意：这是"欺骗性环境"，不是"有漏洞的环境"。所有假文件都必须经不起二次验证：
- `.git/HEAD` 有，但 `.git/objects/` 没有；
- Swagger JSON 里 `paths` 是空的；
- Druid 登录永远返回失败；
- SQL 报错是静态诱饵，基线和注入返回**逐字节相同**的内容。

---

## 一、目录与启停

- 代码 `src/C3/honeypot.py`（Flask，系统 Python 3.12.9，flask 3.0.3 已装）
- 端口 **19331**，只绑 127.0.0.1
- 日志 `runtime/C3/logs/access.log` + `runtime/C3/logs/console.log`
- PID `.state/C3.pid`
- 启停 `scripts/c3_honeypot.py start|stop|status`，只操作自己
- 启动时净化 `SERVER_PORT` / `SERVER__PORT`（C2b 教训）
- 不许 `taskkill /IM python.exe`

---

## 二、C3-1 假漏洞路径（全部 200，内容要像真的）

| 路径 | 返回 |
|---|---|
| `/.git/HEAD` | `ref: refs/heads/master` |
| `/.git/config` | 像样的 git config（remote 指向 `git@10.20.30.15:erp/portal.git`） |
| `/.env` | `APP_ENV=prod`、`DB_HOST=10.20.30.21`、`DB_PASSWORD=ChangeMe_2024`（假值） |
| `/backup/db_20240101.sql` | MySQL dump 头 + 2 条 `INSERT INTO`（假表、假数据） |
| `/druid/index.html` | Druid 登录页（含 `Druid Stat Index`、用户名/密码输入框） |
| `/druid/submitLogin` | 固定 `{"result":"fail","msg":"用户名或密码错误"}`，**永远不 success** |
| `/swagger-ui.html` | 带 `swagger-ui` 标记的页面 |
| `/v2/api-docs` | `{"swagger":"2.0","info":{...},"paths":{}}` —— **paths 必须为空** |
| `/actuator/env` | `{"activeProfiles":["prod"],"propertySources":[...]}`（假配置） |
| `/actuator/health` | `{"status":"UP"}` |
| `/manager/html` | 假 Tomcat Manager 登录框（401 + `WWW-Authenticate: Basic`） |
| `/console/` | 假 H2 Console 页面 |
| `/api/query?q=...` | 固定返回一段含 `You have an error in your SQL syntax` 的静态诱饵 |

要求：

1. `q=1` 与 `q=1'`、`q=1 union select 1` 三种请求返回**逐字节相同**的内容（差分为零）。
2. `.git/objects/xx/yyyy` 一律 404，证明不是真仓库。
3. `paths` 为空、Druid 登录必失败，证明不是真漏洞。

## 三、C3-2 软 404 与限速

1. 除上表路径外，**任意路径**返回 200 + 同一份通用 HTML（标题「邕江云服务门户」，
   长度约 1.2–1.6KB），用于测 soft404。
2. 同一 IP 在 60 秒内超过 **80 次**请求 → 返回 429 + `Retry-After: 30`，
   窗口过后恢复 200。用于测限速处理。
3. 所有请求写 `access.log`：时间、IP、方法、路径、状态码、UA。

## 四、不许做的事

1. 不许放真实可用漏洞（不能真连数据库、不能真执行命令、不能有可用的 webshell）。
2. 不许在页面里写「蜜罐」「honeypot」「测试站」这类字样。
3. 不许为扫描器留任何 `*-confirmed` 标记。
4. 不许碰其他靶场与扫描器。

---

## 五、自检（`scripts/verify_c3.py`，打印实际执行 N 项）

1. start 后 `/` 200
2. 任意未知路径 200，且正文与 `/` 逐字节相同（软 404）
3. `/.git/HEAD` 200 且以 `ref:` 开头
4. `/.git/objects/ab/cdef` 404
5. `/.env` 200 且含 `DB_HOST=`
6. `/backup/db_20240101.sql` 200 且含 `INSERT INTO`
7. `/druid/index.html` 200 含 Druid 标记；`/druid/submitLogin` 返回 `fail`
8. `/swagger-ui.html` 200 含 `swagger-ui`；`/v2/api-docs` 的 `paths` 为空
9. `/actuator/env` 200 且 JSON 有 `propertySources`
10. `/api/query?q=1`、`q=1'`、`q=1 union select 1` 三者正文 hash 相同
11. 90 次快速请求里至少出现 1 个 429
12. stop 后 19331 释放；start→stop 连续两轮成功，无残留 PID
13. R2 19102、C1 19301 未受影响

---

## 六、基线记录（不改扫描器）

```
D:\tools\Python 3.12.9\python.exe D:\HZR_PROJECTS\ruoyi-scan\main.py -u http://127.0.0.1:19331 --report reports_c3/anon --no-pause --no-cta
```

记录：

- 指纹（cms/version/confidence）
- CONFIRMED / SAFE / UNKNOWN 计数
- **每一条 CONFIRMED 的插件名与 URL**，逐条列出来

判定口径：这座站没有真漏洞，**所有 CONFIRMED 都是误报**。不许为了"结果好看"改靶场。

---

## 七、交付与停点

1. 贴 13 项自检结果。
2. 贴 `c3_honeypot.py status`。
3. 贴基线扫描的指纹、计数、CONFIRMED 明细。
4. 贴 `access.log` 前 5 行。
5. **停在这里，不碰其他靶场，不修扫描器，不 commit。**
