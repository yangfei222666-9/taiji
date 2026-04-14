#!/usr/bin/env python3
"""
TTS 语音合成模块
使用 edge-tts 或系统 TTS 进行语音反馈
"""

import os
import sys
import tempfile
import subprocess
import threading
from pathlib import Path
from typing import Optional

class TTSSpeaker:
    """TTS 语音合成器"""
    
    def __init__(self, workspace_dir: str = None):
        self.workspace_dir = workspace_dir or os.getcwd()
        self.flag_path = os.path.join(self.workspace_dir, "logs", "tts_playing.flag")
        
        # 确保日志目录存在
        os.makedirs(os.path.dirname(self.flag_path), exist_ok=True)
        
        # TTS 配置
        self.config = {
            "voice": "zh-CN-XiaoxiaoNeural",  # 中文女性声音
            "rate": "+0%",                     # 语速
            "volume": "+0%",                   # 音量
            "output_format": "mp3",            # 输出格式
        }
    
    def create_flag(self):
        """创建 TTS 播放标志文件"""
        try:
            with open(self.flag_path, "w", encoding="utf-8", errors="replace") as f:
                f.write("tts_playing")
            return True
        except Exception as e:
            print(f"创建标志文件失败: {e}")
            return False
    
    def remove_flag(self):
        """移除 TTS 播放标志文件"""
        try:
            if os.path.exists(self.flag_path):
                os.remove(self.flag_path)
            return True
        except Exception as e:
            print(f"移除标志文件失败: {e}")
            return False
    
    def is_playing(self) -> bool:
        """检查 TTS 是否正在播放"""
        return os.path.exists(self.flag_path)
    
    def speak_with_edge_tts(self, text: str) -> bool:
        """使用 edge-tts 进行语音合成"""
        try:
            import edge_tts
            
            # 创建输出文件
            output_file = tempfile.mktemp(suffix='.mp3')
            
            # 使用 edge-tts
            communicate = edge_tts.Communicate(
                text=text,
                voice=self.config["voice"],
                rate=self.config["rate"],
                volume=self.config["volume"]
            )
            
            # 保存音频文件
            communicate.save(output_file)
            
            # 播放音频
            self._play_audio(output_file)
            
            # 清理临时文件
            try:
                os.remove(output_file)
            except Exception:
                pass

            return True
            
        except ImportError:
            print("edge-tts 未安装，尝试其他方法")
            return False
        except Exception as e:
            print(f"edge-tts 合成失败: {e}")
            return False
    
    def speak_with_system_tts(self, text: str) -> bool:
        """使用系统 TTS（Windows）"""
        try:
            # Windows 系统 TTS
            import win32com.client
            
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            speaker.Speak(text)
            return True
            
        except ImportError:
            print("pywin32 未安装，无法使用系统 TTS")
            return False
        except Exception as e:
            print(f"系统 TTS 失败: {e}")
            return False
    
    def speak_with_pyttsx3(self, text: str) -> bool:
        """使用 pyttsx3 进行语音合成"""
        try:
            import pyttsx3
            
            engine = pyttsx3.init()
            
            # 设置语音属性
            voices = engine.getProperty('voices')
            for voice in voices:
                if 'chinese' in voice.name.lower() or 'zh' in voice.id.lower():
                    engine.setProperty('voice', voice.id)
                    break
            
            engine.say(text)
            engine.runAndWait()
            return True
            
        except ImportError:
            print("pyttsx3 未安装")
            return False
        except Exception as e:
            print(f"pyttsx3 合成失败: {e}")
            return False
    
    def _play_audio(self, audio_file: str):
        """播放音频文件"""
        try:
            # 使用系统命令播放音频
            if sys.platform == "win32":
                # Windows
                os.startfile(audio_file)
            elif sys.platform == "darwin":
                # macOS
                subprocess.run(["afplay", audio_file])
            else:
                # Linux
                subprocess.run(["aplay", audio_file])
                
        except Exception as e:
            print(f"播放音频失败: {e}")
    
    def speak(self, text: str, async_mode: bool = True) -> bool:
        """
        语音合成主函数
        
        参数:
            text: 要合成的文本
            async_mode: 是否异步播放（默认 True）
        
        返回:
            bool: 是否成功
        """
        if not text:
            return False
        
        print(f"TTS: '{text}'")
        
        # 创建标志文件
        if not self.create_flag():
            return False
        
        def _speak_task():
            """实际的语音合成任务"""
            try:
                # 尝试多种 TTS 方法
                methods = [
                    self.speak_with_edge_tts,
                    self.speak_with_pyttsx3,
                    self.speak_with_system_tts,
                ]
                
                success = False
                for method in methods:
                    if method(text):
                        success = True
                        break
                
                if not success:
                    print("所有 TTS 方法都失败了")
                
            finally:
                # 无论成功与否，都移除标志文件
                self.remove_flag()
        
        try:
            if async_mode:
                # 异步播放
                thread = threading.Thread(target=_speak_task, daemon=True)
                thread.start()
                return True
            else:
                # 同步播放
                _speak_task()
                return True
                
        except Exception as e:
            print(f"语音合成出错: {e}")
            self.remove_flag()
            return False
    
    def speak_with_context(self, text: str):
        """
        带上下文管理的语音合成
        
        用法:
            with speaker.speak_with_context("你好"):
                # 在这里执行其他操作
                pass
        """
        class TTSContext:
            def __init__(self, speaker, text):
                self.speaker = speaker
                self.text = text
            
            def __enter__(self):
                if self.speaker.create_flag():
                    # 异步播放
                    thread = threading.Thread(
                        target=self.speaker._speak_sync,
                        args=(self.text,),
                        daemon=True
                    )
                    thread.start()
                return self
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                self.speaker.remove_flag()
        
        return TTSContext(self, text)
    
    def _speak_sync(self, text: str):
        """同步语音合成（内部使用）"""
        methods = [
            self.speak_with_edge_tts,
            self.speak_with_pyttsx3,
            self.speak_with_system_tts,
        ]
        
        for method in methods:
            if method(text):
                return True
        
        return False

def test_tts():
    """测试 TTS 功能"""
    print("TTS 功能测试")
    print("=" * 60)
    
    speaker = TTSSpeaker()
    
    # 测试标志文件管理
    print("1. 测试标志文件管理...")
    speaker.create_flag()
    print(f"   创建标志: {speaker.is_playing()}")
    
    speaker.remove_flag()
    print(f"   移除标志: {not speaker.is_playing()}")
    
    # 测试语音合成
    print("\n2. 测试语音合成...")
    test_texts = [
        "我在，请说命令",
        "语音系统测试成功",
        "当前时间，下午五点三十分",
    ]
    
    for text in test_texts:
        print(f"   合成: '{text}'")
        success = speaker.speak(text, async_mode=False)
        print(f"   结果: {'成功' if success else '失败'}")
    
    # 测试上下文管理
    print("\n3. 测试上下文管理...")
    with speaker.speak_with_context("测试上下文管理"):
        print("   在 TTS 播放期间执行其他操作")
        print(f"   标志状态: {speaker.is_playing()}")
    
    print(f"   播放后标志状态: {not speaker.is_playing()}")
    
    print("\n" + "=" * 60)
    print("TTS 测试完成")

if __name__ == "__main__":
    test_tts()