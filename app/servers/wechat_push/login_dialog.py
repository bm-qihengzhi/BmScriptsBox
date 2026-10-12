"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

微信推送扫码登录对话框：后台线程跑 WechatPushService.login() 再跑 bind_recipient()，
UI 侧渲染二维码、更新状态、需要时收集手机数字配对码；
登录成功后在同一线程的有限窗口内等待对方发来一条消息，绑定唯一收件人后结束。
"""
import base64
import re
import threading

from PySide2.QtCore import QThread, Signal, Qt
from PySide2.QtGui import QPixmap, QImage, QPainter, QColor
from PySide2.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel

from xsideui import XDialog, XLabel, XLineEdit, XPushButton, XButtonVariant, XSize, XColor, tr

from app.utils import BM_LOG
from app.servers.wechat_push.service import WechatPushService

_B64_IMAGE = re.compile(r'^data:image/(\w+);base64,(.+)$', re.S)
_BARE_B64 = re.compile(r'^[A-Za-z0-9+/]{120,}={0,2}$', re.S)
_IMAGE_URL = re.compile(r'\.(png|jpe?g|gif|bmp|webp|svg)(\?|$)', re.I)
_QR_QUIET = 4   # 标准静区：4 个模块
_QR_SIZE = 300  # 二维码绘制/显示上限边长（模块边长取整数，必要时小于该值）

# 关窗时不等待线程（它可能正卡在一次长轮询里），所以在这里替还在跑的 worker 兜住引用：
# worker 不隶属 dialog，dialog 析构后若没人持有，Python 会析构一个正在运行的 QThread。
# 线程 finished 后由它自己从这个集合里摘掉。
_RUNNING_WORKERS = set()


def _shape_of(s):
    """只描述内容形态，不含内容本身，可安全写日志。"""
    if s.startswith('data:image/'):
        return 'data-uri(%d)' % len(s)
    if s.startswith('<svg'):
        return 'svg(%d)' % len(s)
    if s.startswith('http'):
        return 'url(%d)' % len(s)
    if _BARE_B64.match(s.replace('\n', '')):
        return 'base64(%d)' % len(s)
    return 'text(%d)' % len(s)


def _matrix_pixmap(matrix, max_px=_QR_SIZE, border=_QR_QUIET):
    """把 bool 矩阵用 QPainter 画成 QPixmap（不依赖 PIL）。
    每个模块取整数边长，既避免相邻模块间出现发丝白线，也避免缩放采样糊码。"""
    n = len(matrix)
    if not n:
        return QPixmap()
    side = n + border * 2
    k = max(3, max_px // side)
    size = side * k
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.white)
    painter = QPainter(img)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(0, 0, 0))
    for r in range(n):
        row = matrix[r]
        for c in range(n):
            if row[c]:
                painter.drawRect((c + border) * k, (r + border) * k, k, k)
    painter.end()
    return QPixmap.fromImage(img)


def _qr_from_text(text):
    """用 qrcode 生成矩阵并自绘（内嵌运行时可能没有 Pillow）。"""
    import qrcode
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=1, border=0)
    qr.add_data(text)
    qr.make(fit=True)
    return _matrix_pixmap(qr.get_matrix())


def _qr_pixmap(content):
    """渲染二维码。服务端 qrcode_img_content 是「扫码用的 URL」而非图片，
    因此优先尝试当作图片字节解码（http 图片 / data-uri / svg / 裸 base64），
    解码不了就把内容本身编码成二维码。"""
    pm = QPixmap()
    s = str(content or '').strip()
    if not s:
        return pm

    raw = None
    if s.startswith('http'):
        # 服务端给的通常是「扫码用 URL」而非图片地址：只在明显是图片时才下载，
        # 否则直接落到下面的本地编码，避免白白等一次 HTTP 超时。
        if _IMAGE_URL.search(s):
            try:
                import requests
                resp = requests.get(s, timeout=15)
                if resp.status_code == 200:
                    raw = resp.content
            except Exception as e:
                BM_LOG.warning('[微信推送] 拉取二维码图片异常: %s' % e)
    elif s.startswith('data:image/'):
        m = _B64_IMAGE.match(s)
        if m:
            try:
                raw = base64.b64decode(m.group(2))
            except Exception:
                raw = None
    elif s.startswith('<svg'):
        raw = s.encode('utf-8')
    elif _BARE_B64.match(s.replace('\n', '')):
        try:
            raw = base64.b64decode(s)
        except Exception:
            raw = None

    if raw:
        pm = QPixmap()
        pm.loadFromData(raw)
        if not pm.isNull():
            return pm

    try:
        return _qr_from_text(s)
    except Exception as e:
        BM_LOG.error('[微信推送] 生成二维码失败: %s（内容形态 %s）' % (e, _shape_of(s)))
    return QPixmap()


class _LoginWorker(QThread):
    """在子线程执行阻塞式登录/收件人绑定，经 Qt 信号回投到 UI 线程。
    mode='login' 先扫码再绑定；mode='bind' 复用已有 bot_token，只开绑定窗口。"""
    qr_ready = Signal(str)
    status_changed = Signal(str)
    ask_code = Signal(str)
    bind_phase = Signal()
    done = Signal(bool, str)

    def __init__(self, mode='login', parent=None):
        super().__init__(parent)
        self._mode = mode
        self._abort = False
        self._code_event = threading.Event()
        self._code_value = ''

    def abort(self):
        self._abort = True
        self._code_event.set()   # 解除可能在的配对码等待

    def _ask_verify_code(self, prompt):
        self._code_value = ''
        self._code_event.clear()
        self.ask_code.emit(prompt)
        # 分片等待，便于取消
        while not self._code_event.wait(0.3):
            if self._abort:
                return ''
        return self._code_value

    def submit_code(self, value):
        self._code_value = value
        self._code_event.set()

    def run(self):
        BM_LOG.info('[微信推送] 会话线程启动，mode=%s' % self._mode)
        svc = WechatPushService.instance()
        if not svc.begin_session():
            self.done.emit(False, '上一次绑定还在收尾，请过几秒再试')
            return
        try:
            if self._mode == 'login':
                res = svc.login(
                    on_qr=lambda c: self.qr_ready.emit(str(c)),
                    on_status=lambda t: self.status_changed.emit(str(t)),
                    ask_verify_code=self._ask_verify_code,
                    should_abort=lambda: self._abort,
                )
                BM_LOG.info('[微信推送] 登录结束：ok=%s error=%s'
                            % (res.get('ok'), res.get('error') or '无'))
                if not res.get('ok'):
                    self.done.emit(False, res.get('error', '') or '')
                    return
            elif not svc.is_logged_in():
                self.done.emit(False, '未登录，请先扫码')
                return
            # 登录只是拿到 bot_token；还必须在有限窗口内收到对方一条消息才能绑定唯一收件人
            self.bind_phase.emit()
            b = svc.bind_recipient(on_status=lambda t: self.status_changed.emit(str(t)),
                                   should_abort=lambda: self._abort)
            BM_LOG.info('[微信推送] 绑定结束：ok=%s error=%s'
                        % (b.get('ok'), b.get('error') or '无'))
            if b.get('ok'):
                # 绑定已生效，但「连接成功」回执可能没送达：如实告诉用户
                self.done.emit(True, '' if b.get('notice_sent', True) else
                               '已绑定收件人，但连接成功提示未送达')
            elif self._abort:
                self.done.emit(False, '已取消')
            elif self._mode == 'login':
                self.done.emit(False, '已登录，但未绑定收件人：%s' % (b.get('error') or '未知原因'))
            else:
                self.done.emit(False, b.get('error') or '绑定未完成')
        except Exception as e:
            BM_LOG.error('[微信推送] 会话线程异常: %s' % e)
            self.done.emit(False, str(e))
        finally:
            svc.end_session()


class WechatLoginDialog(XDialog):
    """扫码登录 / 收件人绑定窗口。收发只在本窗口打开期间发起，关窗即取消；
    关窗不等线程，只剩那一次已在途的请求（最长 LONG_POLL_TIMEOUT 秒）自行收尾。"""
    login_finished = Signal(bool, str)

    def __init__(self, parent=None, mode='login'):
        super().__init__(parent=parent)
        self.setModal(True)
        self._mode = mode if mode in ('login', 'bind') else 'login'
        self._worker = None
        self._init_ui()
        self._start()

    def _init_ui(self):
        self.hide_title_bar()
        bind_only = self._mode == 'bind'
        self.resize(352, 250 if bind_only else 470)
        frame = QFrame()
        self.addWidget(frame)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(10)

        self._title = XLabel('重新绑定收件人' if bind_only else tr('微信扫码登录'),
                             alignment=Qt.AlignHCenter)
        lay.addWidget(self._title, alignment=Qt.AlignHCenter)

        self._qr = QLabel()
        self._qr.setFixedSize(_QR_SIZE, _QR_SIZE)
        self._qr.setAlignment(Qt.AlignCenter)
        lay.addWidget(self._qr, alignment=Qt.AlignHCenter)
        if bind_only:
            # 不扫码：这块位置直接放绑定说明
            self._qr.setText('请给ClawBot机器人随意发一条消息')

        self._status = XLabel('正在获取二维码…' if not bind_only else '正在等待对方消息…')
        self._status.set_font_size(12)
        self._status.set_word_wrap(True)
        self._status.set_alignment(Qt.AlignHCenter)
        self._status.setFixedWidth(_QR_SIZE)
        lay.addWidget(self._status, alignment=Qt.AlignHCenter)

        # 配对码输入（默认隐藏）
        self._code_row = QHBoxLayout()
        self._code_edit = XLineEdit(placeholder='000000')
        self._code_edit.setMaximumWidth(120)
        self._code_confirm = XPushButton(text=tr('确认'), variant=XButtonVariant.FILLED, )
        self._code_row.addStretch()
        self._code_row.addWidget(self._code_edit)
        self._code_row.addWidget(self._code_confirm)
        self._code_row.addStretch()
        code_container = QFrame()
        code_container.setLayout(self._code_row)
        code_container.setVisible(False)
        self._code_container = code_container
        lay.addWidget(code_container)
        self._code_confirm.clicked.connect(self._on_submit_code)

        # 关掉本窗口即停止收发，所以需要一个明确的出口（标题栏已隐藏）
        btn_row = QHBoxLayout()
        self._cancel_btn = XPushButton(text='关闭' if bind_only else '取消登录',
                                       size=XSize.SMALL, variant=XButtonVariant.FILLED,
                                       color=XColor.TERTIARY)
        btn_row.addStretch()
        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch()
        btns = QFrame()
        btns.setLayout(btn_row)
        lay.addWidget(btns)
        self._cancel_btn.clicked.connect(self.close)

    def _start(self):
        # 刻意不传 parent：关窗后 dialog 会先析构，父化会让 Qt 去销毁一个仍在运行的 QThread
        worker = _LoginWorker(self._mode)
        _RUNNING_WORKERS.add(worker)
        # 默认参数只捕获 worker 本身，不捕获 self，免得 dialog 被信号连接拖住不放
        worker.finished.connect(lambda w=worker: _RUNNING_WORKERS.discard(w))
        worker.qr_ready.connect(self._on_qr)
        worker.status_changed.connect(self._on_status)
        worker.ask_code.connect(self._on_ask_code)
        worker.bind_phase.connect(self._on_bind_phase)
        worker.done.connect(self._on_done)
        self._worker = worker
        worker.start()

    # ------------------------------------------------------------- 槽（UI 线程）

    def _on_bind_phase(self):
        """登录已完成，二维码作废：让位给绑定收件人的提示。"""
        self._qr.setText('请给ClawBot机器人随意发一条消息')
        self._qr.setFixedSize(_QR_SIZE, _QR_SIZE)

    def _on_qr(self, content):
        pm = _qr_pixmap(content)
        if pm.isNull():
            self._qr.setText('二维码加载失败')
            self._on_status('二维码渲染失败，请关闭后重试')
            return
        if pm.width() > _QR_SIZE or pm.height() > _QR_SIZE:
            # 仅超大图才缩小；自绘二维码模块边长为整数，直接原样显示最清晰
            pm = pm.scaled(_QR_SIZE, _QR_SIZE, Qt.KeepAspectRatio, Qt.FastTransformation)
        self._qr.setFixedSize(pm.size())
        self._qr.setPixmap(pm)

    def _on_status(self, text):
        self._status.setText(text)

    def _on_ask_code(self, prompt):
        self._status.setText(prompt)
        self._code_container.setVisible(True)
        self._code_edit.setText('')
        self._code_edit.setFocus()

    def _on_submit_code(self):
        if self._worker:
            self._code_container.setVisible(False)
            self._worker.submit_code(self._code_edit.text().strip())

    def _on_done(self, ok, message):
        self.login_finished.emit(bool(ok), message or '')
        self.close()

    def closeEvent(self, event):
        if self._worker and self._worker.isRunning():
            # 只发取消信号、绝不在这里 wait：worker 正阻塞在一次最长 LONG_POLL_TIMEOUT 秒的请求里，
            # 等它就是把 UI 冻住一个超时周期。引用由 _RUNNING_WORKERS 兜住，线程跑完自行释放。
            self._worker.abort()
        super().closeEvent(event)
