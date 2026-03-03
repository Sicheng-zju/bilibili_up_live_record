import subprocess
import os
import time
from datetime import datetime
from .config import DEFAULT_SAVE_PATH, SEGMENT_TIME

class Recorder:
    def __init__(self, room_id, up_name):
        self.room_id = room_id
        self.up_name = up_name
        self.recording_process = None
        self.save_dir = os.path.join(DEFAULT_SAVE_PATH, f"{up_name}_{room_id}")
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)


    def start_recording(self, stream_url):
        # 必须确保 timestamp 是文件名安全和有效的
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 不要在这里加 .flv，segment 也会处理扩展名，但为了明确我们还是给完整 pattern
        # 使用 %03d 让分段文件有序，如: up_name_20231027_120000_000.flv
        filename_pattern = os.path.join(self.save_dir, f"{self.up_name}_{timestamp_str}_%03d.flv")

        # 确保目录存在
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)

        # ffmpeg 命令
        # -y: 覆盖输出文件 (对于分段来说是指如果不小心重名)
        # -i: 输入流地址
        # -c copy: 直接复制流，不转码 (CPU占用低)
        # -f segment: 开启分段功能
        # -segment_time: 分段时长 (秒)
        # -reset_timestamps 1: 重置每个分段的时间戳，方便播放器播放
        
        # -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5: 尝试自动重连 (针对 HTTP/HTTPS 流)
        # -rw_timeout 15000000: 设置读写超时为 15 秒 (单位微秒)，防止卡死
        
        # 为了提高稳定性，增加 buffer 和重连参数
        # -bufsize 5000k : 增加缓冲区
        # -max_reload 1000 : 增加允许重载次数
        
        cmd = [
            "ffmpeg",
            "-y",
            "-headers", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36\r\nReferer: https://live.bilibili.com/\r\nOrigin: https://live.bilibili.com\r\n",
            "-rw_timeout", "15000000",
            "-reconnect", "1", 
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5",
            "-i", stream_url,
            "-c", "copy",
            "-f", "segment",
            "-segment_time", str(SEGMENT_TIME),
            "-reset_timestamps", "1",
            filename_pattern
        ]

        print(f"正在启动 FFmpeg，保存到: {self.save_dir}")
        print(f"分段时长: {SEGMENT_TIME} 秒")

        try:
            # 启动 ffmpeg 进程
            self.recording_process = subprocess.Popen(
                cmd, 
                stdout=subprocess.DEVNULL, # 隐藏大量输出
                stderr=subprocess.STDOUT   # 合并 stderr 到 stdout
            )
            return True
        except FileNotFoundError:
            print("错误: 未找到 ffmpeg。请确保已安装 ffmpeg 并添加到系统环境变量中。")
            return False
        except Exception as e:
            print(f"录制启动失败: {e}")
            return False
            
    def stop_recording(self):
        if self.recording_process:
            self.recording_process.terminate()
            try:
                # 延长等待时间，给 ffmpeg 更多时间正常收尾
                self.recording_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.recording_process.kill()
            print("录制已停止")
            self.recording_process = None

    def is_recording(self):
        if self.recording_process:
            return self.recording_process.poll() is None
        return False
