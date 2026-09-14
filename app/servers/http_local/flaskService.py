"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import tempfile
import threading
import uuid
from pathlib import Path

import flask
from PySide2.QtCore import QObject, Signal
from app.data import ScriptDatabase
from app.utils import BM_LOG, BmTools, ParameterManager
from app.servers.scripts import ScriptRunner
from app.utils.parameter_generate import build_launch_env


# 链接链防死循环：盒子侧同步调用深度计数（同步联动天然嵌套，深度=真实链路层数）
_LINK_LOCK = threading.Lock()
_LINK_DEPTH = 0
MAX_LINK_DEPTH = 8


def _enter_link() -> bool:
    """尝试进入一层同步链接；超限返回 False 视为死循环拦截"""
    global _LINK_DEPTH
    with _LINK_LOCK:
        if _LINK_DEPTH >= MAX_LINK_DEPTH:
            return False
        _LINK_DEPTH += 1
        return True


def _exit_link():
    global _LINK_DEPTH
    with _LINK_LOCK:
        if _LINK_DEPTH > 0:
            _LINK_DEPTH -= 1



class FlaskSignals(QObject):
    server_started = Signal(str)
    server_stopped = Signal()
    request_received = Signal(str)
    error_occurred = Signal(str)
    show_notify = Signal(tuple)
    execute_script_request = Signal(str, str)


class FlaskServer:
    def __init__(self, host='127.0.0.1', port=9527):
        self.host = host
        self.port = port
        self.app = flask.Flask(__name__)
        self.setup_routes()
        self.signals = FlaskSignals()



    def setup_routes(self):
        self._setup_open_routes()
        self._setup_closed_routes()

    def _setup_open_routes(self):
        """注册开源路由"""
        @self.app.route('/api/execute', methods=['POST'])
        def execute_script():
            BM_LOG.info(f"请求已接收: {flask.request.method} {flask.request.url}")
            try:
                if flask.request.is_json:
                    body = flask.request.get_json() or {}
                else:
                    body = {k: v for k, v in flask.request.form.items()}

                script_id = body.get('script_id')
                if not script_id:
                    return flask.jsonify({"status": "error", "message": "缺少script_id参数"}), 400

                temp_file_path = body.get('temp_file')
                sync = bool(body.get('sync', False))
                data = body.get('data')
                params = body.get('params')

                # 目标脚本
                script_data = ScriptDatabase().get_script_by_id(script_id)
                if not script_data:
                    return flask.jsonify({"status": "error", "message": f"脚本不存在: {script_id}"}), 404

                # 主数据：旧 temp_file 触发流 / 新结构化 data
                if temp_file_path:
                    if not Path(temp_file_path).exists():
                        return flask.jsonify({"status": "error", "message": f"文件不存在: {temp_file_path}"}), 404
                    params_list = BmTools.get_temp_context(temp_file_path)
                else:
                    params_list = self._parse_input_list(script_data, data)

                # 参数表单：声明了 params_form 的脚本触发时弹窗，携带数据预填。
                # 同步/自动调用不弹窗（按给定参数执行）；非同步（右键 DLL）异步弹窗，HTTP 立即返回避免调用方超时。
                if getattr(script_data, 'params_form_enabled', False):
                    if sync:
                        pass
                    else:
                        threading.Thread(
                            target=self._prompt_then_emit,
                            args=(script_id, script_data, params_list),
                            daemon=True,
                        ).start()
                        return flask.jsonify(
                            {"status": "awaiting_input", "message": "参数确认中，完成确认后自动执行"}), 200

                # params：toml 默认值 + 调用方覆盖，再校验 required/choices
                params_defs = script_data.params_schema or []
                merged_params = ParameterManager()._merge_params(params_defs, params)
                check_err = self._validate_params(params_defs, merged_params)
                if check_err:
                    return flask.jsonify({"status": "error", "message": check_err}), 400

                # 为被调脚本重建 environment（任务唯一 output_json，供脚本写回结果；仅同步才需要）
                output_json = str(Path(tempfile.gettempdir()) / f"bms_{uuid.uuid4().hex}.out.json") if sync else None
                env_extra = build_launch_env(
                    script_id,
                    api_base=f"http://{self.host}:{self.port}",
                    invoke_mode="node" if sync else "manual",
                )
                input_data = script_data.inputs_schema[0] if script_data.inputs_schema else {'name': 'source_path'}
                json_path = ParameterManager().construct_parameters(
                    input_data, params_list,
                    output_json=output_json,
                    params_defs=params_defs,
                    params_overrides=params,
                    env_extra=env_extra,
                )
                if not json_path:
                    return flask.jsonify({"status": "error", "message": "参数文件构造失败"}), 500

                # 同步调用：跑完直接返回结果；否则 fire-and-forget
                if sync:
                    result = ScriptRunner().run_script_sync(script_id, str(json_path))
                    return self._sync_response(result), 200

                self.signals.execute_script_request.emit(script_id, str(json_path))
                return flask.jsonify({"status": "success", "message": "脚本执行请求已接收"}), 200

            except Exception as e:
                BM_LOG.error(f"接口执行脚本错误: {e}")
                return flask.jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route('/api/link', methods=['POST'])
        def link_script():
            """脚本串联：A 调 B（B 必须声明为节点）。无 token，防循环走盒子侧同步深度计数。"""
            BM_LOG.info(f"请求已接收: {flask.request.method} {flask.request.url}")
            try:
                if flask.request.is_json:
                    body = flask.request.get_json() or {}
                else:
                    body = {k: v for k, v in flask.request.form.items()}

                script_id = body.get('script_id')
                if not script_id:
                    return flask.jsonify({"status": "error", "message": "缺少script_id参数"}), 400

                # 1. 目标脚本
                script_data = ScriptDatabase().get_script_by_id(script_id)
                if not script_data:
                    return flask.jsonify({"status": "error", "message": f"脚本不存在: {script_id}"}), 404

                # 2. 节点门禁：联运调用一律只放行声明为节点的脚本
                if not script_data.is_node:
                    return flask.jsonify(
                        {"status": "error",
                         "message": f"脚本 '{script_data.name}' 未声明可作为节点，不允许联动调用"}), 403

                # 3. 链深门禁：同步嵌套深度超限视为死循环
                if not _enter_link():
                    return flask.jsonify(
                        {"status": "error",
                         "message": "联动链路过深（超过 8 层），已拦截"}), 400
                try:
                    data = body.get('data')
                    params = body.get('params')

                    params_list = self._parse_input_list(script_data, data)

                    # params：toml 默认值 + 调用方覆盖，再校验 required/choices
                    params_defs = script_data.params_schema or []
                    merged_params = ParameterManager()._merge_params(params_defs, params)
                    check_err = self._validate_params(params_defs, merged_params)
                    if check_err:
                        return flask.jsonify({"status": "error", "message": check_err}), 400

                    # 为被调脚本重建 environment（任务唯一 output_json，供脚本写回结果）
                    output_json = str(Path(tempfile.gettempdir()) / f"bms_{uuid.uuid4().hex}.out.json")
                    env_extra = build_launch_env(
                        script_id,
                        api_base=f"http://{self.host}:{self.port}",
                        invoke_mode="node",
                    )
                    input_data = script_data.inputs_schema[0] if script_data.inputs_schema else {'name': 'source_path'}
                    json_path = ParameterManager().construct_parameters(
                        input_data, params_list,
                        output_json=output_json,
                        params_defs=params_defs,
                        params_overrides=params,
                        env_extra=env_extra,
                    )
                    if not json_path:
                        return flask.jsonify({"status": "error", "message": "参数文件构造失败"}), 500

                    result = ScriptRunner().run_script_sync(script_id, str(json_path))
                    return self._sync_response(result), 200
                finally:
                    _exit_link()

            except Exception as e:
                BM_LOG.error(f"接口串联脚本错误: {e}")
                return flask.jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route('/api/health', methods=['GET'])
        def health_check():
            try:
                return flask.jsonify({"status": "healthy", "service": "BmScriptsBox"}), 200
            except Exception as e:
                return flask.jsonify({"status": "error", "message": str(e)}), 500

        @self.app.route('/api/notify', methods=['Post'])
        def notify():
            if not flask.request.is_json:
                return flask.jsonify({"error": "Content-Type must be application/json"}), 400
            try:
                data = flask.request.get_json(force=True)
                if not data:
                    raise ValueError("Empty JSON body")
                notify_type = data.get('notify_type')
                message = data.get('message')
                duration = data.get('duration', 5000)
                show_close = data.get('show_close', False)
                if not notify_type:
                    raise ValueError("缺少必填字段: notify_type")
                self.signals.show_notify.emit((notify_type, message, duration, show_close))
                return flask.jsonify({"success": True}), 200
            except Exception as e:
                return flask.jsonify({"success": False}), 500

        @self.app.route('/api/model/path', methods=['GET'])
        def get_model_path():
            """查询已下载 AI 模型的本地路径，供脚本加载模型时使用"""
            repo_id = flask.request.args.get('repo_id')
            if not repo_id:
                return flask.jsonify({"code": 400, "message": "缺少 repo_id 参数"}), 400

            from app.servers.models import ModelManager
            path = ModelManager().get_model_path(repo_id)
            if not path:
                return flask.jsonify({"success": False,
                                      "code": 404,
                                      "message": f"模型 {repo_id} 未下载",
                                      "data":{}}), 404

            return flask.jsonify({
                "success": True,
                "code": 200,
                "message": f"模型{repo_id}路径获取成功",
                "data": {"repo_id": repo_id, "path": path}
            })

    def _setup_closed_routes(self):
        """可选注册闭源业务路由"""
        try:
            from app.cloud.http import register_routes
            register_routes(self.app)
            BM_LOG.info("云业务接口已注册")
        except ImportError:
            pass

    @staticmethod
    def _validate_params(params_defs: list, merged: dict) -> str:
        """校验必填与 select 取值；通过返回 None，否则返回错误消息"""
        for pd in params_defs or []:
            name = pd.get('name')
            if pd.get('required') and (name not in merged or merged.get(name) in (None, '')):
                return f"缺少必填参数: {name}"
            if pd.get('type') == 'str' and pd.get('choices'):
                val = merged.get(name)
                if val not in (None, '') and val not in pd['choices']:
                    return f"参数 {name} 取值 '{val}' 不在可选范围 {pd['choices']}"
        return None

    @staticmethod
    def _parse_input_list(script_data, data) -> list:
        """把 data 三态（dict 按 input 键名 / list 直传 / 其它空）折成 params_list"""
        input_name = script_data.inputs_schema[0]['name'] if script_data.inputs_schema else 'source_path'
        if isinstance(data, dict):
            return data.get(input_name, [])
        if isinstance(data, list):
            return data
        return []

    @staticmethod
    def _sync_response(result: dict) -> dict:
        """统一 sync 返回体：进程结果 + 脚本写回信封"""
        result_body = result['result']
        return {
            "status": "success" if result['success'] else "error",
            "message": (result_body or {}).get('msg', '') if isinstance(result_body, dict) else '',
            "exit_code": result['exit_code'],
            "success": result['success'],
            "timed_out": result['timed_out'],
            "stdout": result['stdout'],
            "stderr": result['stderr'],
            "result": result_body,
        }

    def _prompt_then_emit(self, script_id, script_data, params_list):
        """异步参数表单：弹窗请用户确认（阻塞在自身线程），确认后按所选参数启动；用于右键 DLL 等外部触发"""
        try:
            from app.view.script_ui.params_prompt import show_params_prompt
            res = show_params_prompt(script_data, params_list)
            if res is None:  # 用户取消，不启动
                return
            params_list, user_params = res
            params_defs = script_data.params_schema or []
            check_err = self._validate_params(
                params_defs, ParameterManager()._merge_params(params_defs, user_params))
            if check_err:
                return
            env_extra = build_launch_env(
                script_id,
                api_base=f"http://{self.host}:{self.port}",
                invoke_mode="manual",
            )
            input_data = script_data.inputs_schema[0] if script_data.inputs_schema else {'name': 'source_path'}
            json_path = ParameterManager().construct_parameters(
                input_data, params_list,
                params_defs=params_defs,
                params_overrides=user_params,
                env_extra=env_extra,
            )
            if json_path:
                self.signals.execute_script_request.emit(script_id, str(json_path))
        except Exception as e:
            BM_LOG.error(f"参数表单异步启动失败 {script_id}: {e}")

    def run(self):
        try:
            BM_LOG.info(f"🚀 Flask服务器启动在: http://{self.host}:{self.port}")
            self.app.run(
                host=self.host,
                port=self.port,
                debug=False,
                use_reloader=False,
                threaded=True  # 允许同步调用阻塞单个请求而不卡死其它路由
            )
        except Exception as e:
            BM_LOG.error(f"Flask服务器错误: {e}")
            raise RuntimeError('本地http服务启动失败')

