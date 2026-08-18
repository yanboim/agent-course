"""
第 1 课 · 示例 1：你的第一次 LLM API 调用 + "模型无记忆"实验
=============================================================
运行：python 01_first_call.py

本文件要让你带走的三个认知：
1. 调 LLM 就是发一个 messages 列表（对话的完整誊写本）
2. response 里哪几个字段值得看
3. 【最重要】模型本身没有记忆 —— 所谓"多轮对话"，是你的代码
   把历史一次次重新发过去而已。这个认知是将来一切 Agent
   记忆管理（第 5 课）的地基。
"""
import os
from dotenv import load_dotenv
from openai import OpenAI

# 从 .env 文件读环境变量。API key 永远不写死在代码里 —— 基本职业习惯
load_dotenv()

# DeepSeek 完全兼容 OpenAI 的接口格式，所以直接用 openai 这个库，
# 只需把 base_url 指向 DeepSeek。你在网上看到的 OpenAI 教程几乎可以照搬。
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

# ============ messages：LLM 眼中的"对话" ============
# 每条消息是 {role, content}，role 有三种：
#   system    -> 给模型的"岗位说明书"，设定它的身份和行为边界
#   user      -> 用户说的话
#   assistant -> 模型【之前】的回复，由你的代码手动拼进去
messages = [
    {"role": "system", "content": "你是一个简洁的中文技术助手，回答不超过两句话。"},
    {"role": "user", "content": "用一句话解释什么是 API"},
]

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
    temperature=0.7,     # 采样随机性：0=几乎每次相同，越大越发散（0~2）
    # max_tokens=100,    # 可选：限制回复长度
)

# ============ 解剖 response：这三个地方以后天天打交道 ============
print("=" * 50)
print("【模型回复】")
print("response",response)
print(response.choices[0].message.content)

print("\n【finish_reason】", response.choices[0].finish_reason)
#   stop   = 正常说完
#   length = 被 max_tokens 截断了（Agent 里要特殊处理，见第 2 课）

print("\n【token 用量】")
print("  prompt（输入消耗）:", response.usage.prompt_tokens)
print("  completion（输出消耗）:", response.usage.completion_tokens)
print("  总计:", response.usage.total_tokens)
# 计费就按这个来。Agent 是"token 貪食蛇"—— 每轮循环都重发全部历史，
# 所以第 5 课要学上下文裁剪，本质是为了省钱 + 不撑爆窗口。

# ============ 实验：证明模型没有记忆 ============
print("\n" + "=" * 50)
print("实验：两连问，观察'带不带历史'的区别\n")

# 第一问：告诉它名字
r1 = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "我叫小明。请只回复'好的'。"}],
)
print("r1.choices[0].message.content",r1.choices[0].message.content)
print("第一问：我叫小明 ->", r1.choices[0].message.content.strip())

# 第二问【不带历史】：全新的一次调用，模型根本不知道上一轮说过什么
r2 = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "我叫什么名字？"}],
)
print("第二问（不带历史）：我叫什么名字？ ->", r2.choices[0].message.content.strip())

# 第二问【带历史】：把上一轮的问答誊写进 messages 再问
r3 = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "user", "content": "我叫小明。请只回复'好的'。"},
        {"role": "assistant", "content": r1.choices[0].message.content},
        {"role": "user", "content": "我叫什么名字？"},
    ],
)
print("第二问（带历史）  ：我叫什么名字？ ->", r3.choices[0].message.content.strip())

print("""
结论：
  ChatGPT 网页上那种"它记得我"的效果，是网站后端把历史存数据库、
  每次请求重新拼接发送实现的。模型本身是无状态的纯函数：
      f(messages) -> 新消息
  记忆 = 你的代码工程，不是模型的能力。记住这一点，Agent 的
  很多设计（上下文裁剪、摘要、外部存储）就都顺理成章了。
""")
