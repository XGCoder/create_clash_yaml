#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import logging
import os
import sys
from pathlib import Path
from datetime import datetime
from clash_config_generator.subscription import SubscriptionManager
from clash_config_generator.node_parser import NodeParser, parse_proxy
from clash_config_generator.config_generator import ClashConfigGenerator
from clash_config_generator.utils import load_local_file

# 设置日志格式
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("clash_config_generator")


def parse_arguments():
    """
    解析命令行参数
    
    Returns:
        argparse.Namespace: 解析后的参数
    """
    parser = argparse.ArgumentParser(description='Clash 配置生成器')
    
    # 输入选项
    input_group = parser.add_argument_group('输入选项')
    input_group.add_argument('-s', '--subscription', action='append', default=[], 
                         help='订阅链接 (可多次使用)')
    input_group.add_argument('-n', '--node', action='append', default=[],
                         help='直接节点链接 (vmess://, ss://, trojan://等) (可多次使用)')
    input_group.add_argument('-f', '--file', help='包含节点链接的文本文件路径')
    
    # 配置选项
    config_group = parser.add_argument_group('配置选项')
    config_group.add_argument('-p', '--port', type=int, default=7890, help='HTTP端口 (默认: 7890)')
    config_group.add_argument('--socks-port', type=int, default=7891, help='SOCKS端口 (默认: 7891)')
    config_group.add_argument('-m', '--mixed-port', type=int, default=7892, help='混合端口 (默认: 7892)')
    config_group.add_argument('--redir-port', type=int, default=7893, help='重定向端口 (默认: 7893)')
    config_group.add_argument('--tproxy-port', type=int, default=7895, help='透明代理端口 (默认: 7895)')
    config_group.add_argument('--allow-lan', action='store_true', help='允许局域网连接')
    config_group.add_argument('--mode', choices=['Rule', 'Global', 'Direct'], default='Rule', help='代理模式 (默认: Rule)')
    config_group.add_argument('--log-level', choices=['info', 'warning', 'error', 'debug', 'silent'], default='info', help='日志级别 (默认: info)')
    config_group.add_argument('--name', default='Clash', help='配置名称 (默认: Clash)')
    config_group.add_argument('-t', '--template', help='规则模板文件路径')
    
    # 端口映射选项
    mapping_group = parser.add_argument_group('端口映射选项')
    mapping_group.add_argument('--start-port', type=int, default=42000, help='端口映射起始端口 (默认: 42000)')
    mapping_group.add_argument('--mapping', action='store_true', help='启用端口映射')
    mapping_group.add_argument('--listener-type', choices=['mixed', 'socks', 'http'], default='mixed', 
                         help='监听器类型 (默认: mixed)')
    
    # 输出选项
    output_group = parser.add_argument_group('输出选项')
    output_group.add_argument('-o', '--output', default='config.yaml', help='输出文件路径 (默认: config.yaml)')
    output_group.add_argument('-d', '--debug', action='store_true', help='启用调试日志')
    
    return parser.parse_args()


def read_nodes_from_file(file_path):
    """
    从文件读取节点列表
    
    Args:
        file_path (str): 文件路径
        
    Returns:
        list: 节点字符串列表
    """
    nodes = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    nodes.append(line)
        logger.info(f"从文件 {file_path} 读取了 {len(nodes)} 个节点")
    except Exception as e:
        logger.error(f"读取文件 {file_path} 失败: {str(e)}")
    
    return nodes


def main():
    """
    主函数，处理命令行逻辑
    """
    args = parse_arguments()
    
    # 设置日志级别
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 创建配置生成器
    config_generator = ClashConfigGenerator()
    
    # 更新基本配置
    config_generator.update_basic_config(
        port=args.port,
        socks_port=args.socks_port,
        mixed_port=args.mixed_port,
        redir_port=args.redir_port,
        tproxy_port=args.tproxy_port,
        allow_lan=args.allow_lan,
        mode=args.mode,
        log_level=args.log_level
    )
    
    # 更新配置名称
    config_generator.update_config_name(args.name)
    
    # 加载模板
    if args.template:
        if os.path.exists(args.template):
            template_content = load_local_file(args.template)
            if template_content:
                config_generator.update_from_template(template_content)
                logger.info(f"已加载模板: {args.template}")
        else:
            logger.warning(f"模板文件不存在: {args.template}")
    else:
        # 使用默认规则
        config_generator.include_default_rules()
        logger.info("已使用默认规则")
    
    # 收集代理节点
    all_proxies = []
    enabled_proxies = []
    
    # 处理订阅链接
    if args.subscription:
        subscription_manager = SubscriptionManager()
        for url in args.subscription:
            try:
                logger.info(f"正在处理订阅: {url}")
                subscription_proxies = subscription_manager.fetch_and_parse(url)
                if subscription_proxies:
                    all_proxies.extend(subscription_proxies)
                    enabled_proxies.extend(subscription_proxies)
                    logger.info(f"成功从 {url} 解析 {len(subscription_proxies)} 个节点")
                else:
                    logger.warning(f"无法从 {url} 解析节点")
            except Exception as e:
                logger.error(f"处理订阅 {url} 时出错: {str(e)}")
    
    # 处理直接节点
    if args.node:
        for node_uri in args.node:
            try:
                proxy = parse_proxy(node_uri)
                if proxy:
                    all_proxies.append(proxy)
                    enabled_proxies.append(proxy)
                    logger.info(f"成功解析节点: {proxy.get('name', 'Unknown')}")
                else:
                    logger.warning(f"无法解析节点: {node_uri[:30]}...")
            except Exception as e:
                logger.error(f"解析节点 {node_uri[:30]}... 时出错: {str(e)}")
    
    # 处理文件
    if args.file:
        if os.path.exists(args.file):
            try:
                with open(args.file, 'r', encoding='utf-8') as f:
                    file_content = f.read()
                
                file_lines = [line.strip() for line in file_content.split('\n') if line.strip()]
                file_success = 0
                
                for line in file_lines:
                    try:
                        proxy = parse_proxy(line)
                        if proxy:
                            all_proxies.append(proxy)
                            enabled_proxies.append(proxy)
                            file_success += 1
                        else:
                            logger.warning(f"无法解析节点: {line[:30]}...")
                    except Exception as e:
                        logger.error(f"解析节点 {line[:30]}... 时出错: {str(e)}")
                
                logger.info(f"从文件中成功解析 {file_success} 个节点")
            except Exception as e:
                logger.error(f"读取文件 {args.file} 时出错: {str(e)}")
        else:
            logger.error(f"文件不存在: {args.file}")
    
    # 检查是否找到节点
    if not all_proxies:
        logger.error("未找到任何有效节点，无法生成配置")
        sys.exit(1)
    
    # 更新代理
    config_generator.update_proxies(all_proxies)
    config_generator.update_enabled_proxies(enabled_proxies)
    
    # 处理端口映射
    if args.mapping:
        node_mappings = {}
        start_port = args.start_port
        
        for i, proxy in enumerate(enabled_proxies):
            node_mappings[proxy.get('name')] = start_port + i
        
        config_generator.generate_port_mappings(node_mappings, listener_type=args.listener_type)
        logger.info(f"已为 {len(node_mappings)} 个节点配置端口映射，起始端口: {start_port}, 类型: {args.listener_type}")
    
    # 生成配置
    config_yaml = config_generator.generate_full_config()
    
    # 确保输出目录存在
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 写入文件
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(config_yaml)
    
    logger.info(f"配置已成功生成并保存到: {args.output}")
    
    # 输出统计信息
    print(f"\n生成统计信息:")
    print(f"- 总节点数: {len(all_proxies)}")
    print(f"- 已启用节点: {len(enabled_proxies)}")
    if args.mapping:
        print(f"- 端口映射: 已启用, 共 {len(node_mappings)} 个")
    print(f"- 输出文件: {args.output}")


if __name__ == "__main__":
    main()
