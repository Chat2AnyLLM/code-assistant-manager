# 如何使用 Code Assistant Manager 管理 CodeBuddy

> 本文档最后更新：2025-11-30 | CAM 版本：1.0.3

## 引言

在 AI 驱动的开发时代，开发者常常需要使用多个强大的 AI 编码助手，如 Claude、GitHub Copilot 和 CodeBuddy 等。然而，这会导致工作流程分散和低效。Code Assistant Manager（CAM）是一款统一的 Python CLI 工具，用于管理多个 AI 助手的配置、提示、技能和插件，提供一致的接口来管理一切。本文将详细介绍如何使用 CAM 来管理 CodeBuddy，让你的开发体验更加统一和高效。

## CAM 的核心特性

### 1. 统一管理

CAM 支持 **13 种 AI 编码助手**，包括：
- Claude、Codex、Gemini、Qwen、Copilot、**CodeBuddy**、Droid、iFlow、Zed、QoderCLI、Neovate、Crush、Cursor

> **注意**：部分工具（Zed、Qoder、Neovate）默认在菜单中隐藏，因为它们仍在开发中。您可以在 `tools.yaml` 中设置 `enabled: true` 来启用它们。

提供：
- **统一安装和配置**：一键安装和管理多个助手
- **集中化配置**：通过单一的 `providers.json` 文件管理所有 API 密钥和端点设置
- **交互式 TUI**：精美的交互菜单，使用箭头键导航
- **MCP 注册表**：内置 **381 个**预配置的 MCP 服务器，随时安装

### 2. 强大的扩展框架

CAM 提供标准化架构来管理：
- **代理**：独立的助手配置（基于 markdown 的 YAML 前置内容）
- **提示**：可重用的系统提示，在助手间同步
- **技能**：为助手定制的工具和功能（基于目录的 SKILL.md）
- **插件**：支持的助手的市场扩展（GitHub 仓库或本地路径）

### 3. MCP 支持

CAM 提供一流的模型上下文协议支持，允许助手连接外部数据源和工具。CodeBuddy 完全支持 MCP 集成。

## 实战指南：使用 CAM 管理 CodeBuddy

### 第一步：安装 CAM

```bash
# 通过 pip 安装（Python 3.9+）
# 可使用命令行别名：`cam` 或 `code-assistant-manager`
pip install code-assistant-manager

# 或从源码安装
git clone https://github.com/Chat2AnyLLM/code-assistant-manager.git
cd code-assistant-manager
pip install -e .[dev]
```

### 第二步：配置 CodeBuddy

创建 `providers.json` 文件在 `~/.config/code-assistant-manager/` 或项目根目录：

```json
{
  "common": {
    "http_proxy": "http://proxy.example.com:8080/",
    "https_proxy": "http://proxy.example.com:8080/",
    "cache_ttl_seconds": 86400
  },
  "endpoints": {
    "codebuddy-endpoint": {
      "endpoint": "https://your-codebuddy-endpoint.com",
      "api_key_env": "CODEBUDDY_API_KEY",
      "supported_client": "codebuddy",
      "description": "CodeBuddy 配置"
    }
  }
}
```

在 `.env` 文件中设置 API 密钥：
```
CODEBUDDY_API_KEY="your-api-key-here"
```

### 第三步：检查配置

运行诊断命令检查你的设置：
```bash
cam doctor
```

这会检查安装验证、配置文件验证、环境变量检查、工具安装状态和缓存状态。

### 第四步：启动 CodeBuddy

使用交互菜单选择助手和模型：
```bash
cam launch
```

或直接启动 CodeBuddy：
```bash
cam launch codebuddy
```

### 第五步：管理代理、提示、技能、插件与 MCP（详尽指南）

本章详细介绍如何使用 CAM 来管理 CodeBuddy 的所有可扩展项：代理（agent）、提示（prompt）、技能（skill）、插件（plugin）以及 MCP 服务。建议按顺序在本地验证每一步再同步到 CodeBuddy 生产环境。

1) 代理（Agent）管理

CodeBuddy 支持代理管理，代理文件存储在 `~/.codebuddy/agents/` 目录。

- 列表与查询：
```bash
cam agent list                         # 列出所有可用代理
cam agent list -a codebuddy            # 仅列出 CodeBuddy 的代理
cam agent show <agent-key>             # 查看代理详情
```
- 安装与卸载：
```bash
cam agent install <agent-key> -a codebuddy   # 安装代理到 CodeBuddy
cam agent uninstall <agent-key> -a codebuddy # 卸载代理
```
- 从仓库获取：
```bash
cam agent fetch                        # 从配置的仓库获取代理列表
```

2) 提示（Prompt）管理与同步
- 本地管理：
```bash
cam prompt list                     # 列出本地保存的提示（包含 id、名称、描述）
cam prompt show <id>                # 查看提示内容和元数据
cam prompt create --name "fix-bug" --file ./prompts/fix-bug.md  # 从文件创建提示
cam prompt edit <id> --file ./prompts/updated.md               # 编辑提示内容
cam prompt delete <id>              # 删除提示（慎用）
```
- 版本化与导出/导入：
```bash
cam prompt export <id> --out ./backup/prompts/<id>.json
cam prompt import ./backup/prompts/<id>.json
```
- 同步到 CodeBuddy：支持用户级（global）和项目级（project）两种模式，默认安装到用户级（~/.codebuddy/CODEBUDDY.md）除非指定 --level project。注意：若 AGENTS.md 存在，CAM 会优先更新或在其末尾附加同步内容而不是创建 CODEBUDDY.md。
```bash
# 同步到用户级（默认）
cam prompt sync <id> codebuddy                # 将提示同步到 CodeBuddy 用户级（默认合并）
cam prompt sync <id> codebuddy --level user   # 明确同步到用户级 ~/.codebuddy/CODEBUDDY.md

# 同步到当前项目（./CODEBUDDY.md）
cam prompt sync <id> codebuddy --level project                # 将提示同步到项目级 CODEBUDDY.md（合并）
cam prompt sync <id> codebuddy --level project --replace    # 用本地提示替换项目级文件
cam prompt sync --all codebuddy --level project             # 同步所有本地提示到项目级
```
- 行为与优先级：
  - CAM 在同步时会首先检查项目根目录是否存在 AGENTS.md（若存在则优先使用并在其末尾添加同步内容或标记），如果 AGENTS.md 缺失则会创建或更新 CODEBUDDY.md。
  - 用户级（~/.codebuddy/CODEBUDDY.md）遵循同样策略：若 ~/.codebuddy/AGENTS.md 存在，则优先使用 AGENTS.md。
  - 同步命令默认以“安全合并”方式写入（保留已有内容并附加），使用 --replace 可以强制覆盖目标文件。
- 推荐流程：本地测试 -> prompt create/edit -> prompt export (备份) -> prompt sync --level project --replace 到测试实例 -> 验证 -> 同步到生产（用户级或指定生产项目）

3) 技能（Skill）管理

CodeBuddy 支持技能管理，技能文件存储在 `~/.codebuddy/skills/` 目录。

- 查询与安装：
```bash
cam skill list                           # 列出所有可用技能
cam skill list -a codebuddy              # 仅列出 CodeBuddy 的技能
cam skill fetch                          # 从配置的仓库获取技能列表
cam skill install <skill-key> -a codebuddy # 安装技能到 CodeBuddy
```
- 卸载：
```bash
cam skill uninstall <skill-key> -a codebuddy
```

4) 插件（Plugin）管理

**注意**：在 CAM 中，仅 **Claude** 和 **CodeBuddy** 支持插件管理。

- 浏览与安装：
```bash
cam plugin list                          # 列出所有插件
cam plugin list -a codebuddy             # 仅列出 CodeBuddy 的插件
cam plugin install <source> -a codebuddy # 安装插件到 CodeBuddy
```
- 管理：
```bash
cam plugin uninstall <plugin> -a codebuddy
cam plugin enable <plugin> -a codebuddy
cam plugin disable <plugin> -a codebuddy
```
- 插件存储路径：`~/.codebuddy/plugins/`

5) MCP（Model Context Protocol）服务管理
- MCP 概念：MCP（模型上下文协议）允许 AI 助手连接外部数据源和工具，CAM 提供注册、安装、更新与监控等能力。
- 添加/列出/移除 MCP 服务：
```bash
cam mcp list                           # 列出已注册的 MCP 服务器
cam mcp add codebuddy <server-name>    # 从注册表添加 MCP 服务器到 CodeBuddy
cam mcp remove codebuddy <server-name> # 移除 MCP 服务器
```
- 批量安装：
```bash
cam mcp install --all                  # 为所有工具安装 MCP 服务器
cam mcp install --client codebuddy     # 仅为 CodeBuddy 安装
```
- CodeBuddy MCP 配置路径：
  - 用户级：`~/.codebuddy.json`
  - 项目级：`.codebuddy/mcp.json`

6) 配置文件与环境变量（providers.json / .env / 项目覆盖）
- 全局配置路径：默认位于 `~/.config/code-assistant-manager/providers.json`，可以在项目中放置同名文件以实现项目级覆盖。
- providers.json 示例（常用字段）：
```json
{
  "common": {
    "http_proxy": "http://proxy.example.com:8080/",
    "https_proxy": "http://proxy.example.com:8080/",
    "cache_ttl_seconds": 86400
  },
  "endpoints": {
    "codebuddy-endpoint": {
      "endpoint": "https://your-codebuddy-endpoint.com",
      "api_key_env": "CODEBUDDY_API_KEY",
      "supported_client": "codebuddy",
      "description": "CodeBuddy 配置"
    }
  }
}
```
- .env 与敏感信息：将 API Key、MCP Key、Webhook secrets 放在 `.env` 或 CI secrets 中，不要提交到版本库。
```
CODEBUDDY_API_KEY="your-api-key-here"
CODEBUDDY_MCP_KEY="mcp-api-key-here"
```
- 项目覆盖与多配置文件：可通过 CAM 提供的 `--config` 标志加载特定配置文件：
```bash
cam --config ./config/providers.json prompt sync <id> codebuddy
```

7) 同步与部署推荐流程（示例）
- 本地开发与验证：创建 prompt/skill 在本地反复测试。
- 备份：在重要变更前运行 `cam prompt export` / `cam skill export`。
- 测试环境同步：使用 `--replace` 将经过验证的配置同步到测试实例并验证行为。
- 部署到生产：通过 `cam prompt sync <id> codebuddy`、`cam skill install <skill> --to codebuddy` 和 `cam mcp install --server prod-mcp` 按顺序发布。

8) 故障排查与常用命令
```bash
cam doctor                            # 健康检查与常见问题提示
cam version                           # 显示 CAM 版本
cam config list                       # 列出所有配置文件位置
```

9) 最佳实践
- 将关键提示与技能纳入版本控制（例如 prompts/ 和 skills/ 目录），并在 CI 中加入 `cam prompt sync --dry-run` 校验。
- 对生产环境使用专门的配置文件与 secrets 存储，并在变更前做好导出备份。
- 对于大型团队，使用代理与权限策略限流关键技能与插件的使用。

以上内容为使用 CAM 管理 CodeBuddy 配置的详细操作手册；如需针对某一项（例如某个 agent 或 MCP 的具体配置）提供示例配置文件或调试步骤，可继续指定目标进行补充说明。

### 第六步：MCP 服务器管理

添加 MCP 服务器到 CodeBuddy：
```bash
cam mcp add codebuddy <server-name>
cam mcp install --all
```

## CodeBuddy 的特性支持

根据代码库分析，CodeBuddy 在 CAM 中的支持情况如下：

| 特性 | 支持状态 | 说明 |
| :--- | :---: | :--- |
| 代理管理 | ✅ | 存储路径：`~/.codebuddy/agents/` |
| 提示同步 | ✅ | 用户级：`~/.codebuddy/CODEBUDDY.md`；项目级：`./CODEBUDDY.md` |
| 技能安装 | ✅ | 存储路径：`~/.codebuddy/skills/` |
| 插件支持 | ✅ | 仅 Claude 和 CodeBuddy 支持插件管理 |
| MCP 集成 | ✅ | 用户级：`~/.codebuddy.json`；项目级：`.codebuddy/mcp.json` |

### CodeBuddy 配置文件路径总览

| 类型 | 用户级路径 | 项目级路径 |
| :--- | :--- | :--- |
| MCP 配置 | `~/.codebuddy.json` | `.codebuddy/mcp.json` |
| 提示文件 | `~/.codebuddy/CODEBUDDY.md` | `./CODEBUDDY.md` 或 `./AGENTS.md` |
| 技能目录 | `~/.codebuddy/skills/` | - |
| 代理目录 | `~/.codebuddy/agents/` | - |
| 插件目录 | `~/.codebuddy/plugins/` | - |

## 高级用法

### CLI 命令别名

CAM 提供简短的命令别名以提高效率：

| 完整命令 | 别名 | 说明 |
| :--- | :--- | :--- |
| `cam launch` | `cam l` | 启动助手 |
| `cam upgrade` | `cam u` | 升级/安装工具 |
| `cam install` | `cam i` | 安装工具（同 upgrade） |
| `cam doctor` | `cam d` | 诊断检查 |
| `cam mcp` | `cam m` | MCP 管理 |
| `cam prompt` | `cam p` | 提示管理 |
| `cam skill` | `cam s` | 技能管理 |
| `cam plugin` | `cam pl` | 插件管理 |
| `cam agent` | `cam ag` | 代理管理 |
| `cam config` | `cam cf` | 配置管理 |

### 并行升级

并发升级工具：
```bash
cam upgrade codebuddy
```

### 插件市场

浏览和安装插件：
```bash
cam plugin list
cam plugin install <plugin>
```

### 定制化配置

为不同项目自定义 CodeBuddy 配置，通过 `.env` 和 `providers.json` 实现项目级覆盖。

### 查看配置文件位置

```bash
cam config list   # 列出所有配置文件位置及其状态
cam config ls     # 别名
```

### Shell 自动补全

CAM 支持 Bash 和 Zsh 的自动补全：

```bash
cam completion bash > ~/.cam-completion.bash
source ~/.cam-completion.bash

# 或 Zsh
cam completion zsh > ~/.cam-completion.zsh
source ~/.cam-completion.zsh
```

### 工具可见性控制（enabled/disabled）

CAM 允许通过 `tools.yaml` 中的 `enabled` 键控制工具在菜单中的可见性：

```yaml
# 在 tools.yaml 中
codebuddy:
  enabled: true  # 设置为 false 可从菜单隐藏
  install_cmd: npm install -g "@tencent-ai/codebuddy-code@latest"
  cli_command: codebuddy
  description: "Tencent CodeBuddy CLI"
```

- `enabled: true`（默认）- 工具显示在菜单中，可以启动
- `enabled: false` - 工具从菜单中隐藏（适用于开发中的工具）

如果未指定 `enabled` 键，默认为 `true`（向后兼容）。

## 注意事项

- 确保 API 密钥安全存储，不要在版本控制中提交
- 定期运行 `cam doctor` 检查环境健康
- 使用交互菜单探索所有功能
- 对于企业环境，考虑使用代理配置
- CodeBuddy 安装命令：`npm install -g @tencent-ai/codebuddy-code@latest`

## 相关资源

- **GitHub 仓库**：https://github.com/Chat2AnyLLM/code-assistant-manager
- **PyPI 包**：https://pypi.org/project/code-assistant-manager/
- **支持的 MCP 服务器**：381 个预配置服务器，涵盖 GitHub、Slack、PostgreSQL、MongoDB 等

## 结语

Code Assistant Manager 将碎片化的 AI 助手工具转化为统一的强大开发伙伴。通过 CAM，你可以高效管理 CodeBuddy 的配置、扩展和集成，专注于编写优质代码而非管理工具。开始使用 CAM，提升你的 AI 驱动开发体验！

如果在使用的过程中遇到问题，欢迎查看官方文档或提交 issue。祝编码愉快！
