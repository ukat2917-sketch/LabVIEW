# 10. RAMScope GT170 実装ガイド

> **本章をRAMScope実装の唯一の正本とする。**
>
> DLL準備、CLFN、共通エラー変換、薄いDLLラッパ、typedef、構造体生成、Parser、公開API、最小PoCまでを上から順に実施する。
>
> 関数プロトタイプの一次情報は`docs/reference/RAMScopeVP.h`、ハードウェア定数は`docs/reference/GTHard.h`、呼び出し例は`docs/reference/samp_simple.cpp`を優先する。
>
> LabVIEWの操作名と関数名は、NI公式の日本語版LabVIEWマニュアルおよび日本語版プログラミングリファレンスを確認し、**日本語名（英語名）**の順で併記する。LabVIEWの版によって末尾の「関数」やパレット階層が多少異なる場合は、英語名をQuick Dropで検索する。

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

RAMScopeVP APIはLabVIEW用VIではなく、C言語用DLL APIである。LabVIEWから利用するには、次の差を吸収する必要がある。

```text
RAMScopeVP API側
  C関数
  C構造体
  ポインタ
  生バイト列
  API独自ReturnCode

        ↓ そのままではLabVIEW / TestStandから扱いにくい

LabVIEW / TestStand側
  数値・配列・クラスタ
  error cluster
  1イベント単位の公開VI
  試験条件・順序・結果管理
```

すべてを1個の巨大なVIへ入れると、DLL呼び出し、構造体変換、データ解析、試験フローのどこで失敗したかを切り分けにくい。そこで責務ごとに段階を分ける。

| RAMScope実装で発生する問題 | 必要な仕組み | 配置先・主なVI |
|---|---|---|
| C関数をLabVIEWから呼ぶ | CLFN設定を1関数単位で隔離 | `10_DLL_Wrapper\RS_DLL_*` |
| CLFNエラーとAPI ReturnCodeが別経路 | 2系統を標準error clusterへ統合 | `RAMScope_Code_To_Error.vi` |
| API入力がC構造体ポインタ | LabVIEW設定値をC互換U8配列へ組み立てる | `Build_*_Raw.vi` |
| API出力が構造体や生バッファ | U8配列をLabVIEWクラスタや数値へ解析 | `Parse_*` |
| Endianと符号を扱う | 数値とU8配列の変換を共通部品化 | `U8x4_To_U32.vi`等 |
| TestStandからCLFN単位では扱いにくい | 接続・初期化・読出し等へまとめる | `30_Public\RAMScope_*` |
| TestStand組み込み前に下位層を検証したい | LabVIEW単体PoCを用意 | `PoC_RAMScope_Main.vi` |

```text
TestStand
  試験条件、順序、Wait、Loop、分岐、レポート、Cleanup
        ↓
30_Public
  人が理解できる1イベント単位へまとめる
        ↓
20_Data_Conversion / 00_Common
  C構造体とLabVIEWデータ型の差を吸収する
        ↓
10_DLL_Wrapper
  DLL関数を1個だけ安全に呼ぶ
        ↓
RAMScopeVP_API_x64.dll
```

### 各レイヤが必要な理由

- `00_Common`：typedef、Endian変換、APIコード変換を重複実装しないため。
- `10_DLL_Wrapper`：関数名、引数型、Pointer、配列サイズを1関数ずつ検証するため。
- `20_Data_Conversion`：実機なしでもダミーデータでBuilderとParserを単体試験するため。
- `30_Public`：TestStandへ「接続」「初期化」「読む」等の安定したイベント単位を提供するため。
- `40_PoC`：RAMScope側の問題とTestStand設定の問題を混ぜないため。

## 10.2.2 採用構成

| 項目 | 採用内容 |
|---|---|
| 対象機器 | RAMScope GT170 |
| 接続 | USB3.0 |
| LabVIEW | 64bit版 |
| API | RAMScopeVP API 64bit版 |
| API DLL | `RAMScopeVP_API_x64.dll` |
| 呼び出し | Call Library Function Node（CLFN） |
| Calling Convention | `C` |
| DLL状態管理 | API内部のグローバル状態。セッションハンドルは返らない |
| C/C++ランタイム | Visual C++ 2013 Redistributable x64 |

使用しない方式：

- 32bit版DLLと32bit LabVIEW
- マックシステムズ製LabVIEWドライバを本線とする方式
- ヘッダを参照せず引数型を推測する方式

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
├─ 50_CAN\                         （RAM計測PoC後に作成）
└─ 90_TestStand\                   （RAM/CAN PoC後に必要時作成）
```

`RAMScope_Context.ctl`はPoC完了まで作成しない。`UnitNo`、`MdlNo_RAM`、`MdlNo_CAN`、`Endian_RAM`、`Channel List`を個別配線する。

## 10.2.4 レイヤ責務

| レイヤ | 責務 | 含めないもの |
|---|---|---|
| `00_Common` | typedef、バイト変換、APIコード変換 | DLL呼び出し、機器状態遷移 |
| `10_DLL_Wrapper` | 1個のCLFNで1関数だけ呼ぶ | Builder、Parser、複数API制御、Status生成 |
| `20_Data_Conversion` | C構造体互換U8配列生成、生バイト列解析 | DLL呼び出し、測定開始・停止 |
| `30_Public` | ラッパと変換VIを接続して1イベントを完結 | TestStand固有変数への直接依存 |
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
API DLL:
C:\DTSinsight\RAMScopeVP\app\RAMScopeVP_API(64bit)\RAMScopeVP_API_x64.dll

ヘッダ:
C:\DTSinsight\RAMScopeVP_API\header\RAMScopeVP.h
```

## 10.3.2 ベンダー指定の相対配置

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
   ├─ PGT10xX0x.dll
   └─ PGT10xX0x_ENG.dll
```

API DLLを起点とした相対位置を維持する。x86と表示されたファイルを一律削除しない。

## 10.3.3 既知事象：エラー193

```text
Error 193 (0xC1)
%1 は有効な Win32 アプリケーションではありません。
```

64bit APIフォルダへx86版VC++2013ランタイムが混在すると、x64プロセスがローカルDLLを優先して読み込み、エラー193になる可能性が高い。

```text
mfc120jpn.dll
mfc120u.dll
msvcp120.dll
msvcr120.dll
```

対策：

1. Visual C++ 2013 Redistributable x64を導入する。
2. 上記4ファイルが実際にx86の場合だけ、復元可能なバックアップへ移動する。
3. `PGTMgrVP.dll`、`PGTMgrVP_ENG.dll`、`utillc.dll`、`pgtlib`は移動しない。

## 10.3.4 PowerShell疎通確認

```powershell
powershell.exe -ExecutionPolicy Bypass `
  -File .\scripts\Test-RAMScopeDll.ps1 `
  -DllPath "C:\DTSinsight\RAMScopeVP\app\RAMScopeVP_API(64bit)\RAMScopeVP_API_x64.dll" `
  -ExportName "RAMScopeGT150DeviceInit" `
  -ExportOrdinal 14
```

合格条件：

```text
PowerShell 64-bit : True
Loaded module path: 指定したRAMScopeVP_API_x64.dll
Handle            : 0x0以外
Name Found        : True
Ordinal Found     : True
Name Address      : Ordinal Address
```

実機未接続時の観測値`0x30100001`は正式意味が未確定であり、未接続エラーと断定しない。

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
  → GetBufferData（繰り返し）
  → MeasStop
  → ReleaseBufferData（要否検証中）
  → DeviceExit
```

`GetSysInfo`でRAMモジュール番号を取得し、`MdlNo=1`等を固定しない。

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

Timestampの20ns換算は実機照合待ちの作業仮定とする。

---

# 10.5 LabVIEW操作名・関数名の表記ルール

## 10.5.1 操作名の確認方針

- 日本語版LabVIEWで画面上に表示される名称を先に記載する。
- 括弧内にNI公式英語名を併記する。
- NI公式日本語リファレンスのページタイトルには末尾に「関数」が付く場合があるが、パレット上では省略される場合がある。
- パレットで見つからない場合はブロックダイアグラムで`Ctrl + Space`を押し、英語名をQuick Dropへ入力する。

## 10.5.2 本章で使用する主な関数

| 日本語名 | 英語名 | パレットの目安 |
|---|---|---|
| ケースストラクチャ | Case Structure | 関数 → プログラミング → ストラクチャ |
| Forループ | For Loop | 関数 → プログラミング → ストラクチャ |
| 名前でバンドル解除 | Unbundle By Name | 関数 → プログラミング → クラスタ、クラス、バリアント |
| 名前でバンドル | Bundle By Name | 関数 → プログラミング → クラスタ、クラス、バリアント |
| 配列サイズ | Array Size | 関数 → プログラミング → 配列 |
| 指標配列 | Index Array | 関数 → プログラミング → 配列 |
| 部分配列 | Array Subset | 関数 → プログラミング → 配列 |
| 配列初期化 | Initialize Array | 関数 → プログラミング → 配列 |
| 部分配列置換 | Replace Array Subset | 関数 → プログラミング → 配列 |
| 配列連結追加 | Build Array | 関数 → プログラミング → 配列 |
| 1D配列検索 | Search 1D Array | 関数 → プログラミング → 配列 |
| 数値結合 | Join Numbers | 関数 → プログラミング → 数値 → データ操作 |
| 数値分割 | Split Number | 関数 → プログラミング → 数値 → データ操作 |
| 型変換 | Type Cast | 関数 → プログラミング → 数値 → データ操作 |
| 文字列にフォーマット | Format Into String | 関数 → プログラミング → 文字列 |
| バイト配列から文字列 | Byte Array To String | 関数 → プログラミング → 文字列 → 文字列/配列/パス変換 |
| 等しい? | Equal? | 関数 → プログラミング → 比較 |
| 以上? | Greater Or Equal? | 関数 → プログラミング → 比較 |
| 以下? | Less Or Equal? | 関数 → プログラミング → 比較 |
| 0より大きい? | Greater Than 0? | 関数 → プログラミング → 比較 |
| 選択 | Select | 関数 → プログラミング → 比較 |
| 複合演算 | Compound Arithmetic | 関数 → プログラミング → ブール |
| NOT | Not | 関数 → プログラミング → ブール |
| 加算 | Add | 関数 → プログラミング → 数値 |
| 減算 | Subtract | 関数 → プログラミング → 数値 |
| 乗算 | Multiply | 関数 → プログラミング → 数値 |
| 倍精度浮動小数点に変換 | To Double Precision Float | 関数 → プログラミング → 数値 → 変換 |
| エラークリア | Clear Errors | 関数 → プログラミング → ダイアログ&ユーザインタフェース |
| エラーをマージ | Merge Errors | 関数 → プログラミング → ダイアログ&ユーザインタフェース |

## 10.5.3 通常VIのエラーガード

```text
error in
  → 名前でバンドル解除（Unbundle By Name）: status
  → ケースストラクチャ（Case Structure）
      True : 実処理を呼ばず、元エラーと安全な初期出力を返す
      False: 実処理を実行
```

全ケースの出力トンネルを配線し、`Use default if unwired`へ依存しない。

## 10.5.4 ローカル検証エラーコード

| コード | 用途 |
|---:|---|
| `-700101` | U8x4変換VIの入力サイズ不正 |
| `-700102` | U8x8変換VIの入力サイズ不正 |
| `-700110` | MEASINFO生成入力不正 |
| `-700111` | CHINFOチャンネル数不正 |
| `-700112` | LOGINFOモジュール番号または重複不正 |
| `-700120` | SYSINFOサイズ不正 |
| `-700121` | RAMモジュール未検出 |
| `-700130` | Buffer Parser入力不正 |
| `-700131` | Raw Buffer不足 |

---

# 10.6 `RAMScope_Code_To_Error.vi`作成手順

## 10.6.1 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `API ReturnCode` | 入力 | I32 |
| `Function Name` | 入力 | String |
| `error in` | 入力 | error cluster |
| `error out` | 出力 | error cluster |

## 10.6.2 配置する関数

- 名前でバンドル解除（Unbundle By Name）
- ケースストラクチャ（Case Structure）×2
- 等しい?（Equal?）
- 型変換（Type Cast）
- 文字列にフォーマット（Format Into String）
- 名前でバンドル（Bundle By Name）

## 10.6.3 配線

1. `error in`を名前でバンドル解除（Unbundle By Name）へ接続し、`status`を選択する。
2. `status`を外側ケースストラクチャ（Case Structure）のセレクタへ接続する。
3. 外側Trueでは`error in`をそのまま出力する。
4. 外側FalseでAPI ReturnCodeとI32定数`0`を等しい?（Equal?）へ接続する。
5. 結果を内側ケースストラクチャへ接続する。
6. 内側Trueでは正常error clusterを出力する。
7. 内側FalseではReturnCodeを型変換（Type Cast）でU32として解釈する。
8. 文字列にフォーマット（Format Into String）へ次を設定する。

```text
RAMScope %s failed. ReturnCode=0x%08X (%d)
```

9. 名前でバンドル（Bundle By Name）で次を設定する。

```text
status = True
code   = API ReturnCode
source = フォーマット文字列
```

単体テストはReturnCode=`0`、`0x30100001`、既存エラー、`-1`の4種類を行う。

---

# 10.7 薄いDLLラッパ12個

## 10.7.1 共通設定

| 項目 | 設定 |
|---|---|
| Library | `RAMScopeVP_API_x64.dll`のフルパス |
| Calling Convention | `C` |
| Thread | PoC中は`Run in UI thread` |
| Error checking | PoC中は`Maximum` |
| Return | Numeric / Signed 32-bit Integer / Value |

各ラッパはCLFN戻り値とCLFN error outを`RAMScope_Code_To_Error.vi`へ接続する。`DeviceExit`だけはCleanup用なので前段エラーがあっても呼ぶ。

## 10.7.2 CLFN一覧

| VI | DLL関数 | 主な入力・出力 |
|---|---|---|
| `RS_DLL_GT150DeviceInit.vi` | `RAMScopeGT150DeviceInit` | I32 PointerのUnitNum/kind |
| `RS_DLL_GT150DeviceExit.vi` | `RAMScopeGT150DeviceExit` | 引数なし |
| `RS_DLL_GT150AllInit.vi` | `RAMScopeGT150AllInit` | UnitNo I32 Value |
| `RS_DLL_GT150GetSysInfo.vi` | `RAMScopeGT150GetSysInfo` | UnitNo、U8[960] Pointer |
| `RS_DLL_GT150PGT_SetMdlConfig.vi` | `RAMScopeGT150PGT_SetMdlConfig` | UnitNo、I32[16] Pointer |
| `RS_DLL_GT170SetMeasCond.vi` | `RAMScopeGT170SetMeasCond` | UnitNo、MdlNo、U8[72] |
| `RS_DLL_GT170SetMeasCh.vi` | `RAMScopeGT170SetMeasCh` | UnitNo、MdlNo、ChNum、U8[24×ChNum] |
| `RS_DLL_GT150SetLoggingInfo.vi` | `RAMScopeGT150SetLoggingInfo` | UnitNo、U8[136] |
| `RS_DLL_GT150MeasStart.vi` | `RAMScopeGT150MeasStart` | UnitNo |
| `RS_DLL_GT150GetBufferData.vi` | `RAMScopeGT150GetBufferData` | UnitNo、MdlNo、U8 buffer、DataNum、LostDataNum |
| `RS_DLL_GT150ReleaseBufferData.vi` | `RAMScopeGT150ReleaseBufferData` | UnitNo |
| `RS_DLL_GT150MeasStop.vi` | `RAMScopeGT150MeasStop` | UnitNo |

配列ポインタは配列初期化（Initialize Array）で必要要素数を事前確保する。

---

# 10.8 typedef作成

## 10.8.1 標準の作成方法

本プロジェクトでは、**プロジェクトエクスプローラから直接「タイプ定義」を作成する方法を標準**とする。`カスタム制御器`を作成して後からType Def.へ変更する手順は使用しない。

### プロジェクトから新規作成する

1. プロジェクトエクスプローラで`30_RAMScope\00_Common`を右クリックする。
2. `新規 → タイプ定義`を選択する。
3. 制御器エディタが開く。初期配置された不要な制御器がある場合は削除する。
4. 作成する型に応じて次を配置する。
   - クラスタ型：制御器パレット → `モダン → 配列、行列&クラスタ → クラスタ`
   - Enum型：制御器パレット → `モダン → リング&列挙体 → 列挙体`
5. クラスタ型では、数値、文字列、Boolean、配列等の制御器をクラスタ枠内へ配置する。
6. 各数値制御器を右クリックし、`表現形式`をI32、U32、U64、DBL等へ合わせる。
7. 各要素のラベルを本章のフィールド名と完全一致させる。
8. `ファイル → 名前を付けて保存`を選び、`.ctl`名で`30_RAMScope\00_Common`へ保存する。
9. 制御器エディタ上部の種類が`タイプ定義（Type Def.）`になっていることを確認する。

> `新規 → タイプ定義`から作成した場合、後からツールバーで`Type Def.`へ変更する操作は不要である。

### 既存制御器から作成する代替方法

NI公式手順では、既存の制御器、表示器、定数を右クリックし、`タイプ定義にする（Make Type Def.）`を選択する方法も案内されている。この方法は既存VIから型を切り出す場合に使用する。新規に本プロジェクトのctlを作る場合は、前述の`新規 → タイプ定義`を使用する。

## 10.8.2 `RAMScope_Byte_Order.ctl`

1. `新規 → タイプ定義`を開く。
2. 列挙体（Enum）を配置する。
3. 項目を次の順に登録する。

```text
Little Endian
Big Endian
```

4. `RAMScope_Byte_Order.ctl`として保存する。
5. ケースストラクチャ（Case Structure）へ接続し、ケース名がEnum項目名になることを確認する。

## 10.8.3 クラスタ型ctlの共通作業

1. クラスタを配置する。
2. 下表の順番で制御器をクラスタ内へ配置する。
3. 数値の表現形式を設定する。
4. ラベル名を一致させる。
5. 保存後、別VIへtypedef定数を配置し、要素名が正しく表示されることを確認する。

### `RAMScope_Meas_Config.ctl`

| フィールド | 型 | PoC初期例 |
|---|---|---:|
| `DummyInterval` | I32 | 100 |
| `MeasPeri` | I32 | 100 |
| `MeasUnit` | I32 | 2 |

### `RAMScope_Channel.ctl`

| フィールド | 型 | DLLへ渡す |
|---|---|---|
| `Name` | String | いいえ |
| `Enable` | U32 | はい |
| `Core` | U32 | はい |
| `Address` | U32 | はい |
| `Size` | U32 | はい |
| `Sign` | U32 | はい |
| `Speed` | U32 | はい |
| `Scale` | DBL | いいえ |
| `Offset` | DBL | いいえ |
| `Unit` | String | いいえ |

`ChNum = 配列サイズ（Array Size）(Channel List)`とし、別の手入力値を持たせない。

### `RAMScope_Module_Log_Config.ctl`

| フィールド | 型 |
|---|---|
| `MdlNo` | I32 |
| `LogSize` | I32 |
| `BufferSize` | I32 |

### `RAMScope_Module_Info.ctl`

| フィールド | 型 |
|---|---|
| `Record Index` | I32 |
| `ModuleNo` | I32 |
| `Module Type` | I32 |
| `Probe ID` | I32 |
| `Interface ID` | I32 |
| `Version` | I32 |
| `AddInfo` | I32 |
| `Endian` | I32 |
| `Probe Version` | I32 |
| `Security ID Required` | I32 |
| `Security ID Size` | I32 |
| `Flash Enable` | I32 |
| `Name` | String |
| `Connected?` | Boolean |

### `RAMScope_Channel_Value.ctl`

| フィールド | 型 |
|---|---|
| `Channel Index` | I32 |
| `Name` | String |
| `Address` | U32 |
| `Raw U32` | U32 |
| `Value` | DBL |
| `Engineering Value` | DBL |
| `Unit` | String |

### `RAMScope_Packet.ctl`

| フィールド | 型 |
|---|---|
| `Packet Index` | I32 |
| `Channel Values` | `RAMScope_Channel_Value.ctl`一次元配列 |
| `Flag` | U32 |
| `Timestamp Raw` | U64 |
| `Timestamp Seconds` | DBL |

---

# 10.9 数値⇔U8変換VI

## 10.9.1 `U8x4_To_U32.vi`

### 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Bytes` | 入力 | U8一次元配列 |
| `Byte Order` | 入力 | `RAMScope_Byte_Order.ctl` |
| `error in` | 入力 | error cluster |
| `Value` | 出力 | U32 |
| `error out` | 出力 | error cluster |

### 配置する関数

| 個数 | 日本語名 | 英語名 | 配置場所 |
|---:|---|---|---|
| 1 | 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 3 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 1 | 配列サイズ | Array Size | プログラミング → 配列 |
| 1 | 等しい? | Equal? | プログラミング → 比較 |
| 1 | 指標配列 | Index Array | プログラミング → 配列 |
| 6 | 数値結合 | Join Numbers | プログラミング → 数値 → データ操作 |
| 1 | 文字列にフォーマット | Format Into String | プログラミング → 文字列 |
| 1 | 名前でバンドル | Bundle By Name | プログラミング → クラスタ、クラス、バリアント |

### ブロックダイアグラム

1. `error in`を名前でバンドル解除（Unbundle By Name）へ接続し、`status`を選ぶ。
2. `status`を外側ケースストラクチャ（Case Structure）のセレクタへ接続する。
3. 外側True：ValueへU32定数`0`、error outへ元のerror inを接続する。
4. 外側False：Bytesを配列サイズ（Array Size）へ接続する。
5. 配列サイズ出力とI32定数`4`を等しい?（Equal?）へ接続する。
6. 比較結果を2個目のケースストラクチャへ接続する。
7. サイズ不正ケースでは`-700101`のerror clusterを名前でバンドル（Bundle By Name）で生成する。
8. サイズ正常ケースへ指標配列（Index Array）を配置する。
9. Bytesを配列入力へ接続し、指標配列の下端を下へドラッグして出力を4個にする。
10. 最初の指標入力へI32定数`0`を接続する。4出力を上から`b0`、`b1`、`b2`、`b3`として扱う。
11. `Byte Order`を3個目のケースストラクチャへ接続する。
12. Little Endianケースへ数値結合（Join Numbers）を3個配置する。

```text
数値結合 #1: high=b1, low=b0 → Low Word
数値結合 #2: high=b3, low=b2 → High Word
数値結合 #3: high=High Word, low=Low Word → Value
```

13. Big Endianケースも数値結合を3個使用する。

```text
数値結合 #1: high=b0, low=b1 → High Word
数値結合 #2: high=b2, low=b3 → Low Word
数値結合 #3: high=High Word, low=Low Word → Value
```

### 単体テスト

| Bytes | Byte Order | 期待Value |
|---|---|---:|
| `78 56 34 12` | Little Endian | `0x12345678` |
| `12 34 56 78` | Big Endian | `0x12345678` |
| `FF FF FF FF` | Little Endian | `0xFFFFFFFF` |
| 3要素 | 任意 | error code `-700101` |

## 10.9.2 `U8x4_To_I32.vi`

配置：`U8x4_To_U32.vi`、型変換（Type Cast）、I32定数。

```text
Bytes / Byte Order / error in
  → U8x4_To_U32.vi
  → U32 Valueを型変換（Type Cast）
      type端子へI32定数0
  → I32 Value
```

数値変換ではなく型変換を使い、32bitのビット列を保持する。`FF FF FF FF`は`-1`になる。

## 10.9.3 `U8x8_To_U64.vi`

配置する主な関数：

- 配列サイズ（Array Size）
- 等しい?（Equal?）
- ケースストラクチャ（Case Structure）
- 部分配列（Array Subset）×2
- `U8x4_To_U32.vi`×2
- 数値結合（Join Numbers）

配線：

```text
部分配列 #1: array=Bytes, index=0, length=4 → First4
部分配列 #2: array=Bytes, index=4, length=4 → Last4
```

Little Endian：First4をLow DWord、Last4をHigh DWordとして数値結合する。Big Endianは逆にする。8要素でない場合は`-700102`。

## 10.9.4 `U32_To_LE_U8x4.vi`

配置：

- 名前でバンドル解除（Unbundle By Name）
- ケースストラクチャ（Case Structure）
- 数値分割（Split Number）×3
- 配列連結追加（Build Array）

配線：

```text
U32 Value
 → 数値分割 #1 → High Word / Low Word
Low Word  → 数値分割 #2 → b1 / b0
High Word → 数値分割 #3 → b3 / b2
配列連結追加へ b0, b1, b2, b3 の順で接続
```

`0x12345678`の出力は`78 56 34 12`。

## 10.9.5 `I32_To_LE_U8x4.vi`

配置：型変換（Type Cast）、U32定数、`U32_To_LE_U8x4.vi`。

```text
I32 Value → 型変換（type=U32定数） → U32_To_LE_U8x4.vi
```

`-1`の出力は`FF FF FF FF`。

---

# 10.10 構造体Builder

## 10.10.1 `Build_MEASINFO_170_Raw.vi`

配置：

- 配列初期化（Initialize Array）
- 名前でバンドル解除（Unbundle By Name）
- `I32_To_LE_U8x4.vi`×3
- 部分配列置換（Replace Array Subset）×3

配線：

```text
U8定数0 + I32定数72 → 配列初期化 → U8[72]

DummyInterval → I32_To_LE_U8x4 → 部分配列置換 index=0
MeasPeri      → I32_To_LE_U8x4 → 部分配列置換 index=4
MeasUnit      → I32_To_LE_U8x4 → 部分配列置換 index=8
```

出力配列サイズが72であることを確認する。

## 10.10.2 `Build_CHINFO_170_Raw.vi`

配置：

- 配列サイズ（Array Size）
- 以上?（Greater Or Equal?）
- 以下?（Less Or Equal?）
- 複合演算（Compound Arithmetic、AND）
- ケースストラクチャ（Case Structure）
- Forループ（For Loop）
- 名前でバンドル解除（Unbundle By Name）
- `U32_To_LE_U8x4.vi`×6
- 配列連結追加（Build Array）×2
- シフトレジスタ

配線：

1. Channel Listを配列サイズへ接続し、ChNumを取得する。
2. `ChNum >= 1`と`ChNum <= 2048`を複合演算ANDへ接続する。
3. 不正時は空U8配列と`-700111`を返す。
4. Channel ListをForループへ自動指標付け入力する。
5. 各要素からEnable、Core、Address、Size、Sign、Speedを名前でバンドル解除する。
6. 6値を`U32_To_LE_U8x4.vi`へ接続する。
7. 配列連結追加 #1の`入力を連結`を有効にし、6個のU8[4]を順番に接続してU8[24]を作る。
8. 配列連結追加 #2も`入力を連結`にし、シフトレジスタの累積配列と今回のU8[24]を接続する。
9. ループ後のサイズが`24 × ChNum`であることを確認する。

## 10.10.3 `Build_LOGINFO_Raw.vi`

配置：

- 配列初期化（Initialize Array）×2
- `I32_To_LE_U8x4.vi`
- 部分配列置換（Replace Array Subset）
- Forループ（For Loop）
- 指標配列（Index Array）
- 以上?、以下?、NOT、複合演算
- 乗算（Multiply）、加算（Add）
- 名前でバンドル（Bundle By Name）

初期化：

```text
U8 0 × 136 → LOGINFO配列
Boolean False × 16 → Seen配列
```

ヘッダ：

```text
LogDevice    → index 0
LimitHddSize → index 4
```

Forループ内：

```text
0 <= MdlNo <= 15
AND Seen[MdlNo] == False

Log index    = 8  + MdlNo × 8
Buffer index = 12 + MdlNo × 8
```

範囲外または重複時は`-700112`を返す。出力サイズは136。

---

# 10.11 Parser

## 10.11.1 `Parse_SYSINFO_Array.vi`

配置：

- 配列サイズ（Array Size）
- 等しい?（Equal?）
- ケースストラクチャ（Case Structure）
- Forループ（For Loop）
- 乗算（Multiply）
- 部分配列（Array Subset）
- `U8x4_To_I32.vi`
- 1D配列検索（Search 1D Array）
- バイト配列から文字列（Byte Array To String）
- 名前でバンドル（Bundle By Name）
- シフトレジスタ

手順：

1. `Array Size(SYSINFO Raw) == 960`を確認する。不正時は`-700120`。
2. ForループのNへ`16`を接続する。
3. 各反復で`Record Start = i × 60`を計算する。
4. 部分配列で60バイトを切り出す。
5. 次のオフセットから4バイトずつ切り出し、`U8x4_To_I32.vi`へ接続する。

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

6. `name[16]`はindex=44、length=16で切り出す。
7. 1D配列検索へU8定数`0`を接続し、NULL位置を取得する。
8. NULLより前を部分配列で切り出し、バイト配列から文字列へ接続する。
9. 名前でバンドルで`RAMScope_Module_Info.ctl`を作る。
10. 最初のRAMモジュールで`MdlNo_RAM`と`Endian_RAM`を保存し、最初のCANモジュールで`MdlNo_CAN`を保存する。

## 10.11.2 `RAMScope_Parse_Buffer.vi`

配置：

- 配列サイズ（Array Size）
- 乗算（Multiply）、加算（Add）、減算（Subtract）
- 以上?（Greater Or Equal?）、0より大きい?（Greater Than 0?）
- 複合演算（Compound Arithmetic）
- ケースストラクチャ（Case Structure）
- Forループ（For Loop）×2
- 部分配列（Array Subset）
- `U8x4_To_U32.vi`、`U8x4_To_I32.vi`、`U8x8_To_U64.vi`
- 名前でバンドル解除 / 名前でバンドル
- 型変換（Type Cast）
- 倍精度浮動小数点に変換（To Double Precision Float）
- 選択（Select）

入力確認：

```text
ChNum              = Array Size(Channel List)
Packet Size         = 4 × ChNum + 12
Expected Byte Count = Packet Size × DataNum
Actual Byte Count   = Array Size(Raw Buffer)
Unused Byte Count   = Actual - Expected
```

外側ForループはDataNum回、内側ForループはChannel Listを自動指標付けする。

```text
Packet Start = Packet Index × Packet Size
Value Start  = Packet Start + Channel Index × 4
Flag Start   = Packet Start + 4 × ChNum
Time Start   = Flag Start + 4
```

チャンネル値は4バイト、Flagは4バイト、Timestampは8バイトを部分配列で取得する。Signに応じてU32またはI32として解釈し、次を計算する。

```text
Engineering Value = Value × Scale + Offset
```

Raw Buffer不足は`-700131`、入力条件不正は`-700130`。

---

# 10.12 公開API

| VI | 内部フロー |
|---|---|
| `RAMScope_Connect.vi` | DeviceInit → Error_To_TestStatus |
| `RAMScope_Init.vi` | AllInit → GetSysInfo → Parse SYSINFO → PGT設定 |
| `RAMScope_Set_Cond.vi` | Builder → SetMeasCond → SetMeasCh → SetLoggingInfo |
| `RAMScope_Log_Start.vi` | MeasStart |
| `RAMScope_Read.vi` | GetBufferData → Parse Buffer |
| `RAMScope_Release.vi` | ReleaseBufferData。検証用 |
| `RAMScope_Log_Stop.vi` | MeasStop |
| `RAMScope_Close.vi` | 前段エラーがあってもDeviceExit |

`RAMScope_Config.vi`は作成しない。PGT設定は`RAMScope_Init.vi`へ統合する。

`RAMScope_Close.vi`ではエラークリア（Clear Errors）後にDeviceExitを呼び、元エラーと終了エラーをエラーをマージ（Merge Errors）で統合する。

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

Cleanup経路では計測中ならStopを試み、Release採用時のみReleaseを呼び、最後にCloseを必ず実行する。

合格条件：

- DeviceInit、AllInit、GetSysInfo、PGT設定が成功
- MdlNo_RAMを取得
- MEASINFO=72byte、CHINFO=`24×ChNum`byte、LOGINFO=136byte
- SetMeasCond、SetMeasCh、SetLoggingInfoが成功
- MeasStart、GetBufferData、MeasStopが成功
- 既知RAM変数と解析値が一致
- LostDataNumを記録
- 正常・異常の両方でDeviceExitまで実行
- 複数回再実行可能

ReleaseBufferDataは次を比較する。

```text
A: ReadごとにRelease
B: Stop後にRelease
C: Releaseを使用しない
```

---

# 10.14 TestStandへの引き渡し

RAMScope単体PoCと採用CAN方式の単体PoC完了後にTestStandへ組み込む。

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
  If IsMeasuring:
    RAMScope_Log_Stop.vi
  RAMScope_Release.vi（採用時のみ）
  RAMScope_Close.vi
```

TestStandから`RS_DLL_*`を直接呼ばない。

---

# 10.15 トラブルシュート

| 症状 | 主な確認 | 対応 |
|---|---|---|
| エラー193 | x64/x86不一致、ローカルx86依存DLL | 対象ランタイムのみ隔離、VC++2013 x64確認 |
| エラー126 | 依存DLL不足 | ベンダー相対配置、GT170 DLL、VC++確認 |
| エラー127 | 関数名、無効ハンドル | Handle非ゼロ確認、関数名完全一致 |
| LabVIEWクラッシュ | 引数型、配列サイズ、ポインタ | ヘッダとCLFNを再照合 |
| U8変換値が逆 | Byte Order配線 | Little/Bigの数値結合順を確認 |
| CHINFOが2次元 | 配列連結追加の設定 | `入力を連結`を有効化 |
| Buffer不足 | Buffer Byte Size式 | `(4×ChNum+12)×MaxDataNum`を確認 |
| 値と変数名がずれる | Channel List順序不一致 | BuilderとParserへ同一配列を渡す |

---

# 10.16 未確定事項

- `0x30100001`のベンダー正式定義
- GT170接続時のDeviceInit正常値
- AllInit以降の実機通し動作
- `Size`、`Sign`、`Speed`コード
- `Endian_RAM`コードとEnumの正式マッピング
- Timestamp単位
- 既存RAMScopeコンフィグファイルの読込仕様
- `ReleaseBufferData`の必須性と位置
- APIのスレッドセーフ性
- CANの最終方式

---

# 10.17 現在の作業チェックリスト

## 完了済み

- [x] x64 DLLロード
- [x] 関数名と序数14でDeviceInitを解決
- [x] PowerShellからDeviceInitを実呼び出し
- [x] エラー193を解消
- [x] `RAMScope_Code_To_Error.vi`の4パターン試験
- [x] 薄いDLLラッパ12個を作成

## 次に作成

- [ ] typedef 7個
- [ ] `U8x4_To_U32.vi`
- [ ] `U8x4_To_I32.vi`
- [ ] `U8x8_To_U64.vi`
- [ ] `U32_To_LE_U8x4.vi`
- [ ] `I32_To_LE_U8x4.vi`
- [ ] Builder 3個
- [ ] Parser 2個
- [ ] 公開API 8個
- [ ] `PoC_RAMScope_Main.vi`

---

# 10.18 参照したNI公式資料

LabVIEWの操作名と関数名は、次のNI公式資料を確認して記載する。

- [タイプ定義および指定タイプ定義を作成する](https://www.ni.com/docs/ja-JP/bundle/labview/page/creating-type-definitions-and-strict-type-definitions.html)
- [配列サイズ関数（Array Size）](https://www.ni.com/docs/ja-JP/bundle/labview-api-ref/page/functions/array-size.html)
- [指標配列（Index Array）](https://www.ni.com/docs/ja-JP/bundle/labview-api-ref/page/functions/index-array.html)
- [部分配列（Array Subset）](https://www.ni.com/docs/ja-JP/bundle/labview-api-ref/page/functions/array-subset.html)
- [配列初期化（Initialize Array）](https://www.ni.com/docs/ja-JP/bundle/labview-api-ref/page/functions/initialize-array.html)
- [部分配列置換（Replace Array Subset）](https://www.ni.com/docs/ja-JP/bundle/labview-api-ref/page/functions/replace-array-subset.html)
- [配列連結追加（Build Array）](https://www.ni.com/docs/ja-JP/bundle/labview-api-ref/page/functions/build-array.html)
- [型変換関数（Type Cast）](https://www.ni.com/docs/ja-JP/bundle/labview-api-ref/page/functions/type-cast.html)
- [名前でバンドル（Bundle By Name）](https://www.ni.com/docs/ja-JP/bundle/labview-api-ref/page/functions/bundle-by-name.html)
- [以上?関数（Greater Or Equal?）](https://www.ni.com/docs/ja-JP/bundle/labview-api-ref/page/functions/greater-or-equal.html)
- [1D配列検索関数（Search 1D Array）](https://www.ni.com/docs/ja-JP/bundle/labview-api-ref/page/functions/search-1d-array.html)
- [選択関数（Select）](https://www.ni.com/docs/ja-JP/bundle/labview-api-ref/page/functions/select.html)

NI公式日本語ページが版によって表示されない場合は、同じURLの`ja-JP`を`en-US`へ変更して英語版を確認し、本章の日本語名と英語名を照合する。
