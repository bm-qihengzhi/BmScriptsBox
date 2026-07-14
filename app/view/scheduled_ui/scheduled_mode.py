"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
from enum import Enum


class TimeMode(Enum):
    FIXED_INTERVAL = "固定间隔执行"
    RANDOM_INTERVAL = "随机间隔执行"
    COUNTDOWN = "倒计时执行"
    DAILY = "每天执行"
    WEEKLY = "每周执行"


class WeekMode(Enum):
    MONDAY = "周一"
    TUESDAY = "周二"
    WEDNESDAY = "周三"
    THURSDAY = "周四"
    FRIDAY = "周五"
    SATURDAY = "周六"
    SUNDAY = "周日"