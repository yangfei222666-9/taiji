#!/usr/bin/env python3
"""
向后兼容 shim — SimpleTTS 现在是 TTSSpeaker 的别名。
统一语音方案后，所有 TTS 功能由 tts_speaker.py 提供。
"""
from tools.tts_speaker import TTSSpeaker as SimpleTTS  # noqa: F401

if __name__ == "__main__":
    tts = SimpleTTS()
    tts.speak("语音系统测试成功", async_mode=False)
