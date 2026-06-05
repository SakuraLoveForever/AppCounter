"""
GUI 界面模块
基于 tkinter 的主窗口 + 系统托盘图标
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import date, timedelta
from typing import Optional

from config import ConfigManager, DATA_FILE
from monitor import ProcessMonitor

# ---- 常量 ----
APP_TITLE = "AppCounter - 应用使用统计"
APP_ICON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
FONT_FAMILY = "Microsoft YaHei UI"
FONT_SIZE = 10
FONT_SIZE_TITLE = 14
FONT_SIZE_SMALL = 9

# 颜色
COLOR_BG = "#f5f5f5"
COLOR_PRIMARY = "#1890ff"
COLOR_SUCCESS = "#52c41a"
COLOR_WARNING = "#faad14"
COLOR_DANGER = "#ff4d4f"
COLOR_TEXT = "#262626"
COLOR_TEXT_SECONDARY = "#8c8c8c"
COLOR_BORDER = "#d9d9d9"
COLOR_CARD_BG = "#ffffff"

# 月份中文名
_MONTH_NAMES = ["一月", "二月", "三月", "四月", "五月", "六月",
                "七月", "八月", "九月", "十月", "十一月", "十二月"]
_WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"]


class DatePicker:
    """小型日历弹出窗口，选中日期后写入目标 Entry"""

    def __init__(self, parent, entry: tk.Entry):
        self.entry = entry
        self.top = tk.Toplevel(parent)
        self.top.title("选择日期")
        self.top.resizable(False, False)
        self.top.configure(bg=COLOR_CARD_BG)
        self.top.transient(parent)

        # 从 entry 读取初始日期，默认今天
        try:
            parts = entry.get().strip().split("-")
            self._year = int(parts[0])
            self._month = int(parts[1])
        except Exception:
            today = date.today()
            self._year = today.year
            self._month = today.month

        self._build()
        # 定位到 entry 下方
        self.top.update_idletasks()
        ex = entry.winfo_rootx()
        ey = entry.winfo_rooty() + entry.winfo_height() + 2
        self.top.geometry(f"+{ex}+{ey}")
        self.top.focus_set()
        # 点击窗口外部自动关闭
        self.top.bind("<FocusOut>", lambda e: self.top.after(100, self._check_focus))

    def _check_focus(self):
        """延迟检查：如果焦点完全离开了日历窗口则关闭"""
        try:
            focus_widget = self.top.focus_get()
            if focus_widget is None:
                self.top.destroy()
        except Exception:
            self.top.destroy()

    def _build(self):
        # 月份导航
        nav = tk.Frame(self.top, bg=COLOR_PRIMARY)
        nav.pack(fill=tk.X)
        tk.Button(nav, text="◀", font=(FONT_FAMILY, 9), bg=COLOR_PRIMARY, fg="white",
                  relief="flat", bd=0, padx=6,
                  command=self._prev_month).pack(side=tk.LEFT, padx=2, pady=2)
        self.lbl_month = tk.Label(nav, font=(FONT_FAMILY, 10, "bold"),
                                  bg=COLOR_PRIMARY, fg="white")
        self.lbl_month.pack(side=tk.LEFT, expand=True)
        tk.Button(nav, text="▶", font=(FONT_FAMILY, 9), bg=COLOR_PRIMARY, fg="white",
                  relief="flat", bd=0, padx=6,
                  command=self._next_month).pack(side=tk.RIGHT, padx=2, pady=2)

        # 星期头
        wh = tk.Frame(self.top, bg=COLOR_CARD_BG)
        wh.pack(fill=tk.X, padx=4, pady=(4, 0))
        for wd in _WEEKDAYS:
            tk.Label(wh, text=wd, font=(FONT_FAMILY, 8), width=3,
                     bg=COLOR_CARD_BG, fg=COLOR_TEXT_SECONDARY).pack(side=tk.LEFT)

        # 日期网格
        self._grid_frame = tk.Frame(self.top, bg=COLOR_CARD_BG)
        self._grid_frame.pack(padx=4, pady=4)
        self._draw_grid()

    def _draw_grid(self):
        for w in self._grid_frame.winfo_children():
            w.destroy()
        self.lbl_month.config(text=f"{self._year}  {_MONTH_NAMES[self._month - 1]}")

        import calendar
        cal = calendar.monthcalendar(self._year, self._month)
        today = date.today()

        for r, week in enumerate(cal):
            for c, day in enumerate(week):
                if day == 0:
                    lbl = tk.Label(self._grid_frame, text="", width=4, height=2,
                                   bg=COLOR_CARD_BG)
                else:
                    is_today = (self._year == today.year and self._month == today.month
                                and day == today.day)
                    bg = "#e6f7ff" if is_today else COLOR_CARD_BG
                    fg = COLOR_PRIMARY if is_today else COLOR_TEXT
                    lbl = tk.Label(self._grid_frame, text=str(day), width=4, height=2,
                                   bg=bg, fg=fg, font=(FONT_FAMILY, 9),
                                   cursor="hand2", relief="flat")
                    lbl.bind("<Button-1>", lambda e, d=day: self._select(d))
                    lbl.bind("<Enter>", lambda e, l=lbl: l.configure(bg="#bae7ff"))
                    lbl.bind("<Leave>", lambda e, l=lbl, d=day, t=is_today:
                             l.configure(bg="#e6f7ff" if t else COLOR_CARD_BG))
                lbl.grid(row=r, column=c, padx=1, pady=1)

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
        self.root.geometry("960x680")
        self.root.minsize(800, 560)
        self.root.configure(bg=COLOR_BG)

        # 尝试设置图标
        self._set_icon()

        # 样式配置
        self._setup_styles()

        # 构建界面
        self._build_ui()

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
        style = ttk.Style()
        # 使用 Windows 原生主题，避免按钮文字不显示
        available = style.theme_names()
        if "vista" in available:
            style.theme_use("vista")
        elif "winnative" in available:
            style.theme_use("winnative")
        else:
            style.theme_use("clam")

        # 通用配置
        style.configure(".", font=(FONT_FAMILY, FONT_SIZE), background=COLOR_BG)

        # Notebook (标签页)
        style.configure("TNotebook", background=COLOR_BG, borderwidth=0)
        style.configure("TNotebook.Tab", font=(FONT_FAMILY, FONT_SIZE), padding=[20, 8],
                        background=COLOR_BG, borderwidth=0)
        style.map("TNotebook.Tab",
                  background=[("selected", COLOR_CARD_BG)],
                  foreground=[("selected", COLOR_PRIMARY)])

        # Frame
        style.configure("Card.TFrame", background=COLOR_CARD_BG, relief="solid", borderwidth=1)

        # Label
        style.configure("Title.TLabel", font=(FONT_FAMILY, FONT_SIZE_TITLE, "bold"),
                        background=COLOR_CARD_BG, foreground=COLOR_TEXT)
        style.configure("Subtitle.TLabel", font=(FONT_FAMILY, FONT_SIZE_SMALL),
                        background=COLOR_CARD_BG, foreground=COLOR_TEXT_SECONDARY)
        style.configure("Count.TLabel", font=(FONT_FAMILY, 28, "bold"),
                        background=COLOR_CARD_BG, foreground=COLOR_PRIMARY)
        style.configure("Status.TLabel", font=(FONT_FAMILY, FONT_SIZE_SMALL),
                        background=COLOR_BG, foreground=COLOR_TEXT_SECONDARY)

        # Button
        style.configure("Primary.TButton", font=(FONT_FAMILY, FONT_SIZE),
                        background=COLOR_PRIMARY, foreground="white", borderwidth=0,
                        padding=[16, 6])
        style.map("Primary.TButton",
                  background=[("active", "#40a9ff"), ("pressed", "#096dd9")])
        style.configure("Danger.TButton", font=(FONT_FAMILY, FONT_SIZE),
                        background=COLOR_DANGER, foreground="white", borderwidth=0,
                        padding=[16, 6])
        style.configure("Small.TButton", font=(FONT_FAMILY, FONT_SIZE_SMALL),
                        padding=[8, 3])

        # Treeview
        style.configure("Treeview", font=(FONT_FAMILY, FONT_SIZE), rowheight=32,
                        background=COLOR_CARD_BG, fieldbackground=COLOR_CARD_BG)
        style.configure("Treeview.Heading", font=(FONT_FAMILY, FONT_SIZE, "bold"),
                        background="#fafafa", foreground=COLOR_TEXT)
        style.map("Treeview", background=[("selected", "#e6f7ff")],
                  foreground=[("selected", COLOR_TEXT)])

        # Entry
        style.configure("TEntry", font=(FONT_FAMILY, FONT_SIZE), padding=[8, 4])

    # ---- UI 构建 ----

    def _build_ui(self):
        # 顶部标题栏
        self._build_header()

        # 标签页容器
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=(6, 6))

        # 四个 TAB
        self.tab_today = tk.Frame(self.notebook, bg=COLOR_BG)
        self.tab_history = tk.Frame(self.notebook, bg=COLOR_BG)
        self.tab_manage = tk.Frame(self.notebook, bg=COLOR_BG)
        self.tab_settings = tk.Frame(self.notebook, bg=COLOR_BG)

        self.notebook.add(self.tab_today, text="   📊 今日统计   ")
        self.notebook.add(self.tab_history, text="   📅 历史记录   ")
        self.notebook.add(self.tab_manage, text="   ⚙ 软件管理   ")
        self.notebook.add(self.tab_settings, text="   🔧 设置   ")

        self._build_today_tab()
        self._build_history_tab()
        self._build_manage_tab()
        self._build_settings_tab()

        # 底部状态栏
        self._build_status_bar()

    def _build_header(self):
        header = tk.Frame(self.root, bg=COLOR_PRIMARY, height=48)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        title = tk.Label(header, text="📱 AppCounter - 应用使用统计",
                         font=(FONT_FAMILY, 16, "bold"),
                         bg=COLOR_PRIMARY, fg="white")
        title.pack(side=tk.LEFT, padx=16, pady=10)
        self.lbl_total_today = tk.Label(header, text="",
                                        font=(FONT_FAMILY, 12),
                                        bg=COLOR_PRIMARY, fg="#e6f7ff")
        self.lbl_total_today.pack(side=tk.RIGHT, padx=16, pady=10)

    def _build_status_bar(self):
        status_bar = tk.Frame(self.root, bg=COLOR_BG, height=26)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        status_bar.pack_propagate(False)

        self.lbl_status = tk.Label(status_bar, text="", font=(FONT_FAMILY, FONT_SIZE_SMALL),
                                   bg=COLOR_BG, fg=COLOR_TEXT_SECONDARY)
        self.lbl_status.pack(side=tk.LEFT, padx=10, pady=3)

        self.lbl_last_seen = tk.Label(status_bar, text="",
                                      font=(FONT_FAMILY, FONT_SIZE_SMALL),
                                      bg=COLOR_BG, fg=COLOR_TEXT_SECONDARY)
        self.lbl_last_seen.pack(side=tk.RIGHT, padx=10, pady=3)

    def _update_status_bar(self):
        if self.monitor.is_running:
            self.lbl_status.config(text="● 监控运行中")
        else:
            self.lbl_status.config(text="○ 监控已停止", fg=COLOR_DANGER)

    # ==================== TAB 1: 今日统计 ====================

    def _build_today_tab(self):
        frame = self.tab_today
        frame.configure(bg=COLOR_BG)

        # 控制栏
        ctrl = tk.Frame(frame, bg=COLOR_BG)
        ctrl.pack(fill=tk.X, padx=12, pady=(12, 6))

        tk.Label(ctrl, text="今日应用使用统计",
                 font=(FONT_FAMILY, FONT_SIZE_TITLE, "bold"),
                 bg=COLOR_BG, fg=COLOR_TEXT).pack(side=tk.LEFT)

        btn_refresh = ttk.Button(ctrl, text="刷新", style="Small.TButton",
                                 command=self._refresh_today)
        btn_refresh.pack(side=tk.RIGHT, padx=4)

        btn_reset = ttk.Button(ctrl, text="重置今日", style="Danger.TButton",
                               command=self._reset_today)
        btn_reset.pack(side=tk.RIGHT, padx=4)

        # 概览卡片区域
        self.cards_frame = tk.Frame(frame, bg=COLOR_BG)
        self.cards_frame.pack(fill=tk.X, padx=12, pady=(0, 6))

        # Treeview 详情
        tree_frame = tk.Frame(frame, bg=COLOR_CARD_BG)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        columns = ("rank", "display_name", "process", "count", "status")
        self.today_tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                       selectmode="browse")

        self.today_tree.heading("rank", text="#")
        self.today_tree.heading("display_name", text="软件名称")
        self.today_tree.heading("process", text="进程名")
        self.today_tree.heading("count", text="今日使用")
        self.today_tree.heading("status", text="状态")

        self.today_tree.column("rank", width=45, anchor="center")
        self.today_tree.column("display_name", width=200)
        self.today_tree.column("process", width=140)
        self.today_tree.column("count", width=100, anchor="center")
        self.today_tree.column("status", width=80, anchor="center")

        # 双击行 → 启动/切换
        self.today_tree.bind("<Double-1>", lambda e: self._launch_selected())

        # 滚动条
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.today_tree.yview)
        self.today_tree.configure(yscrollcommand=scrollbar.set)

        self.today_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 底部启动按钮
        action_frame = tk.Frame(frame, bg=COLOR_BG)
        action_frame.pack(fill=tk.X, padx=12, pady=(0, 10))
        tk.Button(action_frame, text="▶ 切换到选中应用", font=(FONT_FAMILY, FONT_SIZE),
                  bg=COLOR_PRIMARY, fg="white", relief="flat", padx=16, pady=5,
                  cursor="hand2", command=self._launch_selected).pack(side=tk.LEFT)
        tk.Label(action_frame, text="  双击行也可以切换",
                 font=(FONT_FAMILY, FONT_SIZE_SMALL),
                 bg=COLOR_BG, fg=COLOR_TEXT_SECONDARY).pack(side=tk.LEFT, padx=8)

        # 标签颜色
        self.today_tree.tag_configure("running", foreground=COLOR_SUCCESS)
        self.today_tree.tag_configure("not_running", foreground=COLOR_TEXT_SECONDARY)
        self.today_tree.tag_configure("disabled", foreground="#bfbfbf")

        # item iid -> process name 映射
        self._today_tree_map: dict[str, str] = {}

    def _refresh_today(self):
        """刷新今日统计页面"""
        # 清空卡片
        for w in self.cards_frame.winfo_children():
            w.destroy()

        counts = self.config.get_today_counts()
        enabled = self.config.get_enabled_processes()
        total = sum(counts.get(p, 0) for p in enabled)

        # 顶部总计卡片
        self.lbl_total_today.config(text=f"今日总计: {total} 次")

        # 统计卡片
        active_count = sum(1 for p in enabled if counts.get(p, 0) > 0)
        unique_text = f"{len(enabled)} 个监控中 | {active_count} 个今日有活动"

        card = tk.Frame(self.cards_frame, bg=COLOR_CARD_BG, relief="solid", bd=1)
        card.pack(fill=tk.X, pady=4)

        tk.Label(card, text=str(total), font=(FONT_FAMILY, 28, "bold"),
                 bg=COLOR_CARD_BG, fg=COLOR_PRIMARY).pack(side=tk.LEFT, padx=20, pady=12)
        info_frame = tk.Frame(card, bg=COLOR_CARD_BG)
        info_frame.pack(side=tk.LEFT, padx=4, pady=12)
        tk.Label(info_frame, text="今日使用总次数",
                 font=(FONT_FAMILY, 11, "bold"), bg=COLOR_CARD_BG, fg=COLOR_TEXT).pack(anchor="w")
        tk.Label(info_frame, text=unique_text,
                 font=(FONT_FAMILY, FONT_SIZE_SMALL), bg=COLOR_CARD_BG,
                 fg=COLOR_TEXT_SECONDARY).pack(anchor="w")

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
            item_id = self.today_tree.insert("", tk.END, values=values, tags=(tag,))
            self._today_tree_map[item_id] = proc

    def _launch_selected(self):
        """启动/切换到 today_tree 中选中的应用"""
        sel = self.today_tree.selection()
        if not sel:
            return
        proc = self._today_tree_map.get(sel[0], "")
        if not proc:
            return
        exe_path = self.config.get_exe_path(proc)
        ok = ProcessMonitor.focus_or_launch(proc, exe_path)
        if not ok:
            messagebox.showinfo("提示", f"无法启动 {proc}，请检查程序路径。")
        # 刷新运行状态
        self._refresh_today()

    def _reset_today(self):
        if messagebox.askyesno("确认", "确定要重置今日计数吗？\n此操作不可撤销！"):
            self.config.reset_today()
            self._refresh_today()

    def _on_app_launched(self, proc_name: str, display_name: str):
        """监控回调：应用被使用（窗口被激活）时更新 UI"""
        self.root.after(0, self._refresh_today)

    # ==================== TAB 2: 历史记录 ====================

    def _build_history_tab(self):
        frame = self.tab_history
        frame.configure(bg=COLOR_BG)

        # 控制栏
        ctrl = tk.Frame(frame, bg=COLOR_BG)
        ctrl.pack(fill=tk.X, padx=12, pady=(12, 6))

        tk.Label(ctrl, text="历史统计",
                 font=(FONT_FAMILY, FONT_SIZE_TITLE, "bold"),
                 bg=COLOR_BG, fg=COLOR_TEXT).pack(side=tk.LEFT)

        # 日期范围选择
        range_frame = tk.Frame(ctrl, bg=COLOR_BG)
        range_frame.pack(side=tk.RIGHT)

        tk.Label(range_frame, text="从", bg=COLOR_BG, fg=COLOR_TEXT_SECONDARY,
                 font=(FONT_FAMILY, FONT_SIZE_SMALL)).pack(side=tk.LEFT, padx=(8, 2))
        self.entry_start = ttk.Entry(range_frame, width=12, font=(FONT_FAMILY, FONT_SIZE_SMALL))
        self.entry_start.pack(side=tk.LEFT, padx=2)
        self.entry_start.insert(0, (date.today() - timedelta(days=7)).isoformat())
        tk.Button(range_frame, text="📅", font=(FONT_FAMILY, 8), relief="flat", bd=0,
                  bg=COLOR_BG, cursor="hand2",
                  command=lambda: DatePicker(range_frame, self.entry_start)
                  ).pack(side=tk.LEFT)

        tk.Label(range_frame, text="到", bg=COLOR_BG, fg=COLOR_TEXT_SECONDARY,
                 font=(FONT_FAMILY, FONT_SIZE_SMALL)).pack(side=tk.LEFT, padx=(4, 2))
        self.entry_end = ttk.Entry(range_frame, width=12, font=(FONT_FAMILY, FONT_SIZE_SMALL))
        self.entry_end.pack(side=tk.LEFT, padx=2)
        self.entry_end.insert(0, date.today().isoformat())
        tk.Button(range_frame, text="📅", font=(FONT_FAMILY, 8), relief="flat", bd=0,
                  bg=COLOR_BG, cursor="hand2",
                  command=lambda: DatePicker(range_frame, self.entry_end)
                  ).pack(side=tk.LEFT)

        btn_query = ttk.Button(range_frame, text="查询", style="Small.TButton",
                               command=self._query_history)
        btn_query.pack(side=tk.LEFT, padx=(8, 0))

        # 快捷周期
        quick_frame = tk.Frame(frame, bg=COLOR_BG)
        quick_frame.pack(fill=tk.X, padx=12, pady=(0, 6))
        for label, days in [("今天", 0), ("最近3天", 3), ("最近7天", 7),
                            ("最近30天", 30), ("全部", -1)]:
            btn = ttk.Button(quick_frame, text=label, style="Small.TButton",
                             command=lambda d=days: self._quick_query(d))
            btn.pack(side=tk.LEFT, padx=2)

        # 汇总卡片
        self.history_summary_frame = tk.Frame(frame, bg=COLOR_BG)
        self.history_summary_frame.pack(fill=tk.X, padx=12, pady=(0, 6))

        # 详情表格
        tree_frame = tk.Frame(frame, bg=COLOR_CARD_BG)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

        columns = ("rank", "display_name", "process", "count")
        self.history_tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                         selectmode="none")

        self.history_tree.heading("rank", text="#")
        self.history_tree.heading("display_name", text="软件名称")
        self.history_tree.heading("process", text="进程名")
        self.history_tree.heading("count", text="使用次数")

        self.history_tree.column("rank", width=45, anchor="center")
        self.history_tree.column("display_name", width=220)
        self.history_tree.column("process", width=200)
        self.history_tree.column("count", width=150, anchor="center")

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL,
                                  command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scrollbar.set)

        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 默认加载最近7天
        self._quick_query(7)

    def _quick_query(self, days: int):
        """快捷日期查询"""
        end = date.today()
        if days <= 0:
            start = date(2000, 1, 1)
        else:
            start = end - timedelta(days=days - 1)
        self.entry_start.delete(0, tk.END)
        self.entry_start.insert(0, start.isoformat())
        self.entry_end.delete(0, tk.END)
        self.entry_end.insert(0, end.isoformat())
        self._query_history()

    def _query_history(self):
        start = self.entry_start.get().strip()
        end = self.entry_end.get().strip()
        if not start or not end:
            messagebox.showwarning("提示", "请输入日期范围 (YYYY-MM-DD)")
            return

        counts = self.config.get_range_counts(start, end)
        enabled = self.config.get_enabled_processes()
        display_map = {p: info["display_name"]
                       for p, info in self.config.watchlist.items()}

        # 清空
        self.history_tree.delete(*self.history_tree.get_children())
        for w in self.history_summary_frame.winfo_children():
            w.destroy()

        total_all = sum(counts.values())

        # 汇总卡片
        card = tk.Frame(self.history_summary_frame, bg=COLOR_CARD_BG, relief="solid", bd=1)
        card.pack(fill=tk.X, pady=4)
        tk.Label(card, text=str(total_all), font=(FONT_FAMILY, 28, "bold"),
                 bg=COLOR_CARD_BG, fg=COLOR_PRIMARY).pack(side=tk.LEFT, padx=20, pady=10)
        info_f = tk.Frame(card, bg=COLOR_CARD_BG)
        info_f.pack(side=tk.LEFT, padx=4, pady=10)
        tk.Label(info_f, text=f"日期范围: {start} ~ {end}",
                 font=(FONT_FAMILY, 11, "bold"), bg=COLOR_CARD_BG, fg=COLOR_TEXT).pack(anchor="w")
        tk.Label(info_f, text=f"共 {len(counts)} 款应用有记录",
                 font=(FONT_FAMILY, FONT_SIZE_SMALL), bg=COLOR_CARD_BG,
                 fg=COLOR_TEXT_SECONDARY).pack(anchor="w")

        # 填充表格
        rows = []
        for proc, cnt in counts.items():
            dname = display_map.get(proc, proc)
            rows.append((dname, proc, cnt))
        rows.sort(key=lambda x: -x[2])

        for i, (dname, proc, cnt) in enumerate(rows, 1):
            self.history_tree.insert("", tk.END, values=(i, dname, proc, cnt))

    # ==================== TAB 3: 软件管理 ====================

    def _build_manage_tab(self):
        frame = self.tab_manage
        frame.configure(bg=COLOR_BG)

        # 控制栏
        ctrl = tk.Frame(frame, bg=COLOR_BG)
        ctrl.pack(fill=tk.X, padx=12, pady=(12, 6))

        tk.Label(ctrl, text="监控软件管理",
                 font=(FONT_FAMILY, FONT_SIZE_TITLE, "bold"),
                 bg=COLOR_BG, fg=COLOR_TEXT).pack(side=tk.LEFT)

        btn_scan = ttk.Button(ctrl, text="扫描运行中应用", style="Primary.TButton",
                              command=self._scan_running_apps)
        btn_scan.pack(side=tk.RIGHT, padx=4)

        btn_add = ttk.Button(ctrl, text="＋ 手动添加", style="Small.TButton",
                             command=self._add_custom_app)
        btn_add.pack(side=tk.RIGHT, padx=4)

        btn_refresh = ttk.Button(ctrl, text="刷新", style="Small.TButton",
                                 command=self._refresh_manage)
        btn_refresh.pack(side=tk.RIGHT, padx=4)

        # 提示文字
        hint = tk.Label(frame,
                        text="💡 提示：启用/禁用的修改即时生效。默认软件不可删除，但可以禁用或重命名。",
                        font=(FONT_FAMILY, FONT_SIZE_SMALL),
                        bg=COLOR_BG, fg=COLOR_TEXT_SECONDARY, anchor="w")
        hint.pack(fill=tk.X, padx=12, pady=(0, 6))

        # 搜索框
        search_frame = tk.Frame(frame, bg=COLOR_BG)
        search_frame.pack(fill=tk.X, padx=12, pady=(0, 6))
        tk.Label(search_frame, text="搜索:", bg=COLOR_BG,
                 font=(FONT_FAMILY, FONT_SIZE_SMALL)).pack(side=tk.LEFT, padx=(0, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self._filter_manage_list())
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side=tk.LEFT)

        # 列表区域（Canvas + Scrollbar + Frame 实现滚动）
        self.manage_canvas = tk.Canvas(frame, bg=COLOR_BG, highlightthickness=0)
        manage_scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.manage_canvas.yview)
        self.manage_list_frame = tk.Frame(self.manage_canvas, bg=COLOR_BG)

        self.manage_list_frame.bind("<Configure>",
                                    lambda e: self.manage_canvas.configure(
                                        scrollregion=self.manage_canvas.bbox("all")))
        self.manage_canvas.create_window((0, 0), window=self.manage_list_frame, anchor="nw")
        self.manage_canvas.configure(yscrollcommand=manage_scrollbar.set)

        self.manage_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        manage_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 12))

        # 绑定鼠标滚轮
        self.manage_canvas.bind("<Enter>", lambda e: self._bind_mousewheel(e))
        self.manage_canvas.bind("<Leave>", lambda e: self._unbind_mousewheel(e))

        self._all_manage_rows = []

    def _bind_mousewheel(self, event):
        self.manage_canvas.bind_all("<MouseWheel>",
                                    lambda e: self.manage_canvas.yview_scroll(
                                        int(-1 * (e.delta / 120)), "units"))

    def _unbind_mousewheel(self, event):
        self.manage_canvas.unbind_all("<MouseWheel>")

    def _refresh_manage(self):
        """刷新软件管理列表"""
        for w in self.manage_list_frame.winfo_children():
            w.destroy()
        self._all_manage_rows = []

        items = self.config.get_all_processes()
        self._all_manage_rows = items
        self._render_manage_rows(items)

    def _filter_manage_list(self):
        query = self.search_var.get().lower().strip()
        if not query:
            self._render_manage_rows(self._all_manage_rows)
        else:
            filtered = [item for item in self._all_manage_rows
                        if query in item["display_name"].lower()
                        or query in item["process"].lower()]
            self._render_manage_rows(filtered)

    def _render_manage_rows(self, items):
        for w in self.manage_list_frame.winfo_children():
            w.destroy()

        for item in items:
            self._create_manage_row(self.manage_list_frame, item)

        # 更新 canvas 宽度
        self.manage_list_frame.update_idletasks()
        self.manage_canvas.configure(scrollregion=self.manage_canvas.bbox("all"))

    def _create_manage_row(self, parent, item: dict):
        """创建单行管理卡片"""
        proc = item["process"]
        dname = item["display_name"]
        enabled = item["enabled"]
        is_default = item["is_default"]

        row = tk.Frame(parent, bg=COLOR_CARD_BG, relief="solid", bd=1)
        row.pack(fill=tk.X, pady=2, padx=2)

        # 图标占位
        icon_label = tk.Label(row, text="📱", font=(FONT_FAMILY, 18), bg=COLOR_CARD_BG)
        icon_label.pack(side=tk.LEFT, padx=(12, 8), pady=8)

        # 信息
        info = tk.Frame(row, bg=COLOR_CARD_BG)
        info.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=6)

        name_text = dname
        if not enabled:
            name_text += " (已禁用)"
        name_color = COLOR_TEXT if enabled else COLOR_TEXT_SECONDARY
        tk.Label(info, text=name_text,
                 font=(FONT_FAMILY, 11, "bold"), bg=COLOR_CARD_BG,
                 fg=name_color).pack(anchor="w")
        tk.Label(info, text=f"进程: {proc}" + (" | 默认" if is_default else " | 自定义"),
                 font=(FONT_FAMILY, FONT_SIZE_SMALL), bg=COLOR_CARD_BG,
                 fg=COLOR_TEXT_SECONDARY).pack(anchor="w")

        # 操作按钮
        btn_frame = tk.Frame(row, bg=COLOR_CARD_BG)
        btn_frame.pack(side=tk.RIGHT, padx=8, pady=8)

        # 启用/禁用
        toggle_text = "禁用" if enabled else "启用"
        toggle_style = "Small.TButton" if enabled else "Primary.TButton"
        ttk.Button(btn_frame, text=toggle_text, style=toggle_style,
                   command=lambda p=proc: self._toggle_app(p)).pack(side=tk.LEFT, padx=2)

        # 重命名
        ttk.Button(btn_frame, text="重命名", style="Small.TButton",
                   command=lambda p=proc, d=dname: self._rename_app(p, d)).pack(side=tk.LEFT, padx=2)

        # 删除（仅自定义）
        if not is_default:
            ttk.Button(btn_frame, text="删除", style="Danger.TButton",
                       command=lambda p=proc: self._delete_app(p)).pack(side=tk.LEFT, padx=2)

    def _toggle_app(self, proc: str):
        new_state = self.config.toggle_enabled(proc)
        self.monitor.refresh_baseline()
        self._refresh_manage()
        self._refresh_today()

    def _rename_app(self, proc: str, current_name: str):
        new_name = simpledialog.askstring("重命名", f"为 {proc} 输入新显示名称:",
                                          initialvalue=current_name, parent=self.root)
        if new_name and new_name.strip():
            self.config.rename_display(proc, new_name.strip())
            self._refresh_manage()
            self._refresh_today()

    def _delete_app(self, proc: str):
        dname = self.config.watchlist.get(proc, {}).get("display_name", proc)
        if messagebox.askyesno("确认删除", f"确定要删除自定义软件 \"{dname}\" ({proc}) 吗？"):
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
            messagebox.showinfo("扫描结果", "没有发现新的可监控应用。\n所有运行中的应用已在监控列表中。")
            return

        # 弹出选择对话框
        self._show_scan_dialog(new_apps)

    def _show_scan_dialog(self, apps: dict):
        """显示扫描结果对话框，勾选要添加的应用"""
        dialog = tk.Toplevel(self.root)
        dialog.title("扫描运行中应用")
        dialog.geometry("520x420")
        dialog.configure(bg=COLOR_BG)
        dialog.transient(self.root)
        dialog.grab_set()

        # 居中
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 520) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 420) // 2
        dialog.geometry(f"+{x}+{y}")

        # 标题
        header = tk.Frame(dialog, bg=COLOR_BG)
        header.pack(fill=tk.X, padx=16, pady=(12, 8))
        tk.Label(header, text=f"发现 {len(apps)} 个未监控的应用",
                 font=(FONT_FAMILY, 13, "bold"), bg=COLOR_BG, fg=COLOR_TEXT).pack(side=tk.LEFT)

        # 全选/取消
        sel_frame = tk.Frame(dialog, bg=COLOR_BG)
        sel_frame.pack(fill=tk.X, padx=16, pady=(0, 6))

        def select_all():
            for var in check_vars.values():
                var.set(True)

        def deselect_all():
            for var in check_vars.values():
                var.set(False)

        tk.Button(sel_frame, text="全选", font=(FONT_FAMILY, FONT_SIZE_SMALL),
                  bg=COLOR_BORDER, relief="flat", padx=8, pady=2,
                  command=select_all).pack(side=tk.LEFT, padx=(0, 4))
        tk.Button(sel_frame, text="取消全选", font=(FONT_FAMILY, FONT_SIZE_SMALL),
                  bg=COLOR_BORDER, relief="flat", padx=8, pady=2,
                  command=deselect_all).pack(side=tk.LEFT)

        # 可滚动列表
        canvas = tk.Canvas(dialog, bg=COLOR_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(dialog, orient=tk.VERTICAL, command=canvas.yview)
        list_frame = tk.Frame(canvas, bg=COLOR_BG)

        list_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=list_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0), pady=(0, 8))
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 12), pady=(0, 8))

        # 绑定滚轮
        canvas.bind("<Enter>", lambda e: canvas.bind_all(
            "<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        # 创建勾选项
        check_vars = {}
        proc_names = sorted(apps.keys(), key=lambda k: apps[k]["display"])

        for proc_name in proc_names:
            info = apps[proc_name]
            var = tk.BooleanVar(value=True)
            check_vars[proc_name] = var

            row = tk.Frame(list_frame, bg=COLOR_CARD_BG, relief="solid", bd=1)
            row.pack(fill=tk.X, pady=1, padx=2)

            cb = tk.Checkbutton(row, variable=var, bg=COLOR_CARD_BG,
                                activebackground=COLOR_CARD_BG)
            cb.pack(side=tk.LEFT, padx=(8, 4), pady=6)

            info_f = tk.Frame(row, bg=COLOR_CARD_BG)
            info_f.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=4)
            tk.Label(info_f, text=info["display"],
                     font=(FONT_FAMILY, FONT_SIZE, "bold"), bg=COLOR_CARD_BG,
                     fg=COLOR_TEXT).pack(anchor="w")
            tk.Label(info_f, text=f"进程: {proc_name}",
                     font=(FONT_FAMILY, FONT_SIZE_SMALL), bg=COLOR_CARD_BG,
                     fg=COLOR_TEXT_SECONDARY).pack(anchor="w")

        # 底部按钮
        btn_frame = tk.Frame(dialog, bg=COLOR_BG)
        btn_frame.pack(fill=tk.X, padx=16, pady=(6, 12))

        def do_import():
            count = 0
            for proc_name, var in check_vars.items():
                if var.get():
                    info = apps[proc_name]
                    self.config.add_custom(proc_name, info["display"], info.get("path", ""))
                    count += 1
            if count > 0:
                self.monitor.refresh_baseline()
                self._refresh_manage()
                self._refresh_today()
                messagebox.showinfo("导入完成", f"已添加 {count} 个应用。", parent=dialog)
            dialog.destroy()

        tk.Button(btn_frame, text="添加选中", font=(FONT_FAMILY, FONT_SIZE),
                  bg=COLOR_PRIMARY, fg="white", relief="flat", padx=20, pady=5,
                  command=do_import).pack(side=tk.RIGHT, padx=(4, 0))
        tk.Button(btn_frame, text="取消", font=(FONT_FAMILY, FONT_SIZE),
                  bg=COLOR_BORDER, fg=COLOR_TEXT, relief="flat", padx=20, pady=5,
                  command=dialog.destroy).pack(side=tk.RIGHT)

    def _add_custom_app(self):
        """弹出对话框添加自定义软件"""
        dialog = tk.Toplevel(self.root)
        dialog.title("添加自定义软件")
        dialog.geometry("480x280")
        dialog.resizable(False, False)
        dialog.configure(bg=COLOR_CARD_BG)
        dialog.transient(self.root)
        dialog.grab_set()

        # 居中
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 480) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 280) // 2
        dialog.geometry(f"+{x}+{y}")

        # 内容
        pad_frame = tk.Frame(dialog, bg=COLOR_CARD_BG)
        pad_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

        tk.Label(pad_frame, text="添加要监控的软件",
                 font=(FONT_FAMILY, 14, "bold"), bg=COLOR_CARD_BG,
                 fg=COLOR_TEXT).pack(anchor="w", pady=(0, 12))

        # 选择路径按钮（醒目）
        path_frame = tk.Frame(pad_frame, bg=COLOR_CARD_BG)
        path_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Button(path_frame, text="📁 选择程序文件 (.exe)", font=(FONT_FAMILY, FONT_SIZE),
                  bg=COLOR_PRIMARY, fg="white", relief="flat", padx=12, pady=6,
                  command=lambda: self._browse_exe(dialog, entry_proc, entry_name)).pack()

        # 进程名
        tk.Label(pad_frame, text="进程名称 (自动从路径提取):",
                 font=(FONT_FAMILY, FONT_SIZE), bg=COLOR_CARD_BG,
                 fg=COLOR_TEXT).pack(anchor="w")
        entry_proc = ttk.Entry(pad_frame, width=45)
        entry_proc.pack(fill=tk.X, pady=(2, 4))

        # 显示名称
        tk.Label(pad_frame, text="显示名称:",
                 font=(FONT_FAMILY, FONT_SIZE), bg=COLOR_CARD_BG,
                 fg=COLOR_TEXT).pack(anchor="w")
        entry_name = ttk.Entry(pad_frame, width=45)
        entry_name.pack(fill=tk.X, pady=(2, 10))

        # 按钮
        btn_frame = tk.Frame(pad_frame, bg=COLOR_CARD_BG)
        btn_frame.pack(fill=tk.X)

        def do_add():
            proc = entry_proc.get().strip()
            name = entry_name.get().strip()
            if not proc:
                messagebox.showwarning("提示", "请选择程序或输入进程名称", parent=dialog)
                return
            if not name:
                name = proc
            exe_path = getattr(dialog, "_exe_path", "")
            self.config.add_custom(proc, name, exe_path)
            self.monitor.refresh_baseline()
            self._refresh_manage()
            self._refresh_today()
            dialog.destroy()

        tk.Button(btn_frame, text="添加", font=(FONT_FAMILY, FONT_SIZE),
                  bg=COLOR_PRIMARY, fg="white", relief="flat", padx=16, pady=4,
                  command=do_add).pack(side=tk.RIGHT, padx=(4, 0))
        tk.Button(btn_frame, text="取消", font=(FONT_FAMILY, FONT_SIZE),
                  bg=COLOR_BORDER, fg=COLOR_TEXT, relief="flat", padx=16, pady=4,
                  command=dialog.destroy).pack(side=tk.RIGHT)

        entry_proc.bind("<Return>", lambda e: do_add())
        entry_name.bind("<Return>", lambda e: do_add())

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
        frame.configure(bg=COLOR_BG)

        tk.Label(frame, text="应用设置",
                 font=(FONT_FAMILY, FONT_SIZE_TITLE, "bold"),
                 bg=COLOR_BG, fg=COLOR_TEXT).pack(anchor="w", padx=12, pady=(12, 6))

        # 设置卡片
        card = tk.Frame(frame, bg=COLOR_CARD_BG, relief="solid", bd=1)
        card.pack(fill=tk.X, padx=12, pady=6)

        # 最小化到托盘
        self.tray_var = tk.BooleanVar(value=self.config.get_setting("minimize_to_tray", True))
        self._setting_row(card, "最小化到系统托盘",
                          "关闭窗口时最小化到系统托盘而不是退出",
                          self.tray_var, self._on_tray_setting_change)

        # 开机自启
        self.startup_var = tk.BooleanVar(value=self.config.get_startup_enabled())
        self._setting_row(card, "开机自启动",
                          "电脑开机时自动在后台启动监控",
                          self.startup_var, self._on_startup_setting_change)

        # 启动通知
        self.notify_var = tk.BooleanVar(value=self.config.get_setting("show_notifications", True))
        self._setting_row(card, "使用通知",
                          "切换到应用窗口时弹出通知",
                          self.notify_var, self._on_notify_setting_change)

        # 轮询间隔
        interval_card = tk.Frame(frame, bg=COLOR_CARD_BG, relief="solid", bd=1)
        interval_card.pack(fill=tk.X, padx=12, pady=6)

        interval_header = tk.Frame(interval_card, bg=COLOR_CARD_BG)
        interval_header.pack(fill=tk.X, padx=16, pady=(12, 4))
        tk.Label(interval_header, text="检测间隔",
                 font=(FONT_FAMILY, FONT_SIZE, "bold"), bg=COLOR_CARD_BG,
                 fg=COLOR_TEXT).pack(side=tk.LEFT)
        self.interval_label = tk.Label(interval_header,
                                       text=f"{self.config.get_setting('poll_interval_ms', 500)} ms",
                                       font=(FONT_FAMILY, FONT_SIZE_SMALL),
                                       bg=COLOR_CARD_BG, fg=COLOR_PRIMARY)
        self.interval_label.pack(side=tk.RIGHT)

        tk.Label(interval_card,
                 text="越短越灵敏，100 ms ~ 5000 ms 无极调节",
                 font=(FONT_FAMILY, FONT_SIZE_SMALL),
                 bg=COLOR_CARD_BG, fg=COLOR_TEXT_SECONDARY).pack(anchor="w", padx=16, pady=(0, 6))

        self.interval_scale = tk.Scale(interval_card, from_=100, to=5000, resolution=100,
                                       orient=tk.HORIZONTAL, bg=COLOR_CARD_BG,
                                       highlightthickness=0, length=400,
                                       command=self._on_interval_change)
        current_interval = self.config.get_setting("poll_interval_ms", 500)
        self.interval_scale.set(current_interval)
        self.interval_scale.pack(padx=16, pady=(0, 12), anchor="w")

        # 数据管理
        data_card = tk.Frame(frame, bg=COLOR_CARD_BG, relief="solid", bd=1)
        data_card.pack(fill=tk.X, padx=12, pady=6)

        tk.Label(data_card, text="数据管理",
                 font=(FONT_FAMILY, FONT_SIZE, "bold"),
                 bg=COLOR_CARD_BG, fg=COLOR_TEXT).pack(anchor="w", padx=16, pady=(12, 4))

        tk.Label(data_card, text=f"数据文件位置: {DATA_FILE}",
                 font=(FONT_FAMILY, FONT_SIZE_SMALL),
                 bg=COLOR_CARD_BG, fg=COLOR_TEXT_SECONDARY,
                 wraplength=700).pack(anchor="w", padx=16, pady=(0, 6))

        btn_frame = tk.Frame(data_card, bg=COLOR_CARD_BG)
        btn_frame.pack(anchor="w", padx=16, pady=(0, 12))

        ttk.Button(btn_frame, text="清除今日数据", style="Small.TButton",
                   command=self._reset_today).pack(side=tk.LEFT, padx=(0, 4))

        ttk.Button(btn_frame, text="清除全部历史数据", style="Danger.TButton",
                   command=self._reset_all_data).pack(side=tk.LEFT)

        # 关于
        about_card = tk.Frame(frame, bg=COLOR_CARD_BG, relief="solid", bd=1)
        about_card.pack(fill=tk.X, padx=12, pady=6)

        tk.Label(about_card, text="关于 AppCounter",
                 font=(FONT_FAMILY, FONT_SIZE, "bold"),
                 bg=COLOR_CARD_BG, fg=COLOR_TEXT).pack(anchor="w", padx=16, pady=(12, 4))
        tk.Label(about_card, text="版本 1.0.0 | 监控电脑软件使用次数",
                 font=(FONT_FAMILY, FONT_SIZE_SMALL),
                 bg=COLOR_CARD_BG, fg=COLOR_TEXT_SECONDARY).pack(anchor="w", padx=16, pady=(0, 10))

    def _setting_row(self, parent, title: str, desc: str, var: tk.BooleanVar,
                     command=None):
        row = tk.Frame(parent, bg=COLOR_CARD_BG)
        row.pack(fill=tk.X, padx=16, pady=8)
        info = tk.Frame(row, bg=COLOR_CARD_BG)
        info.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(info, text=title, font=(FONT_FAMILY, FONT_SIZE, "bold"),
                 bg=COLOR_CARD_BG, fg=COLOR_TEXT).pack(anchor="w")
        tk.Label(info, text=desc, font=(FONT_FAMILY, FONT_SIZE_SMALL),
                 bg=COLOR_CARD_BG, fg=COLOR_TEXT_SECONDARY).pack(anchor="w")
        cb = ttk.Checkbutton(row, variable=var, command=command)
        cb.pack(side=tk.RIGHT)

    def _on_tray_setting_change(self):
        self.config.set_setting("minimize_to_tray", self.tray_var.get())

    def _on_notify_setting_change(self):
        self.config.set_setting("show_notifications", self.notify_var.get())

    def _on_startup_setting_change(self):
        if self.startup_var.get():
            ok = self.config.enable_startup()
            if not ok:
                messagebox.showwarning("提示", "设置开机自启失败，请检查权限。")
                self.startup_var.set(False)
        else:
            self.config.disable_startup()

    def _on_interval_change(self, value):
        ms = int(float(value))
        self.config.set_setting("poll_interval_ms", ms)
        self.interval_label.config(text=f"{ms} ms")

    def _reset_all_data(self):
        if messagebox.askyesno("⚠ 确认清除", "确定要清除全部历史计数数据吗？\n此操作不可撤销！"):
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
