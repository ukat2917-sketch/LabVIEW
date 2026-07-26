#!/usr/bin/env python3
"""Generate exact, case-by-case SVG diagrams for RAMScope_Init.vi."""

from __future__ import annotations

import html
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets" / "block-diagrams" / "ramscope-init"

COLORS = {
    "numeric": "#E06B00",
    "array": "#7D5BBE",
    "boolean": "#2F8F46",
    "error": "#C53B3B",
    "string": "#A34AA8",
    "structure": "#8A7C69",
    "data": "#2B76C4",
    "neutral": "#4B5563",
}


class Diagram:
    def __init__(self, title: str, breadcrumb: str, height: int = 900):
        self.width = 1800
        self.height = height
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{height}" '
            f'viewBox="0 0 {self.width} {height}" role="img" aria-labelledby="title desc">',
            f'<title id="title">{html.escape(title)}</title>',
            f'<desc id="desc">{html.escape(breadcrumb)}の実配線を示すLabVIEWブロックダイアグラム。</desc>',
            "<defs>",
            '<filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">'
            '<feDropShadow dx="0" dy="5" stdDeviation="7" flood-color="#333" flood-opacity=".14"/></filter>',
            '<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
            'markerHeight="7" orient="auto"><path d="M0 0 L10 5 L0 10z" fill="context-stroke"/></marker>',
            "</defs>",
            f'<rect width="{self.width}" height="{height}" fill="#FFFFFF"/>',
            f'<text x="900" y="48" text-anchor="middle" font-family="Yu Gothic, Noto Sans JP, sans-serif" '
            f'font-size="30" font-weight="700" fill="#202124">{html.escape(title)}</text>',
            f'<rect x="70" y="72" width="1660" height="50" rx="12" fill="#F4F1EA" stroke="#B9AD9B"/>',
            f'<text x="95" y="105" font-family="Yu Gothic, Noto Sans JP, sans-serif" font-size="18" '
            f'font-weight="600" fill="#51483D">Case階層: {html.escape(breadcrumb)}</text>',
        ]

    def text(self, x: float, y: float, value: str, size: int = 16, weight: int = 400,
             anchor: str = "start", color: str = "#252525") -> None:
        self.parts.append(
            f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
            f'font-family="Yu Gothic, Noto Sans JP, sans-serif" font-size="{size}" '
            f'font-weight="{weight}" fill="{color}">{html.escape(value)}</text>'
        )

    def multiline(self, x: float, y: float, value: str, width: int = 24, size: int = 16,
                  weight: int = 500, anchor: str = "middle", color: str = "#252525",
                  line_h: int = 23) -> None:
        lines: list[str] = []
        for paragraph in value.split("\n"):
            lines.extend(textwrap.wrap(paragraph, width=width, break_long_words=False) or [""])
        start = y - (len(lines) - 1) * line_h / 2
        for i, line in enumerate(lines):
            self.text(x, start + i * line_h, line, size, weight, anchor, color)

    def node(self, x: int, y: int, w: int, h: int, label: str, kind: str = "subvi",
             subtitle: str = "") -> None:
        fills = {
            "subvi": ("#FFF7D8", "#746122"),
            "parser": ("#EAF3FC", "#2B76C4"),
            "function": ("#F3F4F6", "#59636E"),
            "bundle": ("#F8EAF8", "#A34AA8"),
            "constant": ("#FFF0E1", "#E06B00"),
        }
        fill, stroke = fills[kind]
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="4"/>'
        )
        self.multiline(x + w / 2, y + h / 2 - (10 if subtitle else 0), label,
                       max(12, int(w / 12)), 17, 650)
        if subtitle:
            self.text(x + w / 2, y + h - 15, subtitle, 13, 400, "middle", "#555")

    def case(self, x: int, y: int, w: int, h: int, selector: str, state: str) -> None:
        self.parts.extend([
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="#FCFBF8" '
            f'stroke="{COLORS["structure"]}" stroke-width="5"/>',
            f'<rect x="{x + 28}" y="{y - 22}" width="420" height="44" rx="7" fill="#EEE8DD" '
            f'stroke="{COLORS["structure"]}" stroke-width="3"/>',
        ])
        self.text(x + 48, y + 7, f"{selector} Case：{state}", 17, 700, color="#51483D")
        self.parts.append(
            f'<polygon points="{x},{y + 74} {x - 17},{y + 91} {x},{y + 108} {x + 17},{y + 91}" '
            f'fill="#E8F7EC" stroke="{COLORS["boolean"]}" stroke-width="4"/>'
        )
        self.text(x + 22, y + 96, "selector", 13, 600, color=COLORS["boolean"])

    def loop(self, x: int, y: int, w: int, h: int, label: str = "For Loop") -> None:
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#FFFDF7" '
            f'stroke="#7F6A45" stroke-width="6"/>'
        )
        self.text(x + 24, y + 32, label, 18, 700, color="#604D2F")
        self.text(x + 22, y + 65, "N：未配線（自動指標付け配列の16要素で反復）", 14, 500, color="#604D2F")
        self.parts.append(
            f'<rect x="{x - 12}" y="{y + 95}" width="24" height="24" fill="#F4E5CA" '
            f'stroke="#7F6A45" stroke-width="3"/>'
        )
        self.text(x + 21, y + 114, "自動指標付け", 13, 500, color="#604D2F")

    def terminal(self, x: int, y: int, label: str, kind: str, side: str = "left") -> None:
        color = COLORS[kind]
        self.parts.append(f'<circle cx="{x}" cy="{y}" r="11" fill="#FFF" stroke="{color}" stroke-width="5"/>')
        # Keep labels inside the canvas: inputs read above/right, outputs above/left.
        dx = 18 if side == "left" else -18
        anchor = "start" if side == "left" else "end"
        self.text(x + dx, y - 14, label, 15, 600, anchor, color)

    def tunnel(self, x: int, y: int, label: str, kind: str, side: str = "right") -> None:
        color = COLORS[kind]
        self.parts.append(
            f'<rect x="{x - 10}" y="{y - 10}" width="20" height="20" fill="#FFF" '
            f'stroke="{color}" stroke-width="4"/>'
        )
        dx = -17 if side == "left" else 17
        anchor = "end" if side == "left" else "start"
        self.text(x + dx, y + 6, label, 14, 600, anchor, color)

    def wire(self, points: list[tuple[int, int]], kind: str, label: str = "",
             dashed: bool = False, arrow: bool = False) -> None:
        color = COLORS[kind]
        path = "M " + " L ".join(f"{x} {y}" for x, y in points)
        dash = ' stroke-dasharray="10 8"' if dashed else ""
        marker = ' marker-end="url(#arrow)"' if arrow else ""
        self.parts.append(
            f'<path d="{path}" fill="none" stroke="{color}" stroke-width="6" '
            f'stroke-linecap="round" stroke-linejoin="round"{dash}{marker}/>'
        )
        for x, y in points[1:-1]:
            self.parts.append(f'<circle cx="{x}" cy="{y}" r="5" fill="{color}"/>')
        if label:
            mid = points[len(points) // 2]
            self.text(mid[0], mid[1] - 11, label, 13, 600, "middle", color)

    def note(self, x: int, y: int, w: int, text: str, tone: str = "info") -> None:
        fill, stroke = ("#EEF5FC", "#2B76C4") if tone == "info" else ("#FFF2F2", "#C53B3B")
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="64" rx="12" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="2"/>'
        )
        self.multiline(x + w / 2, y + 34, text, max(18, int(w / 13)), 14, 550, color="#333")

    def save(self, filename: str) -> None:
        self.parts.append("</svg>")
        (OUT / filename).write_text("\n".join(self.parts) + "\n", encoding="utf-8")


def common_front() -> None:
    d = Diagram("RAMScope_Init.vi — 01 共通前段配線", "Case Structure外部 → Parser error.status selector", 920)
    d.node(240, 245, 260, 125, "RS_DLL_GT150AllInit.vi")
    d.node(610, 245, 280, 125, "RS_DLL_GT150GetSysInfo.vi")
    d.node(1020, 225, 300, 165, "Parse_SYSINFO_Array.vi", "parser")
    d.terminal(90, 275, "UnitNo I32", "numeric")
    d.terminal(90, 360, "Byte Order", "data")
    d.terminal(90, 760, "error in", "error")
    d.wire([(90, 275), (180, 275), (180, 275), (240, 275)], "numeric", "UnitNo")
    d.wire([(180, 275), (180, 315), (610, 315)], "numeric", "UnitNo")
    d.wire([(90, 360), (960, 360), (960, 330), (1020, 330)], "data", "Byte Order")
    d.wire([(90, 760), (370, 760), (370, 370), (370, 370)], "error")
    d.wire([(500, 345), (555, 345), (555, 345), (610, 345)], "error", "AllInit error out")
    d.wire([(890, 285), (960, 285), (960, 280), (1020, 280)], "array", "SYSINFO Raw U8[960]")
    d.wire([(890, 345), (975, 345), (975, 365), (1020, 365)], "error", "GetSysInfo error out")
    outputs = [
        ("Module List", "array", 180), ("MdlNo_RAM", "numeric", 250),
        ("MdlNo_CAN", "numeric", 320), ("Endian_RAM", "data", 390),
        ("RAM Module Found?", "boolean", 460), ("CAN Module Found?", "boolean", 530),
    ]
    parser_y = [245, 270, 295, 320, 345, 370]
    for (label, kind, y), source_y in zip(outputs, parser_y):
        d.terminal(1690, y, label, kind, "right")
        d.wire([(1320, source_y), (1410, source_y), (1410, y), (1690, y)], kind, label)
    d.case(1450, 620, 260, 170, "Parser error.status", "True / Falseは別図")
    d.wire([(1320, 380), (1370, 380), (1370, 711), (1433, 711)], "boolean", "Unbundle status")
    d.wire([(1320, 760), (1710, 760)], "error", "Parser error out")
    d.save("01-common-front.svg")


def parser_true() -> None:
    d = Diagram("RAMScope_Init.vi — 02 Parser error Case：True",
                "Parser error.status=True（Parserまでにエラーあり）", 780)
    d.case(180, 190, 1440, 430, "Parser error.status", "True")
    d.terminal(90, 300, "I32 0", "numeric")
    d.terminal(90, 375, "I32 16", "numeric")
    d.terminal(90, 550, "Parser error out", "error")
    d.node(500, 275, 270, 130, "Initialize Array", "function", "element=0 / size=16")
    d.tunnel(1620, 335, "SlotErr[16]", "array")
    d.tunnel(1620, 550, "error", "error")
    d.wire([(90, 300), (500, 300)], "numeric", "element")
    d.wire([(90, 375), (500, 375)], "numeric", "dimension size")
    d.wire([(770, 340), (1620, 340)], "array", "I32ゼロ配列16要素")
    d.wire([(90, 550), (1620, 550)], "error", "元Parser errorを保持")
    d.note(850, 260, 570, "PGT_SetMdlConfig.viおよびSlotErr走査For Loopは配置しない", "warn")
    d.save("02-parser-error-true.svg")


def parser_false() -> None:
    d = Diagram("RAMScope_Init.vi — 03 Parser error Case：False",
                "Parser error.status=False → RAM Module Found? selector", 720)
    d.case(160, 185, 1480, 390, "Parser error.status", "False")
    d.terminal(90, 315, "RAM Module Found?", "boolean")
    d.terminal(90, 500, "Parser正常 error out", "error")
    d.case(600, 260, 780, 220, "RAM Module Found?", "True / Falseは別図")
    d.wire([(90, 315), (583, 351)], "boolean", "Case selector")
    d.wire([(90, 500), (520, 500), (520, 445), (600, 445)], "error", "基準error cluster")
    d.note(690, 345, 600, "False：RAM未検出エラー生成　／　True：PGT_SetMdlConfig実行")
    d.save("03-parser-error-false.svg")


def ram_not_found() -> None:
    d = Diagram("RAMScope_Init.vi — 04 RAM Module Found? Case：False",
                "Parser error=False → RAM Module Found?=False", 930)
    d.case(130, 180, 1540, 610, "RAM Module Found?", "False")
    d.node(320, 255, 250, 115, "Initialize Array", "function", "I32 0 × 16")
    d.node(700, 250, 340, 145, "Format Into String", "function",
           "UnitNo=%d / MdlNo_RAM=%d")
    d.node(1150, 245, 300, 155, "Bundle By Name", "bundle",
           "status / code / source")
    d.terminal(70, 280, "I32 0", "numeric")
    d.terminal(70, 345, "I32 16", "numeric")
    d.terminal(70, 470, "UnitNo", "numeric")
    d.terminal(70, 540, "MdlNo_RAM", "numeric")
    d.terminal(70, 690, "Parser正常 error", "error")
    d.wire([(70, 280), (320, 280)], "numeric", "element")
    d.wire([(70, 345), (320, 345)], "numeric", "size")
    d.wire([(570, 310), (610, 310), (610, 215), (1580, 215), (1580, 430), (1670, 430)],
           "array", "SlotErr[16]=0")
    d.wire([(70, 470), (660, 470), (660, 305), (700, 305)], "numeric", "1個目の%d")
    d.wire([(70, 540), (680, 540), (680, 350), (700, 350)], "numeric", "2個目の%d")
    d.wire([(1040, 322), (1100, 322), (1100, 355), (1150, 355)], "string", "source")
    d.wire([(70, 690), (1090, 690), (1090, 280), (1150, 280)], "error", "基準クラスタ")
    d.terminal(1090, 460, "True", "boolean")
    d.terminal(1090, 525, "I32 -700140", "numeric")
    d.wire([(1090, 460), (1150, 310)], "boolean", "status")
    d.wire([(1090, 525), (1120, 525), (1120, 335), (1150, 335)], "numeric", "code")
    d.wire([(1450, 325), (1670, 325)], "error", "生成error")
    d.tunnel(1670, 325, "error", "error")
    d.tunnel(1670, 430, "SlotErr[16]", "array")
    d.note(620, 610, 760,
           "source全文：RAMScope_Init.vi: RAM monitor module was not found. "
           "PGT configuration was not executed. UnitNo=%d, MdlNo_RAM=%d")
    d.note(1210, 520, 340, "このCaseにPGT Wrapperは配置しない", "warn")
    d.save("04-ram-module-found-false.svg")


def ram_found() -> None:
    d = Diagram("RAMScope_Init.vi — 05 RAM Module Found? Case：True",
                "Parser error=False → RAM Module Found?=True → PGT error.status selector", 800)
    d.case(160, 180, 1480, 480, "RAM Module Found?", "True")
    d.node(620, 270, 410, 150, "RS_DLL_GT150PGT_SetMdlConfig.vi")
    d.terminal(80, 310, "UnitNo", "numeric")
    d.terminal(80, 520, "Parser正常 error out", "error")
    d.wire([(80, 310), (620, 310)], "numeric", "UnitNo")
    d.wire([(80, 520), (540, 520), (540, 390), (620, 390)], "error", "error in")
    d.tunnel(1640, 315, "SlotErr[16]", "array")
    d.wire([(1030, 315), (1640, 315)], "array", "Wrapper SlotErrを分岐")
    d.case(1230, 440, 320, 150, "PGT error.status", "True / Falseは別図")
    d.wire([(1030, 390), (1130, 390), (1130, 531), (1213, 531)], "boolean", "Unbundle status")
    d.wire([(1030, 520), (1640, 520)], "error", "Wrapper error out")
    d.save("05-ram-module-found-true.svg")


def pgt_true() -> None:
    d = Diagram("RAMScope_Init.vi — 06 PGT error Case：True",
                "Parser error=False → RAM Found=True → PGT error.status=True", 680)
    d.case(180, 180, 1440, 340, "PGT error.status", "True")
    d.terminal(90, 380, "PGT Wrapper error out", "error")
    d.tunnel(1620, 380, "error", "error")
    d.wire([(90, 380), (1620, 380)], "error", "Wrapper errorをそのまま保持")
    d.note(570, 250, 660, "SlotErr走査For Loopと-700141エラー生成は配置しない", "warn")
    d.save("06-pgt-error-true.svg")


def pgt_false_loop() -> None:
    d = Diagram("RAMScope_Init.vi — 07 PGT error Case：False／SlotErr走査",
                "Parser error=False → RAM Found=True → PGT error=False → For Loop", 1050)
    d.case(95, 170, 1610, 750, "PGT error.status", "False")
    d.loop(330, 285, 1160, 500, "For Loop：SlotErr[16]を先頭から走査")
    d.terminal(55, 380, "SlotErr[16]", "array")
    d.wire([(55, 380), (318, 380)], "array", "自動指標付け")
    d.terminal(55, 505, "I32 -1", "numeric")
    d.terminal(55, 580, "I32 0", "numeric")
    d.terminal(55, 700, "PGT正常 error", "error")
    for y, label in [(505, "First Slot Index"), (580, "First Slot Error"), (700, "error")]:
        kind = "error" if label == "error" else "numeric"
        d.wire([(55, y), (330, y)], kind, label)
        d.tunnel(330, y, f"{label} SR左", kind)
        d.tunnel(1490, y, f"{label} SR右", kind, "right")
    d.node(530, 365, 245, 110, "Not Equal?", "function", "SlotErr != 0")
    d.node(530, 525, 245, 110, "Equal?", "function", "First Index == -1")
    d.node(880, 445, 210, 120, "AND", "function")
    d.case(1170, 390, 250, 235, "First Nonzero?", "True / False")
    d.wire([(330, 380), (470, 380), (470, 420), (530, 420)], "numeric", "現在SlotErr")
    d.wire([(330, 505), (470, 505), (470, 580), (530, 580)], "numeric", "現在First Index")
    d.wire([(775, 420), (830, 420), (830, 475), (880, 475)], "boolean")
    d.wire([(775, 580), (830, 580), (830, 535), (880, 535)], "boolean")
    d.wire([(1090, 505), (1153, 481)], "boolean", "First Nonzero?")
    d.note(450, 820, 910,
           "Shift Registerは3本。Index=-1、Error=0、error=PGT正常errorで初期化し、"
           "各反復で現在値を次へ渡す。")
    d.save("07-pgt-error-false-loop.svg")


def first_nonzero(state: str) -> None:
    is_true = state == "True"
    number = "08" if is_true else "09"
    title = f"RAMScope_Init.vi — {number} First Nonzero? Case：{state}"
    d = Diagram(title,
                f"Parser error=False → RAM Found=True → PGT error=False → First Nonzero?={state}", 800)
    d.case(180, 180, 1440, 470, "First Nonzero?", state)
    d.terminal(90, 300, "First Slot Index SR左", "numeric")
    d.terminal(90, 570, "error SR左", "error")
    d.tunnel(1620, 300, "First Slot Index SR右", "numeric")
    d.tunnel(1620, 390, "First Slot Error SR右", "numeric")
    d.tunnel(1620, 570, "error SR右", "error")
    if is_true:
        d.terminal(90, 390, "現在SlotErr I32", "numeric")
        d.terminal(90, 480, "反復端子 i", "numeric")
        d.wire([(90, 480), (760, 480), (760, 300), (1620, 300)], "numeric", "最初の非ゼロ位置 i を保存")
        d.wire([(90, 390), (1620, 390)], "numeric", "最初の非ゼロSlotErrを保存")
        d.note(520, 515, 760, "条件：(現在SlotErr != 0) AND (First Slot Index == -1)")
    else:
        d.terminal(90, 390, "First Slot Error SR左", "numeric")
        d.wire([(90, 300), (1620, 300)], "numeric", "現在値を維持（-1へ戻さない）")
        d.wire([(90, 390), (480, 390), (480, 430), (1560, 430), (1560, 390), (1620, 390)],
               "numeric", "First Slot Errorの現在値を維持")
        d.note(520, 500, 760, "非ゼロ未検出、または既に最初の非ゼロを保存済み")
    d.wire([(90, 570), (1620, 570)], "error", "両Caseともerrorをそのまま通過")
    d.save(f"{number}-first-nonzero-{state.lower()}.svg")


def slot_error_found(state: str) -> None:
    is_true = state == "True"
    number = "11" if is_true else "10"
    title = f"RAMScope_Init.vi — {number} Slot Error Found? Case：{state}"
    d = Diagram(title,
                f"Parser error=False → RAM Found=True → PGT error=False → Slot Error Found?={state}", 900)
    d.case(150, 180, 1500, 570, "Slot Error Found?（First Slot Index != -1）", state)
    d.terminal(70, 590, "PGT正常 error", "error")
    d.tunnel(1650, 590, "error", "error")
    if not is_true:
        d.wire([(70, 590), (1650, 590)], "error", "全Slot正常：PGT正常errorを出力")
        d.note(560, 320, 680, "First Slot Index == -1：非ゼロSlotErrなし")
    else:
        d.node(430, 265, 380, 145, "Format Into String", "function",
               "SlotIndex=%d / SlotError=%d")
        d.node(1040, 260, 330, 165, "Bundle By Name", "bundle",
               "status=True / code=-700141 / source")
        d.terminal(70, 285, "First Slot Index", "numeric")
        d.terminal(70, 380, "First Slot Error", "numeric")
        d.terminal(950, 455, "True", "boolean")
        d.terminal(950, 520, "I32 -700141", "numeric")
        d.wire([(70, 285), (430, 300)], "numeric", "1個目の%d")
        d.wire([(70, 380), (430, 370)], "numeric", "2個目の%d")
        d.wire([(810, 335), (980, 335), (980, 380), (1040, 380)], "string", "source")
        d.wire([(70, 590), (930, 590), (930, 300), (1040, 300)], "error", "基準クラスタ")
        d.wire([(950, 455), (1010, 455), (1010, 330), (1040, 330)], "boolean", "status")
        d.wire([(950, 520), (1025, 520), (1025, 355), (1040, 355)], "numeric", "code")
        d.wire([(1370, 342), (1510, 342), (1510, 590), (1650, 590)], "error", "Slot error")
        d.note(400, 645, 1000,
               "source全文：RAMScope_Init.vi: PGT module configuration reported a slot error. "
               "SlotIndex=%d, SlotError=%d")
    d.save(f"{number}-slot-error-found-{state.lower()}.svg")


def final_outputs() -> None:
    d = Diagram("RAMScope_Init.vi — 12 最終error・Status出力",
                "各内側Case → RAM Module Found? Case → Parser error Case → Error_To_TestStatus", 850)
    d.node(180, 255, 300, 125, "Slot Error Found? Case", "function")
    d.node(600, 255, 320, 125, "RAM Module Found? Case", "function")
    d.node(1040, 255, 300, 125, "Parser error Case", "function")
    d.node(1090, 520, 330, 145, "Error_To_TestStatus.vi", "subvi")
    d.terminal(90, 575, 'String "RAMScope"', "string")
    d.wire([(480, 320), (600, 320)], "error", "内側error tunnel")
    d.wire([(920, 320), (1040, 320)], "error", "RAM Case error tunnel")
    d.wire([(1340, 320), (1510, 320), (1510, 470), (900, 470), (900, 600), (1090, 600)],
           "error", "Parser Case最終error → error in")
    d.wire([(90, 575), (1090, 575)], "string", "Device Name")
    outputs = [("Status", "data", 510), ("TestError", "data", 590), ("error out", "error", 730)]
    for label, kind, y in outputs:
        d.terminal(1710, y, label, kind, "right")
        source_y = 555 if label == "Status" else 600 if label == "TestError" else 635
        d.wire([(1420, source_y), (1580, source_y), (1580, y), (1710, y)], kind, label)
    d.note(180, 420, 720,
           "Module List、MdlNo_RAM、MdlNo_CAN、Endian_RAM、Found BooleanはParserから直接対応出力へ接続済み。")
    d.note(990, 420, 520,
           "errorトンネルは内側から外側へ順に接続し、元の原因を上書きしない。", "warn")
    d.save("12-final-outputs.svg")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    common_front()
    parser_true()
    parser_false()
    ram_not_found()
    ram_found()
    pgt_true()
    pgt_false_loop()
    first_nonzero("True")
    first_nonzero("False")
    slot_error_found("False")
    slot_error_found("True")
    final_outputs()
    print("generated=12")


if __name__ == "__main__":
    main()
