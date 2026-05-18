import subprocess
import os
import time
import glob
from datetime import datetime
from .config import DEFAULT_SAVE_PATH, SEGMENT_TIME
from .logger import log_info, log_error, log_warning

class Recorder:
    def __init__(self, room_id, up_name):
        self.room_id = room_id
        self.up_name = up_name
        self.recording_process = None
        self.ffmpeg_log_handle = None
        self.save_dir = os.path.join(DEFAULT_SAVE_PATH, f"{up_name}_{room_id}")
        self.current_prefix = None
        self.process_start_time = None
        self.last_progress_time = None
        self.last_observed_file = None
        self.last_observed_size = None
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)


    def start_recording(self, stream_url):
        # 必须确保 timestamp 是文件名安全和有效的
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_prefix = os.path.join(self.save_dir, f"{self.up_name}_{timestamp_str}")
        
        # 不要在这里加 .flv，segment 也会处理扩展名，但为了明确我们还是给完整 pattern
        # 使用 %03d 让分段文件有序，如: up_name_20231027_120000_000.flv
        filename_pattern = f"{self.current_prefix}_%03d.flv"

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

        log_info(f"正在启动 FFmpeg，保存到: {self.save_dir}", console=True)
        log_info(f"分段时长: {SEGMENT_TIME} 秒", console=True)

        try:
            ffmpeg_log_path = os.path.join(self.save_dir, f"{self.up_name}_{timestamp_str}_ffmpeg.log")
            self.ffmpeg_log_handle = open(ffmpeg_log_path, 'a', encoding='utf-8', buffering=1)

            # 启动 ffmpeg 进程
            self.recording_process = subprocess.Popen(
                cmd, 
                stdout=subprocess.DEVNULL, # 隐藏大量输出
                stderr=self.ffmpeg_log_handle
            )
            self.process_start_time = time.time()
            self.last_progress_time = self.process_start_time
            self.last_observed_file = None
            self.last_observed_size = None
            log_info(f"FFmpeg 诊断日志: {ffmpeg_log_path}", console=False)
            return True
        except FileNotFoundError:
            log_error("未找到 ffmpeg。请确保已安装 ffmpeg 并添加到系统环境变量中。", console=True)
            return False
        except Exception as e:
            log_error(f"录制启动失败: {e}", console=True)
            return False
            
    def stop_recording(self):
        if self.recording_process:
            self.recording_process.terminate()
            try:
                # 延长等待时间，给 ffmpeg 更多时间正常收尾
                self.recording_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.recording_process.kill()
            log_info("录制已停止", console=True)
            self.recording_process = None

        if self.ffmpeg_log_handle:
            try:
                self.ffmpeg_log_handle.close()
            except Exception:
                pass
            self.ffmpeg_log_handle = None

        self.current_prefix = None
        self.process_start_time = None
        self.last_progress_time = None
        self.last_observed_file = None
        self.last_observed_size = None

    def is_recording(self):
        if self.recording_process:
            return self.recording_process.poll() is None
        return False

    def _get_latest_segment_file(self):
        if not self.current_prefix:
            return None

        pattern = f"{self.current_prefix}_*.flv"
        files = glob.glob(pattern)
        if not files:
            return None
        return max(files, key=os.path.getmtime)

    def get_health_status(self, idle_timeout=120):
        """
        录制健康检查。
        返回: (is_healthy, reason)
        """
        if not self.is_recording():
            return False, "ffmpeg 进程已退出"

        now = time.time()
        latest_file = self._get_latest_segment_file()

        # 刚启动阶段可能还没有生成第一个分段文件
        if not latest_file:
            if self.process_start_time and now - self.process_start_time <= idle_timeout:
                return True, "启动预热中"
            return False, "长时间未生成任何分段文件"

        try:
            latest_size = os.path.getsize(latest_file)
        except OSError as e:
            return False, f"读取分段文件状态失败: {e}"

        # 分段文件发生轮换(例如 _000 -> _001)也算进展
        if self.last_observed_file is None or latest_file != self.last_observed_file:
            self.last_observed_file = latest_file
            self.last_observed_size = latest_size
            self.last_progress_time = now
            return True, f"分段轮换: {os.path.basename(latest_file)}"

        # 文件字节有增长，认为健康
        if self.last_observed_size is None or latest_size > self.last_observed_size:
            self.last_observed_file = latest_file
            self.last_observed_size = latest_size
            self.last_progress_time = now
            return True, "分段持续写入中"

        # 文件没有增长，短时间内先容忍
        stalled_for = now - (self.last_progress_time or self.process_start_time or now)
        if stalled_for <= idle_timeout:
            return True, f"短时无增长({int(stalled_for)}秒)，等待恢复"

        # 文件无变化超过阈值
        return False, f"录制无数据更新已超过 {int(stalled_for)} 秒"
