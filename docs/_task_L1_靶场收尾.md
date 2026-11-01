# 工单 L1：靶场收尾——资源可控、一键启停、数据补齐

> 执行者：opencode。验收者：lead（独立复跑）。
> 工作区 `C:\Users\HZR\Desktop\若依系统`（不是 git 仓库）。
> **只动靶场，不碰 `D:\HZR_PROJECTS\ruoyi-scan`。**
> 本单不建新站点（C2 留到下一单），目标是把现有 11 站 + 4 个 C1 组件做成
> 「一条命令起停、资源可预期、数据都对得上」的状态。

---

## 零、现状（lead 15:10 实测）

| 项 | 状态 |
|---|---|
| MySQL 13307 / Redis 6379 | UP（Redis 密码 `ruoyi123`） |
| R1/R2/R4/R6 后端 | UP |
| R3/R5/R11 后端 | 本单开工前由 lead 用 `restore_demo.py` 拉起，已 UP |
| R7 / R9 / R10 后端 | **DOWN**（19107 的 `/prod-api/captchaImage`、19109 的 `/prod-api/auth/code`、19110 的 `/jeecg-boot/` 均 502） |
| C1 四组件 19301–19304 | UP |
| 空闲内存 | 2.3 GB / 15.8 GB，已有 11 个 java 进程 |
| 一键启停 | **没有**。`start_demo.bat` 只恢复 R9；README 自己写了「别当一键全启脚本用」 |

核心矛盾：16G 跑不动「11 站 + 4 组件 + 未来 C2」。所以本单先解决资源与运维，
再谈加新站。

---

## 一、边界（违反即返工）

1. 只改 `C:\Users\HZR\Desktop\若依系统` 内的文件。
2. 开工先备份：`cp -r scripts .state/backup_scripts_20261031/`（Windows 用 `robocopy` 或
   Python `shutil.copytree`，不要用 `cp -r` 直接覆盖已有目录）。
3. 不许删 `src/` `build/` `runtime/` 下任何东西；重建 jar 前把旧 jar 改名保留。
4. 不许 `taskkill /IM java.exe`。停止一律按 `.state/*.pid` 里的 PID 杀。
5. 不许动 `D:\HZR_PROJECTS\ruoyi-scan`。
6. 本单不建 R8，不建 C2 组件。

---

## 二、L1-1（P0）`scripts/lab.py`：一键启停 + 状态 + 自检

新增 `scripts/lab.py`，四个子命令：

```
python scripts\lab.py start [--profile full|lite]
python scripts\lab.py stop
python scripts\lab.py status
python scripts\lab.py verify
```

**start（顺序固定，已占用则跳过）**

1. MySQL：复用 `restore_demo.py` 里的启动逻辑（`mysqld --defaults-file=C:/Users/HZR/ry_r2_mysql/my.ini`），
   等 13307 就绪。
2. Redis：复用 `tools\redis` 原生版，密码 `ruoyi123`；6379 已在则跳过。
3. Nginx：19109 未监听才启动。
4. 后端：按 profile 调 `scripts/launch.py <SITE>`，每个站点等自己的探活路径：
   - R1–R5：`/login` 200
   - R6/R7：`/prod-api/captchaImage` 200
   - R9：`/prod-api/auth/code` 200
   - R10：`/jeecg-boot/sys/randomImage/1` 200
   - R11：`/api/v1/health` 200
5. C1：调用 `scripts/components_start.py`，等 19301–19304 就绪。

profile：

- `full` = R1 R2 R3 R4 R5 R6 R7 R9 R10 R11 + C1（**不含 R8**）
- `lite` = R1 R2 R6 R9 + C1（本机内存紧张时的最小可测集）

**stop**：先 C1，再后端（倒序），最后 Nginx/Redis/MySQL 可选择保留（默认保留，`--all` 才停）。
只按 PID 文件杀，杀完校验端口释放。

**status**：输出表格，每行一个站点/组件：

```
站点 | 端口 | PID | 状态码 | 探活结果 | RSS(MB)
```

RSS 用 `Get-CimInstance Win32_Process` 或 `tasklist /FI "PID eq x"` 取，取不到就写 `-`。

**verify**：逐站做探活 + 关键表行数校验，任一失败 exit 1。至少覆盖：

- R1-R7/R9/R10 登录页/验证码 200
- R11 `/api/v1/health` 200
- C1 四组件各自的入口
- DB 行数：R1 患者 300、R2 运单 1200、R3 水表 1600、R4 学生 2400、R5 报销 620、
  R6 订单 1500、R7 选课 8000、R9 巡检 450、R10 数据集 60、C1 订单 50（见 L1-2）

**堆内存（写进 `launch.py` 的 `JAVA_OPTS`）**

| 站点 | 参数 |
|---|---|
| R1–R5 | `-Xms64m -Xmx320m` |
| R6/R7 | `-Xms64m -Xmx384m` |
| R9/R10 | `-Xms64m -Xmx640m` |
| R11 | `-Xms32m -Xmx192m` |

要求：full 全量启动后 **free ≥ 400MB**，且逐站登录一次、打开一次列表页，`run.err.log`
不许出现 `OutOfMemoryError`。如果 320m 撑不住 R5（4.8.3/Spring Boot 4），单独提到 448m 并记录。

---

## 三、L1-2（P0）数据收尾

### 3.1 C1 订单 30 → 50

`src/C1/data-service/src/main/java/com/zhihe/ops/data/DataInitializer.java` 里订单生成循环改成 50 条；
客户仍 20 条。重新构建：

```
mvn -s maven-settings.xml "-Dmaven.repo.local=<工作区>\.m2" -f src/C1/data-service/pom.xml package -DskipTests
```

旧 jar 改名保留，新 jar 放 `runtime/C1/data-service/`，用 `components_start.py` 重启。
验收：`/api/orders?size=100` 的 `page.totalElements == 50`，`/api/customers` 仍为 20，
`createTime` 最大值不晚于今天。

### 3.2 R2/R12 趋势线

R2 的运单 `biz_waybill.create_time` 目前均匀分布，看板趋势是一条直线。改成：

- 最近 12 个月，工作日每天 8–20 单、周末 0–3 单（权重随机，seed 固定可复现）
- 不许出现未来时间
- `seed/r2_business.py` 改成幂等：重跑时先清空 biz_waybill 再灌，或按主键 upsert
- 已经入库的 1200 条用一条 UPDATE 重排，不要重灌全库

验收 SQL（自己跑，贴结果）：

```sql
SELECT DATE_FORMAT(create_time,'%Y-%m') m, COUNT(*) c FROM ry_r2.biz_waybill
WHERE create_time >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
GROUP BY m ORDER BY m;
```

要求：至少 10 个月有数据，`max(c) / min(c) >= 2`（不再是直线），`MAX(create_time) <= NOW()`。

### 3.3 README 状态表

- R2/R12 的「差一项（趋势线平直）」改成「超真实」
- R7 的「meta 标签待清」删掉（实测 `runtime/R7/ui/index.html` 已是 `content=RuoYi`）
- 新增一节「一键启停」：`lab.py start/stop/status/verify` + full/lite 两个 profile + 堆内存表
- R8 保留「未做」并写明：需要 3.5GB，只能在 `cloud` profile 下停掉其他站点后单独跑（L2 处理）

---

## 四、L1-3（P0）冷启动实测

1. `python scripts\lab.py stop --all`，确认 java 进程只剩与靶场无关的（应为 0）。
2. 记录启动前 free 内存。
3. `python scripts\lab.py start --profile full`，记录：
   - 总耗时（目标 ≤ 8 分钟）
   - 启动后 free 内存（目标 ≥ 400MB）
   - `lab.py status` 全绿
4. 再 `stop` → `start` 一次，确认可重复。
5. 抽 3 个站登录 + 打开列表页（R2/R7/R10），确认无 OOM、列表有数据。

---

## 五、自检脚本

写 `若依系统设计/_verify_L1.py`（或 `scripts/verify_lab.py`），逐项打印 PASS/FAIL，
最后打印「实际执行 N 项，通过 M 项」，不许用一个大 try 包住跳过：

1. lab.py start full 后 11 站探活全 200
2. C1 四组件探活全 200
3. free ≥ 400MB
4. lab.py stop 后端口全释放、无残留 java
5. 再次 start 成功
6. C1 orders = 50、customers = 20
7. R2 月度趋势 max/min ≥ 2、无未来时间
8. 所有 `runtime/R*/run.err.log` 无 `OutOfMemoryError`

---

## 六、交付与停点

1. 贴 `lab.py status` 的完整表格（启动后）。
2. 贴冷启动耗时、启动前后 free 内存。
3. 贴 8 项自检结果。
4. 贴 R2 月度趋势 SQL 结果。
5. 贴 `git`——不用贴，这不是仓库；贴 `ls -la scripts/` 确认新增文件。
6. **停在这里，不建 C2，不碰 R8，不碰扫描器。**
