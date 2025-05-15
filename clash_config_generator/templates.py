import os
import yaml
import logging
from .utils import safe_load_yaml, safe_dump_yaml

logger = logging.getLogger(__name__)

DEFAULT_PROXY_GROUPS = [
    {
        "name": "🚀 节点选择",
        "type": "select",
        "proxies": ["♻️ 自动选择", "DIRECT"]
    },
    {
        "name": "♻️ 自动选择",
        "type": "url-test",
        "url": "http://www.gstatic.com/generate_204",
        "interval": 300,
        "tolerance": 50,
        "proxies": []
    },
    {
        "name": "🌍 国外媒体",
        "type": "select",
        "proxies": ["🚀 节点选择", "♻️ 自动选择", "🎯 全球直连"]
    },
    {
        "name": "📲 电报信息",
        "type": "select",
        "proxies": ["🚀 节点选择", "🎯 全球直连"]
    },
    {
        "name": "Ⓜ️ 微软服务",
        "type": "select",
        "proxies": ["🚀 节点选择", "🎯 全球直连"]
    },
    {
        "name": "🍎 苹果服务",
        "type": "select",
        "proxies": ["🚀 节点选择", "🎯 全球直连"]
    },
    {
        "name": "📢 谷歌FCM",
        "type": "select",
        "proxies": ["🚀 节点选择", "🎯 全球直连", "♻️ 自动选择"]
    },
    {
        "name": "🎯 全球直连",
        "type": "select",
        "proxies": ["DIRECT", "🚀 节点选择", "♻️ 自动选择"]
    },
    {
        "name": "🛑 全球拦截",
        "type": "select",
        "proxies": ["REJECT", "DIRECT"]
    },
    {
        "name": "🍃 应用净化",
        "type": "select",
        "proxies": ["REJECT", "DIRECT"]
    },
    {
        "name": "😈 端口分流匹配",
        "type": "select",
        "proxies": ["🎯 全球直连", "🚀 节点选择"]
    }
]

# 基本规则，当无法加载默认规则文件时使用
BASIC_RULES = [
    "DOMAIN-SUFFIX,local,🎯 全球直连",
    "DOMAIN-SUFFIX,cn,🎯 全球直连",
    "IP-CIDR,127.0.0.0/8,🎯 全球直连,no-resolve",
    "IP-CIDR,192.168.0.0/16,🎯 全球直连,no-resolve",
    "GEOIP,CN,🎯 全球直连",
    "MATCH,🚀 节点选择"
]

def get_default_rules():
    """
    获取默认规则
    优先从预设规则文件加载，若无法加载则使用基本规则
    
    Returns:
        list: 规则列表
    """
    # 尝试加载默认规则文件
    default_rule_path = os.path.join(os.path.dirname(__file__), "default_rules.yaml")
    try:
        if os.path.exists(default_rule_path):
            logger.info(f"加载默认规则文件: {default_rule_path}")
            with open(default_rule_path, 'r', encoding='utf-8') as f:
                content = f.read()
                yaml_data = safe_load_yaml(content)
                if yaml_data and 'rules' in yaml_data and isinstance(yaml_data['rules'], list):
                    return yaml_data['rules']
    except Exception as e:
        logger.error(f"加载默认规则文件失败: {e}")
    
    # 如果无法加载，返回基本规则
    logger.warning("使用基本规则")
    return BASIC_RULES

def load_template_from_file(file_path):
    """
    从指定的YAML文件中加载代理组和规则模板
    """
    try:
        if not os.path.exists(file_path):
            logger.warning(f"模板文件 {file_path} 不存在，使用默认模板")
            return DEFAULT_PROXY_GROUPS, get_default_rules()
            
        with open(file_path, 'r', encoding='utf-8') as f:
            template_data = safe_load_yaml(f.read())
            
        if not template_data:
            logger.error(f"从 {file_path} 加载模板失败，使用默认模板")
            return DEFAULT_PROXY_GROUPS, get_default_rules()
            
        proxy_groups = template_data.get('proxy-groups', [])
        rules = template_data.get('rules', [])
        
        if not proxy_groups or not rules:
            logger.warning(f"{file_path} 中缺少proxy-groups或rules，使用默认模板")
            return DEFAULT_PROXY_GROUPS, get_default_rules()
            
        logger.info(f"成功从 {file_path} 加载模板: {len(proxy_groups)} 个代理组, {len(rules)} 条规则")
        return proxy_groups, rules
    except Exception as e:
        logger.error(f"从 {file_path} 加载模板时出错: {e}")
        return DEFAULT_PROXY_GROUPS, get_default_rules()

def get_proxy_groups_and_rules(template_path=None):
    """
    获取代理组和规则，优先使用模板文件，如果无法加载则使用默认模板
    """
    if template_path and os.path.exists(template_path):
        proxy_groups, rules = load_template_from_file(template_path)
    else:
        proxy_groups = DEFAULT_PROXY_GROUPS
        rules = get_default_rules()
        
    return proxy_groups, rules 