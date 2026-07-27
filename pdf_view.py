# pdf_view.py — QPainter 直接绘制 PDF 页
# 没有单 QLabel 跳来跳去，运行时只渲染可见页，滚动丝滑

import bisect

from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QRect, QRectF, QPoint
from PyQt5.QtGui import QPixmap, QImage, QPainter, QColor, QPen, QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QLineEdit, QPushButton, QStackedWidget, QApplication,
)
import fitz
import os


class PdfCanvas(QWidget):
    """QPainter 直接绘制 PDF 页的画布"""

    def __init__(self, reader):
        super().__init__()
        self._r = reader  # backref to PdfScrollArea

    def paintEvent(self, event):
        r = self._r
        if not r._doc or r._page_h <= 0:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        vr = event.rect()
        pg = r._PG
        pw = r._pw if r._pw > 0 else 100
        z = r._zoom
        yoffs = r._page_y_offsets
        pheights = r._page_heights

        # 定位可见页范围（使用各页实际Y偏移）
        first = bisect.bisect_right(yoffs, vr.top()) - 1
        if first < 0:
            first = 0
        last = bisect.bisect_right(yoffs, vr.bottom() + pg) - 1
        if last < first:
            last = first
        if last >= r._total:
            last = r._total - 1

        for idx in range(first, last + 1):
            y = yoffs[idx]
            ph_i = pheights[idx] if idx < len(pheights) else 100
            pm = r._pm_cache.get(idx)
            if pm:
                painter.drawPixmap(0, y, pm)
            else:
                painter.fillRect(0, y, pw, ph_i, Qt.white)

            # 页码浮层
            fs = max(10, min(16, ph_i // 40))
            f = painter.font()
            f.setPointSize(fs)
            f.setBold(True)
            painter.setFont(f)
            txt = f"  {idx + 1}  "
            tr = painter.boundingRect(QRect(0, 0, pw, 999), Qt.AlignCenter, txt)
            tr.moveCenter(QPoint(pw // 2, y + ph_i - tr.height() // 2 - 8))
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 150))
            painter.drawRoundedRect(tr.adjusted(-4, -2, 4, 2), 3, 3)
            painter.setPen(Qt.white)
            painter.drawText(tr, Qt.AlignCenter, txt)

        # 搜索高亮（黄色）
        if r._search_query:
            yel = QColor(255, 255, 0, 160)
            painter.setBrush(yel)
            painter.setPen(QPen(QColor(255, 150, 0), 1))
            for idx in range(first, last + 1):
                if idx in r._search_results:
                    for rect in r._search_results[idx]:
                        painter.drawRects([QRectF(
                            rect.x0 * z, yoffs[idx] + rect.y0 * z,
                            (rect.x1 - rect.x0) * z, (rect.y1 - rect.y0) * z)])

        # 选区高亮（蓝色）
        if r._has_sel and r._words and r._cur >= first and r._cur <= last:
            cy = yoffs[r._cur] if r._cur < len(yoffs) else 0
            blu = QColor(100, 150, 255, 80)
            painter.setBrush(blu)
            painter.setPen(Qt.NoPen)
            for i in r._sel_words:
                wr = r._words[i][0]
                painter.drawRects([QRectF(
                    wr.x0 * z, cy + wr.y0 * z,
                    (wr.x1 - wr.x0) * z, (wr.y1 - wr.y0) * z)])

        # 绘制页间分隔线
        if pg > 0:
            painter.setPen(QPen(QColor(180, 180, 180), 1))
            for idx in range(first, last):
                y = yoffs[idx] + pheights[idx]
                painter.drawLine(0, y, pw, y)

    def contextMenuEvent(self, event):
        from PyQt5.QtWidgets import QMenu, QAction
        from PyQt5.QtGui import QClipboard
        r = self._r
        menu = QMenu(self)
        if r._has_sel:
            a = QAction("复制选中文字", self)
            a.triggered.connect(lambda: QApplication.clipboard().setText(r.get_sel()))
            menu.addAction(a)
        a2 = QAction("复制本页全部文字", self)
        a2.triggered.connect(lambda: r.copy_full_page())
        menu.addAction(a2)
        menu.exec_(event.globalPos())


class PdfScrollArea(QScrollArea):
    """QPainter 绘制多页，QScrollArea 原生滚动"""
    pageChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc = None
        self._total = 0
        self._cur = 0
        self._zoom = 1.0
        self._page_h = 800
        self._pw = 400
        self._PG = 6  # 页间距 px

        self.setWidgetResizable(False)
        self.setAlignment(Qt.AlignCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet("QScrollArea{border:none;background:#e0e0e0;}")

        # 画布
        self._canvas = PdfCanvas(self)
        self._canvas.setMouseTracking(True)
        self._canvas.mousePressEvent = self._on_mouse_down
        self._canvas.mouseMoveEvent = self._on_mouse_move
        self._canvas.mouseReleaseEvent = self._on_mouse_up
        self.setWidget(self._canvas)

        # 词坐标（文字选取）
        self._words = []
        self._words_cache: dict = {}
        self._sel_words = []
        self._drag_start = None
        self._has_sel = False

        # 滚动
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

        # 后台渲染定时器：每 10ms 渲染一页
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(10)
        self._render_timer.timeout.connect(self._render_visible)
        self._render_timer.start()

        # 缓存
        self._pm_cache: dict = {}
        self._page_heights = []
        self._page_y_offsets = []
        self._total_h = 0

        # 搜索
        self._search_results = {}
        self._search_flat = []
        self._search_idx = -1
        self._search_query = ""
        self._dirty = True

    # ── 页面度量（支持不等宽/不等高页面）──

    def _calc_page_metrics(self):
        """计算各页实际像素尺寸及Y偏移（支持不同大小页面）"""
        self._page_heights = []
        self._page_y_offsets = []
        self._pw = 100
        if not self._doc or self._total == 0:
            self._total_h = 0
            self._page_h = 0
            return
        y = 0
        max_w = 0
        for i in range(self._total):
            r = self._doc[i].rect
            w = int(r.width * self._zoom)
            h = int(r.height * self._zoom)
            self._page_heights.append(h)
            self._page_y_offsets.append(y)
            if w > max_w:
                max_w = w
            y += h + self._PG
        self._pw = max(100, max_w)
        self._total_h = y - self._PG  # 去掉最后一页后的冗余间距
        self._page_h = self._page_heights[0] if self._page_heights else 0

    # ── 加载 ──

    def load(self, path):
        self.clear()
        if not os.path.isfile(path):
            return False
        try:
            self._doc = fitz.open(path)
            # 检查是否需要密码
            if self._doc.needs_pass:
                if not self._doc.authenticate(''):
                    print(f'PDF需要密码: {path}')
                    self._doc.close()
                    self._doc = None
                    return False
            self._source_path = path
            self._total = self._doc.page_count
            self._cur = 0

            r = self._doc[0].rect
            self._zoom = max(0.2, min(4.0, self.viewport().width() / r.width * 0.9))
            self._calc_page_metrics()
            self._canvas.setFixedSize(self._pw, self._total_h)

            self._search_results = {}
            self._search_flat = []
            self._search_idx = -1
            self._search_query = ""

            self._page_h = self._page_heights[0] if self._page_heights else 0
            QApplication.processEvents()
            self._render_sync(0)
            # 用实际像素尺寸重设画布（消除 int() 舍入误差）
            self._canvas.setFixedSize(self._pw, self._total_h)
            self._canvas.update()
            self.pageChanged.emit(1)
            return True
        except Exception as e:
            print(f"加载失败: {e}")
            self.clear()
            return False

    def clear(self):
        if self._doc:
            try:
                self._doc.close()
            except:
                pass
            self._doc = None
        self._canvas.update()
        self._total = 0
        self._cur = 0
        self._words = []
        self._words_cache.clear()
        self._sel_words = []
        self._has_sel = False
        self._drag_start = None
        self._pm_cache.clear()
        self._search_results = {}
        self._search_flat = []
        self._search_idx = -1
        self._search_query = ""
        self._dirty = True  # 需要重绘标记

    # ── 渲染 ──

    def _render_sync(self, idx):
        """渲染第 idx 页（同步，更新缓存）"""
        if not self._doc or idx >= self._total or idx in self._pm_cache:
            return
        try:
            page = self._doc[idx]
            mat = fitz.Matrix(self._zoom, self._zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            pm = QPixmap.fromImage(img)
            self._pm_cache[idx] = pm
            if idx == 0 and len(self._page_heights) == 0:
                self._pw = pm.width()
                self._page_h = pm.height()
        except Exception as e:
            print(f"渲染第{idx+1}页失败: {e}")

    def _render_visible(self):
        """后台定时器：每 tick 渲染一页可见页"""
        if not self._doc or not self._page_y_offsets:
            return
        sb = self.verticalScrollBar()
        vh = self.viewport().height()

        # 当前可见页范围 + 前后各 3 页缓冲
        sv = sb.value()
        first = bisect.bisect_right(self._page_y_offsets, sv) - 1 - 3
        if first < 0:
            first = 0
        last = bisect.bisect_right(self._page_y_offsets, sv + vh) - 1 + 4
        if last >= self._total:
            last = self._total - 1

        # 检查是否有未渲染的页
        for idx in range(first, last + 1):
            if idx not in self._pm_cache:
                self._render_sync(idx)
                self._canvas.update()
                return  # 每次只渲染一页，用完 return 等下一个 tick

        # 全部已缓存 → 降低 tick 频率省 CPU
        self._render_timer.setInterval(100)
        if self._dirty or self._search_query:
            self._dirty = False
            self._canvas.update()

    # ── 滚动 ──

    def _on_scroll(self, value):
        if not self._page_y_offsets:
            return
        # 寻找 value 所在的页面（binary search）
        idx = bisect.bisect_right(self._page_y_offsets, value) - 1
        idx = max(0, min(self._total - 1, idx))
        if idx != self._cur:
            self._cur = idx
            self._render_timer.setInterval(10)  # 加速渲染
            self.pageChanged.emit(idx + 1)
            self._has_sel = False
            self._sel_words = []

    def go_to(self, n):
        if self._total == 0 or not self._page_y_offsets:
            return
        i = max(0, min(n - 1, self._total - 1))
        self._cur = i
        target = self._page_y_offsets[i] if i < len(self._page_y_offsets) else 0
        self.verticalScrollBar().setValue(max(0, min(target, self.verticalScrollBar().maximum())))
        QApplication.processEvents()
        self._render_timer.setInterval(10)
        self._canvas.update()
        QApplication.processEvents()
        self.pageChanged.emit(i + 1)

    # ── 加载词坐标 ──

    def _load_words(self, idx):
        if idx in self._words_cache:
            self._words = self._words_cache[idx]
            return
        try:
            ws = self._doc[idx].get_text("words")
            self._words = [(fitz.Rect(w[0], w[1], w[2], w[3]), w[4]) for w in ws]
            self._words_cache[idx] = self._words
        except:
            self._words = []

    # ── 缩放 ──

    def _recalc_sizes(self):
        self._pm_cache.clear()
        self._words_cache.clear()
        self._page_heights = []
        self._page_y_offsets = []
        self._total_h = 0
        if not self._doc:
            return
        self._calc_page_metrics()
        self._canvas.setFixedSize(self._pw, self._total_h)
        self._dirty = True
        self._canvas.update()

        # 重置滚动条
        sb = self.verticalScrollBar()
        target = self._page_y_offsets[self._cur] if self._cur < len(self._page_y_offsets) else 0
        sb.setValue(max(0, min(target, sb.maximum())))
        self._canvas.update()

    def set_zoom(self, z):
        z = max(0.2, min(4.0, z))
        if abs(z - self._zoom) < 0.001:
            return
        self._zoom = z
        self._recalc_sizes()

    def zfw(self):
        if not self._doc:
            return
        vw = self.viewport().width()
        if vw <= 0:
            return
        self._zoom = vw / self._doc[0].rect.width
        self._recalc_sizes()

    def zi(self):
        self.set_zoom(self._zoom * 1.3)

    def zo(self):
        self.set_zoom(self._zoom / 1.3)

    # ── PDF 全文检索 ──

    def search_text(self, query: str) -> int:
        self._search_results = {}
        self._search_flat = []
        self._search_idx = -1
        self._search_query = query

        if not query or not self._doc:
            self._pm_cache.clear()
            self._canvas.update()
            return 0

        for page_idx in range(self._total):
            try:
                page = self._doc[page_idx]
                rects = page.search_for(query)
                if rects:
                    self._search_results[page_idx] = rects
                    for r in rects:
                        self._search_flat.append((page_idx, r))
            except Exception:
                pass

        self._pm_cache.clear()
        if self._search_flat:
            self._search_idx = 0
            page_idx, _ = self._search_flat[0]
            self.go_to(page_idx + 1)
        else:
            self._canvas.update()
        return len(self._search_flat)

    def search_next(self):
        if not self._search_flat:
            return ""
        cur_match_page = self._search_flat[self._search_idx][0]
        if cur_match_page == self._cur:
            # 高亮在本页 → 正常递增
            self._search_idx = (self._search_idx + 1) % len(self._search_flat)
        else:
            # 用户手动翻页离开了 → 从当前页之后找第一个匹配
            for i in range(len(self._search_flat)):
                p = self._search_flat[i][0]
                if p > self._cur and i != self._search_idx:
                    self._search_idx = i
                    break
            else:
                # 之后没有 → 从头
                self._search_idx = 0
        page_idx, _ = self._search_flat[self._search_idx]
        self.go_to(page_idx + 1)
        return f"第{self._search_idx + 1}/{len(self._search_flat)}个"

    def search_prev(self):
        if not self._search_flat:
            return ""
        cur_match_page = self._search_flat[self._search_idx][0]
        if cur_match_page == self._cur:
            # 高亮在本页 → 正常递减
            self._search_idx = (self._search_idx - 1) % len(self._search_flat)
        else:
            # 用户手动翻页离开了 → 从当前页之前找最后一个匹配
            best = -1
            for i, (p, _) in enumerate(self._search_flat):
                if p < self._cur and i != self._search_idx:
                    best = i
            if best >= 0:
                self._search_idx = best
            else:
                # 之前没有 → 从末尾
                self._search_idx = len(self._search_flat) - 1
        page_idx, _ = self._search_flat[self._search_idx]
        self.go_to(page_idx + 1)
        return f"第{self._search_idx + 1}/{len(self._search_flat)}个"

    def clear_search(self):
        self._search_results = {}
        self._search_flat = []
        self._search_idx = -1
        self._search_query = ""
        self._pm_cache.clear()
        self._canvas.update()

    # ── 文字选取 ──

    def _on_mouse_down(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start = event.pos()
            # 加载点击所在页的词坐标
            page_idx = bisect.bisect_right(self._page_y_offsets, event.pos().y()) - 1
            if 0 <= page_idx < self._total:
                self._load_words(page_idx)
            self._sel_words = []
            self._has_sel = False

    def _on_mouse_move(self, event):
        pass

    def _on_mouse_up(self, event):
        if self._drag_start is None:
            return
        r = QRect(self._drag_start, event.pos()).normalized()
        self._drag_start = None
        if r.width() < 5 and r.height() < 5:
            self._has_sel = False
            self._sel_words = []
            self._canvas.update()
            return

        # 转换到页面坐标
        page_idx = bisect.bisect_right(self._page_y_offsets, r.center().y()) - 1
        page_idx = max(0, min(self._total - 1, page_idx))
        page_origin = self._page_y_offsets[page_idx] if page_idx < len(self._page_y_offsets) else 0
        self._load_words(page_idx)
        dr = fitz.Rect(
            r.left() / self._zoom,
            (r.top() - page_origin) / self._zoom,
            r.right() / self._zoom,
            (r.bottom() - page_origin) / self._zoom
        )
        self._sel_words = [i for i, (wr, _) in enumerate(self._words) if wr.intersects(dr)]
        self._sel_words.sort(key=lambda i: (self._words[i][0].y0, self._words[i][0].x0))
        self._has_sel = len(self._sel_words) > 0
        self._dirty = True
        self._canvas.update()

    def get_sel(self):
        if not self._has_sel:
            return ""
        return " ".join(self._words[i][1] for i in self._sel_words)

    def copy_page(self):
        """复制当前页文字（有选区时优先复制选区）"""
        s = self.get_sel()
        if s:
            QApplication.clipboard().setText(s)
            return s
        if not self._doc:
            return ""
        t = self._doc[self._cur].get_text("text").strip()
        QApplication.clipboard().setText(t)
        return t

    def copy_full_page(self):
        """始终复制当前页全部文字（忽略选区）"""
        if not self._doc:
            return ""
        try:
            # OCR 生成的 PDF 中 get_text("text") 可能只返回第一行，
            # 改用 get_text("words") 按坐标排序后完整拼接
            page = self._doc[self._cur]
            words = page.get_text("words")  # [(x0,y0,x1,y1,"字",block,line,word), ...]
            if words:
                # 按行号分组，行内按 x 排序
                lines = {}
                for w in words:
                    ln = w[6]  # line number
                    lines.setdefault(ln, []).append(w)
                parts = []
                for ln in sorted(lines.keys()):
                    line_words = sorted(lines[ln], key=lambda w: w[0])  # sort by x0
                    line_text = "".join(w[4] for w in line_words)
                    parts.append(line_text)
                t = "\n".join(parts).strip()
            else:
                t = page.get_text("text").strip()
            citation = f"\n\n【出处：{os.path.basename(self._source_path)} 第{self._cur + 1}页】"
            QApplication.clipboard().setText(t + citation)
            return t + citation
        except Exception as e:
            print(f"复制整页失败: {e}")
            return ""


# ── PdfViewPanel（与之前一致）──

class PlaceholderPage(QWidget):
    openFileRequested = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        lo = QVBoxLayout(self)
        lo.setAlignment(Qt.AlignCenter)
        t = QLabel("点击下方按钮打开 PDF 文件")
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet("color:#888; font-size:11pt;")
        lo.addWidget(t)
        b = QPushButton("打开 PDF 文件")
        b.setFixedSize(160, 36)
        b.clicked.connect(self.openFileRequested.emit)
        lo.addWidget(b, alignment=Qt.AlignCenter)


class PdfViewPanel(QWidget):
    openFileRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._reader = PdfScrollArea()

        # 搜索防抖定时器
        self._search_debounce = QTimer(self)
        self._search_debounce.setSingleShot(True)
        self._search_debounce.setInterval(800)  # 800ms 无输入后自动搜索
        self._search_debounce.timeout.connect(self._do_search)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._reader)
        ph = PlaceholderPage()
        ph.openFileRequested.connect(self.openFileRequested.emit)
        self._stack.addWidget(ph)

        self._search_bar = QWidget()
        self._search_bar.setObjectName("pdfSearchBar")
        self._search_bar.setVisible(False)
        self._search_bar.setStyleSheet("background:#f5f5f5;border-top:1px solid #ddd;")
        sl = QHBoxLayout(self._search_bar)
        sl.setContentsMargins(6, 3, 6, 3)
        sl.setSpacing(4)

        self._si = QLineEdit()
        self._si.setPlaceholderText("全文检索 (自动搜索)...")
        self._si.setStyleSheet("padding:3px 6px;border:1px solid #ccc;border-radius:3px;background:white;")
        orig_key = self._si.keyPressEvent
        def _si_key(e):
            if e.key() in (Qt.Key_Return, Qt.Key_Enter):
                self._search_debounce.stop()  # 取消防抖
                if e.modifiers() == Qt.ShiftModifier:
                    self._on_search_prev()
                else:
                    self._on_search_enter()
            else:
                orig_key(e)
        self._si.keyPressEvent = _si_key
        self._si.textChanged.connect(lambda: self._search_debounce.start())
        sl.addWidget(self._si, 1)

        self._ml = QLabel("")
        self._ml.setStyleSheet("color:#666;font-size:11px;")
        sl.addWidget(self._ml)

        self._pb = QPushButton("<")
        self._pb.setFixedWidth(26)
        self._pb.setStyleSheet("padding:1px 4px;border:1px solid #aaa;border-radius:2px;background:#eee;")
        self._pb.clicked.connect(self._on_search_prev)
        self._pb.setVisible(False)
        sl.addWidget(self._pb)

        self._nb = QPushButton(">")
        self._nb.setFixedWidth(26)
        self._nb.setStyleSheet("padding:1px 4px;border:1px solid #aaa;border-radius:2px;background:#eee;")
        self._nb.clicked.connect(self._on_search_next)
        self._nb.setVisible(False)
        sl.addWidget(self._nb)

        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(0)
        lo.addWidget(self._search_bar)
        lo.addWidget(self._stack, 1)
        self._stack.setCurrentIndex(0)

    def show_placeholder(self):
        self._search_bar.setVisible(False)
        self._stack.setCurrentIndex(1)

    def load_pdf(self, p):
        ok = self._reader.load(p)
        if ok:
            self._search_bar.setVisible(False)
            self._stack.setCurrentIndex(0)
        return ok

    def clear(self):
        self._reader.clear()
        self._search_bar.setVisible(False)

    def go_to_page(self, n):
        self._reader.go_to(n)

    def zoom_fit_width(self):
        self._reader.zfw()

    def zoom_in(self):
        self._reader.zi()

    def zoom_out(self):
        self._reader.zo()

    def set_zoom(self, z):
        self._reader.set_zoom(z)

    def copy_page_text(self):
        return self._reader.copy_page()

    def copy_full_page_text(self):
        return self._reader.copy_full_page()

    def toggle_search_bar(self):
        if self._stack.currentIndex() != 0:
            return
        v = not self._search_bar.isVisible()
        self._search_bar.setVisible(v)
        if v:
            self._si.setFocus()
            self._si.selectAll()
        else:
            self._reader.clear_search()
            self._ml.setText("")
            self._pb.setVisible(False)
            self._nb.setVisible(False)

    def _do_search(self):
        q = self._si.text().strip()
        n = self._reader.search_text(q)
        if n:
            self._ml.setText(f"第1/{n}个")
            self._pb.setVisible(True)
            self._nb.setVisible(True)
        else:
            self._ml.setText("无匹配" if q else "")
            self._pb.setVisible(False)
            self._nb.setVisible(False)

    def _on_search_next(self):
        label = self._reader.search_next()
        if label:
            self._ml.setText(label)

    def _on_search_prev(self):
        label = self._reader.search_prev()
        if label:
            self._ml.setText(label)

    def _on_search_enter(self):
        """Enter: 重新搜索当前关键词 / 再次按跳下一个"""
        q = self._si.text().strip()
        if q != self._reader._search_query:
            # 关键词已变（包括清空）→ 重新搜索
            self._do_search()
        elif self._reader._search_flat:
            # 关键词不变 → 跳下一个
            self._on_search_next()
        else:
            self._do_search()

    @property
    def pageChanged(self):
        return self._reader.pageChanged

    @property
    def current_page(self):
        return self._reader._cur + 1

    @property
    def total_pages(self):
        return self._reader._total
