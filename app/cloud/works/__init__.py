"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
from .auth_work import LoginStatusWork, UserInfoWork, UpdateTokenWork, QrcodeWork, LoginByPwdWork
from .market_work import MarketScriptsWork, ClassifyWork, AddDownloadWork
from .publish_work import PublishScriptWork, MyScriptsWork, UnpublishScriptWork, ClassifyLoadWork, DeleteScriptWork
from .update_work import BannerUpdateWork, CheckUpdateWork, UpdateDownLoadTask, GetScriptsVersionWork, UpdateScriptsWork

__all__ = [
    "LoginStatusWork",
    "UserInfoWork",
    "UpdateTokenWork",
    "QrcodeWork",
    "LoginByPwdWork",
    "MarketScriptsWork",
    "ClassifyWork",
    "PublishScriptWork",
    "MyScriptsWork",
    "UnpublishScriptWork",
    "ClassifyLoadWork",
    "DeleteScriptWork",
    "BannerUpdateWork",
    "CheckUpdateWork",
    "UpdateDownLoadTask",
    "GetScriptsVersionWork",
    "UpdateScriptsWork",
    'AddDownloadWork',
]
