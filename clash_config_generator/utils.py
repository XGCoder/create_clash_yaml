import base64
import re
import yaml
import logging
import os
from urllib.parse import urlparse, parse_qs, unquote
import json
from collections import OrderedDict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProxiesFlowStyleDumper(yaml.Dumper):
    """自定义YAML Dumper，使代理节点以单行格式输出"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 跟踪正在处理的代理节点路径
        self.in_proxy_node = False
    
    def represent_mapping(self, tag, mapping, flow_style=None):
        """
        重写映射表示方法，使代理节点全部使用单行格式
        """
        # 检查是否是代理节点
        is_proxy_node = False
        old_in_proxy = self.in_proxy_node
        
        if 'name' in mapping and ('server' in mapping or 'type' in mapping):
            is_proxy_node = True
            self.in_proxy_node = True
        
        # 如果是代理节点或在代理节点路径中，使用单行格式
        if is_proxy_node or self.in_proxy_node:
            flow_style = True
        
        result = super().represent_mapping(tag, mapping, flow_style=flow_style)
        
        # 恢复之前的状态
        self.in_proxy_node = old_in_proxy
        
        return result

def decode_base64(encoded_str):
    """
    解码Base64字符串，处理可能的padding问题
    
    :param encoded_str: Base64编码的字符串
    :return: 解码后的字符串，如果解码失败则返回None
    """
    if not encoded_str:
        return None
    
    try:
        # 清理字符串，移除换行符和空格
        encoded_str = encoded_str.strip().replace('\n', '').replace('\r', '').replace(' ', '')
        
        # 处理padding
        padding = 4 - len(encoded_str) % 4
        if padding < 4:
            encoded_str += '=' * padding
        
        # 解码
        decoded_bytes = base64.b64decode(encoded_str)
        
        # 尝试以UTF-8解码
        try:
            return decoded_bytes.decode('utf-8')
        except UnicodeDecodeError:
            # 如果UTF-8解码失败，尝试其他编码
            for encoding in ['gbk', 'gb2312', 'latin1', 'iso-8859-1']:
                try:
                    return decoded_bytes.decode(encoding)
                except UnicodeDecodeError:
                    continue
            
            # 如果所有编码都失败，使用latin1（它可以强制解码任何字节序列）
            logger.warning("无法确定正确的字符编码，使用latin1强制解码")
            return decoded_bytes.decode('latin1', errors='replace')
            
    except Exception as e:
        logger.debug(f"Base64解码失败: {str(e)}")
        return None

def safe_load_yaml(yaml_str):
    """
    安全加载YAML字符串
    
    :param yaml_str: YAML字符串
    :return: 解析后的字典，如果解析失败则返回None
    """
    try:
        logger.info("开始加载YAML内容")
        result = yaml.safe_load(yaml_str)
        
        if result is None:
            logger.warning("YAML加载结果为None，可能是空文档")
            return {}
            
        if not isinstance(result, dict):
            logger.warning(f"YAML加载结果不是字典类型，而是 {type(result)}")
            return {}
            
        # 检查是否成功解析了Clash配置的关键字段
        key_fields = ["port", "proxies", "proxy-groups", "rules"]
        found_fields = [field for field in key_fields if field in result]
        
        if found_fields:
            logger.info(f"成功解析YAML，找到以下关键字段: {', '.join(found_fields)}")
        else:
            logger.warning("YAML解析成功，但未找到任何Clash配置关键字段")
            
        # 打印部分关键统计信息
        if "proxies" in result:
            logger.info(f"配置包含 {len(result.get('proxies', []))} 个代理节点")
        if "proxy-groups" in result:
            logger.info(f"配置包含 {len(result.get('proxy-groups', []))} 个代理组")
        if "rules" in result:
            logger.info(f"配置包含 {len(result.get('rules', []))} 条规则")
            
        return result
    except yaml.YAMLError as e:
        if hasattr(e, 'problem_mark'):
            mark = e.problem_mark
            logger.error(f"YAML解析错误: 第 {mark.line + 1} 行, 第 {mark.column + 1} 列: {e}")
        else:
            logger.error(f"YAML解析失败: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"YAML解析过程中发生其他错误: {str(e)}")
        return None

class CustomDumper(yaml.Dumper):
    """
    自定义YAML Dumper，用于格式化输出
    """
    def increase_indent(self, flow=False, indentless=False):
        return super(CustomDumper, self).increase_indent(flow, False)

def safe_dump_yaml(yaml_obj, file_path=None):
    """
    安全导出YAML对象到文件或字符串
    
    :param yaml_obj: YAML对象
    :param file_path: 可选，文件路径，如果不提供则返回字符串
    :return: 如果file_path为None，则返回YAML字符串；否则返回None
    """
    try:
        # 创建格式化选项
        yaml_str = yaml.dump(
            yaml_obj,
            Dumper=CustomDumper,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            width=100
        )
        
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(yaml_str)
            logger.info(f"YAML已成功写入到文件: {file_path}")
            return None
        else:
            return yaml_str
    except Exception as e:
        logger.error(f"YAML导出失败: {str(e)}")
        return None if file_path else ""

def parse_uri(uri):
    """
    解析URI字符串，获取scheme和内容
    
    :param uri: URI字符串，例如 vmess://xxx
    :return: (scheme, payload) 元组
    """
    try:
        # 使用正则表达式匹配协议和内容
        match = re.match(r'^([a-zA-Z0-9]+)://(.*?)$', uri)
        if match:
            scheme = match.group(1).lower()
            payload = match.group(2)
            return scheme, payload
        else:
            logger.warning(f"无法解析URI: {uri[:30]}...")
            return None, None
    except Exception as e:
        logger.error(f"解析URI时发生异常: {str(e)}")
        return None, None

def load_local_file(file_path):
    """
    加载本地文件内容
    
    :param file_path: 文件路径
    :return: 文件内容字符串，如果加载失败则返回None
    """
    try:
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return None
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        logger.info(f"成功加载文件: {file_path}")
        return content
    except Exception as e:
        logger.error(f"加载文件失败: {str(e)}")
        return None

def decode_url_encoded_name(name):
    """
    解码URL编码的名称
    
    :param name: 可能包含URL编码字符(%xx)的名称
    :return: 解码后的名称
    """
    if not name or '%' not in name:
        return name
        
    try:
        return unquote(name)
    except Exception as e:
        logger.warning(f"URL解码名称失败: {str(e)}")
        return name

def is_base64(s):
    """
    检查字符串是否是Base64编码
    
    :param s: 待检查的字符串
    :return: 布尔值，指示是否是Base64编码
    """
    if not isinstance(s, str):
        return False
        
    if not s:
        return False
        
    # 去除可能的空白字符
    s = s.strip()
    
    # 检查基本模式
    if not re.match(r'^[A-Za-z0-9+/]*={0,2}$', s):
        return False
        
    # 进一步验证，尝试解码
    try:
        # 尝试解码前100个字符
        sample = s[:min(100, len(s))]
        # 确保Base64字符串长度是4的倍数，否则添加填充
        padding = 4 - len(sample) % 4
        if padding < 4:
            sample += '=' * padding
            
        # 尝试解码
        decoded = base64.b64decode(sample)
        return True
    except Exception:
        return False
