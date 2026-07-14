# 10. RAMScope GT170 API 技術リファレンス

> **本章の役割**：RAMScopeVP APIの関数、構造体、定数、呼び出し順序を確認するための正本。
>
> 実際の作業は次の順で進める。
>
> 1. [10A：DLL準備・CLFN疎通確認](./10A_RAMScope実装手順_DLL準備とCLFN疎通確認.md)
> 2. [10B：各VIの作成手順](./10B_RAMScope_VI作成手順_STEP3_STEP4詳細.md)
> 3. [11：TestStandへの組み込み](./11_TestStandシーケンス構築手順.md)

**最終整理日：2026-07-14**

---

## 10.1 現在の採用構成

| 項目 | 採用内容 |
|------|----------|
| 対象機器 | RAMScope GT170 |
| 接続 | USB3.0 |
| LabVIEW | 64bit版 |
| API | RAMScopeVP API 64bit版 |
| API DLL | `RAMScopeVP_API_x64.dll` |
| 呼び出し | Call Library Function Node（CLFN） |
| Calling Convention | `C`。x64 ABIではcdecl/stdcallの区別は実質ない |
| DLL状態管理 | API内部のグローバル状態。セッションハンドルは返らない |
| C/C++ランタイム | Visual C++ 2013 Redistributable x64 |

過去に検討していた次の方式は、現在の実装ルートには使用しない。

- 32bit版DLLと32bit LabVIEWの組み合わせ
- マックシステムズ製LabVIEWドライバを採用する案
- ヘッダやサンプルが未入手であることを前提とした手作業推定

現在は64bit DLL、ヘッダ、ハードウェア定数、ベンダーサンプルを入手済みである。

## 10.2 一次情報の優先順位

矛盾がある場合は次の順で判断する。

1. `docs/reference/RAMScopeVP.h`
2. `docs/reference/GTHard.h`
3. `docs/reference/samp_simple.cpp`
4. RAMScopeVP API外部仕様書
5. 本章
6. PoC・実機結果

PoC結果が仕様書と異なる場合は、ファームウェア、API版数、機器構成を記録し、ベンダーへ確認する。

## 10.3 LabVIEW・DLL・APIの関係

```text
TestStand
  → LabVIEW VI
    → Call Library Function Node
      → RAMScopeVP_API_x64.dll
        → GT170_x64.dll / GT170USB_x64.dll / PGT関連機能
          → RAMScope GT170
```

- DLLは実行コードの本体。
- APIは関数名、引数、戻り値、呼び出し順序の取り決め。
- CLFNはLabVIEWからDLLのエクスポート関数を呼ぶ橋渡し。
- CLFNの標準`error out`とAPIの戻り値は別経路である。

## 10.4 GT150関数とGT170関数の使い分け

関数名の`GT150`は「GT150専用」という意味ではなく、GT170でも使用する共通インタフェースを含む。

### GT170でも使用するGT150共通関数

- `RAMScopeGT150DeviceInit`
- `RAMScopeGT150DeviceExit`
- `RAMScopeGT150AllInit`
- `RAMScopeGT150GetSysInfo`
- `RAMScopeGT150PGT_SetMdlConfig`
- `RAMScopeGT150SetLoggingInfo`
- `RAMScopeGT150MeasStart`
- `RAMScopeGT150GetBufferData`
- `RAMScopeGT150MeasStop`
- `RAMScopeGT150ReleaseBufferData`

### GT170専用関数を使用する処理

- 測定条件：`RAMScopeGT170SetMeasCond`
- 測定チャンネル：`RAMScopeGT170SetMeasCh`
- GT170固有トリガ、CAN、ADC機能：`RAMScopeGT170*`

> 計測開始・停止の正しい関数名は`RAMScopeGT150MeasStart` / `RAMScopeGT150MeasStop`である。`RAMScopeGT170MeasStart` / `RAMScopeGT170MeasStop`は使用しない。

## 10.5 状態ライフサイクル

```text
[オフライン]
  ↓ RAMScopeGT150DeviceInit
[アイドル]
  ↓ RAMScopeGT150AllInit
  ↓ RAMScopeGT150GetSysInfo
  ↓ RAMScopeGT150PGT_SetMdlConfig
  ↓ RAMScopeGT170SetMeasCond
  ↓ RAMScopeGT170SetMeasCh
  ↓ RAMScopeGT150SetLoggingInfo
  ↓ RAMScopeGT150MeasStart
[測定中]
  ↓ RAMScopeGT150GetBufferData（TestStandからポーリング）
  ↓ RAMScopeGT150MeasStop
[アイドル]
  ↓ RAMScopeGT150ReleaseBufferData（要否は実機検証中）
  ↓ RAMScopeGT150DeviceExit
[オフライン]
```

### 呼び出し上の重要事項

- `AllInit`は設定をクリアする。再設定前提で使用する。
- `GetSysInfo`で実際のモジュール番号を取得し、`MdlNo=1`等を固定しない。
- `PGT_SetMdlConfig`は`AllInit`と`GetSysInfo`の後、測定条件設定の前に呼ぶ。
- `SetLoggingInfo`を`MeasStart`より前に呼ぶ。
- `GetBufferData`はポーリング周期とバッファ容量を考慮する。
- `DeviceExit`はCleanupで必ず呼ぶ。

## 10.6 VIとAPIの対応

| VI | TestStand | API |
|----|-----------|-----|
| `RAMScope_Connect.vi` | Setup | `RAMScopeGT150DeviceInit` |
| `RAMScope_Init.vi` | Setup | `RAMScopeGT150AllInit` + `RAMScopeGT150GetSysInfo` |
| `RAMScope_Config.vi` | Setup | `RAMScopeGT150PGT_SetMdlConfig` |
| `RAMScope_Set_Cond.vi` | Setup | `RAMScopeGT170SetMeasCond` + `RAMScopeGT170SetMeasCh` + `RAMScopeGT150SetLoggingInfo` |
| `RAMScope_Log_Start.vi` | Main | `RAMScopeGT150MeasStart` |
| `RAMScope_Read.vi` | Main | `RAMScopeGT150GetBufferData` |
| `RAMScope_Parse_Buffer.vi` | Main | DLL呼び出しなし。取得バイト列を解析 |
| `RAMScope_Log_Stop.vi` | Main | `RAMScopeGT150MeasStop` |
| `RAMScope_Release.vi` | Main / Cleanup候補 | `RAMScopeGT150ReleaseBufferData` |
| `RAMScope_Close.vi` | Cleanup | `RAMScopeGT150DeviceExit` |

最初に作成した`DeviceInit`の最小VIは、名称上`RAMScope_Init.vi`ではなく`RAMScope_Connect.vi`として扱う。

---

# 10.7 使用関数プロトタイプ

Windowsの`long`は32bitである。64bit DLLでもLabVIEWではI32を使用する。

## 10.7.1 接続・終了

```c
long RAMScopeGT150DeviceInit(
    long *pUnitNum,
    long *kind
);

long RAMScopeGT150DeviceExit(void);
```

| 引数 | 方向 | LabVIEW |
|------|------|---------|
| `pUnitNum` | out | I32 / Pointer to Value |
| `kind` | out | I32 / Pointer to Value |
| 戻り値 | result | I32 |

`kind`：

| 値 | 機種 |
|----|------|
| 0 | GT150 |
| 1 | GT12x |
| 2 | GT17x |

## 10.7.2 全体初期化・システム情報

```c
long RAMScopeGT150AllInit(long UnitNo);

long RAMScopeGT150GetSysInfo(
    long UnitNo,
    SYSINFO *pSysInfo
);
```

- `UnitNo`は現構成で`0`。
- `pSysInfo`には`SYSINFO[16]`を渡す。
- LabVIEWではU8配列960バイトを事前確保する。

## 10.7.3 PGT構成

```c
long RAMScopeGT150PGT_SetMdlConfig(
    long UnitNo,
    long *SlotErr
);
```

- `SlotErr`はI32配列16要素。
- API戻り値に加え、`SlotErr[MdlNo_RAM]`も確認する。
- 非推奨の`RAMScopeGT150SetMdlConfig`ではなくPGT版を使用する。

## 10.7.4 測定条件

```c
long RAMScopeGT170SetMeasCond(
    long UnitNo,
    long MdlNo,
    MEASINFO_170 *pMeasInfo
);
```

- `pMeasInfo`は72バイトのunion。
- RAM測定では先頭20バイトの`MEASINFO_RAM170`を使用し、残りを0で初期化する。

## 10.7.5 測定チャンネル

```c
long RAMScopeGT170SetMeasCh(
    long UnitNo,
    long MdlNo,
    long ChNum,
    CHINFO_170 *pChInfo
);
```

- `ChNum`はチャンネル番号ではなく、`pChInfo`配列の要素数。
- RAM用`CHINFO_170`は1要素24バイト。
- 最大RAMチャンネル数は2048。

## 10.7.6 ロギング条件

```c
long RAMScopeGT150SetLoggingInfo(
    long UnitNo,
    LOGINFO *pLogInfo
);
```

- `LOGINFO`は136バイト。
- `mdl[16]`全要素を初期化する。
- 初期PoCでは`logSize=1`、`BuffSize=1`から開始し、取得周期と取りこぼしを見て調整する。

## 10.7.7 測定開始・停止

```c
long RAMScopeGT150MeasStart(long UnitNo);
long RAMScopeGT150MeasStop(long UnitNo);
```

両関数とも`MdlNo`を取らず、`UnitNo=0`だけを渡す。

## 10.7.8 表示用バッファ取得

```c
long RAMScopeGT150GetBufferData(
    long UnitNo,
    long MdlNo,
    void *pData,
    long *pDataNum,
    long *pLostDataNum
);
```

| 引数 | 方向 | 注意 |
|------|------|------|
| `pData` | out | U8配列を必要サイズで事前確保 |
| `pDataNum` | in/out | 呼び出し前に最大パケット数を設定 |
| `pLostDataNum` | out | 取りこぼし数 |

ベンダーサンプルでは`GetBufferData`の`pDataNum`が明示初期化されていないが、LabVIEW実装では必ず最大受信パケット数を設定する。

## 10.7.9 バッファ解放

```c
long RAMScopeGT150ReleaseBufferData(long UnitNo);
```

ベンダー簡易サンプルでは呼ばれていない。VIは用意し、次を実機比較して要否を確定する。

```text
A: MeasStop → ReleaseBufferData → DeviceExit
B: MeasStop → DeviceExit
```

---

# 10.8 構造体と定数

## 10.8.1 `SYSINFO`

```c
typedef struct SYSINFO {
    long module;
    long module_type;
    long probe_id;
    long interface_id;
    long version;
    long addinfo;
    long endian;
    long probe_version;
    long security_id_req;
    long security_id_size;
    long flash_enable;
    char name[16];
} SYSINFO;
```

サイズ：60バイト。`GetSysInfo`には16要素、合計960バイトを渡す。

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

`module_type`：

| 値 | 種別 |
|----|------|
| `0x00` | RAMモニタ |
| `0x02` | CAN |
| `0x03` | アナログ入力 |
| `0x0E` | 電源通信 / CTRL_USB |
| `0x0F` | 非接続 |

`module_type=0x00`の`module`を`MdlNo_RAM`、`0x02`を`MdlNo_CAN`として取得する。

## 10.8.2 `MEASINFO_170`

```c
typedef struct MEASINFO_RAM170 {
    long DummyInterval;
    long MeasPeri;
    long MeasUnit;
    long MeasPeri_reserve[2];
} MEASINFO_RAM170;

typedef struct MEASINFO_ADC170 {
    long DummyInterval;
    long MeasPeri;
    long MeasUnit;
} MEASINFO_ADC170;

typedef struct MEAS_CAN_CH_170 {
    long Enable;
    long Terminate;
    long MonitorOnly;
    long BaudRate;
    long BaudRateHigh;
    long SmpCnt;
    long SmpCntHigh;
    long BusMode;
} MEAS_CAN_CH_170;

typedef struct MEASINFO_CAN170 {
    long DummyInterval;
    long isUseFDFormat;
    MEAS_CAN_CH_170 Ch[2];
} MEASINFO_CAN170;

typedef union MEASINFO_170 {
    MEASINFO_RAM170 RAM;
    MEASINFO_ADC170 ADC;
    MEASINFO_CAN170 CAN;
} MEASINFO_170;
```

サイズ：72バイト。

RAM用途のオフセット：

| フィールド | オフセット |
|-----------|-----------|
| `DummyInterval` | 0 |
| `MeasPeri` | 4 |
| `MeasUnit` | 8 |
| `MeasPeri_reserve[0]` | 12 |
| `MeasPeri_reserve[1]` | 16 |

初期実装：

- `DummyInterval=100`
- `MeasPeri`は試験条件
- `MeasUnit=1`（usec）または`2`（msec）
- reserveは0で初期化

## 10.8.3 `CHINFO_170`

```c
typedef struct CHINFO_RAM170 {
    DWORD enable;
    DWORD core;
    DWORD address;
    DWORD size;
    DWORD sign;
    DWORD speed;
} CHINFO_RAM170;

typedef struct CHINFO_ADC170 {
    DWORD enable;
    DWORD magnification;
} CHINFO_ADC170;

typedef union CHINFO_170 {
    CHINFO_RAM170 RAM;
    CHINFO_ADC170 ADC;
} CHINFO_170;
```

RAM用1要素：24バイト。

| フィールド | オフセット | LabVIEW |
|-----------|-----------|---------|
| `enable` | 0 | U32 |
| `core` | 4 | U32 |
| `address` | 8 | U32 |
| `size` | 12 | U32 |
| `sign` | 16 | U32 |
| `speed` | 20 | U32 |

## 10.8.4 `LOGINFO`

```c
typedef struct LOGINFO {
    long logDevice;
    long limitHddSize;
    struct {
        long logSize;
        long BuffSize;
    } mdl[16];
} LOGINFO;
```

サイズ：136バイト。

| フィールド | オフセット |
|-----------|-----------|
| `logDevice` | 0 |
| `limitHddSize` | 4 |
| `mdl[i].logSize` | `8 + i * 8` |
| `mdl[i].BuffSize` | `12 + i * 8` |

---

# 10.9 RAM測定データパケット

RAMモニタの1パケット：

```text
Data[0]     I32  4byte
...
Data[N-1]   I32  4byte
Flag        U32  4byte
Time        U64  8byte
```

```text
PacketSize = 4 * N + 12
```

- `N`は`SetMeasCh`で設定したチャンネル数。
- Timestampは20ns単位。
- 秒換算：`TimestampSec = TimestampRaw * 20e-9`。
- `GetSysInfo.endian`と実データを比較し、必要な場合はバイト順を反転する。
- パケット解析は`RAMScope_Read.vi`へ埋め込まず、`RAMScope_Parse_Buffer.vi`へ分離する。

---

# 10.10 エラー処理

## 10.10.1 2系統のエラー

```text
CLFN error out
  → DLLロード、関数解決、LabVIEW呼び出し層

API ReturnCode
  → RAMScope内部の処理結果
```

API ReturnCodeは次で共通化する。

```text
ReturnCode
  → RAMScope_Code_To_Error.vi
  → Error_To_TestStatus.vi
  → Status.ctl / TestError.ctl / error out
```

## 10.10.2 確認済みコード

### MeasStart

| コード | 意味 |
|--------|------|
| `0x00000000` | 正常終了 |
| `0x30000001` | 関数内部例外 |
| `0x30000004` | 測定動作状態で呼び出し |
| `0x30000109` | ロギング情報未設定 |
| `0x30000500` | UnitNo不正 |
| `0x3000050E` | オフライン状態 |

### MeasStop

| コード | 意味 |
|--------|------|
| `0x00000000` | 正常終了 |
| `0x30000001` | 関数内部例外 |
| `0x30000105` | 測定処理スレッド停止失敗 |
| `0x30000500` | UnitNo不正 |
| `0x3000050E` | オフライン状態 |

### DeviceInit未接続PoC

実機未接続時に次を観測した。

```text
ReturnCode = 0x30100001
UnitNum    = 0
kind       = 0
```

`0x30100001`の正式な意味は未確認である。「実機未接続エラー」と断定せず、観測値として扱う。

---

# 10.11 CLFN共通設定

| 項目 | 設定 |
|------|------|
| DLL | `RAMScopeVP_API_x64.dll` |
| Function name | ヘッダの名前と完全一致 |
| Calling Convention | C |
| Thread | PoC中はRun in UI thread |
| Error checking | PoC中はMaximum |
| `long` | Signed 32-bit Integer |
| `unsigned long` / `DWORD` | Unsigned 32-bit Integer |
| `long*` | Pointer to Value |
| 配列 / 構造体ポインタ | Array Data Pointer。事前に必要サイズを確保 |

## 10.12 スレッドと排他

RAMScopeVP APIのスレッドセーフ性は未確認である。

- 同一デバイスへ複数のCLFNを同時実行しない。
- RAMポーリングとCAN送信を別ループで同時に行う場合は、DLLアクセスを1つのDevice Accessループへ集約する。
- PoC中はCLFNをUI threadで実行する。

## 10.13 配置とランタイム

- 64bit LabVIEW、64bit DLL、64bit C/C++ランタイムを揃える。
- `RAMScopeVP_API_x64.dll`を起点としたベンダー指定の相対配置を維持する。
- 64bit APIフォルダへx86版`mfc120jpn.dll`、`mfc120u.dll`、`msvcp120.dll`、`msvcr120.dll`を混在させない。
- `PGTMgrVP.dll`、`PGTMgrVP_ENG.dll`、`utillc.dll`、`pgtlib`配下をx86という理由だけで移動しない。
- 詳細は [10A](./10A_RAMScope実装手順_DLL準備とCLFN疎通確認.md) を正とする。

## 10.14 確認状況

### 確認済み

- `RAMScopeVP_API_x64.dll`はx64
- `RAMScopeGT150DeviceInit`は名前付きエクスポートとして存在
- 序数14でも同じ関数を解決可能
- DLLロード、関数解決、PowerShellからの実呼び出しに成功
- CLFNのDeviceInitプロトタイプを確定
- x86版VC++2013ランタイム混在によるエラー193を解消
- ヘッダとベンダーサンプルを入手

### 実機確認待ち

- GT170接続時のDeviceInit正常値
- `0x30100001`の正式定義
- AllInit以降の通しフロー
- PGT設定とSlotErr
- 実データのendian、値、Timestamp
- 長時間ポーリングとLostDataNum
- ReleaseBufferDataの要否
- RAMScope CAN機能の採用範囲
