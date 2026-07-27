"""
page_parser.py - TXT 页码解析器
自动检测多种页码标记格式，兼容不同 CathayOCR 输出。

支持的格式：
  第 N 页              ← 最常见
  ≦ N ≧               ← 另一种常见（西征纪程等）
  === 第 N 页 ===      ← 带装饰线
  --- 第 N 页 ---      ← 带装饰线
"""

import re
from typing import List, Tuple, Optional

# 多个页码模式（按顺序检测，取匹配最多的那个）
PAGE_PATTERNS = [
    # 模式1: ≦ N ≧
    re.compile(r'≦\s*(\d+)\s*≧', re.MULTILINE),
    # 模式2: 第 N 页（带可选 === 装饰线）
    re.compile(
        r'(?:={6,}\s*\n\s*)?'
        r'第\s*(\d+)\s*页'
        r'(?:\s*\n\s*={6,})?',
        re.MULTILINE
    ),
    # 模式3: --- 第 N 页 ---
    re.compile(
        r'(?:-{6,}\s*\n\s*)?'
        r'第\s*(\d+)\s*页'
        r'(?:\s*\n\s*-{6,})?',
        re.MULTILINE
    ),
]


class PageIndex:
    """单册文件的页码索引"""

    def __init__(self, txt_path: str, encoding: str = 'utf-8'):
        self.txt_path = txt_path
        self.encoding = encoding
        self._content: str = ""
        self._pages: List[dict] = []
        self._loaded = False
        self._detected_pattern = None
        self._header_end = 0  # OCR 元数据头结束位置

    def load(self) -> bool:
        """加载文件并解析页码"""
        try:
            with open(self.txt_path, 'r', encoding=self.encoding) as f:
                self._content = f.read()
        except UnicodeDecodeError:
            for enc in ['gbk', 'gb18030', 'utf-8-sig']:
                try:
                    with open(self.txt_path, 'r', encoding=enc) as f:
                        self._content = f.read()
                    self.encoding = enc
                    break
                except UnicodeDecodeError:
                    continue

        if not self._content:
            return False

        # 统一换行为 \n，避免 \r\n 双字节偏移
        if '\r\n' in self._content:
            self._content = self._content.replace('\r\n', '\n')

        self._detect_header()
        self._detect_pattern()
        self._parse_pages()
        self._loaded = True
        return len(self._pages) > 0

    def _detect_header(self):
        """检测并跳过 OCR 元数据头"""
        lines = self._content.split('\n')
        header_end = 0
        for i, ln in enumerate(lines):
            stripped = ln.strip()
            if not stripped:
                continue
            # 时间戳：2026-07-02 04:08:54
            if re.match(r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}', stripped):
                header_end = sum(len(l) + 1 for l in lines[:i + 1])
                continue
            # URL 或路径
            if 'http' in stripped or '\\\\' in stripped:
                header_end = sum(len(l) + 1 for l in lines[:i + 1])
                continue
            break  # 遇到正文行停止
        self._header_end = header_end

    def _detect_pattern(self):
        """自动检测使用哪个页码模式"""
        best = None
        best_count = -1

        for pattern in PAGE_PATTERNS:
            matches = list(pattern.finditer(self._content))
            if len(matches) > best_count:
                best_count = len(matches)
                best = pattern

        self._detected_pattern = best

    def _parse_pages(self):
        """解析所有页码标记"""
        self._pages = []
        if not self._detected_pattern:
            return self._generate_fallback_pages()

        matches = list(self._detected_pattern.finditer(self._content))
        if not matches:
            return self._generate_fallback_pages()

        # 检查匹配是否合理（一册书应有足够页数）
        if len(matches) < 3:
            # 太少匹配，回退
            return self._generate_fallback_pages()

        for i in range(len(matches)):
            try:
                page_num = int(matches[i].group(1))
            except (IndexError, ValueError):
                continue

            # 跳过第一个标记前的 OCR 头
            start_pos = matches[i].end()
            if i == 0:
                # 如果 OCR 头占了很多，跳过它
                if self._content[:matches[i].start()].strip() and \
                   not re.search(r'\w', self._content[:matches[i].start()]):
                    # 标记前全是非文字内容，跳过
                    pass

            if i + 1 < len(matches):
                end_pos = matches[i + 1].start()
            else:
                end_pos = len(self._content)

            self._pages.append({
                'number': page_num,
                'start': start_pos,
                'end': end_pos,
            })

        # 去掉内容为空的页（比如连续标记之间没有正文）
        self._pages = [p for p in self._pages
                       if self._content[p['start']:p['end']].strip()]

        # 如果页码不是从1开始的，尝试调整
        if self._pages and self._pages[0]['number'] > 1:
            pass  # 保持原样

    def _generate_fallback_pages(self):
        """回退方案：按大约 500 字一页划分"""
        lines = self._content.split('\n')
        chars_per_page = 500
        pos = self._header_end
        page_num = 1
        while pos < len(self._content):
            end = min(pos + chars_per_page, len(self._content))
            self._pages.append({
                'number': page_num,
                'start': pos,
                'end': end,
            })
            pos = end
            page_num += 1

    @property
    def page_count(self) -> int:
        return len(self._pages)

    @property
    def content(self) -> str:
        return self._content

    def get_page_text(self, page_number: int) -> str:
        for p in self._pages:
            if p['number'] == page_number:
                return self._content[p['start']:p['end']].strip()
        return ""

    def get_page_range(self, page_number: int) -> Tuple[int, int]:
        for p in self._pages:
            if p['number'] == page_number:
                return (p['start'], p['end'])
        return (0, 0)

    def get_page_at_position(self, pos: int) -> int:
        """根据字符位置返回页码，位置在两页之间时归入后一页"""
        for p in self._pages:
            if p['start'] <= pos < p['end']:
                return p['number']
            # 位置在页标记处（两页之间），归入后一页
            if pos < p['start']:
                return p['number']
        return self._pages[-1]['number'] if self._pages else 1

    def get_detected_pattern(self) -> str:
        if self._detected_pattern is None:
            return "fallback"
        if '≦' in self._detected_pattern.pattern:
            return "≦N≧"
        elif '第' in self._detected_pattern.pattern:
            return "第N页"
        return "other"
