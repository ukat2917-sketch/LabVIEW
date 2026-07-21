# 10-06. PoC・ロギング・TestStand引渡し

**最終整理日：2026-07-21**

---

## 1. `PoC_RAMScope_Main.vi`

`PoC_RAMScope_Main.vi`の正式な作成手順は、次を参照する。

- [06A_PoC_RAMScope_Main_VI詳細作成手順.md](./06A_PoC_RAMScope_Main_VI詳細作成手順.md)

旧版の「Connected?、Measurement Started?、Stopped?、Released?をBoolean Falseで初期化する」という記述だけでは、Booleanの配置方法、各Public VIとの接続、成功判定、Cleanupで参照する値が不足していた。

現行手順では次の方式へ一本化する。

```text
RAMScope_PoC_State.ctlをFalseで初期化
  → Connect error out.statusからConnected?を更新
  → Log Start error out.statusからMeasurement Started?を更新
  → Log Stop error out.statusからStopped?を更新
  → Release error out.statusからReleased?を更新
  → 更新済みStateでCleanup Stop / Release / Closeを判定
```

単独Booleanを別々に引き回さず、`RAMScope_PoC_State.ctl`をBundle By Nameで更新しながら左から右へ流す。PoCは1回実行なので通常ワイヤを使い、将来ReadをWhileループ化するときだけ同じ状態クラスタをShift Registerへ移す。

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
