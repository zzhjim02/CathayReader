# -*- coding: utf-8 -*-
"""
Cathay Reader 主窗口
双栏分屏阅读器，支持 PDF 和 TXT 同步滚动。
"""

import os
from typing import Optional

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QKeySequence
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QSplitter, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QToolBar, QAction, QActionGroup,
    QStatusBar, QFileDialog, QMessageBox, QShortcut,
    QApplication, QToolButton, QInputDialog, QDialog, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QDockWidget, QTreeWidget, QTreeWidgetItem
)

from file_matcher import FileMatcher, FilePair, identify_txt_variant, identify_pdf_variant
from pdf_view import PdfViewPanel
from txt_view import TxtViewPanel


class MainWindow(QMainWindow):
    APP_NAME = "Cathay Reader"
    APP_VERSION = "1.0.0"

    def __init__(self):
        super().__init__()
        self._file_matcher = None
        self._current_index = 0
        self._syncing = False
        self._sync_to = 0  # 正在同步的目标页码
        self._search_active = False
        self.setAcceptDrops(True)  # 启用拖放
        self._init_ui()
        self._setup_shortcuts()
        # 默认不显示欢迎弹窗（闪退兼容）
        if not getattr(self.__class__, '_welcome_disabled', False):
            self._show_welcome()

    def _init_ui(self):
        self.setWindowTitle(self.APP_NAME)
        self.setMinimumSize(1000, 650)
        self.resize(1300, 800)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- 先创建核心面板 ---
        self._splitter = QSplitter(Qt.Horizontal)
        self._pdf_panel = PdfViewPanel()
        self._txt_panel = TxtViewPanel()
        self._txt_panel.configSuffixRequested.connect(self._show_suffix_config)
        self._txt_panel.openFileRequested.connect(self._on_open_file)
        self._pdf_panel.openFileRequested.connect(self._on_open_file)
        self._splitter.addWidget(self._pdf_panel)
        self._splitter.addWidget(self._txt_panel)
        self._splitter.setSizes([640, 520])
        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 1)

        # --- 工具栏 ---
        self._create_toolbar()
        main_layout.addWidget(self._toolbar)

        # --- 信息栏 ---
        self._create_info_bar()
        main_layout.addWidget(self._info_bar)

        # --- 分栏 ---
        main_layout.addWidget(self._splitter, 1)

        # --- 状态栏 ---
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_label = QLabel("就绪")
        self._page_label = QLabel("")
        self._status_bar.addWidget(self._status_label, 1)
        self._status_bar.addPermanentWidget(self._page_label)

        # --- 信号 ---
        self._pdf_panel.pageChanged.connect(self._on_pdf_page_changed)
        self._txt_panel.pageChanged.connect(self._on_txt_page_changed)

        # --- 目录侧栏 ---
        self._create_toc_dock()

    def _create_toolbar(self):
        self._toolbar = QToolBar("主工具栏")
        self._toolbar.setMovable(False)
        tb_style = """
            QToolBar { background: #2c3e50; padding: 3px 6px; spacing: 4px; }
            QToolButton {
                color: white; background: #34495e;
                border: 1px solid #4a6278; padding: 3px 10px;
                border-radius: 3px; font-size: 12px;
            }
            QToolButton:hover { background: #4a6278; }
            QToolButton:pressed { background: #1a252f; }
        """
        self._toolbar.setStyleSheet(tb_style)
        self.addToolBar(self._toolbar)

        def btn(text, slot):
            a = QAction(text, self)
            a.triggered.connect(slot)
            self._toolbar.addAction(a)
            return a

        btn("打开文件夹 [Ctrl+O]", self._on_open_directory)
        btn("打开文件 [Ctrl+Shift+O]", self._on_open_file)
        self._toolbar.addSeparator()
        btn("放大 +", self._pdf_panel.zoom_in)
        btn("缩小 -", self._pdf_panel.zoom_out)
        btn("适应宽度", self._pdf_panel.zoom_fit_width)
        self._toolbar.addSeparator()
        btn("目录 [Ctrl+T]", self._toggle_toc)
        self._toolbar.addSeparator()
        btn("上页 [Left]", self._go_prev_page)
        btn("下页 [Right]", self._go_next_page)
        self._toolbar.addSeparator()
        btn("上一册", self._go_prev_volume)
        btn("下一册", self._go_next_volume)
        self._toolbar.addSeparator()
        btn("设为默认", self._register_app)
        btn("关于", self._show_about)

    def _create_info_bar(self):
        self._info_bar = QWidget()
        self._info_bar.setStyleSheet("background:#f0f3f5; border-bottom:1px solid #d0d5da;")
        layout = QHBoxLayout(self._info_bar)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(8)

        self._path_label = QLabel("[未选择目录]")
        self._path_label.setStyleSheet("color:#555; font-size:12px;")
        self._path_label.setWordWrap(True)
        layout.addWidget(self._path_label, 1)

        # 册选择
        layout.addWidget(QLabel("册:"))
        self._volume_combo = QComboBox()
        self._volume_combo.setMinimumWidth(100)
        self._volume_combo.setStyleSheet("QComboBox { padding:2px 6px; border:1px solid #bbb; border-radius:3px; background:white; color:black; } QComboBox::drop-down { width:22px; } QComboBox QAbstractItemView { color:black; background:white; }")
        self._volume_combo.currentIndexChanged.connect(self._on_volume_changed)
        layout.addWidget(self._volume_combo)

        # 文本模式
        layout.addWidget(QLabel("文本:"))
        self._txt_mode_combo = QComboBox()
        self._txt_mode_combo.addItems(["原文", "繁转简"])
        self._txt_mode_combo.setStyleSheet("QComboBox { padding:2px 6px; border:1px solid #bbb; border-radius:3px; background:white; color:black; } QComboBox::drop-down { width:22px; } QComboBox QAbstractItemView { color:black; background:white; }")
        self._txt_mode_combo.currentIndexChanged.connect(self._on_txt_mode_changed)
        layout.addWidget(self._txt_mode_combo)

        # OCR 版本选择
        layout.addWidget(QLabel("OCR:"))
        self._ocr_combo = QComboBox()
        self._ocr_combo.setMinimumWidth(120)
        self._ocr_combo.setStyleSheet("QComboBox { padding:2px 6px; border:1px solid #bbb; border-radius:3px; background:white; color:black; } QComboBox::drop-down { width:22px; } QComboBox QAbstractItemView { color:black; background:white; }")
        self._ocr_combo.currentIndexChanged.connect(self._on_ocr_changed)
        layout.addWidget(self._ocr_combo)

        # 字号
        layout.addWidget(QLabel("字号:"))
        self._font_size_combo = QComboBox()
        self._font_size_combo.addItems(["10", "11", "12", "14", "16", "18", "20"])
        self._font_size_combo.setCurrentText("11")
        self._font_size_combo.setStyleSheet("QComboBox { padding:2px 6px; border:1px solid #bbb; border-radius:3px; background:white; color:black; } QComboBox::drop-down { width:22px; } QComboBox QAbstractItemView { color:black; background:white; }")
        self._font_size_combo.currentTextChanged.connect(self._on_font_size_changed)
        layout.addWidget(self._font_size_combo)

        # 搜索按钮
        self._search_btn = QPushButton("搜索 [Ctrl+F]")
        self._search_btn.setStyleSheet(
            "padding:2px 8px; border:1px solid #5a8; border-radius:3px; "
            "background:#e8f5e9; color:#2e7d32;")
        self._search_btn.clicked.connect(self._toggle_search)
        layout.addWidget(self._search_btn)

        # 复制PDF文字按钮
        self._copy_btn = QPushButton("复制PDF [Ctrl+Shift+C]")
        self._copy_btn.setStyleSheet(
            "padding:2px 8px; border:1px solid #a7a; border-radius:3px; "
            "background:#f3e5f5; color:#6a1b9a;")
        self._copy_btn.clicked.connect(self._copy_pdf_text)
        layout.addWidget(self._copy_btn)



        # 后缀配置按钮
        self._suffix_btn = QPushButton("后缀设置")
        self._suffix_btn.setFixedWidth(60)
        self._suffix_btn.setToolTip("添加PDF与TXT的自定义后缀配对，让软件能识别更多格式的文件")
        self._suffix_btn.setStyleSheet(
            "padding:2px 6px; border:1px solid #aaa; border-radius:3px; background:#f5f0e8;")
        self._suffix_btn.clicked.connect(self._show_suffix_config)
        layout.addWidget(self._suffix_btn)

        # 页码跳转
        layout.addWidget(QLabel("页码:"))
        self._page_spin = QComboBox()
        self._page_spin.setEditable(True)
        self._page_spin.setMinimumWidth(70)
        self._page_spin.setStyleSheet("QComboBox { padding:2px 6px; border:1px solid #bbb; border-radius:3px; background:white; color:black; } QComboBox::drop-down { width:22px; } QComboBox QAbstractItemView { color:black; background:white; }")
        self._page_spin.lineEdit().returnPressed.connect(self._on_page_jump)
        self._page_spin.activated[str].connect(lambda _: self._on_page_jump())
        layout.addWidget(self._page_spin)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+O"), self, self._on_open_directory)
        QShortcut(QKeySequence("Ctrl+Shift+O"), self, self._on_open_file)
        QShortcut(QKeySequence("Left"), self, self._go_prev_page)
        QShortcut(QKeySequence("Right"), self, self._go_next_page)
        QShortcut(QKeySequence("PageUp"), self, self._go_prev_page)
        QShortcut(QKeySequence("PageDown"), self, self._go_next_page)
        QShortcut(QKeySequence("Ctrl++"), self, self._pdf_panel.zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self, self._pdf_panel.zoom_out)
        QShortcut(QKeySequence("Ctrl+0"), self, self._pdf_panel.zoom_fit_width)
        QShortcut(QKeySequence("Ctrl+F"), self, self._toggle_search)
        QShortcut(QKeySequence("Ctrl+G"), self, self._on_search_next)
        QShortcut(QKeySequence("Ctrl+Shift+G"), self, self._on_search_prev)
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, self._copy_pdf_text)
        QShortcut(QKeySequence("Ctrl+Shift+D"), self, self._copy_full_page_text)
        QShortcut(QKeySequence("Ctrl+T"), self, self._toggle_toc)

    # ── 目录侧栏 ──

    def _create_toc_dock(self):
        self._toc_dock = QDockWidget("PDF 目录", self)
        self._toc_dock.setObjectName("TocDock")
        self._toc_dock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        self._toc_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self._toc_tree = QTreeWidget()
        self._toc_tree.setHeaderLabel("目录")
        self._toc_tree.setIndentation(16)
        self._toc_tree.setAnimated(True)
        self._toc_tree.setStyleSheet("""
            QTreeWidget {
                background: #fafafa; border: none;
                font-size: 12px; color: #333;
            }
            QTreeWidget::item {
                padding: 4px 6px;
                border-bottom: 1px solid #eee;
            }
            QTreeWidget::item:hover {
                background: #e3f2fd;
            }
            QTreeWidget::item:selected {
                background: #bbdefb; color: #1565c0;
            }
        """)
        self._toc_tree.setMinimumWidth(180)
        self._toc_tree.setMaximumWidth(400)
        self._toc_tree.itemClicked.connect(self._on_toc_clicked)
        self._toc_dock.setWidget(self._toc_tree)

        self.addDockWidget(Qt.LeftDockWidgetArea, self._toc_dock)
        self._toc_dock.hide()  # 默认隐藏

        # 目录侧栏显隐时调整分栏宽度
        self._toc_dock.visibilityChanged.connect(self._on_toc_visibility_changed)

    def _on_toc_visibility_changed(self, visible):
        """TOC 侧栏显示/隐藏后重新分配分栏宽度，避免右栏被挤压"""
        QTimer.singleShot(0, self._adjust_splitter_sizes)

    def _adjust_splitter_sizes(self):
        """重新计算分栏宽度：PDF 至少留 450px，TXT 占余下空间"""
        total_w = self._splitter.width()
        min_pdf = 450
        if total_w > min_pdf + 100:
            self._splitter.setSizes([min_pdf, total_w - min_pdf - self._splitter.handleWidth()])

    def _toggle_toc(self):
        """切换目录侧栏显隐"""
        self._toc_dock.setVisible(not self._toc_dock.isVisible())

    def _populate_toc(self, toc_data):
        """用 PDF 目录数据填充树控件"""
        self._toc_tree.clear()
        self._toc_page_map = {}  # QTreeWidgetItem → page_number

        if not toc_data:
            item = QTreeWidgetItem(["（无目录）"])
            item.setDisabled(True)
            self._toc_tree.addTopLevelItem(item)
            return

        # toc_data: [(level, title, page, ...), ...]
        stack = []  # 保留各级最后插入的 item
        for entry in toc_data:
            level = entry[0]
            title = entry[1]
            page = entry[2]

            item = QTreeWidgetItem([f"{title}  → 第{page}页"])
            item.setData(0, Qt.UserRole, page)
            self._toc_page_map[id(item)] = page

            if level == 1 or not stack:
                self._toc_tree.addTopLevelItem(item)
                stack = [item]
            else:
                # 向上找到合适级别
                while len(stack) >= level:
                    stack.pop()
                if stack:
                    stack[-1].addChild(item)
                else:
                    self._toc_tree.addTopLevelItem(item)
                stack.append(item)

        self._toc_tree.expandAll()

    def _on_toc_clicked(self, item, column):
        """点击目录项 → 跳转到对应页"""
        page = item.data(0, Qt.UserRole)
        if page is None or not isinstance(page, int):
            return
        if page < 1 or page > self._pdf_panel.total_pages:
            return
        self._syncing = True
        self._sync_to = page
        self._pdf_panel.go_to_page(page)
        self._txt_panel.go_to_page(page)
        self._update_page_label()
        QTimer.singleShot(500, self._release_sync)


    def _show_welcome(self):
        try:
            QMessageBox.information(
                self, "Cathay Reader",
                "欢迎使用 Cathay Reader\n\n"
                "专为 CathayOCR 用户设计的双栏同步阅读器\n\n"
                "- 点击[打开文件夹]选择包含 PDF/TXT 的目录\n"
                "- 支持同步滚动: PDF 翻页时 TXT 自动跳转\n"
                "- 支持繁体/繁转简文本切换\n\n"
                "快捷键: <-> 翻页 | Ctrl+ +/- 缩放 | Ctrl+O 打开文件夹"
            )
        except Exception:
            pass

    def _toggle_search(self):
        """切换搜索栏"""
        self._search_active = getattr(self, '_search_active', False)
        self._search_active = not self._search_active
        if self._search_active:
            self._search_btn.setStyleSheet(
                "padding:2px 8px; border:1px solid #5a8; border-radius:3px; "
                "background:#fff3e0; color:#e65100;")
        else:
            self._search_btn.setStyleSheet(
                "padding:2px 8px; border:1px solid #5a8; border-radius:3px; "
                "background:#e8f5e9; color:#2e7d32;")
        self._txt_panel.toggle_search()
        self._pdf_panel.toggle_search_bar()

    def _copy_pdf_text(self):
        """复制 PDF 文字到剪贴板（优先选区，无选区则整页）"""
        text = self._pdf_panel.copy_page_text()
        if text:
            preview = text[:50] + "…" if len(text) > 50 else text
            self._status_bar.showMessage(f"已复制 {len(text)} 字：{preview}", 3000)
            self._flash_button(self._copy_btn, "#ce93d8", "#fff")
        else:
            QMessageBox.information(self, "复制", "PDF 未加载或文字提取失败")

    def _copy_full_page_text(self):
        """复制 PDF 当前页全部文字（忽略选区，含出处标注）[Ctrl+Shift+D]"""
        text = self._pdf_panel.copy_full_page_text()
        if text:
            preview = text[:50] + "…" if len(text) > 50 else text
            self._status_bar.showMessage(f"已复制整页 {len(text)} 字：{preview}", 3000)
        else:
            QMessageBox.information(self, "复制", "PDF 未加载或文字提取失败")



    def _flash_button(self, btn, bg, text_color, ms=500):
        """按钮闪烁反馈"""
        orig = btn.styleSheet()
        btn.setStyleSheet(
            f"padding:2px 8px; border:1px solid #bbb; border-radius:3px; "
            f"background:{bg}; color:{text_color};")
        QTimer.singleShot(ms, lambda: btn.setStyleSheet(orig))

    def _show_about(self):
        QMessageBox.about(
            self, "关于 Cathay Reader",
            "Cathay Reader v1.0.0\n\n"
            "CathayOCR 配套阅读器 - 双栏 PDF/TXT 同步阅读\n\n"
            "https://github.com/zzhjim02/CathayOCR"
        )

    # --- 拖放支持 ---

    def _register_app(self):
        import subprocess, sys
        main_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'main.py')
        if not os.path.isfile(main_py):
            QMessageBox.warning(self, '注册失败', '找不到 main.py')
            return
        exe = sys.executable
        reg_lines = [
            'Windows Registry Editor Version 5.00',
            '',
            '[HKEY_CLASSES_ROOT\\' + '.pdf]',
            '@="CathayReader.Document"',
            '',
            '[HKEY_CLASSES_ROOT\\' + '.txt]',
            '@="CathayReader.Document"',
            '',
            '[HKEY_CLASSES_ROOT\\CathayReader.Document]',
            '@="Cathay Reader Document"',
            '',
            '[HKEY_CLASSES_ROOT\\CathayReader.Document\\shell\\open\\command]',
            '@="\\"' + exe + '\\" \\"' + main_py + '\\" \\"%1\\""',
            '',
            '[HKEY_CLASSES_ROOT\\CathayReader.Document\\DefaultIcon]',
            '@="\\"' + exe + '\\",1"',
        ]
        # os 已在模块顶部导入
        reg_dir = os.path.dirname(os.path.abspath(main_py))
        reg_path = os.path.join(reg_dir, 'CathayReader_关联文件.reg')
        with open(reg_path, 'w', encoding='utf-8') as f:
            f.write(chr(10).join(reg_lines))
        QMessageBox.information(
            self, '文件关联',
            '已生成注册表文件：\n' + reg_path + '\n\n'
            '请右键以管理员身份运行该 .reg 文件，\n'
            '即可将本软件设置为 PDF/TXT 默认打开程序。'
        )

    # dragEnterEvent / dropEvent 在文件末尾

    def _open_file(self, path: str):
        """按文件路径打开（拖放 / 命令行参数用）"""
        if not os.path.isfile(path):
            return
        directory = os.path.dirname(path)

        self._file_matcher = FileMatcher(directory)
        pairs = self._file_matcher.scan()

        self._path_label.setText(directory)

        self._volume_combo.blockSignals(True)
        self._volume_combo.clear()

        target_idx = -1
        for i, pair in enumerate(pairs):
            self._volume_combo.addItem(pair.name, pair)
            # 检查是否匹配传入的文件
            if pair.pdf_path and os.path.normcase(pair.pdf_path) == os.path.normcase(path):
                target_idx = i
            else:
                for lbl in pair.get_available_labels():
                    for mode in [False, True]:
                        tp = pair.get_txt_path(lbl, mode)
                        if tp and os.path.normcase(tp) == os.path.normcase(path):
                            target_idx = i
                            break
                    if target_idx >= 0:
                        break

        if target_idx >= 0:
            self._volume_combo.setCurrentIndex(target_idx)
        elif pairs:
            self._volume_combo.setCurrentIndex(0)
        self._volume_combo.blockSignals(False)

        self._current_index = self._volume_combo.currentIndex()
        self._load_direct_volume(self._current_index)

    # --- 文件操作 ---

    def _on_search_next(self):
        self._pdf_panel._on_search_next()

    def _on_search_prev(self):
        self._pdf_panel._on_search_prev()

    def _on_open_directory(self):
        directory = QFileDialog.getExistingDirectory(
            self, "选择包含 PDF 和 TXT 的目录",
            "", QFileDialog.ShowDirsOnly
        )
        if directory:
            self._load_directory(directory)

    def _on_open_file(self):
        """打开单个 PDF 或 TXT，自动查找同目录配对文件和相邻册"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择一个 PDF 或 TXT 文件",
            "",
            "PDF/TXT 文件 (*.pdf *.txt *.PDF *.TXT)"
        )
        if not path:
            return

        directory = os.path.dirname(path)
        fname = os.path.basename(path)
        lower = fname.lower()

        # 扫描目录
        self._file_matcher = FileMatcher(directory)
        pairs = self._file_matcher.scan()

        self._path_label.setText(directory)

        self._volume_combo.blockSignals(True)
        self._volume_combo.clear()

        target_idx = -1
        for i, pair in enumerate(pairs):
            self._volume_combo.addItem(pair.name, pair)
            if pair.pdf_path == path:
                target_idx = i
                break
            # 检查所有 OCR 变体
            for v in pair.txt_variants.values():
                if path in (v.get('orig',''), v.get('simple','')):
                    target_idx = i
                    break
            if target_idx >= 0:
                break

        # 如果所选文件不在扫描结果中，直接按文件名查同目录同级文件
        if target_idx < 0:
            base, ext = os.path.splitext(fname)
            if ext.lower() == '.pdf':
                # 新建 FilePair，扫描同目录所有 TXT
                root, _ = identify_pdf_variant(fname)
                single = FilePair(path, root)
                for f in os.listdir(directory):
                    if f.lower().endswith('.txt'):
                        r, lbl, simp = identify_txt_variant(f)
                        if r == root:
                            single.add_txt(lbl, os.path.join(directory, f), simp)
            else:
                # TXT 文件 → 找同根名的 PDF
                txt_root, txt_lbl, txt_simp = identify_txt_variant(fname)
                single = FilePair("", txt_root)
                single.add_txt(txt_lbl, path, txt_simp)
                # 扫描找同根名 PDF
                for f in os.listdir(directory):
                    if f.lower().endswith('.pdf'):
                        r, _ = identify_pdf_variant(f)
                        if r == txt_root:
                            single.pdf_path = os.path.join(directory, f)
                            break
            self._volume_combo.addItem(single.name, single)
            target_idx = self._volume_combo.count() - 1

            # 如果这个文件不在 pairs 中，把 pairs 里其他文件也补上
            # 以便用户在册下拉框中浏览相邻册
            for i, pair in enumerate(pairs):
                if pair.pdf_path not in [self._volume_combo.itemData(j).pdf_path
                                          for j in range(self._volume_combo.count())]:
                    self._volume_combo.addItem(pair.name, pair)

        self._volume_combo.blockSignals(False)

        if target_idx >= 0:
            self._current_index = target_idx
            self._load_direct_volume(target_idx)
            self._status_label.setText(
                f"已加载 {len(pairs)} 册 + 1 个独立文件"
                if target_idx >= len(pairs) else
                f"已加载 {len(pairs)} 册"
            )

    def _get_current_txt_path(self, pair) -> str:
        """根据当前 OCR 版本和繁简模式获取 TXT 路径"""
        ocr_idx = self._ocr_combo.currentIndex()
        ocr_label = self._ocr_combo.itemData(ocr_idx) if ocr_idx >= 0 else ""
        use_simple = self._txt_mode_combo.currentIndex() == 1
        if ocr_label:
            return pair.get_txt_path(ocr_label, use_simple)
        return ""

    def _update_ocr_combo(self, pair):
        """根据 FilePair 更新 OCR 版本下拉框"""
        self._ocr_combo.blockSignals(True)
        self._ocr_combo.clear()
        labels = pair.get_available_labels()
        for lbl in labels:
            self._ocr_combo.addItem(lbl, lbl)
        if labels:
            # 默认选中第一个（最优版本）
            self._ocr_combo.setCurrentIndex(0)
        self._ocr_combo.blockSignals(False)
        # 同步更新文本模式
        self._update_txt_mode_combo(pair)

    def _update_txt_mode_combo(self, pair):
        """根据 FilePair 动态更新文本模式下拉（仅显示可用选项）"""
        ocr_idx = self._ocr_combo.currentIndex()
        ocr_label = self._ocr_combo.itemData(ocr_idx) if ocr_idx >= 0 else ""
        has_orig = bool(pair.get_txt_path(ocr_label, False)) if ocr_label else False
        has_simple = bool(pair.get_txt_path(ocr_label, True)) if ocr_label else False

        self._txt_mode_combo.blockSignals(True)
        self._txt_mode_combo.clear()
        if has_orig and has_simple:
            self._txt_mode_combo.addItems(["原文", "繁转简"])
            self._txt_mode_combo.setEnabled(True)
            self._txt_mode_combo.setCurrentIndex(0)
        elif has_simple:
            self._txt_mode_combo.addItem("繁转简")
            self._txt_mode_combo.setEnabled(False)
        else:
            # 默认显示繁体原文
            self._txt_mode_combo.addItem("原文")
            self._txt_mode_combo.setEnabled(False)
        self._txt_mode_combo.blockSignals(False)

    def _load_direct_volume(self, index: int):
        """直接按索引加载（不依赖 _file_matcher 类属性）"""
        try:
            pair = self._volume_combo.itemData(index)
            if not pair:
                return

            self._status_label.setText(f"加载: {pair.name}...")
            QApplication.processEvents()

            # 更新 OCR 版本下拉
            self._update_ocr_combo(pair)

            txt_path = self._get_current_txt_path(pair)
            txt_ok = False

            # 加载 PDF，无则显示引导页
            if pair.pdf_path and os.path.isfile(pair.pdf_path):
                pdf_ok = self._pdf_panel.load_pdf(pair.pdf_path)
                if pdf_ok:
                    self._populate_toc(self._pdf_panel.get_toc())
                else:
                    self._status_label.setText(f"PDF 加载失败: {pair.pdf_name}")
                    return
            else:
                pdf_ok = False
                self._pdf_panel.show_placeholder()
                self._populate_toc([])  # 清空目录

            # 加载 TXT（自动检测繁/简模式）
            if txt_path and os.path.isfile(txt_path):
                txt_ok = self._txt_panel.load_txt(txt_path)
            else:
                # 当前模式文件不存在/为空 → 尝试另一种模式
                ocr_idx = self._ocr_combo.currentIndex()
                ocr_label = self._ocr_combo.itemData(ocr_idx) if ocr_idx >= 0 else ""
                other_mode = 1 if self._txt_mode_combo.currentIndex() == 0 else 0
                other_path = pair.get_txt_path(ocr_label, other_mode == 1) if ocr_label else ""
                if other_path and os.path.isfile(other_path):
                    txt_ok = self._txt_panel.load_txt(other_path)
                    if txt_ok:
                        self._txt_mode_combo.setCurrentIndex(other_mode)
                if not txt_ok:
                    self._txt_panel.show_placeholder()

            self._update_page_list()

            if pdf_ok:
                self._pdf_panel.zoom_fit_width()
                self._syncing = True
                self._pdf_panel.go_to_page(1)
                if txt_ok:
                    self._txt_panel.go_to_page(1)
                self._update_page_label()

            QTimer.singleShot(500, self._release_sync)

            mode_name = "繁体" if self._txt_mode_combo.currentIndex() == 0 else "繁转简"
            ocr_name = self._ocr_combo.currentText() if self._ocr_combo.count() > 0 else ""
            parts = [pair.name, mode_name]
            if ocr_name:
                parts.append(ocr_name)
            if pdf_ok:
                parts.append(f"PDF {self._pdf_panel.total_pages}页")
            if txt_ok and self._txt_panel.view.page_index:
                parts.append(f"TXT {self._txt_panel.view.page_index.page_count}页")
            self._status_label.setText(" | ".join(parts))
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._status_label.setText(f"加载错误: {e}")

    def _load_directory(self, directory: str):
        try:
            self._file_matcher = FileMatcher(directory)
            pairs = self._file_matcher.scan()

            if not pairs:
                QMessageBox.warning(
                    self, "未找到文件",
                    "目录中未找到配对的 PDF/TXT 文件。\n\n"
                    "请确认目录包含以下格式的文件:\n"
                    "  第N册_PD6AIFOCR.pdf\n"
                    "  第N册_PD6AIFOCR.txt"
                )
                return

            self._path_label.setText(directory)

            self._volume_combo.blockSignals(True)
            self._volume_combo.clear()
            for pair in pairs:
                self._volume_combo.addItem(pair.name, pair)
            self._volume_combo.blockSignals(False)

            self._current_index = 0
            self._load_direct_volume(0)
            self._status_label.setText(f"已加载 {len(pairs)} 册")
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "加载错误",
                f"加载目录时出错:\n{e}\n\n详情已写入 crash_log.txt")

    def _on_volume_changed(self, index: int):
        if index >= 0:
            self._current_index = index
            self._load_direct_volume(index)

    def _update_page_list(self):
        self._page_spin.blockSignals(True)
        self._page_spin.clear()
        for i in range(1, self._pdf_panel.total_pages + 1):
            self._page_spin.addItem(str(i))
        self._page_spin.blockSignals(False)

    def _update_page_label(self):
        p = self._pdf_panel.current_page
        t = self._pdf_panel.total_pages
        self._page_label.setText(f"第 {p}/{t} 页")

    def _on_page_jump(self):
        try:
            page = int(self._page_spin.currentText())
        except ValueError:
            return
        if page < 1 or page > self._pdf_panel.total_pages:
            return
        # 禁止同步 400ms，阻隔 TXT 的延时信号
        self._syncing = True
        self._sync_to = page
        self._pdf_panel.go_to_page(page)
        self._txt_panel.go_to_page(page)
        self._update_page_label()
        QTimer.singleShot(500, self._release_sync)

    def _release_sync(self):
        self._syncing = False
        self._sync_to = 0

    def _reload_current_txt(self):
        """重新加载当前 TXT（自动检测繁/简模式）"""
        pair = self._volume_combo.itemData(self._volume_combo.currentIndex())
        if not pair:
            return
        # 断开 pageChanged 信号，防止 load_txt 发射 pageChanged(1) 抢同步锁
        was_connected = False
        try:
            self._txt_panel.pageChanged.disconnect(self._on_txt_page_changed)
            was_connected = True
        except TypeError:
            pass

        new_mode = None
        try:
            txt_path = self._get_current_txt_path(pair)
            if txt_path and os.path.isfile(txt_path):
                self._txt_panel.load_txt(txt_path)
            else:
                # 当前模式失败 → 尝试另一种模式
                ocr_idx = self._ocr_combo.currentIndex()
                ocr_label = self._ocr_combo.itemData(ocr_idx) if ocr_idx >= 0 else ""
                other_mode = 1 if self._txt_mode_combo.currentIndex() == 0 else 0
                other_path = pair.get_txt_path(ocr_label, other_mode == 1) if ocr_label else ""
                if other_path and os.path.isfile(other_path):
                    ok = self._txt_panel.load_txt(other_path)
                    if ok:
                        new_mode = other_mode
        finally:
            # 确保信号始终重连
            if was_connected:
                self._txt_panel.pageChanged.connect(self._on_txt_page_changed)

        # 切换到新页码
        target_page = self._pdf_panel.current_page
        if new_mode is not None:
            self._txt_mode_combo.setCurrentIndex(new_mode)
        if self._txt_panel.view.page_index:
            self._txt_panel.go_to_page(target_page)
        else:
            self._txt_panel.show_placeholder()

    def _on_txt_mode_changed(self, index: int):
        self._reload_current_txt()

    def _on_ocr_changed(self, index: int):
        # 更新文本模式下拉选项
        pair = self._volume_combo.itemData(self._volume_combo.currentIndex())
        if pair:
            self._update_txt_mode_combo(pair)
        self._reload_current_txt()

    def _on_font_size_changed(self, size_str: str):
        try:
            size = int(size_str)
        except ValueError:
            return
        self._txt_panel.set_font(QFont("SimSun", size))

    # --- 翻页 ---

    def _go_prev_page(self):
        cp = self._pdf_panel.current_page
        if cp > 1:
            self._syncing = True
            self._sync_to = cp - 1
            self._pdf_panel.go_to_page(cp - 1)
            self._txt_panel.go_to_page(cp - 1)
            self._update_page_label()
            QTimer.singleShot(500, self._release_sync)

    def _go_next_page(self):
        cp = self._pdf_panel.current_page
        if cp < self._pdf_panel.total_pages:
            self._syncing = True
            self._sync_to = cp + 1
            self._pdf_panel.go_to_page(cp + 1)
            self._txt_panel.go_to_page(cp + 1)
            self._update_page_label()
            QTimer.singleShot(500, self._release_sync)

    def _go_prev_volume(self):
        idx = self._volume_combo.currentIndex()
        if idx > 0:
            self._volume_combo.setCurrentIndex(idx - 1)

    def _go_next_volume(self):
        idx = self._volume_combo.currentIndex()
        if idx < self._volume_combo.count() - 1:
            self._volume_combo.setCurrentIndex(idx + 1)

    # --- 同步滚动 ---

    def _on_pdf_page_changed(self, page: int):
        if self._syncing:
            return
        self._update_page_label()
        self._page_spin.setCurrentText(str(page))
        self._syncing = True
        self._sync_to = page
        self._txt_panel.go_to_page(page)
        QTimer.singleShot(500, self._release_sync)

    def _on_txt_page_changed(self, page: int):
        if self._syncing:
            return
        self._page_spin.setCurrentText(str(page))
        self._syncing = True
        self._sync_to = page
        self._pdf_panel.go_to_page(page)
        QTimer.singleShot(500, self._release_sync)
        self._update_page_label()

    def _show_suffix_config(self):
        """后缀设置 — 简单表格，一行一个配对"""
        if not self._file_matcher:
            QMessageBox.information(self, "提示", "请先打开一个目录")
            return

        pairs = self._file_matcher.suffix_pairs  # [[pdf_sfx, txt_sfx], ...]

        dlg = QDialog(self)
        dlg.setWindowTitle("后缀配对设置")
        dlg.setMinimumWidth(460)
        dlg.setMinimumHeight(300)
        vl = QVBoxLayout(dlg)
        vl.setSpacing(8)

        # 说明文字
        tip = QLabel(
            "每行定义一个配对。PDF 文件名尾部含有左栏特征的，"
            "会配上 TXT 文件名尾部含有右栏特征的文件。"
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#666; font-size:11px; padding:4px 0;")
        vl.addWidget(tip)

        # 表格
        table = QTableWidget(len(pairs) if pairs else 1, 2)
        table.setHorizontalHeaderLabels(["PDF 文件后缀", "TXT 文件后缀"])
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.setMinimumHeight(150)

        if pairs:
            for row, (p, t) in enumerate(pairs):
                table.setItem(row, 0, QTableWidgetItem(p))
                table.setItem(row, 1, QTableWidgetItem(t))
        else:
            table.setItem(0, 0, QTableWidgetItem("_校对稿"))
            table.setItem(0, 1, QTableWidgetItem("_扫校版"))

        vl.addWidget(table)

        # 示例
        eg = QLabel("例：PDF 后缀填「_A」、TXT 后缀填「_B」→ book_A.pdf 与 book_B.txt 自动配对")
        eg.setStyleSheet("color:#999; font-size:10px;")
        vl.addWidget(eg)

        # 操作按钮
        btn_row = QHBoxLayout()
        add_btn = QPushButton("➕ 添加一行")
        add_btn.setStyleSheet("padding:3px 12px;")
        add_btn.clicked.connect(lambda: table.insertRow(table.rowCount()))
        del_btn = QPushButton("➖ 删除选中行")
        del_btn.setStyleSheet("padding:3px 12px;")
        del_btn.clicked.connect(lambda: table.removeRow(table.currentRow()) if table.currentRow() >= 0 else None)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        vl.addLayout(btn_row)

        # 确定/取消
        bottom = QHBoxLayout()
        bottom.addStretch()
        ok_btn = QPushButton("保存")
        ok_btn.setStyleSheet("padding:4px 24px; font-weight:bold;")
        ok_btn.clicked.connect(dlg.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("padding:4px 24px;")
        cancel_btn.clicked.connect(dlg.reject)
        bottom.addWidget(ok_btn)
        bottom.addWidget(cancel_btn)
        vl.addLayout(bottom)

        if dlg.exec_() == QDialog.Rejected:
            return

        # 收集表格数据
        new_pairs = []
        for row in range(table.rowCount()):
            p_item = table.item(row, 0)
            t_item = table.item(row, 1)
            if p_item and t_item:
                p = p_item.text().strip()
                t = t_item.text().strip()
                if p and t:
                    new_pairs.append([p, t])

        self._file_matcher.set_suffix_pairs(new_pairs)
        QMessageBox.information(
            self, "已保存",
            f"已保存 {len(new_pairs)} 个后缀配对\n"
            "重新打开目录后生效"
        )

    # --- 拖入支持 ---

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            return
        path = urls[0].toLocalFile()
        if os.path.isdir(path):
            self._load_directory(path)
        elif path.lower().endswith(('.pdf', '.txt')):
            self._open_file(path)

    def closeEvent(self, event):
        event.accept()
