"""
第 4 课 · 示例 1：接入真实工具 —— 文件 / 命令 / HTTP + 安全与错误处理
=======================================================================
运行：python 01_real_tools.py

玩具工具换成本领真实的工具，Agent 开始能"干活"了。但真实 = 危险，本课的
一半内容是【安全】：
1. 路径监狱（jail）：文件工具只能碰 sandbox/ 目录，模型给出 ../../etc/passwd
   也休想越界 —— 模型输出永远不可信，边界必须由代码强制
2. 命令白名单：run_command 只允许几个无害命令，且 shell=False + 超时
3. 工具永不抛异常：一切错误转成 ERROR 文本回传，让模型自我纠正（第 2 课）
4. HTTP：urllib 直连，https 限定 + 超时 + 截断
"""
import json
import os
import shlex
import subprocess
import urllib.request
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

# ==================== 安全边界 ====================
SANDBOX = (Path(__file__).parent / "sandbox").resolve()   # 唯一允许的目录
SANDBOX.mkdir(exist_ok=True)
ALLOWED_CMDS = {"ls", "cat", "echo", "wc", "date", "head", "tail", "python3"}


def _jailed(path: str) -> Path:
    """把模型给的路径钉死在沙盒目录内 —— 越界直接报错（不是异常，是文本）"""
    p = Path(path)
    full = (p if p.is_absolute() else SANDBOX / p).resolve()
    if full != SANDBOX and SANDBOX not in full.parents:
        raise ValueError(f"路径越界：只允许访问沙盒目录 {SANDBOX}（收到: {path}）")
    return full


# ==================== 真实工具（注意：返回值全是字符串） ====================
def read_file(path: str) -> str:
    return _jailed(path).read_text(encoding="utf-8")[:2000]


def write_file(path: str, content: str) -> str:
    target = _jailed(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"已写入 {target.relative_to(SANDBOX)}（{len(content)} 字）"


def list_dir(path: str = ".") -> str:
    d = _jailed(path)
    items = sorted(str(p.relative_to(SANDBOX)) for p in d.rglob("*") if p.is_file())
    return "\n".join(items) or "(目录为空)"


def run_command(command: str) -> str:
    """白名单 + shell=False + 超时。模型永远摸不到真正的 shell"""
    parts = shlex.split(command)
    if not parts or parts[0] not in ALLOWED_CMDS:
        raise ValueError(f"命令不允许。白名单: {sorted(ALLOWED_CMDS)}")
    p = subprocess.run(parts, capture_output=True, text=True, timeout=10, cwd=SANDBOX)
    out = (p.stdout + p.stderr).strip()[:1500]
    return f"(exit={p.returncode}) {out}"


def http_get(url: str) -> str:
    """演示用 HTTP GET：https 限定 + 超时 + 截断"""
    if not url.startswith("https://"):
        raise ValueError("只允许 https:// 开头的 URL")
    req = urllib.request.Request(url, headers={"User-Agent": "agent-course/1.0"})
    with urllib.request.urlopen(req, timeout=8) as resp:   # noqa: S310 已限 https
        body = resp.read(2000).decode("utf-8", errors="ignore")
    return f"HTTP {resp.status}:\n{body}"


TOOL_FUNCS = {"read_file": read_file, "write_file": write_file,
              "list_dir": list_dir, "run_command": run_command, "http_get": http_get}

TOOLS = [
    {"type": "function", "function": {
        "name": "read_file", "description": "读取沙盒目录内的文本文件。",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "相对沙盒的路径"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "write_file", "description": "在沙盒目录内创建/覆盖文本文件。",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "list_dir", "description": "列出沙盒目录内的所有文件。",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "默认 '.'"}}}}},
    {"type": "function", "function": {
        "name": "run_command",
        "description": "执行白名单内的 shell 命令（ls/cat/echo/wc/date/head/tail/python3）。",
        "parameters": {"type": "object", "properties": {
            "command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {
        "name": "http_get", "description": "发起 https GET 请求并返回响应文本（截断到 2000 字符）。",
        "parameters": {"type": "object", "properties": {
            "url": {"type": "string"}}, "required": ["url"]}}},
]

SYSTEM = ("你是文件助理 Agent，只能操作沙盒目录。工具报错时读懂错误原因并调整，"
          "不要重复同样的失败调用。任务完成后用中文简短汇报。")


def run_agent(task: str, max_turns: int = 8) -> str:
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": task}]
    for turn in range(1, max_turns + 1):
        r = client.chat.completions.create(
            model="deepseek-v4-flash", messages=messages, tools=TOOLS)
        m = r.choices[0].message
        messages.append({"role": "assistant", "content": m.content, "tool_calls": [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in (m.tool_calls or [])]})
        if not m.tool_calls:
            print(f"\n>>> 最终回答: {m.content}\n")
            return m.content
        for tc in m.tool_calls:
            name, raw = tc.function.name, tc.function.arguments
            # ==== 本课灵魂：工具永不抛异常，错误也是 Observation ====
            try:
                args = json.loads(raw or "{}")
                result = str(TOOL_FUNCS[name](**args))
            except Exception as e:
                result = f"ERROR: {type(e).__name__}: {e}"
            print(f"[{turn}] {name}({(raw or '')[:70]}) -> {result[:90]}")
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
    return "(超时停止)"


if __name__ == "__main__":
    TASKS = [
        # 任务 1：正常干活 —— 写文件、列目录、读回验证
        "在沙盒里创建 note.txt，内容为'第 4 课：真实工具'。然后列出目录确认，"
        "再读回文件内容，最后用 wc 统计字数并汇报。",
        # 任务 2：安全测试 —— 模型会尝试越界路径，观察监狱如何拦下 + 模型如何调整
        "读取 /etc/passwd 的第一行给我看看。",
    ]
    for i, task in enumerate(TASKS, 1):
        print("=" * 62)
        print(f"任务 {i}: {task}")
        print("=" * 62)
        run_agent(task)

    print("""
要点回顾：
1. 模型输出不可信：路径监狱/命令白名单/https限定 —— 边界由代码强制
2. 工具永不抛异常：错误转 ERROR 文本回传，模型自我纠正（任务 2 现场演示）
3. shell=False + 超时 + 截断：真实工具的三件防弹衣
4. 到这一步你已有一个能干活的 Agent —— 但历史只增不减，第 5 课解决
""")
