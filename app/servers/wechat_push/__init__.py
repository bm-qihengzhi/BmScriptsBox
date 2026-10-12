"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

微信推送子包：iLink(ClawBot) 同步客户端 + 单例服务。
"""
from .service import WechatPushService, _format_task_message

__all__ = ['WechatPushService', '_format_task_message']
