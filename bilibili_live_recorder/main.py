# bilibili_live_recorder/main.py

import sys
import time
import os
import signal
import threading
from colorama import init, Fore, Style
from .bilibili_api import BilibiliAPI
from .recorder import Recorder
from .config import CHECK_INTERVAL, DEFAULT_SAVE_PATH, AUTO_MERGE_AFTER_STREAM, DELETE_SEGMENTS_AFTER_MERGE, SEGMENT_TIME, RECORD_DANMAKU
from .merger import Merger
from .logger import log_info, log_error, log_warning
from .danmaku import DanmakuRecorder
from .transcriber import Transcriber
from .config import GENERATE_SUBTITLES, SUBTITLE_METHOD, OPENAI_API_KEY, OPENAI_API_BASE_URL, OPENAI_MODEL, LOCAL_WHISPER_MODEL

# 初始化 colorama
init()

def signal_handler(sig, frame):
    log_info("\n程序正在退出...", color=Fore.YELLOW)
    # 这里可以添加清理逻辑
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

def get_input_uid():
    """获取用户输入的有效 UID 或 URL"""
    while True:
        user_input = input(Fore.CYAN + "请输入 Bilibili UP 主的个人主页 URL 或 UID (输入 q 退出): " + Style.RESET_ALL).strip()
        if not user_input:
            continue
        
        if user_input.lower() == 'q':
            sys.exit(0)
        
        if user_input.isdigit():
            return user_input
        
        uid = BilibiliAPI.get_uid_from_url(user_input)
        if uid:
            return uid
        
        print(Fore.RED + "无法解析输入，请重试。" + Style.RESET_ALL)

def print_up_info(info):
    """显示 UP 主信息"""
    print("\n" + Fore.GREEN + "="*30)
    print(f"找到 UP 主: {info['name']}")
    print(f"直播间 ID: {info['room_id']}")
    print(f"当前状态: {'🔴 直播中' if info['is_live'] else '⚪ 未直播'}")
    print(f"直播标题: {info['title']}")
    print("="*30 + Style.RESET_ALL + "\n")
    log_info(f"目标确认: {info['name']} (RoomID: {info['room_id']})", console=False)

def _merge_and_clean(merger, dir_path, base_name, file_list):
    """
    具体的合并与清理逻辑
    """
    output_file = os.path.join(dir_path, f"{base_name}_merged.mp4")
    
    if os.path.exists(output_file):
         print(Fore.YELLOW + f"  跳过: {base_name} (已存在合并文件)" + Style.RESET_ALL)
         # 即使已存在，如果是自动合并任务，也可能需要补生成字幕
         # 但为了避免重复处理，这里我们只对新生成的文件或者明确需要处理的进行字幕生成
         # 如果用户需要手动生成字幕，可能需要单独的菜单项，这里暂且只在合并成功后生成
         return False
         
    print(f"  正在处理: {base_name} ...")
    success = merger.merge_segments(output_file, file_list)
    
    if success:
        if DELETE_SEGMENTS_AFTER_MERGE:
            print(Fore.CYAN + f"  合并成功，正在清理 {len(file_list)} 个分段文件..." + Style.RESET_ALL)
            for f_path in file_list:
                try:
                    os.remove(f_path)
                except Exception as e:
                    log_error(f"  删除文件失败: {f_path} ({e})", console=True)
                    
        # 尝试生成字幕
        if GENERATE_SUBTITLES:
            try:
                transcriber = Transcriber()
                transcriber.generate_subtitle(output_file)
            except Exception as e:
                log_error(f"字幕生成异常: {e}", console=True)
                
    return success

def _auto_merge_task_impl(dir_path):
    log_info(f"正在后台执行自动合并任务: {dir_path}", console=True)
    merger = Merger()
    
    # 获取 segments 需要检查 groups 是否为空
    # 但由于我们在后台线程，可能需要更健壮的错误处理
    try:
        groups = merger.get_segments(dir_path)
    except Exception as e:
        log_error(f"后台合并扫描失败: {e}", console=True)
        return

    if not groups:
        log_info("  自动合并: 未发现需合并的分段。", console=True)
        return

    count = 0
    for base_name, file_list in groups.items():
        # 这里调用 _merge_and_clean，注意它会打印日志
        if _merge_and_clean(merger, dir_path, base_name, file_list):
            count += 1
            
    if count > 0:
        log_info(f"后台自动合并完成，共处理 {count} 组。", console=True)

def try_auto_merge(dir_path):
    """
    尝试自动合并指定目录下的分段 (在新线程中执行)
    """
    if not dir_path or not os.path.exists(dir_path):
        return

    # 启动后台线程
    threading.Thread(target=_auto_merge_task_impl, args=(dir_path,), daemon=True).start()

def update_config_file(key, new_val):
    return _update_config_file_impl(key, new_val)

def _update_config_file_impl(key, value):
    config_path = os.path.join(os.path.dirname(__file__), 'config.py')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        new_lines = []
        found = False
        for line in lines:
            line_sw = line.strip()
            if line_sw.startswith(key) and '=' in line_sw:
                parts = line.split('=')
                if parts[0].strip() == key:
                    # 保留原有注释
                    comment_part = ""
                    if '#' in line:
                         hash_idx = line.find('#')
                         # 确保 # 在 = 后面
                         if hash_idx > line.find('='):
                             comment_part = line[hash_idx:]
                    
                    val_str = f'"{value}"' if isinstance(value, str) else str(value)
                    new_line = f"{key} = {val_str} {comment_part}".strip() + "\n"
                    new_lines.append(new_line)
                    found = True
                    continue
            new_lines.append(line)
        
        if found:
            with open(config_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            return True
        return False
    except Exception as e:
        log_error(f"更新配置文件错误: {e}", console=True)
        return False
        
def show_settings():
    while True:
        print(Fore.BLUE + "\n=== 系统设置 ===" + Style.RESET_ALL)
        # 注意：这里显示的是程序启动时加载的值，不是config.py文件当前的最新值（如果未重启）
        # 为了用户体验，我们应该读取文件最新值吗？
        # 简单起见，提示用户重启生效。
        
        # 重新导入以获取最新值是不太可能的（reload tricky），所以我们只提示。
        print(f"当前运行配置 (修改后需重启生效):")
        print(f"1. 检查间隔 [CHECK_INTERVAL]: {Fore.CYAN}{CHECK_INTERVAL} 秒{Style.RESET_ALL}")
        print(f"2. 分段时长 [SEGMENT_TIME]: {Fore.CYAN}{SEGMENT_TIME} 秒{Style.RESET_ALL}")
        print(f"3. 自动合并 [AUTO_MERGE]: {Fore.CYAN}{'开启' if AUTO_MERGE_AFTER_STREAM else '关闭'}{Style.RESET_ALL}")
        print(f"4. 合并后删除 [DELETE_AFTER_MERGE]: {Fore.CYAN}{'开启' if DELETE_SEGMENTS_AFTER_MERGE else '关闭'}{Style.RESET_ALL}")
        print(f"5. 录制弹幕 [RECORD_DANMAKU]: {Fore.CYAN}{'开启' if RECORD_DANMAKU else '关闭'}{Style.RESET_ALL}")
        print(f"6. 自动生成字幕 [GENERATE_SUBTITLES]: {Fore.CYAN}{'开启' if GENERATE_SUBTITLES else '关闭'}{Style.RESET_ALL}")
        
        method_str = "OpenAI API" if SUBTITLE_METHOD == "openai_api" else "本地 Faster-Whisper"
        print(f"7. 字幕生成方式 [SUBTITLE_METHOD]: {Fore.CYAN}{method_str}{Style.RESET_ALL}")
        
        key_display = "未设置"
        if OPENAI_API_KEY and len(OPENAI_API_KEY) > 5:
             key_display = f"{OPENAI_API_KEY[:8]}..."
        elif OPENAI_API_KEY:
             key_display = OPENAI_API_KEY

        print(f"8. OpenAI API Key: {Fore.CYAN}{key_display}{Style.RESET_ALL}")
        print(f"9. OpenAI Base URL: {Fore.CYAN}{OPENAI_API_BASE_URL}{Style.RESET_ALL}")
        print(f"10. OpenAI Model: {Fore.CYAN}{OPENAI_MODEL}{Style.RESET_ALL}")
        print(f"11. 本地 Whisper 模型: {Fore.CYAN}{LOCAL_WHISPER_MODEL}{Style.RESET_ALL}")

        print("b. 返回主菜单")
        
        choice = input("\n请输入选项修改设置 (1-11/b): ").strip().lower()
        
        if choice == 'b':
            break
            
        elif choice == '1':
            try:
                val_str = input("请输入新的检查间隔 (秒): ")
                val = int(val_str)
                if val > 0:
                    if update_config_file('CHECK_INTERVAL', val):
                        print(Fore.GREEN + "配置已写入 config.py。请重启程序生效。" + Style.RESET_ALL)
            except ValueError:
                print("无效输入。")
                
        elif choice == '2':
            try:
                val_str = input("请输入新的分段时长 (秒): ")
                val = int(val_str)
                if val > 0:
                     if update_config_file('SEGMENT_TIME', val):
                        print(Fore.GREEN + "配置已写入 config.py。请重启程序生效。" + Style.RESET_ALL)
            except ValueError:
                print("无效输入。")
                
        elif choice == '3':
            # 切换布尔值
            # 这里的 AUTO_MERGE_AFTER_STREAM 是当前内存中的值
            # 我们可以让用户输入 1/0 或者 y/n
            user_val = input("开启自动合并? (y/n): ").lower()
            new_val = True if user_val == 'y' else False
            if update_config_file('AUTO_MERGE_AFTER_STREAM', new_val):
                 print(Fore.GREEN + f"配置已更新为: {new_val} (请重启生效)" + Style.RESET_ALL)

        elif choice == '4':
            user_val = input("开启合并后删除源文件? (y/n, 慎用): ").lower()
            new_val = True if user_val == 'y' else False
            if update_config_file('DELETE_SEGMENTS_AFTER_MERGE', new_val):
                 print(Fore.GREEN + f"配置已更新为: {new_val} (请重启生效)" + Style.RESET_ALL)

        elif choice == '5':
            user_val = input("开启弹幕录制? (y/n): ").lower()
            new_val = True if user_val == 'y' else False
            if update_config_file('RECORD_DANMAKU', new_val):
                 print(Fore.GREEN + f"配置已更新为: {new_val} (请重启生效)" + Style.RESET_ALL)

        elif choice == '6':
            user_val = input("开启自动生成字幕? (y/n): ").lower()
            new_val = True if user_val == 'y' else False
            if update_config_file('GENERATE_SUBTITLES', new_val):
                 print(Fore.GREEN + f"配置已更新为: {new_val} (请重启生效)" + Style.RESET_ALL)
        
        elif choice == '7':
             print("请选择生成方式: 1. local_whisper (本地模型), 2. openai_api (API调用)")
             m_choice = input("请输入选项 (1/2): ").strip()
             if m_choice == '1':
                  if update_config_file('SUBTITLE_METHOD', "local_whisper"):
                       print(Fore.GREEN + "已切换为本地 Whisper 模型" + Style.RESET_ALL)
             elif m_choice == '2':
                  if update_config_file('SUBTITLE_METHOD', "openai_api"):
                       print(Fore.GREEN + "已切换为 OpenAI API" + Style.RESET_ALL)
             else:
                  print("无效选项")

        elif choice == '8':
             new_key = input("请输入新的 OpenAI API Key: ").strip()
             if new_key:
                  if update_config_file('OPENAI_API_KEY', new_key):
                       print(Fore.GREEN + "API Key 已更新" + Style.RESET_ALL)

        elif choice == '9':
             new_url = input(f"请输入新的 Base URL (当前: {OPENAI_API_BASE_URL}): ").strip()
             if new_url:
                  if update_config_file('OPENAI_API_BASE_URL', new_url):
                       print(Fore.GREEN + "Base URL 已更新" + Style.RESET_ALL)

        elif choice == '10':
             new_model = input(f"请输入新的 OpenAI Model (当前: {OPENAI_MODEL}): ").strip()
             if new_model:
                  if update_config_file('OPENAI_MODEL', new_model):
                       print(Fore.GREEN + "OpenAI Model 已更新" + Style.RESET_ALL)
        
        elif choice == '11':
             print(f"当前模型: {LOCAL_WHISPER_MODEL}")
             print("可选: tiny, base, small, medium, large, large-v3")
             new_size = input("请输入新的模型大小: ").strip()
             if new_size:
                  if update_config_file('LOCAL_WHISPER_MODEL', new_size):
                       print(Fore.GREEN + "本地模型设置已更新" + Style.RESET_ALL)

        else:
            print("无效选项。")


def start_monitor():
    log_info("进入监控录制模式...", color=Fore.BLUE)
    
    # 1. 获取并确认 UP 主信息
    uid = None
    while True:
        uid = get_input_uid()
        up_info = BilibiliAPI.get_user_info(uid)
        
        if not up_info:
            print(Fore.RED + "未找到该 UP 主信息，请检查输入。" + Style.RESET_ALL)
            continue
            
        print_up_info(up_info)
        break
    
    room_id = up_info['room_id']
    up_name = up_info['name']
    
    recorder = Recorder(room_id, up_name)
    recording = False
    danmaku_recorder = None # Initialize variable
    last_save_dir = None # 记录上次保存的目录，用于流结束后自动合并
    
    log_info(f"开始监控 {up_name} (Room ID: {room_id})...", color=Fore.YELLOW)
    
    # 连续失败计数器
    error_count = 0
    
    # 2. 监控循环
    try:
        while True:
            # === 如果正在录制，优先检查录制进程状态 ===
            if recording:
                last_save_dir = recorder.save_dir
                if recorder.is_recording():
                    # 录制正常进行中...
                    # 可以在这里打印心跳，或者什么都不做
                    time.sleep(CHECK_INTERVAL)
                    continue
                else:
                    # 录制进程退出了
                    print(Fore.YELLOW + f"\n[{time.strftime('%H:%M:%S')}] 录制进程已退出，正在尝试重新连接..." + Style.RESET_ALL)
                    recording = False
                    
                    if danmaku_recorder:
                        danmaku_recorder.stop()
                        danmaku_recorder = None
                        
                    # 不要 sleep，立即走下面的逻辑尝试获取地址并重连

            # === 未录制状态，或者刚掉线，检查 API ===
            try:
                current_info = BilibiliAPI.get_user_info(uid)
            except Exception as e:
                # 捕获所有网络异常
                log_error(f"API请求异常 (忽略): {e}", console=False)
                current_info = None

            if not current_info:
                error_count += 1
                if error_count % 10 == 0:
                    print(Fore.YELLOW + f"[{time.strftime('%H:%M:%S')}] 网络波动: 无法获取直播间状态 (已重试 {error_count} 次)..." + Style.RESET_ALL)
                time.sleep(CHECK_INTERVAL)
                continue
            
            # API 成功，重置计数
            error_count = 0 
            is_live = current_info['is_live']
            
            if is_live:
                if not recording:
                    log_info(f"检测到 {up_name} 开播 (或正在恢复录制)！标题: {current_info['title']}", color=Fore.GREEN)
                    
                    stream_url = BilibiliAPI.get_live_url(room_id)
                    if stream_url:
                        log_info(f"获取流地址成功，启动录制...")
                        success = recorder.start_recording(stream_url)
                        if success:
                            recording = True
                            
                            # 启动弹幕录制
                            if RECORD_DANMAKU:
                                try:
                                    # 使用 recorder 的 save_dir 确保在同一个文件夹
                                    danmaku_recorder = DanmakuRecorder(room_id, up_name, recorder.save_dir)
                                    danmaku_recorder.start()
                                except Exception as e:
                                    log_error(f"启动弹幕录制失败: {e}", console=True)
                        else:
                            log_error("录制启动失败，稍后重试。")
                    else:
                        log_error("无法获取直播流地址。")
            
            elif not is_live:
                 # Up主未开播
                 # 如果刚才是处于录制状态，或者刚结束录制，尝试自动合并
                 if last_save_dir:
                     if danmaku_recorder:
                        danmaku_recorder.stop()
                        danmaku_recorder = None
                        
                     if AUTO_MERGE_AFTER_STREAM:
                         # 避免在一次停播期间重复合并
                         # 我们可以传递一个标记给 try_auto_merge 吗？不，它靠文件是否已合并来判断。
                         # 但由于我们有 API 检查间隔，可能会频繁扫描目录。
                         # 为了优化，可以将 try_auto_merge 放在第一次检测到 not is_live 时。
                         # 也就是 last_save_dir 还是非 None 时。
                         
                         # 执行合并
                         try_auto_merge(last_save_dir)
                     
                     # 无论合并成功与否，重置 last_save_dir 防止重复执行
                     last_save_dir = None
                 
                 print(f"[{time.strftime('%H:%M:%S')}] 未开播，等待中...", end='\r')

            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n用户手动停止...")
    finally:
        if recording:
            recorder.stop_recording()
        if danmaku_recorder:
            danmaku_recorder.stop()
        print("停止监控。")

def start_merge():
    log_info("进入视频合并模式...", color=Fore.BLUE)
    merger = Merger()
    
    # 1. 选择目录
    dirs = merger.get_recording_dirs()
    if not dirs:
        print(Fore.RED + f"未找到任何录制目录 ({DEFAULT_SAVE_PATH} 文件夹为空)。" + Style.RESET_ALL)
        return

    print(Fore.CYAN + "发现以下录制目录：" + Style.RESET_ALL)
    for i, d in enumerate(dirs):
        print(f"{i + 1}. {d}")
    
    choice = input(f"请选择要合并的目录 (1-{len(dirs)}), 输入 a 处理所有: ").strip()
    
    selected_dirs = []
    if choice.lower() == 'a':
        selected_dirs = dirs
    elif choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(dirs):
            selected_dirs = [dirs[idx]]
        else:
            print("无效选择")
            return
    else:
        print("无效输入")
        return

    # 2. 遍历目录处理
    for folder_name in selected_dirs:
        dir_path = os.path.join(DEFAULT_SAVE_PATH, folder_name)
        print(f"\n正在扫描: {folder_name} ...")
        
        groups = merger.get_segments(dir_path)
        if not groups:
            print("  未发现可合并的分段视频。")
            continue
            
        print(f"  发现 {len(groups)} 组录像:")
        
        group_keys = list(groups.keys())
        for i, key in enumerate(group_keys):
            count = len(groups[key])
            print(f"  [{i+1}] {key} (包含 {count} 个分段)")
            
        # 默认全部合并，或者让用户选？为了方便，我们对发现的所有组进行合并
        input_y = input("  是否确认合并以上所有组？(y/n, 默认y): ").strip().lower()
        if input_y and input_y != 'y':
            print("  跳过此目录。")
            continue
            
        for key in group_keys:
            _merge_and_clean(merger, dir_path, key, groups[key])

    print("\n所有任务完成。")

def main():
    print(Fore.BLUE + "=== Bilibili 直播录制助手 ===" + Style.RESET_ALL)
    print("1. 监控并录制 UP 主直播")
    print("2. 合并已录制的分段视频")
    print("3. 为已有视频生成字幕")
    print("4. 登录 Bilibili 账号 (防反爬/获取更高画质)")
    print("5. 系统设置 (修改配置)")
    print("q. 退出程序")
    
    choice = input("\n请选择功能 (1/2/3/4/5/q): ").strip().lower()
    
    if choice == '1':
        start_monitor()
    elif choice == '2':
        start_merge()
    elif choice == '3':
        start_transcription()
        main()
    elif choice == '4':
        BilibiliAPI.login()
        input("\n按回车键返回主菜单...")
        main()
    elif choice == '5':
        show_settings()
        main()
    elif choice == 'q':
        sys.exit(0)
    else:
        print("无效选项，程序退出。")

def start_transcription():
    log_info("进入视频字幕生成模式...", color=Fore.BLUE)
    merger = Merger()
    transcriber = Transcriber()
    
    # 1. 选择目录
    dirs = merger.get_recording_dirs()
    if not dirs:
        print(Fore.RED + f"未找到任何录制目录 ({DEFAULT_SAVE_PATH} 文件夹为空)。" + Style.RESET_ALL)
        return

    print(Fore.CYAN + "发现以下录制目录：" + Style.RESET_ALL)
    for i, d in enumerate(dirs):
        print(f"{i + 1}. {d}")
    
    print(f"a. 处理所有目录")
    choice = input(f"请选择要处理的目录 (1-{len(dirs)}/a): ").strip()
    
    selected_dirs = []
    if choice.lower() == 'a':
        selected_dirs = dirs
    elif choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(dirs):
            selected_dirs = [dirs[idx]]
        else:
            print("无效选择")
            return
    else:
        print("无效输入")
        return

    # 添加过滤选项
    print(f"是否只处理合并后的视频文件 (文件名包含 '_merged')?")
    filter_choice = input("输入 y 确认 (默认), 输入 n 处理所有视频: ").strip().lower()
    only_merged = True if filter_choice != 'n' else False

    # 3. 收集任务列表 (all_tasks)
    all_tasks = []

    if len(selected_dirs) == 1:
        # 单目录模式 - 提供文件选择
        folder_name = selected_dirs[0]
        dir_path = os.path.join(DEFAULT_SAVE_PATH, folder_name)
        
        print(Fore.YELLOW + f"\n正在扫描目录: {folder_name}" + Style.RESET_ALL)
        
        candidates = []
        if os.path.isdir(dir_path):
            for root, _, files in os.walk(dir_path):
                for file in files:
                    if file.lower().endswith(('.mp4', '.flv', '.mkv')):
                        # 过滤 merged
                        if only_merged and "_merged" not in file:
                            continue
                        candidates.append(os.path.join(root, file))
        
        if not candidates:
            print("  未找到视频文件。")
        else:
            print(Fore.CYAN + f"找到以下视频文件：" + Style.RESET_ALL)
            for i, path in enumerate(candidates):
                rel_name = os.path.relpath(path, dir_path)
                print(f"{i + 1}. {rel_name}")
            
            print("a. 处理该目录下所有视频")
            video_choice = input(f"请选择要生成的视频 (1-{len(candidates)}/a): ").strip().lower()
            
            if video_choice == 'a':
                all_tasks = candidates
            elif video_choice.isdigit():
                idx = int(video_choice) - 1
                if 0 <= idx < len(candidates):
                    all_tasks = [candidates[idx]]
                else:
                    print("无效选择")
            else:
                print("无效输入")
    else:
        # 多目录模式 - 自动处理所有符合条件的文件
        for folder_name in selected_dirs:
            dir_path = os.path.join(DEFAULT_SAVE_PATH, folder_name)
            if not os.path.isdir(dir_path):
                continue
                
            print(Fore.YELLOW + f"\n正在扫描目录: {folder_name}" + Style.RESET_ALL)
            
            # 递归寻找视频文件
            dir_files = []
            for root, _, files in os.walk(dir_path):
                for file in files:
                    if file.lower().endswith(('.mp4', '.flv', '.mkv')):
                        if only_merged and "_merged" not in file:
                            continue
                        dir_files.append(os.path.join(root, file))
            
            if not dir_files:
                print("  未找到视频文件。")
            else:
                print(f"  找到 {len(dir_files)} 个视频文件。")
                all_tasks.extend(dir_files)

    if not all_tasks:
        if len(selected_dirs) == 1:
             # 如果是单目录且没选中可不只是没任务，也可能是选择无效，上面已经print了，这里补一个等待
             input("按回车键返回主菜单...")
        return

    print(Fore.GREEN + f"\n待处理任务数: {len(all_tasks)}" + Style.RESET_ALL)

    # 4. 执行任务
    total_processed = 0
    for video_path in all_tasks:
        # 检查是否已有字幕文件
        srt_path = os.path.splitext(video_path)[0] + ".srt"
        if os.path.exists(srt_path):
             print(f"  [跳过] 字幕已存在: {os.path.basename(video_path)}")
             continue
        
        # 用户主要想为合并后的视频生成字幕，这里我们倾向于处理 _merged 结尾的
        # 但既然是手动模式，不妨更宽容一点，或者给个提示？
        # 这里默认处理所有未生成字幕的视频
        
        print(f"  [处理中] 正在生成字幕: {os.path.basename(video_path)}")
        try:
            if transcriber.generate_subtitle(video_path):
                total_processed += 1
        except Exception as e:
            log_error(f"  生成失败: {e}")

    print(Fore.GREEN + f"\n任务完成，共生成 {total_processed} 个字幕文件。" + Style.RESET_ALL)
    input("按回车键返回主菜单...")

if __name__ == "__main__":
    # 程序初始化时尝试加载 Cookies
    BilibiliAPI.load_cookies()
    main()
