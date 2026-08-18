"""
第 1 课 · 示例 2：流式输出（streaming）
=========================================
运行：python 02_streaming.py

为什么 Agent 应用几乎都用流式？
1. 用户体验：首 token 800ms 就能看到字往外蹦，比干等 8 秒强得多
2. 可以提前展示"正在思考/正在调用工具"等中间状态
3. 边生成边处理（比如实时检测敏感词、提前中断）

原理：普通调用是一次性返回完整结果；流式则把生成中的文本
切成小块（chunk）持续推送，每个 chunk 里带一小段增量文本（delta）。
"""
import os
import time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

question = "用 200 字解释：为什么说 Agent 的本质是'LLM 驱动的循环'？"

# ---------- 先测非流式：记录总耗时 ----------
t0 = time.time()
r = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": question}],
)
full_text = r.choices[0].message.content
t_normal = time.time() - t0
print(f"[非流式] 总耗时 {t_normal:.1f}s，一次性拿到 {len(full_text)} 字")
print(full_text[:60], "...\n")

# ---------- 再测流式：记录"首字耗时"和总耗时 ----------
t0 = time.time()
stream = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": question}],
    stream=True,                       # 关键开关
)
first_token_at = None
pieces = []                            # 收集所有增量片段
print("[流式] 逐字输出：")
for chunk in stream:
    if not chunk.choices:              # 个别 chunk 可能没有 choices，跳过
        continue
    delta = chunk.choices[0].delta     # delta = 本次增量
    if delta.content:                  # 最后一个 chunk 的 delta.content 为 None
        if first_token_at is None:
            first_token_at = time.time() - t0
        pieces.append(delta.content)
        print(delta.content, end="", flush=True)   # flush 让字立刻上屏

t_stream = time.time() - t0
print(f"\n\n[流式] 首字耗时 {first_token_at:.1f}s，总耗时 {t_stream:.1f}s")
print(f"[流式] 拼接结果与非流式内容一致: {''.join(pieces) == full_text}")

# 注意一个工程细节：流式拿 finish_reason 的方式
# 循环里每个 chunk.choices[0].finish_reason 通常只有最后一个不为 None，
# 需要的话在循环里判断并记录 —— Agent 框架内部就是这么做的。
