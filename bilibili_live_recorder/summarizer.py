# bilibili_live_recorder/summarizer.py
import os
import time
import requests
import json
from .config import GENERATE_SUMMARY, SUMMARY_API_KEY, SUMMARY_API_BASE_URL, SUMMARY_MODEL, SUMMARY_PROMPT
from .logger import log_info, log_error

class Summarizer:
    def __init__(self):
        pass

    def summarize(self, output_file_path, srt_content=None, danmaku_content=None, up_info=None):
        """
        生成直播总结
        output_file_path: 视频文件或合并文件路径，将作为基准生成 _summary.txt
        srt_content: 字幕文本内容
        danmaku_content: 弹幕文本内容
        up_info: 一个字典，包含 up_name, title, date 等
        """
        if not GENERATE_SUMMARY:
            return False

        log_info(f"开始生成直播总结: {output_file_path}", console=True)
        
        base_name = os.path.splitext(output_file_path)[0]
        summary_path = f"{base_name}_summary.txt"
        
        if os.path.exists(summary_path):
            log_info(f"总结文件已存在，跳过: {summary_path}")
            return True

        # 如果没有直接提供 srt_content，尝试读取对应的 .srt 文件
        if not srt_content:
            srt_file = f"{base_name}.srt"
            if os.path.exists(srt_file):
                srt_content = self._read_srt_text(srt_file)
            else:
                log_info("未找到字幕文件，将尝试仅通过弹幕进行总结（如果有）。")

        # 尝试读取弹幕文件
        if not danmaku_content:
            # 尝试根据 base_name 猜测弹幕文件名
            # 通常弹幕文件名包含 _danmaku.txt
            # 如果是 merged 文件，可能名字叫 _merged.mp4，而弹幕是 _danmaku.txt
            # main.py 的逻辑中，_merge_and_clean 可能会清理源文件，但丹幕文件通常是单独保存的
            # 我们这里做一个简单的模式匹配尝试
            # 假设 base_name = "xxx_merged"，我们要找 "xxx_danmaku.txt" 或者就在同目录下找txt
            
            # 最简单的策略：尝试同名替换 _merged 为 _danmaku 或直接看同名txt
            dm_path1 = output_file_path.replace("_merged", "") + "_danmaku.txt"
            dm_path2 = output_file_path.replace("_merged", "") + ".txt"
            dm_path3 = base_name + ".txt"
            
            target_dm = None
            for p in [dm_path1, dm_path2, dm_path3]:
                if os.path.exists(p):
                    target_dm = p
                    break
            
            if target_dm:
                danmaku_content = self._read_file_head_tail(target_dm, max_lines=1000) # 取弹幕摘要防止过长
            
        if not srt_content and not danmaku_content:
            log_error("无法获取字幕或弹幕内容，无法生成总结。")
            return False
            
        # 构建 Prompt
        full_content = f"直播概况:\n"
        if up_info:
            full_content += f"UP主: {up_info.get('up_name', '未知')}\n"
            full_content += f"标题: {up_info.get('title', '未知')}\n"
            full_content += f"时间: {up_info.get('date', '未知')}\n\n"
            
        if srt_content:
            # 截断过长的字幕，保留核心部分
            # 对于很长的直播，可能需要更智能的切分，这里简单截取前 15000 字符 + 后 5000 字符
            if len(srt_content) > 20000:
                srt_content = srt_content[:15000] + "\n...(中间内容省略)...\n" + srt_content[-5000:]
            full_content += f"=== 直播字幕内容 (SRT提取) ===\n{srt_content}\n\n"
            
        if danmaku_content:
            full_content += f"=== 观众弹幕互动 (精选) ===\n{danmaku_content}\n"
            
        # 调用 API
        summary_text = self._call_llm_api(full_content)
        
        if summary_text:
            try:
                with open(summary_path, 'w', encoding='utf-8') as f:
                    f.write(summary_text)
                log_info(f"直播总结生成成功: {summary_path}", color=True)
                return True
            except Exception as e:
                log_error(f"写入总结文件失败: {e}")
                return False
        return False

    def _read_srt_text(self, srt_path):
        """只提取字幕文本，忽略时间轴"""
        text_lines = []
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            is_time_line = False
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if line.isdigit():
                    continue
                if '-->' in line:
                    continue
                text_lines.append(line)
            return "\n".join(text_lines)
        except Exception as e:
            log_error(f"读取 SRT 文件失败: {e}")
            return None

    def _read_file_head_tail(self, file_path, max_lines=500):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            if len(lines) <= max_lines:
                return "".join(lines)
            
            # 取头尾
            head = lines[:max_lines//2]
            tail = lines[-max_lines//2:]
            return "".join(head) + "\n...(中间弹幕省略)...\n" + "".join(tail)
        except Exception as e:
            log_error(f"读取文件失败: {file_path}")
            return None

    def _call_llm_api(self, user_content):
        if not SUMMARY_API_KEY:
            log_error("未配置 SUMMARY_API_KEY，无法调用 LLM。")
            return None

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {SUMMARY_API_KEY}"
        }
        
        data = {
            "model": SUMMARY_MODEL,
            "messages": [
                {"role": "system", "content": SUMMARY_PROMPT},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.7
        }
        
        try:
            log_info(f"正在请求 LLM ({SUMMARY_MODEL}) 进行总结...", console=True)
            response = requests.post(f"{SUMMARY_API_BASE_URL}/chat/completions", headers=headers, json=data, timeout=120)
            
            if response.status_code == 200:
                res_json = response.json()
                content = res_json['choices'][0]['message']['content']
                return content
            else:
                log_error(f"LLM 请求失败: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            log_error(f"调用 LLM 接口异常: {e}")
            return None
