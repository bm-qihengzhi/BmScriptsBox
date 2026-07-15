"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: AGPL-3.0
"""
import re
from dataclasses import dataclass
from typing import Optional, Any, Dict

from packaging.specifiers import SpecifierSet
from packaging.version import Version


@dataclass
class VersionMatchResult:
    """标准化版本匹配结果"""
    found: bool = False  # 是否找到匹配版本
    package_name: str = ""  # 包名
    version: Optional[str] = None  # 匹配到的版本号
    path: Optional[str] = None  # 本地安装路径 (仅本地匹配)
    payload: Optional[Dict] = None  # 额外数据，如云端架构信息 (仅云端匹配)
    error_message: Optional[str] = None  # 错误描述


class VersionMatcher:
    """软件包版本匹配工具类"""

    def _clean_version_string(self, version_str: str) -> str:
        """清洗版本号，处理 'v19.9.0' 为 '19.9.0'"""
        if not version_str:
            return ""
        # 去掉 v 前缀并处理空白
        return version_str.strip().lower().lstrip('v')

    def find_best_local_version(
            self,
            local_manifest: Dict[str, Any],
            package_name: str,
            version_requirement: str
    ) -> VersionMatchResult:
        """
        从本地清单中寻找最优版本
        策略：核心环境(Python/Node/AHK)执行系列锁定，非核心包执行全版本匹配
        """
        result = VersionMatchResult(package_name=package_name)

        # 1. 基础校验
        if package_name not in local_manifest:
            result.error_message = f"本地清单中未发现软件包: {package_name}"
            return result

        installed_versions = local_manifest[package_name].get('versions', {})
        pkg_lower = package_name.lower()

        # 统一清洗查询条件，用于非锁定模式的 SpecifierSet 匹配
        clean_query = version_requirement.replace('v', '').replace('V', '').strip()

        try:
            candidates = []  # 存放格式为 (Version对象, 原始版本字符串, info字典)

            # 正则：尝试抓取 >= 后的第一个数字 (Major) 和第二个数字 (Minor)
            # 例如: >=v19.9.0 -> group(1)=19, group(2)=9
            series_match = re.match(r'^>=(?i:v)?(\d+)(?:\.(\d+))?.*$', version_requirement.strip())

            # 标志位：是否触发了核心包的锁定逻辑
            core_strategy_triggered = False

            # --- 核心锁定策略区 ---

            # A. AutoHotkey 策略：锁定 Major (1.x 或 2.x)
            if series_match and pkg_lower == 'autohotkey':
                core_strategy_triggered = True
                target_major = int(series_match.group(1))
                for v_str, info in installed_versions.items():
                    try:
                        v_obj = Version(self._clean_version_string(v_str))
                        if v_obj.major == target_major:
                            candidates.append((v_obj, v_str, info))
                    except (ValueError, TypeError):
                        continue

            # B. Python / Tkinter 策略：锁定 Major.Minor (如 3.8 或 3.10)
            elif series_match and pkg_lower in ['python', 'tkinter']:
                core_strategy_triggered = True
                target_major = int(series_match.group(1))
                target_minor = int(series_match.group(2)) if series_match.group(2) else None

                # Python 必须锁定到 Minor 才有意义
                if target_minor is not None:
                    for v_str, info in installed_versions.items():
                        try:
                            v_obj = Version(self._clean_version_string(v_str))
                            if v_obj.major == target_major and v_obj.minor == target_minor:
                                candidates.append((v_obj, v_str, info))
                        except (ValueError, TypeError):
                            continue

            # C. Node.js 策略：锁定 Major (如 18.x 或 20.x)
            elif series_match and pkg_lower == 'node':
                core_strategy_triggered = True
                target_major = int(series_match.group(1))
                for v_str, info in installed_versions.items():
                    try:
                        v_obj = Version(self._clean_version_string(v_str))
                        if v_obj.major == target_major:
                            candidates.append((v_obj, v_str, info))
                    except (ValueError, TypeError):
                        continue

            # --- 核心拦截：如果满足锁定条件但该系列下无版本，直接报错 ---
            if core_strategy_triggered and not candidates:
                result.found = False
                result.error_message = f"锁定失败：本地未发现满足 {version_requirement} 系列的 {package_name} 环境"
                return result

            # --- 2. 通用匹配逻辑 (兜底逻辑：非核心包或非标准锁定格式) ---
            if not candidates:
                try:
                    spec = SpecifierSet(clean_query)
                    for v_str, info in installed_versions.items():
                        try:
                            # 注意：SpecifierSet 匹配建议也使用清洗后的版本号字符串
                            clean_v = self._clean_version_string(v_str)
                            if spec.contains(clean_v):
                                candidates.append((Version(clean_v), v_str, info))
                        except (ValueError, TypeError):
                            continue
                except Exception as e:
                    result.error_message = f"版本表达式解析失败: {e}"
                    return result

            # 3. 结果处理
            if candidates:
                # 按版本从高到低排序，取最新版
                candidates.sort(key=lambda x: x[0], reverse=True)
                best_v_obj, original_v_str, best_info = candidates[0]

                result.found = True
                result.version = original_v_str
                result.path = best_info.get('path')
            else:
                result.error_message = f"未找到满足 '{version_requirement}' 的有效版本"

        except Exception as e:
            result.error_message = f"匹配执行异常: {str(e)}"

        return result


    def fetch_best_cloud_version(
            self,
            cloud_manifest: Dict[str, Any],
            package_name: str,
            version_requirement: str
    ) -> VersionMatchResult:
        """
        从云端获取最优版本：同步差异化锁定策略。
        策略：针对 Python/Node/AHK 强制执行大版本锁定，防止越界下载。
        """
        result = VersionMatchResult(package_name=package_name)

        try:
            # 1. 提取云端版本库 (适配多种 JSON 响应结构)
            version_repo = cloud_manifest.get('version') or \
                           cloud_manifest.get(package_name, {}).get('version', {})

            if not version_repo:
                result.error_message = f"云端清单中未发现 {package_name} 的版本库"
                return result

            pkg_lower = package_name.lower()
            clean_query = version_requirement.replace('v', '').replace('V', '').strip()

            candidates = []
            # 通用正则：捕获 Major 和可选的 Minor
            series_match = re.match(r'^>=(?i:v)?(\d+)(?:\.(\d+))?.*$', version_requirement.strip())

            # 标志位：是否触发了核心环境的锁定策略
            core_strategy_triggered = False

            # --- 差异化锁定策略 (必须与本地匹配逻辑严格对齐) ---

            # A. AutoHotkey / Node.js 策略：锁定 Major (大版本锁定)
            if series_match and pkg_lower in ['autohotkey', 'node']:
                core_strategy_triggered = True
                target_major = int(series_match.group(1))
                for v_str, details in version_repo.items():
                    try:
                        v_obj = Version(self._clean_version_string(v_str))
                        if v_obj.major == target_major:
                            candidates.append((v_obj, v_str, details))
                    except (ValueError, TypeError):
                        continue

            # B. Python / Tkinter 策略：锁定 Major.Minor (前两位锁定)
            elif series_match and pkg_lower in ['python', 'tkinter']:
                core_strategy_triggered = True
                target_major = int(series_match.group(1))
                target_minor = int(series_match.group(2)) if series_match.group(2) else None

                if target_minor is not None:
                    for v_str, details in version_repo.items():
                        try:
                            v_obj = Version(self._clean_version_string(v_str))
                            if v_obj.major == target_major and v_obj.minor == target_minor:
                                candidates.append((v_obj, v_str, details))
                        except (ValueError, TypeError):
                            continue

            # --- 核心拦截：如果是核心包锁定逻辑且没找到该系列，则不准向下执行通用匹配 ---
            if core_strategy_triggered and not candidates:
                result.found = False
                result.error_message = f"云端锁定失败：未发现满足该大版本系列的 {package_name} 下载资源"
                return result

            # --- C. 通用匹配模式 (非核心包或非标准锁定查询) ---
            if not candidates:
                try:
                    spec = SpecifierSet(clean_query)
                    for v_str, details in version_repo.items():
                        try:
                            clean_v = self._clean_version_string(v_str)
                            if spec.contains(clean_v):
                                candidates.append((Version(clean_v), v_str, details))
                        except (ValueError, TypeError):
                            continue
                except Exception as e:
                    result.error_message = f"云端版本表达式解析错误: {e}"
                    return result

            # 3. 排序并提取最优解 (取该系列下的最高版本)
            if candidates:
                # 按版本号对象排序 (1.10.0 > 1.9.0)
                candidates.sort(key=lambda x: x[0], reverse=True)
                best_v_obj, best_v_str, best_details = candidates[0]

                result.found = True
                result.version = best_v_str
                # payload 通常存放 architecture 映射，包含不同系统的下载 URL
                result.payload = best_details.get('architecture')
            else:
                result.error_message = f"云端未找到满足 '{version_requirement}' 的有效版本"

        except Exception as e:
            result.error_message = f"云端匹配过程发生异常: {str(e)}"

        return result

