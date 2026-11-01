# 工单 L2：R8 智谷园区运营平台——补齐业务层（独立按需靶场）

> 执行者：opencode。验收者：lead。
> 工作区 `C:\Users\HZR\Desktop\若依系统`。只做 R8，不碰 R1–R7/R9–R12、不碰 C1、不碰扫描器。
> **R8 是独立靶场：自己的目录、端口、数据库、启停脚本。不加入任何"全量启动"，用到才起。**

---

## 零、现状（lead 15:15 实测）

R8 的**基础设施已经齐了**，缺的是业务层：

| 项 | 现状 |
|---|---|
| 源码 | `src/R8`（RuoYi-Cloud v3.6.8，6 个微服务） |
| 前端源码 | `src/R8/ruoyi-ui`（Vue2 + Element UI，官方脚手架） |
| 构建 | `scripts/01_build_R8.bat` |
| 启停 | `scripts/start_r8_cloud.py start/stop/status`（Job Object 守护，已实测） |
| 端口 | gateway 19208、auth 9200、system 9201、gen 9202、job 9203、file 9300 |
| Nacos | `ry_config` 库已有 9 个 dataId（auth/file/gateway/gen/job/monitor/system/application/sentinel） |
| Nginx | `nginx/conf.d/R8.conf`（19108，只反代 `/prod-api/`） |
| 数据库 | `ry_r8` 已有 31 张标准表；**0 张 `biz_*` 业务表** |
| 组织/用户 | `sys_dept` 10 条、`sys_user` 2 条 —— 只有默认数据 |
| 菜单 | `sys_menu` 84 条，全是框架自带；无业务菜单 |

**不要重搭基础设施。** 本单只补：业务表 + 组织用户 + 日志 + 菜单授权 + 品牌 + 看板 + 业务页。

---

## 一、边界

1. 只改 R8 相关：`src/R8`、`runtime/R8`、`seed/r8_*`、`nginx/conf.d/R8.conf`（除非必须，不要动）、
   `scripts/start_r8_cloud.py`（只允许加内存预检）。
2. 不碰 R1–R7、R9–R12、C1 的数据库/文件/进程。
3. 不把 R8 加进 `lab.py` 或任何全量启动脚本（目前也没有）。
4. 启动前如果内存不够，**报错退出，不许自动停别人的站点**。
5. 生成的数据不许出现未来时间；`create_time` 不早于 2025-01-01、不晚于今天。
6. 重建前端前先把 `runtime/R8/ui` 改名保留（`ui_prev_realize`），不要删。

---

## 二、L2-1 内存预检（只改 `start_r8_cloud.py`）

R8 要 Nacos + 6 个 JVM，实测约 3.2–3.5GB。在 `cmd_start()` 最前面加：

1. 用 `psutil` 或 `GlobalMemoryStatusEx` 取当前可用物理内存；
2. 可用 < 3200MB 时打印：

```
[FAIL] 可用内存 1.8GB，R8 需要 ≥3.2GB。
       请先停掉部分站点（例如 python scripts\launch.py 不支持 stop，用 .state\R*.pid + taskkill /PID）
       当前占用最高的 java：
       PID  RSS(MB)  站点
       ...
```

3. 退出码 2，不启动任何进程。
4. 可用 ≥3200MB 时正常启动。

**不许**自动杀别的站点。这是"按需启动"的前提。

---

## 三、L2-2 业务数据（`seed/r8_business.py`，幂等 + 落盘 SQL）

库 `ry_r8`，新增 4 张表（字段自定，但要像真实业务系统）：

| 表 | 行数 | 说明 |
|---|---|---|
| `biz_enterprise` | 180 | 入园企业：企业名、统一社会信用代码、行业、联系人、电话、入驻楼层、面积、状态（在驻/退租/待入驻） |
| `biz_lease` | 260 | 租约：合同号、企业ID、起止日期、月租金、押金、状态（生效/到期/续签中） |
| `biz_energy` | 1500 | 能耗抄表：企业ID、月份、电(kWh)、水(t)、费用、抄表时间 |
| `biz_visit` | 800 | 访客：姓名、手机（脱敏）、被访企业、来访时间、离开时间、事由、状态 |

要求：

- 企业名用中文真实风格（南宁/广西本地感），行业分布合理（电子信息/生物医药/物流/商贸/新材料）
- 租约金额与面积挂钩（每平米 35–80 元/月），状态与起止日期自洽
- 能耗按月分布，工作日高、周末低；夏季（6–9 月）电费明显更高
- 访客时间分布在最近 6 个月，工作日上午多、周末少
- 脚本幂等：重复执行不重复插入（先 `DELETE FROM` 或 `INSERT ... ON DUPLICATE KEY`）
- 同时落盘 `seed/r8_business.sql`

组织和用户（直接写 `sys_dept` / `sys_user`）：

- 17 个部门，3 层（根 100 + 6 个中心 + 10 个组）
- 28 个用户，工号 `ZG0001`–`ZG0028`，口令统一 `admin123`
  （RuoYi-Cloud 用 BCrypt，可直接复用 admin 的 `$2a$10$...` 哈希）
- 登录日志 280 条、操作日志 380 条，覆盖最近 30 天，周末量明显低

---

## 四、L2-3 菜单与授权（只 INSERT，不许 DELETE）

- 顶级菜单 `业务管理`（menu_id 2000，`menu_type=M`，path `business`）
- 4 个 C 菜单：企业入驻 `/business/enterprise`、租约管理 `/business/lease`、
  能耗抄表 `/business/energy`、访客登记 `/business/visit`，component 指向对应 vue 文件
- 3 个 F 按钮：`business:enterprise:list`、`business:lease:list`、`business:energy:list`
- `sys_role_menu`：给 role_id=1 插 8 条（4 菜单 + 3 按钮 + 1 目录），**不许删任何现有行**
- 插完 `SELECT COUNT(*) FROM sys_menu` 应为 84 + 8 = 92（允许 ±1，写清）

---

## 五、L2-4 品牌与页面

**品牌**（`src/R8/ruoyi-ui`）：

- 标题改「智谷园区运营平台」，登录页副标题「南宁智谷科技园 · 园区运营中心」
- 页脚、登录页 logo、Navbar 的 gitee/文档入口清掉
- 可见文案里不许出现「若依」「RuoYi」；favicon 可保留（框架原生形态）
- 构建后 `runtime/R8/ui` 的 index.html 与 JS 产物里 `grep -ri "若依\|ruoyi"` 只允许命中
  `com.ruoyi` 包名占位这类框架原生内容，不许命中标题/文案

**页面**（`src/R8/ruoyi-ui/src/views/business/`）：

- `enterprise/index.vue`：搜索（企业名/行业/状态）+ 分页 + 详情弹窗
- `lease/index.vue`：列表 + 合同状态筛选 + 到期提醒标红
- `energy/index.vue`：列表 + 月份筛选 + 企业筛选
- `visit/index.vue`：列表 + 日期范围 + 状态筛选
- 首页 `views/index.vue` 重写：4 个卡片（企业 180 / 租约 260 / 本月能耗费用 / 本月访客）
  + 2 个 ECharts（近 12 月能耗趋势、企业行业分布环形）+ 5 条待办

---

## 六、L2-5 独立启停与验证

启动（R8 专用，不影响别人）：

```
python scripts\start_r8_cloud.py start
python scripts\start_r8_cloud.py status
python scripts\start_r8_cloud.py stop
```

写 `若依系统设计/_verify_R8.py`（或 `scripts/verify_r8.py`），逐项 PASS/FAIL，
最后打印「实际执行 N 项，通过 M 项」：

1. 内存预检：模拟低内存时 exit 2（可以用参数跳过真实检查，但要有单测/演示）
2. 19108 首页 200，标题含「智谷园区」
3. `POST /prod-api/auth/login` admin/admin123 拿到 `access_token`
4. Nacos 服务列表 `count=6`（8848 API）
5. Nacos 控制台 8080 可打开
6. 四个业务列表 total 分别 = 180 / 260 / 1500 / 800
7. 看板 4 个卡片数字与 DB 一致
8. 首页 2 个 ECharts canvas 存在（用 Playwright 或简单 DOM 检查）
9. 所有业务表 `MAX(create_time) <= NOW()`，无未来时间
10. `sys_menu` 计数 = 92±1，`sys_role_menu` 里 role_id=1 原有行未被删
11. `runtime/R8/logs/*.log` 无 `OutOfMemoryError`
12. 截图：登录页、首页、企业列表各一张（Playwright，控制台 0 报错）

---

## 七、交付与停点

1. 贴 `start_r8_cloud.py status` 的输出。
2. 贴 12 项自检结果。
3. 贴四张业务表行数、`sys_menu` / `sys_role_menu` 计数、看板数字对照。
4. 贴截图路径。
5. **停在这里，不建 C2，不改 R1–R7/R9–R12，不碰扫描器。**
