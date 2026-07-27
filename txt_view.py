"""
txt_view.py - TXT 纯文本显示
"""

import os
import re
from typing import Optional

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QTextCursor, QTextCharFormat
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit,
    QLineEdit, QHBoxLayout, QPushButton, QLabel, QStackedWidget
)

from page_parser import PageIndex

MATCH_COLOR = QColor(255, 200, 100)


class TxtViewWidget(QTextEdit):
    """TXT 控件（纯文本，保留页码标记）"""

    pageChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._page_index: Optional[PageIndex] = None
        self._current_page = 1
        self._syncing = False
        self._is_loading = False
        self._match_pos = []
        self._match_idx = -1
        self._search_txt = ""

        self.setReadOnly(True)
        self.setFont(QFont("SimSun", 11))
        self.setLineWrapMode(QTextEdit.WidgetWidth)
        self.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ccc;
                background-color: #fafaf8;
                padding: 6px;
            }
        """)
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

    def load_txt(self, txt_path: str) -> bool:
        self._is_loading = True
        self.clear()
        self._match_pos = []
        self._match_idx = -1

        if not os.path.isfile(txt_path):
            self._is_loading = False
            return False

        self._page_index = PageIndex(txt_path)
        if not self._page_index.load():
            self._is_loading = False
            return False

        # 保留原始内容（含页码标记），直接显示
        self.setPlainText(self._page_index.content)
        self._current_page = 1

        # 滚动到第一页的起始位置
        start, _ = self._page_index.get_page_range(1)
        if start > 0:
            cursor = QTextCursor(self.document())
            cursor.setPosition(start)
            self.setTextCursor(cursor)
            cr = self.cursorRect(cursor)
            self.verticalScrollBar().setValue(
                max(0, self.verticalScrollBar().value() + cr.top() - 20))

        self._is_loading = False
        self.pageChanged.emit(1)
        return True

    def clear(self):
        super().clear()
        self._page_index = None
        self._current_page = 0
        self._match_pos = []
        self._match_idx = -1

    def go_to_page(self, page_number: int):
        if self._syncing or self._is_loading or not self._page_index:
            return
        self._syncing = True

        start, _ = self._page_index.get_page_range(page_number)
        doc = self.document()
        pos = min(start, doc.characterCount() - 1)
        cursor = QTextCursor(doc)
        cursor.setPosition(pos)
        self.setTextCursor(cursor)
        cr = self.cursorRect(cursor)
        self.verticalScrollBar().setValue(
            max(0, self.verticalScrollBar().value() + cr.top() - 20))

        if page_number != self._current_page:
            self._current_page = page_number

        self.pageChanged.emit(page_number)
        QTimer.singleShot(200, self._release_sync)

    def _release_sync(self):
        self._syncing = False

    def _on_scroll(self, value):
        if self._syncing or self._is_loading or not self._page_index:
            return
        cursor = self.cursorForPosition(
            self.viewport().rect().topLeft())
        pos = cursor.position()
        page = self._page_index.get_page_at_position(pos)
        if page > 0 and page != self._current_page:
            self._current_page = page
            self.pageChanged.emit(page)

    # ---- 搜索 ----

    def search_text(self, query: str) -> bool:
        if not query:
            return False
        self._search_txt = query
        self._clear_highlights()
        doc = self.document()
        self._match_pos = []

        cursor = QTextCursor(doc)
        cursor.movePosition(QTextCursor.Start)
        while True:
            c = doc.find(query, cursor)
            if c.isNull():
                break
            self._match_pos.append(c.position())
            fmt = QTextCharFormat()
            fmt.setBackground(MATCH_COLOR)
            c.mergeCharFormat(fmt)
            cursor.setPosition(c.position() + len(query))

        if not self._match_pos:
            return False

        self._match_idx = 0
        self._jump_match(0)
        return True

    def _clear_highlights(self):
        doc = self.document()
        cc = QTextCursor(doc)
        cc.movePosition(QTextCursor.Start)
        cc.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        nf = QTextCharFormat()
        nf.setBackground(Qt.transparent)
        cc.mergeCharFormat(nf)

    def next_match(self):
        if not self._match_pos:
            return
        cur_match_page = self._page_index.get_page_at_position(
            self._match_pos[self._match_idx]) if self._page_index else -1
        cp = self._current_page
        if cur_match_page == cp:
            # 高亮在本页 → 正常递增
            self._match_idx = (self._match_idx + 1) % len(self._match_pos)
        else:
            # 用户手动翻页离开了 → 从当前页之后找第一个匹配
            for i in range(len(self._match_pos)):
                p = self._page_index.get_page_at_position(self._match_pos[i])
                if p > cp and i != self._match_idx:
                    self._match_idx = i
                    break
            else:
                self._match_idx = 0
        self._jump_match(self._match_idx)

    def prev_match(self):
        if not self._match_pos:
            return
        cur_match_page = self._page_index.get_page_at_position(
            self._match_pos[self._match_idx]) if self._page_index else -1
        cp = self._current_page
        if cur_match_page == cp:
            # 高亮在本页 → 正常递减
            self._match_idx = (self._match_idx - 1) % len(self._match_pos)
        else:
            # 用户手动翻页离开了 → 从当前页之前找最后一个匹配
            best = -1
            for i, pos in enumerate(self._match_pos):
                p = self._page_index.get_page_at_position(pos)
                if p < cp and i != self._match_idx:
                    best = i
            if best >= 0:
                self._match_idx = best
            else:
                self._match_idx = len(self._match_pos) - 1
        self._jump_match(self._match_idx)

    def _jump_match(self, idx: int):
        if not self._match_pos:
            return
        pos = self._match_pos[idx]
        doc = self.document()
        cursor = QTextCursor(doc)
        cursor.setPosition(pos)
        self.setTextCursor(cursor)
        cr = self.cursorRect(cursor)
        self.verticalScrollBar().setValue(
            max(0, self.verticalScrollBar().value() + cr.top() - 50))

        p = self._page_index.get_page_at_position(pos)
        if p > 0 and p != self._current_page:
            self._current_page = p
            self.pageChanged.emit(p)

    @property
    def match_count(self): return len(self._match_pos)

    @property
    def current_match(self):
        return self._match_idx + 1 if self._match_pos else 0

    @property
    def page_index(self): return self._page_index

    @property
    def current_page(self): return self._current_page


class PlaceholderPage(QWidget):
    """无 TXT 时显示的占位页面（含操作按钮）"""

    configSuffixSig = pyqtSignal()
    openFileSig = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        l = QVBoxLayout(self)
        l.setAlignment(Qt.AlignCenter)
        l.setSpacing(16)

        title = QLabel("未找到对应的 TXT 文件")
        title.setStyleSheet(
            "font-size:16px; font-weight:bold; color:#555;")
        title.setAlignment(Qt.AlignCenter)
        l.addWidget(title)

        desc = QLabel(
            "文件名格式可能不一致，\n"
            "可通过设置后缀映射让程序自动配对，\n"
            "或直接选择一个 TXT 文件打开。")
        desc.setStyleSheet("font-size:13px; color:#777; line-height:1.6;")
        desc.setAlignment(Qt.AlignCenter)
        l.addWidget(desc)

        btns = QHBoxLayout()
        btns.setSpacing(20)
        btns.setAlignment(Qt.AlignCenter)

        btn1 = QPushButton(" 设置后缀映射 ")
        btn1.setStyleSheet(
            "QPushButton {"
            "  padding:8px 20px; font-size:14px;"
            "  border:1px solid #4a90d9; border-radius:6px;"
            "  background:#e8f0fe; color:#1a73e8;"
            "}"
            "QPushButton:hover { background:#d2e3fc; }")
        btn1.clicked.connect(self.configSuffixSig.emit)
        btns.addWidget(btn1)

        btn2 = QPushButton(" 打开 TXT/PDF ")
        btn2.setStyleSheet(
            "QPushButton {"
            "  padding:8px 20px; font-size:14px;"
            "  border:1px solid #34a853; border-radius:6px;"
            "  background:#e6f4ea; color:#1e8e3e;"
            "}"
            "QPushButton:hover { background:#ceead6; }")
        btn2.clicked.connect(self.openFileSig.emit)
        btns.addWidget(btn2)

        l.addLayout(btns)

        # 分隔线
        hr = QLabel("─── 或 ───")
        hr.setStyleSheet("color:#aaa; font-size:12px;")
        hr.setAlignment(Qt.AlignCenter)
        l.addWidget(hr)

        help_text = QLabel(
            "提示：点击工具栏「匹配」按钮 → 输入 PDF 和 TXT 的后缀特征\n"
            "示例：PDF 文件以 _A 结尾，TXT 文件以 _B 结尾，\n"
            "      那么在两个框分别填 _A 和 _B 即可自动配对")
        help_text.setStyleSheet(
            "font-size:12px; color:#999; background:#f5f5f5;"
            "padding:10px 14px; border-radius:4px;")
        help_text.setWordWrap(True)
        l.addWidget(help_text)


class TxtViewPanel(QWidget):
    """TXT 面板"""

    pageChanged = pyqtSignal(int)
    configSuffixRequested = pyqtSignal()
    openFileRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._view = TxtViewWidget()
        self._view.pageChanged.connect(self.pageChanged.emit)

        # 搜索栏（隐藏）
        sb = QWidget()
        sb.setObjectName("txtSearchBar")
        sb.setVisible(False)
        sb.setStyleSheet("background:#f5f5f5;border-bottom:1px solid #ddd;")
        sl = QHBoxLayout(sb)
        sl.setContentsMargins(6, 3, 6, 3)
        sl.setSpacing(4)

        self._si = QLineEdit()
        self._si.setPlaceholderText("全文检索 (Enter)...")
        self._si.setStyleSheet("padding:3px 6px;border:1px solid #ccc;border-radius:3px;background:white;")
        self._si.returnPressed.connect(self._do_search)
        sl.addWidget(self._si, 1)

        self._ml = QLabel("")
        self._ml.setStyleSheet("color:#666;font-size:11px;")
        sl.addWidget(self._ml)

        self._pb = QPushButton("<")
        self._pb.setFixedWidth(26)
        self._pb.setStyleSheet("padding:1px 4px;border:1px solid #aaa;border-radius:2px;background:#eee;")
        self._pb.clicked.connect(self._view.prev_match)
        self._pb.setVisible(False)
        sl.addWidget(self._pb)

        self._nb = QPushButton(">")
        self._nb.setFixedWidth(26)
        self._nb.setStyleSheet("padding:1px 4px;border:1px solid #aaa;border-radius:2px;background:#eee;")
        self._nb.clicked.connect(self._view.next_match)
        self._nb.setVisible(False)
        sl.addWidget(self._nb)

        self._search_bar = sb

        # 正常页面：搜索栏 + 文本编辑
        self._normal_page = QWidget()
        nl = QVBoxLayout(self._normal_page)
        nl.setContentsMargins(0, 0, 0, 0)
        nl.setSpacing(0)
        nl.addWidget(sb)
        nl.addWidget(self._view, 1)

        # 占位页面：引导+按钮
        self._placeholder = PlaceholderPage()
        self._placeholder.configSuffixSig.connect(
            self.configSuffixRequested.emit)
        self._placeholder.openFileSig.connect(
            self.openFileRequested.emit)

        # 堆叠切换
        self._stack = QStackedWidget()
        self._stack.addWidget(self._normal_page)  # index 0
        self._stack.addWidget(self._placeholder)   # index 1

        l = QVBoxLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(0)
        l.addWidget(self._stack, 1)

    def _do_search(self):
        q = self._si.text().strip()
        found = self._view.search_text(q)
        if found:
            self._ml.setText(f"第{self._view.current_match}/{self._view.match_count}个")
            self._pb.setVisible(True)
            self._nb.setVisible(True)
        else:
            self._ml.setText("无匹配" if q else "")
            self._pb.setVisible(False)
            self._nb.setVisible(False)

    def toggle_search(self):
        if self._stack.currentIndex() != 0:
            return
        v = not self._search_bar.isVisible()
        self._search_bar.setVisible(v)
        if v:
            self._si.setFocus()
            self._si.selectAll()
        else:
            self._view._clear_highlights()

    def load_txt(self, p):
        ok = self._view.load_txt(p)
        if ok:
            self._stack.setCurrentIndex(0)
        return ok

    def clear(self):
        self._view.clear()

    def show_placeholder(self):
        """切换到占位页面"""
        self._search_bar.setVisible(False)
        self._stack.setCurrentIndex(1)

    def show_no_txt(self):
        self.show_placeholder()

    def go_to_page(self, p): self._view.go_to_page(p)
    def set_font(self, f): self._view.setFont(f)

    @property
    def view(self): return self._view
