"""
第 5 课 · 示例 2：摘要压缩记忆 —— 在省钱和失忆之间折中
=========================================================
运行：python 02_summary_compress.py

思路：老消息不直接扔，先让模型把"已超出窗口的旧对话"压缩成一段摘要，
用一条消息顶替它们。关键事实（名字/订单号/偏好）被要求保留在摘要里。

代价与风险：
1. 摘要本身是一次额外的 LLM 调用（花钱）
2. 摘要有损：细节措辞、语气、次要信息可能被丢
3. 生产系统的"长期记忆"往往再加一层：把关键事实抽成键值对存外部
   数据库（第 5 课 README 练习 3 会让你实现迷你版）
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
THRESHOLD = 6        # 历史条数（含 system）超过它就触发压缩
KEEP_RECENT = 2      # 压缩时保留最近 2 条不动

SUMMARY_PROMPT = """把下面的对话历史压缩成一段摘要，供后续对话使用。
必须原样保留：用户姓名、订单号、快递偏好、预算等关键事实。
用条目式中文输出，不要寒暄。对话历史：
"""


def compress(old_messages):
    """把将被丢弃的旧消息压成一条摘要"""
    text = "\n".join(f"{m['role']}: {m['content']}" for m in old_messages)
    r = client.chat.completions.create(
        model="deepseek-v4-flash",
        messages=[{"role": "user", "content": SUMMARY_PROMPT + text}],
        temperature=0,
    )
    return r.choices[0].message.content


def run_dialog():
    messages = [{"role": "system", "content": SYSTEM}]
    total_prompt, compressed = 0, False
    for user_text in SCRIPT:
        messages.append({"role": "user", "content": user_text})
        # ---- 压缩时机：条数超阈值且还没压过（简化演示：只压一轮） ----
        if len(messages) > THRESHOLD and not compressed:
            old, recent = messages[1:-KEEP_RECENT], messages[-KEEP_RECENT:]
            summary = compress(old)               # 额外的一次 LLM 调用
            print("\n[压缩] 旧对话 -> 摘要：")
            print("      " + summary.replace("\n", "\n      ")[:220])
            messages = ([{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": f"（此前对话摘要）\n{summary}"},
                         {"role": "assistant", "content": "好的，我记住了。"}] + recent)
            compressed = True
        r = client.chat.completions.create(model="deepseek-v4-flash", messages=messages)
        reply = r.choices[0].message.content
        messages.append({"role": "assistant", "content": reply})
        total_prompt += r.usage.prompt_tokens
        print(f"[用户] {user_text[:30]}")
        print(f"[助手·prompt {r.usage.prompt_tokens:3d} tok] {reply.strip()[:60]}")
    print(f">>> 累计输入 token: {total_prompt}（对比 01 的 A 组：更少且不失忆）")


SCRIPT = [
    "我叫小明，订单号是 A-1024，我希望用顺丰到付。",
    "你们平台卖蓝牙耳机吗？",
    "预算 300 以内有什么推荐？",
    "能开发票吗？",
    "发货地是哪里？",
    "好了。我的订单号是多少？快递有什么要求？",   # 再考第 1 轮的记忆
]

if __name__ == "__main__":
    run_dialog()
    print("""
要点回顾：
1. 摘要压缩 = 有损压缩的记忆：省钱且保住关键事实，但措辞细节会丢
2. 压缩本身是一次 LLM 调用 —— 也有成本，别每轮都压（设阈值/定时）
3. 摘要以 user/assistant 对的形式放回历史开头（不能放 system，服务端
   才是 system 的作者；这是工程惯例）
4. 更完整的记忆架构：短期（最近几轮原文）+ 中期（滚动摘要）+
   长期（关键事实抽成键值对，存文件/数据库，检索后注入）
""")
