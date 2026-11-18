"""数据层惰性导出。

ProjectGlobal 是全局状态（无重依赖），保持立即导入；
database（牵出 peewee/playhouse，~140ms）与 schemas（牵出 pydantic 链）
延后到首次实际使用时再加载，把这部分成本移出应用启动的关键路径。

实现：`from app.data import ScriptDatabase` 拿到的是 _LazyAttr 代理——
导入期零成本，首次属性访问/实例化/类方法调用时才加载真实类并转发。
全库已确认这四个类没有继承 / isinstance / 类型注解等会被代理破坏的用法。

注意：`from app.data.database import ...` 这类直接子模块导入会绕过本惰性层，
新增代码请走 `from app.data import ...`。
"""
from .globalVariables import ProjectGlobal

_LAZY = {
    'ScriptDatabase': ('.database', 'ScriptDatabase'),
    'ConfigDatabase': ('.database', 'ConfigDatabase'),
    'TaskDatabase': ('.database', 'TaskDatabase'),
    'ScriptEntity': ('.schemas', 'ScriptEntity'),
}

__all__ = ['ProjectGlobal', 'ScriptDatabase', 'ConfigDatabase', 'TaskDatabase', 'ScriptEntity']


class _LazyAttr:
    """惰性代理：首次属性访问/调用时加载真实对象并完全转发。"""

    __slots__ = ('_module', '_attr', '_real')

    def __init__(self, module: str, attr: str):
        object.__setattr__(self, '_module', module)
        object.__setattr__(self, '_attr', attr)
        object.__setattr__(self, '_real', None)

    def _load(self):
        real = object.__getattribute__(self, '_real')
        if real is None:
            import importlib
            module = object.__getattribute__(self, '_module')
            attr = object.__getattribute__(self, '_attr')
            real = getattr(importlib.import_module(module, __name__), attr)
            object.__setattr__(self, '_real', real)
        return real

    def __getattr__(self, name):
        return getattr(self._load(), name)

    def __setattr__(self, name, value):
        setattr(self._load(), name, value)

    def __call__(self, *args, **kwargs):
        return self._load()(*args, **kwargs)

    def __repr__(self):
        real = object.__getattribute__(self, '_real')
        return repr(real) if real is not None else f'<deferred app.data.{self._attr}>'


ScriptDatabase = _LazyAttr('.database', 'ScriptDatabase')
ConfigDatabase = _LazyAttr('.database', 'ConfigDatabase')
TaskDatabase = _LazyAttr('.database', 'TaskDatabase')
ScriptEntity = _LazyAttr('.schemas', 'ScriptEntity')


def __getattr__(name):
    raise AttributeError(f"module 'app.data' has no attribute {name!r}")


def __dir__():
    return sorted(set(globals()) | set(_LAZY))
