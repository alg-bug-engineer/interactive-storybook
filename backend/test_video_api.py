"""
测试视频生成 API
运行前请确保：
1. 后端服务已启动
2. 已完成至少一个故事
"""
import asyncio
import httpx
import time

API_BASE = "http://localhost:8100"

async def test_video_generation():
    """测试视频生成流程"""
    
    print("=== 测试视频生成功能 ===\n")
    
    # 1. 创建一个测试故事
    print("1. 创建测试故事...")
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{API_BASE}/api/story/start")
        if resp.status_code != 200:
            print(f"❌ 创建故事失败: {resp.text}")
            return
        
        story = resp.json()
        story_id = story["story_id"]
        print(f"✅ 故事创建成功: {story_id}")
        print(f"   标题: {story['title']}")
        print(f"   总段落数: {story['total_segments']}")
    
    # 2. 快速浏览所有段落（触发图片生成）
    print("\n2. 浏览故事段落...")
    current_index = 0
    total_segments = story["total_segments"]
    
    while current_index < total_segments - 1:
        print(f"   浏览段落 {current_index + 1}/{total_segments}...")
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{API_BASE}/api/story/{story_id}/next")
            if resp.status_code != 200:
                print(f"   ⚠️ 获取下一段失败")
                break
            
            data = resp.json()
            current_index = data["current_index"]
            
            # 等待图片生成
            if data.get("current_segment") and not data["current_segment"].get("image_url"):
                print(f"   ⏳ 等待图片生成...")
                await asyncio.sleep(5)
    
    print(f"✅ 故事浏览完成，共 {total_segments} 段\n")
    
    # 3. 查看已生成的视频片段
    print("3. 查看已生成的视频片段...")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{API_BASE}/api/video/clips/{story_id}")
        if resp.status_code == 200:
            clips = resp.json()
            print(f"   已生成片段数: {clips['total_clips']}")
            for clip_key, clip_url in clips['video_clips'].items():
                print(f"   - {clip_key}: {clip_url[:80]}...")
        else:
            print(f"   ⚠️ 暂无视频片段")
    
    # 4. 启动完整视频生成
    print("\n4. 启动完整视频生成...")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{API_BASE}/api/video/generate",
            json={
                "story_id": story_id,
                # enable_audio 使用默认值 True (从缓存加载音频)
            }
        )
        
        if resp.status_code != 200:
            print(f"❌ 启动视频生成失败: {resp.text}")
            return
        
        result = resp.json()
        print(f"✅ 视频生成任务已启动")
        print(f"   状态: {result['status']}")
    
    # 5. 轮询视频生成状态
    print("\n5. 监控视频生成进度...")
    max_wait_time = 600  # 最多等待 10 分钟
    start_time = time.time()
    
    while time.time() - start_time < max_wait_time:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{API_BASE}/api/video/status/{story_id}")
            if resp.status_code != 200:
                print(f"   ⚠️ 查询状态失败")
                break
            
            status = resp.json()
            progress = status['progress']
            state = status['status']
            generated = status['generated_clips']
            total = status['total_clips']
            
            print(f"   进度: {progress}% | 状态: {state} | 片段: {generated}/{total}")
            
            if state == "completed":
                print(f"\n✅ 视频生成成功！")
                print(f"   视频路径: {status['video_url']}")
                print(f"   下载地址: {API_BASE}/api/video/download/{story_id}")
                break
            elif state == "failed":
                print(f"\n❌ 视频生成失败: {status.get('error', '未知错误')}")
                break
            
            await asyncio.sleep(3)
    else:
        print(f"\n⏱️ 等待超时（{max_wait_time}秒）")
    
    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    asyncio.run(test_video_generation())
