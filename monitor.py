"""
进程监控引擎（窗口焦点检测模式）
通过检测前台窗口切换来判断用户是否在使用某个应用。
每次用户切换窗口焦点到目标应用时，计数 +1。

原理：轮询 GetForegroundWindow()，检测前台窗口所属进程是否变化。
"""

import ctypes
import ctypes.wintypes
import time
import threading
from typing import Callable, Dict, Optional

import psutil

from config import ConfigManager

# 同一应用两次计数之间的最短间隔（秒）
# 设为 0 表示每次焦点切换到目标应用都计数
DEBOUNCE_SECONDS = 0.0

# 默认轮询间隔（秒），运行时可通过 config.settings["poll_interval_ms"] 调整
DEFAULT_POLL_INTERVAL = 0.5

# ---- Win32 API ----

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# DWORD GetWindowThreadProcessId(HWND hWnd, LPDWORD lpdwProcessId);
user32.GetWindowThreadProcessId.argtypes = [ctypes.wintypes.HWND, ctypes.POINTER(ctypes.wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = ctypes.wintypes.DWORD

# HWND GetForegroundWindow();
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = ctypes.wintypes.HWND

# BOOL SetForegroundWindow(HWND hWnd);
user32.SetForegroundWindow.argtypes = [ctypes.wintypes.HWND]
user32.SetForegroundWindow.restype = ctypes.wintypes.BOOL

# BOOL IsWindowVisible(HWND hWnd);
user32.IsWindowVisible.argtypes = [ctypes.wintypes.HWND]
user32.IsWindowVisible.restype = ctypes.wintypes.BOOL

# BOOL ShowWindow(HWND hWnd, int nCmdShow);
user32.ShowWindow.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = ctypes.wintypes.BOOL

# BOOL EnumWindows(WNDENUMPROC lpEnumFunc, LPARAM lParam);
WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, ctypes.wintypes.LPARAM]
user32.EnumWindows.restype = ctypes.wintypes.BOOL

# BOOL AllowSetForegroundWindow(DWORD dwProcessId);
user32.AllowSetForegroundWindow.argtypes = [ctypes.wintypes.DWORD]
user32.AllowSetForegroundWindow.restype = ctypes.wintypes.BOOL


def get_foreground_process_name() -> Optional[str]:
    """获取当前前台窗口所属的进程名（小写），失败返回 None"""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    pid = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return None
    try:
        proc = psutil.Process(pid.value)
        return (proc.name() or "").lower()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


class ProcessMonitor:
    """监控前台窗口切换，记录应用使用次数"""

    def __init__(self, config: ConfigManager):
        self._config = config
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_foreground_proc: Optional[str] = None   # 上一次的前台进程名
        self._last_count_time: Dict[str, float] = {}        # proc_name -> 上次计数的时间戳
        self._lock = threading.Lock()
        self._on_launch_callbacks: list[Callable[[str, str], None]] = []

    # ---- 回调机制 ----

    def add_callback(self, cb: Callable[[str, str], None]):
        """注册回调：cb(process_name, display_name) 在检测到使用时调用"""
        self._on_launch_callbacks.append(cb)

    def remove_callback(self, cb: Callable[[str, str], None]):
        if cb in self._on_launch_callbacks:
            self._on_launch_callbacks.remove(cb)

    def _fire_callbacks(self, proc_name: str, display_name: str):
        for cb in self._on_launch_callbacks:
            try:
                cb(proc_name, display_name)
            except Exception as e:
                print(f"[ProcessMonitor] 回调异常: {e}")

    # ---- 核心检测 ----

    def _scan(self):
        """检测前台窗口是否切换到了目标应用"""
        proc_name = get_foreground_process_name()
        if proc_name is None:
            return

        # 只有进程名变化时才处理
        if proc_name == self._last_foreground_proc:
            return
        self._last_foreground_proc = proc_name

        # 检查是否在监控列表中
        enabled = self._config.get_enabled_processes()
        if proc_name not in enabled:
            return

        display_name = enabled[proc_name]
        now = time.time()

        with self._lock:
            # 防抖：同一应用短时间内不重复计数
            last_time = self._last_count_time.get(proc_name, 0)
            if now - last_time < DEBOUNCE_SECONDS:
                return

            self._config.record_launch(proc_name)
            self._last_count_time[proc_name] = now

        self._fire_callbacks(proc_name, display_name)

    def _run_loop(self):
        """后台监控循环"""
        # 初始化：记录当前前台进程（避免启动时误计数）
        self._last_foreground_proc = get_foreground_process_name()
        while self._running:
            try:
                self._scan()
            except Exception as e:
                print(f"[ProcessMonitor] 扫描异常: {e}")
            # 动态读取轮询间隔（毫秒），最小 100ms
            interval_ms = max(100, self._config.get_setting("poll_interval_ms", 500))
            time.sleep(interval_ms / 1000.0)

    # ---- 公开接口 ----

    def start(self):
        """启动监控"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="ProcessMonitor")
        self._thread.start()

    def stop(self):
        """停止监控"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)

    @property
    def is_running(self) -> bool:
        return self._running

    def refresh_baseline(self):
        """重置当前前台进程基线（添加/移除监控目标后调用）"""
        self._last_foreground_proc = get_foreground_process_name()
        # 清空防抖计时器
        with self._lock:
            self._last_count_time.clear()

    # ---- 启动/聚焦 ----

    @staticmethod
    def focus_or_launch(proc_name: str, exe_path: str = "") -> bool:
        """
        如果进程已运行，将其主窗口拉到前台；否则启动它。
        返回 True 表示成功聚焦或启动了。
        """
        import subprocess

        proc_lower = proc_name.strip().lower()

        # 1. 查找是否已经在运行
        running_pids = []
        try:
            for p in psutil.process_iter(["name", "pid"]):
                try:
                    if (p.info["name"] or "").lower() == proc_lower:
                        running_pids.append(p.info["pid"])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass

        if running_pids:
            pid_set = set(running_pids)
            # 枚举窗口找到属于这些 PID 的可见窗口
            result_hwnd = []

            def enum_callback(hwnd, _lparam):
                pid = ctypes.wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value in pid_set and user32.IsWindowVisible(hwnd):
                    result_hwnd.append(hwnd)
                    return False  # 找到，停止枚举
                return True

            user32.EnumWindows(WNDENUMPROC(enum_callback), 0)

            if result_hwnd:
                hwnd = result_hwnd[0]
                # 允许设置前台窗口
                pid = ctypes.wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                user32.AllowSetForegroundWindow(pid.value)
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                user32.SetForegroundWindow(hwnd)
                return True
            # 有进程但无可见窗口，也算已运行
            return True

        # 2. 没有运行 → 尝试启动
        launch_path = exe_path
        if not launch_path:
            import shutil
            found = shutil.which(proc_lower)
            if found:
                launch_path = found

        if launch_path and os.path.exists(launch_path):
            try:
                subprocess.Popen([launch_path], shell=True)
                return True
            except Exception:
                pass

        return False
