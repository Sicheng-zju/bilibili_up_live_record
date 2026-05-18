# bilibili_live_recorder/logger.py

import logging
import os
import sys
from datetime import datetime
from colorama import Fore, Style

# 创建 logs 目录
if not os.path.exists('logs'):
    os.makedirs('logs')

class _ConsoleOnlyFilter(logging.Filter):
    def filter(self, record):
        return bool(getattr(record, 'console', True))


class _ColorConsoleFormatter(logging.Formatter):
    def format(self, record):
        msg = super().format(record)
        color = getattr(record, 'color', None)
        if color:
            return f"{color}{msg}{Style.RESET_ALL}"
        if record.levelno >= logging.ERROR:
            return f"{Fore.RED}{msg}{Style.RESET_ALL}"
        if record.levelno >= logging.WARNING:
            return f"{Fore.YELLOW}{msg}{Style.RESET_ALL}"
        return msg


# 配置 logger
logger = logging.getLogger('BiliRecorder')
logger.setLevel(logging.INFO)
logger.propagate = False

# 避免多进程/重复导入时重复添加 handler
if not logger.handlers:
    # 文件处理器 - 记录所有详细信息
    file_handler = logging.FileHandler(
        filename=f'logs/recorder_{datetime.now().strftime("%Y%m%d")}.log',
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)

    # 控制台处理器 - 同步输出，格式与文件一致
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(_ColorConsoleFormatter('%(asctime)s - %(levelname)s - %(message)s'))
    stream_handler.addFilter(_ConsoleOnlyFilter())

    # 添加处理器
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

def log_info(message, console=True, color=None):
    """
    记录 INFO 级别日志，并可选输出到控制台
    :param message: 日志内容
    :param console: 是否输出到控制台
    :param color: 控制台输出颜色 (colorama.Fore.COLOR)
    """
    logger.info(message, extra={'console': console, 'color': color})

def log_warning(message, console=True):
    logger.warning(message, extra={'console': console})

def log_error(message, console=True):
    logger.error(message, extra={'console': console})

def log_debug(message):
    # debug 信息默认不输出到控制台，只记录文件
    logger.debug(message)
