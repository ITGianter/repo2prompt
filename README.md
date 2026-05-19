# Repo2Prompt

将本地项目目录结构和代码内容一键转换为 LLM 友好的纯文本提示词。

## 解决的问题

当你使用网页版大模型（如 ChatGPT、Claude 等）辅助编程时，需要把项目的完整上下文告诉模型。手动复制粘贴文件不仅低效，还容易遗漏。Repo2Prompt 自动完成这件事：

- 生成带缩进的树形目录结构
- 通过 LLM 为每个文件生成一句话摘要
- 将每个可读文本文件的完整内容嵌入到索引区
- 自动过滤二进制文件、依赖目录等无关内容
- 输出格式经过优化，适合直接粘贴到 LLM 对话框中

## 快速开始

### 安装

```bash
pip install -r requirements.txt
```

### Web 界面（推荐）

Repo2Prompt 提供了现代化的 Web 界面，支持可视化配置参数、实时预览命令、一键运行并查看结果。

```bash
# 安装 Web 依赖
pip install -r requirements-web.txt

# 启动 Web 服务
uvicorn repo2prompt.web.server:app --reload --port 8000
```

然后在浏览器中访问 `http://localhost:8000`。

**Web 界面功能：**
- 可视化配置所有 CLI 参数，实时生成命令预览
- 一键运行命令，实时显示执行进度和日志
- 结果输出支持复制和下载
- 内置预设配置（Quick Scan、Full Summary、Outline Only、Debug Mode）
- 支持保存/加载自定义预设，导入/导出 JSON 配置

### 基本用法

```bash
# 默认使用 LLM 摘要模式（需要 API Key）
python -m repo2prompt.cli . --api-key sk-xxx --base-url https://your-api.com --model gpt-4o-mini

# 通过环境变量配置（推荐，避免命令行泄露密钥）
export OPENAI_API_KEY=sk-xxx
export OPENAI_BASE_URL=https://your-api.com
python -m repo2prompt.cli .

# 使用旧版单段输出（无需 API Key）
python -m repo2prompt.cli . --no-summary

# 指定项目路径并输出到文件
python -m repo2prompt.cli /path/to/your/project -o prompt.txt

# 额外排除某些文件
python -m repo2prompt.cli . -e "*.test.js" -e "docs/"

# 生成完成后直接复制到系统剪贴板（推荐）
python -m repo2prompt.cli . -c

# 查看执行进度（INFO 级别）
python -m repo2prompt.cli . --no-summary -v

# 查看详细调试信息（DEBUG 级别）
python -m repo2prompt.cli . --no-summary -vv

# 精确设置日志级别
python -m repo2prompt.cli . --no-summary --log-level INFO
```

### 交互模式

```bash
# 启动 TUI 交互界面，可视化选择要包含的文件（需要安装 textual）
pip install textual
python -m repo2prompt.cli . -i

# 交互选择 + 旧版模式
python -m repo2prompt.cli . -i --no-summary
```

### 行截断与大纲模式

```bash
# 限制每个文件最多显示 50 行（保留头尾，中间省略）
python -m repo2prompt.cli . --no-summary --max-lines 50

# 用代码骨架（类名、函数签名、文档字符串）替代完整文件内容
python -m repo2prompt.cli . --no-summary --outline-only

# 仅对大于 10KB 的文件提取大纲，小文件保持完整内容
python -m repo2prompt.cli . --no-summary --outline-threshold 10240

# 组合使用：大纲 + 截断
python -m repo2prompt.cli . --no-summary --outline-only --max-lines 100
```

### Token 预估

```bash
# 查看生成内容的 Token 数和预估成本（需要安装 tiktoken）
pip install tiktoken
python -m repo2prompt.cli . --no-summary --show-tokens

# 指定模型计算 Token（默认与 --model 相同，或 gpt-4o）
python -m repo2prompt.cli . --show-tokens --token-model gpt-4o-mini
```

## 输出格式

### 摘要模式（默认）

输出分为两大块：**树形目录 + 摘要索引** 和 **完整文件内容索引**。

**第一块：树形目录 + 摘要**

my_project/  
├── [FILE_001] src/main.py — Program entry point that parses CLI arguments and orchestrates the pipeline  
├── src/  
│   ├── [FILE_002] scanner.py — Recursively walks the directory tree and builds Entry objects  
│   └── [FILE_003] formatter.py — Renders tree structure with embedded file content using DFS  
└── [FILE_004] README.md — Project documentation with usage examples and architecture overview  


**第二块：完整文件内容索引**

============================================================
[FILE_001] src/main.py
============================================================

```python
import sys

def main():
    print("Hello World")
```

============================================================
[FILE_002] src/scanner.py
============================================================

```python
from dataclasses import dataclass

@dataclass
class Entry:
    name: str
    ...
```


### 旧版模式（`--no-summary`）

单段输出，树形目录中直接嵌入完整文件内容：

my_project/  
├── src/  
│   ├── main.py  
│   │   <file_content>  
│   │   ```python
│   │   import sys
│   │
│   │   def main():
│   │       print("Hello World")
│   │   ```  
│   │   </file_content>  
│   └── utils/  
│       └── helpers.py  
│           <file_content>  
│           ```python
│           def add(a, b):
│               return a + b
│           ```  
│           </file_content>  
└── README.md  
    <file_content>  
    ```markdown
    # My Project
    ...
    ```  
    </file_content>  


## 命令行参数

### 通用参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `path` | 项目根目录路径 | `.`（当前目录） |
| `-o`, `--output` | 输出文件路径（不指定则打印到终端） | 无 |
| `-c`, `--copy` | 将生成的输出直接复制到系统剪贴板 | 关 |
| `-e`, `--exclude` | 额外排除的 glob 模式（可重复使用） | 无 |
| `--no-summary` | 使用旧版单段输出模式，不需要 API Key | 关 |
| `-i`, `--interactive` | 启动 TUI 交互界面选择文件（需要 `textual`） | 关 |
| `-v`, `--verbose` | 增加输出详细程度（`-v` 显示 INFO 级别，`-vv` 显示 DEBUG 级别） | 关 |
| `--log-level` | 设置日志级别（DEBUG/INFO/WARNING/ERROR/CRITICAL） | WARNING |

### LLM 摘要参数

| 参数 | 环境变量 | 说明 | 默认值 |
|------|----------|------|--------|
| `--api-key` | `OPENAI_API_KEY` | LLM 服务的 API Key | 无（必填） |
| `--base-url` | `OPENAI_BASE_URL` | 自定义 API 地址（兼容 OpenAI 接口的服务） | 无 |
| `--model` | `R2P_MODEL` | 模型名称 | `gpt-4o-mini` |
| `--temperature` | `R2P_TEMPERATURE` | 生成温度 | `0.3` |
| `--max-workers` | `R2P_MAX_WORKERS` | 并发 LLM 调用数 | `5` |

### 输出控制参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--max-lines` | 每个文件在输出中的最大行数（保留头尾，中间省略） | 无（不限制） |
| `--outline-only` | 用代码骨架（类名、函数签名、文档字符串）替代完整文件内容 | 关 |
| `--outline-threshold SIZE` | 仅对超过 SIZE 字节的文件提取大纲 | 无 |

### Token 预估参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--show-tokens` | 生成完成后显示 Token 数和预估成本（需要 `tiktoken`） | 关 |
| `--token-model` | Token 计数使用的模型（影响编码和费率） | 与 `--model` 相同，或 `gpt-4o` |

> **优先级**：命令行参数 > 环境变量 > 默认值

> **兼容性**：任何兼容 OpenAI 接口的服务都可以通过 `--base-url` 指定，例如 Azure OpenAI、本地部署的 vLLM、Ollama 等。

> **可选依赖**：`-i`（交互模式）需要 `textual`，`--show-tokens`（Token 预估）需要 `tiktoken`。未安装时会提示安装命令。详见 [可选依赖](#可选依赖)。

## 可选依赖

以下功能需要额外安装依赖包，核心功能不受影响：

| 功能 | 依赖包 | 安装命令 |
|------|--------|----------|
| Token 预估 (`--show-tokens`) | `tiktoken` | `pip install tiktoken` |
| TUI 交互选择 (`-i`) | `textual` | `pip install textual` |
| Web 界面 | `fastapi`, `uvicorn` | `pip install -r requirements-web.txt` |

一次性安装所有可选依赖：

```bash
pip install -r requirements-optional.txt
pip install -r requirements-web.txt
```

未安装时使用对应功能会提示安装命令。

## 支持的文件类型

### Python 生态
`.py`, `.pyi`, `.ipynb`, `requirements.txt`, `Pipfile`

### Java 生态
`.java`, `pom.xml`, `build.gradle`, `.properties`, `.xml`

### 通用配置与文档
`.md`, `.json`, `.txt`, `.csv`, `.yml`, `.yaml`, `.toml`, `.sh`, `.html`, `.css`, `.js`, `.ts`, `.sql`, `.rst`, `.ini`, `.cfg`, `.conf`, `Dockerfile`, `Makefile`, `.gitignore`

## 默认忽略规则

即使项目中没有 `.gitignore`，以下内容也会被自动过滤：

### 版本控制
`.git/`

### Python
`__pycache__/`, `venv/`, `.env`, `*.pyc`, `.pytest_cache/`, `.eggs/`, `*.egg-info/`

### Java
`target/`, `build/`, `*.class`, `*.jar`, `*.war`, `.gradle/`, `.idea/`

### 通用
`node_modules/`, `*.log`

### 二进制/媒体文件
`*.png`, `*.jpg`, `*.jpeg`, `*.gif`, `*.bmp`, `*.ico`, `*.svg`, `*.mp3`, `*.mp4`, `*.avi`, `*.mov`, `*.mkv`, `*.wav`, `*.flac`, `*.pdf`, `*.zip`, `*.tar`, `*.gz`, `*.rar`, `*.7z`, `*.exe`, `*.dll`, `*.so`, `*.dylib`, `*.bin`, `*.dat`, `*.db`, `*.sqlite`

如果项目根目录下存在 `.gitignore`，其中的规则会被**合并**使用（不会覆盖默认规则）。

## 性能与稳定性机制

- **哈希本地缓存**：默认在扫描项目根目录生成 `.repo2prompt_cache.json`。只要文件内容未被修改，将直接命中本地缓存，实现零 API 消耗与秒级生成（自身缓存文件会被自动忽略不计入 Prompt 中）。
- **API 限流与自动重试**：底层基于 `tenacity` 实现了指数退避（Exponential Backoff）重试机制。当遭遇 `429 Too Many Requests` 等网络异常或并发限制时，将自动平滑重试，保障大规模代码库处理的成功率。
- **Live 动态进度条**：使用 `rich` 库提供并发请求时的实时动态进度条，直观展示进度与状态。

## 安全机制

- **编码回退**：默认以 UTF-8 读取，失败后尝试 Latin-1，仍失败则跳过该文件
- **大小限制**：单文件最大读取 512KB，超出的文件在树中仅显示文件名，内容区域显示 `<warning>File too large to display</warning>`
- **白名单机制**：只读取已知的文本文件类型，其他文件（即使不是二进制）默认不读取内容
- **摘要容错**：单个文件的 LLM 摘要失败时，不影响其他文件的处理，失败文件显示 `[Summary generation failed]`

## 新增功能

### Token 与成本预估 (`--show-tokens`)

在生成完成后，统计输出内容的总 Token 数，并基于所选模型预估 API 输入成本。支持 GPT-4o、GPT-4o-mini、Claude 3.5 Sonnet 等主流模型的费率。未知模型会显示 Token 数但跳过成本估算。

### 代码骨架大纲模式 (`--outline-only` / `--outline-threshold`)

提取代码的结构"骨架"替代完整文件内容，包括类名、函数签名和文档字符串。适用于大型项目中不需要关注底层实现的场景。

- Python 文件使用 `ast` 模块精确解析
- JavaScript/TypeScript/Java 等语言使用正则匹配
- `--outline-threshold SIZE` 可设置仅对超过指定大小的文件提取大纲

### 动态行截断 (`--max-lines`)

限制每个文件在输出中的最大行数。保留 70% 头部和 30% 尾部，中间部分替换为省略提示。截断在渲染时执行，LLM 摘要仍基于完整文件内容生成。

### TUI 交互选择器 (`-i`)

提供终端交互界面，用方向键浏览项目目录树，按空格键选中/取消文件。确认后生成的 Prompt 仅包含选中的文件。

### Web 界面

基于 FastAPI 和现代前端技术构建的可视化配置界面，提供以下功能：

- **可视化参数配置**：通过表单界面配置所有 CLI 参数，实时生成命令预览
- **一键运行**：点击按钮直接执行命令，无需手动复制到终端
- **实时进度显示**：通过 SSE (Server-Sent Events) 实时显示执行日志和 LLM 摘要进度
- **结果管理**：支持复制结果到剪贴板或下载为文件
- **预设系统**：内置 4 个常用预设，支持保存/加载自定义预设，导入/导出 JSON 配置
- **Glass Terminal 设计**：深色主题 + 绿色强调色的终端风格界面，使用 JetBrains Mono 和 Outfit 字体

启动方式：

```bash
pip install -r requirements-web.txt
uvicorn repo2prompt.web.server:app --reload --port 8000
```

## 日志系统

repo2prompt 内置了基于 Python 标准 `logging` 模块的日志系统，覆盖所有处理阶段。

### 日志级别

| 级别 | 触发方式 | 内容 |
|------|----------|------|
| WARNING | 默认 | 仅显示错误和警告 |
| INFO | `-v` | 各阶段进度（扫描、读取、摘要、渲染统计） |
| DEBUG | `-vv` 或 `--log-level DEBUG` | 每个文件的操作细节（编码回退、大小检查等） |

### 输出格式

- **WARNING**：纯消息文本（与旧版行为一致）
- **INFO**：`模块名 [级别] 消息`，例如 `repo2prompt.scanner [INFO] Tree built: 8 directories, 23 files`
- **DEBUG**：`时间戳 模块名 [级别] 消息`，包含完整时间戳用于性能分析

日志输出到 stderr，不影响 stdout 的 prompt 内容输出。

## 项目结构


repo2prompt/
├── repo2prompt/
│   ├── __init__.py       # 包初始化
│   ├── _optional.py      # 可选依赖检查工具
│   ├── cli.py            # CLI 入口 (argparse)
│   ├── scanner.py        # 目录遍历，生成 Entry 树
│   ├── file_reader.py    # 文件读取（编码、大小、语言检测、行截断）
│   ├── formatter.py      # 树形渲染 + 内容嵌入（核心）
│   ├── ignore.py         # 过滤规则（pathspec + 默认规则）
│   ├── summarizer.py     # LLM 摘要生成与缓存重试 (openai, tenacity)
│   ├── extractor.py      # 代码骨架提取（Python AST + 正则）
│   ├── token_utils.py    # Token 计数与成本预估 (tiktoken)
│   ├── tui.py            # TUI 交互选择器 (textual)
│   └── web/              # Web 界面后端
│       ├── __init__.py
│       ├── server.py     # FastAPI 服务 + SSE 端点
│       └── runner.py     # Web 管道执行器
├── frontend/             # Web 界面前端
│   ├── index.html        # 页面结构
│   ├── styles.css        # 样式设计（Glass Terminal 风格）
│   └── app.js            # 状态管理、命令生成、运行逻辑
├── tests/
│   ├── test_formatter.py
│   ├── test_summarizer.py
│   ├── test_extractor.py
│   ├── test_token_utils.py
│   ├── test_truncation.py
│   ├── test_tui.py
│   └── test_optional.py
├── .gitignore
├── requirements.txt          # 核心依赖：pathspec, python-dotenv, openai, pyperclip, rich, tenacity
├── requirements-optional.txt # 可选依赖：tiktoken, textual
├── requirements-web.txt      # Web 依赖：fastapi, uvicorn
└── README.md


## 核心算法

### 数据流


build_spec(root, extra_exclude)     -- ignore.py
        |
        v
build_tree(root, spec)              -- scanner.py  -->  Entry 树（纯结构）
        |
        v
[launch_selector(tree, root)]       -- tui.py      -->  过滤后的 Entry 树（-i 模式）
        |
        v
build_file_index(tree, root, ...)   -- summarizer.py  -->  FileSummary 列表（含摘要）
        |
        v
render(tree, file_summaries, ...)   -- formatter.py  -->  输出字符串
        |                                  |
        |                          [truncate_content]   --max-lines 截断
        |                          [extract_outline]    --outline-only 大纲提取
        v
[count_tokens(output)]             -- token_utils.py   -->  Token 统计（--show-tokens）


### 树形渲染（formatter.py）

采用**深度优先遍历（DFS）**构建输出字符串：

1. 遍历每个节点时，根据是否为同级最后一个子节点，选择 `├── ` 或 `└── ` 作为连接符
2. 计算当前层级的延续前缀：最后一个子节点用 `    `（空格），其余用 `│   `（管道线）
3. 将延续前缀传递给子节点，子节点在此基础上继续拼接
4. 文件节点显示 `[FILE_NNN] 文件名 — 摘要`，目录节点保持原样
5. 第二段以 `===` 分隔符划分每个文件的内容块

### 摘要生成（summarizer.py）

1. DFS 遍历 Entry 树，收集所有文件节点并按顺序编号
2. 读取每个文件内容，进行 SHA-256 哈希比对。若命中本地缓存，则直接跳过 LLM 调用
3. 缓存未命中的文件，使用 `ThreadPoolExecutor` 并发调用原生 `openai` SDK，默认 5 个并发
4. 通过 `tenacity` 进行自动指数退避重试，多次失败后才返回 `[Summary generation failed]`，不影响其他文件
5. 进度信息通过 `rich` 渲染为动态的控制台进度条（CLI 模式），或通过 `progress_callback` 回调报告进度（Web 模式）
6. 任务结束后，将新生成的摘要与文件内容哈希持久化保存至本地 `.repo2prompt_cache.json` 中

`build_file_index()` 函数支持可选的 `progress_callback` 参数，用于 Web 界面的实时进度报告。当提供此回调时，Rich 进度条将被禁用。

## 运行测试

```bash
pip install pytest
python -m pytest tests/ -v
```

## 作为 Python 包使用

```python
from repo2prompt.ignore import build_spec
from repo2prompt.scanner import build_tree
from repo2prompt.summarizer import Summarizer, build_file_index
from repo2prompt.formatter import render, render_legacy

root = "/path/to/project"
spec = build_spec(root, extra_exclude=["*.test.py"])
tree = build_tree(root, spec)

# 摘要模式
summarizer = Summarizer(model="gpt-4o-mini", api_key="sk-xxx", base_url="https://your-api.com")
file_summaries = build_file_index(tree, root, summarizer)
output = render(tree, file_summaries)
print(output)

# 旧版模式
output = render_legacy(tree, root)
print(output)

# 带行截断
output = render_legacy(tree, root, max_lines=50)

# 带大纲提取
output = render_legacy(tree, root, outline_only=True)

# Token 预估
from repo2prompt.token_utils import count_tokens, format_token_report
token_count = count_tokens(output, "gpt-4o")
print(format_token_report(token_count, "gpt-4o", len(output)))

# TUI 交互选择
from repo2prompt.tui import launch_selector
filtered_tree = launch_selector(tree, root)
if filtered_tree:
    output = render_legacy(filtered_tree, root)
```

## 许可证

MIT
