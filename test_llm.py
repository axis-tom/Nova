import asyncio
import traceback
from backend.utils.llm_client import llm_client

async def test():
    print("测试智谱 GLM-4-Flash:")
    try:
        result = await llm_client._call_zhipu("你好，请用中文介绍你自己。")
        print("成功:", result[:200])
    except Exception as e:
        traceback.print_exc()

asyncio.run(test())