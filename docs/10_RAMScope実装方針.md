# 10. RAMScope GT170 実装ガイド

> **本章をRAMScope実装の唯一の正本とする。**
>
> DLL準備、CLFN、共通エラー変換、薄いDLLラッパ、typedef、数値変換、構造体生成、Parser、公開API、最小PoCまでを上から順に実施する。
>
> 関数プロトタイプの一次情報は`docs/reference/RAMScopeVP.h`、ハードウェア定数は`docs/reference/GTHard.h`、呼び出し例は`docs/reference/samp_simple.cpp`を優先する。
>
> LabVIEWの関数名は、NI公式の日本語版LabVIEWプログラミングリファレンスを基準に、**日本語名（英語名）**の順で併記する。LabVIEWのバージョンによってパレット階層や末尾の「関数」表記が異なる場合は、`Ctrl + Space`でクイックドロップ（Quick Drop）を開き、表中の英語名で検索する。

**最終整理日：2026-07-16**

---

# 10.1 この章の使い方

## 10.1.1 実装の一本道

```text
STEP 0  環境準備とDLL疎通
  ↓
STEP 1  RAMScope_Code_To_Error.vi
  ↓
STEP 2  1関数1VIの薄いDLLラッパ12個
  ↓
STEP 3  typedefと数値⇔U8変換VI
  ↓
STEP 4  MEASINFO / CHINFO / LOGINFO Builder
  ↓
STEP 5  SYSINFO / 測定バッファ Parser
  ↓
STEP 6  1イベント1VIの公開API
  ↓
STEP 7  PoC_RAMScope_Main.viでRAM計測単体確認
  ↓
STEP 8  CAN方式確定・CAN単体PoC
  ↓
STEP 9  TestStand組み込み
```

RAMScopeは最初からTestStandへ組み込まない。各レイヤを単体確認してから次へ進む。

## 10.1.2 状態表記

| 表記 | 意味 |
|---|---|
| **確定** | ヘッダ、外部仕様書、または再現可能な実測で確認済み |
| **PoC済み** | 最小条件で動作確認済み |
| **実機確認待ち** | VI構成は作成できるが、GT170接続時の確認が未完了 |
| **未確定** | 推測で実装へ固定しない |

---

# 10.2 採用構成とフォルダ構成

## 10.2.1 なぜこの構成を採用するのか

RAMScopeVP APIはLabVIEW用VIではなく、C言語用DLL APIである。LabVIEWから使用するには、C関数、構造体、ポインタ、生バイト列、API独自ReturnCodeを、LabVIEWの数値、配列、クラスタ、標準error clusterへ変換する必要がある。

すべてを1個の巨大なVIへ入れると、DLL呼び出し、構造体変換、データ解析、試験フローのどこで失敗したかを切り分けにくい。そこで、責務ごとにレイヤを分ける。

| RAMScope実装で発生する問題 | 必要な仕組み | 配置先・主なVI |
|---|---|---|
| C関数をLabVIEWから呼ぶ | CLFN設定を1関数単位で隔離 | `10_DLL_Wrapper\RS_DLL_*` |
| CLFNエラーとAPI ReturnCodeが別経路 | 2系統を標準error clusterへ統合 | `RAMScope_Code_To_Error.vi` |
| API入力がC構造体ポインタ | LabVIEW設定値をC互換U8配列へ組み立てる | `Build_*_Raw.vi` |
| API出力が構造体や生バッファ | U8配列をLabVIEWクラスタや数値へ解析 | `Parse_*` |
| Endianと符号を扱う | 数値とU8配列の変換を共通部品化 | `U8x4_To_U32.vi`等 |
| TestStandからCLFN単位では扱いにくい | 接続、初期化、読出し等へまとめる | `30_Public\RAMScope_*` |
| TestStand組み込み前に下位層を検証したい | LabVIEW単体PoCを用意 | `PoC_RAMScope_Main.vi` |

```text
TestStand
  ↓
30_Public                 試験イベント単位へまとめる
  ↓
20_Data_Conversion        C構造体とLabVIEWデータ型の差を吸収する
00_Common
  ↓
10_DLL_Wrapper            DLL関数を1個だけ呼ぶ
  ↓
RAMScopeVP_API_x64.dll
```

## 10.2.2 採用構成

| 項目 | 採用内容 |
|---|---|
| 対象機器 | RAMScope GT170 |
| 接続 | USB3.0 |
| LabVIEW | 64bit版 |
| API | RAMScopeVP API 64bit版 |
| API DLL | `RAMScopeVP_API_x64.dll` |
| 呼び出し | ライブラリ関数呼び出しノード（Call Library Function Node） |
| Calling Convention | `C` |
| DLL状態管理 | API内部のグローバル状態。セッションハンドルは返らない |
| C/C++ランタイム | Visual C++ 2013 Redistributable x64 |

## 10.2.3 正式なフォルダ構成

```text
30_RAMScope\
├─ 00_Common\
│  ├─ RAMScope_Code_To_Error.vi
│  ├─ RAMScope_Channel.ctl
│  ├─ RAMScope_Meas_Config.ctl
│  ├─ RAMScope_Module_Log_Config.ctl
│  ├─ RAMScope_Module_Info.ctl
│  ├─ RAMScope_Channel_Value.ctl
│  ├─ RAMScope_Packet.ctl
│  ├─ RAMScope_Byte_Order.ctl
│  ├─ I32_To_LE_U8x4.vi
│  ├─ U32_To_LE_U8x4.vi
│  ├─ U8x4_To_I32.vi
│  ├─ U8x4_To_U32.vi
│  └─ U8x8_To_U64.vi
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
├─ 20_Data_Conversion\
│  ├─ Build_MEASINFO_170_Raw.vi
│  ├─ Build_CHINFO_170_Raw.vi
│  ├─ Build_LOGINFO_Raw.vi
│  ├─ Parse_SYSINFO_Array.vi
│  └─ RAMScope_Parse_Buffer.vi
│
├─ 30_Public\
│  ├─ RAMScope_Connect.vi
│  ├─ RAMScope_Init.vi
│  ├─ RAMScope_Set_Cond.vi
│  ├─ RAMScope_Log_Start.vi
│  ├─ RAMScope_Read.vi
│  ├─ RAMScope_Release.vi
│  ├─ RAMScope_Log_Stop.vi
│  └─ RAMScope_Close.vi
│
├─ 40_PoC\
│  └─ PoC_RAMScope_Main.vi
│
├─ 50_CAN\
└─ 90_TestStand\
```

`RAMScope_Context.ctl`はPoC完了まで作成しない。`UnitNo`、`MdlNo_RAM`、`MdlNo_CAN`、`Endian_RAM`、`Channel List`を個別配線する。

## 10.2.4 レイヤ責務

| レイヤ | 責務 | 含めないもの |
|---|---|---|
| `00_Common` | typedef、バイト変換、APIコード変換 | DLL呼び出し、機器状態遷移 |
| `10_DLL_Wrapper` | 1個のCLFNで1関数だけ呼ぶ | Builder、Parser、複数API制御、Status生成 |
| `20_Data_Conversion` | C構造体互換U8配列生成、生バイト列解析 | DLL呼び出し、測定開始・停止 |
| `30_Public` | ラッパと変換VIを接続し1イベントを完結 | TestStand固有変数への直接依存 |
| `40_PoC` | 公開APIを順に呼び実機単体確認 | 本番試験シナリオ |
| TestStand | 条件、順序、Wait、Loop、分岐、レポート、Cleanup | `RS_DLL_*`の直接呼び出し |

---

# 10.3 環境準備・DLL疎通

## 10.3.1 必要ソフトウェア

- LabVIEW 64bit
- RAMScopeVP / RAMScopeVP API 64bit版
- RAMScope USBドライバ
- PGTツール
- Visual C++ 2013 Redistributable x64

Visual C++ 2015-2022 Redistributable x64は、別コンポーネントが要求する場合だけ追加する。Visual C++ 2013の代替ではない。

確認済みパス：

```text
C:\DTSinsight\RAMScopeVP\app\RAMScopeVP_API(64bit)\RAMScopeVP_API_x64.dll
C:\DTSinsight\RAMScopeVP_API\header\RAMScopeVP.h
```

## 10.3.2 DLL相対配置

API DLLを起点としたベンダー指定の相対位置を維持する。

```text
RAMScopeVP_API(64bit)\
├─ RAMScopeVP_API_x64.dll
├─ UtilLCServer.exe
├─ utillc.dll
├─ PGTMgrServer.exe
├─ PGTMgrVP.dll
├─ PGTMgrVP_ENG.dll
├─ GT170_x64.dll
├─ GT170USB_x64.dll
└─ pgtlib\
```

## 10.3.3 エラー193対策

64bit APIフォルダへx86版VC++2013ランタイムが混在すると、エラー193になる可能性がある。

```text
mfc120jpn.dll
mfc120u.dll
msvcp120.dll
msvcr120.dll
```

上記ファイルが実際にx86であることを確認できた場合のみ、復元可能なバックアップへ移動する。`PGTMgrVP.dll`、`PGTMgrVP_ENG.dll`、`utillc.dll`、`pgtlib`は移動しない。

## 10.3.4 PowerShell疎通合格条件

```text
PowerShell 64-bit : True
Handle            : 0x0以外
Name Found        : True
Ordinal Found     : True
Name Address      : Ordinal Address
```

実機未接続時に観測した`0x30100001`は正式定義未確認であり、「未接続エラー」と断定しない。

---

# 10.4 APIライフサイクルと型

## 10.4.1 呼び出し順

```text
DeviceInit
  → AllInit
  → GetSysInfo
  → Parse_SYSINFO
  → PGT_SetMdlConfig
  → SetMeasCond
  → SetMeasCh
  → SetLoggingInfo
  → MeasStart
  → GetBufferData
  → MeasStop
  → ReleaseBufferData（要否検証中）
  → DeviceExit
```

## 10.4.2 C型とLabVIEW型

| C型 | LabVIEW |
|---|---|
| `long` | I32 |
| `long *` | I32 / Pointer to Value |
| `unsigned long` / `DWORD` | U32 |
| 構造体ポインタ | U8一次元配列 / Array Data Pointer |
| `long[]` | I32一次元配列 / Array Data Pointer |

Windowsの`long`は64bit DLLでも32bit。I64へ変更しない。

## 10.4.3 使用構造体サイズ

| 構造体 | サイズ |
|---|---:|
| `SYSINFO` | 60byte × 16 = 960byte |
| `MEASINFO_170` | 72byte |
| RAM用`CHINFO_170` | 24byte × ChNum |
| `LOGINFO` | 136byte |

RAM測定パケットの現行作業定義：

```text
Channel Data = 4byte × ChNum
Flag         = 4byte
Timestamp    = 8byte
Packet Size  = 4 × ChNum + 12
```

---

# 10.5 LabVIEW共通作業ルール

## 10.5.1 関数名とパレット位置

| 日本語名 | 英語名 | 関数パレットの目安 |
|---|---|---|
| ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| Forループ | For Loop | プログラミング → ストラクチャ |
| 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 名前でバンドル | Bundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 配列サイズ | Array Size | プログラミング → 配列 |
| 指標配列 | Index Array | プログラミング → 配列 |
| 部分配列 | Array Subset | プログラミング → 配列 |
| 配列初期化 | Initialize Array | プログラミング → 配列 |
| 部分配列置換 | Replace Array Subset | プログラミング → 配列 |
| 配列連結追加 | Build Array | プログラミング → 配列 |
| 1D配列検索 | Search 1D Array | プログラミング → 配列 |
| 数値結合 | Join Numbers | プログラミング → 数値 → データ操作 |
| 数値分割 | Split Number | プログラミング → 数値 → データ操作 |
| 型変換 | Type Cast | プログラミング → 数値 → データ操作 |
| 文字列にフォーマット | Format Into String | プログラミング → 文字列 |
| バイト配列から文字列 | Byte Array To String | プログラミング → 文字列 → 文字列/配列/パス変換 |
| 等しい? | Equal? | プログラミング → 比較 |
| 以上? | Greater Or Equal? | プログラミング → 比較 |
| 以下? | Less Or Equal? | プログラミング → 比較 |
| 選択 | Select | プログラミング → 比較 |
| 複合演算 | Compound Arithmetic | プログラミング → ブール |
| NOT | Not | プログラミング → ブール |
| 倍精度浮動小数点に変換 | To Double Precision Float | プログラミング → 数値 → 変換 |
| 加算 | Add | プログラミング → 数値 |
| 減算 | Subtract | プログラミング → 数値 |
| 乗算 | Multiply | プログラミング → 数値 |

## 10.5.2 通常VIのエラーガード

```text
error in
  → 名前でバンドル解除（status）
  → ケースストラクチャ
      True : 実処理を呼ばず、元エラーと安全な初期出力を返す
      False: 実処理を実行
```

全ケースの出力トンネルを配線し、`Use default if unwired`へ依存しない。

## 10.5.3 ローカル検証エラーコード

| コード | 用途 |
|---:|---|
| `-700101` | U8x4変換VIの入力サイズ不正 |
| `-700102` | U8x8変換VIの入力サイズ不正 |
| `-700111` | CHINFOチャンネル数不正 |
| `-700112` | LOGINFOモジュール番号または重複不正 |
| `-700120` | SYSINFOサイズ不正 |
| `-700130` | Buffer Parser入力不正 |
| `-700131` | Raw Buffer不足 |

## 10.5.4 U8配列の単体テスト表示設定

U8配列のバイト値を16進数で確認するときは、配列枠ではなく**配列内の数値セル**を右クリックして設定する。

```text
表示形式 → 16進数
表示項目 → 基数
```

LabVIEW上では`0x78`ではなく`x78`と表示される。資料上の`0x78`とLabVIEW表示の`x78`は同じ値を表す。

出力数値も16進数で確認する場合は、出力表示器で同じ設定を行う。

### 3要素配列を作る方法

4要素配列から3要素へ減らす場合：

1. 配列の指標表示を`3`にして4番目の要素を表示する。
2. 4番目の数値セルを右クリックする。
3. `データ操作 → 要素を削除`を選ぶ。
4. 指標表示を`0`へ戻す。
5. 配列サイズ（Array Size）を一時接続し、実サイズが`3`であることを確認する。

表示行数を3行へ縮めても、実際の配列要素数は変わらない。

---

# 10.6 `RAMScope_Code_To_Error.vi`

## 10.6.1 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `API ReturnCode` | 入力 | I32 |
| `Function Name` | 入力 | String |
| `error in` | 入力 | error cluster |
| `error out` | 出力 | error cluster |

## 10.6.2 配置する関数およびSubVI等

| 日本語名 | 英語名 | 配置場所 |
|---|---|---|
| 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 等しい? | Equal? | プログラミング → 比較 |
| 型変換 | Type Cast | プログラミング → 数値 → データ操作 |
| 文字列にフォーマット | Format Into String | プログラミング → 文字列 |
| 名前でバンドル | Bundle By Name | プログラミング → クラスタ、クラス、バリアント |

## 10.6.3 配線順

1. `error in`を名前でバンドル解除へ接続し、`status`を取り出す。
2. `status`を外側ケースストラクチャへ接続する。
3. 外側Trueでは`error in`をそのまま`error out`へ接続する。
4. 外側Falseで`API ReturnCode == 0`を判定し、内側ケースストラクチャへ接続する。
5. 内側Trueでは正常な`error in`をそのまま出力する。
6. 内側Falseでは`API ReturnCode`を型変換でU32として解釈する。
7. 文字列にフォーマットへ次を設定する。

```text
RAMScope %s failed. ReturnCode=0x%08X (%d)
```

8. 名前でバンドルへ正常クラスタを接続し、`status=True`、`code=API ReturnCode`、`source=生成文字列`を設定する。
9. 名前でバンドル出力を`error out`へ接続する。

## 10.6.4 単体テスト

| error in | ReturnCode | 期待結果 |
|---|---:|---|
| 正常 | 0 | 正常クラスタ |
| 正常 | `806354945` | sourceに`0x30100001` |
| code=1234の既存エラー | 任意 | 1234を保持 |
| 正常 | -1 | sourceに`0xFFFFFFFF` |

---

# 10.7 薄いDLLラッパ12個

## 10.7.1 CLFN共通設定

| 項目 | 設定 |
|---|---|
| Library | `RAMScopeVP_API_x64.dll`のフルパス |
| Calling Convention | `C` |
| Thread | PoC中は`Run in UI thread` |
| Error checking | PoC中は`Maximum` |
| Return | Numeric / Signed 32-bit Integer / Value |

通常ラッパは`error in.status=True`でCLFNをスキップする。`DeviceExit`だけはCleanup用なので前段エラーがあっても呼ぶ。

## 10.7.2 CLFN一覧

| VI | 関数 | CLFN入力 | 初期化・出力 |
|---|---|---|---|
| `RS_DLL_GT150DeviceInit.vi` | `RAMScopeGT150DeviceInit` | I32 Pointer ×2 | 左へ0、右からUnitNum/kind |
| `RS_DLL_GT150DeviceExit.vi` | `RAMScopeGT150DeviceExit` | なし | ReturnCode |
| `RS_DLL_GT150AllInit.vi` | `RAMScopeGT150AllInit` | UnitNo I32 | ReturnCode |
| `RS_DLL_GT150GetSysInfo.vi` | `RAMScopeGT150GetSysInfo` | UnitNo、U8 Pointer | U8[960]を事前確保 |
| `RS_DLL_GT150PGT_SetMdlConfig.vi` | `RAMScopeGT150PGT_SetMdlConfig` | UnitNo、I32 Pointer | I32[16]を事前確保 |
| `RS_DLL_GT170SetMeasCond.vi` | `RAMScopeGT170SetMeasCond` | UnitNo、MdlNo、U8[72] | Builder出力 |
| `RS_DLL_GT170SetMeasCh.vi` | `RAMScopeGT170SetMeasCh` | UnitNo、MdlNo、ChNum、U8[`24×ChNum`] | Builder出力 |
| `RS_DLL_GT150SetLoggingInfo.vi` | `RAMScopeGT150SetLoggingInfo` | UnitNo、U8[136] | Builder出力 |
| `RS_DLL_GT150MeasStart.vi` | `RAMScopeGT150MeasStart` | UnitNo | ReturnCode |
| `RS_DLL_GT150GetBufferData.vi` | `RAMScopeGT150GetBufferData` | UnitNo、MdlNo、U8 buffer、DataNum Pointer、Lost Pointer | Raw/DataNum/LostDataNum |
| `RS_DLL_GT150ReleaseBufferData.vi` | `RAMScopeGT150ReleaseBufferData` | UnitNo | ReturnCode |
| `RS_DLL_GT150MeasStop.vi` | `RAMScopeGT150MeasStop` | UnitNo | ReturnCode |

各CLFNの戻り値とCLFN error outを`RAMScope_Code_To_Error.vi`へ接続する。

---

# 10.8 typedef作成

## 10.8.1 共通手順

1. プロジェクトエクスプローラで`30_RAMScope\00_Common`を右クリックする。
2. `新規 → タイプ定義`を選ぶ。
3. 制御器エディタへクラスタまたは列挙体を配置する。
4. 必要な制御器をクラスタ内へ配置する。
5. 数値制御器を右クリックし、表現形式をI32、U32、U64、DBLへ合わせる。
6. フィールド名を設定する。
7. `.ctl`として保存する。

`新規 → タイプ定義`から作成した場合、後からType Def.へ切り替える操作は不要。

## 10.8.2 型一覧

| typedef | 主なフィールド |
|---|---|
| `RAMScope_Byte_Order.ctl` | `Little Endian`、`Big Endian` |
| `RAMScope_Meas_Config.ctl` | DummyInterval I32、MeasPeri I32、MeasUnit I32 |
| `RAMScope_Channel.ctl` | Name、Enable、Core、Address、Size、Sign、Speed、Scale、Offset、Unit |
| `RAMScope_Module_Log_Config.ctl` | MdlNo I32、LogSize I32、BufferSize I32 |
| `RAMScope_Module_Info.ctl` | SYSINFO解析結果 |
| `RAMScope_Channel_Value.ctl` | 1チャンネルのRaw値、実値、工学値 |
| `RAMScope_Packet.ctl` | Channel Values、Flag、Timestamp |

`ChNum`は`Array Size(Channel List)`で算出し、手入力値を別に持たせない。

---

# 10.9 数値⇔U8変換VI

## 10.9.1 `U8x4_To_U32.vi`

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Bytes` | 入力 | U8一次元配列 |
| `Byte Order` | 入力 | `RAMScope_Byte_Order.ctl` |
| `error in` | 入力 | error cluster |
| `Value` | 出力 | U32 |
| `error out` | 出力 | error cluster |

### 2. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所 |
|---:|---|---|---|
| 1 | 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 3 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 1 | 配列サイズ | Array Size | プログラミング → 配列 |
| 1 | 等しい? | Equal? | プログラミング → 比較 |
| 1 | 指標配列 | Index Array | プログラミング → 配列 |
| 6 | 数値結合 | Join Numbers | プログラミング → 数値 → データ操作 |
| 1 | 文字列にフォーマット | Format Into String | プログラミング → 文字列 |
| 1 | 名前でバンドル | Bundle By Name | プログラミング → クラスタ、クラス、バリアント |

### 3. 配線順

1. `error in`を名前でバンドル解除へ接続し、`status`を外側ケースストラクチャへ接続する。
2. 外側TrueでU32定数`0`を`Value`へ、`error in`を`error out`へ接続する。
3. 外側Falseで`Bytes`を配列サイズへ接続する。
4. 配列サイズ出力とI32定数`4`を等しい?へ接続し、結果を2個目のケースストラクチャへ接続する。
5. サイズ不正のFalseケースではValue=0とし、code=`-700101`のerror clusterを生成する。
6. サイズ正常のTrueケースで指標配列を4出力へ広げる。
7. 4個のindex端子へ上から`0`、`1`、`2`、`3`を接続する。
8. 出力を上から`b0`、`b1`、`b2`、`b3`としてByte Orderケースへ渡す。
9. Little Endianケースでは次の順で数値結合する。

```text
低位16bit: high=b1, low=b0
高位16bit: high=b3, low=b2
U32      : high=高位16bit, low=低位16bit
```

10. Big Endianケースでは次の順で数値結合する。

```text
高位16bit: high=b0, low=b1
低位16bit: high=b2, low=b3
U32      : high=高位16bit, low=低位16bit
```

11. Byte Orderの両ケースで変換値を`Value`へ、正常なerror clusterを`error out`へ接続する。

### 4. 単体テスト

| Bytes | Byte Order | 期待Value |
|---|---|---|
| `x78 x56 x34 x12` | Little Endian | `x12345678` |
| `x12 x34 x56 x78` | Big Endian | `x12345678` |
| `xFF xFF xFF xFF` | Little Endian | `xFFFFFFFF` |
| 3要素 | 任意 | Value=0、code=`-700101` |
| 既存エラー | 任意 | 既存エラー保持、Value=0 |

## 10.9.2 `U8x4_To_I32.vi`

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Bytes` | 入力 | U8一次元配列 |
| `Byte Order` | 入力 | `RAMScope_Byte_Order.ctl` |
| `error in` | 入力 | error cluster |
| `Value` | 出力 | I32 |
| `error out` | 出力 | error cluster |

### 2. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所 |
|---:|---|---|---|
| 1 | `U8x4_To_U32.vi` | SubVI | `30_RAMScope\00_Common` |
| 1 | 型変換 | Type Cast | プログラミング → 数値 → データ操作 |
| 1 | I32数値定数 | I32 Numeric Constant | プログラミング → 数値 |

### 3. 配線順

1. ブロックダイアグラム左側へ`U8x4_To_U32.vi`を配置する。
2. `Bytes`入力をSubVIの`Bytes`へ接続する。
3. `Byte Order`入力をSubVIの`Byte Order`へ接続する。
4. `error in`をSubVIの`error in`へ接続する。
5. 型変換をSubVIの右側へ配置する。
6. SubVIのU32 `Value`を型変換の入力`x`へ接続する。
7. I32数値定数`0`を作り、右クリックして表現形式がI32であることを確認する。
8. I32定数を型変換の型指定入力`type`へ接続する。
9. 型変換のI32出力を本VIの`Value`へ接続する。
10. SubVIの`error out`を本VIの`error out`へ接続する。

通常の数値変換ではなく型変換を使用する。これにより32bitのビット列を変えずに符号付きI32として解釈する。

### 4. 単体テスト

| Bytes | Byte Order | 期待Value | 期待error |
|---|---|---:|---|
| `xFF xFF xFF xFF` | Little Endian | `-1` | 正常 |
| `x00 x00 x00 x80` | Little Endian | `-2147483648` | 正常 |
| `x7F xFF xFF xFF` | Big Endian | `2147483647` | 正常 |
| 3要素 | 任意 | 0 | code=`-700101` |
| 既存エラー | 任意 | 0 | 既存エラー保持 |

## 10.9.3 `U8x8_To_U64.vi`

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Bytes` | 入力 | U8一次元配列 |
| `Byte Order` | 入力 | `RAMScope_Byte_Order.ctl` |
| `error in` | 入力 | error cluster |
| `Value` | 出力 | U64 |
| `error out` | 出力 | error cluster |

### 2. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所 |
|---:|---|---|---|
| 1 | 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 3 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 1 | 配列サイズ | Array Size | プログラミング → 配列 |
| 1 | 等しい? | Equal? | プログラミング → 比較 |
| 2 | 部分配列 | Array Subset | プログラミング → 配列 |
| 2 | `U8x4_To_U32.vi` | SubVI | `30_RAMScope\00_Common` |
| 2 | 数値結合 | Join Numbers | プログラミング → 数値 → データ操作 |
| 1 | 文字列にフォーマット | Format Into String | プログラミング → 文字列 |
| 1 | 名前でバンドル | Bundle By Name | プログラミング → クラスタ、クラス、バリアント |

### 3. 配線順

1. `error in`を名前でバンドル解除へ接続し、`status`を外側ケースストラクチャへ接続する。
2. 外側TrueではU64定数`0`を`Value`へ、`error in`を`error out`へ接続する。
3. 外側Falseで`Bytes`を配列サイズへ接続する。
4. 配列サイズ出力とI32定数`8`を等しい?へ接続し、結果をサイズ判定ケースへ接続する。
5. サイズ不正のFalseケースでValue=0、status=True、code=`-700102`、sourceに実サイズを含むerror clusterを生成する。
6. サイズ正常のTrueケースへ部分配列を2個配置する。
7. 1個目の部分配列へ`Bytes`、index=`0`、length=`4`を接続し、`First4`を作る。
8. 2個目の部分配列へ`Bytes`、index=`4`、length=`4`を接続し、`Last4`を作る。
9. `U8x4_To_U32.vi`を2個横に配置する。
10. `First4`を1個目SubVIの`Bytes`へ、`Last4`を2個目SubVIの`Bytes`へ接続する。
11. `Byte Order`を両SubVIの`Byte Order`へ分岐して接続する。
12. `error in`を1個目SubVIへ、1個目の`error out`を2個目SubVIの`error in`へ直列接続する。
13. Byte Orderを3個目のケースストラクチャへ接続する。
14. Little Endianケースでは数値結合へ次を接続する。

```text
high ← Last4のU32
low  ← First4のU32
```

15. Big Endianケースでは数値結合へ次を接続する。

```text
high ← First4のU32
low  ← Last4のU32
```

16. 両ケースの数値結合出力を`Value`へ接続する。
17. 2個目SubVIの`error out`を本VIの`error out`へ接続する。

### 4. 単体テスト

| Bytes | Byte Order | 期待Value |
|---|---|---|
| `x32 x00 x00 x00 x00 x00 x00 x00` | Little Endian | 50 |
| `x00 x00 x00 x00 x00 x00 x00 x32` | Big Endian | 50 |
| `x78 x56 x34 x12 xEF xCD xAB x90` | Little Endian | `x90ABCDEF12345678` |
| 7要素 | 任意 | Value=0、code=`-700102` |
| 既存エラー | 任意 | 既存エラー保持、Value=0 |

## 10.9.4 `U32_To_LE_U8x4.vi`

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Value` | 入力 | U32 |
| `error in` | 入力 | error cluster |
| `Bytes` | 出力 | U8一次元配列 |
| `error out` | 出力 | error cluster |

### 2. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所 |
|---:|---|---|---|
| 1 | 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 1 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 3 | 数値分割 | Split Number | プログラミング → 数値 → データ操作 |
| 1 | 配列連結追加 | Build Array | プログラミング → 配列 |

### 3. 配線順

1. `error in`を名前でバンドル解除へ接続し、`status`をケースストラクチャへ接続する。
2. Trueケースで空のU8一次元配列を`Bytes`へ、`error in`を`error out`へ接続する。
3. Falseケースへ数値分割を3個配置する。
4. `Value`を1個目の数値分割へ接続する。
5. 1個目の上側出力`most significant half`を`High Word`、下側出力`least significant half`を`Low Word`として扱う。
6. `Low Word`を2個目の数値分割へ接続する。
7. 2個目の上側出力を`b1`、下側出力を`b0`として扱う。
8. `High Word`を3個目の数値分割へ接続する。
9. 3個目の上側出力を`b3`、下側出力を`b2`として扱う。
10. 配列連結追加を4入力へ広げる。
11. 上から`b0`、`b1`、`b2`、`b3`を接続する。
12. 配列連結追加のU8一次元配列を`Bytes`へ接続する。
13. `error in`を変更せず`error out`へ接続する。

### 4. 単体テスト

| Value | 期待Bytes |
|---:|---|
| `x12345678` | `x78 x56 x34 x12` |
| `x00000064` | `x64 x00 x00 x00` |
| `xFFFFFFFF` | `xFF xFF xFF xFF` |
| 既存エラー | 空配列、既存エラー保持 |

## 10.9.5 `I32_To_LE_U8x4.vi`

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Value` | 入力 | I32 |
| `error in` | 入力 | error cluster |
| `Bytes` | 出力 | U8一次元配列 |
| `error out` | 出力 | error cluster |

### 2. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所 |
|---:|---|---|---|
| 1 | 型変換 | Type Cast | プログラミング → 数値 → データ操作 |
| 1 | U32数値定数 | U32 Numeric Constant | プログラミング → 数値 |
| 1 | `U32_To_LE_U8x4.vi` | SubVI | `30_RAMScope\00_Common` |

### 3. 配線順

1. 型変換をブロックダイアグラム左側へ配置する。
2. I32 `Value`を型変換の`x`へ接続する。
3. U32数値定数`0`を作り、型変換の`type`へ接続する。
4. 型変換のU32出力を`U32_To_LE_U8x4.vi`の`Value`へ接続する。
5. `error in`をSubVIの`error in`へ接続する。
6. SubVIの`Bytes`を本VIの`Bytes`へ接続する。
7. SubVIの`error out`を本VIの`error out`へ接続する。

### 4. 単体テスト

| Value | 期待Bytes |
|---:|---|
| 100 | `x64 x00 x00 x00` |
| -1 | `xFF xFF xFF xFF` |
| `-2147483648` | `x00 x00 x00 x80` |
| 既存エラー | 空配列、既存エラー保持 |

---

# 10.10 構造体Builder

## 10.10.1 `Build_MEASINFO_170_Raw.vi`

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Meas Config` | 入力 | `RAMScope_Meas_Config.ctl` |
| `error in` | 入力 | error cluster |
| `MEASINFO_170 Raw` | 出力 | U8一次元配列 |
| `error out` | 出力 | error cluster |

### 2. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所 |
|---:|---|---|---|
| 2 | 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 1 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 1 | 配列初期化 | Initialize Array | プログラミング → 配列 |
| 3 | `I32_To_LE_U8x4.vi` | SubVI | `30_RAMScope\00_Common` |
| 3 | 部分配列置換 | Replace Array Subset | プログラミング → 配列 |

### 3. 配線順

1. `error in`を1個目の名前でバンドル解除へ接続し、`status`をケースストラクチャへ接続する。
2. TrueケースでU8定数`0`とI32定数`72`を配列初期化へ接続し、U8[72]を`MEASINFO_170 Raw`へ接続する。
3. Trueケースで`error in`を`error out`へ接続する。
4. Falseケースで同じくU8[72]のゼロ配列を作成する。
5. `Meas Config`を2個目の名前でバンドル解除へ接続し、`DummyInterval`、`MeasPeri`、`MeasUnit`を表示する。
6. `I32_To_LE_U8x4.vi`を3個横に配置する。
7. `DummyInterval`を1個目、`MeasPeri`を2個目、`MeasUnit`を3個目の`Value`へ接続する。
8. `error in`を1個目SubVIへ、1個目の`error out`を2個目へ、2個目を3個目へ直列接続する。
9. 部分配列置換を3個直列に配置する。
10. U8[72]を1個目の配列入力へ接続し、index=`0`、new element/subarray=`DummyInterval Bytes`とする。
11. 1個目の出力配列を2個目へ接続し、index=`4`、new element/subarray=`MeasPeri Bytes`とする。
12. 2個目の出力配列を3個目へ接続し、index=`8`、new element/subarray=`MeasUnit Bytes`とする。
13. 3個目の出力配列を`MEASINFO_170 Raw`へ接続する。
14. 3個目SubVIの`error out`を本VIの`error out`へ接続する。
15. offset 12～71はゼロのまま残す。

### 4. 単体テスト

入力：

```text
DummyInterval = 100
MeasPeri      = 100
MeasUnit      = 2
```

期待出力：

```text
index 0..3   = x64 x00 x00 x00
index 4..7   = x64 x00 x00 x00
index 8..11  = x02 x00 x00 x00
index 12..71 = x00
Array Size   = 72
error out    = 正常
```

## 10.10.2 `Build_CHINFO_170_Raw.vi`

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Channel List` | 入力 | `RAMScope_Channel.ctl`一次元配列 |
| `error in` | 入力 | error cluster |
| `ChNum` | 出力 | I32 |
| `CHINFO_170 Raw` | 出力 | U8一次元配列 |
| `error out` | 出力 | error cluster |

### 2. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所 |
|---:|---|---|---|
| 1 | 配列サイズ | Array Size | プログラミング → 配列 |
| 1 | 以上? | Greater Or Equal? | プログラミング → 比較 |
| 1 | 以下? | Less Or Equal? | プログラミング → 比較 |
| 1 | 複合演算 | Compound Arithmetic | プログラミング → ブール |
| 1 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 1 | Forループ | For Loop | プログラミング → ストラクチャ |
| 1 | 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 6 | `U32_To_LE_U8x4.vi` | SubVI | `30_RAMScope\00_Common` |
| 2 | 配列連結追加 | Build Array | プログラミング → 配列 |

### 3. 配線順

1. `Channel List`を配列サイズへ接続し、出力を`ChNum`へ接続する。
2. `ChNum >= 1`と`ChNum <= 2048`を作り、複合演算ANDへ接続する。
3. AND出力をケースストラクチャへ接続する。
4. Falseケースで空U8配列、ChNum、code=`-700111`のerror clusterを出力する。
5. TrueケースへForループを配置し、`Channel List`を自動指標付け入力する。
6. ForループへU8空配列用シフトレジスタとerror cluster用シフトレジスタを追加する。
7. 各反復のChannelを名前でバンドル解除へ接続し、Enable、Core、Address、Size、Sign、Speedを取り出す。
8. 6値を6個の`U32_To_LE_U8x4.vi`へ接続し、error clusterを直列接続する。
9. 1個目の配列連結追加を右クリックし、`入力を連結`を有効にする。
10. Enable、Core、Address、Size、Sign、Speedの各U8[4]を順に接続し、U8[24]を作る。
11. 2個目の配列連結追加も`入力を連結`にする。
12. 左へシフトレジスタの累積配列、右へ今回のU8[24]を接続する。
13. 出力を右シフトレジスタへ接続する。
14. ループ後の累積配列を`CHINFO_170 Raw`へ接続する。
15. ループ後のerror clusterを`error out`へ接続する。

### 4. 単体テスト

| Channel List | 期待ChNum | 期待Array Size |
|---|---:|---:|
| 1要素 | 1 | 24 |
| 2要素 | 2 | 48 |
| 0要素 | 0 | code=`-700111` |

## 10.10.3 `Build_LOGINFO_Raw.vi`

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `LogDevice` | 入力 | I32 |
| `LimitHddSize` | 入力 | I32 |
| `Module Log Configs` | 入力 | `RAMScope_Module_Log_Config.ctl`一次元配列 |
| `error in` | 入力 | error cluster |
| `LOGINFO Raw` | 出力 | U8一次元配列 |
| `error out` | 出力 | error cluster |

### 2. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所 |
|---:|---|---|---|
| 1 | 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 2以上 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 2 | 配列初期化 | Initialize Array | プログラミング → 配列 |
| 1 | Forループ | For Loop | プログラミング → ストラクチャ |
| 1 | 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 4 | `I32_To_LE_U8x4.vi` | SubVI | `30_RAMScope\00_Common` |
| 5 | 部分配列置換 | Replace Array Subset | プログラミング → 配列 |
| 1 | 指標配列 | Index Array | プログラミング → 配列 |
| 2 | 以上? / 以下? | Greater Or Equal? / Less Or Equal? | プログラミング → 比較 |
| 1 | NOT | Not | プログラミング → ブール |
| 1 | 複合演算 | Compound Arithmetic | プログラミング → ブール |
| 2 | 乗算 / 加算 | Multiply / Add | プログラミング → 数値 |
| 1 | 文字列にフォーマット | Format Into String | プログラミング → 文字列 |
| 1 | 名前でバンドル | Bundle By Name | プログラミング → クラスタ、クラス、バリアント |

### 3. 配線順

1. `error in`を名前でバンドル解除へ接続し、`status`を外側ケースストラクチャへ接続する。
2. 外側TrueでU8[136]のゼロ配列を`LOGINFO Raw`へ、`error in`を`error out`へ接続する。
3. 外側FalseでU8定数`0`とI32定数`136`を配列初期化へ接続し、LOGINFO初期配列を作る。
4. Boolean定数FalseとI32定数`16`を2個目の配列初期化へ接続し、Seen Boolean[16]を作る。
5. `I32_To_LE_U8x4.vi`を2個配置し、`LogDevice`と`LimitHddSize`を変換する。
6. `error in`をLogDevice変換へ、LogDevice変換のerror outをLimitHddSize変換へ接続する。
7. 部分配列置換を2個直列に配置する。
8. U8[136]へLogDevice Bytesをindex=`0`で書き込む。
9. 続けてLimitHddSize Bytesをindex=`4`で書き込む。
10. Forループを配置し、`Module Log Configs`を自動指標付け入力する。
11. Forループへ次の3本のシフトレジスタを追加する。

```text
LOGINFO U8[136]
Seen Boolean[16]
error cluster
```

12. ループ内で先にerror statusをケースストラクチャへ接続する。Trueなら3本のシフトレジスタを変更せず右側へ渡す。
13. errorなしのFalseケースで1要素のModule Log Configを名前でバンドル解除し、MdlNo、LogSize、BufferSizeを取り出す。
14. `MdlNo >= 0`と`MdlNo <= 15`を作る。
15. Seen配列を指標配列へ接続し、indexへMdlNoを接続する。
16. Seen[MdlNo]へNOTを接続する。
17. 範囲内判定2個とNOT出力を複合演算ANDへ接続する。
18. AND出力を有効/無効判定ケースストラクチャへ接続する。
19. 有効Trueケースで`Log index = 8 + MdlNo × 8`を計算する。
20. 同じケースで`Buffer index = 12 + MdlNo × 8`を計算する。
21. `I32_To_LE_U8x4.vi`を2個配置し、LogSizeとBufferSizeを変換する。error clusterを直列接続する。
22. 累積LOGINFO配列へLogSize BytesをLog indexで書き込む。
23. 続けてBufferSize BytesをBuffer indexで書き込む。
24. Seen配列へBoolean Trueをindex=MdlNoで書き込み、重複済みとして更新する。
25. 更新したLOGINFO、Seen、errorを右シフトレジスタへ接続する。
26. 無効FalseケースではLOGINFOとSeenを変更せず、code=`-700112`のerror clusterを生成して右シフトレジスタへ接続する。
27. ループ後のLOGINFO配列を`LOGINFO Raw`へ接続する。
28. ループ後のerror clusterを`error out`へ接続する。

### 4. 単体テスト

入力例：

```text
LogDevice   = 1
LimitHddSize = 0
Module Log Configs[0]
  MdlNo      = 0
  LogSize    = 100
  BufferSize = 200
```

期待出力：

```text
index 0..3   = x01 x00 x00 x00
index 4..7   = x00 x00 x00 x00
index 8..11  = x64 x00 x00 x00
index 12..15 = xC8 x00 x00 x00
Array Size   = 136
error out    = 正常
```

異常テスト：

| 条件 | 期待結果 |
|---|---|
| MdlNo=16 | code=`-700112` |
| 同じMdlNoを2回指定 | code=`-700112` |
| 既存エラー | U8[136]ゼロ配列、既存エラー保持 |

---

# 10.11 Parser

## 10.11.1 `Parse_SYSINFO_Array.vi`

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `SYSINFO Raw` | 入力 | U8一次元配列 |
| `Byte Order` | 入力 | `RAMScope_Byte_Order.ctl` |
| `error in` | 入力 | error cluster |
| `Module List` | 出力 | `RAMScope_Module_Info.ctl`一次元配列 |
| `MdlNo_RAM` | 出力 | I32 |
| `MdlNo_CAN` | 出力 | I32 |
| `Endian_RAM` | 出力 | I32 |
| `RAM Module Found?` | 出力 | Boolean |
| `CAN Module Found?` | 出力 | Boolean |
| `error out` | 出力 | error cluster |

### 2. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所 |
|---:|---|---|---|
| 1 | 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 複数 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 1 | 配列サイズ | Array Size | プログラミング → 配列 |
| 1 | 等しい? | Equal? | プログラミング → 比較 |
| 1 | Forループ | For Loop | プログラミング → ストラクチャ |
| 1 | 乗算 | Multiply | プログラミング → 数値 |
| 12以上 | 部分配列 | Array Subset | プログラミング → 配列 |
| 11 | `U8x4_To_I32.vi` | SubVI | `30_RAMScope\00_Common` |
| 1 | 1D配列検索 | Search 1D Array | プログラミング → 配列 |
| 1 | バイト配列から文字列 | Byte Array To String | プログラミング → 文字列 → 文字列/配列/パス変換 |
| 1 | 名前でバンドル | Bundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 複数 | 等しい? / 以上? | Equal? / Greater Or Equal? | プログラミング → 比較 |
| 複数 | 複合演算 | Compound Arithmetic | プログラミング → ブール |
| 1 | 文字列にフォーマット | Format Into String | プログラミング → 文字列 |

### 3. 配線順

1. `error in`を名前でバンドル解除へ接続し、`status`を外側ケースストラクチャへ接続する。
2. 外側Trueでは次を出力する。

```text
Module List      = 空配列
MdlNo_RAM        = -1
MdlNo_CAN        = -1
Endian_RAM       = 0
RAM Found?       = False
CAN Found?       = False
error out        = error in
```

3. 外側Falseで`SYSINFO Raw`を配列サイズへ接続する。
4. 配列サイズ出力とI32定数`960`を等しい?へ接続し、サイズ判定ケースへ接続する。
5. サイズ不正のFalseケースでは上記安全値とcode=`-700120`を出力する。
6. サイズ正常のTrueケースへForループを配置し、N端子へI32定数`16`を接続する。
7. Forループへ次のシフトレジスタを追加する。

```text
MdlNo_RAM  初期値 -1
MdlNo_CAN  初期値 -1
Endian_RAM 初期値 0
error      初期値 error in
```

8. 反復端子`i`とI32定数`60`を乗算し、Record Startを作る。
9. 部分配列へ`SYSINFO Raw`、index=`Record Start`、length=`60`を接続し、Record U8[60]を作る。
10. Recordから以下の11個の4バイト部分配列を取り出す。

| フィールド | index | length |
|---|---:|---:|
| module | 0 | 4 |
| module_type | 4 | 4 |
| probe_id | 8 | 4 |
| interface_id | 12 | 4 |
| version | 16 | 4 |
| addinfo | 20 | 4 |
| endian | 24 | 4 |
| probe_version | 28 | 4 |
| security_id_req | 32 | 4 |
| security_id_size | 36 | 4 |
| flash_enable | 40 | 4 |

11. `U8x4_To_I32.vi`を11個配置する。
12. 各4バイト配列を対応するSubVIの`Bytes`へ接続する。
13. `Byte Order`を11個のSubVIへ分岐して接続する。
14. error clusterはmodule変換からflash_enable変換まで直列接続する。
15. Recordへ部分配列を接続し、index=`44`、length=`16`でName Bytesを取得する。
16. Name Bytesを1D配列検索へ接続し、検索要素へU8定数`0`を接続する。
17. 検索結果をケースストラクチャへ接続する。
18. `-1`ケースではName Bytes全体をバイト配列から文字列へ接続する。
19. Defaultケースでは部分配列へName Bytes、index=`0`、length=`検索結果`を接続し、NULLより前だけをバイト配列から文字列へ接続する。
20. `RAMScope_Module_Info.ctl`定数を名前でバンドルへ接続し、次を設定する。

```text
Record Index
ModuleNo
Module Type
Probe ID
Interface ID
Version
AddInfo
Endian
Probe Version
Security ID Required
Security ID Size
Flash Enable
Name
Connected?
```

21. `Connected?`は`module_type != 0x0F`で生成する。
22. 名前でバンドル出力をForループ右枠へ接続し、出力トンネルの自動指標付けを有効にして`Module List`を作る。
23. RAM判定として`module_type == 0x00`かつ現在の`MdlNo_RAM == -1`を複合演算ANDへ接続する。
24. RAM判定Trueでは`module`をMdlNo_RAM、`endian`をEndian_RAMの右シフトレジスタへ接続する。
25. Falseでは左シフトレジスタ値をそのまま右へ渡す。
26. CAN判定として`module_type == 0x02`かつ現在の`MdlNo_CAN == -1`を作る。
27. CAN判定Trueでは`module`をMdlNo_CANへ、Falseでは以前の値を保持する。
28. 最後の変換SubVIのerror outをerrorシフトレジスタへ接続する。
29. ループ後のMdlNo_RAM、MdlNo_CAN、Endian_RAMを各出力へ接続する。
30. `MdlNo_RAM >= 0`を`RAM Module Found?`へ接続する。
31. `MdlNo_CAN >= 0`を`CAN Module Found?`へ接続する。
32. ループ後のerror clusterを`error out`へ接続する。

### 4. 単体テスト

ダミーSYSINFOを作るときは、未使用レコードの`module_type`を`0x0F`へ設定する。全960バイトをゼロのままにすると、未使用レコードもRAMモジュールとして誤検出する可能性がある。

テスト例：

```text
Record 0
  module      = 0
  module_type = 0x00
  endian      = 0
  name        = "RAM0"

Record 1
  module      = 1
  module_type = 0x02
  name        = "CAN0"

Record 2～15
  module_type = 0x0F
```

期待出力：

```text
Array Size(Module List) = 16
MdlNo_RAM               = 0
MdlNo_CAN               = 1
Endian_RAM              = 0
RAM Module Found?       = True
CAN Module Found?       = True
error out               = 正常
```

異常テスト：

| 条件 | 期待結果 |
|---|---|
| SYSINFO Rawが959要素 | code=`-700120`、MdlNo=-1 |
| RAMモジュールなし | RAM Found=False、Parser自体は正常 |
| 既存エラー | 安全値、既存エラー保持 |

## 10.11.2 `RAMScope_Parse_Buffer.vi`

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Raw Buffer` | 入力 | U8一次元配列 |
| `DataNum` | 入力 | I32 |
| `Channel List` | 入力 | `RAMScope_Channel.ctl`一次元配列 |
| `Byte Order` | 入力 | `RAMScope_Byte_Order.ctl` |
| `error in` | 入力 | error cluster |
| `Packets` | 出力 | `RAMScope_Packet.ctl`一次元配列 |
| `Parsed Packet Count` | 出力 | I32 |
| `Unused Byte Count` | 出力 | I32 |
| `error out` | 出力 | error cluster |

### 2. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所 |
|---:|---|---|---|
| 1 | 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 複数 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 3以上 | 配列サイズ | Array Size | プログラミング → 配列 |
| 複数 | 加算、減算、乗算 | Add, Subtract, Multiply | プログラミング → 数値 |
| 複数 | 以上?、等しい? | Greater Or Equal?, Equal? | プログラミング → 比較 |
| 複数 | 複合演算 | Compound Arithmetic | プログラミング → ブール |
| 2 | Forループ | For Loop | プログラミング → ストラクチャ |
| 複数 | 部分配列 | Array Subset | プログラミング → 配列 |
| 複数 | `U8x4_To_U32.vi` | SubVI | `30_RAMScope\00_Common` |
| 1 | `U8x8_To_U64.vi` | SubVI | `30_RAMScope\00_Common` |
| 1 | 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 2 | 名前でバンドル | Bundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 1 | 型変換 | Type Cast | プログラミング → 数値 → データ操作 |
| 2 | 倍精度浮動小数点に変換 | To Double Precision Float | プログラミング → 数値 → 変換 |
| 1 | 選択 | Select | プログラミング → 比較 |
| 1 | 文字列にフォーマット | Format Into String | プログラミング → 文字列 |

### 3. 配線順

1. `error in`を名前でバンドル解除へ接続し、`status`を外側ケースストラクチャへ接続する。
2. 外側Trueでは空Packets、Parsed Packet Count=0、Unused Byte Count=0、元のerrorを出力する。
3. 外側Falseで`Channel List`を配列サイズへ接続し、`ChNum`を作る。
4. I32定数`4`とChNumを乗算し、I32定数`12`を加算して`Packet Size`を作る。
5. `Packet Size × DataNum`で`Expected Byte Count`を作る。
6. `Raw Buffer`を配列サイズへ接続し、`Actual Byte Count`を作る。
7. `Actual - Expected`を`Unused Byte Count`へ接続する。
8. 次の3条件を作る。

```text
ChNum >= 1
DataNum >= 0
Actual Byte Count >= Expected Byte Count
```

9. 3条件を複合演算ANDへ接続し、入力検証ケースストラクチャへ接続する。
10. ChNumまたはDataNum不正の場合は空Packets、count=0、code=`-700130`を出力する。
11. Actual不足の場合は空Packets、count=0、code=`-700131`を出力する。
12. `DataNum == 0`を判定するケースを作り、Trueでは空Packets、count=0、正常errorを出力する。
13. DataNum>0のケースへ外側Forループを配置し、N端子へDataNumを接続する。
14. 外側Forループへerror cluster用シフトレジスタを追加する。
15. 反復端子`i × Packet Size`で`Packet Start`を作る。
16. 内側Forループを配置し、`Channel List`を自動指標付け入力する。
17. 内側Forループの反復端子`j × 4`へPacket Startを加算し、`Value Start`を作る。
18. 部分配列へRaw Buffer、index=`Value Start`、length=`4`を接続する。
19. 4バイト配列を`U8x4_To_U32.vi`へ接続し、Raw U32を取得する。
20. Byte OrderをSubVIへ接続し、error clusterを内側ループの処理順に直列接続する。
21. 自動指標付けされたChannelクラスタを名前でバンドル解除へ接続し、Name、Address、Sign、Scale、Offset、Unitを取り出す。
22. Raw U32を1個目の倍精度浮動小数点に変換へ接続し、符号なしDBLを作る。
23. Raw U32を型変換へ接続し、型指定入力へI32定数`0`を接続する。
24. 型変換出力I32を2個目の倍精度浮動小数点に変換へ接続し、符号ありDBLを作る。
25. `Sign == 0`を作る。
26. 選択へ次を接続する。

```text
s = Sign == 0
True入力  = 符号なしDBL
False入力 = 符号ありDBL
```

27. 選択出力を`Value`とする。
28. `Value × Scale + Offset`を計算し、`Engineering Value`を作る。
29. `RAMScope_Channel_Value.ctl`定数を名前でバンドルへ接続する。
30. Channel Index、Name、Address、Raw U32、Value、Engineering Value、Unitを接続する。
31. 名前でバンドル出力を内側Forループ右枠へ接続し、自動指標付けで`Channel Values`配列を作る。
32. `Packet Start + 4 × ChNum`で`Flag Start`を作る。
33. 部分配列へRaw Buffer、Flag Start、length=`4`を接続する。
34. Flag Bytesを`U8x4_To_U32.vi`へ接続し、Flagを取得する。
35. `Flag Start + 4`で`Timestamp Start`を作る。
36. 部分配列へRaw Buffer、Timestamp Start、length=`8`を接続する。
37. Timestamp Bytesを`U8x8_To_U64.vi`へ接続し、Timestamp Rawを取得する。
38. 現行作業仮定として`Timestamp Raw × 20e-9`を計算し、Timestamp Secondsを作る。
39. `RAMScope_Packet.ctl`定数を名前でバンドルへ接続する。
40. Packet Index、Channel Values、Flag、Timestamp Raw、Timestamp Secondsを接続する。
41. Packetクラスタを外側Forループ右枠へ接続し、自動指標付けで`Packets`を作る。
42. 外側Forループ後のPacketsを配列サイズへ接続し、`Parsed Packet Count`へ接続する。
43. 外側Forループ後のerror clusterを`error out`へ接続する。
44. すべての異常ケースでも`Packets`、`Parsed Packet Count`、`Unused Byte Count`、`error out`の4出力を必ず配線する。

### 4. 単体テスト

Channel Listを2要素にする。

```text
Channel 0
  Name="Unsigned"
  Sign=0
  Scale=1.0
  Offset=0.0

Channel 1
  Name="Signed"
  Sign=1
  Scale=1.0
  Offset=0.0
```

Raw Buffer：

```text
x01 x00 x00 x00              Channel 0 = 1
xFE xFF xFF xFF              Channel 1 = -2
xA5 x00 x00 x00              Flag = xA5
x32 x00 x00 x00 x00 x00 x00 x00   Timestamp = 50
```

入力：

```text
DataNum   = 1
Byte Order = Little Endian
```

期待出力：

```text
Packets[0].Channel Values[0].Value = 1
Packets[0].Channel Values[1].Value = -2
Packets[0].Flag                    = xA5
Packets[0].Timestamp Raw           = 50
Parsed Packet Count                = 1
Unused Byte Count                  = 0
error out                          = 正常
```

異常テスト：

| 条件 | 期待結果 |
|---|---|
| Channel Listが空 | code=`-700130` |
| DataNum=-1 | code=`-700130` |
| Raw BufferがExpectedより1byte短い | code=`-700131` |
| DataNum=0 | 空Packets、count=0、正常 |
| 既存エラー | 空Packets、count=0、既存エラー保持 |

---

# 10.12 公開API

全公開APIは末尾で`Error_To_TestStatus.vi`を1回呼び、`Status.ctl`、`TestError.ctl`、標準error clusterを出力する。

## 10.12.1 `RAMScope_Connect.vi`

```text
RS_DLL_GT150DeviceInit.vi
  → Error_To_TestStatus.vi
```

## 10.12.2 `RAMScope_Init.vi`

```text
RS_DLL_GT150AllInit.vi
  → RS_DLL_GT150GetSysInfo.vi
  → Parse_SYSINFO_Array.vi
  → RAM Module Found?判定
  → RS_DLL_GT150PGT_SetMdlConfig.vi
  → SlotErr判定
  → Error_To_TestStatus.vi
```

`RAMScope_Config.vi`は作成しない。PGT設定は`RAMScope_Init.vi`へ統合する。

## 10.12.3 `RAMScope_Set_Cond.vi`

```text
Build_MEASINFO_170_Raw.vi
  → RS_DLL_GT170SetMeasCond.vi

Build_CHINFO_170_Raw.vi
  → RS_DLL_GT170SetMeasCh.vi

Build_LOGINFO_Raw.vi
  → RS_DLL_GT150SetLoggingInfo.vi
```

## 10.12.4 `RAMScope_Log_Start.vi`

`RS_DLL_GT150MeasStart.vi`だけを呼ぶ。

## 10.12.5 `RAMScope_Read.vi`

```text
Packet Size = 4 × ChNum + 12
Buffer Byte Size = Packet Size × Max DataNum

RS_DLL_GT150GetBufferData.vi
  → RAMScope_Parse_Buffer.vi
  → Error_To_TestStatus.vi
```

## 10.12.6 `RAMScope_Release.vi`

`RS_DLL_GT150ReleaseBufferData.vi`だけを呼ぶ実験用公開API。要否確定後に残すか廃止する。

## 10.12.7 `RAMScope_Log_Stop.vi`

`RS_DLL_GT150MeasStop.vi`だけを呼ぶ。

## 10.12.8 `RAMScope_Close.vi`

前段エラーがあってもDeviceExitを実行し、元エラーと終了エラーを統合する。

---

# 10.13 最小PoC

```text
RAMScope_Connect.vi
  → RAMScope_Init.vi
  → RAMScope_Set_Cond.vi
  → RAMScope_Log_Start.vi
  → Wait
  → RAMScope_Read.vi
  → RAMScope_Log_Stop.vi
  → RAMScope_Close.vi
```

Cleanup経路では、計測中ならStopし、Release候補を実行してからCloseする。

## 10.13.1 合格条件

- DeviceInitが成功しUnitNum/kindを取得
- AllInit、GetSysInfo、PGT_SetMdlConfigが成功
- MdlNo_RAMを取得
- MEASINFO=72byte
- CHINFO=`24×ChNum`byte
- LOGINFO=136byte
- SetMeasCond、SetMeasCh、SetLoggingInfoが成功
- MeasStart、GetBufferData、MeasStopが成功
- 既知RAM変数と解析値が一致
- LostDataNumを記録
- 正常・異常の両方でDeviceExitまで実行
- 複数回再接続・再測定が可能

---

# 10.14 TestStandへの引き渡し

RAMScope単体PoCと採用CAN方式の単体PoCが完了してからTestStandへ組み込む。

```text
Setup
  RAMScope_Connect.vi
  RAMScope_Init.vi
  RAMScope_Set_Cond.vi

Main
  RAMScope_Log_Start.vi
  Loop:
    RAMScope_Read.vi
    Wait
  RAMScope_Log_Stop.vi

Cleanup
  RAMScope_Log_Stop.vi（計測中のみ）
  RAMScope_Release.vi（採用時のみ）
  RAMScope_Close.vi
```

TestStandから`RS_DLL_*`を直接呼ばない。

---

# 10.15 トラブルシュート

| 症状 | 主な確認 | 対応 |
|---|---|---|
| エラー193 | x64/x86不一致 | x86ランタイム隔離、VC++2013 x64確認 |
| エラー126 | 依存DLL不足 | ベンダー相対配置を確認 |
| エラー127 | 関数名、無効Handle | Handle非ゼロ、関数名完全一致 |
| LabVIEWクラッシュ | 引数型、配列サイズ | ヘッダとCLFN再照合 |
| U8変換値が逆 | Byte Order | Little/Bigの数値結合順を確認 |
| 同じバイトが4回出る | 指標配列index | `0,1,2,3`を接続 |
| CHINFOが2次元 | 配列連結追加 | `入力を連結`を有効化 |
| Buffer不足 | Buffer Byte Size | `(4×ChNum+12)×MaxDataNum`を確認 |
| 値と変数名がずれる | Channel List順序 | BuilderとParserへ同一配列を渡す |

---

# 10.16 未確定事項

- `0x30100001`のベンダー正式定義
- GT170接続時のDeviceInit正常値
- AllInit以降の実機通し動作
- `Size`、`Sign`、`Speed`コードの正式定義
- `Endian_RAM`コードとByte Orderの正式マッピング
- Timestamp単位の実機確定
- 既存RAMScopeコンフィグファイルの正式読込仕様
- `ReleaseBufferData`の必須性と呼び出し位置
- APIのスレッドセーフ性
- CANの最終方式

未確定事項は公開APIへ推測で固定しない。

---

# 10.17 現在の作業チェックリスト

## 完了済み

- [x] x64 DLLロード
- [x] DeviceInit関数解決
- [x] x86版VC++2013ランタイム混在によるエラー193を解消
- [x] `RAMScope_Code_To_Error.vi`の4パターン試験
- [x] 薄いDLLラッパ12個を作成
- [x] `U8x4_To_U32.vi`のLittle Endian正常試験

## 次に作成・確認

- [ ] `RAMScope_Byte_Order.ctl`
- [ ] `U8x4_To_U32.vi`のBig Endian、3要素、既存エラー試験
- [ ] `U8x4_To_I32.vi`
- [ ] `U8x8_To_U64.vi`
- [ ] `U32_To_LE_U8x4.vi`
- [ ] `I32_To_LE_U8x4.vi`
- [ ] 残りtypedef
- [ ] Builder 3個
- [ ] Parser 2個
- [ ] 公開API 8個
- [ ] `PoC_RAMScope_Main.vi`

---

# 10.18 参照した公式資料

- NI LabVIEWプログラミングリファレンス：配列サイズ関数
- NI LabVIEWプログラミングリファレンス：指標配列
- NI LabVIEWプログラミングリファレンス：型変換関数
- NI LabVIEWプログラミングリファレンス内の各関数ページ
- `docs/reference/RAMScopeVP.h`
- `docs/reference/GTHard.h`
- `docs/reference/samp_simple.cpp`
