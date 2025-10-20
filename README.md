# Create Clash Yaml

一个强大、美观、易用的 Clash 配置文件生成工具，采用现代化UI设计，支持多种订阅格式，可自动解析和合并多个节点来源。

[![Language](https://img.shields.io/badge/Language-Python-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-0.2.1-orange.svg)](https://github.com/XGCoder/Config_Merge_Shunt)

## 📑 目录

- [Create Clash Yaml](#create-clash-yaml)
  - [📑 目录](#-目录)
  - [✨ 主要特性](#-主要特性)
  - [🔧 安装方法](#-安装方法)
  - [📖 使用指南](#-使用指南)
    - [Web界面 (GUI)](#web界面-gui)
    - [命令行工具 (CLI)](#命令行工具-cli)
  - [🔄 支持的格式](#-支持的格式)
  - [⚙️ Clash Verge 兼容说明](#️-clash-verge-兼容说明)
  - [❓ 常见问题解答](#-常见问题解答)
  - [📁 项目结构](#-项目结构)
  - [🔄 版本历史](#-版本历史)
  - [👥 贡献指南](#-贡献指南)
  - [📄 许可证](#-许可证)

## ✨ 主要特性

- 📊 **全新现代化UI**：采用单页三栏式布局，引导式操作流程，支持明亮/暗黑模式自动适配。
- 🔄 **多格式源输入**：支持从多个订阅源、手动输入链接和本地文件加载节点并合并。
- 🔌 **多协议支持**：兼容 VLESS、VMess、Shadowsocks、ShadowsocksR、Trojan、Hysteria、Hysteria2 等主流协议。
- 룰 **高级规则集成**：可一键启用内置的高级规则集，提供强大的广告拦截和分流功能。
- 🔧 **端口映射**：使用标准 `listeners` 配置为特定节点创建独立的 HTTP/SOCKS/Mixed 代理端口。
- 📂 **配置预设**：方便地保存和加载常用配置组合，提高效率。
- 🔍 **可视化生成**：生成过程中的每一步都有日志输出，过程清晰透明。

## 🔧 安装方法

### 系统要求

- Python 3.8 或更高版本（本地安装）
- Docker 和 Docker Compose（Docker 部署）
- 适用于 Windows、macOS 和 Linux

### 方式一：Docker 部署（推荐）

使用 Docker Compose 可以快速部署，无需配置 Python 环境。

1. 克隆仓库

```bash
git clone https://github.com/XGCoder/create_clash_yaml.git
cd create_clash_yaml
```

2. 使用 Docker Compose 启动

```bash
docker-compose up -d
```

3. 访问应用

打开浏览器访问 `http://localhost:8501`

4. 停止服务

```bash
docker-compose down
```

### 方式二：本地安装

1. 克隆仓库

```bash
git clone https://github.com/XGCoder/create_clash_yaml.git
cd create_clash_yaml
```

2. 安装依赖

```bash
pip install -r requirements.txt
```

项目依赖（仅3个核心库）：
- `streamlit>=1.24.0` - Web界面框架
- `pyyaml>=6.0` - YAML文件处理
- `requests>=2.28.0` - HTTP请求库

3. 启动程序

```bash
streamlit run gui.py
```

## 📖 使用指南

本工具提供两种使用方式:
- **Web界面 (GUI)**: 可视化操作,适合日常使用
- **命令行工具 (CLI)**: 自动化脚本,适合批量处理

---

### Web界面 (GUI)

#### 界面概述

全新的 `Create Clash Yaml` 采用单页三栏式布局，为您提供从左到右的引导式工作流。

- **左侧栏 (📥 输入源)**：用于提供所有节点来源，包括订阅链接、手动输入的节点和本地文件。
- **中间栏 (⚙️ 节点配置)**：核心操作区，在加载节点后，您可以在此查看所有节点信息，并进行端口映射等配置。
- **右侧栏 (🚀 全局与生成)**：全局控制面板，您可以在此管理配置预设、调整端口和模板等全局设置，并最终生成配置文件。

#### 工作流程

1.  **输入源**：在页面 **左侧** 的对应输入框中，填入您的订阅链接、直接节点链接，或上传包含节点的文件。

2.  **加载节点**：点击左侧底部的 **"加载节点"** 按钮。程序会自动获取并解析所有来源的节点。

3.  **配置节点**：节点加载成功后，会显示在页面 **中间** 的区域。顶部会显示节点总数等统计信息。
    - 如果您在右侧启用了"端口映射"，则可以在此为指定的节点勾选"启用"并分配端口。

4.  **全局设置**：在页面 **右侧** 的控制面板中，您可以：
    - 保存或加载常用的**配置预设**。
    - 启用或关闭**端口映射**功能，并设置起始端口和监听器类型。
    - 调整最终配置文件的 **HTTP/混合端口** 和 **输出文件名**。
    - 选择是否 **使用高级规则集** 或上传您自己的 **自定义模板**。

5.  **生成配置**：完成所有配置后，点击右侧底部的 **"生成配置文件"** 按钮。
    - 生成过程会实时显示在下方的日志区域中。
    - 生成成功后，旁边会出现下载按钮，点击即可下载最终的 `config.yaml` 文件。

---

### 命令行工具 (CLI)

CLI工具支持**交互式**和**命令行**两种模式,适合不同场景使用。

#### 快速开始

**1. 交互式模式** (推荐新手)

```bash
python cli.py
```

零参数启动后,程序会自动引导您完成4个步骤:
1. 📄 选择模板文件 (自动扫描当前目录)
2. 🔗 添加订阅链接 (支持逐个输入或从文件读取)
3. 🔌 端口映射配置 (可选)
4. 💾 配置输出 (自动生成带时间戳的文件名)

**2. 命令行模式** (适合自动化)

```bash
# 基础用法
python cli.py -t template.yaml -s https://sub.com --non-interactive

# 从文件读取订阅
python cli.py -t template.yaml --subs-file subscriptions.txt

# 添加多个订阅
python cli.py -t template.yaml -s https://sub1.com -s https://sub2.com
```

#### CLI参数说明

| 参数 | 简写 | 说明 |
|------|------|------|
| `--template` | `-t` | YAML模板文件路径 |
| `--subscription` | `-s` | 订阅链接 (可多次使用) |
| `--subs-file` | - | 从文件读取订阅链接 |
| `--output` | `-o` | 输出文件路径 (默认自动生成) |
| `--interactive` | `-i` | 强制进入交互式模式 |
| `--non-interactive` | - | 强制非交互模式 |
| `--debug` | `-d` | 启用调试日志 |

#### 使用示例

**交互式模式示例**:
```bash
$ python cli.py

╔════════════════════════════════════════════════╗
║                                                ║
║         Clash 配置文件生成器 v0.2.1              ║
║                                                ║
╚════════════════════════════════════════════════╝

==================================================
📄 [步骤 1/4] 选择模板文件
==================================================

可用模板:
  1. qichiyu_config.yaml (推荐) (12.8 KB)
  2. 手动输入路径 (yaml文件)
  3. 跳过(不使用模板)

请选择 [1-3]: 1
✅ 已选择: qichiyu_config.yaml
...
```

**命令行模式示例**:
```bash
# 完整参数
python cli.py -t template.yaml -s https://sub.com -o output.yaml --non-interactive

# 自动生成文件名 (config_20251020_100235.yaml)
python cli.py -t template.yaml -s https://sub.com --non-interactive

```

#### CLI特性

✨ **智能双模式**: 自动检测参数完整性,选择交互式或命令行模式
✨ **模板自动发现**: 自动扫描并过滤当前目录的YAML模板
✨ **端口映射**: 交互式模式下可为所有节点自动分配连续端口
✨ **时间戳文件名**: 自动生成格式为 `config_20251020_095830.yaml` 的文件名
✨ **向后兼容**: 所有旧版命令仍然有效

## 🔄 支持的格式

### 订阅格式

- Clash 配置文件（YAML格式）
- V2Ray 订阅（Base64编码）
- 普通文本节点列表
- JSON格式的节点列表

### 节点协议

- VLESS
- Vmess
- Shadowsocks
- ShadowsocksR
- Trojan
- Hysteria
- Hysteria2

## ⚙️ Clash Verge 兼容说明

本工具专门为 Clash Verge 设计，生成的配置文件完全兼容 Clash Verge：

- 支持生成标准的 `proxies`, `proxy-groups` 和 `rules` 配置。
- 使用标准的 `listeners` 配置替代不被支持的旧版 `mixed-proxy`。
- 正确处理 HTTP、SOCKS 和 Mixed 协议的端口映射。
- 支持解析包含中文和 Emoji 的节点名称。

## ❓ 常见问题解答

**Q: 配置文件导入 Clash Verge 报错？**  
A: 确保使用最新版本的工具，检查订阅源是否可访问，确认使用的节点格式是 Clash Verge 支持的类型。

**Q: 为什么“使用高级规则集”需要 `qichiyu_config.yaml` 文件？**  
A: 这是根据您的要求定制的功能。程序会加载您放置在项目根目录下的这个文件，并提取其中的规则作为高级规则使用。如果文件不存在，程序会自动回退到默认规则。

**Q: 部分节点无法正常使用？**  
A: 检查节点配置是否完整，确认使用的协议是否受支持（如VLESS, VMess等），验证节点服务器是否在线。

**Q: 端口映射不起作用？**  
A: 确保在右侧的设置面板中已“启用端口映射”，并在中间的节点列表中勾选了您想映射的节点。

## 📁 项目结构

```
create_clash_yaml/
├── clash_config_generator/        # 核心代码包
│   ├── __init__.py                # 包初始化
│   ├── config_generator.py        # 配置生成核心逻辑（YAML序列化优化）
│   ├── subscription.py            # 订阅处理和解析（支持Unicode清理）
│   ├── node_parser.py             # 各协议节点解析器（支持Reality等新协议）
│   └── utils.py                   # 工具函数（Base64解码、YAML处理）
├── gui.py                         # GUI界面（Streamlit）
├── cli.py                         # 命令行接口
├── README.md                      # 项目说明
└── requirements.txt               # 依赖列表
```

## 📚 依赖库说明

### 外部依赖（3个核心库）

| 库名 | 版本 | 用途 |
|------|------|------|
| **streamlit** | ≥1.24.0 | 构建交互式Web GUI界面 |
| **pyyaml** | ≥6.0 | 解析和生成YAML配置文件 |
| **requests** | ≥2.28.0 | 获取订阅链接内容，支持超时和重试 |

### Python标准库

项目还使用了以下Python内置标准库（无需额外安装）：
- `base64` - Base64编解码
- `json` - JSON数据处理
- `re` - 正则表达式匹配
- `logging` - 日志记录
- `datetime`/`time`/`random` - 时间和随机数
- `urllib.parse` - URL解析和编码
- `os`/`glob` - 文件系统操作
- `argparse` - 命令行参数解析

## 🔄 版本历史

- **0.2.1** (当前版本)
  - ✨ **CLI工具优化升级**:
    - 新增智能双模式支持 (交互式/命令行/混合)
    - 新增交互式引导流程 (4步完成配置)
    - 新增模板自动发现和过滤功能
    - 新增从文件读取订阅 (`--subs-file`)
    - 新增端口映射交互式配置
    - 新增自动时间戳文件名生成
    - 优化用户体验 (彩色图标、步骤引导、友好提示)
    - 完全向后兼容旧版命令
  - ✅ **GUI端口映射BUG修复**:
    - 修复端口验证不生效问题
    - 新增「确认端口映射」复选框
    - 优化端口冲突提示逻辑
  - ✅ **UI优化**:
    - 移除界面中的序号标记,简化视觉设计
    - 配置文件名增加时分信息
    - 强制使用东八区(北京时间)生成文件名
  - 🎯 **用户体验提升**:
    - 端口修改时自动取消确认状态
    - 端口冲突时显示详细节点信息
    - 未确认端口映射时阻止配置生成
    - 支持 Ctrl+C 优雅退出CLI
- **0.2.0** - 三栏式UI重构版
  - 全新的三栏式现代化UI,支持明暗主题
  - 新增 VLESS 协议支持(含Reality协议)
  - 新增高级规则集一键启用功能
  - 优化了状态管理和交互逻辑
- **0.1.0** - 初始版本发布

## 👥 贡献指南

欢迎贡献代码或提交问题报告！如果您想参与项目开发，请：

1. Fork 本仓库
2. 创建您的特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交您的更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 打开一个 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 详细信息请查看 [LICENSE](LICENSE) 文件