"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from pydantic import (BaseModel, ConfigDict, Field, model_validator,
                      ValidationInfo, field_validator)

from app.utils import BmError
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from .input_match_spec import (
    MAX_REGEX_PATTERN,
    PATH_MATCH_FIELDS,
    PREDICATE_FIELDS,
    PREDICATE_OPS,
    SIMPLE_MATCH_FIELDS,
    TEXT_FORMATS,
    TEXT_MATCH_FIELDS,
    URL_MATCH_FIELDS,
)


# --- 二进制来源白名单：直连模式仅允许 GitHub ---
GITHUB_ALLOWED_HOSTS = {
    "github.com", "api.github.com", "codeload.github.com",
    "raw.githubusercontent.com", "objects.githubusercontent.com",
}
GITHUB_ALLOWED_HOST_SUFFIX = ".githubusercontent.com"

# 保留命令名：直连模式禁止以这些名字注册 shim，避免劫持盒子/系统核心工具
RESERVED_COMMAND_NAMES = {
    "python", "pythonw", "python3", "pip", "pip3",
    "node", "nodejs", "npm", "npx", "pnpm", "yarn",
    "uv", "uvx", "pwsh", "powershell",
    "cmd", "command", "bash", "sh", "git",
    "msiexec", "reg", "regedit", "rundll32", "cscript", "wscript",
    "explorer", "taskkill", "tasklist", "where", "whoami", "net", "sc",
    "conhost", "schtasks", "wmic", "certutil", "bitsadmin",
}


def _is_allowed_binary_url(url: str) -> bool:
    """直连下载地址校验：必须为 https 且属地 GitHub 白名单域名"""
    try:
        p = urlparse(url)
    except Exception:
        return False
    if p.scheme != "https":
        return False
    host = (p.netloc or "").split("@")[-1].split(":")[0].lower()
    if not host:
        return False
    return host in GITHUB_ALLOWED_HOSTS or host.endswith(GITHUB_ALLOWED_HOST_SUFFIX)


def _reserve_name_of(name: str) -> str:
    """取命令名的基名（去掉 .exe 后缀、小写），用于保留名比对"""
    base = (name or "").strip().lower()
    if base.endswith(".exe"):
        base = base[:-4]
    return base



@dataclass
class ScriptLoadResult:
    """脚本加载结果的容器"""
    success: bool
    config: Optional[Any] = None  # 成功时的 Pydantic 对象
    error_messages: List[str] = None  # 失败时的友好错误描述



# --- 1. 基础信息子模型 ---
class ScriptInfo(BaseModel):
    id: UUID
    name: str = Field(min_length=1)
    desc: str = ""
    icon: str = ""
    version: str = Field(pattern=r'^\d+\.\d+\.\d+$')

    @field_validator('icon')
    @classmethod
    def check_not_absolute(cls, v: str) -> str:
        if os.path.isabs(v) or v.startswith('\\\\'):
            raise BmError('config.path.relative', field='icon')
        return v

    @model_validator(mode='after')
    def resolve_icon_path(self, info: ValidationInfo):
        script_dir = info.context.get("script_dir")
        if script_dir and self.icon and not os.path.isabs(self.icon):
            self.icon = os.path.normpath(os.path.join(script_dir, self.icon))
        return self


# --- 2. AI 模型声明 ---
class ScriptModel(BaseModel):
    source: str = "modelscope"
    repo_id: str = Field(min_length=1)
    files: List[str] = Field(default_factory=lambda: ["*"])

    @field_validator('source')
    @classmethod
    def check_source(cls, v: str) -> str:
        allowed = {"modelscope", "huggingface"}
        if v.lower() not in allowed:
            raise BmError('config.enum.invalid', field='source',
                           allowed=allowed, value=v)
        return v.lower()


# --- 2.5 外部二进制声明 ([[bmscriptsbox.runtime.binaries]]) ---
class ScriptBinary(BaseModel):
    """
    外部二进制声明，支持两种模式：
    - 官方清单模式：只写 name（+可选 version），从盒子官方二进制仓库解析下载；
    - 作者直连模式：写 url（GitHub 直链），盒子下载 → 校验 → 解压/安装 → 注册 shim。
    兼容旧形态：{name="x", version=">=1"} 直接解析为官方清单模式。
    """
    name: str = Field(min_length=1)                 # 命令名 / shim 名
    version: str = ""                               # 官方模式：版本约束
    url: Optional[str] = None                       # 直连模式：GitHub 直链（可为 /releases/latest/download/...）
    sha256: Optional[str] = None                    # 直连模式：可选，固定版本建议填写；latest 走 TOFU
    bin: List[str] = Field(default_factory=list)    # 解压后需暴露的可执行文件名（单文件可留空）
    extract: bool = True                            # True=按归档解压；False=单文件/exe/msi
    install: Optional[Dict[str, Any]] = None        # exe/msi 静默安装参数（需用户二次确认）
    env_set: Optional[bool] = None                  # 是否生成命令并加入 PATH；None=用默认（官方取清单值、直连取 false）

    @field_validator('url')
    @classmethod
    def check_url(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not str(v).strip():
            return None
        v = str(v).strip()
        if not _is_allowed_binary_url(v):
            raise BmError('config.binary.github_url')
        return v

    @field_validator('sha256')
    @classmethod
    def check_sha256(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not str(v).strip():
            return None
        v = str(v).strip().lower()
        if not re.fullmatch(r'[0-9a-f]{64}', v):
            raise BmError('config.binary.sha256')
        return v

    @model_validator(mode='after')
    def check_direct_mode(self):
        # 直连模式（写了 url）：禁止使用保留命令名，防止劫持核心工具
        if self.url:
            if _reserve_name_of(self.name) in RESERVED_COMMAND_NAMES:
                raise BmError('config.binary.reserved_name', name=self.name)
        return self


# --- 3. 运行时子模型 ---
class ScriptRuntime(BaseModel):
    language: str = Field(min_length=1)
    language_version: str
    entry: str = Field(min_length=1)
    terminal: str = "always"
    concurrency: Literal["single", "forward"] = "single"
    binaries: List[ScriptBinary] = Field(default_factory=list)

    @field_validator("concurrency", mode="before")
    @classmethod
    def normalize_concurrency(cls, v):
        if v is None or not str(v).strip():
            return "single"
        return str(v).strip().lower()

    @field_validator('binaries', mode='before')
    @classmethod
    def filter_empty_binaries(cls, v):
        """兼容旧配置中的空占位条目：name/url 均为空则丢弃"""
        if not v:
            return v
        out = []
        for item in v:
            if isinstance(item, dict):
                if not (str(item.get('name') or '').strip() or str(item.get('url') or '').strip()):
                    continue
            out.append(item)
        return out

    @field_validator('entry')
    @classmethod
    def check_not_absolute(cls, v: str) -> str:
        if os.path.isabs(v) or v.startswith('\\\\'):
            raise BmError('config.path.relative', field='entry')
        return v

    @model_validator(mode='after')
    def resolve_entry_path(self, info: ValidationInfo):
        script_dir = info.context.get("script_dir")
        if script_dir and self.entry and not os.path.isabs(self.entry):
            self.entry = os.path.normpath(os.path.join(script_dir, self.entry))
        return self

    @model_validator(mode='after')
    def validate_language_and_version(self):
        lang = self.language.lower()
        ver = self.language_version.strip()

        # 1. 如果是 bat，允许为空，直接通过
        if lang in ("bat", "html"):
            return self

        # 2. 如果是其他语言，必须填写版本号
        if not ver:
            raise BmError('config.version.required', language=self.language)

        # 3. 校验版本号格式 (要求以比较运算符开头，如 >=3.8, ==3.10)
        # 正则解析：开头必须是 > 或 < 或 = 或 >= 或 <= 或 ==，后面跟着数字和点
        pattern = r'^(>=|<=|==|>|<)(?i:v)?\d+(\.\d+)*$'
        if not re.match(pattern, ver):
            raise BmError('config.version.invalid', version=ver)


        return self


# --- 4. 触发器子模型 (重点) ---
class ContextMenuConfig(BaseModel):
    enabled: bool = False
    targets: List[str] = Field(default_factory=list)
    filters: List[str] = Field(default_factory=list)


class ShortcutConfig(BaseModel):
    enabled: bool = False
    input_type: str = ''
    filters: List[str] = Field(default_factory=list)
    hotkey: Optional[str] = None   # 全局快捷键组合（如 "ctrl+alt+k"），供数据库热键唯一性校验使用


class QuickCopyConfig(BaseModel):
    enabled: bool = False


# --- 5. IO 与 工作流 ---
def _normalize_string_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        value = value.strip()
        return [value] if value else []
    if isinstance(value, (list, tuple, set)):
        return [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]
    return value


class InputPredicate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    op: str
    value: Any = None

    @field_validator('field')
    @classmethod
    def check_field(cls, v: str) -> str:
        value = str(v or "").strip()
        if value not in PREDICATE_FIELDS:
            raise BmError('config.enum.invalid', field='inputs.match.field',
                           allowed=sorted(PREDICATE_FIELDS), value=value)
        return value

    @field_validator('op')
    @classmethod
    def check_op(cls, v: str) -> str:
        value = str(v or "").strip()
        if value not in PREDICATE_OPS:
            raise BmError('config.enum.invalid', field='inputs.match.op',
                           allowed=sorted(PREDICATE_OPS), value=value)
        return value

    @model_validator(mode='after')
    def validate_value(self):
        if self.op in ('in', 'not_in'):
            if not isinstance(self.value, (list, tuple, set)):
                raise BmError('config.match.value_array', op=self.op)
        elif self.op in ('gte', 'lte'):
            if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
                raise BmError('config.match.value_number', op=self.op)
        elif self.op == 'regex':
            if not isinstance(self.value, str) or not self.value:
                raise BmError('config.match.regex_empty')
            if len(self.value) > MAX_REGEX_PATTERN:
                raise BmError('config.match.regex_length', limit=MAX_REGEX_PATTERN)
            try:
                re.compile(self.value)
            except re.error as exc:
                raise BmError('config.match.regex_invalid', reason=str(exc)) from exc
        return self


class InputMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["url", "path", "text", "magnet"]
    weight: int = 0
    ignore_case: bool = False

    scheme: List[str] = Field(default_factory=list)
    domain: List[str] = Field(default_factory=list)
    host: List[str] = Field(default_factory=list)
    path: str = ""
    query_contains: str = ""
    ext: List[str] = Field(default_factory=list)
    exists: Optional[bool] = None
    is_file: Optional[bool] = None
    is_folder: Optional[bool] = None
    name: str = ""

    format: List[str] = Field(default_factory=list)
    prefix: str = ""
    suffix: str = ""
    contains: str = ""
    equals: str = ""
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    regex: str = ""

    all: List[InputPredicate] = Field(default_factory=list)
    none: List[InputPredicate] = Field(default_factory=list)

    @field_validator('scheme', 'domain', 'host', 'ext', 'format', mode='before')
    @classmethod
    def normalize_list(cls, v):
        return _normalize_string_list(v)

    @model_validator(mode='after')
    def validate_rule(self):
        for field in ('scheme', 'domain', 'host', 'format'):
            values = getattr(self, field)
            setattr(self, field, [
                value.lower() for value in values if value
            ])
        self.ext = [
            value.lower() if value.startswith('.') else ('.' + value.lower())
            for value in self.ext if value
        ]

        if self.min_length is not None and self.max_length is not None:
            if self.min_length > self.max_length:
                raise BmError('config.match.length_range')

        simple = self._active_simple_fields()
        advanced = bool(self.all or self.none)
        if advanced and simple:
            raise BmError('config.match.mixed')

        allowed = set()
        if self.kind == 'url':
            allowed |= URL_MATCH_FIELDS
        elif self.kind == 'path':
            allowed |= PATH_MATCH_FIELDS
        elif self.kind == 'text':
            allowed |= TEXT_MATCH_FIELDS
        invalid = simple - allowed
        if invalid:
            raise BmError('config.match.unsupported_field',
                           kind=self.kind, fields=sorted(invalid))

        for name in self.format:
            if name not in TEXT_FORMATS:
                raise BmError('config.enum.invalid', field='inputs.match.format',
                               allowed=sorted(TEXT_FORMATS), value=name)

        if self.regex:
            if len(self.regex) > MAX_REGEX_PATTERN:
                raise BmError('config.match.regex_length', limit=MAX_REGEX_PATTERN)
            try:
                re.compile(self.regex)
            except re.error as exc:
                raise BmError('config.match.regex_invalid', reason=str(exc)) from exc
        return self

    def _active_simple_fields(self):
        active = set()
        for name in SIMPLE_MATCH_FIELDS:
            if name in ('kind', 'weight', 'ignore_case', 'all', 'none'):
                continue
            value = getattr(self, name)
            if name in ('min_length', 'max_length'):
                if value is not None:
                    active.add(name)
            elif isinstance(value, bool):
                if value is not None:
                    active.add(name)
            elif isinstance(value, (int, float)):
                if value != 0:
                    active.add(name)
            elif value:
                active.add(name)
        return active


class SearchTrigger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    match: List[InputMatch] = Field(default_factory=list)


class TriggersConfig(BaseModel):
    context_menu: ContextMenuConfig = Field(default_factory=ContextMenuConfig)
    shortcut: ShortcutConfig = Field(default_factory=ShortcutConfig)
    quick_copy: QuickCopyConfig = Field(default_factory=QuickCopyConfig)
    search: Optional[SearchTrigger] = None


class IOParam(BaseModel):
    name: str = ""
    label: str = ""             # 输入显示名（表单标签；空则回退 name）
    type: str = ""            # 留空=占位（filter_empty_io 过滤）；否则 list（路径数组）| str（文本）
    exts: List[str] = Field(default_factory=list)
    description: str = ""
    pick: Optional[str] = None   # 本地文件选择器：files | folders | both；不写 = 纯文本多行
    # 注：data[name] 始终为数组；type 仅用于 UI/选择器提示

    @model_validator(mode='before')
    @classmethod
    def reject_legacy_match(cls, data):
        if isinstance(data, dict) and "match" in data:
            raise BmError('config.match.removed')
        return data

    @field_validator('type')
    @classmethod
    def check_type(cls, v: str) -> str:
        allowed = {"str", "list"}
        if v and v not in allowed:
            raise BmError('config.enum.invalid', field='inputs.type',
                           allowed=allowed, value=v)
        return v

    @field_validator('pick')
    @classmethod
    def check_pick(cls, v: Optional[str]) -> Optional[str]:
        allowed = {"files", "folders", "both"}
        if v and v not in allowed:
            raise BmError('config.enum.invalid', field='inputs.pick',
                           allowed=allowed, value=v)
        return v


# --- 5.5 脚本运行参数 ([[bmscriptsbox.params]]) ---
class ScriptParam(BaseModel):
    name: str = Field(min_length=1)
    label: str = ""               # 参数显示名（表单标签；空则回退 name）
    type: str = "str"             # str | int | float | bool | list | dict（JSON 数据类型）
    default: Any = None
    required: bool = False
    choices: List[str] = Field(default_factory=list)
    choice_labels: Optional[Dict[str, str]] = None   # 取值→显示名（仅 UI 显示；传参仍用取值）
    description: str = ""
    secret: bool = False
    when: Optional[Dict[str, Any]] = None   # 联动显隐：{field=<另一参数名>, eq=<值>} 或 {field, in=[..]}

    @field_validator('type')
    @classmethod
    def check_type(cls, v: str) -> str:
        allowed = {"str", "int", "float", "bool", "list", "dict"}
        if v not in allowed:
            raise BmError('config.enum.invalid', field='params.type',
                           allowed=allowed, value=v)
        return v

    @field_validator('choice_labels')
    @classmethod
    def check_choice_labels(cls, v, info):
        if not v:
            return v
        choices = info.data.get('choices') or []
        extra = [k for k in v if k not in choices]
        if extra:
            raise BmError('config.param.choice_labels', keys=extra)
        return v

    @field_validator('when')
    @classmethod
    def check_when(cls, v: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if v is None:
            return v
        if not isinstance(v, dict):
            raise BmError('config.param.when_type')
        if not isinstance(v.get('field'), str) or not v.get('field'):
            raise BmError('config.param.when_field')
        # eq / in 可省略 → 揭示型：仅随被依赖字段的显隐而显隐
        return v


# --- 5.6 脚本依赖 ([[bmscriptsbox.dependencies]]) ---
class ScriptDependency(BaseModel):
    id: str = Field(min_length=1)   # 被依赖脚本的 script_id（社区已发布）


# --- 5.7 脚本节点声明 ([bmscriptsbox.node]) ---
class ScriptNode(BaseModel):
    enabled: bool = True   # 声明本脚本可作为节点被联动调用


# --- 5.8 脚本定时任务声明 ([bmscriptsbox.schedule]) ---
class ScriptSchedule(BaseModel):
    enabled: bool = True   # 声明本脚本可被定时任务调度（须能无人值守、仅凭 params 运行）


# --- 5.9 脚本参数表单声明 ([bmscriptsbox.params_form]) ---
class ScriptParamsForm(BaseModel):
    enabled: bool = True   # 声明：交互式运行本脚本时，盒子先生成参数表单让用户填写


# --- 6. 顶层根模型 ---
class ScriptTomlConfig(BaseModel):
    info: ScriptInfo
    runtime: ScriptRuntime
    triggers: Optional[TriggersConfig] = None
    inputs: List[IOParam] = Field(default_factory=list)
    outputs: List[IOParam] = Field(default_factory=list)
    params: List[ScriptParam] = Field(default_factory=list)
    dependencies: List[ScriptDependency] = Field(default_factory=list)
    node: Optional[ScriptNode] = None
    schedule: Optional[ScriptSchedule] = None
    params_form: Optional[ScriptParamsForm] = None
    workflow: Dict[str, bool] = Field(default_factory=lambda: {"workflow_enabled": True})
    models: List[ScriptModel] = Field(default_factory=list)

    @model_validator(mode='after')
    def filter_empty_io(self):
        # 如果 name 和 type 都是空的，说明是占位符，直接过滤掉
        self.inputs = [i for i in self.inputs if i.name or i.type]
        self.outputs = [o for o in self.outputs if o.name or o.type]
        return self

    @model_validator(mode='after')
    def validate_search(self):
        search = self.triggers.search if self.triggers else None
        if not search or not search.enabled:
            return self
        if not self.inputs:
            raise BmError('config.search.target')
        return self

    @model_validator(mode='after')
    def validate_params(self):
        # inputs 严格 ≤1；副文件输入用 params 的 str 类型声明路径参数
        if len(self.inputs) > 1:
            raise BmError('config.inputs.too_many')

        names = [p.name for p in self.params]
        if len(names) != len(set(names)):
            raise BmError('config.duplicate_param')

        # when.field 必须指向已声明的 params：指向不存在的字段会让该字段永远无法显现
        for p in self.params:
            ref = (p.when or {}).get('field')
            if ref and ref not in names:
                raise BmError('config.param.when_unknown',
                               name=p.name, ref=ref)

        for p in self.params:
            if p.type != 'str' and p.choices:
                raise BmError('config.param.choices_type',
                               name=p.name, type=p.type)
        return self

    @model_validator(mode='after')
    def validate_dependencies(self):
        ids = [d.id for d in self.dependencies]
        if len(ids) != len(set(ids)):
            raise BmError('config.duplicate_dependency')
        if str(self.info.id) in ids:
            raise BmError('config.dependency.self')
        return self

    @model_validator(mode='after')
    def validate_node(self):
        # 声明可作为节点的脚本必须有返回能力（至少 1 个 outputs）
        if self.node and self.node.enabled and not self.outputs:
            raise BmError('config.outputs.required')
        return self
