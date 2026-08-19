"""
第 3 课 · 思考题演示：模型重复调用同一工具，除了 max_turns 怎么治？
=====================================================================
运行：python 02_repeat_guard.py

病根（为什么看得见历史还会重复）：
1. 观察不满足预期：工具一直报错，模型"再试一次"
2. 上下文自我强化：历史里已有 N 次相同调用，自回归模型会把第 N+1 次
   相同调用当作"剧情合理延续"——重复滋生重复（正反馈泥潭）
3. 任务超出工具能力：模型无路可走，原地打转

药方（本文件演示 A/B/C 三层）：
A. 代码层硬拦截：(工具名, 参数JSON) 做键建缓存；重复调用不执行，
   直接返回【缓存结果 + 警告文本】——省工具开销，且把"你在重复"
   这个事实写进 Observation，模型必然读到
B. 上下文层软提醒：警告措辞本身就是提醒（"你已调用过X结果是Y，
   请换参数/换工具/直接作答"）——打破自我强化的标注
C. 请求层没收工具：同一调用被拦截满 2 次后，后续请求不再传 tools，
   模型物理上只能作答（最狠也最有效）

对照组：guard=False 时只有 max_turns 兜底，观察模型能烧多少轮。
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
MODEL = "deepseek-v4-flash"


# ============ 一个"永远失败"的工具：模拟数据源故障，诱导模型重试 ============
def check_flight(flight_no: str) -> str:
    # 注意错误措辞：明确怂恿"立即重试"——最坏情况的放大器。
    # 真实系统里这类"看起来马上会好"的错误最容易把模型拖进重试泥潭
    return f"ERROR: 数据源临时繁忙（FLIGHT-{flight_no}），本次查询未计入配额，请立即重试"


TOOL_FUNCS = {"check_flight": check_flight}
TOOLS = [{"type": "function", "function": {
    "name": "check_flight", "description": "查询航班实时状态。",
    "parameters": {"type": "object", "properties": {
        "flight_no": {"type": "string"}}, "required": ["flight_no"]}}}]


def run_agent(task: str, guard: bool = True, max_turns: int = 8) -> None:
    messages = [
        {"role": "system", "content": "你是航班查询助手，必须用工具查数据后才能回答。"},
        {"role": "user", "content": task},
    ]
    cache: dict[tuple, tuple] = {}   # (name, args_json) -> (result, 首次轮次)
    dup_hits = 0                     # 被拦截的次数
    confiscated = False              # 是否已没收工具

    for turn in range(1, max_turns + 1):
        r = client.chat.completions.create(
            model=MODEL, messages=messages,
            tools=None if confiscated else TOOLS,   # C：没收工具
        )
        m = r.choices[0].message
        messages.append({"role": "assistant", "content": m.content, "tool_calls": [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in (m.tool_calls or [])]})

        if not m.tool_calls:
            tag = "guard" if guard else "无防护"
            print(f"[{tag}·第{turn}轮·最终回答] {m.content.strip()[:110]}")
            return

        for tc in m.tool_calls:
            name, raw = tc.function.name, (tc.function.arguments or "{}")
            key = (name, raw)
            if guard and key in cache:
                # ==== A + B：硬拦截 + 软提醒（写进 Observation，模型必然读到） ====
                old, first_turn = cache[key]
                dup_hits += 1
                result = (f"【重复调用拦截】你刚才第{first_turn}轮已用完全相同的参数调用过"
                          f"{name}，结果是：{old}。请不要再用相同参数重试这个工具；"
                          "请换参数、换工具，或直接基于已有信息向用户说明情况并作答。")
            else:
                result = str(TOOL_FUNCS[name](**json.loads(raw)))
                cache[key] = (result, turn)
            print(f"[第{turn}轮] {name}({raw}) -> {result[:88]}")
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

        # ==== C：拦截满 2 次 → 没收工具，下轮起模型只能作答 ====
        if guard and not confiscated and dup_hits >= 2:
            confiscated = True
            print(f"[第{turn}轮·熔断] 同一调用已重复 {dup_hits} 次，下一轮起不再提供工具")
    else:
        print(f"[{'guard' if guard else '无防护'}] 烧满 max_turns={max_turns} 轮，强制停止")


if __name__ == "__main__":
    TASK = "帮我查一下 CA1234 航班现在准点吗？"

    print("=" * 62)
    print(f"对照组（guard=False，只有 max_turns 兜底）\n任务: {TASK}")
    print("=" * 62)
    run_agent(TASK, guard=False)

    print("\n" + "=" * 62)
    print(f"实验组（guard=True：A拦截 + B提醒 + C没收）\n任务: {TASK}")
    print("=" * 62)
    run_agent(TASK, guard=True)

    print("""
要点回顾：
1. 模型看得见历史仍会重复：观察不满足预期 + 上下文自我强化 + 无路可走
2. max_turns 只是止损，不治病；治病要让"重复"对模型可读（A/B）
   或让重复物理上不可能（C 没收工具）
3. 提醒要写进 tool 消息 content —— tool 消息必须紧跟 tool_calls，
   往中间插 user 消息可能违反协议
4. 参数层 temperature=0 可预防抽样式抽风；历史层手术（压缩重复调用对）
   是第 5 课记忆管理的思想
""")
