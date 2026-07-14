"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import threading
from PySide2.QtCore import QThread

from app.servers.http_local import FlaskServer, FlaskSignals
from app.utils import BM_LOG
from app.servers.scripts import ScriptRunner


class FlaskWork(QThread):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.flask_service = FlaskServer()
        self.signals = FlaskSignals()
        self._is_running = True
        
        # 转发Flask服务的信号到主线程
        self.flask_service.signals.show_notify.connect(self.signals.show_notify)
        self.flask_service.signals.execute_script_request.connect(self.execute_script_handler)
        self.flask_service.signals.execute_script_request.connect(
            lambda sid, jp: self.signals.execute_script_request.emit(sid, jp))

    def run(self):
        """在线程中运行Flask服务器"""
        try:
            self.signals.server_started.emit(
                f"http://{self.flask_service.host}:{self.flask_service.port}"
            )
            self.flask_service.run()
        except Exception as e:
            error_msg = f"Flask服务器错误: {e}"
            self.signals.error_occurred.emit(error_msg)
        finally:
            self.signals.server_stopped.emit()

    def stop(self):
        """优雅停止服务器"""
        self._is_running = False
        self.quit()
        if not self.wait(1000):  # 等待1秒
            self.terminate()  # 强制终止
            self.wait()

    def execute_script_handler(self, script_id, json_path):
        """处理脚本执行请求 - 避免阻塞Flask线程"""
        from app.data import ProjectGlobal
        with ProjectGlobal.RUNNING_SCRIPTS_LOCK:
            if script_id in ProjectGlobal.RUNNING_SCRIPTS:
                self.signals.show_notify.emit(('warning', f'脚本正在运行中，请等待完成', 3000, False))
                return
        try:
            # 发射开始通知
            self.signals.show_notify.emit(('info', '正在执行脚本', 2000, False))
            # 在单独的线程或进程池中执行耗时脚本
            thread = threading.Thread(
                target=self._execute_script_in_thread,
                args=(script_id, json_path)
            )
            thread.daemon = True  # 设置为守护线程
            thread.start()

        except Exception as e:
            BM_LOG.error(f"{e}")

    def _execute_script_in_thread(self, script_id, json_path):
        """在单独的线程中执行脚本"""
        try:
            ScriptRunner().run_script(script_id, json_path)
        except Exception as e:
            BM_LOG.error(f"启动脚本失败: {e}")
            self.signals.show_notify.emit(('error', '脚本执行失败，详细请看日志', 2000, False))


