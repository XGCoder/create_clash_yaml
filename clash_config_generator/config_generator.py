import logging
import os
import copy
import yaml
from . import utils
from .templates import get_proxy_groups_and_rules, load_template_from_file, get_default_rules
from .utils import safe_dump_yaml
from datetime import datetime

logger = logging.getLogger(__name__)

class ClashConfigGenerator:
    """Clash配置生成器"""
    
    def __init__(self, port=7890, mixed_port=7891, default_port=None, start_mapping_port=None, template_path=None):
        """
        初始化配置生成器，设置默认端口
        
        Args:
            port (int): HTTP代理端口
            mixed_port (int): HTTP/SOCKS5混合代理端口
            default_port (int, optional): 默认节点专用端口
            start_mapping_port (int, optional): 节点映射起始端口
            template_path (str, optional): 模板文件路径
        """
        self.port = port
        self.mixed_port = mixed_port
        self.default_port = default_port  # 默认节点专用端口
        self.start_mapping_port = start_mapping_port  # 节点映射起始端口
        self.default_node_name = None  # 默认节点名称
        self.template_path = template_path  # 模板文件路径
        self.config = {}
        self.proxies = []
        self.custom_port_mappings = {}  # 自定义端口映射配置
        self.enabled_proxies = []
        self.port_mappings = {}
        self.port_rules = []  # 存储端口分流规则
        
        # 从模板加载代理组和规则
        self.template_proxy_groups, self.template_rules = get_proxy_groups_and_rules(template_path)
    
    def set_ports(self, port, mixed_port, default_port=None, start_mapping_port=None):
        """
        设置端口
        
        Args:
            port (int): HTTP代理端口
            mixed_port (int): HTTP/SOCKS5混合代理端口
            default_port (int, optional): 默认节点专用端口
            start_mapping_port (int, optional): 节点映射起始端口
        """
        self.port = port
        self.mixed_port = mixed_port
        if default_port:
            self.default_port = default_port
        if start_mapping_port:
            self.start_mapping_port = start_mapping_port
    
    def set_template_path(self, template_path):
        """
        设置模板文件路径
        
        Args:
            template_path (str): 模板文件路径
        """
        self.template_path = template_path
        # 更新模板
        self.template_proxy_groups, self.template_rules = get_proxy_groups_and_rules(template_path)
        logger.info(f"更新模板文件路径: {template_path}")
        
    def set_default_node(self, node_name):
        """
        设置默认节点
        
        Args:
            node_name (str): 节点名称
        """
        self.default_node_name = node_name
        logger.info(f"设置默认节点: {node_name}")
    
    def set_port_mappings(self, port_mappings):
        """
        设置自定义端口映射配置
        
        Args:
            port_mappings (dict): 节点名称到映射配置的字典，格式为:
                {
                    "节点名称1": {"enabled": True, "port": 端口号},
                    "节点名称2": {"enabled": False, "port": 端口号},
                    ...
                }
                
        Returns:
            int: 设置的有效映射数量
        """
        # 过滤只保留启用的映射
        enabled_mappings = {name: mapping for name, mapping in port_mappings.items() if mapping.get("enabled", False)}
        
        self.custom_port_mappings = enabled_mappings
        logger.info(f"设置了 {len(enabled_mappings)} 个自定义端口映射")
        return len(enabled_mappings)
    
    def generate_base_config(self):
        """
        生成基础配置部分
        
        Returns:
            dict: 基础配置字典
        """
        base_config = {
            'port': self.port,
            'socks-port': self.mixed_port,
            'allow-lan': True,
            'mode': 'Rule',
            'log-level': 'info',
            'external-controller': ':9090',
            'dns': {
                'enable': True,
                'listen': '0.0.0.0:53',
                'ipv6': True,
                'enhanced-mode': 'fake-ip',
                'nameserver': [
                    '114.114.114.114',
                    '8.8.8.8',
                    '223.5.5.5'
                ]
            }
        }
        
        self.config.update(base_config)
        return base_config
    
    def add_proxies(self, new_proxies):
        """
        添加代理节点
        
        Args:
            proxies (list): 代理节点列表
            
        Returns:
            int: 添加的有效节点数量
        """
        if not new_proxies:
            return 0
            
        added_count = 0
        for proxy in new_proxies:
            # 验证节点格式
            if not self._is_valid_proxy(proxy):
                logger.warning(f"跳过无效节点: {proxy.get('name', '未命名')}")
                continue
                
            # 添加到列表
            self.proxies.append(proxy)
            added_count += 1
            
        logger.info(f"添加了 {added_count} 个有效节点")
        return added_count
    
    def generate_proxy_groups(self, proxy_names=None):
        """
        生成代理组配置，使用模板中的代理组结构
        
        Args:
            proxy_names (list, optional): 代理节点名称列表，默认使用全部节点
            
        Returns:
            list: 代理组配置列表
        """
        if proxy_names is None:
            proxy_names = [proxy['name'] for proxy in self.proxies]
            
        if not proxy_names:
            logger.warning("没有可用的代理节点，无法创建代理组")
            return []
        
        # 复制模板代理组
        proxy_groups = []
        for group in self.template_proxy_groups:
            group_copy = group.copy()
            
            # 对于类型为select或url-test的组，向代理列表添加所有节点
            if group_copy['type'] in ['select', 'url-test'] and group_copy['name'] in ['🚀 节点选择', '♻️ 自动选择']:
                # 对于自动选择组，只添加节点列表
                if group_copy['name'] == '♻️ 自动选择':
                    group_copy['proxies'] = proxy_names.copy()
                # 对于节点选择组，保留原有选项并添加所有节点
                elif group_copy['name'] == '🚀 节点选择':
                    original_options = group_copy.get('proxies', [])
                    group_copy['proxies'] = original_options + proxy_names if original_options else proxy_names
            
            proxy_groups.append(group_copy)
        
        self.config['proxy-groups'] = proxy_groups
        return proxy_groups
    
    def generate_port_mappings(self, node_port_mappings, listener_type="mixed"):
        """
        生成端口映射配置和对应的端口分流规则
        
        :param node_port_mappings: 节点名到端口的映射, 例如 {"节点1": 42001, "节点2": 42002}
                                  每个节点将创建一个对应类型的监听器
        :param listener_type: 监听器类型，可选值为"mixed"(HTTP+SOCKS5), "http", "socks"
                            默认为"mixed"同时支持HTTP和SOCKS5协议
        """
        self.port_mappings = node_port_mappings
        self.listener_type = listener_type
        
        # 生成端口分流规则
        self.port_rules = []
        for proxy_name, port in node_port_mappings.items():
            # 使用DST-PORT规则，将目标端口为映射端口的流量直接使用对应节点
            port_rule = f"DST-PORT,{port},{proxy_name}"
            self.port_rules.append(port_rule)
        
        logger.info(f"端口映射已更新，共 {len(node_port_mappings)} 个映射")
        logger.info(f"已生成 {len(self.port_rules)} 条端口分流规则")
        logger.info(f"使用 {listener_type} 类型的监听器")
        
    def generate_rules(self):
        """
        生成规则，使用模板中的规则列表
        
        Returns:
            list: 规则列表
        """
        # 使用模板规则
        rules = self.template_rules
        
        self.config['rules'] = rules
        return rules
    
    def generate_full_config(self, additional_proxies=None):
        """
        生成完整配置
        
        Args:
            additional_proxies (list, optional): 额外的代理节点列表
            
        Returns:
            str: YAML格式的配置字符串
        """
        # 先更新配置基础部分
        if not self.config or 'port' not in self.config:
            self.generate_base_config()
            
        # 添加额外的代理节点
        if additional_proxies:
            self.add_proxies(additional_proxies)
        
        # 确保配置中有代理组
        if 'proxy-groups' not in self.config:
            proxy_names = [proxy['name'] for proxy in self.proxies]
            self.generate_proxy_groups(proxy_names)
            
        # 确保配置中有规则
        if 'rules' not in self.config:
            self.generate_rules()
        
        # 深拷贝配置，避免修改原始配置
        config = copy.deepcopy(self.config)
        
        # 添加代理
        config["proxies"] = [proxy for proxy in self.enabled_proxies]
        
        # 添加端口映射（使用listeners配置）
        if self.port_mappings:
            listeners = []
            listener_type = getattr(self, 'listener_type', 'mixed')  # 默认为mixed类型
            
            counter = 0  # 用于生成简洁的名称
            for proxy_name, port in self.port_mappings.items():
                # 为每个节点创建对应类型的监听器
                # 使用更简洁的名称格式
                listener = {
                    "name": f"mixed{counter}" if listener_type == "mixed" else
                           f"http{counter}" if listener_type == "http" else
                           f"socks{counter}",
                    "type": listener_type,
                    "port": port,
                    "proxy": proxy_name
                }
                listeners.append(listener)
                counter += 1
            
            # 添加listeners配置
            config["listeners"] = listeners
            logger.info(f"已添加 {len(self.port_mappings)} 个端口映射（{len(listeners)}个{listener_type}类型监听器）")
        
        # 确保端口分流规则位于规则列表开头
        if self.port_rules:
            # 确保规则存在
            if "rules" not in config:
                config["rules"] = []
            
            # 移除可能重复的端口规则
            non_port_rules = [rule for rule in config["rules"] 
                             if not rule.startswith("DST-PORT,")]
            
            # 重新组合规则，确保端口规则在前
            config["rules"] = self.port_rules + non_port_rules
            logger.info(f"已添加 {len(self.port_rules)} 条端口分流规则")
        
        # 添加元信息
        config['meta'] = {
            'created': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'generator': 'Clash Config Generator'
        }
        
        # 生成YAML
        yaml_str = safe_dump_yaml(config)
        return yaml_str
    
    def save_config(self, file_path='config.yaml'):
        """
        保存配置到文件
        
        Args:
            file_path (str): 输出文件路径
            
        Returns:
            bool: 保存是否成功
        """
        # 确保配置已生成
        if not self.config:
            logger.warning("配置未生成，请先调用generate_full_config()")
            return False
            
        # 确保目录存在
        dir_path = os.path.dirname(file_path)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path)
            
        # 保存配置
        return utils.safe_dump_yaml(self.config, file_path)
    
    def _is_valid_proxy(self, proxy):
        """
        验证代理节点格式是否有效
        
        Args:
            proxy (dict): 代理节点配置
            
        Returns:
            bool: 是否有效
        """
        # 检查基本格式
        if not isinstance(proxy, dict):
            return False
            
        # 检查必要字段
        required_fields = ['name', 'type', 'server', 'port']
        if not all(field in proxy for field in required_fields):
            return False
            
        # 根据类型检查特定字段
        proxy_type = proxy['type']
        if proxy_type == 'vmess':
            return 'uuid' in proxy
        elif proxy_type == 'ss':
            return 'cipher' in proxy and 'password' in proxy
        elif proxy_type == 'trojan':
            return 'password' in proxy
        elif proxy_type == 'hysteria':
            return 'auth_str' in proxy
        
        # 对于其他未知类型，只检查基本字段
        return True

    def update_basic_config(self, port=7890, socks_port=7891, mixed_port=7892, 
                           redir_port=7893, tproxy_port=7895, allow_lan=True, 
                           mode="Rule", log_level="info", external_controller="127.0.0.1:9090",
                           external_ui="ui", ipv6=False):
        """
        更新基本配置参数
        """
        self.config["port"] = port
        self.config["socks-port"] = socks_port
        self.config["mixed-port"] = mixed_port
        self.config["redir-port"] = redir_port
        self.config["tproxy-port"] = tproxy_port
        self.config["allow-lan"] = allow_lan
        self.config["mode"] = mode
        self.config["log-level"] = log_level
        self.config["external-controller"] = external_controller
        self.config["ipv6"] = ipv6
        
        if external_ui:
            self.config["external-ui"] = external_ui
            
        logger.info("基本配置已更新")

    def update_config_name(self, name):
        """
        更新配置名称
        
        :param name: 配置名称
        """
        self.config["name"] = name
        logger.info(f"配置名称已更新为: {name}")

    def update_proxies(self, proxies):
        """
        更新代理列表
        
        :param proxies: 代理列表
        """
        self.proxies = proxies
        logger.info(f"代理列表已更新，共 {len(proxies)} 个代理")

    def update_enabled_proxies(self, proxies):
        """
        更新已启用的代理列表
        
        :param proxies: 已启用的代理列表
        """
        self.enabled_proxies = proxies
        
        # 确保配置中存在proxy-groups
        if "proxy-groups" not in self.config:
            # 先生成代理组
            proxy_names = [proxy.get("name") for proxy in proxies]
            self.generate_proxy_groups(proxy_names)
            logger.info("生成代理组，共 %d 个", len(self.config.get("proxy-groups", [])))
        
        # 更新自动选择组的代理
        for group in self.config["proxy-groups"]:
            if group["name"] == "♻️ 自动选择":
                group["proxies"] = [proxy.get("name") for proxy in proxies]
            
            # 更新节点选择组，添加所有启用的节点
            if group["name"] == "🚀 节点选择":
                group["proxies"] = ["♻️ 自动选择", "DIRECT"] + [proxy.get("name") for proxy in proxies]
        
        logger.info(f"已启用代理列表已更新，共 {len(proxies)} 个代理")

    def update_from_template(self, template_content):
        """
        从模板内容更新配置
        
        :param template_content: 模板内容
        """
        try:
            if isinstance(template_content, str):
                template = yaml.safe_load(template_content)
            else:
                template = template_content
                
            if template:
                # 保存当前的端口分流规则（如果有的话）
                current_port_rules = self.port_rules.copy() if self.port_rules else []
                
                # 仅更新规则和代理组，保留其他配置
                if "rules" in template:
                    # 更新规则但保留端口分流规则
                    self.config["rules"] = template["rules"]
                    
                if "proxy-groups" in template:
                    self.config["proxy-groups"] = template["proxy-groups"]
                    
                # 如果有端口分流规则，确保它们保留在rules列表的开头
                if current_port_rules:
                    # 确保config中有rules
                    if "rules" not in self.config:
                        self.config["rules"] = []
                        
                    # 确保self.port_rules与保存的规则保持一致
                    self.port_rules = current_port_rules
                    
                    # 将端口规则放置在规则列表的开头
                    if "rules" in self.config:
                        # 移除可能重复的端口规则
                        non_port_rules = [rule for rule in self.config["rules"] 
                                          if not rule.startswith("DST-PORT,")]
                        # 重新组合规则，确保端口规则在前
                        self.config["rules"] = current_port_rules + non_port_rules
                        logger.info(f"保留 {len(current_port_rules)} 条端口分流规则")
                
                logger.info("配置已从模板更新")
            else:
                logger.warning("模板内容为空，未更新配置")
        except Exception as e:
            logger.error(f"从模板更新配置失败: {str(e)}")

    def include_default_rules(self):
        """
        包含默认规则
        """
        # 保存当前的端口分流规则（如果有的话）
        current_port_rules = self.port_rules.copy() if self.port_rules else []
        
        # 获取默认规则
        default_rules = get_default_rules()
        
        # 确保不重复端口规则
        non_port_default_rules = [rule for rule in default_rules 
                                 if not rule.startswith("DST-PORT,")]
        
        # 更新规则，确保端口规则在前
        self.config["rules"] = current_port_rules + non_port_default_rules
        
        # 确保self.port_rules与保存的规则保持一致
        self.port_rules = current_port_rules
        
        logger.info(f"已包含默认规则，并保留 {len(current_port_rules)} 条端口分流规则")
