#!/usr/bin/env python3
"""快速测试后端 API 是否正常"""
import httpx
import sys

try:
    resp = httpx.get("http://localhost:8100/health", timeout=5)
    print(f"✅ Health check: {resp.status_code} - {resp.json()}")
    
    resp = httpx.get("http://localhost:8100/", timeout=5)
    print(f"✅ Root endpoint: {resp.status_code} - {resp.json()}")
    
    print("\n✅ 后端 API 正常运行！")
except Exception as e:
    print(f"❌ 后端连接失败: {e}")
    sys.exit(1)
