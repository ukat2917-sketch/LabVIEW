#!/usr/bin/env python3
"""Generate consistent SVG input/output diagrams from Markdown VI definitions."""

from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUT = DOCS / "assets" / "vi-diagrams"
MARKER = "<!-- generated-vi-diagram -->"
APPENDIX_START = "<!-- generated-vi-reference-start -->"
APPENDIX_END = "<!-- generated-vi-reference-end -->"


@dataclass(frozen=True)
class Terminal:
    name: str
    type_name: str
    value: str


def clean(value: str) -> str:
    value = re.sub(r"<br\s*/?>", " / ", value, flags=re.I)
    value = re.sub(r"[`*_]", "", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", value)
    return re.sub(r"\s+", " ", value).strip(" |。")


def normalize_vi_name(name: str) -> str:
    return clean(name).replace("\\", "/").rsplit("/", 1)[-1]


def slug(name: str) -> str:
    base = re.sub(r"[^A-Za-z0-9]+", "-", name.removesuffix(".vi")).strip("-").lower()
    return base or hashlib.sha1(name.encode()).hexdigest()[:12]


def sample_value(name: str, type_name: str, direction: str) -> str:
    key = f"{name} {type_name}".lower()
    if "error" in key:
        return "status=False"
    if "boolean" in key or "bool" in key or name.endswith("?"):
        return "False"
    if "string" in key:
        return '""'
    if "path" in key:
        return "C:\\logs\\test.tdms"
    if "timestamp" in key:
        return "0.0 s"
    if "array" in key or "[]" in key or "配列" in key:
        return "[]"
    if "ref" in key or "session" in key:
        return "有効Ref"
    if "status.ctl" in key:
        return "OK"
    if "testerror.ctl" in key:
        return "code=0"
    if any(t in key for t in ("i32", "u32", "i64", "u64", "numeric", "number")):
        return "0"
    if any(t in key for t in ("dbl", "double", "single")):
        return "0.0"
    if "enum" in key:
        return "既定値"
    return "正常値" if direction == "out" else "既定値"


def parse_table(lines: list[str], index: int, context: str) -> tuple[list[Terminal], list[Terminal], int]:
    block: list[list[str]] = []
    i = index
    while i < len(lines) and lines[i].lstrip().startswith("|"):
        cells = [clean(c) for c in lines[i].strip().strip("|").split("|")]
        block.append(cells)
        i += 1
    if len(block) < 2:
        return [], [], i
    header = [c.lower() for c in block[0]]
    if all(set(c) <= {"-", ":"} for c in block[1]):
        rows = block[2:]
    else:
        rows = block[1:]
    name_idx = next((n for n, c in enumerate(header) if any(x in c for x in ("端子", "入力", "出力", "項目", "名前"))), 0)
    dir_idx = next((n for n, c in enumerate(header) if "方向" in c), None)
    type_idx = next((n for n, c in enumerate(header) if "型" in c), None)
    default_dir = "in" if "入力" in context and "出力" not in context else "out" if "出力" in context else None
    inputs: list[Terminal] = []
    outputs: list[Terminal] = []
    for row in rows:
        if name_idx >= len(row):
            continue
        name = row[name_idx]
        if not name or len(name) > 70:
            continue
        direction = default_dir
        if dir_idx is not None and dir_idx < len(row):
            d = row[dir_idx]
            if "入力" in d:
                direction = "in"
            elif "出力" in d:
                direction = "out"
        if direction is None:
            continue
        type_name = row[type_idx] if type_idx is not None and type_idx < len(row) else "本文参照"
        term = Terminal(name, type_name or "本文参照", sample_value(name, type_name, direction))
        (inputs if direction == "in" else outputs).append(term)
    return inputs, outputs, i


def section_for(lines: list[str], start: int) -> list[str]:
    level = len(lines[start]) - len(lines[start].lstrip("#"))
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("#"):
            next_level = len(lines[i]) - len(lines[i].lstrip("#"))
            if next_level <= level:
                end = i
                break
    return lines[start:end]


def parse_terminals(section: list[str]) -> tuple[list[Terminal], list[Terminal]]:
    table_inputs: list[Terminal] = []
    table_outputs: list[Terminal] = []
    arrow_inputs: list[Terminal] = []
    arrow_outputs: list[Terminal] = []
    context = ""
    i = 0
    while i < len(section):
        line = section[i]
        if line.startswith("#"):
            context = clean(line.lstrip("#"))
        if line.lstrip().startswith("|"):
            ins, outs, i = parse_table(section, i, context)
            table_inputs.extend(ins)
            table_outputs.extend(outs)
            continue
        if "→" in line and not line.lstrip().startswith("|") and "─" not in line:
            left, right = [clean(x) for x in line.split("→", 1)]
            internal = ("clfn", "case", "loop", "右端子", "左端子", "vi内", "処理")
            if 0 < len(left) <= 55 and 0 < len(right) <= 55:
                if not any(x in left.lower() for x in internal):
                    arrow_inputs.append(Terminal(left, "本文参照", sample_value(left, "", "in")))
                if not any(x in right.lower() for x in internal):
                    arrow_outputs.append(Terminal(right, "本文参照", sample_value(right, "", "out")))
        i += 1

    def dedupe(items: list[Terminal]) -> list[Terminal]:
        result: list[Terminal] = []
        seen: set[str] = set()
        for item in items:
            key = item.name.lower()
            if key in seen or len(item.name) > 70:
                continue
            seen.add(key)
            result.append(item)
        return result

    has_table_terminals = any("error" not in t.name.lower() for t in table_inputs + table_outputs)
    inputs = dedupe(table_inputs if has_table_terminals else arrow_inputs)
    outputs = dedupe(table_outputs if has_table_terminals else arrow_outputs)
    # Internal error wiring must never appear as an additional front-panel terminal.
    inputs = [t for t in inputs if "error" not in t.name.lower()]
    outputs = [t for t in outputs if "error" not in t.name.lower()]
    if not inputs:
        inputs.append(Terminal("入力端子", "実VIで確認", "確認待ち"))
    if not outputs:
        outputs.append(Terminal("出力端子", "実VIで確認", "確認待ち"))
    # Reserve the last slot for exactly one standard error terminal on each side.
    inputs = inputs[:13] + [Terminal("error in", "error cluster", "status=False")]
    outputs = outputs[:13] + [Terminal("error out", "error cluster", "status=False")]
    return inputs, outputs


def terminal_color(term: Terminal) -> tuple[str, str]:
    key = f"{term.name} {term.type_name}".lower()
    if "error" in key:
        return "#A63A3A", "#FCE8E8"
    if any(x in key for x in ("bool", "boolean", "?")):
        return "#2F8F46", "#E8F7EC"
    if any(x in key for x in ("string", "path")):
        return "#A34AA8", "#F8EAF8"
    if any(x in key for x in ("ref", "session")):
        return "#2B76C4", "#E8F2FC"
    if any(x in key for x in ("cluster", ".ctl")):
        return "#B57A00", "#FFF4D6"
    return "#E06B00", "#FFF0E1"


def svg_for_vi(name: str, source: str, inputs: list[Terminal], outputs: list[Terminal]) -> str:
    count = max(len(inputs), len(outputs), 5)
    row_h = 72
    top = 125
    height = max(620, top + count * row_h + 72)
    width = 1600
    block_x, block_w = 620, 360
    block_y, block_h = 105, height - 190
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f"<title id=\"title\">{html.escape(name)} 入出力イメージ</title>",
        f"<desc id=\"desc\">中央にVI、左に入力端子、右に出力端子、最下段にerror inとerror outを配置した図。</desc>",
        "<defs>",
        '<linearGradient id="panel" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFFDF9"/><stop offset="1" stop-color="#ECE8E1"/></linearGradient>',
        '<filter id="shadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="8" stdDeviation="10" flood-color="#333333" flood-opacity=".18"/></filter>',
        "</defs>",
        '<rect width="1600" height="100%" fill="#FFFFFF"/>',
        f'<text x="800" y="46" text-anchor="middle" font-family="Yu Gothic, Noto Sans JP, sans-serif" font-size="26" font-weight="600" fill="#222">{html.escape(name)}</text>',
        f'<text x="800" y="76" text-anchor="middle" font-family="Yu Gothic, Noto Sans JP, sans-serif" font-size="15" fill="#666">入力値 → VI処理 → 出力値　　出典: {html.escape(source)}</text>',
        f'<rect x="{block_x}" y="{block_y}" width="{block_w}" height="{block_h}" rx="28" fill="url(#panel)" stroke="#343434" stroke-width="7" filter="url(#shadow)"/>',
        f'<rect x="{block_x+75}" y="{block_y+70}" width="{block_w-150}" height="130" rx="18" fill="#FFFFFF" stroke="#666" stroke-width="3"/>',
        f'<path d="M {block_x+105} {block_y+145} C {block_x+145} {block_y+65}, {block_x+190} {block_y+225}, {block_x+250} {block_y+125}" fill="none" stroke="#444" stroke-width="8" stroke-linecap="round"/>',
        f'<text x="800" y="{block_y+250}" text-anchor="middle" font-family="Yu Gothic, Noto Sans JP, sans-serif" font-size="20" font-weight="600" fill="#333">VI</text>',
    ]

    def draw_side(items: list[Terminal], side: str) -> None:
        for idx, term in enumerate(items):
            y = top + idx * row_h
            stroke, fill = terminal_color(term)
            if side == "left":
                box_x, box_w, port_x = 55, 475, block_x + 22
                line_x1, line_x2 = box_x + box_w, port_x
                text_x, anchor = box_x + 20, "start"
            else:
                box_x, box_w, port_x = 1070, 475, block_x + block_w - 22
                line_x1, line_x2 = port_x, box_x
                text_x, anchor = box_x + 20, "start"
            parts.extend([
                f'<line x1="{line_x1}" y1="{y+22}" x2="{line_x2}" y2="{y+22}" stroke="{stroke}" stroke-width="5" stroke-linecap="round"/>',
                f'<circle cx="{port_x}" cy="{y+22}" r="13" fill="{fill}" stroke="{stroke}" stroke-width="5"/>',
                f'<rect x="{box_x}" y="{y-4}" width="{box_w}" height="54" rx="14" fill="{fill}" stroke="{stroke}" stroke-width="2"/>',
                f'<text x="{text_x}" y="{y+17}" text-anchor="{anchor}" font-family="Yu Gothic, Noto Sans JP, sans-serif" font-size="17" font-weight="600" fill="#242424">{html.escape(term.name)}</text>',
                f'<text x="{text_x}" y="{y+39}" text-anchor="{anchor}" font-family="Yu Gothic, Noto Sans JP, sans-serif" font-size="14" fill="#4B4B4B">{html.escape(term.type_name)} · {html.escape(term.value)}</text>',
            ])

    draw_side(inputs, "left")
    draw_side(outputs, "right")
    parts.extend([
        f'<text x="55" y="{height-28}" font-family="Yu Gothic, Noto Sans JP, sans-serif" font-size="14" fill="#666">左：制御器／定数から入力</text>',
        f'<text x="1545" y="{height-28}" text-anchor="end" font-family="Yu Gothic, Noto Sans JP, sans-serif" font-size="14" fill="#666">右：表示器／次段VIへ出力</text>',
        "</svg>",
    ])
    return "\n".join(parts)


FLOW_SPECS = {
    "08_負荷電流VIと並列処理.md": [(
        "load-current-parallel-flow.svg",
        "負荷電流ランプと並列処理",
        [
            ("TestStand", "条件・非同期開始"),
            ("Load_Current_Ramp.vi", "Current / Stop / error"),
            ("CAN・計測処理", "指定時刻で並行"),
            ("Cleanup", "安全値へ復帰"),
        ],
    )],
    "09_CAN通信の実装.md": [(
        "canalyzer-public-api-flow.svg",
        "CANalyzer公開API接続",
        [
            ("CANalyzer_Open.vi", "Session ID / State"),
            ("CANalyzer_Start.vi", "Measuring?"),
            ("Read / Write SysVar", "Value / Result"),
            ("Fault Control", "Fault State"),
            ("CANalyzer_Stop.vi", "Stopped?"),
            ("CANalyzer_Close.vi", "error out"),
        ],
    )],
    "10_RAMScope実装方針.md": [(
        "ramscope-public-api-flow.svg",
        "RAMScope公開API接続",
        [
            ("RAMScope_Connect.vi", "UnitNum / kind"),
            ("RAMScope_Init.vi", "Module List / MdlNo"),
            ("RAMScope_Set_Cond.vi", "測定条件"),
            ("RAMScope_Log_Start.vi", "Started"),
            ("RAMScope_Read.vi", "Packets / DataNum"),
            ("RAMScope_Log_Stop.vi", "Stopped"),
            ("RAMScope_Release.vi", "Released"),
            ("RAMScope_Close.vi", "Final error"),
        ],
    ), (
        "ramscope-logging-public-api-flow.svg",
        "RAMScopeロギング公開API接続",
        [
            ("RAMScope_Connect.vi", "UnitNum / kind"),
            ("RAMScope_Init.vi", "Module List / MdlNo"),
            ("RAMScope_Set_Cond.vi", "測定条件"),
            ("RAMScope_File_Log_Open.vi", "File Ref"),
            ("RAMScope_Log_Start.vi", "Started"),
            ("RAMScope_Log_Stop.vi", "Stopped"),
            ("Get Log Summary", "Block / Sample概要"),
            ("Get Block Count", "Block数"),
            ("Read Logging Block", "Logging Data"),
            ("RAMScope_File_Log_Append.vi", "保存結果"),
            ("RAMScope_Release.vi", "Released"),
            ("RAMScope_File_Log_Close.vi", "File closed"),
            ("RAMScope_Close.vi", "Final error"),
        ],
    )],
    "11_TestStandシーケンス構築手順.md": [(
        "teststand-public-api-flow.svg",
        "TestStandと公開APIの接続",
        [
            ("Setup", "Connect / Init / Set"),
            ("Main", "Start / DUT / Read / Stop"),
            ("Logging", "Summary / Block / TDMS"),
            ("Cleanup", "Release / Close"),
        ],
    )],
    "12_異常系処理とシャットダウン設計.md": [(
        "cleanup-flow.svg",
        "異常時Cleanup接続",
        [
            ("Original Error", "最初の失敗を保持"),
            ("危険出力OFF", "電源・負荷・FG420"),
            ("測定Stop", "RAMScope / CANalyzer"),
            ("データ保存・Close", "TDMS / Buffer"),
            ("通信Close", "全Reference解放"),
            ("Merge Errors", "Original優先"),
        ],
    )],
    "A1A_FG420複数台2ch出力リミットPoC.md": [(
        "fg420-public-api-flow.svg",
        "FG420公開API接続",
        [
            ("FG420_Prepare_Device.vi", "VISA Ref / State"),
            ("Configure_Channel_Safe.vi", "Ch1 / Ch2条件"),
            ("FG420_Output.vi", "Output=True"),
            ("試験・測定", "応答値"),
            ("FG420_Output.vi", "Output=False"),
            ("FG420_Close.vi", "error out"),
        ],
    )],
}


def strip_generated(lines: list[str]) -> list[str]:
    result: list[str] = []
    i = 0
    while i < len(lines):
        if lines[i].strip() == APPENDIX_START:
            i += 1
            while i < len(lines) and lines[i].strip() != APPENDIX_END:
                i += 1
            i += 1
            continue
        if lines[i].strip() == MARKER:
            if result and not result[-1].strip():
                result.pop()
            i += 1
            if i < len(lines) and lines[i].lstrip().startswith("!["):
                i += 1
            continue
        result.append(lines[i])
        i += 1
    while result and not result[-1].strip():
        result.pop()
    return result


def flow_svg(title: str, nodes: list[tuple[str, str]]) -> str:
    width = 1600
    cols = 3
    card_w, card_h = 420, 130
    x_gap, y_gap = 105, 100
    rows = (len(nodes) + cols - 1) // cols
    height = 150 + rows * (card_h + y_gap)
    pos: list[tuple[int, int]] = []
    for i in range(len(nodes)):
        row, col = divmod(i, cols)
        if row % 2:
            col = cols - 1 - col
        pos.append((65 + col * (card_w + x_gap), 105 + row * (card_h + y_gap)))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img">',
        "<defs>",
        '<linearGradient id="flowPanel" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFFDF9"/><stop offset="1" stop-color="#EEE9E1"/></linearGradient>',
        '<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#B43A3A"/></marker>',
        '<filter id="shadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="6" stdDeviation="8" flood-color="#333" flood-opacity=".16"/></filter>',
        "</defs>",
        f'<rect width="{width}" height="{height}" fill="#FFFFFF"/>',
        f'<text x="800" y="52" text-anchor="middle" font-family="Yu Gothic, Noto Sans JP, sans-serif" font-size="28" font-weight="600" fill="#222">{html.escape(title)}</text>',
    ]
    for i in range(len(nodes) - 1):
        x1, y1 = pos[i]
        x2, y2 = pos[i + 1]
        if y1 == y2:
            start_x = x1 + card_w if x2 > x1 else x1
            end_x = x2 if x2 > x1 else x2 + card_w
            parts.append(f'<line x1="{start_x}" y1="{y1+65}" x2="{end_x}" y2="{y2+65}" stroke="#B43A3A" stroke-width="5" marker-end="url(#arrow)"/>')
        else:
            parts.append(f'<path d="M {x1+card_w/2} {y1+card_h} V {y2-28} H {x2+card_w/2} V {y2}" fill="none" stroke="#B43A3A" stroke-width="5" marker-end="url(#arrow)"/>')
    for (name, data), (x, y) in zip(nodes, pos):
        parts.extend([
            f'<rect x="{x}" y="{y}" width="{card_w}" height="{card_h}" rx="24" fill="url(#flowPanel)" stroke="#3A3A3A" stroke-width="4" filter="url(#shadow)"/>',
            f'<circle cx="{x+32}" cy="{y+65}" r="11" fill="#FFF0E1" stroke="#E06B00" stroke-width="4"/>',
            f'<circle cx="{x+card_w-32}" cy="{y+65}" r="11" fill="#E8F2FC" stroke="#2B76C4" stroke-width="4"/>',
            f'<text x="{x+card_w/2}" y="{y+52}" text-anchor="middle" font-family="Yu Gothic, Noto Sans JP, sans-serif" font-size="20" font-weight="600" fill="#222">{html.escape(name)}</text>',
            f'<text x="{x+card_w/2}" y="{y+88}" text-anchor="middle" font-family="Yu Gothic, Noto Sans JP, sans-serif" font-size="16" fill="#555">{html.escape(data)}</text>',
        ])
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sources: dict[str, tuple[str, list[Terminal], list[Terminal]]] = {}
    doc_matches: dict[Path, list[tuple[int, str]]] = {}
    doc_all_names: dict[Path, list[str]] = {}
    for path in sorted(DOCS.glob("*.md")):
        if path.name.startswith("10A_") or path.name.startswith("14_"):
            continue
        lines = strip_generated(path.read_text(encoding="utf-8").splitlines())
        full_text = "\n".join(lines)
        all_names = list(dict.fromkeys(normalize_vi_name(n) for n in re.findall(r"`([^`\n]+\.vi)`", full_text)))
        doc_all_names[path] = all_names
        matches: list[tuple[int, str]] = []
        for idx, line in enumerate(lines):
            if not line.startswith("#"):
                continue
            for raw_name in re.findall(r"`([^`]+\.vi)`", line):
                name = normalize_vi_name(raw_name)
                matches.append((idx, name))
                section = section_for(lines, idx)
                ins, outs = parse_terminals(section)
                score = len(ins) + len(outs)
                old = sources.get(name)
                if old is None or score > len(old[1]) + len(old[2]):
                    sources[name] = (path.name, ins, outs)
        # Some chapters define VI names in tables or prose instead of headings.
        # Generate a conservative diagram from the nearest surrounding section.
        for name in all_names:
            if name in sources:
                continue
            occurrence = next((i for i, line in enumerate(lines) if name in line), 0)
            heading = 0
            for i in range(occurrence, -1, -1):
                if lines[i].startswith("#"):
                    heading = i
                    break
            ins, outs = parse_terminals(section_for(lines, heading))
            sources[name] = (path.name, ins, outs)
        doc_matches[path] = matches

    for name, (source, ins, outs) in sources.items():
        (OUT / f"{slug(name)}.svg").write_text(svg_for_vi(name, source, ins, outs), encoding="utf-8")

    for flows in FLOW_SPECS.values():
        for filename, title, nodes in flows:
            (OUT / filename).write_text(flow_svg(title, nodes), encoding="utf-8")

    # Insert each image immediately below the VI heading. Repeat headings reuse one SVG.
    for path, matches in doc_matches.items():
        if not matches and not doc_all_names.get(path):
            continue
        lines = strip_generated(path.read_text(encoding="utf-8").splitlines())
        result: list[str] = []
        flows = FLOW_SPECS.get(path.name, [])
        inserted_flow = False
        i = 0
        by_index = {idx: name for idx, name in matches}
        while i < len(lines):
            line = lines[i]
            result.append(line)
            if not inserted_flow and flows and line.startswith("# "):
                for filename, title, _ in flows:
                    result.extend(["", MARKER, f"![{title}](./assets/vi-diagrams/{filename})"])
                inserted_flow = True
            if i in by_index:
                name = by_index[i]
                next_slice = "\n".join(lines[i + 1 : i + 5])
                if MARKER not in next_slice:
                    result.extend(["", MARKER, f"![{name} 入出力イメージ](./assets/vi-diagrams/{slug(name)}.svg)"])
            i += 1
        heading_names = {name for _, name in matches}
        remaining = [name for name in doc_all_names.get(path, []) if name not in heading_names]
        if remaining:
            result.extend(["", APPENDIX_START, "", "---", "", "## 章内で参照するVIの入出力イメージ", ""])
            for name in remaining:
                result.extend([
                    f"### `{name}`",
                    "",
                    MARKER,
                    f"![{name} 入出力イメージ](./assets/vi-diagrams/{slug(name)}.svg)",
                    "",
                ])
            result.append(APPENDIX_END)
        path.write_text("\n".join(result) + "\n", encoding="utf-8")

    index = [
        "# 14. VI入出力・公開API接続イメージ図",
        "",
        "**最終生成日：2026-07-26**",
        "",
        "中央にVI、左に入力、右に出力を配置し、`error in`／`error out`を必ず最下段へ固定したSVG一覧である。",
        "画像生成スキルで作成したデザイン原案を基準に、端子名・型・値を検索可能なベクター文字としてSVG化した。",
        "各章で確定していない端子は推測せず、`実VIで確認`／`確認待ち`と明示する。",
        "",
        "## 公開API・処理接続図",
        "",
    ]
    for flows in FLOW_SPECS.values():
        for filename, title, _ in flows:
            index.extend([f"### {title}", "", f"![{title}](./assets/vi-diagrams/{filename})", ""])
    index.extend(["## VI単体図", ""])
    for name, (source, _, _) in sorted(sources.items()):
        index.extend([f"### `{name}`", "", f"出典章：`{source}`", "", f"![{name} 入出力イメージ](./assets/vi-diagrams/{slug(name)}.svg)", ""])
    (DOCS / "14_VI入出力イメージ図.md").write_text("\n".join(index), encoding="utf-8")
    print(f"generated_vi={len(sources)} flow={sum(len(v) for v in FLOW_SPECS.values())}")


if __name__ == "__main__":
    main()
