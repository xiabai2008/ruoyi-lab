# 工单 L2b：R8 返工——企业名去模板化 + 网关健康 503 + 自检文案

> 执行者：opencode。验收者：lead。
> 只改 R8 的种子数据与网关健康配置，不碰其他站点、不碰扫描器。
> 前置：R8 当前在线（`start_r8_cloud.py status` 全 ready）。

---

## 零、lead 验收发现（2026-10-31 17:25）

R8 的功能层通过：四张业务表 180/260/1500/800、看板数字与 DB 一致、
菜单 92、role1 新增 8 / role2 原有 84、品牌标题正确、其他站点数据未变。

但有 3 个问题：

### 1. 企业名全是模板（真实感不合格）

实测前 10 条：

```
南宁科技有限公司
广西科技有限公司
邕城科技有限公司
绿城科技有限公司
东盟科技有限公司
五象科技有限公司
青秀科技有限公司
西乡塘科技有限公司
江南科技有限公司
良庆科技有限公司
```

180 条全是「地名 + 科技有限公司」，没有行业、没有品牌词，一眼就是脚本批量生成的。
统一社会信用代码也不对：`91450108053BI28UAP`、`91450124UMKO8TKJN7` 里出现了 `I`、`O`，
真实 USCC 的字符集是数字 + 大写字母，**排除 I/O/S/V/Z**。

### 2. 网关健康检查 503

`GET http://127.0.0.1:19208/actuator/health` 返回 `status: DOWN`，子项：

```json
"redis":{"details":{"error":"org.springframework.data.redis.RedisSystemException: Cannot read Redis info"},"status":"DOWN"}
```

配置里 `spring.data.redis.password=ruoyi123`、`database=2` 是对的，`redis-cli -a ruoyi123 -n 2 INFO`
也能正常返回。业务全部正常，只是健康子项挂。一个「正常生产配置」的站点，健康检查 DOWN 不合理。

### 3. 自检第 10 项文案说反了

自检输出「`sys_menu=92 且 role_id=1 原有 84 行未删`」，但实际是 `role1=8（新增）`、
`role2=84（原有）`。结论对，表述错，会误导后来人。

---

## 一、L2b-1 企业名与信用代码去模板化

改 `seed/r8_business.py`（幂等，重跑只更新 `biz_enterprise`，不动租约/能耗/访客的外键）：

1. 企业名 = 地名（南宁/广西/邕城/绿城/五象/青秀/西乡塘/江南/良庆/武鸣/横州/宾阳）
   + 品牌词（2–4 字，如 瀚海/绿洲/跨境/云栖/恒锐/博远/华芯/启航/汇通/光谷/新元/锐驰…）
   + 行业词（智能科技/生物医药/供应链/新材料/电子信息/现代物流/节能环保/数字创意）
   + 后缀（有限公司/股份有限公司）
   - **180 条全部唯一**
   - 同一品牌词最多用 2 次；不许出现「南宁科技有限公司」这种只有地名+行业通用词的组合
2. 统一社会信用代码：18 位，字符集 `0123456789ABCDEFGHJKLMNPQRTUWXY`（排除 I/O/S/V/Z），
   前 2 位 `91`，第 3–8 位用 `4501xx` / `4502xx` 等广西行政区划，其余随机但**全表唯一**。
3. 行业分布保持合理：电子信息 30% / 生物医药 15% / 现代物流 20% / 商贸 15% / 新材料 12% / 其他 8%
4. 跑完同步 `seed/r8_business.sql`。

验收：`SELECT COUNT(DISTINCT enterprise_name)=180`；抽 10 条贴出来；
`SELECT COUNT(*) FROM biz_enterprise WHERE credit_code REGEXP '[IOSVZ]'` = 0；
`LENGTH(credit_code)=18` 全表成立。

---

## 二、L2b-2 网关健康 503

先定位，再修，不许直接关掉所有健康检查：

1. 看 `runtime/R8/logs/ruoyi-gateway.log` 启动阶段有没有 Redis 连接异常（NOAUTH / WRONGPASS / timeout）。
2. 用 `redis-cli -a ruoyi123 -n 2 INFO` 对照，确认 Redis 侧正常。
3. 若确认是 **Windows 版 Redis 5.0.14 的 INFO 响应与 Lettuce 解析不兼容**（业务读写正常、
   只有 INFO 解析失败），在 Nacos `ruoyi-gateway-dev.yml` 里加：

```yaml
management:
  health:
    redis:
      enabled: false
```

   并在文件里写一行注释说明原因（Windows 版 Redis INFO 兼容问题，业务读写正常）。
   改完重启 R8，确认 `/actuator/health` 返回 `status: UP`。
4. 如果是密码/库号配错，改配置修好，不许用关闭健康项掩盖。
5. 把最终原因和处置写进 `docs/R8/部署说明.md` 的「已知偏差」一节。

验收：`curl -s http://127.0.0.1:19208/actuator/health` 的 `status` 为 `UP`；
`/actuator/gateway/routes` 仍 200；业务接口仍正常。

---

## 三、L2b-3 自检第 10 项改对

`_verify_R8.py` 第 10 项改成：

- `sys_menu` 总数 = 92（±1 允许，写清）
- `sys_role_menu` 里 `role_id=1` = 8（本次新增）
- `role_id=2` = 84（原有，必须未被删）
- 断言三者同时成立，输出文案写清楚哪个是新增、哪个是原有

---

## 四、不许做的事

1. 不许重灌 `biz_lease` / `biz_energy` / `biz_visit`（外键会乱），只更新 `biz_enterprise` 的名称与信用代码。
2. 不许删 `sys_role_menu` 任何行。
3. 不许碰 R1–R7、R9–R12、C1。
4. 不许把 `management.health.*` 全关，只允许针对 redis 一项且有注释。

---

## 五、门禁与自检

1. 重跑 `_verify_R8.py`，12 项仍全过（第 10 项用新文案）。
2. 贴企业名样例 10 条、信用代码非法字符计数、`/actuator/health` 完整 JSON。
3. 贴 `start_r8_cloud.py status`。
4. 确认 R2/R5/R7/R10 行数不变（1200/620/8000/60）。

停在这里，不建 C2，不碰扫描器。
