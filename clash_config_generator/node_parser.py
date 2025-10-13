import base64
import json
import logging
import re
import random
from urllib.parse import urlparse, parse_qs, unquote

logger = logging.getLogger(__name__)

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
        rem = len(encoded_str) % 4
        if rem > 0:
            encoded_str += '=' * (4 - rem)
        
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

class NodeParser:
    """节点解析器，支持多种协议格式"""
    
    def __init__(self):
        pass

    def parse_vless(self, vless_uri):
        """
        Parses a vless:// URI
        vless://uuid@host:port?params#name
        """
        try:
            parsed_url = urlparse(vless_uri)
            
            uuid = parsed_url.username
            server = parsed_url.hostname
            port = parsed_url.port
            name = unquote(parsed_url.fragment) if parsed_url.fragment else f"vless-{server}"

            if not all([uuid, server, port]):
                logger.error(f"VLESS URI missing essential parts: {vless_uri}")
                return None

            params = parse_qs(parsed_url.query)

            clash_config = {
                'name': name,
                'type': 'vless',
                'server': server,
                'port': port,
                'uuid': uuid,
                'udp': True,
            }

            # Network type
            network_type = params.get('type', ['tcp'])[0]
            if network_type != 'tcp':
                clash_config['network'] = network_type

            # Security (TLS or REALITY)
            security = params.get('security', ['none'])[0]
            if security == 'tls':
                clash_config['tls'] = True
                clash_config['servername'] = params.get('sni', [server])[0]
                clash_config['client-fingerprint'] = params.get('fp', ['chrome'])[0]
                
                # flow
                flow = params.get('flow', [None])[0]
                if flow:
                    clash_config['flow'] = flow

            elif security == 'reality':
                clash_config['tls'] = True # REALITY requires tls: true
                clash_config['servername'] = params.get('sni', [server])[0]
                clash_config['client-fingerprint'] = params.get('fp', ['chrome'])[0]
                
                public_key = params.get('pbk', [None])[0]
                short_id = params.get('sid', [None])[0]
                
                if not public_key:
                    logger.error(f"VLESS REALITY node missing public key (pbk): {vless_uri}")
                    return None
                
                clash_config['reality-opts'] = {
                    'public-key': public_key
                }
                if short_id:
                    clash_config['reality-opts']['short-id'] = short_id
                
                # flow
                flow = params.get('flow', [None])[0]
                if flow:
                    clash_config['flow'] = flow


            # Transport options
            if network_type == 'ws':
                ws_path = params.get('path', ['/'])[0]
                ws_host = params.get('host', [server])[0]
                clash_config['ws-opts'] = {
                    'path': ws_path,
                    'headers': {'Host': ws_host}
                }
            elif network_type == 'grpc':
                service_name = params.get('serviceName', [''])[0]
                clash_config['grpc-opts'] = {
                    'grpc-service-name': service_name
                }

            return clash_config

        except Exception as e:
            logger.error(f"Failed to parse VLESS URI: {vless_uri} - {str(e)}")
            return None
    
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
            _, encoded_content = parse_uri(vmess_uri)
            
            # 解码Base64内容
            json_str = decode_base64(encoded_content)
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
            parsed_url = urlparse(ss_uri)
            
            # 提取节点名称
            name = unquote(parsed_url.fragment) if parsed_url.fragment else None

            # 定义变量
            method = None
            password = None
            server = parsed_url.hostname
            port = parsed_url.port

            # 处理认证信息
            # 新格式: ss://base64(method:password)@server:port
            # 旧格式: ss://method:password@server:port
            if parsed_url.username:
                auth_info = parsed_url.username
                # 有些客户端会将整个认证信息进行base64编码
                try:
                    decoded_auth = decode_base64(auth_info)
                    if ':' in decoded_auth:
                        auth_info = decoded_auth
                except Exception:
                    pass # 不是base64编码，直接使用
                
                if ':' in auth_info:
                    method, password = auth_info.split(':', 1)
                else:
                    # 兼容没有密码的旧格式
                    method = auth_info
                    password = parsed_url.password or ""
            else:
                # 兼容一些非常规的格式
                # ss://base64(method:password@server:port)#name
                encoded_part = ss_uri.split('//')[1].split('#')[0]
                decoded_part = decode_base64(encoded_part)
                if decoded_part and '@' in decoded_part and ':' in decoded_part:
                     auth_part, server_part = decoded_part.split('@', 1)
                     method, password = auth_part.split(':', 1)
                     # The fix: use the server and port from the decoded part
                     server, port_str = server_part.split(':', 1)
                     port = int(port_str)
                else:
                    logger.error(f"无法解析SS认证信息: {ss_uri}")
                    return None

            if not all([server, port, method, password is not None]):
                 logger.error(f"SS URI缺少必要部分: {ss_uri}")
                 return None

            # 解析查询参数
            params = parse_qs(parsed_url.query)
            
            # 构建Clash配置
            clash_config = {
                'name': name or f"ss-{server}",
                'type': 'ss',
                'server': server,
                'port': port,
                'cipher': method,
                'password': password,
                'udp': True
            }

            # 处理插件
            plugin = params.get('plugin', [None])[0]
            if plugin:
                clash_config['plugin'] = plugin
                
                plugin_opts = {}
                if 'obfs' in params:
                    plugin_opts['mode'] = params.get('obfs-type', params.get('obfs', [None]))[0]
                if 'obfs-host' in params:
                    plugin_opts['host'] = params['obfs-host'][0]
                if 'obfs-uri' in params:
                    plugin_opts['path'] = params['obfs-uri'][0]
                
                if plugin_opts:
                    clash_config['plugin-opts'] = plugin_opts

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
            parsed_url = urlparse(trojan_uri)
            
            password = parsed_url.username
            server = parsed_url.hostname
            port = parsed_url.port
            name = unquote(parsed_url.fragment) if parsed_url.fragment else f"trojan-{server}"
            params = parse_qs(parsed_url.query)

            if not all([password, server, port]):
                logger.error(f"Trojan URI 缺少必要部分: {trojan_uri}")
                return None

            # 构建Clash配置
            clash_config = {
                'name': name,
                'type': 'trojan',
                'server': server,
                'port': int(port),
                'password': password,
                'udp': True
            }
            
            # 添加SNI
            sni = params.get('sni', params.get('peer', [None]))[0]
            if sni:
                clash_config['sni'] = sni
            
            # 添加跳过证书验证
            if params.get('allowInsecure', ['0'])[0] == '1':
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
            _, content = parse_uri(hysteria_uri)
            
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
        解析 hysteria2://格式的URI
        
        Args:
            hysteria_uri (str): hysteria2://开头的URI
            
        Returns:
            dict: Clash格式的节点配置
        """
        try:
            # 移除 hysteria2://前缀
            _, content = parse_uri(hysteria_uri)
            
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
                protocol, _ = parse_uri(node_str)
                
                # 根据协议调用相应的解析方法
                if protocol == 'vless':
                    return self.parse_vless(node_str)
                elif protocol == 'vmess':
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
        if node_type == 'vless' and 'uuid' not in node:
            return False
        elif node_type == 'vmess' and ('uuid' not in node or 'alterId' not in node):
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
        scheme, _ = parse_uri(uri)
        
        if scheme == 'vless':
            proxy = node_parser.parse_vless(uri)
        elif scheme == 'vmess':
            proxy = node_parser.parse_vmess(uri)
        elif scheme == 'ss':
            proxy = node_parser.parse_ss(uri)
        
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

