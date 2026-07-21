# 10. RAMScope GT170 実装ガイド

> **本章をRAMScope実装の唯一の正本とする。**
>
> DLL準備、CLFN、共通エラー変換、薄いDLLラッパ、typedef、数値変換、構造体生成、Parser、公開API、ダミーデータ検証、最小PoCまでを上から順に実施する。
>
> 手順の書き方は[00A_LabVIEW実装資料の記述ルール.md](./00A_LabVIEW実装資料の記述ルール.md)を正とする。関数プロトタイプの一次情報は`docs/reference/RAMScopeVP.h`、ハードウェア定数は`docs/reference/GTHard.h`、呼び出し例は`docs/reference/samp_simple.cpp`を優先する。

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

RAMScopeは最初からTestStandへ組み込まない。各レイヤをLabVIEW単体で確認してから次へ進む。

## 10.1.2 VI作成手順の統一書式

本章で作成するVIは、次の順番で説明する。

```text
0. 目的と処理概要
1. 入出力
2. 配置する関数およびSubVI等
3. 配線順
4. 単体テスト
```

配線順では次を省略しない。

- 接続元の正式な端子名
- 接続先の関数名と端子名
- 数値定数の型
- Case Structureの条件と全ケース出力
- ForループのN端子と自動指標付けの有効・無効
- シフトレジスタの初期値、左右端子、最終出力
- ダミー配列の生成方法と書込index
- 推奨プローブ位置

## 10.1.3 状態表記

| 表記 | 意味 |
|---|---|
| **確定** | ヘッダ、外部仕様書、または再現可能な実測で確認済み |
| **PoC済み** | 最小条件で動作確認済み |
| **実機確認待ち** | VI構成は作成できるが、GT170接続時の確認が未完了 |
| **未確定** | 推測で実装へ固定しない |
| **作業仮定** | 単体テスト用に置いた暫定ルール。一次情報入手後に再確認する |

---

# 10.2 採用構成とフォルダ構成

## 10.2.1 なぜこの構成を採用するのか

RAMScopeVP APIはLabVIEW用VIではなくC言語用DLL APIである。LabVIEWから使用するには、C関数、構造体ポインタ、生バイト列、API独自ReturnCodeを、LabVIEWの数値、配列、クラスタ、標準error clusterへ変換する必要がある。

すべてを1個の巨大なVIへ入れると、DLL呼び出し、構造体変換、データ解析、試験フローのどこで失敗したかを切り分けられない。そこで責務ごとにレイヤを分ける。

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
│  ├─ PoC_RAMScope_Main.vi
│  ├─ Test_Parse_SYSINFO_Array.vi
│  └─ Test_RAMScope_Parse_Buffer.vi
│
├─ 50_CAN\
└─ 90_TestStand\
```

`Test_Parse_SYSINFO_Array.vi`と`Test_RAMScope_Parse_Buffer.vi`はダミーデータ生成用であり、本番公開APIから呼ばない。

`RAMScope_Context.ctl`はPoC完了まで作成しない。`UnitNo`、`MdlNo_RAM`、`MdlNo_CAN`、`Endian_RAM`、`Channel List`を個別配線する。

## 10.2.4 レイヤ責務

| レイヤ | 責務 | 含めないもの |
|---|---|---|
| `00_Common` | typedef、バイト変換、APIコード変換 | DLL呼び出し、機器状態遷移 |
| `10_DLL_Wrapper` | 1個のCLFNで1関数だけ呼ぶ | Builder、Parser、複数API制御、Status生成 |
| `20_Data_Conversion` | C構造体互換U8配列生成、生バイト列解析 | DLL呼び出し、測定開始・停止 |
| `30_Public` | ラッパと変換VIを接続し1イベントを完結 | TestStand固有変数への直接依存 |
| `40_PoC` | 公開APIとParserを単体確認 | 本番試験シナリオ |
| TestStand | 条件、順序、Wait、Loop、分岐、レポート、Cleanup | `RS_DLL_*`の直接呼び出し |

---

# 10.3 環境準備・DLL疎通

## 10.3.1 必要ソフトウェア

| ソフトウェア | 必要な理由 | 確認方法 |
|---|---|---|
| LabVIEW 64bit | x64 API DLLを同一プロセスへロードする | About画面で64bitを確認 |
| RAMScopeVP / RAMScopeVP API 64bit版 | GT170ドライバ、API、PGT設定 | 純正アプリとAPIフォルダを確認 |
| RAMScope USBドライバ | GT170をUSB3.0で認識する | デバイスマネージャーと純正アプリ |
| PGTツール | プローブ・モジュール構成を設定する | 純正ツールで構成読出し |
| Visual C++ 2013 Redistributable x64 | `120`系x64ランタイムを提供する | DLL疎通結果で確認 |

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

上記ファイルが実際にx86であることを確認できた場合だけ、復元可能なバックアップフォルダへ移動する。`PGTMgrVP.dll`、`PGTMgrVP_ENG.dll`、`utillc.dll`、`pgtlib`は一律移動しない。

## 10.3.4 PowerShell疎通合格条件

```text
PowerShell 64-bit : True
Requested path    : RAMScopeVP_API_x64.dllのフルパス
Loaded path       : Requested pathと同じ
Handle            : 0x0以外
Name Found        : True
Ordinal Found     : True
Name Address      : Ordinal Address
```

実機未接続時に`RAMScopeGT150DeviceInit`から`0x30100001`を観測した。正式定義は未確認であり、「未接続エラー」と断定しない。

## 10.3.5 LabVIEW疎通確認

1. `RS_DLL_GT150DeviceInit.vi`を開く。
2. Context Helpで`pUnitNum`、`kind`、ReturnCode、error in/outを確認する。
3. PowerShellと同じDLLフルパスをCLFNへ設定する。
4. GT170未接続状態で実行し、LabVIEWがクラッシュせずReturnCodeを取得できることを確認する。
5. GT170接続後にUnitNum、kind、ReturnCodeを記録する。

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

| C型 | LabVIEW | CLFN設定の考え方 |
|---|---|---|
| `long` | I32 | Numeric / Signed 32-bit / Value |
| `long *` | I32 | Numeric / Signed 32-bit / Pointer to Value |
| `unsigned long` / `DWORD` | U32 | Numeric / Unsigned 32-bit |
| 構造体ポインタ | U8一次元配列 | Array / Unsigned 8-bit / Array Data Pointer |
| `long[]` | I32一次元配列 | Array / Signed 32-bit / Array Data Pointer |

Windowsの`long`は64bit DLLでも32bitである。I64へ変更しない。

## 10.4.3 使用構造体サイズ

| 構造体 | サイズ | 用途 |
|---|---:|---|
| `SYSINFO` | 60byte × 16 = 960byte | モジュール情報取得 |
| `MEASINFO_170` | 72byte | 測定周期等の設定 |
| RAM用`CHINFO_170` | 24byte × ChNum | チャンネル設定 |
| `LOGINFO` | 136byte | モジュール別ログ設定 |

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
| シフトレジスタ | Shift Register | Forループ枠を右クリック → シフトレジスタを追加 |
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
| 文字列からバイト配列 | String To Byte Array | プログラミング → 文字列 → 文字列/配列/パス変換 |
| バイト配列から文字列 | Byte Array To String | プログラミング → 文字列 → 文字列/配列/パス変換 |
| 等しい? | Equal? | プログラミング → 比較 |
| 等しくない? | Not Equal? | プログラミング → 比較 |
| 以上? | Greater Or Equal? | プログラミング → 比較 |
| 以下? | Less Or Equal? | プログラミング → 比較 |
| 選択 | Select | プログラミング → 比較 |
| 複合演算 | Compound Arithmetic | プログラミング → ブール |
| NOT | Not | プログラミング → ブール |
| 倍精度浮動小数点に変換 | To Double Precision Float | プログラミング → 数値 → 変換 |
| 加算 | Add | プログラミング → 数値 |
| 減算 | Subtract | プログラミング → 数値 |
| 乗算 | Multiply | プログラミング → 数値 |

見つからない場合は`Ctrl + Space`でクイックドロップを開き、英語名で検索する。

## 10.5.2 通常VIのエラーガード

```text
error in
  → 名前でバンドル解除（status）
  → ケースストラクチャ
      True : 実処理を呼ばず、元エラーと安全な初期出力を返す
      False: 入力検証後に実処理を実行
```

全ケースの出力トンネルを配線し、`Use default if unwired`へ依存しない。

## 10.5.3 Forループの自動指標付け

### 配列から1要素ずつ取り出す場合

```text
Channel List配列
  → Forループ入力トンネル
  → 指標付けを有効（Enable Indexing）
```

ループ外は配列、ループ内は`RAMScope_Channel.ctl`単体になる。

### 配列全体から任意位置を切り出す場合

```text
SYSINFO Raw U8[960]
  → Forループ入力トンネル
  → 指標付けを無効（Disable Indexing）
```

ループ内でもU8[960]全体を保持する。自動指標付けを有効にするとU8単体になり、部分配列の`array`端子へ接続できない。

## 10.5.4 シフトレジスタ

追加方法：

```text
Forループ枠を右クリック
  → シフトレジスタを追加（Add Shift Register）
```

```text
左外側端子 : ループ開始前の初期値
左内側端子 : 前回反復までの値
右内側端子 : 今回反復後の値
右外側端子 : 全反復終了後の最終値
```

判定Falseケースでは左内側の現在値を右内側へ渡す。初期値`-1`や`0`へ毎回戻さない。

## 10.5.5 U8配列の表示

配列枠ではなく、配列内の数値セルを右クリックする。

```text
表示形式 → 16進数
表示項目 → 基数
```

LabVIEWの`x78`は資料中の`0x78`と同じ値である。

## 10.5.6 実要素数の変更

表示枠を狭めても実配列サイズは変わらない。

```text
配列内要素を右クリック
  → データ操作
  → 要素を挿入／要素を削除
```

配列サイズ（Array Size）で実要素数を確認する。

## 10.5.7 ローカル検証エラーコード

| コード | 用途 |
|---:|---|
| `-700101` | U8x4変換VIの入力サイズ不正 |
| `-700102` | U8x8変換VIの入力サイズ不正 |
| `-700111` | CHINFOチャンネル数不正 |
| `-700112` | LOGINFOモジュール番号または重複不正 |
| `-700120` | SYSINFOサイズ不正 |
| `-700130` | Buffer Parser入力不正 |
| `-700131` | Raw Buffer不足 |
| `-700140` | RAMモジュール未検出 |
| `-700141` | PGT SlotErr検出 |

---

# 10.6 `RAMScope_Code_To_Error.vi`

## 10.6.1 目的と処理概要

CLFNのerror clusterとRAMScope API ReturnCodeを1本の標準error clusterへ統合する。既存エラーがある場合はReturnCodeで上書きしない。

## 10.6.2 入出力

| 端子 | 方向 | 型 | 用途 |
|---|---|---|---|
| `API ReturnCode` | 入力 | I32 | DLL関数の戻り値 |
| `Function Name` | 入力 | String | sourceへ記録する関数名 |
| `error in` | 入力 | error cluster | CLFN errorまたは前段エラー |
| `error out` | 出力 | error cluster | 統合結果 |

## 10.6.3 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所 |
|---:|---|---|---|
| 1 | 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 2 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 1 | 等しい? | Equal? | プログラミング → 比較 |
| 1 | 型変換 | Type Cast | プログラミング → 数値 → データ操作 |
| 1 | 文字列にフォーマット | Format Into String | プログラミング → 文字列 |
| 1 | 名前でバンドル | Bundle By Name | プログラミング → クラスタ、クラス、バリアント |

## 10.6.4 配線順

1. `error in`を名前でバンドル解除へ接続し、`status`を取り出す。
2. `status`を外側ケースストラクチャへ接続する。
3. 外側Trueでは`error in`をそのまま`error out`へ接続する。
4. 外側Falseで`API ReturnCode`を等しい?の一方へ接続する。
5. I32定数`0`を等しい?のもう一方へ接続する。
6. 比較結果を内側ケースストラクチャへ接続する。
7. 内側Trueでは正常な`error in`をそのまま`error out`へ接続する。
8. 内側Falseでは`API ReturnCode`を型変換の`x`へ接続する。
9. U32定数`0`を型変換の`type`へ接続し、同じ32bitをU32として解釈する。
10. 文字列にフォーマットへ次を設定する。

```text
RAMScope %s failed. ReturnCode=0x%08X (%d)
```

11. `%s`へ`Function Name`を接続する。
12. `%08X`へU32変換値を接続する。
13. `%d`へ元のI32 ReturnCodeを接続する。
14. 名前でバンドルへ正常な`error in`を基準クラスタとして接続する。
15. Boolean定数Trueを`status`へ接続する。
16. 元のI32 ReturnCodeを`code`へ接続する。
17. 生成文字列を`source`へ接続する。
18. 名前でバンドル出力を`error out`へ接続する。

## 10.6.5 単体テスト

| error in | ReturnCode | 期待結果 |
|---|---:|---|
| 正常 | 0 | 正常クラスタ |
| 正常 | `806354945` | sourceに`0x30100001` |
| code=1234の既存エラー | 任意 | code=1234とsourceを保持 |
| 正常 | -1 | sourceに`0xFFFFFFFF` |

---

# 10.7 薄いDLLラッパ12個

## 10.7.1 目的と共通構造

各VIは1個のDLL関数だけを呼ぶ。CLFN設定、API引数、ReturnCode変換以外の処理を入れない。

```text
error in.status
  → Case Structure
      True  : CLFNを呼ばず、安全な初期出力
      False : CLFNを1回呼ぶ
                → RAMScope_Code_To_Error.vi
  → error out
```

`RS_DLL_GT150DeviceExit.vi`だけはCleanup用のため、前段エラーがあってもDeviceExitを試みる。

## 10.7.2 CLFN共通設定

| 項目 | 設定 |
|---|---|
| Library | `RAMScopeVP_API_x64.dll`のフルパス |
| Calling Convention | `C` |
| Thread | PoC中は`Run in UI thread` |
| Error checking | PoC中は`Maximum` |
| Return | Numeric / Signed 32-bit Integer / Value |

## 10.7.3 ラッパ一覧と接続内容

| VI | DLL関数 | CLFN入力 | 事前生成する値 | CLFN出力 |
|---|---|---|---|---|
| `RS_DLL_GT150DeviceInit.vi` | `RAMScopeGT150DeviceInit` | I32 Pointer ×2 | pUnitNum=0、kind=0 | UnitNum、kind、ReturnCode |
| `RS_DLL_GT150DeviceExit.vi` | `RAMScopeGT150DeviceExit` | なし | なし | ReturnCode |
| `RS_DLL_GT150AllInit.vi` | `RAMScopeGT150AllInit` | UnitNo I32 Value | なし | ReturnCode |
| `RS_DLL_GT150GetSysInfo.vi` | `RAMScopeGT150GetSysInfo` | UnitNo、U8 Array Pointer | U8[960]ゼロ配列 | SYSINFO Raw、ReturnCode |
| `RS_DLL_GT150PGT_SetMdlConfig.vi` | `RAMScopeGT150PGT_SetMdlConfig` | UnitNo、I32 Array Pointer | I32[16]ゼロ配列 | SlotErr[16]、ReturnCode |
| `RS_DLL_GT170SetMeasCond.vi` | `RAMScopeGT170SetMeasCond` | UnitNo、MdlNo、U8 Array Pointer | MEASINFO U8[72] | ReturnCode |
| `RS_DLL_GT170SetMeasCh.vi` | `RAMScopeGT170SetMeasCh` | UnitNo、MdlNo、ChNum、U8 Array Pointer | CHINFO U8[`24×ChNum`] | ReturnCode |
| `RS_DLL_GT150SetLoggingInfo.vi` | `RAMScopeGT150SetLoggingInfo` | UnitNo、U8 Array Pointer | LOGINFO U8[136] | ReturnCode |
| `RS_DLL_GT150MeasStart.vi` | `RAMScopeGT150MeasStart` | UnitNo | なし | ReturnCode |
| `RS_DLL_GT150GetBufferData.vi` | `RAMScopeGT150GetBufferData` | UnitNo、MdlNo、MaxDataNum、Raw Buffer Pointer、DataNum Pointer、Lost Pointer | 必要サイズのU8ゼロ配列 | Raw Buffer、DataNum、LostDataNum、ReturnCode |
| `RS_DLL_GT150ReleaseBufferData.vi` | `RAMScopeGT150ReleaseBufferData` | UnitNo | なし | ReturnCode |
| `RS_DLL_GT150MeasStop.vi` | `RAMScopeGT150MeasStop` | UnitNo | なし | ReturnCode |

## 10.7.4 各ラッパの共通配線順

1. CLFNを1個配置する。
2. ライブラリパス、関数名、Calling Convention、Return型を設定する。
3. ヘッダの左から右の引数順にCLFNパラメータを追加する。
4. 入力値を対応するCLFN端子へ接続する。
5. Pointer出力用の初期値または配列をCLFN左側端子へ接続する。
6. CLFN右側端子を本VIの出力表示器へ接続する。
7. CLFN ReturnCodeを`RAMScope_Code_To_Error.vi`の`API ReturnCode`へ接続する。
8. CLFNの`error out`を同SubVIの`error in`へ接続する。
9. DLL関数名文字列を`Function Name`へ接続する。
10. SubVIの`error out`を本ラッパの`error out`へ接続する。
11. CLFN error inへ本ラッパの`error in`を接続する。
12. Pointer出力、ReturnCode、error outをコネクタペインへ割り当てる。

## 10.7.5 単体テスト

- `DeviceInit`：PowerShellと同じ関数を解決し、クラッシュせずReturnCodeを返す。
- `GetSysInfo`：未接続または状態不正でもSYSINFO Rawのサイズが960である。
- `PGT_SetMdlConfig`：SlotErr配列サイズが16である。
- `SetMeasCond`：入力配列サイズ72でCLFNへ到達する。
- `SetMeasCh`：`Array Size(CHINFO)=24×ChNum`である。
- `SetLoggingInfo`：入力配列サイズ136である。
- `GetBufferData`：事前確保したRaw BufferサイズとDataNum/LostDataNumを記録する。
- 全ラッパで既存error in時の通常処理スキップを確認する。
- DeviceExitは既存error inでもCLFNを呼ぶことを確認する。

---

# 10.8 typedef作成

## 10.8.1 共通作成手順

1. プロジェクトエクスプローラで`30_RAMScope\00_Common`を右クリックする。
2. `新規 → タイプ定義`を選ぶ。
3. 制御器エディタが開いたことを確認する。
4. クラスタ型の場合はクラスタを配置する。
5. Enum型の場合は列挙体を配置する。
6. 必要な数値、文字列、Boolean、配列を配置する。
7. 数値制御器を右クリックし、`表現形式`をI32、U32、U64、DBLへ合わせる。
8. フィールド名とクラスタ順序を表の順に合わせる。
9. 指定ファイル名で保存する。
10. `新規 → タイプ定義`から作成したため、後からType Def.へ変更する操作は不要である。

## 10.8.2 型一覧

### `RAMScope_Byte_Order.ctl`

Enum：

```text
Little Endian
Big Endian
```

### `RAMScope_Meas_Config.ctl`

| フィールド | 型 |
|---|---|
| `DummyInterval` | I32 |
| `MeasPeri` | I32 |
| `MeasUnit` | I32 |

### `RAMScope_Channel.ctl`

| フィールド | 型 | 用途 |
|---|---|---|
| `Name` | String | 変数名 |
| `Enable` | U32 | 有効設定 |
| `Core` | U32 | Core番号 |
| `Address` | U32 | RAMアドレス |
| `Size` | U32 | データサイズコード |
| `Sign` | U32 | 符号コード |
| `Speed` | U32 | 速度・取得設定コード |
| `Scale` | DBL | 工学値変換倍率 |
| `Offset` | DBL | 工学値オフセット |
| `Unit` | String | 単位 |

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
| `Name` | String |
| `Flash Enable` | I32 |
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

## 10.8.3 `Channel List`一次元配列の作り方

`RAMScope_Channel.ctl`は1チャンネル分のクラスタであり、配列型ではない。

1. 対象VIのフロントパネルへ空の配列枠を配置する。
2. プロジェクトエクスプローラから`RAMScope_Channel.ctl`を配列枠の内側へドラッグする。
3. 配列全体のラベルを`Channel List`へ変更する。
4. ブロックダイアグラムで配列ワイヤになることを確認する。
5. 単体テストで1要素を使う場合は、配列内クラスタを右クリックし、`データ操作 → 要素を挿入`を実行する。
6. 配列サイズへ接続し、1要素なら`ChNum=1`になることを確認する。

```text
RAMScope_Channel.ctl          = 1チャンネル分
Channel List                 = RAMScope_Channel.ctlの一次元配列
ChNum                        = Array Size(Channel List)
CHINFO_170 Rawの必要バイト数 = 24 × ChNum
```

---

# 10.9 数値⇔U8変換VI

## 10.9.1 `U8x4_To_U32.vi`

### 0. 目的と処理概要

4個のU8をEndian指定に従ってU32へ結合する。入力配列サイズが4でない場合はローカル検証エラーを返す。

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
4. 配列サイズ出力とI32定数`4`を等しい?へ接続する。
5. 比較結果をサイズ判定ケースへ接続する。
6. サイズ不正FalseケースでU32定数`0`を`Value`へ接続する。
7. 文字列にフォーマットへ次を設定する。

```text
U8x4_To_U32.vi: Input size must be 4. Actual=%d
```

8. `%d`へ配列サイズ出力を接続する。
9. 名前でバンドルへ`error in`を基準クラスタとして接続する。
10. `status=True`、`code=-700101`、`source=生成文字列`を接続する。
11. 名前でバンドル出力を`error out`へ接続する。
12. サイズ正常Trueケースで指標配列を4出力へ広げる。
13. 4個のindex端子へ上からI32定数`0`、`1`、`2`、`3`を接続する。
14. 出力を上から`b0`、`b1`、`b2`、`b3`としてByte Orderケースへ渡す。
15. Little Endianケースでは次の順で数値結合する。

```text
低位16bit: high=b1, low=b0
高位16bit: high=b3, low=b2
U32      : high=高位16bit, low=低位16bit
```

16. Big Endianケースでは次の順で数値結合する。

```text
高位16bit: high=b0, low=b1
低位16bit: high=b2, low=b3
U32      : high=高位16bit, low=低位16bit
```

17. Byte Orderの両ケースで変換値を`Value`へ、正常なerror clusterを`error out`へ接続する。

### 4. 単体テスト

事前に`Bytes`配列内セルと`Value`表示器を16進数表示へ変更し、基数を表示する。

| Bytes | Byte Order | 期待Value |
|---|---|---|
| `x78 x56 x34 x12` | Little Endian | `x12345678` |
| `x12 x34 x56 x78` | Big Endian | `x12345678` |
| `xFF xFF xFF xFF` | Little Endian | `xFFFFFFFF` |
| 3要素 | 任意 | Value=0、code=`-700101` |
| 既存エラー | 任意 | 既存エラー保持、Value=0 |

3要素テストは表示枠を縮めず、4番目の要素を`データ操作 → 要素を削除`で削除し、配列サイズが3であることを確認する。

## 10.9.2 `U8x4_To_I32.vi`

### 0. 目的と処理概要

`U8x4_To_U32.vi`で作った32bitビット列を、ビット列を変更せずI32として解釈する。

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

1. `Bytes`を`U8x4_To_U32.vi`の`Bytes`へ接続する。
2. `Byte Order`を同SubVIの`Byte Order`へ接続する。
3. `error in`を同SubVIの`error in`へ接続する。
4. SubVIのU32 `Value`を型変換の`x`へ接続する。
5. I32定数`0`を型変換の`type`へ接続する。
6. 型変換のI32出力を本VIの`Value`へ接続する。
7. SubVIの`error out`を本VIの`error out`へ接続する。

### 4. 単体テスト

| Bytes | Byte Order | 期待Value |
|---|---|---:|
| `xFF xFF xFF xFF` | Little Endian | -1 |
| `x00 x00 x00 x80` | Little Endian | -2147483648 |
| `x7F xFF xFF xFF` | Big Endian | 2147483647 |
| 3要素 | 任意 | Value=0、code=`-700101` |

## 10.9.3 `U8x8_To_U64.vi`

### 0. 目的と処理概要

8個のU8を4バイトずつU32へ変換し、Endian指定に従ってU64へ結合する。

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

1. 外側error Caseを`U8x4_To_U32.vi`と同じ構成で作る。
2. `Bytes`の配列サイズがI32定数`8`と等しいか判定する。
3. サイズ不正ケースでU64定数`0`とcode=`-700102`を返す。
4. サイズ正常ケースへ部分配列を2個配置する。
5. 1個目へ`Bytes`、index=`0`、length=`4`を接続し、出力を`First4`とする。
6. 2個目へ`Bytes`、index=`4`、length=`4`を接続し、出力を`Last4`とする。
7. `U8x4_To_U32.vi`を2個配置する。
8. `First4`を1個目SubVIの`Bytes`へ、`Last4`を2個目SubVIの`Bytes`へ接続する。
9. `Byte Order`を両SubVIへ分岐する。
10. error clusterを1個目から2個目へ直列接続する。
11. Byte Orderケースを配置する。
12. Little Endianケースでは数値結合へ`high=Last4のU32`、`low=First4のU32`を接続する。
13. Big Endianケースでは`high=First4のU32`、`low=Last4のU32`を接続する。
14. 数値結合のU64出力を`Value`へ接続する。
15. 2個目SubVIの`error out`を本VIの`error out`へ接続する。

### 4. 単体テスト

| Bytes | Byte Order | 期待Value |
|---|---|---|
| `x32 x00 x00 x00 x00 x00 x00 x00` | Little Endian | 50 |
| `x00 x00 x00 x00 x00 x00 x00 x32` | Big Endian | 50 |
| `x78 x56 x34 x12 xEF xCD xAB x90` | Little Endian | `x90ABCDEF12345678` |
| 7要素 | 任意 | Value=0、code=`-700102` |

## 10.9.4 `U32_To_LE_U8x4.vi`

### 0. 目的と処理概要

U32を下位バイトから順に並べたLittle Endian U8[4]へ変換する。

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
| 1 | 空U8配列定数 | Empty U8 Array Constant | プログラミング → 配列 |

### 3. 配線順

1. `error in.status`をケースストラクチャへ接続する。
2. Trueケースで空U8配列を`Bytes`へ、元の`error in`を`error out`へ接続する。
3. Falseケースへ数値分割を3個配置する。
4. `Value`を1個目へ接続する。
5. 1個目の上側出力を`High Word`、下側出力を`Low Word`とする。
6. `Low Word`を2個目へ接続する。
7. 2個目の上側出力を`b1`、下側出力を`b0`とする。
8. `High Word`を3個目へ接続する。
9. 3個目の上側出力を`b3`、下側出力を`b2`とする。
10. 配列連結追加を4入力へ広げる。
11. 上から`b0`、`b1`、`b2`、`b3`を接続する。
12. 出力を`Bytes`へ接続する。
13. 正常な`error in`を`error out`へ接続する。

### 4. 単体テスト

| Value | 期待Bytes |
|---:|---|
| `x12345678` | `x78 x56 x34 x12` |
| `x00000064` | `x64 x00 x00 x00` |
| `xFFFFFFFF` | `xFF xFF xFF xFF` |
| 既存エラー | 空配列、既存エラー保持 |

## 10.9.5 `I32_To_LE_U8x4.vi`

### 0. 目的と処理概要

I32の32bitビット列を変更せずU32へ型変換し、Little Endian U8[4]へ変換する。

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

1. I32 `Value`を型変換の`x`へ接続する。
2. U32定数`0`を型変換の`type`へ接続する。
3. 型変換のU32出力を`U32_To_LE_U8x4.vi`の`Value`へ接続する。
4. `error in`をSubVIの`error in`へ接続する。
5. SubVIの`Bytes`を本VIの`Bytes`へ接続する。
6. SubVIの`error out`を本VIの`error out`へ接続する。

### 4. 単体テスト

| Value | 期待Bytes |
|---:|---|
| 100 | `x64 x00 x00 x00` |
| -1 | `xFF xFF xFF xFF` |
| -2147483648 | `x00 x00 x00 x80` |
| 既存エラー | 空配列、既存エラー保持 |

---

# 10.10 構造体Builder

## 10.10.1 `Build_MEASINFO_170_Raw.vi`

### 0. 目的と処理概要

`RAMScope_Meas_Config.ctl`の3個のI32値を、DLLが期待する72バイトの`MEASINFO_170`互換U8配列へ書き込む。

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
| 2 | 配列初期化 | Initialize Array | プログラミング → 配列 |
| 3 | `I32_To_LE_U8x4.vi` | SubVI | `30_RAMScope\00_Common` |
| 3 | 部分配列置換 | Replace Array Subset | プログラミング → 配列 |

### 3. 配線順

1. `error in.status`を外側ケースへ接続する。
2. TrueケースでU8定数`0`とI32定数`72`を配列初期化へ接続する。
3. U8[72]を`MEASINFO_170 Raw`へ、元の`error in`を`error out`へ接続する。
4. FalseケースでもU8[72]ゼロ配列を作る。
5. `Meas Config`を名前でバンドル解除へ接続し、`DummyInterval`、`MeasPeri`、`MeasUnit`を取り出す。
6. `I32_To_LE_U8x4.vi`を3個配置する。
7. 各値を対応SubVIの`Value`へ接続する。
8. error clusterを3個のSubVIへ直列接続する。
9. 部分配列置換を3個直列に配置する。
10. U8[72]を1個目の`array`へ接続する。
11. I32定数`0`を1個目の`index`へ、DummyInterval Bytesを`new element/subarray`へ接続する。
12. 1個目の出力を2個目の`array`へ接続する。
13. I32定数`4`とMeasPeri Bytesを2個目へ接続する。
14. 2個目の出力を3個目の`array`へ接続する。
15. I32定数`8`とMeasUnit Bytesを3個目へ接続する。
16. 3個目の出力を`MEASINFO_170 Raw`へ接続する。
17. 3個目SubVIの`error out`を本VIの`error out`へ接続する。
18. index 12～71は初期ゼロのまま残す。

### 4. 単体テスト

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

推奨プローブ：3個の変換SubVIのBytes出力、最後の部分配列置換出力。

## 10.10.2 `Build_CHINFO_170_Raw.vi`

### 0. 目的と処理概要

`Channel List`から1チャンネルずつ取り出し、各チャンネルの6個のU32フィールドを24バイトへ変換する。全チャンネル分をU8[`24×ChNum`]へ累積する。

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Channel List` | 入力 | `RAMScope_Channel.ctl`一次元配列 |
| `error in` | 入力 | error cluster |
| `ChNum` | 出力 | I32 |
| `CHINFO_170 Raw` | 出力 | U8一次元配列 |
| `error out` | 出力 | error cluster |

### 2. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所・追加方法 |
|---:|---|---|---|
| 1 | 配列サイズ | Array Size | プログラミング → 配列 |
| 2 | 以上? / 以下? | Greater Or Equal? / Less Or Equal? | プログラミング → 比較 |
| 1 | 複合演算 | Compound Arithmetic | プログラミング → ブール |
| 3 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 1 | Forループ | For Loop | プログラミング → ストラクチャ |
| 2 | シフトレジスタ | Shift Register | Forループ枠を右クリック → 追加 |
| 2 | 配列初期化 | Initialize Array | プログラミング → 配列 |
| 2 | 乗算 | Multiply | プログラミング → 数値 |
| 2 | 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 6 | `U32_To_LE_U8x4.vi` | SubVI | `30_RAMScope\00_Common` |
| 1 | 配列連結追加 | Build Array | プログラミング → 配列 |
| 1 | 部分配列置換 | Replace Array Subset | プログラミング → 配列 |
| 1 | 文字列にフォーマット | Format Into String | プログラミング → 文字列 |
| 1 | 名前でバンドル | Bundle By Name | プログラミング → クラスタ、クラス、バリアント |

### 3. 配線順

#### A. ChNumと範囲判定

1. `Channel List`を配列サイズへ接続する。
2. 配列サイズ出力を`ChNum`へ直接接続する。
3. `ChNum >= 1`と`ChNum <= 2048`を作る。比較定数はI32とする。
4. 2条件をANDへ接続する。
5. AND出力をチャンネル数判定ケースへ接続する。

#### B. チャンネル数不正Falseケース

1. 配列初期化へU8定数`0`とI32定数`0`を接続し、空U8配列を作る。
2. 空U8配列を`CHINFO_170 Raw`へ接続する。
3. 文字列にフォーマットへ次を設定する。

```text
Build_CHINFO_170_Raw.vi: Channel count must be 1..2048. ChNum=%d
```

4. `%d`へ`ChNum`を接続する。
5. 名前でバンドルへ`error in`を基準クラスタとして接続する。
6. `status=True`、`code=-700111`、`source=生成文字列`を接続する。
7. 名前でバンドル出力を`error out`へ接続する。

#### C. TrueケースのForループ

1. Forループを配置する。
2. `Channel List`をForループ左枠へ接続する。
3. 入力トンネルを右クリックし、`指標付けを有効`にする。
4. トンネルに`[]`が表示されたことを確認する。
5. N端子は未配線にする。Channel List要素数だけ反復する。

#### D. CHINFO配列用シフトレジスタ

1. Forループ枠を右クリックし、1本目のシフトレジスタを追加する。
2. `ChNum`とI32定数`24`を乗算し、`Total Byte Size`を作る。
3. 配列初期化へU8定数`0`と`Total Byte Size`を接続する。
4. U8[`24×ChNum`]ゼロ配列を1本目の左外側端子へ接続する。

#### E. error用シフトレジスタ

1. Forループ枠を再度右クリックし、2本目を追加する。
2. `error in`を2本目の左外側端子へ接続する。

#### F. 各反復の既存エラー確認

1. error左内側を名前でバンドル解除へ接続し、`status`をループ内ケースへ接続する。
2. TrueケースではCHINFO配列左内側を右内側へそのまま接続する。
3. 同じTrueケースでerror左内側を右内側へそのまま接続する。
4. Falseケースへ1チャンネル変換処理を作る。

#### G. 1チャンネルを24バイトへ変換

1. 自動指標付けトンネルから出た`RAMScope_Channel.ctl`単体を名前でバンドル解除へ接続する。
2. `Enable`、`Core`、`Address`、`Size`、`Sign`、`Speed`を取り出す。
3. `U32_To_LE_U8x4.vi`を6個配置する。
4. 各フィールドを対応SubVIの`Value`入力へ接続する。
5. error左内側をEnable変換SubVIの`error in`へ接続する。
6. 6個のSubVIのerror clusterを直列接続する。
7. 配列連結追加を6入力へ広げ、`入力を連結`を有効にする。
8. 上からEnable Bytes、Core Bytes、Address Bytes、Size Bytes、Sign Bytes、Speed Bytesを接続する。
9. 出力を`Current Channel Bytes` U8[24]とする。

#### H. 累積配列へ書込

1. Forループ反復端子`i`とI32定数`24`を乗算し、`Write Index`を作る。
2. 部分配列置換の`array`へCHINFO配列左内側を接続する。
3. `index`へ`Write Index`を接続する。
4. `new element/subarray`へ`Current Channel Bytes`を接続する。
5. 部分配列置換出力をCHINFO配列右内側へ接続する。
6. 6個目変換SubVIの`error out`をerror右内側へ接続する。

#### I. ループ終了後

1. CHINFO配列右外側を`CHINFO_170 Raw`へ接続する。
2. error右外側を`error out`へ接続する。

### 4. 単体テスト

1チャンネルへ次を設定する。

```text
Enable  = x11223344
Core    = x55667788
Address = x12345678
Size    = 4
Sign    = 1
Speed   = 2
```

期待出力：

```text
index  0..3  = x44 x33 x22 x11
index  4..7  = x88 x77 x66 x55
index  8..11 = x78 x56 x34 x12
index 12..15 = x04 x00 x00 x00
index 16..19 = x01 x00 x00 x00
index 20..23 = x02 x00 x00 x00
ChNum        = 1
Array Size   = 24
```

2チャンネルでは`ChNum=2`、Array Size=48を確認する。フロントパネルに10セルしか見えていない場合でも、配列サイズが24または48なら正常である。

推奨プローブ：ChNum、Total Byte Size、Current Channel Bytes、部分配列置換出力、右外側端子。

## 10.10.3 `Build_LOGINFO_Raw.vi`

### 0. 目的と処理概要

LogDeviceとLimitHddSizeを先頭8バイトへ書き込み、各`Module Log Configs`をMdlNoに対応する8バイト領域へ書き込む。Seen Boolean[16]でMdlNo重複を検出する。

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

| 数 | 日本語名 | 英語名 | 配置場所・追加方法 |
|---:|---|---|---|
| 2 | 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 複数 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 2 | 配列初期化 | Initialize Array | プログラミング → 配列 |
| 1 | Forループ | For Loop | プログラミング → ストラクチャ |
| 3 | シフトレジスタ | Shift Register | Forループ枠を右クリック → 追加 |
| 4 | `I32_To_LE_U8x4.vi` | SubVI | `30_RAMScope\00_Common` |
| 5 | 部分配列置換 | Replace Array Subset | プログラミング → 配列 |
| 1 | 指標配列 | Index Array | プログラミング → 配列 |
| 2 | 以上? / 以下? | Greater Or Equal? / Less Or Equal? | プログラミング → 比較 |
| 1 | NOT | Not | プログラミング → ブール |
| 1 | 複合演算 | Compound Arithmetic | プログラミング → ブール |
| 1 | 乗算 | Multiply | プログラミング → 数値 |
| 2 | 加算 | Add | プログラミング → 数値 |
| 1 | 文字列にフォーマット | Format Into String | プログラミング → 文字列 |
| 1 | 名前でバンドル | Bundle By Name | プログラミング → クラスタ、クラス、バリアント |

### 3. 配線順

#### A. 外側エラーガード

1. `error in.status`を外側ケースへ接続する。
2. TrueケースでU8[136]ゼロ配列を作る。
3. U8[136]を`LOGINFO Raw`へ、元の`error in`を`error out`へ接続する。

#### B. 初期配列とヘッダ

1. FalseケースでU8[136]ゼロ配列を作る。
2. Boolean定数FalseとI32定数`16`を配列初期化へ接続し、Seen Boolean[16]を作る。
3. `I32_To_LE_U8x4.vi`を2個配置する。
4. `LogDevice`を1個目SubVIの`Value`へ接続する。
5. `LimitHddSize`を2個目SubVIの`Value`へ接続する。
6. error clusterを2個のSubVIへ直列接続する。
7. 部分配列置換を2個直列に配置する。
8. U8[136]を1個目の`array`へ、I32定数`0`を`index`へ、LogDevice Bytesを`new element/subarray`へ接続する。
9. 1個目出力を2個目の`array`へ、I32定数`4`を`index`へ、LimitHddSize Bytesを`new element/subarray`へ接続する。
10. 2個目出力を`Header Written LOGINFO`とする。

#### C. Forループと3本のシフトレジスタ

1. Forループを配置する。
2. `Module Log Configs`を左枠へ接続し、自動指標付けを有効にする。
3. N端子は未配線にする。
4. シフトレジスタを3本追加する。
5. 1本目左外側へ`Header Written LOGINFO`を接続する。
6. 2本目左外側へSeen Boolean[16]を接続する。
7. 3本目左外側へヘッダ変換後のerror clusterを接続する。

```text
シフトレジスタ1 = 累積LOGINFO U8[136]
シフトレジスタ2 = Seen Boolean[16]
シフトレジスタ3 = error cluster
```

#### D. 各反復の既存エラー確認

1. error左内側の`status`をループ内ケースへ接続する。
2. TrueケースではLOGINFO、Seen、errorの左内側を各右内側へそのまま接続する。
3. FalseケースへMdlNo検証と書込処理を作る。

#### E. MdlNo範囲と重複判定

1. 自動指標付けされた1要素を名前でバンドル解除へ接続する。
2. `MdlNo`、`LogSize`、`BufferSize`を取り出す。
3. `MdlNo >= 0`と`MdlNo <= 15`を作る。
4. Seen左内側を指標配列の`array`へ、`MdlNo`を`index`へ接続する。
5. `Seen[MdlNo]`をNOTへ接続する。
6. 3条件をANDへ接続する。
7. AND出力を有効判定ケースへ接続する。

#### F. 有効Trueケース：書込位置を作る

1. 乗算へ`MdlNo`とI32定数`8`を接続する。
2. 乗算出力を`Base Offset`とする。
3. `Base Offset`のワイヤを2本へ分岐する。
4. 1個目の加算の一方へ`Base Offset`、もう一方へI32定数`8`を接続する。
5. 1個目加算出力を`Log Index`とする。
6. 2個目の加算の一方へ`Base Offset`、もう一方へI32定数`12`を接続する。
7. 2個目加算出力を`Buffer Index`とする。

```text
Base Offset  = MdlNo × 8
Log Index    = Base Offset + 8
Buffer Index = Base Offset + 12
```

#### G. LogSizeとBufferSizeをU8[4]へ変換

1. `I32_To_LE_U8x4.vi`を2個配置する。
2. `LogSize`を1個目の`I32_To_LE_U8x4.vi`の`Value`入力へ接続する。
3. `BufferSize`を2個目の`I32_To_LE_U8x4.vi`の`Value`入力へ接続する。
4. error左内側を1個目SubVIの`error in`へ接続する。
5. 1個目の`error out`を2個目の`error in`へ接続する。
6. 1個目の`Bytes`出力を`Log Bytes`とする。
7. 2個目の`Bytes`出力を`Buffer Bytes`とする。

#### H. 2個の値をLOGINFOへ直列書込

1. 部分配列置換 #1の`array`へ累積LOGINFO左内側を接続する。
2. #1の`index`へ`Log Index`を接続する。
3. #1の`new element/subarray`へ`Log Bytes`を接続する。
4. #1出力を`LogSize書込後LOGINFO`とする。
5. 部分配列置換 #2の`array`へ`LogSize書込後LOGINFO`を接続する。
6. #2の`index`へ`Buffer Index`を接続する。
7. #2の`new element/subarray`へ`Buffer Bytes`を接続する。
8. #2出力を`更新後LOGINFO`とする。

2個の部分配列置換は並列ではなく直列に接続する。

#### I. Seen配列を更新

1. Seen更新用部分配列置換の`array`へSeen左内側を接続する。
2. `index`へ`MdlNo`を接続する。
3. `new element/subarray`へBoolean定数Trueを接続する。
4. 出力を`更新後Seen`とする。

#### J. シフトレジスタへ戻す

1. `更新後LOGINFO`を1本目右内側へ接続する。
2. `更新後Seen`を2本目右内側へ接続する。
3. 2個目`I32_To_LE_U8x4.vi`の`error out`を3本目右内側へ接続する。

#### K. 無効Falseケース

1. 累積LOGINFO左内側を1本目右内側へ接続する。
2. Seen左内側を2本目右内側へ接続する。
3. 文字列にフォーマットへ次を設定する。

```text
Build_LOGINFO_Raw.vi: MdlNo must be 0..15 and must not be duplicated. MdlNo=%d
```

4. `%d`へMdlNoを接続する。
5. 名前でバンドルへerror左内側を基準クラスタとして接続する。
6. `status=True`、`code=-700112`、`source=生成文字列`を接続する。
7. 名前でバンドル出力を3本目右内側へ接続する。

#### L. ループ終了後

1. LOGINFO右外側を`LOGINFO Raw`へ接続する。
2. error右外側を`error out`へ接続する。
3. Seen右外側は本VIの出力にはしない。

### 4. 単体テスト

```text
LogDevice    = 1
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

推奨プローブ：Base Offset、Log Index、Buffer Index、Log Bytes、Buffer Bytes、部分配列置換 #2出力、LOGINFO右外側。

| 条件 | 期待結果 |
|---|---|
| MdlNo=1 | Log Index=16、Buffer Index=20 |
| MdlNo=16 | code=`-700112` |
| 同じMdlNoを2回指定 | code=`-700112` |
| 既存エラー | U8[136]ゼロ配列、既存エラー保持 |

---

# 10.11 Parser

## 10.11.1 `Parse_SYSINFO_Array.vi`

### 0. 目的と処理概要

U8[960]を60バイト×16レコードへ分け、各レコードの11個のI32、Name、Connected?を解析する。最初に見つけたRAMモジュール番号、CANモジュール番号、RAM Endianをシフトレジスタで保持する。

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

| 数 | 日本語名 | 英語名 | 配置場所・追加方法 |
|---:|---|---|---|
| 2 | 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 複数 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 1 | 配列サイズ | Array Size | プログラミング → 配列 |
| 複数 | 等しい? / 等しくない? / 以上? | Equal? / Not Equal? / Greater Or Equal? | プログラミング → 比較 |
| 1 | Forループ | For Loop | プログラミング → ストラクチャ |
| 4 | シフトレジスタ | Shift Register | Forループ枠を右クリック → 追加 |
| 1 | 乗算 | Multiply | プログラミング → 数値 |
| 12以上 | 部分配列 | Array Subset | プログラミング → 配列 |
| 11 | `U8x4_To_I32.vi` | SubVI | `30_RAMScope\00_Common` |
| 1 | 1D配列検索 | Search 1D Array | プログラミング → 配列 |
| 1 | バイト配列から文字列 | Byte Array To String | プログラミング → 文字列 |
| 1 | 名前でバンドル | Bundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 複数 | 複合演算 | Compound Arithmetic | プログラミング → ブール |
| 2 | 文字列にフォーマット / 名前でバンドル | Format Into String / Bundle By Name | プログラミング → 文字列 / クラスタ |

### 3. 配線順

#### A. 外側エラーガード

1. `error in.status`を外側ケースへ接続する。
2. Trueケースで空の`RAMScope_Module_Info.ctl`一次元配列を`Module List`へ接続する。
3. I32定数`-1`を`MdlNo_RAM`と`MdlNo_CAN`へ接続する。
4. I32定数`0`を`Endian_RAM`へ接続する。
5. Boolean定数Falseを2個のFound出力へ接続する。
6. 元の`error in`を`error out`へ接続する。

#### B. SYSINFOサイズ判定

1. 外側Falseで`SYSINFO Raw`を配列サイズへ接続する。
2. 配列サイズ出力とI32定数`960`を等しい?へ接続する。
3. 比較結果をサイズ判定ケースへ接続する。
4. サイズ不正FalseケースでAと同じ安全値を各出力へ接続する。
5. 次のsourceとcode=`-700120`を生成する。

```text
Parse_SYSINFO_Array.vi: SYSINFO Raw size must be 960. Actual=%d
```

#### C. Forループと4本のシフトレジスタ

1. サイズ正常TrueケースへForループを配置する。
2. N端子へI32定数`16`を接続する。
3. `SYSINFO Raw`をForループ左枠へ接続する。
4. 入力トンネルを右クリックし、`指標付けを無効（Disable Indexing）`にする。
5. ループ内でもSYSINFO RawがU8一次元配列のままであることを確認する。
6. シフトレジスタを4本追加する。
7. 1本目左外側へI32定数`-1`を接続し、MdlNo_RAM用とする。
8. 2本目左外側へI32定数`-1`を接続し、MdlNo_CAN用とする。
9. 3本目左外側へI32定数`0`を接続し、Endian_RAM用とする。
10. 4本目左外側へ正常なerror clusterを接続する。

#### D. 60バイトレコードを切り出す

1. 反復端子`i`を乗算の一方へ接続する。
2. I32定数`60`を乗算のもう一方へ接続する。
3. 乗算出力を`Record Start`とする。
4. 部分配列の`array`へ、指標付けを無効にしたSYSINFO Raw U8[960]を接続する。
5. `index`へ`Record Start`を接続する。
6. `length`へI32定数`60`を接続する。
7. 出力を`Record U8[60]`とする。

```text
i=0  → index 0～59
i=1  → index 60～119
...
i=15 → index 900～959
```

#### E. 既存エラー確認

1. error左内側の`status`をループ内ケースへ接続する。
2. Trueケースでは4本の左内側を各右内側へそのまま接続する。
3. TrueケースのModule Info出力へ空の`RAMScope_Module_Info.ctl`定数を接続する。
4. Falseケースへフィールド解析を作る。

#### F. 11個のI32フィールドを解析

| フィールド | Record内index | length |
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

1. 各フィールド用の部分配列へ`Record U8[60]`を接続する。
2. 表のindexとI32定数`4`を各部分配列へ接続する。
3. `U8x4_To_I32.vi`を11個配置する。
4. 各U8[4]を対応SubVIの`Bytes`へ接続する。
5. `Byte Order`を11個へ分岐して接続する。
6. error左内側をmodule変換SubVIの`error in`へ接続する。
7. moduleからflash_enableまでerror clusterを直列接続する。
8. 以降の判定には、部分配列のU8[4]ではなく各`U8x4_To_I32.vi`のI32 `Value`出力を使用する。

#### G. Nameを文字列へ変換

1. 部分配列へRecord、index=`44`、length=`16`を接続し、Name Bytesを作る。
2. Name Bytesを1D配列検索の`array`へ接続する。
3. U8定数`0`を検索要素へ接続する。
4. 検索結果indexをケースストラクチャへ接続する。
5. `-1`ケースではName Bytes全体をバイト配列から文字列へ接続する。
6. DefaultケースではName Bytesのindex=`0`、length=`検索結果`を部分配列で切り出す。
7. NULLより前のU8配列をバイト配列から文字列へ接続する。
8. 出力を`Name String`とする。

#### H. Module Infoクラスタを作る

1. `RAMScope_Module_Info.ctl`定数を名前でバンドルの基準クラスタへ接続する。
2. `Record Index`へ反復端子`i`を接続する。
3. 11個の変換済みI32を対応フィールドへ接続する。
4. `Name String`を`Name`へ接続する。
5. 等しくない?（Not Equal?）を配置する。
6. 変換済み`module_type` I32を一方の入力へ接続する。
7. I32定数`x0F`をもう一方へ接続する。
8. 比較結果のBooleanを`Connected?`へ接続する。
9. 名前でバンドル出力をForループ右枠へ接続し、出力の自動指標付けを有効にする。
10. ループ終了後、この配列を`Module List`へ接続する。

`Connected?`へBoolean定数Trueを直接接続しない。

#### I. RAMモジュール番号を保持

1. 等しい?へ変換済み`module_type` I32とI32定数`x00`を接続する。
2. 2個目の等しい?へMdlNo_RAMシフトレジスタ左内側とI32定数`-1`を接続する。
3. 2個のBooleanをANDへ接続する。
4. AND出力をRAM判定ケースへ接続する。
5. RAM判定Trueケースで、変換済み`module` I32をMdlNo_RAM右内側へ接続する。
6. 同じTrueケースで、変換済み`endian` I32をEndian_RAM右内側へ接続する。
7. RAM判定FalseケースでMdlNo_RAM左内側をMdlNo_RAM右内側へ接続する。
8. 同じFalseケースでEndian_RAM左内側をEndian_RAM右内側へ接続する。

Falseケースへ固定の`-1`や`0`を接続しない。前の反復で検出した現在値を保持する。

#### J. CANモジュール番号を保持

1. 等しい?へ変換済み`module_type` I32とI32定数`x02`を接続する。
2. 2個目の等しい?へMdlNo_CAN左内側とI32定数`-1`を接続する。
3. 2個のBooleanをANDへ接続する。
4. AND出力をCAN判定ケースへ接続する。
5. CAN判定Trueケースで変換済み`module` I32をMdlNo_CAN右内側へ接続する。
6. CAN判定FalseケースでMdlNo_CAN左内側をMdlNo_CAN右内側へ接続する。
7. flash_enable変換SubVIの`error out`をerror右内側へ接続する。

#### K. Forループ終了後

1. MdlNo_RAMシフトレジスタ右外側をI32表示器`MdlNo_RAM`へ接続する。
2. MdlNo_CAN右外側をI32表示器`MdlNo_CAN`へ接続する。
3. Endian_RAM右外側をI32表示器`Endian_RAM`へ接続する。
4. 通常の自動指標付け出力トンネルをMdlNo表示器へ接続しない。
5. `MdlNo_RAM >= 0`のBooleanを`RAM Module Found?`へ接続する。
6. `MdlNo_CAN >= 0`のBooleanを`CAN Module Found?`へ接続する。
7. error右外側を`error out`へ接続する。

### 4. 単体テスト

#### 4.1 テスト用VIを分離する

Parser本体へテスト値生成回路を埋め込まず、`40_PoC\Test_Parse_SYSINFO_Array.vi`を作成する。

```text
ダミーSYSINFO生成回路
  → Parse_SYSINFO_Array.vi
  → 出力表示器
```

#### 4.2 U8[960]の初期化

1. 配列初期化へU8定数`0`を`element`として接続する。
2. I32定数`960`を`dimension size`へ接続する。
3. 出力を`SYSINFO Test Raw` U8[960]とする。

#### 4.3 部分配列置換の共通配線

各部分配列置換を直列に接続する。

```text
array                = 直前の更新済みU8配列
index                = I32書込開始位置
new element/subarray = U8一次元配列
```

数値フィールドはU8[4]で書き込む。単体U8を接続しない。

#### 4.4 Record 0：RAM

元配列がゼロのため、module=0、module_type=0、endian=0は書込を省略できる。

Nameだけを設定する。

```text
index = 44
new element/subarray = x52 x41 x4D x30
```

ASCII：`RAM0`

#### 4.5 Record 1：CAN

```text
module=1
  index = 60
  U8[4] = x01 x00 x00 x00

module_type=2
  index = 64
  U8[4] = x02 x00 x00 x00

name="CAN0"
  index = 104
  U8[4] = x43 x41 x4E x30
```

index 64へmodule=1を重複して書き込まない。

#### 4.6 Record 2～15：未使用

**作業仮定**として、未使用レコードの`module_type`をI32 `x0F`へ設定する。

各位置へU8[4] `x0F x00 x00 x00`を書き込む。

| Record | module_type開始index |
|---:|---:|
| 2 | 124 |
| 3 | 184 |
| 4 | 244 |
| 5 | 304 |
| 6 | 364 |
| 7 | 424 |
| 8 | 484 |
| 9 | 544 |
| 10 | 604 |
| 11 | 664 |
| 12 | 724 |
| 13 | 784 |
| 14 | 844 |
| 15 | 904 |

未使用レコードをゼロのままにすると`module_type=x00`となり、Connected=TrueまたはRAM候補として扱われる可能性がある。

#### 4.7 Parserへ入力

1. 最後の部分配列置換出力を`Parse_SYSINFO_Array.vi`の`SYSINFO Raw`へ接続する。
2. `Byte Order=Little Endian`を接続する。
3. 正常なerror clusterを接続する。
4. Parserの全出力を表示器へ接続する。

期待出力：

```text
Array Size(Module List) = 16
MdlNo_RAM               = 0
MdlNo_CAN               = 1
Endian_RAM              = 0
RAM Module Found?       = True
CAN Module Found?       = True
Module List[0].Name     = RAM0
Module List[1].Name     = CAN0
Record 2～15 Connected? = False
error out               = 正常
```

異常テスト：

| 条件 | 期待結果 |
|---|---|
| SYSINFO Rawが959要素 | code=`-700120`、MdlNo=-1 |
| RAMレコードなし | RAM Found=False、Parser自体は正常 |
| 既存エラー | 安全値、既存エラー保持 |

推奨プローブ：Record Start、Record U8[60]、module_type変換値、RAM/CAN判定Boolean、各シフトレジスタ右外側。

## 10.11.2 `RAMScope_Parse_Buffer.vi`

### 0. 目的と処理概要

Raw BufferをDataNum個のパケットへ分割し、各チャンネルのU32値、Flag、Timestampを解析する。Channel ListのName、Address、Sign、Scale、Offset、Unitを解析結果へ付加する。

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

| 数 | 日本語名 | 英語名 | 配置場所・追加方法 |
|---:|---|---|---|
| 複数 | 名前でバンドル解除 / 名前でバンドル | Unbundle By Name / Bundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 複数 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 複数 | 配列サイズ | Array Size | プログラミング → 配列 |
| 複数 | 加算、減算、乗算 | Add, Subtract, Multiply | プログラミング → 数値 |
| 複数 | 以上?、等しい? | Greater Or Equal?, Equal? | プログラミング → 比較 |
| 複数 | 複合演算 | Compound Arithmetic | プログラミング → ブール |
| 2 | Forループ | For Loop | プログラミング → ストラクチャ |
| 2 | シフトレジスタ | Shift Register | 各Forループ枠を右クリック → 追加 |
| 複数 | 部分配列 | Array Subset | プログラミング → 配列 |
| 複数 | `U8x4_To_U32.vi` | SubVI | `30_RAMScope\00_Common` |
| 1 | `U8x8_To_U64.vi` | SubVI | `30_RAMScope\00_Common` |
| 1 | 型変換 | Type Cast | プログラミング → 数値 → データ操作 |
| 2 | 倍精度浮動小数点に変換 | To Double Precision Float | プログラミング → 数値 → 変換 |
| 1 | 選択 | Select | プログラミング → 比較 |

### 3. 配線順

#### A. 外側エラーガード

1. `error in.status`を外側ケースへ接続する。
2. Trueケースで空Packets、Parsed Count=0、Unused=0、元エラーを出力する。

#### B. サイズ計算と入力検証

1. `Channel List`を配列サイズへ接続し、`ChNum`を作る。
2. `ChNum × 4`へI32定数`12`を加え、`Packet Size`を作る。
3. `Packet Size × DataNum`を`Expected Byte Count`とする。
4. `Array Size(Raw Buffer)`を`Actual Byte Count`とする。
5. `Actual - Expected`を`Unused Byte Count`へ接続する。
6. `ChNum >= 1`と`DataNum >= 0`をANDへ接続する。
7. 不正ケースで空Packets、count=0、Unused=0、code=`-700130`を返す。
8. 正常ケースで`Actual >= Expected`を判定する。
9. Raw不足ケースで空Packets、count=0、code=`-700131`を返す。
10. Raw十分ケースで`DataNum == 0`を判定する。
11. DataNum=0では空Packets、count=0、計算済みUnused、正常errorを返す。
12. DataNum>0でパケット解析へ進む。

#### C. 外側Forループ：パケット

1. 外側Forループを配置し、N端子へ`DataNum`を接続する。
2. error用シフトレジスタを追加する。
3. 正常なerror clusterを左外側へ接続する。
4. 反復端子`i × Packet Size`を`Packet Start`とする。
5. error左内側のstatusをパケット処理ケースへ接続する。
6. Trueケースで空Packetクラスタと元errorを出力する。
7. Falseケースへチャンネル、Flag、Timestamp解析を作る。

#### D. 内側Forループ：チャンネル

1. 内側Forループを配置する。
2. `Channel List`を左枠へ接続し、自動指標付けを有効にする。
3. N端子は未配線にする。
4. error用シフトレジスタを追加し、外側error左内側を左外側へ接続する。
5. `Value Start = Packet Start + j × 4`を作る。
6. Raw Bufferの`Value Start`からlength=`4`を部分配列で切り出す。
7. U8[4]を`U8x4_To_U32.vi`へ接続する。
8. ChannelクラスタからName、Address、Sign、Scale、Offset、Unitを取り出す。
9. Raw U32をDBLへ変換し、符号なし値を作る。
10. Raw U32を型変換でI32として解釈し、DBLへ変換して符号あり値を作る。
11. `Sign == 0`を選択のselectorへ接続する。
12. True入力へ符号なしDBL、False入力へ符号ありDBLを接続する。
13. 選択出力を`Value`とする。
14. `Engineering Value = Value × Scale + Offset`を計算する。
15. `RAMScope_Channel_Value.ctl`を名前でバンドルし、全フィールドを接続する。
16. 内側Forループ右枠へ接続し、自動指標付けでChannel Values配列を作る。
17. 変換SubVIのerror outを内側error右内側へ接続する。

#### E. FlagとTimestamp

1. `Flag Start = Packet Start + 4 × ChNum`を作る。
2. Raw BufferからFlag Start、length=`4`を切り出す。
3. `U8x4_To_U32.vi`でFlagを変換する。
4. `Timestamp Start = Flag Start + 4`を作る。
5. Raw BufferからTimestamp Start、length=`8`を切り出す。
6. `U8x8_To_U64.vi`でTimestamp Rawを変換する。
7. **作業仮定**として`Timestamp Seconds = Timestamp Raw × 20e-9`を計算する。
8. Timestamp単位の正式定義入手後に倍率を再確認する。

#### F. Packetクラスタと出力

1. `RAMScope_Packet.ctl`定数を名前でバンドルへ接続する。
2. Packet Indexへ外側反復端子`i`を接続する。
3. Channel Values、Flag、Timestamp Raw、Timestamp Secondsを接続する。
4. Packetクラスタを外側Forループ右枠へ接続し、自動指標付けでPacketsを作る。
5. Timestamp変換のerror outを外側error右内側へ接続する。
6. ループ後のPacketsを本VIの`Packets`へ接続する。
7. `Array Size(Packets)`を`Parsed Packet Count`へ接続する。
8. error右外側を`error out`へ接続する。
9. 計算済みUnused Byte Countを出力へ接続する。

### 4. 単体テスト

`40_PoC\Test_RAMScope_Parse_Buffer.vi`でダミーRaw Bufferを生成する。

Channel Listを2要素にする。

```text
Channel 0: Name="Unsigned", Sign=0, Scale=1, Offset=0
Channel 1: Name="Signed",   Sign=1, Scale=1, Offset=0
```

Raw Buffer：

```text
x01 x00 x00 x00                    Channel 0 = 1
xFE xFF xFF xFF                    Channel 1 = -2
xA5 x00 x00 x00                    Flag = xA5
x32 x00 x00 x00 x00 x00 x00 x00  Timestamp Raw = 50
```

入力：

```text
DataNum    = 1
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

推奨プローブ：Packet Size、Expected/Actual Byte Count、Packet Start、Value Start、Flag Start、Timestamp Start、各変換SubVI出力。

---

# 10.12 公開API

全公開APIは末尾で`Error_To_TestStatus.vi`を1回呼び、`Status.ctl`、`TestError.ctl`、標準error clusterを出力する。

## 10.12.1 `RAMScope_Connect.vi`

### 0. 目的

DeviceInitを実行し、接続台数と機種コードを返す。

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `error in` | 入力 | error cluster |
| `UnitNum` | 出力 | I32 |
| `kind` | 出力 | I32 |
| `Status` | 出力 | `Status.ctl` |
| `TestError` | 出力 | `TestError.ctl` |
| `error out` | 出力 | error cluster |

### 2. SubVI

- `RS_DLL_GT150DeviceInit.vi`
- `Error_To_TestStatus.vi`

### 3. 配線順

1. `error in`をDeviceInitラッパへ接続する。
2. ラッパのUnitNum、kindを各出力へ接続する。
3. ラッパのerror outを`Error_To_TestStatus.vi`へ接続する。
4. 機器名文字列`RAMScope`を同SubVIへ接続する。
5. Status、TestError、error outを本VIへ接続する。

### 4. 単体テスト

未接続時と接続時のReturnCode、UnitNum、kind、Statusを記録する。

## 10.12.2 `RAMScope_Init.vi`

### 0. 目的

Unitを初期化し、SYSINFOを解析してRAM/CANモジュール番号とEndianを取得し、PGT設定を適用する。

### 1. 主な入出力

```text
入力 : UnitNo、Byte Order、error in
出力 : Module List、MdlNo_RAM、MdlNo_CAN、Endian_RAM、SlotErr[16]、Status、TestError、error out
```

### 2. SubVI

```text
RS_DLL_GT150AllInit.vi
RS_DLL_GT150GetSysInfo.vi
Parse_SYSINFO_Array.vi
RS_DLL_GT150PGT_SetMdlConfig.vi
Error_To_TestStatus.vi
```

### 3. 配線順

1. error clusterを上記SubVIへ順番に直列接続する。
2. GetSysInfoのSYSINFO RawをParserへ接続する。
3. Parserの全出力を本VIの出力へ接続する。
4. `RAM Module Found?`をケースストラクチャへ接続する。
5. Falseケースでcode=`-700140`を生成し、PGT設定を呼ばない。
6. TrueケースでPGT設定ラッパを呼ぶ。
7. SlotErr[16]を走査し、非ゼロがあればcode=`-700141`を生成する。
8. 最後のerror clusterを`Error_To_TestStatus.vi`へ接続する。

### 4. 単体テスト

- ダミーParserではMdlNo_RAM=0、MdlNo_CAN=1を確認する。
- 実機ではSYSINFO Raw、Module List、SlotErrをログ保存する。
- RAMモジュールなしでErrorとなることを確認する。

`RAMScope_Config.vi`は作成しない。PGT設定は本VIへ統合する。

## 10.12.3 `RAMScope_Set_Cond.vi`

### 0. 目的

測定条件、チャンネル条件、ログ条件をBuilderでU8配列へ変換し、3個の設定APIへ順番に渡す。

### 1. 主な入出力

```text
入力 : UnitNo、MdlNo_RAM、Meas Config、Channel List、LogDevice、LimitHddSize、Module Log Configs、error in
出力 : ChNum、Status、TestError、error out
```

### 2. SubVIと順序

```text
Build_MEASINFO_170_Raw.vi
  → RS_DLL_GT170SetMeasCond.vi
  → Build_CHINFO_170_Raw.vi
  → RS_DLL_GT170SetMeasCh.vi
  → Build_LOGINFO_Raw.vi
  → RS_DLL_GT150SetLoggingInfo.vi
  → Error_To_TestStatus.vi
```

### 3. 配線順

1. error clusterを全SubVIへ直列接続する。
2. Builder出力を対応するDLLラッパのU8配列入力へ接続する。
3. `Build_CHINFO_170_Raw.vi`のChNumをSetMeasChラッパと本VI出力へ接続する。
4. UnitNo、MdlNo_RAMを各ラッパへ接続する。
5. 最後のerror clusterをStatus変換へ接続する。

### 4. 単体テスト

DLLラッパを呼ぶ前に、MEASINFO=72、CHINFO=`24×ChNum`、LOGINFO=136をプローブで確認する。

## 10.12.4 `RAMScope_Log_Start.vi`

### 0. 目的

RAMScope計測を開始する。

### 1. 入出力

```text
入力 : UnitNo、error in
出力 : Status、TestError、error out
```

### 2. SubVI

- `RS_DLL_GT150MeasStart.vi`
- `Error_To_TestStatus.vi`

### 3. 配線順

UnitNoとerror inをラッパへ接続し、ラッパerror outをStatus変換へ接続する。

### 4. 単体テスト

Set_Cond前に呼んだ場合と、Set_Cond後に呼んだ場合のReturnCodeを記録する。

## 10.12.5 `RAMScope_Read.vi`

### 0. 目的

必要サイズのRaw Bufferを確保してGetBufferDataを呼び、取得したDataNum個をPacket配列へ解析する。

### 1. 主な入出力

```text
入力 : UnitNo、MdlNo_RAM、MaxDataNum、Channel List、Byte Order、error in
出力 : Raw Buffer、DataNum、LostDataNum、Packets、Parsed Packet Count、Unused Byte Count、Status、TestError、error out
```

### 2. 配置する関数・SubVI

- 配列サイズ（Array Size）
- 乗算（Multiply）と加算（Add）
- 配列初期化（Initialize Array）
- `RS_DLL_GT150GetBufferData.vi`
- `RAMScope_Parse_Buffer.vi`
- `Error_To_TestStatus.vi`

### 3. 配線順

1. `ChNum=Array Size(Channel List)`を作る。
2. `Packet Size=4×ChNum+12`を作る。
3. `Buffer Byte Size=Packet Size×MaxDataNum`を作る。
4. U8定数`0`とBuffer Byte Sizeを配列初期化へ接続する。
5. U8ゼロ配列をGetBufferDataラッパへ接続する。
6. ラッパのRaw Buffer、DataNum、LostDataNumを本VI出力へ接続する。
7. Raw Buffer、DataNum、Channel List、Byte Order、error outをParserへ接続する。
8. Parser出力を本VIへ接続する。
9. Parser error outをStatus変換へ接続する。

### 4. 単体テスト

- MaxDataNum=1で事前確保サイズがPacket Sizeと一致する。
- DataNum=0でも正常に空Packetsを返す。
- LostDataNumをログへ残す。
- Raw Buffer不足時にParserが`-700131`を返す。

## 10.12.6 `RAMScope_Release.vi`

### 0. 目的

ReleaseBufferDataの要否と呼出位置を実験するための独立公開API。

```text
RS_DLL_GT150ReleaseBufferData.vi
  → Error_To_TestStatus.vi
```

Read後、Stop後、未使用の3条件を比較し、正式仕様確認後に残すか廃止する。

## 10.12.7 `RAMScope_Log_Stop.vi`

```text
入力 : UnitNo、error in
処理 : RS_DLL_GT150MeasStop.vi
出力 : Status、TestError、error out
```

正常停止、未開始状態、二重停止を単体テストする。

## 10.12.8 `RAMScope_Close.vi`

### 0. 目的

前段エラーがあってもDeviceExitを試み、元エラーを失わず終了結果を記録する。

### 1. SubVI

- `RS_DLL_GT150DeviceExit.vi`
- エラーをマージ（Merge Errors）または同等の統合処理
- `Error_To_TestStatus.vi`

### 2. 配線順

1. 元の`error in`を保持する。
2. DeviceExitラッパへ正常なerror clusterを入力し、前段エラーに関係なく呼ぶ。
3. 元エラーとDeviceExitエラーをマージする。
4. 元エラーを優先し、元エラーがない場合だけDeviceExitエラーを返す。
5. 統合errorをStatus変換へ接続する。

### 3. 単体テスト

- 正常状態でCloseできる。
- 既存error inでもDeviceExitが呼ばれる。
- 二重Close時のReturnCodeを記録する。
- Close後に再Connectできる。

---

# 10.13 最小PoC

## 10.13.1 `PoC_RAMScope_Main.vi`

### 0. 目的

TestStandを使わず、公開APIの順序と実機動作を確認する。TestStand設定の問題とRAMScope実装の問題を混ぜない。

### 1. 入力

- UnitNo
- Byte Order
- Meas Config
- Channel List
- Module Log Configs
- MaxDataNum
- Wait Time

### 2. 実行順

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

### 3. 記録する値

```text
UnitNum / kind
MdlNo_RAM / MdlNo_CAN / Endian_RAM
SlotErr
MEASINFO / CHINFO / LOGINFOの配列サイズ
各API ReturnCode
Raw Buffer / DataNum / LostDataNum
Parsed Packet Count / Unused Byte Count
Packetsの先頭・末尾Timestamp
Close結果
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

TestStandから`RS_DLL_*`、Builder、Parserを直接呼ばない。

---

# 10.15 トラブルシュート

| 症状 | 主な原因 | 確認・対応 |
|---|---|---|
| エラー193 | x64/x86不一致 | x86ランタイム隔離、VC++2013 x64確認 |
| エラー126 | 依存DLL不足 | ベンダー相対配置を確認 |
| エラー127 | 関数名または無効Handle | Handle非ゼロ、関数名完全一致 |
| LabVIEWクラッシュ | CLFN引数型、配列サイズ | ヘッダとCLFNを再照合 |
| U8変換値が逆 | Byte Order | Little/Bigの数値結合順を確認 |
| 同じバイトが4回出る | 指標配列indexが全部0 | `0,1,2,3`を接続 |
| 16進入力が`x4E`等になる | 10進で78入力後に表示だけ変更 | 16進表示へ変更後に`78`を再入力 |
| 3要素試験にならない | 表示行数と実要素数を混同 | 要素を削除しArray Sizeで3を確認 |
| Channel ListをArray Sizeへ接続できない | ctl単体を置いている | 配列枠内へ`RAMScope_Channel.ctl`を配置 |
| CHINFOが2次元 | Build Arrayが通常モード | `入力を連結`を有効化 |
| シフトレジスタが見つからない | 関数パレットを探している | Forループ枠を右クリックして追加 |
| LOGINFOのLogSize/BufferSizeが反映されない | Replace Array Subsetが並列、右内側へ旧配列 | 2個を直列接続し最後の出力を右内側へ接続 |
| Log/Buffer indexが不明 | Base Offsetの説明不足 | `Base=MdlNo×8`、`Log=Base+8`、`Buffer=Base+12` |
| SYSINFO RawをArray Subsetへ接続できない | For入力の自動指標付けが有効 | 指標付けを無効にしU8[960]全体を渡す |
| Connected?へ何を接続するか不明 | 比較条件の省略 | `変換済みmodule_type I32 != I32 x0F`のBooleanを接続 |
| MdlNo表示器で配線エラー | I32配列をI32単体へ接続 | シフトレジスタ右外側を表示器へ接続 |
| RAM/CAN判定後に値が-1へ戻る | Falseケースで初期値を再接続 | 左内側の現在値を右内側へ渡す |
| module/endianの接続元が不明 | Raw U8[4]と変換値を混同 | `U8x4_To_I32.vi`のI32 Value出力を使用 |
| SYSINFOテストで全RecordがConnected | 未使用Recordがゼロ | Record 2～15のmodule_typeへx0Fを書込 |
| Nameが空 | Name Bytesの書込型がU8単体 | index 44/104へU8[4] ASCII配列を書込 |
| Buffer不足 | Buffer Byte Size計算 | `(4×ChNum+12)×MaxDataNum`を確認 |
| 値と変数名がずれる | Channel List順序不一致 | BuilderとParserへ同一配列を渡す |

---

# 10.16 未確定事項

- `0x30100001`のベンダー正式定義
- GT170接続時のDeviceInit正常値
- AllInit以降の実機通し動作
- `Size`、`Sign`、`Speed`コードの正式定義
- `Endian_RAM`コードとByte Orderの正式マッピング
- `module_type`コード`0x00 / 0x02 / 0x0F`のベンダー正式定義
- Timestamp単位の実機確定
- 既存RAMScopeコンフィグファイルの正式読込仕様
- `ReleaseBufferData`の必須性と呼出位置
- APIのスレッドセーフ性
- CANの最終方式

未確定事項は公開APIへ推測で固定しない。作業仮定として使う場合は、単体テスト用であることを明記する。

---

# 10.17 現在の作業チェックリスト

## 完了済み

- [x] x64 DLLロード
- [x] DeviceInit関数解決
- [x] x86版VC++2013ランタイム混在によるエラー193を解消
- [x] `RAMScope_Code_To_Error.vi`の4パターン試験
- [x] 薄いDLLラッパ12個を作成
- [x] `U8x4_To_U32.vi` Little Endian正常試験
- [x] `Build_CHINFO_170_Raw.vi` 1チャンネル正常試験
- [x] `Build_LOGINFO_Raw.vi` MdlNo=0正常試験
- [x] `Parse_SYSINFO_Array.vi`の基本配線を作成

## 次に確認

- [ ] `U8x4_To_U32.vi` Big Endian、3要素、既存エラー試験
- [ ] 残り数値変換VIの境界・異常試験
- [ ] `Build_MEASINFO_170_Raw.vi`単体試験
- [ ] `Build_CHINFO_170_Raw.vi` 2チャンネル・0要素・2049要素試験
- [ ] `Build_LOGINFO_Raw.vi` MdlNo=1、重複、範囲外試験
- [ ] `Test_Parse_SYSINFO_Array.vi`でU8[960]ダミーデータ生成
- [ ] `Parse_SYSINFO_Array.vi`正常・959要素・RAMなし試験
- [ ] `RAMScope_Parse_Buffer.vi`ダミーパケット試験
- [ ] 公開API 8個
- [ ] `PoC_RAMScope_Main.vi`

---

# 10.18 参照資料

- NI LabVIEWプログラミングリファレンス：配列サイズ（Array Size）
- NI LabVIEWプログラミングリファレンス：指標配列（Index Array）
- NI LabVIEWプログラミングリファレンス：部分配列（Array Subset）
- NI LabVIEWプログラミングリファレンス：部分配列置換（Replace Array Subset）
- NI LabVIEWプログラミングリファレンス：型変換（Type Cast）
- NI LabVIEWプログラミングリファレンス：Forループ（For Loop）
- NI LabVIEWプログラミングリファレンス：シフトレジスタ（Shift Register）
- [00A_LabVIEW実装資料の記述ルール.md](./00A_LabVIEW実装資料の記述ルール.md)
- `docs/reference/RAMScopeVP.h`
- `docs/reference/GTHard.h`
- `docs/reference/samp_simple.cpp`
