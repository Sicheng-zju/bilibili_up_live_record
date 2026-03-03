import os
import subprocess
import re
from .config import DEFAULT_SAVE_PATH
from colorama import Fore, Style

class Merger:
    def __init__(self):
        pass

    def get_recording_dirs(self):
        """获取所有录制目录"""
        if not os.path.exists(DEFAULT_SAVE_PATH):
            return []
        dirs = [d for d in os.listdir(DEFAULT_SAVE_PATH) if os.path.isdir(os.path.join(DEFAULT_SAVE_PATH, d))]
        return dirs

    def get_segments(self, dir_path):
        """
        在指定目录下查找可以合并的视频分段。
        返回一个字典: { 'UpName_Timestamp': [file1_fullpath, file2_fullpath, ...] }
        """
        if not os.path.exists(dir_path):
            return {}

        files = [f for f in os.listdir(dir_path) if f.endswith('.flv') or f.endswith('.mp4')]
        files.sort() # 按文件名排序，保证分段顺序正确

        groups = {}
        # 匹配: 任意前缀 + _ + 3位数字分段号 + .flv/.mp4
        # 例如: my_up_20230101_120000_000.flv -> group: my_up_20230101_120000
        pattern = re.compile(r"(.+)_(\d{3})\.(flv|mp4)$")

        for f in files:
            match = pattern.match(f)
            if match:
                base_name = match.group(1) # UpName_Timestamp
                
                if base_name not in groups:
                    groups[base_name] = []
                
                full_path = os.path.join(dir_path, f)
                groups[base_name].append(full_path)
        
        return groups

    def merge_segments(self, output_file_path, file_list):
        """
        使用 ffmpeg concat demuxer 合并文件
        """
        if not file_list:
            print(Fore.RED + "没有文件可合并" + Style.RESET_ALL)
            return False

        output_dir = os.path.dirname(output_file_path)
        list_txt_path = os.path.join(output_dir, "concat_list.txt")

        try:
            # 生成 list.txt
            with open(list_txt_path, 'w', encoding='utf-8') as f:
                for file_path in file_list:
                    # ffmpeg concat list 需要 absolute path，Windows下可能需要转义
                    abs_path = os.path.abspath(file_path).replace("\\", "/")
                    f.write(f"file '{abs_path}'\n")
            
            print(Fore.CYAN + f"正在合并 {len(file_list)} 个分段到 {os.path.basename(output_file_path)} ..." + Style.RESET_ALL)

            # ffmpeg command
            # -f concat -safe 0 -i list.txt -c copy output.mp4
            cmd = [
                "ffmpeg",
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", list_txt_path,
                "-c", "copy", # 流复制，速度快且无损
                output_file_path
            ]
            
            # 使用 subprocess.run 等待完成
            process = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL, # 隐藏大部分输出
                stderr=subprocess.PIPE     # 捕获错误输出，但如果不报错就不打印
            )

            if process.returncode == 0:
                print(Fore.GREEN + "合并成功！" + Style.RESET_ALL)
                ret = True
            else:
                print(Fore.RED + "合并失败！" + Style.RESET_ALL)
                print(process.stderr.decode('utf-8', errors='ignore')) # 打印 ffmpeg 错误信息
                ret = False

            # 清理 list.txt
            if os.path.exists(list_txt_path):
                os.remove(list_txt_path)
            
            return ret

        except Exception as e:
            print(Fore.RED + f"合并过程出错: {e}" + Style.RESET_ALL)
            return False
