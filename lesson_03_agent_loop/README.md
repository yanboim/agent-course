# 第 3 课：手写 ReAct Agent —— 约 100 行的主循环

## 知识点清单

1. **Agent = 第 2 课协议 + while 循环**。没有魔法：
   ```text
   while True:
       回答 = 问模型(全部历史 + 工具说明书)      # Thought
       if 回答不带 tool_calls: 返回回答          # 出口
       for 每个调用:
           历史.append(执行结果)                 # Action + Observation
   ```
2. **ReAct = Reason + Act**：每轮 Thought → Action → Observation，
   循环往复直到模型认为能作答
3. **出口条件**：`tool_calls` 为空（等价 `finish_reason != "tool_calls"`）
4. **max_turns 兜底**：模型可能死循环（反复调同一个工具），必须设上限
5. **安全计算器**：`ast` 白名单求值，绝不把模型输出直接喂给 `eval`
6. **token 贪食蛇**：每轮全量重发历史，prompt token 逐轮暴涨（第 5 课解决）

## 运行

```bash
cd lesson_03_agent_loop
python agent.py        # 观察逐轮打印：思考/动作/观察/最终回答/token统计
```

## 代码地图（agent.py）

| 区块 | 内容 |
|------|------|
| 一、工具函数 | calculate（安全求值）/ web_search（假搜索）/ get_current_time |
| 二、TOOLS 说明书 | JSON Schema；description 决定模型何时想起该工具 |
| 三、run_agent() | **主角**。逐行读，尤其看出口条件和错误兜底 |

## 练习（做完才算过关）

1. 改 TASK 为一个需要 3 次以上工具调用的任务（如"搜两个概念并对比，
   再算一个数"），观察轮数和 token 增长。
2. 新增一个工具 `read_file(path)`（只允许读本目录），让 Agent 自己找到
   并读取 `secret.txt`（自己创建一个）。
   —— 参考实现已并入 `agent.py`（含 `/etc/passwd` 越界测试），
      建议先自己写，再对照。
3. 把 `max_turns` 改成 2 跑同一个任务，观察兜底消息 —— 体会上限的必要性。
4. 思考：如果模型每轮都重复调用同一个工具，除了 max_turns 还能怎么治？
   （提示：把"你已调用过 X，结果为 Y"写进 system；或对重复调用直接拒绝）
