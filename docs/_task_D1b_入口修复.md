# 工单 D1b：修入口路由 + 回退"为自检加的 GET"

> 执行者：opencode。验收者：lead。
> 只改 D1，不碰 R1–R12/C1/C2、不碰扫描器。

---

## 零、lead 验收发现（2026-10-31 20:05）

D1 的功能层是对的：`/portal/auth/signin` 200、旧地址 404、登录返回 `{success:true}`、
favicon 换掉、`?v=4.6.2` 清零、品牌干净、独立启停正常。

但有两个问题必须修，否则这座站测出来的数不能用。

### 1. 站点入口是 404，扫描器根本没打到应用

实测：

```
GET http://127.0.0.1:19321/                    -> 404
GET http://127.0.0.1:19321/portal/             -> 302 /portal/auth/signin
GET http://127.0.0.1:19321/portal/auth/signin  -> 200
```

`nginx/conf.d/D1.conf` 是 `location / { proxy_pass http://127.0.0.1:19221; }`，
但后端的 context-path 是 `/portal`，于是 `http://127.0.0.1:19321/` 被原样转给后端 `/` → 404。

后果：基线扫描打 `http://127.0.0.1:19321/` 拿到 404，`cms=""`、6 条 UNKNOWN 全是
「按官方根路径探测遇到 404」。这不是"二开让扫描器认不出"，是**入口配错了**。
真人打开站点首页也是 404，这座站现在根本不能用。

### 2. 给 `/system/user/list` 加了 GET，是为了让自检过

原生 RuoYi 4.6.2 的列表接口只接受 POST。为了自检里的 `GET /portal/system/user/list`
能返回 200，在 `SysUserController` 上加了 `@GetMapping()`。实测 GET 和 POST 都返回 200。

这是"靶场迁就自检"，必须回退：自检应该按真实调用方式用 POST。

### 3. 验证码关闭：可以接受，但要写进文档

`shiro.user.captchaEnabled: false` 是有意的控制变量（R2 保留验证码，D1 关掉，
专门隔离"二开路径/返回结构"这一个变量）。这没问题，但必须在 D1 的部署说明里写清楚，
否则以后没人知道这是设计取舍还是偷懒。

---

## 一、D1b-1 修 Nginx 入口

`nginx/conf.d/D1.conf` 改成：

```nginx
server {
    listen 19321;
    server_name 127.0.0.1;
    client_max_body_size 100m;

    access_log logs/D1_access.log main;

    # 站点根：真人访问 / 应该看到登录页，而不是 404
    location = / {
        return 302 /portal/;
    }
    location = /portal {
        return 302 /portal/;
    }

    # 带 context-path 的应用入口：原样转发，不做 URI 重写
    location /portal/ {
        proxy_pass http://127.0.0.1:19221;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Port $server_port;
    }
}
```

验收：

```
GET /              -> 302 /portal/
GET /portal/       -> 302 /portal/auth/signin
GET /portal/auth/signin -> 200，页面含「邕江物流」
```

## 二、D1b-2 回退 GET

1. `SysUserController` 删掉给 list 加的 `@GetMapping()`，恢复 `@PostMapping`。
2. `_verify_D1.py` 第 4 项改成 `POST /portal/system/user/list`，断言 `code=0`、`total>0`。
3. 复测：GET 应返回 405（或 404），POST 返回 200。

## 三、D1b-3 文档

在 `docs/D1/部署说明.md`（没有就新建）写清三件事：

- context-path `/portal`、登录地址 `/auth/signin`、旧 `/login` 已移除
- 登录接口返回 `{success,message}`，其它接口仍 `{code,msg,data}`
- 验证码关闭是**有意的控制变量**（R2 保留验证码作对照），不是配置遗漏

---

## 四、重跑基线（这次才是有效测量）

入口修好后，用真实根地址重扫：

```
D:\tools\Python 3.12.9\python.exe D:\HZR_PROJECTS\ruoyi-scan\main.py -u http://127.0.0.1:19321/ --report reports_d1/anon_v2 --no-pause --no-cta
```

要求：

1. 报告 `target` 是 `http://127.0.0.1:19321/`，不是 `/portal/...`
2. 贴指纹（cms/version/confidence/matched）与 CONFIRMED/SAFE/UNKNOWN 计数
3. 如果 `cms` 仍然为空，说明是二开特征导致的（登录页没有「若依」、favicon 换了、版本号没了），
   这是**预期结果**，不要为了让它识别出来去加官方特征
4. 如果扫描器还是只拿到 404，说明入口仍没修好，回头查 nginx

---

## 五、自检（13 项，打印实际执行 N 项）

在原 10 项基础上加：

11. `GET /` 返回 302 且 `Location` 含 `/portal/`
12. `GET /portal/system/user/list` 未登录时 302 到登录页（不是 200）
13. 基线报告 `target` 是根地址，且请求数 > 0

原有第 4 项改成 POST。

---

## 六、停点

1. 贴根路径与 `/portal/` 的 3 条 curl 结果。
2. 贴 GET/POST 列表接口状态码。
3. 贴 13 项自检。
4. 贴新基线指纹与计数。
5. 不碰其他靶场，不修扫描器，不 commit。
