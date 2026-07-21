# 10-05. Public API 8個の監査済み作成手順

**監査日：2026-07-18**

本書では、TestStandから呼び出す`RAMScope_*`公開API 8個を、00Aの再現可能な配線手順と00Bの設計理由の両方で説明する。

全公開APIは最後に`Error_To_TestStatus.vi`を1回だけ呼び、`Status.ctl`、`TestError.ctl`、標準`error out`を返す。DLL Wrapper、Builder、Parserから同SubVIを呼ばない。

---

## 1. `RAMScope_Connect.vi`

### 0～5. 機能、データ、アルゴリズム、構造選定

`DeviceInit`を1回実行し、接続Unit数と機種コードを上位へ返す。下位処理は1個のWrapperだけなので、Public VI内に追加のForループや状態保持は不要である。既存エラーのスキップはWrapper側が担当する。

### 6. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `error in` | 入力 | error cluster |
| `UnitNum` | 出力 | I32 |
| `kind` | 出力 | I32 |
| `Status` | 出力 | `Status.ctl` |
| `TestError` | 出力 | `TestError.ctl` |
| `error out` | 出力 | error cluster |

### 7. 配置する関数・SubVI

- `RS_DLL_GT150DeviceInit.vi`
- `Error_To_TestStatus.vi`
- 文字列定数`RAMScope`

### 8. 配線順

1. `error in`を`RS_DLL_GT150DeviceInit.vi / error in`へ接続する。
2. Wrapperの`UnitNum`を本VIの`UnitNum`へ接続する。
3. Wrapperの`kind`を本VIの`kind`へ接続する。
4. Wrapperの`error out`を`Error_To_TestStatus.vi / error in`へ接続する。
5. 文字列定数`RAMScope`を同SubVIの`Device Name`へ接続する。
6. 同SubVIの`Status`、`TestError`、`error out`を本VIの同名出力へ接続する。

### 9. 単体テスト

- 既存`error in.status=True`ではWrapperのCLFNが呼ばれず、UnitNum=0、kind=0、元エラー保持。
- GT170接続時はReturnCode、UnitNum、kindを記録する。正常値は実機確認待ち。

---

## 2. `RAMScope_Init.vi`

### 0. 実現したい機能とVIの責務

Unit全体を初期化し、SYSINFOを解析してRAM/CANモジュール番号とRAM Endianを取得し、RAMモジュールが存在するときだけPGT設定を実行する。PGTのSlotErr[16]も検査し、最初に見つかった非ゼロ値を標準error clusterへ変換する。

### 1. 入力データの実体

```text
UnitNo
  → AllInit
  → GetSysInfoがU8[960]を返す
  → Parse_SYSINFO_Array.viが16レコードへ解析
  → RAM Module Found? / MdlNo_RAM / Endian_RAM
  → PGT_SetMdlConfigがI32[16] SlotErrを返す
```

### 2. 出力データモデル

- `Module List`は`RAMScope_Module_Info.ctl`の一次元配列。
- `MdlNo_RAM`、`MdlNo_CAN`、`Endian_RAM`はParserの最終検出値。
- `SlotErr[16]`はPGT設定結果。PGT未実行時はI32ゼロ配列16要素。

### 3. 前提条件・異常条件

```text
前段またはAllInit/GetSysInfo/Parserエラーあり
  → 後続PGTを呼ばない
RAM Module Found?=False
  → -700140
RAM Module Found?=True
  → PGT設定
PGT Wrapperエラーあり
  → SlotErr走査を行わずWrapperエラーを保持
PGT Wrapper正常かつSlotErrに非ゼロあり
  → -700141
```

### 4. 処理アルゴリズム

```text
AllInit
GetSysInfo
Parse SYSINFO
if Parser error:
    Parser errorを返す
elif RAM Module Found? == False:
    RAM未検出エラーを返す
else:
    PGT_SetMdlConfig
    if PGT error:
        PGT errorを返す
    else:
        SlotErrを先頭から走査
        最初の非ゼロがあればSlotエラーを返す
        なければ正常
最後にError_To_TestStatus
```

### 5. LabVIEW構造の選定理由

- error clusterを直列接続し、AllInit→GetSysInfo→Parserの順序を固定する。
- Parserエラーを元の原因として保持するため、`Parser error.status`のCaseをRAM Module Found? Caseより外側に置く。
- PGTをRAM未検出時に呼ばないため、`RAM Module Found?` Caseを使う。
- SlotErrは同じ判定を16要素へ適用するためForループを使う。
- 最初の非ゼロSlotだけを保持するため、Slot IndexとSlot ErrorのShift Registerを使う。

### 6. 入出力

```text
入力 : UnitNo I32、Byte Order、error in
出力 : Module List、MdlNo_RAM、MdlNo_CAN、Endian_RAM、
       RAM Module Found?、CAN Module Found?、SlotErr[16]、
       Status、TestError、error out
```

### 7. 配置する関数・SubVI

- `RS_DLL_GT150AllInit.vi`
- `RS_DLL_GT150GetSysInfo.vi`
- `Parse_SYSINFO_Array.vi`
- `RS_DLL_GT150PGT_SetMdlConfig.vi`
- `Error_To_TestStatus.vi`
- 名前でバンドル解除（Unbundle By Name）
- ケースストラクチャ（Case Structure）3個以上
- 配列初期化（Initialize Array）
- Forループ（For Loop）
- シフトレジスタ（Shift Register）3本
- 等しくない?（Not Equal?）
- 等しい?（Equal?）
- 複合演算（Compound Arithmetic）
- 文字列にフォーマット（Format Into String）2個
- 名前でバンドル（Bundle By Name）2個

### 8. 配線順

#### A. AllInit、GetSysInfo、Parser

1. `UnitNo`と`error in`を`RS_DLL_GT150AllInit.vi`へ接続する。
2. AllInitの`error out`を`RS_DLL_GT150GetSysInfo.vi / error in`へ接続する。
3. `UnitNo`をGetSysInfo Wrapperへ接続する。
4. GetSysInfoの`SYSINFO Raw`を`Parse_SYSINFO_Array.vi / SYSINFO Raw`へ接続する。
5. `Byte Order`をParserへ接続する。
6. GetSysInfoの`error out`をParserの`error in`へ接続する。
7. ParserのModule List、MdlNo_RAM、MdlNo_CAN、Endian_RAM、Found Booleanを本VIの対応出力へ接続する。
8. Parserの`error out.status`を外側Case Structureのselectorへ接続する。

#### B. Trueケース（Parser error.status=True：Parserまでにエラーあり）

1. `RS_DLL_GT150PGT_SetMdlConfig.vi`とSlotErr走査処理を配置しない。
2. 配列初期化へI32定数`0`を`element`、I32定数`16`を`dimension size`として接続する。
3. I32ゼロ配列16要素を`SlotErr[16]`出力トンネルへ接続する。
4. Parserの`error out`をerror出力トンネルへそのまま接続する。

#### C. Falseケース（Parser error.status=False：Parser正常）

1. `RAM Module Found?`を内側Case Structureのselectorへ接続する。

#### D. Falseケース（RAM Module Found?=False：RAM未検出）

1. 配列初期化へI32定数`0`とI32定数`16`を接続し、I32ゼロ配列16要素を作る。
2. ゼロ配列を`SlotErr[16]`出力トンネルへ接続する。
3. 文字列にフォーマットへ次の全文を設定する。

```text
RAMScope_Init.vi: RAM monitor module was not found. PGT configuration was not executed. UnitNo=%d, MdlNo_RAM=%d
```

4. 1個目の`%d`へ`UnitNo` I32を接続する。
5. 2個目の`%d`へParserの`MdlNo_RAM` I32を接続する。
6. 名前でバンドルの基準クラスタへParserの正常な`error out`を接続する。
7. Boolean定数`True`を`status`へ接続する。
8. I32定数`-700140`を`code`へ接続する。
9. Format Into String出力を`source`へ接続する。
10. Bundle By Name出力をRAM Module Found? Caseのerror出力トンネルへ接続する。
11. このCaseにはPGT Wrapperを配置しない。

期待source例：

```text
RAMScope_Init.vi: RAM monitor module was not found. PGT configuration was not executed. UnitNo=0, MdlNo_RAM=-1
```

#### E. Trueケース（RAM Module Found?=True：RAM検出済み）

1. `RS_DLL_GT150PGT_SetMdlConfig.vi`を配置する。
2. `UnitNo`を同Wrapperの`UnitNo`へ接続する。
3. Parserの正常な`error out`を同Wrapperの`error in`へ接続する。
4. Wrapperの`SlotErr`を本VIの`SlotErr[16]`出力トンネルへ分岐する。
5. Wrapperの`error out.status`をPGT error Case Structureのselectorへ接続する。

#### F. Trueケース（PGT error.status=True：PGT Wrapperエラーあり）

1. SlotErr走査Forループを配置しない。
2. Wrapperの`error out`をerror出力トンネルへそのまま接続する。

#### G. Falseケース（PGT error.status=False：PGT Wrapper正常）

1. Forループを配置する。
2. Wrapperの`SlotErr[16]`をForループ左枠へ接続する。
3. 入力トンネルの指標付けを有効にし、1反復でSlotErr I32単体を処理する。
4. N端子は未配線にし、SlotErr配列の16要素で反復する。
5. Shift Registerを3本追加する。
6. 1本目の左外側へI32定数`-1`を接続し、`First Slot Index`とする。
7. 2本目の左外側へI32定数`0`を接続し、`First Slot Error`とする。
8. 3本目の左外側へWrapperの正常な`error out`を接続する。
9. 現在のSlotErr I32とI32定数`0`を等しくない?へ接続する。
10. `First Slot Index == -1`を作る。
11. 2条件をANDし、`First Nonzero?` Case Structureのselectorへ接続する。
12. Trueケース（First Nonzero?=True：最初の非ゼロ）で反復端子`i`をFirst Slot Index右内側へ、現在のSlotErrをFirst Slot Error右内側へ接続する。
13. Falseケース（First Nonzero?=False：非ゼロ未検出または既に検出済み）で各左内側の現在値を右内側へ接続する。初期値へ戻さない。
14. error Shift Registerは両Caseで左内側から右内側へそのまま接続する。
15. ループ右外側のFirst Slot IndexとI32定数`-1`を等しくない?へ接続し、`Slot Error Found?` Case Structureのselectorへ接続する。
16. Falseケース（Slot Error Found?=False：全Slot正常）でPGTの正常errorを出力する。
17. Trueケース（Slot Error Found?=True：SlotErr非ゼロあり）で次のFormat Stringを設定する。

```text
RAMScope_Init.vi: PGT module configuration reported a slot error. SlotIndex=%d, SlotError=%d
```

18. 1個目の`%d`へFirst Slot Index I32を接続する。
19. 2個目の`%d`へFirst Slot Error I32を接続する。
20. Bundle By Nameの基準クラスタへPGT Wrapperの正常な`error out`を接続する。
21. `status=True`、`code=I32 -700141`、`source=Format Into String出力`を接続する。
22. Bundle出力をSlot Error Found? Caseのerror出力トンネルへ接続する。
23. RAM Module Found? Case、Parser error Caseの順に、全error出力トンネルを外側へ接続する。
24. 最終errorを`Error_To_TestStatus.vi / error in`へ接続する。
25. 文字列定数`RAMScope`を`Device Name`へ接続する。
26. Status、TestError、error outを本VI出力へ接続する。

### 9. 単体テスト

| 条件 | 期待結果 |
|---|---|
| Parser既存エラー | PGT未実行、SlotErrゼロ16要素、元エラー保持 |
| RAM Module Found?=False | code=-700140、PGT未実行、source全文一致 |
| RAM検出、SlotErr全0 | 正常 |
| SlotErr[3]=5 | code=-700141、sourceにSlotIndex=3、SlotError=5 |
| SlotErr[3]=5、SlotErr[7]=9 | 最初のSlot 3を返す |
| PGT Wrapperエラー | -700141で上書きせずWrapperエラー保持 |

---

## 3. `RAMScope_Set_Cond.vi`

### 0～5. 設計

Meas Config、Channel List、Module Log Configsを各BuilderでDLL用U8配列へ変換し、サイズが正しいことを確認してから、SetMeasCond→SetMeasCh→SetLoggingInfoの順に実行する。Builderエラーやサイズ不正時に後続APIを呼ばないため、error cluster直列接続とサイズ判定Caseを使う。

### 6. 入出力

```text
入力 : UnitNo、MdlNo_RAM、Meas Config、Channel List、
       LogDevice、LimitHddSize、Module Log Configs、error in
出力 : ChNum、Status、TestError、error out
```

### 7. 配置

`Build_MEASINFO_170_Raw.vi`、`Build_CHINFO_170_Raw.vi`、`Build_LOGINFO_Raw.vi`、3個のDLL Wrapper、Array Size、比較、Compound Arithmetic、Case Structure、Format Into String、Bundle By Name、`Error_To_TestStatus.vi`。

### 8. 配線順

1. 3個のBuilderをMEASINFO→CHINFO→LOGINFOの順にerror clusterで直列接続する。
2. MEASINFO RawのArray Sizeが72、CHINFO Rawが`24×ChNum`、LOGINFO Rawが136か比較する。
3. 3条件をANDし、`Builder Size Valid?` Caseへ接続する。
4. Falseケース（Builder Size Valid?=False：Builder出力サイズ不正）では3個のDLL Wrapperを配置せず、次のFormat Stringを作る。

```text
RAMScope_Set_Cond.vi: Builder output size is invalid. MEASINFO=%d, CHINFO=%d, ExpectedCHINFO=%d, LOGINFO=%d
```

5. `%d`へ順にMEASINFO Array Size I32、CHINFO Array Size I32、`24×ChNum` I32、LOGINFO Array Size I32を接続する。
6. Bundle By Nameの基準へ最後のBuilderの正常errorを接続し、`status=True`、`code=I32 -700150`、`source=Format出力`を接続する。
7. Trueケース（Builder Size Valid?=True：サイズ正常）でSetMeasCond→SetMeasCh→SetLoggingInfoをerror clusterで直列接続する。
8. UnitNo、MdlNo、ChNum、各Raw配列を対応Wrapper端子へ接続する。
9. 最終errorを`Error_To_TestStatus.vi`へ接続し、Device Name=`RAMScope`とする。

### 9. テスト

72、`24×ChNum`、136の正常値、各1byte不足、Builder既存エラー、ChNum=1/2を確認する。

---

## 4. `RAMScope_Log_Start.vi`

### 0～5. 設計

測定開始APIを1回呼ぶ1イベントVI。状態遷移は上位PoC/TestStandが管理する。

### 6～8. 配線

1. `UnitNo`と`error in`を`RS_DLL_GT150MeasStart.vi`へ接続する。
2. Wrapper errorを`Error_To_TestStatus.vi`へ接続する。
3. Device Name=`RAMScope`とし、Status、TestError、error outを出力する。

### 9. テスト

Set Cond後の正常開始、Set Cond前、二重開始、既存エラーを記録する。

---

## 5. `RAMScope_Read.vi`

### 0～5. 設計

Channel ListからPacket Sizeを求め、MaxDataNum分のU8配列を確保してGetBufferDataを呼び、実際のDataNumだけParserで解析する。

```text
ChNum           = Array Size(Channel List)
Packet Size     = 4 × ChNum + 12
Buffer Byte Size= Packet Size × MaxDataNum
```

MaxDataNumまたは計算サイズが不正な場合にCLFNへ不正Pointerを渡さないため、入力検証CaseをWrapperより外側へ置く。

### 6. 入出力

```text
入力 : UnitNo、MdlNo_RAM、MaxDataNum、Channel List、Byte Order、error in
出力 : Raw Buffer、DataNum、LostDataNum、Packets、
       Parsed Packet Count、Unused Byte Count、Status、TestError、error out
```

### 7～8. 配線順

1. `Array Size(Channel List)`をChNumとする。
2. Packet SizeとBuffer Byte SizeをI32で計算する。
3. `ChNum>=1`、`MaxDataNum>0`、`Buffer Byte Size>0`をANDし、Input Valid? Caseへ接続する。
4. Falseケース（Input Valid?=False：Read入力不正）では空Raw、DataNum=0、Lost=0、空Packets、各Count=0を接続し、次のsourceを作る。

```text
RAMScope_Read.vi: ChNum and MaxDataNum must be positive. ChNum=%d, MaxDataNum=%d, BufferByteSize=%d
```

5. `%d`へChNum I32、MaxDataNum I32、Buffer Byte Size I32を順に接続する。
6. Bundle By Nameへ正常なerror、status=True、code=I32 -700160、sourceを接続する。
7. Trueケース（Input Valid?=True：Read入力正常）でBuffer Byte SizeとMaxDataNumを`RS_DLL_GT150GetBufferData.vi`へ接続する。
8. WrapperのRaw Buffer、DataNum、LostDataNumを本VIへ接続する。
9. Raw Buffer、DataNum、Channel List、Byte Order、Wrapper errorを`RAMScope_Parse_Buffer.vi`へ接続する。
10. ParserのPackets、Parsed Count、Unused、errorを本VIへ接続する。
11. Parser errorを`Error_To_TestStatus.vi`へ接続する。

### 9. テスト

MaxDataNum=1/0/-1、Channel List空、DataNum=0、正常1Packet、LostDataNum非ゼロ、Parserバッファ不足を確認する。

---

## 6. `RAMScope_Release.vi`

### 0～5. 設計

測定停止後のアイドル状態で保存用データバッファを解放する。測定中に発行不可なので、Readの直後へ内包しない。

### 6～8. 配線

1. `UnitNo`と`error in`を`RS_DLL_GT150ReleaseBufferData.vi`へ接続する。
2. Wrapper errorを`Error_To_TestStatus.vi`へ接続する。
3. Device Name=`RAMScope`とする。

### 9. テスト

オフライン、測定中、MeasStop後アイドル、二重Releaseを記録する。本番では`MeasStop成功 → Release → Close`とする。

---

## 7. `RAMScope_Log_Stop.vi`

### 0～5. 設計

測定を停止してアイドル状態へ移す。Releaseと分離し、Stop失敗時にReleaseを呼ばない判断を上位へ残す。

### 6～8. 配線

1. `UnitNo`と`error in`を`RS_DLL_GT150MeasStop.vi`へ接続する。
2. Wrapper errorを`Error_To_TestStatus.vi`へ接続する。
3. Device Name=`RAMScope`とする。

### 9. テスト

正常停止、未開始、二重停止、既存エラーを確認する。Cleanup専用経路では前段エラーがあってもStopを試す設計を別途用意する。

---

## 8. `RAMScope_Close.vi`

### 0～5. 設計

前段エラーがあってもDeviceExitを試み、最初のエラーを失わないCleanup VI。DeviceExit Wrapperは元errorを保持したまま内部でClear Errors後にCLFNを実行する。

### 6～8. 配線順

1. 本VIの`error in`を`Original Error`として分岐・保持する。
2. 同じ`error in`を`RS_DLL_GT150DeviceExit.vi`へ接続する。
3. Wrapperの`DeviceExit error`とOriginal Errorを2入力のCaseまたはMerge Errors相当処理へ接続する。
4. `Original Error.status=True`ならOriginal Errorを最終errorへ接続する。
5. `Original Error.status=False`ならDeviceExit errorを最終errorへ接続する。
6. 最終errorを`Error_To_TestStatus.vi`へ接続する。
7. Device Name=`RAMScope`とし、Status、TestError、error outを出力する。

### 9. テスト

正常Close、既存エラー付きClose、DeviceExitエラー、二重Close、Close後の再Connectを確認する。
