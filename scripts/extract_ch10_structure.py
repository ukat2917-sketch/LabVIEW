from pathlib import Path
import re

src = Path('docs/10_RAMScope実装方針.md')
out = Path('docs/ch10-structure.txt')
text = src.read_text(encoding='utf-8')
lines = text.splitlines()
records = []
for i, line in enumerate(lines, start=1):
    if re.match(r'^(#{2,5})\s+10(?:\.|\s)', line):
        records.append(f'{i:05d}\t{line}')
out.write_text('\n'.join(records) + '\n', encoding='utf-8')
