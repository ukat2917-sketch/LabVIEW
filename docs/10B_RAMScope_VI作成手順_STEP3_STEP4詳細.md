# 10B. RAMScope VI実装手順：DLLラッパ → 公開API → 最小PoC

> **本章の役割**： [10A](./10A_RAMScope実装手順_DLL準備とCLFN疎通確認.md) でDLL疎通を確認した後、
> RAMScope単体の最小PoCを完成させるまでのVI作成順序を定義する。
>
> 関数プロトタイプ、構造体、定数は [10](./10_RAMScope実装方針.md) とメーカー提供ヘッダを正とする。
> CAN実装方針は [09](./09_CAN通信の実装.md)、TestStandへの配置は [11](./11_TestStandシーケンス構築手順.md) を参照する。

**最終整理日：2026-07-14**

---

## 10B.1 今回採用する実装順序

RAMScopeは最初からTestStandへ組み込まない。次の順で段階的に確認する。

```text
10A：DLL配置・x64疎通確認
  ↓
Layer 1：1関数1VIの薄いDLLラッパを作成
  ↓
Layer 2：共通エラー変換・構造体生成・Parserを作成
  ↓
Layer 3：複数のDLLラッパをつないだ公開APIを作成
  ↓
PoC_RAMScope_Main.viでRAM計測単体の通し確認
  ↓
RAM計測PoC完了
  ↓
CAN方式を確定し、必要なCANモジュール用VIを作成
  ↓
RAM/CAN単体PoC完了
  ↓
TestStandから公開APIを呼び出す
```

### 重要な修正点

添付フローを実際のベンダーサンプルの呼び出し順へ合わせるため、次を反映する。

1. `RAMScope_Init.vi`と`RAMScope_Log_Start.vi`の間に、**`RAMScope_Set_Cond.vi`を必須工程として追加**する。
   - `SetMeasCond`
   - `SetMeasCh`
   - `SetLoggingInfo`
2. `RAMScope_Connect.vi`はデバイスをオープンして`UnitNum`と`kind`を取得するVIであり、
   **DLLがネイティブなSessionハンドルを生成するわけではない**。
3. `ReleaseBufferData`は正式な必須条件が未確認のため、当面は`RAMScope_Read.vi`へ内包しない。
   **独立VIとして作成し、PoCで呼ぶ／呼ばないを比較可能にする**。
4. TestStandはRAMScope単体PoCとCAN単体PoCが完了してから着手する。

---

## 10B.2 レイヤ構成

### 10B.2.1 推奨フォルダ

```text
30_RAMScope\
├─ 00_Common\
│  ├─ RAMScope_Code_To_Error.vi
│  ├─ RAMScope_Channel.ctl
│  └─ RAMScope_Context.ctl               （任意。PoC後に採用判断）
│
├─ 10_DLL_Wrapper\
│  ├─ RS_DLL_GT150DeviceInit.vi
│  ├─ RS_DLL_GT150DeviceExit.vi
│  ├─ RS_DLL_GT150AllInit.vi
│  ├─ RS_DLL_GT150GetSysInfo.vi
│  ├─ RS_DLL_GT150PGT_SetMdlConfig.vi
│  ├─ RS_DLL_GT170SetMeasCond.vi
│  ├─ RS_DLL_GT170SetMeasCh.vi
│  ├─ RS_DLL_GT150SetLoggingInfo.vi
│  ├─ RS_DLL_GT150MeasStart.vi
│  ├─ RS_DLL_GT150GetBufferData.vi
│  ├─ RS_DLL_GT150ReleaseBufferData.vi
│  └─ RS_DLL_GT150MeasStop.vi
│
├─ 20_Parser\
│  ├─ Parse_SYSINFO_Array.vi
│  └─ RAMScope_Parse_Buffer.vi
│
├─ 30_Public\
│  ├─ RAMScope_Connect.vi
│  ├─ RAMScope_Init.vi
│  ├─ RAMScope_Set_Cond.vi
│  ├─ RAMScope_Log_Start.vi
│  ├─ RAMScope_Read.vi
│  ├─ RAMScope_Release.vi                 （実験用。必須性確認後に確定）
│  ├─ RAMScope_Log_Stop.vi
│  └─ RAMScope_Close.vi
│
├─ 40_PoC\
│  └─ PoC_RAMScope_Main.vi
│
├─ 50_CAN\                              （RAM計測PoC後に作成）
└─ 90_TestStand\                        （RAM/CAN PoC後に必要時作成）
```

### 10B.2.2 レイヤごとの責務

| レイヤ | 責務 | やってはいけないこと |
|--------|------|----------------------|
| DLLラッパ | CLFNでDLL関数を1個だけ呼ぶ | 複数APIの順序制御、Parser、TestStand判定 |
| Common / Parser | APIコード変換、構造体生成、生バイト解析 | DLLの直接呼び出し、機器状態遷移 |
| 公開API | DLLラッパとParserを接続し、1イベントを完結させる | TestStand固有変数への直接依存 |
| PoC | 公開APIを順番に呼び、実機単体で通し確認する | 本番試験ロジックを作り込む |
| CAN | 採用したCAN方式の薄いラッパ・公開API・単体PoC | 方式未決定のまま全候補を量産する |
| TestStand | 条件、順序、ループ、待ち、分岐、レポート、Cleanup | DLLラッパを直接呼ぶ |

---

## 10B.3 全VIの共通ルール

### 10B.3.1 DLLラッパの標準入出力

DLLラッパは原則として次を持つ。

| 端子 | 型 | 用途 |
|------|----|------|
| API引数 | ヘッダに対応した型 | `UnitNo`、`MdlNo`、配列等 |
| `error in` | error cluster | 前段エラー |
| API出力 | ヘッダに対応した型 | `UnitNum`、`kind`、`DataNum`等 |
| `API ReturnCode` | I32 | DLLの戻り値をそのまま保持 |
| `error out` | error cluster | CLFNエラーとAPIコード変換後のエラー |

DLLラッパでは`Status.ctl`と`TestError.ctl`を作らない。これらは公開APIの最後で一度だけ作る。

### 10B.3.2 DLLラッパの内部構成

```text
error in
  → Case Structure
      ├─ errorあり：通常はCLFNを呼ばず、そのまま伝播
      └─ errorなし：CLFNを1個実行
           → API ReturnCode
           → RAMScope_Code_To_Error.vi
           → error out
```

`RS_DLL_GT150DeviceExit.vi`だけはCleanup用のため、前段エラーがあっても実行できる構成にする。
元エラーと終了エラーの統合は公開APIの`RAMScope_Close.vi`で行う。

### 10B.3.3 CLFN共通設定

| 項目 | 設定 |
|------|------|
| DLL | `RAMScopeVP_API_x64.dll` |
| Calling Convention | C |
| Thread | PoC中は`Run in UI thread` |
| Error checking | PoC中は`Maximum` |
| Cの`long` | I32 |
| `unsigned long` / `DWORD` | U32 |
| `long *` | I32 / Pointer to Value |
| 構造体 | U8配列を事前確保してArray Data Pointer |
| 数値配列 | 対応型の配列を事前確保してArray Data Pointer |

### 10B.3.4 公開APIの共通出力

| 端子 | 型 | 用途 |
|------|----|------|
| `実行結果ステータス` | `Status.ctl` | TestStandの継続・中断判定 |
| `エラー情報` | `TestError.ctl` | 機器名、コード、メッセージ、時刻 |
| `error out` | error cluster | 後段VIへの標準エラー伝播 |
| `API ReturnCode` | I32または配列 | PoC・ログ用。公開継続はPoC後に判断 |

公開APIの最後で`Error_To_TestStatus.vi`を1回だけ呼び、機器名に`RAMScope`を渡す。

---

# STEP 1：共通エラー変換を作成する

## 10B.4 `RAMScope_Code_To_Error.vi`

RAMScope APIの戻り値を標準error clusterへ変換する。

### 入出力

| 端子 | 方向 | 型 |
|------|------|----|
| `API ReturnCode` | 入力 | I32 |
| `Function Name` | 入力 | String |
| `error in` | 入力 | error cluster |
| `error out` | 出力 | error cluster |

### ロジック

1. `error in.status=True`なら元エラーを変更せず出力する。
2. `API ReturnCode == 0`なら正常クラスタを出力する。
3. 0以外なら次を作成する。

```text
status = True
code   = API ReturnCode
source = "RAMScope <Function Name> failed. ReturnCode=0xXXXXXXXX (<decimal>)"
```

16進表示はI32をU32へType Castし、`Format Into String`の`%08X`で整形する。

> `0x30100001`の正式名称は未確認だが、戻り値0以外はベンダーサンプル上で失敗扱いである。
> 正式な名称・対処方法はエラーコード表またはベンダー回答を入手後にマッピングへ追加する。

---

# STEP 2：薄いDLLラッパを作成する

## 10B.5 DLLラッパ一覧

| VI | DLL関数 | 主なCLFN設定 |
|----|---------|--------------|
| `RS_DLL_GT150DeviceInit.vi` | `RAMScopeGT150DeviceInit` | `pUnitNum` I32 Pointer、`kind` I32 Pointer |
| `RS_DLL_GT150DeviceExit.vi` | `RAMScopeGT150DeviceExit` | 引数なし |
| `RS_DLL_GT150AllInit.vi` | `RAMScopeGT150AllInit` | `UnitNo` I32 Value |
| `RS_DLL_GT150GetSysInfo.vi` | `RAMScopeGT150GetSysInfo` | `SYSINFO` U8[960] Pointer |
| `RS_DLL_GT150PGT_SetMdlConfig.vi` | `RAMScopeGT150PGT_SetMdlConfig` | `SlotErr` I32[16] Pointer |
| `RS_DLL_GT170SetMeasCond.vi` | `RAMScopeGT170SetMeasCond` | `MEASINFO_170` U8[72] Pointer |
| `RS_DLL_GT170SetMeasCh.vi` | `RAMScopeGT170SetMeasCh` | `CHINFO_170` U8[24×ChNum] Pointer |
| `RS_DLL_GT150SetLoggingInfo.vi` | `RAMScopeGT150SetLoggingInfo` | `LOGINFO` U8[136] Pointer |
| `RS_DLL_GT150MeasStart.vi` | `RAMScopeGT150MeasStart` | `UnitNo` I32 Value |
| `RS_DLL_GT150GetBufferData.vi` | `RAMScopeGT150GetBufferData` | raw U8 Pointer、`pDataNum` I32 Pointer、`pLostDataNum` I32 Pointer |
| `RS_DLL_GT150ReleaseBufferData.vi` | `RAMScopeGT150ReleaseBufferData` | `UnitNo` I32 Value |
| `RS_DLL_GT150MeasStop.vi` | `RAMScopeGT150MeasStop` | `UnitNo` I32 Value |

### 作成順序

1. 10Aで作成したDeviceInitのCLFN部分を`RS_DLL_GT150DeviceInit.vi`として保存する。
2. 同じコネクタ配置とエラー処理をテンプレート化する。
3. 引数が単純な順に作成する。

```text
DeviceExit
  → AllInit
  → MeasStart
  → MeasStop
  → ReleaseBufferData
  → GetSysInfo
  → PGT_SetMdlConfig
  → SetMeasCond
  → SetMeasCh
  → SetLoggingInfo
  → GetBufferData
```

### ラッパ単体確認

- CLFNの詳細ヘルプに意図したプロトタイプが表示されること。
- 壊れた実行矢印がないこと。
- API ReturnCodeがI32で取得できること。
- `RAMScope_Code_To_Error.vi`へ関数名を正確に渡すこと。
- ParserやTestStand用のStatus生成をラッパへ入れないこと。

---

# STEP 3：Parserと構造体生成を作成する

## 10B.6 `Parse_SYSINFO_Array.vi`

`GetSysInfo`が返すU8[960]を60バイト×16レコードとして解析する。

### 主な出力

| 出力 | 型 | 初期値 |
|------|----|--------|
| `MdlNo_RAM` | I32 | -1 |
| `MdlNo_CAN` | I32 | -1 |
| `Endian_RAM` | I32 | 0 |
| `Module List` | クラスタ配列 | 空配列 |

### SYSINFOオフセット

| フィールド | オフセット | 型 |
|-----------|-----------|----|
| `module` | 0 | I32 |
| `module_type` | 4 | I32 |
| `probe_id` | 8 | I32 |
| `interface_id` | 12 | I32 |
| `version` | 16 | I32 |
| `addinfo` | 20 | I32 |
| `endian` | 24 | I32 |
| `probe_version` | 28 | I32 |
| `security_id_req` | 32 | I32 |
| `security_id_size` | 36 | I32 |
| `flash_enable` | 40 | I32 |
| `name[16]` | 44 | U8[16] |

`module_type`の正式な値は`GTHard.h`を正とし、RAM/CANの判定値を定数またはEnumへまとめる。

## 10B.7 `RAMScope_Parse_Buffer.vi`

このVIはDLLを呼ばない純粋な変換VIにする。

### 入力例

- `Raw Buffer` U8配列
- `DataNum`
- `Channel List`
- `Endian_RAM`
- パケット長またはデータ構成情報

### 出力例

- パケット配列
- 各チャンネル値
- Flag
- Timestamp
- 解析できたパケット数
- 解析エラー位置

### 単体テスト

実機取得前に、既知のダミーバイト列を入力して次を確認する。

- 1/2/4バイト値の変換
- 符号あり／なし
- Little Endian／Big Endian
- 複数チャンネルの並び
- 不完全な末尾データの検出

実機PoCでは純正RAMScopeVPの表示値または既知RAM変数と比較し、最終的なパケット構成を確定する。

---

# STEP 4：公開APIを作成する

## 10B.8 `RAMScope_Connect.vi`

```text
RS_DLL_GT150DeviceInit.vi
  → Error_To_TestStatus.vi
```

### 役割

- RAMScopeデバイスをオープン・列挙する。
- `UnitNum`と`kind`を返す。
- DLLがSessionハンドルを返すわけではない。
- 最小PoCでは`UnitNo=0`を後続へ使用する。

10Aで作成したVIは、CLFNを`RS_DLL_GT150DeviceInit.vi`へ切り出したうえで、公開APIとして作り直す。

## 10B.9 `RAMScope_Init.vi`

```text
RS_DLL_GT150AllInit.vi
  → RS_DLL_GT150GetSysInfo.vi
  → Parse_SYSINFO_Array.vi
  → RS_DLL_GT150PGT_SetMdlConfig.vi
  → Error_To_TestStatus.vi
```

### 役割

- API・デバイス初期化
- 接続モジュールの検出
- RAM/CANモジュール番号の抽出
- RAMモジュールのEndian取得
- PGT設定適用と`SlotErr`確認

以前の`RAMScope_Config.vi`は独立公開APIにせず、今回の最小PoCでは`RAMScope_Init.vi`へ統合する。
将来、PGT設定だけを再適用する要求が出た場合にのみ分離する。

## 10B.10 `RAMScope_Set_Cond.vi`

```text
MEASINFO_170生成
  → RS_DLL_GT170SetMeasCond.vi
CHINFO_170配列生成
  → RS_DLL_GT170SetMeasCh.vi
LOGINFO生成
  → RS_DLL_GT150SetLoggingInfo.vi
  → Error_To_TestStatus.vi
```

### 役割

- 測定周期・測定単位の設定
- RAMアドレス、サイズ、符号、チャンネル数の設定
- バッファ・ログ条件の設定

### PoCで必要な入力

| 入力 | 内容 |
|------|------|
| `MdlNo_RAM` | `RAMScope_Init.vi`の出力 |
| `MeasPeri` | ベンダー仕様に合う測定周期 |
| `MeasUnit` | usec / msec等のAPI値 |
| `RAM Channel List` | 既知RAM変数のアドレス、サイズ、符号 |
| `BufferSize` | 初期PoC値 |
| `LogSize` | 初期PoC値 |

> 図のフローでは省略されていたが、ベンダーサンプルでは測定開始前にこの3設定を実行している。
> RAM値を取得する最小PoCでは省略しない。

## 10B.11 `RAMScope_Log_Start.vi`

```text
RS_DLL_GT150MeasStart.vi
  → Error_To_TestStatus.vi
```

計測開始だけを行う。待ち時間やRead回数はPoC MainまたはTestStand側で管理する。

## 10B.12 `RAMScope_Read.vi`

```text
バッファを事前確保
  → RS_DLL_GT150GetBufferData.vi
  → RAMScope_Parse_Buffer.vi
  → Error_To_TestStatus.vi
```

### 主な出力

- `Raw Buffer`
- `DataNum`
- `LostDataNum`
- 解析後のパケット・チャンネル値
- Timestamp

### 注意

- `pDataNum`には取得可能な最大パケット数を入力してから呼ぶ。
- バッファ不足にならないサイズを事前確保する。
- `LostDataNum`を毎回記録する。
- **`ReleaseBufferData`はこのVIへ内包しない**。必須性と呼び出し位置が確定するまで独立させる。

## 10B.13 `RAMScope_Release.vi`

```text
RS_DLL_GT150ReleaseBufferData.vi
  → Error_To_TestStatus.vi
```

現時点では実験用の公開APIとする。

### 確認するパターン

```text
A：Read → Release → Stop
B：Read → Stop → Release
C：Releaseを呼ばずStop → Close
```

ベンダー仕様、API戻り値、再測定可否、メモリ使用量を比較して正式な配置を決める。
決定するまで本番フローへ固定しない。

## 10B.14 `RAMScope_Log_Stop.vi`

```text
RS_DLL_GT150MeasStop.vi
  → Error_To_TestStatus.vi
```

計測停止だけを行う。

## 10B.15 `RAMScope_Close.vi`

```text
前段errorを保持
  → RS_DLL_GT150DeviceExit.viを必ず実行
  → 元エラーとDeviceExitエラーをMerge Errors
  → Error_To_TestStatus.vi
```

正常終了、異常終了を問わず最後に実行する。

---

# STEP 5：RAMScope単体の最小PoCを作成する

## 10B.16 `PoC_RAMScope_Main.vi`

### ベースラインフロー

```text
RAMScope_Connect.vi
  ↓
RAMScope_Init.vi
  ↓
RAMScope_Set_Cond.vi
  ↓
RAMScope_Log_Start.vi
  ↓
Wait（初期PoCは1秒程度）
  ↓
RAMScope_Read.vi
  ↓
RAMScope_Log_Stop.vi
  ↓
RAMScope_Close.vi
```

`RAMScope_Close.vi`は途中でエラーが発生しても実行できるよう、通常処理とは別のCleanup相当経路へ配置する。

### PoCフロントパネル

#### 入力

- DLLパスまたは固定パス確認表示
- `UnitNo`（初期値0）
- 測定周期・単位
- RAMチャンネル設定
- 最大取得パケット数
- Wait時間
- `Use ReleaseBufferData`（初期値False）

#### 出力

- 各APIのReturnCode
- `UnitNum` / `kind`
- `MdlNo_RAM` / `MdlNo_CAN` / `Endian_RAM`
- `SlotErr[]`
- `DataNum` / `LostDataNum`
- Raw Buffer
- 解析後のRAM値・Timestamp
- Status / TestError / error cluster

### Release確認を行う場合

ベースラインが成功してから、`Use ReleaseBufferData=True`のケースを追加する。
呼び出し位置はA/B試験できるよう固定せず、ケースまたは別PoC VIで比較する。

### 最小PoCの完了条件

| 項目 | 完了条件 |
|------|----------|
| 接続 | DeviceInitが0を返し、UnitNum/kindを取得できる |
| 初期化 | AllInit、GetSysInfo、PGT_SetMdlConfigが成功する |
| モジュール | RAMモジュール番号を取得できる |
| 設定 | SetMeasCond、SetMeasCh、SetLoggingInfoが成功する |
| 測定 | MeasStart → GetBufferData → MeasStopが通る |
| データ | 既知RAM変数と解析値が一致する |
| 損失 | LostDataNumを記録し、許容値を定義できる |
| 終了 | 正常・異常の両方でDeviceExitまで実行できる |
| 再実行 | PoCを繰り返して再接続・再測定できる |

### PoCで残すログ

- 実行日時
- RAMScopeVP API / DLLバージョン
- GT170型式・ファームウェア
- 各関数のReturnCode
- UnitNum / kind / SYSINFO / SlotErr
- 測定条件・チャンネル設定
- DataNum / LostDataNum
- Raw Bufferと解析値
- ReleaseBufferDataの使用有無・位置

---

# STEP 6：RAMScope CANモジュール用VIを作成する

RAM計測PoCが完了してから着手する。

## 10B.17 着手条件

- `PoC_RAMScope_Main.vi`が実機で完走する。
- RAMデータの解析が既知値と一致する。
- Start / Read / Stop / Closeを繰り返せる。
- RAMScope CAN方式を採用することが [09](./09_CAN通信の実装.md) で決定している。

## 10B.18 CAN側も同じレイヤ構造にする

```text
50_CAN\
├─ 10_DLL_Wrapper\
│  └─ RS_DLL_GT170CAN_*.vi
├─ 20_Parser\
│  └─ RAMScope_CAN_Parse_*.vi
├─ 30_Public\
│  └─ RAMScope_CAN_*.vi
└─ 40_PoC\
   └─ PoC_RAMScope_CAN_Main.vi
```

CAN関数も「1DLL関数1ラッパ → 1イベント1公開API → CAN単体PoC」の順で作る。
同じCAN IDをCANalyzer等の別送信主体と同時送信しない。

---

# STEP 7：TestStand用のインタフェースを作成する

## 10B.19 着手条件

- RAMScope RAM計測PoCが完了している。
- 採用するCAN方式の単体PoCが完了している。
- 各公開APIのコネクタペインとStatus/TestError仕様が固定されている。

## 10B.20 TestStandから呼ぶもの

TestStandは`RS_DLL_*`を直接呼ばず、`RAMScope_*`公開APIを呼ぶ。

```text
Setup
  RAMScope_Connect.vi
  RAMScope_Init.vi
  RAMScope_Set_Cond.vi

Main
  RAMScope_Log_Start.vi
  RAMScope_Read.vi（Loop / WaitはTestStand側）
  RAMScope_Log_Stop.vi

Cleanup
  RAMScope_Close.vi
```

TestStand Adapterで引数を単純化する必要がある場合だけ、`90_TestStand`へ薄い`TS_RAMScope_*.vi`を追加する。
公開APIと同じ処理を複製しない。

---

## 10B.21 現時点の残課題

| 残課題 | PoCでの扱い | 確定方法 |
|--------|-------------|----------|
| `0x30100001`の正式定義 | 未接続時の観測コードとして記録 | ベンダーエラー表・正式回答 |
| AllInit以降の通し動作 | `PoC_RAMScope_Main.vi`で検証 | GT170実機＋既知RAM変数 |
| ReleaseBufferDataの必須性 | 独立VIとしてA/B/C比較 | ベンダー仕様＋繰り返し試験 |
| Endian / Timestamp | Rawと解析値を両方保存 | SYSINFO・既知値・純正表示との比較 |
| APIスレッドセーフ性 | PoC中はUI Thread・直列実行 | ベンダー仕様または排他試験 |

未確定事項は公開API内部へ固定せず、薄いラッパと独立VIによって差し替え可能な状態を維持する。
