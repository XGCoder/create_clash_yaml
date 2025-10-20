#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import logging
import os
import sys
import glob
from datetime import datetime, timezone, timedelta
from clash_config_generator.config_generator import ClashConfigGenerator
from clash_config_generator.subscription import SubscriptionManager

# 设置日志格式
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("clash_config_generator_cli")


# ==================== 交互式辅助函数 ====================

def find_template_files():
    """
    自动发现当前目录下的YAML模板文件

    Returns:
        list: 模板文件路径列表
    """
    yaml_files = glob.glob("*.yaml") + glob.glob("*.yml")
    # 过滤掉输出文件和非模板文件
    exclude_patterns = [
        'config_',           # 输出文件
        'docker-compose',    # Docker配置
        'compose',           # Docker Compose配置
    ]
    template_files = [
        f for f in yaml_files
        if not any(f.startswith(pattern) for pattern in exclude_patterns)
    ]
    return template_files


def interactive_select_template():
    """
    交互式选择模板文件

    Returns:
        str: 选中的模板文件路径,如果跳过则返回None
    """
    print("\n" + "="*50)
    print("📄 [步骤 1/3] 选择模板文件")
    print("="*50)

    templates = find_template_files()

    if not templates:
        print("⚠️  当前目录未找到任何YAML模板文件")
        manual_path = input("请手动输入模板路径 (回车跳过): ").strip()
        return manual_path if manual_path else None

    # 优先显示包含'qichiyu'或'default'的模板
    preferred = [t for t in templates if 'qichiyu' in t.lower() or 'default' in t.lower()]
    other = [t for t in templates if t not in preferred]
    sorted_templates = preferred + other

    print("\n可用模板:")
    for i, template in enumerate(sorted_templates, 1):
        size_kb = os.path.getsize(template) / 1024
        marker = " (推荐)" if template in preferred else ""
        print(f"  {i}. {template}{marker} ({size_kb:.1f} KB)")

    print(f"  {len(sorted_templates) + 1}. 手动输入路径 (yaml文件)")
    print(f"  {len(sorted_templates) + 2}. 跳过(不使用模板)")

    while True:
        try:
            choice = input(f"\n请选择 [1-{len(sorted_templates) + 2}]: ").strip()
            if not choice:
                # 默认选择第一个
                return sorted_templates[0] if sorted_templates else None

            choice_num = int(choice)
            if 1 <= choice_num <= len(sorted_templates):
                selected = sorted_templates[choice_num - 1]
                print(f"✅ 已选择: {selected}")
                return selected
            elif choice_num == len(sorted_templates) + 1:
                manual_path = input("请输入模板路径: ").strip()
                if os.path.exists(manual_path):
                    print(f"✅ 已选择: {manual_path}")
                    return manual_path
                else:
                    print(f"❌ 文件不存在: {manual_path}")
                    continue
            elif choice_num == len(sorted_templates) + 2:
                print("⚠️  已跳过模板选择")
                return None
            else:
                print(f"❌ 无效选择,请输入 1-{len(sorted_templates) + 2}")
        except ValueError:
            print("❌ 请输入数字")
        except KeyboardInterrupt:
            print("\n\n❌ 用户取消操作")
            sys.exit(0)


def interactive_input_subscriptions():
    """
    交互式输入订阅链接

    Returns:
        list: 订阅链接列表
    """
    print("\n" + "="*50)
    print("🔗 [步骤 2/3] 添加订阅链接")
    print("="*50)

    print("\n选择输入方式:")
    print("  1. 逐个输入订阅链接 (输入空行结束)")
    print("  2. 从文件读取订阅链接")
    print("  3. 跳过 (仅使用模板中的节点)")

    while True:
        try:
            choice = input("\n请选择 [1-3]: ").strip()

            if choice == '1':
                # 逐个输入
                subscriptions = []
                print("\n请输入订阅链接 (每行一个,输入空行结束):")
                line_num = 1
                while True:
                    try:
                        url = input(f"  订阅 {line_num}: ").strip()
                        if not url:
                            break
                        if url.startswith('http://') or url.startswith('https://'):
                            subscriptions.append(url)
                            line_num += 1
                        else:
                            print("    ⚠️  请输入有效的HTTP/HTTPS链接")
                    except KeyboardInterrupt:
                        print("\n")
                        break

                if subscriptions:
                    print(f"✅ 已添加 {len(subscriptions)} 个订阅链接")
                return subscriptions

            elif choice == '2':
                # 从文件读取
                file_path = input("请输入订阅文件路径: ").strip()
                if not os.path.exists(file_path):
                    print(f"❌ 文件不存在: {file_path}")
                    continue

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        subscriptions = [line.strip() for line in f if line.strip() and line.strip().startswith('http')]

                    if subscriptions:
                        print(f"✅ 从文件读取了 {len(subscriptions)} 个订阅链接")
                        return subscriptions
                    else:
                        print("❌ 文件中未找到有效的订阅链接")
                        continue
                except Exception as e:
                    print(f"❌ 读取文件失败: {e}")
                    continue

            elif choice == '3':
                print("⚠️  已跳过订阅输入")
                return []

            else:
                print("❌ 无效选择,请输入 1-3")

        except KeyboardInterrupt:
            print("\n\n❌ 用户取消操作")
            sys.exit(0)


def interactive_output_filename():
    """
    交互式配置输出文件名

    Returns:
        str: 输出文件名
    """
    print("\n" + "="*50)
    print("💾 [步骤 4/4] 配置输出")
    print("="*50)

    # 使用东八区时间生成默认文件名
    beijing_tz = timezone(timedelta(hours=8))
    beijing_time = datetime.now(beijing_tz)
    default_filename = f"config_{beijing_time.strftime('%Y%m%d_%H%M%S')}.yaml"

    print(f"\n默认文件名: {default_filename}")
    custom = input("使用自定义文件名? [y/N]: ").strip().lower()

    if custom in ['y', 'yes']:
        while True:
            filename = input("请输入文件名: ").strip()
            if not filename:
                print("❌ 文件名不能为空")
                continue
            if not filename.endswith('.yaml') and not filename.endswith('.yml'):
                filename += '.yaml'
            print(f"✅ 输出文件: {filename}")
            return filename
    else:
        print(f"✅ 输出文件: {default_filename}")
        return default_filename


def interactive_port_mapping():
    """
    交互式配置端口映射

    Returns:
        tuple: (是否启用端口映射, 起始端口)
    """
    print("\n" + "="*50)
    print("🔌 [步骤 3/4] 端口映射配置 (可选)")
    print("="*50)

    print("\n端口映射功能说明:")
    print("  为每个节点分配独立的本地端口,便于通过不同端口直接访问特定节点")
    print("  例如: 节点1 -> 42001端口, 节点2 -> 42002端口")

    enable = input("\n是否启用端口映射? [y/N]: ").strip().lower()

    if enable in ['y', 'yes']:
        print("\n请配置起始端口:")
        while True:
            try:
                port_input = input("  起始端口 [默认: 42001]: ").strip()
                if not port_input:
                    start_port = 42001
                else:
                    start_port = int(port_input)

                if start_port < 1025 or start_port > 65000:
                    print("  ❌ 端口范围必须在 1025-65000 之间")
                    continue

                print(f"✅ 端口映射已启用,起始端口: {start_port}")
                return True, start_port
            except ValueError:
                print("  ❌ 请输入有效的数字")
            except KeyboardInterrupt:
                print("\n")
                return False, 42001
    else:
        print("⚠️  端口映射未启用")
        return False, 42001


def print_banner():
    """打印欢迎横幅"""
    banner = """
╔════════════════════════════════════════════════╗
║                                                ║
║       🚀 Clash 配置文件生成器 v0.2.1          ║
║                                                ║
╚════════════════════════════════════════════════╝
"""
    print(banner)


def parse_arguments():
    """
    解析命令行参数

    Returns:
        argparse.Namespace: 解析后的参数
    """
    parser = argparse.ArgumentParser(
        description='Clash 配置生成器 (支持交互式和命令行两种模式)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 交互式模式 (零参数启动)
  python cli.py

  # 命令行模式 (完整参数)
  python cli.py -t template.yaml -s https://sub1.com -s https://sub2.com -o output.yaml

  # 从文件读取订阅链接
  python cli.py -t template.yaml --subs-file subscriptions.txt

  # 混合模式 (部分参数 + 交互式补全)
  python cli.py -t template.yaml
        """
    )

    # 输入选项
    input_group = parser.add_argument_group('输入选项')
    input_group.add_argument('-t', '--template',
                         help='YAML模板文件路径 (例如: qichiyu_config.yaml)')
    input_group.add_argument('-s', '--subscription', action='append', default=[],
                         help='订阅链接 (可多次使用)')
    input_group.add_argument('--subs-file',
                         help='从文件读取订阅链接 (每行一个)')

    # 输出选项
    output_group = parser.add_argument_group('输出选项')
    output_group.add_argument('-o', '--output',
                          help='输出文件路径 (默认: config_<时间戳>.yaml)')

    # 模式选项
    mode_group = parser.add_argument_group('模式选项')
    mode_group.add_argument('-i', '--interactive', action='store_true',
                        help='强制进入交互式模式 (即使提供了参数)')
    mode_group.add_argument('--non-interactive', action='store_true',
                        help='强制非交互模式 (缺少参数时报错退出)')

    # 其他选项
    other_group = parser.add_argument_group('其他选项')
    other_group.add_argument('-d', '--debug', action='store_true', help='启用调试日志')

    return parser.parse_args()


def main():
    """
    主函数，智能处理交互式和命令行两种模式
    """
    args = parse_arguments()

    # 设置日志级别
    if args.debug:
        logger.setLevel(logging.DEBUG)

    # ==================== 模式检测 ====================
    # 判断是否需要进入交互式模式
    is_interactive = args.interactive or (
        not args.template and
        not args.subscription and
        not args.subs_file and
        not args.non_interactive
    )

    if is_interactive:
        # 交互式模式
        print_banner()
        template_path = args.template or interactive_select_template()
        subscriptions = args.subscription.copy() if args.subscription else []

        # 如果命令行没有提供订阅,则进入交互式订阅输入
        if not subscriptions and not args.subs_file:
            subscriptions = interactive_input_subscriptions()

        # 端口映射配置
        enable_port_mapping, start_port = interactive_port_mapping()

        output_path = args.output or interactive_output_filename()
    else:
        # 命令行模式
        template_path = args.template
        subscriptions = args.subscription.copy() if args.subscription else []

        # 命令行模式下默认不启用端口映射
        enable_port_mapping = False
        start_port = 42001

        # 生成默认输出文件名(如果未提供)
        if not args.output:
            beijing_tz = timezone(timedelta(hours=8))
            beijing_time = datetime.now(beijing_tz)
            output_path = f"config_{beijing_time.strftime('%Y%m%d_%H%M%S')}.yaml"
        else:
            output_path = args.output

        # 非交互模式下检查必要参数
        if args.non_interactive and not template_path:
            logger.error("非交互模式下必须提供 -t/--template 参数")
            sys.exit(1)

    # ==================== 处理订阅文件 ====================
    if args.subs_file:
        if not os.path.exists(args.subs_file):
            logger.error(f"订阅文件未找到: {args.subs_file}")
            sys.exit(1)

        try:
            with open(args.subs_file, 'r', encoding='utf-8') as f:
                file_subs = [line.strip() for line in f if line.strip() and line.strip().startswith('http')]
            subscriptions.extend(file_subs)
            logger.info(f"从文件 '{args.subs_file}' 读取了 {len(file_subs)} 个订阅链接")
        except Exception as e:
            logger.error(f"读取订阅文件失败: {e}")
            sys.exit(1)

    # ==================== 验证模板文件 ====================
    if template_path and not os.path.exists(template_path):
        logger.error(f"模板文件未找到: {template_path}")
        sys.exit(1)

    # ==================== 开始生成配置 ====================
    try:
        print("\n" + "="*50)
        print("⚙️  正在生成配置...")
        print("="*50)

        # 1. 初始化配置生成器
        if template_path:
            logger.info(f"使用模板 '{template_path}' 初始化...")
            config_generator = ClashConfigGenerator(template_path=template_path)
        else:
            logger.warning("未提供模板文件,将生成基础配置")
            # 这里可以创建一个最小化的默认配置
            logger.error("当前版本必须提供模板文件")
            sys.exit(1)

        # 2. 获取并添加订阅节点
        if subscriptions:
            logger.info(f"找到了 {len(subscriptions)} 个订阅链接，正在获取节点...")
            sub_manager = SubscriptionManager()
            all_proxies = []

            for i, url in enumerate(subscriptions, 1):
                print(f"\n[{i}/{len(subscriptions)}] 正在获取订阅: {url[:50]}...")
                proxies = sub_manager.fetch_and_parse(url)
                if proxies:
                    all_proxies.extend(proxies)
                    print(f"  ✅ 成功获取 {len(proxies)} 个节点")
                else:
                    print(f"  ⚠️  未能获取节点")

            if all_proxies:
                logger.info(f"总共获取 {len(all_proxies)} 个节点，正在添加到配置中...")
                config_generator.add_proxies(all_proxies)

                # 处理端口映射(仅在交互式模式且启用了端口映射)
                if is_interactive and enable_port_mapping:
                    logger.info(f"启用端口映射,起始端口: {start_port}")
                    # 为所有节点生成端口映射
                    node_port_mappings = {}
                    for i, proxy in enumerate(all_proxies):
                        node_port_mappings[proxy['name']] = start_port + i
                    config_generator.generate_port_mappings(node_port_mappings)
                    print(f"\n✅ 已为 {len(all_proxies)} 个节点生成端口映射 (端口范围: {start_port}-{start_port + len(all_proxies) - 1})")
            else:
                logger.warning("未能从订阅链接获取任何节点")
        else:
            logger.info("未提供订阅链接，将仅使用模板中的静态节点。")

        # 3. 保存最终配置
        logger.info(f"正在生成并保存配置到 '{output_path}'...")
        success = config_generator.save_config(output_path)

        if success:
            # 输出统计信息
            print("\n" + "="*50)
            print("🎉 配置生成成功!")
            print("="*50)
            print(f"✓ 模板: {template_path or '(无)'}")
            if subscriptions:
                print(f"✓ 订阅链接: {len(subscriptions)} 个")
                print(f"✓ 总计节点: {len(config_generator.config.get('proxies', []))} 个")
            print(f"✓ 输出文件: {os.path.abspath(output_path)}")
            print("="*50 + "\n")
        else:
            logger.error("生成配置文件时遇到错误。")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n❌ 用户取消操作")
        sys.exit(0)
    except Exception as e:
        logger.error(f"发生未知错误: {e}", exc_info=args.debug)
        sys.exit(1)



if __name__ == "__main__":
    main()