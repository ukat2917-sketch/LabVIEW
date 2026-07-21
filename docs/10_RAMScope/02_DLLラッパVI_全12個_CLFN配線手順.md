# 10-02. DLL Wrapper 12個の個別作成手順

**監査日：2026-07-18**

本書は薄いDLL Wrapper 12個の監査済み索引である。各VIのCプロトタイプ、CLFN Parameters、左右端子、事前確保、Function Name、配線は[復元した全個別手順](./10B2_RAMScope_DLLラッパVI_CLFN配線手順.md)を参照する。

復元元の詳細手順と本書または[00_現行補正](./00_00A_00B監査結果と現行補正.md)が競合する場合は、現行補正を優先する。

---

## 1. 共通説明で削除してはいけない個別情報

各Wrapperの節には次を残す。

```text
0. 実現したい機能と責務
1～5. 入力データ、前提条件、アルゴリズム、Case選定理由
6. 全端子
7. CプロトタイプとCLFN Parameters
8. 左端子入力、右端子出力、error配線、Function Name
9. 単体テスト
```

通常Wrapperは`error in.status`をselectorとする外側Caseを持つ。

```text
Trueケース（error in.status=True：既存エラーあり）
  CLFNを呼ばない
  API ReturnCode=I32 0
  API固有出力=各VIで定義した安全値
  error out=元のerror in

Falseケース（error in.status=False：既存エラーなし）
  CLFNを1回呼ぶ
  CLFN ReturnとCLFN error outをRAMScope_Code_To_Error.viへ渡す
```

`RS_DLL_GT150DeviceExit.vi`だけはCleanup専用なので、既存エラーがあっても内部でClear Errors後にCLFNを呼ぶ。

---

## 2. 12個の個別手順

| VI | 詳細位置 | 個別に確認する端子・配列 |
|---|---|---|
| `RS_DLL_GT150DeviceInit.vi` | [DeviceInit](./10B2_RAMScope_DLLラッパVI_CLFN配線手順.md#3-rs_dll_gt150deviceinitvi) | `pUnitNum`、`kind`をPointer to Valueで左右配線 |
| `RS_DLL_GT150DeviceExit.vi` | [DeviceExit](./10B2_RAMScope_DLLラッパVI_CLFN配線手順.md#4-rs_dll_gt150deviceexitvi) | 引数なし、Cleanup専用、DeviceExit error |
| `RS_DLL_GT150AllInit.vi` | [AllInit](./10B2_RAMScope_DLLラッパVI_CLFN配線手順.md#5-rs_dll_gt150allinitvi) | UnitNo I32 Value |
| `RS_DLL_GT150GetSysInfo.vi` | [GetSysInfo](./10B2_RAMScope_DLLラッパVI_CLFN配線手順.md#6-rs_dll_gt150getsysinfovi) | U8[960]事前確保、Array Data Pointer |
| `RS_DLL_GT150PGT_SetMdlConfig.vi` | [PGT SetMdlConfig](./10B2_RAMScope_DLLラッパVI_CLFN配線手順.md#7-rs_dll_gt150pgt_setmdlconfigvi) | I32[16] SlotErr事前確保 |
| `RS_DLL_GT170SetMeasCond.vi` | [SetMeasCond](./10B2_RAMScope_DLLラッパVI_CLFN配線手順.md#8-rs_dll_gt170setmeascondvi) | U8[72] MEASINFO、UnitNo、MdlNo |
| `RS_DLL_GT170SetMeasCh.vi` | [SetMeasCh](./10B2_RAMScope_DLLラッパVI_CLFN配線手順.md#9-rs_dll_gt170setmeaschvi) | ChNum、U8[24×ChNum] CHINFO |
| `RS_DLL_GT150SetLoggingInfo.vi` | [SetLoggingInfo](./10B2_RAMScope_DLLラッパVI_CLFN配線手順.md#10-rs_dll_gt150setlogginginfovi) | U8[136] LOGINFO |
| `RS_DLL_GT150MeasStart.vi` | [MeasStart](./10B2_RAMScope_DLLラッパVI_CLFN配線手順.md#11-rs_dll_gt150measstartvi) | UnitNoのみ、MdlNoなし |
| `RS_DLL_GT150GetBufferData.vi` | [GetBufferData](./10B2_RAMScope_DLLラッパVI_CLFN配線手順.md#12-rs_dll_gt150getbufferdatavi) | Raw U8配列、pDataNum入力/出力、pLostDataNum |
| `RS_DLL_GT150ReleaseBufferData.vi` | [ReleaseBufferData](./10B2_RAMScope_DLLラッパVI_CLFN配線手順.md#13-rs_dll_gt150releasebufferdatavi) | UnitNoのみ、アイドル時に発行 |
| `RS_DLL_GT150MeasStop.vi` | [MeasStop](./10B2_RAMScope_DLLラッパVI_CLFN配線手順.md#14-rs_dll_gt150measstopvi) | UnitNoのみ、MdlNoなし |

---

## 3. 現行補正

### `RS_DLL_GT170SetMeasCh.vi`

GT170 RAM用構造体は`CHINFO_RAM170`で、1チャンネル24byteである。

```text
enable / core / address / size / sign / speed
```

`size`はバイト数そのものではなく、`0=1byte`、`1=2byte`、`2=4byte`のコードである。

### `RS_DLL_GT150ReleaseBufferData.vi`

復元元では呼出位置が未確定と記載されているが、現在は次で確定している。

```text
測定中     → 呼ばない
オフライン → 呼ばない
MeasStop成功後のアイドル状態 → 呼ぶ
```

### 全Wrapper

- Cの`long`はI32。
- Pointer出力は左端子へ初期値を入れ、右端子から結果を受ける。
- Array Data Pointerへ渡す配列はCLFN前に必要要素数を確保する。
- `Function Name`はヘッダの関数名と完全一致させる。
- 各Caseの全出力トンネルを配線し、`Use default if unwired`へ依存しない。
