"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

微信 iLink(ClawBot) 推送的同步 HTTP 客户端（嵌入式 Python 3.8 兼容）。
从 demo `微信clawbot推送-python/bot.py`(需 3.10+、asyncio) 提炼并改写为 requests 同步实现，
仅保留登录、轮询、收消息、发送、生命周期通知所需的最小端点。运行期不依赖 demo 文件。
"""
import base64
import json
import re
import secrets
import time
from urllib.parse import quote

import requests

from app.utils import BM_LOG

BASE_URL = "https://ilinkai.weixin.qq.com"
CHANNEL_VERSION = "2.4.6"
ILINK_APP_ID = "bot"
ILINK_APP_CLIENT_VERSION = str((2 << 16) | (4 << 8) | 6)
BOT_AGENT = "weixin-ClawBot-API/1.2.0 (python)"

# 超时（秒）：二维码状态/getupdates 是服务端挂起的长轮询。
# 客户端等待时间就是「手机端状态变化 → 电脑端感知」的最大延迟，所以刻意取短值：
# 到点就重新问一次，游标/二维码参数不变，不会漏消息，只是多问几次。
QR_STATUS_TIMEOUT = 5
LONG_POLL_TIMEOUT = 10
API_TIMEOUT = 15
CONFIG_TIMEOUT = 10
# 推送走的 sendmessage：定时任务的工作线程里同步等它，取短值，别把调度拖住
PUSH_TIMEOUT = 8

# 日志脱敏：避免把 token/二维码/上下文凭据写进 BM_LOG
_REDACT_KEYS = ('bot_token', 'token', 'context_token', 'typing_ticket', 'qrcode',
                'qrcode_img_content', 'verify_code', 'aeskey', 'aes_key', 'encrypt_query_param',
                'get_updates_buf')
_REDACT_JSON = re.compile(
    r'(?i)("(?:' + '|'.join(_REDACT_KEYS) + r')"\s*:\s*")([^"]*)(")')
_REDACT_URL = re.compile(
    r'(?i)((?:' + '|'.join(_REDACT_KEYS) + r')=)([^&\s,"}]+)')


def redact(value):
    """把敏感字段值替换成 ***，用于日志。"""
    text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value or '')
    text = _REDACT_JSON.sub(r'\1***\3', text)
    text = _REDACT_URL.sub(r'\1***', text)
    return text[:500]


def summary(data):
    """可安全写进日志的响应摘要：业务码 + 状态字符串 + 字段名（凭据值一律不出现在日志里）。"""
    if not isinstance(data, dict):
        return redact(data)
    parts = ['%s=%r' % (k, data[k]) for k in ('ret', 'errcode', 'status', 'errmsg') if k in data]
    parts.append('keys=%s' % sorted(data.keys()))
    return ' '.join(parts)


class ILinkError(Exception):
    """iLink HTTP、JSON 或业务层错误。"""

    def __init__(self, message, path='', status=None, ret=None, errcode=None,
                 response=None, network_type=None):
        super().__init__(message)
        self.path = path
        self.status = status
        self.ret = ret
        self.errcode = errcode
        self.response = response or {}
        self.network_type = network_type

    @property
    def code(self):
        return self.ret if self.ret not in (None, 0) else self.errcode

    @property
    def is_stale_token(self):
        return self.code == -14


def _common_headers():
    return {
        'iLink-App-Id': ILINK_APP_ID,
        'iLink-App-ClientVersion': ILINK_APP_CLIENT_VERSION,
    }


def _headers(token=None):
    h = {
        'Content-Type': 'application/json',
        'AuthorizationType': 'ilink_bot_token',
        'X-WECHAT-UIN': base64.b64encode(str(secrets.randbits(32)).encode()).decode(),
    }
    h.update(_common_headers())
    if token and str(token).strip():
        h['Authorization'] = 'Bearer %s' % str(token).strip()
    return h


def base_info():
    return {'channel_version': CHANNEL_VERSION, 'bot_agent': BOT_AGENT}


def _client_id():
    return 'openclaw-weixin:%d-%s' % (int(time.time() * 1000), secrets.token_hex(4))


def _url(base_url, path):
    return '%s/%s' % ((base_url or BASE_URL).rstrip('/'), path.lstrip('/'))


def _parse_json(text, path, status):
    try:
        data = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise ILinkError('%s 返回非 JSON: %s' % (path, exc), path=path, status=status)
    if not isinstance(data, dict):
        raise ILinkError('%s 返回类型错误: %s' % (path, type(data).__name__), path=path, status=status)
    return data


def ensure_business_success(data, path):
    """检查 ret/errcode；缺省按官方客户端兼容规则视为成功。"""
    ret = data.get('ret')
    errcode = data.get('errcode')
    if ret not in (None, 0) or errcode not in (None, 0):
        BM_LOG.warning('[微信推送][业务] %s 失败 ret=%r errcode=%r errmsg=%r'
                       % (path, ret, errcode, data.get('errmsg')))
        raise ILinkError(
            '%s ret=%r errcode=%r: %s' % (path, ret, errcode, data.get('errmsg') or 'iLink 业务请求失败'),
            path=path, ret=ret, errcode=errcode, response=data)
    return data


def _raise_for_status(data, method, path, status):
    if 200 <= status < 300:
        return
    raise ILinkError(
        '%s %s HTTP %s: %s' % (method, path, status, data.get('errmsg', '')),
        path=path, status=status, ret=data.get('ret'), errcode=data.get('errcode'), response=data)


def _post(path, body, token=None, base_url=None, timeout=API_TIMEOUT, long_poll=False,
          fallback_cursor=''):
    safe_path = redact(path)
    BM_LOG.info('[微信推送][HTTP] -> POST %s (登录态=%s, 超时=%s)'
                % (safe_path, '有' if token else '无', timeout))
    try:
        resp = requests.post(_url(base_url, path), json=body, headers=_headers(token), timeout=timeout)
    except requests.Timeout:
        if long_poll:
            BM_LOG.info('[微信推送][HTTP] <- POST %s 长轮询超时，按空轮处理' % safe_path)
            return {'ret': 0, 'msgs': [], 'get_updates_buf': fallback_cursor, '_timeout': True}
        BM_LOG.warning('[微信推送][HTTP] !! POST %s 超时' % safe_path)
        raise ILinkError('POST %s 超时' % path, path=path, network_type='timeout')
    except (requests.RequestException, OSError) as exc:
        BM_LOG.warning('[微信推送][HTTP] !! POST %s 网络错误: %s' % (safe_path, exc))
        raise ILinkError('POST %s 网络错误: %s' % (path, exc), path=path, network_type='network')
    data = _parse_json(resp.text, path, resp.status_code)
    BM_LOG.info('[微信推送][HTTP] <- POST %s HTTP %s %s' % (safe_path, resp.status_code, summary(data)))
    BM_LOG.debug('[微信推送][HTTP]    POST %s 响应体=%s' % (safe_path, redact(data)))
    _raise_for_status(data, 'POST', path, resp.status_code)
    return data


def _get(path, token=None, base_url=None, timeout=QR_STATUS_TIMEOUT, long_poll=False):
    # 2.4.6 二维码状态 GET 仅带公共应用头，不带 Bearer
    safe_path = redact(path)
    BM_LOG.info('[微信推送][HTTP] -> GET %s (超时=%s)' % (safe_path, timeout))
    try:
        resp = requests.get(_url(base_url, path), headers=_common_headers(), timeout=timeout)
    except requests.Timeout:
        if long_poll:
            BM_LOG.info('[微信推送][HTTP] <- GET %s 长轮询超时，按 wait 处理' % safe_path)
            return {'status': 'wait', '_timeout': True}
        BM_LOG.warning('[微信推送][HTTP] !! GET %s 超时' % safe_path)
        raise ILinkError('GET %s 超时' % path, path=path, network_type='timeout')
    except (requests.RequestException, OSError) as exc:
        BM_LOG.warning('[微信推送][HTTP] !! GET %s 网络错误: %s' % (safe_path, exc))
        raise ILinkError('GET %s 网络错误: %s' % (path, exc), path=path, network_type='network')
    data = _parse_json(resp.text, path, resp.status_code)
    BM_LOG.info('[微信推送][HTTP] <- GET %s HTTP %s %s' % (safe_path, resp.status_code, summary(data)))
    BM_LOG.debug('[微信推送][HTTP]    GET %s 响应体=%s' % (safe_path, redact(data)))
    _raise_for_status(data, 'GET', path, resp.status_code)
    return data


# --------------------------------------------------------------------- 端点

def fetch_qrcode(local_token_list=None):
    """申请登录二维码：POST get_bot_qrcode?bot_type=3 → {qrcode, qrcode_img_content}。"""
    tokens = []
    for t in (local_token_list or []):
        t = str(t or '').strip()
        if t and t not in tokens:
            tokens.append(t)
    return ensure_business_success(
        _post('ilink/bot/get_bot_qrcode?bot_type=3', {'local_token_list': tokens[:10]},
              None, BASE_URL, timeout=API_TIMEOUT),
        'get_bot_qrcode')


def poll_status(qrcode, verify_code=None, base_url=None, timeout=QR_STATUS_TIMEOUT):
    """轮询扫码状态，归一化为 dict。超时视为 wait。"""
    endpoint = 'ilink/bot/get_qrcode_status?qrcode=%s' % quote(qrcode, safe='')
    if verify_code:
        endpoint += '&verify_code=%s' % quote(verify_code, safe='')
    status = _get(endpoint, None, base_url or BASE_URL, timeout=timeout, long_poll=True)
    if status.get('_timeout'):
        return {'status': 'wait'}
    ensure_business_success(status, 'get_qrcode_status')
    state = status.get('status', '')
    BM_LOG.info('[微信推送] 扫码状态原始值=%r（服务端未返回 status 时看 keys）' % state)

    if state == 'confirmed' or status.get('bot_token'):
        bot_token = status.get('bot_token')
        ilink_bot_id = status.get('ilink_bot_id')
        if not bot_token or not ilink_bot_id:
            BM_LOG.error('[微信推送] confirmed 但凭据不全：bot_token=%s ilink_bot_id=%s'
                         % ('有' if bot_token else '缺失', ilink_bot_id or '缺失'))
            return {'login_error': 'confirmed 响应缺少 bot_token 或 ilink_bot_id'}
        BM_LOG.info('[微信推送] 登录确认成功：ilink_bot_id=%s ilink_user_id=%s baseurl=%s'
                    % (ilink_bot_id, status.get('ilink_user_id', ''),
                       status.get('baseurl') or status.get('base_url') or base_url or BASE_URL))
        return {
            'bot_token': bot_token,
            'baseurl': status.get('baseurl') or status.get('base_url') or base_url or BASE_URL,
            'ilink_bot_id': ilink_bot_id,
            'ilink_user_id': status.get('ilink_user_id', ''),
        }
    if state == 'binded_redirect' or status.get('binded_redirect'):
        return {'already_connected': True}
    if state == 'expired':
        return {'expired': True}
    if state == 'scaned_but_redirect':
        host = status.get('redirect_host')
        if host:
            base = str(host)
            if not base.startswith('http'):
                base = 'https://' + base
            return {'redirect_base': base.rstrip('/')}
        return {}
    if state == 'scaned':
        return {'scanned': True, 'verify_code_accepted': bool(verify_code)}
    if state in ('need_verifycode', 'verify_code_blocked') or status.get('need_verifycode'):
        if state == 'verify_code_blocked':
            return {'verify_code_blocked': True}
        return {'need_verifycode': True, 'retry_verifycode': bool(verify_code)}
    BM_LOG.warning('[微信推送] 收到未识别的扫码状态 %r，已忽略（继续轮询直到超时）；'
                   '如是新状态值，需要在 poll_status 里补分支' % (state,))
    return {}


def get_updates(cursor, token, base_url=None, timeout=LONG_POLL_TIMEOUT):
    """长轮询收消息：返回 {msgs, get_updates_buf, ...}；超时返回空轮。"""
    result = _post('ilink/bot/getupdates', {'get_updates_buf': cursor or '', 'base_info': base_info()},
                   token, base_url, timeout=timeout, long_poll=True, fallback_cursor=cursor or '')
    if not result.get('_timeout'):
        ensure_business_success(result, 'getupdates')
        msgs = result.get('msgs') or []
        new_cursor = result.get('get_updates_buf')
        BM_LOG.info('[微信推送] getupdates 收到 %d 条消息，游标%s'
                    % (len(msgs), '有更新' if new_cursor and new_cursor != cursor else '未变'))
        for i, m in enumerate(msgs):
            if isinstance(m, dict):
                BM_LOG.info('[微信推送]   消息[%d] message_type=%r from_user_id=%s 有context_token=%s'
                            % (i, m.get('message_type'), m.get('from_user_id'),
                               bool(m.get('context_token'))))
    return result


def send_message(to_id, context_token, text, token, base_url=None):
    """主动推送一条文本消息；业务失败(含 -14)抛 ILinkError，成功返回响应 dict。"""
    BM_LOG.info('[微信推送] 准备发送 → to=%s 文本长度=%d 有context_token=%s'
                % (redact(to_id), len(text or ''), bool(context_token)))
    payload = {
        'msg': {
            'from_user_id': '',
            'to_user_id': to_id,
            'client_id': _client_id(),
            'message_type': 2,
            'message_state': 2,
            'context_token': context_token,
            'item_list': [{'type': 1, 'text_item': {'text': text}}],
        },
        'base_info': base_info(),
    }
    return ensure_business_success(
        _post('ilink/bot/sendmessage', payload, token, base_url, timeout=PUSH_TIMEOUT),
        'sendmessage')


def notify_lifecycle(endpoint, token, base_url=None):
    """notifystart / notifystop 生命周期通知，best-effort。"""
    try:
        result = ensure_business_success(
            _post(endpoint, {'base_info': base_info()}, token, base_url, timeout=CONFIG_TIMEOUT),
            endpoint)
        BM_LOG.info('[微信推送] 生命周期通知 %s 已发送' % endpoint)
        return result
    except ILinkError as e:
        BM_LOG.warning('[微信推送] 生命周期通知 %s 失败（不影响收发）: %s' % (endpoint, redact(e)))
        return None
