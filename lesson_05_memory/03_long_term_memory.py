"""
第 5 课 · 练习 3（核心）：迷你长期记忆 —— 关键事实外置 + 每轮注入
=====================================================================
运行：python 03_long_term_memory.py

三层记忆架构的"长期层"落地：
  短期：messages 最近 K 轮原文 —— 本脚本故意配滑动窗口 K=4
        （01 例里正是这个配置让订单号失忆翻车）
  长期：memory.json —— 每轮结束后让模型抽取关键事实（结构化输出），
        合并写盘；下一轮请求前读出、拼进 system

预期：窗口会把第 1 轮的订单号裁掉，但事实每轮都从外部文件重新注入
system —— 最后一问照样答对。第二场"全新会话"再证明跨会话持久。

代价：每轮多一次抽取调用（结构化输出很小，token 不多但非零）。
"""
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
MODEL = "deepseek-v4-flash"

MEMORY_FILE = Path(__file__).parent / "memory.json"
SYSTEM = "你是一个简洁的中文购物助手。"
K = 4          # 与 01 例相同的窗口大小（那一场它失忆翻车）

SCRIPT = [
    "我叫小明，订单号是 A-1024，我希望用顺丰到付。",
    "你们平台卖蓝牙耳机吗？",
    "预算 300 以内有什么推荐？",
    "能开发票吗？",
    "发货地是哪里？",
    "好了。现在告诉我：我的订单号是多少？快递有什么要求？",   # 考第 1 轮的记忆
]


# ============ 长期记忆的三个原语：读 / 写 / 注入 ============
def load_memory() -> dict:
    if MEMORY_FILE.exists():
        return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    return {}


def save_memory(mem: dict) -> None:
    MEMORY_FILE.write_text(json.dumps(mem, ensure_ascii=False, indent=2),
                           encoding="utf-8")


def build_system(mem: dict) -> str:
    """每轮请求前：把记忆拼进 system（这就是'注入'）"""
    if not mem:
        return SYSTEM
    facts = "；".join(f"{k}={v}" for k, v in mem.items() if v)
    return SYSTEM + f"\n【长期记忆（此前会话积累的事实）】{facts}"


# ============ 抽取：让模型从最新一轮对话里挖事实 ============
def extract_facts(user_text: str, assistant_text: str, mem: dict) -> dict:
    r = client.chat.completions.create(
        model=MODEL, temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content":
                   "从下面这轮对话中抽取关键事实，输出 JSON（没提到的字段填 null）：\n"
                   '{"姓名": null, "订单号": null, "偏好": null}\n'
                   f"用户：{user_text}\n助手：{assistant_text}"}],
    )
    try:
        new = json.loads(r.choices[0].message.content)
    except json.JSONDecodeError:
        return mem                       # 抽取失败就跳过，不能让记忆层炸主流程
    for k, v in new.items():             # 只覆盖非空值（新事实覆盖旧事实）
        if v and str(v).strip().lower() not in ("null", "none", ""):
            mem[k] = v
    return mem


def ask(system: str, history: list) -> tuple[str, int]:
    r = client.chat.completions.create(
        model=MODEL, messages=[{"role": "system", "content": system}] + history)
    return r.choices[0].message.content, r.usage.prompt_tokens


if __name__ == "__main__":
    MEMORY_FILE.unlink(missing_ok=True)          # 实验从零开始
    mem, history, total, extra_calls = {}, [], 0, 0

    print("=" * 60)
    print(f"第一场：滑动窗口 K={K} + 长期记忆注入（01 例仅窗口时翻车）")
    print("=" * 60)
    for i, user_text in enumerate(SCRIPT, 1):
        history.append({"role": "user", "content": user_text})
        history = history[-K:]                   # 滑动窗口：只留最近 K 条
        reply, ptok = ask(build_system(mem), history)
        history.append({"role": "assistant", "content": reply})
        total += ptok
        mem = extract_facts(user_text, reply, mem)   # 每轮结束：抽取+写盘
        save_memory(mem)
        extra_calls += 1
        print(f"[第{i}轮·prompt {ptok:3d} tok] {reply.strip()[:52]}")
        print(f"        记忆更新: {json.dumps(mem, ensure_ascii=False)}")

    ok1 = ("1024" in history[-1]["content"]) and ("顺丰" in history[-1]["content"])
    print(f"\n>>> 第一场验证（窗口内已无第1轮原文）: {'PASS 答对了' if ok1 else 'FAIL'}")
    print(f">>> memory.json 内容: {MEMORY_FILE.read_text(encoding='utf-8').strip()}")

    # ============ 第二场：全新会话，只有 memory.json 活着 ============
    print("\n" + "=" * 60)
    print("第二场：全新会话（history 清空，唯一的记忆载体是 memory.json）")
    print("=" * 60)
    mem2 = load_memory()                          # 从盘上读 —— 跨会话就在这一步
    reply, ptok = ask(build_system(mem2),
                      [{"role": "user", "content": "我的订单号是多少？快递有什么要求？"}])
    print(f"[新会话·prompt {ptok} tok] {reply.strip()[:80]}")
    ok2 = ("1024" in reply) and ("顺丰" in reply)
    print(f"\n>>> 第二场验证（跨会话持久）: {'PASS 答对了' if ok2 else 'FAIL'}")
    print(f">>> 成本：本轮对话共 {extra_calls} 次额外抽取调用，累计 prompt {total} tok")

    print(f"""
要点回顾：
1. 长期记忆 = 外置存储（memory.json）+ 每轮注入 system + 每轮抽取合并
2. 它治好了滑动窗口的失忆：窗口裁掉原文没关系，事实在 system 里永生
3. 跨会话持久：新会话读盘即恢复记忆 —— 这才是"长期"的真正含义
4. 代价：每轮一次抽取调用；抽取失败要静默跳过（记忆层不能炸主流程）
5. 这就是 RAG 思想在记忆上的应用：需要时检索（读盘）注入上下文，
   而不是把一切都塞进对话历史（第 6 课正式展开）
""")
