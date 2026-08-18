"""
第 1 课 · 示例 3：结构化输出（JSON）
======================================
运行：python 03_structured.py

LLM 默认输出的是"给人看的自然语言"，但 Agent 要用程序消费模型的输出。
桥就是结构化输出：让模型按规定 schema 吐 JSON，我们 json.loads 后
就能像操作普通 dict 一样操作模型的回答。

这个机制是第 2 课 Function Calling 的直系祖先 —— 工具调用本质上就是
"模型输出一段结构化 JSON：我想调用哪个函数、参数是什么"。
"""
import json
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

# 一个典型任务：从非结构化文本里抽取结构化数据
review = """
这台扫地机器人用了两周。优点是吸力确实大，地毯上的毛发一次过；
App 建图很快，虚拟墙好用。缺点也明显：噪音偏大，白天开着没法看电视；
尘盒偏小，全屋扫一次要倒两次。综合来说家里没宠物的可以买。
"""

schema_hint = """请从用户评论中抽取信息，严格输出如下 JSON（不要输出任何其他文字）：
{
  "sentiment": "positive" | "negative" | "mixed",
  "product": "产品名（字符串）",
  "pros": ["优点1", "优点2"],
  "cons": ["缺点1"],
  "score": 0 到 10 的整数
}"""

messages = [
    {"role": "system", "content": schema_hint},
    {"role": "user", "content": review},
]

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
    temperature=0,                                   # 抽取任务要稳定，用 0
    response_format={"type": "json_object"},         # DeepSeek 支持，强制输出合法 JSON
)

raw = response.choices[0].message.content
print("【模型原始输出】")
print(raw)

# ---- 拿到 JSON 字符串后，程序世界的大门就打开了 ----
data = json.loads(raw)
print("\n【json.loads 之后】")
print(json.dumps(data, ensure_ascii=False, indent=2))

print("\n【像普通 dict 一样消费】")
print("  情感倾向:", data["sentiment"])
print("  缺点数量:", len(data["cons"]))
if data["score"] >= 8:
    print("  判定：推荐")
elif data["score"] >= 5:
    print("  判定：褒贬不一")
else:
    print("  判定：不推荐")

# ---- 生产代码必须有防御：模型输出不能 100% 信任 ----
try:
    assert isinstance(data["score"], int), "score 必须是整数"
    assert data["sentiment"] in ("positive", "negative", "mixed"), "sentiment 取值非法"
except (json.JSONDecodeError, KeyError, AssertionError) as e:
    # 常见补救：把错误信息发回去让模型重试（Agent 里的 self-correction 就源于此）
    print("输出不合规，需要重试：", e)

print("""
要点回顾：
1. temperature=0 + 明确 schema + response_format=json_object = 稳定抽取三件套
2. 永远 try/except 包住 json.loads —— 模型是概率机器，不是数据库
3. 想通了"让模型输出机器可读的 JSON"，下一课的 Function Calling
   只是把这个约定变成了 API 层的正式协议而已
""")
