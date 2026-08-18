"""
第 7 课 · 示例 1：多 Agent 协作 —— planner / executor / reviewer
=================================================================
运行：python 01_pipeline.py

多 Agent 的真相先说破：每个"Agent"就是一个独立的 LLM 调用（有自己的
system prompt 和自己的消息历史），协作 = 你的代码在它们之间搬运文本。
没有任何神秘的"Agent 间通信协议"。

三角色流水线：
  planner  （规划）：把总任务拆成步骤清单（结构化输出 JSON）
  executor （执行）：逐步执行，可用计算器工具（复用第 3 课的循环）
  reviewer （审稿）：对照总任务审查结果，不通过则打回重做（最多 1 轮）

角色间接口 = 结构化 JSON（第 1 课结构化输出的直接应用）。
代价直觉：3 个角色 ≈ 3 倍以上 token —— 多 Agent 不是免费的。
"""
import ast
import json
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
MODEL = "deepseek-v4-flash"


# ============ executor 用的计算器工具（同第 3 课） ============
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


OPS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
       ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b,
       ast.Mod: lambda a, b: a % b, ast.Pow: lambda a, b: a ** b,
       ast.USub: lambda a: -a}

TOOLS = [{"type": "function", "function": {
    "name": "calculate", "description": "精确计算数学表达式，禁止心算。",
    "parameters": {"type": "object", "properties": {
        "expression": {"type": "string"}}, "required": ["expression"]}}}]


# ============ 角色 1：planner（规划者） ============
def plan(task: str) -> list[str]:
    r = client.chat.completions.create(
        model=MODEL, temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content":
                "你是规划者。把任务拆成 2~4 个明确步骤，输出 JSON："
                '{"steps": ["步骤1", "步骤2", ...]}。只输出 JSON。'},
            {"role": "user", "content": task},
        ],
    )
    steps = json.loads(r.choices[0].message.content)["steps"]
    print("[planner] 拆解出步骤：")
    for i, s in enumerate(steps, 1):
        print(f"   {i}. {s}")
    return steps


# ============ 角色 2：executor（执行者，带工具的小 Agent） ============
def execute(step: str, feedback: str = "") -> str:
    messages = [
        {"role": "system", "content":
            "你是执行者。完成当前步骤：需要计算必须用 calculate 工具，"
            "完成后用一句话汇报结果。" + (f"（审稿意见：{feedback}）" if feedback else "")},
        {"role": "user", "content": step},
    ]
    for _ in range(4):                                   # 迷你 Agent 循环
        r = client.chat.completions.create(model=MODEL, messages=messages, tools=TOOLS)
        m = r.choices[0].message
        messages.append({"role": "assistant", "content": m.content, "tool_calls": [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in (m.tool_calls or [])]})
        if not m.tool_calls:
            print(f"[executor] {step[:22]}... -> {m.content.strip()[:60]}")
            return m.content
        for tc in m.tool_calls:
            # 工具永不抛异常：错误也是 Observation，让模型读到后自我纠正
            try:
                result = calculate(**json.loads(tc.function.arguments))
            except Exception as e:
                result = (f"ERROR: {type(e).__name__}: {e}（提示：expression"
                          " 必须是纯数学表达式，如 '(128*64)/16'，不能含中文）")
            print(f"[executor·工具] {result}")
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
    return "(执行超轮数)"


# ============ 角色 3：reviewer（审稿者） ============
def review(task: str, report: str) -> tuple[str, str]:
    """返回 (verdict, reason)：APPROVE 通过 / REVISE 打回"""
    r = client.chat.completions.create(
        model=MODEL, temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content":
                "你是严格的审稿者。对照原始任务检查报告是否完整正确。输出 JSON："
                '{"verdict": "APPROVE" 或 "REVISE", "reason": "理由"}'},
            {"role": "user", "content": f"原始任务：{task}\n\n执行报告：{report}"},
        ],
    )
    d = json.loads(r.choices[0].message.content)
    print(f"[reviewer] {d['verdict']} —— {d['reason'][:60]}")
    return d["verdict"], d["reason"]


# ============ 编排：你的代码把三个角色串起来 ============
if __name__ == "__main__":
    TASK = "计算 (128*64)/16 的值，验证它是否等于 512，最后给一句结论。"
    print("=" * 60)
    print("总任务:", TASK)
    print("=" * 60)

    steps = plan(TASK)
    for i, step in enumerate(steps, 1):
        print(f"\n--- 执行步骤 {i}/{len(steps)} ---")
        report = execute(step)

    print("\n--- 审稿 ---")
    verdict, reason = review(TASK, report)
    if verdict == "REVISE":                      # 打回重做（最多 1 轮）
        print("\n--- 打回重做 ---")
        report = execute("根据审稿意见完善最终报告", feedback=reason)
        verdict, _ = review(TASK, report)

    print("\n" + "=" * 60)
    print("最终报告:", report)
    print("""
要点回顾：
1. 多 Agent = 多个独立 LLM 调用 + 你写的编排代码（搬运文本而已）
2. 角色边界靠各自的 system prompt；角色接口靠结构化 JSON
3. executor 内部就是第 3 课的 Agent 循环 —— 没有新东西，只有组合
4. reviewer 打回机制 = 外层又一个循环（自我纠错的团队版）
5. 成本：角色越多调用越多；先问"单个 Agent 真的不够吗"
""")
