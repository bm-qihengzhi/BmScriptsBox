"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

微信推送服务单例：管理登录态、唯一收件人绑定与按需推送。
状态持久化到 BmData/weixin_state.json，扫码一次即长期有效，
唯一失效信号是服务端 ret/errcode==-14；收到 -14 才标记需重新扫码并暂停推送。
不驻留后台线程：只在绑定收件人的短暂窗口内收消息，
之后要推送时直接用已持久化的 bot_token + context_token 发一次请求即可。
"""
import json
import os
import threading
import time
from datetime import datetime

from app.data.database import ConfigDatabase
from app.data.model import db_path
from app.utils import BM_LOG, BmNotify

from . import api

# 绑定窗口：登录成功后在此时长内等对方发一条消息，绑定成功即结束（不转成常驻轮询）
BIND_TIMEOUT = 180

# 绑定成功后回推给对方的固定提示
BIND_OK_TEXT = (
    '[不忙脚本盒子] 连接成功\n'
    '本微信号已绑定为定时任务推送收件人。\n'
    '之后定时任务的执行结果会推送到这里；如需更换收件人，请在电脑端重新扫码绑定。'
)


def _empty_state():
    return {
        'bot_token': '',
        'baseurl': '',
        'ilink_bot_id': '',
        'ilink_user_id': '',
        'get_updates_buf': '',
        'recipient': {'to': '', 'context_token': ''},
    }


class WechatPushService:
    """微信推送的唯一状态属主（进程内单例）。除绑定窗口外不发任何常驻请求。"""
    _instance = None
    _inst_lock = threading.Lock()

    def __init__(self):
        self._lock = threading.Lock()          # 保护 _state / _needs_reconnect / _needs_rebind / _last_reason / _busy
        self._needs_reconnect = False
        self._needs_rebind = False
        self._busy = False                     # 同一时刻只允许一个登录/绑定窗口在收发
        self._login_time = 0.0
        self._last_reason = ''
        self._state_file = db_path.parent / 'weixin_state.json'
        self._state = self._read_file()
        BM_LOG.info('[微信推送] 服务初始化：状态文件=%s 本地登录态=%s 已绑定收件人=%s'
                    % (self._state_file, '有' if self._state.get('bot_token') else '无',
                       '有' if (self._state.get('recipient') or {}).get('to') else '无'))

    @classmethod
    def instance(cls):
        with cls._inst_lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    # --------------------------------------------------------- 会话窗口互斥

    def session_busy(self):
        """是否已有一个登录/绑定窗口在收发（关窗后线程可能还在收尾一次长轮询）。"""
        with self._lock:
            return self._busy

    def begin_session(self):
        """占用会话窗口；已被占用返回 False（避免两个窗口同时 notifystart/轮询）。"""
        with self._lock:
            if self._busy:
                return False
            self._busy = True
            return True

    def end_session(self):
        with self._lock:
            self._busy = False

    def _set_reason(self, reason):
        with self._lock:
            self._last_reason = reason

    # ------------------------------------------------------------- 状态文件

    def _read_file(self):
        st = _empty_state()
        try:
            if self._state_file.exists():
                raw = json.loads(self._state_file.read_text(encoding='utf-8'))
                if isinstance(raw, dict):
                    for k in st:
                        if k in raw:
                            st[k] = raw[k]
                    if not isinstance(st.get('recipient'), dict):
                        st['recipient'] = {'to': '', 'context_token': ''}
                    self._migrate_legacy(raw, st)
                    BM_LOG.info('[微信推送] 已读取状态文件，字段=%s' % sorted(raw.keys()))
            else:
                BM_LOG.info('[微信推送] 状态文件不存在（首次使用，视为未登录）')
        except (OSError, ValueError, TypeError) as e:
            BM_LOG.error('[微信推送] 读状态失败，从空状态开始: %s' % e)
        return st

    @staticmethod
    def _migrate_legacy(raw, st):
        """旧版多联系人 contexts 迁移成唯一 recipient（现在只支持一个收件人）。"""
        ctxs = raw.get('contexts')
        if not isinstance(ctxs, dict) or not ctxs:
            return
        picked = ''
        last = raw.get('last_contact')
        if isinstance(last, dict):
            fid = str(last.get('from_id') or '')
            if fid in ctxs and str(ctxs.get(fid) or '') == str(last.get('context_token') or ''):
                picked = fid
        if not picked:
            try:
                cfg_to = (ConfigDatabase.get_all().get('wechat_push_to') or '').strip()
            except Exception:
                cfg_to = ''
            if cfg_to in ctxs:
                picked = cfg_to
        if not picked and len(ctxs) == 1:
            picked = list(ctxs.keys())[0]
        if picked:
            st['recipient'] = {'to': picked, 'context_token': str(ctxs.get(picked) or '')}
            BM_LOG.info('[微信推送] 旧状态有 %d 个联系人，已迁移为唯一收件人 %s'
                        % (len(ctxs), api.redact(picked)))
        else:
            BM_LOG.warning('[微信推送] 旧状态有 %d 个联系人但无法确定唯一收件人，请重新绑定' % len(ctxs))

    def _save_locked(self):
        """原子写盘（调用方须持有 _lock）。
        覆盖失败时保留刚写好的临时文件：绝不为「先腾位置再替换」而先删正式文件，
        那样一旦 replace 失败就把 bot_token 永久弄丢了。"""
        try:
            tmp = self._state_file.with_suffix('.json.tmp')
            tmp.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding='utf-8')
            try:
                os.replace(str(tmp), str(self._state_file))
            except OSError as e:
                BM_LOG.error('[微信推送] 覆盖状态文件失败（本次改动保留在 .json.tmp，下次写盘会带上）: %s' % e)
        except (OSError, ValueError, TypeError) as e:
            BM_LOG.error('[微信推送] 存状态失败: %s' % e)

    # ------------------------------------------------------------- 只读快照

    def is_logged_in(self):
        with self._lock:
            return bool(self._state.get('bot_token')) and not self._needs_reconnect

    def needs_reconnect(self):
        with self._lock:
            return self._needs_reconnect

    def needs_rebind(self):
        with self._lock:
            return self._needs_rebind

    def recipient_id(self):
        """当前绑定的唯一收件人 id（未绑定返回 ''）。"""
        with self._lock:
            return str((self._state.get('recipient') or {}).get('to') or '')

    def has_recipient(self):
        return bool(self.recipient_id())

    def connection_status(self):
        with self._lock:
            if self._needs_reconnect:
                return '需重新扫码'
            if not self._state.get('bot_token'):
                return '未登录'
            if not (self._state.get('recipient') or {}).get('to'):
                return '已登录，未绑定'
            if self._needs_rebind:
                # 服务端没有「context_token 失效」专用码，只能笼统怀疑；下次发送成功会自动清掉
                return '最近推送被拒，可尝试重新绑定'
            return '已连接'

    def _session_snapshot(self):
        with self._lock:
            return (self._state.get('bot_token', ''),
                    self._state.get('baseurl') or api.BASE_URL,
                    self._state.get('get_updates_buf', ''),
                    str(self._state.get('ilink_bot_id') or ''),
                    self._needs_reconnect)

    def _recipient_snapshot(self):
        with self._lock:
            r = self._state.get('recipient') or {}
            return (self._state.get('bot_token', ''),
                    self._state.get('baseurl') or api.BASE_URL,
                    str(r.get('to') or ''),
                    str(r.get('context_token') or ''),
                    self._needs_reconnect)

    # ---------------------------------------------------------------- 登录

    def login(self, on_qr, on_status, ask_verify_code, should_abort=None):
        """执行扫码登录（只登录、不收消息）。回调均由调用方(UI 线程侧 worker)提供：
        on_qr(content) 渲染二维码；on_status(text) 更新状态；
        ask_verify_code(prompt)->str 索取手机数字配对码；
        should_abort()->bool 供 UI 提前取消。返回 {'ok': bool, 'error': str?}。"""
        _abort = should_abort or (lambda: False)
        deadline = time.time() + 480
        refresh_count = 1
        BM_LOG.info('[微信推送] 登录流程开始（整体最长等待 480s，二维码最多刷新 3 次）')
        while True:
            if _abort():
                BM_LOG.info('[微信推送] 登录被用户取消')
                return {'ok': False, 'error': '已取消'}
            if time.time() >= deadline:
                BM_LOG.warning('[微信推送] 登录等待超时（480s 内未完成扫码+确认）')
                return {'ok': False, 'error': '登录等待超时，请重试'}
            try:
                data = api.fetch_qrcode()
            except api.ILinkError as e:
                return {'ok': False, 'error': '获取二维码失败: %s' % api.redact(e)}
            qrcode = data.get('qrcode')
            if not qrcode:
                BM_LOG.error('[微信推送] 二维码响应缺少 qrcode，keys=%s' % sorted(data.keys()))
                return {'ok': False, 'error': '二维码响应缺少 qrcode'}
            content = data.get('qrcode_img_content') or qrcode
            BM_LOG.info('[微信推送] 第 %d 次申请二维码成功：扫码内容=%s 长度=%d'
                        % (refresh_count, 'URL' if str(content).startswith('http') else '文本',
                           len(str(content))))
            on_qr(content)
            on_status('等待扫码…' if refresh_count == 1
                      else '二维码已刷新（第 %d 张），请重新扫码…' % refresh_count)

            res = self._wait_confirmation(qrcode, deadline, on_status, ask_verify_code, _abort)
            BM_LOG.info('[微信推送] 本轮等待结束，结果字段=%s' % sorted(res.keys()))
            if res.get('cancelled'):
                return {'ok': False, 'error': '已取消'}
            if res.get('bot_token'):
                self._apply_login(res)
                return {'ok': True}
            if res.get('already_connected'):
                token = self._session_snapshot()[0]
                if token:
                    BM_LOG.info('[微信推送] 服务端提示已连接，复用本地 token')
                    return {'ok': True}
                # 本地无可复用 token → 刷新二维码
                BM_LOG.info('[微信推送] 服务端提示已连接，但本地没有可复用 token，重新申请二维码')
            elif res.get('login_error'):
                return {'ok': False, 'error': res['login_error']}

            refresh_count += 1
            if refresh_count > 3:
                BM_LOG.warning('[微信推送] 二维码已刷新 3 次仍未完成登录，放弃')
                return {'ok': False, 'error': '二维码多次失效或登录失败，请稍后重试'}

    def _wait_confirmation(self, qrcode, deadline, on_status, ask_verify_code, abort):
        current_base = None
        pending_verify = None
        scanned_printed = False
        while True:
            if abort():
                return {'cancelled': True}
            if time.time() >= deadline:
                return {'timeout': True}
            try:
                r = api.poll_status(qrcode, pending_verify, current_base)
            except api.ILinkError as e:
                BM_LOG.warning('[微信推送] 轮询扫码状态失败(%s)，1s 后重试: %s'
                               % (getattr(e, 'network_type', None) or '业务', api.redact(e)))
                time.sleep(1)
                continue
            if r:
                BM_LOG.info('[微信推送] 扫码状态归一化结果=%s' % sorted(r.keys()))
            for key in ('bot_token', 'login_error', 'already_connected', 'expired', 'verify_code_blocked'):
                if r.get(key):
                    return r
            if r.get('redirect_base'):
                current_base = r['redirect_base']
                BM_LOG.info('[微信推送] 扫码轮询切换节点: %s' % current_base)
                continue
            if r.get('scanned'):
                if pending_verify and r.get('verify_code_accepted'):
                    BM_LOG.info('[微信推送] 配对码已被服务端接受，继续等待确认')
                    pending_verify = None
                if not scanned_printed:
                    on_status('已扫码，等待手机端确认…')
                    scanned_printed = True
            if r.get('need_verifycode'):
                prompt = '数字不匹配，请重新输入：' if r.get('retry_verifycode') else '请输入手机微信显示的数字配对码：'
                BM_LOG.info('[微信推送] 需要手机数字配对码（第%s次索取）'
                            % ('二次' if r.get('retry_verifycode') else '一'))
                pending_verify = (ask_verify_code(prompt) or '').strip()
                BM_LOG.info('[微信推送] 用户输入配对码，长度=%d' % len(pending_verify))
                continue
            time.sleep(1)

    def _apply_login(self, res):
        with self._lock:
            old_id = self._state.get('ilink_bot_id')
            new_id = res.get('ilink_bot_id')
            account_changed = bool(new_id and old_id and old_id != new_id)
            self._state.update({
                'bot_token': res['bot_token'],
                'baseurl': res.get('baseurl') or api.BASE_URL,
                'ilink_bot_id': new_id,
                'ilink_user_id': res.get('ilink_user_id') or self._state.get('ilink_user_id', ''),
            })
            if account_changed:
                # 换账号：旧的会话游标与收件人 context_token 都不再适用
                self._state['get_updates_buf'] = ''
                self._state['recipient'] = {'to': '', 'context_token': ''}
            self._needs_reconnect = False
            self._needs_rebind = False
            self._last_reason = ''
            self._login_time = time.time()
            self._save_locked()
            base = self._state['baseurl']
        BM_LOG.info('[微信推送] 登录成功并已落盘：ilink_bot_id=%s baseurl=%s 换账号=%s'
                    % (new_id or '未返回', base, account_changed))
        if account_changed:
            BM_LOG.info('[微信推送] 检测到切换到新账号，已清空旧的会话游标与收件人绑定')

    # ------------------------------------------------------- 绑定唯一收件人

    def bind_recipient(self, timeout=BIND_TIMEOUT, on_status=None, should_abort=None):
        """临时收消息窗口：让对方给机器人发一条消息，最新一位发信人即绑定为唯一收件人；
        绑定成功后回推一条「连接成功」提示，然后立即结束收发（不驻留线程、不继续轮询）。
        on_status(text) 更新进度；should_abort()->bool 可提前取消。
        返回 {'ok': bool, 'to': str?, 'notice_sent': bool?, 'error': str?}
        （notice_sent=False 表示绑定已生效，只是「连接成功」那条回执没发出去）。"""
        _say = on_status or (lambda t: None)
        _abort = should_abort or (lambda: False)
        timeout = max(15, int(timeout))
        token, base, cursor, bot_id, stale = self._session_snapshot()
        if stale or not token:
            BM_LOG.warning('[微信推送] 未登录，无法绑定收件人')
            return {'ok': False, 'error': '未登录或登录已失效，请先扫码登录'}
        BM_LOG.info('[微信推送] 开始绑定唯一收件人，窗口 %d 秒' % timeout)
        api.notify_lifecycle('ilink/bot/msg/notifystart', token, base)
        deadline = time.time() + timeout
        _say('等待对方发消息（最长 %d 秒）' % timeout)
        backoff = 2
        try:
            while True:
                if _abort():
                    BM_LOG.info('[微信推送] 绑定被用户取消')
                    return {'ok': False, 'error': '已取消'}
                left = deadline - time.time()
                if left <= 0:
                    BM_LOG.warning('[微信推送] %d 秒内未收到对方消息，绑定超时' % timeout)
                    return {'ok': False, 'error': '绑定超时，没收到对方消息'}
                try:
                    r = api.get_updates(cursor, token, base)
                    backoff = 2
                except api.ILinkError as e:
                    if e.is_stale_token:
                        self._mark_reconnect()
                        return {'ok': False, 'error': '登录已失效(-14)，请重新扫码'}
                    BM_LOG.warning('[微信推送] 绑定轮询失败(%s)，%ds 后重试' % (e.network_type or '业务', backoff))
                    _say('网络不稳定，%d 秒后重试…' % backoff)
                    time.sleep(min(backoff, max(1, left)))
                    backoff = min(backoff * 2, 30)
                    continue
                if r.get('_timeout'):
                    continue
                new_cursor = r.get('get_updates_buf')
                if isinstance(new_cursor, str) and new_cursor and new_cursor != cursor:
                    cursor = new_cursor
                    self._save_cursor(cursor)
                fid, ct = self._pick_inbound(r.get('msgs') or [], bot_id)
                if not fid:
                    # 长轮询每次最多阻塞 LONG_POLL_TIMEOUT 秒；万一服务端立刻回空，稍等再问，别把接口打满
                    time.sleep(1)
                    continue
                self._set_recipient(fid, ct)
                _say('已绑定，正在发送连接成功提示…')
                notice_sent = self._confirm_bound(fid, ct, token, base)
                BM_LOG.info('[微信推送] 收件人绑定完成，连接成功提示=%s'
                            % ('已送达' if notice_sent else '未送达'))
                return {'ok': True, 'to': fid, 'notice_sent': notice_sent}
        finally:
            # 绑定窗口一结束就关掉服务端会话通知：之后只发不收，不做任何常驻请求
            api.notify_lifecycle('ilink/bot/msg/notifystop', token, base)

    @staticmethod
    def _pick_inbound(msgs, bot_id):
        """取本轮最新一条可用于主动推送的入站文本消息（from_user_id + context_token）。"""
        picked = ('', '')
        for m in msgs or []:
            if not isinstance(m, dict) or m.get('message_type') != 1:
                BM_LOG.debug('[微信推送] 跳过非文本入站消息 message_type=%r' % (m.get('message_type'),))
                continue
            fid = str(m.get('from_user_id') or '')
            ct = str(m.get('context_token') or '')
            if not fid or not ct:
                BM_LOG.warning('[微信推送] 入站消息缺少 from_user_id/context_token，无法用于主动推送')
                continue
            if bot_id and fid == bot_id:
                BM_LOG.debug('[微信推送] 跳过机器人自身发出的消息')
                continue
            picked = (fid, ct)
        return picked

    def _set_recipient(self, to, context_token):
        with self._lock:
            self._state['recipient'] = {'to': to, 'context_token': context_token}
            self._needs_rebind = False
            self._last_reason = ''
            self._save_locked()
        BM_LOG.info('[微信推送] 已绑定唯一收件人：%s' % api.redact(to))
        try:
            ConfigDatabase.update_item('wechat_push_to', to)
        except Exception as e:
            BM_LOG.warning('[微信推送] 同步 wechat_push_to 配置失败（不影响推送）: %s' % e)

    def _confirm_bound(self, to, context_token, token, base):
        """给对方回一条「连接成功」。best-effort：发送失败不影响绑定结果，
        只把结果返给调用方，让 UI 能说清「已绑定但回执没送达」。"""
        try:
            api.send_message(to, context_token, BIND_OK_TEXT, token, base)
            BM_LOG.info('[微信推送] 已回推连接成功提示 → %s' % api.redact(to))
            return True
        except api.ILinkError as e:
            if e.is_stale_token:
                self._mark_reconnect()
            BM_LOG.warning('[微信推送] 连接成功提示发送失败: %s' % api.redact(e))
            return False

    def _save_cursor(self, cursor):
        with self._lock:
            self._state['get_updates_buf'] = cursor
            self._save_locked()

    def logout(self):
        """断开连接：结束服务端会话并忘掉 bot_token、会话游标与收件人绑定，
        之后要再用就得重新扫码。除此之外运行期不做任何周期请求。"""
        token, base, _cursor, _bot, stale = self._session_snapshot()
        if token and not stale:
            api.notify_lifecycle('ilink/bot/msg/notifystop', token, base)
        with self._lock:
            self._state.update(_empty_state())
            self._needs_reconnect = False
            self._needs_rebind = False
            self._last_reason = ''
            self._login_time = 0.0
            self._save_locked()
        try:
            ConfigDatabase.update_item('wechat_push_to', '')
        except Exception as e:
            BM_LOG.warning('[微信推送] 清空 wechat_push_to 配置失败: %s' % e)
        BM_LOG.info('[微信推送] 已断开连接，本地登录态与收件人绑定均已清除')
        return True

    # ---------------------------------------------------------------- 推送

    def send(self, text):
        """向已绑定的唯一收件人主动推送一条文本。best-effort：
        未登录/未绑定/网络失败均返回 False（不抛），除这一次请求外不发任何东西。
        是否该推由调用方决定（定时任务按任务勾选）；这里只管「能不能发」。
        没发出去时，具体原因记在 last_skip_reason() 里供 UI 提示。"""
        token, base, to, ctx, stale = self._recipient_snapshot()
        if stale or not token:
            self._set_reason('未登录或登录已失效，请重新扫码')
            BM_LOG.warning('[微信推送] 未登录或需重新扫码，跳过推送')
            return False
        if not to or not ctx:
            self._set_reason('未绑定收件人，点「重新绑定」让对方发一条消息')
            BM_LOG.warning('[微信推送] 未绑定收件人，跳过推送')
            return False
        self._set_reason('')
        try:
            api.send_message(to, ctx, text, token, base)
            with self._lock:
                self._needs_rebind = False
            BM_LOG.info('[微信推送] 发送成功 → %s' % api.redact(to))
            return True
        except api.ILinkError as e:
            if e.is_stale_token:
                self._set_reason('登录已失效(-14)，请重新扫码')
                self._mark_reconnect()
            else:
                # context_token 过期没有专用错误码：只有服务端明确回了业务码才怀疑上下文失效，
                # 网络/超时（code 为 None）不动 rebind 状态；发送成功后该标志会自动清掉。
                rebind = e.code not in (None, 0)
                with self._lock:
                    self._needs_rebind = rebind
                self._set_reason('发送失败：%s%s' % (
                    api.redact(e), '，可点「重新绑定」' if rebind else ''))
                BM_LOG.error('[微信推送] 发送失败: %s' % api.redact(e))
            return False

    def last_skip_reason(self):
        """最近一次 send() 没发出去的原因（成功时为 ''）。"""
        with self._lock:
            return self._last_reason

    def push_task_result(self, task, status, code, msg, duration_ms):
        """定时任务执行结果推送（固定模板）。仅在任务勾选了推送且已绑定收件人时发出。"""
        text = _format_task_message(task, status, code, msg, duration_ms)
        return self.send(text)

    def _mark_reconnect(self):
        with self._lock:
            first = not self._needs_reconnect
            self._needs_reconnect = True
            self._state['bot_token'] = ''   # 失效：清 token，阻断后续 send，直到重新扫码
            self._save_locked()
        if first:
            BM_LOG.warning('[微信推送] token 已失效(-14)，需到推送页重新扫码')
            try:
                BmNotify().show_warning_notify('微信推送登录已失效，请到推送页重新扫码')
            except Exception:
                pass


def _format_task_message(task, status, code, msg, duration_ms):
    """固定模板（中）。status 来自 execute_script：success 之外一律按失败表述
    （重叠跳过的 'skipped' 只进执行历史、不推送，所以不在这里分支）。"""
    name = task.get('task_name', '未知任务') if isinstance(task, dict) else str(task)
    if status == 'success':
        st = '成功'
    else:
        st = '失败'
    if code is not None and status != 'success':
        st += ' (code=%s)' % code
    when = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    lines = [
        '[不忙脚本盒子] 定时任务通知',
        '任务：%s' % name,
        '状态：%s' % st,
        '时间：%s' % when,
        '耗时：%s ms' % (duration_ms if duration_ms is not None else '?'),
    ]
    detail = (str(msg).strip() if msg else '')
    if detail:
        lines.append('信息：%s' % detail)
    return '\n'.join(lines)
