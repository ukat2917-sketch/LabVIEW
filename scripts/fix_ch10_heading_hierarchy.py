from pathlib import Path
import re

DOC = Path("docs/10_RAMScope実装方針.md")
SCRIPT = Path("scripts/fix_ch10_heading_hierarchy.py")
WORKFLOW = Path(".github/workflows/fix-ch10-heading-hierarchy.yml")

text = DOC.read_text(encoding="utf-8")

text = text.replace(
    "### 10.8.3 2つのPoCの完成条件",
    "### 10.13.4 2つのPoCの完成条件",
)

# Logging PoCの0〜9節は、10.13.2の子見出しへ下げる。
start = text.index("### 10.13.2 `PoC_RAMScope_Logging_Main.vi`")
end = text.index("### 10.13.3 TestStand組込み順", start)
segment = text[start:end]
segment = re.sub(r"(?m)^### ([0-9]+\. .*)$", r"#### \1", segment)
segment = re.sub(r"(?m)^#### ([A-G]\. .*)$", r"##### \1", segment)
text = text[:start] + segment + text[end:]

# 追加Wrapper／追加Public APIの個別VI見出しを親節の子へ下げる。
text = re.sub(r"(?m)^### (10\.8\.3\.\d+ .*)$", r"#### \1", text)
text = re.sub(r"(?m)^### (10\.11\.9\.\d+ .*)$", r"#### \1", text)

# 連続した区切り線を1本へ整理する。
text = re.sub(r"\n---\n\n---\n", "\n---\n", text)

DOC.write_text(text, encoding="utf-8", newline="\n")
SCRIPT.unlink(missing_ok=True)
WORKFLOW.unlink(missing_ok=True)
