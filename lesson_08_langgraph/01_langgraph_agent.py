"""
第 8 课：用 LangGraph 重写第 3 课的 Agent —— 框架到底解决了什么
=================================================================
运行（需先装依赖，见 README）：
    uv pip install langgraph --index-url https://mirrors.aliyun.com/pypi/simple/
    python 01_langgraph_agent.py

先想清楚再读代码：第 3 课手写的循环，每一部分对应 LangGraph 的什么？

    手写版                         LangGraph 版
    --------------------------     ---------------------------------
    messages 列表                  State（状态，含 reducer）
    while True                     图的边 + 条件边（循环由图表达）
    if not m.tool_calls: return    条件边指向 END
    for tc: 执行+回传              tools 节点
    max_turns 兜底                 recursion_limit

框架真正多给的（手写要费劲的部分）：
    checkpoint 持久化（中断恢复/时间旅行调试）、human-in-the-loop 中断、
    多节点并行分支、状态流转的可观测性。
循环本身？框架和你的 while 没有区别 —— 这就是"先见循环，再见封装"。
"""
import ast
import json
import os
from typing import Annotated, TypedDict
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from openai import OpenAI

load_dotenv()
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
MODEL = "deepseek-chat"

# ==================== 工具（与第 3 课相同） ====================
OPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
       ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b,
       ast.Mod: lambda a, b: a % b, ast.Pow: lambda a, b: a ** b,
       ast.USub: lambda a: -a}


def calculate(expression: str) -> str:
    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.BinOp) and type(node.op) in OPS:
            return OPS[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in OPS:
            return OPS[type(node.op)](ev(node.operand))
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("不支持的表达式")
    return f"{expression} = {ev(ast.parse(expression, mode='eval'))}"


def web_search(query: str) -> str:
    kb = {"react": "ReAct：Thought->Action->Observation 循环的 Agent 设计模式（2022 论文）。"}
    for key, text in kb.items():
        if key in query.lower():
            return f"[搜索:{query}] {text}"
    return f"[搜索:{query}] 无直接结果。"


TOOL_FUNCS = {"calculate": calculate, "web_search": web_search}
TOOLS = [
    {"type": "function", "function": {
        "name": "web_search", "description": "搜索互联网信息。",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "calculate", "description": "精确计算数学表达式，禁止心算。",
        "parameters": {"type": "object", "properties": {
            "expression": {"type": "string"}}, "required": ["expression"]}}},
]
SYSTEM = "你是会使用工具的助手：事实与计算必须调用工具，禁止编造。"


# ==================== State：框架替你管理的"messages 列表" ====================
def append_messages(existing: list, new: list) -> list:
    """reducer：新消息 append 而不是覆盖 —— 对应手写版的 messages.append。
    注意这里故意不用框架自带的 add_messages：它会把手写 dict 转成
    LangChain 的消息对象，而本项目直接用 OpenAI SDK 调用，必须保持
    纯 dict（这是混用裸 SDK 与框架时最常踩的坑，见课末要点）。"""
    return existing + (new if isinstance(new, list) else [new])


class State(TypedDict):
    messages: Annotated[list, append_messages]


# ==================== 节点 = 手写版循环体里的两段 ====================
def agent_node(state: State):
    """问模型（对应 while 循环的 'Thought' 段）"""
    r = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": SYSTEM}] + state["messages"],
        tools=TOOLS,
    )
    m = r.choices[0].message
    return {"messages": [{"role": "assistant", "content": m.content, "tool_calls": [
        {"id": tc.id, "type": "function",
         "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
        for tc in (m.tool_calls or [])]}]}


def tools_node(state: State):
    """执行所有调用并回传（对应 'Action + Observation' 段）"""
    last = state["messages"][-1]
    outs = []
    for tc in last["tool_calls"]:
        try:
            fn = TOOL_FUNCS[tc["function"]["name"]]
            result = str(fn(**json.loads(tc["function"]["arguments"] or "{}")))
        except Exception as e:
            result = f"ERROR: {e}"
        print(f"  [tools] {tc['function']['name']}({tc['function']['arguments']}) -> {result[:70]}")
        outs.append({"role": "tool", "tool_call_id": tc["id"], "content": result})
    return {"messages": outs}


def route(state: State):
    """条件边：还要工具 -> tools 节点；不要了 -> END（手写版的出口 if）"""
    last = state["messages"][-1]
    return "tools" if last.get("tool_calls") else END


# ==================== 组图 = 把 while 循环画成图 ====================
graph = StateGraph(State)
graph.add_node("agent", agent_node)
graph.add_node("tools", tools_node)
graph.add_edge(START, "agent")                # 入口：先问模型
graph.add_conditional_edges("agent", route)   # 模型说了算：继续 or 结束
graph.add_edge("tools", "agent")              # 工具结果送回模型 —— 循环的"边"
app = graph.compile()

if __name__ == "__main__":
    TASK = ("先搜索什么是 ReAct，再精确计算 (3567*89+1234)/7，"
            "最后整合成一段话。")
    print("任务:", TASK, "\n" + "=" * 60)
    # recursion_limit 对应手写版的 max_turns 兜底
    result = app.invoke(
        {"messages": [{"role": "user", "content": TASK}]},
        config={"recursion_limit": 30},
    )
    print("=" * 60)
    print("最终回答:", result["messages"][-1]["content"])
    print("""
要点回顾：
1. LangGraph 没有消灭循环，只是把 while 画成了图：条件边=出口判断，
   tools->agent 边=循环体，State+reducer=你的 messages 列表
2. 框架的真正增值：checkpoint 持久化、human-in-the-loop 中断、
   并行分支、可观测性 —— 生产需要、玩具不需要
3. 第 3 课先手写循环的意义：现在你能看穿任何 Agent 框架的源码结构
""")
