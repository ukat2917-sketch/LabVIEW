# RAMScopeロギング取得VI 現行API改訂案

**作成日：2026-07-22**  
**状態：実機確認待ち**

本書は、RAMScopeVP APIの現行マニュアルに記載されたロギング取得APIをLabVIEWへ実装するための改訂案である。

本リポジトリの正式な記述ルールである次の2資料へ従う。

- `00A_LabVIEW実装資料の記述ルール.md`
- `00B_LabVIEW学習型VI設計ルール.md`

正式統合前は、本書をレビュー用差分として扱う。実機でABIを確認した後、`10_RAMScope実装方針.md`のロギング取得節へ統合する。

---

## 0. 今回解決する問題

現在の第10章では、測定中の最新データ取得APIである`RAMScopeGT150GetBufferData()`を`RAMScope_Read.vi`から呼ぶ構成になっている。

一方、測定停止後にRAMScopeVP API内部の保存用データバッファからログを取得する場合は、次の階層をたどる必要がある。

```text
測定全体
  ├─ 測定番号 MeasNo 0 ... MeasNum-1
  │    ├─ ロギングブロック BlockNo 0 ... BlockNum-1
  │    │    ├─ 保存Packet数
  │    │    └─ 保存Packet本体
  │    └─ ...
  └─ ...
```

したがって、測定中の最新値取得と、測定停止後の保存ログ取得を同じVIへ混在させない。

```text
RAMScope_Read.vi
  → 測定中の最新データ取得
  → RAMScopeGT150GetBufferData()

RAMScope_Read_Logging_Block.vi
  → 測定停止後の保存ログを1ブロック取得
  → RAMScopeGT150GetLoggingDataNum()
  → RAMScopeGT150GetLoggingData()
```

保存ログはブロック単位で取得し、取得直後にTDMSへ追記する。全ブロックを1個の巨大配列へ蓄積しない。

---

## 1. 実装前のABI確認

### 1.1 現行マニュアルの関数宣言

現行マニュアルでは、`RAMScopeGT150GetLoggingData()`は`MaxDataNum`を独立引数として持つ。

```c
long RAMScopeGT150GetLoggingData(
    long UnitNo,
    long MdlNo,
    long MeasNo,
    long BlockNo,
    long MaxDataNum,
    unsigned char *pData,
    long *pDataNum,
    long *pLostDataNum
);
```

### 1.2 リポジトリ内の旧ヘッダとの差異

リポジトリ内の`docs/reference/RAMScopeVP.h`と旧サンプルは、`MaxDataNum`を持たず、`pDataNum`へ最大取得数を事前入力する旧形式になっている。

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

この差異はCLFNの引数個数とスタック配置へ直接影響する。誤った宣言で呼び出すと、LabVIEWがクラッシュする可能性がある。

### 1.3 実装開始条件

次の3点が一致するまで、`RS_DLL_GT150GetLoggingData.vi`を実機で実行しない。

1. 使用中の`RAMScopeVP_API_x64.dll`に同梱されたヘッダ。
2. 使用中のAPIユーザーズマニュアル。
3. RAMScopeVP APIの製品バージョン。

本書では、現行マニュアルの8引数形式を正式候補とする。

`GetProcAddress`やDLLエクスポート一覧では関数名しか確認できず、引数個数までは確認できない。必ず同梱ヘッダまたはDTS INSIGHTへの確認で確定する。

---

## 2. 追加するVI

### 2.1 薄いDLLラッパ

```text
RS_DLL_GT150GetGapTime.vi
RS_DLL_GT150GetMeasNum.vi
RS_DLL_GT150GetBlockNum.vi
RS_DLL_GT150GetLoggingDataNum.vi
RS_DLL_GT150GetLoggingData.vi
```

### 2.2 公開API

```text
RAMScope_Get_Log_Summary.vi
RAMScope_Get_Block_Count.vi
RAMScope_Read_Logging_Block.vi
```

### 2.3 既存VIの扱い

```text
RAMScope_Read.vi
  → 変更しない
  → 測定中の最新データ取得として維持する

RAMScope_Release.vi
  → 全ロギングブロック取得後に呼ぶ
  → Read系VIへ内包しない
```

---

# 3. `RS_DLL_GT150GetGapTime.vi`

## 3.0 実現したい機能とVIの責務

測定開始関数の発行直後から、RAMScopeVP APIがハードウェアへ測定開始要求を出す直前までの経過時間をミリ秒単位で取得する。

この値は時刻補正へ自動適用せず、測定メタデータとして上位へ返す。

## 3.1 入力データの実体

```c
long RAMScopeGT150GetGapTime(
    long UnitNo,
    unsigned long *pGapTime
);
```

`UnitNo`は現仕様では常に0を指定する。`pGapTime`は32bit符号なし整数への出力Pointerである。

## 3.2 出力データモデル

```text
GapTimeMs U32
API ReturnCode I32
error out error cluster
```

## 3.3 前提条件・異常条件

- `error in.status=True`の場合はCLFNを呼ばない。
- バイパス時は`GapTimeMs=U32 0`を返す。
- API ReturnCodeが0以外の場合は`RAMScope_Code_To_Error.vi`でエラー化する。

## 3.4 処理アルゴリズム

```text
既存エラーがある場合
  → APIを呼ばず安全値を返す

既存エラーがない場合
  → pGapTimeへU32 0を事前入力する
  → APIを1回呼ぶ
  → 右端子からGapTimeMsを受け取る
  → ReturnCodeをerror clusterへ変換する
```

## 3.5 LabVIEW構造の選定理由

通常Wrapperの共通方式として、`error in.status`をselectorとするケースストラクチャ（Case Structure）を使用する。

## 3.6 入出力

| 端子名 | 方向 | 型 | 用途 |
|---|---|---|---|
| `UnitNo` | 入力 | I32 | 現仕様では0 |
| `error in` | 入力 | error cluster | 前段エラー |
| `GapTimeMs` | 出力 | U32 | 測定開始要求までの経過時間 ms |
| `API ReturnCode` | 出力 | I32 | RAMScope API戻り値 |
| `error out` | 出力 | error cluster | 変換後エラー |

## 3.7 配置する関数およびSubVI

| 数 | 日本語名 | 英語名 | 配置場所・追加方法 |
|---:|---|---|---|
| 1 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 1 | ライブラリ関数呼び出しノード | Call Library Function Node | 接続 → ライブラリ＆実行可能ファイル |
| 1 | `RAMScope_Code_To_Error.vi` | SubVI | RAMScope共通VIフォルダ |
| 1 | U32定数0 | U32 Numeric Constant | プログラミング → 数値 |
| 1 | I32定数0 | I32 Numeric Constant | プログラミング → 数値 |

## 3.8 CLFN設定と配線順

### CLFN Parameters

| 順番 | 名前 | Type | Data Type | Pass |
|---:|---|---|---|---|
| Return | 戻り値 | Numeric | Signed 32-bit Integer | Value |
| 1 | `UnitNo` | Numeric | Signed 32-bit Integer | Value |
| 2 | `pGapTime` | Numeric | Unsigned 32-bit Integer | Pointer to Value |

Function Name：`RAMScopeGT150GetGapTime`

### Trueケース（error in.status=True：既存エラーあり）

1. CLFNと`RAMScope_Code_To_Error.vi`を配置しない。
2. U32定数`0`を`GapTimeMs`出力トンネルへ接続する。
3. I32定数`0`を`API ReturnCode`出力トンネルへ接続する。
4. 元の`error in`を`error out`出力トンネルへ接続する。

### Falseケース（error in.status=False：既存エラーなし）

1. `UnitNo`をCLFNの`UnitNo`左端子へ接続する。
2. U32定数`0`をCLFNの`pGapTime`左端子へ接続する。
3. `error in`をCLFNの`error in`へ接続する。
4. CLFNの`pGapTime`右端子を`GapTimeMs`出力トンネルへ接続する。
5. CLFN戻り値を`API ReturnCode`出力トンネルへ分岐する。
6. CLFN戻り値を`RAMScope_Code_To_Error.vi / API ReturnCode`へ接続する。
7. 文字列定数`RAMScopeGT150GetGapTime`を`Function Name`へ接続する。
8. CLFNの`error out`を`RAMScope_Code_To_Error.vi / error in`へ接続する。
9. 同SubVIの`error out`を本VIの`error out`出力トンネルへ接続する。

## 3.9 単体テスト

| 条件 | 期待結果 |
|---|---|
| 既存エラーあり | CLFN未実行、GapTimeMs=0、元エラー保持 |
| 正常 | ReturnCode=0、GapTimeMs取得 |
| APIエラー | ReturnCodeを保持したerror cluster |
| MeasStart前 | 実機の戻り値とエラーを記録し、仕様化する |

---

# 4. 件数取得Wrapper 3個

次の3個は同じ構造を使用する。

```text
RS_DLL_GT150GetMeasNum.vi
RS_DLL_GT150GetBlockNum.vi
RS_DLL_GT150GetLoggingDataNum.vi
```

## 4.0 実現したい機能とVIの責務

| VI | 取得値 |
|---|---|
| `RS_DLL_GT150GetMeasNum.vi` | MeasStartからMeasStopまでに処理された測定回数 |
| `RS_DLL_GT150GetBlockNum.vi` | 指定MeasNoに存在するロギングブロック数 |
| `RS_DLL_GT150GetLoggingDataNum.vi` | 指定MeasNo、BlockNo、MdlNoの保存Packet数 |

## 4.1 Cプロトタイプ

```c
long RAMScopeGT150GetMeasNum(
    long UnitNo,
    long *pMeasNum
);

long RAMScopeGT150GetBlockNum(
    long UnitNo,
    long MeasNo,
    long *pBlockNum
);

long RAMScopeGT150GetLoggingDataNum(
    long UnitNo,
    long MdlNo,
    long MeasNo,
    long BlockNo,
    long *pDataNum
);
```

## 4.2 Pointerの扱い

すべてのPointer出力はI32である。

```text
I32定数 0
  → Pointer左端子
  → CLFN呼出し
  → Pointer右端子から実値を取得
```

## 4.3 CLFN Parameters

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

### `RS_DLL_GT150GetLoggingDataNum.vi`

| 順番 | 名前 | Type | Data Type | Pass |
|---:|---|---|---|---|
| Return | 戻り値 | Numeric | Signed 32-bit Integer | Value |
| 1 | `UnitNo` | Numeric | Signed 32-bit Integer | Value |
| 2 | `MdlNo` | Numeric | Signed 32-bit Integer | Value |
| 3 | `MeasNo` | Numeric | Signed 32-bit Integer | Value |
| 4 | `BlockNo` | Numeric | Signed 32-bit Integer | Value |
| 5 | `pDataNum` | Numeric | Signed 32-bit Integer | Pointer to Value |

## 4.4 共通配線ルール

### Trueケース（error in.status=True：既存エラーあり）

- 件数出力へI32定数`0`を接続する。
- `API ReturnCode`へI32定数`0`を接続する。
- 元の`error in`を`error out`へ接続する。
- CLFNを呼ばない。

### Falseケース（error in.status=False：既存エラーなし）

1. 各Value引数をCプロトタイプ順にCLFNへ接続する。
2. 件数Pointerの左端子へI32定数`0`を接続する。
3. Pointer右端子を各件数出力へ接続する。
4. CLFN戻り値を`API ReturnCode`へ分岐する。
5. CLFN戻り値とCLFN errorを`RAMScope_Code_To_Error.vi`へ接続する。
6. Function Nameは各API名の全文を使用する。

## 4.5 単体テスト

| VI | テスト条件 |
|---|---|
| GetMeasNum | 正常停止後、未開始、測定中、既存エラー |
| GetBlockNum | MeasNo=0、MeasNo=MeasNum-1、MeasNo=-1、MeasNo=MeasNum |
| GetLoggingDataNum | DataNum=0、正常非ゼロ、BlockNo=-1、BlockNo=BlockNum |

---

# 5. `RS_DLL_GT150GetLoggingData.vi`

## 5.0 実現したい機能とVIの責務

指定した測定番号、ロギングブロック番号およびモジュール番号に対応する保存Packetを、RAMScopeVP API内部の保存用データバッファからU8一次元配列へコピーする。

本VIはC関数を1回呼ぶ薄いWrapperである。Packet解析は行わない。

## 5.1 入力データの実体

現行マニュアル候補：

```c
long RAMScopeGT150GetLoggingData(
    long UnitNo,
    long MdlNo,
    long MeasNo,
    long BlockNo,
    long MaxDataNum,
    unsigned char *pData,
    long *pDataNum,
    long *pLostDataNum
);
```

`pData`へ必要なバイト数の領域をLabVIEW側で事前確保する。

```text
1 Packet
  ├─ Flag              4 byte
  ├─ Channel 0         4 byte
  ├─ Channel 1         4 byte
  ├─ ...
  └─ Timestamp         8 byte
```

Packet Sizeは次で計算する。

```text
Packet Size = 4 + ChNum × 4 + 8
            = ChNum × 4 + 12
```

必要な配列要素数：

```text
Buffer Byte Size = MaxDataNum × Packet Size
```

## 5.2 出力データモデル

```text
Allocated Raw Buffer U8[]
DataNum I32
LostDataNum I32
API ReturnCode I32
error out error cluster
```

`Allocated Raw Buffer`はCLFNへ渡した確保済み配列全体である。実データ部分への切り詰めは公開API側で行う。

## 5.3 前提条件・異常条件

- `MaxDataNum > 0`
- `Buffer Byte Size > 0`
- `Buffer Byte Size`はI32へ安全に変換可能
- `pData`の要素数は`Buffer Byte Size`と一致
- `error in.status=True`の場合はCLFNを呼ばない

入力検証の正式責務は公開API側とする。Wrapperは既存エラー時のバイパスだけを担当する。

## 5.4 処理アルゴリズム

```text
U8 0をBuffer Byte Size個並べた配列を作る
pDataNumへI32 0を入れる
pLostDataNumへI32 0を入れる
Cプロトタイプ順にCLFNを1回呼ぶ
右端子から配列、DataNum、LostDataNumを受け取る
ReturnCodeをerror clusterへ変換する
```

## 5.5 LabVIEW構造の選定理由

- 既存エラー時にDLLを呼ばないためCase Structureを使用する。
- 可変長出力配列をCへ渡すため配列初期化（Initialize Array）を使用する。
- `pDataNum`と`pLostDataNum`はPointer出力なのでPointer to Valueを使用する。

## 5.6 入出力

| 端子名 | 方向 | 型 | 用途 |
|---|---|---|---|
| `UnitNo` | 入力 | I32 | 現仕様では0 |
| `MdlNo` | 入力 | I32 | RAMモニタモジュール番号 |
| `MeasNo` | 入力 | I32 | 0からMeasNum-1 |
| `BlockNo` | 入力 | I32 | 0からBlockNum-1 |
| `MaxDataNum` | 入力 | I32 | 最大コピーPacket数 |
| `Buffer Byte Size` | 入力 | I32 | 事前確保するU8要素数 |
| `error in` | 入力 | error cluster | 前段エラー |
| `Allocated Raw Buffer` | 出力 | U8一次元配列 | DLL書込後の確保済み配列全体 |
| `DataNum` | 出力 | I32 | 実際にコピーしたPacket数 |
| `LostDataNum` | 出力 | I32 | ロギングトリガから現在までの累積欠落数 |
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
| 3 | I32定数0 | I32 Numeric Constant | プログラミング → 数値 |
| 1 | 空のU8一次元配列定数 | Empty U8 Array Constant | 配列枠へU8定数を配置 |

## 5.8 CLFN設定と配線順

### CLFN Parameters

| 順番 | 名前 | Type | Data Type | Dimensions | Array Format / Pass |
|---:|---|---|---|---:|---|
| Return | 戻り値 | Numeric | Signed 32-bit Integer | - | Value |
| 1 | `UnitNo` | Numeric | Signed 32-bit Integer | - | Value |
| 2 | `MdlNo` | Numeric | Signed 32-bit Integer | - | Value |
| 3 | `MeasNo` | Numeric | Signed 32-bit Integer | - | Value |
| 4 | `BlockNo` | Numeric | Signed 32-bit Integer | - | Value |
| 5 | `MaxDataNum` | Numeric | Signed 32-bit Integer | - | Value |
| 6 | `pData` | Array | Unsigned 8-bit Integer | 1 | Array Data Pointer |
| 7 | `pDataNum` | Numeric | Signed 32-bit Integer | - | Pointer to Value |
| 8 | `pLostDataNum` | Numeric | Signed 32-bit Integer | - | Pointer to Value |

Function Name：`RAMScopeGT150GetLoggingData`

Calling Convention：`C`

### Trueケース（error in.status=True：既存エラーあり）

1. 空のU8一次元配列定数を`Allocated Raw Buffer`出力トンネルへ接続する。
2. I32定数`0`を`DataNum`へ接続する。
3. I32定数`0`を`LostDataNum`へ接続する。
4. I32定数`0`を`API ReturnCode`へ接続する。
5. 元の`error in`を`error out`へ接続する。
6. CLFNを呼ばない。

### Falseケース（error in.status=False：既存エラーなし）

1. U8定数`0`を配列初期化（Initialize Array）の`element`へ接続する。
2. `Buffer Byte Size` I32を同関数の`dimension size`へ接続する。
3. Initialize Array出力を`Allocated Buffer Before Call`として扱う。
4. `UnitNo`をCLFNの引数1へ接続する。
5. `MdlNo`をCLFNの引数2へ接続する。
6. `MeasNo`をCLFNの引数3へ接続する。
7. `BlockNo`をCLFNの引数4へ接続する。
8. `MaxDataNum`をCLFNの引数5へ接続する。
9. `Allocated Buffer Before Call`をCLFNの`pData`左端子へ接続する。
10. I32定数`0`をCLFNの`pDataNum`左端子へ接続する。
11. I32定数`0`をCLFNの`pLostDataNum`左端子へ接続する。
12. `error in`をCLFNの`error in`へ接続する。
13. CLFNの`pData`右端子を`Allocated Raw Buffer`出力トンネルへ接続する。
14. CLFNの`pDataNum`右端子を`DataNum`出力トンネルへ接続する。
15. CLFNの`pLostDataNum`右端子を`LostDataNum`出力トンネルへ接続する。
16. CLFN戻り値を`API ReturnCode`出力へ分岐する。
17. CLFN戻り値を`RAMScope_Code_To_Error.vi / API ReturnCode`へ接続する。
18. 文字列定数`RAMScopeGT150GetLoggingData`を`Function Name`へ接続する。
19. CLFNの`error out`を`RAMScope_Code_To_Error.vi / error in`へ接続する。
20. 同SubVIの`error out`を本VIの`error out`出力へ接続する。

## 5.9 単体テスト

| 条件 | 期待結果 |
|---|---|
| 既存エラーあり | CLFN未実行、空Raw、DataNum=0、Lost=0、元エラー保持 |
| MaxDataNum=1 | 1Packet以下を取得 |
| DataNumがMaxDataNum未満 | 後段で実データ長へ切り詰め可能 |
| DataNum=0 | Rawは確保配列、実データ部は空 |
| LostDataNum非ゼロ | 値をそのまま出力 |
| MeasNoまたはBlockNo不正 | APIエラーを保持 |
| 旧7引数DLLへ8引数設定 | 実行禁止。ABI確認テストで事前に排除する |

---

# 6. `RAMScope_Get_Log_Summary.vi`

## 6.0 実現したい機能とVIの責務

測定停止後、ログ取得に必要な測定全体の情報を取得する。

```text
GapTimeMs
MeasNum
```

## 6.1 入力データの実体

`UnitNo`と前段errorだけを受け取る。

## 6.2 出力データモデル

| 出力 | 型 | 意味 |
|---|---|---|
| `GapTimeMs` | U32 | MeasStart発行からハードウェア開始要求直前までの時間 |
| `MeasNum` | I32 | MeasStartからMeasStopまでに成立した測定数 |
| `Status` | Status.ctl | TestStand判定 |
| `TestError` | TestError.ctl | 機器エラー詳細 |
| `error out` | error cluster | 最終エラー |

## 6.3 前提条件・異常条件

- `RAMScope_Log_Stop.vi`成功後に呼ぶ。
- GetGapTime失敗時はGetMeasNumを呼ばない。
- `MeasNum < 0`はローカル検証エラーとする。
- `MeasNum = 0`は正常な空ログとして扱う。

## 6.4 処理アルゴリズム

```text
GapTimeを取得する
MeasNumを取得する
MeasNumが負数ならエラーを作る
最終errorをStatusとTestErrorへ変換する
```

## 6.5 LabVIEW構造の選定理由

- API順序をerror wireで固定する。
- 負数件数をDLLへ続けて渡さないため、MeasNum検証Caseを配置する。

## 6.6 入出力

```text
入力 : UnitNo I32、error in
出力 : GapTimeMs U32、MeasNum I32、Status、TestError、error out
```

## 6.7 配置する関数およびSubVI

- `RS_DLL_GT150GetGapTime.vi`
- `RS_DLL_GT150GetMeasNum.vi`
- 小さい?（Less?）
- ケースストラクチャ（Case Structure）
- 文字列にフォーマット（Format Into String）
- 名前でバンドル（Bundle By Name）
- `Error_To_TestStatus.vi`

## 6.8 配線順

1. `UnitNo`と`error in`を`RS_DLL_GT150GetGapTime.vi`へ接続する。
2. GetGapTimeの`error out`を`RS_DLL_GT150GetMeasNum.vi / error in`へ接続する。
3. `UnitNo`をGetMeasNumへ接続する。
4. GetGapTimeの`GapTimeMs`を本VIの同名出力へ接続する。
5. GetMeasNumの`MeasNum`を本VIの同名出力へ分岐する。
6. `MeasNum < I32 0`の比較結果を`MeasNum Valid?` Caseのselectorへ接続する。
7. Falseケース（MeasNum<0=False：件数正常）ではGetMeasNumのerrorをそのまま出力する。
8. Trueケース（MeasNum<0=True：負数件数）では次のsourceを作る。

```text
RAMScope_Get_Log_Summary.vi: MeasNum must not be negative. MeasNum=%d
```

9. `%d`へ`MeasNum` I32を接続する。
10. Bundle By Nameの基準クラスタへGetMeasNumの正常errorを接続する。
11. `status=True`、`code=I32 -700170`、`source=Format Into String出力`を接続する。
12. Case出力errorを`Error_To_TestStatus.vi / error in`へ接続する。
13. 文字列定数`RAMScope`を`Device Name`へ接続する。
14. Status、TestError、error outを本VI出力へ接続する。

## 6.9 単体テスト

| 条件 | 期待結果 |
|---|---|
| MeasNum=0 | 正常、上位ループ0回 |
| MeasNum=1 | 正常、MeasNo=0のみ |
| MeasNum=3 | 正常、MeasNo=0～2 |
| MeasNum=-1ダミー | code=-700170 |
| GetGapTimeエラー | GetMeasNum未実行、元エラー保持 |

---

# 7. `RAMScope_Get_Block_Count.vi`

## 7.0 実現したい機能とVIの責務

指定した`MeasNo`に存在するロギングブロック数を取得する。

## 7.1 入力データの実体

```text
MeasNo = 0 ... MeasNum-1
```

上位TestStandまたはPoCがMeasNum回のFor Loopを管理し、ループ反復端子を`MeasNo`へ渡す。

## 7.2 出力データモデル

```text
BlockNum I32
Status
TestError
error out
```

## 7.3 前提条件・異常条件

- `MeasNo >= 0`
- `BlockNum >= 0`
- `BlockNum=0`は正常

## 7.4 処理アルゴリズム

```text
MeasNoが負数ならAPIを呼ばずエラー
正常ならGetBlockNumを呼ぶ
戻ったBlockNumが負数ならローカルエラー
```

## 7.5 LabVIEW構造の選定理由

入力検証と戻り値検証を別のCaseへ分け、C APIへ不正番号を渡す前に止める。

## 7.6 入出力

```text
入力 : UnitNo I32、MeasNo I32、error in
出力 : BlockNum I32、Status、TestError、error out
```

## 7.7 配置する関数およびSubVI

- `RS_DLL_GT150GetBlockNum.vi`
- 大きいか等しい?（Greater Or Equal?）
- ケースストラクチャ（Case Structure）2個
- 文字列にフォーマット（Format Into String）2個
- 名前でバンドル（Bundle By Name）2個
- `Error_To_TestStatus.vi`

## 7.8 配線順

1. `MeasNo >= I32 0`を`Input Valid?` Caseのselectorへ接続する。
2. Falseケース（Input Valid?=False：MeasNo負数）ではWrapperを呼ばず、BlockNum=0を出力する。
3. Falseケースで次のsourceを作る。

```text
RAMScope_Get_Block_Count.vi: MeasNo must not be negative. MeasNo=%d
```

4. `status=True`、`code=I32 -700171`を設定する。
5. Trueケース（Input Valid?=True：MeasNo正常）で`UnitNo`、`MeasNo`、`error in`をWrapperへ接続する。
6. Wrapperの`BlockNum < I32 0`を`BlockNum Valid?` Caseのselectorへ接続する。
7. Falseケース（BlockNum<0=False：件数正常）ではWrapper errorをそのまま通す。
8. Trueケース（BlockNum<0=True：負数件数）では次のsourceを作る。

```text
RAMScope_Get_Block_Count.vi: BlockNum must not be negative. MeasNo=%d, BlockNum=%d
```

9. `status=True`、`code=I32 -700172`を設定する。
10. 最終errorを`Error_To_TestStatus.vi`へ接続する。
11. Device Name=`RAMScope`とし、Status、TestError、error outを出力する。

## 7.9 単体テスト

| 条件 | 期待結果 |
|---|---|
| MeasNo=-1 | Wrapper未実行、code=-700171 |
| BlockNum=0 | 正常、Block Loop 0回 |
| BlockNum=1 | BlockNo=0のみ |
| BlockNum=4 | BlockNo=0～3 |
| Wrapper出力BlockNum=-1ダミー | code=-700172 |

---

# 8. `RAMScope_Read_Logging_Block.vi`

## 8.0 実現したい機能とVIの責務

指定した`MeasNo`と`BlockNo`の保存Packet数を取得し、必要なU8配列を確保して保存データを読み込み、実際に取得したPacket数だけを既存`RAMScope_Parse_Buffer.vi`で解析する。

本VIは1回の呼出しで1ロギングブロックだけを処理する。

```text
1 Block取得
  → 直後にTDMSへ追記
  → 次Blockを取得
```

## 8.1 入力データの実体

```text
Channel List
  → ChNumを決める

MeasNo
  → 取得対象の測定番号

BlockNo
  → 取得対象のロギングトリガ番号

GetLoggingDataNum出力
  → AvailableDataNum
  → MaxDataNumとしてGetLoggingDataへ渡す
```

Packet構造：

```text
Raw Buffer U8[]
├─ Packet 0
│  ├─ Flag              4 byte
│  ├─ Channel Data      ChNum × 4 byte
│  └─ Timestamp         8 byte
├─ Packet 1
└─ ...
```

既存Parserの実装が`Channel Data → Flag → Timestamp`順を前提としている場合は、実機データとマニュアルの並びを照合し、Parser側の正本を1つへ統一する。

## 8.2 出力データモデル

| 出力 | 型 | 意味 |
|---|---|---|
| `AvailableDataNum` | I32 | API内部バッファに保存されているPacket数 |
| `DataNum` | I32 | 実際にコピーされたPacket数 |
| `LostDataNum` | I32 | 対象トリガから現在までの累積欠落数 |
| `Raw Buffer` | U8一次元配列 | 実データ長へ切り詰めた生データ |
| `Packets` | RAMScope_Packet.ctl一次元配列 | 解析済みPacket |
| `Parsed Packet Count` | I32 | Parser出力件数 |
| `Unused Byte Count` | I32 | 正常時0 |
| `Status` | Status.ctl | TestStand判定 |
| `TestError` | TestError.ctl | 機器エラー詳細 |
| `error out` | error cluster | 最終エラー |

## 8.3 前提条件・異常条件

### 入力条件

```text
ChNum >= 1
MeasNo >= 0
BlockNo >= 0
Max Buffer Bytes > 0
```

### 件数条件

```text
AvailableDataNum >= 0
0 <= DataNum <= AvailableDataNum
```

### 配列サイズ条件

```text
Packet Size I64 = ChNum × 4 + 12
Required Bytes I64 = AvailableDataNum × Packet Size

Required Bytes <= Max Buffer Bytes
Required Bytes <= 2147483647
```

I32で乗算してからI64へ変換しない。各入力を先にI64へ変換してから乗算し、オーバーフローを防ぐ。

### DataNum=0

`AvailableDataNum=0`は正常とする。`GetLoggingData`とParserを呼ばず、空配列を返す。

### LostDataNum

`LostDataNum`はロギングトリガから現在までの累積値である。複数BlockのLostDataNumを単純加算しない。TDMSへBlockごとの属性として保存する。

## 8.4 処理アルゴリズム

```text
ChNumを求める
入力値を検証する
保存Packet数を取得する

AvailableDataNumが0なら
    空データを返す
else
    Packet Sizeを求める
    Required BytesをI64で求める
    メモリ上限を検証する
    MaxDataNum=AvailableDataNumとして保存データを取得する
    DataNumの範囲を検証する
    Actual Byte Count=DataNum×Packet Sizeを求める
    確保済み配列をActual Byte Countへ切り詰める
    ParserでDataNum Packetを解析する
    Parsed Packet CountとDataNumが一致するか検証する
end

最終errorをStatusとTestErrorへ変換する
```

## 8.5 LabVIEW構造の選定理由

| 必要なロジック | LabVIEW構造 | 選定理由 |
|---|---|---|
| 入力値によってAPI呼出しを止める | Case Structure | 不正Pointerと巨大配列確保を防ぐ |
| DataNum=0で処理を省略する | Case Structure | ゼロ長時にCLFNを呼ばない |
| I64サイズを上限判定する | 比較とCompound Arithmetic | I32オーバーフロー前に止める |
| 実データ長へ切り詰める | 部分配列（Array Subset） | 未使用のゼロ領域をParserへ渡さない |
| API順序を固定する | error cluster直列配線 | DataNum取得前に本体取得しない |

本VI内にはFor Loopを配置しない。MeasNoとBlockNoの反復はTestStandまたはPoCが管理する。

## 8.6 入出力

| 端子名 | 方向 | 型 | 用途 |
|---|---|---|---|
| `UnitNo` | 入力 | I32 | 現仕様では0 |
| `MdlNo_RAM` | 入力 | I32 | RAMモジュール番号 |
| `MeasNo` | 入力 | I32 | 測定番号 |
| `BlockNo` | 入力 | I32 | ブロック番号 |
| `Channel List` | 入力 | RAMScope_Channel.ctl一次元配列 | ChNumとParser設定 |
| `Byte Order` | 入力 | RAMScope_Byte_Order.ctl | ParserのEndian設定 |
| `Max Buffer Bytes` | 入力 | I64 | 1回で確保可能な最大バイト数。PoC初期値268435456 |
| `error in` | 入力 | error cluster | 前段エラー |
| `AvailableDataNum` | 出力 | I32 | 保存Packet数 |
| `DataNum` | 出力 | I32 | コピーPacket数 |
| `LostDataNum` | 出力 | I32 | 累積欠落数 |
| `Raw Buffer` | 出力 | U8一次元配列 | 実データ部分のみ |
| `Packets` | 出力 | RAMScope_Packet.ctl一次元配列 | 解析結果 |
| `Parsed Packet Count` | 出力 | I32 | Parser件数 |
| `Unused Byte Count` | 出力 | I32 | 正常時0 |
| `Status` | 出力 | Status.ctl | TestStand判定 |
| `TestError` | 出力 | TestError.ctl | 詳細エラー |
| `error out` | 出力 | error cluster | 最終エラー |

## 8.7 配置する関数およびSubVI

| 数 | 日本語名 | 英語名 | 配置場所・追加方法 |
|---:|---|---|---|
| 1 | 配列サイズ | Array Size | プログラミング → 配列 |
| 4以上 | 数値変換 | To 64-bit Integer / To 32-bit Integer | プログラミング → 数値 → 変換 |
| 2 | 乗算 | Multiply | プログラミング → 数値 |
| 1 | 加算 | Add | プログラミング → 数値 |
| 1 | 部分配列 | Array Subset | プログラミング → 配列 |
| 5以上 | 比較関数 | Comparison | プログラミング → 比較 |
| 2以上 | 複合演算 | Compound Arithmetic | プログラミング → Boolean |
| 4以上 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 1 | `RS_DLL_GT150GetLoggingDataNum.vi` | SubVI | DLL Wrapperフォルダ |
| 1 | `RS_DLL_GT150GetLoggingData.vi` | SubVI | DLL Wrapperフォルダ |
| 1 | `RAMScope_Parse_Buffer.vi` | SubVI | Parserフォルダ |
| 1 | `Error_To_TestStatus.vi` | SubVI | 共通VIフォルダ |
| 必要数 | 文字列にフォーマット | Format Into String | プログラミング → 文字列 |
| 必要数 | 名前でバンドル | Bundle By Name | プログラミング → クラスタ |

## 8.8 配線順

### A. ChNumと入力検証

1. `Channel List`を配列サイズ（Array Size）へ接続する。
2. Array Size出力を`ChNum I32`として扱う。
3. `ChNum >= I32 1`を作る。
4. `MeasNo >= I32 0`を作る。
5. `BlockNo >= I32 0`を作る。
6. `Max Buffer Bytes > I64 0`を作る。
7. 4条件を複合演算（Compound Arithmetic）のANDへ接続する。
8. AND出力を`Input Valid?` Case Structureのselectorへ接続する。

### B. Falseケース（Input Valid?=False：入力値不正）

1. 2個のDLL WrapperとParserを配置しない。
2. `AvailableDataNum=I32 0`を出力する。
3. `DataNum=I32 0`を出力する。
4. `LostDataNum=I32 0`を出力する。
5. `Raw Buffer`へ空のU8一次元配列を接続する。
6. `Packets`へ空のRAMScope_Packet.ctl一次元配列を接続する。
7. `Parsed Packet Count=I32 0`を出力する。
8. `Unused Byte Count=I32 0`を出力する。
9. 次のsource全文を文字列にフォーマット（Format Into String）へ設定する。

```text
RAMScope_Read_Logging_Block.vi: Input is invalid. ChNum=%d, MeasNo=%d, BlockNo=%d, MaxBufferBytes=%lld
```

10. `%d`へ順にChNum、MeasNo、BlockNoを接続する。
11. `%lld`へMax Buffer Bytes I64を接続する。
12. Bundle By Nameの基準クラスタへ正常な`error in`を接続する。
13. `status=True`、`code=I32 -700173`、`source=Format出力`を接続する。
14. 生成errorを`Error_To_TestStatus.vi`へ接続する。

### C. Trueケース（Input Valid?=True：入力値正常）

1. `UnitNo`、`MdlNo_RAM`、`MeasNo`、`BlockNo`を`RS_DLL_GT150GetLoggingDataNum.vi`へ接続する。
2. `error in`を同Wrapperの`error in`へ接続する。
3. Wrapperの`DataNum`を`AvailableDataNum`として本VI出力へ分岐する。
4. `AvailableDataNum >= I32 0`を`Available Count Valid?` Caseのselectorへ接続する。

### D. Falseケース（AvailableDataNum>=0=False：負数件数）

1. GetLoggingData WrapperとParserを配置しない。
2. DataNum、LostDataNum、各CountへI32 0を接続する。
3. Raw BufferとPacketsへ空配列を接続する。
4. 次のsourceを作る。

```text
RAMScope_Read_Logging_Block.vi: AvailableDataNum must not be negative. MeasNo=%d, BlockNo=%d, AvailableDataNum=%d
```

5. `status=True`、`code=I32 -700174`を設定する。

### E. Trueケース（AvailableDataNum>=0=True：件数非負）

1. `AvailableDataNum == I32 0`を`No Data?` Caseのselectorへ接続する。

### F. Trueケース（No Data?=True：保存Packetなし）

1. GetLoggingData WrapperとParserを配置しない。
2. DataNum、LostDataNum、各CountへI32 0を接続する。
3. Raw BufferとPacketsへ空配列を接続する。
4. GetLoggingDataNum Wrapperの正常errorをそのまま通す。

### G. Falseケース（No Data?=False：保存Packetあり）

1. `ChNum` I32をI64へ変換する。
2. I64定数`4`と乗算し、`Channel Bytes I64`とする。
3. I64定数`12`を加算し、`Packet Size I64`とする。
4. `AvailableDataNum` I32をI64へ変換する。
5. `AvailableDataNum I64 × Packet Size I64`を`Required Bytes I64`とする。
6. `Required Bytes <= Max Buffer Bytes`を作る。
7. `Required Bytes <= I64 2147483647`を作る。
8. `Required Bytes > I64 0`を作る。
9. 3条件をANDし、`Buffer Size Valid?` Caseのselectorへ接続する。

### H. Falseケース（Buffer Size Valid?=False：必要サイズが上限外）

1. GetLoggingData WrapperとParserを配置しない。
2. DataNum、LostDataNum、各CountへI32 0を接続する。
3. Raw BufferとPacketsへ空配列を接続する。
4. 次のsourceを作る。

```text
RAMScope_Read_Logging_Block.vi: Required buffer size is invalid or exceeds the limit. RequiredBytes=%lld, MaxBufferBytes=%lld, AvailableDataNum=%d, PacketSize=%lld
```

5. `%lld`へRequired Bytes、Max Buffer Bytes、Packet Sizeを指定順に接続する。
6. `%d`へAvailableDataNumを接続する。
7. `status=True`、`code=I32 -700175`を設定する。

### I. Trueケース（Buffer Size Valid?=True：配列確保可能）

1. `Required Bytes I64`をI32へ変換し、`Buffer Byte Size I32`とする。
2. `AvailableDataNum`を`MaxDataNum`として`RS_DLL_GT150GetLoggingData.vi`へ接続する。
3. UnitNo、MdlNo_RAM、MeasNo、BlockNoを同Wrapperの対応端子へ接続する。
4. `Buffer Byte Size I32`を同Wrapperへ接続する。
5. GetLoggingDataNum Wrapperの`error out`をGetLoggingData Wrapperの`error in`へ接続する。
6. GetLoggingData Wrapperの`DataNum`を本VIの`DataNum`出力へ分岐する。
7. 同Wrapperの`LostDataNum`を本VIの同名出力へ接続する。
8. `DataNum >= I32 0`を作る。
9. `DataNum <= AvailableDataNum`を作る。
10. 2条件をANDし、`Returned Count Valid?` Caseのselectorへ接続する。

### J. Falseケース（Returned Count Valid?=False：戻り件数不正）

1. Parserを配置しない。
2. Raw BufferとPacketsへ空配列を接続する。
3. Parsed Packet CountとUnused Byte CountへI32 0を接続する。
4. 次のsourceを作る。

```text
RAMScope_Read_Logging_Block.vi: Returned DataNum is outside the valid range. DataNum=%d, AvailableDataNum=%d, MeasNo=%d, BlockNo=%d
```

5. `status=True`、`code=I32 -700176`を設定する。

### K. Trueケース（Returned Count Valid?=True：戻り件数正常）

1. `DataNum` I32をI64へ変換する。
2. `DataNum I64 × Packet Size I64`を`Actual Byte Count I64`とする。
3. Actual Byte CountをI32へ変換する。
4. GetLoggingData Wrapperの`Allocated Raw Buffer`を部分配列（Array Subset）の`array`へ接続する。
5. I32定数`0`をArray Subsetの`index`へ接続する。
6. Actual Byte Count I32をArray Subsetの`length`へ接続する。
7. Array Subset出力を`Trimmed Raw Buffer`として本VIの`Raw Buffer`へ接続する。
8. Trimmed Raw Bufferを`RAMScope_Parse_Buffer.vi / Raw Buffer`へ接続する。
9. DataNum、Channel List、Byte OrderをParserの対応入力へ接続する。
10. GetLoggingData Wrapperの`error out`をParserの`error in`へ接続する。
11. ParserのPackets、Parsed Packet Count、Unused Byte Countを本VIの同名出力へ接続する。
12. `Parsed Packet Count == DataNum`を`Parse Count Match?` Caseのselectorへ接続する。

### L. Falseケース（Parse Count Match?=False：Parser件数不一致）

1. Parserが返したRaw Buffer、Packets、Countはデバッグ出力として保持する。
2. 次のsourceを作る。

```text
RAMScope_Read_Logging_Block.vi: Parsed packet count does not match DataNum. Parsed=%d, DataNum=%d, MeasNo=%d, BlockNo=%d
```

3. `status=True`、`code=I32 -700177`を設定する。
4. Bundle By Nameの基準クラスタへParserの正常errorを接続する。

### M. Trueケース（Parse Count Match?=True：解析件数一致）

1. Parserのerrorをそのまま最終errorへ接続する。

### N. 最終出力

1. 各Caseのerror出力を外側へ接続する。
2. 最終errorを`Error_To_TestStatus.vi / error in`へ接続する。
3. 文字列定数`RAMScope`を`Device Name`へ接続する。
4. Status、TestError、error outを本VIの対応出力へ接続する。
5. すべてのCaseで全データ出力トンネルを配線する。
6. `Use default if unwired`を使用しない。

## 8.9 単体テスト

| No. | 条件 | 期待結果 |
|---:|---|---|
| 1 | Channel List空 | code=-700173、DLL未実行 |
| 2 | MeasNo=-1 | code=-700173、DLL未実行 |
| 3 | BlockNo=-1 | code=-700173、DLL未実行 |
| 4 | AvailableDataNum=0 | 正常、GetLoggingData未実行、空配列 |
| 5 | Required BytesがMax Buffer Bytes超過 | code=-700175、配列未確保 |
| 6 | DataNum=AvailableDataNum | 正常、Unused Byte Count=0 |
| 7 | DataNumがAvailableDataNum未満 | RawをDataNum分へ切り詰め、Unused=0 |
| 8 | DataNum<0 | code=-700176、Parser未実行 |
| 9 | DataNum>AvailableDataNum | code=-700176、Parser未実行 |
| 10 | Parsed Count不一致 | code=-700177 |
| 11 | LostDataNum非ゼロ | 値をBlock属性として保持 |
| 12 | Wrapper既存エラー | 後続WrapperとParser未実行、元エラー保持 |

---

# 9. TestStandまたはPoCでの呼出し順

## 9.1 正常シーケンス

```text
RAMScope_Connect.vi
  → RAMScope_Init.vi
  → RAMScope_Set_Cond.vi
  → RAMScope_Log_Start.vi
  → 試験実行・必要なWait
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

## 9.2 TDMS保存単位

1ブロック取得後、次のグループ名で即時保存する。

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
AvailableDataNum
DataNum
LostDataNum
PacketSize
MeasurementStartTime
RAMScopeApiVersion
A2LFileName
```

`LostDataNum`はBlockごとの累積値として保存し、全Blockの単純合計を作らない。

## 9.3 エラー時Cleanup

ロギング取得でエラーが発生しても、測定停止済みで接続中なら次を試行する。

```text
Original Error
  ├─ RAMScope_Release.viをCleanup経路で試行
  ├─ RAMScope_Close.viを試行
  └─ Merge ErrorsでOriginal Errorを最優先に保持
```

通常の`RAMScope_Release.vi`が既存エラー時にバイパスする設計の場合は、前段エラーがあってもReleaseを試みるCleanup専用VIを別途設計する。正式方式は実機でReleaseの必要性を確認後に決定する。

---

# 10. 実機PoC確認項目

- [ ] 使用DLLと現行マニュアルの`GetLoggingData`引数個数が一致する
- [ ] 8引数形式でLabVIEWがクラッシュしない
- [ ] GetMeasNumが純正RAMScopeVP上の測定数と一致する
- [ ] 各MeasNoのGetBlockNumが純正表示と一致する
- [ ] GetLoggingDataNumとGetLoggingDataのDataNumが一致する
- [ ] DataNumがMaxDataNum以下である
- [ ] pDataの実Packet並びがParser定義と一致する
- [ ] Packet Sizeが`ChNum×4+12`で一致する
- [ ] Flag位置が実データと一致する
- [ ] Timestamp位置と20ns換算が実時間と一致する
- [ ] GapTimeMsの意味が実測と一致する
- [ ] LostDataNumの増加条件を再現できる
- [ ] DataNum=0で正常終了する
- [ ] 大容量BlockでMax Buffer Bytesガードが動く
- [ ] 全BlockをTDMSへ保存後、チャネル数とサンプル数が一致する
- [ ] 全取得後のReleaseとCloseが正常終了する

---

# 11. 正式統合時に更新する箇所

実機PoC後、次を同一コミットで更新する。

1. `docs/reference/RAMScopeVP.h`を使用DLL同梱版へ差し替える。
2. `docs/reference/samp_simple.cpp`を現行関数宣言へ更新する。
3. `10_RAMScope実装方針.md`の薄いWrapper一覧へ5個を追加する。
4. 公開API一覧へ3個を追加する。
5. 既存`RAMScope_Read.vi`を「最新データ取得」と明記する。
6. 本書の内容を第10章へ統合し、本書を削除する。
7. READMEのWrapper数と公開API数を更新する。

本書と第10章へ同じ詳細手順を残さない。正式統合後は第10章だけを正本とする。
