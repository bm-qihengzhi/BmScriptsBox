"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import json
from pprint import pprint
from typing import Optional

import toml
import uuid
import zipfile
from pathlib import Path

from app.data import ScriptDatabase
from app.data.toml_schemas import ScriptTomlConfig, ScriptLoadResult
from pydantic import ValidationError


class TomlManager:
    """
    toml数据读取验证类
    """

    def read_package_json_by_dir(self, script_dir: str):
        """读取目录中的package.json"""
        script_path = Path(script_dir)
        package_file = script_path / 'package.json'
        if not package_file.exists():
            raise FileNotFoundError("该JS脚本根目录下未包含必要的package.json文件")
        try:
            with open(package_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except Exception as e:
            raise Exception(f"读取package.json文件错误: {e}")

    def read_package_json_by_zip(self, zip_path):
        """读取zip根目录下的package.json,适用于javascript脚本"""
        zip_path = Path(zip_path)
        if not zip_path.exists():
            raise FileNotFoundError(f"Zip文件不存在: {zip_path}")
        if zip_path.suffix != '.zip':
            raise ValueError(f"文件不是ZIP格式: {zip_path}")

        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                # 严格匹配根目录下的 package.json (精确匹配)
                package_files = [
                    f for f in zf.namelist()
                    if f == "package.json"  # 严格等于根目录文件名
                ]

                if not package_files:
                    # 尝试带BOM的UTF-8编码常见情况
                    package_files = [
                        f for f in zf.namelist()
                        if f.lower() == "package.json" and '/' not in f
                    ]
                    if not package_files:
                        raise FileNotFoundError(
                            "ZIP中未找到根目录下的package.json文件。"
                            "注意：仅支持根目录文件，不支持子目录"
                        )

                if len(package_files) > 1:
                    # 安全机制：理论上不可能，但防御性编程
                    raise ValueError(f"ZIP中存在多个根目录package.json: {package_files}")

                package_file = package_files[0]
                content = zf.read(package_file).decode('utf-8-sig')  # 处理BOM

                try:
                    return json.loads(content)  # 正确解析为Python字典
                except json.JSONDecodeError as e:
                    raise ValueError(
                        f"无效的JSON格式 in {package_file}: {str(e)}\n"
                        f"文件内容预览: {content[:100]}..."
                    )

        except zipfile.BadZipFile as e:
            raise ValueError(f"无效的ZIP文件: {str(e)}")
        except Exception as e:
            raise Exception(f"读取ZIP时出错: {str(e)}") from e



    def read_pyproject_toml_from_dir(self, script_dir: str) ->dict:
        """读取目录中的pyproject.toml"""
        try:
            pyproject_file = Path(script_dir) / 'pyproject.toml'
            if not pyproject_file.exists():
                raise FileNotFoundError("目录中不存在pyproject.toml文件")
            with open(pyproject_file, 'r', encoding='utf-8') as f:
                data = toml.load(f)
            return data
        except Exception as e:
            raise RuntimeError(f'读取 pyproject.toml 文件错误: {e}')

    def read_toml_id_from_zip(self, zip_path):
        """从压缩包的bm-scripts-box-rc.toml中读取脚本ID"""
        with zipfile.ZipFile(zip_path, 'r') as zf:
            toml_file = next((f for f in zf.namelist() if f.endswith('bm-scripts-box-rc.toml')), None)
            if toml_file:
                toml_content = zf.read(toml_file).decode('utf-8')
                data = toml.loads(toml_content)
                return data['bmscriptsbox']['info']['id']
            else:
                raise FileNotFoundError("脚本压缩包内无配置文件bm-scripts-box-rc.toml")


    def read_toml_from_dir(self, script_dir: str) -> ScriptLoadResult:
        """读取文件夹下toml配置文件、用于云端按照"""
        try:
            script_path = Path(script_dir)
            # 寻找配置文件
            toml_files = list(script_path.rglob('bm-scripts-box-rc.toml'))
            if not toml_files:
                return ScriptLoadResult(success=False, error_messages=["目录下找不到 bm-scripts-box-rc.toml 配置文件"])

            toml_file = toml_files[0]
            with open(toml_file, 'r', encoding='utf-8') as f:
                data = toml.load(f)

        except Exception as e:
            return ScriptLoadResult(success=False, error_messages=[f"文件读取失败: {str(e)}"])

        return self.serialize_toml_data(data, script_dir)

    def serialize_toml_data(self, toml_data: dict, script_dir: str) -> ScriptLoadResult:
        """将原始字典转换为经过校验的模型对象"""
        root_data = toml_data.get('bmscriptsbox')
        if not root_data:
            return ScriptLoadResult(success=False, error_messages=["配置文件格式错误：缺少 [bmscriptsbox] 根节点"])

        # --- 定义语义化映射表 (汉化) ---
        LOC_MAP = {
            "info": "基本信息",
            "id": "唯一标识(ID)",
            "name": "脚本名称",
            "version": "版本号",
            "environment": "运行环境",
            "language": "编程语言",
            "entry": "入口文件",
            "triggers": "触发器设置",
            "context_menu": "右键菜单",
            "shortcut": "快捷键",
            "inputs": "输入参数",
            "outputs": "输出参数"
        }

        try:
            # 执行校验
            script_obj = ScriptTomlConfig.model_validate(
                root_data,
                context={"script_dir": script_dir}
            )
            return ScriptLoadResult(success=True, config=script_obj)

        except ValidationError as e:
            semantic_errors = []

            for error in e.errors():
                loc_path = " -> ".join([LOC_MAP.get(str(l), str(l)) for l in error['loc']])
                #  语义化错误原因
                err_type = error['type']
                err_msg = error['msg']  # 默认保留 Pydantic 的原始消息作为保底

                if err_type == "uuid_parsing":
                    err_msg = "不是有效的 UUID 格式 (标准格式如: xxxxxxxx-xxxx-...)"
                elif err_type == "string_too_short":
                    err_msg = "不能为空 (至少需要 1 个字符)"
                elif err_type == "string_pattern_mismatch":
                    # 针对版本号这种正则匹配
                    if "version" in str(error['loc']):
                        err_msg = "格式不正确 (应为数字组成的语义化版本，如: 1.0.0)"
                    else:
                        err_msg = "格式校验不通过"
                elif err_type == "missing":
                    err_msg = "此项为必填项，但配置文件中缺失"

                # C. 获取输入值
                input_val = error.get('input', '无')

                # 组装成最终的语义化消息
                detail = f"❌ 【{loc_path}】: {err_msg} (当前值: '{input_val}')"
                semantic_errors.append(detail)

            return ScriptLoadResult(success=False, error_messages=semantic_errors)


if __name__ == "__main__":
    manager = TomlManager()
    # 拿到结果对象，而不是让它崩溃
    result = manager.read_toml_from_dir(r"D:\ScriptsHub\python\files_classification")
    # result = manager.read_pyproject_toml_from_dir(r"D:\ScriptsHub\python\微信双开")
    # print(result)
    # ScriptDatabase().from_config_model(result.config)
    # result = manager.read_toml_from_zip(r"D:\ScriptsHub\bat\系统记事本\系统记事本.zip")

    if result.success:
        print(f"✅ 成功！脚本名称: {result.config.runtime.language_version}")
    else:
        print("❌ 导入失败，错误清单如下：")
        print(result.error_messages)
        for msg in result.error_messages:
            print(f"  - {msg}")
