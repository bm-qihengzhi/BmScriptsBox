---
title: Windows 定时任务脚本 - 声明式定时调度配置
description: 不忙脚本盒子定时任务——设定参数后脚本在预设时间自动静默运行、无需人工干预；如何声明可配置参数、设静默终端模式、并给脚本完善的退出机制
status: 稳定
docType: how-to
audience: 脚本开发者
docVersion: 0.3.0
---

# 定时任务

> **设定好参数，脚本到点自动运行，全程无人值守。**

定时任务让脚本在预设时间自行启动，全程无需人工干预。

**它和「节点 / 脚本联动」无关**，本质是一次**自动化的普通触发**：`environment.invoke_mode = "scheduled"`。它没有调用方，也不需要回传信封（`output_json` 默认为 `null`，仅在你主动上报结果时才用到）。盒子只负责**到点启动**。从启动、处理到结束，**全程由脚本自己跑完**。这正是脚本要声明 `[bmscriptsbox.schedule]` 的原因：**自证"我的脚本能无人值守自动跑完整流程"**。

---

## 盒子怎么做到的

- **不在 TOML 里声明任务**——用户在盒子的「定时任务」页面自行创建（固定间隔 / 随机间隔 / 倒计时 / 每天 / 每周）。
- 运行期，盒子到点启动脚本，注入 `invoke_mode = "scheduled"`；运行方式按 `runtime.terminal` 的声明（不是强制静默）。
- **`output_json` 默认为 `null`**。它是一个**可选的上报通道**：需要脚本上报执行结果时，盒子会分配一个文件路径，脚本用 `if out:` 判空后写入即可（见[上报执行结果](#让定时任务上报执行结果可选)）。不写不影响任务运行。
- 输入来源：`inputs` 与 `params` 都能在定时任务表单里配置——盒子取你在 `[[bmscriptsbox.inputs]]` / `[[bmscriptsbox.params]]` 声明的默认值，叠加用户在表单里填的覆盖值合并注入。完全无输入的脚本（如「打开某个软件」「关闭某服务」）同样可定时，因为它的自动化流程就是"启动 / 关停"。

**定时任务不需要写信封、不关心 `is_node`、不会 403**。你只要让脚本能在"被盒子启动后，自己把整个流程自动跑完并退出"的状态下工作。

---

## 三步上手：让脚本能被定时

**前提**：脚本要在盒子的「定时任务」里可选，必须先 opt-in 声明可被调度：

```toml
[bmscriptsbox.schedule]
enabled = true   # 不写 = 不出现在定时任务脚本列表
```

声明并重新安装后，脚本才会出现在定时任务 UI 的脚本列表里。下面四条保证脚本在无人值守时能正常跑完。

### 1. 把「手动运行必须填的东西」都声明成 params，并给默认值

定时任务无人值守，没有人帮你填参数。盒子会按你声明的 `params` 在定时任务表单里生成配置项，用户建任务时填一次，之后全自动。

```toml
[[bmscriptsbox.params]]
name = "script_name"
type = "str"
default = ""            # 合理默认值；空串则靠 required 提示用户必填
description = "要定时播放的录制动作名"
required = true         # 缺它任务没法跑 → 表单中标 * 提示必填
```

要点：

- 代码里 `params.get("xxx")` 读取、且定时场景必须有的，全部要声明成 `params`。
- 有文件 / 路径 / 单条文本输入时，也可用 `inputs` 声明——定时任务表单同样能填。
- 给 `default` → 盒子合并参数时它一定存在，脚本侧 `.get(name, default)` 永不缺值。
- `required = true` → 定时任务表单会在该字段后标 `*`，提示用户必填。
- `choices` 限制取值、`description` 说明用途，用户在表单里一眼看懂。

### 2. 用 `.get` 读取，永远不阻塞

```python
params = payload.get("params", {})
script_name = params.get("script_name", "")
```

即使在定时任务里，盒子也已把默认值合并注入；真缺且无默认的必填会在创建 / 运行前被拦下，根本到不了脚本。绝不要在定时路径上用 `input()` 等人输入。

### 3. `terminal` 设成 `never`（静默）

```toml
[bmscriptsbox.runtime]
terminal = "never"
```

定时任务本就该在后台安静跑完。四种模式的差异见 [终端模式详解](./terminal-mode)。

::: warning 调试别用 never
`never` 模式下 stdout / stderr 被丢弃，你**看不到任何输出**，出错极难排查。先用 `always` 把逻辑跑通，确认无误再改回 `never`。
:::

### 4. 完善的退出机制（最关键）

无人值守意味着脚本要自己完成启动、运行、退出整个流程，不能停在等待人工操作的状态。

- **正常完成 → 以退出码 0 退出**。CLI 脚本跑完自然结束即可。
- **GUI 脚本（tkinter / PySide）跑完必须主动关窗口、退出进程**——否则进程常驻，定时任务永远停在「运行中」，下次触发也起不来。在「活儿干完」的回调里退出：

  ```python
  # tkinter：收尾动作（如提示音）播完后关根窗口，mainloop() 返回 → 进程自然退出
  def on_done(ok):
      if auto_mode:
          root.after(1000, root.destroy)
  ```

- **出错也要退**：工作包在 `try / except` 里，异常时记录日志并以**非 0 退出码**退出（如 `sys.exit(1)`），别让异常把主线程挂起。
- **不要在定时路径上弹窗、等点击、用 `input()`**——那等于让无人值守任务永远卡死。

---

## 完整示例：定时播放键鼠动作

```toml
[bmscriptsbox.runtime]
terminal = "never"        # 静默运行

[[bmscriptsbox.params]]
name = "script_name"
type = "str"
description = "要定时播放的录制动作名"
```

```python
# main.py（节选）
import sys

def main():
    script_name = None
    if len(sys.argv) > 1:
        script_name = read_param(sys.argv[1], "script_name")  # 从参数文件取
    app = App(auto_script=script_name)
    app.mainloop()   # 有 auto_script → 播完自动退出；没有 → 弹 UI 手动操作
```

```python
# App._on_replay_finished：播完收尾再退出
def _on_replay_finished(self, ok):
    if self._auto_script:
        self.after(1000, self._on_close)   # 1 秒后关窗口 → mainloop 返回 → 进程退出
```

一个合格的定时任务脚本：参数声明即可配置、静默运行、播完自动退出。

---

## 参数从哪来：定时任务 vs 手动触发

| 来源 | 手动触发（右键 / 快捷键） | 定时任务 |
| --- | --- | --- |
| `params` 默认值 | 来自 TOML | 来自 TOML |
| 用户覆盖 | 当次触发由盒子传入（或弹窗询问） | 用户在定时任务表单填一次，存为 `task_params` |
| 合并结果 | `默认值 + 当次传入` | `默认值 + 该任务的覆盖值` |

盒子**只保留你声明过的参数名**，并按声明类型强转（`str` / `int` / `float` / `bool`），见 [参数注入](./parameter-passing)。

---

## 让定时任务上报执行结果（可选）

定时任务每次跑完，盒子会记一条执行历史（时间 / 状态 / 消息）。记录展示在「定时任务」列表的**最近执行**列，以及**执行记录**对话框中。

想让记录更精确（而不只是"已执行"），脚本可以往 `environment.output_json` 写一个**信封**：

```python
import json, sys
payload = json.load(open(sys.argv[1], encoding='utf-8'))
env = payload["environment"]

# 只在被定时/需要上报时写（其余手动触发 output_json 为 null）
out = env.get("output_json")
if out:
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "code": 0,            # 0 成功，非 0 失败
            "msg": "已备份 3 个文件",  # 一句人能看懂的话
        }, f, ensure_ascii=False)
```

- 写了信封：执行记录显示**成功/失败**（按 `code`）+ `msg`
- 不写信封：盒子记录为「已执行」，仅时间与是否正常启动
- **盒子只记 `code` 与 `msg`**：标签说的是给人看的，额外业务键不会被记录或展示，往 `msg` 写清结果即可
- 信封格式与错误码见 [输出信封契约](./script-linking)。

---

## 上线前自检

- [ ] 所有「定时场景必填」的参数都声明为 `[[bmscriptsbox.params]]` 且给了 `default`
- [ ] 代码里一律用 `params.get(name, default)` 读取，无 `input()` / 弹窗等待
- [ ] `runtime.terminal` 按脚本特性选择——纯后台静默任务用 `"never"`，需要可见窗口（如打开某个带界面的软件）用 `"always"`/`"auto"`
- [ ] CLI 跑完自然退出；GUI 在干完活后主动 `destroy()` / `sys.exit`，不留常驻进程
- [ ] 异常被捕获并以非 0 退出码退出，不会挂死
- [ ] 先用 `terminal = "always"` 调试看到完整流程，确认无误后再切回符合脚本的目标模式

---

## 相关文档

- 参数怎么声明与合并 → [参数注入](./parameter-passing)
- 静默 / 弹窗怎么选 → [终端模式详解](./terminal-mode)
- 声明运行参数 → [输入输出契约](./io-contract)
- 触发方式配置 → [右键菜单触发](./context-menu)、[快捷键触发](./hotkey)、[超级复制触发](./quick-copy)