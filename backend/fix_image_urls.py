#!/usr/bin/env python3
"""
修复故事数据中的图片 URL
将 http://localhost:xxxx/static/images/xxx.jpg 转换为 /static/images/xxx.jpg
"""
import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data" / "stories"

def fix_url(url):
    """将绝对 URL 转换为相对路径"""
    if not url:
        return url
    # 匹配 http(s)://localhost|127.0.0.1:任意端口/static/images/文件名
    pattern = r'https?://(?:localhost|127\.0\.0\.1):\d+(/static/images/[^"]+)'
    match = re.search(pattern, url, re.IGNORECASE)
    if match:
        return match.group(1)
    if url.startswith("static/images/"):
        return f"/{url}"
    return url

def fix_story_file(file_path):
    """修复单个故事文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        modified = False
        
        # 修复每个段落的 image_url
        if 'segments' in data:
            for seg in data['segments']:
                if 'image_url' in seg and seg['image_url']:
                    old_url = seg['image_url']
                    new_url = fix_url(old_url)
                    if old_url != new_url:
                        seg['image_url'] = new_url
                        modified = True
                        print(f"  ✓ {old_url} -> {new_url}")
        
        # 保存修改
        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        return False
    except Exception as e:
        print(f"  ✗ 处理失败: {e}")
        return False

def main():
    print("=" * 60)
    print("修复故事数据中的图片 URL")
    print("=" * 60)
    print()
    
    if not DATA_DIR.exists():
        print(f"❌ 数据目录不存在: {DATA_DIR}")
        return
    
    story_files = list(DATA_DIR.glob("*.json"))
    if not story_files:
        print(f"📁 数据目录为空: {DATA_DIR}")
        return
    
    print(f"📂 找到 {len(story_files)} 个故事文件")
    print()
    
    fixed_count = 0
    for file_path in story_files:
        if file_path.name == "_index.json":
            continue
        print(f"📖 处理: {file_path.name}")
        if fix_story_file(file_path):
            fixed_count += 1
    
    print()
    print("=" * 60)
    print(f"✅ 完成！修复了 {fixed_count} 个文件")
    print("=" * 60)

if __name__ == "__main__":
    main()
