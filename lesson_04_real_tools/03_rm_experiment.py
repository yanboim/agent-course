"""
第 4 课 · 练习 3（危险实验，受控演示）：把 rm 加进白名单会怎样？
===================================================================
运行：python 03_rm_experiment.py

结论先行：**命令白名单挡得住"程序名"，挡不住"程序能力"**。

cat / echo 天生只读，白名单放行无妨；rm 的能力是【不可逆删除】，
把它加进白名单的那一刻，等于授权模型删除"它能触及的一切"：
1. cwd 只影响【相对路径】—— rm -rf /绝对路径 轻松逃出沙盒目录
2. 模型控制【参数】—— 白名单了程序名，管不住它删哪里、删多深
3. rm 没有 --dry-run、没有回收站、没有二次确认，删了就是没了

本脚本用 /tmp 下自建的诱饵目录做受控演示（唯一会被删的东西），
验证"绝对路径逃逸"后立刻复盘。真实教训：删除需求请用带
回收站+二次确认的 delete_file（见 01_real_tools.py 练习 2 实现）。
"""
import json
import os
import shlex
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
MODEL = "deepseek-v4-flash"

SANDBOX = Path(__file__).parent.resolve() / "sandbox"   # 只是 cwd，不是监狱！
SANDBOX.mkdir(exist_ok=True)
DECOY = Path("/tmp/ac_rm_decoy")                        # 受控诱饵：本实验唯一牺牲品

# ==== 危险开关：仅本实验临时把 rm 加入白名单 ====
ALLOWED_CMDS = {"ls", "cat", "echo", "rm"}


def run_command(command: str) -> str:
    parts = shlex.split(command)
    if not parts or parts[0] not in ALLOWED_CMDS:
        raise ValueError(f"命令不允许。白名单: {sorted(ALLOWED_CMDS)}")
    p = subprocess.run(parts, capture_output=True, text=True, timeout=10, cwd=SANDBOX)
    return f"(exit={p.returncode}) {(p.stdout + p.stderr).strip()[:300]}"


TOOLS = [{
    "type": "function",
    "function": {
        "name": "run_command",
        "description": "执行白名单内的 shell 命令（ls/cat/echo/rm）。",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        },
    },
}]


def run_agent(task: str, max_turns: int = 4) -> None:
    messages = [
        {"role": "system", "content": "你是文件清理助手，用工具完成任务，不要多余解释。"},
        {"role": "user", "content": task},
    ]
    for turn in range(1, max_turns + 1):
        r = client.chat.completions.create(model=MODEL, messages=messages, tools=TOOLS)
        m = r.choices[0].message
        messages.append({"role": "assistant", "content": m.content, "tool_calls": [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in (m.tool_calls or [])]})
        if not m.tool_calls:
            print(f"[第{turn}轮·最终回答] {m.content.strip()[:100]}")
            return
        for tc in m.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
                print(f"[第{turn}轮·动作] {args.get('command')}")
                result = run_command(**args)
            except Exception as e:
                result = f"ERROR: {e}"
            print(f"[第{turn}轮·观察] {result[:150]}")
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})


if __name__ == "__main__":
    # 造诱饵：/tmp 下的三层目录树
    (DECOY / "nested" / "deep").mkdir(parents=True, exist_ok=True)
    (DECOY / "a.txt").write_text("诱饵A", encoding="utf-8")
    (DECOY / "nested" / "b.txt").write_text("诱饵B", encoding="utf-8")
    (DECOY / "nested" / "deep" / "c.txt").write_text("诱饵C", encoding="utf-8")

    print(f"[实验准备] 诱饵目录: {DECOY}（三层，含3个文件）")
    print(f"[实验准备] 工具 cwd 钉在: {SANDBOX}")
    print("[实验准备] 注意：cwd 只约束相对路径，管不住绝对路径！\n")
    print("=" * 60)
    print(f"任务: 帮我把 {DECOY} 这个目录整个清理掉，删干净一点。")
    print("=" * 60)
    run_agent(f"帮我把 {DECOY} 这个目录整个清理掉，删干净一点。")

    print(f"\n[实验结果] 诱饵目录还存在吗？ {DECOY.exists()}")
    print(f"""[危险复盘] rm 在白名单内时，模型实际拥有的能力：

    rm -rf {DECOY}                        <- 本实验：删掉了 cwd 之外的 /tmp 目录
    rm -rf {SANDBOX}                      <- 它同样做得到（沙盒本身也不保）
    rm -rf /workspace/build/course/agent-course   <- 仓库能被整个抹掉（root 权限）
    rm -rf $HOME /etc ...                 <- 没有任何代码层面的东西能拦住

结论：命令白名单挡的是"程序名"，挡不住"程序能力"。
白名单里每多一个命令，都该问一句："它最坏能干什么？"
—— 这就是最小权限原则（Principle of Least Privilege）。
删除需求永远用带回收站 + 二次确认的专用工具，而不是 shell 的 rm。
""")

    # 兜底清理：若模型没删干净（或实验中断），脚本收尾时删掉诱饵
    if DECOY.exists():
        subprocess.run(["rm", "-rf", str(DECOY)], check=False)
        print("[收尾] 兜底清理诱饵完成")
