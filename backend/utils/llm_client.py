import traceback
import asyncio
import re
import httpx
from typing import Optional, List, Dict, Any
from backend.config.config import settings


class LLMClient:
    def __init__(self):
        self.groq_api_key = settings.GROQ_API_KEY
        self.gemini_api_key = settings.GEMINI_API_KEY
        self.zhipu_api_key = settings.ZHIPU_API_KEY

        # 代理配置
        self.proxies = {}
        if settings.HTTP_PROXY:
            self.proxies["http://"] = settings.HTTP_PROXY
        if settings.HTTPS_PROXY:
            self.proxies["https://"] = settings.HTTPS_PROXY

        print(f"Using proxies: {self.proxies}")

        # 限流参数（每分钟请求数）
        self.groq_rpm = 30
        self.gemini_rpm = 10
        self.zhipu_rpm = 30

        # 令牌桶
        self.groq_tokens = asyncio.Queue()
        self.gemini_tokens = asyncio.Queue()
        self.zhipu_tokens = asyncio.Queue()

    async def _acquire_token(self, queue: asyncio.Queue, rpm: int):
        if queue.empty():
            for _ in range(rpm):
                await queue.put(1)
        await queue.get()
        asyncio.create_task(self._refill_token(queue, 60 / rpm))

    async def _refill_token(self, queue: asyncio.Queue, interval: float):
        await asyncio.sleep(interval)
        await queue.put(1)

    def _desensitize(self, text: str) -> str:
        """脱敏：手机号、邮箱、身份证号、详细地址"""
        text = re.sub(r'\b1[3-9]\d{9}\b', '[手机号]', text)
        text = re.sub(r'\b[\w\.-]+@[\w\.-]+\.\w+\b', '[邮箱地址]', text)
        text = re.sub(r'\b\d{17}[\dXx]\b', '[身份证号]', text)
        text = re.sub(r'\b([\u4e00-\u9fa5]{2,}路|[\u4e00-\u9fa5]{2,}街|[\u4e00-\u9fa5]{2,}巷|[\u4e00-\u9fa5]{2,}号)\s*\d+(-\d+)?\b', '[地址]', text)
        return text

    async def analyze_message(self, content: str) -> Dict[str, Any]:
        prompt = f"""分析以下消息，返回 JSON 格式（只输出 JSON，不要其他文字）：
{{
  "subject": "主题",
  "intent": "意图",
  "keyInfo": "关键信息",
  "sentiment": "正面/负面/中性",
  "priority": "高/中/低"
}}
消息内容：{self._desensitize(content)}"""
        result = await self.generate(prompt, use_long_context=False)
        try:
            import json
            return json.loads(result)
        except:
            return {"error": "解析失败", "raw": result}

    async def generate_briefing(self, messages: List[str]) -> str:
        total_chars = sum(len(m) for m in messages)
        if total_chars > 8000:
            return await self._generate_long_briefing(messages)
        else:
            return await self._generate_short_briefing(messages)

    async def _generate_short_briefing(self, messages: List[str]) -> str:
        prompt = "请根据以下消息生成简报（简洁列出要点）：\n\n" + "\n---\n".join(messages)
        return await self.generate(prompt, use_long_context=False)

    async def _generate_long_briefing(self, messages: List[str]) -> str:
        prompt = "请根据以下大量消息生成详细周报，按主题分类：\n\n" + "\n---\n".join(messages)
        return await self.generate(prompt, use_long_context=True)

    async def generate(self, prompt: str, use_long_context: bool = False) -> str:
        # 1. 尝试 Groq（短文本优先）
        if self.groq_api_key:
            try:
                await self._acquire_token(self.groq_tokens, self.groq_rpm)
                return await self._call_groq(prompt)
            except Exception as e:
                print(f"Groq 调用失败: {e}")

        # 2. 尝试 Gemini（长文本或 Groq 不可用）
        if self.gemini_api_key:
            try:
                await self._acquire_token(self.gemini_tokens, self.gemini_rpm)
                return await self._call_gemini(prompt)
            except Exception as e:
                print(f"Gemini 调用失败: {e}")

        # 3. 兜底：智谱
        if self.zhipu_api_key:
            try:
                await self._acquire_token(self.zhipu_tokens, self.zhipu_rpm)
                return await self._call_zhipu(prompt)
            except Exception as e:
                print(f"智谱调用失败: {e}")

        return "简报生成失败：未配置任何可用的 API 密钥，或所有服务均不可用。"

    async def _call_groq(self, prompt: str) -> str:
        try:
            async with httpx.AsyncClient(proxies=self.proxies, timeout=30.0) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.groq_api_key}"},
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.7,
                    },
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print("Groq 调用详细错误:")
            traceback.print_exc()
            raise

    async def _call_gemini(self, prompt: str) -> str:
        """
        调用 Google Gemini API
        文档: https://ai.google.dev/api/rest
        """
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_api_key}"
        async with httpx.AsyncClient(proxies=self.proxies, timeout=30.0) as client:
            try:
                resp = await client.post(
                    url,
                    json={
                        "contents": [
                            {"parts": [{"text": prompt}]}
                        ],
                        "generationConfig": {
                            "temperature": 0.7,
                            "maxOutputTokens": 1024
                        }
                    }
                )
                resp.raise_for_status()
                data = resp.json()
                # 提取文本内容
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except httpx.HTTPStatusError as e:
                print(f"Gemini HTTP 错误: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                print("Gemini 调用详细错误:")
                traceback.print_exc()
                raise

    async def _call_zhipu(self, prompt: str) -> str:
        """
        调用智谱 GLM-4-Flash API
        文档: https://open.bigmodel.cn/dev/api
        """
        url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        async with httpx.AsyncClient(proxies=self.proxies, timeout=30.0) as client:
            try:
                resp = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {self.zhipu_api_key}"},
                    json={
                        "model": "glm-4-flash",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.7,
                        "max_tokens": 1024
                    }
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]
            except httpx.HTTPStatusError as e:
                print(f"智谱 HTTP 错误: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                print("智谱调用详细错误:")
                traceback.print_exc()
                raise

llm_client = LLMClient()


