# 10B-2. RAMScope DLLラッパVIのCLFN設定・配線手順

> **本章の役割**：`RS_DLL_*` DLLラッパVIについて、CLFNへ追加するパラメータ、各端子へ接続する値、配列の事前確保、出力の受け方を、LabVIEWで初めてDLLラッパを作成する人でも再現できる粒度で説明する。
>
> 共通エラー変換は [10B-1：RAMScope_Code_To_Error.vi 作成手順](./10B1_RAMScope_Code_To_Error_VI作成手順.md)、全体の実装順は [10B](./10B_RAMScope_VI作成手順_STEP3_STEP4詳細.md) を参照する。
>
> 関数プロトタイプの一次情報は `docs/reference/RAMScopeVP.h` とする。

**最終整理日：2026-07-14**

---

## 1. 本章で作成するDLLラッパVI

```text
30_RAMScope\10_DLL_Wrapper\
├─ RS_DLL_GT150DeviceInit.vi
├─ RS_DLL_GT150DeviceExit.vi
├─ RS_DLL_GT150AllInit.vi
├─ RS_DLL_GT150GetSysInfo.vi
├─ RS_DLL_GT150PGT_SetMdlConfig.vi
├─ RS_DLL_GT170SetMeasCond.vi
├─ RS_DLL_GT170SetMeasCh.vi
├─ RS_DLL_GT150SetLoggingInfo.vi
├─ RS_DLL_GT150MeasStart.vi
├─ RS_DLL_GT150GetBufferData.vi
├─ RS_DLL_GT150ReleaseBufferData.vi
└─ RS_DLL_GT150MeasStop.vi
```

DLLラッパは**1VIにつきDLL関数を1個だけ呼ぶ**。

DLLラッパ内では以下を行う。

1. `error in`を確認する。
2. CLFNで対象関数を1回呼ぶ。
3. CLFNの`error out`とAPIの戻り値を`RAMScope_Code_To_Error.vi`へ渡す。
4. API固有の出力値と標準`error out`を返す。

DLLラッパ内では`Status.ctl`と`TestError.ctl`を生成しない。これらは`RAMScope_*`公開APIの最後で生成する。

---

# 2. CLFN共通設定

すべてのCLFNで次を共通設定とする。

| 項目 | 設定 |
|---|---|
| Library name or path | `RAMScopeVP_API_x64.dll`のフルパス |
| Function name | 各節に記載した関数名と完全一致 |
| Calling convention | `C` |
| Thread | PoC中は`Run in UI thread` |
| Error checking | PoC中は`Maximum` |
| 戻り値 | `Numeric / Signed 32-bit Integer / Value` |
| Cの`long` | `Signed 32-bit Integer`、LabVIEWではI32 |
| Cの`unsigned long` / `DWORD` | `Unsigned 32-bit Integer`、LabVIEWではU32 |
| Cの`long *` | `Numeric / Signed 32-bit Integer / Pointer to Value` |
| 構造体ポインタ | U8一次元配列を`Array Data Pointer`で渡す |
| I32配列ポインタ | I32一次元配列を`Array Data Pointer`で渡す |

64bit DLLでも、WindowsのC言語`long`は32bitである。I64やPointer-sized Integerへ変更しない。

---

## 2.1 通常ラッパの共通ブロックダイアグラム

通常のラッパは、`error in.status`をセレクタとしたCase Structureを使用する。

```text
error in
  │
  ├─ Unbundle By Name（status）
  │        │
  │        ▼
  │   Case Structure
  │   ├─ True：前段エラーあり
  │   │    ├─ CLFNを呼ばない
  │   │    ├─ error inをそのままerror outへ
  │   │    └─ API固有出力は安全な初期値を返す
  │   │
  │   └─ False：前段エラーなし
  │        ├─ CLFNを実行
  │        ├─ API ReturnCodeを取得
  │        ├─ CLFN error outを取得
  │        └─ RAMScope_Code_To_Error.vi
  │              ├─ API ReturnCode
  │              ├─ Function Name定数
  │              ├─ CLFN error out
  │              └─ error out
  │
  └──────────────────────────────→ error out
```

### Trueケースで返す初期値

| 出力型 | 初期値 |
|---|---|
| I32 | `0` |
| U32 | `0` |
| U8配列 | 空配列、または関数仕様で決めた初期化済み配列 |
| I32配列 | 空配列、または関数仕様で決めた初期化済み配列 |
| API ReturnCode | `0` |

すべてのCaseで出力トンネルを配線する。`Use default if unwired`には頼らない。

---

## 2.2 配列ポインタの重要事項

CLFNで`Array Data Pointer`を使用しても、LabVIEWが自動的に配列サイズを確保するわけではない。

DLLが書き込む配列は、呼び出し前に`Initialize Array`で必要要素数を確保する。

```text
要素の初期値 + 要素数
          ↓
   Initialize Array
          ↓
   CLFNの配列入力端子
          ↓
   CLFNの配列出力端子
```

フロントパネルで配列枠を縦に伸ばして表示行数を増やしても、配列要素数は増えない。

---

# 3. `RS_DLL_GT150DeviceInit.vi`

## 3.1 Cプロトタイプ

```c
long RAMScopeGT150DeviceInit(
    long *pUnitNum,
    long *kind
);
```

## 3.2 フロントパネル端子

| 端子 | 方向 | 型 |
|---|---|---|
| `error in` | 入力 | error cluster |
| `UnitNum` | 出力 | I32 |
| `kind` | 出力 | I32 |
| `API ReturnCode` | 出力 | I32 |
| `error out` | 出力 | error cluster |

## 3.3 CLFNパラメータ

CLFNのParametersタブで、上から次の順に設定する。

| 順番 | 名前 | Type | Data Type | Pass |
|---:|---|---|---|---|
| Return | 戻り値 | Numeric | Signed 32-bit Integer | Value |
| 1 | `pUnitNum` | Numeric | Signed 32-bit Integer | Pointer to Value |
| 2 | `kind` | Numeric | Signed 32-bit Integer | Pointer to Value |

表示プロトタイプ例：

```c
int32_t RAMScopeGT150DeviceInit(
    int32_t *pUnitNum,
    int32_t *kind
);
```

## 3.4 CLFNへ接続する値

```text
I32定数 0 ─────────→ pUnitNum 左端子
I32定数 0 ─────────→ kind 左端子
error in ──────────→ CLFN error in

CLFN戻り値 ────────→ API ReturnCode
pUnitNum 右端子 ───→ UnitNum
kind 右端子 ───────→ kind
CLFN error out ─────→ RAMScope_Code_To_Error.vi の error in
```

`RAMScope_Code_To_Error.vi`の`Function Name`には次の文字列定数を接続する。

```text
RAMScopeGT150DeviceInit
```

---

# 4. `RS_DLL_GT150DeviceExit.vi`

## 4.1 Cプロトタイプ

```c
long RAMScopeGT150DeviceExit(void);
```

## 4.2 フロントパネル端子

| 端子 | 方向 | 型 |
|---|---|---|
| `error in` | 入力 | error cluster |
| `API ReturnCode` | 出力 | I32 |
| `DeviceExit error` | 出力 | error cluster |

`DeviceExit error`は、DeviceExit呼び出し自体の結果を返す。元の`error in`との統合は`RAMScope_Close.vi`で行う。

## 4.3 CLFNパラメータ

| 順番 | 設定 |
|---:|---|
| Return | Numeric / Signed 32-bit Integer / Value |
| 引数 | なし |

表示プロトタイプ例：

```c
int32_t RAMScopeGT150DeviceExit(void);
```

## 4.4 前段エラーがあっても呼ぶ構成

DeviceExitはCleanup用なので、通常ラッパのように`error in.status=True`でスキップしない。

```text
error in
  ├──────────────────────────────────────→ RAMScope_Close.vi側で保持
  │
  └→ Clear Errors.vi
        ↓
      CLFN RAMScopeGT150DeviceExit
        ├─ 戻り値 → API ReturnCode
        └─ error out
              ↓
        RAMScope_Code_To_Error.vi
              ↓
        DeviceExit error
```

`Clear Errors.vi`を通すことで、前段エラーがあってもCLFNを実行でき、`error in`からCLFNへのデータ依存も維持できる。

`Function Name`：

```text
RAMScopeGT150DeviceExit
```

---

# 5. `RS_DLL_GT150AllInit.vi`

## 5.1 Cプロトタイプ

```c
long RAMScopeGT150AllInit(long UnitNo);
```

## 5.2 フロントパネル端子

| 端子 | 方向 | 型 |
|---|---|---|
| `UnitNo` | 入力 | I32 |
| `error in` | 入力 | error cluster |
| `API ReturnCode` | 出力 | I32 |
| `error out` | 出力 | error cluster |

## 5.3 CLFNパラメータ

| 順番 | 名前 | Type | Data Type | Pass |
|---:|---|---|---|---|
| Return | 戻り値 | Numeric | Signed 32-bit Integer | Value |
| 1 | `UnitNo` | Numeric | Signed 32-bit Integer | Value |

## 5.4 配線

```text
UnitNo I32 ─────────→ UnitNo
error in ───────────→ CLFN error in
CLFN戻り値 ─────────→ API ReturnCode
CLFN error out ──────→ RAMScope_Code_To_Error.vi
Function Name ───────→ "RAMScopeGT150AllInit"
```

最小PoCでは、公開APIから`UnitNo=0`を渡す。

---

# 6. `RS_DLL_GT150GetSysInfo.vi`

## 6.1 Cプロトタイプ

```c
long RAMScopeGT150GetSysInfo(
    long UnitNo,
    SYSINFO *pSysInfo
);
```

`SYSINFO`は1要素60バイト。最大16モジュール分として合計960バイトを確保する。

## 6.2 フロントパネル端子

| 端子 | 方向 | 型 |
|---|---|---|
| `UnitNo` | 入力 | I32 |
| `error in` | 入力 | error cluster |
| `SYSINFO Raw` | 出力 | U8一次元配列 |
| `API ReturnCode` | 出力 | I32 |
| `error out` | 出力 | error cluster |

## 6.3 CLFNパラメータ

| 順番 | 名前 | Type | Data Type | Dimensions | Array Format / Pass |
|---:|---|---|---|---:|---|
| Return | 戻り値 | Numeric | Signed 32-bit Integer | - | Value |
| 1 | `UnitNo` | Numeric | Signed 32-bit Integer | - | Value |
| 2 | `pSysInfo` | Array | Unsigned 8-bit Integer | 1 | Array Data Pointer |

表示プロトタイプ例：

```c
int32_t RAMScopeGT150GetSysInfo(
    int32_t UnitNo,
    uint8_t *pSysInfo
);
```

## 6.4 U8[960]の作成

ブロックダイアグラムへ`Initialize Array`を配置する。

```text
U8定数 0 ───────────→ element
I32定数 960 ─────────→ dimension size

Initialize Array出力 → pSysInfo 左端子
pSysInfo 右端子 ─────→ SYSINFO Raw
```

要素側の`0`は必ずU8にする。オレンジ色のDBL定数を使用しない。

## 6.5 全配線

```text
UnitNo I32 ───────────────→ CLFN UnitNo
U8[960]初期化配列 ────────→ CLFN pSysInfo 左端子
error in ─────────────────→ CLFN error in

CLFN pSysInfo 右端子 ─────→ SYSINFO Raw
CLFN戻り値 ────────────────→ API ReturnCode
CLFN error out ─────────────→ RAMScope_Code_To_Error.vi
Function Name ───────────────→ "RAMScopeGT150GetSysInfo"
```

動作確認時は`Array Size`を接続し、`SYSINFO Raw`の要素数が960であることを確認する。

---

# 7. `RS_DLL_GT150PGT_SetMdlConfig.vi`

## 7.1 Cプロトタイプ

```c
long RAMScopeGT150PGT_SetMdlConfig(
    long UnitNo,
    long *SlotErr
);
```

## 7.2 フロントパネル端子

| 端子 | 方向 | 型 |
|---|---|---|
| `UnitNo` | 入力 | I32 |
| `error in` | 入力 | error cluster |
| `SlotErr` | 出力 | I32一次元配列 |
| `API ReturnCode` | 出力 | I32 |
| `error out` | 出力 | error cluster |

## 7.3 CLFNパラメータ

| 順番 | 名前 | Type | Data Type | Dimensions | Array Format / Pass |
|---:|---|---|---|---:|---|
| Return | 戻り値 | Numeric | Signed 32-bit Integer | - | Value |
| 1 | `UnitNo` | Numeric | Signed 32-bit Integer | - | Value |
| 2 | `SlotErr` | Array | Signed 32-bit Integer | 1 | Array Data Pointer |

## 7.4 I32[16]の作成と配線

```text
I32定数 0 ───────────→ Initialize Array element
I32定数 16 ──────────→ Initialize Array dimension size

I32[16]初期化配列 ───→ CLFN SlotErr 左端子
CLFN SlotErr 右端子 ─→ SlotErr表示器
```

全体：

```text
UnitNo ───────────────→ CLFN UnitNo
I32[16] ──────────────→ CLFN SlotErr
error in ─────────────→ CLFN error in

CLFN戻り値 ───────────→ API ReturnCode
CLFN SlotErr出力 ─────→ SlotErr
CLFN error out ───────→ RAMScope_Code_To_Error.vi
Function Name ─────────→ "RAMScopeGT150PGT_SetMdlConfig"
```

`SlotErr[MdlNo_RAM]`の追加判定は公開APIの`RAMScope_Init.vi`で行う。

---

# 8. `RS_DLL_GT170SetMeasCond.vi`

## 8.1 Cプロトタイプ

```c
long RAMScopeGT170SetMeasCond(
    long UnitNo,
    long MdlNo,
    MEASINFO_170 *pMeasInfo
);
```

`MEASINFO_170`は72バイトのunionである。

## 8.2 フロントパネル端子

| 端子 | 方向 | 型 |
|---|---|---|
| `UnitNo` | 入力 | I32 |
| `MdlNo` | 入力 | I32 |
| `MEASINFO_170 Raw` | 入力 | U8一次元配列、72要素 |
| `error in` | 入力 | error cluster |
| `API ReturnCode` | 出力 | I32 |
| `error out` | 出力 | error cluster |

構造体の生成は公開APIまたはCommon層で行い、ラッパへU8[72]として渡す。

## 8.3 CLFNパラメータ

| 順番 | 名前 | Type | Data Type | Dimensions | Array Format / Pass |
|---:|---|---|---|---:|---|
| Return | 戻り値 | Numeric | Signed 32-bit Integer | - | Value |
| 1 | `UnitNo` | Numeric | Signed 32-bit Integer | - | Value |
| 2 | `MdlNo` | Numeric | Signed 32-bit Integer | - | Value |
| 3 | `pMeasInfo` | Array | Unsigned 8-bit Integer | 1 | Array Data Pointer |

## 8.4 配線

```text
UnitNo ───────────────→ CLFN UnitNo
MdlNo ────────────────→ CLFN MdlNo
MEASINFO_170 Raw ─────→ CLFN pMeasInfo
error in ─────────────→ CLFN error in

CLFN戻り値 ───────────→ API ReturnCode
CLFN error out ───────→ RAMScope_Code_To_Error.vi
Function Name ─────────→ "RAMScopeGT170SetMeasCond"
```

呼び出し前に`Array Size == 72`であることを公開API側で確認する。

---

# 9. `RS_DLL_GT170SetMeasCh.vi`

## 9.1 Cプロトタイプ

```c
long RAMScopeGT170SetMeasCh(
    long UnitNo,
    long MdlNo,
    long ChNum,
    CHINFO_170 *pChInfo
);
```

RAM用`CHINFO_170`は1チャンネル24バイトである。

## 9.2 フロントパネル端子

| 端子 | 方向 | 型 |
|---|---|---|
| `UnitNo` | 入力 | I32 |
| `MdlNo` | 入力 | I32 |
| `ChNum` | 入力 | I32 |
| `CHINFO_170 Raw` | 入力 | U8一次元配列、`24 × ChNum`要素 |
| `error in` | 入力 | error cluster |
| `API ReturnCode` | 出力 | I32 |
| `error out` | 出力 | error cluster |

## 9.3 CLFNパラメータ

| 順番 | 名前 | Type | Data Type | Dimensions | Array Format / Pass |
|---:|---|---|---|---:|---|
| Return | 戻り値 | Numeric | Signed 32-bit Integer | - | Value |
| 1 | `UnitNo` | Numeric | Signed 32-bit Integer | - | Value |
| 2 | `MdlNo` | Numeric | Signed 32-bit Integer | - | Value |
| 3 | `ChNum` | Numeric | Signed 32-bit Integer | - | Value |
| 4 | `pChInfo` | Array | Unsigned 8-bit Integer | 1 | Array Data Pointer |

## 9.4 配線

```text
UnitNo ───────────────→ CLFN UnitNo
MdlNo ────────────────→ CLFN MdlNo
ChNum ────────────────→ CLFN ChNum
CHINFO_170 Raw ───────→ CLFN pChInfo
error in ─────────────→ CLFN error in

CLFN戻り値 ───────────→ API ReturnCode
CLFN error out ───────→ RAMScope_Code_To_Error.vi
Function Name ─────────→ "RAMScopeGT170SetMeasCh"
```

公開API側で次を確認する。

```text
Array Size(CHINFO_170 Raw) == 24 × ChNum
```

`ChNum`はチャンネル番号ではなく、配列のチャンネル要素数である。

---

# 10. `RS_DLL_GT150SetLoggingInfo.vi`

## 10.1 Cプロトタイプ

```c
long RAMScopeGT150SetLoggingInfo(
    long UnitNo,
    LOGINFO *pLogInfo
);
```

`LOGINFO`は136バイトである。

## 10.2 フロントパネル端子

| 端子 | 方向 | 型 |
|---|---|---|
| `UnitNo` | 入力 | I32 |
| `LOGINFO Raw` | 入力 | U8一次元配列、136要素 |
| `error in` | 入力 | error cluster |
| `API ReturnCode` | 出力 | I32 |
| `error out` | 出力 | error cluster |

## 10.3 CLFNパラメータ

| 順番 | 名前 | Type | Data Type | Dimensions | Array Format / Pass |
|---:|---|---|---|---:|---|
| Return | 戻り値 | Numeric | Signed 32-bit Integer | - | Value |
| 1 | `UnitNo` | Numeric | Signed 32-bit Integer | - | Value |
| 2 | `pLogInfo` | Array | Unsigned 8-bit Integer | 1 | Array Data Pointer |

## 10.4 配線

```text
UnitNo ───────────────→ CLFN UnitNo
LOGINFO Raw ──────────→ CLFN pLogInfo
error in ─────────────→ CLFN error in

CLFN戻り値 ───────────→ API ReturnCode
CLFN error out ───────→ RAMScope_Code_To_Error.vi
Function Name ─────────→ "RAMScopeGT150SetLoggingInfo"
```

呼び出し前に`Array Size == 136`であることを公開API側で確認する。

---

# 11. `RS_DLL_GT150MeasStart.vi`

## 11.1 Cプロトタイプ

```c
long RAMScopeGT150MeasStart(long UnitNo);
```

## 11.2 フロントパネル端子

| 端子 | 方向 | 型 |
|---|---|---|
| `UnitNo` | 入力 | I32 |
| `error in` | 入力 | error cluster |
| `API ReturnCode` | 出力 | I32 |
| `error out` | 出力 | error cluster |

## 11.3 CLFNパラメータと配線

| 順番 | 名前 | Type | Data Type | Pass |
|---:|---|---|---|---|
| Return | 戻り値 | Numeric | Signed 32-bit Integer | Value |
| 1 | `UnitNo` | Numeric | Signed 32-bit Integer | Value |

```text
UnitNo ───────────────→ CLFN UnitNo
error in ─────────────→ CLFN error in
CLFN戻り値 ───────────→ API ReturnCode
CLFN error out ───────→ RAMScope_Code_To_Error.vi
Function Name ─────────→ "RAMScopeGT150MeasStart"
```

`MdlNo`は接続しない。

---

# 12. `RS_DLL_GT150GetBufferData.vi`

## 12.1 Cプロトタイプ

```c
long RAMScopeGT150GetBufferData(
    long UnitNo,
    long MdlNo,
    void *pData,
    long *pDataNum,
    long *pLostDataNum
);
```

## 12.2 推奨フロントパネル端子

| 端子 | 方向 | 型 | 用途 |
|---|---|---|---|
| `UnitNo` | 入力 | I32 | 通常0 |
| `MdlNo` | 入力 | I32 | RAMモジュール番号 |
| `Buffer Byte Size` | 入力 | I32 | 事前確保するU8配列の要素数 |
| `Max DataNum` | 入力 | I32 | `pDataNum`へ事前入力する最大パケット数 |
| `error in` | 入力 | error cluster | 前段エラー |
| `Raw Buffer` | 出力 | U8一次元配列 | DLLが書き込んだ生データ |
| `DataNum` | 出力 | I32 | 実際に取得したパケット数 |
| `LostDataNum` | 出力 | I32 | 取りこぼし数 |
| `API ReturnCode` | 出力 | I32 | API戻り値 |
| `error out` | 出力 | error cluster | 変換後エラー |

`RAMScope_Read.vi`で、次の式を使用して`Buffer Byte Size`を計算する。

```text
Packet Size      = 4 × Channel Count + 12
Buffer Byte Size = Packet Size × Max DataNum
```

## 12.3 CLFNパラメータ

| 順番 | 名前 | Type | Data Type | Dimensions | Array Format / Pass |
|---:|---|---|---|---:|---|
| Return | 戻り値 | Numeric | Signed 32-bit Integer | - | Value |
| 1 | `UnitNo` | Numeric | Signed 32-bit Integer | - | Value |
| 2 | `MdlNo` | Numeric | Signed 32-bit Integer | - | Value |
| 3 | `pData` | Array | Unsigned 8-bit Integer | 1 | Array Data Pointer |
| 4 | `pDataNum` | Numeric | Signed 32-bit Integer | - | Pointer to Value |
| 5 | `pLostDataNum` | Numeric | Signed 32-bit Integer | - | Pointer to Value |

表示プロトタイプ例：

```c
int32_t RAMScopeGT150GetBufferData(
    int32_t UnitNo,
    int32_t MdlNo,
    uint8_t *pData,
    int32_t *pDataNum,
    int32_t *pLostDataNum
);
```

## 12.4 呼び出し前の初期値

```text
U8定数 0 + Buffer Byte Size
          ↓
   Initialize Array
          ↓
   Raw Buffer初期配列

Max DataNum ─────────→ pDataNum 左端子
I32定数 0 ───────────→ pLostDataNum 左端子
```

`pDataNum`はPointerなので、左側へ`Max DataNum`を入力し、右側から実際の`DataNum`を受け取る。

## 12.5 全配線

```text
UnitNo ───────────────────────→ CLFN UnitNo
MdlNo ────────────────────────→ CLFN MdlNo
U8初期配列 ───────────────────→ CLFN pData 左端子
Max DataNum ──────────────────→ CLFN pDataNum 左端子
I32 0 ────────────────────────→ CLFN pLostDataNum 左端子
error in ─────────────────────→ CLFN error in

CLFN pData 右端子 ────────────→ Raw Buffer
CLFN pDataNum 右端子 ─────────→ DataNum
CLFN pLostDataNum 右端子 ─────→ LostDataNum
CLFN戻り値 ───────────────────→ API ReturnCode
CLFN error out ────────────────→ RAMScope_Code_To_Error.vi
Function Name ─────────────────→ "RAMScopeGT150GetBufferData"
```

### 安全確認

- `Buffer Byte Size > 0`
- `Max DataNum > 0`
- `Raw Buffer`の要素数が`Buffer Byte Size`と一致
- `DataNum <= Max DataNum`
- `LostDataNum`を毎回記録

`ReleaseBufferData`はこのラッパへ内包しない。

---

# 13. `RS_DLL_GT150ReleaseBufferData.vi`

## 13.1 Cプロトタイプ

```c
long RAMScopeGT150ReleaseBufferData(long UnitNo);
```

## 13.2 端子とCLFN設定

| 端子 | 方向 | 型 |
|---|---|---|
| `UnitNo` | 入力 | I32 |
| `error in` | 入力 | error cluster |
| `API ReturnCode` | 出力 | I32 |
| `error out` | 出力 | error cluster |

| 順番 | 名前 | Type | Data Type | Pass |
|---:|---|---|---|---|
| Return | 戻り値 | Numeric | Signed 32-bit Integer | Value |
| 1 | `UnitNo` | Numeric | Signed 32-bit Integer | Value |

```text
UnitNo ───────────────→ CLFN UnitNo
error in ─────────────→ CLFN error in
CLFN戻り値 ───────────→ API ReturnCode
CLFN error out ───────→ RAMScope_Code_To_Error.vi
Function Name ─────────→ "RAMScopeGT150ReleaseBufferData"
```

呼び出し位置は未確定のため、独立ラッパとして維持する。

---

# 14. `RS_DLL_GT150MeasStop.vi`

## 14.1 Cプロトタイプ

```c
long RAMScopeGT150MeasStop(long UnitNo);
```

## 14.2 端子とCLFN設定

| 端子 | 方向 | 型 |
|---|---|---|
| `UnitNo` | 入力 | I32 |
| `error in` | 入力 | error cluster |
| `API ReturnCode` | 出力 | I32 |
| `error out` | 出力 | error cluster |

| 順番 | 名前 | Type | Data Type | Pass |
|---:|---|---|---|---|
| Return | 戻り値 | Numeric | Signed 32-bit Integer | Value |
| 1 | `UnitNo` | Numeric | Signed 32-bit Integer | Value |

```text
UnitNo ───────────────→ CLFN UnitNo
error in ─────────────→ CLFN error in
CLFN戻り値 ───────────→ API ReturnCode
CLFN error out ───────→ RAMScope_Code_To_Error.vi
Function Name ─────────→ "RAMScopeGT150MeasStop"
```

`MdlNo`は接続しない。

---

# 15. DLLラッパ一覧・配線早見表

| VI | CLFNへ入力する値 | CLFNから受け取る値 |
|---|---|---|
| `RS_DLL_GT150DeviceInit.vi` | I32 `0` → `pUnitNum`、I32 `0` → `kind` | `UnitNum`、`kind`、ReturnCode |
| `RS_DLL_GT150DeviceExit.vi` | 引数なし。`Clear Errors`後のerror cluster | ReturnCode、DeviceExit error |
| `RS_DLL_GT150AllInit.vi` | `UnitNo` I32 Value | ReturnCode |
| `RS_DLL_GT150GetSysInfo.vi` | `UnitNo`、U8[960] | `SYSINFO Raw` U8[960]、ReturnCode |
| `RS_DLL_GT150PGT_SetMdlConfig.vi` | `UnitNo`、I32[16] | `SlotErr` I32[16]、ReturnCode |
| `RS_DLL_GT170SetMeasCond.vi` | `UnitNo`、`MdlNo`、U8[72] | ReturnCode |
| `RS_DLL_GT170SetMeasCh.vi` | `UnitNo`、`MdlNo`、`ChNum`、U8[`24×ChNum`] | ReturnCode |
| `RS_DLL_GT150SetLoggingInfo.vi` | `UnitNo`、U8[136] | ReturnCode |
| `RS_DLL_GT150MeasStart.vi` | `UnitNo` | ReturnCode |
| `RS_DLL_GT150GetBufferData.vi` | `UnitNo`、`MdlNo`、U8バッファ、`Max DataNum`、I32 `0` | Raw、DataNum、LostDataNum、ReturnCode |
| `RS_DLL_GT150ReleaseBufferData.vi` | `UnitNo` | ReturnCode |
| `RS_DLL_GT150MeasStop.vi` | `UnitNo` | ReturnCode |

---

# 16. 各ラッパの完成チェックリスト

すべてのラッパについて確認する。

- [ ] VI名とDLL関数名が対応している
- [ ] Function nameがヘッダと完全一致している
- [ ] Calling Conventionが`C`
- [ ] PoC中は`Run in UI thread`
- [ ] Error checkingが`Maximum`
- [ ] 戻り値がI32
- [ ] `long`をI64にしていない
- [ ] `long *`をPointer to Valueにしている
- [ ] 構造体をU8一次元配列で渡している
- [ ] DLL出力配列を呼び出し前に確保している
- [ ] 配列の要素型が正しい
- [ ] 全Caseの出力トンネルを配線している
- [ ] CLFN error outとReturnCodeを`RAMScope_Code_To_Error.vi`へ接続している
- [ ] `Function Name`文字列が実際のDLL関数名と一致している
- [ ] DLLラッパ内で`Error_To_TestStatus.vi`を呼んでいない
- [ ] DLLラッパ内で複数のDLL関数を呼んでいない

---

# 17. 推奨作成順

引数の少ない関数から作り、完成したラッパをテンプレートとして複製する。

```text
1. RS_DLL_GT150DeviceInit.vi       （作成済みCLFNを整理）
2. RS_DLL_GT150DeviceExit.vi
3. RS_DLL_GT150AllInit.vi
4. RS_DLL_GT150MeasStart.vi
5. RS_DLL_GT150MeasStop.vi
6. RS_DLL_GT150ReleaseBufferData.vi
7. RS_DLL_GT150GetSysInfo.vi
8. RS_DLL_GT150PGT_SetMdlConfig.vi
9. RS_DLL_GT170SetMeasCond.vi
10. RS_DLL_GT170SetMeasCh.vi
11. RS_DLL_GT150SetLoggingInfo.vi
12. RS_DLL_GT150GetBufferData.vi
```

各ラッパを作成したら、CLFNの詳細ヘルプに表示されるプロトタイプを本章のCプロトタイプと照合する。