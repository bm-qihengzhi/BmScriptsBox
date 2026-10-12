"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
from PySide2.QtWidgets import QWidget, QVBoxLayout, QFrame
from xsideui import XGroupCard, XLabel, XPushButton, XSize, XButtonVariant, XColor, tr, XScrollArea

from app.utils import BmNotify, BM_LOG
from app.servers.wechat_push import WechatPushService
from app.servers.wechat_push.login_dialog import WechatLoginDialog

_BTN_LOGIN = '扫码绑定'
_BTN_BIND = '重新绑定'



class PushWidget(QWidget):
    """微信推送的连接页（独立 tab）：只负责扫码登录与收件人绑定，有且仅有一个收件人，
    本页不主动发任何请求：绑定/解绑/测试都由点击触发。推不推由每个定时任务自己勾选。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._init_signal()
        self._refresh_state()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(11, 11, 11, 11)
        layout.setSpacing(11)

        scroll = XScrollArea()
        scroll.setWidgetResizable(True)
        scroll.set_scrollbar_visible(True, False)
        layout.addWidget(scroll)

        frame = QFrame()
        scroll.setWidget(frame)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)

        card = XGroupCard(title=tr('WeChat ClawBot'))
        frame_layout.addWidget(card)
        frame_layout.addStretch(1)

        # 连接状态
        status_group = card.add_group()
        card.addWidget(XLabel(tr('Connection Status')), group_index=status_group.index, stretch=1)
        self.wechat_status_label = XLabel('')
        card.addWidget(self.wechat_status_label, group_index=status_group.index, stretch=0)

        # 收件人（唯一，由绑定流程写入，不可手填）
        to_group = card.add_group()
        card.addWidget(XLabel(tr('Recipient')), group_index=to_group.index, stretch=1)
        self.wechat_to_label = XLabel('')
        self.wechat_to_label.set_font_size(12)
        card.addWidget(self.wechat_to_label, group_index=to_group.index, stretch=0)

        # 绑定 / 断开 / 测试
        btn_group = card.add_group()
        self.wechat_bind_btn = XPushButton(text=_BTN_LOGIN, size=XSize.SMALL,
                                           variant=XButtonVariant.FILLED, color='primary')
        self.wechat_logout_btn = XPushButton(text='断开连接', size=XSize.SMALL,
                                             variant=XButtonVariant.FILLED, color=XColor.TERTIARY)
        self.wechat_test_btn = XPushButton(text=tr('Send Test'), size=XSize.SMALL,
                                           variant=XButtonVariant.FILLED, color=XColor.TERTIARY)
        card.addWidget(self.wechat_bind_btn, group_index=btn_group.index, stretch=0)
        card.addWidget(self.wechat_logout_btn, group_index=btn_group.index, stretch=0)
        card.addWidget(self.wechat_test_btn, group_index=btn_group.index, stretch=0)




    def _init_signal(self):
        self.wechat_bind_btn.clicked.connect(self._open_dialog)
        self.wechat_logout_btn.clicked.connect(self._logout)
        self.wechat_test_btn.clicked.connect(self._send_wechat_test)

    def _refresh_state(self):
        """只读内存里的服务状态，不发任何网络请求。"""
        svc = WechatPushService.instance()
        logged = svc.is_logged_in()
        self.wechat_status_label.setText(svc.connection_status())
        self.wechat_to_label.setText(svc.recipient_id() or '未绑定')
        self.wechat_bind_btn.setText(_BTN_BIND if logged else _BTN_LOGIN)
        self.wechat_logout_btn.setEnabled(logged)


    # ------------------------------------------------------------- 绑定/断开

    def _open_dialog(self):
        """未登录走扫码+绑定，已登录只重开绑定窗口；两者都由窗口生命周期管住收发。"""
        svc = WechatPushService.instance()
        if svc.session_busy():
            BmNotify().show_warning_notify('上一次绑定还在收尾，请过几秒再试', in_window=True)
            return
        mode = 'bind' if svc.is_logged_in() else 'login'
        dlg = WechatLoginDialog(parent=self, mode=mode)
        dlg.login_finished.connect(self._on_dialog_finished)
        dlg.exec_()
        self._refresh_state()

    def _on_dialog_finished(self, ok, msg):
        """扫码窗口内部已把「登录 + 绑定」跑完，这里只报结果。"""
        if ok:
            # 绑定成功但回执没送达时，worker 会带上一句如实的 msg
            BmNotify().show_success_notify(msg or '已连接并绑定收件人', in_window=True)
        elif msg and msg != '已取消':
            BmNotify().show_warning_notify(msg, in_window=True)

    def _logout(self):
        WechatPushService.instance().logout()
        BmNotify().show_success_notify('已断开连接，需重新扫码才能推送', in_window=True)
        self._refresh_state()

    # ------------------------------------------------------------------ 测试

    def _send_wechat_test(self):
        svc = WechatPushService.instance()
        if svc.send('这是一条来自不忙脚本盒子的测试消息'):
            BmNotify().show_success_notify('测试消息已发送', in_window=True)
        else:
            reason = svc.last_skip_reason() or '未知原因，详见日志 BmLogs/BmLogs.log'
            BM_LOG.warning('[微信推送] 测试发送未成功：%s' % reason)
            BmNotify().show_warning_notify('发送未成功：%s' % reason, in_window=True)
        self._refresh_state()
