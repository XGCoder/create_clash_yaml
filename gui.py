#!/usr/bin/env python
# -*- coding: utf-8 -*-

import streamlit as st
import logging
import os
import glob
import re
import yaml
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

# 从包导入所需的组件
from clash_config_generator.config_generator import ClashConfigGenerator
from clash_config_generator.subscription import SubscriptionManager
from clash_config_generator.node_parser import parse_proxy

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("clash_config_generator_gui")

# 设置页面配置
st.set_page_config(
    page_title="Clash Configurator Pro",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Session State Initialization ---
states = {
    'subscription_urls': "",
    'selected_template': None,
    'custom_template_content': None,
    'nodes_loaded': False,
    'all_proxies': [],
    'proxies_by_source': {},
    'enable_port_mapping': False,
    'node_mappings': {},
    'start_mapping_port': 42001,
    'source_all_selected': {},
    'port_mapping_confirmed': False,
}
for key, value in states.items():
    if key not in st.session_state:
        st.session_state[key] = value

def get_template_files():
    """获取项目根目录下的所有YAML模板文件。"""
    return glob.glob("*.yaml")

def update_node_ports():
    """当起始端口改变时，更新所有节点的端口映射。"""
    start_port = st.session_state.start_mapping_port
    if 'all_proxies' in st.session_state and 'node_mappings' in st.session_state:
        for i, proxy in enumerate(st.session_state.all_proxies):
            if proxy['name'] in st.session_state.node_mappings:
                st.session_state.node_mappings[proxy['name']]['port'] = start_port + i

def toggle_all_nodes(source_key, proxies):
    """切换一个源的所有节点的启用状态。"""
    is_checked = st.session_state[f"all_{source_key}"]
    for p in proxies:
        node_name = p['name']
        if node_name in st.session_state.node_mappings:
            # 更新 node_mappings 中的状态
            st.session_state.node_mappings[node_name]['enabled'] = is_checked
            # 同步更新单个checkbox的session state key
            checkbox_key = f"enable_{node_name}"
            st.session_state[checkbox_key] = is_checked

def validate_port_unique(node_name, new_port):
    """
    验证端口是否唯一（仅检查已启用的节点）

    Args:
        node_name (str): 当前节点名称
        new_port (int): 要设置的新端口

    Returns:
        tuple: (是否唯一, 冲突的节点名或None)
    """
    for name, mapping in st.session_state.node_mappings.items():
        if name != node_name and mapping.get('enabled') and mapping.get('port') == new_port:
            return False, name
    return True, None

def on_port_change():
    """
    端口输入框的 on_change 回调
    当用户修改任何端口时，自动取消「确认端口映射」状态
    """
    if st.session_state.get('port_mapping_confirmed', False):
        st.session_state.port_mapping_confirmed = False
        logger.info("端口已修改，已自动取消「确认端口映射」状态")

def validate_and_confirm_ports():
    """
    验证并确认所有端口映射的回调函数
    当用户勾选「确认端口映射」复选框时触发

    验证所有已启用节点的端口冲突：
    - 无冲突：保持勾选状态
    - 有冲突：强制取消勾选，显示错误提示
    """
    is_checked = st.session_state.get('port_mapping_confirmed', False)

    if not is_checked:
        # 用户取消勾选，无需验证
        logger.info("用户取消了端口映射确认")
        return

    # 用户勾选，先同步所有端口输入框的值到 node_mappings
    logger.info("开始同步端口值到 node_mappings...")
    for node_name, mapping in st.session_state.node_mappings.items():
        if mapping.get('enabled'):
            port_input_key = f"port_{node_name}"
            if port_input_key in st.session_state:
                # 获取用户输入的端口值
                new_port = st.session_state[port_input_key]
                # 同步到 node_mappings
                st.session_state.node_mappings[node_name]['port'] = new_port
                logger.debug(f"节点 '{node_name}' 端口同步: {mapping.get('port')} -> {new_port}")

    # 开始验证
    has_conflicts, conflicts = check_port_conflicts()

    if has_conflicts:
        # 有冲突，强制取消勾选
        st.session_state.port_mapping_confirmed = False

        # 显示详细的冲突信息
        conflict_details = []
        for port, nodes in conflicts:
            conflict_details.append(f"端口 {port}: {', '.join([n[:20] + '...' if len(n) > 20 else n for n in nodes])}")

        error_msg = f"❌ 端口验证失败！检测到 {len(conflicts)} 个端口冲突：\n" + "\n".join(conflict_details)
        st.toast(error_msg, icon="❌")
        logger.error(f"端口映射确认失败: 存在 {len(conflicts)} 个端口冲突")
        st.rerun()
    else:
        # 无冲突，保持勾选
        enabled_count = sum(1 for m in st.session_state.node_mappings.values() if m.get('enabled'))
        st.toast(f"✅ 端口验证通过！所有 {enabled_count} 个端口均无冲突")
        logger.info(f"端口映射确认成功: 所有 {enabled_count} 个端口均无冲突")

def auto_fix_port_conflicts():
    """
    自动修正所有端口冲突
    从起始端口开始，为所有启用的节点重新分配不冲突的端口
    """
    if 'node_mappings' not in st.session_state:
        return

    start_port = st.session_state.get('start_mapping_port', 42001)
    enabled_nodes = [(name, mapping) for name, mapping in st.session_state.node_mappings.items() if mapping.get('enabled')]

    # 按原有端口排序，保持相对顺序
    enabled_nodes.sort(key=lambda x: x[1].get('port', 0))

    # 重新分配端口
    current_port = start_port
    for name, mapping in enabled_nodes:
        st.session_state.node_mappings[name]['port'] = current_port
        current_port += 1

    logger.info(f"自动修正端口冲突完成，共分配 {len(enabled_nodes)} 个端口")

def check_port_conflicts():
    """
    检查当前所有启用节点的端口冲突

    Returns:
        tuple: (是否有冲突, 冲突列表)
        冲突列表格式: [(端口号, [节点名1, 节点名2, ...])]
    """
    port_usage = {}
    for name, mapping in st.session_state.node_mappings.items():
        if mapping.get('enabled'):
            port = mapping.get('port')
            if port not in port_usage:
                port_usage[port] = []
            port_usage[port].append(name)

    conflicts = [(port, nodes) for port, nodes in port_usage.items() if len(nodes) > 1]
    return len(conflicts) > 0, conflicts

def add_multiple_nodes():
    """
    从文本区域解析一个或多个节点URI并将其添加到会话状态。
    """
    uris = st.session_state.get("multiple_node_uris", "")
    if not uris.strip():
        st.toast("⚠️ 请输入至少一个节点URI。" )
        return

    uris_list = [uri.strip() for uri in uris.splitlines() if uri.strip()]
    
    successful_count = 0
    failed_count = 0
    
    manual_source_name = "手动添加"

    # 确保核心 state keys 存在
    if 'all_proxies' not in st.session_state:
        st.session_state.all_proxies = []
    if 'proxies_by_source' not in st.session_state:
        st.session_state.proxies_by_source = {}
    if manual_source_name not in st.session_state.proxies_by_source:
        st.session_state.proxies_by_source[manual_source_name] = []
    if 'node_mappings' not in st.session_state:
        st.session_state.node_mappings = {}

    with st.spinner(f"正在解析和添加 {len(uris_list)} 个节点..."):
        for uri in uris_list:
            try:
                node = parse_proxy(uri)
                if node:
                    # 检查节点是否已存在
                    if any(p['name'] == node['name'] for p in st.session_state.all_proxies):
                        logger.warning(f"节点 '{node['name']}' 已存在，跳过添加。" )
                        failed_count += 1
                        continue

                    node['_source'] = manual_source_name
                    
                    st.session_state.all_proxies.append(node)
                    st.session_state.proxies_by_source[manual_source_name].append(node)
                    
                    # 为新节点添加映射
                    port = st.session_state.start_mapping_port + len(st.session_state.all_proxies) - 1
                    st.session_state.node_mappings[node['name']] = {"enabled": False, "port": port}
                    
                    successful_count += 1
                else:
                    logger.error(f"无法解析URI: {uri}")
                    failed_count += 1
            except Exception as e:
                logger.error(f"处理URI时出错 '{uri}': {e}")
                failed_count += 1

    # 显示结果
    if successful_count > 0:
        st.toast(f"✅ 成功添加 {successful_count} 个节点。" )
        st.session_state.force_collapse = True
    if failed_count > 0:
        st.toast(f"❌ {failed_count} 个节点添加失败（可能已存在或格式错误）。" )

    # 清理输入框
    if successful_count > 0:
        st.session_state.multiple_node_uris = ""

def callback_load_nodes():
    """
    Callback function to load nodes from subscription URLs.
    """
    with st.spinner("正在从订阅链接加载节点..."):
        # 先筛选出所有手动添加的节点并保留
        manual_source_name = "手动添加"
        existing_proxies = st.session_state.get('all_proxies', [])
        all_proxies = [p for p in existing_proxies if p.get('_source') == manual_source_name]
        
        existing_sources = st.session_state.get('proxies_by_source', {})
        proxies_by_source = {k: v for k, v in existing_sources.items() if k == manual_source_name}

        sub_manager = SubscriptionManager()

        if st.session_state.subscription_urls:
            urls = [url.strip() for url in st.session_state.subscription_urls.split('\n') if url.strip()]
            for url in urls:
                proxies = sub_manager.fetch_and_parse(url)
                if proxies:
                    source_name = urlparse(url).netloc
                    # Always replace (not extend) to avoid accumulating old proxies
                    proxies_by_source[source_name] = proxies

        # Rebuild all_proxies from scratch by combining all sources
        # This ensures no accumulation when reloading
        for source_proxies in proxies_by_source.values():
            all_proxies.extend(source_proxies)
        
        st.session_state.all_proxies = all_proxies
        st.session_state.proxies_by_source = proxies_by_source
        st.session_state.nodes_loaded = True
        
        old_mappings = st.session_state.get('node_mappings', {})
        new_mappings = {}
        port = st.session_state.start_mapping_port
        for proxy in all_proxies:
            proxy_name = proxy['name']
            if proxy_name in old_mappings:
                new_mappings[proxy_name] = {
                    "enabled": old_mappings[proxy_name].get('enabled', False),
                    "port": port
                }
            else:
                new_mappings[proxy_name] = {"enabled": False, "port": port}
            port += 1
        st.session_state.node_mappings = new_mappings
        st.session_state.force_collapse = True

def display_proxy_details(proxy):
    """Displays the details of a proxy node in a YAML format, excluding internal keys."""
    details_to_show = proxy.copy()
    details_to_show.pop('_source', None) # Safely remove the internal key
    st.code(yaml.dump(details_to_show, allow_unicode=True, sort_keys=False), language='yaml')

def main():
    """Streamlit应用主函数"""
    
    st.title("Clash Configurator Pro")
    st.markdown("一个基于模板的、现代化的Clash配置文件生成工具。" )

    # --- 主布局 ---
    col1, col2, col3 = st.columns([3, 5, 2.8])

    # --- Column 1: Inputs ---
    with col1:
        st.header("📥 输入源")
        with st.container(border=True):
            st.subheader("① 选择或上传模板")
            template_files = get_template_files()
            if not template_files and not st.session_state.custom_template_content:
                st.error("错误：项目根目录下未找到任何.yaml模板文件。请添加一个或上传一个模板。" )

            if st.session_state.selected_template is None and template_files:
                preferred_template = next((t for t in template_files if 'qishiyu' in t), template_files[0])
                st.session_state.selected_template = preferred_template

            st.selectbox("选择一个预设模板", options=template_files, key='selected_template')
            
            uploaded_file = st.file_uploader("或上传自定义模板", type=['yaml', 'yml'])
            if uploaded_file:
                st.session_state.custom_template_content = uploaded_file.getvalue().decode('utf-8')
                st.success(f"已上传模板 '{uploaded_file.name}'")

        with st.container(border=True):
            st.subheader("② 输入订阅链接")
            st.text_area("每个链接占一行", key="subscription_urls", height=150)

        st.button("加载节点", type="primary", use_container_width=True, on_click=callback_load_nodes)

        with st.container(border=True):
            st.subheader("③ 添加手动节点")
            st.text_area(
                "输入单个或多个节点URI (每行一个)", 
                key="multiple_node_uris", 
                height=150,
                placeholder="例如: vmess://...\nss://...\ntrojan://..."
            )
            st.button("添加节点", type="primary", use_container_width=True, on_click=add_multiple_nodes)

    # --- Column 3: Settings & Actions ---
    with col3:
        st.header("🚀 设置与生成")
        with st.container(border=True):
            st.subheader("端口映射")
            st.checkbox("启用多端口映射", key='enable_port_mapping')
            if st.session_state.enable_port_mapping:
                st.number_input(
                    "起始端口",
                    value=st.session_state.start_mapping_port,
                    key='start_mapping_port',
                    min_value=1025,
                    max_value=65000,
                    on_change=update_node_ports
                )

                # 确认端口映射复选框
                st.checkbox(
                    "确认端口映射",
                    key='port_mapping_confirmed',
                    on_change=validate_and_confirm_ports,
                    help="勾选以验证所有端口配置，验证通过后才能生成配置文件"
                )

                # 端口冲突检查和自动修复
                has_conflicts, conflicts = check_port_conflicts()
                if has_conflicts:
                    st.warning(f"⚠️ 检测到 {len(conflicts)} 个端口冲突")
                    with st.expander("查看冲突详情", expanded=True):
                        for port, nodes in conflicts:
                            st.error(f"**端口 {port}** 被以下节点共用:")
                            for node in nodes:
                                st.text(f"  • {node[:40]}{'...' if len(node) > 40 else ''}")

                    # 自动修复按钮
                    if st.button("🔧 自动修复端口冲突", use_container_width=True, type="secondary"):
                        auto_fix_port_conflicts()
                        st.success("✅ 端口冲突已自动修正！")
                        st.rerun()
                else:
                    # 检查是否已确认端口映射
                    enabled_count = sum(1 for m in st.session_state.node_mappings.values() if m.get('enabled'))
                    if enabled_count > 0:
                        if st.session_state.get('port_mapping_confirmed', False):
                            # 已确认且无冲突
                            st.success(f"✅ 所有 {enabled_count} 个端口均无冲突")
                        else:
                            # 未确认
                            st.info(f"ℹ️ 请勾选上方的「确认端口映射」以验证 {enabled_count} 个端口配置")

        with st.container(border=True):
            st.subheader("生成配置文件")
            # 使用东八区（北京时间）
            beijing_tz = timezone(timedelta(hours=8))
            beijing_time = datetime.now(beijing_tz)
            output_filename = st.text_input("输出文件名", value=f"config_{beijing_time.strftime('%Y%m%d_%H%M')}.yaml")

            if st.button("生成配置文件", type="primary", use_container_width=True):
                template_path = st.session_state.selected_template
                if not template_path and not st.session_state.custom_template_content:
                    st.error("请先选择或上传一个模板文件！")
                else:
                    # 检查端口映射确认状态
                    if st.session_state.enable_port_mapping:
                        if not st.session_state.get('port_mapping_confirmed', False):
                            st.error("❌ 请先勾选上方的「确认端口映射」以验证所有端口配置！")
                            logger.error("生成配置失败: 端口映射未确认")
                        else:
                            # 已确认，继续生成
                            generate_config_file(template_path, output_filename)
                    else:
                        # 未启用端口映射，直接生成
                        generate_config_file(template_path, output_filename)

    # --- Column 2: Node Configuration ---
    with col2:
        st.header("⚙️ 节点列表")
        if not st.session_state.nodes_loaded:
            st.info("请从左侧加载节点以查看列表。")
        else:
            total_nodes = len(st.session_state.all_proxies)
            mapped_nodes = sum(1 for m in st.session_state.node_mappings.values() if m.get('enabled'))
            c1, c2 = st.columns(2)
            c1.metric("总节点数", f"{total_nodes} 个")
            c2.metric("已映射端口", f"{mapped_nodes} 个" if st.session_state.enable_port_mapping else "-")

            st.info("点击订阅源可展开/折叠节点列表：")

            # Consume the collapse flag, and set the default state
            force_collapse = st.session_state.pop('force_collapse', False)
            default_expanded_state = not force_collapse

            for source, proxies in st.session_state.proxies_by_source.items():
                if not proxies:
                    continue

                expander_title = f"源: {source} ({len(proxies)}个节点)"
                with st.expander(expander_title, expanded=default_expanded_state):
                    source_key = re.sub(r'[^a-zA-Z0-9]', '_', source)

                    if st.session_state.enable_port_mapping:
                        # 在渲染全选checkbox之前，根据所有单个节点状态初始化全选checkbox的state
                        all_checkbox_key = f"all_{source_key}"
                        if all_checkbox_key not in st.session_state:
                            # 首次初始化为False
                            st.session_state[all_checkbox_key] = False
                        else:
                            # 如果已存在，根据当前所有节点状态更新（在widget创建前更新是允许的）
                            all_enabled = all(st.session_state.node_mappings.get(p['name'], {}).get('enabled', False) for p in proxies)
                            st.session_state[all_checkbox_key] = all_enabled

                        st.checkbox(
                            "全选/取消全选",
                            key=all_checkbox_key,
                            on_change=toggle_all_nodes,
                            kwargs={'source_key': source_key, 'proxies': proxies}
                        )
                        st.markdown("---")

                        for proxy in proxies:
                            node_name = proxy['name']
                            node_mapping = st.session_state.node_mappings.get(node_name)
                            if not node_mapping:
                                continue

                            # 初始化checkbox的session state（如果不存在）
                            checkbox_key = f"enable_{node_name}"
                            if checkbox_key not in st.session_state:
                                st.session_state[checkbox_key] = node_mapping["enabled"]

                            c1, c2, c3 = st.columns([1, 5, 3])
                            # 移除value参数，只使用key参数，避免Streamlit警告
                            enabled = c1.checkbox(" ", key=checkbox_key, label_visibility="collapsed")

                            # 检查状态是否改变
                            if enabled != node_mapping['enabled']:
                                # 更新 node_mappings
                                st.session_state.node_mappings[node_name]['enabled'] = enabled
                                st.rerun()

                            with c2.expander(node_name):
                                display_proxy_details(proxy)

                            if enabled:
                                # 端口输入框（修改端口时自动取消确认状态）
                                c3.number_input(
                                    "端口",
                                    value=node_mapping["port"],
                                    key=f"port_{node_name}",
                                    label_visibility="collapsed",
                                    min_value=1025,
                                    max_value=65535,
                                    on_change=on_port_change
                                )
                    else:
                        for proxy in proxies:
                            with st.expander(proxy['name']):
                                display_proxy_details(proxy)

def generate_config_file(template_path, output_filename):
    """生成配置文件的实际逻辑（提取为独立函数）"""
    temp_template_path = None
    try:
        with st.spinner("正在生成配置..."):
            if st.session_state.custom_template_content:
                temp_template_path = "temp_template.yaml"
                with open(temp_template_path, "w", encoding="utf-8") as f:
                    f.write(st.session_state.custom_template_content)
                template_path = temp_template_path

            config_generator = ClashConfigGenerator(template_path=template_path)

            # 将解析出的节点静态注入到 proxies 列表
            if st.session_state.all_proxies:
                config_generator.add_proxies(st.session_state.all_proxies)

            # 处理端口映射
            if st.session_state.enable_port_mapping:
                enabled_mappings = {name: mapping["port"] for name, mapping in st.session_state.node_mappings.items() if mapping.get("enabled")}
                if enabled_mappings:
                    config_generator.generate_port_mappings(enabled_mappings)

            config_yaml = config_generator.generate_full_config()
            st.success("🎉 配置生成成功！")
            st.download_button("点击下载配置文件", config_yaml, output_filename, 'text/yaml', use_container_width=True)

            with st.expander("查看生成的配置预览", expanded=False):
                st.code(config_yaml, language='yaml')

    except Exception as e:
        logger.error("Failed to generate config file.", exc_info=True)
        st.error(f"生成配置时出错: {e}")
    finally:
        if temp_template_path and os.path.exists(temp_template_path):
            os.remove(temp_template_path)
            logger.info(f"已清理临时模板文件: {temp_template_path}")

if __name__ == "__main__":
    main()