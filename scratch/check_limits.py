import os
import requests
from groq import Groq

api_key = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=api_key)

response = requests.post(
    "https://api.groq.com/openai/v1/chat/completions",
    headers={"Authorization": f"Bearer {api_key}"},
    json={
        "model": "qwen/qwen3.6-27b",
        "messages": [{"role": "user", "content": "Hello"}]
    }
)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    print("Tokens remaining today:")
    for k, v in response.headers.items():
        if "ratelimit" in k.lower():
            print(f"{k}: {v}")
else:
    print(response.text)
