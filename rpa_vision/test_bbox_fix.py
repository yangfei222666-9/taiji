"""
验证 Windows OCR bbox 修复
3 个回归检查：
1. line.bbox 不再全是默认值
2. line.bbox 必须覆盖其 words[*].bbox
3. 在 150% DPI 下，截图上画出的框和屏幕肉眼位置一致（需要人工验证）
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "rpa-vision"))

from PIL import Image, ImageGrab, ImageDraw, ImageFont
from ocr.windows_ocr import WindowsOCR
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_1_no_default_bbox(results):
    """检查 1：line.bbox 不再全是默认值"""
    default_bbox = (0, 0, 100, 20)
    non_default_count = 0
    
    for item in results:
        if item["bbox"] != default_bbox:
            non_default_count += 1
    
    if non_default_count > 0:
        logger.info(f"✅ Check 1 PASS: {non_default_count}/{len(results)} lines have non-default bbox")
        return True
    else:
        logger.error(f"❌ Check 1 FAIL: All {len(results)} lines have default bbox")
        return False


def check_2_bbox_covers_words(results):
    """检查 2：line.bbox 必须覆盖其 words[*].bbox"""
    all_pass = True
    
    for i, item in enumerate(results):
        line_bbox = item["bbox"]
        words = item.get("words", [])
        
        if not words:
            continue
        
        lx, ly, lw, lh = line_bbox
        line_right = lx + lw
        line_bottom = ly + lh
        
        for word in words:
            wx, wy, ww, wh = word["bbox"]
            word_right = wx + ww
            word_bottom = wy + wh
            
            # 检查 word 是否在 line 内
            if not (wx >= lx and wy >= ly and word_right <= line_right and word_bottom <= line_bottom):
                logger.error(f"❌ Check 2 FAIL: Line {i} bbox {line_bbox} does not cover word '{word['text']}' bbox {word['bbox']}")
                all_pass = False
    
    if all_pass:
        logger.info(f"✅ Check 2 PASS: All line bboxes cover their words")
        return True
    else:
        return False


def check_3_visual_verification(image, results, output_path="debug_screenshots/bbox_verification.png"):
    """检查 3：在截图上画出框，供人工验证"""
    draw = ImageDraw.Draw(image)
    
    # 尝试加载字体（如果失败使用默认字体）
    try:
        font = ImageFont.truetype("msyh.ttc", 16)  # 微软雅黑
    except:
        font = ImageFont.load_default()
    
    for i, item in enumerate(results):
        x, y, w, h = item["bbox"]
        
        # 画 line bbox（红色）
        draw.rectangle([x, y, x + w, y + h], outline="red", width=2)
        
        # 画 words bbox（绿色）
        for word in item.get("words", []):
            wx, wy, ww, wh = word["bbox"]
            draw.rectangle([wx, wy, wx + ww, wy + wh], outline="green", width=1)
        
        # 标注文本
        draw.text((x, y - 20), f"{i}: {item['text']}", fill="blue", font=font)
    
    # 保存
    Path(output_path).parent.mkdir(exist_ok=True)
    image.save(output_path)
    logger.info(f"✅ Check 3: Visual verification image saved to {output_path}")
    logger.info(f"   Please manually verify that red boxes match screen text positions")
    
    return True


def main():
    logger.info("=== Windows OCR bbox 修复验证 ===\n")
    
    # 1. 截图
    logger.info("Step 1: Capturing screen...")
    screenshot = ImageGrab.grab()
    logger.info(f"Screenshot size: {screenshot.size}\n")
    
    # 2. OCR
    logger.info("Step 2: Running Windows OCR...")
    ocr = WindowsOCR(language="zh-CN")
    
    if not ocr.is_available():
        logger.error("❌ Windows OCR not available")
        return
    
    results = ocr.extract(screenshot)
    logger.info(f"OCR found {len(results)} lines\n")
    
    # 3. 打印前 3 条结果
    logger.info("Step 3: First 3 results:")
    for i, item in enumerate(results[:3]):
        logger.info(f"[{i}] text: {item['text']}")
        logger.info(f"    bbox: {item['bbox']}")
        logger.info(f"    words: {len(item.get('words', []))} words")
        if item.get('words'):
            for word in item['words'][:3]:  # 只显示前 3 个 word
                logger.info(f"      - '{word['text']}' @ {word['bbox']}")
        logger.info("")
    
    # 4. 回归检查
    logger.info("Step 4: Regression checks:")
    check1_pass = check_1_no_default_bbox(results)
    check2_pass = check_2_bbox_covers_words(results)
    check3_pass = check_3_visual_verification(screenshot, results)
    
    logger.info("\n=== Summary ===")
    logger.info(f"Check 1 (no default bbox): {'✅ PASS' if check1_pass else '❌ FAIL'}")
    logger.info(f"Check 2 (bbox covers words): {'✅ PASS' if check2_pass else '❌ FAIL'}")
    logger.info(f"Check 3 (visual verification): ✅ DONE (manual check required)")
    
    if check1_pass and check2_pass:
        logger.info("\n🎉 All automated checks passed!")
        logger.info("Please manually verify debug_screenshots/bbox_verification.png")
    else:
        logger.error("\n❌ Some checks failed")


if __name__ == "__main__":
    main()
