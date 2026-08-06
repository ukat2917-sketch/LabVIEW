from __future__ import annotations

from pathlib import Path
import re
import sys

MAIN_PATH = Path("docs/10_RAMScope実装方針.md")
DETAIL_PATH = Path("docs/10R_RAMScope_Read_vi_作成手順.md")
README_PATH = Path("README.md")

NOTE_BLOCK = """
**Read詳細統合日：2026-08-06**

> 2026-07-26時点の本文は削除・要約・置換せず、そのまま保持する。
> `RAMScope_Read.vi`の詳細作成手順と`PoC_RAMScope_Main.vi`の追加配線は、該当節へ追記する形で統合する。
"""

POC_BLOCK = r'''

<!-- ramscope-poc-read-wiring-merged-start -->
#### 10.13.1.1 `RAMScope_Read.vi`追加端子とPoC配線（追記統合）

本項は、前項までの`PoC_RAMScope_Main.vi`本文を残したまま、`GetBufferDataNum`対応後に追加されたRead端子と表示器だけを補足する。

##### A. フロントパネル入力を整理する

1. 旧`MaxDataNum`制御器は削除せず、ラベルを`RequestedDataNum Limit`へ変更する。
2. `RequestedDataNum Limit`の表現形式をI32にする。
3. この値は1回のReadで要求してよいPacket数の上限であり、Byte数ではない。
4. `RAMScope_Read.vi / Max Buffer Bytes`端子を右クリックし、`作成 → 制御器`でI64数値制御器を作る。
5. ラベルを`Max Buffer Bytes`とし、0より大きい値を設定する。PoC初期値例は`268435456`byte（256MiB）とする。

```text
RequestedDataNum Limit I32
  = 1回に要求するPacket数の上限

Max Buffer Bytes I64
  = Read VIが1回に確保してよいRaw BufferのByte上限

Required Bytes I64
  = Read VI内部でRequestedDataNumとPacket Sizeから計算する値
```

##### B. Read VIへ入力を接続する

```text
PoC UnitNo I32 ─────────────────→ RAMScope_Read.vi / UnitNo
Init.MdlNo_RAM I32 ─────────────→ RAMScope_Read.vi / MdlNo
PoC RequestedDataNum Limit I32 ─→ RAMScope_Read.vi / RequestedDataNum Limit
PoC Channel List ───────────────→ RAMScope_Read.vi / Channel List
PoC Byte Order ─────────────────→ RAMScope_Read.vi / Byte Order
PoC Max Buffer Bytes I64 ───────→ RAMScope_Read.vi / Max Buffer Bytes
Sequence後のerror wire ─────────→ RAMScope_Read.vi / error in
```

`Max Buffer Bytes`は`RS_DLL_GT150GetBufferDataNum.vi`へ接続しない。Read VI内部のRequired Bytes上限判定にだけ使用する。

##### C. Read VIの出力表示器を追加する

```text
RAMScope_Read.vi / AvailableDataNum ─→ PoC AvailableDataNum I32
RAMScope_Read.vi / RequestedDataNum ─→ PoC RequestedDataNum I32
RAMScope_Read.vi / Raw Buffer ────────→ PoC Raw Buffer U8[]
RAMScope_Read.vi / DataNum ───────────→ PoC DataNum I32
RAMScope_Read.vi / LostDataNum ───────→ PoC LostDataNum I32
RAMScope_Read.vi / Packets ───────────→ PoC Packets[]
```

これらの出力はRead VIの近くで表示器へ直接接続し、Stop、Release、Cleanup、Close Caseを通さない。

##### D. Packet件数はI32、Byte数計算だけI64にする

```text
GetBufferDataNum
  → AvailableDataNum I32

RequestedDataNum Limit I32
  → Min & Max
  → RequestedDataNum I32
      ├─ GetBufferData / pDataNum入力
      ├─ DataNum範囲比較
      └─ To 64-bit Integer
           → Required Bytes計算
```

`RequestedDataNum Limit`だけを先にI64化してMin & Maxへ入れない。多態関数（入力型に合わせて出力型が変わる関数）にI64が混ざると、`RequestedDataNum`までI64になるためである。

`AvailableDataNum < 0`を先にエラー処理する構造では、要求数は次でよい。

```text
RequestedDataNum I32
= min(AvailableDataNum I32, RequestedDataNum Limit I32)
```

確定後の`RequestedDataNum`だけをI64へ変換する。

```text
Packet Size I64
= I64(ChNum) × I64(4) + I64(12)

Required Bytes I64
= I64(RequestedDataNum) × Packet Size I64
```

##### E. PoCで確認する関係

```text
0 <= DataNum <= RequestedDataNum
RequestedDataNum <= RequestedDataNum Limit
RequestedDataNum <= AvailableDataNum
Required Bytes <= Max Buffer Bytes
```

`DataNum`は`GetBufferData`が実際に返したPacket数である。`RequestedDataNum`以下であることを確認する。`RequestedDataNum`はMin演算により既に`AvailableDataNum`以下なので、DataNumをAvailableDataNumと重複比較する必要はない。

##### F. Connect成功履歴を防御的に更新する場合

既存本文の成功判定を維持したうえで、実機接続数も条件へ加える場合は次を使用する。

```text
Connected?
= NOT(RAMScope_Connect.vi.error out.status)
  AND UnitNum > 0
```

これにより、DLL呼出し自体は正常でも`UnitNum=0`の状態を接続成功として記録しない。

##### G. 追加単体確認

- `AvailableDataNum=0`では正常な空データになる。
- `AvailableDataNum < RequestedDataNum Limit`ではAvailableDataNumが要求数になる。
- `AvailableDataNum > RequestedDataNum Limit`ではLimitが要求数になる。
- `RequestedDataNum`はGetBufferDataの`pDataNum`へI32で入る。
- Required Bytes計算では乗算前に両入力がI64になっている。
- `Max Buffer Bytes=0`は入力不正になる。
- `DataNum<0`または`DataNum>RequestedDataNum`は`-700164`になる。
- `Parsed Packet Count != DataNum`は`-700165`になる。
<!-- ramscope-poc-read-wiring-merged-end -->
'''


def require_once(text: str, marker: str, label: str) -> None:
    count = text.count(marker)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one marker, found {count}: {marker!r}")


def convert_detail_headings(detail: str) -> str:
    start = "## 0. 実現したい機能とVIの責務"
    require_once(detail, start, "10R start")
    body = detail[detail.index(start):].rstrip()
    converted: list[str] = []
    for line in body.splitlines():
        if line.startswith("#### "):
            converted.append(f"**{line[5:]}**")
        elif line.startswith("### "):
            converted.append("###### " + line[4:])
        elif line.startswith("## "):
            converted.append("##### " + line[3:])
        else:
            converted.append(line)
    return "\n".join(converted)


def update_readme(readme: str) -> str:
    readme = re.sub(
        r"> RAMScopeの環境準備、DLLラッパ、構造体生成、Parser、公開API、PoCは\[10_RAMScope実装方針\.md\]\(\./docs/10_RAMScope実装方針\.md\)を上位正本とし、`RAMScope_Read\.vi`の端子・Case・配線単位の詳細は\[10R_RAMScope_Read_vi_作成手順\.md\]\(\./docs/10R_RAMScope_Read_vi_作成手順\.md\)を使用する。",
        "> RAMScopeの環境準備、DLLラッパ、構造体生成、Parser、公開API、Read詳細手順、PoCは[10_RAMScope実装方針.md](./docs/10_RAMScope実装方針.md)を唯一の正本として使用する。",
        readme,
    )
    readme = re.sub(r"^  ├─ 10R RAMScope_Read\.vi詳細作成手順\n", "", readme, flags=re.MULTILINE)
    readme = readme.replace(
        "RAMScope実装では旧`10A`、`10B`、`10B-1`から`10B-4`を参照しない。第10章を上位正本とし、`RAMScope_Read.vi`の詳細作業だけは子文書`10R`を併用する。",
        "RAMScope実装では旧`10A`、`10B`、`10B-1`から`10B-4`を参照しない。環境準備から`RAMScope_Read.vi`の詳細作業、PoCまで第10章だけを使用する。",
    )
    readme = re.sub(r"^\| 10R \|.*\n", "", readme, flags=re.MULTILINE)
    return readme


def main() -> int:
    original = MAIN_PATH.read_text(encoding="utf-8")
    detail = DETAIL_PATH.read_text(encoding="utf-8")

    required = [
        "## 10.4 環境準備・DLL疎通確認",
        "## 10.8 薄いDLLラッパVI 18個",
        "## 10.9 数値変換・構造体Builder",
        "## 10.10 Parser",
        "## 10.11 公開API 11個",
        "## 10.12 LabVIEW側TDMS保存VI",
        "## 10.13 通信確認PoC・ロギングPoC・TestStand",
        "## 10.14 単体試験・実機PoC・完了判定",
    ]
    missing = [item for item in required if item not in original]
    if missing:
        raise RuntimeError(f"Original chapter is incomplete; missing sections: {missing}")

    if "ramscope-read-detail-merged-start" in original or "ramscope-poc-read-wiring-merged-start" in original:
        raise RuntimeError("Merge markers already exist; refusing a duplicate insertion")

    date_anchor = "**最終整理日：2026-07-26**\n"
    release_anchor = "\n---\n\n#### 6. `RAMScope_Release.vi`"
    error_anchor = "| `-700165` | `RAMScope_Read.vi` | Parsed Packet CountとDataNumが不一致 |\n"
    poc_anchor = "\n### 10.12.1 全フロントパネル出力の生成元"

    require_once(original, date_anchor, "date")
    require_once(original, release_anchor, "Release section")
    require_once(original, error_anchor, "-700165 table row")
    require_once(original, poc_anchor, "PoC output section")

    detail_body = convert_detail_headings(detail)
    detail_block = (
        "\n\n<!-- ramscope-read-detail-merged-start -->\n"
        "##### `RAMScope_Read.vi` 詳細作成手順（旧本文を保持した追記統合）\n\n"
        "> 直前の最終仕様を設計概要として残し、本項ではLabVIEW画面上で再現する端子、Case Structure、I32／I64型、ローカルエラー、配線および単体試験を展開する。\n\n"
        + detail_body
        + "\n<!-- ramscope-read-detail-merged-end -->\n"
    )
    error_row = "| `-700166` | `RAMScope_Read.vi` | ChNum、RequestedDataNum Limit、MdlNoまたはMax Buffer Bytesが不正 |\n"

    merged = original
    merged = merged.replace(date_anchor, date_anchor + NOTE_BLOCK, 1)
    merged = merged.replace(release_anchor, detail_block + release_anchor, 1)
    merged = merged.replace(error_anchor, error_anchor + error_row, 1)
    merged = merged.replace(poc_anchor, POC_BLOCK + poc_anchor, 1)

    restored = merged
    for inserted in (NOTE_BLOCK, detail_block, error_row, POC_BLOCK):
        restored = restored.replace(inserted, "", 1)
    if restored != original:
        raise RuntimeError("Insertion-only verification failed: original chapter text changed")

    MAIN_PATH.write_text(merged, encoding="utf-8", newline="\n")
    README_PATH.write_text(update_readme(README_PATH.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")

    for path in Path("docs").rglob("*.md"):
        if path in {MAIN_PATH, DETAIL_PATH} or "archive" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        updated = text.replace("10R_RAMScope_Read_vi_作成手順.md", "10_RAMScope実装方針.md")
        if updated != text:
            path.write_text(updated, encoding="utf-8", newline="\n")

    DETAIL_PATH.unlink()

    print(f"Original chars: {len(original)}")
    print(f"Merged chars:   {len(merged)}")
    print(f"Added chars:    {len(merged) - len(original)}")
    print("Insertion-only verification: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
