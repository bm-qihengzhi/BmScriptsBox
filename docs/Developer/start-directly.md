---
title: 直接启动
description: 从盒子窗口点击脚本卡片即可启动脚本——该方式恒定可用、无需声明；未配置运行界面时 data 恒为空。
status: 稳定
docType: explanation
audience: 脚本开发者
docVersion: 0.3.0
---

# 直接启动


「直接启动」指用户在盒子主界面点击脚本卡片触发脚本。它是最基础、也最特殊的触发方式：不依赖任何 `triggers` 声明，装上就能点。

---

## 特性要点

- **恒定可用**：所有脚本都具备，不需要在 TOML 里声明任何触发字段
- **区别于其他触发**：右键菜单、快捷键、超级复制都需要声明对应的 `triggers` 才会注册；直接启动不需要
- **调用方式**：`environment.invoke_mode = "manual"`（手动触发）

---

## 参数行为

直接启动时，JSON 参数文件里的 `data` 段取决于是否配置了 `[bmscriptsbox.params_form]`：

### 未配置运行界面：data 恒为空

没有声明 `[bmscriptsbox.params_form]` 时，盒子直接启动脚本，注入的 `data` **恒为空值**：

```json
{
    "environment": { "...": "盒子信息" },
    "data": {},
    "params": {}
}
```

脚本读到的 `data` 是空对象。适合不需要外部输入的脚本（如清空回收站、打开某个工具）。

### 配置了运行界面：按界面参数注入

声明了 `[bmscriptsbox.params_form]` 时，盒子会弹出运行界面，把 UI 上用户设定的值注入 JSON 参数文件后启动脚本：

- **`inputs` 的值** → 注入 `data` 段
- **`params` 的值** → 注入 `params` 段

```json
{
    "environment": { "...": "盒子信息" },
    "data": {
        "target_paths": ["C:/a.txt"]
    },
    "params": {
        "quality": 80
    }
}
```

脚本端按声明读取即可：

```python
paths = payload["data"]["target_paths"]
quality = payload["params"].get("quality", 80)
```

运行界面的完整机制见 [自动生成运行界面](./auto-generated-ui)。

---

## 对 terminal 配置的参考意义

直接启动是**唯一的"空数据"触发场景之一**：未配置运行界面时，`data` 恒为空。而 [终端模式详解](./terminal-mode) 里 `auto` / `inverse` 的切换依据正是**`data` 是否为空**。

开发者配置 `terminal` 字段时，可以结合这个特性预判窗口行为：

| 你的脚本 | 直接启动时 `data` | 建议 terminal |
| --- | --- | --- |
| 需要用户交互（GUI / CLI） | 空 | `always` |
| 后台批处理，无交互 | 空 | `never` |
| 想手动点击弹窗、被调用时静默 | 空 | `auto` |

::: tip 提示
`auto` / `inverse` 判断的是 `data` 是否为空，而不是脚本是否声明了 `inputs`。理解直接启动的"空 data"特性，就能准确预测脚本的行为。
:::

---

## 常见问题

**Q：不声明任何 triggers，用户怎么运行脚本？**
A：直接在盒子主界面点击脚本卡片即可——这就是直接启动，所有脚本默认具备。

**Q：直接启动时 data 一定是空的吗？**
A：未配置 `params_form` 时恒为空。配置了 `params_form` 时，`data` 会带上 UI 里用户填写的 `inputs` 值。

---

## 相关文档

- 参数文件的三段契约 → [参数注入](./parameter-passing)
- 运行界面怎么弹 → [自动生成运行界面](./auto-generated-ui)
- terminal 四种模式 → [终端模式详解](./terminal-mode)