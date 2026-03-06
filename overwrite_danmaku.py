
import asyncio
import threading
import os
import json
from datetime import datetime
from .logger import log_info, log_error

try:
    from bilibili_api import live, sync, Credential
except ImportError:
    live = None
    sync = None
    Credential = None

class DanmakuRecorder:
    def __init__(self, room_id, up_name, save_dir):
        self.room_id = int(room_id)
        self.up_name = up_name
        self.save_dir = save_dir
        self.loop = None
        self.room = None
        
        # Ensure log directory exists
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file_path = os.path.join(save_dir, f"{up_name}_{timestamp}_danmaku.txt")
        self.thread = None

    def start(self):
        if live is None:
            log_error("未安装 bilibili-api-python 库，无法录制弹幕。", console=True)
            return

        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        log_info(f"弹幕录制开始: {os.path.basename(self.log_file_path)}", console=True)

    def stop(self):
        # Stop is tricky with asyncio running in another thread
        if self.loop and self.room:
             # Schedule disconnect in the loop
             asyncio.run_coroutine_threadsafe(self.room.disconnect(), self.loop)
        log_info("弹幕录制已停止", console=True)

    def _run(self):
        # Create new loop for this thread
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.loop = loop
        
        # Load credentials from cookies.pkl via BilibiliAPI
        from .bilibili_api import BilibiliAPI
        
        sessdata = None
        bili_jct = None
        buvid3 = None
        dedeuserid = None
        
        if BilibiliAPI.session:
            cookies = BilibiliAPI.session.cookies
            sessdata = cookies.get('SESSDATA')
            bili_jct = cookies.get('bili_jct')
            buvid3 = cookies.get('buvid3')
            dedeuserid = cookies.get('DedeUserID')

        cred = None
        if sessdata and bili_jct:
            cred = Credential(sessdata=sessdata, bili_jct=bili_jct, buvid3=buvid3, dedeuserid=dedeuserid)
        
        self.room = live.LiveDanmaku(self.room_id, credential=cred)
        
        @self.room.on('DANMU_MSG')
        async def on_danmaku(event):
            try:
                info = event['data']['info']
                content = info[1]
                user = info[2][1]
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                line = f"[{timestamp}] {user}: {content}\n"
                
                with open(self.log_file_path, 'a', encoding='utf-8') as f:
                    f.write(line)
            except Exception:
                pass
        
        # Connect
        try:
            loop.run_until_complete(self.room.connect())
        except Exception as e:
            # log_error(f"弹幕连接断开: {e}", console=False)
            pass
        finally:
            loop.close()
