"""
Copyright (c) 2026 綦恒智
Email: bmscriptsbox@163.com
SPDX-License-Identifier: MIT
SPDX-License-Identifier: LicenseRef-Commons-Clause

可本地化的业务异常基类。

约定：
- `code` 稳定（`域.模块.原因`），`params` 只放数据，不放拼好的句子；
- 英文模板写在 `ERROR_TEMPLATES`，中文译文按模板文本进 `zh_CN.ts`；
- UI 层直接 `str(exc)` 即可拿到当前语言文案，切换语言后重新取值也正确。

用法：
    raise BmError('install.archive.unsupported', suffix='.rar')
"""

ERROR_TEMPLATES = {
    'error.unknown': 'Something went wrong',
    'install.failed': 'Installation failed',
    'install.archive.unsupported': 'Unsupported archive type: %(suffix)s',
    'install.config.missing': 'The script package is missing its config file',
    'install.repo.download_failed': 'Failed to download the script repository, check the URL or network',
    'install.archive.illegal_path': 'Archive contains an unsafe path: %(name)s',
    'install.archive.too_many_entries': 'Archive has too many entries: %(count)s (limit %(limit)s)',
    'install.archive.too_large': 'Archive expands to %(size)s bytes, over the limit of %(limit)s',
    'install.archive.illegal_link': 'Archive contains an unsafe link: %(name)s -> %(target)s',
    'install.tool.missing': 'Extraction tool is missing: %(tool)s',
    'install.extract.failed': 'Failed to extract the package',
    'install.package.not_found': 'Package file not found: %(path)s',
    'install.package.not_zip': 'Invalid ZIP file: %(path)s',
    'install.package.corrupt_zip': 'Corrupted ZIP file: %(path)s',
    'install.config.multiple': 'Multiple config files found: %(file)s',
    'install.config.missing_package_json': 'Script package has no package.json in its root',
    'install.config.multiple_package_json': 'Multiple package.json files found in the package root',
    'install.config.missing_manifest': 'Required manifest file is missing: %(file)s',
    'install.config.invalid_json': 'Invalid JSON in %(file)s',
    'install.config.read_failed': 'Failed to read the script config',
    'env.python.venv_invalid': 'The Python environment is broken, please reinstall the script',
    'env.python.tk_missing': 'Tkinter source directory not found: %(path)s',
    'env.python.tk_patch_failed': 'Failed to patch Tkinter',
    'env.script.dir_missing': 'Script directory not found: %(path)s',
    'env.disk.low_space': 'Not enough disk space; keep at least 500 MB free',
    'env.task.failed': '%(task)s failed',
    'env.task.timeout': '%(task)s timed out after %(seconds)s s',
    'env.system.call_failed': 'Failed to call a system component',
    'env.pnpm.install_failed': 'PNPM installation failed (exit code %(code)s)',
    'env.node.no_runtime': 'No Node.js runtime matches %(spec)s',
    'env.pnpm.missing': 'PNPM is not available',
    'env.pnpm.timeout': 'Dependency installation timed out after %(seconds)s s',
    'env.ahk.missing': 'AutoHotkey executable not found: %(path)s',
    'env.package.no_matching_version': 'No package matches %(package)s %(requirement)s',
    'env.package.deploy_failed': 'Failed to deploy package %(package)s',
    'install.binary.confirm_unavailable': 'Cannot confirm the external binary %(name)s without a dialog',
    'install.binary.declined': 'Download of %(name)s was declined',
    'install.binary.silent_failed': 'Silent installation of %(name)s failed',
    'install.binary.exe_missing': 'Declared executable not found for %(name)s: %(missing)s',
    'install.binary.bin_required': '%(name)s is an installer and must declare bin',
    'install.binary.checksum_failed': 'Checksum mismatch for %(name)s',
    'install.binary.tampered': 'Content of %(name)s changed since the first record',
    'install.model.download_failed': 'Failed to download the model files, installation stopped',
    'install.dependency.cycle': 'Circular script dependency: %(script_id)s',
    'install.dependency.too_deep': 'Script dependency chain is too deep (limit %(limit)s)',
    'install.dependency.missing': 'Missing dependency script: %(script_id)s',
    'install.fs.init_failed': 'Failed to prepare the install directory: %(path)s',
    'download.url.empty': 'Download URL is empty',
    'download.url.no_filename': 'Cannot determine a file name from the URL: %(url)s',
    'download.result.missing': 'Download finished but the file is missing or empty: %(path)s',
    'config.path.relative': '%(field)s must be a relative path inside the script directory',
    'config.enum.invalid': '%(field)s must be one of %(allowed)s (got "%(value)s")',
    'config.binary.github_url': 'binaries.url must be a direct GitHub link (https://github.com/... or *.githubusercontent.com)',
    'config.binary.sha256': 'binaries.sha256 must be a 64-character hex string',
    'config.binary.reserved_name': '"%(name)s" is a reserved command name',
    'config.version.required': 'language_version is required when language is "%(language)s"',
    'config.version.invalid': 'Invalid language_version "%(version)s" (e.g. ">=3.8", "==3.10.1", ">=v16.0")',
    'config.match.mixed': 'inputs.match cannot mix plain fields with all/none',
    'config.match.unsupported_field': 'inputs.match (kind "%(kind)s") does not support: %(fields)s',
    'config.match.removed': 'inputs.match was removed; use [bmscriptsbox.triggers.search] instead',
    'config.match.value_array': 'Value of op "%(op)s" must be a list',
    'config.match.value_number': 'Value of op "%(op)s" must be a number',
    'config.match.length_range': 'inputs.match.min_length cannot exceed max_length',
    'config.match.regex_empty': 'inputs.match.regex cannot be empty',
    'config.match.regex_length': 'inputs.match.regex is too long (max %(limit)s)',
    'config.match.regex_invalid': 'Invalid inputs.match.regex: %(reason)s',
    'config.param.choice_labels': 'params.choice_labels has keys outside choices: %(keys)s',
    'config.param.when_type': 'params.when must be a table',
    'config.param.when_field': 'params.when must contain field (the parameter it depends on)',
    'config.param.when_unknown': 'Param "%(name)s" references unknown when.field "%(ref)s"',
    'config.param.choices_type': 'Param "%(name)s": choices only apply to str type (current: "%(type)s")',
    'config.search.target': 'triggers.search needs at least one input as its data target',
    'config.inputs.too_many': 'Only one input can be declared; use params with str type for extra files',
    'config.duplicate_param': 'Duplicate param name in params',
    'config.duplicate_dependency': 'Duplicate dependency id in dependencies',
    'config.dependency.self': 'A script cannot depend on itself',
    'config.outputs.required': 'Scripts that act as a node must declare at least one output',
    'script.not_found': 'Script not found or uninstalled: %(script_id)s',
    'script.busy': 'Script is already running: %(script_id)s',
    'script.language.unsupported': 'Unsupported language: %(language)s',
    'script.entry.missing': 'Entry file not found: %(entry)s',
    'script.launch.failed': 'Failed to start the script',
    'script.terminal.unsupported': 'Unsupported terminal mode: %(mode)s',
    'script.params.build_failed': 'Failed to build the parameter file',
    'menu.batch.missing': 'Batch file not found: %(path)s',
    'menu.config.invalid': 'Menu configuration is invalid (menuItems list is missing)',
    'menu.config.corrupted': 'BmContext.json is corrupted; writing was blocked to avoid overwriting it',
    'menu.config.write_failed': 'Failed to write the menu configuration',
    'menu.item.missing': 'Menu item not found: %(script_id)s',
    'menu.status.update_failed': 'Failed to update the menu item status',
    'menu.status.save_failed': 'Failed to update the menu item status: saving the configuration failed',
    'menu.sync.failed': 'Failed to sync the context menu',
    'menu.remove.failed': 'Failed to remove the script menu',
    'hotkey.empty': 'Shortcut cannot be empty',
    'hotkey.cjk_not_allowed': 'Shortcut cannot contain Chinese characters',
    'hotkey.invalid': 'Unrecognized shortcut: %(key)s',
    'explorer.window.unknown': 'Cannot determine the current Explorer window path',
    'explorer.window.not_found': 'Explorer window not found for path: %(path)s',
    'explorer.selection.too_many': 'Too many items selected (limit %(limit)s)',
    'wechat.net.timeout': 'The WeChat service timed out, please check your network',
    'wechat.net.error': 'Network error while contacting the WeChat service',
    'wechat.api.bad_response': 'Unexpected response from the WeChat service, please try again later',
    'wechat.api.error': 'The WeChat service returned an error, please try again later',
    'wechat.api.http_error': 'The WeChat service returned HTTP %(http)s',
    'update.check.failed': 'Failed to check for updates, please try again later',
    'update.parse.failed': 'Failed to parse the update information',
    'update.download.failed': 'Failed to download the update',
    'update.data.invalid': 'Update data is missing the version field',
    'update.banner.save_failed': 'Failed to save the update banner data',
    'remote.manifest.failed': 'Failed to fetch the remote manifest',
    'remote.filename.empty': 'File name cannot be empty',
}


def register_error(code: str, template: str) -> None:
    """登记错误码对应的英文模板（模板即 ts 的 source）。"""
    ERROR_TEMPLATES[code] = template


def localize(text: str) -> str:
    """按当前语言翻译模板；无 Qt 环境时回退原文。"""
    try:
        from xsideui import XI18N
    except Exception:
        return text
    try:
        return XI18N.x_tr(text)
    except Exception:
        return text


class BmError(ValueError):
    """带有稳定错误码与参数的异常，`str()` 返回本地化文案。"""

    code = 'error.unknown'

    def __init__(self, code: str = None, message: str = None, **params):
        self.code = code or self.code
        self.params = dict(params)
        self._fallback = message
        super().__init__(self.message)

    @property
    def template(self) -> str:
        return ERROR_TEMPLATES.get(self.code) or self._fallback or self.code

    @property
    def message(self) -> str:
        text = localize(self.template)
        if not self.params:
            return text
        try:
            return text % self.params
        except (KeyError, TypeError, ValueError):
            return text

    def __str__(self) -> str:
        return self.message

    def __repr__(self) -> str:
        return '%s(%r, %r)' % (type(self).__name__, self.code, self.params)
