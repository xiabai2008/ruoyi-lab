# 工单 C2b：修 SCF 启动不可复现（环境变量抢端口）

> 执行者：opencode。验收者：lead。
> 只改 C2 的启停脚本，不碰源码业务逻辑、不碰其他靶场、不碰扫描器。

---

## 零、现象（lead 19:20 实测）

`python scripts\c2_scf.py start` 失败：

```
Tomcat initialized with port(s): 62148 (http)
PortInUseException: Port 62148 is already in use
APPLICATION FAILED TO START
```

SCF 的 `application.yml` 写的是 `server.port: 19314`，但实际去绑 62148。
原因：启动脚本直接 `env = dict(os.environ)`，把宿主的 **`SERVER__PORT=62148`** 原样传给了
Spring Boot。Spring 的 relaxed binding 把它当成 `server.port`，优先级高于 yml，于是端口被劫持。
62148 已被别的进程占用（PID 6948），启动即失败。

对照：

- `c2_sba.py` 传了 `--server.port=%d`，命令行参数优先级最高，所以没中招；
- `c2_scf.py` 只传了 `-jar`，中招；
- `c2_s4s.py` 是 Tomcat，不走 Spring Boot，不涉及。

副作用：失败后 `.state/C2-scf.pid` 残留（19:20 那次），下次 status 会误判。

---

## 一、C2b-1 三个脚本统一做环境净化

在 `c2_sba.py`、`c2_s4s.py`、`c2_scf.py` 构造 `env` 的地方，统一加：

```python
# 宿主环境可能带 SERVER_PORT / SERVER__PORT（Spring relaxed binding 会当成 server.port），
# 不清掉会劫持端口，导致启动到随机端口或直接 PortInUse。
for key in ("SERVER_PORT", "SERVER__PORT"):
    env.pop(key, None)
```

## 二、C2b-2 SCF 显式传端口

`c2_scf.py` 的 java 命令加上：

```
"--server.port=19314"
```

命令行参数优先级最高，双保险。

## 三、C2b-3 失败清理 PID

三个脚本在「进程提前退出 / 探活超时」分支里，必须删除自己的 PID 文件（当前 SCF 没删）。
先删掉现存的 `.state/C2-scf.pid`。

## 四、C2b-4 回归：带毒环境变量启动

`verify_c2.py` 增加一条（或改造现有第 8–10 项），在启动子进程前把
`SERVER__PORT=62148` 注入环境，验证：

1. `c2_sba.py start` 仍在 19311/19312
2. `c2_s4s.py start` 仍在 19313
3. `c2_scf.py start` 仍在 19314
4. 三座 stop 后端口均释放、无残留 PID

另外加一条：SCF `start → stop → start` 连续两轮都成功。

---

## 五、验收

```
set SERVER__PORT=62148
python scripts\c2_scf.py start     # 必须绑 19314
python scripts\c2_scf.py status    # listening=True
python scripts\c2_scf.py stop
python scripts\c2_scf.py start     # 第二轮仍成功
python scripts\c2_scf.py stop
python scripts\verify_c2.py        # 全绿
```

贴：

1. 带 `SERVER__PORT=62148` 时 SCF 的启动日志前 10 行（必须出现 `port(s): 19314`）
2. 两轮 start/stop 的 status
3. `verify_c2.py` 的完整结果（实际执行 N 项）
4. `.state` 下无残留 C2-*.pid
