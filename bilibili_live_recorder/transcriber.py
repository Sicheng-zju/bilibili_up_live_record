# bilibili_live_recorder/transcriber.py
import os
import subprocess
import time
from .config import SUBTITLE_METHOD, OPENAI_API_KEY, OPENAI_API_BASE_URL, OPENAI_MODEL, LOCAL_WHISPER_MODEL
from .logger import log_info, log_error

class Transcriber:
    def __init__(self):
        self.output_srt = None
        
    def generate_subtitle(self, video_path):
        """
        Extract audio from video file and transcribe it to SRT.
        Args:
            video_path (str): Path to the video file.
        Returns:
            bool: True if successful, False otherwise.
        """
        log_info(f"开始为视频生成字幕: {video_path}", console=True)
        
        # 1. Check file existence
        if not os.path.exists(video_path):
            log_error(f"视频文件不存在: {video_path}")
            return False
            
        base_name = os.path.splitext(video_path)[0]
        # 修改: 音频文件不再作为临时文件，而是保留下来
        audio_path = f"{base_name}.mp3"
        srt_path = f"{base_name}.srt"
        
        if os.path.exists(srt_path):
            log_info(f"字幕文件已存在，跳过生成: {srt_path}")
            return True

        # 2. Extract Audio using FFmpeg
        # 如果音频文件不存在，则提取
        if not os.path.exists(audio_path):
            log_info(f"正在提取音频...", console=True)
            try:
                # -vn: disable video, -acodec libmp3lame: convert to mp3, -q:a 4: quality level
                cmd = [
                    "ffmpeg", "-y", "-i", video_path, 
                    "-vn", "-acodec", "libmp3lame", "-q:a", "4",
                    audio_path
                ]
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                log_error(f"提取音频失败: {e}", console=True)
                return False
        else:
             log_info(f"音频文件已存在，跳过提取: {audio_path}", console=True)

        # 3. Transcribe Audio
        try:
            log_info(f"正在通过 {SUBTITLE_METHOD} 转写音频...", console=True)
            srt_content = ""
            
            if SUBTITLE_METHOD == "openai_api":
                srt_content = self._transcribe_api(audio_path)
            elif SUBTITLE_METHOD == "local_whisper":
                srt_content = self._transcribe_local(audio_path)
            else:
                log_error(f"未知的字幕生成方式: {SUBTITLE_METHOD}")
                return False
                
            if srt_content:
                with open(srt_path, 'w', encoding='utf-8') as f:
                    f.write(srt_content)
                log_info(f"字幕生成成功: {srt_path}", color=True)
                return True
            else:
                log_error("未能获取字幕内容。")
                return False

        except Exception as e:
            log_error(f"字幕生成过程中出错: {e}", console=True)
            return False
        # finally block removed to keep audio file

    def _transcribe_api(self, audio_path):
        try:
            from openai import OpenAI
        except ImportError:
            log_error("未安装 openai 库。请运行 `pip install openai`")
            return None

        if "YOUR_API_KEY_HERE" in OPENAI_API_KEY:
            log_error("请先在 config.py 中通过 OPENAI_API_KEY 配置你的 API Key！")
            return None

        if len(OPENAI_API_KEY) < 10:
             log_error("未配置有效的 OpenAI API Key。")
             return None

        try:
            client = OpenAI(
                api_key=OPENAI_API_KEY,
                base_url=OPENAI_API_BASE_URL
            )
            
            log_info("正在调用 OpenAI API...", console=False)
            
            # Whisper API format: response_format="srt" returns SRT text directly
            with open(audio_path, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    model=OPENAI_MODEL, 
                    file=audio_file,
                    response_format="srt"
                )
            
            # OpenAI python lib returns the string content directly when response_format="srt"
            return transcription
        except Exception as e:
            log_error(f"OpenAI API 调用失败: {e}")
            return None

    def _transcribe_local(self, audio_path):
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            log_error("未安装 faster-whisper 库。请运行 `pip install faster-whisper`")
            return None
            
        try:
            # 禁用 HuggingFace Hub 的 Symlink 警告
            os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
            
            log_info(f"加载本地模型: {LOCAL_WHISPER_MODEL} ...", console=False)
            
            # detect device: cuda or cpu
            # 如果安装了 torch，我们可以通过 torch 检查是否存在 CUDA
            # 如果没安装 torch，faster-whisper (ctranslate2) 依赖本地的 CUDA/cuDNN 库
            device = "cpu"
            try:
                import torch
                if torch.cuda.is_available():
                    device = "cuda"
                    log_info("检测到 CUDA 设备，将使用 GPU 加速。", console=True)
                else:
                    log_info("未检测到 CUDA 设备或 Torch未启用CUDA，将使用 CPU 进行转写 (速度较慢)。", console=True)
            except ImportError:
                 # 未安装 torch，尝试让 ctranslate2 自动检测
                 device = "auto"
                 log_info("未检测到 torch，尝试自动选择设备...", console=True)

            log_info(f"正在初始化模型 (Device: {device}, Compute: int8)...", console=False)
            
            try:
                model = WhisperModel(LOCAL_WHISPER_MODEL, device=device, compute_type="int8")
            except ValueError as ve:
                # 如果指定 cuda 但失败了（例如缺少 cuBLAS/cuDNN 库），回退到 cpu
                if "cuda" in str(ve).lower() or device == "cuda":
                    log_error(f"GPU 初始化失败 ({ve})，尝试回退到 CPU...", console=True)
                    model = WhisperModel(LOCAL_WHISPER_MODEL, device="cpu", compute_type="int8")
                else:
                    raise ve

            segments, info = model.transcribe(audio_path, beam_size=5)
            
            log_info(f"检测到语言: {info.language} (置信度: {info.language_probability})", console=False)
            
            # Convert segments to SRT format
            srt_str = ""
            for i, segment in enumerate(segments, start=1):
                start = self._format_timestamp(segment.start)
                end = self._format_timestamp(segment.end)
                text = segment.text.strip()
                srt_str += f"{i}\n{start} --> {end}\n{text}\n\n"
                
            return srt_str
            
        except Exception as e:
            log_error(f"本地模型运行失败: {e}")
            return None

    def _format_timestamp(self, seconds):
        """Convert seconds to SRT timestamp format (HH:MM:SS,mmm)"""
        whole_seconds = int(seconds)
        milliseconds = int((seconds - whole_seconds) * 1000)
        
        hours = whole_seconds // 3600
        minutes = (whole_seconds % 3600) // 60
        secs = whole_seconds % 60
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
