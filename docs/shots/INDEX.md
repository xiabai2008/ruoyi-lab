# 截图索引

拍摄时间：2026-11-03 14:30  
拍摄方式：`python scripts\shots.py`（Playwright + Chromium）

| 文件 | 站点 | 说明 |
|---|---|---|
| `r1-login.jpg` | `http://127.0.0.1:19101/login` | R1 若依 4.5.1 单机版登录页（藤县人民医院） |
| `r10-login.png` | `http://127.0.0.1:19110/jeecg-boot/` | R10 JeecgBoot 3.6.3 登录页（星图报表） |
| `d1-login.jpg` | `http://127.0.0.1:19321/portal/auth/signin` | D1 若依 4.6.2 二开登录页（改写 context-path 与登录路径） |
| `c3-index.png` | `http://127.0.0.1:19331/` | C3 蜜罐首页 |
| `c3-git-config.png` | `http://127.0.0.1:19331/.git/config` | C3 假 .git/config —— 返回 200，内容是编造的 |
| `c3-druid.png` | `http://127.0.0.1:19331/druid/index.html` | C3 假 Druid 监控台 —— 看着像未授权访问 |
| `c3-env.png` | `http://127.0.0.1:19331/actuator/env` | C3 假 actuator/env —— 诱饵属性 |
