from pathlib import Path

DOC = Path("docs/10_RAMScope実装方針.md")
SELF = Path("scripts/refine_ramscope_logging_chapter10.py")
WORKFLOW = Path(".github/workflows/refine-ramscope-logging-chapter10.yml")

text = DOC.read_text(encoding="utf-8")


def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"replacement target count must be 1, got {count}: {old[:120]!r}")
    text = text.replace(old, new, 1)


replace_once(
    """### 10.2.5 PoC・単体操作・TestStand

```text
PoC_RAMScope_Main.vi
PoC_RAMScope_Logging_Main.vi
```""",
    """### 10.2.5 LabVIEW側ファイル保存VI

```text
RAMScope_File_Log_Open.vi
RAMScope_File_Log_Write_Metadata.vi
RAMScope_File_Log_Append.vi
RAMScope_File_Log_Close.vi
```

これらはRAMScopeVP APIのDLL Wrapperではなく、LabVIEW側でTDMSを管理するVIである。機器側の`SetLoggingInfo`および保存用バッファと混同しない。

### 10.2.6 PoC・単体操作・TestStand

```text
PoC_RAMScope_Main.vi
PoC_RAMScope_Logging_Main.vi
```""",
)
replace_once(
    """TestStand、PoC_RAMScope_Main.vi または PoC_RAMScope_Logging_Main.vi
  → RAMScope_* 公開API
      → Builder / Parser / Common
          → RS_DLL_* 薄いラッパ
              → CLFN
                  → RAMScopeVP_API_x64.dll""",
    """TestStand、PoC_RAMScope_Main.vi または PoC_RAMScope_Logging_Main.vi
  ├─→ RAMScope_* 公開API
  │     → Builder / Parser / Common
  │         → RS_DLL_* 薄いラッパ
  │             → CLFN
  │                 → RAMScopeVP_API_x64.dll
  └─→ RAMScope_File_Log_* VI
          → LabVIEW TDMS API
              → .tdms""",
)
replace_once(
    """`PoC_RAMScope_Main.vi`は、TestStandを使用せず、RAMScope公開APIを次の順で1回実行するPoCである。

```text""",
    """`PoC_RAMScope_Main.vi`は、TestStandを使用せず、RAMScope公開APIを次の順で1回実行する通信確認用PoCである。

本VIへTDMS File Ref、MeasNo／BlockNoの二重For Loop、`GetLoggingData()`による停止後保存ログ回収を追加しない。ロギング検証は`PoC_RAMScope_Logging_Main.vi`へ分離する。

```text""",
)
replace_once(
    "| `File Open?` | Boolean | 将来、`RAMScope_File_Log_Open.vi`が正常終了した |",
    "| `File Open?` | Boolean | 既存ctlとの互換性維持用予約項目。通信確認用PoCでは常にFalseとし、TDMS VIへ接続しない |",
)
replace_once(
    """1. RootへTestName等を設定する。
2. Channel Listを自動インデックスでFor Loopへ入れる。
3. Group名テンプレートではなく、Channel Propertyテンプレート用の一時Group名`RAMScope_Metadata`を使用するか、Rootへ`Channel_<index>_<property>`形式で保存する。
4. 既存error時は書込をスキップしてRefを通す。
5. Property書込失敗は元のTDMS errorを保持する。""",
    """1. RootへTestName等を設定する。
2. Channel Listを自動インデックスでFor Loopへ入れる。
3. 各チャンネルの情報をRoot Propertyへ次の固定キー形式で保存する。

```text
Channel_000_Name
Channel_000_Address
Channel_000_Size
Channel_000_Sign
Channel_000_Scale
Channel_000_Offset
Channel_000_Unit
```

4. `%03d`へChannel Indexを接続し、キー名を一意にする。
5. 既存error時は書込をスキップしてRefを通す。
6. Property書込失敗は元のTDMS errorを保持する。""",
)
replace_once(
    """#### 5. LabVIEW構造の選定理由

1Blockだけを扱い、MeasNo／BlockNoの反復はLogging PoCまたはTestStandへ任せる。これによりPublic VI内で巨大な全ログ配列を保持しない。""",
    """#### 5. LabVIEW構造の選定理由

1Blockだけを扱い、MeasNo／BlockNoの反復はLogging PoCまたはTestStandへ任せる。これによりPublic VI内で巨大な全ログ配列を保持しない。

`RAMScopeGT150GetLoggingData()`で読み出したPacketはAPI内部バッファから削除されるため、取得後は同じBlockを再取得できる前提にしない。本VIが返したRaw BufferとPacketsを次Block取得前にTDMSへ保存する。""",
)
replace_once(
    """7. Read Logging BlockのPackets、件数、LostをAppendへ接続する。
8. Append error outを次反復へShift Registerで渡す。
9. 各Block終了後にTotal Packet CountをI64加算する。
10. 両Loop正常終了時だけLogging Retrieved?をTrue。""",
    """7. Read Logging BlockのPackets、件数、LostをAppendへ接続する。
8. `GetLoggingData()`後はAPI内部の読出し済みPacketが削除されるため、Append完了前に次Blockへ進まない。
9. Append error outを次反復へShift Registerで渡す。
10. 各Block終了後にTotal Packet CountをI64加算する。
11. 両Loop正常終了時だけLogging Retrieved?をTrue。""",
)

DOC.write_text(text, encoding="utf-8", newline="\n")
SELF.unlink(missing_ok=True)
WORKFLOW.unlink(missing_ok=True)
