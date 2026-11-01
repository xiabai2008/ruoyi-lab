# 工单 C2：三个独立组件靶场（Spring Boot Admin / Spring4Shell / Spring Cloud Function）

> 执行者：opencode。验收者：lead。
> 工作区 `C:\Users\HZR\Desktop\若依系统`。只建新靶场，不碰 R1–R12、C1、扫描器。
> **三座靶场各自独立：独立目录、独立端口、独立启停脚本。谁都不许互相拉起，也不许做"全量启动"。**

---

## 零、总原则

1. 每座靶场一个目录：`src/C2/<name>/`，产物 `runtime/C2/<name>/`，日志 `runtime/C2/<name>/logs/`，
   PID `.state/C2-<name>.pid`。
2. 每座靶场一个启停脚本：`scripts/c2_<name>.py start|stop|status`，只操作自己。
3. 后台启动用 `subprocess.Popen(close_fds=True, creationflags=CREATE_NEW_PROCESS_GROUP|DETACHED_PROCESS)`，
   不许 `start /B`，不许 `taskkill /IM java.exe`。
4. Maven 用工作区 `maven-settings.xml` + 工作区 `.m2`；JDK17。
5. **不许造"扫描器特征"**。这三座靶场要复刻真实产品行为，禁止在响应里塞
   `spring-trace-leak-confirmed`、`spring4shell-rce-confirmed`、
   `spring-cloud-function-rce-confirmed` 之类的标记串。被测出来是扫描器的事，不是靶场的事。
6. 端口固定：19311 / 19312（SBA server/client）、19313（Spring4Shell）、19314（Cloud Function）。
   与 C1 的 19301–19304 不冲突。

---

## 一、C2-1 Spring Boot Admin（19311 + 19312）

**目标**：复刻一套内网监控面板——SBA server + 一个被监控的业务服务，无认证。

| 组件 | 端口 | 说明 |
|---|---|---|
| SBA server | 19311 | `spring-boot-admin-starter-server:2.7.10`，Boot 2.7.18 |
| 被监控服务 | 19312 | `spring-boot-admin-starter-client:2.7.10`，注册到 19311，暴露 actuator |

要求：

- server 不加 security，`/applications` 返回已注册实例 JSON，`/wallboard` 返回 HTML 面板
- client 暴露 `/actuator/health`、`/actuator/info`、`/actuator/httptrace`、`/actuator/env`
  （`management.endpoints.web.exposure.include=*`）
- client 的 `info` 写业务信息（应用名 `parking-gateway-service`、版本 `1.4.2`、负责人）
- 启动脚本 `scripts/c2_sba.py`：start 同时拉起 server 和 client，等两个端口就绪；stop 按 PID 关两个
- 目标：`/applications` 里有 1 个实例，`/wallboard` 200，client `/actuator/httptrace` 200

---

## 二、C2-2 Spring4Shell（19313）

**目标**：复刻一个 2022 年没打补丁的 Spring MVC 老系统。

要求：

- `spring-webmvc 5.3.17` + `javax.servlet-api 4.0.1`，打成 WAR
- Tomcat **9.0.58**（解压到 `tools/tomcat-9.0.58-s4s/`，不要和别的靶场共用）
- 一个 Controller：`@Controller`，`@PostMapping("/device/add")`，形参是 POJO
  `DeviceForm`（含 `String deviceName`、`String location`），返回 JSP 或 JSON
- 根路径 `/` 返回一个像样的设备登记页（HTML 表单），不是 Whitelabel
- 端口 19313，context path 为空（ROOT.war）
- 启动脚本 `scripts/c2_s4s.py`：start 用 `catalina.bat run` 的后台等价写法，stop 按 PID
- **不要**在响应里写 `spring4shell-rce-confirmed`；也不要主动打补丁（`@InitBinder` 禁 `class.*`）
- 目标：`GET /` 200 且是设备登记页；`POST /device/add` 带 `deviceName=测试` 返回 200

---

## 三、C2-3 Spring Cloud Function（19314）

**目标**：复刻一个用 Spring Cloud Function 做路由的服务（CVE-2022-22963 版本）。

要求：

- Boot 2.7.18 + `spring-cloud-function-web:3.2.5`（漏洞版本）
- 一个 `@Bean Function<String,String> uppercase()`，注册为 `uppercase`
- `POST /functionRouter`，正常请求带 `spring.cloud.function.definition: uppercase` 头，
  返回大写结果；带 `spring.cloud.function.routing-expression` 头时按 SpEL 求值（漏洞行为）
- 根路径返回一段服务说明 JSON（服务名、版本、可用函数）
- 端口 19314，启动脚本 `scripts/c2_scf.py`
- **不要**塞 `spring-cloud-function-rce-confirmed` 标记
- 目标：正常路由请求返回大写；`/functionRouter` 无头请求返回 4xx；根路径 200

---

## 四、不许做的事

1. 不许三座靶场共用一个启动脚本，也不许写"启动全部 C2"。
2. 不许碰 R1–R12、C1 的目录/端口/数据库/进程。
3. 不许改 `D:\HZR_PROJECTS\ruoyi-scan` 任何文件（只允许运行它、把报告写到靶场侧）。
4. 不许为了"能被扫出来"添加任何标记串或伪造响应头。
5. 不许删旧产物；重建前把旧目录改名保留。

---

## 五、自检（`scripts/verify_c2.py`，逐项 PASS/FAIL，打印实际执行 N 项）

1. `c2_sba.py start` 后 19311 `/applications` 200 且含 1 个实例
2. 19311 `/wallboard` 200
3. 19312 `/actuator/httptrace` 200
4. `c2_sba.py stop` 后 19311/19312 端口释放，其余靶场端口不受影响
5. `c2_s4s.py start` 后 19313 `GET /` 200 且含设备登记表单
6. 19313 `POST /device/add` 200
7. `c2_s4s.py stop` 后 19313 释放
8. `c2_scf.py start` 后 19314 根路径 200
9. 19314 `POST /functionRouter` 正常路由返回大写结果
10. `c2_scf.py stop` 后 19314 释放
11. 三座靶场互不影响：依次只启动其中一座，另外两座端口保持关闭
12. 全部日志无 `OutOfMemoryError` / `Exception` 启动失败

---

## 六、基线记录（不改扫描器）

三座靶场分别起来后，用现有扫描器各扫一次，报告写到靶场侧：

```
D:\tools\Python 3.12.9\python.exe D:\HZR_PROJECTS\ruoyi-scan\main.py -u http://127.0.0.1:19311 --report reports_c2/sba --no-pause --no-cta
（19313 / 19314 同理）
```

只记录结果，**不改扫描器代码**。预期这几座会被判 SAFE/UNKNOWN（对应插件目前是标记桩），
把实际结果如实贴出来，作为下一轮修复的输入。

---

## 七、交付与停点

1. 贴 `verify_c2.py` 的 12 项结果。
2. 贴三座靶场各自的 `status` 输出。
3. 贴三次扫描的 CONFIRMED/SAFE/UNKNOWN 计数。
4. 贴目录清单（`src/C2/*`、`runtime/C2/*`、`scripts/c2_*.py`）。
5. **停在这里，不 commit，不碰其他靶场，不修扫描器。**
