"""
第 3 课：手写 ReAct Agent —— 约 100 行的 Agent 主循环
=======================================================
运行：python agent.py

第 2 课你已经见过协议了：模型要工具 -> 你执行 -> 结果回传 -> 再问模型。
本课只做一件事：把这个协议包进 while 循环。就这么多 —— 这就是 Agent。

    while True:
        回答 = 问模型(历史 + 工具说明书)
        if 回答不带 tool_calls:  return 回答        # 思考完毕，出口
        for 每个调用: 历史.append(执行结果)           # Action + Observation

ReAct = Reason + Act：每轮循环里
    Thought（思考，模型的 content）-> Action（tool_calls）-> Observation（tool 结果）
循环往复，直到模型认为可以作答。没有任何魔法。

阅读顺序：先看工具函数 -> 再看 TOOLS 说明书 -> 最后盯死 run_agent() 的循环体。
"""
import ast
import json
import os
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
from pathlib import Path

load_dotenv()
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
MODEL = "deepseek-v4-flash"

BASE_DIR = Path(__file__).parent.resolve()   # "本目录" = 脚本所在目录

# ==================== 一、工具（模型的手） ====================
def calculate(expression: str) -> str:
    """安全计算器：用 ast 白名单求值，绝不 eval 模型给的字符串"""
    ops = {
        ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
        ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b,
        ast.Mod: lambda a, b: a % b, ast.Pow: lambda a, b: a ** b,
        ast.FloorDiv: lambda a, b: a // b, ast.USub: lambda a: -a,
    }

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.BinOp) and type(node.op) in ops:
            return ops[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in ops:
            return ops[type(node.op)](ev(node.operand))
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("不支持的表达式元素")

    return f"{expression} = {ev(ast.parse(expression, mode='eval'))}"


def web_search(query: str) -> str:
    """假搜索引擎：真实项目换成搜索 API（第 4 课接 HTTP）"""
    kb = {
        "react": "ReAct 是一种 Agent 设计模式：LLM 交替进行 Thought(思考)->Action(调工具)->Observation(观察) 的循环，直到得出最终答案。出自 2022 年论文《ReAct: Synergizing Reasoning and Acting in Language Models》。",
        "agent": "Agent 是以 LLM 为大脑、以循环为骨架的程序：每轮模型决定下一步动作（作答或调工具），执行后结果进入下一轮上下文。",
    }
    for key, text in kb.items():
        if key in query.lower():
            return f"[搜索:{query}] {text}"
    return f"[搜索:{query}] 无直接结果。仅有一条：Agent 开发的关键是先手写循环再上框架。"


def get_current_time() -> str:
    return datetime.now().strftime("现在时间是 %Y-%m-%d %H:%M:%S")


def read_file(path: str) -> str:
    """读取本目录内的文本文件；越界/不存在一律返回 ERROR 文本"""
    full = (BASE_DIR / path).resolve()            # 拼接 + 解析掉 ./ ../ 花招
    if full != BASE_DIR and BASE_DIR not in full.parents:   # 监狱检查
        return f"ERROR: 路径越界，只允许读取本目录({BASE_DIR.name}/)内的文件"
    if not full.is_file():
        return f"ERROR: 文件不存在: {path}"
    return full.read_text(encoding="utf-8")[:1500]          # 截断防撑爆上下文


TOOL_FUNCS = {"calculate": calculate, "web_search": web_search,
              "get_current_time": get_current_time}

# ==================== 二、工具说明书（模型的目录） ====================
TOOLS = [
    {"type": "function", "function": {
        "name": "web_search",
        "description": "搜索互联网信息。需要事实性知识（概念、新闻、论文）时使用。",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "搜索关键词"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "calculate",
        "description": "精确计算数学表达式。一切算术必须用它，禁止心算。",
        "parameters": {"type": "object", "properties": {
            "expression": {"type": "string", "description": "如 '(3567*89+1234)/7'"}},
            "required": ["expression"]}}},
    {"type": "function", "function": {
        "name": "get_current_time", "description": "获取当前日期时间。",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "read_file", "description": "读取本目录内的文本文件内容。",
        "parameters": {"type": "object", "properties": {}}}},    
]

SYSTEM = ("你是一个会使用工具的助手。规则：涉及事实与计算必须调用工具，"
          "拿到结果后才能下结论；禁止编造。工具失败时换一种方式再试。")


# ==================== 三、Agent 主循环（本课的全部） ====================
def run_agent(task: str, max_turns: int = 8) -> str:
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": task},
    ]
    total_prompt_tokens = 0            # 直观展示"token 贪食蛇"

    for turn in range(1, max_turns + 1):
        # --- Thought：带着全部历史 + 工具说明书问模型 ---
        r = client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOLS,
        )
        m = r.choices[0].message
        total_prompt_tokens += r.usage.prompt_tokens

        # 誊写：模型这轮的话（含调用意图）也是历史的一部分
        messages.append({"role": "assistant", "content": m.content, "tool_calls": [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in (m.tool_calls or [])]})

        if not m.tool_calls:                       # 出口：不再要工具 = 思考完毕
            print(f"\n[第{turn}轮·最终回答] {m.content}")
            print(f"[统计] 共 {turn} 轮调用，累计输入 token ≈ {total_prompt_tokens}")
            print(f"messages: {messages}")
            return m.content

        if m.content:                              # Thought 文本（可无）
            print(f"[第{turn}轮·思考] {m.content}")

        # --- Action + Observation：执行每个调用，结果回传 ---
        for tc in m.tool_calls:
            name, raw = tc.function.name, tc.function.arguments
            print(f"name {name} , raw {raw}")
            try:
                args = json.loads(raw or "{}")
                result = str(TOOL_FUNCS[name](**args))
            except Exception as e:                 # 错误也是一种 Observation
                result = f"ERROR: {type(e).__name__}: {e}"
            print(f"[第{turn}轮·动作] {name}({raw})")
            print(f"[第{turn}轮·观察] {result[:100]}")
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
    return "(超过最大轮数，强制停止 —— 防死循环兜底)"


if __name__ == "__main__":
    TASK = ("先搜索一下什么是 ReAct 模式和与LangGraph，比较下它们的区别；再用计算器精确计算 (3567*89+1234)/7；并且读取本地文件secret.txt,并输出其结果"
            "最后把两个答案整合成一段话告诉我。")
    print("=" * 60)
    print("任务:", TASK)
    print("=" * 60)
    run_agent(TASK)
    print("""
要点回顾：
1. Agent = 第 2 课的协议 + while 循环，没有别的了
2. 出口条件：模型不再请求工具（finish_reason != 'tool_calls'）
3. max_turns 兜底：模型可能陷入循环，工程上必须设上限
4. 累计 prompt token 逐轮暴涨 —— 历史每轮全量重发（第 5 课主题）
""")
