"""
TokenRouter client — OpenAI-compatible drop-in for 50+ models.
Uses your $200 free hackathon credit.
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url=os.getenv("TOKENROUTER_BASE_URL", "https://api.tokenrouter.io/v1"),
    api_key=os.getenv("TOKENROUTER_API_KEY", ""),
)


def chat(prompt: str, model: str = "claude-opus-4-7") -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    print(chat("What is the best way to generate B2B leads using AI?"))
