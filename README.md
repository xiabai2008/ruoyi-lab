# 若依历史系统复刻靶场

给 `ruoyi-scan` 做演示与验证用的靶场：把 12 套"客户系统"按当年上线时的原始状态重建，
每套都换成一家虚构单位、灌入真实业务数据，让它看起来就是一台正在干活的生产系统。

用途有两个：
1. 录演示视频时，扫描器打的是"像真的一样"的站点，不是裸奔的若依默认页。
2. 做版本差异研究，同一套工具在 R1–R10 上必须给出不同的判定结果。

## 快速开始

```bash
cd "C:\Users\HZR\Desktop\若依系统"

# 起全部站点（首次约 2.5 分钟）
"D:\tools\Python 3.12.9\python.exe" scripts\restore_demo.py R1 R2 R3 R4 R5 R6 R7 R9 R10 R11

# 只起某一个
"D:\tools\Python 3.12.9\python.exe" scripts\launch.py R9
```

> `start_demo.bat` 和 `启动演示环境.bat` 内容一样，**只恢复 R9**，别当成一键全启脚本用。

启动顺序是固定的：MySQL(13307) → Redis(6379) → 各站后端(192xx) → Nginx(191xx)。
`restore_demo.py` 会自己按这个顺序来，端口已占用就跳过。

## 端口与账号

| 层 | 端口 | 说明 |
|---|---|---|
| Nginx | 19101–19112 | 对外入口，站点号与端口尾号对应（R9 = 19109） |
| 后端 | 19201–19211 | Spring Boot，不经 Nginx 也能直连 |
| MySQL | 13307 | root 空密码，库名 `ry_r1` … `ry_r10`、`ry_config` |
| Redis | 6379 | 密码 `ruoyi123`，各站用不同 database index |

| 站点 | 账号 | 备注 |
|---|---|---|
| R1–R7、R9 | `admin` / `admin123` | RuoYi 系列统一口令 |
| R10 | `admin` / `123456` | JeecgBoot 用 PBEWithMD5AndDES，不是 md5，改口令要重算散列 |
| R11 | 无登录 | 自建 API，没有认证体系 |
| R1–R5、R12 | `scanner_low` / `LowPriv_2026` | 低权账号，给扫描器做越权测试用。R6/R7/R9/R10 没有 |

## 站点现状

形态：A = 单机版（Thymeleaf + jQuery），B = 前后端分离（Vue SPA + 独立后端）。

| 站点 | 端口 | 形态/版本 | 虚构单位 | 主模块 | 状态 |
|---|---|---|---|---|---|
| R1 | 19101 | A / 4.5.1 | 藤县人民医院 | 门诊挂号 | 超真实 |
| R2 | 19102 | A / 4.6.2 | 广西顺捷物流 | 运单管理 | 差一项（趋势线平直） |
| R3 | 19103 | A / 4.7.8 | 梧州市自来水 | 水表抄表 | 超真实 |
| R4 | 19104 | A / 4.8.0 | 长洲区教育局 | 学籍管理 | 超真实 |
| R5 | 19105 | A / 4.8.3 | 华投集团财务共享中心 | 费用报销 | 超真实 |
| R6 | 19106 | B / 3.9.2 | 深圳跨境通电商 | 订单管理 | 超真实 |
| R7 | 19107 | B / 3.8.9 | 明德职业技术学院 | 选课管理 | 超真实（meta 标签待清） |
| R8 | 19108 | B / Cloud 3.6.8 | 南宁智谷科技园 | 租约管理 | **未做**，见下方说明 |
| R9 | 19109 | B / Plus 5.6.2 | 华电石家庄热电 | 设备巡检 | 超真实（样板站） |
| R10 | 19110 | B / JeecgBoot 3.6.3 | 星图数据科技 | 报表订阅 | 超真实 |
| R11 | 19111 | 自建 Spring Boot 3.4.1 | `internal-api`（无中文名） | —— | 负样本（故意不是若依） |
| R12 | 19112 | A / R2 镜像 + WAF | 同 R2 | 跟随 R2 | 差一项（同 R2） |

业务数据实测（2026-10-31 核对，与看板数字一致）：

| 站点 | 业务表行数 | 部门/用户 | 登录日志/操作日志 |
|---|---|---|---|
| R1 | 患者 300、挂号 900、处方 650、药品 220 | 22 / 25 | 278 / 354 |
| R2 | 运单 1200、车辆 45、司机 60、客户 180 | 17 / 26 | 264 / 362 |
| R3 | 用水户 520、水表 540、抄表 1600、缴费 1300 | 27 / 33 | 235 / 360 |
| R4 | 学校 8、班级 96、学生 2400、成绩 8000 | 27 / 33 | 294 / 420 |
| R5 | 报销 620、凭证 900、供应商 150、预算 60 | 28 / 32 | 285 / 420 |
| R6 | SKU 400、订单 1500、库存 400、物流单 1200 | 23 / 32 | 321 / 400 |
| R7 | 专业 12、课程 180、教学班 240、学生 1800、选课 8000 | 20 / 32 | 290 / 380 |
| R8 | **0 张业务表** | 10 / 2 | 13 / 0 |
| R9 | 设备 68、巡检 450、缺陷 72、计划 12 | 22 / 33 | 214 / 350 |
| R10 | 数据集 60、报表 180、看板 40、订阅 200 | 17 / 29 | 日志合计 1026 |
| R11 | 无数据库 | —— | —— |

### R8 为什么没做

RuoYi-Cloud 要拉 Nacos + gateway/auth/system/gen/job/file 六个微服务，一共 7 个 JVM，
实测需要约 3.5GB。本机 16G，同时跑其余 9 站后余量不够，容易 OOM 把 R9 一起带崩。

要补的话得先把其他站点的堆内存压下去，或者单独一台机器跑。

### R12 的特殊之处

R12 不是独立站点，是 R2 前面加了一层带规则的 Nginx（`nginx/conf.d/R12.conf`）模拟商业 WAF：

- 共用 R2 的后端 19202，**数据天然同步，不需要额外导数据**
- 拦截路径穿越、`union select`、`${}` 模板表达式、`java.lang.` 等特征，返回自定义 403 页
- 正常业务请求原样透传

## 目录结构

```
若依系统/
├─ src/R1 … R11/          官方 tag 源码（R6/R7/R10 另有 -ui 前端工程）
├─ build/Rx/              编译产物 jar、前端构建日志
├─ runtime/Rx/            运行目录：run.log、前端 dist 部署位
├─ nginx/conf.d/          每站点一个 conf，191xx 反代到 192xx
├─ db/                    库脚本与检查中间产物
├─ seed/                  每站点业务数据灌入脚本（r1_business.py … r10_business.py，R9 叫 r9_business_data.py）
├─ scripts/               启动器与验证脚本
├─ docs/                  规格文档（动手前必读）
└─ certs/                 自签证书
```

## 单站点构建与部署

单机版（R1–R5）：

```bash
"D:\tools\apache-maven-3.9.12\bin\mvn.cmd" -f src\R5\pom.xml clean package -DskipTests
cp src\R5\ruoyi-admin\target\ruoyi-admin.jar build\R5\
"D:\tools\Python 3.12.9\python.exe" scripts\launch.py R5
```

前后端分离（R6/R7/R9/R10）：

```bash
cd src\R10-ui
pnpm build                       # 构建前若 dist 有文件，先 mv dist dist_prev_xxx
mv ..\..\runtime\R10\ui ..\..\runtime\R10\ui_prev_xxx
cp -r dist ..\..\runtime\R10\ui
```

## 验证脚本

| 脚本 | 覆盖范围 |
|---|---|
| `scripts/verify_r1_r5.py` | R1–R5 批量验证，借 `ruoyi-scan` 的验证码识别自动登录，抓首页看板 |
| `scripts/e2e_r9.py` | R9 全链路：登录 → 看板 → 4 个业务页 → 搜索/分页，只看 DOM 不依赖截图 |
| `scripts/e2e_r10.py` | R10 全链路：登录页品牌 → 验证码（从 Redis 取答案）→ 看板 → 3 个列表页，含截图 |
| `scripts/verify_r10.py` | R10 接口级验收：核对 `/report/*` 返回条数与数据库行数是否一致 |

## 已知坑位

1. **单机版首页是 `templates/main.html`，不是 `index.html`。**
   `index.html` 只是 iframe 框架壳，改错地方等于没改。R1–R5 都踩过。

2. **启动不要用 `start /B` 或 PowerShell 的 `Start-Process`。**
   java 会继承父进程标准句柄，调用方的管道一直不关，一次循环 4 个站能挂 15 分钟。
   必须用 `scripts/launch.py`（`subprocess` 默认 `close_fds=True`）。

3. **RuoYi 4.x 登录表单字段名是 `rememberMe` 不是 `rememberme`。**
   HTML 里 checkbox 的 name 是小写，但 `login.js` 提交时转成了 `rememberMe`。
   用 curl 压测时写错大小写，后端 `Boolean rememberMe` 拿到 null 会抛
   `NullPointerException: Cannot invoke "java.lang.Boolean.booleanValue()"`，看着像站点坏了。

4. **临时关验证码要改 `runtime/<站点>/application.yml`，改 jar 里的无效。**
   放一个只含 `shiro.user.captchaEnabled: false` 的外部文件即可覆盖，**验完必须删掉并重启**，
   否则漏洞面与设计不一致（默认口令插件要没有验证码才能 CONFIRM）。

5. **SPA 的 `try_files $uri $uri/ /index.html` 会让任意未知路径返回 200。**
   这是前端路由的正常配置，但对扫描器是灾难——所有探测路径都"存在"。
   扫描侧必须接软 404 判定，靶场侧不要为了凑结果去改这个配置。

6. **R10 前端构建有两个硬约束。**
   一是 `vue` 必须锁 3.4.x（`^3.4.15` 会被装成 3.5.x，配合 rollup 3.30 会丢绑定）；
   二是 `vite.config.ts` 里必须留着 `patchBareVueApis()` 插件，
   否则产物里 `defineComponent` 变成裸全局引用，首屏 `ReferenceError` 白屏。

7. **R10 的登录页不是 `sys/login/Login.vue`。**
   `router/routes/index.ts` 里 `/login` 指向 `views/system/loginmini/MiniLogin.vue`，
   改错文件毫无效果。JeecgBoot 的商家宣传图也在这套 loginmini 素材里。

8. **MySQL 的 `--defaults-file` 必须走 ASCII junction 路径。**
   实际用的是 `C:/Users/HZR/ry_r2_mysql/my.ini`，直接给项目中文路径会起不来。

9. **日志里写了端口不代表进程还活着。**
   必须 `netstat -ano | grep :192xx` 确认 LISTENING，或者直接 curl 一次。

## 三条基本规则

1. **底座用官方 tag 源码**，从 Gitee 拉，不手写、不用第三方 fork。
2. **二开只做加法**：加业务模块、加菜单、加表。既有代码一行不动，接口契约一个字符不改。
   唯一例外是界面品牌化（标题、logo、登录页文案、页脚），这一步本来就是"换皮"，
   依据是 `..\若依系统设计\08_站点真实化施工手册.md`，不是在 `docs/` 里。
3. **不做改造**：不升级依赖、不加安全配置、不做代码格式化、不写单测、不配 CI。
   —— 靶场要复刻的是"当年上线时的样子"，包括它的漏洞。

## 规格文档

| 文件 | 内容 |
|---|---|
| `docs/站点清单.md` | 12 套系统的版本、端口、业务模块、历史配置状态、实施顺序 |
| `docs/部署与技术规格.md` | 目录结构、工具链、构建方式、端口表、启停脚本规范 |
| `docs/接口契约.md` | 不得改动的接口、参数、返回体、页面文案 |
| `docs/交付标准.md` | 数据规模、日志、备份、证书、遗留物的要求 |
| `toolchain.md` | 2026-10-29 的工具链探测原始结果（历史快照，Node 版本那条已过时） |
