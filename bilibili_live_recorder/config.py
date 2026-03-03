# 配置文件

# 默认录制保存路径
DEFAULT_SAVE_PATH = "Recordings"

# 检查直播状态间隔（秒）
CHECK_INTERVAL = 30 # 每30秒检查一次

# 直播分段时长（秒），例如 3600 秒（1小时）分段一次
SEGMENT_TIME = 900 

import random
import uuid

def get_random_buvid():
    return str(uuid.uuid4()) + "infoc"

# User-Agent
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://live.bilibili.com/",
    "Origin": "https://live.bilibili.com",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
}
