---
title: 单实例与并发
description: 不忙盒子脚本并发策略——concurrency 的 single / forward 语义、GUI 单实例参数转发与盒子/脚本职责边界。
status: 稳定
docType: reference
audience: 脚本开发者
docVersion: 0.3.0
---

# 单实例与并发

> **默认情况下，同一个脚本同时只允许一个进程。自带 GUI 的常驻脚本可以声明 `forward`，由脚本自己把新参数转发给已有窗口。**

---

## 默认行为：`single`

不声明 `concurrency` 时，盒子对每个 `script_id` 维护一个全局运行键：

- 第一次触发：占用运行键，启动脚本；
- 脚本运行期间，再次触发同一脚本：盒子直接拒绝，并提示「脚本正在运行中，请等待完成」；
- 脚本进程退出后，运行键释放。

这对大多数脚本是安全的默认值：

- 防止热键连按、双击卡片、右键重复点击启动多个实例；
- 避免批量转码、写同一目录的脚本互相踩；
- 定时任务不会因为调度间隔短而无限叠加。

但有一种情况不适用：**自带 GUI 的脚本**。GUI 进程会一直存活，运行键一直不释放，第二次触发就永远被拒绝。

---

## 声明并发策略

在 `bm-scripts-box-rc.toml` 的 `[bmscriptsbox.runtime]` 段声明：

```toml
[bmscriptsbox.runtime]
language = "python"
language_version = ">=3.8"
entry = "main.py"

# single（默认）| forward
concurrency = "forward"
```

| 值 | 行为 | 适用 |
| --- | --- | --- |
| `single` | 默认。同一脚本同时只允许一个进程；重复触发拒绝 | 普通脚本 |
| `forward` | 不查重；每次触发都启动新进程，由脚本自己转发给已有实例 | 自带 GUI 的翻译、预览、编辑器等 |

> 当前只支持 `single` / `forward`。`queue`（排队）和 `replace`（替换）是后续规划，不要在当前配置中使用。

修改 TOML 后，需要重新安装或更新脚本，让盒子把新配置写入本地脚本库。

---

## `forward` 的工作方式

```text
第一次触发
  → 盒子构造参数 JSON，启动进程 A
  → 进程 A 显示 GUI，处理参数

第二次触发
  → 盒子不查重，构造新的参数 JSON，启动进程 B
  → 进程 B 启动后先检测：已有实例吗？
      ├─ 有：读取 JSON 内容，通过 IPC 发给进程 A，然后退出
      └─ 没有：进程 B 成为第一个实例，显示 GUI
  → 进程 A 收到新内容，在当前 GUI 继续处理
```

关键点：

- 盒子只负责**不拦截**和**把参数交给新进程**；
- 盒子不解析脚本的 IPC，也不会把参数直接注入已有 GUI；
- 参数转发由脚本自己完成。

---

## 职责边界

| 环节 | 盒子负责 | 脚本负责 |
| --- | --- | --- |
| 策略声明 | 读取 `runtime.concurrency` | 在 TOML 声明 |
| 去重 | `single` 原子占用；`forward` 不拦截 | `forward` 自己保证单实例 |
| 参数构造 | 生成 JSON，`argv[1]` 传入 | 读取、校验 JSON |
| 第二次触发 | 启动新进程 | 检测已有实例，转发参数，退出 |
| 更新已有 GUI | 不参与 | 接收 IPC，在当前窗口执行 |
| 临时文件 | 进程退出后清理 | 退出前读完 JSON 内容 |
| 转发失败 | 不重试 | 降级为第一个实例 |
| 运行状态 | `forward` 不写运行键 | 自己维护窗口/队列状态 |

---

## 脚本侧实现要求

### 1. 读取参数

盒子启动脚本时，`argv[1]` 是参数 JSON 的路径：

```python
import sys
from pathlib import Path

def read_payload() -> str:
    if len(sys.argv) < 2:
        return ""
    path = Path(sys.argv[1])
    return path.read_text(encoding="utf-8") if path.is_file() else ""
```

第二个实例必须**读取文件内容**，不能只转发路径——盒子会在第二个进程退出后清理临时 JSON。

### 2. 检测已有实例

PySide6 推荐 `QLocalServer` / `QLocalSocket`：

```python
from PySide6.QtCore import QLocalServer, QLocalSocket, QThread

PIPE_NAME = "bms-your-script-uuid"

def forward(payload: str) -> bool:
    if not payload:
        return False
    sock = QLocalSocket()
    for _ in range(3):
        sock.connectToServer(PIPE_NAME)
        if sock.waitForConnected(300):
            sock.write(payload.encode("utf-8"))
            sock.flush()
            sock.waitForBytesWritten(1000)
            sock.disconnectFromServer()
            return True
        QThread.msleep(100)
    return False
```

### 3. 启动顺序

```python
payload = read_payload()

if forward(payload):
    sys.exit(0)  # 第二个实例：转发完成，退出

# 没有已有实例，成为第一个实例
QLocalServer.removeServer(PIPE_NAME)
server = QLocalServer()
if not server.listen(PIPE_NAME):
    # 并发启动竞争：再尝试转发一次
    if forward(payload):
        sys.exit(0)
    raise RuntimeError(f"无法监听 {PIPE_NAME}")
```

顺序不能反：

- **先尝试转发**；
- 只有确认没有已有实例，才 `removeServer` / `listen`；
- 第二个实例不能调用 `removeServer`，否则会删掉第一个实例的服务名。

### 4. 处理新内容

```python
def on_new_connection():
    sock = server.nextPendingConnection()
    sock.readyRead.connect(
        lambda: handle_payload(bytes(sock.readAll()).decode("utf-8")))

server.newConnection.connect(on_new_connection)
```

`handle_payload` 应该在 GUI 线程更新界面。如果脚本自己的窗口正在处理长任务，需要在脚本内部决定排队、丢弃还是打断。

### 5. 失败降级

- 没有已有实例 → 新进程成为第一个实例，正常显示 GUI；
- 连接超时/失败 → 同上；
- 已有实例崩溃但 IPC 残留 → `removeServer` 后重新监听。

---

## 定时任务

`forward` 只对人工触发生效：

- 卡片、热键、超级复制、HTTP 异步触发：遵守 `forward`；
- 定时任务触发：仍按 `single` 执行，忙时跳过本次，避免无人值守时叠出多个 GUI。

---

## 常见问题

### 声明了 `forward`，但还是只开了一个窗口？

检查脚本是否真的实现了单实例转发。盒子只负责启动第二个进程，不会替你连接已有 GUI。

### 第二个进程启动了，但新内容没生效？

常见原因：

- 只转发了 JSON 路径，盒子清理临时文件后第一个实例读不到；
- 第一个实例没有在 GUI 线程处理 IPC 消息；
- 第二个进程没有退出，导致出现两个窗口。

### 第一次启动就没有参数？

正常。`argv[1]` 可能不存在，脚本应该在没有参数时正常打开空窗口，或者提示用户输入。

### 普通脚本需要 `forward` 吗？

不需要。默认 `single` 更安全；只有“同一个 GUI 需要接收后续参数”的脚本才使用 `forward`。

---

## 相关文档

- 配置字段总览 → [声明式接入](./declarative-access)
- 参数 JSON 结构 → [参数注入](./parameter-passing)
- 盒子如何启动脚本 → [运行机制](./run-mechanism)
- 终端模式 → [终端模式详解](./terminal-mode)