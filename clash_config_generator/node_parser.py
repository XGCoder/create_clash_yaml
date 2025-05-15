import base64
import json
import logging
import re
import random
from urllib.parse import urlparse, parse_qs, unquote
from . import utils

logger = logging.getLogger(__name__)

class NodeParser:
    """节点解析器，支持多种协议格式"""
    
    def __init__(self):
        pass
    
    def parse_vmess(self, vmess_uri):
        """
        解析vmess://格式的URI
        
        Args:
            vmess_uri (str): vmess://开头的URI
            
        Returns:
            dict: Clash格式的节点配置
        """
        try:
            # 移除vmess://前缀
            _, encoded_content = utils.parse_uri(vmess_uri)
            
            # 解码Base64内容
            json_str = utils.decode_base64(encoded_content)
            if not json_str:
                return None
                
            # 解析JSON
            vmess_config = json.loads(json_str)
            
            # 必要字段验证
            required_fields = ['add', 'port', 'id', 'aid', 'net']
            if not all(field in vmess_config for field in required_fields):
                logger.error(f"Vmess配置缺少必要字段: {vmess_config}")
                return None
            
            # 转换为Clash格式
            clash_config = {
                'name': vmess_config.get('ps', f"vmess-{vmess_config['add']}"),
                'type': 'vmess',
                'server': vmess_config['add'],
                'port': int(vmess_config['port']),
                'uuid': vmess_config['id'],
                'alterId': int(vmess_config['aid']),
                'cipher': vmess_config.get('scy', 'auto'),
                'udp': True,
                'network': vmess_config['net']
            }
            
            # 处理节点名称，进行URL解码
            if clash_config['name'] and '%' in clash_config['name']:
                try:
                    clash_config['name'] = unquote(clash_config['name'])
                except Exception as e:
                    logger.warning(f"URL解码VMess节点名称失败: {str(e)}")
            
            # 处理TLS
            if vmess_config.get('tls') == 'tls':
                clash_config['tls'] = True
                if 'sni' in vmess_config:
                    clash_config['servername'] = vmess_config['sni']
            
            # 处理路径和主机
            if vmess_config['net'] == 'ws':
                clash_config['ws-opts'] = {'path': vmess_config.get('path', '/')}
                if 'host' in vmess_config:
                    clash_config['ws-opts']['headers'] = {'Host': vmess_config['host']}
            elif vmess_config['net'] == 'h2':
                clash_config['h2-opts'] = {'path': vmess_config.get('path', '/')}
                if 'host' in vmess_config:
                    clash_config['h2-opts']['host'] = [vmess_config['host']]
            elif vmess_config['net'] == 'grpc':
                clash_config['grpc-opts'] = {'grpc-service-name': vmess_config.get('path', '')}
            
            return clash_config
            
        except Exception as e:
            logger.error(f"解析Vmess失败: {str(e)}")
            return None
    
    def parse_ss(self, ss_uri):
        """
        解析ss://格式的URI
        
        Args:
            ss_uri (str): ss://开头的URI
            
        Returns:
            dict: Clash格式的节点配置
        """
        try:
            # 移除ss://前缀
            _, encoded_content = utils.parse_uri(ss_uri)
            
            # 检查是否使用了新风格的URI格式（包含@符号）
            if '@' in encoded_content:
                # 处理新格式: ss://base64(method:password)@server:port#name
                auth_str, server_port = encoded_content.split('@', 1)
                
                # 处理可能的URL编码
                if auth_str.count(':') == 0:
                    # 需要base64解码
                    auth_str = utils.decode_base64(auth_str)
                
                # 提取方法和密码
                method, password = auth_str.split(':', 1)
                
                # 提取服务器、端口和名称
                server_port_parts = server_port.split('#', 1)
                server_port = server_port_parts[0]
                name = server_port_parts[1] if len(server_port_parts) > 1 else None
                
                # 分割服务器和端口
                if ':' in server_port:
                    server, port = server_port.split(':', 1)
                else:
                    logger.error("SS URI格式错误: 缺少端口")
                    return None
            else:
                # 处理旧格式: ss://base64(method:password@server:port)
                decoded_content = utils.decode_base64(encoded_content.split('#')[0])
                if not decoded_content or '@' not in decoded_content:
                    logger.error("SS URI解码失败或格式错误")
                    return None
                
                # 提取方法、密码、服务器和端口
                auth_str, server_port = decoded_content.split('@', 1)
                method, password = auth_str.split(':', 1)
                server, port = server_port.split(':', 1)
                
                # 提取名称
                name_parts = encoded_content.split('#', 1)
                name = name_parts[1] if len(name_parts) > 1 else None
            
            # 构建Clash配置
            clash_config = {
                'name': name or f"ss-{server}",
                'type': 'ss',
                'server': server,
                'port': int(port),
                'cipher': method,
                'password': password,
                'udp': True
            }
            
            # 处理节点名称，进行URL解码
            if clash_config['name'] and '%' in clash_config['name']:
                try:
                    clash_config['name'] = unquote(clash_config['name'])
                except Exception as e:
                    logger.warning(f"URL解码SS节点名称失败: {str(e)}")
            
            return clash_config
            
        except Exception as e:
            logger.error(f"解析SS失败: {str(e)}")
            return None
    
    def parse_trojan(self, trojan_uri):
        """
        解析trojan://格式的URI
        
        Args:
            trojan_uri (str): trojan://开头的URI
            
        Returns:
            dict: Clash格式的节点配置
        """
        try:
            # 移除trojan://前缀
            _, content = utils.parse_uri(trojan_uri)
            
            # 解析格式: trojan://password@server:port?sni=sni.com&allowInsecure=1#name
            if '@' not in content:
                logger.error("Trojan URI格式错误: 缺少@符号")
                return None
                
            # 分离密码和其他部分
            password, server_port_params = content.split('@', 1)
            
            # 分离服务器:端口和参数
            if '?' in server_port_params:
                server_port, params = server_port_params.split('?', 1)
            else:
                params = ""
                if '#' in server_port_params:
                    server_port, _ = server_port_params.split('#', 1)
                else:
                    server_port = server_port_params
            
            # 分离服务器和端口
            if ':' in server_port:
                server, port = server_port.split(':', 1)
                # 处理端口中可能包含的标签
                if '#' in port:
                    port, _ = port.split('#', 1)
            else:
                logger.error("Trojan URI格式错误: 缺少端口")
                return None
            
            # 解析参数
            query_params = {}
            if params:
                param_pairs = params.split('&')
                for pair in param_pairs:
                    if '=' in pair:
                        key, value = pair.split('=', 1)
                        # 处理值中可能包含的标签
                        if '#' in value:
                            value, _ = value.split('#', 1)
                        query_params[key] = value
            
            # 提取名称
            name = None
            if '#' in content:
                name = content.split('#', 1)[1]
            
            # 构建Clash配置
            clash_config = {
                'name': name or f"trojan-{server}",
                'type': 'trojan',
                'server': server,
                'port': int(port),
                'password': password,
                'udp': True
            }
            
            # 处理节点名称，进行URL解码
            if clash_config['name'] and '%' in clash_config['name']:
                try:
                    clash_config['name'] = unquote(clash_config['name'])
                except Exception as e:
                    logger.warning(f"URL解码Trojan节点名称失败: {str(e)}")
            
            # 添加SNI
            if 'sni' in query_params:
                clash_config['sni'] = query_params['sni']
            elif 'peer' in query_params:
                clash_config['sni'] = query_params['peer']
            
            # 添加跳过证书验证
            if 'allowInsecure' in query_params and query_params['allowInsecure'] == '1':
                clash_config['skip-cert-verify'] = True
            
            return clash_config
            
        except Exception as e:
            logger.error(f"解析Trojan失败: {str(e)}")
            return None
    
    def parse_hysteria(self, hysteria_uri):
        """
        解析hysteria://格式的URI
        
        Args:
            hysteria_uri (str): hysteria://开头的URI
            
        Returns:
            dict: Clash格式的节点配置
        """
        try:
            # 移除hysteria://前缀
            _, content = utils.parse_uri(hysteria_uri)
            
            # 解析URL
            url_parts = urlparse(f"hysteria://{content}")
            
            # 提取服务器和端口
            server = url_parts.hostname
            port = url_parts.port or 443
            
            # 解析查询参数
            query_params = parse_qs(url_parts.query)
            
            # 提取协议
            protocol = query_params.get('protocol', ['udp'])[0]
            
            # 提取密码/认证信息
            auth = ""
            if url_parts.username:
                auth = url_parts.username
            elif 'auth' in query_params:
                auth = query_params['auth'][0]
            
            # 提取上行/下行速度
            up_mbps = int(query_params.get('upmbps', [50])[0])
            down_mbps = int(query_params.get('downmbps', [50])[0])
            
            # 提取SNI和跳过证书验证
            sni = query_params.get('peer', query_params.get('sni', ['']))[0]
            skip_cert_verify = 'insecure' in query_params
            
            # 提取名称
            name = None
            if url_parts.fragment:
                name = url_parts.fragment
            
            # 构建Clash配置
            clash_config = {
                'name': name or f"hysteria-{server}",
                'type': 'hysteria',
                'server': server,
                'port': port,
                'auth_str': auth,
                'protocol': protocol,
                'up': up_mbps,
                'down': down_mbps,
                'sni': sni,
                'skip-cert-verify': skip_cert_verify
            }
            
            # 处理节点名称，进行URL解码
            if clash_config['name'] and '%' in clash_config['name']:
                try:
                    clash_config['name'] = unquote(clash_config['name'])
                except Exception as e:
                    logger.warning(f"URL解码Hysteria节点名称失败: {str(e)}")
            
            return clash_config
            
        except Exception as e:
            logger.error(f"解析Hysteria失败: {str(e)}")
            return None
    
    def parse_hysteria2(self, hysteria_uri):
        """
        解析hysteria2://格式的URI
        
        Args:
            hysteria_uri (str): hysteria2://开头的URI
            
        Returns:
            dict: Clash格式的节点配置
        """
        try:
            # 移除hysteria2://前缀
            _, content = utils.parse_uri(hysteria_uri)
            
            # 先检查是否是简单格式的URI (没有使用标准URL格式)
            if '?' not in content and '#' not in content and '@' not in content:
                # 可能是一个简单的凭证，尝试分离服务器和端口
                if ':' in content:
                    server_parts = content.split(':')
                    server = server_parts[0]
                    port = int(server_parts[1]) if len(server_parts) > 1 else 443
                    
                    # 构建基本配置
                    return {
                        'name': f"hysteria2-{server}",
                        'type': 'hysteria2',
                        'server': server,
                        'port': port,
                        'password': content,  # 将整个内容当作密码
                        'sni': server,
                        'skip-cert-verify': True,
                        'client-fingerprint': 'chrome',
                        'udp': True
                    }
            
            # 处理标准URL格式
            # 先确保内容是合法的URL格式
            if not content.startswith('http://') and not content.startswith('https://'):
                content = f"https://{content}"
            
            # 解析URL
            url_parts = urlparse(content)
            
            # 提取服务器和端口
            server = url_parts.hostname
            if not server and '@' in content:
                # 处理格式如 hysteria2://password@server:port
                try:
                    credentials, server_part = content.split('@', 1)
                    server_port = server_part.split('?')[0].split('#')[0]
                    server = server_port.split(':')[0]
                    port = int(server_port.split(':')[1]) if ':' in server_port else 443
                    password = credentials
                except Exception as e:
                    logger.warning(f"解析Hysteria2密码部分时出错: {str(e)}")
                    password = ""
            else:
                port = url_parts.port or 443
                # 从URL用户名部分或查询字符串中提取密码
                password = url_parts.username or ""
                if not password and 'password' in parse_qs(url_parts.query):
                    password = parse_qs(url_parts.query)['password'][0]
                elif not password and 'auth' in parse_qs(url_parts.query):
                    password = parse_qs(url_parts.query)['auth'][0]
            
            # 解析查询参数
            query_params = parse_qs(url_parts.query)
            
            # 提取SNI和安全设置
            sni = query_params.get('sni', [''])[0]
            insecure = 'insecure' in query_params or 'allowInsecure' in query_params
            if not sni and 'peer' in query_params:
                sni = query_params['peer'][0]
            # 如果没有SNI，尝试使用服务器作为SNI
            if not sni:
                sni = server
            
            # 对于某些特定域名，使用通用SNI
            if sni and ('5i996.top' in sni or 'ip地址' in sni):
                sni = 'bing.com'
            
            # 提取混淆设置
            obfs = query_params.get('obfs', [''])[0]
            obfs_password = query_params.get('obfs-password', [''])[0]
            
            # 提取多路复用端口
            mport_str = query_params.get('mport', [''])[0]
            mport = None
            if mport_str:
                # 可能是端口范围，如 "20000-50000"
                if '-' in mport_str:
                    mport = mport_str
                else:
                    try:
                        mport = int(mport_str)
                    except ValueError:
                        mport = None
            
            # 提取客户端指纹
            fingerprint = query_params.get('fingerprint', ['chrome'])[0]
            
            # 提取名称
            name = None
            if url_parts.fragment:
                name = url_parts.fragment
            
            # 构建Clash配置
            clash_config = {
                'name': name or f"hysteria2-{server}",
                'type': 'hysteria2',
                'server': server,
                'port': port,
                'password': password,
                'sni': sni,
                'skip-cert-verify': insecure,
                'client-fingerprint': fingerprint,
                'udp': True
            }
            
            # 处理节点名称，进行URL解码
            if clash_config['name'] and '%' in clash_config['name']:
                try:
                    clash_config['name'] = unquote(clash_config['name'])
                except Exception as e:
                    logger.warning(f"URL解码Hysteria2节点名称失败: {str(e)}")
            
            # 添加可选配置
            if mport:
                clash_config['mport'] = mport
                
            if obfs and obfs_password:
                clash_config['obfs'] = obfs
                clash_config['obfs-password'] = obfs_password
            
            return clash_config
            
        except Exception as e:
            logger.error(f"解析Hysteria2失败: {str(e)}")
            return None
    
    def parse_direct_node(self, node_str):
        """
        解析直接提供的节点信息（识别协议类型并调用相应方法）
        
        Args:
            node_str (str): 节点信息字符串
            
        Returns:
            dict: Clash格式的节点配置
        """
        try:
            # 检查是否为URI格式
            if '://' in node_str:
                protocol, _ = utils.parse_uri(node_str)
                
                # 根据协议调用相应的解析方法
                if protocol == 'vmess':
                    return self.parse_vmess(node_str)
                elif protocol == 'ss':
                    return self.parse_ss(node_str)
                elif protocol == 'trojan':
                    return self.parse_trojan(node_str)
                elif protocol == 'hysteria':
                    return self.parse_hysteria(node_str)
                elif protocol == 'hysteria2':
                    return self.parse_hysteria2(node_str)
                else:
                    logger.warning(f"不支持的协议: {protocol}")
                    return None
            
            # 尝试作为JSON字符串解析
            if node_str.strip().startswith('{') and node_str.strip().endswith('}'):
                try:
                    node_json = json.loads(node_str)
                    # 验证是否为Clash节点格式
                    if 'type' in node_json and 'server' in node_json and 'port' in node_json:
                        # 确保节点有名称
                        if 'name' not in node_json:
                            node_json['name'] = f"{node_json['type']}-{node_json['server']}"
                        return node_json
                    else:
                        logger.warning("JSON不符合Clash节点格式")
                        return None
                except json.JSONDecodeError:
                    logger.warning("无效的JSON字符串")
                    return None
            
            logger.warning(f"无法识别的节点格式: {node_str[:30]}...")
            return None
            
        except Exception as e:
            logger.error(f"解析节点失败: {str(e)}")
            return None
    
    def validate_node(self, node):
        """
        验证节点信息的完整性和有效性
        
        Args:
            node (dict): 节点配置
            
        Returns:
            bool: 节点是否有效
        """
        if not isinstance(node, dict):
            return False
            
        # 检查必要字段
        required_fields = ['name', 'type', 'server', 'port']
        if not all(field in node for field in required_fields):
            return False
            
        # 根据类型检查特定字段
        node_type = node['type']
        if node_type == 'vmess' and ('uuid' not in node or 'alterId' not in node):
            return False
        elif node_type == 'ss' and ('cipher' not in node or 'password' not in node):
            return False
        elif node_type == 'trojan' and 'password' not in node:
            return False
        elif node_type == 'hysteria' and 'auth_str' not in node:
            return False
        elif node_type == 'hysteria2' and 'password' not in node:
            return False
            
        return True

# 为了兼容性，添加一个独立的parse_proxy函数
def parse_proxy(uri):
    """
    解析代理节点URI
    
    Args:
        uri (str): 代理节点URI
        
    Returns:
        dict: 解析后的代理配置字典，如果解析失败则返回None
    """
    try:
        node_parser = NodeParser()
        scheme, _ = utils.parse_uri(uri)
        
        if scheme == 'vmess':
            proxy = node_parser.parse_vmess(uri)
        elif scheme == 'ss':
            proxy = node_parser.parse_ss(uri)
        elif scheme == 'ssr':
            proxy = node_parser.parse_ssr(uri)
        elif scheme == 'trojan':
            proxy = node_parser.parse_trojan(uri)
        elif scheme == 'hysteria':
            proxy = node_parser.parse_hysteria(uri)
        elif scheme == 'hysteria2':
            proxy = node_parser.parse_hysteria2(uri)
        else:
            logger.warning(f"不支持的协议类型: {scheme}")
            return None
        
        # 确保节点名称使用UTF-8编码，避免乱码
        if proxy and 'name' in proxy:
            try:
                # 尝试确保名称是有效的UTF-8字符串
                name = proxy['name']
                if isinstance(name, bytes):
                    proxy['name'] = name.decode('utf-8', errors='replace')
                elif isinstance(name, str):
                    # 测试是否可以编码为UTF-8
                    name.encode('utf-8')
            except UnicodeError:
                # 如果有编码问题，替换为安全名称
                proxy['name'] = f"{proxy['type']}-{proxy['server']}"
                logger.warning(f"节点名称编码有问题，已自动替换: {proxy['name']}")
        
        # 验证代理配置
        if proxy and node_parser.validate_node(proxy):
            return proxy
        else:
            logger.warning(f"代理配置验证失败: {uri[:30]}...")
            return None
    
    except Exception as e:
        logger.error(f"解析代理URI时发生异常: {str(e)}")
        return None
