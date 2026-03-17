"""JSON 处理工具类 - 增强版"""
import json
import re
from typing import Any, Dict, List, Union, Optional, Tuple
from app.logger import get_logger

logger = get_logger(__name__)


def clean_json_response(text: str) -> str:
    """清洗 AI 返回的 JSON（增强版 - 多重容错）"""
    if not text or not text.strip():
        logger.warning("⚠️ clean_json_response: 输入为空")
        return "{}"
    
    original_length = len(text)
    logger.debug(f"🔍 开始清洗JSON，原始长度: {original_length}")
    logger.debug(f"   原始内容预览: {text[:200]}...")
    
    # 步骤 1: 去除 markdown 代码块
    text = _remove_markdown_code_blocks(text)
    
    # 步骤 2: 快速路径 - 尝试直接解析
    try:
        json.loads(text)
        logger.debug(f"✅ 直接解析成功，无需清洗")
        return text
    except Exception:
        pass
    
    # 步骤 3: 修复常见 JSON 格式问题
    text = _fix_common_json_issues(text)
    
    # 步骤 4: 提取有效的 JSON 部分
    text = _extract_json_section(text)
    
    # 步骤 5: 修复未闭合的 JSON
    text = _fix_unclosed_json(text)
    
    # 步骤 6: 修复尾随逗号
    text = _fix_trailing_commas(text)
    
    # 验证结果
    try:
        json.loads(text)
        logger.debug(f"✅ 清洗后JSON验证成功，最终长度: {len(text)}")
    except json.JSONDecodeError as e:
        logger.error(f"❌ 清洗后JSON仍然无效: {e}")
        logger.error(f"   清洗后内容: {text[:500]}...")
    
    return text


def _remove_markdown_code_blocks(text: str) -> str:
    """去除 markdown 代码块标记"""
    # 去除开头的 ```json 或 ```
    text = re.sub(r'^```(?:json)?\s*\n?', '', text, flags=re.MULTILINE | re.IGNORECASE)
    # 去除结尾的 ```
    text = re.sub(r'\n?```\s*$', '', text, flags=re.MULTILINE)
    return text.strip()


def _fix_common_json_issues(text: str) -> str:
    """修复常见的 JSON 格式问题"""
    # 1. 处理中文引号（先保护已转义的引号）
    text = text.replace('\\"', '\x00ESCAPED\x00')
    text = text.replace('"', '"').replace('"', '"')  # 中文引号替换
    text = text.replace('\x00ESCAPED\x00', '\\"')
    
    # 2. 移除注释
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    text = re.sub(r'//.*?$', '', text, flags=re.MULTILINE)
    
    # 3. 修复布尔值和 null 的大小写
    text = re.sub(r'(?<![\w"])\bTrue\b', 'true', text)
    text = re.sub(r'(?<![\w"])\bFalse\b', 'false', text)
    text = re.sub(r'(?<![\w"])\bNone\b', 'null', text)
    
    # 4. 修复未转义的换行符（在字符串值中）
    # 这个比较复杂，需要更精细的处理
    
    return text.strip()


def _extract_json_section(text: str) -> str:
    """提取有效的 JSON 部分"""
    # 找到第一个 { 或 [
    start = -1
    start_char = ''
    for i, c in enumerate(text):
        if c in ('{', '['):
            start = i
            start_char = c
            break
    
    if start == -1:
        logger.warning(f"⚠️ 未找到JSON起始符号 {{ 或 [")
        return text
    
    text = text[start:]
    
    # 使用改进的栈匹配找到对应的闭合括号
    end_char = '}' if start_char == '{' else ']'
    stack = []
    in_string = False
    escape_next = False
    end_pos = -1
    last_valid_pos = 0
    
    for i, c in enumerate(text):
        if escape_next:
            escape_next = False
            if in_string:
                last_valid_pos = i
            continue
            
        if c == '\\':
            escape_next = True
            if in_string:
                last_valid_pos = i
            continue
            
        if c == '"':
            in_string = not in_string
            if in_string:
                last_valid_pos = i
            continue
            
        if in_string:
            last_valid_pos = i
            continue
            
        # 记录最后一个有效的位置（用于截断）
        if c in ('{', '['):
            stack.append(c)
            last_valid_pos = i
        elif c in ('}', ']'):
            if stack:
                expected = '{' if c == '}' else '['
                if stack[-1] == expected:
                    stack.pop()
                    last_valid_pos = i
                    if not stack:
                        end_pos = i + 1
                        break
                else:
                    logger.warning(f"⚠️ 括号不匹配: 遇到 {c} 但栈顶是 {stack[-1]}")
        elif c in (',', ':'):
            last_valid_pos = i
    
    if end_pos > 0:
        return text[:end_pos]
    
    # 未找到闭合，返回到最后有效位置
    if last_valid_pos > 0 and not in_string:
        logger.warning(f"⚠️ JSON未完全闭合，截断到位置 {last_valid_pos}")
        return text[:last_valid_pos + 1]
    
    logger.warning(f"⚠️ 无法确定JSON边界，返回全部内容")
    return text


def _fix_unclosed_json(text: str) -> str:
    """修复未闭合的 JSON"""
    text = text.strip()
    if not text:
        return "{}"
    
    start_char = text[0]
    if start_char not in ('{', '['):
        return text
    
    end_char = '}' if start_char == '{' else ']'
    
    # 统计括号
    stack = []
    in_string = False
    escape_next = False
    
    for c in text:
        if escape_next:
            escape_next = False
            continue
        if c == '\\':
            escape_next = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        
        if c in ('{', '['):
            stack.append(c)
        elif c in ('}', ']'):
            if stack:
                stack.pop()
    
    # 补充缺失的闭合括号
    if in_string:
        # 字符串未闭合，先闭合字符串
        text += '"'
        logger.debug(f"   补充未闭合的字符串引号")
    
    while stack:
        text += end_char
        stack.pop()
        logger.debug(f"   补充闭合括号: {end_char}")
    
    return text


def _fix_trailing_commas(text: str) -> str:
    """修复尾随逗号"""
    # 修复对象中的尾随逗号: {"a": 1,} -> {"a": 1}
    text = re.sub(r',(\s*})', r'\1', text)
    # 修复数组中的尾随逗号: [1, 2,] -> [1, 2]
    text = re.sub(r',(\s*])', r'\1', text)
    return text


def parse_json(text: str) -> Union[Dict, List]:
    """解析 JSON，带多重容错"""
    if not text or not text.strip():
        raise ValueError("输入文本为空")
    
    # 尝试 1: 直接解析
    try:
        return json.loads(text)
    except Exception:
        pass
    
    # 尝试 2: 清洗后解析
    cleaned = clean_json_response(text)
    try:
        return json.loads(cleaned)
    except Exception as e:
        logger.error(f"❌ parse_json 失败: {e}")
        logger.error(f"   原始文本长度: {len(text)}")
        logger.error(f"   清洗后长度: {len(cleaned)}")
        raise


def is_valid_json(text: str) -> bool:
    """检查文本是否为有效 JSON"""
    if not text or not text.strip():
        return False
    try:
        json.loads(text)
        return True
    except:
        try:
            cleaned = clean_json_response(text)
            json.loads(cleaned)
            return True
        except:
            return False


def extract_json_from_text(text: str) -> Optional[str]:
    """从文本中提取 JSON 部分"""
    try:
        return clean_json_response(text)
    except:
        return None
