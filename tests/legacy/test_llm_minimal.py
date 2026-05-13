#!/usr/bin/env python3
"""
最小 LLM Client 测试
目标：验证 LLM Client 可用性，输入 "Hello AI"，返回真实模型结果
"""
import asyncio
import sys
from backend.utils.llm_client import llm_client

async def test_llm_client():
    print("=== LLM Client 最小调用测试 ===")
    print(f"输入文本: 'Hello AI'")
    
    try:
        # 调用 generate 方法
        result = await llm_client.generate("Hello AI", use_long_context=False)
        
        print(f"✓ 调用成功！")
        print(f"返回结果长度: {len(result)} 字符")
        print(f"返回结果预览: {result[:200]}...")
        
        # 验证结果是否为非固定字符串
        if result == "简报生成失败：未配置任何可用的 API 密钥，或所有服务均不可用。":
            print("✗ 错误：返回了固定错误字符串，可能 API 密钥无效或服务不可用")
            return False
        elif len(result.strip()) == 0:
            print("✗ 错误：返回结果为空")
            return False
        else:
            print("✓ 验证通过：返回了非固定字符串结果")
            return True
            
    except Exception as e:
        print(f"✗ 调用失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_llm_client())
    sys.exit(0 if success else 1)