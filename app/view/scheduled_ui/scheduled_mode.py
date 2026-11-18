"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause
"""
from enum import Enum


class TimeMode(Enum):
    FIXED_INTERVAL = "固定间隔执行"
    COUNTDOWN = "倒计时执行"
    DAILY = "每天执行"
    WEEKLY = "每周执行"
    MONTHLY = "每月执行"


WEEKDAY_LABELS = {
    "周一": "Monday", "周二": "Tuesday", "周三": "Wednesday",
    "周四": "Thursday", "周五": "Friday", "周六": "Saturday",
    "周日": "Sunday",
}


def weekday_label(value):
    """存储值是中文周几，展示时转为当前语言。"""
    from xsideui import XI18N
    key = str(value or "")
    return XI18N.x_tr(WEEKDAY_LABELS.get(key, key))


class WeekMode(Enum):
    MONDAY = "周一"
    TUESDAY = "周二"
    WEDNESDAY = "周三"
    THURSDAY = "周四"
    FRIDAY = "周五"
    SATURDAY = "周六"
    SUNDAY = "周日"