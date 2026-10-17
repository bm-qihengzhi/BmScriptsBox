"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import threading
from PySide2.QtCore import QThread

from app.servers.http_local import FlaskServer, FlaskSignals
from app.utils import BM_LOG


class FlaskWork(QThread):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.flask_service = FlaskServer()
        self.signals = FlaskSignals()
        self._is_running = True

        # 转发Flask服务的信号到主线程（单一 execute_script_request 通道，携带 LaunchContext）
        self.flask_service.signals.show_notify.connect(self.signals.show_notify)
        self.flask_service.signals.execute_script_request.connect(self.execute_script_handler)
        self.flask_service.signals.execute_script_request.connect(
            lambda ctx: self.signals.execute_script_request.emit(ctx))

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

    def execute_script_handler(self, ctx):
        """处理脚本执行请求 - 避免阻塞Flask线程（占用已在路由/弹窗线程完成）"""
        if ctx is None:
            return
        try:
            # 发射开始通知
            self.signals.show_notify.emit(('info', '正在执行脚本', 2000, False))
            # 在单独的线程中执行耗时脚本
            thread = threading.Thread(
                target=self._execute_script_in_thread,
                args=(ctx,)
            )
            thread.daemon = True  # 设置为守护线程
            thread.start()

        except Exception as e:
            BM_LOG.error(f"{e}")

    def _execute_script_in_thread(self, ctx):
        """在单独的线程中执行脚本，结束时释放占用并清理参数文件"""
        from app.servers.scripts import ScriptLaunchService
        try:
            ScriptLaunchService.run(ctx)
        except Exception as e:
            BM_LOG.error(f"启动脚本失败: {e}")
            self.signals.show_notify.emit(('error', '脚本执行失败，详细请看日志', 2000, False))
        finally:
            ScriptLaunchService.cleanup(ctx)


