"""
第 2 课 · 示例 1：第一次 Function Calling —— 三段式协议全程解剖
=================================================================
运行：python 01_first_tool_call.py

核心认知（本课全部）：
1. 模型从不执行函数！它只输出结构化 JSON："我想调 get_weather(北京)"
2. 执行者是你的代码；模型是大脑，你是手
3. 一次工具调用 = 两次 API 请求夹一次本地函数执行：
   请求A(带tools) -> 模型回 tool_calls -> 你执行 -> 结果以 role="tool"
   拼回 messages -> 请求B -> 模型生成最终回答
4. 对照第 1 课：tool 结果也只是"誊写进上下文的文本"而已
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

# ============ 本地函数：模型看不见这行代码，只看得见说明书 ============
def get_weather(city: str) -> dict:
    """假工具。真实项目里这里会是 HTTP 请求天气 API。"""
    fake_db = {
        "北京": {"temp_c": 22, "condition": "晴", "aqi": 45},
        "上海": {"temp_c": 26, "condition": "多云", "aqi": 60},
    }
    return fake_db.get(city, {"error": f"查不到城市：{city}"})


# ============ ① 用 JSON Schema 向模型"注册"函数 ============
# 模型决策的全部依据只有：name / description / parameters 结构
# description 写得好不好，直接决定模型什么时候想起这个工具
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市的实时天气。用户问到天气、温度、空气质量时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名，如 '北京'"},
                },
                "required": ["city"],
            },
        },
    }
]

messages = [
    {"role": "system", "content": "你是天气助手，必须通过工具查询数据，禁止编造。"},
    {"role": "user", "content": "北京今天天气怎么样？"},
]

# ============ ② 请求 A：模型决定"调工具" ============
print("=" * 55)
print("【第 1 次请求】模型看到 tools 说明书，决定怎么回应")
print("=" * 55)
r1 = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
    tools=tools,        # 关键：工具说明书随请求发给模型
)
msg = r1.choices[0].message

print("finish_reason:", r1.choices[0].finish_reason)  # 'tool_calls' = 它想调工具
print("content      :", msg.content)                   # 思考性文本，可能为 None
print("tool_calls   :")
for tc in msg.tool_calls:
    print("  函数名 :", tc.function.name)
    print("  参数   :", tc.function.arguments)          # 注意：是 JSON 字符串！
    print("  调用id :", tc.id)                           # 回传结果时对号入座用

# 关键一步：模型这条"我想调工具"的消息也要誊写回历史（它是对话的一部分）
messages.append({
    "role": "assistant",
    "content": msg.content,
    "tool_calls": [
        {"id": tc.id, "type": "function",
         "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
        for tc in msg.tool_calls
    ],
})

# ============ ③ 你的代码执行函数（模型在这里毫无参与） ============
print()
print("=" * 55)
print("【本地执行】你的代码真正运行函数")
print("=" * 55)
tc = msg.tool_calls[0]
args = json.loads(tc.function.arguments)      # arguments 是 JSON 字符串，要解析
print("解析出的参数:", args)
result = get_weather(**args)                   # 真正的执行点！
result_str = json.dumps(result, ensure_ascii=False)
print("执行结果:", result_str)

# ============ ④ 以 role="tool" 回传，发起请求 B ============
messages.append({
    "role": "tool",
    "tool_call_id": tc.id,        # 对号入座：回应哪一次调用
    "content": result_str,        # content 必须是字符串
})

print()
print("=" * 55)
print("【第 2 次请求】模型读到工具结果，生成最终回答")
print("=" * 55)
r2 = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,            # 此时历史已有 4 条：system/user/assistant(tool_calls)/tool
    tools=tools,
)
final = r2.choices[0].message.content
print("最终回答:", final)
print("finish_reason:", r2.choices[0].finish_reason)   # 'stop' = 正常说完

# ============ 对照实验：不给 tools 会怎样？ ============
print()
print("=" * 55)
print("【对照】同样的提问，但不给 tools —— 模型只能编")
print("=" * 55)
r3 = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "你是天气助手。"},
        {"role": "user", "content": "北京今天天气怎么样？"},
    ],
    # 没有 tools —— 模型没有任何数据来源，只能一本正经地编一个
)
print("无工具时的回答:", r3.choices[0].message.content)
print("(天气数据是编的 —— 工具的意义就是把'编'变成'查')")

print("""
要点回顾：
1. 模型输出的是"调用意图"(JSON)，执行永远在你的代码里
2. tool_calls 消息和 tool 结果消息都要誊写回 messages —— 还是第 1 课那套
3. tool_call_id 是"对号入座"的关键：一轮多个调用时靠它配对
4. 没有工具时模型不是拒绝回答，而是编 —— Agent 要靠 system prompt + 工具来治
""")
