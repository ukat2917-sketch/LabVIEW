# RAMScopeロギング取得VI 現行API改訂案

**作成日：2026-07-22**  
**状態：関数宣言およびRAMモニタPacket配置確認済み。実機値照合待ち**

本書は、RAMScopeVP APIマニュアルの測定データ取得APIをLabVIEWへ実装するためのレビュー用改訂案である。

記述は次の正本へ従う。

- `00A_LabVIEW実装資料の記述ルール.md`
- `00B_LabVIEW学習型VI設計ルール.md`

正式統合後は`10_RAMScope実装方針.md`だけを正本とし、本書は削除する。

---

## 0. 確認済み仕様

### 0.1 `RAMScopeGT150GetLoggingData()`は7引数

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

独立した`MaxDataNum`引数は存在しない。要求Packet数は`pDataNum`左端子へ事前入力し、API正常終了後に同じPointerの右端子から実取得Packet数を受け取る。

```text
要求Packet数 I32
  → pDataNum左端子
  → DLL呼出し
  → pDataNum右端子
  → 実取得Packet数 I32
```

この方式は`RAMScopeGT150GetBufferData()`も同じである。

### 0.2 RAMモニタPacket配置

RAMモニタのPacket構成はGT150_IFとGT170_IFで共通である。

`RAMScopeGT150GetBufferData()`または`RAMScopeGT150GetLoggingData()`の`pData`には、次の順でPacketが連続格納される。

```text
pData U8[]
├─ Packet[0]
├─ Packet[1]
├─ ...
└─ Packet[M-1]
```

1Packetの内部配置は次である。

```text
Packet[k]
├─ Data[0]      4byte
├─ Data[1]      4byte
├─ ...
├─ Data[N-1]    4byte
├─ Flag         4byte
└─ Time         8byte
```

`N`は`RAMScopeGT1x0SetMeasCh()`で設定した測定有効チャンネル数である。Dataの並び順は`SetMeasCh()`へ設定したチャンネル順と同じである。各チャンネルの設定データサイズが1byte、2byte、4byteのどれであっても、Packet内のData領域は1チャンネル4byte固定である。

```text
Packet Size = N × 4 + 4 + 8
            = N × 4 + 12 byte
```

### 0.3 FlagとTime

```text
Flag = 4byte固定のステータス情報
Time = 測定開始を0とし、20ns周期でカウントアップする64bit値
```

秒換算は次とする。

```text
Timestamp Seconds = Time Raw U64 × 20e-9
```

### 0.4 Parserの正式Offset

既存`RAMScope_Parse_Buffer.vi`が採用する`Channel Data → Flag → Timestamp`の並びはマニュアルと一致する。

```text
Packet Start = Packet Index × Packet Size
Data Start   = Packet Start + Channel Index × 4
Flag Start   = Packet Start + N × 4
Time Start   = Flag Start + 4
```

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

すべての件数Pointerは`long *`である。Windows版APIの`long`は32bitなので、LabVIEWではI32の`Pointer to Value`を使用する。

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

指定した測定番号とロギングブロック番号の保存Packetを、RAMScopeVP API内部バッファからU8一次元配列へコピーする。本VIはPacket解析を行わない。

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

`pLostDataNum`は、測定中に保存用データバッファがあふれた場合に破棄されたPacket数を返す。累積か差分かは実機確認項目とする。

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
| `MdlNo` | 入力 | I32 | RAMモニタモジュール番号 |
| `MeasNo` | 入力 | I32 | 0からMeasNum-1 |
| `BlockNo` | 入力 | I32 | 0からBlockNum-1 |
| `RequestedDataNum` | 入力 | I32 | pDataNum左端子へ渡す要求Packet数 |
| `Buffer Byte Size` | 入力 | I32 | 事前確保するU8要素数 |
| `error in` | 入力 | error cluster | 前段エラー |
| `Allocated Raw Buffer` | 出力 | U8一次元配列 | DLL書込後の確保済み配列 |
| `DataNum` | 出力 | I32 | 実際に読み出したPacket数 |
| `LostDataNum` | 出力 | I32 | 破棄Packet数 |
| `API ReturnCode` | 出力 | I32 | API戻り値 |
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
| 1 | 空のU8一次元配列定数 | Empty U8 Array Constant | 配列枠へU8定数を配置 |

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

```text
Function Name      = RAMScopeGT150GetLoggingData
Calling Convention = C
Error Checking     = Maximum
PoC実行スレッド     = Run in UI thread
```

## 5.9 配線順

### Trueケース（error in.status=True：既存エラーあり）

1. CLFNを配置しない。
2. 空のU8一次元配列を`Allocated Raw Buffer`へ接続する。
3. I32定数0を`DataNum`へ接続する。
4. I32定数0を`LostDataNum`へ接続する。
5. I32定数0を`API ReturnCode`へ接続する。
6. 元の`error in`を`error out`へ接続する。

### Falseケース（error in.status=False：既存エラーなし）

1. U8定数0を配列初期化（Initialize Array）の`element`へ接続する。
2. `Buffer Byte Size` I32を同関数の`dimension size`へ接続する。
3. Initialize Array出力を`Allocated Buffer Before Call`として扱う。
4. `UnitNo`をCLFN引数1へ接続する。
5. `MdlNo`をCLFN引数2へ接続する。
6. `MeasNo`をCLFN引数3へ接続する。
7. `BlockNo`をCLFN引数4へ接続する。
8. `Allocated Buffer Before Call`をCLFNの`pData`左端子へ接続する。
9. `RequestedDataNum`をCLFNの`pDataNum`左端子へ接続する。
10. I32定数0をCLFNの`pLostDataNum`左端子へ接続する。
11. `error in`をCLFNの`error in`へ接続する。
12. CLFNの`pData`右端子を`Allocated Raw Buffer`へ接続する。
13. CLFNの`pDataNum`右端子を`DataNum`へ接続する。
14. CLFNの`pLostDataNum`右端子を`LostDataNum`へ接続する。
15. CLFN戻り値を`API ReturnCode`へ分岐する。
16. CLFN戻り値を`RAMScope_Code_To_Error.vi / API ReturnCode`へ接続する。
17. 文字列定数`RAMScopeGT150GetLoggingData`を`Function Name`へ接続する。
18. CLFNの`error out`を同SubVIの`error in`へ接続する。
19. 同SubVIの`error out`を本VIの`error out`へ接続する。

## 5.10 単体テスト

| 条件 | 期待結果 |
|---|---|
| 既存エラーあり | CLFN未実行、空Raw、DataNum=0、Lost=0、元エラー保持 |
| RequestedDataNum=1 | 1Packet以下を取得 |
| DataNum=RequestedDataNum | 正常 |
| DataNumがRequestedDataNum未満 | 公開APIで実データ長へ切り詰め可能 |
| DataNum=0 | 正常な空実データとして処理可能 |
| LostDataNum非ゼロ | 値をそのまま上位へ返す |
| MeasNoまたはBlockNo不正 | APIエラーを保持 |

---

# 6. `RAMScope_Parse_Buffer.vi`への確定反映

## 6.0 入力データの実体

```text
Raw Buffer U8[]
├─ Packet[0]
│  ├─ Data[0]      4byte
│  ├─ ...
│  ├─ Data[N-1]    4byte
│  ├─ Flag         4byte
│  └─ Time         8byte
├─ Packet[1]
└─ ...
```

## 6.1 サイズとOffset

```text
Packet Size         = ChNum × 4 + 12
Expected Byte Count = DataNum × Packet Size

Packet Start = Packet Index × Packet Size
Data Start   = Packet Start + Channel Index × 4
Flag Start   = Packet Start + ChNum × 4
Time Start   = Flag Start + 4
```

## 6.2 Time解析

1. `Time Start`から8byteを部分配列（Array Subset）で切り出す。
2. `U8x8_To_U64.vi`へ接続し、`Time Raw` U64を得る。
3. Time RawをDBLへ変換する。
4. DBL定数`20e-9`を乗算し、`Timestamp Seconds`を得る。

## 6.3 Parser単体テスト

2チャンネル、1PacketのLittle Endianデータ：

```text
Data[0]   = 01 00 00 00
Data[1]   = FE FF FF FF
Flag      = A5 00 00 00
Time      = 32 00 00 00 00 00 00 00
```

期待結果：

```text
Data[0] Raw         = 1
Data[1] Raw         = -2、Sign設定に従う
Flag                = 0x000000A5
Time Raw            = 50
Timestamp Seconds   = 0.000001
Parsed Packet Count = 1
Unused Byte Count   = 0
```

---

# 7. `RAMScope_Read_Logging_Block.vi`

## 7.0 実現したい機能とVIの責務

指定したMeasNoとBlockNoの保存Packet数を取得し、必要なU8配列を確保して保存データを読み込み、実取得Packet数だけを既存Parserで解析する。

## 7.1 処理アルゴリズム

```text
ChNum = Array Size(Channel List)
Packet Size = ChNum × 4 + 12

AvailableDataNum = GetLoggingDataNum()

AvailableDataNumが0なら
  空データを正常として返す
else
  Required Bytes = AvailableDataNum × Packet Size
  メモリ上限を検証する
  RequestedDataNum = AvailableDataNum
  GetLoggingDataを呼ぶ
  DataNumの範囲を検証する
  Actual Bytes = DataNum × Packet Size
  Raw BufferをActual Bytesへ切り詰める
  ParserでDataNum Packetを解析する
end
```

## 7.2 重要な検証

- サイズ計算は入力を先にI64へ変換してから行う。
- `Required Bytes > 0`を確認する。
- `Required Bytes <= Max Buffer Bytes`を確認する。
- `Required Bytes <= 2147483647`を確認してからI32へ変換する。
- `0 <= DataNum <= RequestedDataNum`を確認する。
- `Parsed Packet Count == DataNum`を確認する。
- 全Caseの全出力トンネルを配線する。
- `Use default if unwired`を使用しない。

## 7.3 TDMS保存

1Block取得後、次Blockへ進む前にTDMSへ追記する。

```text
RAMScope_Meas0000_Block0000
RAMScope_Meas0000_Block0001
RAMScope_Meas0001_Block0000
```

グループプロパティ候補：

```text
GapTimeMs
MeasNo
BlockNo
RequestedDataNum
DataNum
LostDataNum
PacketSize
MeasurementStartTime
A2LFileName
```

---

# 8. TestStandまたはPoCでの呼出し順

```text
RAMScope_Connect.vi
  → RAMScope_Init.vi
  → RAMScope_Set_Cond.vi
  → RAMScope_Log_Start.vi
  → 試験実行・Wait
  → RAMScope_Log_Stop.vi
  → RAMScope_Get_Log_Summary.vi
      └─ MeasNum
          → For MeasNo = 0 ... MeasNum-1
              → RAMScope_Get_Block_Count.vi
                  └─ BlockNum
                      → For BlockNo = 0 ... BlockNum-1
                          → RAMScope_Read_Logging_Block.vi
                          → TDMSへBlock単位で追記
  → RAMScope_Release.vi
  → RAMScope_Close.vi
```

---

# 9. 実機PoC確認項目

関数宣言とPacket配置はマニュアル確認済みである。実機PoCでは実値と動作を確認する。

- [ ] GetMeasNumが純正RAMScopeVP表示と一致する
- [ ] 各MeasNoのGetBlockNumが純正表示と一致する
- [ ] GetLoggingDataNumとGetLoggingDataのDataNumが一致する
- [ ] DataNumがRequestedDataNum以下である
- [ ] Data順がSetMeasCh順と一致する
- [ ] 1byte／2byte設定チャンネルもPacket内で4byteスロットを使用する
- [ ] 符号付き1byte／2byte値の上位バイトが符号拡張かゼロ埋めかを確認する
- [ ] Flag位置が`Packet Start + ChNum×4`と一致する
- [ ] Time位置が`Flag Start + 4`と一致する
- [ ] Time差分×20nsが実測時間と一致する
- [ ] LostDataNumの増加条件と呼出しごとの差分／累積を確認する
- [ ] DataNum=0で正常終了する
- [ ] 大容量BlockでMax Buffer Bytesガードが動く
- [ ] 全Block取得後のReleaseとCloseが正常終了する

---

# 10. 残課題

1. Flagの各bit定義を`RAMScope_Packet.ctl`へ展開するか、U32 Rawのまま保持するか決める。
2. 1byte／2byte符号付きデータの上位24bit／16bitの格納規則を実機で確認する。
3. LostDataNumがAPI呼出し単位の値か累積値かを実機で確認する。
4. 実機PoC後、第10章へ統合して本Draftを削除する。
