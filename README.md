# AI 小说生成器 (AI Writer)

一个基于 LLM 驱动的自动化小说创作工具，支持从大纲生成到分章细化的全流程迭代创作。

## 核心特性

- **多驱动支持**: 内置 Google Gemini 和 OpenAI 双驱动，支持灵活切换。
- **记忆系统**: 自动提取并维护故事梗概、伏笔和章节结尾状态，确保剧情连贯性。
- **迭代模式**: 分阶段生成（核心构思 -> 章节骨架 -> 详细扩展 -> 正文创作），有效避免长文本生成中的幻觉和截断问题。
- **结构化管理**: 自动保存结构化大纲和记忆文件，支持中断后继续生成。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
# 如果需要使用 OpenAI 驱动
pip install openai
```

### 2. 配置 API Key

您可以直接设置环境变量，或者在项目根目录下创建一个 `.env` 文件（参考 `.env.example`）：

```bash
cp .env.example .env
# 然后编辑 .env 文件，填写您的密钥和配置
```

`.env` 完整配置示例：
```env
# OpenAI 配置
OPENAI_API_KEY=your_openai_api_key
OPENAI_BASE_URL=https://api.your-proxy.com/v1  # 可选：自定义中转地址
OPENAI_MODEL=gpt-4o                            # 可选：默认使用模型

# Gemini 配置
GEMINI_API_KEY=your_gemini_api_key
GEMINI_BASE_URL=                               # 可选：自定义地址
GEMINI_MODEL=gemini-3-flash-preview            # 可选：默认使用模型
```

> **注意**：如果 `.env` 中的 `BASE_URL` 留空，程序将自动回退到官方默认 API 地址。

### 3. 配置优先级
1. **配置文件 (`.yaml`)**: 如果在故事配置文件中明确指定了 `llm.model` 或 `llm.base_url`，则优先级最高。
2. **环境变量 (`.env`)**: 如果配置文件中未指定，则读取 `.env` 中的默认设置。
3. **程序默认值**: 如果以上均未指定，则使用内置默认值（如 Gemini 驱动和对应的默认模型）。

### 4. 运行生成

运行主程序并按提示选择配置文件：

```bash
python main.py
```

或者直接指定配置文件：

```bash
python main.py --config configs/scifi.yaml
```

## 配置文件说明

一个典型的配置文件包括：

```yaml
标题: "星际余生"
背景: "2200年，地球资源枯竭，人类寄居在空间站..."
章节设置:
  目标章数: 20
  每章小节数: 3
llm:
  provider: openai
  model: gpt-4o
```

## 项目结构

- `src/llm.py`: LLM 驱动抽象层及实现。
- `src/generator.py`: 核心生成逻辑及记忆系统。
- `configs/`: 预设的故事模板和配置。
- `output/`: 生成的故事正文、大纲及记忆文件。

## 许可

MIT
