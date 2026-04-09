"""
真实 Windows OCR 验证
4 条检查：
A. 语言可用性检查
B. bbox 真实性检查
C. DPI 150% 回归
D. dry-run search_demo
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "skills" / "rpa-vision"))

from PIL import Image, ImageGrab, ImageDraw, ImageFont
from ocr.windows_ocr import WindowsOCR
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_a_language_availability(ocr):
    """检查 A：语言可用性"""
    logger.info("=== Check A: Language Availability ===")
    
    available = ocr.get_available_languages()
    logger.info(f"Available languages: {available}")
    
    if "zh-CN" in available:
        logger.info("✅ zh-CN is available")
        return True
    else:
        logger.warning("⚠️ zh-CN not available, using fallback")
        return False


def check_b_bbox_reality(results):
    """检查 B：bbox 真实性"""
    logger.info("\n=== Check B: Bbox Reality ===")
    
    all_pass = True
    
    # B1: 同一行里，每个 word 都有不同 bbox
    for i, item in enumerate(results[:5]):  # 只检查前 5 行
        words = item.get("words", [])
        if len(words) <= 1:
            continue
        
        word_bboxes = [w["bbox"] for w in words]
        unique_bboxes = set(word_bboxes)
        
        if len(unique_bboxes) != len(word_bboxes):
            logger.error(f"❌ B1 FAIL: Line {i} has duplicate word bboxes")
            all_pass = False
    
    if all_pass:
        logger.info("✅ B1 PASS: All words have unique bboxes")
    
    # B2: line.bbox 能包住所有 word.bbox
    for i, item in enumerate(results[:5]):
        line_bbox = item["bbox"]
        words = item.get("words", [])
        
        if not words:
            continue
        
        lx1, ly1, lx2, ly2 = line_bbox
        
        for word in words:
            wx1, wy1, wx2, wy2 = word["bbox"]
            
            if not (wx1 >= lx1 and wy1 >= ly1 and wx2 <= lx2 and wy2 <= ly2):
                logger.error(f"❌ B2 FAIL: Line {i} bbox {line_bbox} does not cover word '{word['text']}' bbox {word['bbox']}")
                all_pass = False
    
    if all_pass:
        logger.info("✅ B2 PASS: All line bboxes cover their words")
    
    # B3: 不再出现全员默认框
    default_count = sum(1 for item in results if item["bbox"] == (0, 0, 100, 20))
    if default_count == 0:
        logger.info(f"✅ B3 PASS: No default bboxes (0/{len(results)})")
    else:
        logger.error(f"❌ B3 FAIL: {default_count}/{len(results)} lines have default bbox")
        all_pass = False
    
    return all_pass


def check_c_dpi_regression(image, results, output_path="debug_screenshots/real_ocr_bbox.png"):
    """检查 C：DPI 150% 回归（画框验证）"""
    logger.info("\n=== Check C: DPI 150% Regression ===")
    
    draw = ImageDraw.Draw(image)
    
    # 尝试加载字体
    try:
        font = ImageFont.truetype("msyh.ttc", 16)
    except:
        font = ImageFont.load_default()
    
    for i, item in enumerate(results):
        x1, y1, x2, y2 = item["bbox"]
        
        # 画 line bbox（红色）
        draw.rectangle([x1, y1, x2, y2], outline="red", width=2)
        
        # 画 words bbox（绿色）
        for word in item.get("words", []):
            wx1, wy1, wx2, wy2 = word["bbox"]
            draw.rectangle([wx1, wy1, wx2, wy2], outline="green", width=1)
        
        # 标注文本（只标注前 20 行，避免太乱）
        if i < 20:
            draw.text((x1, y1 - 20), f"{i}: {item['text'][:20]}", fill="blue", font=font)
    
    # 保存
    Path(output_path).parent.mkdir(exist_ok=True)
    image.save(output_path)
    logger.info(f"✅ Check C: Debug image saved to {output_path}")
    logger.info(f"   Please manually verify that red boxes match screen text positions at 150% DPI")
    
    return True


def check_d_dry_run_search(ocr, screenshot):
    """检查 D：dry-run search_demo"""
    logger.info("\n=== Check D: Dry-Run Search Demo ===")
    
    # 模拟 find_text + click_text
    target = "搜索"
    
    results = ocr.extract(screenshot)
    
    found = None
    for item in results:
        if target in item["text"]:
            found = item
            break
    
    if found:
        x1, y1, x2, y2 = found["bbox"]
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        
        logger.info(f"✅ Found '{target}' at bbox {found['bbox']}")
        logger.info(f"   Center point: ({center_x}, {center_y})")
        logger.info(f"   [DRY-RUN] Would click at ({center_x}, {center_y})")
        
        # 保存画框截图
        debug_img = screenshot.copy()
        draw = ImageDraw.Draw(debug_img)
        draw.rectangle([x1, y1, x2, y2], outline="red", width=3)
        draw.ellipse([center_x-5, center_y-5, center_x+5, center_y+5], fill="red")
        
        output_path = "debug_screenshots/search_demo_dry_run.png"
        debug_img.save(output_path)
        logger.info(f"   Debug image saved to {output_path}")
        
        return True
    else:
        logger.warning(f"⚠️ Text '{target}' not found")
        return False


def main():
    logger.info("=== 真实 Windows OCR 验证 ===\n")
    
    # 初始化 OCR
    ocr = WindowsOCR(language="zh-CN")
    
    if not ocr.is_available():
        logger.error("❌ Windows OCR not available")
        return
    
    # Check A: 语言可用性
    check_a_language_availability(ocr)
    
    # 截图
    logger.info("\nCapturing screen...")
    screenshot = ImageGrab.grab()
    logger.info(f"Screenshot size: {screenshot.size}")
    
    # OCR
    logger.info("\nRunning Windows OCR...")
    results = ocr.extract(screenshot)
    logger.info(f"OCR found {len(results)} lines\n")
    
    # 打印前 3 条结果
    logger.info("=== First 3 Results ===")
    for i, item in enumerate(results[:3]):
        logger.info(f"[{i}] text: {item['text']}")
        logger.info(f"    bbox: {item['bbox']}")
        logger.info(f"    words: {len(item.get('words', []))} words")
        if item.get('words'):
            for word in item['words'][:3]:
                logger.info(f"      - '{word['text']}' @ {word['bbox']}")
        logger.info("")
    
    # Check B: bbox 真实性
    check_b_pass = check_b_bbox_reality(results)
    
    # Check C: DPI 150% 回归
    check_c_dpi_regression(screenshot, results)
    
    # Check D: dry-run search_demo
    check_d_pass = check_d_dry_run_search(ocr, screenshot)
    
    # Summary
    logger.info("\n=== Summary ===")
    logger.info(f"Check A (language): ✅ DONE")
    logger.info(f"Check B (bbox reality): {'✅ PASS' if check_b_pass else '❌ FAIL'}")
    logger.info(f"Check C (DPI regression): ✅ DONE (manual check required)")
    logger.info(f"Check D (dry-run search): {'✅ PASS' if check_d_pass else '⚠️ NOT FOUND'}")
    
    if check_b_pass and check_d_pass:
        logger.info("\n🎉 All automated checks passed!")
        logger.info("Next: Manually verify debug_screenshots/real_ocr_bbox.png")
    else:
        logger.error("\n❌ Some checks failed")


if __name__ == "__main__":
    main()
