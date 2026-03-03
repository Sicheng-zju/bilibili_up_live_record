# Bilibili 直播录制工具

## 简介
这是一个简单的 Python 工具，用于监控指定的 Bilibili UP 主直播状态。一旦 UP 主开播，自动调用 ffmpeg 进行录制。

## 功能
- 根据 URL 或 UID 搜索 UP 主。
- 自动监控直播间状态。
- 使用 ffmpeg 录制直播流。
- [x] 按时间分段保存录像（默认为 10 分钟）。
- 自动重试机制。

## 前置要求
1. **Python 3.6+**: 必须安装 Python 环境。
2. **FFmpeg**: 必须安装 FFmpeg 并将其添加到系统环境变量 PATH 中。  
   *Windows 用户下载编译好的 ffmpeg.exe 放入 C:\Windows\System32 或手动添加 Path 即可。*

## 安装依赖
在项目根目录下运行：
```bash
pip install -r requirements.txt
```

## 使用方法
双击运行 `run.py` 或者在命令行中输入：
```bash
python run.py
```
然后按照提示输入 UP 主的主页链接（如 `https://space.bilibili.com/123456`）或 UID（如 `123456`）。

程序会自动监控，名为 `Recordings` 的文件夹会自动生成在项目目录下，录好的视频会保存在其中。

## 配置
你可以修改 `bilibili_live_recorder/config.py` 文件来调整配置：
- `SEGMENT_TIME`: 分段时长（秒），默认 600 秒（10分钟）。
- `CHECK_INTERVAL`: 检查间隔（秒）。
