# 第 8 课补充笔记：LangGraph 看不懂？先读这篇

> 困难 99% 来自**词汇陌生**，不是逻辑陌生。LangGraph 里的每个概念，
> 你都在第 3 课手写过。本文把它们一一翻译回去。

## 一句话祛魅

**LangGraph = 把第 3 课的 while 循环，画成一张流程图。**

它没有引入任何新的智能——模型还是那个模型，工具还是那些工具，循环
还是那个循环。变的只是**表达循环的语法**：

```text
第 3 课（手写）:  while + if + append     ← 你指挥每一步
第 8 课（图）:    节点 + 边 + 状态盒子    ← 你画好图，框架替你走
```

## 核心对照表（先背这张表再读代码）

| 你已掌握的（第 3 课 agent.py） | LangGraph 的新词 | 干的事 |
|---|---|---|
| `messages` 列表 | `State`（状态） | 装着 messages 的盒子，在节点间传递 |
| `messages.append(...)` | **reducer**（`append_messages`） | 节点只声明"增量"，框架负责合并 |
| 循环体前半段（问模型） | **节点** `agent_node` | 普通函数：吃 State，吐增量 |
| 循环体后半段（执行工具） | **节点** `tools_node` | 同上 |
| `if not m.tool_calls: return` | **条件边** `route` | 返回下一个节点的名字 |
| `while True` 本身 | **边** `tools → agent` | 这条边构成的环**就是**循环 |
| `max_turns=8` 兜底 | `recursion_limit=30` | 防死循环上限 |
| `run_agent(TASK)` 启动 | `app.invoke({...})` | 点火，跑到 END 为止 |

## 三个新概念逐个击破

### ① State + reducer（最反直觉）

手写版里列表归你，直接改；图版本里列表归框架管，节点只能**声明增量**：

```python
def agent_node(state):
    ...
    return {"messages": [新消息]}     # 注意：只返回增量，没有 append！
```

谁来做 append？reducer。State 里登记合并规则：

```python
class State(TypedDict):
    messages: Annotated[list, append_messages]   # "追加"，不是"覆盖"

def append_messages(existing, new):
    return existing + new      # 旧值 + 增量 = 新状态
```

为什么绕这一道？图版本里同一个 State 可能被**多个节点并行写**。大家都
直接改列表就会互相踩踏；声明增量 + 统一合并规则，框架才能安全调度。

### ② 节点 = 循环体切出来的两段

```python
def agent_node(state):     # 对应 "Thought" 段
    r = client.chat.completions.create(...)      # 问模型
    return {"messages": [模型的消息]}

def tools_node(state):     # 对应 "Action + Observation" 段
    for tc in state["messages"][-1]["tool_calls"]:   # 读盒子里 agent 刚放的意图
        执行，收集 tool 消息
    return {"messages": outs}     # 增量：这轮的工具结果
```

节点间**不传参数**，靠 State 通信——就像手写版下半段读上半段写进
`messages` 的 `tool_calls` 一样。

### ③ 边与条件边 = 循环的骨架

```python
graph.add_edge(START, "agent")              # 入口：从 agent 开始
graph.add_conditional_edges("agent", route) # agent 之后走哪？route 说了算
graph.add_edge("tools", "agent")            # tools 后必回 agent ← 这条边就是 while！
```

条件边就是出口 if，只是换了个写法——**返回值是下一站的名字**：

```python
def route(state):
    last = state["messages"][-1]
    return "tools" if last.get("tool_calls") else END
    #      ↑ 还要工具 → 去 tools        ↑ 不要了 → 出口（END 是哨兵）
```

`START` / `END` 不是节点，是两个**路标哨兵**：一个标记"从这里进"，
一个标记"到这里停"。

## 组图 8 行 → while 循环的一字不差翻译

```python
graph = StateGraph(State)                    # 建图，状态盒子长这样
graph.add_node("agent", agent_node)          # 注册节点1（问模型）
graph.add_node("tools", tools_node)          # 注册节点2（执行工具）
graph.add_edge(START, "agent")               # 入口 → agent
graph.add_conditional_edges("agent", route)  # agent 后：route 决定去向
graph.add_edge("tools", "agent")             # tools 后：必回 agent（成环）
app = graph.compile()                        # 编译成可运行的机器
```

```python
messages = [初始消息]                        # State 初始化
while True:                                  # add_edge("tools","agent") 形成的环
    m = 问模型(messages)                      # agent_node
    messages.append(m)                       # reducer
    if not m.tool_calls: break               # route 返回 END
    for tc in m.tool_calls:                  # tools_node
        messages.append(执行结果)             # reducer
```

## invoke 的执行时间线

```text
app.invoke({"messages": [用户任务]})
   │
   ▼
START ──▶ agent_node ──▶ route: 有 tool_calls? ──是──▶ tools_node ──┐
              │                    │                             │
              │                    └──否──▶ END                  │
              ▼                                                  │
        （reducer 合并：assistant 消息进了 State）               │
              ▲                                                  │
              └───────── add_edge("tools","agent") ◀─────────────┘
```

运行输出节奏：`agent → tools → agent → tools → agent → END`，
与第 3 课的 `[第1轮·思考/动作/观察]` 完全同构。

## 那到底为什么要用框架？

玩具 Agent 手写更好——更短、零依赖、完全透明。框架的价值在流程
**变大**之后：

1. **checkpoint 持久化**：每过一个节点自动存档，崩了从断点续跑；
2. **human-in-the-loop**：指定节点前自动暂停，等人批准再继续；
3. **并行分支**：多节点同时跑，reducer 自动合并（手写要管线程竞态）；
4. **复杂路由**：5 个节点十几种跳转时，图比嵌套 if/while 清晰。

课程把它放最后一课的原因：**先见循环，再见封装**——看穿了它，
以后读任何 Agent 框架（LangGraph / CrewAI / AutoGen）都能对号入座。

## 本课踩过的真实坑（血泪纪念）

1. **`add_messages` 与裸 OpenAI SDK 混用**：框架自带的 `add_messages`
   会把 dict 转成 LangChain 消息对象，直接传给 OpenAI SDK 会产生非法
   JSON（API 400）。解法：自定义纯 dict 的 reducer（见课程代码
   `append_messages`）。
2. **JSON Schema 手写括号**：`required` 应与 `properties` 平级，手写
   极易嵌错层（第 4 课真实踩过，API 报 `Invalid schema`）。排查技巧：
   `json.dumps(tools, indent=2)` 打印看真实结构。

## 自检三问

1. `Annotated[list, append_messages]` 里那个函数是干嘛的？
   （合并规则：节点返回增量时框架用它拼新旧值，等价于 `messages.append`）
2. 图里没有 `while` 这个词，循环体现在哪？
   （`tools → agent` 那条边：走完又回到起点，环即循环）
3. `route` 返回 `END` 时发生什么？
   （框架停止调度，`invoke` 返回最终 State——等价于手写版的 return）
