# 第 2 课：Function Calling —— Agent 的心脏

## 知识点清单

1. **"函数调用"是个误称**：模型从不执行任何函数！它只输出一段结构化 JSON：
   "我想调用 `get_weather`，参数 `{"city": "北京"}`"。真正执行的是**你的代码**。
   模型是大脑，你是手。
2. **三段式协议**（背下来，第 3 课的 Agent 就是把它包进 while 循环）：
   - ① 请求带 `tools`：用 JSON Schema 写的"函数说明书"
   - ② 模型回 `message.tool_calls` + `finish_reason="tool_calls"`
   - ③ 你执行函数，结果以 `role="tool"` + `tool_call_id` 回传，模型生成最终回答
3. **tool 结果也只是上下文**：和第 1 课"誊写历史"完全同构——所谓工具调用
   循环，就是不断把新的文本（调用意图、执行结果）拼进 messages 再发一次
4. **并行调用**：模型一轮可能返回多个 tool_calls（列表），必须逐个回应
5. **错误也要回传**：工具报错时把 ERROR 文本作为 tool 消息发回去，
   模型会据此调整策略——self-correction（自我纠正）由此而来
6. **每个 tool_call 必须有对应 tool 消息**，缺了 API 直接 400

## 运行

```bash
cd lesson_02_tool_calling
python 01_first_tool_call.py   # 三段式协议全程解剖（最重要）
python 02_multi_tools.py       # 多工具选择 + 并行调用 + 通用循环雏形
python 03_error_feedback.py    # 错误回传与自我纠正 + 缺 tool 消息的 400
```

## 练习（做完才算过关）

1. 给 `01_first_tool_call.py` 加一个新工具 `get_population(city)`，观察模型
   如何在"天气"和"人口"两个工具之间做选择（靠 description）。
2. 故意把某个工具的 description 写得含糊，观察模型选错工具——体会
   description 就是模型的"工具目录"。
3. 问一个工具覆盖不了的问题（如"推荐一部电影"），观察模型是直接回答
   还是硬调工具。
4. 思考：第 3 课的 Agent 循环 = 本课协议 + while。提前想：循环的
   退出条件是什么？（提示：finish_reason）
