"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import json
import tempfile
import uuid
from pathlib import Path

from typing import List, Optional

from app.utils import BM_LOG


class ParameterManager:

    def construct_parameters(self,
                             script_input_data: Optional[dict] = None,
                             data: Optional[List[str]] = None,
                             model: str = 'standalone',
                             json_name: Optional[str] = None,
                             space: Optional[str] = None,
                             output_json: Optional[str] = None) -> Optional[Path]:
        """
        统一构建json格式参数文件
        """
        try:
            if not isinstance(script_input_data, dict):
                script_input_data = {}
            if not isinstance(data, list):
                data = []
            parameter_name = script_input_data.get('name', 'source_path')

            parameters = {
                'environment': {
                    'model': model,
                    'workspace': space,
                    "output_json": output_json,
                    "encoding": "utf-8",

                },
                'data': {
                    parameter_name: data
                }
            }
            if not space:
                space = tempfile.gettempdir()
            if not json_name:
                json_name = f"{uuid.uuid4()}.json"
            json_path = Path(space) / json_name
            with open(json_path, 'w', encoding='utf-8') as f:
                json_str = json.dumps(parameters, ensure_ascii=False, indent=4)
                f.write(json_str)
            return json_path
        except Exception as e:
            BM_LOG.error(f"<参数构造报错>{e}")
            return None



