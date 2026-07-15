# 10. RAMScope GT170 実装ガイド

> **本章をRAMScope実装の唯一の正本とする。**
>
> 旧`10A`、`10B`、`10B-1`、`10B-2`、`10B-3`、`10B-4`の内容を本章へ統合した。
> DLL準備、CLFN、共通エラー変換、薄いDLLラッパ、構造体生成、Parser、公開API、最小PoCまでを上から順に実施する。
>
> 関数プロトタイプの一次情報は`docs/reference/RAMScopeVP.h`、ハードウェア定数は`docs/reference/GTHard.h`、呼び出し例は`docs/reference/samp_simple.cpp`を優先する。

**最終整理日：2026-07-15**

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

RAMScopeVP APIは、LabVIEW向けに作られたVIライブラリではなく、C言語用のDLL APIである。そのため、LabVIEWから利用するには、次の差を吸収する仕組みが必要になる。

```text
RAMScopeVP API側
  C関数
  C構造体
  ポインタ
  生バイト列
  API独自ReturnCode

        ↓ そのままではLabVIEW / TestStandから扱いにくい

LabVIEW / TestStand側
  数値・配列・Cluster
  error cluster
  1イベント単位の公開VI
  試験条件・順序・結果管理
```

すべてを1個の巨大なVIへ入れると、DLL呼び出し、構造体変換、データ解析、試験フローのどこで失敗したかを切り分けにくい。そこで、責務ごとに段階を分ける。

### 問題と必要なレイヤの対応

| RAMScope実装で発生する問題 | 必要な仕組み | 配置先・主なVI |
|---|---|---|
| C関数をLabVIEWから呼ぶ必要がある | CLFN設定を1関数単位で隔離する | `10_DLL_Wrapper\RS_DLL_*` |
| CLFNエラーとAPI ReturnCodeが別経路で返る | 2系統のエラーを標準error clusterへ統合する | `RAMScope_Code_To_Error.vi` |
| API入力がC構造体ポインタである | LabVIEWの設定値をC互換U8配列へ組み立てる | `Build_MEASINFO_170_Raw.vi`等 |
| API出力が構造体や生バッファである | U8配列をLabVIEWのClusterや数値へ解析する | `Parse_SYSINFO_Array.vi`等 |
| Endianと符号を意識して数値変換する必要がある | 数値とU8配列の変換を共通部品化する | `U8x4_To_U32.vi`等 |
| TestStandからCLFN単位では扱いづらい | 接続、初期化、読出し等のイベント単位へまとめる | `30_Public\RAMScope_*` |
| TestStand組み込み前に下位層を検証したい | 公開APIだけを順番に呼ぶ単体PoCを用意する | `PoC_RAMScope_Main.vi` |

### レイヤを分ける理由

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

この構成にすると、次の切り分けができる。

- DLLがロードできない場合は`10_DLL_Wrapper`より下を確認する。
- ReturnCodeの表現がおかしい場合は`RAMScope_Code_To_Error.vi`を確認する。
- 設定値がDLLへ正しく渡らない場合はBuilderを確認する。
- 読み出した値がずれる場合はParserとByte Orderを確認する。
- 呼び出し順が違う場合は公開APIまたはPoCを確認する。
- 試験条件や繰り返しが違う場合はTestStandを確認する。

### なぜ各VIが必要なのか

#### `00_Common`

| VI / ctl | 必要な理由 |
|---|---|
| `RAMScope_Code_To_Error.vi` | CLFN自体のエラーとRAMScope API ReturnCodeを同じerror clusterへ流すため |
| `RAMScope_Byte_Order.ctl` | Little / Big Endianを数値ではなく意味のある選択肢として扱うため |
| `RAMScope_Channel.ctl` | 1個の監視RAM変数について、アドレス、符号、スケール等を1つにまとめるため |
| `RAMScope_Meas_Config.ctl` | 測定周期関係の設定をBuilderへまとめて渡すため |
| `RAMScope_Module_Log_Config.ctl` | モジュールごとのログ条件を配列で管理するため |
| `RAMScope_Module_Info.ctl` | SYSINFO 1レコードの解析結果を型として固定するため |
| `RAMScope_Channel_Value.ctl` | 1チャンネル分のRaw値と工学値を関連付けるため |
| `RAMScope_Packet.ctl` | 1パケットのチャンネル値、Flag、Timestampをまとめるため |
| 数値⇔U8変換VI | Endian、符号、4byte / 8byte変換をBuilderやParserへ重複実装しないため |

#### `10_DLL_Wrapper`

`RS_DLL_*`は、ヘッダに定義されたDLL関数と1対1で対応する。1関数1VIにすることで、CLFNの引数型、Pointer設定、事前確保サイズ、関数名を個別にテストできる。

```text
RS_DLL_GT150GetSysInfo.vi
  担当：GetSysInfoを呼び、U8[960]を受け取るところまで

Parse_SYSINFO_Array.vi
  担当：U8[960]の意味を解析する
```

DLLラッパへParserを入れないのは、DLL呼び出し成功とデータ解析成功を別々に判断するためである。

#### `20_Data_Conversion`

BuilderとParserはDLLを呼ばない純粋処理VIとする。実機がなくてもダミーデータで単体テストでき、CLFNクラッシュの影響を受けずにバイト配置を検証できる。

```text
LabVIEW設定値
  → Builder
  → C構造体互換U8配列
  → DLLラッパ

DLLラッパ
  → 生U8配列
  → Parser
  → LabVIEW Cluster / 数値
```

#### `30_Public`

TestStandが必要としているのは、`GetSysInfo`や`SetMeasCh`というDLL関数名ではなく、「接続する」「初期化する」「測定条件を設定する」「読む」「閉じる」という試験イベントである。公開APIは複数の下位VIを正しい順番で接続し、TestStandへ安定した端子を提供する。

#### `40_PoC`

公開APIをTestStandへ組み込む前に、LabVIEWだけで通し動作を確認する。これにより、実機・DLL・Parserの問題とTestStand設定の問題を混ぜずに済む。

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

旧`20_Parser`フォルダを既に作成している場合は、Builderを含む責務に合わせて`20_Data_Conversion`へ名前を変更する。

`RAMScope_Context.ctl`は現時点では作成しない。PoC中は`UnitNo`、`MdlNo_RAM`、`MdlNo_CAN`、`Endian_RAM`、`Channel List`を個別配線する。

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

## 10.3.3 既知事象：エラー193とCLFN関数未認識

観測した現象：

```text
Error 193 (0xC1)
%1 は有効な Win32 アプリケーションではありません。
```

確認済み：

```text
RAMScopeVP_API_x64.dll : x64
RAMScopeGT150DeviceInit: 名前付きエクスポートあり
Ordinal                : 14
```

64bit APIフォルダへ次のx86版VC++2013ランタイムが混在していた場合、x64プロセスがローカルDLLを優先して読み込み、エラー193になる可能性が高い。

```text
mfc120jpn.dll
mfc120u.dll
msvcp120.dll
msvcr120.dll
```

対策：

1. Visual C++ 2013 Redistributable x64を導入する。
2. 上記4ファイルが実際にx86で、64bit APIフォルダへ混在している場合だけ、復元可能なバックアップフォルダへ移動する。
3. `PGTMgrVP.dll`、`PGTMgrVP_ENG.dll`、`utillc.dll`、`pgtlib`配下は移動しない。

```powershell
$root = "C:\DTSinsight\RAMScopeVP\app\RAMScopeVP_API(64bit)"
$backup = Join-Path $root "_x86_runtime_backup"

New-Item -ItemType Directory -Path $backup -Force | Out-Null

@(
    "mfc120jpn.dll",
    "mfc120u.dll",
    "msvcp120.dll",
    "msvcr120.dll"
) | ForEach-Object {
    $source = Join-Path $root $_
    if (Test-Path -LiteralPath $source) {
        Move-Item -LiteralPath $source -Destination $backup -Force
    }
}
```

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

`Handle=0x0`はロード失敗。無効ハンドルで`GetProcAddress`を実行した結果は評価しない。

## 10.3.5 実機未接続時の観測

```text
ReturnCode = 0x30100001
UnitNum    = 0
kind       = 0
```

ここから確認できるのはDLLロード、関数解決、関数呼び出し、ポインタ引数でクラッシュしないことまで。`0x30100001`の正式意味は未確定であり、「未接続エラー」と断定しない。

---

# 10.4 APIライフサイクルと型

## 10.4.1 GT170でも使用するGT150共通関数

- `RAMScopeGT150DeviceInit`
- `RAMScopeGT150DeviceExit`
- `RAMScopeGT150AllInit`
- `RAMScopeGT150GetSysInfo`
- `RAMScopeGT150PGT_SetMdlConfig`
- `RAMScopeGT150SetLoggingInfo`
- `RAMScopeGT150MeasStart`
- `RAMScopeGT150GetBufferData`
- `RAMScopeGT150ReleaseBufferData`
- `RAMScopeGT150MeasStop`

GT170専用：

- `RAMScopeGT170SetMeasCond`
- `RAMScopeGT170SetMeasCh`

## 10.4.2 呼び出し順

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

## 10.4.3 C型とLabVIEW型

| C型 | LabVIEW |
|---|---|
| `long` | I32 |
| `long *` | I32 / Pointer to Value |
| `unsigned long` / `DWORD` | U32 |
| 構造体ポインタ | U8一次元配列 / Array Data Pointer |
| `long[]` | I32一次元配列 / Array Data Pointer |

Windowsの`long`は64bit DLLでも32bit。I64へ変更しない。

## 10.4.4 使用構造体サイズ

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

# 10.5 LabVIEW共通作業ルール

## 10.5.1 関数の探し方

関数パレットの日本語名称はLabVIEW版によって若干異なる。見つからない場合はブロックダイアグラム上で`Ctrl + Space`を押し、以下の英語名を入力してQuick Dropから配置する。

| 関数 | パレットの目安 |
|---|---|
| `Case Structure` | 関数 → プログラミング → ストラクチャ |
| `For Loop` | 関数 → プログラミング → ストラクチャ |
| `Unbundle By Name` | 関数 → プログラミング → クラスタ、クラス、バリアント |
| `Bundle By Name` | 関数 → プログラミング → クラスタ、クラス、バリアント |
| `Array Size` | 関数 → プログラミング → 配列 |
| `Index Array` | 関数 → プログラミング → 配列 |
| `Array Subset` | 関数 → プログラミング → 配列 |
| `Initialize Array` | 関数 → プログラミング → 配列 |
| `Replace Array Subset` | 関数 → プログラミング → 配列 |
| `Build Array` | 関数 → プログラミング → 配列 |
| `Join Numbers` | 関数 → プログラミング → 数値 → データ操作 |
| `Split Number` | 関数 → プログラミング → 数値 → データ操作 |
| `Type Cast` | 関数 → プログラミング → 数値 → データ操作 |
| `Format Into String` | 関数 → プログラミング → 文字列 |
| `Equal?` | 関数 → プログラミング → 比較 |
| `Greater Or Equal?` | 関数 → プログラミング → 比較 |
| `Less Or Equal?` | 関数 → プログラミング → 比較 |
| `Compound Arithmetic` | 関数 → プログラミング → Boolean |

## 10.5.2 通常VIのエラーガード

```text
error in
  → Unbundle By Name(status)
  → Case Structure
      True : 実処理を呼ばず、元エラーと安全な初期出力を返す
      False: 実処理を実行
```

全ケースの出力トンネルを配線し、`Use default if unwired`へ依存しない。

## 10.5.3 ローカル検証エラーコード

PoC中の入力検証エラーは次の範囲を使用する。本表を正本とし、別の番号を各VIへ勝手に追加しない。

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

## 10.6.1 フロントパネル

| 端子 | 方向 | 型 |
|---|---|---|
| `API ReturnCode` | 入力 | I32 |
| `Function Name` | 入力 | String |
| `error in` | 入力 | error cluster |
| `error out` | 出力 | error cluster |

保存先：

```text
30_RAMScope\00_Common\RAMScope_Code_To_Error.vi
```

## 10.6.2 配置する関数

- `Unbundle By Name`
- `Case Structure` ×2
- `Equal?`
- I32定数`0`
- `Type Cast`
- U32型指定定数
- `Format Into String`
- `Bundle By Name`

## 10.6.3 配線

1. `error in`を`Unbundle By Name`へ接続し、要素名を`status`にする。
2. `status`を外側Case Structureの`?`端子へ接続する。
3. 外側Trueケースでは`error in`をそのまま`error out`へ接続する。
4. 外側Falseケースへ`Equal?`を置く。
5. `API ReturnCode`とI32定数`0`を`Equal?`へ接続する。
6. `Equal?`出力を内側Case Structureへ接続する。
7. 内側Trueケースは`ReturnCode=0`なので`error in`をそのまま出力する。
8. 内側Falseケースでは`API ReturnCode`を`Type Cast`でU32として解釈する。
9. `Format Into String`へ次を設定する。

```text
RAMScope %s failed. ReturnCode=0x%08X (%d)
```

引数順：

```text
%s   ← Function Name
%08X ← Type Cast後U32
%d   ← 元のI32 ReturnCode
```

10. `Bundle By Name`へ正常な`error in`を基準クラスタとして接続し、次を上書きする。

```text
status = True
code   = API ReturnCode（I32）
source = Format Into String出力
```

## 10.6.4 単体テスト

| error in | ReturnCode | 期待結果 |
|---|---:|---|
| 正常 | 0 | 正常クラスタ |
| 正常 | `806354945` | `0x30100001`を含むエラー |
| code=1234の既存エラー | 任意 | 1234を保持 |
| 正常 | -1 | 16進表示`0xFFFFFFFF` |

---

# 10.7 薄いDLLラッパ12個

## 10.7.1 全CLFN共通設定

| 項目 | 設定 |
|---|---|
| Library | `RAMScopeVP_API_x64.dll`のフルパス |
| Calling Convention | `C` |
| Thread | PoC中は`Run in UI thread` |
| Error checking | PoC中は`Maximum` |
| Return | Numeric / Signed 32-bit Integer / Value |

通常ラッパは`error in.status=True`でCLFNをスキップする。`DeviceExit`だけはCleanup用なので前段エラーがあっても呼ぶ。

各ラッパのCLFN後段：

```text
CLFN戻り値 ─────────→ API ReturnCode表示器
CLFN戻り値 ─────────→ RAMScope_Code_To_Error / API ReturnCode
関数名文字列定数 ───→ RAMScope_Code_To_Error / Function Name
CLFN error out ──────→ RAMScope_Code_To_Error / error in
変換後error out ─────→ ラッパerror out
```

## 10.7.2 CLFN一覧

| VI | 関数 | CLFN入力 | CLFN出力・初期化 |
|---|---|---|---|
| `RS_DLL_GT150DeviceInit.vi` | `RAMScopeGT150DeviceInit` | `pUnitNum` I32 Pointer、`kind` I32 Pointer | 左端子へI32 `0`。右端子からUnitNum/kind |
| `RS_DLL_GT150DeviceExit.vi` | `RAMScopeGT150DeviceExit` | 引数なし | ReturnCode。前段エラーでも呼ぶ |
| `RS_DLL_GT150AllInit.vi` | `RAMScopeGT150AllInit` | `UnitNo` I32 Value | ReturnCode |
| `RS_DLL_GT150GetSysInfo.vi` | `RAMScopeGT150GetSysInfo` | `UnitNo`、`pSysInfo` U8 Array Data Pointer | U8[960]を事前確保 |
| `RS_DLL_GT150PGT_SetMdlConfig.vi` | `RAMScopeGT150PGT_SetMdlConfig` | `UnitNo`、`SlotErr` I32 Array Data Pointer | I32[16]を事前確保 |
| `RS_DLL_GT170SetMeasCond.vi` | `RAMScopeGT170SetMeasCond` | `UnitNo`、`MdlNo`、U8[72] | Builder出力を接続 |
| `RS_DLL_GT170SetMeasCh.vi` | `RAMScopeGT170SetMeasCh` | `UnitNo`、`MdlNo`、`ChNum`、U8[`24×ChNum`] | Builder出力を接続 |
| `RS_DLL_GT150SetLoggingInfo.vi` | `RAMScopeGT150SetLoggingInfo` | `UnitNo`、U8[136] | Builder出力を接続 |
| `RS_DLL_GT150MeasStart.vi` | `RAMScopeGT150MeasStart` | `UnitNo` | `MdlNo`なし |
| `RS_DLL_GT150GetBufferData.vi` | `RAMScopeGT150GetBufferData` | `UnitNo`、`MdlNo`、U8 buffer、`pDataNum`、`pLostDataNum` | buffer事前確保、pDataNumへ最大数、Lostへ0 |
| `RS_DLL_GT150ReleaseBufferData.vi` | `RAMScopeGT150ReleaseBufferData` | `UnitNo` | 独立ラッパ |
| `RS_DLL_GT150MeasStop.vi` | `RAMScopeGT150MeasStop` | `UnitNo` | `MdlNo`なし |

## 10.7.3 配列ポインタの作り方

### U8[960]

```text
U8定数0 → Initialize Array / element
I32定数960 → Initialize Array / dimension size
Initialize Array出力 → CLFN pSysInfo左端子
CLFN pSysInfo右端子 → SYSINFO Raw
```

### I32[16]

```text
I32定数0 → Initialize Array / element
I32定数16 → Initialize Array / dimension size
出力 → CLFN SlotErr左端子
CLFN SlotErr右端子 → SlotErr表示器
```

### GetBufferData

```text
Packet Size      = 4 × Channel Count + 12
Buffer Byte Size = Packet Size × Max DataNum

U8定数0 + Buffer Byte Size → Initialize Array → pData
Max DataNum → pDataNum左端子
I32定数0 → pLostDataNum左端子

pData右端子        → Raw Buffer
pDataNum右端子     → DataNum
pLostDataNum右端子 → LostDataNum
```

`ReleaseBufferData`をGetBufferDataラッパへ内包しない。

---

# 10.8 typedef作成

## 10.8.1 typedef共通手順

1. `ファイル → 新規 → カスタム制御器`を開く。
2. ClusterまたはEnumを配置する。
3. 各制御器を枠内へ入れる。
4. 各数値を右クリックし、`表現形式`をI32/U32/DBLへ合わせる。
5. ツールバーの制御器種別を`Type Def.`へ変更する。
6. `30_RAMScope\00_Common`へ保存する。

## 10.8.2 `RAMScope_Byte_Order.ctl`

Enumへ次の順で登録する。

```text
Little Endian
Big Endian
```

Enum値をCase Structureへ直接接続すると、ケース名が文字列ラベルで表示される。

## 10.8.3 `RAMScope_Meas_Config.ctl`

| フィールド | 型 | PoC初期例 |
|---|---|---:|
| `DummyInterval` | I32 | 100 |
| `MeasPeri` | I32 | 100 |
| `MeasUnit` | I32 | 2 |

## 10.8.4 `RAMScope_Channel.ctl`

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

`ChNum = Array Size(Channel List)`とし、別の手入力値を持たせない。

## 10.8.5 `RAMScope_Module_Log_Config.ctl`

| フィールド | 型 |
|---|---|
| `MdlNo` | I32 |
| `LogSize` | I32 |
| `BufferSize` | I32 |

## 10.8.6 `RAMScope_Module_Info.ctl`

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

## 10.8.7 `RAMScope_Channel_Value.ctl`

| フィールド | 型 |
|---|---|
| `Channel Index` | I32 |
| `Name` | String |
| `Address` | U32 |
| `Raw U32` | U32 |
| `Value` | DBL |
| `Engineering Value` | DBL |
| `Unit` | String |

## 10.8.8 `RAMScope_Packet.ctl`

| フィールド | 型 |
|---|---|
| `Packet Index` | I32 |
| `Channel Values` | `RAMScope_Channel_Value.ctl`一次元配列 |
| `Flag` | U32 |
| `Timestamp Raw` | U64 |
| `Timestamp Seconds` | DBL |

---

# 10.9 数値⇔U8変換VIの詳細作成手順

この節は、各関数の配置場所と各端子への配線を省略しない。

## 10.9.1 `U8x4_To_U32.vi`

### A. 完成時の入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Bytes` | 入力 | U8一次元配列 |
| `Byte Order` | 入力 | `RAMScope_Byte_Order.ctl` |
| `error in` | 入力 | error cluster |
| `Value` | 出力 | U32 |
| `error out` | 出力 | error cluster |

保存先：

```text
30_RAMScope\00_Common\U8x4_To_U32.vi
```

コネクタペイン推奨：

```text
左上  Bytes
左中  Byte Order
左下  error in
右上  Value
右下  error out
```

### B. 配置する関数と場所

| 個数 | 関数 | 配置場所 |
|---:|---|---|
| 1 | `Unbundle By Name` | プログラミング → クラスタ、クラス、バリアント |
| 3 | `Case Structure` | プログラミング → ストラクチャ |
| 1 | `Array Size` | プログラミング → 配列 |
| 1 | `Equal?` | プログラミング → 比較 |
| 1 | `Index Array` | プログラミング → 配列 |
| 6 | `Join Numbers` | プログラミング → 数値 → データ操作 |
| 1 | `Format Into String` | プログラミング → 文字列 |
| 1 | `Bundle By Name` | プログラミング → クラスタ、クラス、バリアント |

`Join Numbers`はLittle Endianケースに3個、Big Endianケースに3個配置する。

### C. 外側Case Structureを作る

1. `error in`を`Unbundle By Name`左端子へ接続する。
2. `Unbundle By Name`の要素名を`status`にする。
3. `status`のBoolean出力を最も外側のCase Structureの`?`端子へ接続する。
4. `Bytes`、`Byte Order`、`error in`をCase Structure左枠へ配線してトンネルを作る。
5. `Value`と`error out`用の右側トンネルを作る。

#### 外側Trueケース

前段エラーあり。

```text
U32定数0 → Value出力トンネル
error in  → error out出力トンネル
```

このケースでは配列を解析しない。

#### 外側Falseケース

以下のサイズ判定を作る。

### D. U8配列サイズを検証する

1. `Array Size`を外側Falseケース内へ配置する。
2. `Bytes`を`Array Size`の配列入力へ接続する。
3. I32数値定数`4`を置く。
4. `Equal?`の一方へ`Array Size`出力、もう一方へI32定数`4`を接続する。
5. `Equal?`のBoolean出力を2個目のCase Structureの`?`端子へ接続する。

ケースの意味：

```text
True  : Array Size(Bytes) == 4
False : 4バイトではない
```

### E. サイズ不正ケース

内側Falseケースへ次を配置する。

1. U32定数`0`を`Value`出力トンネルへ接続する。
2. `Format Into String`を置く。
3. フォーマット文字列を次にする。

```text
U8x4_To_U32.vi: Input size must be 4. Actual=%d
```

4. `%d`の入力へ`Array Size`出力を接続する。
5. `Bundle By Name`を置き、基準クラスタへ`error in`を接続する。
6. 要素を`status`、`code`、`source`の3個に広げる。
7. 次を接続する。

```text
Boolean True       → status
I32定数 -700101    → code
Format Into String → source
```

8. `Bundle By Name`出力を`error out`トンネルへ接続する。

### F. 4バイトを取り出す

内側Trueケースへ`Index Array`を配置する。

1. `Bytes`を`Index Array`の配列入力へ接続する。
2. `Index Array`の下端を下へドラッグし、出力を4個表示する。
3. index入力へI32定数`0`を接続する。
4. 4個の出力を上から順に次の名前として扱う。

```text
出力0 = b0 = Bytes[0]
出力1 = b1 = Bytes[1]
出力2 = b2 = Bytes[2]
出力3 = b3 = Bytes[3]
```

各出力がU8であることを詳細ヘルプで確認する。

### G. Byte Order Case Structureを作る

1. 3個目のCase Structureを内側Trueケースへ配置する。
2. `Byte Order`をセレクタ`?`へ接続する。
3. ケース名が`Little Endian`と`Big Endian`になることを確認する。
4. b0、b1、b2、b3をケース枠へ配線する。

### H. Little Endianケースの接続

`Join Numbers`は上側入力が上位側、下側入力が下位側である。端子名は詳細ヘルプで`high`と`low`を確認する。

```text
Join #1（低位16bitを作る）
  high byte ← b1
  low byte  ← b0
  output    → Low Word U16

Join #2（高位16bitを作る）
  high byte ← b3
  low byte  ← b2
  output    → High Word U16

Join #3（U32を作る）
  high word ← High Word U16
  low word  ← Low Word U16
  output    → Value
```

例：

```text
Bytes = 78 56 34 12
Value = 0x12345678
```

### I. Big Endianケースの接続

```text
Join #1（高位16bitを作る）
  high byte ← b0
  low byte  ← b1
  output    → High Word U16

Join #2（低位16bitを作る）
  high byte ← b2
  low byte  ← b3
  output    → Low Word U16

Join #3（U32を作る）
  high word ← High Word U16
  low word  ← Low Word U16
  output    → Value
```

例：

```text
Bytes = 12 34 56 78
Value = 0x12345678
```

### J. error outを接続する

Byte Orderの両ケースで`error in`を変更せず、同じ出力トンネルへ接続する。

最終的な構造：

```text
外側Case: error in.status
├─ True
│   ├─ Value = 0
│   └─ error out = error in
└─ False
    └─ 内側Case: Array Size(Bytes) == 4
        ├─ False
        │   ├─ Value = 0
        │   └─ -700101エラー生成
        └─ True
            ├─ Index Arrayでb0..b3
            └─ Byte Order Case
                ├─ Little Endian: b1/b0, b3/b2をJoin
                └─ Big Endian   : b0/b1, b2/b3をJoin
```

### K. 単体テスト

| Bytes | Byte Order | 期待Value |
|---|---|---:|
| `78 56 34 12` | Little Endian | `0x12345678` |
| `12 34 56 78` | Big Endian | `0x12345678` |
| `FF FF FF FF` | Little Endian | `0xFFFFFFFF` |
| 3要素 | 任意 | error code `-700101` |
| 既存エラー | 任意 | 既存エラーを保持、Value=0 |

## 10.9.2 `U8x4_To_I32.vi`

`U8x4_To_U32.vi`を内部で再利用し、同じ解析処理を複製しない。

### 端子

| 端子 | 方向 | 型 |
|---|---|---|
| `Bytes` | 入力 | U8一次元配列 |
| `Byte Order` | 入力 | `RAMScope_Byte_Order.ctl` |
| `error in` | 入力 | error cluster |
| `Value` | 出力 | I32 |
| `error out` | 出力 | error cluster |

### 配置する関数

- `U8x4_To_U32.vi`
- `Type Cast`
- I32数値定数（型指定用）

### 配線

```text
Bytes ────────→ U8x4_To_U32 / Bytes
Byte Order ───→ U8x4_To_U32 / Byte Order
error in ─────→ U8x4_To_U32 / error in

U8x4_To_U32 / Value U32 ─→ Type Cast / x
I32定数0 ─────────────────→ Type Cast / type
Type Cast出力 ─────────────→ Value I32
U8x4_To_U32 / error out ───→ error out
```

通常の数値変換ではなく`Type Cast`を使い、32bitのビット列を維持して符号付きとして解釈する。

単体テスト：

```text
Bytes = FF FF FF FF / Little Endian
期待Value = -1
```

## 10.9.3 `U8x8_To_U64.vi`

### 端子

| 端子 | 方向 | 型 |
|---|---|---|
| `Bytes` | 入力 | U8一次元配列 |
| `Byte Order` | 入力 | `RAMScope_Byte_Order.ctl` |
| `error in` | 入力 | error cluster |
| `Value` | 出力 | U64 |
| `error out` | 出力 | error cluster |

### 配置する関数

- `Unbundle By Name`
- `Case Structure` ×3
- `Array Size`
- `Equal?`
- `Array Subset` ×2
- `U8x4_To_U32.vi` ×2
- `Join Numbers` ×2（Byte Order各ケースに1個）
- `Format Into String`
- `Bundle By Name`

### サイズ判定

`U8x4_To_U32.vi`と同じ外側エラーCaseを作り、内側で次を判定する。

```text
Array Size(Bytes) == 8
```

不正時はValue=0、code=`-700102`、sourceに実サイズを入れる。

### 8バイトを2分割する

内側Trueケースで次を作る。

```text
Array Subset #1
  array  ← Bytes
  index  ← 0
  length ← 4
  output → First4

Array Subset #2
  array  ← Bytes
  index  ← 4
  length ← 4
  output → Last4
```

`First4`と`Last4`をそれぞれ`U8x4_To_U32.vi`へ接続し、error clusterを直列にする。

### Little Endian

```text
First4 U32 → Low DWord
Last4 U32  → High DWord

Join Numbers
  high ← High DWord
  low  ← Low DWord
  out  → U64 Value
```

### Big Endian

```text
First4 U32 → High DWord
Last4 U32  → Low DWord

Join Numbers
  high ← High DWord
  low  ← Low DWord
  out  → U64 Value
```

単体テスト：

```text
Bytes = 32 00 00 00 00 00 00 00 / Little Endian
期待Value = 50

Bytes = 00 00 00 00 00 00 00 32 / Big Endian
期待Value = 50
```

## 10.9.4 `U32_To_LE_U8x4.vi`

構造体はLittle Endianで生成するため、Byte Order入力は持たせない。

### 端子

| 端子 | 方向 | 型 |
|---|---|---|
| `Value` | 入力 | U32 |
| `error in` | 入力 | error cluster |
| `Bytes` | 出力 | U8一次元配列 |
| `error out` | 出力 | error cluster |

### 配置する関数

- `Unbundle By Name`
- `Case Structure`
- `Split Number` ×3
- `Build Array`

### Falseケースの配線

1. `Split Number #1`へU32 `Value`を接続する。
2. 出力の`most significant half`を`High Word U16`、`least significant half`を`Low Word U16`として扱う。
3. `Split Number #2`へ`Low Word`を接続する。
4. 出力を`b1`（most significant byte）、`b0`（least significant byte）とする。
5. `Split Number #3`へ`High Word`を接続する。
6. 出力を`b3`（most significant byte）、`b2`（least significant byte）とする。
7. `Build Array`へ次の順で接続する。

```text
input 0 ← b0
input 1 ← b1
input 2 ← b2
input 3 ← b3
```

出力はU8一次元配列になる。

```text
Value 0x12345678
  → Bytes 78 56 34 12
```

外側Trueケースは空U8配列と元エラーを返す。

## 10.9.5 `I32_To_LE_U8x4.vi`

### 配置する関数

- `Type Cast`
- U32数値定数（型指定用）
- `U32_To_LE_U8x4.vi`

### 配線

```text
I32 Value → Type Cast / x
U32定数0  → Type Cast / type
Type Cast U32 → U32_To_LE_U8x4 / Value
error in      → U32_To_LE_U8x4 / error in
Bytes         ← U32_To_LE_U8x4 / Bytes
error out     ← U32_To_LE_U8x4 / error out
```

単体テスト：

```text
Value = 100 → 64 00 00 00
Value = -1  → FF FF FF FF
```

---

# 10.10 構造体Builderの詳細作成手順

## 10.10.1 `Build_MEASINFO_170_Raw.vi`

### 端子

| 端子 | 方向 | 型 |
|---|---|---|
| `Meas Config` | 入力 | `RAMScope_Meas_Config.ctl` |
| `error in` | 入力 | error cluster |
| `MEASINFO_170 Raw` | 出力 | U8一次元配列 |
| `error out` | 出力 | error cluster |

### 配置する関数

- `Unbundle By Name`（error status用）
- `Case Structure`
- `Initialize Array`
- `Unbundle By Name`（Meas Config用）
- `I32_To_LE_U8x4.vi` ×3
- `Replace Array Subset` ×3
- `Array Size`（デバッグ確認用）

### 配線

1. `error in.status`でCase Structureを作る。
2. TrueケースはU8[72]ゼロ配列と元エラーを返す。
3. FalseケースでU8定数`0`とI32定数`72`を`Initialize Array`へ接続する。
4. `Meas Config`を`Unbundle By Name`へ接続し、`DummyInterval`、`MeasPeri`、`MeasUnit`を取り出す。
5. 3値をそれぞれ`I32_To_LE_U8x4.vi`へ接続し、errorを直列にする。
6. `Replace Array Subset`を3個直列にする。

```text
U8[72]
 → Replace index 0  / DummyInterval U8[4]
 → Replace index 4  / MeasPeri U8[4]
 → Replace index 8  / MeasUnit U8[4]
 → MEASINFO_170 Raw
```

offset 12から71は0のままにする。

### 単体テスト

```text
DummyInterval=100, MeasPeri=100, MeasUnit=2

64 00 00 00
64 00 00 00
02 00 00 00
00 00 00 00
00 00 00 00
...
Array Size = 72
```

## 10.10.2 `Build_CHINFO_170_Raw.vi`

### 端子

| 端子 | 方向 | 型 |
|---|---|---|
| `Channel List` | 入力 | `RAMScope_Channel.ctl`一次元配列 |
| `error in` | 入力 | error cluster |
| `ChNum` | 出力 | I32 |
| `CHINFO_170 Raw` | 出力 | U8一次元配列 |
| `error out` | 出力 | error cluster |

### 配置する関数

- `Array Size`
- `Greater Or Equal?`
- `Less Or Equal?`
- `Compound Arithmetic`（AND）
- `Case Structure`
- `For Loop`
- `Unbundle By Name`
- `U32_To_LE_U8x4.vi` ×6
- `Build Array` ×2
- Shift Register
- `Format Into String`
- `Bundle By Name`

### ChNum判定

```text
Channel List → Array Size → To I32 → ChNum

ChNum >= 1
ChNum <= 2048
       ↓
Compound Arithmetic AND
       ↓
Case Structure
```

Falseケース：

```text
CHINFO Raw = 空U8配列
error code = -700111
source = Build_CHINFO_170_Raw.vi: Channel count must be 1..2048. ChNum=%d
```

### For Loop

1. `Channel List`をFor Loop枠へ配線し、入力トンネルの自動インデックスを有効にする。
2. For Loop枠を右クリックし、`Add Shift Register`を選ぶ。
3. 左Shift Registerへ空のU8一次元配列定数を接続する。
4. 1反復へ1個の`RAMScope_Channel.ctl`が入る。
5. `Unbundle By Name`で次を取り出す。

```text
Enable
Core
Address
Size
Sign
Speed
```

6. 6値を`U32_To_LE_U8x4.vi`へ直列接続する。
7. `Build Array #1`を右クリックし、`Concatenate Inputs`を有効にする。
8. 入力を6個まで増やし、次の順で接続する。

```text
Enable Bytes
Core Bytes
Address Bytes
Size Bytes
Sign Bytes
Speed Bytes
```

出力はU8[24]。

9. `Build Array #2`も`Concatenate Inputs`を有効にする。
10. 左入力へShift Registerの累積U8配列、右入力へ今回のU8[24]を接続する。
11. 出力を右Shift Registerへ接続する。
12. ループ後のShift Registerを`CHINFO_170 Raw`へ接続する。

```text
Array Size(CHINFO_170 Raw) = 24 × ChNum
```

2次元配列になった場合は`Build Array`の`Concatenate Inputs`が無効になっている。

## 10.10.3 `Build_LOGINFO_Raw.vi`

### 端子

| 端子 | 方向 | 型 |
|---|---|---|
| `LogDevice` | 入力 | I32 |
| `LimitHddSize` | 入力 | I32 |
| `Module Log Configs` | 入力 | `RAMScope_Module_Log_Config.ctl`一次元配列 |
| `error in` | 入力 | error cluster |
| `LOGINFO Raw` | 出力 | U8一次元配列 |
| `error out` | 出力 | error cluster |

### 配置する関数

- `Initialize Array` ×2
- `I32_To_LE_U8x4.vi` ×4（ヘッダ2個、ループ内2個）
- `Replace Array Subset` ×4
- `For Loop`
- Shift Register ×2（U8[136]、Seen Boolean[16]）
- `Unbundle By Name`
- `Greater Or Equal?`
- `Less Or Equal?`
- `Compound Arithmetic`
- `Index Array`
- `Not`
- `Case Structure`
- `Multiply`、`Add`
- `Replace Array Subset`（Seen更新用）
- `Format Into String`
- `Bundle By Name`

### 初期配列とヘッダ

```text
U8 0 × 136 → LOGINFO初期配列
Boolean False × 16 → Seen初期配列

LogDevice    → I32_To_LE_U8x4 → Replace index 0
LimitHddSize → I32_To_LE_U8x4 → Replace index 4
```

### For Loop内

`Module Log Configs`を自動インデックス入力する。`Unbundle By Name`で`MdlNo`、`LogSize`、`BufferSize`を取得する。

判定：

```text
0 <= MdlNo <= 15
AND Seen[MdlNo] == False
```

Trueケース：

```text
Log index    = 8  + MdlNo × 8
Buffer index = 12 + MdlNo × 8

LogSize    → I32_To_LE_U8x4 → Replace Log index
BufferSize → I32_To_LE_U8x4 → Replace Buffer index

Boolean True → Replace Array Subset(Seen, index=MdlNo)
```

Falseケース：

- 現在のU8[136]を変更せず出力する。
- error code=`-700112`を生成する。
- sourceへ`MdlNo`と重複有無を含める。

ループ終了後：

```text
Array Size(LOGINFO Raw) = 136
```

---

# 10.11 Parserの詳細作成手順

## 10.11.1 `Parse_SYSINFO_Array.vi`

### 端子

| 端子 | 方向 | 型 |
|---|---|---|
| `SYSINFO Raw` | 入力 | U8一次元配列 |
| `Byte Order` | 入力 | `RAMScope_Byte_Order.ctl` |
| `error in` | 入力 | error cluster |
| `Module List` | 出力 | `RAMScope_Module_Info.ctl`一次元配列 |
| `MdlNo_RAM` | 出力 | I32、初期値-1 |
| `MdlNo_CAN` | 出力 | I32、初期値-1 |
| `Endian_RAM` | 出力 | I32、初期値0 |
| `RAM Module Found?` | 出力 | Boolean |
| `CAN Module Found?` | 出力 | Boolean |
| `error out` | 出力 | error cluster |

### 配置する関数

- `Unbundle By Name`
- `Case Structure` ×複数
- `Array Size`
- `Equal?`
- `For Loop`
- `Multiply`
- `Array Subset`
- `U8x4_To_I32.vi` ×11
- `Search 1D Array`
- `Byte Array To String`
- `Bundle By Name`
- Shift Register ×3
- `Compound Arithmetic`
- `Greater Or Equal?`
- `Format Into String`

### 外側エラーとサイズ判定

1. `error in.status`で外側Caseを作る。
2. Falseケースで`Array Size(SYSINFO Raw) == 960`を判定する。
3. サイズ不正時は次を返す。

```text
Module List = 空配列
MdlNo_RAM = -1
MdlNo_CAN = -1
Endian_RAM = 0
Found? = False
error code = -700120
```

### For Loop

1. For LoopのN端子へI32定数`16`を接続する。
2. 反復端子`i`とI32定数`60`を`Multiply`へ接続する。
3. `Array Subset`へ次を接続する。

```text
array  ← SYSINFO Raw
index  ← i × 60
length ← 60
```

4. レコードU8[60]から各4バイトを`Array Subset`で取り出し、`U8x4_To_I32.vi`へ接続する。

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

変換VIのerror clusterをフィールド順に直列接続する。

### name[16]

1. `Array Subset(index=44, length=16)`でName Bytesを取得する。
2. `Search 1D Array`の配列入力へName Bytes、検索要素へU8定数`0`を接続する。
3. 検索結果をCase Structureへ接続する。
4. `-1`ケースは16バイト全て使用する。
5. `Default`ケースは`Array Subset(index=0, length=検索結果)`でNULLより前を切り出す。
6. U8配列を`Byte Array To String`へ接続し、Name文字列を取得する。

### Module Infoクラスタ

`Bundle By Name`へ`RAMScope_Module_Info.ctl`定数を接続し、全フィールドを格納する。

```text
Connected? = module_type != 0x0F
```

For Loopの出力トンネルを自動インデックスにし、`Module List`を作る。

### RAM/CANモジュール番号

Shift Register初期値：

```text
MdlNo_RAM = -1
MdlNo_CAN = -1
Endian_RAM = 0
```

RAM判定：

```text
module_type == 0x00 AND MdlNo_RAM == -1
```

True時：`MdlNo_RAM=module`、`Endian_RAM=endian`。

CAN判定：

```text
module_type == 0x02 AND MdlNo_CAN == -1
```

True時：`MdlNo_CAN=module`。

ループ後：

```text
RAM Module Found? = MdlNo_RAM >= 0
CAN Module Found? = MdlNo_CAN >= 0
```

CAN未搭載はParserエラーにしない。RAM未搭載の停止判定は`RAMScope_Init.vi`で行う。

## 10.11.2 `RAMScope_Parse_Buffer.vi`

### 端子

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

### 配置する関数

- `Array Size` ×複数
- `Multiply`、`Add`、`Subtract`
- `Greater Or Equal?`、`Greater Than 0?`
- `Compound Arithmetic`
- `Case Structure`
- `For Loop` ×2
- `Array Subset`
- `U8x4_To_U32.vi`
- `U8x4_To_I32.vi`
- `U8x8_To_U64.vi`
- `Unbundle By Name`
- `Bundle By Name`
- `Type Cast`
- `To Double Precision Float`
- `Select`
- Shift Register（error cluster）

### 入力サイズ計算

```text
ChNum              = Array Size(Channel List)
Packet Size         = 4 × ChNum + 12
Expected Byte Count = Packet Size × DataNum
Actual Byte Count   = Array Size(Raw Buffer)
Unused Byte Count   = Actual - Expected
```

有効条件：

```text
ChNum > 0
DataNum >= 0
Actual >= Expected
```

- `DataNum=0`は正常。空Packetsを返す。
- `Actual < Expected`はcode=`-700131`。
- ChNumやDataNumが不正な場合はcode=`-700130`。

### 外側For Loop

N端子へ`DataNum`を接続する。

```text
Packet Start = packet index × Packet Size
```

error clusterをShift Registerでループへ持ち込む。各反復の先頭でerror statusをCase Structureへ接続し、Trueなら解析をスキップする。

### 内側For Loop

`Channel List`を自動インデックス入力する。

```text
Value Start = Packet Start + channel index × 4
```

1. `Array Subset(array=Raw Buffer, index=Value Start, length=4)`を作る。
2. 4バイトを`U8x4_To_U32.vi`へ接続し、`Raw U32`を取得する。
3. Channel clusterを`Unbundle By Name`し、`Name`、`Address`、`Sign`、`Scale`、`Offset`、`Unit`を取得する。
4. `Sign == 0`を判定する。
5. 符号なし：U32を`To Double Precision Float`へ接続する。
6. 符号あり：Raw U32を`Type Cast`でI32へ変換し、I32をDBLへ変換する。
7. `Select`で符号あり/なしのDBLを選ぶ。
8. 次を計算する。

```text
Engineering Value = Value × Scale + Offset
```

9. `Bundle By Name`で`RAMScope_Channel_Value.ctl`を作る。
10. 内側For Loop出力を自動インデックスにし、Channel Values配列を作る。

`Sign`の正式マッピングは未確定。PoCでは`0=符号なし、0以外=符号あり`として既知値と照合する。

### Flag

```text
Flag Start = Packet Start + 4 × ChNum
Array Subset(length=4)
  → U8x4_To_U32.vi
  → Flag
```

### Timestamp

```text
Timestamp Start = Packet Start + 4 × ChNum + 4
Array Subset(length=8)
  → U8x8_To_U64.vi
  → Timestamp Raw
```

作業仮定：

```text
Timestamp Seconds = Timestamp Raw × 20e-9
```

### Packetクラスタ

```text
Packet Index
Channel Values
Flag
Timestamp Raw
Timestamp Seconds
```

を`Bundle By Name`へ接続する。外側For Loopの自動インデックス出力を`Packets`へ接続する。

```text
Parsed Packet Count = Array Size(Packets)
```

### 単体テスト

2チャンネル、1パケット：

```text
01 00 00 00              Channel 0 = 1
FE FF FF FF              Channel 1 = -2
A5 00 00 00              Flag = 0xA5
32 00 00 00 00 00 00 00 Timestamp = 50
```

期待：

```text
Value[0] = 1
Value[1] = -2
Flag = 0xA5
Timestamp Raw = 50
Parsed Packet Count = 1
Unused Byte Count = 0
```

---

# 10.12 公開API作成

全公開APIは末尾で`Error_To_TestStatus.vi`を1回呼び、`Status.ctl`、`TestError.ctl`、標準error clusterを出力する。

## 10.12.1 `RAMScope_Connect.vi`

```text
RS_DLL_GT150DeviceInit.vi
  → Error_To_TestStatus.vi
```

出力：UnitNum、kind、API ReturnCode、Status、TestError、error out。

## 10.12.2 `RAMScope_Init.vi`

```text
RS_DLL_GT150AllInit.vi
  → RS_DLL_GT150GetSysInfo.vi
  → Parse_SYSINFO_Array.vi
  → RAM Module Found?判定
  → RS_DLL_GT150PGT_SetMdlConfig.vi
  → SlotErr[MdlNo_RAM]判定
  → Error_To_TestStatus.vi
```

`RAMScope_Config.vi`は作成しない。PGT設定は`RAMScope_Init.vi`へ統合する。

出力：Module List、MdlNo_RAM、MdlNo_CAN、Endian_RAM、SlotErr。

## 10.12.3 `RAMScope_Set_Cond.vi`

```text
Meas Config
 → Build_MEASINFO_170_Raw.vi
 → RS_DLL_GT170SetMeasCond.vi

Channel List
 → Build_CHINFO_170_Raw.vi
 → ChNum / CHINFO Raw
 → RS_DLL_GT170SetMeasCh.vi

Module Log Configs
 → Build_LOGINFO_Raw.vi
 → RS_DLL_GT150SetLoggingInfo.vi

最後にError_To_TestStatus.vi
```

## 10.12.4 `RAMScope_Log_Start.vi`

`RS_DLL_GT150MeasStart.vi`だけを呼ぶ。

## 10.12.5 `RAMScope_Read.vi`

```text
Channel List → Array Size → ChNum
Packet Size = 4 × ChNum + 12
Buffer Byte Size = Packet Size × Max DataNum

RS_DLL_GT150GetBufferData.vi
  → Raw Buffer / DataNum / LostDataNum
  → RAMScope_Parse_Buffer.vi
  → Packets
  → Error_To_TestStatus.vi
```

`ReleaseBufferData`は内包しない。

## 10.12.6 `RAMScope_Release.vi`

`RS_DLL_GT150ReleaseBufferData.vi`だけを呼ぶ実験用公開API。要否確定後に残すか廃止する。

## 10.12.7 `RAMScope_Log_Stop.vi`

`RS_DLL_GT150MeasStop.vi`だけを呼ぶ。

## 10.12.8 `RAMScope_Close.vi`

前段エラーがあってもDeviceExitを実行する。

```text
元のerror in ─────────────────────────────┐
                                           ├→ Merge Errors → Error_To_TestStatus
Clear Errors → RS_DLL_GT150DeviceExit.vi ─┘
```

元エラーを優先し、DeviceExitエラーも別途ログへ残す。

---

# 10.13 最小PoC

## 10.13.1 `PoC_RAMScope_Main.vi`

```text
Setup/Main経路
  RAMScope_Connect.vi
    → RAMScope_Init.vi
    → RAMScope_Set_Cond.vi
    → RAMScope_Log_Start.vi
    → Wait
    → RAMScope_Read.vi
    → RAMScope_Log_Stop.vi

Cleanup経路
  計測中ならRAMScope_Log_Stop.vi
    → RAMScope_Release.vi（比較条件で有効化）
    → RAMScope_Close.vi
```

## 10.13.2 合格条件

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
- 複数回の再接続・再測定が可能

## 10.13.3 `ReleaseBufferData`比較

```text
A: ReadごとにRelease
B: Stop後にRelease
C: Releaseを使用しない
```

メモリ使用量、再測定、DataNum、LostDataNum、APIエラーを比較して決定する。

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
| エラー193 | x64/x86不一致、ローカルx86依存DLL | 対象4ランタイムのみ隔離、VC++2013 x64確認 |
| エラー126 | 依存DLL不足 | ベンダー相対配置、GT170 DLL、VC++確認 |
| エラー127 | 関数名、無効ハンドル | 先にHandle非ゼロ確認、関数名完全一致 |
| CLFN正常・ReturnCode異常 | RAMScope API内部結果 | ReturnCodeを別経路で評価 |
| LabVIEWクラッシュ | 引数型、配列サイズ、ポインタ | ヘッダとCLFNを再照合、UI thread/Maximum |
| U8変換値が逆 | Byte Order配線 | Little/BigのJoin Numbers順を確認 |
| CHINFOが2次元 | Build Array設定 | `Concatenate Inputs`を有効化 |
| Buffer不足 | Buffer Byte Size式 | `(4×ChNum+12)×MaxDataNum`を確認 |
| 値と変数名がずれる | Channel List順序不一致 | BuilderとParserへ同一配列を渡す |

---

# 10.16 未確定事項

- `0x30100001`のベンダー正式定義
- GT170接続時のDeviceInit正常戻り値、UnitNum、kind
- AllInit以降の実機通し動作
- `Size`、`Sign`、`Speed`コードの正式定義
- `Endian_RAM`コードと`RAMScope_Byte_Order.ctl`の正式マッピング
- Timestamp単位の実機確定
- 既存RAMScopeコンフィグファイルの正式読込仕様
- `ReleaseBufferData`の必須性と呼び出し位置
- APIのスレッドセーフ性
- CANの最終方式

未確定事項は公開APIへ推測で固定せず、実機結果またはベンダー一次資料取得後に更新する。

---

# 10.17 現在の作業チェックリスト

## 完了済み

- [x] x64 DLLロード
- [x] 関数名と序数14でDeviceInitを解決
- [x] PowerShellからDeviceInitを実呼び出し
- [x] x86版VC++2013ランタイム混在によるエラー193を解消
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

各VIは、端子型、関数配置、全ケースの出力配線、ダミーデータ単体試験を完了してから次へ進む。
