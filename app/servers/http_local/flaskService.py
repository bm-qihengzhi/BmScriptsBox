"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import os
import tempfile
import threading
import uuid
from pathlib import Path

import flask
from PySide2.QtCore import QObject, Signal
from app.data import ScriptDatabase
from app.utils import BM_LOG, BmTools, ParameterManager
from app.servers.scripts import ScriptLaunchService, ScriptBusyError, ScriptNotFoundError
from app.utils.parameter_generate import build_launch_env


def _as_bool(value) -> bool:
    """严格布尔解析：仅 True/'true'/'1'/1 为真，避免 'false' 被 str 真值误判"""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in ('1', 'true', 'yes', 'on')
    return False


# 链接链防死循环：盒子侧同步调用深度计数（同步联动天然嵌套，深度=真实链路层数）
_LINK_LOCK = threading.Lock()
_LINK_DEPTH = 0
MAX_LINK_DEPTH = 8

# 直接自环兜底：当前正在嵌套链路中的 script_id 集合（覆盖并发误判下漏网的自环）
_LINK_ACTIVE_LOCK = threading.Lock()
_LINK_ACTIVE_SCRIPTS = set()


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
    execute_script_request = Signal(object)


class FlaskServer:
    def __init__(self, host='127.0.0.1', port=9527):
        self.host = host
        self.port = port
        self.app = flask.Flask(__name__)
        self.app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024  # 限制请求体大小
        self.setup_routes()
        self.signals = FlaskSignals()



    def setup_routes(self):
        self._setup_local_guard()
        self._setup_open_routes()
        self._setup_closed_routes()

    def _setup_local_guard(self):
        """仅接受本机回环请求（服务绑定 127.0.0.1，此处为纵深防御）"""
        @self.app.before_request
        def _guard_local_only():
            addr = flask.request.remote_addr or ''
            if addr not in ('127.0.0.1', '::1', 'localhost'):
                BM_LOG.warning(f"拒绝非本机请求: {addr} {flask.request.path}")
                return flask.jsonify({"status": "error", "message": "仅允许本机访问"}), 403


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
                if not script_id or not isinstance(script_id, str) or len(script_id) > 64:
                    return flask.jsonify({"status": "error", "message": "缺少或非法 script_id 参数"}), 400

                temp_file_path = body.get('temp_file')
                sync = _as_bool(body.get('sync', False))
                data = body.get('data')
                params = body.get('params')

                # 目标脚本
                script_data = ScriptDatabase().get_script_by_id(script_id)
                if not script_data:
                    return flask.jsonify({"status": "error", "message": f"脚本不存在: {script_id}"}), 404

                # 主数据：旧 temp_file 触发流 / 新结构化 data
                if temp_file_path:
                    if not self._is_allowed_temp_file(temp_file_path):
                        return flask.jsonify({"status": "error", "message": "非法 temp_file 路径"}), 400
                    if not Path(temp_file_path).exists():
                        return flask.jsonify({"status": "error", "message": f"文件不存在: {temp_file_path}"}), 404
                    params_list = BmTools.get_temp_context(temp_file_path)
                else:
                    params_list = self._parse_input_list(script_data, data)

                # 参数表单：声明了 params_form 的脚本触发时弹窗，携带数据预填。
                # 同步/自动调用不弹窗（按给定参数执行）；非同步（右键 DLL）异步弹窗，HTTP 立即返回避免调用方超时。
                if getattr(script_data, 'params_form_enabled', False) and not sync:
                    threading.Thread(
                        target=self._prompt_then_emit,
                        args=(script_id, params_list),
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

                api_base = f"http://{self.host}:{self.port}"

                if sync:
                    # 同步调用：不占用运行键（节点可重入），跑完直接返回结果
                    output_json = str(Path(tempfile.gettempdir()) / f"bms_{uuid.uuid4().hex}.out.json")
                    env_extra = build_launch_env(script_id, api_base=api_base, invoke_mode="node")
                    ctx = ScriptLaunchService.prepare(
                        script_id, data=params_list, params_overrides=params,
                        params_defs=params_defs, invoke_mode="node",
                        allow_params_form=False, reserve_first=False,
                        output_json=output_json, env_extra=env_extra,
                    )
                    try:
                        result = ScriptLaunchService.run(ctx, sync=True)
                    finally:
                        ScriptLaunchService.cleanup(ctx)
                    return self._sync_response(result), 200

                # 异步：原子占用 + 构造参数，随后交给工作线程执行
                env_extra = build_launch_env(script_id, api_base=api_base, invoke_mode="manual")
                try:
                    ctx = ScriptLaunchService.prepare(
                        script_id, data=params_list, params_overrides=params,
                        params_defs=params_defs, invoke_mode="manual",
                        allow_params_form=False, reserve_first=True, env_extra=env_extra,
                    )
                except ScriptBusyError:
                    return flask.jsonify(
                        {"status": "error", "message": "脚本正在运行中，请等待完成"}), 200
                except ScriptNotFoundError as e:
                    return flask.jsonify({"status": "error", "message": str(e)}), 404

                self.signals.execute_script_request.emit(ctx)
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

                # 3. 自环兜底：同一 script_id 已在嵌套链路中 → 判定为直接自环
                with _LINK_ACTIVE_LOCK:
                    if script_id in _LINK_ACTIVE_SCRIPTS:
                        return flask.jsonify(
                            {"status": "error",
                             "message": f"检测到脚本自环调用: {script_id}"}), 400

                # 4. 链深门禁：同步嵌套深度超限视为死循环
                if not _enter_link():
                    return flask.jsonify(
                        {"status": "error",
                         "message": "联动链路过深（超过 8 层），已拦截"}), 400
                with _LINK_ACTIVE_LOCK:
                    _LINK_ACTIVE_SCRIPTS.add(script_id)
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
                    ctx = ScriptLaunchService.prepare(
                        script_id, data=params_list, params_overrides=params,
                        params_defs=params_defs, invoke_mode="node",
                        allow_params_form=False, reserve_first=False,
                        output_json=output_json, env_extra=env_extra,
                    )
                    try:
                        result = ScriptLaunchService.run(ctx, sync=True)
                    finally:
                        ScriptLaunchService.cleanup(ctx)
                    return self._sync_response(result), 200
                finally:
                    with _LINK_ACTIVE_LOCK:
                        _LINK_ACTIVE_SCRIPTS.discard(script_id)
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
    def _is_allowed_temp_file(file_path: str) -> bool:
        """限定 temp_file 位于系统临时目录或盒子根目录内，避免任意文件读取"""
        try:
            target = os.path.realpath(str(file_path))
            temp_dir = os.path.realpath(tempfile.gettempdir())
            root_dir = os.path.realpath(str(BmTools.get_root_path()))
        except Exception:
            return False
        for base in (temp_dir, root_dir):
            try:
                if os.path.commonpath([target, base]) == base:
                    return True
            except ValueError:  # 跨盘符
                continue
        return False

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

    def _prompt_then_emit(self, script_id, params_list):
        """异步参数表单：弹窗请用户确认（阻塞在自身线程），确认后按所选参数启动；用于右键 DLL 等外部触发"""
        try:
            from app.view.script_ui.params_prompt import show_params_prompt
            script_data = ScriptDatabase().get_script_by_id(script_id)
            if not script_data:
                return
            # 先原子占用，避免弹窗期间被其它入口重复触发
            if not ScriptLaunchService.reserve(script_id):
                return
            try:
                res = show_params_prompt(script_data, params_list)
                if res is None:  # 用户取消，不启动
                    ScriptLaunchService.release(script_id)
                    return
                data_list, user_params = res
                params_defs = script_data.params_schema or []
                check_err = self._validate_params(
                    params_defs, ParameterManager()._merge_params(params_defs, user_params))
                if check_err:
                    ScriptLaunchService.release(script_id)
                    return
                env_extra = build_launch_env(
                    script_id,
                    api_base=f"http://{self.host}:{self.port}",
                    invoke_mode="manual",
                )
                try:
                    ctx = ScriptLaunchService.prepare(
                        script_id, data=data_list, params_overrides=user_params,
                        params_defs=params_defs, invoke_mode="manual",
                        allow_params_form=False, reserve_first=False,
                        env_extra=env_extra,
                    )
                except Exception:
                    ScriptLaunchService.release(script_id)
                    raise
                if ctx is None:
                    ScriptLaunchService.release(script_id)
                    return
                self.signals.execute_script_request.emit(ctx)
            except Exception:
                ScriptLaunchService.release(script_id)
                raise
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

