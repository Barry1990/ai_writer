# ✍️ AI 小说生成器 (AI Writer)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.8+](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)

一个基于大语言模型 (LLM) 驱动的自动化小说创作工具。它不仅是简单的文本生成，更是一套完整的小说创作工作流，支持从宏观大纲设计到微观章节描写的全迭代深度创作。

---

## 🔥 核心特性

- **🚀 多模型驱动**: 深度集成 Google Gemini 和 OpenAI，支持灵活切换驱动，适配不同创作需求。
- **🧠 进阶记忆系统**: 动态提取并维护故事梗概、活跃伏笔、人物状态及场景信息，彻底告别剧情断层。
- **📅 结构化创作流**: 遵循「核心构思 -> 章节骨架 -> 详细扩写 -> 最终正文」的工业级创作流程。
- **📁 自动化归档**: **[NEW]** 每次创作都会自动创建专属于该小说的输出文件夹，完美隔离不同作品的大纲、记忆和章节内容。
- **🛠️ 中断续写**: 内置完善的状态保存与恢复机制，支持随时中断并精准续刷。

---

## 🛠️ 快速开始

### 1. 环境准备

```bash
pip install -r requirements.txt
```

### 2. 身份认证

复制 `.env.example` 并配置您的 API 密钥：

```bash
cp .env.example .env
```

在 `.env` 中填写：
- `LLM_PROVIDER`: 驱动提供商 (`openai` 或 `gemini`)
- `API_KEY` 及对应的 `BASE_URL`（支持模型中转）

### 3. 开始创作

运行主程序，您可以根据交互式菜单选择配置文件：

```bash
python main.py
```

或指定特定配置启动：

```bash
python main.py --config configs/xianxia.yaml
```

---

## 📁 目录结构

生成的成果将按以下逻辑组织：

```text
output/
└── [小说标题]/                 # 每一部小说都有独立的舞台
    ├── outline.txt             # 完整故事大纲
    ├── outline_structure.yaml  # 结构化大纲（用于上下文优化）
    ├── memory.yaml             # 小说“魂魄”：记忆、伏笔、人物状态
    ├── chapter_plan.yaml       # 详细的分章计划
    ├── 第1章_标题/              # 章节正文（分小节保存）
    │   ├── 第1节.txt
    │   └── ...
    └── [小说标题].txt           # 合并后的完美全文 (通过工具生成)
```

---

## 🧰 辅助工具

项目内置了强大的命令行工具，助力作品打磨：

### 1. 全文合并工具
将目录下的散落在各处的章节片段拼合为最终的成稿。
```bash
# 自动合并最近创作的小说
python tools/merge_novel.py

# 或手动指定小说目录
python tools/merge_novel.py --dir output/星际余生
```

### 2. 衔接性专项分析
调用严苛的 AI 审校专家，对章节间的逻辑、动作、环境跳跃进行专项扫描。
```bash
# 自动分析最近创作的小说
python tools/analyze_novel.py

# 或手动指定小说目录
python tools/analyze_novel.py --dir output/星际余生
```
分析报告和日志将保存在该小说目录下。

---

## 📝 配置建议

在 `configs/` 目录下，您可以定义小说的灵魂：
- **章节设置**: 目标章数和每章的细分程度。
- **LLM 设置**: 为特定小说指定不同的模型或参数。

---

## 📜 许可

本项目采用 [MIT](LICENSE) 协议。
