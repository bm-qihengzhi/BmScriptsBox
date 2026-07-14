"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
from pathlib import Path

import flask
from PySide2.QtCore import QObject, Signal
from app.data import ScriptDatabase
from app.utils import BM_LOG, BmTools, ParameterManager



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
                    data = flask.request.get_json()
                    script_id = data.get('script_id')
                    temp_file_path = data.get('temp_file')
                else:
                    script_id = flask.request.form.get('script_id')
                    temp_file_path = flask.request.form.get('temp_file')

                if not script_id:
                    return flask.jsonify({"status": "error", "message": "缺少script_id参数"}), 400
                if not temp_file_path:
                    return flask.jsonify({"status": "error", "message": "缺少temp_file参数"}), 400
                if not Path(temp_file_path).exists():
                    return flask.jsonify({"status": "error", "message": f"文件不存在: {temp_file_path}"}), 404

                script_data = ScriptDatabase().get_script_by_id(script_id)
                if not script_data:
                    raise ValueError(f"脚本不存在: {script_id}")
                input_data = script_data.inputs_schema[-1] if script_data.inputs_schema else {}
                params = BmTools.get_temp_context(temp_file_path)
                json_path = ParameterManager().construct_parameters(input_data, params)
                self.signals.execute_script_request.emit(script_id, str(json_path))

                return flask.jsonify({"status": "success", "message": "脚本执行请求已接收"}), 200

            except Exception as e:
                BM_LOG.error(f"接口执行脚本错误: {e}")
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

    def _setup_closed_routes(self):
        """可选注册闭源业务路由"""
        try:
            from app.cloud.http import register_routes
            register_routes(self.app)
            BM_LOG.info("云业务接口已注册")
        except ImportError:
            pass

    def run(self):
        try:
            BM_LOG.info(f"🚀 Flask服务器启动在: http://{self.host}:{self.port}")
            self.app.run(
                host=self.host,
                port=self.port,
                debug=False,
                use_reloader=False
            )
        except Exception as e:
            BM_LOG.error(f"Flask服务器错误: {e}")
            raise RuntimeError('本地http服务启动失败')

