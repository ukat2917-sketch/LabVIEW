# RAMScopeロギング取得VI 現行API改訂案

**作成日：2026-07-22**  
**状態：関数宣言確認済み、Packet配置は実機確認待ち**

本書は、RAMScopeVP APIマニュアルの測定データ取得APIをLabVIEWへ実装するためのレビュー用改訂案である。

記述は次の正本へ従う。

- `00A_LabVIEW実装資料の記述ルール.md`
- `00B_LabVIEW学習型VI設計ルール.md`

正式統合後は`10_RAMScope実装方針.md`だけを正本とし、本書は削除する。

---

## 0. 今回の訂正

`RAMScopeGT150GetLoggingData()`は7引数である。

```c
long RAMScopeGT150GetLoggingData(
    long UnitNo,
    long MdlNo,
    long MeasNo,
    long BlockNo,
    void *pData,
    long *pDataNum,
    long *pLostDataNum
);
```

独立した`MaxDataNum`引数は存在しない。

最大要求Packet数は、CLFNの`pDataNum`左端子へ事前入力する。API正常終了後、同じ`pDataNum`右端子から実際に取得したPacket数を受け取る。

```text
要求Packet数 I32
  → pDataNum 左端子
  → DLL呼出し
  → pDataNum 右端子
  → 実取得Packet数 I32
```

この方式は`RAMScopeGT150GetBufferData()`も同じである。

---

## 1. 測定データ取得API監査結果

| API | 確認した関数宣言 | 判定 |
|---|---|---|
| `RAMScopeGT150GetGapTime` | `long (long UnitNo, unsigned long *pGapTime)` | 一致 |
| `RAMScopeGT150GetMeasNum` | `long (long UnitNo, long *pMeasNum)` | 一致 |
| `RAMScopeGT150GetBlockNum` | `long (long UnitNo, long MeasNo, long *pBlockNum)` | 一致 |
| `RAMScopeGT150GetBufferDataNum` | `long (long UnitNo, long MdlNo, long *pDataNum)` | 一致 |
| `RAMScopeGT150GetBufferData` | `long (long UnitNo, long MdlNo, void *pData, long *pDataNum, long *pLostDataNum)` | 一致 |
| `RAMScopeGT150GetLoggingDataNum` | `long (long UnitNo, long MdlNo, long MeasNo, long BlockNo, long *pDataNum)` | 一致 |
| `RAMScopeGT150GetLoggingData` | `long (long UnitNo, long MdlNo, long MeasNo, long BlockNo, void *pData, long *pDataNum, long *pLostDataNum)` | 一致 |
| `RAMScopeGT150MemoryRead` | `long (long UnitNo, long MdlNo, unsigned long Address, long Size, long Count, char *Buffer, long Tmout)` | 一致。ロギング取得とは別機能 |

リポジトリ内の`docs/reference/RAMScopeVP.h`および`docs/reference/samp_simple.cpp`は、上記7引数形式と一致する。

---

## 2. ロギング取得処理の責務分離

### 2.1 測定中の最新データ

```text
RAMScopeGT150GetBufferDataNum()
  → 現在API内部バッファにあるPacket数

RAMScopeGT150GetBufferData()
  → 測定中の最新データを取得
```

### 2.2 測定停止後の保存ログ

```text
RAMScopeGT150GetMeasNum()
  → 測定回数

RAMScopeGT150GetBlockNum()
  → 指定MeasNoのBlock数

RAMScopeGT150GetLoggingDataNum()
  → 指定MeasNo、BlockNo、MdlNoの保存Packet数

RAMScopeGT150GetLoggingData()
  → 指定Blockの保存Packet本体
```

測定中の最新値取得と測定停止後の保存ログ取得を同じ公開API VIへ混在させない。

---

## 3. 追加する薄いDLLラッパVI

```text
RS_DLL_GT150GetGapTime.vi
RS_DLL_GT150GetMeasNum.vi
RS_DLL_GT150GetBlockNum.vi
RS_DLL_GT150GetBufferDataNum.vi
RS_DLL_GT150GetLoggingDataNum.vi
RS_DLL_GT150GetLoggingData.vi
```

既存の`RS_DLL_GT150GetBufferData.vi`は、`pDataNum`を入出力として扱うことを明記して改訂する。

全Wrapperは、C関数1個をCLFNで1回だけ呼ぶ。

---

# 4. 件数取得Wrapper共通設計

対象：

```text
RS_DLL_GT150GetMeasNum.vi
RS_DLL_GT150GetBlockNum.vi
RS_DLL_GT150GetBufferDataNum.vi
RS_DLL_GT150GetLoggingDataNum.vi
```

## 4.0 実現したい機能とVIの責務

C APIがPointerへ返す件数をI32表示器へ取り出し、API ReturnCodeを標準error clusterへ変換する。

## 4.1 入力データの実体

すべての件数Pointerは`long *`である。

Windows版APIの`long`は32bitなので、LabVIEWではI32の`Pointer to Value`を使用する。

## 4.2 出力データモデル

```text
件数 I32
API ReturnCode I32
error out error cluster
```

## 4.3 前提条件・異常条件

- `error in.status=True`ならCLFNを呼ばない。
- バイパス時の件数はI32 0。
- API ReturnCodeが0以外なら`RAMScope_Code_To_Error.vi`でエラー化する。
- 公開API側で負数件数を検出し、後続Loopや配列確保を停止する。

## 4.4 処理アルゴリズム

```text
既存エラーあり
  → 件数0、ReturnCode 0、元errorを返す

既存エラーなし
  → Pointer左端子へI32 0
  → CLFNを1回呼ぶ
  → Pointer右端子から件数を取得
  → ReturnCodeとCLFN errorを標準errorへ変換
```

## 4.5 LabVIEW構造の選定理由

既存エラー時にDLL呼出しを止めるため、`error in.status`をselectorとするケースストラクチャ（Case Structure）を使用する。

## 4.6 共通入出力

| 端子名 | 方向 | 型 | 用途 |
|---|---|---|---|
| `error in` | 入力 | error cluster | 前段エラー |
| 件数出力 | 出力 | I32 | APIから受け取った件数 |
| `API ReturnCode` | 出力 | I32 | C API戻り値 |
| `error out` | 出力 | error cluster | 変換後エラー |

各VI固有のValue入力はCプロトタイプ順に追加する。

## 4.7 CLFN Parameters

### `RS_DLL_GT150GetMeasNum.vi`

| 順番 | 名前 | Type | Data Type | Pass |
|---:|---|---|---|---|
| Return | 戻り値 | Numeric | Signed 32-bit Integer | Value |
| 1 | `UnitNo` | Numeric | Signed 32-bit Integer | Value |
| 2 | `pMeasNum` | Numeric | Signed 32-bit Integer | Pointer to Value |

### `RS_DLL_GT150GetBlockNum.vi`

| 順番 | 名前 | Type | Data Type | Pass |
|---:|---|---|---|---|
| Return | 戻り値 | Numeric | Signed 32-bit Integer | Value |
| 1 | `UnitNo` | Numeric | Signed 32-bit Integer | Value |
| 2 | `MeasNo` | Numeric | Signed 32-bit Integer | Value |
| 3 | `pBlockNum` | Numeric | Signed 32-bit Integer | Pointer to Value |

### `RS_DLL_GT150GetBufferDataNum.vi`

| 順番 | 名前 | Type | Data Type | Pass |
|---:|---|---|---|---|
| Return | 戻り値 | Numeric | Signed 32-bit Integer | Value |
| 1 | `UnitNo` | Numeric | Signed 32-bit Integer | Value |
| 2 | `MdlNo` | Numeric | Signed 32-bit Integer | Value |
| 3 | `pDataNum` | Numeric | Signed 32-bit Integer | Pointer to Value |

### `RS_DLL_GT150GetLoggingDataNum.vi`

| 順番 | 名前 | Type | Data Type | Pass |
|---:|---|---|---|---|
| Return | 戻り値 | Numeric | Signed 32-bit Integer | Value |
| 1 | `UnitNo` | Numeric | Signed 32-bit Integer | Value |
| 2 | `MdlNo` | Numeric | Signed 32-bit Integer | Value |
| 3 | `MeasNo` | Numeric | Signed 32-bit Integer | Value |
| 4 | `BlockNo` | Numeric | Signed 32-bit Integer | Value |
| 5 | `pDataNum` | Numeric | Signed 32-bit Integer | Pointer to Value |

## 4.8 配線順

### Trueケース（error in.status=True：既存エラーあり）

1. CLFNを配置しない。
2. 件数出力へI32定数`0`を接続する。
3. `API ReturnCode`へI32定数`0`を接続する。
4. 元の`error in`を`error out`へ接続する。

### Falseケース（error in.status=False：既存エラーなし）

1. Value引数をCプロトタイプ順にCLFNへ接続する。
2. 件数Pointerの左端子へI32定数`0`を接続する。
3. Pointer右端子を件数表示器へ接続する。
4. CLFN戻り値を`API ReturnCode`へ分岐する。
5. CLFN戻り値を`RAMScope_Code_To_Error.vi / API ReturnCode`へ接続する。
6. CLFNの`error out`を同SubVIの`error in`へ接続する。
7. 各API名の全文を`Function Name`へ接続する。
8. 同SubVIの`error out`を本VIの`error out`へ接続する。

## 4.9 単体テスト

- 既存エラー時にCLFN未実行。
- 正常時に件数が純正RAMScopeVP表示と一致。
- MeasNo=-1、MeasNo=MeasNum、BlockNo=-1、BlockNo=BlockNumでAPIエラーを確認。
- 返却件数0を正常として扱えることを確認。

---

# 5. `RS_DLL_GT150GetLoggingData.vi`

## 5.0 実現したい機能とVIの責務

指定した測定番号とロギングブロック番号の保存Packetを、RAMScopeVP API内部バッファからU8一次元配列へコピーする。

本VIはPacket解析を行わない。

## 5.1 入力データの実体

```c
long RAMScopeGT150GetLoggingData(
    long UnitNo,
    long MdlNo,
    long MeasNo,
    long BlockNo,
    void *pData,
    long *pDataNum,
    long *pLostDataNum
);
```

`pDataNum`は入出力である。

```text
左端子：要求Packet数
右端子：実際に読み出したPacket数
```

`pLostDataNum`は、測定中に保存用データバッファがあふれた場合に破棄されたPacket数を返す。累積か差分かはマニュアル記載だけでは断定せず、実機確認項目とする。

## 5.2 出力データモデル

```text
Allocated Raw Buffer U8[]
RequestedDataNum I32
DataNum I32
LostDataNum I32
API ReturnCode I32
error out error cluster
```

## 5.3 前提条件・異常条件

- `RequestedDataNum > 0`
- `Buffer Byte Size > 0`
- `Buffer Byte Size`と確保配列要素数が一致
- `error in.status=True`ならCLFNを呼ばない
- 戻り値は`0 <= DataNum <= RequestedDataNum`

## 5.4 処理アルゴリズム

```text
U8 0をBuffer Byte Size個並べた配列を作る
RequestedDataNumをpDataNum左端子へ接続する
I32 0をpLostDataNum左端子へ接続する
CLFNを1回呼ぶ
pData右端子から配列を受け取る
pDataNum右端子からDataNumを受け取る
pLostDataNum右端子からLostDataNumを受け取る
ReturnCodeをerror clusterへ変換する
```

## 5.5 LabVIEW構造の選定理由

- 既存エラー時にDLLを呼ばないためCase Structureを使用する。
- Cへ書込先メモリを渡すため配列初期化（Initialize Array）を使用する。
- 件数入出力にはI32のPointer to Valueを使用する。

## 5.6 入出力

| 端子名 | 方向 | 型 | 用途 |
|---|---|---|---|
| `UnitNo` | 入力 | I32 | 現仕様では0 |
| `MdlNo` | 入力 | I32 | 対象モジュール番号 |
| `MeasNo` | 入力 | I32 | 0からMeasNum-1 |
| `BlockNo` | 入力 | I32 | 0からBlockNum-1 |
| `RequestedDataNum` | 入力 | I32 | pDataNum左端子へ渡す要求Packet数 |
| `Buffer Byte Size` | 入力 | I32 | U8配列の事前確保要素数 |
| `error in` | 入力 | error cluster | 前段エラー |
| `Allocated Raw Buffer` | 出力 | U8一次元配列 | DLL書込後の確保配列 |
| `DataNum` | 出力 | I32 | 実取得Packet数 |
| `LostDataNum` | 出力 | I32 | 破棄Packet数 |
| `API ReturnCode` | 出力 | I32 | C API戻り値 |
| `error out` | 出力 | error cluster | 変換後エラー |

## 5.7 配置する関数およびSubVI

| 数 | 日本語名 | 英語名 | 配置場所・追加方法 |
|---:|---|---|---|
| 1 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 1 | 配列初期化 | Initialize Array | プログラミング → 配列 |
| 1 | ライブラリ関数呼び出しノード | Call Library Function Node | 接続 → ライブラリ＆実行可能ファイル |
| 1 | `RAMScope_Code_To_Error.vi` | SubVI | RAMScope共通VIフォルダ |
| 1 | U8定数0 | U8 Numeric Constant | プログラミング → 数値 |
| 2 | I32定数0 | I32 Numeric Constant | プログラミング → 数値 |

## 5.8 CLFN Parameters

| 順番 | 名前 | Type | Data Type | Dimensions | Array Format / Pass |
|---:|---|---|---|---:|---|
| Return | 戻り値 | Numeric | Signed 32-bit Integer | - | Value |
| 1 | `UnitNo` | Numeric | Signed 32-bit Integer | - | Value |
| 2 | `MdlNo` | Numeric | Signed 32-bit Integer | - | Value |
| 3 | `MeasNo` | Numeric | Signed 32-bit Integer | - | Value |
| 4 | `BlockNo` | Numeric | Signed 32-bit Integer | - | Value |
| 5 | `pData` | Array | Unsigned 8-bit Integer | 1 | Array Data Pointer |
| 6 | `pDataNum` | Numeric | Signed 32-bit Integer | - | Pointer to Value |
| 7 | `pLostDataNum` | Numeric | Signed 32-bit Integer | - | Pointer to Value |

Function Name：`RAMScopeGT150GetLoggingData`

Calling Convention：`C`

## 5.9 配線順

### Trueケース（error in.status=True：既存エラーあり）

1. 空のU8一次元配列を`Allocated Raw Buffer`へ接続する。
2. I32定数`0`を`DataNum`へ接続する。
3. I32定数`0`を`LostDataNum`へ接続する。
4. I32定数`0`を`API ReturnCode`へ接続する。
5. 元の`error in`を`error out`へ接続する。
6. CLFNを呼ばない。

### Falseケース（error in.status=False：既存エラーなし）

1. U8定数`0`を配列初期化（Initialize Array）の`element`へ接続する。
2. `Buffer Byte Size`を同関数の`dimension size`へ接続する。
3. Initialize Array出力を`Allocated Buffer Before Call`として扱う。
4. `UnitNo`、`MdlNo`、`MeasNo`、`BlockNo`をCLFN引数1から4へ順に接続する。
5. `Allocated Buffer Before Call`をCLFNの`pData`左端子へ接続する。
6. `RequestedDataNum`をCLFNの`pDataNum`左端子へ接続する。
7. I32定数`0`をCLFNの`pLostDataNum`左端子へ接続する。
8. `error in`をCLFNの`error in`へ接続する。
9. CLFNの`pData`右端子を`Allocated Raw Buffer`へ接続する。
10. CLFNの`pDataNum`右端子を`DataNum`へ接続する。
11. CLFNの`pLostDataNum`右端子を`LostDataNum`へ接続する。
12. CLFN戻り値を`API ReturnCode`へ分岐する。
13. CLFN戻り値とCLFN errorを`RAMScope_Code_To_Error.vi`へ接続する。
14. 文字列定数`RAMScopeGT150GetLoggingData`を`Function Name`へ接続する。
15. 同SubVIの`error out`を本VIの`error out`へ接続する。

## 5.10 単体テスト

- 既存エラー時にCLFN未実行。
- RequestedDataNum=1でDataNumが0または1。
- RequestedDataNum=GetLoggingDataNum出力で全Packetを取得。
- `DataNum <= RequestedDataNum`。
- LostDataNum非ゼロをそのまま保持。
- MeasNoまたはBlockNo不正時にAPIエラーを保持。

---

# 6. `RS_DLL_GT150GetBufferData.vi`の訂正

Cプロトタイプ：

```c
long RAMScopeGT150GetBufferData(
    long UnitNo,
    long MdlNo,
    void *pData,
    long *pDataNum,
    long *pLostDataNum
);
```

既存資料の`Max DataNum`入力は、DLLの独立引数ではない。

公開APIから受け取った要求件数を、Wrapper内部で`pDataNum`左端子へ接続するための入力名として使用する。

推奨端子名は、誤解を避けるため次へ変更する。

```text
旧：Max DataNum
新：RequestedDataNum
```

CLFN Parametersは5引数である。

| 順番 | 名前 | Type | Data Type | Dimensions | Array Format / Pass |
|---:|---|---|---|---:|---|
| Return | 戻り値 | Numeric | Signed 32-bit Integer | - | Value |
| 1 | `UnitNo` | Numeric | Signed 32-bit Integer | - | Value |
| 2 | `MdlNo` | Numeric | Signed 32-bit Integer | - | Value |
| 3 | `pData` | Array | Unsigned 8-bit Integer | 1 | Array Data Pointer |
| 4 | `pDataNum` | Numeric | Signed 32-bit Integer | - | Pointer to Value |
| 5 | `pLostDataNum` | Numeric | Signed 32-bit Integer | - | Pointer to Value |

---

# 7. `RAMScope_Read_Logging_Block.vi`

## 7.0 実現したい機能とVIの責務

指定したMeasNoとBlockNoの保存Packet数を取得し、必要なU8配列を確保して保存データを読み込み、実取得Packet数だけをParserへ渡す。

## 7.1 入力データの実体

```text
GetLoggingDataNum出力
  → AvailableDataNum
  → RequestedDataNumとしてGetLoggingDataのpDataNum左端子へ入力
```

Packet Sizeは既存Parserの定義に従い、暫定的に次とする。

```text
Packet Size = ChNum × 4 + 12
```

ただし、Channel、Flag、Timestampの格納順は今回提示された関数仕様ページには記載されていない。Packetフォーマット章または実機Rawデータで確認するまで、既存Parserの並びを確定情報として扱わない。

## 7.2 出力データモデル

```text
AvailableDataNum I32
RequestedDataNum I32
DataNum I32
LostDataNum I32
Raw Buffer U8[]
Packets RAMScope_Packet.ctl[]
Parsed Packet Count I32
Unused Byte Count I32
Status
TestError
error out
```

## 7.3 前提条件・異常条件

```text
ChNum >= 1
MeasNo >= 0
BlockNo >= 0
AvailableDataNum >= 0
Required Bytes > 0
Required Bytes <= Max Buffer Bytes
Required Bytes <= 2147483647
0 <= DataNum <= RequestedDataNum
```

`AvailableDataNum=0`は正常な空Blockとする。

## 7.4 処理アルゴリズム

```text
ChNumを求める
入力値を検証する
GetLoggingDataNumを呼ぶ
AvailableDataNumが0なら空出力
AvailableDataNumが正ならRequestedDataNumへ設定
I64でRequired Bytesを計算する
上限内ならGetLoggingDataを呼ぶ
DataNumの範囲を検証する
Actual Byte Count = DataNum × Packet Size
Raw配列をActual Byte Countへ切り詰める
ParserでDataNum Packetを解析する
最終errorをStatusとTestErrorへ変換する
```

GetLoggingDataには開始位置またはOffset引数がない。1Blockを複数回へ分割取得できるかは未確認である。

したがって初期実装では、`RequestedDataNum=AvailableDataNum`として1回でBlock全体を取得する。必要バッファが上限を超えた場合は処理を止め、同APIの分割取得動作を実機またはベンダーへ確認する。

## 7.5 LabVIEW構造の選定理由

- 不正入力時にDLL呼出しを止めるためCase Structureを使用する。
- I32オーバーフロー前に止めるため、サイズ計算は入力を先にI64へ変換する。
- 未使用の確保領域をParserへ渡さないためArray Subsetで切り詰める。
- MeasNoとBlockNoの反復はTestStandまたはPoCが管理し、本VI内にFor Loopを置かない。

## 7.6 入出力

| 端子名 | 方向 | 型 | 用途 |
|---|---|---|---|
| `UnitNo` | 入力 | I32 | 現仕様では0 |
| `MdlNo_RAM` | 入力 | I32 | RAMモジュール番号 |
| `MeasNo` | 入力 | I32 | 測定番号 |
| `BlockNo` | 入力 | I32 | ブロック番号 |
| `Channel List` | 入力 | RAMScope_Channel.ctl一次元配列 | ChNumとParser設定 |
| `Byte Order` | 入力 | RAMScope_Byte_Order.ctl | Parser設定 |
| `Max Buffer Bytes` | 入力 | I64 | 1Blockの配列確保上限 |
| `error in` | 入力 | error cluster | 前段エラー |
| `AvailableDataNum` | 出力 | I32 | 保存Packet数 |
| `DataNum` | 出力 | I32 | 実取得Packet数 |
| `LostDataNum` | 出力 | I32 | 破棄Packet数 |
| `Raw Buffer` | 出力 | U8一次元配列 | 実データ部分のみ |
| `Packets` | 出力 | RAMScope_Packet.ctl一次元配列 | Parser出力 |
| `Parsed Packet Count` | 出力 | I32 | Parser件数 |
| `Unused Byte Count` | 出力 | I32 | Parser未使用バイト数 |
| `Status` | 出力 | Status.ctl | TestStand判定 |
| `TestError` | 出力 | TestError.ctl | 詳細エラー |
| `error out` | 出力 | error cluster | 最終エラー |

## 7.7 配置する関数およびSubVI

- 配列サイズ（Array Size）
- 数値変換（To 64-bit Integer、To 32-bit Integer）
- 乗算（Multiply）
- 加算（Add）
- 部分配列（Array Subset）
- 比較関数
- 複合演算（Compound Arithmetic）
- ケースストラクチャ（Case Structure）
- `RS_DLL_GT150GetLoggingDataNum.vi`
- `RS_DLL_GT150GetLoggingData.vi`
- `RAMScope_Parse_Buffer.vi`
- `Error_To_TestStatus.vi`
- 文字列にフォーマット（Format Into String）
- 名前でバンドル（Bundle By Name）

## 7.8 配線順

1. `Channel List`を配列サイズ（Array Size）へ接続し、出力を`ChNum I32`とする。
2. `ChNum>=1`、`MeasNo>=0`、`BlockNo>=0`、`Max Buffer Bytes>0`をANDする。
3. AND出力を`Input Valid?` Caseのselectorへ接続する。
4. Falseケース（Input Valid?=False：入力不正）ではDLL WrapperとParserを呼ばず、全データ出力へ安全値を接続する。
5. Falseケースのsourceは次とする。

```text
RAMScope_Read_Logging_Block.vi: Input is invalid. ChNum=%d, MeasNo=%d, BlockNo=%d, MaxBufferBytes=%lld
```

6. Trueケース（Input Valid?=True：入力正常）で`GetLoggingDataNum`を呼ぶ。
7. 同Wrapperの`DataNum`出力を`AvailableDataNum`とする。
8. `AvailableDataNum<0`ならローカルエラーを生成する。
9. `AvailableDataNum=0`ならGetLoggingDataとParserを呼ばず、空出力と正常errorを返す。
10. `AvailableDataNum>0`なら`RequestedDataNum=AvailableDataNum`とする。
11. `ChNum`と`RequestedDataNum`を先にI64へ変換する。
12. `Packet Size I64 = ChNum I64 × 4 + 12`を計算する。
13. `Required Bytes I64 = RequestedDataNum I64 × Packet Size I64`を計算する。
14. `Required Bytes<=Max Buffer Bytes`、`Required Bytes<=2147483647`、`Required Bytes>0`をANDする。
15. Falseケース（Buffer Size Valid?=False：配列確保不可）ではGetLoggingDataとParserを呼ばず、code=`-700175`を返す。
16. Trueケース（Buffer Size Valid?=True：配列確保可能）でRequired BytesをI32へ変換する。
17. UnitNo、MdlNo_RAM、MeasNo、BlockNo、RequestedDataNum、Buffer Byte Sizeを`RS_DLL_GT150GetLoggingData.vi`へ接続する。
18. GetLoggingDataNumの`error out`をGetLoggingDataの`error in`へ接続する。
19. `DataNum>=0`と`DataNum<=RequestedDataNum`をANDする。
20. Falseケース（Returned Count Valid?=False：戻り件数不正）ではParserを呼ばず、code=`-700176`を返す。
21. Trueケース（Returned Count Valid?=True：戻り件数正常）で`Actual Byte Count=DataNum×Packet Size`をI64で計算する。
22. Actual Byte CountをI32へ変換する。
23. GetLoggingDataの`Allocated Raw Buffer`を部分配列（Array Subset）の`array`へ接続する。
24. I32定数`0`を`index`へ接続する。
25. Actual Byte Count I32を`length`へ接続する。
26. Array Subset出力を`Raw Buffer`へ接続する。
27. Raw Buffer、DataNum、Channel List、Byte Order、GetLoggingDataのerrorを`RAMScope_Parse_Buffer.vi`へ接続する。
28. ParserのPackets、Parsed Packet Count、Unused Byte Countを本VI出力へ接続する。
29. Parserの最終errorを`Error_To_TestStatus.vi`へ接続する。
30. Device Name=`RAMScope`とし、Status、TestError、error outを接続する。
31. すべてのCaseで全出力トンネルを配線し、`Use default if unwired`を使用しない。

## 7.9 単体テスト

| 条件 | 期待結果 |
|---|---|
| Channel List空 | DLL未実行、入力エラー |
| MeasNo=-1 | DLL未実行、入力エラー |
| BlockNo=-1 | DLL未実行、入力エラー |
| AvailableDataNum=0 | 正常、空配列 |
| Required Bytesが上限超過 | 配列未確保、エラー |
| DataNum=RequestedDataNum | 正常 |
| DataNumがRequestedDataNum未満 | 実DataNum分だけ切り詰める |
| DataNum<0 | Parser未実行、エラー |
| DataNum>RequestedDataNum | Parser未実行、エラー |
| LostDataNum非ゼロ | 値をそのまま出力・保存 |
| Parserバッファ不足 | Parserエラー保持 |

---

## 8. TestStandまたはPoCでの呼出し順

```text
RAMScope_Log_Stop.vi
  → RS_DLL_GT150GetGapTime.viまたは公開Summary VI
  → RS_DLL_GT150GetMeasNum.viまたは公開Summary VI
      → For MeasNo = 0 ... MeasNum-1
          → RS_DLL_GT150GetBlockNum.viまたは公開Block Count VI
              → For BlockNo = 0 ... BlockNum-1
                  → RAMScope_Read_Logging_Block.vi
                  → TDMSへBlock単位で追記
  → RAMScope_Release.vi
  → RAMScope_Close.vi
```

1Block取得後にTDMSへ追記し、次Blockへ進む。

```text
RAMScope_Meas0000_Block0000
RAMScope_Meas0000_Block0001
RAMScope_Meas0001_Block0000
```

TDMSグループプロパティ候補：

```text
GapTimeMs
MeasNo
BlockNo
AvailableDataNum
RequestedDataNum
DataNum
LostDataNum
PacketSize
A2LFileName
RAMScopeApiVersion
```

---

## 9. 実機PoC確認項目

- [ ] 全APIのCLFN引数個数と順序がマニュアルおよびヘッダと一致する
- [ ] `pDataNum`左端子の要求数がAPIへ渡る
- [ ] `pDataNum`右端子が実取得数へ更新される
- [ ] GetBufferDataNumとGetBufferDataのDataNum関係が妥当
- [ ] GetLoggingDataNumとGetLoggingDataのDataNum関係が妥当
- [ ] GetMeasNumが純正RAMScopeVP表示と一致する
- [ ] GetBlockNumが純正RAMScopeVP表示と一致する
- [ ] Packet Sizeが実Rawデータと一致する
- [ ] Channel、Flag、Timestampの格納順が既存Parserと一致する
- [ ] Timestamp換算が実時間と一致する
- [ ] LostDataNumが累積値か呼出し単位の値か確認する
- [ ] DataNum=0で正常終了する
- [ ] 1BlockがMax Buffer Bytesを超えた場合の製品仕様を確認する
- [ ] 同一Blockを複数回呼んだ場合に先頭から再取得するか、内部位置が進むか確認する
- [ ] 全Block取得後にReleaseとCloseが正常終了する

---

## 10. 正式統合時の更新箇所

1. `10_RAMScope実装方針.md`の測定データ取得Wrapper一覧を更新する。
2. `RS_DLL_GT150GetBufferData.vi`の`pDataNum`入出力説明を明確化する。
3. ロギング取得Wrapperと公開APIを第10章へ追加する。
4. Packet配置を確認後、`RAMScope_Parse_Buffer.vi`の正本定義を更新する。
5. READMEのWrapper数と公開API数を更新する。
6. 本書を削除し、第10章だけを正本にする。
