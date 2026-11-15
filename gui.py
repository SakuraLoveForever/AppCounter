"""
GUI 界面模块
基于 tkinter 的主窗口 + 系统托盘图标
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, simpledialog, filedialog, font
from datetime import date, timedelta
from typing import Optional

from config import ConfigManager, DATA_FILE
from monitor import ProcessMonitor

# ---- 常量 ----
APP_TITLE = "AppCounter - 应用使用统计"
APP_ICON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
FONT_FAMILY = "Microsoft YaHei UI"
FONT_SIZE = 10
FONT_SIZE_SMALL = 9

COLOR_BG = "#141820"
COLOR_CARD_BG = "#1d2430"
COLOR_BORDER = "#303a4b"
COLOR_BUTTON = "#273140"
COLOR_HOVER = "#354259"
COLOR_SELECTED = "#2a4162"
COLOR_PRIMARY = "#a4c6ff"
COLOR_SUCCESS = "#91d6b2"
COLOR_DANGER = "#ffb0b8"
COLOR_TEXT = "#edf1f7"
COLOR_TEXT_SECONDARY = "#a6b2c5"

# 月份中文名
_MONTH_NAMES = ["一月", "二月", "三月", "四月", "五月", "六月",
                "七月", "八月", "九月", "十月", "十一月", "十二月"]
_WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]


def _dark_titlebar(window):
    """在支持的 Windows 版本上设置深色标题栏。"""
    import ctypes
    from ctypes import wintypes

    window.update_idletasks()
    hwnd = wintypes.HWND(int(window.tk.call("wm", "frame", str(window)), 16))
    enabled = wintypes.BOOL(True)
    try:
        set_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
        if set_attribute(hwnd, 20, ctypes.byref(enabled), ctypes.sizeof(enabled)) != 0:
            set_attribute(hwnd, 19, ctypes.byref(enabled), ctypes.sizeof(enabled))
    except (AttributeError, OSError):
        pass


class DarkDialog(simpledialog.Dialog):
    """应用内提示、确认和重命名，共用 Tk 的模态窗口行为。"""

    def __init__(self, parent, title, message, *, confirm=False, initial=None):
        self.message = message
        self.confirm = confirm
        self.initial = initial
        previous_grab = parent.grab_current()
        try:
            super().__init__(parent, title)
        finally:
            if previous_grab is not None and previous_grab.winfo_exists():
                previous_grab.grab_set()

    def body(self, master):
        self.configure(bg=COLOR_BG)
        master.configure(bg=COLOR_BG, padx=10, pady=6)
        self.resizable(False, False)
        self.bind("<Map>", lambda event: _dark_titlebar(self) if event.widget == self else None)
        ttk.Label(master, text=self.message, wraplength=340, justify="left").pack(anchor="w")
        if self.initial is not None:
            self.entry = ttk.Entry(master, width=32)
            self.entry.insert(0, self.initial)
            self.entry.selection_range(0, tk.END)
            self.entry.pack(fill=tk.X, pady=(6, 0))
            return self.entry

    def buttonbox(self):
        actions = ttk.Frame(self)
        actions.pack(fill=tk.X, padx=15, pady=(0, 12))
        ok = ttk.Button(actions, text="确定", command=self.ok,
                        style="Danger.TButton" if self.confirm else "Primary.TButton")
        ok.pack(side=tk.RIGHT)
        ok.bind("<Return>", self.ok)
        if self.confirm or self.initial is not None:
            cancel = ttk.Button(actions, text="取消", command=self.cancel)
            cancel.pack(side=tk.RIGHT, padx=(0, 5))
            cancel.bind("<Return>", self.cancel)
            if self.confirm:
                self.initial_focus = cancel
        else:
            self.initial_focus = ok
        if self.initial is not None:
            self.entry.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)

    def apply(self):
        self.result = self.entry.get() if self.initial is not None else True


class DatePicker:
    """小型日历弹出窗口，选中日期后写入目标 Entry"""

    def __init__(self, parent, entry: ttk.Entry):
        self.entry = entry
        self.top = tk.Toplevel(parent)
        self.top.title("选择日期")
        self.top.resizable(False, False)
        self.top.configure(bg=COLOR_BG)
        self.top.transient(parent.winfo_toplevel())

        try:
            current = date.fromisoformat(entry.get().strip())
        except ValueError:
            current = date.today()
        self._year = current.year
        self._month = current.month

        self._build()
        ex = entry.winfo_rootx()
        ey = entry.winfo_rooty() + entry.winfo_height() + 2
        self.top.geometry(f"+{ex}+{ey}")
        _dark_titlebar(self.top)
        self.top.focus_set()
        self.top.bind("<Escape>", lambda event: self.top.destroy())
        self.top.bind("<FocusOut>", self._on_focus_out)

    def _on_focus_out(self, event):
        self.top.after_idle(self._check_focus)

    def _check_focus(self):
        focus = self.top.focus_get()
        if focus is None or focus.winfo_toplevel() != self.top:
            self.top.destroy()

    def _build(self):
        nav = ttk.Frame(self.top, padding=(5, 5))
        nav.pack(fill=tk.X)
        ttk.Button(nav, text="‹", width=3, command=self._prev_month).pack(side=tk.LEFT)
        self.lbl_month = ttk.Label(nav, style="Summary.TLabel")
        self.lbl_month.pack(side=tk.LEFT, expand=True)
        ttk.Button(nav, text="›", width=3, command=self._next_month).pack(side=tk.RIGHT)

        self._grid_frame = ttk.Frame(self.top, padding=(5, 0, 5, 5))
        self._grid_frame.pack()
        self._draw_grid()

    def _draw_grid(self):
        import calendar

        for widget in self._grid_frame.winfo_children():
            widget.destroy()
        self.lbl_month.config(text=f"{self._year} 年 {_MONTH_NAMES[self._month - 1]}")
        for column, weekday in enumerate(_WEEKDAYS):
            ttk.Label(self._grid_frame, text=weekday, style="Muted.TLabel",
                      anchor="center").grid(row=0, column=column, sticky="ew")
        today = date.today()
        for row, week in enumerate(calendar.Calendar().monthdayscalendar(self._year, self._month), 1):
            for column, day in enumerate(week):
                if day:
                    is_today = (self._year, self._month, day) == (today.year, today.month, today.day)
                    ttk.Button(self._grid_frame, text=str(day), width=3,
                               style="Primary.TButton" if is_today else "TButton",
                               command=lambda d=day: self._select(d)
                               ).grid(row=row, column=column, padx=1, pady=1)

    def _prev_month(self):
        if self._month == 1:
            self._month = 12
            self._year -= 1
        else:
            self._month -= 1
        self._draw_grid()

    def _next_month(self):
        if self._month == 12:
            self._month = 1
            self._year += 1
        else:
            self._month += 1
        self._draw_grid()

    def _select(self, day: int):
        self.entry.delete(0, tk.END)
        self.entry.insert(0, f"{self._year:04d}-{self._month:02d}-{day:02d}")
        self.top.destroy()


class AppCounterGUI:
    """主 GUI 应用"""

    def __init__(self, config: ConfigManager, monitor: ProcessMonitor):
        self.config = config
        self.monitor = monitor

        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        scale = float(self.root.tk.call("tk", "scaling")) / (96 / 72)
        self.root.geometry(f"{round(640 * scale)}x{round(420 * scale)}")
        self.root.minsize(round(560 * scale), round(340 * scale))
        self.root.configure(bg=COLOR_BG)

        # 尝试设置图标
        self._set_icon()

        # 样式配置
        self._setup_styles()

        # 构建界面
        self._build_ui()
        _dark_titlebar(self.root)

        # 注册监控回调（更新今日页面）
        self.monitor.add_callback(self._on_app_launched)

        # 定时刷新
        self._schedule_refresh()

        # 关闭窗口行为
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # 系统托盘
        self._tray_icon = None
        self._tray_thread: Optional[threading.Thread] = None
        if self.config.get_setting("minimize_to_tray", True):
            self._setup_tray()

        # 启动监控
        self.monitor.start()
        self._update_status_bar()

    # ---- 图标 ----

    def _set_icon(self):
        if os.path.exists(APP_ICON):
            try:
                self.root.iconbitmap(APP_ICON)
            except Exception:
                pass

    # ---- 样式 ----

    def _setup_styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        base_font = (FONT_FAMILY, FONT_SIZE)
        small_font = (FONT_FAMILY, FONT_SIZE_SMALL)
        row_height = font.Font(root=self.root, font=base_font).metrics("linespace") + 6

        style.configure(".", font=base_font, background=COLOR_BG, foreground=COLOR_TEXT,
                        bordercolor=COLOR_BORDER, lightcolor=COLOR_BORDER, darkcolor=COLOR_BORDER,
                        troughcolor=COLOR_BG, focuscolor=COLOR_PRIMARY)
        style.configure("TNotebook", borderwidth=0, tabmargins=(0, 0, 0, 0))
        style.configure("TNotebook.Tab", padding=(12, 5), background=COLOR_BG,
                        foreground=COLOR_TEXT_SECONDARY, borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", COLOR_SELECTED), ("active", COLOR_BUTTON)],
                  foreground=[("selected", COLOR_TEXT), ("active", COLOR_TEXT)])
        style.configure("TLabel", padding=0)
        style.configure("Card.TFrame", background=COLOR_CARD_BG)
        style.configure("Card.TLabel", background=COLOR_CARD_BG)
        style.configure("Detail.Card.TLabel", font=small_font, foreground=COLOR_TEXT_SECONDARY)
        style.configure("Summary.Card.TLabel", foreground=COLOR_PRIMARY)
        style.configure("Muted.TLabel", font=small_font, foreground=COLOR_TEXT_SECONDARY)
        style.configure("Summary.TLabel", font=base_font + ("bold",), foreground=COLOR_PRIMARY)
        style.configure("TButton", font=small_font, width=0, padding=(8, 3),
                        background=COLOR_BUTTON, relief="flat")
        style.map("TButton",
                  background=[("pressed", COLOR_SELECTED), ("active", COLOR_HOVER)],
                  bordercolor=[("focus", COLOR_PRIMARY)],
                  foreground=[("disabled", COLOR_TEXT_SECONDARY)])
        style.configure("Primary.TButton", background=COLOR_SELECTED, foreground=COLOR_PRIMARY)
        style.configure("Danger.TButton", foreground=COLOR_DANGER)

        style.configure("Treeview", font=base_font, rowheight=row_height, borderwidth=1,
                        background=COLOR_CARD_BG, fieldbackground=COLOR_CARD_BG)
        style.configure("Treeview.Heading", font=small_font + ("bold",),
                        padding=(5, 3), background=COLOR_BUTTON, relief="flat")
        style.map("Treeview", background=[("selected", COLOR_SELECTED)],
                  foreground=[("selected", COLOR_TEXT)])
        style.map("Treeview.Heading", background=[("active", COLOR_HOVER)])
        style.configure("TEntry", fieldbackground=COLOR_CARD_BG, padding=(5, 3),
                        insertcolor=COLOR_TEXT, selectbackground=COLOR_SELECTED,
                        selectforeground=COLOR_TEXT)
        style.map("TEntry",
                  fieldbackground=[("readonly", COLOR_CARD_BG)],
                  bordercolor=[("focus", COLOR_PRIMARY)],
                  lightcolor=[("focus", COLOR_PRIMARY)],
                  darkcolor=[("focus", COLOR_PRIMARY)])
        style.configure("Vertical.TScrollbar", arrowsize=10, background=COLOR_BUTTON,
                        arrowcolor=COLOR_TEXT_SECONDARY, relief="flat")
        style.map("Vertical.TScrollbar", background=[("active", COLOR_HOVER)])
        # Keep the dark layout and use the alt theme's checkmark indicator.
        style.element_create("Checkmark.indicator", "from", "alt", "Checkbutton.indicator")
        checkbox_layout = style.layout("TCheckbutton")
        checkbox_parts = checkbox_layout[0][1]["children"]
        checkbox_parts[0] = ("Checkmark.indicator", checkbox_parts[0][1])
        style.layout("TCheckbutton", checkbox_layout)
        style.configure("TCheckbutton", indicatorcolor=COLOR_BUTTON,
                        bordercolor=COLOR_TEXT_SECONDARY, lightcolor=COLOR_TEXT_SECONDARY,
                        shadecolor=COLOR_TEXT_SECONDARY)
        style.map("TCheckbutton", indicatorcolor=[("selected", COLOR_SELECTED)],
                  background=[("active", COLOR_BUTTON)])
        style.configure("Card.TCheckbutton", background=COLOR_CARD_BG)

    # ---- UI 构建 ----

    def _build_ui(self):
        self._build_status_bar()
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=(6, 0))

        self.tab_today = ttk.Frame(self.notebook)
        self.tab_history = ttk.Frame(self.notebook)
        self.tab_manage = ttk.Frame(self.notebook)
        self.tab_settings = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_today, text="今日统计")
        self.notebook.add(self.tab_history, text="历史记录")
        self.notebook.add(self.tab_manage, text="软件管理")
        self.notebook.add(self.tab_settings, text="设置")
        self.notebook.enable_traversal()

        self._build_today_tab()
        self._build_history_tab()
        self._build_manage_tab()
        self._build_settings_tab()

    def _build_status_bar(self):
        status_bar = ttk.Frame(self.root, padding=(9, 4))
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        self.lbl_status = ttk.Label(status_bar, style="Muted.TLabel")
        self.lbl_status.pack(side=tk.LEFT)

    def _update_status_bar(self):
        if self.monitor.is_running:
            self.lbl_status.config(text="● 监控运行中", foreground=COLOR_SUCCESS)
        else:
            self.lbl_status.config(text="○ 监控已停止", foreground=COLOR_DANGER)

    # ==================== TAB 1: 今日统计 ====================

    def _build_today_tab(self):
        frame = self.tab_today
        ctrl = ttk.Frame(frame, padding=(0, 6))
        ctrl.pack(fill=tk.X)
        for label, style, action in (
            ("刷新", "TButton", self._refresh_today),
            ("重置今日", "Danger.TButton", self._reset_today),
            ("切换到选中应用", "Primary.TButton", self._launch_selected),
        ):
            ttk.Button(ctrl, text=label, style=style, command=action).pack(
                side=tk.RIGHT, padx=(4, 0))
        self.lbl_total_today = ttk.Label(ctrl, style="Summary.TLabel")
        self.lbl_total_today.pack(side=tk.LEFT)

        tree_frame = ttk.Frame(frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        columns = ("rank", "display_name", "process", "count", "status")
        self.today_tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                       selectmode="browse", height=9)
        heading_font = font.Font(root=self.root, font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"))
        for key, label, width, anchor, stretch in (
            ("rank", "#", 32, "center", False),
            ("display_name", "软件名称", 150, "w", True),
            ("process", "进程名", 130, "w", True),
            ("count", "使用次数", 72, "center", False),
            ("status", "状态", 88, "center", False),
        ):
            self.today_tree.heading(key, text=label, anchor=anchor)
            self.today_tree.column(key, width=max(width, heading_font.measure(label) + 16),
                                   anchor=anchor, stretch=stretch)

        self.today_tree.bind("<Double-1>", lambda event: self._launch_selected()
                             if self.today_tree.identify_row(event.y) else None)
        self.today_tree.bind("<Return>", lambda event: self._launch_selected())
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.today_tree.yview)
        self.today_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.today_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.today_tree.tag_configure("running", foreground=COLOR_SUCCESS)
        self.today_tree.tag_configure("not_running", foreground=COLOR_TEXT_SECONDARY)
        self.today_tree.tag_configure("disabled", foreground=COLOR_TEXT_SECONDARY)
        self.today_tree.tag_configure("alternate", background=COLOR_BG)

    def _refresh_today(self):
        """刷新今日统计页面"""
        counts = self.config.get_today_counts()
        enabled = self.config.get_enabled_processes()
        total = sum(counts.get(p, 0) for p in enabled)
        active = sum(1 for p in enabled if counts.get(p, 0) > 0)
        self.lbl_total_today.config(text=f"今日 {total} 次 · {active}/{len(enabled)} 款有使用")

        selection = self.today_tree.selection()
        position = self.today_tree.yview()[0]

        # 刷新 Treeview
        self.today_tree.delete(*self.today_tree.get_children())

        # 构建排序列表
        rows = []
        for proc, display_name in enabled.items():
            cnt = counts.get(proc, 0)
            is_enabled = self.config.watchlist.get(proc, {}).get("enabled", True)
            # 检查是否在运行
            try:
                import psutil
                running = any(p.name().lower() == proc.lower() for p in psutil.process_iter(["name"]))
            except Exception:
                running = False
            rows.append((display_name, proc, cnt, running, is_enabled))

        rows.sort(key=lambda x: (-x[2], x[0]))

        for i, (dname, proc, cnt, running, is_enabled) in enumerate(rows, 1):
            status = "● 运行中" if running else ("○ 未使用" if is_enabled else "已禁用")
            tag = "running" if running else ("disabled" if not is_enabled else "not_running")
            values = (i, dname, proc, cnt, status)
            tags = (tag, "alternate") if i % 2 == 0 else (tag,)
            self.today_tree.insert("", tk.END, iid=proc, values=values, tags=tags)
        if selection and self.today_tree.exists(selection[0]):
            self.today_tree.selection_set(selection[0])
            self.today_tree.focus(selection[0])
        self.today_tree.yview_moveto(position)

    def _launch_selected(self):
        """启动/切换到 today_tree 中选中的应用"""
        sel = self.today_tree.selection()
        if not sel:
            return
        proc = sel[0]
        exe_path = self.config.get_exe_path(proc)
        ok = ProcessMonitor.focus_or_launch(proc, exe_path)
        if not ok:
            DarkDialog(self.root, "提示", f"无法启动 {proc}，请检查程序路径。")
        # 刷新运行状态
        self._refresh_today()

    def _reset_today(self):
        if DarkDialog(self.root, "重置今日", "确定要重置今日计数吗？\n此操作不可撤销。", confirm=True).result:
            self.config.reset_today()
            self._refresh_today()

    def _on_app_launched(self, proc_name: str, display_name: str):
        """监控回调：应用被使用（窗口被激活）时更新 UI"""
        self.root.after(0, self._refresh_today)

    # ==================== TAB 2: 历史记录 ====================

    def _build_history_tab(self):
        frame = self.tab_history
        dates = ttk.Frame(frame, padding=(0, 6))
        dates.pack(fill=tk.X)
        entries = []
        for label in ("从", "到"):
            ttk.Label(dates, text=label, style="Muted.TLabel").pack(side=tk.LEFT, padx=(0, 4))
            entry = ttk.Entry(dates, width=11)
            entry.pack(side=tk.LEFT)
            entry.bind("<Return>", lambda event: self._query_history())
            ttk.Button(dates, text="日历", command=lambda e=entry: DatePicker(dates, e)).pack(
                side=tk.LEFT, padx=(3, 8))
            entries.append(entry)
        self.entry_start, self.entry_end = entries
        ttk.Button(dates, text="查询", style="Primary.TButton", command=self._query_history).pack(
            side=tk.LEFT)

        presets = ttk.Frame(frame, padding=(0, 0, 0, 6))
        presets.pack(fill=tk.X)
        self.history_summary = ttk.Label(presets, style="Summary.TLabel")
        self.history_summary.pack(side=tk.RIGHT)
        for label, days in [("今天", 0), ("近3天", 3), ("近7天", 7),
                            ("近30天", 30), ("全部", -1)]:
            ttk.Button(presets, text=label, command=lambda d=days: self._quick_query(d)).pack(
                side=tk.LEFT, padx=(0, 4))

        tree_frame = ttk.Frame(frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        columns = ("rank", "display_name", "process", "count")
        self.history_tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                         selectmode="none", height=8)
        heading_font = font.Font(root=self.root, font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"))
        for key, label, width, anchor, stretch in (
            ("rank", "#", 32, "center", False),
            ("display_name", "软件名称", 170, "w", True),
            ("process", "进程名", 140, "w", True),
            ("count", "使用次数", 88, "center", False),
        ):
            self.history_tree.heading(key, text=label, anchor=anchor)
            self.history_tree.column(key, width=max(width, heading_font.measure(label) + 16),
                                     anchor=anchor, stretch=stretch)
        self.history_tree.tag_configure("alternate", background=COLOR_BG)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._quick_query(7)

    def _quick_query(self, days: int):
        """快捷日期查询"""
        end = date.today()
        if days < 0:
            start = date(2000, 1, 1)
        else:
            start = end - timedelta(days=max(0, days - 1))
        self.entry_start.delete(0, tk.END)
        self.entry_start.insert(0, start.isoformat())
        self.entry_end.delete(0, tk.END)
        self.entry_end.insert(0, end.isoformat())
        self._query_history()

    def _query_history(self):
        start = self.entry_start.get().strip()
        end = self.entry_end.get().strip()
        if not start or not end:
            DarkDialog(self.root, "日期范围", "请输入日期范围（YYYY-MM-DD）。")
            return

        counts = self.config.get_range_counts(start, end)
        display_map = {p: info["display_name"]
                       for p, info in self.config.watchlist.items()}

        self.history_tree.delete(*self.history_tree.get_children())
        self.history_summary.config(text=f"{sum(counts.values())} 次 · {len(counts)} 款应用")

        # 填充表格
        rows = []
        for proc, cnt in counts.items():
            dname = display_map.get(proc, proc)
            rows.append((dname, proc, cnt))
        rows.sort(key=lambda x: -x[2])

        for i, (dname, proc, cnt) in enumerate(rows, 1):
            tags = ("alternate",) if i % 2 == 0 else ()
            self.history_tree.insert("", tk.END, values=(i, dname, proc, cnt), tags=tags)

    # ==================== TAB 3: 软件管理 ====================

    def _build_manage_tab(self):
        frame = self.tab_manage
        ctrl = ttk.Frame(frame, padding=(0, 6))
        ctrl.pack(fill=tk.X)
        for label, style, action in (
            ("扫描运行中应用", "Primary.TButton", self._scan_running_apps),
            ("手动添加", "TButton", self._add_custom_app),
            ("刷新", "TButton", self._refresh_manage),
        ):
            ttk.Button(ctrl, text=label, style=style, command=action).pack(
                side=tk.RIGHT, padx=(4, 0))
        ttk.Label(ctrl, text="搜索", style="Muted.TLabel").pack(side=tk.LEFT, padx=(0, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._filter_manage_list())
        ttk.Entry(ctrl, textvariable=self.search_var, width=12).pack(
            side=tk.LEFT, fill=tk.X, expand=True)

        self.manage_canvas, self.manage_list_frame = self._scrolling_list(frame)
        self.root.bind("<MouseWheel>", lambda event: self.manage_canvas.yview_scroll(
            -int(event.delta / 120), "units") if self.notebook.select() == str(frame) else None)
        self._all_manage_rows = []

    @staticmethod
    def _scrolling_list(parent):
        area = ttk.Frame(parent)
        area.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(area, bg=COLOR_BG, highlightthickness=0, width=0, height=0,
                           yscrollincrement=16)
        scrollbar = ttk.Scrollbar(area, orient=tk.VERTICAL, command=canvas.yview)
        list_frame = ttk.Frame(canvas)
        content = canvas.create_window((0, 0), window=list_frame, anchor="nw")
        list_frame.bind("<Configure>", lambda event: canvas.configure(
            scrollregion=canvas.bbox(content)))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(content, width=event.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        return canvas, list_frame

    def _refresh_manage(self):
        """刷新软件管理列表"""
        items = self.config.get_all_processes()
        if items != self._all_manage_rows or not self.manage_list_frame.winfo_children():
            self._all_manage_rows = items
            self._filter_manage_list()

    def _filter_manage_list(self):
        query = self.search_var.get().lower().strip()
        items = [item for item in self._all_manage_rows
                 if query in item["display_name"].lower() or query in item["process"].lower()]
        self._render_manage_rows(items)

    def _render_manage_rows(self, items):
        for widget in self.manage_list_frame.winfo_children():
            widget.destroy()
        for item in items:
            self._create_manage_row(self.manage_list_frame, item)
        if not items:
            ttk.Label(self.manage_list_frame, text="没有匹配的软件", style="Muted.TLabel").pack(
                anchor="w", pady=5)
        self.manage_list_frame.update_idletasks()

    def _create_manage_row(self, parent, item: dict):
        proc = item["process"]
        dname = item["display_name"]
        enabled = item["enabled"]
        is_default = item["is_default"]

        row = tk.Frame(parent, bg=COLOR_CARD_BG)
        row.pack(fill=tk.X, pady=(0, 2))
        buttons = ttk.Frame(row, style="Card.TFrame")
        buttons.pack(side=tk.RIGHT, padx=6, pady=4)
        ttk.Button(buttons, text="禁用" if enabled else "启用",
                   style="TButton" if enabled else "Primary.TButton",
                   command=lambda: self._toggle_app(proc)).pack(side=tk.LEFT)
        ttk.Button(buttons, text="重命名", command=lambda: self._rename_app(proc, dname)).pack(
            side=tk.LEFT, padx=(4, 0))
        if not is_default:
            ttk.Button(buttons, text="删除", style="Danger.TButton",
                       command=lambda: self._delete_app(proc)).pack(side=tk.LEFT, padx=(4, 0))

        info = ttk.Frame(row, style="Card.TFrame")
        info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0), pady=2)
        ttk.Label(info, text=dname if enabled else f"{dname}（已禁用）",
                  style="Card.TLabel", anchor="w").pack(fill=tk.X)
        ttk.Label(info, text=f"{proc} · {'默认' if is_default else '自定义'}",
                  style="Detail.Card.TLabel", anchor="w").pack(fill=tk.X)

    def _toggle_app(self, proc: str):
        self.config.toggle_enabled(proc)
        self.monitor.refresh_baseline()
        self._refresh_manage()
        self._refresh_today()

    def _rename_app(self, proc: str, current_name: str):
        new_name = DarkDialog(self.root, "重命名", f"{proc} 的显示名称",
                              initial=current_name).result
        if new_name and new_name.strip():
            self.config.rename_display(proc, new_name.strip())
            self._refresh_manage()
            self._refresh_today()

    def _delete_app(self, proc: str):
        dname = self.config.watchlist.get(proc, {}).get("display_name", proc)
        if DarkDialog(self.root, "确认删除", f"确定要删除「{dname}」（{proc}）吗？",
                      confirm=True).result:
            self.config.remove_custom(proc)
            self._refresh_manage()
            self._refresh_today()

    def _scan_running_apps(self):
        """扫描当前运行中有可见窗口的应用，让用户勾选添加"""
        import ctypes
        import ctypes.wintypes
        import psutil

        user32 = ctypes.windll.user32

        # 收集有可见窗口的进程
        discovered = {}  # proc_name_lower -> {"display": best_display_name, "path": exe_path}

        def enum_callback(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            # 获取窗口标题
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            title_buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, title_buf, length + 1)
            title = title_buf.value.strip()
            if not title:
                return True

            # 获取 PID
            pid = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if not pid.value:
                return True

            try:
                proc = psutil.Process(pid.value)
                proc_name = (proc.name() or "").lower()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                return True

            # 跳过系统进程
            skip_names = {"explorer.exe", "svchost.exe", "dllhost.exe", "conhost.exe",
                          "runtimebroker.exe", "shellexperiencehost.exe", "searchui.exe",
                          "systemsettings.exe", "applicationframehost.exe", "textinputhost.exe",
                          "sihost.exe", "taskmgr.exe", "ctfmon.exe", "winlogon.exe",
                          "csrss.exe", "smss.exe", "services.exe", "lsass.exe", "wininit.exe"}
            if proc_name in skip_names:
                return True

            # 跳过没有 exe 路径的
            try:
                exe_path = proc.exe()
            except Exception:
                return True

            # 使用窗口标题作为显示名（更好看）
            if proc_name not in discovered or len(title) > len(discovered[proc_name]["display"]):
                discovered[proc_name] = {"display": title, "path": exe_path}
            return True

        # 遍历所有顶层窗口
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
        user32.EnumWindows(WNDENUMPROC(enum_callback), 0)

        # 过滤掉已经在监控列表中的
        existing = set(self.config.watchlist.keys())
        new_apps = {k: v for k, v in discovered.items() if k not in existing}

        if not new_apps:
            DarkDialog(self.root, "扫描结果", "没有发现新的可监控应用。")
            return

        # 弹出选择对话框
        self._show_scan_dialog(new_apps)

    def _new_dialog(self, title):
        dialog = tk.Toplevel(self.root, bg=COLOR_BG)
        dialog.withdraw()
        dialog.title(title)
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.bind("<Escape>", lambda event: dialog.destroy())
        return dialog

    def _show_dialog(self, dialog):
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - dialog.winfo_reqwidth()) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - dialog.winfo_reqheight()) // 2
        dialog.geometry(f"+{x}+{y}")
        dialog.deiconify()
        _dark_titlebar(dialog)
        dialog.grab_set()
        dialog.focus_set()

    def _show_scan_dialog(self, apps: dict):
        """勾选要添加的应用"""
        dialog = self._new_dialog("扫描运行中应用")
        body = ttk.Frame(dialog, padding=9)
        body.pack(fill=tk.BOTH, expand=True)

        controls = ttk.Frame(body)
        controls.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(controls, text=f"发现 {len(apps)} 款应用", style="Summary.TLabel").pack(side=tk.LEFT)

        check_vars = {}

        def select_all(value):
            for var in check_vars.values():
                var.set(value)

        ttk.Button(controls, text="取消全选", command=lambda: select_all(False)).pack(side=tk.RIGHT)
        ttk.Button(controls, text="全选", command=lambda: select_all(True)).pack(
            side=tk.RIGHT, padx=(0, 4))

        canvas, list_frame = self._scrolling_list(body)
        dialog.bind("<MouseWheel>", lambda event: canvas.yview_scroll(
            -int(event.delta / 120), "units"))
        for proc_name in sorted(apps, key=lambda key: apps[key]["display"]):
            var = tk.BooleanVar(value=True)
            check_vars[proc_name] = var
            row = ttk.Frame(list_frame, style="Card.TFrame", padding=(5, 3))
            row.pack(fill=tk.X, pady=(0, 2))
            ttk.Checkbutton(row, variable=var, text=apps[proc_name]["display"],
                            style="Card.TCheckbutton").pack(fill=tk.X)
            ttk.Label(row, text=proc_name, style="Detail.Card.TLabel").pack(
                fill=tk.X, padx=(19, 0))

        dialog.update_idletasks()
        canvas.configure(width=max(380, controls.winfo_reqwidth()),
                         height=min(230, list_frame.winfo_reqheight()))

        def do_import():
            count = 0
            for proc_name, var in check_vars.items():
                if var.get():
                    info = apps[proc_name]
                    self.config.add_custom(proc_name, info["display"], info.get("path", ""))
                    count += 1
            if count:
                self.monitor.refresh_baseline()
                self._refresh_manage()
                self._refresh_today()
                DarkDialog(dialog, "导入完成", f"已添加 {count} 款应用。")
            dialog.destroy()

        actions = ttk.Frame(body)
        actions.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(actions, text="添加选中", style="Primary.TButton",
                   command=do_import).pack(side=tk.RIGHT)
        ttk.Button(actions, text="取消", command=dialog.destroy).pack(side=tk.RIGHT, padx=(0, 4))
        self._show_dialog(dialog)

    def _add_custom_app(self):
        dialog = self._new_dialog("添加自定义软件")
        body = ttk.Frame(dialog, padding=12)
        body.pack(fill=tk.BOTH, expand=True)
        ttk.Button(body, text="选择程序文件 (.exe)",
                   command=lambda: self._browse_exe(dialog, entry_proc, entry_name)
                   ).pack(anchor="w", pady=(0, 8))

        ttk.Label(body, text="进程名称").pack(anchor="w")
        entry_proc = ttk.Entry(body, width=34)
        entry_proc.pack(fill=tk.X, pady=(2, 6))
        ttk.Label(body, text="显示名称").pack(anchor="w")
        entry_name = ttk.Entry(body, width=34)
        entry_name.pack(fill=tk.X, pady=(2, 8))

        def do_add():
            proc = entry_proc.get().strip()
            name = entry_name.get().strip()
            if not proc:
                DarkDialog(dialog, "添加自定义软件", "请选择程序或输入进程名称。")
                return
            self.config.add_custom(proc, name or proc, getattr(dialog, "_exe_path", ""))
            self.monitor.refresh_baseline()
            self._refresh_manage()
            self._refresh_today()
            dialog.destroy()

        actions = ttk.Frame(body)
        actions.pack(fill=tk.X)
        ttk.Button(actions, text="添加", style="Primary.TButton", command=do_add).pack(side=tk.RIGHT)
        ttk.Button(actions, text="取消", command=dialog.destroy).pack(side=tk.RIGHT, padx=(0, 4))
        entry_proc.bind("<Return>", lambda event: do_add())
        entry_name.bind("<Return>", lambda event: do_add())
        self._show_dialog(dialog)
        entry_proc.focus_set()

    def _browse_exe(self, dialog, entry_proc, entry_name):
        """打开文件选择器，选取 .exe 并自动填入进程名和显示名"""
        path = filedialog.askopenfilename(
            title="选择要监控的程序 (.exe)",
            filetypes=[("可执行文件", "*.exe"), ("所有文件", "*.*")],
            parent=dialog,
        )
        if path:
            dialog._exe_path = path
            proc_name = os.path.basename(path).lower()
            # 去掉扩展名作为默认显示名
            display_name = os.path.splitext(os.path.basename(path))[0]
            entry_proc.delete(0, tk.END)
            entry_proc.insert(0, proc_name)
            entry_name.delete(0, tk.END)
            entry_name.insert(0, display_name)

    # ==================== TAB 4: 设置 ====================

    def _build_settings_tab(self):
        frame = self.tab_settings
        card = ttk.Frame(frame, style="Card.TFrame", padding=(9, 5))
        card.pack(fill=tk.X, pady=(6, 4))

        self.tray_var = tk.BooleanVar(value=self.config.get_setting("minimize_to_tray", True))
        self.startup_var = tk.BooleanVar(value=self.config.get_startup_enabled())
        self.notify_var = tk.BooleanVar(value=self.config.get_setting("show_notifications", True))
        self._setting_row(card, "关闭窗口时最小化到系统托盘",
                          self.tray_var, self._on_tray_setting_change)
        self._setting_row(card, "开机时在后台启动监控",
                          self.startup_var, self._on_startup_setting_change)
        self._setting_row(card, "切换到应用时显示通知",
                          self.notify_var, self._on_notify_setting_change)

        interval_card = ttk.Frame(frame, style="Card.TFrame", padding=(9, 5))
        interval_card.pack(fill=tk.X, pady=(0, 4))
        current_interval = self.config.get_setting("poll_interval_ms", 500)
        ttk.Label(interval_card, text="检测间隔", style="Card.TLabel").pack(side=tk.LEFT)
        self.interval_label = ttk.Label(interval_card, text=f"{current_interval} ms",
                                        style="Summary.Card.TLabel", width=9, anchor="e")
        self.interval_label.pack(side=tk.RIGHT, padx=(6, 0))
        self.interval_scale = tk.Scale(
            interval_card, from_=100, to=5000, resolution=100, showvalue=False,
            orient=tk.HORIZONTAL, bg=COLOR_BUTTON, activebackground=COLOR_HOVER,
            troughcolor=COLOR_BG, highlightbackground=COLOR_CARD_BG,
            highlightcolor=COLOR_PRIMARY, highlightthickness=1, borderwidth=0,
            sliderrelief="flat", width=12, command=self._on_interval_change,
        )
        self.interval_scale.set(current_interval)
        self.interval_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(7, 0))

        data_card = ttk.Frame(frame, style="Card.TFrame", padding=(9, 6))
        data_card.pack(fill=tk.X)
        file_row = ttk.Frame(data_card, style="Card.TFrame")
        file_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(file_row, text="数据文件", style="Card.TLabel").pack(side=tk.LEFT, padx=(0, 7))
        data_path = ttk.Entry(file_row, width=20, font=(FONT_FAMILY, FONT_SIZE_SMALL))
        data_path.insert(0, DATA_FILE)
        data_path.state(["readonly"])
        data_path.pack(side=tk.LEFT, fill=tk.X, expand=True)

        buttons = ttk.Frame(data_card, style="Card.TFrame")
        buttons.pack(fill=tk.X)
        ttk.Button(buttons, text="清除今日数据", command=self._reset_today).pack(side=tk.LEFT)
        ttk.Button(buttons, text="清除全部历史数据", style="Danger.TButton",
                   command=self._reset_all_data).pack(side=tk.LEFT, padx=(4, 0))
        ttk.Label(buttons, text="AppCounter 1.0.0", style="Detail.Card.TLabel").pack(side=tk.RIGHT)

    def _setting_row(self, parent, title: str, var: tk.BooleanVar, command):
        ttk.Checkbutton(parent, text=title, variable=var, command=command,
                        style="Card.TCheckbutton").pack(fill=tk.X, pady=2)

    def _on_tray_setting_change(self):
        self.config.set_setting("minimize_to_tray", self.tray_var.get())

    def _on_notify_setting_change(self):
        self.config.set_setting("show_notifications", self.notify_var.get())

    def _on_startup_setting_change(self):
        if self.startup_var.get():
            ok = self.config.enable_startup()
            if not ok:
                DarkDialog(self.root, "开机自启", "设置开机自启失败，请检查权限。")
                self.startup_var.set(False)
        else:
            self.config.disable_startup()

    def _on_interval_change(self, value):
        ms = int(float(value))
        self.config.set_setting("poll_interval_ms", ms)
        self.interval_label.config(text=f"{ms} ms")

    def _reset_all_data(self):
        if DarkDialog(self.root, "清除历史", "确定要清除全部历史计数数据吗？\n此操作不可撤销。",
                      confirm=True).result:
            self.config.reset_all()
            self._refresh_today()

    # ==================== 系统托盘 ====================

    def _setup_tray(self):
        """在独立线程中启动系统托盘"""
        try:
            from PIL import Image, ImageDraw

            # 生成一个简单图标
            img = Image.new("RGBA", (64, 64), (24, 144, 255, 255))
            draw = ImageDraw.Draw(img)
            draw.rectangle([16, 20, 48, 44], fill="white")
            draw.rectangle([22, 14, 28, 50], fill="white")
            draw.rectangle([36, 14, 42, 50], fill="white")

            self._tray_image = img

            def _run_tray():
                import pystray

                def on_show(icon, item):
                    self.root.after(0, self._show_window)

                def on_exit(icon, item):
                    icon.stop()
                    self.root.after(0, self._quit_app)

                menu = pystray.Menu(
                    pystray.MenuItem("显示主窗口", on_show, default=True),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem("退出", on_exit),
                )
                self._tray_icon = pystray.Icon("AppCounter", img, APP_TITLE, menu)
                self._tray_icon.run()

            self._tray_thread = threading.Thread(target=_run_tray, daemon=True, name="TrayIcon")
            self._tray_thread.start()
        except ImportError:
            # pystray 未安装，不启用托盘
            pass

    # ==================== 窗口管理 ====================

    def _on_close(self):
        if self.config.get_setting("minimize_to_tray", True) and self._tray_icon:
            self.root.withdraw()
        else:
            self._quit_app()

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _quit_app(self):
        self.monitor.stop()
        # 确保退出前保存数据
        self.config.save()
        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
        self.root.destroy()

    # ==================== 定时刷新 ====================

    def _schedule_refresh(self):
        self._refresh_today()
        self._refresh_manage()
        # 每 5 秒刷新 UI（不会触发重新扫描，只是刷新显示）
        self.root.after(5000, self._schedule_refresh)

    # ==================== 运行入口 ====================

    def run(self):
        """启动 GUI 主循环"""
        self._refresh_today()
        self._refresh_manage()
        self.root.mainloop()
