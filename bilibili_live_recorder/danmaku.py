import json
import zlib
import threading
import time
import os
import struct
import requests
import websocket
from datetime import datetime
from .logger import log_info, log_error

try:
    import brotli
except ImportError:
    brotli = None
    # log_error is safe now
    log_error("未检测到 brotli 库，可能无法解压部分弹幕包。请尝试 `pip install brotli`", console=True)

from .config import HEADERS
from .bilibili_api import BilibiliAPI

# Protocol Constants
VER_ZLIB = 2
VER_BROTLI = 3
OP_HEARTBEAT = 2
OP_HEARTBEAT_REPLY = 3
OP_MESSAGE = 5
OP_USER_AUTHENTICATION = 7
OP_CONNECT_SUCCESS = 8

class DanmakuRecorder:
    def __init__(self, room_id, up_name, save_dir):
        self.room_id = int(room_id)
        self.up_name = up_name
        self.save_dir = save_dir
        
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file_path = os.path.join(save_dir, f"{up_name}_{timestamp}_danmaku.txt")
        
        self.ws = None
        self.thread = None
        self.stop_event = threading.Event()
        self.file = None

    def start(self):
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        log_info(f"弹幕录制开始: {os.path.basename(self.log_file_path)}", console=True)

    def stop(self):
        self.stop_event.set()
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
        if self.file:
            try:
                self.file.close()
            except Exception:
                pass
            self.file = None

    def _get_danmu_info(self):
        # 优先尝试 getConf (旧接口但无需风控验证)
        # 使用不带 Cookie 的纯净请求，避免因账号风控导致获取失败
        try:
            url = f"https://api.live.bilibili.com/room/v1/Danmu/getConf?room_id={self.room_id}&platform=pc&player=web"
            resp = requests.get(url, headers=HEADERS, timeout=10)
            data = resp.json()
            if data['code'] == 0:
                token = data['data']['token']
                host = data['data']['host']
                port = 2243
                wss_port = 443
                if 'host_server_list' in data['data']:
                     for s in data['data']['host_server_list']:
                         if 'wss_port' in s:
                             wss_port = s['wss_port']
                             host = s['host']
                             break
                
                log_info(f"获取弹幕服务器成功(getConf): {host}", console=False)
                return f"wss://{host}:{wss_port}/sub", token
        except Exception:
            pass

        # 备用尝试 getDanmuInfo (新接口)
        try:
            url = f"https://api.live.bilibili.com/xlive/web-room/v1/index/getDanmuInfo?id={self.room_id}&type=0"
            resp = requests.get(url, headers=HEADERS, timeout=10)
            data = resp.json()
            if data['code'] == 0:
                token = data['data']['token']
                host_list = data['data']['host_list']
                wss_port = host_list[0]['wss_port']
                host = host_list[0]['host']
                log_info(f"获取弹幕服务器成功(getDanmuInfo): {host}", console=False)
                return f"wss://{host}:{wss_port}/sub", token
            else:
                pass 
        except Exception as e:
            pass
            
        return None, None

    def _run(self):
        try:
            self.file = open(self.log_file_path, 'a', encoding='utf-8', buffering=1)
        except Exception as e:
            log_error(f"无法打开弹幕文件: {e}", console=True)
            return

        while not self.stop_event.is_set():
            try:
                uri, token = self._get_danmu_info()
                if not uri:
                    log_error("无法获取弹幕服务器地址，尝试默认配置...", console=True)
                    uri = "wss://broadcastlv.chat.bilibili.com:2245/sub"
                    token = ""
                
                log_info(f"正在连接弹幕服务器: {uri}...", console=False)
                
                # Setup WebSocket
                self.ws = websocket.WebSocketApp(
                    uri,
                    header=HEADERS,
                    on_open=lambda w: self._on_open(w, token),
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close
                )
                
                # Run forever blocks until connection closes
                self.ws.run_forever(ping_interval=30, ping_timeout=10)
                
                if self.stop_event.is_set():
                    break
                
                # Retry logic
                log_info("弹幕连接断开，5秒后重试...", console=False)
                time.sleep(5)
                
            except Exception as e:
                log_error(f"WebSocket 运行异常: {e}", console=True)
                time.sleep(5)

    def _send_packet(self, ws, operation, body):
        header = struct.pack('!IHHII', 16 + len(body), 16, 1, operation, 1)
        ws.send(header + body)

    def _on_open(self, ws, token):
        log_info("WebSocket连接建立，发送认证包...", console=False)
        auth_data = {
            "uid": 0,
            "roomid": self.room_id,
            "protover": 3,
            "platform": "web",
            "type": 2,
            "key": token
        }
        body = json.dumps(auth_data).encode('utf-8')
        try:
            self._send_packet(ws, OP_USER_AUTHENTICATION, body)
        except Exception as e:
            log_error(f"发送认证包失败: {e}", console=True)
        
        # Start Heartbeat Thread for this connection
        threading.Thread(target=self._heartbeat_loop, args=(ws,), daemon=True).start()

    def _heartbeat_loop(self, ws):
        while not self.stop_event.is_set() and ws.keep_running:
            try:
                self._send_packet(ws, OP_HEARTBEAT, b'[object Object]')
                time.sleep(30)
            except Exception:
                break

    def _on_message(self, ws, message):
        if not message:
            return
            
        offset = 0
        try:
            while offset + 16 <= len(message):
                header = message[offset:offset+16]
                packet_len, header_len, proto_ver, operation, seq = struct.unpack('!IHHII', header)
                
                body_len = packet_len - header_len
                body = message[offset+header_len : offset+packet_len]
                
                if operation == OP_MESSAGE:
                    # Decompress if needed
                    if proto_ver == VER_ZLIB:
                        decompressed = zlib.decompress(body)
                        self._on_message(ws, decompressed)
                    elif proto_ver == VER_BROTLI and brotli:
                        try:
                            # brotli might raise error if data is partial
                            decompressed = brotli.decompress(body)
                            self._on_message(ws, decompressed)
                        except brotli.error:
                            pass
                    elif proto_ver == 0:
                        # JSON text
                        # There might be multiple json objects? No, normally one packet one body.
                        # However, sometimes multiple raw packets are in one message? No, the outer loop handles packet slicing.
                        text = body.decode('utf-8', errors='ignore')
                        self._handle_cmd(text)
                
                elif operation == OP_CONNECT_SUCCESS:
                    log_info("弹幕服务器认证成功 (Op 8)", console=False)
                
                offset += packet_len
                
                if packet_len == 0:
                     break
                     
        except Exception:
            pass

    def _handle_cmd(self, text):
        try:
            data = json.loads(text)
            cmd = data.get('cmd', '')
            if cmd.startswith('DANMU_MSG'):
                info = data.get('info')
                if info and len(info) > 2:
                    content = info[1]
                    user = info[2][1]
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    line = f"[{timestamp}] {user}: {content}\n"
                    
                    if self.file:
                        try:
                            self.file.write(line)
                            self.file.flush()
                            # log_info(f"收到弹幕: {content}", console=False)
                        except ValueError:
                            pass # File closed
        except Exception as e:
            log_error(f"处理弹幕异常: {e}", console=False)
            pass

    def _on_error(self, ws, error):
        pass

    def _on_close(self, ws, close_status_code, close_msg):
        pass
