"""
第 2 课 · 示例 2：多工具选择 + 并行调用 + 通用循环雏形
=========================================================
运行：python 02_multi_tools.py

认知目标：
1. 模型在多个工具间怎么选？—— 全靠 description（模型的"工具目录"）
2. 一轮可以返回【多个】tool_calls（并行调用），必须逐个执行、逐个回应
3. 把"调工具<->拿结果"写成 while 循环 —— 这就是第 3 课 Agent 的雏形：
   循环退出条件 = finish_reason 不再是 'tool_calls'
"""
import json
import os
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

# ============ 三个本地函数 ============
def calculate(expression: str) -> str:
    """假装是精确计算器（演示用，直接 eval 不安全，这里限位数）"""
    if not expression or len(expression) > 100:
        return "ERROR: 表达式太长"
    allowed = set("0123456789+-*/(). %")
    if not set(expression) <= allowed:
        return "ERROR: 表达式含非法字符"
    return f"{expression} = {eval(expression)}"     # 仅课堂演示，生产见第 4 课安全做法


def get_current_time() -> str:
    return datetime.now().strftime("现在时间是 %Y-%m-%d %H:%M:%S（星期%w）")


def get_weather(city: str) -> str:
    db = {"北京": "晴 22°C", "上海": "多云 26°C", "广州": "雷阵雨 31°C"}
    return db.get(city, f"暂无 {city} 的天气数据")


TOOL_FUNCS = {
    "calculate": calculate,
    "get_current_time": get_current_time,
    "get_weather": get_weather,
}

# ============ 工具说明书（模型的"目录"） ============
tools = [
    {"type": "function", "function": {
        "name": "calculate",
        "description": "精确计算数学表达式。任何算术问题都必须用它，禁止心算。",
        "parameters": {"type": "object", "properties": {
            "expression": {"type": "string", "description": "如 '123*456'"},
        }, "required": ["expression"]},
    }},
    {"type": "function", "function": {
        "name": "get_current_time",
        "description": "获取当前的日期和时间。用户问'现在/今天/几点'时使用。",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "get_weather",
        "description": "查询城市实时天气。",
        "parameters": {"type": "object", "properties": {
            "city": {"type": "string"},
        }, "required": ["city"]},
    }},
]

# ============ 通用循环：跑完就不许说看不懂 Agent ============
def run(task: str, max_turns: int = 6) -> str:
    messages = [
        {"role": "system", "content": "你是严谨的助手：能用工具就用工具，禁止编造。"},
        {"role": "user", "content": task},
    ]
    for turn in range(1, max_turns + 1):
        r = client.chat.completions.create(
            model="deepseek-chat", messages=messages, tools=tools,
        )
        m = r.choices[0].message
        finish = r.choices[0].finish_reason

        # 誊写模型这条消息（无论是否带 tool_calls）
        entry = {"role": "assistant", "content": m.content, "tool_calls": [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in (m.tool_calls or [])
        ]}
        messages.append(entry)

        # ---- 退出条件：模型不再要工具，给出最终回答 ----
        if finish != "tool_calls" or not m.tool_calls:
            print(f"[第{turn}轮] 模型给出最终回答（finish_reason={finish}）")
            return m.content

        # ---- 执行本轮所有调用（可能多个 = 并行调用） ----
        print(f"[第{turn}轮] 模型要求 {len(m.tool_calls)} 个工具调用:")
        for tc in m.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments or "{}")
            print(f"    -> {name}({args})")
            result = str(TOOL_FUNCS[name](**args))     # 本地执行
            print(f"       结果: {result[:80]}")
            messages.append({                          # 逐个"对号入座"回传
                "role": "tool", "tool_call_id": tc.id,
                "content": result,
            })
    return "(达到最大轮数，强制停止 —— 防死循环，第 3 课会常见)"


# ============ 演示 1：一个任务串起三个工具 ============
print("=" * 60)
print("演示 1：多工具任务")
print("=" * 60)
answer = run("现在几点了？另外帮我算 123*456，再查一下北京天气，"
             "最后把三个信息合成一段话汇报。")
print("\n最终回答：\n", answer)

# ============ 演示 2：观察"并行调用" ============
print()
print("=" * 60)
print("演示 2：诱导并行调用（一次性要两个互不依赖的数据）")
print("=" * 60)
answer = run("帮我查北京和上海两个城市的天气。")
print("\n最终回答：\n", answer)

print("""
要点回顾：
1. 工具选择全靠 description —— 它就是模型的"工具目录"
2. 一轮可返回多个 tool_calls（并行），逐个执行、靠 tool_call_id 逐个回应
3. while + finish_reason 判断 = Agent 主循环的全部骨架（第 3 课见 100 行版）
""")
