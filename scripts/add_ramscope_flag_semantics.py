from pathlib import Path

DOC = Path("docs/10_RAMScope実装方針.md")
SELF = Path("scripts/add_ramscope_flag_semantics.py")
WORKFLOW = Path(".github/workflows/add-ramscope-flag-semantics.yml")

text = DOC.read_text(encoding="utf-8")


def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"replacement target count must be 1, got {count}: {old[:120]!r}")
    text = text.replace(old, new, 1)


replace_once(
    """| Event Bits | 16～23 | `(Flag Raw >> 16) AND 0xFF` |
| Data Lost | 28 | `((Flag Raw >> 28) AND 1) != 0` |

予約bitは値不定のため、0であることを正常条件にしない。

`Skip`、`Data Lost`、`Status != 0`は測定Packet内の状態情報であり、Parser自身の配列エラーとは分ける。該当Packetを捨てず、Raw値と解析結果をTDMSへ保存する。""",
    """| Event Bits | 16～23 | `(Flag Raw >> 16) AND 0xFF` |
| Data Lost | 28 | `((Flag Raw >> 28) AND 1) != 0` |

Statusコードは次の意味で保存する。

| Status | 意味 |
|---:|---|
| `0x00` | 正常動作 |
| `0xFF` | バスエラー、デバッグIF通信異常 |
| `0xFE` | オフライン、ターゲットマイコン電源検出NG |
| `0xFA` | セキュリティIDエラー、デバッグIF通信異常 |
| `0xF9` | リンクエラー |
| `0xF8` | パラメータ未設定エラー |
| その他 | 予約値。意味未定義のためRawコードを保持する |

Log Triggerは次の値を持つ。

| Log Trigger | 意味 |
|---:|---|
| `0` | 開始、センター、終了のいずれでもない |
| `1` | 測定データBlockの開始位置 |
| `2` | ポイント指定時のセンター位置、基準トリガ成立Packet |
| `3` | 測定データBlockの終了位置 |

各Boolean／bit fieldの意味は次のとおり。

- `Skip?=True`：このPacketより前に、測定周期、チャンネル数、メモリ操作負荷などの競合で収録タイミングをスキップした周期がある。
- `Dummy?=True`：通常の測定値Packetではなく、RAMScopeハードウェアが情報通知目的で生成したDummy Packetである。Packet自体は保存するが、Dataを通常測定値として自動判定に使用しない。
- `Event Bits`：bit0からbit7がイベントe1からe8に対応する。
- `Data Lost?=True`：このPacket以前にRAMScopeハードウェアとホストPC間でデータ欠落が発生した。

予約bitは値不定のため、0であることを正常条件にしない。

`Skip`、`Data Lost`、`Status != 0`は測定Packet内の状態情報であり、Parser自身の配列エラーとは分ける。該当Packetを捨てず、Raw値と解析結果をTDMSへ保存する。`pLostDataNum`はAPIが返す破棄Packet数として別項目で保存し、Flagの`Data Lost?`と統合しない。""",
)
replace_once(
    """- TDMS VI：Open、Write Metadata、Append、Close。
- For Loop×2、Shift Register、Case Structure、Bundle By Name、Unbundle By Name、Clear Errors、Merge Errors、Error_To_TestStatus。""",
    """- TDMS VI：Open、Write Metadata、Append、Close。
- 現在の日時を秒で取得（Get Date/Time In Seconds）：プログラミング → タイミング。Log Start直前のMeasurementStartTimeを保持する。
- For Loop×2、Shift Register、Case Structure、Bundle By Name、Unbundle By Name、Clear Errors、Merge Errors、Error_To_TestStatus。""",
)

DOC.write_text(text, encoding="utf-8", newline="\n")
SELF.unlink(missing_ok=True)
WORKFLOW.unlink(missing_ok=True)
