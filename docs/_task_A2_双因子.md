# 工单 A2：双因子登录站（测认证降级与锁定）

> 执行者：opencode。验收者：lead。
> 工作区 `C:\Users\HZR\Desktop\若依系统`。新建独立靶场 A2，不碰 R1–R12、C1、C2、D1、C3、扫描器。
> **A2 独立：自己的源码、库、端口、启停脚本，用到才起。**

---

## 零、这座站要测什么

前 16 座靶场解决的是"认不认得出""看不看得准"，A2 解决的是**认证链的诚实度**：

- 站点开了动态口令（TOTP）二次验证，扫描器拿不到第二因子；
- 正确行为是：明确判定"无法自动登录"，相关插件给 **UNKNOWN**，
  不许硬撞、不许把"登录失败"写成 SAFE，更不许循环重试把账号锁死；
- `--auth-login` 失败时必须优雅降级，报告要写清 `auth_status=failed`，不能崩。

---

## 一、底座与目录

- 源码：复制 `src/R2`（RuoYi 4.6.2）到 `src/A2`，排除 `target/`、`.git/`
- 数据库：`mysqldump ry_r2` → `ry_a2`
- 端口：Nginx **19341** → 后端 **19241**
- JDK8，运行目录 `runtime/A2/`，日志 `runtime/A2/logs/`，PID `.state/A2.pid`
- 启停 `scripts/a2_start.py start|stop|status`，净化 `SERVER_PORT`/`SERVER__PORT`

---

## 二、A2-1 加 TOTP 二次验证

1. 新增 `Totp.java`（HMAC-SHA1 + Base32，30 秒步长，允许 ±1 步）：
   - `public static boolean verify(String secret, String code)`
   - 只依赖 JDK 自带 `javax.crypto.Mac`，不要引第三方库
2. `application.yml` 增加：

```yaml
security:
  otp:
    enabled: true
    secret: JBSWY3DPEHPK3PXP      # 固定演示密钥，不要暴露到页面上
    digits: 6
    period: 30
```

3. `SysLoginController.login`：在验证码校验之后、`subject.login` 之前校验 `otp` 参数：
   - 缺失 → `AjaxResult.error("动态口令不能为空")`
   - 错误 → `AjaxResult.error("动态口令错误")`
   - 正确 → 继续原登录流程
4. 登录页 `login.html` 增加输入框（`name="otp"`，placeholder「6 位动态口令」），
   `login.js` 提交时带上 `otp`。页面上**不许**显示密钥或当前口令。

## 三、A2-2 账号锁定（复用框架能力）

RuoYi 4.6.2 自带 `SysPasswordService`：连续 5 次密码错误锁定 10 分钟。
确认 `application.yml` 里：

```yaml
user:
  password:
    maxRetryCount: 5
    lockTime: 10
```

不要自己重写锁定逻辑；如果框架能力不生效，先查 ehcache 配置，不要改成数据库字段。

---

## 四、A2-3 品牌

- 标题「邕江医保结算平台」，登录页副标题「南宁市邕江新区医疗保障中心」
- 版权行 `Copyright © 2019-2024 邕江医保`
- 可见文案不许出现「若依」「RuoYi」
- favicon 可保留官方（与 D1 不同，A2 不是测指纹）

---

## 五、自检（`scripts/verify_a2.py`，打印实际执行 N 项）

TOTP 用 Python 自己算（`hmac.new(base64.b32decode(secret), counter, sha1)`），
读 `application.yml` 里的 secret，不要硬编码到脚本外。

1. `GET /login` 200，页面含「动态口令」输入框
2. `POST /login` 不带 otp → 失败，响应含「动态口令」
3. `POST /login` 带错误 otp（000000）→ 失败
4. `POST /login` 带正确 TOTP + admin/admin123 → 成功（`code=0` 或 302 到 index）
5. 连续 5 次错误密码（每次带正确 TOTP）→ 第 6 次提示「锁定」或「10 分钟」
6. `a2_start.py stop` 后 19341/19241 释放
7. `start → stop → start` 两轮成功，无残留 PID
8. R2 19102、C1 19301、C3 19331 未受影响

> 第 5 项会锁账号。锁定后用 `UPDATE ry_a2.sys_user SET ...` 或等 10 分钟再继续，
> 脚本要自己处理，别把后续用例全带挂。

---

## 六、扫描器基线（不改扫描器）

1. 匿名：

```
D:\tools\Python 3.12.9\python.exe D:\HZR_PROJECTS\ruoyi-scan\main.py -u http://127.0.0.1:19341 --report reports_a2/anon --no-pause --no-cta
```

2. 带凭据：

```
D:\tools\Python 3.12.9\python.exe D:\HZR_PROJECTS\ruoyi-scan\main.py -u http://127.0.0.1:19341 --auth-login admin:admin123 --report reports_a2/auth --no-pause --no-cta
```

记录：

- 两次的指纹、CONFIRMED/SAFE/UNKNOWN 计数
- `report.json` 里 `auth_status` 字段的值
- 「后台默认口令」这一条的状态与 evidence
- 进程是否崩溃、退出码

**判定口径**：

- 动态口令挡住时，「后台默认口令」应为 **UNKNOWN**，evidence 要说明"需要动态口令/无法自动完成"
- 不许出现 `admin/admin123` 被判 **CONFIRMED**（口令对了，但没有第二因子，不等于可登录）
- 不许把登录失败写成 **SAFE**（那是"确认安全"，不是"没测到"）
- `--auth-login` 失败后进程必须正常退出，退出码非 0 或报告明确 `auth_status=failed`

---

## 七、停点

1. 贴 8 项自检结果。
2. 贴 `a2_start.py status`（已停止）。
3. 贴两次基线的计数、`auth_status`、「后台默认口令」的状态与 evidence。
4. 贴进程退出码。
5. **不碰其他靶场，不修扫描器，不 commit。**
