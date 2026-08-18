"""
第 6 课 · 示例 2：迷你 RAG —— 检索增强生成的完整闭环
=======================================================
运行：python 02_mini_rag.py

RAG 回答问题的流程（生产系统也就是这几步）：
  知识库 -> 切块(chunk) -> embed 建索引
  提问 -> embed 问题 -> 余弦检索 top-k -> （可选）重排
  -> 把命中块塞进 prompt（"参考资料"）-> LLM 依据资料作答

本质还是第 1 课那句话：模型只知道你放进上下文的东西。
RAG = 先查资料，再把资料誊写进上下文。对照实验会现场证明。

（embed/cosine 与 01_vector_search.py 相同；因数字开头文件无法被 import，
  这里直接内联，保证每个示例可独立运行）
"""
import math
import os
from collections import Counter
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

DIM = 512


def embed(text: str) -> list[float]:
    """字符 bigram 哈希嵌入（真实 embedding 模型的教学替身）"""
    vec = [0.0] * DIM
    for g, cnt in Counter(text[i:i + 2] for i in range(len(text) - 1)).items():
        vec[hash(g) % DIM] += cnt
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


# ==================== 1. 知识库（模型训练时从没见过的私有事实） ====================
DOCS = [
    "第 1 课 Hello LLM：messages 结构、流式输出、结构化输出、模型无状态。",
    "第 2 课 Tool Calling：函数调用协议是 Agent 的心脏。",
    "第 3 课 Agent Loop：约 100 行手写 ReAct Agent，while 循环加工具分发。",
    "第 4 课 Real Tools：文件读写、执行命令、HTTP 请求、路径安全与错误处理。",
    "第 5 课 Memory：滑动窗口裁剪、摘要压缩、长期记忆。",
    "第 6 课 RAG：手写 embedding、向量检索、重排。",
    "第 7 课 Multi-Agent：planner、executor、reviewer 三角色协作。",
    "第 8 课 LangGraph：用框架重写第 3 课的 Agent，理解框架解决了什么。",
    "课程原则：先用裸 API 手写，最后才碰框架。框架只是循环的封装。",
    "课程环境：Ubuntu 服务器、uv 虚拟环境、DeepSeek OpenAI 兼容接口。",
]

# ==================== 2. 建索引（生产 = 向量数据库，如 FAISS/Milvus） ====================
INDEX = [embed(d) for d in DOCS]


def retrieve(query: str, top_k: int = 3):
    """向量检索 + 简易重排：余弦找"像"的，字面重合度奖励"对"的"""
    q = embed(query)
    q_chars = set(query)
    scored = []
    for vec, doc in zip(INDEX, DOCS):
        sim = cosine(q, vec)
        overlap = len(q_chars & set(doc)) / max(len(q_chars), 1)   # 字面重合率
        scored.append((sim + 0.3 * overlap, sim, doc))             # 重排分
    scored.sort(reverse=True)
    return scored[:top_k]


# ==================== 3. RAG 问答 ====================
def answer_with_rag(question: str) -> str:
    hits = retrieve(question)
    print("  检索命中：")
    for rank, (rr, sim, doc) in enumerate(hits, 1):
        print(f"   [{rank}] 重排分{rr:.3f}/相似度{sim:.3f}  {doc[:38]}")
    context = "\n".join(f"[{i}] {doc}" for i, (_, _, doc) in enumerate(hits, 1))
    r = client.chat.completions.create(
        model="deepseek-v4-flash",
        temperature=0,
        messages=[
            {"role": "system",
             "content": "仅依据下面的参考资料回答；引用资料编号如[1]；"
                        "资料里没有就回答'资料里没有'，禁止编造。"},
            {"role": "user", "content": f"参考资料：\n{context}\n\n问题：{question}"},
        ],
    )
    return r.choices[0].message.content


def answer_without_rag(question: str) -> str:
    """对照组：不给资料直接问 —— 模型只能瞎猜（这些是私有事实）"""
    r = client.chat.completions.create(
        model="deepseek-v4-flash", temperature=0,
        messages=[{"role": "user", "content": question}],
    )
    return r.choices[0].message.content


if __name__ == "__main__":
    for q in ["这门课第 8 课学什么？", "课程的原则是什么？"]:
        print("=" * 60)
        print("问题:", q)
        print("-" * 60, "\n【RAG 模式】")
        print("  回答:", answer_with_rag(q))
        print("-" * 60, "\n【无 RAG 对照】")
        print("  回答:", answer_without_rag(q), "\n")

    print("""
要点回顾：
1. RAG = 检索增强生成：先查资料，再把资料誊写进上下文 —— 仍是第 1 课的真理
2. 私有/新知识不用重训模型：加文档、重建索引即可（这是 RAG 最大的价值）
3. 重排(rerank)：向量找"像"，重排找"对"；生产用 cross-encoder 模型重排
4. 防幻觉三件套：仅限资料 + 要求引用编号 + 明说"没有就说没有"
5. 局限：检索错了后面全错（garbage in, garbage out）—— 分块与检索质量是命门
""")
