#!/usr/bin/env python3
"""Generate slide-ready NI license selection diagrams as exact SVG text."""

from __future__ import annotations

import html
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets" / "licensing"
FONT = "Noto Sans JP Thin, Noto Sans JP, Yu Gothic, Meiryo, sans-serif"


def txt(x, y, value, size=24, weight=400, anchor="start", color="#252525"):
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="{FONT}" '
        f'font-size="{size}" font-weight="{weight}" fill="{color}">{html.escape(value)}</text>'
    )


def multiline(x, y, value, width=24, size=22, weight=400, anchor="middle",
              color="#252525", line_h=30):
    lines = []
    for paragraph in value.split("\n"):
        lines.extend(textwrap.wrap(paragraph, width=width, break_long_words=False) or [""])
    return "\n".join(
        txt(x, y + i * line_h, line, size, weight, anchor, color)
        for i, line in enumerate(lines)
    )


def rounded(x, y, w, h, fill="#FFFFFF", stroke="#555", sw=3, rx=18):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def base(title, subtitle):
    return [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080" role="img">',
        '<rect width="1920" height="1080" fill="#FFFFFF"/>',
        txt(70, 82, title, 42, 700),
        txt(70, 125, subtitle, 21, 400, color="#5B6168"),
        '<line x1="0" y1="150" x2="1920" y2="150" stroke="#B51225" stroke-width="7"/>',
    ]


def icon(cx, cy, symbol, color):
    size = 19 if len(symbol) > 1 else 38
    return "\n".join([
        f'<circle cx="{cx}" cy="{cy}" r="38" fill="{color}"/>',
        txt(cx, cy + 7, symbol, size, 700, "middle", "#FFFFFF"),
    ])


def decision_diagram():
    p = base(
        "実験PC向け LabVIEW／TestStand ライセンス選定",
        "結論：完成済みEXEの実行はLabVIEW開発ライセンス不要。TestStandは用途ごとに実験PC単位で選択する。",
    )
    p += [
        rounded(595, 185, 730, 100, "#FFF8F8", "#B51225", 4, 24),
        icon(660, 235, "?", "#B51225"),
        txt(985, 250, "実験PCで何をしたい？", 36, 700, "middle"),
        '<path d="M960 285 V330 M235 330 H1685 M235 330 V365 M720 330 V365 M1200 330 V365 M1685 330 V365" '
        'fill="none" stroke="#B51225" stroke-width="5"/>',
    ]
    cards = [
        (50, "EXE", "完成済みLabVIEW\nEXEを実行",
         "VIの配置・処理順は変更しない", "LabVIEW Run-Time Engine", "0円",
         "TestStandを使わない構成", "#078455"),
        (535, "RUN", "完成済みTestStand\nシーケンスを実行",
         "定義済みループ・条件・レポートを実行", "TestStand Base Deployment Engine", "116,000円／PC・永続",
         "シーケンス編集・開発は不可", "#078455"),
        (1020, "DBG", "配備先でデバッグ\n軽微な不具合修正",
         "配備済みシステムの原因調査", "TestStand Debug Deployment Environment", "438,000円／PC・永続",
         "新機能追加・本格開発は不可", "#D97706"),
        (1505, "DEV", "VI／シーケンスを\n開発・変更",
         "ステップ追加・並べ替え・機能変更", "開発ライセンス", "用途により年額／永続",
         "TestStand Development＋必要なLabVIEW版", "#B51225"),
    ]
    for x, symbol, title, action, license_name, cost, note, color in cards:
        p += [
            rounded(x, 365, 420, 250, "#FFFFFF", color, 4, 22),
            icon(x + 55, 425, symbol, color),
            multiline(x + 250, 400, title, 15, 20, 700, "middle", color, 27),
            multiline(x + 210, 520, action, 23, 19, 400, "middle", "#444", 27),
            f'<path d="M{x + 210} 615 V650" stroke="{color}" stroke-width="5"/>',
            f'<polygon points="{x + 198},650 {x + 222},650 {x + 210},667" fill="{color}"/>',
            rounded(x, 667, 420, 245, "#F8FAFB", color, 3, 20),
            txt(x + 210, 710, "実験PCに必要", 18, 700, "middle", color),
            multiline(x + 210, 758, license_name, 25, 22, 700, "middle", "#222", 30),
            txt(x + 210, 840, cost, 23, 700, "middle", color),
            multiline(x + 210, 880, note, 28, 16, 500, "middle", "#555", 24),
        ]
    p += [
        rounded(70, 950, 1780, 80, "#FFF9E8", "#C79622", 2, 14),
        txt(105, 986, "重要", 20, 700, color="#9A6700"),
        txt(190, 986,
            "入力条件違いのループは、TestStandで実装した場合のみTestStandが必要。LabVIEW EXE内へ実装すればTestStandなしでも実行可能。",
            20, 600),
        txt(190, 1015,
            "Visionなど一部モジュール／ツールキットは別途Runtimeライセンスが必要な場合がある。価格は添付NI購入画面の参考値で、正式見積を優先。",
            16, 400, color="#555"),
        "</svg>",
    ]
    (OUT / "experiment-pc-license-selection.svg").write_text("\n".join(p), encoding="utf-8")


def cost_diagram():
    p = base(
        "実験PCで行う作業別の最小ライセンス費用",
        "参考価格：添付のNI購入画面。公開価格は変動するため、購入時はNI／社内EA契約の正式見積を優先する。",
    )
    headers = ["実験PCで行うこと", "LabVIEW", "TestStand", "最小参考費用／PC", "できないこと・注意"]
    widths = [430, 360, 420, 300, 340]
    xs = [35]
    for w in widths[:-1]:
        xs.append(xs[-1] + w)
    y0 = 190
    for x, w, h in zip(xs, widths, headers):
        p += [rounded(x, y0, w, 70, "#3F4246", "#FFFFFF", 1, 0), txt(x + w/2, y0 + 45, h, 19, 700, "middle", "#FFFFFF")]
    rows = [
        ("完成済みLabVIEW EXEだけ実行", "Run-Time Engine\n無料", "不要", "0円", "VI編集不可。\n必要なドライバと同一版・\nbitnessのRTEを導入。"),
        ("完成済みTestStandシーケンスを実行", "Run-Time Engine\n原則無料", "Base Deployment Engine", "116,000円・永続", "定義済み条件変更・ループ実行は可。\nSequence Editorでの開発は不可。"),
        ("配備先でデバッグ／軽微修正", "Debug Deploymentの範囲", "Debug Deployment\nEnvironment", "438,000円・永続", "配備済みシステムの不具合修正向け。\n機能追加や本格開発は不可。"),
        ("TestStandシーケンスを追加・並べ替え", "コードモジュールを\n変更しないなら不要", "Development System", "336,000円／年\nまたは1,176,000円・永続", "TestStandの開発・編集が可能。\n実験PCを開発機として扱う。"),
        ("VIを編集する", "Base 87,000円／年～", "TestStand不使用なら不要", "87,000円／年～", "使用関数・ツールキットにより\nFull／Professionalが必要。\nBaseだけではEXEビルド不可。"),
        ("VI編集＋EXEを再ビルド", "Professional\nまたはBase／Full＋\nApplication Builder", "必要に応じ\nDevelopment System", "Professional\n380,000円／年～", "LabVIEWとTestStand双方を\n変更する場合、両方の開発権が必要。"),
        ("LabVIEW＋TestStandを一式開発", "LabVIEW Professionalを含む", "Development Systemを含む", "LabVIEW+ Suite\n569,000円／年\nまたは1,992,000円・永続", "社内EA契約がある場合は\n契約価格・利用条件を優先。"),
    ]
    row_h = 108
    y = y0 + 70
    for i, row in enumerate(rows):
        fill = "#F7F9FA" if i % 2 == 0 else "#FFFFFF"
        for x, w, value in zip(xs, widths, row):
            p.append(rounded(x, y, w, row_h, fill, "#C9CDD1", 1, 0))
            p.append(multiline(x + w/2, y + 37, value, max(13, int(w/17)), 17, 600 if x == xs[0] else 400, "middle", "#242424", 23))
        y += row_h
    p += [
        txt(45, 1050,
            "価格注記：表示額は税別とみられる参考値。NIサイトは地域・契約・サービス条件で変動。Base Deployment／Debug Deploymentは実験PCごとに必要。",
            15, 400, color="#555"),
        "</svg>",
    ]
    (OUT / "experiment-pc-license-cost-table.svg").write_text("\n".join(p), encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    decision_diagram()
    cost_diagram()
    print("generated=2")


if __name__ == "__main__":
    main()
