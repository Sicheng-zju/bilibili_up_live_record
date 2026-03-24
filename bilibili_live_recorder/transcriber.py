# bilibili_live_recorder/transcriber.py
import os
import subprocess
import time
import gc
import shutil
import glob
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
                if srt_content:
                    with open(srt_path, 'w', encoding='utf-8') as f:
                        f.write(srt_content)
                    log_info(f"字幕生成成功: {srt_path}", color=True)
                    return True
                else:
                    log_error("未能获取字幕内容。")
                    return False
            elif SUBTITLE_METHOD == "local_whisper":
                # 本地模型改为流式写入，防止长时间运行后无结果
                if self._transcribe_local(audio_path, srt_path):
                    log_info(f"字幕生成成功: {srt_path}", color=True)
                    return True
                else:
                    return False
            else:
                log_error(f"未知的字幕生成方式: {SUBTITLE_METHOD}")
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

    def _transcribe_local(self, audio_path, srt_path):
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            log_error("未安装 faster-whisper 库。请运行 `pip install faster-whisper`")
            return False
            
        try:
            # 禁用 HuggingFace Hub 的 Symlink 警告
            os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
            
            log_info(f"加载本地模型: {LOCAL_WHISPER_MODEL} ...", console=False)
            
            # detect device: cuda or cpu
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

            print(f"  已生成 {segment_count} 条字幕 (完成)")
            
            # 由于在独立子进程中运行，进程结束时会自动释放显存
            return True
            
        except Exception as e:
            log_error(f"本地模型运行失败: {e}", console=True)
            import traceback
            traceback.print_exc()
            return False

    def _split_and_transcribe(self, model, audio_path, srt_path):
        """
        处理大文件：分割 -> 转写 -> 合并 -> 清理
        """
        temp_dir = os.path.join(os.path.dirname(audio_path), f"temp_split_{int(time.time())}")
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
            
        try:
            # 1. Split audio
            # Segment duration: 900s (15min). -c copy for mp3 is lossy-boundary safe enough for speech.
            # Using -f segment.
            log_info("文件较大，正在分割音频以提高转写稳定性...", console=True)
            part_pattern = os.path.join(temp_dir, "part_%03d.mp3")
            cmd = [
                "ffmpeg", "-y", "-i", audio_path, 
                "-f", "segment", "-segment_time", "900", 
                "-c", "copy", part_pattern
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # 2. Transcribe parts
            parts = sorted(glob.glob(os.path.join(temp_dir, "part_*.mp3")))
            if not parts:
                log_error("音频分割失败，未找到分段文件。", console=True)
                return False
                
            log_info(f"音频已分割为 {len(parts)} 个片段，开始逐个转写...", console=True)
            
            global_offset = 0.0
            segment_count = 0
            
            with open(srt_path, "w", encoding="utf-8") as f_out:
                for idx, part_file in enumerate(parts):
                    print(f"  正在处理片段 {idx+1}/{len(parts)} ...", end='\r')
                    
                    # 关键配置: condition_on_previous_text=False 防止死循环复读
                    # vad_filter=True 过滤静音
                    segments, info = model.transcribe(
                        part_file, 
                        beam_size=5, 
                        vad_filter=True, 
                        condition_on_previous_text=False
                    )
                    
                    # 写入当前分段的字幕
                    for segment in segments:
                        segment_count += 1
                        # 时间戳需要加上之前的总时长
                        start_time = segment.start + global_offset
                        end_time = segment.end + global_offset
                        
                        start_str = self._format_timestamp(start_time)
                        end_str = self._format_timestamp(end_time)
                        text = segment.text.strip()
                        
                        f_out.write(f"{segment_count}\n{start_str} --> {end_str}\n{text}\n\n")
                        f_out.flush()
                    
                    # 更新偏移量 (使用 info.duration 获取准确的片段时长)
                    global_offset += info.duration
            
            print(f"  转写完成，共生成 {segment_count} 条字幕。")
            return True
        
        except Exception as e:
            log_error(f"分段转写过程中出错: {e}", console=True)
            return False
        finally:
            # Cleanup
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _transcribe_local(self, audio_path, srt_path):
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            log_error("未安装 faster-whisper 库。请运行 `pip install faster-whisper`")
            return False
            
        try:
            # 禁用 HuggingFace Hub 的 Symlink 警告
            os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
            
            log_info(f"加载本地模型: {LOCAL_WHISPER_MODEL} ...", console=False)
            
            # detect device: cuda or cpu
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

            log_info("开始转写...", console=True)
            
            # 检查文件大小，如果大于 50MB (约 1小时 mp3 128kbps = 56MB)，则使用分段处理
            # 为了保险起见，或者响应用户需求，可以默认大文件都切。
            # 这里设定阈值为 20MB (约20分钟)
            file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
            if file_size_mb > 20:
                return self._split_and_transcribe(model, audio_path, srt_path)
            else:
                # 小文件直接处理，但也加上稳定性参数
                segments, info = model.transcribe(
                    audio_path, 
                    beam_size=5,
                    vad_filter=True, # 开启 VAD 过滤静音
                    condition_on_previous_text=False # 防止死循环复读
                )
                
                log_info(f"检测到语言: {info.language} (置信度: {info.language_probability})", console=False)
                
                with open(srt_path, "w", encoding="utf-8") as f:
                    segment_count = 0
                    for i, segment in enumerate(segments, start=1):
                        start = self._format_timestamp(segment.start)
                        end = self._format_timestamp(segment.end)
                        text = segment.text.strip()
                        
                        f.write(f"{i}\n{start} --> {end}\n{text}\n\n")
                        f.flush()
                        
                        segment_count = i
                        if segment_count % 10 == 0:
                            print(f"  已生成 {segment_count} 条字幕...", end='\r')
                
                print(f"  已生成 {segment_count} 条字幕 (完成)")
                return True
            
        except Exception as e:
            log_error(f"本地模型运行失败: {e}", console=True)
            return False

    def _format_timestamp(self, seconds):
        """Convert seconds to SRT timestamp format (HH:MM:SS,mmm)"""
        whole_seconds = int(seconds)
        milliseconds = int((seconds - whole_seconds) * 1000)
        
        hours = whole_seconds // 3600
        minutes = (whole_seconds % 3600) // 60
        secs = whole_seconds % 60
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"
