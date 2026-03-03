# bilibili_live_recorder/main.py

import sys
import time
import os
import signal
from colorama import init, Fore, Style
from .bilibili_api import BilibiliAPI
from .recorder import Recorder
from .config import CHECK_INTERVAL, DEFAULT_SAVE_PATH
from .merger import Merger
from .logger import log_info, log_error, log_warning

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
    
    log_info(f"开始监控 {up_name} (Room ID: {room_id})...", color=Fore.YELLOW)
    
    # 连续失败计数器
    error_count = 0
    
    # 2. 监控循环
    try:
        while True:
            # === 如果正在录制，优先检查录制进程状态 ===
            if recording:
                if recorder.is_recording():
                    # 录制正常进行中...
                    # 可以在这里打印心跳，或者什么都不做
                    time.sleep(CHECK_INTERVAL)
                    continue
                else:
                    # 录制进程退出了
                    print(Fore.YELLOW + f"\n[{time.strftime('%H:%M:%S')}] 录制进程已退出，正在尝试重新连接..." + Style.RESET_ALL)
                    recording = False
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
                        else:
                            log_error("录制启动失败，稍后重试。")
                    else:
                        log_error("无法获取直播流地址。")
            
            elif not is_live:
                 # Up主未开播
                 print(f"[{time.strftime('%H:%M:%S')}] 未开播，等待中...", end='\r')

            time.sleep(CHECK_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n用户手动停止...")
    finally:
        if recording:
            recorder.stop_recording()
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
            file_list = groups[key]
            # 合并后的文件名
            output_file = os.path.join(dir_path, f"{key}_merged.mp4")
            
            if os.path.exists(output_file):
                 print(f"  跳过: {key} (已存在合并文件)")
                 continue
                 
            print(f"  正在处理: {key} ...")
            merger.merge_segments(output_file, file_list)

    print("\n所有任务完成。")

def main():
    print(Fore.BLUE + "=== Bilibili 直播录制助手 ===" + Style.RESET_ALL)
    print("1. 监控并录制 UP 主直播")
    print("2. 合并已录制的分段视频")
    print("3. 登录 Bilibili 账号 (防反爬/获取更高画质)")
    print("q. 退出程序")
    
    choice = input("\n请选择功能 (1/2/3/q): ").strip().lower()
    
    if choice == '1':
        start_monitor()
    elif choice == '2':
        start_merge()
    elif choice == '3':
        BilibiliAPI.login()
        input("\n按回车键返回主菜单...")
        main()
    elif choice == 'q':
        sys.exit(0)
    else:
        print("无效选项，程序退出。")

if __name__ == "__main__":
    main()
