"""
配置与数据持久化模块
管理监控列表、计数数据、应用设置的读写
"""

import json
import os
import sys
from datetime import date, datetime
from typing import Dict, Optional

# 数据文件路径（与 exe/脚本 同目录，方便管理）
if getattr(sys, "frozen", False):
    DATA_DIR = os.path.dirname(sys.executable)
else:
    DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(DATA_DIR, "app_counter_data.json")

# 开机自启文件夹
STARTUP_DIR = os.path.join(os.environ.get("APPDATA", ""),
                           r"Microsoft\Windows\Start Menu\Programs\Startup")
STARTUP_BAT = os.path.join(STARTUP_DIR, "AppCounter.bat")

# 默认监控的常见软件（进程名 -> 显示名）
DEFAULT_WATCHLIST: Dict[str, dict] = {
    "weixin.exe":     {"display_name": "微信",        "enabled": True, "is_default": True},
    "qq.exe":         {"display_name": "QQ",          "enabled": True, "is_default": True},
    "tim.exe":        {"display_name": "TIM",         "enabled": True, "is_default": True},
    "dingtalk.exe":   {"display_name": "钉钉",        "enabled": True, "is_default": True},
    "feishu.exe":     {"display_name": "飞书",        "enabled": True, "is_default": True},
    "wps.exe":        {"display_name": "WPS Office",  "enabled": True, "is_default": True},
    "winword.exe":    {"display_name": "Word",        "enabled": True, "is_default": True},
    "excel.exe":      {"display_name": "Excel",        "enabled": True, "is_default": True},
    "powerpnt.exe":   {"display_name": "PowerPoint",  "enabled": True, "is_default": True},
    "chrome.exe":     {"display_name": "Chrome 浏览器", "enabled": True, "is_default": True},
    "msedge.exe":     {"display_name": "Edge 浏览器",   "enabled": True, "is_default": True},
    "firefox.exe":    {"display_name": "Firefox 浏览器","enabled": True, "is_default": True},
    "notepad.exe":    {"display_name": "记事本",       "enabled": True, "is_default": True},
    "calc.exe":       {"display_name": "计算器",       "enabled": True, "is_default": True},
    "vscode.exe":     {"display_name": "VS Code",     "enabled": True, "is_default": True},
    "code.exe":       {"display_name": "VS Code (Insiders)", "enabled": False, "is_default": True},
    "explorer.exe":   {"display_name": "文件资源管理器", "enabled": False, "is_default": True},
    "telegram.exe":   {"display_name": "Telegram",    "enabled": True, "is_default": True},
    "discord.exe":    {"display_name": "Discord",     "enabled": True, "is_default": True},
    "steam.exe":      {"display_name": "Steam",       "enabled": True, "is_default": True},
}

DEFAULT_SETTINGS = {
    "start_with_windows": False,
    "minimize_to_tray": True,
    "poll_interval_ms": 100,
    "show_notifications": True,
}


class ConfigManager:
    """管理所有配置和计数的单例"""

    def __init__(self):
        self._data = self._load()

    # ---- 内部加载/保存 ----

    def _load(self) -> dict:
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # 合并新增的默认软件
                merged = self._merge_defaults(data)
                return merged
            except (json.JSONDecodeError, OSError):
                pass
        return self._default_data()

    def _default_data(self) -> dict:
        return {
            "watchlist": dict(DEFAULT_WATCHLIST),
            "counts": {},
            "settings": dict(DEFAULT_SETTINGS),
        }

    def _merge_defaults(self, data: dict) -> dict:
        """将新增的默认软件合并到已有配置中"""
        existing = data.get("watchlist", {})
        for proc, info in DEFAULT_WATCHLIST.items():
            if proc not in existing:
                existing[proc] = dict(info)
        data["watchlist"] = existing
        # 合并新增的设置项
        saved_settings = data.get("settings", {})
        for key, val in DEFAULT_SETTINGS.items():
            if key not in saved_settings:
                saved_settings[key] = val
        data["settings"] = saved_settings
        return data

    def save(self):
        """保存数据到磁盘"""
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            print(f"[ConfigManager] 保存失败: {e}")

    # ---- 监控列表 CRUD ----

    @property
    def watchlist(self) -> Dict[str, dict]:
        """返回 {proc_name: {display_name, enabled, is_default}}"""
        return self._data.setdefault("watchlist", {})

    def get_enabled_processes(self) -> Dict[str, str]:
        """返回已启用的 {proc_name: display_name}"""
        return {
            p: info["display_name"]
            for p, info in self.watchlist.items()
            if info.get("enabled", True)
        }

    def get_all_processes(self) -> list:
        """返回所有监控项列表，按显示名排序"""
        items = []
        for proc, info in self.watchlist.items():
            items.append({
                "process": proc,
                "display_name": info.get("display_name", proc),
                "enabled": info.get("enabled", True),
                "is_default": info.get("is_default", False),
                "exe_path": info.get("exe_path", ""),
            })
        items.sort(key=lambda x: (not x["enabled"], x["display_name"]))
        return items

    def get_exe_path(self, process_name: str) -> str:
        """获取应用的 exe 路径（用于启动）"""
        proc = process_name.strip().lower()
        return self.watchlist.get(proc, {}).get("exe_path", "")

    def set_exe_path(self, process_name: str, exe_path: str):
        """设置应用的 exe 路径"""
        proc = process_name.strip().lower()
        if proc in self.watchlist:
            self.watchlist[proc]["exe_path"] = exe_path
            self.save()

    def add_custom(self, process_name: str, display_name: str, exe_path: str = ""):
        """添加自定义软件"""
        proc = process_name.strip().lower()
        if not proc:
            return
        if not proc.endswith(".exe"):
            proc += ".exe"
        self.watchlist[proc] = {
            "display_name": display_name.strip() or process_name,
            "enabled": True,
            "is_default": False,
            "exe_path": exe_path,
        }
        self.save()

    def remove_custom(self, process_name: str):
        """删除自定义软件（只能删除非默认的）"""
        proc = process_name.strip().lower()
        if proc in self.watchlist and not self.watchlist[proc].get("is_default", False):
            del self.watchlist[proc]
            self.save()

    def toggle_enabled(self, process_name: str) -> bool:
        """切换启用/禁用状态，返回新状态"""
        proc = process_name.strip().lower()
        if proc in self.watchlist:
            current = self.watchlist[proc].get("enabled", True)
            self.watchlist[proc]["enabled"] = not current
            self.save()
            return not current
        return True

    def rename_display(self, process_name: str, new_name: str):
        """重命名显示名称"""
        proc = process_name.strip().lower()
        if proc in self.watchlist and new_name.strip():
            self.watchlist[proc]["display_name"] = new_name.strip()
            self.save()

    # ---- 计数 ----

    @property
    def counts(self) -> dict:
        return self._data.setdefault("counts", {})

    def record_launch(self, process_name: str):
        """记录一次使用（窗口被激活/切换到前台）"""
        today = date.today().isoformat()
        daily = self.counts.setdefault(today, {})
        daily[process_name] = daily.get(process_name, 0) + 1
        self.save()

    def get_today_counts(self) -> Dict[str, int]:
        """获取今日计数 {proc: count}"""
        today = date.today().isoformat()
        return dict(self.counts.get(today, {}))

    def get_history(self, days: int = 30) -> Dict[str, Dict[str, int]]:
        """获取最近 N 天的历史数据 {date_str: {proc: count}}"""
        from datetime import timedelta

        result = {}
        today = date.today()
        for i in range(days):
            d = (today - timedelta(days=i)).isoformat()
            if d in self.counts:
                result[d] = dict(self.counts[d])
        return result

    def get_total_counts(self) -> Dict[str, int]:
        """获取总计 {proc: total_count}"""
        totals: Dict[str, int] = {}
        for daily in self.counts.values():
            for proc, cnt in daily.items():
                totals[proc] = totals.get(proc, 0) + cnt
        # 按次数降序排列
        return dict(sorted(totals.items(), key=lambda x: x[1], reverse=True))

    def get_range_counts(self, start: str, end: str) -> Dict[str, int]:
        """获取日期范围内的总计 {proc: total}"""
        totals: Dict[str, int] = {}
        for day_str, daily in self.counts.items():
            if start <= day_str <= end:
                for proc, cnt in daily.items():
                    totals[proc] = totals.get(proc, 0) + cnt
        return dict(sorted(totals.items(), key=lambda x: x[1], reverse=True))

    def reset_today(self):
        """重置今日计数"""
        today = date.today().isoformat()
        if today in self.counts:
            del self.counts[today]
            self.save()

    def reset_all(self):
        """清除所有历史计数"""
        self._data["counts"] = {}
        self.save()

    # ---- 设置 ----

    @property
    def settings(self) -> dict:
        return self._data.setdefault("settings", {})

    def get_setting(self, key: str, default=None):
        return self.settings.get(key, default)

    def set_setting(self, key: str, value):
        self.settings[key] = value
        self.save()

    # ---- 开机自启 ----

    def get_startup_enabled(self) -> bool:
        """检查开机自启是否已启用"""
        return os.path.exists(STARTUP_BAT)

    def enable_startup(self, exe_path: str = ""):
        """启用开机自启：在启动文件夹创建批处理"""
        if not exe_path and getattr(sys, "frozen", False):
            exe_path = sys.executable
        elif not exe_path:
            # 源码运行时，指向 main.py
            script_dir = os.path.dirname(os.path.abspath(__file__))
            exe_path = os.path.join(script_dir, "main.py")
        try:
            os.makedirs(STARTUP_DIR, exist_ok=True)
            bat_content = (
                f'@echo off\r\n'
                f'start "" "{exe_path}" --console\r\n'
            )
            with open(STARTUP_BAT, "w", encoding="ascii") as f:
                f.write(bat_content)
            return True
        except OSError:
            return False

    def disable_startup(self):
        """禁用开机自启：删除启动文件夹的批处理"""
        try:
            if os.path.exists(STARTUP_BAT):
                os.remove(STARTUP_BAT)
            return True
        except OSError:
            return False
