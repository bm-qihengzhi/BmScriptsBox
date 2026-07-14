"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from PySide2.QtCore import QObject, Signal, QCoreApplication, QThread, Slot

import requests
from requests.adapters import HTTPAdapter
from app.data import ProjectGlobal
from app.utils import BM_LOG



class XDownLoad(QObject):
    """下载器"""
    download_progress = Signal(dict)
    """
    格式约定：{‘status’:True,'msg':"xxx完成"}
    """
    download_finished = Signal(str)
    download_error = Signal(str)

    def __init__(self):
        super().__init__()
        # 创建全局会话，复用连接池
        self.session = requests.Session()
        self.session.trust_env = False
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

        self._is_china = self._check_if_china()

    @Slot(str, str)
    def start_download_task(self, url, folder):
        """
        这是子线程的真正入口。
        使用 @Slot 装饰器确保它作为一个槽函数被正确识别。
        """
        try:
            result = self.download(url, folder)
            self.download_finished.emit(result)
        except Exception as e:
            self.download_error.emit(str(e))

    def download(self, down_url: str, save_folder, cn_url: str = None) -> str:
        if not down_url: raise ValueError("URL 不能为空")

        parsed_url = urlparse(down_url)
        urls_to_try = self._get_url_list(down_url, parsed_url, cn_url)

        is_github = "github" in parsed_url.netloc.lower()
        last_exception = ""
        for attempt, current_url in enumerate(urls_to_try):
            try:
                # 根据当前实际 URL 确定保存路径（兼容 url_cn 不同后缀）
                current_parsed = urlparse(current_url)
                save_path = Path(save_folder) / Path(current_parsed.path).name
                downloaded_size = save_path.stat().st_size if save_path.exists() else 0
                headers = {'User-Agent': 'Mozilla/5.0'}
                if downloaded_size > 0:
                    headers['Range'] = f'bytes={downloaded_size}-'
                with self.session.get(current_url, headers=headers, stream=True, timeout=(5, 300)) as r:
                    # 关键修复：处理 416 错误（本地文件比服务器还大）
                    if r.status_code == 416:
                        BM_LOG.warning("Range请求无效，重置文件...")
                        if save_path.exists(): save_path.unlink()
                        downloaded_size = 0
                        # 重新请求（不带Range）
                        r = self.session.get(current_url, headers={'User-Agent': 'Mozilla/5.0'}, stream=True,
                                             timeout=(5, 300))

                    r.raise_for_status()

                    mode = 'ab' if r.status_code == 206 else 'wb'
                    if mode == 'wb': downloaded_size = 0

                    # 修复：容错处理 content-length 为空的情况
                    raw_cl = r.headers.get('content-length')
                    total_size = (int(raw_cl) + downloaded_size) if raw_cl else 0

                    last_progress_time = 0
                    with open(save_path, mode) as f:
                        last_progress_time = time.time()
                        last_bytes = downloaded_size  # 记录起始字节

                        for chunk in r.iter_content(chunk_size=128 * 1024):
                            if chunk:
                                f.write(chunk)
                                downloaded_size += len(chunk)

                                current_time = time.time()
                                interval = current_time - last_progress_time

                                # 每 0.5 秒计算并发送一次进度
                                if interval >= 0.5:
                                    # 计算单位时间内的增量
                                    chunk_delta = downloaded_size - last_bytes
                                    speed = chunk_delta / interval  # 字节/秒

                                    self._emit_status(downloaded_size, total_size, speed)

                                    # 更新快照
                                    last_progress_time = current_time
                                    last_bytes = downloaded_size

                if save_path.exists() and save_path.stat().st_size > 0:
                    self.download_finished.emit(str(save_path))
                    return str(save_path)

            except Exception as e:
                last_exception = e
                BM_LOG.warning(f"源 {attempt} 下载失败: {e}")
                continue

        error_msg = f"下载失败: {last_exception}\n"
        if is_github and self._is_china:
            error_msg += (
                "\n【检测到您处于中国区环境】\n"
                "1. 请尝试【关闭】科学上网/加速器后重试（直连镜像站）。\n"
                "2. 如果必须使用代理，请确保开启了【全局/TUN模式】且节点有效。"
            )
        else:
            error_msg += "\n请检查网络连接或链接是否失效。"

        raise RuntimeError(error_msg)

    def _check_if_china(self) -> bool:
        try:
            response = self.session.get(
                "http://ip-api.com/json/?fields=countryCode",
                timeout=2)
            if response.status_code == 200:
                return response.json().get("countryCode") == "CN"
        except Exception as e:
            BM_LOG.debug(f"IP区域检测失败，默认国内: {e}")
        return True  # 失败则默认国内，走加速镜像

    def _get_url_list(self, down_url, parsed_url, cn_url=None):
        """根据区域生成下载 URL 队列"""
        urls = []
        is_github = any(domain in parsed_url.netloc for domain in ['github.com', 'githubusercontent.com'])

        # 核心逻辑：国内镜像不限域名，优先使用
        if cn_url and self._is_china:
            BM_LOG.info("发现国内镜像下载地址，优先使用")
            urls.append(cn_url)

        # 中国区 + GitHub 源：添加代理加速
        if is_github and self._is_china:
            BM_LOG.info("中国区 GitHub 下载，启用加速代理")
            for proxy in ProjectGlobal.PROXIES:
                urls.append(f"{proxy.rstrip('/')}/{down_url}")

        # 无论如何，原始链接都作为保底（或在非中国区作为首选）
        urls.append(down_url)
        return urls

    def _get_headers(self):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*'
        }

    def _emit_status(self, current, total, speed):
        # 格式化速度单位
        if speed < 1024 * 1024:
            speed_str = f"{speed / 1024:.1f} KB/s"
        else:
            speed_str = f"{speed / 1024 / 1024:.1f} MB/s"

        if total > 0:
            perc = (current / total) * 100
            msg = f"进度: {perc:.1f}% | 速度: {speed_str} | ({current / 1024 / 1024:.1f}MB / {total / 1024 / 1024:.1f}MB)"
        else:
            msg = f"已下载: {current / 1024 / 1024:.1f}MB | 速度: {speed_str}"

        self.download_progress.emit({'status': True, 'msg': msg})


def demo_download():
    # 彻底清理环境变量，防止 requests 尝试连接不存在的本地代理文件
    os.environ.pop('http_proxy', None)
    os.environ.pop('https_proxy', None)
    os.environ.pop('all_proxy', None)

    app = QCoreApplication(sys.argv)

    test_url = "https://github.com/bmscriptsbox/tkinter/releases/download/tkinter/3.8.10.7z"
    save_dir = Path("./test_download")
    save_dir.mkdir(exist_ok=True)

    downloader = XDownLoad()
    thread = QThread()

    # 1. 移动到子线程
    downloader.moveToThread(thread)

    # 2. 连接信号（用于打印反馈）
    downloader.download_progress.connect(lambda msg: print(f"[进度] {msg}"))
    downloader.download_finished.connect(lambda path: [print(f"\n[成功] {path}"), app.quit()])
    downloader.download_error.connect(lambda err: [print(f"\n[失败] {err}"), app.quit()])

    # 3. 关键：当线程启动时，触发 downloader 的 Slot
    # 注意：这里使用 lambda 时，Qt 会自动处理跨线程的信号调度
    thread.started.connect(lambda: downloader.start_download_task(test_url, str(save_dir)))

    # 4. 线程销毁时自动退出（好习惯）
    thread.finished.connect(thread.deleteLater)

    thread.start()

    print(f"测试开始 - 区域判定: {'中国区' if downloader._is_china else '境外区'}")
    sys.exit(app.exec_())


if __name__ == '__main__':
    demo_download()
