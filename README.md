# Clash 配置生成器

一个强大易用的 Clash 配置文件生成工具，支持多种订阅格式，可自动解析和合并多个节点来源，提供直观的GUI界面。

[![Language](https://img.shields.io/badge/Language-Python-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/Version-0.1.0-orange.svg)](https://github.com/XGCoder/Config_Merge_Shunt)

## 📑 目录

- [Clash 配置生成器](#clash-配置生成器)
  - [📑 目录](#-目录)
  - [✨ 主要特性](#-主要特性)
  - [🔧 安装方法](#-安装方法)
    - [系统要求](#系统要求)
    - [安装步骤](#安装步骤)
  - [📖 使用指南](#-使用指南)
    - [界面概述](#界面概述)
    - [订阅管理](#订阅管理)
    - [节点管理](#节点管理)
    - [配置生成](#配置生成)
    - [端口映射功能](#端口映射功能)
    - [配置预设功能](#配置预设功能)
  - [🔄 支持的格式](#-支持的格式)
    - [订阅格式](#订阅格式)
    - [节点协议](#节点协议)
  - [⚙️ Clash Verge 兼容说明](#️-clash-verge-兼容说明)
  - [❓ 常见问题解答](#-常见问题解答)
  - [📁 项目结构](#-项目结构)
  - [🔄 版本历史](#-版本历史)
  - [👥 贡献指南](#-贡献指南)
  - [📄 许可证](#-许可证)
  - [🙏 致谢](#-致谢)

## ✨ 主要特性

- 🔄 **多订阅合并**：支持从多个订阅源、直连节点和文件中加载节点并合并
- 🔌 **多协议支持**：兼容 Vmess、Shadowsocks、ShadowsocksR、Trojan、Hysteria、Hysteria2 等协议
- 🌐 **Clash配置文件生成**：生成符合 Clash Verge 标准的配置文件
- 🔧 **端口映射**：使用标准 listeners 配置为特定节点创建 HTTP/SOCKS 监听器
- 📊 **可视化界面**：直观的 Streamlit 界面，方便操作和配置
- 📂 **配置预设**：保存和加载常用配置，提高使用效率
- 🔍 **节点分组**：按订阅源分组显示节点，支持批量操作
- 🌈 **中文名称支持**：正确解析包含中文和Emoji的节点名称

## 🔧 安装方法

### 系统要求

- Python 3.7 或更高版本
- 适用于 Windows、macOS 和 Linux

### 安装步骤

1. 克隆仓库

```bash
git clone https://github.com/XGCoder/Config_Merge_Shunt.git
cd Config_Merge_Shunt
```

2. 安装依赖

```bash
pip install -r requirements.txt
```

3. 启动程序

```bash
streamlit run gui.py
```

## 📖 使用指南

### 界面概述

启动程序后，您将看到一个直观的Web界面，分为以下几个部分：

- **侧边栏**：包含全局配置选项和配置预设管理
- **主界面**：包含多个选项卡，用于管理不同类型的节点来源和生成配置

### 订阅管理

在"订阅链接"选项卡中：

1. 输入一个或多个订阅URL，每行一个
2. 点击"保存订阅链接"按钮保存输入的链接
3. 在配置生成选项卡中点击"加载节点"获取这些订阅的节点

### 节点管理

在"直连节点"选项卡中：

1. 输入单个节点链接或上传包含节点的文件
2. 支持 vmess://、ss://、trojan:// 等多种格式的链接
3. 点击"保存直连节点"按钮保存输入的节点

### 配置生成

在"配置生成"选项卡中：

1. 点击"加载节点"按钮加载所有订阅和直连节点
2. 节点将按来源分组显示，可进行选择操作
3. 设置端口映射（可选）
4. 点击"生成配置"按钮生成最终配置文件
5. 点击"下载配置"按钮下载生成的配置文件

### 端口映射功能

通过端口映射功能，可以为特定节点分配专用端口：

1. 启用侧边栏中的"启用端口映射"选项
2. 点击"加载节点"加载所有节点
3. 在端口映射配置表中选择要映射的节点
4. 可选择调整端口号（默认从设定的起始端口开始递增）
5. 点击"保存端口映射配置"保存设置

每个映射节点将创建一个mixed类型监听器，同时支持HTTP和SOCKS5协议访问。程序会自动为每个映射端口生成相应的分流规则（DST-PORT规则），确保通过该端口的流量直接使用对应的节点，无需通过规则选择器选择。

使用方法示例：
- 如果节点"HK-01"映射到端口42001，则可以通过设置代理为"127.0.0.1:42001"直接使用该节点
- 该端口同时支持HTTP和SOCKS5代理协议

### 配置预设功能

配置预设功能可以保存常用的配置组合，方便下次快速加载：

1. 在侧边栏的"配置管理"部分设置所有参数
2. 输入预设名称（或留空使用默认日期格式）
3. 点击"保存当前配置为预设"
4. 下次使用时，只需从下拉列表选择预设并点击"加载选中的预设"

## 🔄 支持的格式

### 订阅格式

- Clash 配置文件（YAML格式）
- V2Ray 订阅（Base64编码）
- 普通文本节点列表
- JSON格式的节点列表

### 节点协议

- Vmess
- Shadowsocks
- ShadowsocksR
- Trojan
- Hysteria
- Hysteria2

## ⚙️ Clash Verge 兼容说明

本工具专门为 Clash Verge 设计，生成的配置文件完全兼容 Clash Verge：

- 支持生成标准的 proxies, proxy-groups 和 rules 配置
- 使用标准的 listeners 配置替代不被支持的 mixed 类型代理
- 正确处理 HTTP 和 SOCKS 协议的端口映射
- 支持解析包含中文和 Emoji 的节点名称

## ❓ 常见问题解答

**Q: 配置文件导入 Clash Verge 报错？**  
A: 确保使用最新版本的 Clash Config Generator，检查订阅源是否可访问，确认使用的节点格式是 Clash Verge 支持的类型。

**Q: 部分节点无法正常使用？**  
A: 检查节点配置是否完整，确认使用的协议是否受支持，验证节点服务器是否在线。

**Q: 端口映射不起作用？**  
A: 确保为节点启用了端口映射功能，检查映射的端口是否被其他程序占用，验证配置文件中是否正确生成了 listeners 部分。

**Q: 如何添加自定义规则？**  
A: 目前版本使用内置的规则模板，未来版本将支持自定义规则导入功能。

## 📁 项目结构

```
Config_Merge_Shunt/
├── clash_config_generator/        # 核心代码包
│   ├── __init__.py                # 包初始化
│   ├── config_generator.py        # 配置生成核心逻辑
│   ├── subscription.py            # 订阅处理和解析
│   ├── node_parser.py             # 各协议节点解析器
│   ├── templates.py               # 规则和代理组模板
│   ├── utils.py                   # 工具函数
│   └── default_rules.yaml         # 默认规则配置
├── gui.py                         # GUI界面（Streamlit）
├── cli.py                         # 命令行接口
├── local_configs/                 # 本地配置预设存储目录
├── README.md                      # 项目说明
├── LICENSE                        # 许可证文件
├── .gitignore                     # Git忽略配置
└── requirements.txt               # 依赖列表
```

## 🔄 版本历史

- **0.1.0** - 初始版本发布
  - 支持多种订阅源和节点格式
  - 提供基本的配置生成功能
  - 实现端口映射功能
  - 添加配置预设管理

## 👥 贡献指南

欢迎贡献代码或提交问题报告！如果您想参与项目开发，请：

1. Fork 本仓库
2. 创建您的特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交您的更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 打开一个 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 详细信息请查看 [LICENSE](LICENSE) 文件

## 🙏 致谢

- [Streamlit](https://streamlit.io/) - 提供强大的Web界面
- [Clash](https://github.com/Dreamacro/clash) - 优秀的代理工具
- [Clash Verge](https://github.com/zzzgydi/clash-verge) - 优秀的Clash客户端
