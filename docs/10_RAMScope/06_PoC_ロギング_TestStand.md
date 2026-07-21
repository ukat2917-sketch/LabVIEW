# 10-06. PoC・ロギング・TestStand引渡し

**監査日：2026-07-18**

---

## 1. `PoC_RAMScope_Main.vi`

### 0. 実現したい機能と責務

TestStandを使用せず、RAMScope公開APIの呼出順、状態遷移、Parser結果、CleanupをLabVIEW単体で確認する。TestStand設定の問題とRAMScope実装の問題を混ぜない。

### 1～5. データ、アルゴリズム、構造選定

PoCは次の順序を保証する。

```text
Connect
  → Init
  → Set_Cond
  → Log_Start
  → Wait
  → Read
  → Log_Stop
  → Release
  → Close
```

途中でエラーが発生した場合でも、実行済み状態に応じてCleanupへ進む必要がある。このため次のBooleanをShift Registerまたは状態クラスタで保持する。

```text
Connected?
Measurement Started?
Stopped?
Released?
File Open?
```

通常処理とCleanupを同じerror wireだけで直列接続すると、前段エラー時にCleanup Wrapperがスキップされる。Cleanupは元エラーを保持しながら、状態BooleanをselectorとするCase Structureで個別に試す。

### 6. 主な入出力

```text
入力 : Byte Order、Meas Config、Channel List、Module Log Configs、
       MaxDataNum、Wait Time、保存設定、error in
出力 : UnitNum、kind、Module List、MdlNo_RAM、MdlNo_CAN、Endian_RAM、
       Raw Buffer、Packets、LostDataNum、保存パス、Status、TestError、error out
```

### 7. 配置するSubVI

- `RAMScope_Connect.vi`
- `RAMScope_Init.vi`
- `RAMScope_Set_Cond.vi`
- `RAMScope_Log_Start.vi`
- 待機（Wait (ms)）
- `RAMScope_Read.vi`
- `RAMScope_Log_Stop.vi`
- `RAMScope_Release.vi`
- `RAMScope_Close.vi`
- 必要なCase Structure、Shift Register、Merge Errors相当処理

### 8. 配線順

1. `Connected?`、`Measurement Started?`、`Stopped?`、`Released?`をBoolean Falseで初期化する。
2. `RAMScope_Connect.vi`成功時だけConnected?をTrueへ更新する。
3. Connect errorを`RAMScope_Init.vi`へ接続する。
4. Init出力のMdlNo_RAMとEndian_RAMをSet CondおよびReadへ分岐する。
5. Set Cond成功後にLog Startを呼ぶ。
6. Log Start成功時だけMeasurement Started?をTrueへ更新する。
7. Wait後にReadを呼び、Raw Buffer、DataNum、LostDataNum、Packetsを記録する。
8. 通常経路でLog Stopを呼び、成功時にStopped?をTrueへ更新する。
9. Stopped?=Trueの場合だけReleaseを呼び、成功時にReleased?をTrueへ更新する。
10. Connected?=Trueの場合は最後にCloseを呼ぶ。
11. 途中エラー時はCleanup経路へ移り、Measurement Started?=TrueかつStopped?=FalseならCleanup専用Stopを試す。
12. Stop成功を確認できた場合だけReleaseを試す。
13. 最後にConnected?=TrueならCloseを試す。
14. 元エラーがある場合はCleanupエラーで上書きせず、最初のエラーを最終errorとする。

### 9. 記録する値と合格条件

```text
UnitNum / kind
各API ReturnCode
MdlNo_RAM / MdlNo_CAN / Endian_RAM
Module List / SlotErr[16]
MEASINFO=72byte
CHINFO=24×ChNum byte
LOGINFO=136byte
Raw Buffer / DataNum / LostDataNum
Parsed Packet Count / Unused Byte Count
Packet先頭・末尾Timestamp
Close結果 / 再Connect結果
```

合格条件：

- 全WrapperのFunction NameとCプロトタイプが一致する。
- Builderサイズが72、24×ChNum、136である。
- SYSINFO Parserが実機構成と一致する。
- 既知RAM変数とPacket解析値が一致する。
- Timestampが20ns換算と一致する。
- 正常・異常の両方でCloseまで到達する。
- 複数回再接続・再測定できる。

---

## 2. RAMScope側ロギングとLabVIEW側ファイル保存

次を同じ意味で使用しない。

```text
機器側ロギング設定
  Build_LOGINFO_Raw.vi
    → RS_DLL_GT150SetLoggingInfo.vi
    → RAMScope内部の保存条件・バッファ条件を設定

LabVIEW側ファイル保存
  RAMScope_File_Log_Open.vi
    → RAMScope_File_Log_Append.vi
    → RAMScope_File_Log_Close.vi
    → 解析済みPacketをTDMS等へ保存
```

SetLoggingInfoが成功しても、LabVIEW側のTDMSが作成されたことにはならない。

### 2.1 追加するファイル保存VI

```text
30_RAMScope/25_File_Logging/
├─ RAMScope_File_Log_Open.vi
├─ RAMScope_File_Log_Write_Metadata.vi
├─ RAMScope_File_Log_Append.vi
└─ RAMScope_File_Log_Close.vi
```

各VIは00A・00Bの10項目構成で別途確定する。少なくとも次を省略しない。

- File Path。
- Open Modeと既存ファイル時の動作。
- File Referenceの保持方法。
- Root/Group/Channel名。
- Flush条件。
- Close。
- 前段エラー時のCleanup。

### 2.2 TDMS保存モデル

```text
Root Properties
  Test Name
  DUT ID
  UnitNo / kind
  MdlNo_RAM / Endian_RAM
  Channel Count / Byte Order

Packets Group
  Packet Index
  Timestamp Raw
  Timestamp Seconds
  Flag
  Channel/<Name>/Raw U32
  Channel/<Name>/Value
  Channel/<Name>/Engineering Value

ReadStatus Group
  DataNum
  Parsed Packet Count
  LostDataNum
  Unused Byte Count
  Read Error Code
```

ファイルOpenに失敗した場合は測定を開始しない。途中エラーが発生してもFile Closeは試みる。

### 2.3 本番フロー

```text
Connect
  → Init
  → Set_Cond
  → File_Log_Open
  → Log_Start
  → Loop:
       Read
       必要な判定
       File_Log_Append
       Wait
  → Log_Stop
  → Release
  → File_Log_Close
  → Close
```

機器内部保存データを測定停止後に回収する方式は、`GetMeasNum`、`GetBlockNum`、`GetLoggingDataNum`、`GetLoggingData`の正式プロトタイプを入手してから追加する。推測したCLFNは作成しない。

---

## 3. TestStandへの引渡し

RAMScope単体PoCとファイル保存PoCに合格してからTestStandへ組み込む。

```text
Setup
  RAMScope_Connect.vi
  RAMScope_Init.vi
  RAMScope_Set_Cond.vi
  RAMScope_File_Log_Open.vi

Main
  RAMScope_Log_Start.vi
  Loop:
    RAMScope_Read.vi
    判定
    RAMScope_File_Log_Append.vi
    Wait
  RAMScope_Log_Stop.vi

Cleanup
  Measurement Started? かつ未停止ならCleanup Stop
  Stop成功ならRAMScope_Release.vi
  File Open?ならRAMScope_File_Log_Close.vi
  Connected?ならRAMScope_Close.vi
```

TestStandは`RS_DLL_*`、Builder、Parserを直接呼ばない。公開APIのStatus、TestError、error outだけで判定する。

---

## 4. Cleanupのエラー優先順位

```text
1. Main処理で最初に発生したエラー
2. Stopエラー
3. Releaseエラー
4. File Closeエラー
5. DeviceExitエラー
```

上位のエラーが存在する場合、下位Cleanupエラーで上書きしない。ただし、各Cleanupの実行結果は追加ログへ記録する。
