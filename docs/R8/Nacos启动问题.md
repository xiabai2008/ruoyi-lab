# R8 Nacos 启动问题（2026-11-01，已解决）

## 结论

8848 被 **Windows Hyper-V 的保留端口段 8788–8887** 占住，任何进程 bind 8848 都会得到
`WSAEACCES (10013)`。Nacos 与 Docker 都把它报成 `Address already in use`，看起来像端口冲突，
实际是系统保留。

解决：管理员 PowerShell 执行

```powershell
net stop winnat
net start winnat
```

之后 8848 恢复可绑定，Nacos zip 正常启动。

## 排查过程（保留，避免下次重复踩）

1. 第一层：宿主环境有 `SERVER__PORT=55829`，Spring relaxed binding 把它当 `server.port`，
   Nacos 控制台被顶到 55829，报 `Port 55829 already in use`。
   已在 `start_nacos_zip()` 改用 `build_env()`（启动前 pop `SERVER_PORT`/`SERVER__PORT`）。
2. 第二层：清掉环境变量后仍报 8848 冲突。日志里两个 Tomcat 都初始化 8848，
   一度怀疑 Nacos 3.0.2 merged 模式的 server/console 撞端口。
   试过 `deployment.type=server`、`nacos.console.ui.enabled=false`、显式 `server.port=8080`，
   都不成立——因为真正原因是 **8848 被系统保留**，不是 Nacos 配置。
3. 定位：`netsh interface ipv4 show excludedportrange protocol=tcp` 显示 `8788–8887`，
   8848 在段内；Python `socket.bind(8848)` 返回 WinError 10013。
   Docker `docker start` 也报
   `ports are not available ... bind: An attempt was made to access a socket in a way forbidden by its access permissions`。
4. 停止 Docker / `wsl --shutdown` 都不能释放保留段；只有管理员重启 `winnat` 有效。

## 验证结果（2026-11-01 10:45）

- Nacos：8848 API UP、8080 控制台 200、服务列表 `count=6`
  （auth / system / gen / job / file / gateway）
- R8：19108 首页 200，`<title>智谷园区运营平台</title>`
- 登录：`POST /prod-api/auth/login` admin/admin123 返回 token
- 业务接口：`/prod-api/system/business/{enterprises,leases,energies,visits}`
  total = 180 / 260 / 1500 / 800
- 6 个服务日志无 `OutOfMemoryError`
- 启动方式：**zip 模式**（Docker Desktop 已停止，不需要容器）

## 本轮对脚本的改动（都在 `scripts/start_r8_cloud.py`）

1. `start_nacos_zip()` 改用 `build_env()`，清掉 `SERVER_PORT` / `SERVER__PORT`。
2. `memory_precheck()` 支持 `R8_MIN_FREE_MB` 覆盖默认 3200MB
   （只在确知没有其他站点时使用，避免把常规启动变成压内存）。
3. `port_pid_map()` 对 `netstat` 输出为 `None` 做兜底，修掉 `stop` 时的
   `AttributeError: 'NoneType' object has no attribute 'splitlines'`。

## 当前状态

R8 正在运行（Nacos zip + 6 服务），可用内存约 2.1GB。
不用时执行：

```
python scripts\start_r8_cloud.py stop
```

注意：`stop` 会停 Nacos 与 6 个服务；Redis（6379）不在 R8 管理范围内，
如果 Redis 没起，system 服务会因 `Unable to connect to Redis` 启动失败。
