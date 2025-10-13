#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import logging
import os
import sys
from clash_config_generator.config_generator import ClashConfigGenerator
from clash_config_generator.subscription import SubscriptionManager

# 设置日志格式
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("clash_config_generator_cli")


def parse_arguments():
    """
    解析命令行参数
    
    Returns:
        argparse.Namespace: 解析后的参数
    """
    parser = argparse.ArgumentParser(description='Clash 配置生成器 (基于模板)')
    
    # 输入选项
    input_group = parser.add_argument_group('输入选项')
    input_group.add_argument('-t', '--template', required=True,
                         help='YAML模板文件路径 (例如: qishiyu_config.yaml)')
    input_group.add_argument('-s', '--subscription', action='append', default=[], 
                         help='订阅链接 (可多次使用，将覆盖模板中的 proxy-providers)')
    
    # 输出选项
    output_group = parser.add_argument_group('输出选项')
    output_group.add_argument('-o', '--output', default='config.yaml', 
                          help='输出文件路径 (默认: config.yaml)')
    
    # 其他选项
    other_group = parser.add_argument_group('其他选项')
    other_group.add_argument('-d', '--debug', action='store_true', help='启用调试日志')
    
    return parser.parse_args()


def main():
    """
    主函数，处理命令行逻辑
    """
    args = parse_arguments()
    
    # 设置日志级别
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    # 检查模板文件是否存在
    if not os.path.exists(args.template):
        logger.error(f"模板文件未找到: {args.template}")
        sys.exit(1)
        
    try:
        # 1. 使用模板初始化配置生成器
        logger.info(f"使用模板 '{args.template}' 初始化...")
        config_generator = ClashConfigGenerator(template_path=args.template)
        
        # 2. 如果提供了订阅链接，则获取并添加节点
        if args.subscription:
            logger.info(f"找到了 {len(args.subscription)} 个订阅链接，正在获取节点...")
            sub_manager = SubscriptionManager()
            all_proxies = []
            for url in args.subscription:
                proxies = sub_manager.fetch_and_parse(url)
                if proxies:
                    all_proxies.extend(proxies)
                    logger.info(f"从 {url} 成功获取 {len(proxies)} 个节点。")
                else:
                    logger.warning(f"未能从 {url} 获取任何节点。")
            
            if all_proxies:
                logger.info(f"总共获取 {len(all_proxies)} 个节点，正在添加到配置中...")
                config_generator.add_proxies(all_proxies)
        else:
            logger.info("未提供订阅链接，将仅使用模板中的静态节点。")

        # 3. 保存最终配置
        logger.info(f"正在生成并保存配置到 '{args.output}'...")
        success = config_generator.save_config(args.output)
        
        if success:
            logger.info("配置已成功生成！")
            # 输出统计信息
            print("\n--- 生成摘要 ---")
            print(f"✓ 模板: {args.template}")
            if args.subscription:
                print(f"✓ 订阅链接: {len(args.subscription)} 个已处理")
                print(f"✓ 总计节点: {len(config_generator.config.get('proxies', []))} 个")
            print(f"✓ 输出文件: {os.path.abspath(args.output)}")
            print("--------------------")
        else:
            logger.error("生成配置文件时遇到错误。")
            sys.exit(1)

    except Exception as e:
        logger.error(f"发生未知错误: {e}", exc_info=args.debug)
        sys.exit(1)



if __name__ == "__main__":
    main()