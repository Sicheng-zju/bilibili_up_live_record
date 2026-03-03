# bilibili_live_recorder/logger.py

import logging
import os
import sys
from datetime import datetime
from colorama import Fore, Style

# 创建 logs 目录
if not os.path.exists('logs'):
    os.makedirs('logs')

# 配置 logger
logger = logging.getLogger('BiliRecorder')
logger.setLevel(logging.INFO)

# 文件处理器 - 记录所有详细信息
file_handler = logging.FileHandler(
    filename=f'logs/recorder_{datetime.now().strftime("%Y%m%d")}.log',
    encoding='utf-8'
)
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

# 添加处理器
logger.addHandler(file_handler)

def log_info(message, console=True, color=None):
    """
    记录 INFO 级别日志，并可选输出到控制台
    :param message: 日志内容
    :param console: 是否输出到控制台
    :param color: 控制台输出颜色 (colorama.Fore.COLOR)
    """
    logger.info(message)
    if console:
        if color:
            print(f"{color}{message}{Style.RESET_ALL}")
        else:
            print(message)

def log_warning(message, console=True):
    logger.warning(message)
    if console:
        print(f"{Fore.YELLOW}[警告] {message}{Style.RESET_ALL}")

def log_error(message, console=True):
    logger.error(message)
    if console:
        print(f"{Fore.RED}[错误] {message}{Style.RESET_ALL}")

def log_debug(message):
    # debug 信息默认不输出到控制台，只记录文件
    logger.debug(message)
