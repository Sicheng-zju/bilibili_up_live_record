# 配置文件

# 默认录制保存路径
DEFAULT_SAVE_PATH = "Recordings"

# 检查直播状态间隔（秒）
CHECK_INTERVAL = 30 # 每30秒检查一次

# 直播分段时长（秒），例如 3600 秒（1小时）分段一次
SEGMENT_TIME = 900 

# 直播结束后是否自动合并分段视频
AUTO_MERGE_AFTER_STREAM = True

# 合并完成后是否自动删除分段视频
DELETE_SEGMENTS_AFTER_MERGE = True

# 是否录制弹幕
RECORD_DANMAKU = True

# ========== 字幕生成设置 (OpenAI API / Local Whisper) ==========
# 是否直播结束后自动生成字幕
GENERATE_SUBTITLES = True

# 字幕生成方式: "local_whisper" (本地模型, 推荐, 需安装 faster-whisper) 或 "openai_api" (需API Key)
SUBTITLE_METHOD = "local_whisper"

# OpenAI API 设置 (如果是使用 ChatGPT 或类似兼容接口)
OPENAI_API_KEY = "sk-YOUR_API_KEY_HERE"
OPENAI_API_BASE_URL = "https://api.openai.com/v1" # 可以改为国内中转API地址
OPENAI_MODEL = "whisper-1"

# 本地 Whisper 模型大小: "tiny", "base", "small", "medium", "large-v3"
# 注意: medium/large 需要较好的显卡 (GPU)
LOCAL_WHISPER_MODEL = "large"

# ========== 自动摘要设置 (LLM) ==========
# 是否合并/字幕生成后自动总结直播内容
GENERATE_SUMMARY = True

# 摘要生成使用的 API 设置 (兼容 OpenAI 格式，可填 ChatGPT, DeepSeek, Ollama, LM Studio 等)
# 若使用本地 LLM (如 Ollama)，Base URL 通常为 "http://localhost:11434/v1"
SUMMARY_API_KEY = "sk-YOUR_API_KEY_HERE"
SUMMARY_API_BASE_URL = "https://api.deepseek.com" # 这是deepseek的 Base URL
SUMMARY_MODEL = "deepseek-chat" # 或本地模型名，如 "llama3"

# 摘要提示词 (Prompt)，可自定义
SUMMARY_PROMPT = """
你是一个专业的直播内容总结助手。请根据提供的直播字幕内容(SRT)和部分弹幕内容(如果有)，生成一份详细的直播内容总结。
重点关注：直播的主要话题、有趣的互动、关键事件以及观众的反应。
请按以下格式输出：
1. 直播主题概览
2. 时间轴/关键节点 (如能提取)
3. 详细内容回顾
4. 观众互动亮点
"""
# ==========================================================

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
