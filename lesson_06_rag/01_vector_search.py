"""
第 6 课 · 示例 1：手写 embedding + 向量检索 —— RAG 的地基
=============================================================
运行：python 01_vector_search.py

embedding（嵌入）：把一段文本映射成一个向量（一串数），语义越接近的
文本，向量方向越接近。于是"找相关内容"变成"向量夹角最小"（余弦相似度）。

本课用纯 Python 手写一个"字符二元组哈希向量"代替真 embedding 模型：
  文本 -> 所有相邻字符对 -> 哈希到 512 维 -> 计数 -> 归一化
它只懂"字面像"，不懂"语义像"（下面第 3 个查询会暴露差距），但检索的
【机制】与生产系统完全一致：embed -> 存向量 -> 算余弦 -> 排序取 top-k。
"""
import math
from collections import Counter

DIM = 512


def embed(text: str) -> list[float]:
    """字符 bigram 哈希嵌入：真实 embedding 模型的教学替身"""
    vec = [0.0] * DIM
    grams = [text[i:i + 2] for i in range(len(text) - 1)]   # 相邻字符对
    for g, cnt in Counter(grams).items():
        vec[hash(g) % DIM] += cnt                            # 哈希落到某一维
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0         # L2 归一化
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    """余弦相似度：两向量夹角。1=同向（最像），0=正交（无关）"""
    return sum(x * y for x, y in zip(a, b))


CORPUS = [
    "第 2 课学习函数调用：模型输出结构化的调用意图，代码负责执行并回传结果。",
    "第 3 课手写约 100 行的 ReAct Agent，核心是 while 循环加工具分发。",
    "第 5 课讲上下文管理：滑动窗口、摘要压缩、长期记忆。",
    "第 6 课手写迷你 RAG：embedding、向量检索、重排。",
    "课程原则：先用裸 API 手写，最后才碰框架。",
    "课程环境是 Ubuntu 服务器，API 使用 DeepSeek 的 OpenAI 兼容接口。",
    "模型没有记忆，多轮对话的真相是代码反复重发历史。",
    "temperature 控制采样随机性，越低越稳定。",
]

VECTORS = [embed(doc) for doc in CORPUS]


def search(query: str, top_k: int = 3):
    q = embed(query)
    scored = sorted(((cosine(q, v), doc) for v, doc in zip(VECTORS, CORPUS)),
                    reverse=True)
    return scored[:top_k]


if __name__ == "__main__":
    queries = [
        "agent 的循环怎么写",            # 字面命中 -> 检索正确
        "怎么管理对话历史和记忆",         # 字面部分命中 -> 大致正确
        "让 AI 帮我调用外部程序",          # 语义问法，字面几乎不重合 -> 检索较差
    ]
    for q in queries:
        print(f"\n查询: {q}")
        for score, doc in search(q):
            print(f"  {score:.3f}  {doc}")

    print("""
要点回顾：
1. embedding 的作用：文本 -> 向量，相似度变成可计算的数（余弦）
2. 检索 = 对库中所有向量算余弦、排序、取 top-k。就这么多
3. 手写 bigram 向量只懂"字面像"：第 3 个查询暴露了差距 ——
   真实 embedding 模型（BGE / text-embedding 系列）懂"语义像"，
   但机制完全同构：换掉 embed() 这一个函数即可升级
4. 下一例把这套检索接上 LLM，就是完整 RAG
""")
