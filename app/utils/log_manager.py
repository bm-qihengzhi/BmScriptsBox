"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import logging
import logging.handlers
import queue
import sys
import webbrowser
from pathlib import Path


class AsyncLoggerManager:
    def __init__(self, log_level=logging.INFO):
        if getattr(sys, 'frozen', False):
            _root = Path(sys.executable).parent
        else:
            _root = Path(__file__).parents[2]
        self.log_file_path = _root / "BmLogs" / 'BmLogs.log'
        self.log_level = log_level
        self.logger = None
        self.queue_listener = None

        # 确保日志目录存在
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
        # 确保日志文件存在
        self.log_file_path.touch(exist_ok=True)
        self._setup_async_logger()

    def _setup_async_logger(self):
        """配置异步日志系统"""
        # 创建logger实例
        self.logger = logging.getLogger("BmScriptsBox")
        self.logger.setLevel(self.log_level)

        # 清除已有的handlers避免重复
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        # 创建日志队列
        log_queue = queue.Queue(maxsize=10000)

        # 创建文件处理器（带轮转）
        file_handler = logging.handlers.RotatingFileHandler(
            self.log_file_path,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=5,
            encoding='utf-8'
        )
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(formatter)

        # 创建队列处理器
        queue_handler = logging.handlers.QueueHandler(log_queue)
        self.logger.addHandler(queue_handler)

        # 创建队列监听器
        self.queue_listener = logging.handlers.QueueListener(
            log_queue,
            file_handler,
            respect_handler_level=True
        )

        # 启动监听器
        self.queue_listener.start()

        # 确保程序退出时正确关闭
        import atexit
        atexit.register(self.shutdown)

    def get_logger(self):
        """获取logger实例"""
        return self.logger

    def shutdown(self):
        """关闭异步日志系统"""
        if self.queue_listener:
            self.queue_listener.stop()

    def open_log_file(self):
        """
        使用默认程序打开日志文件
        """
        if self.log_file_path.exists():
            webbrowser.open(f"file://{self.log_file_path.absolute()}")
        else:
            # 如果日志文件不存在，创建一个空文件
            self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
            self.log_file_path.touch()
            webbrowser.open(f"file://{self.log_file_path.absolute()}")

    def clear_log_content(self):
        """
        清空日志文件内容，但保留文件
        """
        if self.log_file_path.exists():
            # 停止当前的队列监听器以避免写入冲突
            if self.queue_listener:
                self.queue_listener.stop()

            # 清空文件内容
            with open(self.log_file_path, 'w', encoding='utf-8') as f:
                f.write('')

            # 重新启动日志系统
            self._setup_async_logger()


# 创建全局异步日志管理器实例
async_logger_manager = AsyncLoggerManager()

# 获取logger实例供其他模块使用
BM_LOG = async_logger_manager.get_logger()




