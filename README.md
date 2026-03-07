# Bilibili 直播录制助手 (Bilibili Live Recorder)

## 📌 简介
这是一个功能强大的 Bilibili 直播自动录制工具，能够全天候监控指定 UP 主的直播状态。
一旦开播，工具会自动启动录制，同时保存直播弹幕，并在直播结束后自动将分段视频合并为完整的 MP4 文件。

## ✨ 主要功能
*   **全自动监控**：输入 UP 主主页链接或 UID 即可开始监控。
*   **直播录制**：调用 FFmpeg 进行高质量录制，支持自定义分段时长。
*   **弹幕保存**：自动连接直播间弹幕服务器，实时保存弹幕内容到本地 TXT 文件（支持断电保护，实时写入）。
*   **自动合并**：直播结束后，自动将分出的 FLV 片段合并为 MP4，方便观看和存档。
*   **扫码登录**：支持 Bilibili 扫码登录，使用登录态进行录制和获取弹幕，连接更稳定，画质更高。
*   **断流重连**：网络波动或直播异常中断时，工具会自动尝试重连，确保录制完整。
*   **生成字幕**：使用openai api或本地faster-wispher生成录制视频的字幕。

## 🛠️ 前置要求
1.  **Python 3.10+**: 请确保已安装 Python 环境。
2.  **FFmpeg**: 必须安装 FFmpeg 并将其添加到系统环境变量 PATH 中。
    *   Windows 用户请下载 FFmpeg 编译包，解压并将 `bin` 目录添加到系统环境变量，或者直接将 `ffmpeg.exe` 放入 `C:\Windows\System32`。

## 📦 安装与配置
使用 `pip` 安装所需的依赖库，包括 core libraries 和 AI Whisper 模型支持库：

```bash
pip install -r requirements.txt
```

### 🧠(重要) AI 字幕生成环境配置 (GPU 加速)
如果你希望使用本地显卡加速生成字幕，请务必安装对应 CUDA 版本的 PyTorch。

**步骤 1**: 确保电脑已安装 NVIDIA 显卡驱动。
**步骤 2**:根据 CUDA 版本选择命令安装 PyTorch (推荐 CUDA 12.x):

```bash
# 推荐: CUDA 12.4
# 如果已经安装了cpu版本的torch得先卸载：pip uninstall torch torchvision torchaudio
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```
或者前往 [PyTorch 官网](https://pytorch.org/get-started/locally/)查找适合自己的安装命令。

**注意**: 直接运行 `pip install torch` 可能只会安装 CPU 版本，无法调用显卡，生成字幕速度会极慢。

### 🚀 运行程序
双击 `run.py` 或在终端运行：
1.  **克隆或下载本项目**
2.  **安装依赖库**
    在项目根目录下打开终端，运行：
    ```bash
    pip install -r requirements.txt
    ```
    > 注意：本项目依赖 `brotli` 库来解压弹幕数据，请确保安装成功。

## 🚀 使用方法
1.  **启动程序**
    在终端运行：
    ```bash
    python run.py
    ```
2.  **选择功能**
    *   输入 `1` 进入 **监控录制模式**，输入 UP 主的 URL 或 UID 即可开始挂机。
    *   输入 `2` 进入 **视频合并模式**，手动合并已录制的分段文件。
    *   输入 `3` 进入 **字幕生成模式**，手动为已合并后的录制视频生成字幕。
    *   输入 `4` 进行 **扫码登录**，建议首次使用前先登录，以提高录制稳定性。
    *   输入 `5` 进入 **系统设置**，调整系统设置参数。

3.  **结果查看**
    *   录制的视频和弹幕文件默认保存在 `Recordings/` 目录下，按 UP 主和时间分类。
    *   弹幕文件为 `.txt` 格式，包含时间戳、发送者和内容。

## ⚙️ 高级配置
你可以直接修改 `bilibili_live_recorder/config.py` 文件，或者使用菜单中的“系统设置”来调整：
*   `CHECK_INTERVAL`: 监控检查间隔（秒），即挂机时每隔多少秒检查一次up主有没有开播。
*   `SEGMENT_TIME`: 分段录制时长（秒），建议 900 秒。
*   `AUTO_MERGE_AFTER_STREAM`: 是否在直播结束后自动合并视频（True/False）。
*   `DELETE_SEGMENTS_AFTER_MERGE`: 合并后是否删除原始分段文件（True/False）。
*   `RECORD_DANMAKU`: 是否录制弹幕（True/False）。
*   `GENERATE_SUBTITLES`: 是否直播结束后自动生成字幕（True/False）。
*   `SUBTITLE_METHOD`: 字幕生成方式（local_whisper/openai_api）。
*   `LOCAL_WHISPER_MODEL`: 本地 Whisper 模型大小（"tiny", "base", "small", "medium", "large-v3"）。

## 📝 常见问题
*   **弹幕文件为空？**
    *   请确保已安装 `brotli` 库。
    *   尝试在菜单中选择“扫码登录”更新 Cookie。
*   **FFmpeg 报错？**
    *   请检查 FFmpeg 是否正确安装并配置了环境变量。

## 📄 许可证
MIT License
