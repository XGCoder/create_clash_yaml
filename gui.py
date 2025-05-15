#!/usr/bin/env python
# -*- coding: utf-8 -*-

import streamlit as st
import logging
import os
import io
import json
import glob
import base64
import re
from datetime import datetime
from tempfile import NamedTemporaryFile
from pathlib import Path
from io import StringIO

# 从包导入所需的组件
from clash_config_generator.config_generator import ClashConfigGenerator
from clash_config_generator.subscription import SubscriptionManager
from clash_config_generator.node_parser import NodeParser, parse_proxy
from clash_config_generator.utils import load_local_file

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("clash_config_generator_gui")

# 设置页面配置
st.set_page_config(
    page_title="Clash Config Generator",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 定义配置预设目录和文件格式
CONFIG_DIR = "local_configs"
if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)

def get_download_link(file_path, file_name):
    """
    生成一个文件下载链接
    
    Args:
        file_path (str): 文件路径
        file_name (str): 下载时使用的文件名
        
    Returns:
        str: HTML格式的下载链接
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        data = f.read()
    
    b64 = base64.b64encode(data.encode()).decode()
    href = f'<a href="data:file/yaml;base64,{b64}" download="{file_name}">点击下载配置文件</a>'
    return href

def save_config_preset(name, data):
    """
    保存配置预设到本地文件
    
    Args:
        name (str): 预设名称，如果为None则使用日期格式
        data (dict): 预设数据
        
    Returns:
        str: 保存的文件名
    """
    if not name:
        name = f"local_config_{datetime.now().strftime('%y-%m-%d')}"
    
    # 确保文件名不含非法字符
    name = "".join(c for c in name if c.isalnum() or c in "-_.")
    
    file_path = os.path.join(CONFIG_DIR, f"{name}.json")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"配置预设已保存: {file_path}")
    return name

def load_config_preset(name):
    """
    加载本地配置预设
    
    Args:
        name (str): 预设名称
        
    Returns:
        dict: 预设数据，如果加载失败则返回None
    """
    file_path = os.path.join(CONFIG_DIR, f"{name}.json")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"配置预设已加载: {file_path}")
        return data
    except Exception as e:
        logger.error(f"加载配置预设失败: {str(e)}")
        return None

def delete_config_preset(name):
    """
    删除本地配置预设
    
    Args:
        name (str): 预设名称
        
    Returns:
        bool: 是否成功删除
    """
    file_path = os.path.join(CONFIG_DIR, f"{name}.json")
    try:
        os.remove(file_path)
        logger.info(f"配置预设已删除: {file_path}")
        return True
    except Exception as e:
        logger.error(f"删除配置预设失败: {str(e)}")
        return False

def get_config_presets():
    """
    获取所有本地配置预设
    
    Returns:
        list: 预设名称列表
    """
    presets = []
    for file_path in glob.glob(os.path.join(CONFIG_DIR, "*.json")):
        name = os.path.basename(file_path).replace(".json", "")
        presets.append(name)
    return sorted(presets, reverse=True)  # 最新的排在前面

def main():
    """Streamlit应用主函数"""
    
    st.title("Clash 配置生成器")
    st.markdown("使用此工具可以合并多个订阅源和直连节点，生成 Clash Verge 配置文件。")
    
    # 添加全局CSS样式
    st.markdown("""
    <style>
    .node-cell {
        display: flex;
        align-items: center;
        min-height: 40px;
    }
    .stExpander {
        border: 1px solid #f0f2f6;
        border-radius: 4px;
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 检查会话状态中是否存在必要的变量
    if 'subscriptions' not in st.session_state:
        st.session_state.subscriptions = []
    
    if 'all_proxies' not in st.session_state:
        st.session_state.all_proxies = []
    
    if 'nodes_loaded' not in st.session_state:
        st.session_state.nodes_loaded = False
    
    if 'enable_port_mapping' not in st.session_state:
        st.session_state.enable_port_mapping = False
    
    if 'node_mappings' not in st.session_state:
        st.session_state.node_mappings = {}
    
    if 'start_mapping_port' not in st.session_state:
        st.session_state.start_mapping_port = 42000
    
    if 'proxies_by_source' not in st.session_state:
        st.session_state.proxies_by_source = {}
    
    if 'template_path' not in st.session_state:
        st.session_state.template_path = None
    
    # 用于存储来源节点全选状态的会话变量
    if 'source_all_selected' not in st.session_state:
        st.session_state.source_all_selected = {}
    
    # 用于折叠日志的会话变量
    if 'mapping_log_expanded' not in st.session_state:
        st.session_state.mapping_log_expanded = False
    
    if 'config_log_expanded' not in st.session_state:
        st.session_state.config_log_expanded = False

    # 用于存储表单数据的会话状态
    if 'subscription_urls' not in st.session_state:
        st.session_state.subscription_urls = ""
    if 'direct_nodes' not in st.session_state:
        st.session_state.direct_nodes = ""
    if 'port' not in st.session_state:
        st.session_state.port = 7890
    if 'mixed_port' not in st.session_state:
        st.session_state.mixed_port = 7891
    if 'default_port' not in st.session_state:
        st.session_state.default_port = 7897
    if 'default_node' not in st.session_state:
        st.session_state.default_node = ""
    if 'output_file' not in st.session_state:
        st.session_state.output_file = "config.yaml"
    
    # 侧边栏设置
    with st.sidebar:
        st.header("配置选项")
        
        # 配置管理部分
        st.subheader("配置管理")
        
        # 获取可用的配置预设
        presets = get_config_presets()
        
        # 选择预设
        selected_preset = st.selectbox(
            "加载预设配置",
            [""] + presets,
            index=0,
            help="选择之前保存的配置预设"
        )
        
        # 加载预设按钮
        if selected_preset and st.button("加载选中的预设"):
            preset_data = load_config_preset(selected_preset)
            if preset_data:
                # 更新会话状态
                for key, value in preset_data.items():
                    if key in st.session_state:
                        st.session_state[key] = value
                st.success(f"已加载预设: {selected_preset}")
                st.experimental_rerun()
            else:
                st.error("加载预设失败")
        
        # 保存当前配置为预设
        st.markdown("---")
        preset_name = st.text_input("预设名称", value="", help="留空则使用日期格式自动命名")
        
        if st.button("保存当前配置为预设"):
            # 收集当前配置
            current_config = {
                'subscription_urls': st.session_state.subscription_urls,
                'direct_nodes': st.session_state.direct_nodes,
                'port': st.session_state.port,
                'mixed_port': st.session_state.mixed_port,
                'enable_port_mapping': st.session_state.enable_port_mapping,
                'default_port': st.session_state.default_port,
                'start_mapping_port': st.session_state.start_mapping_port,
                'default_node': st.session_state.default_node,
                'output_file': st.session_state.output_file,
                'listener_type': st.session_state.listener_type if 'listener_type' in st.session_state else 'mixed'
            }
            
            # 保存配置预设
            saved_name = save_config_preset(preset_name, current_config)
            st.success(f"已保存预设: {saved_name}")
            # 刷新页面以更新预设列表
            st.experimental_rerun()
        
        # 删除预设
        if presets and st.button("删除选中的预设"):
            if selected_preset:
                if delete_config_preset(selected_preset):
                    st.success(f"已删除预设: {selected_preset}")
                    # 刷新页面以更新预设列表
                    st.experimental_rerun()
                else:
                    st.error("删除预设失败")
            else:
                st.warning("请先选择一个预设")
        
        st.markdown("---")
        
        # 基本端口设置
        st.subheader("基本端口设置")
        port = st.number_input("HTTP代理端口", value=st.session_state.port, min_value=1, max_value=65535)
        mixed_port = st.number_input("混合代理端口", value=st.session_state.mixed_port, min_value=1, max_value=65535)
        
        # 模板文件选择
        st.subheader("规则模板设置")
        template_file = st.file_uploader(
            "选择规则模板文件", 
            type=["yaml", "yml"],
            help="上传包含代理组和规则的YAML模板文件，如果不上传将使用默认模板"
        )
        
        if template_file is not None:
            # 保存上传的模板文件
            template_path = os.path.join(os.path.dirname(__file__), "template.yaml")
            with open(template_path, "wb") as f:
                f.write(template_file.getvalue())
            st.session_state.template_path = template_path
            st.success(f"成功加载模板文件: {template_file.name}")
        
        # 端口映射设置
        st.subheader("端口映射设置")
        enable_port_mapping = st.checkbox("启用端口映射", value=st.session_state.enable_port_mapping, help="为选定节点分配特定端口")
        
        # 更新会话状态
        st.session_state.enable_port_mapping = enable_port_mapping
        
        # 设置映射起始端口和监听器类型
        if enable_port_mapping:
            st.session_state.start_mapping_port = st.number_input(
                "端口映射起始值",
                value=st.session_state.start_mapping_port,
                min_value=1025,
                max_value=65000,
                help="建议的节点端口映射起始值，可在配置端口映射时修改")
            
            # 添加监听器类型选择
            listener_type_options = ["mixed", "socks", "http"]
            listener_type_index = 0  # 默认选择 mixed
            
            if 'listener_type' in st.session_state:
                try:
                    listener_type_index = listener_type_options.index(st.session_state.listener_type)
                except ValueError:
                    listener_type_index = 0
            
            listener_type = st.selectbox(
                "端口映射监听器类型",
                listener_type_options,
                index=listener_type_index,
                help="mixed: 同时支持HTTP和SOCKS5, socks: 仅SOCKS5, http: 仅HTTP"
            )
            
            # 更新会话状态
            st.session_state.listener_type = listener_type
            
            # 添加端口映射的说明
            st.info(f"端口映射将使您可以通过不同端口直接访问特定节点，无需通过规则选择。每个节点会创建一个{listener_type}类型监听器，{'同时支持HTTP和SOCKS5协议' if listener_type == 'mixed' else '仅支持SOCKS5协议' if listener_type == 'socks' else '仅支持HTTP协议'}。系统会自动为每个映射端口生成相应的分流规则，确保通过该端口的流量直接使用对应节点。您可以在加载节点后选择需要映射的节点和端口。")
        else:
            # 确保listener_type默认值存在
            if 'listener_type' not in st.session_state:
                st.session_state.listener_type = "mixed"
        
        # 文件名设置
        st.subheader("输出设置")
        output_file = st.text_input("配置文件名", value=st.session_state.output_file)
        
        # 更新会话状态
        st.session_state.output_file = output_file
        
        # 关于信息
        st.markdown("---")
        st.markdown("### 关于")
        st.markdown("Clash 配置生成器是一个用于合并多个代理订阅的工具。")
        st.markdown("支持Vmess、Shadowsocks、Trojan和Hysteria等协议。")
    
    # 创建标签页
    tab1, tab2, tab3 = st.tabs(["订阅链接", "直连节点", "配置生成"])
    
    # 订阅链接标签页
    with tab1:
        st.header("订阅链接")
        st.markdown("添加一个或多个订阅链接，每行一个链接")
        
        subscription_urls = st.text_area(
            "订阅链接 (每行一个)",
            value=st.session_state.subscription_urls,
            height=150,
            help="输入Clash订阅链接，每行一个",
        )
        
        # 更新会话状态
        st.session_state.subscription_urls = subscription_urls
    
    # 直连节点标签页
    with tab2:
        st.header("直连节点")
        st.markdown("添加直连节点，支持vmess://、ss://、trojan://等格式")
        
        direct_nodes = st.text_area(
            "直连节点 (每行一个)",
            value=st.session_state.direct_nodes,
            height=150,
            help="输入节点链接，每行一个，支持vmess://、ss://、trojan://等格式",
        )
        
        # 更新会话状态
        st.session_state.direct_nodes = direct_nodes
        
        uploaded_file = st.file_uploader(
            "或者上传包含节点的文件",
            help="上传包含节点链接的文本文件，每行一个节点",
        )
    
    # 配置生成标签页
    with tab3:
        st.header("配置生成")
        
        # 添加加载节点按钮
        if st.button("加载节点", help="获取所有节点但不立即生成配置，可用于配置端口映射"):
            with st.spinner("正在加载节点..."):
                try:
                    # 初始化组件
                    sub_manager = SubscriptionManager()
                    node_parser = NodeParser()
                    
                    # 收集所有节点
                    all_proxies = []
                    
                    # 处理订阅链接
                    if subscription_urls:
                        urls = [url.strip() for url in subscription_urls.split('\n') if url.strip()]
                        for url in urls:
                            st.info(f"正在处理订阅: {url}")
                            proxies = sub_manager.fetch_and_parse(url)
                            st.success(f"从订阅获取到 {len(proxies)} 个节点")
                            all_proxies.extend(proxies)
                            
                            # 按来源分组保存
                            if url not in st.session_state.proxies_by_source:
                                st.session_state.proxies_by_source[url] = []
                            st.session_state.proxies_by_source[url].extend(proxies)
                    
                    # 处理直连节点
                    if direct_nodes:
                        nodes = [node.strip() for node in direct_nodes.split('\n') if node.strip()]
                        direct_proxies = []
                        
                        for node_str in nodes:
                            proxy = parse_proxy(node_str)
                            if proxy:
                                # 添加来源信息
                                proxy['_source'] = 'direct'
                                direct_proxies.append(proxy)
                                all_proxies.append(proxy)
                                logger.info(f"成功解析直连节点: {proxy['name']}")
                            else:
                                st.warning(f"无法解析节点: {node_str[:30]}...")
                        
                        # 按来源分组保存直连节点
                        if direct_proxies:
                            st.session_state.proxies_by_source['direct'] = direct_proxies
                    
                    # 处理上传的文件
                    if uploaded_file:
                        content = uploaded_file.getvalue().decode('utf-8')
                        nodes = [node.strip() for node in content.split('\n') if node.strip() and not node.startswith('#')]
                        file_proxies = []
                        
                        for node_str in nodes:
                            proxy = parse_proxy(node_str)
                            if proxy:
                                # 添加来源信息
                                proxy['_source'] = f'file:{uploaded_file.name}'
                                file_proxies.append(proxy)
                                all_proxies.append(proxy)
                                logger.info(f"成功解析文件中的节点: {proxy['name']}")
                            else:
                                logger.warning(f"无法解析文件中的节点: {node_str[:30]}...")
                        
                        # 按来源分组保存上传文件的节点
                        if file_proxies:
                            file_source = f'file:{uploaded_file.name}'
                            st.session_state.proxies_by_source[file_source] = file_proxies
                            
                        st.success(f"从文件中解析了 {len(nodes)} 个节点，成功 {len(file_proxies)} 个")
                    
                    # 检查是否有有效节点
                    if not all_proxies:
                        st.error("没有找到有效的代理节点，请检查输入")
                        return
                    
                    # 保存节点到会话状态
                    st.session_state.all_proxies = all_proxies
                    st.session_state.nodes_loaded = True
                    
                    # 初始化端口映射字典
                    node_mappings = {}
                    if enable_port_mapping:
                        # 为节点分配建议的端口值，用户可以稍后修改
                        port = st.session_state.start_mapping_port
                        for proxy in all_proxies:
                            node_mappings[proxy['name']] = {"enabled": False, "port": port}
                            port += 1
                    
                    st.session_state.node_mappings = node_mappings
                    
                    st.success(f"成功加载 {len(all_proxies)} 个节点，可以继续配置端口映射。")
                    
                except Exception as e:
                    st.error(f"加载节点时出错: {str(e)}")
        
        # 显示节点表格和端口映射配置（如果节点已加载）
        if st.session_state.nodes_loaded and st.session_state.enable_port_mapping:
            st.subheader("节点端口映射配置")
            st.markdown("为需要进行端口映射的节点配置端口。只有启用的节点会创建端口映射。")
            
            # 创建一个表单用于配置节点端口映射
            with st.form("port_mapping_form"):
                # 获取分组后的节点
                proxies_by_source = st.session_state.proxies_by_source
                all_proxies = st.session_state.all_proxies
                
                # 设置起始端口
                start_port = st.number_input(
                    "端口映射起始值", 
                    value=st.session_state.start_mapping_port,
                    min_value=1000,
                    max_value=65000,
                    help="设置端口映射的起始值，选中的节点将从此端口开始分配"
                )
                
                # 更新会话状态中的起始端口
                st.session_state.start_mapping_port = start_port
                
                # 初始化更新后的映射
                updated_mappings = {}
                node_index = 0  # 用于生成唯一的键
                
                # 遍历每个订阅源
                for source, proxies in proxies_by_source.items():
                    if not proxies:
                        continue
                        
                    # 显示订阅源标题
                    source_display = source
                    if source == 'direct':
                        source_display = '直连节点'
                    elif source.startswith('file:'):
                        source_display = f'文件: {source[5:]}'
                        
                    st.markdown(f"### {source_display} ({len(proxies)}个)")
                    
                    # 添加全选按钮
                    source_key = f"source_{source.replace(':', '_')}"
                    
                    # 获取当前全选状态
                    if source_key not in st.session_state.source_all_selected:
                        st.session_state.source_all_selected[source_key] = False
                    
                    # 显示全选复选框 - 移除on_change参数
                    all_enabled = st.checkbox(
                        f"全选此来源的节点", 
                        value=st.session_state.source_all_selected[source_key],
                        key=f"all_{source_key}"
                    )
                    
                    # 检测全选状态变化
                    if all_enabled != st.session_state.source_all_selected[source_key]:
                        # 更新全选状态
                        st.session_state.source_all_selected[source_key] = all_enabled
                        
                        # 同步更新所有节点状态到会话状态
                        for proxy in proxies:
                            node_name = proxy['name']
                            if node_name in st.session_state.node_mappings:
                                # 将节点状态与全选状态同步
                                st.session_state.node_mappings[node_name]["enabled"] = all_enabled
                                
                                # 同时更新updated_mappings，确保表单提交时状态一致
                                if node_name in updated_mappings:
                                    updated_mappings[node_name]["enabled"] = all_enabled
                    
                    # 创建折叠区域来展示节点
                    with st.expander(f"展开查看 {source_display} 的所有节点", expanded=False):
                        # 使用单行布局展示节点，每行一个节点卡片
                        for i, proxy in enumerate(proxies):
                            node_name = proxy['name']
                            
                            # 获取当前节点的映射配置
                            node_mapping = st.session_state.node_mappings.get(node_name, {
                                "enabled": False, 
                                "port": start_port + node_index
                            })
                            
                            # 如果全选状态被激活，同步到节点状态
                            if all_enabled and not node_mapping["enabled"]:
                                node_mapping["enabled"] = True
                            
                            # 使用单行布局，创建一个节点卡片
                            with st.container():
                                col1, col2, col3 = st.columns([2, 5, 3])
                                
                                with col1:
                                    st.markdown('<div class="node-cell">', unsafe_allow_html=True)
                                    enabled = st.checkbox(
                                        "启用", 
                                        value=node_mapping["enabled"],
                                        key=f"enable_{node_index}"
                                    )
                                    st.markdown('</div>', unsafe_allow_html=True)
                                
                                with col2:
                                    st.markdown('<div class="node-cell">', unsafe_allow_html=True)
                                    st.markdown(f"**{node_name}**")
                                    st.markdown('</div>', unsafe_allow_html=True)
                                
                                with col3:
                                    st.markdown('<div class="node-cell">', unsafe_allow_html=True)
                                    # 只有在启用时才显示端口输入框
                                    if enabled:
                                        port = st.number_input(
                                            f"端口", 
                                            value=node_mapping["port"], 
                                            min_value=1, 
                                            max_value=65535, 
                                            key=f"port_{node_index}"
                                        )
                                    else:
                                        port = node_mapping["port"]
                                    st.markdown('</div>', unsafe_allow_html=True)
                            
                            # 添加分隔线，使节点之间视觉上分离
                            st.markdown('<hr style="margin: 3px 0; border: 0; border-top: 1px solid #eee;">', unsafe_allow_html=True)
                            
                            # 更新映射配置
                            updated_mappings[node_name] = {"enabled": enabled, "port": port}
                            node_index += 1
                    
                    # 添加小节间的分隔线
                    st.markdown("---")
                
                # 提交按钮
                submitted = st.form_submit_button("保存端口映射配置")
                if submitted:
                    # 同步全选状态到节点状态
                    for source, proxies in proxies_by_source.items():
                        source_key = f"source_{source.replace(':', '_')}"
                        if source_key in st.session_state.source_all_selected and st.session_state.source_all_selected[source_key]:
                            # 如果此来源被全选，确保所有节点都被启用
                            for proxy in proxies:
                                node_name = proxy['name']
                                if node_name in updated_mappings:
                                    updated_mappings[node_name]["enabled"] = True
                    
                    # 更新会话状态中的端口映射配置
                    st.session_state.node_mappings = updated_mappings
                    
                    # 创建折叠日志区域
                    with st.expander("操作日志", expanded=False):
                        st.success("端口映射配置已保存！")
                        
                        # 计算已启用的端口映射总数
                        enabled_count = sum(1 for mapping in updated_mappings.values() if mapping.get("enabled", False))
                        st.info(f"共有 {len(updated_mappings)} 个节点，其中已启用 {enabled_count} 个端口映射")
                        
                        # 显示详细信息
                        if enabled_count > 0:
                            st.subheader("已启用的端口映射")
                            listener_type = st.session_state.listener_type if 'listener_type' in st.session_state else 'mixed'
                            for name, mapping in updated_mappings.items():
                                if mapping.get("enabled", False):
                                    st.text(f"- {name} → {listener_type.capitalize()}:{mapping['port']}")
            
            # 移除重复的端口映射摘要，改为在表单外简单显示总数
            enabled_mappings = {name: mapping for name, mapping in st.session_state.node_mappings.items() if mapping["enabled"]}
            if enabled_mappings:
                st.success(f"已成功配置 {len(enabled_mappings)} 个节点的端口映射")
                # 添加查看提示
                st.info("点击上方的「操作日志」可查看详细的端口映射信息")
        
        st.markdown("---")
        st.markdown("点击下方按钮生成并下载配置文件")
        
        if st.button("生成配置", type="primary"):
            with st.spinner("正在生成配置..."):
                try:
                    # 初始化组件
                    sub_manager = SubscriptionManager()
                    config_generator = ClashConfigGenerator()
                    
                    # 更新基本配置
                    config_generator.update_basic_config(
                        port=port,
                        mixed_port=mixed_port
                    )
                    
                    # 使用已加载的节点或重新加载
                    all_proxies = []
                    
                    # 创建一个折叠日志区域
                    log_expander = st.expander("生成配置日志", expanded=False)
                    
                    with log_expander:
                        if st.session_state.nodes_loaded:
                            all_proxies = st.session_state.all_proxies
                            st.info(f"使用已加载的 {len(all_proxies)} 个节点")
                        else:
                            # 收集所有节点
                            # 处理订阅链接
                            if subscription_urls:
                                urls = [url.strip() for url in subscription_urls.split('\n') if url.strip()]
                                for url in urls:
                                    st.info(f"正在处理订阅: {url}")
                                    proxies = sub_manager.fetch_and_parse(url)
                                    st.success(f"从订阅获取到 {len(proxies)} 个节点")
                                    all_proxies.extend(proxies)
                            
                            # 处理直连节点
                            if direct_nodes:
                                nodes = [node.strip() for node in direct_nodes.split('\n') if node.strip()]
                                for node_str in nodes:
                                    proxy = parse_proxy(node_str)
                                    if proxy:
                                        all_proxies.append(proxy)
                                        logger.info(f"成功解析直连节点: {proxy['name']}")
                                    else:
                                        st.warning(f"无法解析节点: {node_str[:30]}...")
                            
                            # 处理上传的文件
                            if uploaded_file:
                                content = uploaded_file.getvalue().decode('utf-8')
                                nodes = [node.strip() for node in content.split('\n') if node.strip() and not node.startswith('#')]
                                for node_str in nodes:
                                    proxy = parse_proxy(node_str)
                                    if proxy:
                                        all_proxies.append(proxy)
                                        logger.info(f"成功解析文件中的节点: {proxy['name']}")
                                    else:
                                        logger.warning(f"无法解析文件中的节点: {node_str[:30]}...")
                                st.success(f"从文件中解析了 {len(nodes)} 个节点")
                    
                    # 检查是否有有效节点
                    if not all_proxies:
                        st.error("没有找到有效的代理节点，请检查输入")
                        return
                    
                    # 更新代理列表
                    config_generator.update_proxies(all_proxies)
                    config_generator.update_enabled_proxies(all_proxies)
                    
                    # 使用模板路径（如果有）
                    if st.session_state.template_path and os.path.exists(st.session_state.template_path):
                        template_content = load_local_file(st.session_state.template_path)
                        if template_content:
                            config_generator.update_from_template(template_content)
                            with log_expander:
                                st.info(f"已应用模板: {st.session_state.template_path}")
                    
                    # 处理端口映射
                    if st.session_state.enable_port_mapping and st.session_state.nodes_loaded:
                        # 如果用户已经配置了端口映射，使用用户的配置
                        if st.session_state.node_mappings:
                            # 获取监听器类型
                            listener_type = st.session_state.listener_type if 'listener_type' in st.session_state else 'mixed'
                            
                            # 转换为node_port_mappings格式
                            node_port_mappings = {}
                            for node_name, mapping in st.session_state.node_mappings.items():
                                if mapping.get("enabled", False):
                                    node_port_mappings[node_name] = mapping["port"]
                            
                            config_generator.generate_port_mappings(node_port_mappings, listener_type=listener_type)
                            
                            # 显示已启用的端口映射信息
                            if node_port_mappings:
                                with log_expander:
                                    st.subheader(f"使用以下端口映射 (类型: {listener_type})")
                                    for name, port in node_port_mappings.items():
                                        st.text(f"{name} → {listener_type.capitalize()}:{port}")
                    
                    # 生成配置
                    with log_expander:
                        st.info(f"共有 {len(all_proxies)} 个节点，开始生成配置")
                    
                    # 生成配置
                    config_yaml = config_generator.generate_full_config()
                    
                    # 创建临时文件
                    with NamedTemporaryFile(suffix='.yaml', delete=False) as temp_file:
                        temp_path = temp_file.name
                        with open(temp_path, 'w', encoding='utf-8') as f:
                            f.write(config_yaml)
                    
                    # 创建下载链接
                    st.markdown(get_download_link(temp_path, output_file), unsafe_allow_html=True)
                    st.success("配置生成完成!")
                    
                    # 可选：保存配置到本地目录
                    save_local = st.checkbox("同时保存配置到本地目录", value=True)
                    if save_local:
                        local_filename = f"local_config_{datetime.now().strftime('%y-%m-%d')}.yaml"
                        local_path = os.path.join(CONFIG_DIR, local_filename)
                        with open(local_path, 'w', encoding='utf-8') as f:
                            f.write(config_yaml)
                        with log_expander:
                            st.success(f"配置已保存到本地: {local_path}")
                    
                    # 删除临时文件
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
                    
                except Exception as e:
                    st.error(f"生成配置时出错: {str(e)}")
                    with st.expander("错误详情", expanded=True):
                        import traceback
                        st.error(traceback.format_exc())

if __name__ == "__main__":
    main()
