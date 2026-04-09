"""
Search Demo - 搜索演示（dry-run 模式）
只验证：
1. 能不能识别"搜索"相关区域
2. 能不能给出点击坐标
3. 有没有生成调试截图和日志
"""
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import RPAVision
import time

def main():
    print("=" * 50)
    print("Search Demo (Dry-Run Mode)")
    print("=" * 50)
    
    # 初始化（默认 dry_run=True）
    bot = RPAVision(dry_run=True, debug=True)
    
    # 1. 截图
    print("\n[Step 1] Capturing screen...")
    image = bot.capture_screen()
    if image:
        print(f"[OK] Screenshot captured: {image.size}")
    else:
        print("[FAIL] Screenshot failed")
        return
    
    # 2. 查找"搜索"
    print("\n[Step 2] Finding '搜索'...")
    bbox = bot.find_text("搜索")
    
    if bbox:
        print(f"[OK] Found '搜索' at: {bbox}")
        
        # 计算点击坐标（中心点）
        x = (bbox[0] + bbox[2]) // 2
        y = (bbox[1] + bbox[3]) // 2
        print(f"[OK] Click coordinates: ({x}, {y})")
        
        # 3. 模拟点击（dry-run）
        print("\n[Step 3] Simulating click...")
        bot.click(x, y)
        
        # 4. 模拟输入（dry-run）
        print("\n[Step 4] Simulating text input...")
        bot.type_text("test query")
        
    else:
        print("[FAIL] '搜索' not found")
    
    print("\n" + "=" * 50)
    print("Demo Complete")
    print("Check debug_screenshots/ for output")
    print("=" * 50)

if __name__ == "__main__":
    main()
