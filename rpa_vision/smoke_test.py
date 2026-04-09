"""
Smoke Test - 最小验证
只验证 3 件事：
1. 能不能 import 成功
2. 能不能截图
3. OCR 和 find_text() 有没有返回结果
"""
from main import RPAVision

def main():
    print("=" * 50)
    print("RPA Vision Smoke Test")
    print("=" * 50)
    
    # 1. Import 测试
    print("\n[1/3] Testing import...")
    try:
        bot = RPAVision(dry_run=True, debug=True)
        print("[OK] Import successful")
    except Exception as e:
        print(f"[FAIL] Import failed: {e}")
        return
    
    # 2. 截图测试
    print("\n[2/3] Testing screenshot...")
    try:
        image = bot.capture_screen()
        if image is not None:
            print(f"[OK] Screenshot OK: {image.size}")
        else:
            print("[FAIL] Screenshot returned None")
    except Exception as e:
        print(f"[FAIL] Screenshot failed: {e}")
    
    # 3. OCR 测试
    print("\n[3/3] Testing OCR...")
    try:
        result = bot.extract_text()
        print(f"[OK] OCR result type: {type(result)}")
        print(f"[OK] OCR result: {result[:3] if isinstance(result, list) else result}")
    except Exception as e:
        print(f"[FAIL] OCR failed: {e}")
    
    # 4. find_text 测试
    print("\n[4/4] Testing find_text...")
    try:
        found = bot.find_text("搜索")
        print(f"[OK] find_text result: {found}")
    except Exception as e:
        print(f"[FAIL] find_text failed: {e}")
    
    print("\n" + "=" * 50)
    print("Smoke Test Complete")
    print("=" * 50)

if __name__ == "__main__":
    main()
