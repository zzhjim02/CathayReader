#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cathay Reader v1.0.0
CathayOCR 配套双栏同步阅读器
"""

import sys
import os

# ====== 环境变量修复（必须在任何导入之前）======
# 这些环境变量能解决 PyQt5 在 Windows 上的各种闪退问题：
# - DLL 冲突（PyQt5 vs PyMuPDF/OpenCV 的 Qt 版本不同）
# - GPU 驱动兼容性（Qt 渲染崩溃）
# - 平台插件找不到

os.environ.setdefault('QT_QPA_PLATFORM_PLUGIN_PATH', '')
os.environ.setdefault('QT_OPENGL', 'software')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
os.environ.setdefault('QT_QPA_PLATFORM', 'windows')

# 防止 Qt 在 4K 屏上缩放混乱
os.environ.setdefault('QT_AUTO_SCREEN_SCALE_FACTOR', '0')
os.environ.setdefault('QT_SCALE_FACTOR', '1')

# Python 3.8+ DLL 搜索路径修复
if hasattr(os, 'add_dll_directory') and sys.platform == 'win32':
    try:
        # 先找到 PyQt5 的 DLL 目录，优先加入搜索路径
        import importlib.util
        spec = importlib.util.find_spec('PyQt5')
        if spec and spec.submodule_search_locations:
            pyqt5_dir = list(spec.submodule_search_locations)[0]
            for subdir in ['', 'Qt5', 'Qt5\\bin']:
                d = os.path.join(pyqt5_dir, subdir)
                if os.path.isdir(d):
                    os.add_dll_directory(d)
    except Exception:
        pass

# ====== 主程序 ======

def main():
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'crash_log.txt')

    # 清空旧日志
    try:
        open(log_path, 'w').close()
    except Exception:
        pass

    try:
        # ---- 先导入 PyQt5（必须先于 fitz） ----
        from PyQt5.QtWidgets import QApplication
        from PyQt5.QtCore import QTimer

        # ---- 再导入业务模块 ----
        from ui_main import MainWindow

    except ImportError as e:
        err = f"缺少依赖: {e}"
        print(err)
        print("请执行: pip install PyMuPDF PyQt5")
        input("按 Enter 键退出...")
        sys.exit(1)

    # ---- 阻止欢迎弹窗（某些 Windows 系统弹窗就崩）----
    MainWindow._welcome_disabled = True

    # ---- 最小化启动 ----
    from PyQt5.QtGui import QIcon
    # PyInstaller 打包后图标在 sys._MEIPASS 下
    def _icon_path(name):
        if getattr(sys, 'frozen', False):
            return os.path.join(sys._MEIPASS, name)
        return name
    app = QApplication(sys.argv)
    app.setApplicationName("Cathay Reader")
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(_icon_path('CathayReader.ico')))
    app.setStyleSheet("")  # 不设全局样式

    try:
        window = MainWindow()
        # 延迟加载（确保窗口先显示出来）
        def _delayed_open():
            try:
                if len(sys.argv) > 1:
                    fp = sys.argv[1]
                    if os.path.isdir(fp):
                        window._load_directory(fp)
                    elif os.path.isfile(fp) and fp.lower().endswith(('.pdf', '.txt')):
                        window._open_file(fp)
            except Exception as e:
                _write_log(log_path, f"延迟打开失败: {e}")
        QTimer.singleShot(200, _delayed_open)
        window.show()
        sys.exit(app.exec_())
    except Exception as e:
        _write_log(log_path, f"启动失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        print(f"\n异常: {e}")
        print(f"详情: {log_path}")
        input("按 Enter 键退出...")
        sys.exit(1)


def _write_log(path, msg):
    import traceback
    try:
        with open(path, 'a', encoding='utf-8') as f:
            f.write(msg + '\n')
            traceback.print_exc(file=f)
    except Exception:
        pass


if __name__ == "__main__":
    main()
