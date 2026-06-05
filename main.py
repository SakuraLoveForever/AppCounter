"""
AppCounter - 电脑软件使用次数监控工具
===============================
监控微信、QQ 等常见软件以及自定义软件的打开次数。

用法:
    python main.py              # 正常启动（GUI + 后台监控）
    python main.py --console    # 仅后台监控（无 GUI，适合开机自启）
    python main.py --reset      # 重置所有数据
"""

import argparse
import sys
import os

# 确保能找到同目录的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import ConfigManager, DATA_FILE
from monitor import ProcessMonitor


def run_gui():
    """启动完整 GUI 模式"""
    from gui import AppCounterGUI

    config = ConfigManager()
    monitor = ProcessMonitor(config)

    app = AppCounterGUI(config, monitor)
    app.run()


def run_console():
    """仅后台监控模式（无 GUI）"""
    import time
    import signal

    config = ConfigManager()
    monitor = ProcessMonitor(config)

    print("=" * 50)
    print("  AppCounter - 后台监控模式")
    print("=" * 50)
    print(f"  监控进程数: {len(config.get_enabled_processes())}")
    print(f"  数据文件: {DATA_FILE}")
    print(f"  按 Ctrl+C 退出")
    print("=" * 50)

    # 注册回调：打印使用信息
    def on_launch(proc_name, display_name):
        print(f"  [使用] {display_name} ({proc_name})")

    monitor.add_callback(on_launch)
    monitor.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n  正在退出...")
    finally:
        monitor.stop()
        config.save()
        print("  已退出。")


def main():
    parser = argparse.ArgumentParser(
        description="AppCounter - 电脑软件使用次数监控工具",
    )
    parser.add_argument(
        "--console", "-c",
        action="store_true",
        help="仅后台监控模式（无 GUI）",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="重置所有数据后退出",
    )
    args = parser.parse_args()

    if args.reset:
        config = ConfigManager()
        config.reset_all()
        print("所有数据已重置。")
        return

    if args.console:
        run_console()
    else:
        run_gui()


if __name__ == "__main__":
    main()
