"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
import json
import os
import subprocess
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

from PySide2.QtCore import QObject, Signal, Slot

from app.data import ProjectGlobal
from app.utils import BM_LOG
from app.utils.region import is_china


class _SlowDownload(RuntimeError):
    """下载速度过慢触发的换源信号"""


class XDownLoad(QObject):
    """下载器 - 基于 MUDL (mudl.exe) 的多线程多源下载"""
    download_progress = Signal(dict)
    """
    格式约定：{'status':True,'msg':"xxx完成"}
    """
    download_finished = Signal(str)
    download_error = Signal(str)

    CONNECTIONS = 8
    TIMEOUT = 20
    RETRIES = 5
    MAX_SOURCES = 16
    PROGRESS_INTERVAL = 0.3
    SLOW_SPEED_THRESHOLD = 100 * 1024  # 100KB/s 以下视为慢速
    SLOW_DURATION = 10.0  # 连续慢速达 10 秒触发换源

    def __init__(self):
        super().__init__()
        self._is_china = is_china()
        self._proc = None

    @property
    def mudl_path(self) -> Path:
        """定位并校验 MUDL 可执行文件"""
        path = Path(__file__).parent / 'mudl.exe'
        if not path.exists():
            raise FileNotFoundError(f"找不到 MUDL 下载工具: {path}")
        return path

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

    def download(self, down_url: str, save_folder, cn_url: str = None,
                 output_filename: str = None) -> str:
        if not down_url:
            raise ValueError("URL 不能为空")

        parsed_url = urlparse(down_url)
        is_github = "github" in parsed_url.netloc.lower()

        if output_filename:
            filename = output_filename
        else:
            filename = Path(unquote(parsed_url.path)).name
        if not filename:
            raise ValueError("无法从 URL 中解析出文件名")

        save_dir = Path(save_folder)
        save_dir.mkdir(parents=True, exist_ok=True)

        # 国内镜像：只要提供就永远优先（不按地区门控，兼容挂梯子场景）
        base = []
        if cn_url:
            BM_LOG.info("使用国内镜像下载地址")
            base.append(cn_url)
        proxies = self._build_proxy_urls(down_url) if is_github else []

        if self._is_china:
            # 中国区：镜像 → GitHub代理 → 原始链接，一次跑完
            sources = base + proxies + [down_url]
            try:
                return self._run_mudl(sources, filename, save_dir, is_github, watchdog=True)
            except _SlowDownload:
                BM_LOG.info("多源下载过慢，回退到 镜像+直连 重试")
                return self._run_mudl(base + [down_url], filename, save_dir,
                                      is_github, watchdog=False)

        # 非中国区：直连优先（挂梯子时通常可直连）；github 慢速/失败后带代理源重试一次
        try:
            return self._run_mudl(base + [down_url], filename, save_dir,
                                  is_github, watchdog=True)
        except RuntimeError:
            if not is_github:
                raise
            BM_LOG.info("直连下载失败或过慢，切换 GitHub 代理源重试")
            return self._run_mudl(base + proxies + [down_url], filename, save_dir,
                                  is_github, watchdog=False)

    def _run_mudl(self, sources: list, filename: str, save_dir: Path,
                  is_github: bool, watchdog: bool = True) -> str:
        """执行一次 MUDL 下载并返回保存路径，失败抛 RuntimeError"""
        save_path = save_dir / filename

        deduped = []
        for s in sources:
            if s not in deduped:
                deduped.append(s)
        sources = deduped[:self.MAX_SOURCES]

        self.download_progress.emit({
            'status': True,
            'msg': f"正在从 {len(sources)} 个源下载 ..."
        })

        cmd = [
            str(self.mudl_path),
            '-q',
            '-c', str(self.CONNECTIONS),
            '--progress', 'json',
            '-d', str(save_dir),
            '-o', filename,
            '--timeout', str(self.TIMEOUT),
            '--retries', str(self.RETRIES),
        ] + sources

        BM_LOG.debug(f"[MUDL] {' '.join(cmd[:8])} ...")
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
        self._proc = proc

        last_log = ""
        last_emit_time = 0.0
        slow_since = None
        try:
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                except ValueError:
                    last_log = line[-500:]
                    BM_LOG.debug(f"[MUDL] {line}")
                    continue

                if evt.get('s') == 'dl':
                    now = time.time()
                    speed = evt.get('sp', 0)
                    downloaded = evt.get('dl', 0)
                    total = evt.get('sz', 0)

                    # 慢速看门狗：已收数据且未完成时，持续低于阈值达 SLOW_DURATION 则换源
                    if watchdog and is_github and downloaded > 0 and not (total > 0 and downloaded >= total):
                        if speed < self.SLOW_SPEED_THRESHOLD:
                            if slow_since is None:
                                slow_since = now
                            elif now - slow_since >= self.SLOW_DURATION:
                                BM_LOG.warning(
                                    f"下载速度过慢 ({speed / 1024:.0f} KB/s)，中止并切换源")
                                proc.terminate()
                                proc.wait()
                                raise _SlowDownload(
                                    f"下载速度过慢 ({speed / 1024:.0f} KB/s)，切换源")
                        else:
                            slow_since = None

                    if now - last_emit_time >= self.PROGRESS_INTERVAL:
                        self._emit_from_event(evt)
                        last_emit_time = now
                elif evt.get('s') == 'done':
                    last_log = f"完成 {evt.get('dl', 0)} 字节"
        finally:
            self._proc = None

        returncode = proc.wait()
        if returncode != 0:
            error_msg = f"下载失败: {last_log or f'MUDL 退出码 {returncode}'}"
            if is_github and self._is_china:
                error_msg += (
                    "\n【检测到您处于中国区环境】\n"
                    "1. 请尝试【关闭】科学上网/加速器后重试（直连镜像站）。\n"
                    "2. 如果必须使用代理，请确保开启了【全局/TUN模式】且节点有效。"
                )
            else:
                error_msg += "\n请检查网络连接或链接是否失效。"
            raise RuntimeError(error_msg)

        if not save_path.exists() or save_path.stat().st_size == 0:
            raise RuntimeError(f"下载产物缺失或为空: {save_path}")

        self.download_finished.emit(str(save_path))
        return str(save_path)

    def cancel(self):
        """中断当前下载进程"""
        if self._proc is not None and self._proc.poll() is None:
            try:
                self._proc.terminate()
                BM_LOG.info("已发送下载取消请求")
            except Exception as e:
                BM_LOG.warning(f"取消下载失败: {e}")

    # --- 内部辅助方法 ---

    @staticmethod
    def _build_proxy_urls(target_url: str) -> list:
        """根据代理前缀列表生成完整代理下载地址"""
        return [f"{prefix.rstrip('/')}/{target_url}" for prefix in ProjectGlobal.PROXIES]

    def _emit_from_event(self, evt: dict):
        """将 MUDL JSON 进度事件转换为前端进度文案"""
        downloaded = evt.get('dl', 0)
        total = evt.get('sz', 0)
        speed = evt.get('sp', 0)

        if total > 0:
            perc = evt.get('p', 0.0)
            msg = (f"进度: {perc:.1f}% | 速度: {self._fmt_speed(speed)} | "
                   f"({self._fmt_size(downloaded)} / {self._fmt_size(total)})")
        else:
            msg = f"已下载: {self._fmt_size(downloaded)} | 速度: {self._fmt_speed(speed)}"

        self.download_progress.emit({'status': True, 'msg': msg})

    @staticmethod
    def _fmt_speed(speed) -> str:
        if speed < 1024 * 1024:
            return f"{speed / 1024:.1f} KB/s"
        return f"{speed / 1024 / 1024:.1f} MB/s"

    @staticmethod
    def _fmt_size(size) -> str:
        return f"{size / 1024 / 1024:.1f}MB"