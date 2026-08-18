# 第 7 课：Multi-Agent —— planner / executor / reviewer 协作

## 知识点清单

1. **多 Agent 的真相**：每个 Agent = 一个独立的 LLM 调用（自己的 system
   prompt + 自己的消息历史）。"协作" = 你的代码在角色之间搬运文本。
   没有神秘的 Agent 间通信协议
2. **三角色流水线**：
   - planner：拆解任务 → 步骤清单（结构化 JSON）
   - executor：逐步执行（内部就是第 3 课的 Agent 循环）
   - reviewer：对照任务审查 → APPROVE / REVISE（打回重做）
3. **角色间接口 = 结构化输出**：第 1 课 JSON 三件套（schema+temperature=0+
   json_object）直接复用
4. **审稿循环**：reviewer 打回 = 外层又套了一个循环（团队版自我纠错）
5. **成本意识**：3 角色 ≈ 3 倍以上 token。多 Agent 不是默认选项，
   先问"单个 Agent + 好工具真的不够吗"

## 运行

```bash
cd lesson_07_multi_agent
python 01_pipeline.py    # 观察三角色接力 + 审稿/打回
```

## 练习（做完才算过关）

1. 把任务改成一个需要真实搜索的任务，给 executor 加上第 6 课的
   `retrieve` 作为工具 —— 你就得到了"会查私有知识的执行者"。
2. 增加第四个角色 writer（把 executor 的结果改写成正式报告），
   体会"角色 = 职责单一化"的收益与 token 代价。
3. 故意给 reviewer 一个错误任务（如"验证 (128*64)/16 是否等于 999"），
   观察 REVISE 循环 —— 思考：审稿者自己会犯错怎么办？（无标准答案，
   这是多 Agent 研究的开放问题：交叉审稿/多数投票）
4. 思考：planner 输出的步骤如果之间有依赖（步骤 2 要用步骤 1 的结果），
   现在的代码有什么缺陷？（提示：每个 execute 调用的历史是独立的）
