# 第 1 课：Hello, LLM —— API 基础与"无状态"真相

## 知识点清单

1. **调用模型 = 发送 messages 列表**
   - 三种角色：`system`（岗位说明书）/ `user`（用户）/ `assistant`（模型历史回复，需自己拼）
2. **response 三大看点**
   - `choices[0].message.content`：正文
   - `choices[0].finish_reason`：`stop` 正常 / `length` 被截断
   - `usage`：token 计费依据，Agent 是"token 貪食蛇"
3. **模型无状态**：`f(messages) -> 新消息`，纯函数。"记忆"是网站后端反复重发历史实现的
4. **流式输出**：chunk + delta 增量；关注首 token 耗时（用户体验核心指标）
5. **结构化输出**：明确 schema + `temperature=0` + `response_format={"type":"json_object"}`；
   `json.loads` 必须有异常防御

## 运行

```bash
cd lesson_01_hello_llm
python 01_first_call.py   # 基础调用 + 无记忆实验
python 02_streaming.py    # 流式 vs 非流式
python 03_structured.py   # JSON 结构化抽取
```

## 练习（做完才算过关）

1. **观察**：把 `01_first_call.py` 里 temperature 改成 `0` 和 `1.5`，各跑 3 次，
   对比同一问题的输出稳定性差异。
2. **动手（本课核心练习）**：新建 `my_chat.py`，写一个命令行多轮聊天程序：
   - `while True` 循环里 `input()` 读用户输入
   - 维护一个不断增长的 `messages` 列表（每轮把 assistant 的回复 append 回去）
   - 用流式输出打印
   - 输入 `exit` 退出
   → 写完它你就亲手实现了"对话记忆"。第 3 课的 Agent 主循环骨架就是这个程序。
3. **思考**：聊天轮数多了以后，这个 `messages` 列表会发生什么问题？（两个角度：
   钱、上下文窗口上限）第 5 课会正面解决。
