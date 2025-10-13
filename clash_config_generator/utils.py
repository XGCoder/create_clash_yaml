import base64
import logging
import re
import yaml
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


def is_base64(s: str) -> bool:
    """
    判断字符串是否为有效的Base64编码。
    """
    if not isinstance(s, str) or not s:
        return False
    
    s = s.strip()
    # Base64 字符串的长度必须是 4 的倍数
    if len(s) % 4 != 0:
        return False
        
    # 检查是否只包含有效的 Base64 字符
    if not re.match(r'^[A-Za-z0-9+/]*={0,2}$', s):
        return False
        
    try:
        # 尝试解码，如果失败则不是有效的 Base64
        base64.b64decode(s)
        return True
    except Exception:
        return False

# --- Representer for bool to output 'true'/'false' ---
def bool_representer(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:bool', 'true' if data else 'false')

yaml.add_representer(bool, bool_representer, Dumper=yaml.SafeDumper)
yaml.add_representer(bool, bool_representer, Dumper=yaml.Dumper)
# ---

def safe_load_yaml(file_path):
    """
    安全加载YAML文件。
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"YAML文件加载失败: {file_path}, 错误: {e}")
        return None

def decode_base64(encoded_str: str) -> str:
    """
    解码Base64字符串。
    """
    try:
        # 补充=号，直到长度是4的倍数
        padding = len(encoded_str) % 4
        if padding > 0:
            encoded_str += '=' * (4 - padding)
        
        decoded_bytes = base64.urlsafe_b64decode(encoded_str)
        return decoded_bytes.decode('utf-8')
    except (base64.binascii.Error, UnicodeDecodeError) as e:
        logger.error(f"Base64解码失败: {encoded_str}, 错误: {e}")
        return ""

def parse_uri(uri: str) -> dict:
    """
    解析包含查询参数的URI。
    """
    try:
        parsed = urlparse(uri)
        query_params = parse_qs(parsed.query)
        # 将查询参数的值从列表转为单个值
        params = {k: v[0] for k, v in query_params.items()}
        return {
            "scheme": parsed.scheme,
            "netloc": parsed.netloc,
            "path": parsed.path,
            "params": params
        }
    except Exception as e:
        logger.error(f"URI解析失败: {uri}, 错误: {e}")
        return {}

def load_local_file(file_path: str) -> str:
    """
    加载本地文件内容。
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"本地文件加载失败: {file_path}, 错误: {e}")
        return ""