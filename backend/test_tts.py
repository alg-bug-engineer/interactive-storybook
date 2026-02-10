"""测试 edge-tts 是否正常工作"""
import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    import edge_tts
    print("✅ edge-tts 已安装")
    print(f"   版本: {edge_tts.__version__ if hasattr(edge_tts, '__version__') else '未知'}")
except ImportError:
    print("❌ edge-tts 未安装")
    print("   请运行: pip install edge-tts")
    sys.exit(1)


async def test_tts():
    """测试 TTS 生成"""
    print("\n🧪 测试 TTS 生成...")
    
    test_text = "你好，这是一个测试。"
    output_file = "test_tts_output.mp3"
    voice_id = "zh-CN-XiaoxiaoNeural"
    
    try:
        print(f"   文本: {test_text}")
        print(f"   音色: {voice_id}")
        print(f"   输出: {output_file}")
        print("   生成中...")
        
        communicate = edge_tts.Communicate(test_text, voice_id)
        await communicate.save(output_file)
        
        # 检查文件
        if Path(output_file).exists():
            file_size = Path(output_file).stat().st_size
            print(f"✅ 生成成功！文件大小: {file_size} bytes")
            print(f"   可以播放: {output_file}")
            return True
        else:
            print("❌ 文件未生成")
            return False
            
    except Exception as e:
        print(f"❌ 生成失败: {e}")
        print(f"   错误类型: {type(e).__name__}")
        
        if "403" in str(e):
            print("\n💡 可能的原因：")
            print("   1. edge-tts 版本过旧，请升级: pip install --upgrade edge-tts")
            print("   2. Microsoft TTS 服务暂时不可用")
            print("   3. 网络环境限制（代理/防火墙）")
            print("\n💡 解决方案：")
            print("   1. 等待几分钟后重试")
            print("   2. 检查网络连接")
            print("   3. 考虑使用备用 TTS 方案（如 gTTS）")
        
        return False


async def list_voices():
    """列出可用音色"""
    print("\n📋 可用中文音色:")
    try:
        voices = await edge_tts.list_voices()
        zh_voices = [v for v in voices if v["Locale"].startswith("zh-CN")]
        
        for v in zh_voices:
            print(f"   - {v['ShortName']}: {v['FriendlyName']}")
        
        print(f"\n   共 {len(zh_voices)} 个中文音色")
        
    except Exception as e:
        print(f"❌ 获取音色列表失败: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("🎙️  Edge TTS 测试工具")
    print("=" * 60)
    
    # 测试生成
    success = asyncio.run(test_tts())
    
    # 列出音色
    # asyncio.run(list_voices())
    
    print("\n" + "=" * 60)
    if success:
        print("✅ TTS 服务正常")
    else:
        print("❌ TTS 服务异常，请检查上述错误信息")
    print("=" * 60)
