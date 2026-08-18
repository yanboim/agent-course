"""
第 2 课 · 示例 3：错误回传与自我纠正 + 协议红线实验
=====================================================
运行：python 03_error_feedback.py

认知目标：
1. 工具执行失败时，【不要抛异常打断流程】，把 ERROR 文本作为 tool 消息
   发回去 —— 模型会看到错误并调整策略（换参数/换工具/向用户澄清）
2. self-correction（自我纠正）：Agent 韧性的来源
3. 协议红线：有 tool_calls 就必须有对应的 tool 消息，否则 API 直接 400
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

# ============ 一个"会失败"的工具：查询订单 ============
ORDERS = {"A1024": "已发货，顺丰，预计明天到", "B2048": "待付款"}


def query_order(order_id: str) -> str:
    if order_id not in ORDERS:
        # 关键认知：工具"失败"不抛异常，返回错误描述文本
        # —— 让模型读到错误，自己决定下一步
        return f"ERROR: 查无订单 {order_id}。已知订单只有: {list(ORDERS)}"
    return f"订单 {order_id}: {ORDERS[order_id]}"


tools = [{"type": "function", "function": {
    "name": "query_order",
    "description": "按订单号查询订单状态。订单号形如 A1024 / B2048。",
    "parameters": {"type": "object", "properties": {
        "order_id": {"type": "string"},
    }, "required": ["order_id"]},
}}]


def run(task: str) -> None:
    messages = [
        {"role": "system", "content": "你是客服助手，只能依据工具结果回答。"},
        {"role": "user", "content": task},
    ]
    for turn in range(1, 5):
        r = client.chat.completions.create(
            model="deepseek-v4-flash", messages=messages, tools=tools,
        )
        m = r.choices[0].message
        messages.append({"role": "assistant", "content": m.content, "tool_calls": [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in (m.tool_calls or [])
        ]})
        if not m.tool_calls:
            print(f"[第{turn}轮·最终回答] {m.content}\n")
            return
        for tc in m.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            print(f"[第{turn}轮·动作] {tc.function.name}({args})")
            result = query_order(**args)
            print(f"[第{turn}轮·观察] {result[:100]}")
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})


# ============ 实验 1：模型拿着不存在的订单号来查 ============
print("=" * 60)
print("实验 1：工具报错 -> 错误回传 -> 模型自我纠正")
print("=" * 60)
run("帮我查一下订单 C9999 的状态。")

# ============ 实验 2：踩协议红线 —— 不回传 tool 消息 ============
print("=" * 60)
print("实验 2：有 tool_calls 却不回传 tool 消息（预期 API 400）")
print("=" * 60)
try:
    r1 = client.chat.completions.create(
        model="deepseek-v4-flash",
        messages=[{"role": "user", "content": "查订单 A1024"}],
        tools=tools,
    )
    m = r1.choices[0].message
    print("模型第 1 步没问题，返回了 tool_calls:", [tc.function.name for tc in m.tool_calls])
    # 故意【不】append tool 消息，直接再问 —— 违反协议
    client.chat.completions.create(
        model="deepseek-v4-flash",
        messages=[
            {"role": "user", "content": "查订单 A1024"},
            {"role": "assistant", "content": m.content, "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in m.tool_calls
            ]},
            # 缺失：{"role": "tool", "tool_call_id": ..., "content": ...}
            {"role": "user", "content": "怎么还不给我结果？"},
        ],
        tools=tools,
    )
    print("居然成功了？—— 服务器比预想宽容，但别依赖这个行为")
except Exception as e:
    print(f"被服务器拒绝！错误类型: {type(e).__name__}")
    print(f"错误信息（截断）: {str(e)[:300]}")

print("""
要点回顾：
1. 工具失败 -> 返回 ERROR 文本而不是抛异常 -> 模型读到错误自我纠正
   （这就是 Agent 的"韧性"：错误也是一次 Observation）
2. 协议要求每个 tool_call 都有对应 tool 消息 —— 写循环时漏掉就会炸
3. 生产建议：无论服务器是否宽容，都严格走完协议
""")
