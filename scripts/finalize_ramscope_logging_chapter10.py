from pathlib import Path

DOC = Path("docs/10_RAMScope実装方針.md")
SELF = Path("scripts/finalize_ramscope_logging_chapter10.py")
WORKFLOW = Path(".github/workflows/finalize-ramscope-logging-chapter10.yml")

text = DOC.read_text(encoding="utf-8")


def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"replacement target count must be 1, got {count}: {old[:120]!r}")
    text = text.replace(old, new, 1)


replace_once(
    """- [ ] 1パケットごとにChannel/Flag/Timestampを解析
- [ ] 符号付き変換でType Castを使用
- [ ] Engineering ValueをScale/Offsetで変換
- [ ] 余剰バイト数を出力""",
    """- [ ] 1パケットごとにChannel/Flag/Timestampを解析
- [ ] Size=0／1／2を1byte／2byte／4byteとしてmaskし、符号付き値は同じbit幅へType Castする
- [ ] Status、Skip、Log Trigger、Dummy、Event Bits、Data LostをFlag Rawから抽出する
- [ ] Engineering ValueをScale/Offsetで変換
- [ ] Timestamp Rawへ20nsを掛けて秒へ変換する
- [ ] 余剰バイト数を出力""",
)
replace_once(
    """## 10.11 公開API 8個

本書では、TestStandから呼び出す`RAMScope_*`公開API 8個を、00Aの再現可能な配線手順と00Bの設計理由の両方で説明する。

全公開APIは最後に`Error_To_TestStatus.vi`を1回だけ呼び、`Status.ctl`、`TestError.ctl`、標準`error out`を返す。DLL Wrapper、Builder、Parserから同SubVIを呼ばない。""",
    """## 10.11 既存公開API 8個

本節では、通信確認と基本測定に使用する既存`RAMScope_*`公開API 8個を、00Aの再現可能な配線手順と00Bの設計理由の両方で説明する。停止後保存ログ取得用の追加公開API 3個は10.13.5で説明する。

既存8個と追加3個の全公開APIは最後に`Error_To_TestStatus.vi`を1回だけ呼び、`Status.ctl`、`TestError.ctl`、標準`error out`を返す。DLL Wrapper、Builder、Parserから同SubVIを呼ばない。""",
)
replace_once(
    """    <Channel Name 0>
    <Channel Name 1>
    ...""",
    """    <Channel Name 0>          Engineering Value DBL
    <Channel Name 0>__Raw     Raw Slot U32
    <Channel Name 1>          Engineering Value DBL
    <Channel Name 1>__Raw     Raw Slot U32
    ...""",
)
replace_once(
    "Boolean状態は解析ツール互換性を優先し、TDMS上ではU8の0／1として保存する。測定値チャンネルはEngineering Value DBLを保存し、Raw値、Address、Size、Sign、Scale、Offset、UnitはChannel Propertyへ保存する。",
    "Boolean状態は解析ツール互換性を優先し、TDMS上ではU8の0／1として保存する。測定値はEngineering Value DBLとRaw Slot U32を別チャンネルで保存し、Address、Size、Sign、Scale、Offset、UnitはChannel Propertyへ保存する。",
)
replace_once(
    "TDMS Rootおよび各測定チャンネルに、後のMF4変換へ必要なメタデータを記録する。",
    "TDMS Rootへ試験全体情報とチャンネル定義を記録し、後のMF4変換で信号名、型、単位、換算情報を再構成できるようにする。",
)
replace_once(
    "Root Properties書込 → Channel List For LoopでChannel Property書込 → Flush任意。",
    "Root Properties書込 → Channel List For Loopで`Channel_%03d_*`形式のRoot Propertyを書込 → Flush任意。",
)
replace_once(
    "Open直後、Log Start前に1回だけ呼ぶ。",
    "Log Stop後の`RAMScope_Get_Log_Summary.vi`成功直後、最初のBlockをTDMSへAppendする前に1回だけ呼ぶ。MeasurementStartTimeはLog Start直前に取得した値、GapTimeMsはSummary出力を接続する。",
)
replace_once(
    """    Channel NameでTDMS Write
    Raw/Address/Size/Sign/Scale/Offset/UnitをChannel Propertyへ保存
if Flush After Write?: TDMS Flush""",
    """    Channel NameでEngineering Value DBLをTDMS Write
    Channel Name + "__Raw"でRaw Slot U32をTDMS Write
    Address/Size/Sign/Scale/Offset/UnitをEngineering Value Channel Propertyへ保存
if Flush After Write?: TDMS Flush""",
)
replace_once(
    """6. Channel外側For LoopでEngineering Value配列を作る。
7. Channel名が空の場合は`Channel_%03d`を使用する。
8. 同名Channelがある場合はIndexを付加して一意化する。
9. Flush入力がTrueならTDMS Flushする。
10. Written Packet Count=DataNumを返す。""",
    """6. Channel外側For LoopでEngineering Value DBL配列とRaw Slot U32配列を作る。
7. Engineering ValueはChannel名、Raw Slotは`<Channel名>__Raw`でTDMS Writeする。
8. Channel名が空の場合は`Channel_%03d`を使用する。
9. 同名Channelがある場合はIndexを付加して一意化する。
10. Address、Size、Sign、Scale、Offset、UnitをEngineering Value Channel Propertyへ設定する。
11. Flush入力がTrueならTDMS Flushする。
12. Written Packet Count=DataNumを返す。""",
)
replace_once(
    """File Log Open
File Open?更新
Write Metadata

Log Start""",
    """File Log Open
File Open?更新
MeasurementStartTimeを保存

Log Start""",
)
replace_once(
    """Get Log Summary
Log Summary Read?更新

for MeasNo""",
    """Get Log Summary
Log Summary Read?更新
Write Metadata(Test情報、Channel定義、MeasurementStartTime、GapTimeMs)

for MeasNo""",
)
replace_once(
    """#### C. TDMS OpenとMetadata

1. Set Cond error outをFile Log Openへ接続する。
2. Open成功時にFile Open?をTrueへ更新する。
3. File RefとerrorをWrite Metadataへ接続する。
4. Write Metadata error outをLog Startへ接続する。""",
    """#### C. TDMS Openと測定開始時刻の保持

1. Set Cond error outをFile Log Openへ接続する。
2. Open成功時にFile Open?をTrueへ更新する。
3. Get Date/Time In Secondsを配置し、Log Start直前の値を`MeasurementStartTime`として保持する。
4. File Log Openのerror outをLog Startへ接続する。
5. File Ref、MeasurementStartTimeおよびStateをSummary後のMetadata書込位置まで通す。""",
)
replace_once(
    """1. Stop error outをGet Log Summaryへ接続する。
2. 成功時にLog Summary Read?をTrue。
3. MeasNumを外側For Loop Nへ接続する。""",
    """1. Stop error outをGet Log Summaryへ接続する。
2. 成功時にLog Summary Read?をTrue。
3. SummaryのGapTimeMs、Cで保持したMeasurementStartTime、File Ref、Channel ListをFile Log Write Metadataへ接続する。
4. Write Metadataのerror outを外側For Loopへ接続する。
5. MeasNumを外側For Loop Nへ接続する。""",
)
replace_once(
    """4. 外側iをMeasNoへ接続する。
5. Get Block CountのBlockNumを内側For Loop Nへ接続する。
6. 内側iをBlockNoへ接続する。
7. Read Logging BlockのPackets、件数、LostをAppendへ接続する。
8. `GetLoggingData()`後はAPI内部の読出し済みPacketが削除されるため、Append完了前に次Blockへ進まない。
9. Append error outを次反復へShift Registerで渡す。
10. 各Block終了後にTotal Packet CountをI64加算する。
11. 両Loop正常終了時だけLogging Retrieved?をTrue。""",
    """6. 外側iをMeasNoへ接続する。
7. Get Block CountのBlockNumを内側For Loop Nへ接続する。
8. 内側iをBlockNoへ接続する。
9. Read Logging BlockのPackets、件数、LostをAppendへ接続する。
10. `GetLoggingData()`後はAPI内部の読出し済みPacketが削除されるため、Append完了前に次Blockへ進まない。
11. Append error outを次反復へShift Registerで渡す。
12. 各Block終了後にTotal Packet CountをI64加算する。
13. 両Loop正常終了時だけLogging Retrieved?をTrue。""",
)
replace_once(
    """Setup
  RAMScope_Connect.vi
  RAMScope_Init.vi
  RAMScope_Set_Cond.vi
  RAMScope_File_Log_Open.vi
  RAMScope_File_Log_Write_Metadata.vi

Main
  RAMScope_Log_Start.vi
  DUT試験
  RAMScope_Log_Stop.vi
  RAMScope_Get_Log_Summary.vi""",
    """Setup
  RAMScope_Connect.vi
  RAMScope_Init.vi
  RAMScope_Set_Cond.vi
  RAMScope_File_Log_Open.vi
  MeasurementStartTimeを保持

Main
  RAMScope_Log_Start.vi
  DUT試験
  RAMScope_Log_Stop.vi
  RAMScope_Get_Log_Summary.vi
  RAMScope_File_Log_Write_Metadata.vi""",
)

DOC.write_text(text, encoding="utf-8", newline="\n")
SELF.unlink(missing_ok=True)
WORKFLOW.unlink(missing_ok=True)
