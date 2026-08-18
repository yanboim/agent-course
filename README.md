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

## 快速开始（从零跑起来）

### 1. 克隆仓库

```bash
git clone https://github.com/yanboim/agent-course.git
cd agent-course
```

### 2. 准备 Python 环境（3.10+，推荐 [uv](https://docs.astral.sh/uv/)）

```bash
# 安装 uv（Linux/macOS；已有任意虚拟环境工具可跳过）
curl -LsSf https://astral.sh/uv/install.sh | sh

uv venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
```

### 3. 安装依赖

```bash
uv pip install -r requirements.txt --index-url https://mirrors.aliyun.com/pypi/simple/
# 或普通 pip：pip install -r requirements.txt
```

### 4. 配置 API Key（本课程用 DeepSeek，OpenAI 兼容接口）

```bash
cp .env.example .env
# 编辑 .env，填入你的 key（获取：https://platform.deepseek.com -> API Keys）
```

> 安全提醒：`.env` 已被 `.gitignore` 排除，永远不要把它提交进仓库。

### 5. 跑通第一课

```bash
python lesson_01_hello_llm/01_first_call.py
```

看到"无记忆实验"的三连问输出，环境就绪。

### 模型说明

示例代码统一使用 `deepseek-v4-flash`（写死显式模型名，避免官方滚动别名静默变更导致行为漂移）。
换成任何 OpenAI 兼容服务（如 vLLM 自部署端点）只需改 `base_url` + `model`。

## 每课流程

1. 读该课 `README.md`（课后复习用，讲解以对话为主）
2. 依次运行、阅读带注释的示例代码
3. 完成课末练习（做完才算过关）
4. 有任何看不懂的地方随时问

## 课程主线（一句话版）

1～3 课揭示 Agent 本质：**LLM 驱动的循环**（无状态 → 工具协议 → while 循环）；
4～7 课补生产拼图：安全、记忆、检索、协作；
第 8 课拆穿框架：LangGraph 只是把你的 `while` 画成了图。

## License

[MIT](./LICENSE) —— 教学代码随意取用，欢迎 Star / PR / 提 Issue。
