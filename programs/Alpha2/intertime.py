# _*_coding :utf-8 _
# @Time : 2026/6/18 13:33
# @Author : C盘研究所
# @File : intertime
# @Project : HamLog Project
import subprocess
import re
import platform


def get_ping_time(ip, timeout=2):
    """获取单个IP/域名的ping延迟

    返回: (success: bool, value: str)
        success=True 时 value 为延迟毫秒数（如 "32" 或 "<1"）
        success=False 时 value 为错误描述（如 "超时"、"失败"）
    """
    system = platform.system()
    try:
        if system == "Windows":
            cmd = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), ip]
        else:
            cmd = ["ping", "-c", "1", "-W", str(timeout), ip]

        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout + 3, encoding='utf-8', errors='replace'
        )
        output = result.stdout + result.stderr

        # 调试: 如果需要在日志中查看原始输出，可以取消下面的注释
        # print(f"[DEBUG] ping {ip} output:\n{output}")

        # 统一替换中文关键词，方便正则匹配
        unified = output.replace('时间', 'time').replace('毫秒', 'ms')

        # 策略1: 匹配 time=XXms / time=XX ms (Windows/Linux 通用)
        match = re.search(r'time[=<>](\d+(?:\.\d+)?)\s*ms', unified, re.IGNORECASE)
        if match:
            return True, match.group(1)

        # 策略2: 匹配 time<1ms (无数字)
        if re.search(r'time<1\s*ms', unified, re.IGNORECASE):
            return True, "<1"

        # 策略3: 匹配中文格式 "32ms" 或 "32毫秒" (不带 time= 前缀)
        match = re.search(r'(\d+(?:\.\d+)?)\s*(?:ms|毫秒)', unified, re.IGNORECASE)
        if match:
            return True, match.group(1)

        # 策略4: 匹配 Windows 英文平均时间行 Average = XXms
        match = re.search(r'average\s*=\s*(\d+(?:\.\d+)?)\s*ms', unified, re.IGNORECASE)
        if match:
            return True, match.group(1)

        # 判断常见失败原因
        lower = unified.lower()
        if any(k in lower for k in ['timeout', 'timed out', '请求超时', 'time out']):
            return False, "超时"
        if any(k in lower for k in ['unreachable', '无法访问', 'destination host unreachable', 'unreachable']):
            return False, "不可达"
        if any(k in lower for k in ['unknown host', '找不到主机', 'could not find', 'ping request could not find']):
            return False, "解析失败"
        if result.returncode != 0:
            return False, "失败"

        return False, "未知"
    except subprocess.TimeoutExpired:
        return False, "超时"
    except FileNotFoundError:
        return False, "无ping命令"
    except Exception as e:
        return False, f"错误:{str(e)}"


def get_multi_ping_times(nodes, timeout=2):
    """批量获取多个节点的ping延迟

    :param nodes: 节点列表，如 ["www.baidu.com", "8.8.8.8"]
    :param timeout: 单个节点超时秒数
    :return: [(节点名, 成功, 结果), ...]
    """
    results = []
    for node in nodes:
        node = node.strip()
        if not node:
            results.append((node, False, "空"))
            continue
        ok, val = get_ping_time(node, timeout)
        results.append((node, ok, val))
    return results
