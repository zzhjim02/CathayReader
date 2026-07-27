<div align="center">

# 📖 Cathay Reader

**面向人文社科研究者的TXT/PDF双栏同步阅读器**

*古籍 OCR 结果 PDF + TXT 双栏对照阅读*

</div>

---


## 🔗 Cathay 人文研究工具链

<div align="center">

| 步骤 | 工具 | 功能 | 状态 |
|:----:|:----|:----|:----:|
| ① | [**CathayOCR**](https://github.com/zzhjim02/CathayOCR) | 📄 多引擎 GPU 加速古籍 PDF 批处理 OCR | ✅ v1.1.0 |
| ② | [**CathaySimplify**](https://github.com/zzhjim02/CathaySimplify) | 🔄 TXT 繁简体批量双向转换 | ✅ v1.0.0 |
| ③ | **⭐ CathayReader (你在这里)** | 📖 PDF/TXT 双栏同步古籍校勘阅读器 | ✅ v1.0.0 |

</div>

**典型工作流：**
```
CathayOCR (OCR 古籍 PDF → 繁体 TXT) → CathaySimplify (繁→简) → CathayReader (双栏校勘)
```

---


## 📋 这是什么？

**Cathay Reader** 是 [**CathayOCR**](https://github.com/zzhjim02/CathayOCR) 的**配套阅读器**，专门用来对照阅读 CathayOCR 输出的双层 PDF 和纯文本 TXT 文件，也可作为普通阅读器使用。

> CathayOCR 处理古籍 PDF 后，每本书会生成两个文件：
> - `*_layered.pdf` — 图像+文字双层 PDF
> - `*_result.txt` — 纯文本识别结果
>
> Cathay Reader 将它们**左右并排显示**，左侧 PDF、右侧 TXT，同步滚动，方便校勘。

---

## ✨ 功能特性

| 功能 | 说明 |
|:----|:------|
| 📂 **智能配对** | 自动匹配同名的 PDF + TXT（支持 7 级 OCR 输出后缀），拖入任意一个即自动配对 |
| 📑 **双栏同步** | 左侧 PDF 渲染页、右侧 TXT 分页，滚动/翻页同步 |
| 🔍 **全文搜索** | Ctrl+F 搜索，PDF 和 TXT 侧同时高亮，搜索结果可上下跳转 |
| 📄 **复制文字** | 选中复制（Ctrl+C）、复制整页（Ctrl+Shift+C）、**复制整页含出处标注**（Ctrl+Shift+D） |
| 🔤 **繁简切换** | TXT 侧一键繁简转换（OpenCC） |
| 🎯 **页码智能检测** | 自动识别 OCR 输出中的 `≦N≧` / `第N页` / `===N===` 页码格式 |
| 🔒 **加密 PDF 保护** | 加密 PDF 优雅提示，不会崩溃 |
| 🖼️ **QPainter 渲染** | 虚拟滚动 + 后台增量渲染，大 PDF 流畅不卡 |

### 快捷键

| 快捷键 | 功能 |
|:------|:-----|
| `Ctrl+O` | 打开文件 |
| `Ctrl+F` | 搜索 |
| `F3` / `Shift+F3` | 搜索下一个 / 上一个 |
| `Ctrl+C` | 复制选中文字 |
| `Ctrl+Shift+C` | 复制当前页全部文字 |
| `Ctrl+Shift+D` | 复制当前页全部文字 + 出处标注 |
| `Ctrl++` / `Ctrl+-` | 放大 / 缩小 |
| `Ctrl+0` | 适应宽度 |
| `PgUp` / `PgDn` | 上下翻页 |
| `Home` / `End` | 跳到首页 / 末页 |
| `Ctrl+Q` | 退出程序 |

---

## 🚀 快速上手

```bash
1. 下载并打开 Cathay Reader
2. 点击「打开 PDF 文件」或 Ctrl+O
3. 选择任一 OCR 输出的 PDF 或 TXT 文件
4. 自动配对 → 双栏显示 → 开始阅读校勘
```

> 💡 **提示**：配对支持的后缀名包括 `.pdf` / `_result.txt` / `_【繁转简】.txt` / `_PD6AIFOCR.txt` 等 7 级 OCR 输出格式。

---

## 🔗 与 CathayOCR 的关系

```
CathayOCR ──→ 批量 OCR 古籍 PDF → 输出双层 PDF + TXT
     ↓
Cathay Reader ──→ 对照阅读 OCR 结果
```

| 工具 | 做什么 | 谁需要 |
|:----|:-------|:-------|
| [**CathayOCR**](https://github.com/zzhjim02/CathayOCR) | 古籍 OCR 工具，把 PDF 扫描件转成可搜索的双层 PDF + TXT | 需要数字化古籍的研究者 |
| **Cathay Reader** | 查看 OCR 结果的阅读器，PDF + TXT 双栏对照 | 需要校勘 OCR 效果的学者 |

> 🚧 **计划中的配套工具**：CathayTranscriber（TXT 繁简转换）、CathayNotes（史料摘录与长编制作）—— 敬请期待！

---

## 🗂️ 项目结构

```
CathayReader/
├── Cathay Reader v1.0.exe   ← 发行版（PyInstaller 单文件打包）
├── main.py                  ← 入口点
├── pdf_view.py              ← PDF 渲染引擎（QPainter + 虚拟滚动）
├── txt_view.py              ← TXT 分页显示
├── ui_main.py               ← 主窗口 + 工具栏 + 快捷键
├── file_matcher.py          ← 7 级 OCR 后缀自动配对
├── page_parser.py           ← 页码格式自动检测
└── README.md                ← 本文件
```

---

## 🛠️ 从源码运行

```bash
# 需要 Python 3.10+，安装依赖：
pip install PyQt5 PyMuPDF

# 运行：
python main.py
```

---

## 📜 许可证

本项目基于 **GPLv3** 许可证开源。

作为 [CathayOCR](https://github.com/zzhjim02/CathayOCR) 的附属项目，与 CathayOCR 采用相同的许可证。
