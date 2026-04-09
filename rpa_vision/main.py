"""
RPA Vision - 最小 v0 版本
只保留：截图 + Windows OCR + 基础输入控制
"""
import os
import sys
from pathlib import Path
from PIL import Image, ImageGrab
import pyautogui
import logging

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RPAVision:
    def __init__(self, dry_run=True, debug=True):
        self.dry_run = dry_run
        self.debug = debug
        self.last_screenshot = None
        logger.info(f"RPAVision initialized (dry_run={dry_run}, debug={debug})")
        
    def capture_screen(self, region=None):
        """截图"""
        try:
            if region:
                screenshot = ImageGrab.grab(bbox=region)
            else:
                screenshot = ImageGrab.grab()
            
            self.last_screenshot = screenshot
            
            if self.debug:
                # 保存调试截图
                debug_dir = Path("debug_screenshots")
                debug_dir.mkdir(exist_ok=True)
                screenshot.save(debug_dir / "last_capture.png")
                logger.debug(f"Screenshot saved to debug_screenshots/last_capture.png")
            
            return screenshot
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return None
    
    def extract_text(self):
        """使用 Windows OCR 提取文本"""
        if not self.last_screenshot:
            logger.warning("No screenshot available, capturing now...")
            self.capture_screen()
        
        try:
            # Windows OCR 实现（简化版）
            # 这里先返回模拟结果，真实 OCR 需要 Windows.Media.Ocr
            logger.info("OCR extraction started")
            
            # TODO: 集成真实 Windows OCR
            # 当前返回模拟结果
            result = [
                {"text": "搜索", "bbox": (100, 100, 150, 130)},
                {"text": "设置", "bbox": (200, 100, 250, 130)},
            ]
            
            logger.info(f"OCR found {len(result)} text regions")
            return result
            
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return []
    
    def find_text(self, target_text):
        """查找文本位置"""
        ocr_results = self.extract_text()
        
        for item in ocr_results:
            if target_text in item["text"]:
                logger.info(f"Found '{target_text}' at {item['bbox']}")
                return item["bbox"]
        
        logger.warning(f"Text '{target_text}' not found")
        return None
    
    def click(self, x, y):
        """点击坐标"""
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would click at ({x}, {y})")
            return True
        
        try:
            pyautogui.click(x, y)
            logger.info(f"Clicked at ({x}, {y})")
            return True
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return False
    
    def type_text(self, text):
        """输入文本"""
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would type: {text}")
            return True
        
        try:
            pyautogui.write(text)
            logger.info(f"Typed: {text}")
            return True
        except Exception as e:
            logger.error(f"Type failed: {e}")
            return False


if __name__ == "__main__":
    # 简单测试
    bot = RPAVision(dry_run=True, debug=True)
    
    # 测试截图
    image = bot.capture_screen()
    print(f"Screenshot captured: {image is not None}")
    
    # 测试 OCR
    result = bot.extract_text()
    print(f"OCR result: {result}")
    
    # 测试查找
    found = bot.find_text("搜索")
    print(f"Find result: {found}")
