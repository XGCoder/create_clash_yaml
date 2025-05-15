"""
Clash Config Generator

一个用于生成 Clash Verge 配置文件的工具，支持多订阅源和直连节点的合并。
"""

__version__ = '0.1.0'
__author__ = 'ClashConfigGenerator'

from .config_generator import ClashConfigGenerator
from .node_parser import parse_proxy
from .subscription import SubscriptionManager
from .utils import safe_load_yaml, safe_dump_yaml, decode_base64, parse_uri, load_local_file

__all__ = [
    'ClashConfigGenerator',
    'SubscriptionManager',
    'parse_proxy',
    'safe_load_yaml',
    'safe_dump_yaml',
    'decode_base64',
    'parse_uri',
    'load_local_file'
]
