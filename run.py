import sys
import os

# 将当前目录添加到 Python 路径中，确保能找到 bilibili_live_recorder 包
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    from bilibili_live_recorder.main import main
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保已安装所有依赖项。运行: pip install -r requirements.txt")
    # 如果是在命令行直接跑，input 可以暂停窗口
    input("按回车键退出...") 
    sys.exit(1)

if __name__ == "__main__":
    main()
 