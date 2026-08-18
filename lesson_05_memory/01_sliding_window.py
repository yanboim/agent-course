"""
第 5 课 · 示例 1：滑动窗口裁剪 —— 最粗暴也最常用的记忆管理
=============================================================
运行：python 01_sliding_window.py

问题回顾：Agent 每轮全量重发历史（token 贪食蛇）。两个代价：
  钱：prompt token 线性增长；窗口上限：超了直接报错。

最简单的对策：只保留最近 K 条消息（滑动窗口）。
本脚本用同一套 6 轮对话跑两遍做对照：
  A 组：完整历史（记得住，但 token 暴涨）
  B 组：只留最近 K=4 条（省钱，但第 1 轮说的信息被裁掉 —— 当场翻车）
"""
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

SYSTEM = "你是一个简洁的中文购物助手。"
K = 4     # B 组窗口大小：system 之外最多保留 4 条


def ask(messages):
    r = client.chat.completions.create(model="deepseek-v4-flash", messages=messages)
    return (r.choices[0].message.content, r.usage.prompt_tokens)


def run_dialog(label: str, window: int | None):
    """window=None 完整历史；window=K 滑动窗口"""
    messages = [{"role": "system", "content": SYSTEM}]
    total = 0
    print(f"\n{'='*58}\n{label}\n{'='*58}")
    for user_text in SCRIPT:
        messages.append({"role": "user", "content": user_text})
        # ---- 裁剪：保留 system + 最近 window 条 ----
        if window:
            messages = [messages[0]] + messages[-(window + 1):]
        reply, ptok = ask(messages)
        messages.append({"role": "assistant", "content": reply})
        total += ptok
        print(f"[用户] {user_text[:28]}")
        print(f"[助手·prompt {ptok:3d} tok] {reply.strip()[:60]}")
    print(f">>> {label} 累计输入 token: {total}")
    return total


# 剧本：第 1 轮埋下关键信息，最后一轮考记忆
SCRIPT = [
    "我叫小明，订单号是 A-1024，我希望用顺丰到付。",
    "你们平台卖蓝牙耳机吗？",
    "预算 300 以内有什么推荐？",
    "能开发票吗？",
    "发货地是哪里？",
    "好了。现在告诉我：我的订单号是多少？快递有什么要求？",   # 考第 1 轮的记忆
]

if __name__ == "__main__":
    t_full = run_dialog(f"A 组：完整历史（不裁剪）", None)
    t_win = run_dialog(f"B 组：滑动窗口 K={K}（只留最近 {K} 条）", K)
    print(f"""
{'='*58}
对照结论：
  A 组累计输入 token: {t_full}   —— 记得住订单号，但历史越长越贵
  B 组累计输入 token: {t_win}    —— 省钱，但第 1 轮的信息被裁掉，
                                    最后一问翻车（订单号答不出/瞎编）
滑动窗口的问题不是"变笨"，是"失忆"：裁掉的不是垃圾，是记忆。
下一例（02）用"摘要压缩"折中：老对话压成一段摘要再丢弃原文。
""")
