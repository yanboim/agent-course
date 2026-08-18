# 第 8 课：LangGraph —— 用框架重写第 3 课的 Agent

## 知识点清单

1. **手写 ↔ 框架对照表**（本课核心，逐行对照 `01_langgraph_agent.py`）：

   | 第 3 课手写版 | LangGraph 版 |
   |---|---|
   | `messages` 列表 | `State` + `add_messages` reducer |
   | `while True` | 边与条件边构成的环 |
   | `if not m.tool_calls: return` | 条件边 `route` 指向 `END` |
   | `for tc: 执行+回传` | `tools` 节点 |
   | `max_turns` 兜底 | `recursion_limit` |

2. **框架的真正增值**（手写循环没有、生产需要的）：
   - checkpoint 持久化：中断恢复、时间旅行调试
   - human-in-the-loop：在指定节点暂停等人审批再继续
   - 并行分支 / 子图：多 Agent 编排的图原生表达
   - 可观测性：每步状态流转可追踪
3. **框架没有消灭循环**：`tools -> agent` 的边就是你的 `while`。
   看穿这一点，任何 Agent 框架的源码你都能对号入座
4. 课程原则闭环：先用裸 API 手写（第 3 课），最后才碰框架（本课）——
   框架只是循环的封装，先见循环，再见封装

## 安装与运行

```bash
# 依赖已包含在仓库根目录 requirements.txt（langgraph）
cd lesson_08_langgraph
python 01_langgraph_agent.py
```

> 若离线装不上：代码仍值得通读，图结构与第 3 课逐行同构；联网后装上再跑。

## 练习（做完才算过关）

1. 给图加一个 `reviewer` 节点：agent 回答后先过审，REVISE 则打回
   （把第 7 课的审稿逻辑搬进图）—— 体会"多 Agent = 多节点"。
2. 加 `checkpointer=MemorySaver`，用 `thread_id` 跑两次同一任务，
   第二次观察状态复用（中断恢复的最小演示）。
3. 思考：同样这个 Agent，用第 3 课手写版实现 reviewer 打回要改几行？
   用 LangGraph 要改几行？—— 体会图结构在流程变复杂时的优势。
4. （结课）把 8 课的积木拼起来：给第 3 课的 Agent 换上第 4 课的真实
   工具 + 第 5 课的记忆管理 + 第 6 课的 RAG 检索工具 —— 这就是一个
   完整的生产级 Agent 雏形。
