"""
file_matcher.py - 文件匹配器
支持多种 OCR 后缀体系，一个 PDF 对应多个 OCR 版本的 TXT。
"""

import os
import re
import json
from typing import List, Optional, Dict, Tuple

# ========== 后缀定义 ==========
# 可压缩后缀（始终放到最后）
OPT_SUFFIXES = ('_OPT', '_opt', '_Opt')

# 繁转简标记
SIMPLE_TAG = '_【繁转简】'

# OCR 后缀（从长到短排列，剥离时从右到左优先匹最长）
# 每个元素: (suffix, label_显示名)
OCR_SUFFIXES = [
    ('_PDVL6AIFOCR', 'PPOCR-VL1.6'),
    ('_PDVL6AIOCR',  'PPOCR-VL1.6'),
    ('_PDVL5AIFOCR', 'PPOCR-VL1.5'),
    ('_PDVL5AIOCR',  'PPOCR-VL1.5'),
    ('_layered',     'CATHAYOCR(导出)'),
    ('_result',      'CATHAYOCR(结果)'),
    ('_PD6AIFOCR',   'PPOCR V6'),
    ('_PD6AIOCR',    'PPOCR V6'),
    ('_PD5AIFOCR',   'PPOCR V5'),
    ('_PD5AIOCR',    'PPOCR V5'),
    ('_AIFOCR',      '第1代AI'),
    ('_AIOCR',       '第1代AI'),
    ('_FOCR',        '传统OCR'),
    ('_OCR',         '传统OCR'),
]

# OCR 后缀纯字符串列表（供剥离用）
OCR_SUFFIX_STRS = [s for s, _ in OCR_SUFFIXES]

# 后缀 → 标签映射
SUFFIX_TO_LABEL = dict(OCR_SUFFIXES)

DEFAULT_LABEL = '原件'


# ========== 后缀剥离工具 ==========

def strip_ocr_suffixes(name: str) -> Tuple[str, List[str]]:
    """从右到左迭代剥离所有已知 OCR 后缀。
    返回 (剥离后基名, 剥离的OCR后缀列表[从右到左])。
    额外处理：_OCR / _FOCR 后接描述文字（如 _OCR优化）也整体剥离。
    """
    stripped = []
    changed = True
    while changed:
        changed = False
        for sfx in OCR_SUFFIX_STRS:
            if name.endswith(sfx):
                stripped.append(sfx)
                name = name[:-len(sfx)]
                changed = True
                break
        if not changed:
            # 尝试剥离 _OCR / _FOCR + 描述文字（如 _OCR优化）
            for tag in ('_OCR', '_FOCR'):
                idx = name.rfind(tag)
                if idx >= 0:
                    rest = name[idx + len(tag):]
                    # 描述文字：非 _ 开头的连续字符
                    if rest and not rest.startswith('_'):
                        stripped.append(tag + rest)
                        name = name[:idx]
                        changed = True
                        break
    return name, stripped


def strip_all(name: str) -> Tuple[str, List[str]]:
    """剥离 _OPT + 所有 OCR 后缀。
    返回 (根名, 剥离后缀列表)。
    """
    # 1. 剥离 _OPT
    for ign in OPT_SUFFIXES:
        if name.endswith(ign):
            name = name[:-len(ign)]
            break
    # 2. 剥离 OCR 后缀
    root, _ = strip_ocr_suffixes(name)
    return root, _  # Return just suffix list for the last OCR


def get_ocr_label(stripped_suffixes: List[str]) -> str:
    """从剥离的OCR后缀列表中提取版本标签。
    取最右端（最先被剥离的）OCR 后缀作为版本标识。
    对 _OCR优化 / _FOCR版 等带描述的后缀，回退到基础后缀的标签。
    """
    if not stripped_suffixes:
        return DEFAULT_LABEL
    rightmost = stripped_suffixes[0]  # 最先被剥离 = 最右端
    if rightmost in SUFFIX_TO_LABEL:
        return SUFFIX_TO_LABEL[rightmost]
    # 带描述文字：检查是否以已知 OCR 后缀开头
    for sfx_full, lbl in OCR_SUFFIXES:
        if rightmost.startswith(sfx_full):
            return lbl
    return rightmost  # 未知后缀


def identify_txt_variant(basename: str) -> Tuple[str, str, bool]:
    """分析 TXT 文件名，返回 (根名, OCR标签, 是否繁转简)。"""
    # 去除 .txt 扩展（大小写不敏感）
    if basename.lower().endswith('.txt'):
        name = basename[:-4]
    else:
        name = basename
    # 是否繁转简
    is_simple = name.endswith(SIMPLE_TAG)
    if is_simple:
        name = name[:-len(SIMPLE_TAG)]
    # 剥离 _OPT
    for ign in OPT_SUFFIXES:
        if name.endswith(ign):
            name = name[:-len(ign)]
            break
    # 剥离 OCR 后缀
    root, stripped_suffixes = strip_ocr_suffixes(name)
    ocr_label = get_ocr_label(stripped_suffixes)
    return root, ocr_label, is_simple


def identify_pdf_variant(basename: str) -> Tuple[str, str]:
    """分析 PDF 文件名，返回 (根名, OCR标签)。"""
    if basename.lower().endswith('.pdf'):
        name = basename[:-4]
    else:
        name = basename
    # 剥离 _OPT
    for ign in OPT_SUFFIXES:
        if name.endswith(ign):
            name = name[:-len(ign)]
            break
    root, stripped_suffixes = strip_ocr_suffixes(name)
    ocr_label = get_ocr_label(stripped_suffixes)
    return root, ocr_label


# ========== OCR 版本排序优先级 ==========
# 越靠前越优先
PRIORITY_ORDER = [
    'PPOCR-VL1.6', 'PPOCR-VL1.6',
    'PPOCR-VL1.5', 'PPOCR-VL1.5',
    'CATHAYOCR', 'CATHAYOCR',
    'PPOCR V6',    'PPOCR V6',
    'PPOCR V5',    'PPOCR V5',
    '第1代AI',     '第1代AI',
    '传统OCR',     '传统OCR',
    '原件',
]


def sort_ocr_labels(labels: List[str]) -> List[str]:
    """按品质排序（最优在前）。"""
    def rank(l):
        try:
            return PRIORITY_ORDER.index(l)
        except ValueError:
            return 999
    return sorted(labels, key=rank)


# ========== FilePair ==========

class FilePair:
    """一个 PDF 及其对应的多个 OCR 版本 TXT。"""

    def __init__(self, pdf_path: str, root_name: str):
        self.pdf_path = pdf_path
        self.root_name = root_name
        # {ocr_label: {"orig": txt_path, "simple": txt_path}}
        self.txt_variants: Dict[str, Dict[str, str]] = {}

    def add_txt(self, ocr_label: str, txt_path: str, is_simple: bool):
        key = "simple" if is_simple else "orig"
        if ocr_label not in self.txt_variants:
            self.txt_variants[ocr_label] = {"orig": "", "simple": ""}
        self.txt_variants[ocr_label][key] = txt_path

    @property
    def name(self) -> str:
        """显示名，用作下拉框条目"""
        return self.root_name

    @property
    def pdf_name(self) -> str:
        return os.path.basename(self.pdf_path)

    def get_txt_path(self, ocr_label: str, use_simple: bool) -> str:
        variant = self.txt_variants.get(ocr_label)
        if not variant:
            return ""
        key = "simple" if use_simple else "orig"
        return variant.get(key, "")

    def get_available_labels(self) -> List[str]:
        return sort_ocr_labels(list(self.txt_variants.keys()))

    def get_default_label(self) -> str:
        labels = self.get_available_labels()
        return labels[0] if labels else DEFAULT_LABEL

    def __repr__(self):
        return f"FilePair({self.pdf_name} <-> {len(self.txt_variants)} variants)"


SIMPLE_RE = re.compile(r'_?' + re.escape('【繁转简】') + '$')


class FileMatcher:
    """扫描目录，自动将 PDF 与同源的多个 OCR 版本 TXT 配对。"""

    CONFIG_FILE = ".filematcher_config"

    def __init__(self, directory: str):
        self.directory = directory
        self.pairs: List[FilePair] = []
        self.combined_txt: Optional[str] = None
        self.error: Optional[str] = None
        self.suffix_pairs = self._load_config()

    def _load_config(self) -> list:
        config_path = os.path.join(self.directory, self.CONFIG_FILE)
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            raw = config if isinstance(config, list) else config.get('suffix_map', [])
            return raw
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save_config(self, suffix_pairs: list):
        config_path = os.path.join(self.directory, self.CONFIG_FILE)
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump({'suffix_map': suffix_pairs}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def set_suffix_pairs(self, pairs: list):
        self.suffix_pairs = pairs
        self._save_config(pairs)

    def scan(self) -> List[FilePair]:
        """扫描目录，按根名分组配对。"""
        self.pairs = []
        self.combined_txt = None

        if not os.path.isdir(self.directory):
            self.error = f"目录不存在: {self.directory}"
            return []

        try:
            all_files = os.listdir(self.directory)
        except PermissionError as e:
            self.error = f"无权限访问目录: {e}"
            return []

        # 第一遍：识别所有 PDF 和 TXT 的根名
        pdf_map: Dict[str, str] = {}      # root_name → pdf_path
        txt_groups: Dict[str, list] = {}   # root_name → [(ocr_label, txt_path, is_simple)]

        for fname in all_files:
            fpath = os.path.join(self.directory, fname)
            if not os.path.isfile(fpath):
                continue

            lower = fname.lower()
            if lower.endswith('.pdf'):
                root, _ = identify_pdf_variant(fname)
                # 也尝试用户自定义后缀
                custom_matched = False
                if self.suffix_pairs:
                    base = fname[:-4]  # 去掉 .pdf
                    for pdf_sfx, txt_sfx in self.suffix_pairs:
                        if base.endswith(pdf_sfx):
                            alt = base[:-len(pdf_sfx)]
                            if alt not in pdf_map:
                                pdf_map[alt] = fpath
                            custom_matched = True
                            break  # 一个文件只匹配第一个自定义后缀
                # 优先保留无 OPT 的版本
                # 自定义后缀已匹配且OCR没变 → 不添加 OCR 根（避免孤立条目）
                if root not in pdf_map:
                    base_noext = fname[:-4]
                    if not custom_matched or root != base_noext:
                        pdf_map[root] = fpath
            elif lower.endswith('.txt'):
                root, ocr_label, is_simple = identify_txt_variant(fname)
                # 也尝试用户自定义后缀
                custom_matched = False
                if self.suffix_pairs:
                    base = fname[:-4]  # 去掉 .txt
                    for pdf_sfx, txt_sfx in self.suffix_pairs:
                        if base.endswith(txt_sfx):
                            alt = base[:-len(txt_sfx)]
                            custom_label = txt_sfx
                            txt_groups.setdefault(alt, [])
                            # 避免重复
                            dup = any(lbl == custom_label and p == fpath for lbl, p, _ in txt_groups[alt])
                            if not dup:
                                txt_groups[alt].append((custom_label, fpath, False))
                            custom_matched = True
                            break  # 一个文件只匹配第一个自定义后缀
                # 自定义后缀已匹配且OCR没变 → 不添加 OCR 根（避免孤立条目）
                base_noext = fname[:-4]
                if not custom_matched or root != base_noext:
                    txt_groups.setdefault(root, [])
                    for i, (lbl, p, simp) in enumerate(txt_groups[root]):
                        if lbl == ocr_label and simp == is_simple:
                            if len(os.path.basename(fpath)) < len(os.path.basename(p)):
                                txt_groups[root][i] = (ocr_label, fpath, is_simple)
                            break
                    else:
                        txt_groups[root].append((ocr_label, fpath, is_simple))

        # 第二遍：构建 FilePair
        paired_roots = set(pdf_map.keys()) & set(txt_groups.keys())
        orphan_txt_roots = set(txt_groups.keys()) - set(pdf_map.keys())

        for root in sorted(paired_roots):
            pair = FilePair(pdf_map[root], root)
            for ocr_label, txt_path, is_simple in txt_groups[root]:
                pair.add_txt(ocr_label, txt_path, is_simple)
            self.pairs.append(pair)

        # 只有 TXT 没有 PDF 的也加入（占位 PDF）
        for root in sorted(orphan_txt_roots):
            pair = FilePair("", root)
            for ocr_label, txt_path, is_simple in txt_groups[root]:
                pair.add_txt(ocr_label, txt_path, is_simple)
            self.pairs.append(pair)

        # 只有 PDF 没有 TXT 的也加入
        orphan_pdf_roots = set(pdf_map.keys()) - paired_roots - orphan_txt_roots
        for root in sorted(orphan_pdf_roots):
            pair = FilePair(pdf_map[root], root)
            self.pairs.append(pair)

        # 排序
        def sort_key(p: FilePair) -> tuple:
            nums = re.findall(r'\d+', p.name)
            return (int(nums[0]) if nums else 0, p.name)
        self.pairs.sort(key=sort_key)

        return self.pairs

    def _exact_match(self, pdf_files, txt_files, simple_txt_files):
        """旧版兼容：精确匹配，现在不用了"""
        pass

    def _prefix_match(self, pdf_files, txt_files, simple_txt_files, matched: set):
        pass

    def _add_orphan_pdfs(self, pdf_files: dict):
        pass

    def _strip_one(self, name: str, suffixes: list) -> str:
        for suffix in suffixes:
            if suffix and name.endswith(suffix):
                return name[:-len(suffix)]
        return name

    def get_pair_count(self) -> int:
        return len(self.pairs)

    def get_pair_names(self) -> List[str]:
        return [p.name for p in self.pairs]

    def get_pair_by_index(self, index: int) -> Optional[FilePair]:
        if 0 <= index < len(self.pairs):
            return self.pairs[index]
        return None

    def get_pair_by_name(self, name: str) -> Optional[FilePair]:
        for p in self.pairs:
            if p.name == name:
                return p
        return None
