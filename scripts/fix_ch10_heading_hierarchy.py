from pathlib import Path
import re

DOC = Path("docs/10_RAMScope実装方針.md")
SCRIPT = Path("scripts/fix_ch10_heading_hierarchy.py")
WORKFLOW = Path(".github/workflows/fix-ch10-heading-hierarchy.yml")
TRIGGER = Path(".chapter10-heading-fix-trigger")

text = DOC.read_text(encoding="utf-8")

text = text.replace(
    "### 10.8.3 2つのPoCの完成条件",
    "### 10.13.4 2つのPoCの完成条件",
)

start = text.index("### 10.13.2 `PoC_RAMScope_Logging_Main.vi`")
end = text.index("### 10.13.3 TestStand組込み順", start)
segment = text[start:end]
segment = re.sub(r"(?m)^### ([0-9]+\. .*)$", r"#### \1", segment)
segment = re.sub(r"(?m)^#### ([A-G]\. .*)$", r"##### \1", segment)
text = text[:start] + segment + text[end:]

text = re.sub(r"(?m)^### (10\.8\.3\.\d+ .*)$", r"#### \1", text)
text = re.sub(r"(?m)^### (10\.11\.9\.\d+ .*)$", r"#### \1", text)
text = re.sub(r"\n---\n\n---\n", "\n---\n", text)

DOC.write_text(text, encoding="utf-8", newline="\n")
for path in (SCRIPT, WORKFLOW, TRIGGER):
    path.unlink(missing_ok=True)
