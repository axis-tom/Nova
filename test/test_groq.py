import os
import sys
import requests

# 配置
API_KEY = os.environ.get("GROQ_API_KEY", "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")  # 优先从环境变量读取
URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "mixtral-8x7b-32768"  # 可选: llama3-70b-8192, gemma2-9b-it 等
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}
PAYLOAD = {
    "model": MODEL,
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, are you working? Respond with 'Yes, I am working fine.'"}
    ],
    "temperature": 0,
    "max_tokens": 50
}

def test_groq_api():
    if API_KEY == "your-api-key-here":
        print("❌ 错误: 请先设置 GROQ_API_KEY 环境变量或在脚本中填入有效密钥。")
        sys.exit(1)

    try:
        response = requests.post(URL, headers=HEADERS, json=PAYLOAD, timeout=30)
        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            print("✅ Groq API 测试成功！")
            print("回复内容：", content)
        else:
            print(f"❌ API 请求失败，状态码: {response.status_code}")
            print("响应详情：", response.text)
    except requests.exceptions.RequestException as e:
        print("❌ 网络请求异常：", e)

if __name__ == "__main__":
    test_groq_api()