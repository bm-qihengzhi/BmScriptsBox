---
title: Windows 右键菜单脚本 - 选中文件即可运行
description: 脚本如何出现在文件资源管理器的右键菜单——context_menu 配置、targets 显示位置、filters 扩展名白名单与排查方法
status: 稳定
docType: how-to
audience: 脚本开发者
docVersion: 0.3.0
---

# 右键菜单触发

> **盒子提供从右键菜单启动脚本的能力**

声明 [bmscriptsbox.triggers.context_menu] 即可让脚本出现在右键菜单中，无需编码。用户使用右键菜单启动脚本时，盒子会根据声明自动注入选中的文件/文件夹路径及当前目录路径作为启动参数。

---

## 配置方式

```toml
[bmscriptsbox.triggers.context_menu]
enabled = true
targets = ["files", "directory"]
filters = [".txt", ".md"]
```

## 字段说明

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `enabled` | 布尔值 | 否 | `false` | 是否启用右键菜单 |
| `targets` | 字符串数组 | 是 | — | 菜单显示的位置 |
| `filters` | 字符串数组 | 否 | `[]` | 文件扩展名白名单 |

## targets 可选值

| 值 | 显示位置 | 适用场景 |
| --- | --- | --- |
| `"files"` | 选中文件上右键 | 处理文件的脚本 |
| `"directory"` | 选中文件夹上右键 | 处理文件夹的脚本 |
| `"background"` | 文件夹空白处右键 | 以当前目录为工作区 |

支持组合：`targets = ["files", "background"]` 表示文件上右键和空白处右键都会显示。

## filters 规则

`filters` 仅在 `targets` 包含 `"files"` 时生效，采用白名单机制：

- 只有所有选中文件的扩展名都匹配时，菜单才显示
- 选中了不匹配的文件 → 菜单不出现，脚本也不运行
- 空列表表示不限制扩展名

```toml
# 只有选中的文件全是 .txt 或 .md 时，菜单才显示
filters = [".txt", ".md"]
```

> 需要排除某些类型、而非仅允许某些类型时，在脚本内部自行写过滤逻辑。

---

## 常见问题

**Q：右键菜单没出现？**
A：按顺序检查：

1. `context_menu.enabled` 是否为 `true`
2. `targets` 是否包含你右键的位置
3. 配了 `filters` 时，所有选中文件的扩展名都要匹配
4. 安装后是否重启了资源管理器

---

## 相关文档

- 触发后参数怎么传 → [参数注入](./parameter-passing)
- 触发时自动弹参数界面 → [自动生成运行界面](./auto-generated-ui)
- 快捷键触发 → [快捷键触发](./hotkey)
- 超级复制触发 → [超级复制触发](./quick-copy)