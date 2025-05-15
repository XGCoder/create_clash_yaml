import requests
import base64
import json
import yaml
import re
import logging
import random
import time
from urllib.parse import urlparse, unquote
from . import utils
from .utils import decode_base64, safe_load_yaml, parse_uri
from .node_parser import NodeParser

logger = logging.getLogger(__name__)

class SubscriptionManager:
    """订阅管理器，用于获取和解析订阅源"""
    
    def __init__(self, timeout=60, max_retries=3):
        """
        初始化订阅管理器
        
        Args:
            timeout (int): 请求超时时间（秒）
            max_retries (int): 最大重试次数
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.node_parser = NodeParser()
        
    def fetch_subscription(self, url):
        """
        获取订阅内容
        
        Args:
            url (str): 订阅地址
            
        Returns:
            str: 订阅内容，获取失败则返回None
        """
        logger.info(f"开始获取订阅: {url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        
        retry_count = 0
        while retry_count < self.max_retries:
            try:
                # 添加随机延迟，避免被服务器认为是爬虫
                if retry_count > 0:
                    delay = random.uniform(1, 3)
                    logger.info(f"等待 {delay:.2f} 秒后重试...")
                    time.sleep(delay)
                
                logger.info(f"正在请求订阅 {url} (尝试 {retry_count + 1}/{self.max_retries})")
                response = requests.get(url, headers=headers, timeout=self.timeout)
                
                if response.status_code == 200:
                    logger.info(f"成功获取订阅，内容长度: {len(response.text)} 字节")
                    return response.text
                else:
                    logger.warning(f"获取订阅失败，状态码: {response.status_code}")
            except requests.exceptions.Timeout:
                logger.warning(f"请求超时 (已尝试 {retry_count + 1}/{self.max_retries})")
            except requests.exceptions.ConnectionError:
                logger.warning(f"连接错误 (已尝试 {retry_count + 1}/{self.max_retries})")
            except requests.exceptions.RequestException as e:
                logger.warning(f"请求异常: {str(e)} (已尝试 {retry_count + 1}/{self.max_retries})")
            
            retry_count += 1
        
        logger.error(f"获取订阅失败，已达到最大重试次数 ({self.max_retries})")
        return None
    
    def parse_subscription(self, content):
        """
        解析订阅内容
        
        Args:
            content (str): 订阅内容
            
        Returns:
            list: 解析后的节点列表
        """
        logger.info(f"开始解析订阅内容，长度: {len(content)}")
        
        # 尝试先按yaml/json加载
        if content.strip().startswith('{') or content.strip().startswith('[') or 'proxies:' in content:
            try:
                logger.info("尝试按YAML/JSON解析")
                if content.strip().startswith('{') or content.strip().startswith('['):
                    # JSON格式
                    logger.info("检测到JSON格式，尝试解析")
                    data = json.loads(content)
                    if 'proxies' in data:
                        logger.info(f"从JSON中找到 {len(data['proxies'])} 个节点")
                        proxies = data['proxies']
                        # 对节点的name字段做处理，确保唯一性
                        self._ensure_unique_names(proxies)
                        return proxies
                    
                    logger.warning("JSON中未找到proxies字段，尝试其他解析方法")
                else:
                    # YAML格式
                    logger.info("检测到YAML格式，尝试解析")
                    try:
                        data = yaml.safe_load(content)
                        if 'proxies' in data and isinstance(data['proxies'], list):
                            logger.info(f"从YAML中找到 {len(data['proxies'])} 个节点")
                            proxies = data['proxies']
                            # 对节点的name字段做处理，确保唯一性
                            self._ensure_unique_names(proxies)
                            return proxies
                        
                        logger.warning("YAML中未找到有效的proxies字段，尝试其他解析方法")
                    except Exception as e:
                        logger.warning(f"YAML解析失败: {str(e)}")
                
            except Exception as e:
                logger.warning(f"解析YAML/JSON时出错: {str(e)}")
        
        # 检测是否是base64编码
        if utils.is_base64(content):
            logger.info("检测到BASE64编码，尝试解码")
            try:
                decoded = utils.decode_base64(content)
                return self._parse_decoded_content(decoded)
            except Exception as e:
                logger.warning(f"BASE64解码失败: {str(e)}")
        
        # 未识别到特定格式，尝试按行解析
        return self._parse_raw_content(content)
    
    def _determine_content_format(self, content):
        """
        确定内容格式
        
        Args:
            content (str): 订阅内容
            
        Returns:
            str: 格式类型，'base64', 'yaml', 'json'或'unknown'
        """
        content_strip = content.strip()
        
        # 首先检查是否是完整的Clash配置YAML格式
        # 通过特征检测：以port:、socks-port:或proxies:开头，或包含proxy-groups:、rules:等典型字段
        if (content_strip.startswith('port:') or 
            content_strip.startswith('mixed-port:') or
            content_strip.startswith('socks-port:') or
            content_strip.startswith('allow-lan:') or
            content_strip.startswith('proxies:') or
            'proxy-groups:' in content_strip[:500] or
            'rules:' in content_strip[:500]):
            logger.info("检测到完整的Clash配置YAML格式")
            return 'yaml'
        
        # 检查是否是Base64编码
        try:
            # 尝试解码前几个字符，判断是否可能是Base64
            if re.match(r'^[A-Za-z0-9+/=]+$', content_strip):
                # 临时解码一小部分检查有效性
                sample = content[:100].strip()
                decoded = decode_base64(sample)
                if decoded and (
                    decoded.startswith('ss://') or 
                    decoded.startswith('vmess://') or 
                    decoded.startswith('trojan://') or 
                    '{' in decoded or 
                    'proxies:' in decoded
                ):
                    return 'base64'
        except Exception:
            pass
        
        # 检查是否是标准YAML格式
        if 'type:' in content_strip[:200]:
            return 'yaml'
        
        # 检查是否是JSON格式
        try:
            # 尝试解析前几个字符
            if (content_strip.startswith('{') and content_strip.endswith('}')) or (
                content_strip.startswith('[') and content_strip.endswith(']')):
                json.loads(content_strip[:100] + content_strip[-10:])
                return 'json'
        except Exception:
            pass
        
        # 如果包含vmess://或ss://，可能是按行组织的节点列表
        if 'vmess://' in content or 'ss://' in content or 'trojan://' in content:
            return 'raw'
        
        # 默认假设为Base64编码的内容，让解码函数处理错误
        return 'base64'
    
    def _parse_decoded_content(self, content):
        """
        解析已解码的内容
        
        Args:
            content (str): 已解码的内容
            
        Returns:
            list: 解析出的节点列表
        """
        if not content:
            return []
            
        # 如果内容以特定的协议前缀开始，可能是按行组织的节点
        if (content.startswith('vmess://') or 
            content.startswith('ss://') or 
            content.startswith('trojan://') or 
            'vmess://' in content[:100] or 
            'ss://' in content[:100] or 
            'trojan://' in content[:100]):
            return self._parse_raw_content(content)
            
        # 检查是否是YAML格式
        if (content.startswith('proxies:') or 
            content.startswith('port:') or 
            content.startswith('mixed-port:') or 
            'proxy-groups:' in content[:500] or
            'rules:' in content[:500] or
            'type:' in content[:200]):
            logger.info("检测到YAML格式，使用YAML解析器")
            return self.parse_subscription(content)  # 使用主解析方法处理
            
        # 检查是否是JSON格式
        if content.startswith('{') or content.startswith('['):
            try:
                json_data = json.loads(content)
                if 'proxies' in json_data:
                    logger.info("解析为JSON格式，提取proxies")
                    return json_data['proxies']
            except Exception as e:
                logger.warning(f"JSON解析失败: {str(e)}")
        
        # 否则就按行解析
        return self._parse_raw_content(content)
    
    def _parse_raw_content(self, content):
        """
        解析原始内容，假设每行是一个节点
        
        Args:
            content (str): 原始内容
            
        Returns:
            list: 解析出的节点列表
        """
        if not content:
            return []
            
        proxies = []
        # 按行分割
        lines = content.split('\n')
        logger.info(f"尝试按行解析内容，共 {len(lines)} 行")
        
        # 过滤掉空行和注释行
        valid_lines = [line.strip() for line in lines if line.strip() and not line.strip().startswith('#')]
        logger.info(f"过滤后剩余 {len(valid_lines)} 行有效内容")
        
        # 逐行解析
        parsed_count = 0
        for line in valid_lines:
            try:
                # 跳过明显不是节点的行
                if not (line.startswith('vmess://') or 
                        line.startswith('ss://') or 
                        line.startswith('trojan://') or 
                        line.startswith('ssr://') or
                        line.startswith('hysteria://') or
                        line.startswith('hysteria2://') or
                        line.startswith('http://') or 
                        line.startswith('https://') or
                        line.startswith('vless://')):
                    continue
                
                proxy = self.node_parser.parse_direct_node(line)
                if proxy:
                    proxies.append(proxy)
                    parsed_count += 1
                    logger.debug(f"成功解析节点: {proxy.get('name', 'unnamed')}")
            except Exception as e:
                logger.warning(f"解析行出错: {str(e)}, 行内容: {line[:30]}...")
        
        logger.info(f"按行解析完成，成功解析 {parsed_count} 个节点")
        
        # 对节点的name字段做处理，确保唯一性
        if proxies:
            self._ensure_unique_names(proxies)
            
        return proxies
    
    def _ensure_unique_names(self, proxies):
        """
        确保节点名称唯一，并处理可能的编码问题
        
        Args:
            proxies (list): 节点列表
        """
        # 记录已使用的名称
        used_names = set()
        
        for proxy in proxies:
            original_name = proxy.get('name', '')
            
            # 处理名称编码问题
            try:
                # 如果是字节类型，尝试解码
                if isinstance(original_name, bytes):
                    original_name = original_name.decode('utf-8', errors='replace')
                # 尝试确保名称是有效的UTF-8字符串
                elif isinstance(original_name, str):
                    # 尝试URL解码（处理%xx格式的编码字符）
                    if '%' in original_name:
                        try:
                            original_name = unquote(original_name)
                            logger.debug(f"URL解码名称: {proxy.get('name', '')} -> {original_name}")
                        except Exception as e:
                            logger.warning(f"URL解码名称失败: {str(e)}")
                    
                    # 测试是否可以编码为UTF-8
                    original_name.encode('utf-8')
            except UnicodeError:
                # 如果有编码问题，使用类型和服务器创建一个安全名称
                server = proxy.get('server', 'unknown')
                proxy_type = proxy.get('type', 'node')
                original_name = f"{proxy_type}-{server}-{random.randint(1000, 9999)}"
                logger.warning(f"节点名称编码有问题，已自动替换: {original_name}")
            
            # 如果名称为空，生成一个默认名称
            if not original_name:
                proxy['name'] = f"未命名节点_{random.randint(1000, 9999)}"
                original_name = proxy['name']
            
            # 确保名称唯一
            name = original_name
            counter = 1
            while name in used_names:
                name = f"{original_name}_{counter}"
                counter += 1
            
            # 更新节点名称
            proxy['name'] = name
            used_names.add(name)
        
        logger.info(f"完成节点名称唯一性处理，共 {len(proxies)} 个节点")
    
    def get_proxies_from_url(self, url):
        """
        从URL获取代理节点列表 (保留此方法以兼容旧代码)
        
        Args:
            url (str): 订阅URL
            
        Returns:
            list: 代理节点列表
        """
        return self.fetch_and_parse(url)
    
    def fetch_and_parse(self, url):
        """
        获取并解析订阅内容
        
        Args:
            url (str): 订阅地址
            
        Returns:
            list: 解析出的节点列表
        """
        logger.info(f"开始获取并解析订阅: {url}")
        
        # 获取订阅内容
        content = self.fetch_subscription(url)
        if not content:
            logger.error(f"获取订阅内容失败: {url}")
            return []
        
        logger.info(f"成功获取订阅内容，长度: {len(content)}")
        logger.info(f"订阅内容开头片段: {content[:100].replace('\n', ' ')}...")
        
        # 解析订阅
        proxies = self.parse_subscription(content)
        if not proxies:
            logger.error(f"解析订阅失败，未找到有效节点: {url}")
            return []
        
        logger.info(f"成功解析订阅，找到 {len(proxies)} 个节点")
        # 打印部分节点名称作为示例
        node_samples = [proxy.get('name', 'unnamed') for proxy in proxies[:min(5, len(proxies))]]
        logger.info(f"节点示例: {', '.join(node_samples)}{' 等...' if len(proxies) > 5 else ''}")
        
        # 为每个代理节点添加来源信息
        for proxy in proxies:
            proxy['_source'] = url
        
        return proxies
