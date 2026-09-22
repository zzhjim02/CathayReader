# Cathay Reader

> **Cathay 工具链主线第 ⑤ 步 · 双栏同步阅读器** | [CathayIndex](https://github.com/zzhjim02/CathayIndex) · [CathayFinder](https://github.com/zzhjim02/CathayFinder) · [CathayOCR](https://github.com/zzhjim02/CathayOCR) · [CathayShelf](https://github.com/zzhjim02/CathayShelf) · [CathayReader](https://github.com/zzhjim02/CathayReader)

一款专为古籍 OCR 校勘工作设计的桌面阅读器。将 OCR 识别后的 PDF 与 TXT 文件双栏并排展示，支持同步翻页、多版本 TXT 切换、PDF 文字检索与复制，大幅提升古籍校勘效率。

---


## 🔗 Cathay 人文社科工具链

> 🧭 主线一句话：**CathayIndex 建本地库 → CathayFinder 查书 → CathayPDG 把查到的书（读秀/超星 PDG）转成 PDF → CathayOCR 识别 → CathayShelf 著录归架 → CathayReader 双栏校勘。**

| 步骤 | 工具 | 功能 | 状态 |
|:---:|---|---|---|
| ① | [CathayIndex](https://github.com/zzhjim02/CathayIndex) | v1.0.0 | 把本地文件夹建成可检索的「本地文件库」 |
| ② | [CathayFinder](https://github.com/zzhjim02/CathayFinder) | v1.0.0 | 综合性图书检索引擎：11 个渠道精准查书（找 SSID / 找路径） |
| ③ | [CathayPDG](https://github.com/zzhjim02/CathayPDG) | v0.1.5 | 读秀/超星 **PDG 批量转 PDF**：解压解密、横竖排分柜（把查到的书变成 PDF） |
| ④ | [CathayOCR](https://github.com/zzhjim02/CathayOCR) | v1.2.4 | 扫描件 OCR，产出可搜索文字层 PDF |
| ⑤ | [CathayShelf](https://github.com/zzhjim02/CathayShelf) | v0.4.5 | 图书著录自动化整理（一 PDF 一夹、命名规范化） |
| ⑥ | **CathayReader（你在这里）** | v1.0.0 | 双栏校勘阅读器 |

**备用软件（四个，按需取用）**

| 工具 | 什么时候用 |
|---|---|
| [CathayRepair](https://github.com/zzhjim02/CathayRepair) | ④ OCR 前：PDF 目录结构坏了先修一下 |
| [CathayRestore](https://github.com/zzhjim02/CathayRestore) | ④ 之后：把 OCR 的 TXT 写回成竖排可搜索文字层 |
| [CathayExtract](https://github.com/zzhjim02/CathayExtract) | ④ 的替代入口：已经有字层的双层 PDF，直接抽 TXT |
| [CathaySimplify](https://github.com/zzhjim02/CathaySimplify) | 繁简转换 / 编码规范化（功能已并入 ⑤ CathayShelf） |

---

## 软件截图

```
┌────────────────────────────────────────────────┐
│  📁 打开目录  🔍搜索  ➕放大  ➖缩小  上页 下页  │
├────────────────────────────────────────────────┤
│ 目录: D:\古籍库\经部\西征纪程 │ 册: 第01册  │
│ 文本: 原文 │ OCR: PPOCR-VL1.6 │ 字号: 11  │
├────────────────────────────────────────┬───────┤
│ [PDF 渲染区]                           │ [TXT] │
│                                        │ 第1页  │
│  古籍扫描页图片                         │ 正文… │
│  页码浮层: 第 1 页                      │       │
│                                        │ 第2页  │
│                                        │ 正文… │
├────────────────────────────────────────┴───────┤
│ 就绪                         第 1/212 页       │
└────────────────────────────────────────────────┘
```

---

## 功能总览

### 📖 核心阅读
| 功能 | 说明 |
|------|------|
| **双栏同步阅读** | PDF 左栏 + TXT 右栏，翻页自动同步 |
| **虚拟滚动渲染** | 大 PDF 流畅滚动，仅渲染可见页 |
| **页码浮层** | 每页 PDF 图片上方叠加页码（半透明黑底白字） |
| **TXT 翻页定位** | 根据页码标记自动定位到相应文本位置 |

### 🔍 OCR 文件管理
| 功能 | 说明 |
|------|------|
| **自动配对** | 同一目录下 PDF 与 TXT 按文件名自动配对 |
| **多版本 TXT** | 支持多种 OCR 引擎输出共存，一键切换 |
| **自定义后缀** | 可配置任意 PDF/TXT 文件名后缀映射关系 |
| **孤立文件** | 无对应 TXT 的 PDF 或纯文本文件也能加载 |

### 🔎 搜索与复制
| 功能 | 说明 |
|------|------|
| **PDF 全文检索** | Ctrl+F 打开搜索栏，跨页高亮，▲/▼ 跳转 |
| **PDF 目录导航** | Ctrl+T 打开左侧目录侧栏，点击跳转到对应页面 |
| **PDF 文字复制** | 鼠标拖拽逐词高亮，Ctrl+Shift+C 复制 |
| **整页文字复制** | 右键菜单选中「复制本页全部文字」 |
| **出处自动标注** | 复制内容末尾自动追加 `【出处：文件名 第XX页】` |

### 🛠 工具与配置
| 功能 | 说明 |
|------|------|
| **后缀设置** | 图形化表格编辑器，任意多组后缀映射 |
| **文本模式切换** | 原文 / 繁转简 一键切换 |
| **字号调整** | TXT 字体大小实时调节 |
| **独立打开文件** | Ctrl+Shift+O 打开单个文件，自动查找配对 |
| **拖入打开** | 直接拖入 .pdf / .txt 文件或目录 |
| **注册文件关联** | 「设为默认」按钮，.pdf 文件双击用本软件打开 |
| **键盘快捷键** | ← → 翻页，Ctrl+O 开文件夹，Ctrl+F 搜索，Ctrl+T 目录，Ctrl++ 缩放 |

---

## 支持的 OCR 后缀体系

软件自动识别并优先排序以下 OCR 输出版本：

| 层级 | 后缀标识 | OCR 引擎 |
|------|---------|----------|
| 1 | `_PDVL6AIFOCR` / `_PDVL6AIOCR` | PaddleOCR-VL1.6 |
| 2 | `_PDVL5AIFOCR` / `_PDVL5AIOCR` | PaddleOCR-VL1.5 |
| 3 | `_layered` / `_result` | CathayOCR 轻量版/专业版/开发版 |
| 4 | `_PD6AIFOCR` / `_PD6AIOCR` | PaddleOCR V6 |
| 5 | `_PD5AIFOCR` / `_PD5AIOCR` | PaddleOCR V5 |
| 6 | `_AIFOCR` / `_AIOCR` |  AI OCR 通用 |
| 7 | `_FOCR` / `_OCR` | 传统 OCR |

> 文件名示例：`西征纪程_PDVL6AIFOCR.txt` → 自动识别为 PPOCR-VL1.6 版本

---

## 快速开始

### 下载
从 [Releases](../../releases) 下载 `Cathay Reader v1.0.zip`，解压即可运行 `Cathay Reader.exe`（单文件，无需安装 Python）。

### 使用步骤

1. **运行**：双击 `Cathay Reader.exe`
2. **打开文件夹**：点击工具栏「打开文件夹 [Ctrl+O]」，选择存放古籍 PDF/TXT 的文件夹
3. **自动加载**：软件自动扫描目录，按文件名配对 PDF 和 TXT
4. **翻阅**：在「册」下拉框选择卷册，用 ← → 或「上页/下页」按钮翻页
5. **切换 OCR 版本**：在「OCR」下拉框选择不同引擎的识别结果
6. **搜索**：按 Ctrl+F 打开搜索栏，输入关键词，支持 ▲/▼ 跳转

### 自定义后缀匹配

当 PDF 和 TXT 文件名不加标准 OCR 后缀时：

1. 点击工具栏「后缀设置」
2. 在表格中一行一个配对：`_扫校版` → `_校对稿`
3. 保存后重新打开目录生效

---

## 系统要求

- **操作系统**：Windows 7 / 10 / 11（64位）
- **依赖**：无需安装 Python（单文件 exe）
- **推荐**：内存 1GB 以上，CPU 支持 SSE2

---

## 开发指南

### 环境
```bash
pip install PyMuPDF PyQt5
```

### 模块结构
```
Cathay Reader DEV/
├── main.py              # 入口（环境修复、崩溃保护）
├── ui_main.py           # 主窗口（工具栏、信息栏、双栏布局）
├── pdf_view.py          # PDF 渲染（虚拟滚动、搜索、文字选择）
├── txt_view.py          # TXT 显示（翻页定位、搜索）
├── file_matcher.py      # 文件配对（OCR 后缀检测、自定义映射）
├── page_parser.py       # 页码解析（多格式自动检测）
└── README.md            # 本说明文件
```

### 打包
```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "Cathay Reader" ^
  --hidden-import fitz --hidden-import PyQt5.sip ^
  --hidden-import PyQt5.QtCore --hidden-import PyQt5.QtGui ^
  --hidden-import PyQt5.QtWidgets main.py
```

---

## 许可

本项目遵循 [GPL-3.0 License](LICENSE)。

配套 OCR 引擎：[CathayOCR](https://github.com/zzhjim02/CathayOCR) — 古籍专用高精度 OCR 工具集。
