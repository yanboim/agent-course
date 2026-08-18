# Agent 开发手把手课程

> 目标方向：**通用 Agent 应用开发**（工作流自动化 / RAG / 多 Agent 协作）
> 教学方式：每课 = 原理讲解 → 一起写代码 → 运行观察 → 留练习
> 原则：**先用裸 API 手写，最后才碰框架**。框架只是循环的封装，先见循环，再见封装。

## 课程表（按序完成，勾选进度）

- [ ] **第 1 课** `lesson_01_hello_llm` —— LLM API 基础：messages 结构 / 流式 / 结构化输出 / "模型无记忆"的真相
- [ ] **第 2 课** `lesson_02_tool_calling` —— Function Calling：Agent 的心脏
- [ ] **第 3 课** `lesson_03_agent_loop` —— 约 100 行手写 ReAct Agent（while 循环 + 工具选择）
- [ ] **第 4 课** `lesson_04_real_tools` —— 接入真实工具（文件读写 / 执行命令 / HTTP）+ 错误处理
- [ ] **第 5 课** `lesson_05_memory` —— 上下文管理：裁剪、摘要压缩、长期记忆
- [ ] **第 6 课** `lesson_06_rag` —— 手写迷你 RAG（embedding + 向量检索 + 重排）
- [ ] **第 7 课** `lesson_07_multi_agent` —— 多 Agent 协作（planner / executor / reviewer）
- [ ] **第 8 课** `lesson_08_langgraph` —— 用 LangGraph 重写第 3 课的 Agent，理解框架到底解决了什么

## 环境（服务器：Ubuntu 26.04 @ 192.168.0.111）

课程项目位于 `/workspace/build/course/agent-course`（workspace 根为 `/workspace/build/course`）：

- Python 3.14.4（系统）+ 独立虚拟环境 `.venv/`（由 uv 创建）
- 依赖：openai 3.2.0、python-dotenv（走阿里 PyPI 镜像，直连无需代理）
- API：DeepSeek（OpenAI 兼容接口），key 在 `.env`

### 日常使用

```bash
ssh root@192.168.0.111
cd /workspace/build/course/agent-course
source .venv/bin/activate          # 激活虚拟环境（每次登录后执行一次）
python lesson_01_hello_llm/01_first_call.py   # 运行示例
```

### 管理依赖（需要加包时）

```bash
uv pip install <包名> --index-url https://mirrors.aliyun.com/pypi/simple/
```

## 每课流程

1. 读该课 `README.md`（课后复习用，讲解以对话为主）
2. 依次运行、阅读带注释的示例代码
3. 完成课末练习
4. 有任何看不懂的地方随时问
