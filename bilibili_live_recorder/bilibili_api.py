import requests
import re
import os
import pickle
import qrcode
import time
import sys
from .config import HEADERS
from .logger import log_info, log_error

class BilibiliAPI:
    # 初始化 Session
    session = requests.Session()
    session.headers.update(HEADERS)
    COOKIE_FILE = "cookies.pkl"

    @classmethod
    def load_cookies(cls):
        """加载保存的 Cookies"""
        if os.path.exists(cls.COOKIE_FILE):
            try:
                with open(cls.COOKIE_FILE, 'rb') as f:
                    cookies = pickle.load(f)
                    cls.session.cookies.update(cookies)
                # 验证 Cookie 有效性（可选）
                # 简单检查是否有 SESSDATA
                # if 'SESSDATA' in cls.session.cookies:
                #     log_info("已加载用户 Cookies，将以登录状态访问 API。", console=False)
                return True
            except Exception as e:
                log_error(f"加载 Cookies 失败: {e}", console=True)
        return False

    @classmethod
    def save_cookies(cls):
        """保存当前 Session 的 Cookies"""
        try:
            with open(cls.COOKIE_FILE, 'wb') as f:
                pickle.dump(cls.session.cookies, f)
            log_info("Cookies 已保存。", console=True)
        except Exception as e:
            log_error(f"保存 Cookies 失败: {e}", console=True)

    @classmethod
    def login(cls):
        """扫码登录逻辑"""
        try:
            # 1. 获取二维码 URL
            url = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
            response = cls.session.get(url).json()
            if response['code'] != 0:
                print("获取二维码失败，请稍后重试。")
                return False
            
            qrcode_url = response['data']['url']
            qrcode_key = response['data']['qrcode_key']

            # 2. 生成并在终端显示二维码
            qr = qrcode.QRCode(border=1)
            qr.add_data(qrcode_url)
            qr.make(fit=True) 
            
            print("\n请使用 Bilibili App 扫描下方二维码登录：")
            check = qr.print_ascii(invert=True)

            print("等待扫码确认...")

            # 3. 轮询扫码状态
            while True:
                poll_url = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
                params = {"qrcode_key": qrcode_key}
                poll_res = cls.session.get(poll_url, params=params).json()
                
                code = poll_res['data']['code']
                
                if code == 0:
                    # 登录成功
                    print("登录成功！")
                    cls.save_cookies()
                    return True
                elif code == 86101: 
                    # 未扫码
                    pass 
                elif code == 86090:
                    # 已扫码未确认
                    print("已扫描，请在手机上确认...", end='\r')
                elif code == 86038:
                    print("二维码已过期，请重新尝试。")
                    return False
                
                time.sleep(2)
        
        except Exception as e:
            print(f"登录过程中发生错误: {e}")
            return False

    @classmethod
    def get_uid_from_url(cls, url):
        # 常见格式: https://space.bilibili.com/123456
        pattern = r"space\.bilibili\.com/(\d+)"
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        return None

    @classmethod
    def get_user_info(cls, uid):
        # 使用批量查询接口
        url = "https://api.live.bilibili.com/room/v1/Room/get_status_info_by_uids"
        payload = {
            "uids[]": uid
        }
        try:
            # 使用 session.post
            response = cls.session.post(url, data=payload, timeout=10)
            data = response.json()
            
            if data['code'] == 0:
                user_data = data['data'].get(str(uid))
                if user_data:
                    return {
                        'name': user_data['uname'],
                        'room_id': user_data['room_id'],
                        'is_live': user_data['live_status'] == 1,
                        'title': user_data['title']
                    }
            return None
        except Exception as e:
            # log_error(f"获取用户信息出错: {e}", console=False)
            return None

    @classmethod
    def get_live_room_info(cls, room_id):
        url = f"https://api.live.bilibili.com/room/v1/Room/get_info?room_id={room_id}"
        try:
            response = cls.session.get(url, timeout=10)
            data = response.json()
            if data['code'] == 0:
                return data['data']
            return None
        except Exception:
            return None

    @classmethod
    def get_danmu_info(cls, room_id):
        """获取弹幕服务器信息"""
        url = f"https://api.live.bilibili.com/xlive/web-room/v1/index/getDanmuInfo?id={room_id}&type=0"
        try:
            response = cls.session.get(url, timeout=10).json()
            if response['code'] == 0:
                return response['data']
            return None
        except Exception as e:
            log_error(f"获取弹幕信息失败: {e}", console=False)
            return None

    @classmethod
    def get_live_url(cls, room_id):
        try:
            url = "https://api.live.bilibili.com/xlive/web-room/v1/playUrl/playUrl"
            params = {
                "cid": room_id,
                "platform": "web",
                "qn": 10000, # 原画
                "https_url_req": 1,
                "ptype": 16
            }
            # 使用 session.get
            response = cls.session.get(url, params=params, timeout=10)
            data = response.json()
            if data['code'] == 0:
                durl = data.get('data', {}).get('durl')
                if durl and len(durl) > 0:
                    return durl[0]['url']
            return None
        except Exception as e:
            log_error(f"获取直播流失败: {e}", console=False)
            return None

    @classmethod
    def get_live_stream_url(cls, room_id):
        url = f"https://api.live.bilibili.com/xlive/web-room/v1/playUrl/playUrl?cid={room_id}&platform=web&qn=10000"
        try:
            response = cls.session.get(url, timeout=10)
            data = response.json()
            if data['code'] == 0:
                durl = data['data']['durl']
                if durl:
                    return durl[0]['url']
            return None
        except Exception as e:
            print(f"获取直播流地址出错: {e}")

# 初始化时尝试加载 Cookie
BilibiliAPI.load_cookies()
