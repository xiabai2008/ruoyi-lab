# 工单 D1：若依二开变形站（RuoYi 4.6.2 改到"不像若依"）

> 执行者：opencode。验收者：lead。
> 工作区 `C:\Users\HZR\Desktop\若依系统`。新建独立靶场 D1，不碰 R1–R12、C1、C2、扫描器。
> **D1 独立：自己的源码、库、端口、启停脚本，用到才起。**

---

## 零、为什么要这座站

现有 12 座全是官方 tag 原样部署。现实里 90% 的若依是二开过的：
改了上下文路径、改了登录地址、改了返回结构、换了 favicon、去掉了版本号。
扫描器现在只认官方形态——这座站就是用来打这个盲区的。

**不许为了"能被扫出来"保留官方特征。** 该改的都改掉，扫不出来是扫描器的事。

---

## 一、底座与目录

- 源码：复制 `src/R2`（RuoYi 4.6.2 单机版）到 `src/D1`，排除 `target/`、`.git/`
- 数据库：`mysqldump ry_r2` → 新库 `ry_d1`，不改表结构
- 端口：Nginx **19321** → 后端 **19221**
- JDK8（与 R2 一致）
- 运行目录 `runtime/D1/`，日志 `runtime/D1/logs/`，PID `.state/D1.pid`
- 启停脚本 `scripts/d1_start.py start|stop|status`，只操作 D1

---

## 二、D1-1 改上下文路径与登录地址

1. `application.yml`：

```yaml
server:
  port: 19221
  servlet:
    context-path: /portal
```

2. Shiro 过滤链（`ruoyi-framework/.../ShiroConfig.java`）：
   - 把 `/login` 的 anon 规则改成 `/auth/signin`
   - **删掉** `/login` 的 anon 与 controller 映射（旧地址必须 404，不是跳转）
   - `/captcha/captchaImage` 保持 anon

3. 登录 Controller（`SysLoginController`）：
   - `@GetMapping("/auth/signin")` → 返回 `login` 视图
   - `@PostMapping("/auth/signin")` → 原登录逻辑
   - 原来的 `/login` 两个映射删除

4. 模板与 JS：
   - `templates/login.html` 表单 `th:action="@{/auth/signin}"`（Thymeleaf 会自动带 context-path）
   - `static/ruoyi/js/login.js` 的提交地址改成 `ctx + "auth/signin"`（沿用项目里的 `ctx` 变量）

---

## 三、D1-2 改登录返回结构（只改登录，不动列表接口）

二开常见的做法：登录接口返回 `{success, message}`，而不是 `{code, msg}`。

1. `SysLoginController` 的 POST 分支不要返回 `AjaxResult`，改成自定义 `Map`：
   - 成功：`{"success": true, "message": "登录成功"}`
   - 失败：`{"success": false, "message": "用户不存在/密码错误"}` 或验证码错误文案
   - 保留 `HttpStatus` 200，不要改成 401/500
2. `login.js` 的成功判据从 `result.code == 0` 改成 `result.success === true`
3. **其它接口不要动**：`/system/user/list` 仍然返回 `{code:0, rows:[...], total:N}`，
   避免把整个前端改崩

---

## 四、D1-3 去官方特征

1. **favicon**：换一个自制 `.ico`（不同 md5，随便画个方块也行），
   放在 `static/favicon.ico`，确保 `md5` ≠ `e49fd30ea870c7a820464ca56a113e6e`
2. **版本参数**：全站模板里 `?v=4.6.2` 这类静态资源版本参数删掉
   （`grep -rn "v=4.6.2" src/D1/ruoyi-admin/src/main/resources/templates/` 应为空）
3. **版权行**：登录页页脚改成 `Copyright © 2019-2024 邕江物流有限公司`，
   页面 `<title>` 改「邕江物流运输管理系统」
4. **可见文案**：登录页、框架页、错误页里不许出现「若依」「RuoYi」
   （`com.ruoyi` 包名占位可以留，那是框架原生形态）
5. 错误页 `templates/error/*` 的标题一并改掉

---

## 五、D1-4 独立启停

`scripts/d1_start.py`：

- start：校验 19221 空闲 → JDK8 启动 `build/D1/ruoyi-admin.jar --server.port=19221` →
  等 `/portal/auth/signin` 200 → 写 PID
- stop：按 PID 杀，等端口释放，删 PID
- status：打印 pid/alive/port/HTTP 状态
- 环境净化：`env.pop("SERVER_PORT")`、`env.pop("SERVER__PORT")`（C2b 的教训）
- 不许 `taskkill /IM java.exe`

Nginx：新增 `nginx/conf.d/D1.conf`，19321 → 19221，`proxy_set_header Host $http_host`。

---

## 六、自检（`scripts/verify_d1.py`，打印实际执行 N 项）

1. `d1_start.py start` 后 `GET /portal/auth/signin` 200，页面含「邕江物流」
2. `GET /portal/login` 404、`GET /login` 404（旧地址必须消失）
3. `POST /portal/auth/signin` admin/admin123 返回 `success=true`
4. 带会话 `GET /portal/system/user/list` 返回 `code=0` 且 `total>0`
5. favicon md5 ≠ 若依官方 md5
6. 模板里 `?v=4.6.2` 数量 = 0
7. 登录页/框架页可见文案无「若依」「RuoYi」
8. `d1_start.py stop` 后 19321/19221 释放
9. `start → stop → start` 两轮成功，无残留 PID
10. 其它靶场（R2 19102、C1 19301）进程未受影响

---

## 七、基线记录（不改扫描器）

```
D:\tools\Python 3.12.9\python.exe D:\HZR_PROJECTS\ruoyi-scan\main.py -u http://127.0.0.1:19321 --report reports_d1/anon --no-pause --no-cta
```

把指纹（cms/version/confidence）、CONFIRMED/SAFE/UNKNOWN 计数如实贴出来。
预期会掉得很惨（favicon 换了、版本号没了、登录地址变了）——这正是要测量的东西。

---

## 八、交付与停点

1. 贴 10 项自检结果。
2. 贴 `d1_start.py status`。
3. 贴基线扫描的指纹与计数。
4. 贴 `grep -rn "v=4.6.2"` 和 favicon md5 的结果。
5. **停在这里，不碰 R1–R12/C1/C2，不修扫描器，不 commit。**
