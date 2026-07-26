# 10. RAMScope GT170 実装・学習ガイド

**最終整理日：2026-07-26**

> 本章をRAMScope実装資料の唯一の正本とする。
>
> 本章は、LabVIEWで初めてVIを組む読者が、画面を再現するだけでなく、各VIの責務、データモデル、アルゴリズム、Case Structure、For Loop、Shift RegisterおよびCLFNを選ぶ理由を説明できる状態を目標とする。
>
> 本章は環境準備からctl、共通VI、薄いDLL Wrapper、公開API、TDMS保存VI、通信確認PoC、ロギングPoCまでを一つの作成順で説明する。既存VIのロギング対応も各VIの既存手順へ統合し、後段の修正付録を正本としない。
>
> NI標準関数の一般仕様とVersion基準は[00C](./00C_一次資料とバージョン基準.md)、RAMScope関数のシグネチャは配布DLL同梱`RAMScopeVP.h`とAPI仕様書を根拠とする。ctl 11個、Common／Builder／Parser 11個、Wrapper 18個、公開API 11個、TDMS VI 4個、PoC 2個の既決構成は変更しない。

---

## 10.1 本章の記述ルール

各VIは、原則として次の順序で説明する。

```text
0. 実現したい機能とVIの責務
1. 入力データの実体
2. 出力データモデル
3. 前提条件・異常条件
4. 処理アルゴリズム
5. LabVIEW構造の選定理由
6. フロントパネル入出力と接続元・接続先
7. 配置する関数およびSubVI
8. 配線順
9. 単体テスト
```

### 10.1.1 機能要求からLabVIEW構造へ翻訳する

```text
条件で処理を変える
  → 分岐が必要
  → Case Structure

同じ処理を複数要素へ適用する
  → 反復が必要
  → For Loop

前反復の値や累積結果を保持する
  → 状態保持が必要
  → Shift Register

U8配列の一部を読む
  → OffsetとLengthが必要
  → Array Subset

固定位置へ構造体データを書く
  → 書込Indexが必要
  → Replace Array Subset
```

「Caseを置く」「For Loopを置く」から説明を始めず、必要な分岐・反復・状態保持を先に示す。

### 10.1.2 ストラクチャを先に配置する

```text
1. Case Structure、For LoopまたはWhile Loopを配置する。
2. selector、N端子または停止条件を接続する。
3. 作業対象のCaseへ切り替える。
4. そのCaseまたはLoop内へ関数・SubVIを配置する。
5. 全Caseの全出力トンネルを接続する。
```

内部処理を説明したあとで、後付けのようにストラクチャを登場させない。

### 10.1.3 Case名は実際のTrue／Falseを先に書く

```text
Falseケース（Input Valid?=False：入力値不正）
Trueケース（Input Valid?=True：入力値正常）
Falseケース（Connected?=False：DeviceInit未成功）
Trueケース（Connected?=True：DeviceExitが必要）
```

`正常ケース`、`エラーケース`、`不足ケース`だけでは記載しない。selector式と具体的な評価例も直前に示す。

### 10.1.4 新しい関数を突然登場させない

初めて使用する関数またはSubVIは、次を必ず書く。

```text
日本語名（英語名）
配置場所またはQuick Drop名
採用理由
入力端子ごとの接続元
出力端子ごとの接続先
代替案を採用しない理由
```

`CaseまたはMerge Errors相当`のように実装方法を選択式で投げない。本章では採用方式を1つへ固定する。

### 10.1.5 error clusterを端子単位で説明する

ローカルエラー生成では、次をすべて記載する。

```text
Bundle By Nameの基準クラスタ
statusへ接続するBoolean
codeへ接続するI32
sourceの文字列全文
Format Into Stringのプレースホルダ順
Bundle出力を接続するCase出力トンネル
```

### 10.1.6 Caseのバイパス側でも全出力を作る

False側でSubVIを呼ばない場合でも、True側と同じ型の全出力を接続する。

例：Close CaseのFalseケースでは`RAMScope_Close.vi`を呼ばないが、`Error_To_TestStatus.vi`を使って`Status`、`TestError`、`error out`を生成し、Stateは入力をそのまま通す。

### 10.1.7 フロントパネル出力の生成元を明記する

各出力について、次を表で示す。

```text
PoC出力名
接続元となるVI名
接続元端子名
途中Caseを通るか
Caseの両側で何を接続するか
```

制御器と表示器、入力と出力、内部デバッグ表示器と公開出力を混同しない。

### 10.1.8 状態Booleanの更新元を明記する

`Connected?をTrueへ更新する`だけでは不足である。

```text
Connected?
= NOT(RAMScope_Connect.vi.error out.status)

Measurement Started?
= State.Connected? AND NOT(RAMScope_Log_Start.vi.error out.status)
```

状態クラスタの初期値、更新式、Bundle By Nameのクラスタ入力、更新後Stateの接続先まで示す。

### 10.1.9 薄いラッパVIを共通説明だけで省略しない

全Wrapperに次を個別記載する。

```text
Cプロトタイプ
CLFN Parametersの順番
Type / Data Type / Pass
Pointer左端子の初期値
Pointer右端子の出力
配列の事前確保サイズ
Function Name文字列
API ReturnCodeとerror outの接続
True／False両Caseの安全出力
単体テスト
```

---

## 10.2 現行ファイル構成

本章では既存ファイルとロギング追加ファイルを完成時の構成として同じ作成順へ並べる。通信確認用PoCとロギング用PoCは別VIとするが、作成手順は10.5の一本化フローを正本とする。

### 10.2.1 ctlファイル

| ファイル | 担当 |
|---|---|
| `Status.ctl` | TestStandの継続・中断判定 |
| `TestError.ctl` | 機器名、コード、メッセージ、時刻、致命判定 |
| `RAMScope_Byte_Order.ctl` | Big / Little Endian選択 |
| `RAMScope_Meas_Config.ctl` | MEASINFOへ変換する測定条件 |
| `RAMScope_Channel.ctl` | 1チャンネル分のRAM測定設定 |
| `RAMScope_Module_Log_Config.ctl` | 1モジュール分のログ容量設定 |
| `RAMScope_Module_Info.ctl` | SYSINFO 1レコードの解析結果 |
| `RAMScope_Channel_Value.ctl` | 1チャンネル分の解析値 |
| `RAMScope_Packet.ctl` | 1Packet分のChannel、Flag、Timestamp |
| `RAMScope_PoC_State.ctl` | 通信確認用PoCのConnect、Start、Stop、Release等の成功履歴 |
| `RAMScope_Logging_PoC_State.ctl` | ロギング専用PoCのFile Open、Start、Stop、保存ログ回収、Release等の成功履歴 |

### 10.2.2 共通変換・Builder・Parser VI

```text
RAMScope_Code_To_Error.vi
U8x4_To_U32.vi
U8x4_To_I32.vi
U8x8_To_U64.vi
U32_To_LE_U8x4.vi
I32_To_LE_U8x4.vi
Build_MEASINFO_170_Raw.vi
Build_CHINFO_170_Raw.vi
Build_LOGINFO_Raw.vi
Parse_SYSINFO_Array.vi
RAMScope_Parse_Buffer.vi
```

### 10.2.3 薄いDLLラッパVI

```text
RS_DLL_GT150DeviceInit.vi
RS_DLL_GT150DeviceExit.vi
RS_DLL_GT150AllInit.vi
RS_DLL_GT150GetSysInfo.vi
RS_DLL_GT150PGT_SetMdlConfig.vi
RS_DLL_GT170SetMeasCond.vi
RS_DLL_GT170SetMeasCh.vi
RS_DLL_GT150SetLoggingInfo.vi
RS_DLL_GT150MeasStart.vi
RS_DLL_GT150GetGapTime.vi
RS_DLL_GT150GetMeasNum.vi
RS_DLL_GT150GetBlockNum.vi
RS_DLL_GT150GetBufferDataNum.vi
RS_DLL_GT150GetBufferData.vi
RS_DLL_GT150GetLoggingDataNum.vi
RS_DLL_GT150GetLoggingData.vi
RS_DLL_GT150ReleaseBufferData.vi
RS_DLL_GT150MeasStop.vi
```

### 10.2.4 公開API

```text
RAMScope_Connect.vi
RAMScope_Init.vi
RAMScope_Set_Cond.vi
RAMScope_Log_Start.vi
RAMScope_Read.vi
RAMScope_Log_Stop.vi
RAMScope_Get_Log_Summary.vi
RAMScope_Get_Block_Count.vi
RAMScope_Read_Logging_Block.vi
RAMScope_Release.vi
RAMScope_Close.vi
```

### 10.2.5 LabVIEW側ファイル保存VI

```text
RAMScope_File_Log_Open.vi
RAMScope_File_Log_Write_Metadata.vi
RAMScope_File_Log_Append.vi
RAMScope_File_Log_Close.vi
```

これらはRAMScopeVP APIのDLL Wrapperではなく、LabVIEW側でTDMSを管理するVIである。機器側の`SetLoggingInfo`および保存用バッファと混同しない。

### 10.2.6 PoC・単体操作・TestStand

```text
PoC_RAMScope_Main.vi
PoC_RAMScope_Logging_Main.vi
```

`PoC_RAMScope_Main.vi`は既存の通信確認用PoCとして残す。DeviceInit、初期化、条件設定、測定開始、短時間の最新値取得、停止、Release、Closeまでの疎通を確認し、長時間TDMS保存および測定停止後の保存ログ回収は実装しない。

`PoC_RAMScope_Logging_Main.vi`はロギング専用PoCとして新規作成する。機器側保存バッファの測定、停止後のMeasNo／BlockNo列挙、全Block取得、Packet解析、TDMS追記、欠落情報保存、Cleanupを検証する。

TestStandは公開APIを呼び、MeasNoとBlockNoの反復、試験条件、レポートおよび全体Cleanupを管理する。TestStand専用のDLL Wrapperは追加しない。

---

## 10.3 レイヤ構成と責務

```text
TestStand、PoC_RAMScope_Main.vi または PoC_RAMScope_Logging_Main.vi
  ├─→ RAMScope_* 公開API
  │     → Builder / Parser / Common
  │         → RS_DLL_* 薄いラッパ
  │             → CLFN
  │                 → RAMScopeVP_API_x64.dll
  └─→ RAMScope_File_Log_* VI
          → LabVIEW TDMS API
              → .tdms
```

| レイヤ | 説明できるべき責務 |
|---|---|
| ctl | VI間で共有するデータの意味と型を固定する |
| Common | API ReturnCode、Endian、数値変換を一元化する |
| Builder | 意味付き設定をDLL用U8配列へ変換する |
| Parser | DLLのU8配列を意味付きクラスタへ変換する |
| 薄いラッパ | C関数1個をCLFNで1回呼ぶ |
| 公開API | 複数の下位VIを1つの機器操作へまとめる |
| PoC | TestStandなしで順序、状態、Cleanupを検証する |
| TestStand | 条件分岐、反復、レポート、全体Cleanupを管理する |

---

## 10.4 環境準備・DLL疎通確認

#### 10A.1 適用構成

| 項目 | 使用するもの |
|------|--------------|
| RAMScope | GT170 |
| 接続 | USB3.0 |
| LabVIEW | 64bit版 |
| PowerShell | 64bitプロセス |
| API | RAMScopeVP API 64bit版 |
| API DLL | `RAMScopeVP_API_x64.dll` |
| CLFN | Call Library Function Node |
| C/C++ランタイム | Visual C++ 2013 Redistributable x64 |

この章では最小疎通関数として次を使用する。

```c
long RAMScopeGT150DeviceInit(long *pUnitNum, long *kind);
```

GT170でも接続・初期化・終了の共通処理には`RAMScopeGT150*`関数を使用する。

---

### STEP 0：必要ソフトとファイルを準備する

#### 10A.2 必要ソフトウェア

- LabVIEW 64bit
- RAMScopeVP / RAMScopeVP API 64bit版
- RAMScope USBドライバ
- PGTツール
- Visual C++ 2013 Redistributable x64

Visual C++ 2015-2022 Redistributable x64は、別コンポーネントが要求する場合に導入する。ただし、Visual C++ 2013の代替ではない。

#### 10A.3 確認済みパス

```text
API DLL:
C:\DTSinsight\RAMScopeVP\app\RAMScopeVP_API(64bit)\RAMScopeVP_API_x64.dll

ヘッダ:
C:\DTSinsight\RAMScopeVP_API\header\RAMScopeVP.h
```

環境差がある場合は実際のインストール先へ読み替える。

#### 10A.4 ベンダー指定の相対配置

`RAMScopeVP_API_x64.dll`を起点として、関連ファイルの相対位置を維持する。

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

##### 配置ルール

- `UtilLCServer.exe`、`PGTMgrServer.exe`、`GT170_x64.dll`、`GT170USB_x64.dll`はAPI DLLと同じフォルダへ置く。
- `utillc.dll`は`UtilLCServer.exe`と同じフォルダへ置く。
- `PGTMgrVP.dll`、`PGTMgrVP_ENG.dll`は`PGTMgrServer.exe`と同じフォルダへ置く。
- PGTライブラリはAPI DLLフォルダ直下の`pgtlib`へ置く。
- 「64bitフォルダにあるx86ファイルをすべて削除する」という対応は禁止する。

---

#### 10A.5 Visual C++ 2013 Redistributable x64の役割

Visual C++ RedistributableはRAMScopeのUSBドライバではない。RAMScopeのDLLが内部で使用するMicrosoft C/C++共通ライブラリをWindowsへ提供する。

```text
LabVIEW 64bit
  → RAMScopeVP_API_x64.dll
    → Visual C++ 2013 x64ランタイム
```

今回問題になったファイル：

```text
mfc120jpn.dll
mfc120u.dll
msvcp120.dll
msvcr120.dll
```

`120`はVisual C++ 2013世代を表す。正しいx64版がWindowsから利用可能であることを確認する。

---

#### 10A.6 既知事象：CLFNが関数を認識しない

##### 現象

- CLFNでDLLを指定しても`RAMScopeGT150DeviceInit`を選択・認識できない。
- `GetProcAddress`で関数アドレスを取得できない。
- DLLロード時にエラー193が発生する。

```text
Error 193 (0xC1)
%1 は有効な Win32 アプリケーションではありません。
```

##### 確認結果

```text
DLL          : RAMScopeVP_API_x64.dll
Architecture : x64
Function     : RAMScopeGT150DeviceInit
Ordinal      : 14
```

DLL本体と関数は存在していた。一方、API DLLと同じフォルダにx86版の次のランタイムが混在していた。

```text
mfc120jpn.dll
mfc120u.dll
msvcp120.dll
msvcr120.dll
```

x64プロセスがローカルのx86 DLLを依存DLLとして読み込もうとし、エラー193になった可能性が高い。

##### 対策

1. Visual C++ 2013 Redistributable x64を利用可能にする。
2. 次の4ファイルがx86であり、64bit APIフォルダへ混在している場合だけ、復元可能なフォルダへ隔離する。

```text
mfc120jpn.dll
mfc120u.dll
msvcp120.dll
msvcr120.dll
```

移動先例：

```text
C:\DTSinsight\RAMScopeVP\app\RAMScopeVP_API(64bit)\_x86_runtime_backup
```

PowerShell例：

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

##### 移動してはいけないファイル

次はベンダー指定の配置を維持する。

```text
PGTMgrVP.dll
PGTMgrVP_ENG.dll
utillc.dll
pgtlib\*.dll
```

これらは32bitヘルパープロセスやPGT構成で使用される可能性がある。x86と表示されたことだけを理由に隔離しない。

---

### STEP 1：PowerShellでDLLと関数を確認する

#### 10A.7 疎通スクリプト

```powershell
powershell.exe -ExecutionPolicy Bypass `
  -File .\scripts\Test-RAMScopeDll.ps1 `
  -DllPath "C:\DTSinsight\RAMScopeVP\app\RAMScopeVP_API(64bit)\RAMScopeVP_API_x64.dll" `
  -ExportName "RAMScopeGT150DeviceInit" `
  -ExportOrdinal 14
```

##### 合格条件

```text
PowerShell 64-bit : True
Loaded module path: 指定したRAMScopeVP_API_x64.dll
Handle            : 0x0以外
Name Found        : True
Ordinal Found     : True
Name Address      : Ordinal Address
```

##### 重要な判定

- `Handle=0x0`は必ずロード失敗。
- 画面に「OK」と表示されてもハンドルが0なら成功扱いしない。
- 無効なハンドルで`GetProcAddress`を呼ぶとエラー127になり、関数が存在しないように見える。

##### 実測結果

対策後、次を確認済み。

```text
PowerShell 64-bit : True
Handle            : 非ゼロ
Name Found        : True
Ordinal Found     : True
Address           : 名前と序数で一致
```

---

### STEP 2：`RS_DLL_GT150DeviceInit.vi`でCLFN疎通を確認する

#### 10A.8 ヘッダ定義

```c
typedef long (*RAMScopeGT150DeviceInitPtr)(long *pUnitNum, long *kind);
```

実質的な関数：

```c
long RAMScopeGT150DeviceInit(long *pUnitNum, long *kind);
```

Windowsの`long`は32bitである。64bit DLLでもI64にはしない。

#### 10A.9 CLFN設定

| 項目 | 設定 |
|------|------|
| Library name or path | `RAMScopeVP_API_x64.dll`のフルパス |
| Function name | `RAMScopeGT150DeviceInit` |
| Calling Convention | C |
| Thread | Run in UI thread |
| Error checking | Maximum |
| 戻り値 | Numeric / Signed 32-bit Integer / Value |
| `pUnitNum` | Numeric / Signed 32-bit Integer / Pointer to Value |
| `kind` | Numeric / Signed 32-bit Integer / Pointer to Value |

表示プロトタイプ：

```c
int32_t RAMScopeGT150DeviceInit(
    int32_t *pUnitNum,
    int32_t *kind
);
```

#### 10A.10 最小配線

```text
error in ─────────────────────────────────────┐
                                               ▼
I32 0 → pUnitNum ─────────────────────────── CLFN ─→ UnitNum
I32 0 → kind ──────────────────────────────────┤  └→ kind
                                               └────→ API ReturnCode
error out ◀─────────────────────────────────────────
```

- `pUnitNum`と`kind`の入力側へI32の0を接続する。
- 右側端子からDLLが書き込んだ値を取得する。
- 標準`error in / error out`を配線する。
- この段階ではReturnCodeを表示し、関数呼び出しが成立することを優先する。

##### VI名

現行構成では、DeviceInitのCLFNは薄いラッパとして次の名称で保存する。

```text
RS_DLL_GT150DeviceInit.vi
```

公開APIの`RAMScope_Connect.vi`は、この薄いラッパを内部から呼ぶ。`RAMScope_Init.vi`はAllInit、GetSysInfo、ParserおよびPGT設定を担当する。

#### 10A.11 実機未接続PoC

実機を接続していない状態で次を観測した。

```text
DeviceInit completed
Return code : 806354945
Return hex  : 0x30100001
Unit count  : 0
Device kind : 0
```

ここから確定できること：

- DLLロード成功
- 関数解決成功
- 引数の型とポインタ渡しでクラッシュしない
- 関数の実呼び出し成功
- 接続デバイス数は0

`0x30100001`の正式定義は未確認である。実機未接続時の観測コードとして記録し、意味を断定しない。

---

#### 10A.12 トラブルシュート

| 症状 | 確認 | 対応 |
|------|------|------|
| エラー193 | x64/x86不一致、ローカルx86依存DLL | PowerShell/LabVIEW/DLLのbit数確認。対象4ファイルだけ隔離 |
| エラー126 | DLL本体または依存DLL不足 | ベンダー相対配置、VC++2013 x64、GT170 DLLを確認 |
| エラー127 | 関数名不一致、または無効ハンドル | 先にHandle非ゼロを確認。関数名を完全一致 |
| Handle `0x0` | DLLロード失敗 | Load errorを確認。GetProcAddress結果を評価しない |
| CLFN errorなし、ReturnCode異常 | API内部結果エラー | ReturnCodeを別経路で評価する |
| LabVIEWクラッシュ | 引数型、配列サイズ、ポインタ、関数設定 | ヘッダとCLFNを再照合。UI thread / Maximumで再試験 |
| UnitNum `0` | 機器未接続、電源、USBドライバ、排他使用 | 実機・デバイスマネージャー・純正アプリ終了を確認 |

---

#### 10A.13 本章の完了条件

- [x] x64 PowerShellでDLLをロードできる
- [x] DLL Handleが非ゼロ
- [x] `RAMScopeGT150DeviceInit`を名前で取得できる
- [x] 序数14でも取得できる
- [x] 名前と序数のアドレスが一致する
- [x] PowerShellから関数を実呼び出しできる
- [x] LabVIEWのCLFNプロトタイプが確定している
- [x] `RS_DLL_GT150DeviceInit.vi`の最小配線ができている
- [x] 実機未接続時でもクラッシュせずReturnCodeを返す

次に 本章内の該当節 で、エラー変換の共通化と後続VIを作成する。

---

## 10.5 一本化した作成順・確定仕様・監査結果

### 10.5.1 一本化方針

本章では「通信確認用の既存手順」と「ロギング対応の修正手順」を分けない。各ファイルは、最初からロギング対応を含む最終形で作成または修正する。

```text
環境確認
  → ctlを最終形で作成
  → 共通変換・Builder・Parserを作成
  → 薄いDLL WrapperをAPI呼出順で作成
  → 公開APIを機器操作順で作成
  → TDMS保存VIを作成
  → 通信確認PoCを回帰確認
  → ロギングPoCを作成
  → 結合試験・TestStand組込み
```

- `RAMScope_Packet.ctl`は、後からFlag項目を追加するのではなく、10.6の最終フィールドで作成する。
- `RAMScope_Parse_Buffer.vi`と`RAMScope_Read.vi`は、旧版を作成してからロギング用に直すのではなく、10.10と10.11の最終アルゴリズムで作成する。
- 追加Wrapperと追加公開APIは別付録へ置かず、既存ファイルと同じレイヤの作成順へ組み込む。
- `PoC_RAMScope_Main.vi`は通信確認用として残し、`PoC_RAMScope_Logging_Main.vi`は別VIとして作る。

### 10.5.2 完成までの一連の作成順

#### Phase 0：環境とCLFN疎通

1. 10.4に従って64bit環境、DLL配置、依存DLL、DeviceInitのCLFN疎通を確認する。
2. `RAMScope_Code_To_Error.vi`を作り、以降のWrapperで共通使用する。

#### Phase 1：ctlを最終形で作成

3. `RAMScope_Byte_Order.ctl`
4. `RAMScope_Meas_Config.ctl`
5. `RAMScope_Channel.ctl`
6. `RAMScope_Module_Log_Config.ctl`
7. `RAMScope_Module_Info.ctl`
8. `RAMScope_Channel_Value.ctl`
9. `RAMScope_Packet.ctl`。Flag Raw、Status、Skip、Log Trigger、Dummy、Event Bits、Data Lost、Timestampを最初から含める。
10. `RAMScope_PoC_State.ctl`
11. `RAMScope_Logging_PoC_State.ctl`

#### Phase 2：共通変換・Builder・Parser

12. `U8x4_To_U32.vi`、`U8x4_To_I32.vi`、`U8x8_To_U64.vi`
13. `U32_To_LE_U8x4.vi`、`I32_To_LE_U8x4.vi`
14. `Build_MEASINFO_170_Raw.vi`、`Build_CHINFO_170_Raw.vi`、`Build_LOGINFO_Raw.vi`
15. `Parse_SYSINFO_Array.vi`
16. `RAMScope_Parse_Buffer.vi`を10.10の最終仕様で作成する。Size別復号、Flag分解、I64サイズ検証を含める。

#### Phase 3：薄いDLL WrapperをAPI呼出順で作成

17. 接続・初期化：`DeviceInit`、`AllInit`、`GetSysInfo`、`PGT_SetMdlConfig`
18. 条件設定：`SetMeasCond`、`SetMeasCh`、`SetLoggingInfo`
19. 測定開始・オンライン読出し：`MeasStart`、`GetBufferDataNum`、`GetBufferData`
20. 停止後ログ列挙：`MeasStop`、`GetGapTime`、`GetMeasNum`、`GetBlockNum`
21. 保存ログ読出し：`GetLoggingDataNum`、`GetLoggingData`
22. 後処理：`ReleaseBufferData`、`DeviceExit`

全WrapperはC関数1個をCLFNで1回だけ呼ぶ。通常Wrapperは既存error時にDLLを呼ばず、安全値と元errorを返す。

#### Phase 4：公開APIを機器操作順で作成

23. `RAMScope_Connect.vi`
24. `RAMScope_Init.vi`
25. `RAMScope_Set_Cond.vi`
26. `RAMScope_Log_Start.vi`
27. `RAMScope_Read.vi`
28. `RAMScope_Log_Stop.vi`
29. `RAMScope_Get_Log_Summary.vi`
30. `RAMScope_Get_Block_Count.vi`
31. `RAMScope_Read_Logging_Block.vi`
32. `RAMScope_Release.vi`
33. `RAMScope_Close.vi`

#### Phase 5：TDMSとPoC

34. `RAMScope_File_Log_Open.vi`
35. `RAMScope_File_Log_Write_Metadata.vi`
36. `RAMScope_File_Log_Append.vi`
37. `RAMScope_File_Log_Close.vi`
38. 既存`PoC_RAMScope_Main.vi`で通信・オンライン読出しの回帰確認を行う。
39. `PoC_RAMScope_Logging_Main.vi`を作成し、Stop後のMeasNo／BlockNo列挙、1Block単位のRead→Parse→Append、Cleanupを確認する。
40. TestStand組込み、TDMS再読込、MF4変換前提のメタデータ確認を行う。

### 10.5.3 ロギング対応で確定したAPI・Packet仕様

#### 10.5.3.1 保存ログ取得API

```c
long RAMScopeGT150GetGapTime(
    long UnitNo,
    unsigned long *pGapTime
);

long RAMScopeGT150GetMeasNum(
    long UnitNo,
    long *pMeasNum
);

long RAMScopeGT150GetBlockNum(
    long UnitNo,
    long MeasNo,
    long *pBlockNum
);

long RAMScopeGT150GetBufferDataNum(
    long UnitNo,
    long MdlNo,
    long *pDataNum
);

long RAMScopeGT150GetBufferData(
    long UnitNo,
    long MdlNo,
    void *pData,
    long *pDataNum,
    long *pLostDataNum
);

long RAMScopeGT150GetLoggingDataNum(
    long UnitNo,
    long MdlNo,
    long MeasNo,
    long BlockNo,
    long *pDataNum
);

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

`GetBufferData()`と`GetLoggingData()`の`pDataNum`は入出力である。

```text
呼出し前のpDataNum
  = 要求Packet数

正常終了後のpDataNum
  = 実際に読み出したPacket数
```

独立した`MaxDataNum`引数は存在しない。CLFNに存在しない引数を追加しない。

#### 10.5.3.2 RAMモニタPacket

```text
Packet[k]
├─ Data[0]      4byte
├─ Data[1]      4byte
├─ ...
├─ Data[N-1]    4byte
├─ Flag         4byte
└─ Time         8byte
```

```text
Packet Size = N × 4 + 12 byte
```

- `N`は測定有効チャンネル数。
- Dataの順番は`RAMScopeGT1x0SetMeasCh()`へ設定した順番。
- 設定データサイズが1byte、2byte、4byteのいずれでも、Packet内では1チャンネル4byte固定。
- Timeは測定開始を0とする64bitカウンタで、1countは20ns。

```text
Timestamp Seconds = Time Raw U64 × 20e-9
```

#### 10.5.3.3 RAMモニタFlag

| フィールド | bit | 抽出式 |
|---|---:|---|
| Status | 0～7 | `Flag Raw AND 0x000000FF` |
| Skip | 8 | `((Flag Raw >> 8) AND 1) != 0` |
| Log Trigger | 10～11 | `(Flag Raw >> 10) AND 3` |
| Dummy | 12 | `((Flag Raw >> 12) AND 1) != 0` |
| Event Bits | 16～23 | `(Flag Raw >> 16) AND 0xFF` |
| Data Lost | 28 | `((Flag Raw >> 28) AND 1) != 0` |

Statusコードは次の意味で保存する。

| Status | 意味 |
|---:|---|
| `0x00` | 正常動作 |
| `0xFF` | バスエラー、デバッグIF通信異常 |
| `0xFE` | オフライン、ターゲットマイコン電源検出NG |
| `0xFA` | セキュリティIDエラー、デバッグIF通信異常 |
| `0xF9` | リンクエラー |
| `0xF8` | パラメータ未設定エラー |
| その他 | 予約値。意味未定義のためRawコードを保持する |

Log Triggerは次の値を持つ。

| Log Trigger | 意味 |
|---:|---|
| `0` | 開始、センター、終了のいずれでもない |
| `1` | 測定データBlockの開始位置 |
| `2` | ポイント指定時のセンター位置、基準トリガ成立Packet |
| `3` | 測定データBlockの終了位置 |

各Boolean／bit fieldの意味は次のとおり。

- `Skip?=True`：このPacketより前に、測定周期、チャンネル数、メモリ操作負荷などの競合で収録タイミングをスキップした周期がある。
- `Dummy?=True`：通常の測定値Packetではなく、RAMScopeハードウェアが情報通知目的で生成したDummy Packetである。Packet自体は保存するが、Dataを通常測定値として自動判定に使用しない。
- `Event Bits`：bit0からbit7がイベントe1からe8に対応する。
- `Data Lost?=True`：このPacket以前にRAMScopeハードウェアとホストPC間でデータ欠落が発生した。

予約bitは値不定のため、0であることを正常条件にしない。

`Skip`、`Data Lost`、`Status != 0`は測定Packet内の状態情報であり、Parser自身の配列エラーとは分ける。該当Packetを捨てず、Raw値と解析結果をTDMSへ保存する。`pLostDataNum`はAPIが返す破棄Packet数として別項目で保存し、Flagの`Data Lost?`と統合しない。

---


### 10.5.4 監査結果と既存仕様

本書は、RAMScopeページに掲載されていた全VIについて、本章内の該当節と本章内の該当節への適合状況を監査し、統合時に省略された作成手順と、ベンダー資料で確定した仕様を補正する。

各詳細ページは統合前に存在した個別手順を復元したものである。日付が古い記述と本書が競合する場合は、本書を優先する。

---

#### 1. 監査で見つかった問題

##### 1.1 DLL Wrapperの個別手順が共通説明へ圧縮されていた

監査前の第10章では、12個のWrapperに共通するCase StructureとCLFN設定は記載されていたが、次の情報が各VIの節から消えていた。

- Cプロトタイプ。
- Parametersタブの引数順。
- `Value`、`Pointer to Value`、`Array Data Pointer`の区別。
- Pointer左端子へ入れる初期値。
- Pointer右端子から受け取る出力。
- U8[960]、I32[16]、測定Raw Buffer等の事前確保。
- `Function Name`へ接続する文字列定数。
- 既存エラーCaseで返す各出力。
- 各Wrapper固有の単体テスト。

[10.8 薄いDLLラッパVI 18個](#108-薄いdllラッパvi-18個)へ、18個それぞれの手順を統合した。共通節はテンプレートとして利用してよいが、個別節を削除してはならない。

##### 1.2 Public APIの配線順が設計メモの粒度だった

次のような記述はVI作成手順として不十分である。

```text
Falseケースでcode=-700140を生成する。
TrueケースでPGT設定ラッパを呼ぶ。
SlotErrを走査し、非ゼロがあればcode=-700141を生成する。
```

これではCaseをどこへ配置するか、Bundle By Nameの基準クラスタ、status、source、Format String、出力トンネルが分からない。[10.11 公開API 11個](#1011-公開api-11個)で、11個すべてを端子単位へ補正した。

##### 1.3 ParserとBuilderに「なぜその構造か」の説明が不足していた

配置・配線は存在していても、次の翻訳過程が不足していた。

```text
欲しい機能
  → 入力データの実体
  → 出力データモデル
  → 前提条件
  → 擬似コード
  → 分岐・反復・保持の必要性
  → Case / For / Shift Register
```

BuilderとParserの詳細ページでは、データの見取り図、反復単位、Offset式、Shift Registerで保持する値を先に説明する。

---

#### 2. 全VI監査一覧

| 区分 | VI | 個別手順 | 主な監査ポイント |
|---|---|---|---|
| Common | `RAMScope_Code_To_Error.vi` | 01 | CLFNエラー優先、ReturnCode分岐、Format String、Bundle By Name |
| Wrapper | `RS_DLL_GT150DeviceInit.vi` | 02 | `pUnitNum`、`kind`のPointer左右端子 |
| Wrapper | `RS_DLL_GT150DeviceExit.vi` | 02 | 前段エラー時も呼ぶCleanup専用経路 |
| Wrapper | `RS_DLL_GT150AllInit.vi` | 02 | UnitNo Value、Function Name |
| Wrapper | `RS_DLL_GT150GetSysInfo.vi` | 02 | U8[960]事前確保、Array Data Pointer |
| Wrapper | `RS_DLL_GT150PGT_SetMdlConfig.vi` | 02 | I32[16] SlotErr事前確保 |
| Wrapper | `RS_DLL_GT170SetMeasCond.vi` | 02 | U8[72]、UnitNo/MdlNo、サイズ前提 |
| Wrapper | `RS_DLL_GT170SetMeasCh.vi` | 02 | ChNum、U8[24×ChNum]、サイズ前提 |
| Wrapper | `RS_DLL_GT150SetLoggingInfo.vi` | 02 | U8[136]、機器側ロギング設定 |
| Wrapper | `RS_DLL_GT150MeasStart.vi` | 02 | UnitNoのみ、MdlNoを接続しない |
| Wrapper | `RS_DLL_GT150GetBufferData.vi` | 02 | Raw事前確保、pDataNum入出力、LostDataNum |
| Wrapper | `RS_DLL_GT150ReleaseBufferData.vi` | 02 | アイドル時のみ、Stop成功後 |
| Wrapper | `RS_DLL_GT150MeasStop.vi` | 02 | UnitNoのみ、Cleanup呼出可否 |
| Conversion | `U8x4_To_U32.vi` | 03 | 4byte検証、Endian、-700101全文 |
| Conversion | `U8x4_To_I32.vi` | 03 | ビット列を保ったType Cast |
| Conversion | `U8x8_To_U64.vi` | 03 | 8byte検証、上下U32結合、-700102全文 |
| Conversion | `U32_To_LE_U8x4.vi` | 03 | Split Numberとb0..b3順 |
| Conversion | `I32_To_LE_U8x4.vi` | 03 | I32→U32 Type Cast後の変換 |
| Builder | `Build_MEASINFO_170_Raw.vi` | 03 | 72byteモデル、書込index 0/4/8 |
| Builder | `Build_CHINFO_170_Raw.vi` | 03 | 24byte×ChNum、コード・Address検証、累積配列 |
| Builder | `Build_LOGINFO_Raw.vi` | 03 | 136byte、Base Offset、重複検出 |
| Parser | `Parse_SYSINFO_Array.vi` | 04 | 60byte×16、全体配列、検出値保持 |
| Parser | `RAMScope_Parse_Buffer.vi` | 04 | Packet/Channel二重反復、多段ガード、条件付き指標付け |
| Public | `RAMScope_Connect.vi` | 05 | DeviceInitとStatus変換の全端子 |
| Public | `RAMScope_Init.vi` | 05 | Parserエラー、RAM未検出、SlotErrの3段階 |
| Public | `RAMScope_Set_Cond.vi` | 05 | Builderサイズ検証後に3 APIを直列実行 |
| Public | `RAMScope_Log_Start.vi` | 05 | Start前提、Status変換 |
| Public | `RAMScope_Read.vi` | 05 | Buffer Byte Size算出、取得、Parser |
| Public | `RAMScope_Release.vi` | 05 | Stop成功・アイドル状態でのみ呼ぶ |
| Public | `RAMScope_Log_Stop.vi` | 05 | MeasStop結果を保持 |
| Public | `RAMScope_Close.vi` | 05 | 元エラーを保持しDeviceExitを必ず試す |
| PoC | `PoC_RAMScope_Main.vi` | 06 | 状態Boolean、正常/異常Cleanup、記録項目 |

---

#### 3. Case Structureの表記と作業順

意味名だけの`正常ケース`、`異常ケース`は禁止する。

```text
Trueケース（error in.status=True：既存エラーあり）
Falseケース（error in.status=False：既存エラーなし）
Falseケース（Input Valid?=False：入力値不正）
Trueケース（Input Valid?=True：入力値正常）
Falseケース（Raw Buffer Sufficient?=False：Raw Buffer不足）
Trueケース（Raw Buffer Sufficient?=True：Raw Buffer十分）
```

内部処理より先にストラクチャを作る。

```text
1. Case StructureまたはFor Loopを配置する。
2. selectorまたはN端子を接続する。
3. 作業対象のTrue／Falseケースへ切り替える。
4. そのケース内へ関数とSubVIを配置する。
5. 全Caseの出力トンネルを配線する。
```

---

#### 4. error cluster生成の必須記述

ローカルエラーは名前でバンドル（Bundle By Name）で生成する。

```text
基準クラスタ ← 対象Caseへ入ってきた正常なerror cluster
status       ← Boolean True
code         ← I32ローカルエラーコード
source       ← Format Into String出力
```

資料には次を全部書く。

1. Format String全文。
2. `%d`、`%s`、`%X`等の数と順番。
3. 各入力値の接続元と型。
4. Bundle By Nameの基準クラスタ。
5. status、code、sourceの値。
6. Bundle出力を接続するCase出力トンネル。
7. 単体テスト時の期待source。

---

#### 5. 現行ローカルエラーコード

| code | VI | sourceの意味 |
|---:|---|---|
| `-700101` | `U8x4_To_U32.vi` | 入力が4byteではない |
| `-700102` | `U8x8_To_U64.vi` | 入力が8byteではない |
| `-700111` | `Build_CHINFO_170_Raw.vi` | ChNumが1..2048外 |
| `-700112` | `Build_CHINFO_170_Raw.vi` | Size、Sign、Core、SpeedまたはAddress境界が不正 |
| `-700113` | `Build_LOGINFO_Raw.vi` | MdlNoが0..15外 |
| `-700114` | `Build_LOGINFO_Raw.vi` | MdlNo重複 |
| `-700120` | `Parse_SYSINFO_Array.vi` | SYSINFO Rawが960byteではない |
| `-700140` | `RAMScope_Init.vi` | RAMモジュール未検出 |
| `-700141` | `RAMScope_Init.vi` | PGT SlotErr非ゼロ |
| `-700150` | `RAMScope_Set_Cond.vi` | Builder出力サイズ不正 |
| `-700160` | `RAMScope_Parse_Buffer.vi` | Channel Sizeが0、1、2以外 |
| `-700161` | `RAMScope_Parse_Buffer.vi` | ChNum、DataNumまたはRaw Buffer長が不正 |
| `-700162` | `RAMScope_Read.vi` | AvailableDataNumが負数 |
| `-700163` | `RAMScope_Read.vi` | 必要Bufferサイズが不正または上限超過 |
| `-700164` | `RAMScope_Read.vi` | DataNumが要求範囲外 |
| `-700165` | `RAMScope_Read.vi` | Parsed Packet CountとDataNumが不一致 |
| `-700170` | `RAMScope_Get_Log_Summary.vi` | MeasNumが負数 |
| `-700171` | `RAMScope_Get_Block_Count.vi` | MeasNoが負数 |
| `-700172` | `RAMScope_Get_Block_Count.vi` | BlockNumが負数 |
| `-700173`～`-700177` | `RAMScope_Read_Logging_Block.vi` | 入力、件数、Bufferサイズ、Parser整合性が不正 |
| `-700178` | `RAMScope_File_Log_Open.vi` | 既存ファイル上書き禁止 |
| `-700180` | `RAMScope_File_Log_Append.vi` | Packet件数とDataNumが不一致 |

---

#### 6. ベンダー資料で確定した補正

##### 6.1 CHINFO_RAM170

```text
offset  0 : enable   U32
       4 : core     U32
       8 : address  U32
      12 : size     U32
      16 : sign     U32
      20 : speed    U32
```

```text
enable : 0=無効、1=有効
core   : 現在0
size   : 0=1byte、1=2byte、2=4byte
sign   : 0=unsigned、1=signed
speed  : 現在0
```

Address条件：

```text
size=0 → 任意Address
size=1 → Address mod 2 = 0
size=2 → Address mod 4 = 0
```

旧テスト値の`Size=4`や`Speed=2`はバイト配置確認用の識別値であり、実機設定値として使用しない。実機設定テストでは正式コードを使う。

##### 6.2 SYSINFO

```text
endian=0 → Big Endian
endian=1 → Little Endian
```

```text
module_type=0x00 → RAM
module_type=0x02 → CAN
module_type=0x03 → Analog
module_type=0x0E → Power Communication
module_type=0x0F → Disconnected
```

##### 6.3 測定Packet

```text
Channel Data : 4byte × ChNum
Flag         : 4byte
Timestamp    : 8byte
Packet Size  : 4 × ChNum + 12
```

Timestampは測定開始時0、20nsごとに1 count増加する。

```text
Timestamp Seconds = DBL(Timestamp Raw) × 20e-9
```

##### 6.4 PGT設定とRelease

- 非推奨の`RAMScopeGT150SetMdlConfig`ではなく`RAMScopeGT150PGT_SetMdlConfig`を使用する。
- `ReleaseBufferData`はオフラインおよび測定中に呼ばない。
- 正常順序は`MeasStop → Idle → ReleaseBufferData → DeviceExit`である。

---

#### 7. 単体テストの監査ルール

各VIには、少なくとも次のうち該当するテストを持たせる。

- 正常値。
- 境界値。
- 不足配列、0要素、範囲外。
- 既存`error in.status=True`。
- 配線順を識別できる異なる値。
- Array Size、ReturnCode、error code、source。
- 推奨プローブ位置。

フロントパネルで見えているセル数を実要素数として扱わない。配列サイズ（Array Size）で確認する。

---

## 10.6 ctlファイル・共通データモデル

詳細な関数配置と端子配線は本章内の該当節を参照する。本書は00A・00B監査後の設計理由と、ベンダー資料で確定したコードを補正する。

---

#### 1. なぜBuilderと数値変換VIが必要か

LabVIEW上の設定はクラスタやI32/U32で保持するが、DLLはC構造体へのPointerを要求する。Builderは意味付き設定をC構造体と同じバイト配置のU8一次元配列へ変換する。

```text
LabVIEW設定クラスタ
  → 各数値を4byte Little Endianへ変換
  → 構造体offsetへ書込
  → DLLへ渡すU8配列
```

同じ4byte変換を各Builderへ複製すると、Endianと符号の修正が複数箇所へ散る。そのため変換VIへ分離する。

---

#### 2. 個別VI一覧

| VI | 責務 | 必要な構造 |
|---|---|---|
| `U32_To_LE_U8x4.vi` | U32をb0,b1,b2,b3へ分解 | 既存error Case、Split Number、Build Array |
| `I32_To_LE_U8x4.vi` | I32のビット列を保ってU32経由で変換 | Type Cast、`U32_To_LE_U8x4.vi` |
| `Build_MEASINFO_170_Raw.vi` | 72byte MEASINFOを生成 | error Case、U8[72]初期化、offset 0/4/8へ書込 |
| `Build_CHINFO_170_Raw.vi` | 24byte×ChNumのCHINFO配列を生成 | 入力検証Case、For、配列とerrorのShift Register |
| `Build_LOGINFO_Raw.vi` | 136byte LOGINFOを生成 | For、更新配列・Seen・errorのShift Register |

Parser側で使用する`U8x4_To_U32.vi`、`U8x4_To_I32.vi`、`U8x8_To_U64.vi`は[10.10 Parser](#1010-parser)を参照する。

---

#### 3. `Build_CHINFO_170_Raw.vi`の現行補正

##### 3.1 入力データと出力モデル

`Channel List`は`RAMScope_Channel.ctl`の一次元配列で、1要素が1チャンネルである。出力は次の24byteレコードをChNum個連結したU8配列である。

```text
offset  0 : enable  U32
       4 : core    U32
       8 : address U32
      12 : size    U32
      16 : sign    U32
      20 : speed   U32
```

##### 3.2 正式コード

```text
enable : 0 / 1
core   : 0
size   : 0=1byte、1=2byte、2=4byte
sign   : 0=unsigned、1=signed
speed  : 0
```

```text
size=0 → Address任意
size=1 → Address mod 2 = 0
size=2 → Address mod 4 = 0
```

##### 3.3 アルゴリズム

```text
ChNum = Array Size(Channel List)
if ChNum < 1 or ChNum > 2048:
    -700111
else:
    U8[24×ChNum]を0初期化
    for each Channel:
        コードとAddress境界を検証
        6個のU32を各4byteへ変換
        Write Index = Channel Index × 24
        累積配列へ書込
```

Forループは同じ24byte変換を全チャンネルへ適用するために必要である。配列Shift Registerは前反復までに書き込んだU8配列を保持する。error Shift Registerは最初の変換エラーを後続反復で上書きしないために必要である。

##### 3.4 エラー全文

ChNum不正：

```text
Build_CHINFO_170_Raw.vi: Channel count must be 1..2048. ChNum=%d
```

```text
%d ← ChNum I32
status=True
code=I32 -700111
source=Format Into String出力
基準クラスタ=対象Caseへ入った正常error
```

チャンネル設定不正：

```text
Build_CHINFO_170_Raw.vi: Channel setting is invalid. ChannelIndex=%d, Size=%d, Sign=%d, Core=%d, Speed=%d, Address=%u
```

```text
1: Channel Index I32
2: Size U32
3: Sign U32
4: Core U32
5: Speed U32
6: Address U32
status=True
code=I32 -700112
```

旧手順の`Size=4`、`Speed=2`はバイト位置を識別するダミー値としてのみ使用し、実機設定値として使用しない。

---

#### 4. `Build_LOGINFO_Raw.vi`の現行補正

##### 4.1 データモデル

```text
index 0..3   LogDevice I32
index 4..7   LimitHddSize I32
各MdlNoの領域:
  Base Offset = 8 + MdlNo × 8
  Base+0..3   LogSize I32
  Base+4..7   BufferSize I32
全体136byte
```

##### 4.2 構造選定

- Module Log Configsを1要素ずつ処理するためForループ。
- U8[136]更新結果を保持する配列Shift Register。
- MdlNo重複を検出するBoolean[16] Seen Shift Register。
- 最初のエラーを保持するerror Shift Register。

##### 4.3 エラー全文

MdlNo範囲外：

```text
Build_LOGINFO_Raw.vi: MdlNo must be 0..15. MdlNo=%d
```

```text
%d ← MdlNo I32
status=True
code=I32 -700113
```

MdlNo重複：

```text
Build_LOGINFO_Raw.vi: Duplicate MdlNo is not allowed. MdlNo=%d
```

```text
%d ← MdlNo I32
status=True
code=I32 -700114
```

両エラーともBundle By Nameの基準クラスタ、status、code、source、error出力トンネルまで配線する。

---

#### 5. 単体テスト

- MEASINFOはArray Size=72、index 0/4/8の値を確認する。
- CHINFOはChNum=1/2、Array Size=24/48、正式コード、Address境界、0要素、2049要素、既存errorを確認する。
- LOGINFOはMdlNo=0/1/15、範囲外、重複、複数要素、既存errorを確認する。
- 配線順確認には異なる識別値を使うが、実機コード試験と区別する。

---

### 10.6.6 `RAMScope_Packet.ctl`の最終作成手順

#### 0. 実現したい機能とctlの責務

1PacketのRaw Flagを保持したまま、RAMモニタ用Flagの各フィールドを上位VIとTDMS保存VIへ渡せるようにする。

#### 1. 入力データの実体

ParserがPacket内のFlag 4byteをU32へ変換した値を使用する。

#### 2. 出力データモデル

既存項目を削除せず、次の順へ整理する。

```text
Packet Index          I32
Channel Values        RAMScope_Channel_Value.ctl[]
Flag Raw              U32
Status                U8
Skip?                 Boolean
Log Trigger           U8
Dummy?                 Boolean
Event Bits            U8
Data Lost?             Boolean
Timestamp Raw         U64
Timestamp Seconds     DBL
```

既存項目名が`Flag`の場合は、型をU32のまま維持して`Flag Raw`へ名称変更する。既存VIの破損を避けるためtypedef更新後に全呼出し元を一括確認する。

#### 3. 前提条件・異常条件

- 予約bit専用Booleanを追加しない。
- StatusをEnumだけに変換してRawコードを失わない。
- Dummy Packetもctlへ格納する。

#### 4. 処理アルゴリズム

ctlはデータ型定義だけを担当し、bit演算を持たない。bit演算は`RAMScope_Parse_Buffer.vi`で行う。

#### 5. LabVIEW構造の選定理由

既存ctlを拡張し、新規Packet ctlを並立させない。最新値取得と保存ログ取得で同じPacket構造を共有できるためである。

#### 6. フロントパネル入出力と接続元・接続先

| 項目 | 生成元 | 接続先 |
|---|---|---|
| Flag Raw～Data Lost? | `RAMScope_Parse_Buffer.vi` | Read系公開API、TDMS Append、PoC表示 |
| Timestamp | `RAMScope_Parse_Buffer.vi` | Read系公開API、TDMS Append |

#### 7. 配置する要素

既存clusterへU8、Boolean、U32表示器を追加し、typedefとして保存する。

#### 8. 作成順

1. `RAMScope_Packet.ctl`を開く。
2. typedef編集モードであることを確認する。
3. 既存`Flag`を`Flag Raw`へ変更する。
4. Status、Skip?、Log Trigger、Dummy?、Event Bits、Data Lost?を上記順で追加する。
5. 既定値を数値0、Boolean Falseに設定する。
6. typedefを保存し、変更を全インスタンスへ適用する。
7. 壊れた`Bundle By Name`と`Unbundle By Name`を修正する。

#### 9. 単体テスト

`Flag Raw=0x10FF1D00`を入力し、各フィールドが独立して保持できることを確認する。ctl単体ではbit演算を行わない。

---

### 10.6.7 `RAMScope_Logging_PoC_State.ctl`の作成手順

#### 0. 責務

ロギングPoCで、どのCleanupが必要か、保存ログ取得がどこまで完了したかを1本の状態クラスタで保持する。

#### 1. フィールド

```text
Connected?             Boolean False
File Open?             Boolean False
Measurement Started?   Boolean False
Stopped?               Boolean False
Log Summary Read?      Boolean False
Logging Retrieved?     Boolean False
Released?              Boolean False
```

#### 2. 作成順

1. 新規カスタム制御器へClusterを配置する。
2. 上記Booleanを記載順で配置し、既定値をすべてFalseにする。
3. typedefへ変更する。
4. `30_RAMScope\00_Common\RAMScope_Logging_PoC_State.ctl`として保存する。
5. 通信確認用`RAMScope_PoC_State.ctl`は変更せず、ロギングPoCだけで使用する。

#### 3. 更新元

| フィールド | Trueへ更新する条件 |
|---|---|
| Connected? | `RAMScope_Connect.vi`正常終了 |
| File Open? | `RAMScope_File_Log_Open.vi`正常終了 |
| Measurement Started? | `RAMScope_Log_Start.vi`正常終了 |
| Stopped? | 通常またはCleanupのStop成功 |
| Log Summary Read? | `RAMScope_Get_Log_Summary.vi`正常終了 |
| Logging Retrieved? | 全MeasNo／BlockNoのReadとAppendが正常終了 |
| Released? | `RAMScope_Release.vi`正常終了 |

#### 4. 単体確認

Bundle By Nameで1項目だけ更新しても、他項目が入力クラスタの値を維持することを確認する。

## 10.7 `RAMScope_Code_To_Error.vi`

#### 1. 完成時の動作

| `error in.status` | `API ReturnCode` | `error out` |
|---|---:|---|
| False | 0 | エラーなし |
| False | 0以外 | RAMScope APIエラーを新規作成 |
| True | 任意 | 元の`error in`を変更せず出力 |

優先順位は次のとおりとする。

```text
既存のCLFN／前段エラー
  ＞ RAMScope API ReturnCode
```

つまり、DLLロード失敗やCLFN引数エラーが既に存在する場合に、API戻り値で元エラーを上書きしない。

---

#### 2. 新規VIを作成する

1. LabVIEWを起動する。
2. `ファイル → 新規VI`を選択する。
3. `ファイル → 名前を付けて保存`を選択する。
4. 次の名前で保存する。

```text
30_RAMScope\00_Common\RAMScope_Code_To_Error.vi
```

5. フロントパネルを開く。

---

#### 3. フロントパネルを作成する

次の4端子を配置する。

| ラベル | 方向 | LabVIEW型 | 作成方法 |
|---|---|---|---|
| `API ReturnCode` | 入力 | I32数値制御器 | 数値制御器を配置し、表現形式をI32へ変更 |
| `Function Name` | 入力 | 文字列制御器 | 文字列制御器を配置 |
| `error in` | 入力 | error cluster制御器 | `制御器 → 配列、行列、クラスタ → エラー入力` |
| `error out` | 出力 | error cluster表示器 | `制御器 → 配列、行列、クラスタ → エラー出力` |

##### 3.1 `API ReturnCode`をI32にする

1. 数値制御器を右クリックする。
2. `表現形式`を開く。
3. `I32`を選択する。
4. ラベルを`API ReturnCode`に変更する。

DBLのままにしない。RAMScope APIのC言語`long`はWindowsでは32bitである。

##### 3.2 コネクタペイン

コネクタペインは、左側を入力、右側を出力にする。

推奨配置：

```text
左上   API ReturnCode
左中   Function Name
左下   error in
右下   error out
```

設定手順：

1. VIアイコンを右クリックする。
2. `コネクタを表示`を選択する。
3. 端子をクリックしてから、対応する制御器または表示器をクリックする。
4. `API ReturnCode`と`Function Name`は`必須`、`error in`は`推奨`に設定する。

---

#### 4. ブロックダイアグラムへ配置する関数

ブロックダイアグラムを開き、次を配置する。

| No. | 関数／ストラクチャ | 配置場所の目安 | 用途 |
|---:|---|---|---|
| 1 | `Unbundle By Name` | `関数 → プログラミング → クラスタ、クラス、バリアント` | `error in.status`を取り出す |
| 2 | `Case Structure` ×2 | `関数 → プログラミング → ストラクチャ` | 既存エラー判定、ReturnCode判定 |
| 3 | `Equal?` | `関数 → プログラミング → 比較` | `API ReturnCode == 0`を判定 |
| 4 | I32数値定数`0` | `関数 → プログラミング → 数値` | 正常コードとの比較 |
| 5 | `Type Cast` | `関数 → プログラミング → 数値 → データ操作` | I32のビット列をU32として扱う |
| 6 | U32数値定数 | 数値定数の表現形式をU32へ変更 | `Type Cast`の出力型を指定 |
| 7 | `Format Into String` | `関数 → プログラミング → 文字列 → 文字列のフォーマット／スキャン` | 関数名、16進、10進を1本の文字列へ変換 |
| 8 | 文字列定数 | 文字列パレット | フォーマット文字列 |
| 9 | `Bundle By Name` | `関数 → プログラミング → クラスタ、クラス、バリアント` | 新しいerror clusterを作る |

LabVIEWのバージョンによりパレット名の日本語表記が少し異なる場合がある。その場合は、関数パレットの検索欄へ英語名を入力して配置する。

---

#### 5. 完成形のブロックダイアグラム

全体は次の二重Case Structureにする。

```text
error in
  │
  ├─→ Unbundle By Name（status）
  │          │
  │          ▼
  │    外側Case Structure
  │    ├─ True：既存エラーあり
  │    │     └─ error inをそのままerror outへ
  │    │
  │    └─ False：既存エラーなし
  │          │
  │          ├─ API ReturnCode == 0 ?
  │          │            │
  │          │            ▼
  │          │      内側Case Structure
  │          │      ├─ True：API正常
  │          │      │     └─ error inをそのままerror outへ
  │          │      │
  │          │      └─ False：API異常
  │          │            ├─ ReturnCodeを16進／10進文字列化
  │          │            ├─ Bundle By Nameでerror cluster生成
  │          │            └─ error outへ
  │          │
  └──────────┴─────────────────────────────→ error out
```

---

#### 6. 外側Case Structureを作成する

外側Case Structureは、**前段またはCLFNのエラーが既にあるか**を判定する。

##### 6.1 `error in.status`を取り出す

1. `Unbundle By Name`を配置する。
2. `error in`を`Unbundle By Name`のクラスタ入力へ配線する。
3. `Unbundle By Name`の要素名をクリックする。
4. `status`を選択する。
5. 取り出したBooleanを外側Case Structureのセレクタ端子`?`へ配線する。

##### 6.2 外側Trueケース

条件：

```text
error in.status == True
```

処理：

1. `error in`をCase Structure左側のトンネルから入れる。
2. そのまま右側の出力トンネルへ配線する。
3. 右側トンネルを`error out`へ配線する。

このケースではReturnCodeを評価しない。元エラーを最優先で保持する。

##### 6.3 外側Falseケース

条件：

```text
error in.status == False
```

処理：

- `API ReturnCode == 0`を判定する。
- 判定結果を内側Case Structureへ渡す。

---

#### 7. ReturnCodeが0か判定する

外側Falseケース内へ次を配置する。

1. `Equal?`を配置する。
2. 一方へ`API ReturnCode`を配線する。
3. もう一方へI32定数`0`を配線する。
4. 定数を右クリックし、表現形式が`I32`であることを確認する。
5. `Equal?`のBoolean出力を内側Case Structureのセレクタ端子へ配線する。

判定結果：

| 内側ケース | 条件 | 意味 |
|---|---|---|
| True | `API ReturnCode == 0` | RAMScope API正常 |
| False | `API ReturnCode != 0` | RAMScope API異常 |

TrueとFalseの意味を逆にしない。`Equal?`を使用しているため、**True側が正常**になる。

---

#### 8. 内側Trueケースを作成する

条件：

```text
API ReturnCode == 0
```

処理：

1. 外側Caseへ入れた`error in`を内側Caseへ配線する。
2. 内側Trueケースでは`error in`をそのまま出力トンネルへ配線する。
3. 新しいエラーは生成しない。

この時点の`error in`は外側Falseケースを通っているため、`status=False`の正常クラスタである。

---

#### 9. 内側Falseケースでエラー文字列を作る

条件：

```text
API ReturnCode != 0
```

作成する文字列：

```text
RAMScope RAMScopeGT150DeviceInit failed. ReturnCode=0x30100001 (806354945)
```

##### 9.1 16進表示用にI32をU32へType Castする

`API ReturnCode`はI32だが、16進表示では32bitのビット列をそのまま8桁表示したい。

1. `Type Cast`を配置する。
2. `API ReturnCode`を`Type Cast`のデータ入力へ配線する。
3. U32数値定数を配置する。
4. U32定数を`Type Cast`の型指定入力へ配線する。
5. `Type Cast`出力がU32になったことをワイヤ色と詳細ヘルプで確認する。

通常の数値変換ではなく`Type Cast`を使う理由：

- 戻り値のビット列を変更せず、符号なし32bitとして16進表示するため。
- 上位ビットが1のコードでも`FFFFFFFF`のように正しく表示するため。

##### 9.2 `Format Into String`を配置する

1. `Format Into String`を配置する。
2. ノードの下端を下へドラッグし、引数端子を3個表示する。
3. 文字列定数を配置する。
4. 次のフォーマット文字列を入力する。

```text
RAMScope %s failed. ReturnCode=0x%08X (%d)
```

##### 9.3 `Format Into String`へ配線する順番

フォーマット指定と引数の対応は次のとおり。

| 順番 | フォーマット | 配線する値 | 型 |
|---:|---|---|---|
| 1 | `%s` | `Function Name` | String |
| 2 | `%08X` | Type Cast後のReturnCode | U32 |
| 3 | `%d` | 元の`API ReturnCode` | I32 |

配線イメージ：

```text
Format string:
"RAMScope %s failed. ReturnCode=0x%08X (%d)"

Function Name ───────────────→ 引数1 `%s`
Type Cast後のU32 ReturnCode ─→ 引数2 `%08X`
元のI32 ReturnCode ──────────→ 引数3 `%d`
```

各指定子の意味：

| 指定子 | 意味 |
|---|---|
| `%s` | 文字列 |
| `%08X` | 16進数、大文字、8桁、空き桁を0で埋める |
| `%d` | 符号付き10進整数 |

`0x`は`%08X`が自動で付けるものではないため、フォーマット文字列側へ直接記載する。

##### 9.4 期待出力

入力：

```text
Function Name  = RAMScopeGT150DeviceInit
API ReturnCode = 806354945
```

出力：

```text
RAMScope RAMScopeGT150DeviceInit failed. ReturnCode=0x30100001 (806354945)
```

---

#### 10. `Bundle By Name`でerror clusterを作る

内側Falseケースへ`Bundle By Name`を配置する。

##### 10.1 基準クラスタを接続する

1. `error in`を`Bundle By Name`のクラスタ入力へ配線する。
2. `Bundle By Name`を下方向へ広げ、次の3要素を表示する。

```text
status
code
source
```

##### 10.2 各要素へ配線する

| error cluster要素 | 配線する値 |
|---|---|
| `status` | Boolean定数`True` |
| `code` | `API ReturnCode`のI32値 |
| `source` | `Format Into String`の出力文字列 |

作成結果：

```text
status = True
code   = API ReturnCode
source = RAMScope <Function Name> failed. ReturnCode=0xXXXXXXXX (<decimal>)
```

`code`へU32を接続しない。error clusterの`code`はI32なので、元の`API ReturnCode`を配線する。

##### 10.3 出力トンネル

1. `Bundle By Name`のクラスタ出力を内側Case Structureの右側トンネルへ配線する。
2. 内側Trueケースでも同じ出力トンネルへ`error in`を配線する。
3. 内側Caseの出力を外側Falseケースの出力トンネルへ配線する。
4. 外側Trueケースでも同じ出力トンネルへ`error in`を配線する。
5. 外側Caseの出力を`error out`へ配線する。

全ケースで出力トンネルを配線しないと、VIの実行矢印が壊れる。

---

#### 11. ケースごとの最終配線

##### 11.1 外側Trueケース

```text
error in.status=True

error in ─────────────────────────→ error out
```

##### 11.2 外側False／内側Trueケース

```text
error in.status=False
API ReturnCode=0

error in ─────────────────────────→ error out
```

##### 11.3 外側False／内側Falseケース

```text
error in.status=False
API ReturnCode!=0

API ReturnCode ─→ Type Cast(U32) ─┐
Function Name ────────────────────┼→ Format Into String ─→ source
API ReturnCode(I32) ──────────────┘

error in ─→ Bundle By Name
             status=True
             code=API ReturnCode
             source=生成文字列
                  ↓
              error out
```

---

#### 12. VIアイコンと説明を設定する

##### 12.1 VI説明

`ファイル → VIプロパティ → ドキュメント`へ次を記載する。

```text
RAMScope APIのI32戻り値をLabVIEW標準error clusterへ変換する。
error inに既存エラーがある場合は元エラーを優先して保持する。
ReturnCode=0は正常、0以外はstatus=Trueのエラーを生成する。
```

##### 12.2 端子説明

| 端子 | 説明 |
|---|---|
| `API ReturnCode` | RAMScope API関数のI32戻り値 |
| `Function Name` | エラーメッセージへ表示するAPI関数名 |
| `error in` | CLFNまたは前段VIのエラー。存在する場合は優先する |
| `error out` | 既存エラーまたはAPI戻り値から生成したエラー |

---

#### 13. 単体テスト

VI単体で次の4ケースを確認する。

##### テスト1：正常

```text
error in.status = False
API ReturnCode  = 0
Function Name   = RAMScopeGT150DeviceInit
```

期待結果：

```text
error out.status = False
error out.code   = 0
```

##### テスト2：RAMScope APIエラー

```text
error in.status = False
API ReturnCode  = 806354945
Function Name   = RAMScopeGT150DeviceInit
```

期待結果：

```text
error out.status = True
error out.code   = 806354945
error out.source = RAMScope RAMScopeGT150DeviceInit failed. ReturnCode=0x30100001 (806354945)
```

##### テスト3：既存エラーを優先

`error in`へ次を与える。

```text
status = True
code   = 1234
source = Existing error
```

さらに、

```text
API ReturnCode = 806354945
```

を与える。

期待結果：

```text
status = True
code   = 1234
source = Existing error
```

RAMScope APIエラーで元エラーを上書きしないことを確認する。

##### テスト4：上位ビットが1のコード

```text
API ReturnCode = -1
```

期待する16進表示：

```text
0xFFFFFFFF
```

これにより、I32からU32への`Type Cast`が正しく機能していることを確認できる。

---

#### 14. DLLラッパでの接続方法

各`RS_DLL_*` VIでは、CLFNの後ろへ次のように接続する。

```text
CLFN
├─ 戻り値 I32 ─────────────→ API ReturnCode
├─ 戻り値 I32 ─────────────→ RAMScope_Code_To_Error.vi / API ReturnCode
├─ CLFN error out ─────────→ RAMScope_Code_To_Error.vi / error in
└─ 関数名文字列定数 ───────→ RAMScope_Code_To_Error.vi / Function Name

RAMScope_Code_To_Error.vi / error out ─→ DLLラッパのerror out
```

例：`RS_DLL_GT150DeviceInit.vi`

```text
Function Name = "RAMScopeGT150DeviceInit"
```

CLFNの`error out`にエラーがある場合は、そのエラーがそのまま返る。
CLFNは正常でもAPI ReturnCodeが0以外の場合は、RAMScope APIエラーへ変換される。

---

#### 15. よくあるミス

| 症状 | 原因 | 対策 |
|---|---|---|
| 内側CaseのTrueでエラーになる | `Equal?`のTrue/Falseを逆に理解している | Trueは`ReturnCode==0`の正常ケース |
| 実行矢印が壊れる | Case Structureのどこかで出力トンネル未配線 | 外側・内側の全ケースでerror clusterを配線 |
| 16進が8桁にならない | `%X`のみ使用 | `%08X`を使用 |
| `0x`が付かない | フォーマット指定に含めていない | `0x%08X`と記載 |
| 上位ビットが1のコードが崩れる | I32をそのまま16進化 | I32をU32へ`Type Cast`してから`%08X` |
| `code`端子へ配線できない | U32をerror clusterのcodeへ接続している | 元のI32 ReturnCodeを接続 |
| 元のCLFNエラーが消える | ReturnCodeを常に新規エラー化 | 外側Caseで`error in.status=True`を最優先 |
| ReturnCode比較の0がDBL | 数値定数の表現形式が未設定 | 定数をI32へ変更 |
| メッセージの値が入れ替わる | Format Into Stringの引数順が違う | `%s`、`%08X`、`%d`の順に配線 |

---

#### 16. 完了チェックリスト

- [ ] `API ReturnCode`がI32である
- [ ] `Function Name`がStringである
- [ ] `error in / error out`が標準error clusterである
- [ ] 外側Caseのセレクタが`error in.status`である
- [ ] 外側Trueケースが元エラーをそのまま出力する
- [ ] 内側Caseのセレクタが`API ReturnCode == 0`である
- [ ] 内側Trueケースが正常クラスタを出力する
- [ ] 内側Falseケースで`Bundle By Name`を使用している
- [ ] 16進表示前にI32をU32へ`Type Cast`している
- [ ] フォーマット文字列が`RAMScope %s failed. ReturnCode=0x%08X (%d)`である
- [ ] `status=True`、`code=API ReturnCode`、`source=生成文字列`になっている
- [ ] 全Case Structureの出力トンネルが配線されている
- [ ] 4パターンの単体テストが完了している

---

## 10.8 薄いDLLラッパVI 18個

### 10.8.0 全18 Wrapperの機器操作順

```text
接続・初期化
  DeviceInit → AllInit → GetSysInfo → PGT_SetMdlConfig
条件設定
  SetMeasCond → SetMeasCh → SetLoggingInfo
開始・オンライン読出し
  MeasStart → GetBufferDataNum → GetBufferData
停止後保存ログ
  MeasStop → GetGapTime → GetMeasNum → GetBlockNum
  → GetLoggingDataNum → GetLoggingData
後処理
  ReleaseBufferData → DeviceExit
```

この順序はMain VIの呼出順を示す。各Wrapper自体は前後の機器操作を内包しない。

### 10.8.1 現行補正と一覧

本節は既存12個とロギング追加6個、合計18個の薄いDLL Wrapperを同じ規則で作成する。各VIのCプロトタイプ、CLFN Parameters、左右端子、事前確保、Function Name、配線は本章内の該当節を参照する。

過去資料の詳細手順と本書が競合する場合は、本書の[10.5 一本化した作成順・確定仕様・監査結果](#105-一本化した作成順確定仕様監査結果)を優先する。

---

#### 1. 共通説明で削除してはいけない個別情報

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

#### 2. 既存12個と追加6個の作成順

| VI | 詳細位置 | 個別に確認する端子・配列 |
|---|---|---|
| `RS_DLL_GT150DeviceInit.vi` | 本章内の該当節 | `pUnitNum`、`kind`をPointer to Valueで左右配線 |
| `RS_DLL_GT150DeviceExit.vi` | 本章内の該当節 | 引数なし、Cleanup専用、DeviceExit error |
| `RS_DLL_GT150AllInit.vi` | 本章内の該当節 | UnitNo I32 Value |
| `RS_DLL_GT150GetSysInfo.vi` | 本章内の該当節 | U8[960]事前確保、Array Data Pointer |
| `RS_DLL_GT150PGT_SetMdlConfig.vi` | 本章内の該当節 | I32[16] SlotErr事前確保 |
| `RS_DLL_GT170SetMeasCond.vi` | 本章内の該当節 | U8[72] MEASINFO、UnitNo、MdlNo |
| `RS_DLL_GT170SetMeasCh.vi` | 本章内の該当節 | ChNum、U8[24×ChNum] CHINFO |
| `RS_DLL_GT150SetLoggingInfo.vi` | 本章内の該当節 | U8[136] LOGINFO |
| `RS_DLL_GT150MeasStart.vi` | 本章内の該当節 | UnitNoのみ、MdlNoなし |
| `RS_DLL_GT150GetBufferData.vi` | 本章内の該当節 | Raw U8配列、pDataNum入力/出力、pLostDataNum |
| `RS_DLL_GT150ReleaseBufferData.vi` | 本章内の該当節 | UnitNoのみ、アイドル時に発行 |
| `RS_DLL_GT150MeasStop.vi` | 本章内の該当節 | UnitNoのみ、MdlNoなし |

---

#### 3. 現行補正

##### `RS_DLL_GT170SetMeasCh.vi`

GT170 RAM用構造体は`CHINFO_RAM170`で、1チャンネル24byteである。

```text
enable / core / address / size / sign / speed
```

`size`はバイト数そのものではなく、`0=1byte`、`1=2byte`、`2=4byte`のコードである。

##### `RS_DLL_GT150ReleaseBufferData.vi`

復元元では呼出位置が未確定と記載されているが、現在は次で確定している。

```text
測定中     → 呼ばない
オフライン → 呼ばない
MeasStop成功後のアイドル状態 → 呼ぶ
```

##### 全Wrapper

- Cの`long`はI32。
- Pointer出力は左端子へ初期値を入れ、右端子から結果を受ける。
- Array Data Pointerへ渡す配列はCLFN前に必要要素数を確保する。
- `Function Name`はヘッダの関数名と完全一致させる。
- 各Caseの全出力トンネルを配線し、`Use default if unwired`へ依存しない。

### 10.8.2 既存Wrapperの省略しない作成手順

#### 1. 本章で作成するDLLラッパVI

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

### 2. CLFN共通設定

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

#### 2.1 通常ラッパの共通ブロックダイアグラム

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

##### Trueケースで返す初期値

| 出力型 | 初期値 |
|---|---|
| I32 | `0` |
| U32 | `0` |
| U8配列 | 空配列、または関数仕様で決めた初期化済み配列 |
| I32配列 | 空配列、または関数仕様で決めた初期化済み配列 |
| API ReturnCode | `0` |

すべてのCaseで出力トンネルを配線する。`Use default if unwired`には頼らない。

---

#### 2.2 配列ポインタの重要事項

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

### 3. `RS_DLL_GT150DeviceInit.vi`

#### 3.1 Cプロトタイプ

```c
long RAMScopeGT150DeviceInit(
    long *pUnitNum,
    long *kind
);
```

#### 3.2 フロントパネル端子

| 端子 | 方向 | 型 |
|---|---|---|
| `error in` | 入力 | error cluster |
| `UnitNum` | 出力 | I32 |
| `kind` | 出力 | I32 |
| `API ReturnCode` | 出力 | I32 |
| `error out` | 出力 | error cluster |

#### 3.3 CLFNパラメータ

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

#### 3.4 CLFNへ接続する値

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

### 4. `RS_DLL_GT150DeviceExit.vi`

#### 4.1 Cプロトタイプ

```c
long RAMScopeGT150DeviceExit(void);
```

#### 4.2 フロントパネル端子

| 端子 | 方向 | 型 |
|---|---|---|
| `error in` | 入力 | error cluster |
| `API ReturnCode` | 出力 | I32 |
| `DeviceExit error` | 出力 | error cluster |

`DeviceExit error`は、DeviceExit呼び出し自体の結果を返す。元の`error in`との統合は`RAMScope_Close.vi`で行う。

#### 4.3 CLFNパラメータ

| 順番 | 設定 |
|---:|---|
| Return | Numeric / Signed 32-bit Integer / Value |
| 引数 | なし |

表示プロトタイプ例：

```c
int32_t RAMScopeGT150DeviceExit(void);
```

#### 4.4 前段エラーがあっても呼ぶ構成

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

### 5. `RS_DLL_GT150AllInit.vi`

#### 5.1 Cプロトタイプ

```c
long RAMScopeGT150AllInit(long UnitNo);
```

#### 5.2 フロントパネル端子

| 端子 | 方向 | 型 |
|---|---|---|
| `UnitNo` | 入力 | I32 |
| `error in` | 入力 | error cluster |
| `API ReturnCode` | 出力 | I32 |
| `error out` | 出力 | error cluster |

#### 5.3 CLFNパラメータ

| 順番 | 名前 | Type | Data Type | Pass |
|---:|---|---|---|---|
| Return | 戻り値 | Numeric | Signed 32-bit Integer | Value |
| 1 | `UnitNo` | Numeric | Signed 32-bit Integer | Value |

#### 5.4 配線

```text
UnitNo I32 ─────────→ UnitNo
error in ───────────→ CLFN error in
CLFN戻り値 ─────────→ API ReturnCode
CLFN error out ──────→ RAMScope_Code_To_Error.vi
Function Name ───────→ "RAMScopeGT150AllInit"
```

最小PoCでは、公開APIから`UnitNo=0`を渡す。

---

### 6. `RS_DLL_GT150GetSysInfo.vi`

#### 6.1 Cプロトタイプ

```c
long RAMScopeGT150GetSysInfo(
    long UnitNo,
    SYSINFO *pSysInfo
);
```

`SYSINFO`は1要素60バイト。最大16モジュール分として合計960バイトを確保する。

#### 6.2 フロントパネル端子

| 端子 | 方向 | 型 |
|---|---|---|
| `UnitNo` | 入力 | I32 |
| `error in` | 入力 | error cluster |
| `SYSINFO Raw` | 出力 | U8一次元配列 |
| `API ReturnCode` | 出力 | I32 |
| `error out` | 出力 | error cluster |

#### 6.3 CLFNパラメータ

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

#### 6.4 U8[960]の作成

ブロックダイアグラムへ`Initialize Array`を配置する。

```text
U8定数 0 ───────────→ element
I32定数 960 ─────────→ dimension size

Initialize Array出力 → pSysInfo 左端子
pSysInfo 右端子 ─────→ SYSINFO Raw
```

要素側の`0`は必ずU8にする。オレンジ色のDBL定数を使用しない。

#### 6.5 全配線

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

### 7. `RS_DLL_GT150PGT_SetMdlConfig.vi`

#### 7.1 Cプロトタイプ

```c
long RAMScopeGT150PGT_SetMdlConfig(
    long UnitNo,
    long *SlotErr
);
```

#### 7.2 フロントパネル端子

| 端子 | 方向 | 型 |
|---|---|---|
| `UnitNo` | 入力 | I32 |
| `error in` | 入力 | error cluster |
| `SlotErr` | 出力 | I32一次元配列 |
| `API ReturnCode` | 出力 | I32 |
| `error out` | 出力 | error cluster |

#### 7.3 CLFNパラメータ

| 順番 | 名前 | Type | Data Type | Dimensions | Array Format / Pass |
|---:|---|---|---|---:|---|
| Return | 戻り値 | Numeric | Signed 32-bit Integer | - | Value |
| 1 | `UnitNo` | Numeric | Signed 32-bit Integer | - | Value |
| 2 | `SlotErr` | Array | Signed 32-bit Integer | 1 | Array Data Pointer |

#### 7.4 I32[16]の作成と配線

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

### 8. `RS_DLL_GT170SetMeasCond.vi`

#### 8.1 Cプロトタイプ

```c
long RAMScopeGT170SetMeasCond(
    long UnitNo,
    long MdlNo,
    MEASINFO_170 *pMeasInfo
);
```

`MEASINFO_170`は72バイトのunionである。

#### 8.2 フロントパネル端子

| 端子 | 方向 | 型 |
|---|---|---|
| `UnitNo` | 入力 | I32 |
| `MdlNo` | 入力 | I32 |
| `MEASINFO_170 Raw` | 入力 | U8一次元配列、72要素 |
| `error in` | 入力 | error cluster |
| `API ReturnCode` | 出力 | I32 |
| `error out` | 出力 | error cluster |

構造体の生成は公開APIまたはCommon層で行い、ラッパへU8[72]として渡す。

#### 8.3 CLFNパラメータ

| 順番 | 名前 | Type | Data Type | Dimensions | Array Format / Pass |
|---:|---|---|---|---:|---|
| Return | 戻り値 | Numeric | Signed 32-bit Integer | - | Value |
| 1 | `UnitNo` | Numeric | Signed 32-bit Integer | - | Value |
| 2 | `MdlNo` | Numeric | Signed 32-bit Integer | - | Value |
| 3 | `pMeasInfo` | Array | Unsigned 8-bit Integer | 1 | Array Data Pointer |

#### 8.4 配線

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

### 9. `RS_DLL_GT170SetMeasCh.vi`

#### 9.1 Cプロトタイプ

```c
long RAMScopeGT170SetMeasCh(
    long UnitNo,
    long MdlNo,
    long ChNum,
    CHINFO_170 *pChInfo
);
```

RAM用`CHINFO_170`は1チャンネル24バイトである。

#### 9.2 フロントパネル端子

| 端子 | 方向 | 型 |
|---|---|---|
| `UnitNo` | 入力 | I32 |
| `MdlNo` | 入力 | I32 |
| `ChNum` | 入力 | I32 |
| `CHINFO_170 Raw` | 入力 | U8一次元配列、`24 × ChNum`要素 |
| `error in` | 入力 | error cluster |
| `API ReturnCode` | 出力 | I32 |
| `error out` | 出力 | error cluster |

#### 9.3 CLFNパラメータ

| 順番 | 名前 | Type | Data Type | Dimensions | Array Format / Pass |
|---:|---|---|---|---:|---|
| Return | 戻り値 | Numeric | Signed 32-bit Integer | - | Value |
| 1 | `UnitNo` | Numeric | Signed 32-bit Integer | - | Value |
| 2 | `MdlNo` | Numeric | Signed 32-bit Integer | - | Value |
| 3 | `ChNum` | Numeric | Signed 32-bit Integer | - | Value |
| 4 | `pChInfo` | Array | Unsigned 8-bit Integer | 1 | Array Data Pointer |

#### 9.4 配線

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

### 10. `RS_DLL_GT150SetLoggingInfo.vi`

#### 10.1 Cプロトタイプ

```c
long RAMScopeGT150SetLoggingInfo(
    long UnitNo,
    LOGINFO *pLogInfo
);
```

`LOGINFO`は136バイトである。

#### 10.2 フロントパネル端子

| 端子 | 方向 | 型 |
|---|---|---|
| `UnitNo` | 入力 | I32 |
| `LOGINFO Raw` | 入力 | U8一次元配列、136要素 |
| `error in` | 入力 | error cluster |
| `API ReturnCode` | 出力 | I32 |
| `error out` | 出力 | error cluster |

#### 10.3 CLFNパラメータ

| 順番 | 名前 | Type | Data Type | Dimensions | Array Format / Pass |
|---:|---|---|---|---:|---|
| Return | 戻り値 | Numeric | Signed 32-bit Integer | - | Value |
| 1 | `UnitNo` | Numeric | Signed 32-bit Integer | - | Value |
| 2 | `pLogInfo` | Array | Unsigned 8-bit Integer | 1 | Array Data Pointer |

#### 10.4 配線

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

### 11. `RS_DLL_GT150MeasStart.vi`

#### 11.1 Cプロトタイプ

```c
long RAMScopeGT150MeasStart(long UnitNo);
```

#### 11.2 フロントパネル端子

| 端子 | 方向 | 型 |
|---|---|---|
| `UnitNo` | 入力 | I32 |
| `error in` | 入力 | error cluster |
| `API ReturnCode` | 出力 | I32 |
| `error out` | 出力 | error cluster |

#### 11.3 CLFNパラメータと配線

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

### 12. `RS_DLL_GT150GetBufferData.vi`（最終仕様）

#### 0. 実現したい機能とVIの責務

測定中の表示用バッファから要求Packet数以下を取得する既存Wrapperである。関数引数は変更せず、`pDataNum`の入出力と配列事前確保を正す。

#### 1. 入力データの実体

```c
long RAMScopeGT150GetBufferData(
    long UnitNo,
    long MdlNo,
    void *pData,
    long *pDataNum,
    long *pLostDataNum
);
```

#### 2. 出力データモデル

```text
Allocated Raw Buffer U8[]
DataNum I32
LostDataNum I32
API ReturnCode I32
error out
```

#### 3. 前提条件・異常条件

- RequestedDataNum > 0。
- Buffer Byte Size > 0。
- error in.status=TrueならCLFNを呼ばない。

#### 4. 処理アルゴリズム

RequestedDataNumを`pDataNum`左端子へ渡し、右端子からDataNumを受け取る。

#### 5. LabVIEW構造の選定理由

既存エラー時のCLFN実行を防ぐCase Structureと、U8配列確保用Initialize Arrayを使用する。

#### 6. 入出力

既存端子`MaxDataNum`は意味を明確にするため`RequestedDataNum`へ名称変更する。コネクタ位置と型は維持する。

#### 7. CLFN Parameters

| 順 | 名前 | Type | Data Type | Pass |
|---:|---|---|---|---|
| Return | return | Numeric | Signed 32-bit | Value |
| 1 | UnitNo | Numeric | Signed 32-bit | Value |
| 2 | MdlNo | Numeric | Signed 32-bit | Value |
| 3 | pData | Array | Unsigned 8-bit、1D | Array Data Pointer |
| 4 | pDataNum | Numeric | Signed 32-bit | Pointer to Value |
| 5 | pLostDataNum | Numeric | Signed 32-bit | Pointer to Value |

Function Name：`RAMScopeGT150GetBufferData`

#### 8. 配線順

1. U8 0をBuffer Byte Size個Initialize Arrayする。
2. 配列をpData左端子へ接続する。
3. RequestedDataNumをpDataNum左端子へ接続する。
4. I32 0をpLostDataNum左端子へ接続する。
5. pData、pDataNum、pLostDataNumの右端子を各出力へ接続する。
6. ReturnCodeとCLFN errorを`RAMScope_Code_To_Error.vi`へ接続する。
7. bypassケースは空U8[]、DataNum=0、LostDataNum=0、ReturnCode=0、元errorを返す。

#### 9. 単体テスト

1Packet、複数Packet、実取得数が要求数未満、既存error、表示用バッファ空を確認する。

---

### 13. `RS_DLL_GT150ReleaseBufferData.vi`

#### 13.1 Cプロトタイプ

```c
long RAMScopeGT150ReleaseBufferData(long UnitNo);
```

#### 13.2 端子とCLFN設定

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

### 14. `RS_DLL_GT150MeasStop.vi`

#### 14.1 Cプロトタイプ

```c
long RAMScopeGT150MeasStop(long UnitNo);
```

#### 14.2 端子とCLFN設定

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

### 15. DLLラッパ一覧・配線早見表

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

### 16. 各ラッパの完成チェックリスト

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

### 17. 推奨作成順

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

---

### 10.8.3 ロギング取得用Wrapperの作成手順

全WrapperはC関数1個をCLFNで1回だけ呼ぶ。通常Wrapperは`error in.status=True`でCLFNを呼ばず、安全値と元errorを返す。

#### 10.8.3.1 `RS_DLL_GT150GetGapTime.vi`

#### 0. 責務

MeasStart発行直後からハードウェアへの測定開始要求直前までの時間をms単位で取得する。

#### 1. 入力データ

```c
long RAMScopeGT150GetGapTime(long UnitNo, unsigned long *pGapTime);
```

#### 2. 出力

GapTimeMs U32、API ReturnCode I32、error out。

#### 3. 条件

UnitNoは現仕様0。既存error時はGapTimeMs=0。

#### 4. アルゴリズム

pGapTime左端子へU32 0を入れ、右端子から値を得る。

#### 5. 構造理由

Case Structureで既存error時のCLFN呼出しを止める。

#### 6. 入出力

UnitNo、error in／GapTimeMs、API ReturnCode、error out。

#### 7. CLFN Parameters

| 順 | 名前 | Type | Data Type | Pass |
|---:|---|---|---|---|
| Return | return | Numeric | Signed 32-bit | Value |
| 1 | UnitNo | Numeric | Signed 32-bit | Value |
| 2 | pGapTime | Numeric | Unsigned 32-bit | Pointer to Value |

Function Name：`RAMScopeGT150GetGapTime`

#### 8. 配線

UnitNo、U32 0、error inをCLFNへ接続し、pGapTime右端子をGapTimeMsへ接続する。ReturnCodeとCLFN errorを`RAMScope_Code_To_Error.vi`へ接続する。bypass側は0、0、元error。

#### 9. テスト

Start前、Start直後、Stop後、既存errorを確認する。

---

#### 10.8.3.2 `RS_DLL_GT150GetMeasNum.vi`

#### 0. 責務

MeasStartからMeasStopまでに成立した測定回数を取得する。

#### 1. 入力データ

```c
long RAMScopeGT150GetMeasNum(long UnitNo, long *pMeasNum);
```

#### 2. 出力

MeasNum I32、API ReturnCode、error out。

#### 3. 条件

Stop後に使用する。既存error時はMeasNum=0。

#### 4. アルゴリズム

pMeasNum左端子へI32 0、右端子からMeasNum。

#### 5. 構造理由

既存errorバイパス用Case Structure。

#### 6. 入出力

UnitNo、error in／MeasNum、API ReturnCode、error out。

#### 7. CLFN Parameters

| 順 | 名前 | Type | Data Type | Pass |
|---:|---|---|---|---|
| Return | return | Numeric | Signed 32-bit | Value |
| 1 | UnitNo | Numeric | Signed 32-bit | Value |
| 2 | pMeasNum | Numeric | Signed 32-bit | Pointer to Value |

Function Name：`RAMScopeGT150GetMeasNum`

#### 8. 配線

I32 0をPointer左端子へ接続し、右端子をMeasNumへ接続する。ReturnCodeとerrorを共通変換する。

#### 9. テスト

測定0回、1回、複数回、測定中発行、既存error。

---

#### 10.8.3.3 `RS_DLL_GT150GetBlockNum.vi`

#### 0. 責務

指定MeasNoのロギングBlock数を取得する。

#### 1. 入力データ

```c
long RAMScopeGT150GetBlockNum(long UnitNo, long MeasNo, long *pBlockNum);
```

#### 2. 出力

BlockNum I32、API ReturnCode、error out。

#### 3. 条件

`0 <= MeasNo < MeasNum`。既存error時は0。

#### 4. アルゴリズム

pBlockNum左端子0、右端子からBlockNum。

#### 5. 構造理由

通常Wrapper共通Case Structure。

#### 6. 入出力

UnitNo、MeasNo、error in／BlockNum、ReturnCode、error out。

#### 7. CLFN Parameters

| 順 | 名前 | Type | Data Type | Pass |
|---:|---|---|---|---|
| Return | return | Numeric | Signed 32-bit | Value |
| 1 | UnitNo | Numeric | Signed 32-bit | Value |
| 2 | MeasNo | Numeric | Signed 32-bit | Value |
| 3 | pBlockNum | Numeric | Signed 32-bit | Pointer to Value |

Function Name：`RAMScopeGT150GetBlockNum`

#### 8. 配線

Cプロトタイプ順に接続し、Pointer右端子をBlockNumへ接続する。bypass側は0、0、元error。

#### 9. テスト

先頭／末尾MeasNo、-1、MeasNum、BlockNum=0。

---

#### 10.8.3.4 `RS_DLL_GT150GetBufferDataNum.vi`

#### 0. 責務

測定中の表示用バッファに現在保存されているPacket数を取得する。

#### 1. 入力データ

```c
long RAMScopeGT150GetBufferDataNum(long UnitNo, long MdlNo, long *pDataNum);
```

#### 2. 出力

AvailableDataNum I32、API ReturnCode、error out。

#### 3. 条件

RAMモニタMdlNoを指定する。既存error時は0。

#### 4. アルゴリズム

pDataNum左端子0、右端子からAvailableDataNum。

#### 5. 構造理由

通常Wrapper共通Case Structure。

#### 6. 入出力

UnitNo、MdlNo、error in／AvailableDataNum、ReturnCode、error out。

#### 7. CLFN Parameters

| 順 | 名前 | Type | Data Type | Pass |
|---:|---|---|---|---|
| Return | return | Numeric | Signed 32-bit | Value |
| 1 | UnitNo | Numeric | Signed 32-bit | Value |
| 2 | MdlNo | Numeric | Signed 32-bit | Value |
| 3 | pDataNum | Numeric | Signed 32-bit | Pointer to Value |

Function Name：`RAMScopeGT150GetBufferDataNum`

#### 8. 配線

Pointer左0、右AvailableDataNum。ReturnCodeを共通変換する。

#### 9. テスト

測定開始直後、Wait後、GetBufferData実行後、既存error。

---

#### 10.8.3.5 `RS_DLL_GT150GetLoggingDataNum.vi`

#### 0. 責務

指定MeasNo、BlockNo、MdlNoの保存Packet数を取得する。

#### 1. 入力データ

```c
long RAMScopeGT150GetLoggingDataNum(
    long UnitNo,
    long MdlNo,
    long MeasNo,
    long BlockNo,
    long *pDataNum
);
```

#### 2. 出力

AvailableDataNum I32、API ReturnCode、error out。

#### 3. 条件

Stop後、Release前に使用する。MeasNoとBlockNoは上位APIで検証する。

#### 4. アルゴリズム

pDataNum左端子0、右端子から保存Packet数。

#### 5. 構造理由

通常Wrapper共通Case Structure。

#### 6. 入出力

UnitNo、MdlNo、MeasNo、BlockNo、error in／AvailableDataNum、ReturnCode、error out。

#### 7. CLFN Parameters

| 順 | 名前 | Type | Data Type | Pass |
|---:|---|---|---|---|
| Return | return | Numeric | Signed 32-bit | Value |
| 1 | UnitNo | Numeric | Signed 32-bit | Value |
| 2 | MdlNo | Numeric | Signed 32-bit | Value |
| 3 | MeasNo | Numeric | Signed 32-bit | Value |
| 4 | BlockNo | Numeric | Signed 32-bit | Value |
| 5 | pDataNum | Numeric | Signed 32-bit | Pointer to Value |

Function Name：`RAMScopeGT150GetLoggingDataNum`

#### 8. 配線

引数順を変更しない。Pointer右端子をAvailableDataNumへ接続する。bypass側は0、0、元error。

#### 9. テスト

Block先頭／末尾、DataNum=0、MeasNo不正、BlockNo不正、測定中発行。

---

#### 10.8.3.6 `RS_DLL_GT150GetLoggingData.vi`

#### 0. 責務

指定Blockの保存PacketをU8一次元配列へコピーする。Packet解析は行わない。

#### 1. 入力データ

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

#### 2. 出力

Allocated Raw Buffer U8[]、DataNum I32、LostDataNum I32、ReturnCode、error out。

#### 3. 条件

RequestedDataNum>0、Buffer Byte Size>0、Stop後、Release前。

#### 4. アルゴリズム

- Buffer Byte Size分のU8配列をInitialize Array。
- RequestedDataNumをpDataNum左端子へ入力。
- pLostDataNum左端子はI32 0。
- CLFN後にpDataNum右端子から実取得数。

#### 5. 構造理由

Case Structure、Initialize Array、Array Data Pointer、Pointer to Valueを使用する。

#### 6. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| UnitNo、MdlNo、MeasNo、BlockNo | 入力 | I32 |
| RequestedDataNum | 入力 | I32 |
| Buffer Byte Size | 入力 | I32 |
| error in | 入力 | error cluster |
| Allocated Raw Buffer | 出力 | U8[] |
| DataNum、LostDataNum、ReturnCode | 出力 | I32 |
| error out | 出力 | error cluster |

#### 7. CLFN Parameters

| 順 | 名前 | Type | Data Type | Pass |
|---:|---|---|---|---|
| Return | return | Numeric | Signed 32-bit | Value |
| 1 | UnitNo | Numeric | Signed 32-bit | Value |
| 2 | MdlNo | Numeric | Signed 32-bit | Value |
| 3 | MeasNo | Numeric | Signed 32-bit | Value |
| 4 | BlockNo | Numeric | Signed 32-bit | Value |
| 5 | pData | Array | Unsigned 8-bit、1D | Array Data Pointer |
| 6 | pDataNum | Numeric | Signed 32-bit | Pointer to Value |
| 7 | pLostDataNum | Numeric | Signed 32-bit | Pointer to Value |

Function Name：`RAMScopeGT150GetLoggingData`

#### 8. 配線

1. Initialize Array出力をpData左端子へ接続する。
2. RequestedDataNumをpDataNum左端子へ接続する。
3. I32 0をpLostDataNum左端子へ接続する。
4. pData右端子をAllocated Raw Bufferへ接続する。
5. pDataNum右端子をDataNumへ接続する。
6. pLostDataNum右端子をLostDataNumへ接続する。
7. ReturnCodeとCLFN errorを共通変換する。
8. bypass側は空U8[]、DataNum=0、Lost=0、Return=0、元error。

#### 9. テスト

Requested=1、全件要求、実取得数が要求未満、DataNum=0、不正番号、既存error。引数7個であることをCLFN画面で再確認する。

---

## 10.9 数値変換・構造体Builder

### 10.9.1 現行仕様とアルゴリズム

詳細な関数配置と端子配線は本章内の該当節を参照する。本書は00A・00B監査後の設計理由と、ベンダー資料で確定したコードを補正する。

---

#### 1. なぜBuilderと数値変換VIが必要か

LabVIEW上の設定はクラスタやI32/U32で保持するが、DLLはC構造体へのPointerを要求する。Builderは意味付き設定をC構造体と同じバイト配置のU8一次元配列へ変換する。

```text
LabVIEW設定クラスタ
  → 各数値を4byte Little Endianへ変換
  → 構造体offsetへ書込
  → DLLへ渡すU8配列
```

同じ4byte変換を各Builderへ複製すると、Endianと符号の修正が複数箇所へ散る。そのため変換VIへ分離する。

---

#### 2. 個別VI一覧

| VI | 責務 | 必要な構造 |
|---|---|---|
| `U32_To_LE_U8x4.vi` | U32をb0,b1,b2,b3へ分解 | 既存error Case、Split Number、Build Array |
| `I32_To_LE_U8x4.vi` | I32のビット列を保ってU32経由で変換 | Type Cast、`U32_To_LE_U8x4.vi` |
| `Build_MEASINFO_170_Raw.vi` | 72byte MEASINFOを生成 | error Case、U8[72]初期化、offset 0/4/8へ書込 |
| `Build_CHINFO_170_Raw.vi` | 24byte×ChNumのCHINFO配列を生成 | 入力検証Case、For、配列とerrorのShift Register |
| `Build_LOGINFO_Raw.vi` | 136byte LOGINFOを生成 | For、更新配列・Seen・errorのShift Register |

Parser側で使用する`U8x4_To_U32.vi`、`U8x4_To_I32.vi`、`U8x8_To_U64.vi`は[10.10 Parser](#1010-parser)を参照する。

---

#### 3. `Build_CHINFO_170_Raw.vi`の現行補正

##### 3.1 入力データと出力モデル

`Channel List`は`RAMScope_Channel.ctl`の一次元配列で、1要素が1チャンネルである。出力は次の24byteレコードをChNum個連結したU8配列である。

```text
offset  0 : enable  U32
       4 : core    U32
       8 : address U32
      12 : size    U32
      16 : sign    U32
      20 : speed   U32
```

##### 3.2 正式コード

```text
enable : 0 / 1
core   : 0
size   : 0=1byte、1=2byte、2=4byte
sign   : 0=unsigned、1=signed
speed  : 0
```

```text
size=0 → Address任意
size=1 → Address mod 2 = 0
size=2 → Address mod 4 = 0
```

##### 3.3 アルゴリズム

```text
ChNum = Array Size(Channel List)
if ChNum < 1 or ChNum > 2048:
    -700111
else:
    U8[24×ChNum]を0初期化
    for each Channel:
        コードとAddress境界を検証
        6個のU32を各4byteへ変換
        Write Index = Channel Index × 24
        累積配列へ書込
```

Forループは同じ24byte変換を全チャンネルへ適用するために必要である。配列Shift Registerは前反復までに書き込んだU8配列を保持する。error Shift Registerは最初の変換エラーを後続反復で上書きしないために必要である。

##### 3.4 エラー全文

ChNum不正：

```text
Build_CHINFO_170_Raw.vi: Channel count must be 1..2048. ChNum=%d
```

```text
%d ← ChNum I32
status=True
code=I32 -700111
source=Format Into String出力
基準クラスタ=対象Caseへ入った正常error
```

チャンネル設定不正：

```text
Build_CHINFO_170_Raw.vi: Channel setting is invalid. ChannelIndex=%d, Size=%d, Sign=%d, Core=%d, Speed=%d, Address=%u
```

```text
1: Channel Index I32
2: Size U32
3: Sign U32
4: Core U32
5: Speed U32
6: Address U32
status=True
code=I32 -700112
```

旧手順の`Size=4`、`Speed=2`はバイト位置を識別するダミー値としてのみ使用し、実機設定値として使用しない。

---

#### 4. `Build_LOGINFO_Raw.vi`の現行補正

##### 4.1 データモデル

```text
index 0..3   LogDevice I32
index 4..7   LimitHddSize I32
各MdlNoの領域:
  Base Offset = 8 + MdlNo × 8
  Base+0..3   LogSize I32
  Base+4..7   BufferSize I32
全体136byte
```

##### 4.2 構造選定

- Module Log Configsを1要素ずつ処理するためForループ。
- U8[136]更新結果を保持する配列Shift Register。
- MdlNo重複を検出するBoolean[16] Seen Shift Register。
- 最初のエラーを保持するerror Shift Register。

##### 4.3 エラー全文

MdlNo範囲外：

```text
Build_LOGINFO_Raw.vi: MdlNo must be 0..15. MdlNo=%d
```

```text
%d ← MdlNo I32
status=True
code=I32 -700113
```

MdlNo重複：

```text
Build_LOGINFO_Raw.vi: Duplicate MdlNo is not allowed. MdlNo=%d
```

```text
%d ← MdlNo I32
status=True
code=I32 -700114
```

両エラーともBundle By Nameの基準クラスタ、status、code、source、error出力トンネルまで配線する。

---

#### 5. 単体テスト

- MEASINFOはArray Size=72、index 0/4/8の値を確認する。
- CHINFOはChNum=1/2、Array Size=24/48、正式コード、Address境界、0要素、2049要素、既存errorを確認する。
- LOGINFOはMdlNo=0/1/15、範囲外、重複、複数要素、既存errorを確認する。
- 配線順確認には異なる識別値を使うが、実機コード試験と区別する。

### 10.9.2 各VIの作成手順

### 1. 作成するファイル

```text
30_RAMScope\
├─ 00_Common\
│  ├─ RAMScope_Meas_Config.ctl
│  ├─ RAMScope_Channel.ctl
│  ├─ RAMScope_Module_Log_Config.ctl
│  ├─ I32_To_LE_U8x4.vi
│  └─ U32_To_LE_U8x4.vi
│
└─ 20_Parser\
   ├─ Build_MEASINFO_170_Raw.vi
   ├─ Build_CHINFO_170_Raw.vi
   └─ Build_LOGINFO_Raw.vi
```

構造体生成VIはDLLを呼ばない。入力された設定値をU8配列へ変換する純粋処理とする。

---

### 2. 共通ルール

#### 2.1 C構造体はWindowsのメモリ配置で生成する

今回使用するフィールドはすべて4バイト境界で並び、ヘッダ上の`long`、`unsigned long`、`DWORD`はいずれも4バイトである。

構造体生成では次の順序を守る。

1. 構造体全体をU8の0で必要サイズ分初期化する。
2. 各I32/U32を4バイトのLittle Endian配列へ変換する。
3. `Replace Array Subset`でヘッダ記載のオフセットへ格納する。
4. 最後に`Array Size`で想定サイズを確認する。

#### 2.2 使用する主なLabVIEW関数

| 関数 | パレットの目安 | 用途 |
|---|---|---|
| `Initialize Array` | プログラミング → 配列 | U8配列を必要サイズで初期化 |
| `Replace Array Subset` | プログラミング → 配列 | 指定オフセットへ4バイト配列を格納 |
| `Array Size` | プログラミング → 配列 | 配列要素数の取得 |
| `For Loop` | プログラミング → ストラクチャ | チャンネル、モジュール設定を順に処理 |
| `Shift Register` | For Loop枠を右クリック | U8配列を1次元のまま連結 |
| `Build Array` | プログラミング → 配列 | 配列の連結。`Concatenate Inputs`を使用 |
| `Unbundle By Name` | プログラミング → クラスタ | typedefクラスタから設定値を取得 |
| `Flatten To String` | プログラミング → 文字列 | I32/U32を指定Byte Orderで4バイト化 |
| `String To Byte Array` | プログラミング → 文字列 | 4バイト文字列をU8配列へ変換 |
| `Case Structure` | プログラミング → ストラクチャ | 既存エラー、入力値不正の分岐 |
| `Bundle By Name` | プログラミング → クラスタ | ローカル検証エラーの生成 |

---

### 3. I32/U32をLittle Endian U8[4]へ変換する共通VI

構造体生成VI内で同じ処理を何度も複製しないため、2つの共通VIを先に作る。

---

#### 3.1 `I32_To_LE_U8x4.vi`

##### 3.1.1 フロントパネル端子

| 端子 | 方向 | 型 |
|---|---|---|
| `Value` | 入力 | I32 |
| `error in` | 入力 | error cluster |
| `Bytes` | 出力 | U8一次元配列 |
| `error out` | 出力 | error cluster |

##### 3.1.2 ブロックダイアグラムへ配置する関数

```text
Unbundle By Name（error in.status）
Case Structure
Flatten To String
String To Byte Array
Array Size
```

##### 3.1.3 Case Structure

`error in.status`をCase Structureのセレクタへ接続する。

###### Trueケース

```text
error in → error out
空のU8配列 → Bytes
```

###### Falseケース

1. `Value`を`Flatten To String`のanything入力へ接続する。
2. `Flatten To String`の`byte order`端子を表示する。
3. byte orderへ`little-endian`定数を接続する。
4. 出力文字列を`String To Byte Array`へ接続する。
5. U8配列を`Bytes`へ出力する。
6. `Array Size`が4であることをデバッグ時に確認する。
7. `error in`をそのまま`error out`へ出力する。

完成イメージ：

```text
I32 Value
   ↓
Flatten To String（little-endian）
   ↓
String To Byte Array
   ↓
U8[4]
```

##### 3.1.4 単体テスト

```text
Value = 100
期待Bytes = 64 00 00 00

Value = -1
期待Bytes = FF FF FF FF
```

---

#### 3.2 `U32_To_LE_U8x4.vi`

`I32_To_LE_U8x4.vi`を別名保存し、`Value`の表現形式だけU32へ変更する。

##### 単体テスト

```text
Value = 0x00001000
期待Bytes = 00 10 00 00

Value = 0xFFFFFFFF
期待Bytes = FF FF FF FF
```

---

### 4. typedefを作成する

---

#### 4.1 `RAMScope_Meas_Config.ctl`

##### 4.1.1 作成方法

1. 新規カスタム制御器を作成する。
2. Clusterを配置する。
3. 以下のI32数値制御器をClusterへ入れる。
4. 制御器を`typedef`へ変更する。
5. `30_RAMScope\00_Common\RAMScope_Meas_Config.ctl`として保存する。

##### 4.1.2 フィールド

| フィールド | 型 | 初期PoC例 | 用途 |
|---|---|---:|---|
| `DummyInterval` | I32 | 100 | ダミー測定間隔 |
| `MeasPeri` | I32 | 100 | 測定周期 |
| `MeasUnit` | I32 | 2 | 測定周期の単位コード |

`MeasUnit`の数値定義は使用中APIの外部仕様書を正とし、未確認の値を推測で固定しない。

---

#### 4.2 `RAMScope_Channel.ctl`

このtypedefは1個のRAM監視対象を表す。`RAMScope_Channel.ctl`の配列要素数が、そのまま`ChNum`になる。

##### 4.2.1 フィールド

| フィールド | 型 | DLLへ渡すか | 用途 |
|---|---|---|---|
| `Name` | String | いいえ | 変数名、Parser表示名 |
| `Enable` | U32 | はい | `CHINFO_RAM170.enable` |
| `Core` | U32 | はい | `CHINFO_RAM170.core` |
| `Address` | U32 | はい | 監視RAMアドレス |
| `Size` | U32 | はい | APIのデータサイズコード |
| `Sign` | U32 | はい | APIの符号コード |
| `Speed` | U32 | はい | APIの速度コード |
| `Scale` | DBL | いいえ | Parserの工学値変換。初期値1.0 |
| `Offset` | DBL | いいえ | Parserの工学値変換。初期値0.0 |
| `Unit` | String | いいえ | 工学単位表示 |

`Size`、`Sign`、`Speed`はベンダーAPIコードをそのまま保持する。意味が正式資料で確定するまでは独自変換しない。

##### 4.2.2 `ChNum`の決定方法

```text
RAMScope_Channel.ctl 配列
           ↓
       Array Size
           ↓
         ChNum
```

`ChNum`を操作者が別入力で手入力しない。設定配列の要素数から自動算出する。

##### 4.2.3 既存RAMScopeコンフィグとの接続

PoCでは、既存RAMScope設定に登録されている監視変数を`RAMScope_Channel.ctl`配列へ転記する。

将来の自動読込は次の責務分担とする。

```text
RAMScope設定ファイルまたはエクスポートCSV
           ↓
Load_RAMScope_Channel_Config.vi
           ↓
RAMScope_Channel.ctl 配列
           ├─ Array Size → ChNum
           ├─ Build_CHINFO_170_Raw.vi
           └─ RAMScope_Parse_Buffer.vi
```

ベンダー設定ファイルが非公開形式の場合、バイナリ構造を推測で解析しない。ベンダーの仕様書を入手するか、CSV/テキストへエクスポートした中間ファイルを正本にする。

---

#### 4.3 `RAMScope_Module_Log_Config.ctl`

`LOGINFO.mdl[16]`のうち、設定するモジュールだけを記述するtypedef。

| フィールド | 型 | 用途 |
|---|---|---|
| `MdlNo` | I32 | 0から15のモジュール番号 |
| `LogSize` | I32 | ログ容量設定 |
| `BufferSize` | I32 | バッファ容量設定 |

---

### 5. `Build_MEASINFO_170_Raw.vi`

#### 5.1 C構造体

```c
typedef struct MEASINFO_RAM170 {
    long DummyInterval;       // offset 0
    long MeasPeri;            // offset 4
    long MeasUnit;            // offset 8
    long MeasPeri_reserve[2]; // offset 12, 16
} MEASINFO_RAM170;

typedef union MEASINFO_170 {
    MEASINFO_RAM170 RAM;
    MEASINFO_ADC170 ADC;
    MEASINFO_CAN170 CAN;
} MEASINFO_170;
```

union全体は72バイト。RAM設定では先頭20バイトを使用し、残りを0で初期化する。

#### 5.2 フロントパネル端子

| 端子 | 方向 | 型 |
|---|---|---|
| `Meas Config` | 入力 | `RAMScope_Meas_Config.ctl` |
| `error in` | 入力 | error cluster |
| `MEASINFO_170 Raw` | 出力 | U8一次元配列 |
| `error out` | 出力 | error cluster |

#### 5.3 ブロックダイアグラムへ配置する関数

```text
Unbundle By Name
Initialize Array
I32_To_LE_U8x4.vi ×3
Replace Array Subset ×3
Case Structure
Array Size
```

#### 5.4 初期配列を作る

```text
U8定数 0 ─────────→ Initialize Array element
I32定数 72 ────────→ Initialize Array dimension size
```

出力はU8[72]になる。

#### 5.5 各フィールドを4バイト化する

`Meas Config`を`Unbundle By Name`へ接続し、以下を取り出す。

```text
DummyInterval
MeasPeri
MeasUnit
```

それぞれを`I32_To_LE_U8x4.vi`へ接続する。

#### 5.6 `Replace Array Subset`で格納する

`Replace Array Subset`を3個直列にする。

| 順番 | 格納値 | index |
|---:|---|---:|
| 1 | `DummyInterval Bytes` | 0 |
| 2 | `MeasPeri Bytes` | 4 |
| 3 | `MeasUnit Bytes` | 8 |

```text
U8[72]初期配列
  → Replace(index=0, DummyInterval U8[4])
  → Replace(index=4, MeasPeri U8[4])
  → Replace(index=8, MeasUnit U8[4])
  → MEASINFO_170 Raw
```

offset 12以降は初期値0のままにする。

#### 5.7 エラー分岐

`error in.status`をCase Structureのセレクタへ接続する。

- True：U8[72]のゼロ配列と元の`error in`を出力する。
- False：構造体生成処理を実行し、正常な`error out`を出力する。

#### 5.8 単体テスト

入力：

```text
DummyInterval = 100
MeasPeri      = 100
MeasUnit      = 2
```

先頭20バイト期待値：

```text
64 00 00 00
64 00 00 00
02 00 00 00
00 00 00 00
00 00 00 00
```

確認項目：

- `Array Size = 72`
- offset 0、4、8が期待値
- offset 12から71が0

---

### 6. `Build_CHINFO_170_Raw.vi`

#### 6.1 C構造体

```c
typedef struct CHINFO_RAM170 {
    DWORD enable;  // offset 0
    DWORD core;    // offset 4
    DWORD address; // offset 8
    DWORD size;    // offset 12
    DWORD sign;    // offset 16
    DWORD speed;   // offset 20
} CHINFO_RAM170;
```

1チャンネル24バイト。`CHINFO_170[]`の配列長は`ChNum`と一致させる。

#### 6.2 フロントパネル端子

| 端子 | 方向 | 型 |
|---|---|---|
| `Channel List` | 入力 | `RAMScope_Channel.ctl`一次元配列 |
| `error in` | 入力 | error cluster |
| `ChNum` | 出力 | I32 |
| `CHINFO_170 Raw` | 出力 | U8一次元配列 |
| `error out` | 出力 | error cluster |

#### 6.3 ブロックダイアグラムへ配置する関数

```text
Array Size
Greater Than 0?
Less Or Equal?
Compound Arithmetic（AND）
Case Structure
For Loop
Unbundle By Name
U32_To_LE_U8x4.vi ×6
Build Array（Concatenate Inputs）
Shift Register
```

#### 6.4 `ChNum`を自動算出する

```text
Channel List → Array Size → ChNum
```

`ChNum`をI32へ変換して出力する。

初期PoCの有効範囲：

```text
1 <= ChNum <= 2048
```

範囲外の場合はCLFNへ渡さない。

#### 6.5 For Loopを作る

1. `Channel List`をFor Loopへ自動インデックス入力する。
2. For LoopへU8空配列のShift Registerを追加する。
3. 左Shift Registerへ空のU8配列定数を接続する。
4. 1反復で1チャンネル分の24バイトを生成する。
5. 生成した24バイトを累積配列へ連結する。
6. 最終Shift Registerを`CHINFO_170 Raw`へ接続する。

#### 6.6 1チャンネル分の24バイトを作る

For Loop内で`Unbundle By Name`を使用し、以下を取り出す。

```text
Enable
Core
Address
Size
Sign
Speed
```

各U32を`U32_To_LE_U8x4.vi`へ接続する。

`Build Array`を配置し、右クリックして`Concatenate Inputs`を有効にする。入力を6個まで増やし、次の順番で接続する。

```text
Enable Bytes
Core Bytes
Address Bytes
Size Bytes
Sign Bytes
Speed Bytes
```

出力がU8[24]になる。

#### 6.7 全チャンネルを1次元配列へ連結する

別の`Build Array`を配置し、`Concatenate Inputs`を有効にする。

```text
左Shift Registerの累積U8配列
+ 今回のU8[24]
        ↓
右Shift Register
```

2次元配列にしない。`Build Array`の`Concatenate Inputs`が有効であることを確認する。

#### 6.8 入力不正時のCase

`ChNum`範囲判定をCase Structureへ接続する。

- True：For LoopでRaw配列を生成する。
- False：空のU8配列を出力し、`Bundle By Name`でローカル検証エラーを作成する。

エラーメッセージ例：

```text
Build_CHINFO_170_Raw.vi: Channel count must be 1..2048. ChNum=<value>
```

エラーコードはプロジェクトで定義したユーザーエラー範囲から一意に割り当て、数値を複数VIへ直書きしない。

#### 6.9 単体テスト

1チャンネル入力例：

```text
Name    = TestValue
Enable  = 1
Core    = 0
Address = 0x00001000
Size    = 0
Sign    = 0
Speed   = 0
```

期待値：

```text
ChNum = 1
Array Size(CHINFO_170 Raw) = 24

01 00 00 00  // Enable
00 00 00 00  // Core
00 10 00 00  // Address
00 00 00 00  // Size
00 00 00 00  // Sign
00 00 00 00  // Speed
```

3チャンネルの場合：

```text
ChNum = 3
Array Size = 72
```

---

### 7. `Build_LOGINFO_Raw.vi`

#### 7.1 C構造体

```c
typedef struct LOGINFO {
    long logDevice;       // offset 0
    long limitHddSize;    // offset 4
    struct {
        long logSize;     // offset 8 + i*8
        long BuffSize;    // offset 12 + i*8
    } mdl[16];
} LOGINFO;
```

合計136バイト。

#### 7.2 フロントパネル端子

| 端子 | 方向 | 型 |
|---|---|---|
| `LogDevice` | 入力 | I32 |
| `LimitHddSize` | 入力 | I32 |
| `Module Log Configs` | 入力 | `RAMScope_Module_Log_Config.ctl`一次元配列 |
| `error in` | 入力 | error cluster |
| `LOGINFO Raw` | 出力 | U8一次元配列 |
| `error out` | 出力 | error cluster |

#### 7.3 初期配列とヘッダを作る

```text
U8 0 × 136 → Initialize Array
```

`LogDevice`、`LimitHddSize`を`I32_To_LE_U8x4.vi`へ接続し、次の位置へ格納する。

| 値 | index |
|---|---:|
| `LogDevice` | 0 |
| `LimitHddSize` | 4 |

#### 7.4 モジュールごとの設定を格納する

`Module Log Configs`をFor Loopへ自動インデックス入力する。

各反復で次を取り出す。

```text
MdlNo
LogSize
BufferSize
```

MdlNoを検証する。

```text
0 <= MdlNo <= 15
```

格納位置を計算する。

```text
LogSize index    = 8  + MdlNo × 8
BufferSize index = 12 + MdlNo × 8
```

`LogSize`、`BufferSize`をI32の4バイトへ変換し、`Replace Array Subset`で累積配列へ格納する。

For LoopにはU8[136]のShift Registerを使用する。

#### 7.5 重複MdlNoの確認

同じMdlNoが複数回入力されると後の値で上書きされる。正式実装では次のどちらかを採用する。

- `Seen` Boolean[16]をShift Registerで持ち、2回目をエラーにする。
- 事前にMdlNo配列を作成し、重複検出VIで確認する。

最小PoCでRAMモジュール1個だけを入力する場合も、将来の複数モジュール化を考慮し、重複を許可しない。

#### 7.6 単体テスト

入力：

```text
LogDevice   = 0
LimitHddSize = 0

Module Log Configs[0]
  MdlNo      = 1
  LogSize    = 1
  BufferSize = 1
```

期待値：

```text
Array Size = 136
offset 0  = 0
offset 4  = 0
offset 16 = 1  // 8 + 1*8
offset 20 = 1  // 12 + 1*8
その他は0
```

---

### 8. `RAMScope_Set_Cond.vi`での接続

構造体生成とDLLラッパを次の順で接続する。

```text
Meas Config
  → Build_MEASINFO_170_Raw.vi
  → RS_DLL_GT170SetMeasCond.vi

Channel List
  → Build_CHINFO_170_Raw.vi
      ├─ ChNum
      └─ CHINFO_170 Raw
  → RS_DLL_GT170SetMeasCh.vi

Module Log Configs
  → Build_LOGINFO_Raw.vi
  → RS_DLL_GT150SetLoggingInfo.vi
```

エラー線は直列に接続する。

```text
error in
 → Build_MEASINFO
 → SetMeasCond
 → Build_CHINFO
 → SetMeasCh
 → Build_LOGINFO
 → SetLoggingInfo
 → Error_To_TestStatus.vi
 → error out
```

`ChNum`は`Build_CHINFO_170_Raw.vi`の出力をそのまま`RS_DLL_GT170SetMeasCh.vi`へ接続する。別の手入力端子から入力しない。

---

### 9. 完成チェックリスト

#### 共通変換VI

- [ ] I32/U32の出力が必ずU8[4]
- [ ] byte orderがLittle Endian
- [ ] `-1`が`FF FF FF FF`になる

#### MEASINFO

- [ ] 出力サイズ72
- [ ] offset 0、4、8へ正しい値
- [ ] reserveと未使用領域が0

#### CHINFO

- [ ] `ChNum = Array Size(Channel List)`
- [ ] 1チャンネル24バイト
- [ ] 出力が1次元U8配列
- [ ] フィールド順がEnable/Core/Address/Size/Sign/Speed
- [ ] `Array Size = 24 × ChNum`
- [ ] 0チャンネルと2048超を拒否

#### LOGINFO

- [ ] 出力サイズ136
- [ ] MdlNoが0..15
- [ ] offset計算が`8+i*8`、`12+i*8`
- [ ] 未指定モジュールは0
- [ ] 重複MdlNoを拒否

#### 公開API接続

- [ ] BuilderのRaw出力を対応DLLラッパへ接続
- [ ] BuilderとDLLラッパのerror clusterを直列接続
- [ ] ChNumを手入力せずBuilder出力から接続
- [ ] 同じChannel ListをParserにも渡せる構成

---

## 10.10 Parser

### 10.10.1 データモデルと構造選定

詳細な関数配置と端子配線は本章内の該当節を参照する。本書は、なぜParser、Case Structure、Forループ、Shift Registerが必要なのかと、現行の確定仕様を補正する。

---

#### 1. Parserが必要な理由

DLLが返すU8配列には型情報やフィールド名がない。人が扱いたいのは、モジュール、チャンネル値、Flag、Timestamp等の意味付きデータである。

```text
DLLのU8配列
  → バイト位置とEndianを仕様で解釈
  → 数値へ変換
  → typedefクラスタへ格納
```

ParserをDLL Wrapperから分離すると、GT170がなくてもダミーU8配列で解析ロジックを検証できる。

---

#### 2. 数値変換VI

| VI | 入力 | 出力 | 構造 |
|---|---|---|---|
| `U8x4_To_U32.vi` | U8[4]、Byte Order | U32 | error Case、サイズCase、Endian Case、Join Numbers |
| `U8x4_To_I32.vi` | U8[4]、Byte Order | I32 | U32変換後にType Cast |
| `U8x8_To_U64.vi` | U8[8]、Byte Order | U64 | サイズCase、4byte分割、上下U32結合 |

##### 2.1 U8x4サイズエラー

```text
U8x4_To_U32.vi: Input size must be 4. Actual=%d
```

```text
%d ← Array Size(Bytes) I32
status=True
code=I32 -700101
source=Format Into String出力
基準クラスタ=サイズ判定Caseへ入った正常error
```

##### 2.2 U8x8サイズエラー

```text
U8x8_To_U64.vi: Input size must be 8. Actual=%d
```

```text
%d ← Array Size(Bytes) I32
status=True
code=I32 -700102
source=Format Into String出力
```

---

#### 3. `Parse_SYSINFO_Array.vi`

##### 3.1 入力データの実体

SYSINFO Rawは60byteのレコード16個を連結したU8[960]である。

```text
Record Start = Record Index × 60
Record 0     = index 0..59
Record 1     = index 60..119
...
Record 15    = index 900..959
```

1レコード内の主な位置：

```text
0  module
4  module_type
8  probe_id
12 interface_id
16 version
20 addinfo
24 endian
28 probe_version
32 security_id_req
36 security_id_size
40 flash_enable
44 name[16]
```

##### 3.2 出力モデル

- `Module List`は`RAMScope_Module_Info.ctl[16]`。
- `MdlNo_RAM`、`MdlNo_CAN`、`Endian_RAM`は最初に検出した対象モジュールの値。
- `Connected? = module_type != 0x0F`。

##### 3.3 アルゴリズムと構造選定

```text
if error in.status:
    安全出力、元エラー
elif Array Size(SYSINFO Raw) != 960:
    -700120
else:
    MdlNo_RAM=-1、MdlNo_CAN=-1、Endian_RAM=0で初期化
    for Record Index 0..15:
        Raw全体から60byteを切り出す
        各4byteをI32へ変換
        NameのNULL終端前を文字列化
        Module Infoを作る
        未検出かつRAMならMdlNo_RAMとEndianを保持
        未検出かつCANならMdlNo_CANを保持
```

Forループ入力ではSYSINFO Rawの自動指標付けを無効にする。毎反復でU8単体を受け取るのではなく、U8[960]全体から任意位置を切り出す必要があるためである。

MdlNo_RAM、MdlNo_CAN、Endian_RAM、errorにはShift Registerを使用する。Falseケースで初期値へ戻さず、左内側の現在値を右内側へ渡す。

##### 3.4 サイズエラー

```text
Parse_SYSINFO_Array.vi: SYSINFO Raw size must be 960. Actual=%d
```

```text
%d ← Array Size(SYSINFO Raw) I32
status=True
code=I32 -700120
source=Format Into String出力
```

##### 3.5 確定コード

```text
module_type=0x00 → RAM
module_type=0x02 → CAN
module_type=0x03 → Analog
module_type=0x0E → Power Communication
module_type=0x0F → Disconnected

endian=0 → Big Endian
endian=1 → Little Endian
```

##### 3.6 単体テスト

U8[960]をInitialize Arrayで作り、Replace Array Subsetを直列接続して次を入れる。

```text
Record 0: module=0、module_type=0x00、endian=0、name=RAM0
Record 1: module=1、module_type=0x02、name=CAN0
Record 2..15: module_type=0x0F
```

期待：Module List=16、MdlNo_RAM=0、MdlNo_CAN=1、Endian_RAM=0、両Found=True。959byte、RAMなし、既存errorも確認する。

---

#### 4. `RAMScope_Parse_Buffer.vi`

##### 4.1 入力データの実体

```text
Raw Buffer
├─ Packet 0
│  ├─ Channel 0 : 4byte
│  ├─ Channel 1 : 4byte
│  ├─ ...
│  ├─ Flag      : 4byte
│  └─ Timestamp : 8byte
├─ Packet 1
└─ ...
```

```text
Packet Size         = 4 × ChNum + 12
Expected Byte Count = Packet Size × DataNum
Packet Start        = Packet Index × Packet Size
Value Start         = Packet Start + Channel Index × 4
Flag Start          = Packet Start + 4 × ChNum
Timestamp Start     = Flag Start + 4
```

##### 4.2 出力データモデル

`Packets`は`RAMScope_Packet.ctl`の一次元配列である。1Packetクラスタ内にChannel Values配列、Flag、Timestamp Raw、Timestamp Secondsを持つ。

##### 4.3 前提条件と多段Case

```text
error in.status?
├─ True  → 空Packets、0、0、元エラー
└─ False
    Input Valid? = ChNum>=1 AND DataNum>=0
    ├─ False → -700130
    └─ True
        Raw Buffer Sufficient? = Actual>=Expected
        ├─ False → -700131
        └─ True
            DataNum == 0?
            ├─ True  → 空Packets、正常
            └─ False → Packet解析
```

Caseを分ける理由は、どの前提で解析を中止したかをsourceとcodeで特定し、配列範囲外アクセスを防ぐためである。

##### 4.4 ループ構造

- 外側ForループはDataNum個のPacketを処理する。N=DataNum。
- 内側ForループはChannel Listを自動指標付けし、1反復で1チャンネルを処理する。Nは未配線。
- 内側反復端子も画面上は`i`だが、資料では外側iと区別してChannel Indexとして説明する。
- Packet出力は外側Forループの条件付き指標付けを使う。`Append Packet?=NOT(最終error.status)`とし、途中エラーPacketを配列へ追加しない。

##### 4.5 入力不正エラー

```text
RAMScope_Parse_Buffer.vi: ChNum must be >= 1 and DataNum must be >= 0. ChNum=%d, DataNum=%d
```

```text
1個目の%d ← ChNum I32
2個目の%d ← DataNum I32
status=True
code=I32 -700130
```

##### 4.6 Raw Buffer不足エラー

```text
RAMScope_Parse_Buffer.vi: Raw Buffer is too small. Expected=%d, Actual=%d
```

```text
1個目の%d ← Expected Byte Count I32
2個目の%d ← Actual Byte Count I32
status=True
code=I32 -700131
```

`Expected=20`、`Actual=20`なら`Actual >= Expected=True`なので、Trueケース（Raw Buffer十分）へ進む。Falseケースへエラー生成回路を置かない。

##### 4.7 Timestamp

```text
Timestamp Seconds = DBL(Timestamp Raw) × DBL定数20e-9
```

20nsは作業仮定ではなくベンダー資料で確定した仕様である。

##### 4.8 単体テスト

Channel Listは2要素。

```text
Channel 0: Name=Unsigned、Sign=0、Scale=1、Offset=0
Channel 1: Name=Signed、Sign=1、Scale=1、Offset=0
```

Raw Buffer 20byte：

```text
01 00 00 00                    Channel 0 = 1
FE FF FF FF                    Channel 1 = -2
A5 00 00 00                    Flag = 0xA5
32 00 00 00 00 00 00 00       Timestamp Raw = 50
```

期待：Parsed Packet Count=1、Unused=0、Value=1/-2、Flag=165、Timestamp Raw=50、Timestamp Seconds=1e-6、error正常。

追加でChannel List空、DataNum=-1、19byte不足、DataNum=0、既存errorを確認する。

### 10.10.2 各VIの作成手順

### 1. 作成するファイル

```text
30_RAMScope\
├─ 00_Common\
│  ├─ RAMScope_Module_Info.ctl
│  ├─ RAMScope_Channel_Value.ctl
│  ├─ RAMScope_Packet.ctl
│  ├─ RAMScope_Byte_Order.ctl
│  ├─ U8x4_To_I32.vi
│  ├─ U8x4_To_U32.vi
│  └─ U8x8_To_U64.vi
│
└─ 20_Parser\
   ├─ Parse_SYSINFO_Array.vi
   └─ RAMScope_Parse_Buffer.vi
```

Parser VIはDLLを呼ばない。入力された生バイト列だけを処理する純粋処理とし、実機なしで単体テストできる構成にする。

---

### 2. 共通typedefを作成する

---

#### 2.1 `RAMScope_Byte_Order.ctl`

1. 新規カスタム制御器を作成する。
2. Enumを配置する。
3. 次の2項目を登録する。

```text
Little Endian
Big Endian
```

4. typedefへ変更する。
5. `30_RAMScope\00_Common\RAMScope_Byte_Order.ctl`として保存する。

初期PoCは`Little Endian`で開始し、純正RAMScopeVP表示または既知RAM値と比較して確定する。

---

#### 2.2 `RAMScope_Module_Info.ctl`

`SYSINFO`1レコードをLabVIEWクラスタへ変換した型。

| フィールド | 型 | 元フィールド |
|---|---|---|
| `Record Index` | I32 | U8[960]内の0..15 |
| `ModuleNo` | I32 | `SYSINFO.module` |
| `Module Type` | I32 | `SYSINFO.module_type` |
| `Probe ID` | I32 | `SYSINFO.probe_id` |
| `Interface ID` | I32 | `SYSINFO.interface_id` |
| `Version` | I32 | `SYSINFO.version` |
| `AddInfo` | I32 | `SYSINFO.addinfo` |
| `Endian` | I32 | `SYSINFO.endian` |
| `Probe Version` | I32 | `SYSINFO.probe_version` |
| `Security ID Required` | I32 | `SYSINFO.security_id_req` |
| `Security ID Size` | I32 | `SYSINFO.security_id_size` |
| `Flash Enable` | I32 | `SYSINFO.flash_enable` |
| `Name` | String | `SYSINFO.name[16]` |
| `Connected?` | Boolean | `Module Type != 0x0F` |

---

#### 2.3 `RAMScope_Channel_Value.ctl`

1パケット内の1チャンネル値を表す。

| フィールド | 型 | 用途 |
|---|---|---|
| `Channel Index` | I32 | Channel List内の位置 |
| `Name` | String | `RAMScope_Channel.ctl.Name` |
| `Address` | U32 | 監視アドレス |
| `Raw U32` | U32 | 受信した32bitのビット列 |
| `Value` | DBL | 符号解釈後の数値 |
| `Engineering Value` | DBL | `Value × Scale + Offset` |
| `Unit` | String | 工学単位 |

---

#### 2.4 `RAMScope_Packet.ctl`

1パケット分の解析結果。

| フィールド | 型 |
|---|---|
| `Packet Index` | I32 |
| `Channel Values` | `RAMScope_Channel_Value.ctl`一次元配列 |
| `Flag` | U32 |
| `Timestamp Raw` | U64 |
| `Timestamp Seconds` | DBL |

---

### 3. U8配列を数値へ戻す共通VI

---

#### 3.1 `U8x4_To_U32.vi`

##### 3.1.1 フロントパネル端子

| 端子 | 方向 | 型 |
|---|---|---|
| `Bytes` | 入力 | U8一次元配列 |
| `Byte Order` | 入力 | `RAMScope_Byte_Order.ctl` |
| `error in` | 入力 | error cluster |
| `Value` | 出力 | U32 |
| `error out` | 出力 | error cluster |

##### 3.1.2 配置する関数

```text
Array Size
Equal?
Case Structure
Byte Array To String
Unflatten From String
Bundle By Name
```

##### 3.1.3 サイズ判定

```text
Array Size(Bytes) == 4
```

Falseの場合は`Value=0`を出力し、ローカル検証エラーを生成する。

エラーメッセージ例：

```text
U8x4_To_U32.vi: Input size must be 4. Actual=<size>
```

##### 3.1.4 数値変換

1. `Bytes`を`Byte Array To String`へ接続する。
2. `Unflatten From String`を配置する。
3. type入力へU32数値定数を接続する。
4. `Byte Order`をCase Structureへ接続する。
5. Little Endianケースでは`Unflatten From String`のbyte orderへlittle-endian定数を接続する。
6. Big Endianケースではbig-endian定数を接続する。
7. unflattened dataを`Value`へ出力する。
8. `Unflatten From String`のerror outをVIのerror outへ接続する。

---

#### 3.2 `U8x4_To_I32.vi`

`U8x4_To_U32.vi`を別名保存し、`Unflatten From String`のtype入力をI32へ変更する。

単体テスト：

```text
Bytes = FF FF FF FF、Little Endian
期待Value = -1
```

---

#### 3.3 `U8x8_To_U64.vi`

`U8x4_To_U32.vi`を別名保存し、次を変更する。

- サイズ判定：8
- type入力：U64
- 出力型：U64

単体テスト：

```text
Bytes = 32 00 00 00 00 00 00 00、Little Endian
期待Value = 50
```

---

### 4. `Parse_SYSINFO_Array.vi`

#### 4.1 入出力

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

#### 4.2 SYSINFOレコード配置

1レコード60バイト、16レコード、合計960バイト。

| フィールド | レコード内offset | 長さ |
|---|---:|---:|
| `module` | 0 | 4 |
| `module_type` | 4 | 4 |
| `probe_id` | 8 | 4 |
| `interface_id` | 12 | 4 |
| `version` | 16 | 4 |
| `addinfo` | 20 | 4 |
| `endian` | 24 | 4 |
| `probe_version` | 28 | 4 |
| `security_id_req` | 32 | 4 |
| `security_id_size` | 36 | 4 |
| `flash_enable` | 40 | 4 |
| `name[16]` | 44 | 16 |

#### 4.3 ブロックダイアグラムへ配置する関数

```text
Array Size
Equal?
Case Structure
For Loop（N=16）
Multiply
Array Subset
U8x4_To_I32.vi ×11
Search 1D Array
Byte Array To String
Bundle By Name
Shift Register
Equal?
Not Equal?
Select
```

#### 4.4 入力サイズを確認する

```text
Array Size(SYSINFO Raw) == 960
```

Falseの場合：

- `Module List`は空配列
- `MdlNo_RAM=-1`
- `MdlNo_CAN=-1`
- Found?はFalse
- ローカル検証エラーを出力

エラーメッセージ例：

```text
Parse_SYSINFO_Array.vi: SYSINFO size must be 960. Actual=<size>
```

#### 4.5 For Loopを作る

1. For Loopを配置する。
2. N端子へI32定数16を接続する。
3. ループ反復端子`i`へ60を掛ける。
4. `Array Subset`のindexへ`i × 60`を接続する。
5. lengthへ60を接続する。
6. 出力を1レコードU8[60]として使用する。

```text
Record Start = i × 60
```

#### 4.6 各I32フィールドを取得する

レコードU8[60]から`Array Subset`で4バイトずつ取得し、`U8x4_To_I32.vi`へ接続する。

例：

```text
record → Array Subset(index=0, length=4) → module
record → Array Subset(index=4, length=4) → module_type
record → Array Subset(index=24, length=4) → endian
```

11フィールドすべて同様に作成する。

#### 4.7 `name[16]`を文字列へ変換する

1. `Array Subset(index=44, length=16)`でName Bytesを取得する。
2. `Search 1D Array`でU8定数0を検索する。
3. 検索結果をCase Structureへ接続する。

##### 検索結果が-1

NULL終端がないため16バイトすべてを使用する。

##### 検索結果が0以上

検索結果をlengthとして`Array Subset`で先頭から切り出す。

4. 切り出したU8配列を`Byte Array To String`へ接続する。
5. 出力を`Name`へ使用する。

#### 4.8 Module Infoクラスタを作る

`Bundle By Name`で`RAMScope_Module_Info.ctl`へ各値を格納する。

```text
Record Index = i
ModuleNo = module
Module Type = module_type
...
Name = 変換文字列
Connected? = module_type != 0x0F
```

For Loopの出力トンネルを自動インデックスにし、`Module List`を作る。

#### 4.9 RAM/CANモジュール番号を抽出する

For Loopへ次のShift Registerを追加する。

```text
MdlNo_RAM 初期値 = -1
MdlNo_CAN 初期値 = -1
Endian_RAM 初期値 = 0
```

判定値：

```text
RAM module_type = 0x00
CAN module_type = 0x02
Disconnected    = 0x0F
```

##### RAM判定

```text
module_type == 0x00
AND 現在のMdlNo_RAM == -1
```

Trueなら：

```text
MdlNo_RAM = module
Endian_RAM = endian
```

FalseならShift Register値を維持する。

##### CAN判定

```text
module_type == 0x02
AND 現在のMdlNo_CAN == -1
```

Trueなら`MdlNo_CAN=module`とする。

For Loop終了後：

```text
RAM Module Found? = MdlNo_RAM >= 0
CAN Module Found? = MdlNo_CAN >= 0
```

CAN未搭載はParserエラーにしない。RAM未搭載を試験停止条件にするかは`RAMScope_Init.vi`で判断する。

#### 4.10 単体テスト

ダミーU8[960]を作り、レコード1へ次を格納する。

```text
module = 1
module_type = 0x00
endian = 0
name = "RAM"
```

期待結果：

```text
MdlNo_RAM = 1
RAM Module Found? = True
Name = RAM
Module List要素数 = 16
```

別レコードへ`module_type=0x02`を入れ、CAN検出も確認する。

---

### 5. `RAMScope_Parse_Buffer.vi`（オンライン・保存ログ共通の最終仕様）

#### 0. 実現したい機能とVIの責務

最新値取得と保存ログ取得の両方から渡されるU8配列を、チャンネル値、RAM用Flag、20ns Timeを持つPacket配列へ変換する。

#### 1. 入力データの実体

```text
Raw Buffer U8[]
DataNum I32
Channel List RAMScope_Channel.ctl[]
Byte Order RAMScope_Byte_Order.ctl
```

Packet内の各Dataスロットは4byte固定だが、有効値幅は`RAMScope_Channel.ctl.Size`で決まる。

```text
Size=0 → 1byte有効
Size=1 → 2byte有効
Size=2 → 4byte有効
```

#### 2. 出力データモデル

```text
Packets RAMScope_Packet.ctl[]
Parsed Packet Count I32
Unused Byte Count I32
error out error cluster
```

#### 3. 前提条件・異常条件

```text
ChNum > 0
DataNum >= 0
Actual Byte Count >= DataNum × Packet Size
```

- `DataNum=0`は正常な空データ。
- Buffer不足はParserエラー。
- Status、Skip、Data LostはPacket状態でありParserエラーにしない。
- Sizeが0、1、2以外ならローカルエラー`-700160`。

source全文：

```text
RAMScope_Parse_Buffer.vi: Unsupported channel Size. ChannelIndex=%d, Size=%d
```

#### 4. 処理アルゴリズム

```text
ChNum = Array Size(Channel List)
Packet Size = ChNum × 4 + 12
Expected Bytes = DataNum × Packet Size
Actual Bytes = Array Size(Raw Buffer)

for PacketIndex in 0 ... DataNum-1:
    Packet Start = PacketIndex × Packet Size

    for ChannelIndex in 0 ... ChNum-1:
        Data Start = Packet Start + ChannelIndex × 4
        Raw Slot U32 = U8x4_To_U32(Data Start, Byte Order)
        Value = DecodeBySizeAndSign(Raw Slot U32, Size, Sign)
        Engineering Value = Value × Scale + Offset

    Flag Start = Packet Start + ChNum × 4
    Flag Raw = U8x4_To_U32(Flag Start, Byte Order)
    Flag fields = mask and shift

    Time Start = Flag Start + 4
    Time Raw = U8x8_To_U64(Time Start, Byte Order)
    Time Seconds = DBL(Time Raw) × 20e-9

    Bundle RAMScope_Packet.ctl
```

#### 5. LabVIEW構造の選定理由

- Packet反復は外側For Loop。
- Channel反復は内側For Loop。
- Size別の値幅はCase Structure。
- 4byte、8byte切出しはArray Subset。
- 符号付き値はType Castでbit列を維持する。
- FlagはLogical ShiftとANDで抽出する。

#### 6. フロントパネル入出力と接続元・接続先

| 端子 | 方向 | 型 | 接続元・接続先 |
|---|---|---|---|
| Raw Buffer | 入力 | U8[] | `RAMScope_Read.vi`または`RAMScope_Read_Logging_Block.vi` |
| DataNum | 入力 | I32 | 各DLL Wrapperの実取得数 |
| Channel List | 入力 | `RAMScope_Channel.ctl[]` | SetMeasChへ渡した同一配列 |
| Byte Order | 入力 | typedef | Init結果を明示変換した値 |
| Packets | 出力 | `RAMScope_Packet.ctl[]` | PoC、TDMS Append、TestStand |
| Parsed Packet Count | 出力 | I32 | 件数照合 |
| Unused Byte Count | 出力 | I32 | デバッグ・品質判定 |

#### 7. 配置する関数およびSubVI

- For Loop ×2。
- Case Structure：Size 0、1、2、Default。
- Array Size、Array Subset。
- U8x4_To_U32.vi、U8x8_To_U64.vi。
- AND、Logical Shift、Not Equal To 0?。
- Type Cast、To Double Precision Float。
- Bundle By Name。
- Format Into String、Bundle By Nameによるローカルerror生成。

#### 8. 配線順

##### A. サイズ検証

1. Channel ListをArray Sizeへ接続してChNumを得る。
2. ChNum、DataNumを先にI64へ変換する。
3. `Packet Size I64 = ChNum I64 × 4 + 12`を作る。
4. `Expected Bytes I64 = DataNum I64 × Packet Size I64`を作る。
5. Raw BufferのArray SizeをI64へ変換する。
6. `ChNum>0 AND DataNum>=0 AND Actual>=Expected`をCase selectorへ接続する。
7. Falseケースは空Packets、Count 0、Unused 0と`-700161`を返す。

source全文：

```text
RAMScope_Parse_Buffer.vi: Buffer is shorter than expected or input is invalid. ChNum=%d, DataNum=%d, Expected=%lld, Actual=%lld
```

##### B. Channel DataのSize別解析

1. 内側For LoopでChannel clusterからSizeとSignをUnbundleする。
2. Raw Slot U32をSize Caseへ接続する。
3. Size=0では`AND 0x000000FF`後にU8へ変換する。
4. Size=1では`AND 0x0000FFFF`後にU16へ変換する。
5. Size=2ではU32全体を使う。
6. 各Case内でSign=0なら符号なし数値をDBL化する。
7. Sign!=0なら同じbit幅のI8、I16、I32へType CastしてDBL化する。
8. `Value × Scale + Offset`をEngineering Valueへ接続する。
9. Defaultケースは`-700160`を生成する。

##### C. Flag解析

1. `Flag Start = Packet Start + ChNum×4`を作る。
2. 4byteをArray Subsetし、U8x4_To_U32.viへ接続する。
3. Flag Rawを次へ分岐する。

```text
Status      = U8(Flag Raw AND 0x000000FF)
Skip?       = ((Flag Raw >> 8) AND 1) != 0
Log Trigger = U8((Flag Raw >> 10) AND 3)
Dummy?      = ((Flag Raw >> 12) AND 1) != 0
Event Bits  = U8((Flag Raw >> 16) AND 0xFF)
Data Lost?  = ((Flag Raw >> 28) AND 1) != 0
```

4. 予約bitは解析しない。

##### D. Time解析

1. `Time Start = Flag Start + 4`。
2. 8byteをArray Subsetする。
3. U8x8_To_U64.viでTime Rawを取得する。
4. DBLへ変換して`20e-9`を乗算する。

##### E. Packet Bundle

1. 既存`RAMScope_Packet.ctl`定数をBundle By Nameの基準クラスタへ接続する。
2. Packet Index、Channel Values、Flag全項目、Time全項目を接続する。
3. 外側For Loopを自動インデックス出力にする。
4. Array Size(Packets)をParsed Packet Countへ接続する。

#### 9. 単体テスト

- 1byte unsigned `0xFF` → 255。
- 1byte signed `0xFF` → -1。
- 2byte unsigned `0xFFFF` → 65535。
- 2byte signed `0xFFFF` → -1。
- 4byte signed `0xFFFFFFFE` → -2。
- Flag各bitを1個ずつ立てて抽出結果を確認。
- Time Raw=50 → 1us。
- Buffer末尾1byte不足 → Parserエラー。
- DataNum=0 → 正常な空配列。

---

### 7. 公開APIでの接続

#### 7.1 `RAMScope_Init.vi`

```text
RS_DLL_GT150GetSysInfo.vi
  ├─ SYSINFO Raw
  └─ error out
        ↓
Parse_SYSINFO_Array.vi
  ├─ Module List
  ├─ MdlNo_RAM
  ├─ MdlNo_CAN
  ├─ Endian_RAM
  ├─ RAM Module Found?
  └─ error out
```

RAM Module Found?がFalseの場合のエラー生成は`RAMScope_Init.vi`で行う。

#### 7.2 `RAMScope_Read.vi`

```text
RS_DLL_GT150GetBufferData.vi
  ├─ Raw Buffer
  ├─ DataNum
  ├─ LostDataNum
  └─ error out
        ↓
RAMScope_Parse_Buffer.vi
  ├─ Channel List
  ├─ Byte Order
  ├─ Packets
  └─ error out
```

`Channel List`は`Build_CHINFO_170_Raw.vi`へ渡したものと同じ配列を使用する。順序を変更すると取得データと変数名の対応がずれる。

---

### 8. 実機PoCで確認する項目

- [ ] `SYSINFO Raw`が960バイト
- [ ] RAMモジュール番号が純正RAMScopeVP表示と一致
- [ ] Channel Listの順序と取得値の順序が一致
- [ ] 既知RAM変数の値が一致
- [ ] 符号あり／なしの解釈が一致
- [ ] Byte Order設定が一致
- [ ] Flagの変化が妥当
- [ ] Timestampが単調増加する
- [ ] Timestampの20ns換算が実測時間と一致
- [ ] `Parsed Packet Count == DataNum`
- [ ] `LostDataNum`を記録できる
- [ ] 不完全バッファでクラッシュせずエラーを返す

---

### 9. 完成チェックリスト

#### SYSINFO Parser

- [ ] 入力サイズ960を検証
- [ ] 60バイト×16で処理
- [ ] 11個のI32フィールドを正しいoffsetで取得
- [ ] name[16]のNULL終端を除去
- [ ] Module Listが16要素
- [ ] RAM/CANの最初の該当モジュール番号を取得
- [ ] CAN未搭載をエラーにしない

#### Buffer Parser

- [ ] ChNumをChannel Listから算出
- [ ] Packet Sizeが`4×ChNum+12`
- [ ] Expected Byte Countを事前検証
- [ ] 1パケットごとにChannel/Flag/Timestampを解析
- [ ] Size=0／1／2を1byte／2byte／4byteとしてmaskし、符号付き値は同じbit幅へType Castする
- [ ] Status、Skip、Log Trigger、Dummy、Event Bits、Data LostをFlag Rawから抽出する
- [ ] Engineering ValueをScale/Offsetで変換
- [ ] Timestamp Rawへ20nsを掛けて秒へ変換する
- [ ] 余剰バイト数を出力
- [ ] 不完全バッファを検出
- [ ] 実機なしのダミーデータ試験を完了
- [ ] 実機PoCで純正表示または既知値と照合

---

## 10.11 公開API 11個

本節では通信確認用8個と停止後保存ログ取得用3個、合計11個の`RAMScope_*`公開APIを機器操作順で説明する。

全11個の公開APIは最後に`Error_To_TestStatus.vi`を1回だけ呼び、`Status.ctl`、`TestError.ctl`、標準`error out`を返す。DLL Wrapper、Builder、Parserから同SubVIを呼ばない。

---

### 10.11.0 全11公開APIの呼出順

```text
Connect → Init → Set Cond → Log Start → Read → Log Stop
→ Get Log Summary → Get Block Count → Read Logging Block
→ Release → Close
```

`Read`は測定中の表示Buffer、`Read Logging Block`はStop後の保存Bufferを扱う。両者は同じ`RAMScope_Parse_Buffer.vi`を使用する。

---

#### 1. `RAMScope_Connect.vi`

##### 0～5. 機能、データ、アルゴリズム、構造選定

`DeviceInit`を1回実行し、接続Unit数と機種コードを上位へ返す。下位処理は1個のWrapperだけなので、Public VI内に追加のForループや状態保持は不要である。既存エラーのスキップはWrapper側が担当する。

##### 6. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `error in` | 入力 | error cluster |
| `UnitNum` | 出力 | I32 |
| `kind` | 出力 | I32 |
| `Status` | 出力 | `Status.ctl` |
| `TestError` | 出力 | `TestError.ctl` |
| `error out` | 出力 | error cluster |

##### 7. 配置する関数・SubVI

- `RS_DLL_GT150DeviceInit.vi`
- `Error_To_TestStatus.vi`
- 文字列定数`RAMScope`

##### 8. 配線順

1. `error in`を`RS_DLL_GT150DeviceInit.vi / error in`へ接続する。
2. Wrapperの`UnitNum`を本VIの`UnitNum`へ接続する。
3. Wrapperの`kind`を本VIの`kind`へ接続する。
4. Wrapperの`error out`を`Error_To_TestStatus.vi / error in`へ接続する。
5. 文字列定数`RAMScope`を同SubVIの`Device Name`へ接続する。
6. 同SubVIの`Status`、`TestError`、`error out`を本VIの同名出力へ接続する。

##### 9. 単体テスト

- 既存`error in.status=True`ではWrapperのCLFNが呼ばれず、UnitNum=0、kind=0、元エラー保持。
- GT170接続時はReturnCode、UnitNum、kindを記録する。正常値は実機確認待ち。

---

#### 2. `RAMScope_Init.vi`

##### 0. 実現したい機能とVIの責務

Unit全体を初期化し、SYSINFOを解析してRAM/CANモジュール番号とRAM Endianを取得し、RAMモジュールが存在するときだけPGT設定を実行する。PGTのSlotErr[16]も検査し、最初に見つかった非ゼロ値を標準error clusterへ変換する。

##### 1. 入力データの実体

```text
UnitNo
  → AllInit
  → GetSysInfoがU8[960]を返す
  → Parse_SYSINFO_Array.viが16レコードへ解析
  → RAM Module Found? / MdlNo_RAM / Endian_RAM
  → PGT_SetMdlConfigがI32[16] SlotErrを返す
```

##### 2. 出力データモデル

- `Module List`は`RAMScope_Module_Info.ctl`の一次元配列。
- `MdlNo_RAM`、`MdlNo_CAN`、`Endian_RAM`はParserの最終検出値。
- `SlotErr[16]`はPGT設定結果。PGT未実行時はI32ゼロ配列16要素。

##### 3. 前提条件・異常条件

```text
前段またはAllInit/GetSysInfo/Parserエラーあり
  → 後続PGTを呼ばない
RAM Module Found?=False
  → -700140
RAM Module Found?=True
  → PGT設定
PGT Wrapperエラーあり
  → SlotErr走査を行わずWrapperエラーを保持
PGT Wrapper正常かつSlotErrに非ゼロあり
  → -700141
```

##### 4. 処理アルゴリズム

```text
AllInit
GetSysInfo
Parse SYSINFO
if Parser error:
    Parser errorを返す
elif RAM Module Found? == False:
    RAM未検出エラーを返す
else:
    PGT_SetMdlConfig
    if PGT error:
        PGT errorを返す
    else:
        SlotErrを先頭から走査
        最初の非ゼロがあればSlotエラーを返す
        なければ正常
最後にError_To_TestStatus
```

##### 5. LabVIEW構造の選定理由

- error clusterを直列接続し、AllInit→GetSysInfo→Parserの順序を固定する。
- Parserエラーを元の原因として保持するため、`Parser error.status`のCaseをRAM Module Found? Caseより外側に置く。
- PGTをRAM未検出時に呼ばないため、`RAM Module Found?` Caseを使う。
- SlotErrは同じ判定を16要素へ適用するためForループを使う。
- 最初の非ゼロSlotだけを保持するため、Slot IndexとSlot ErrorのShift Registerを使う。

##### 6. 入出力

```text
入力 : UnitNo I32、Byte Order、error in
出力 : Module List、MdlNo_RAM、MdlNo_CAN、Endian_RAM、
       RAM Module Found?、CAN Module Found?、SlotErr[16]、
       Status、TestError、error out
```

##### 7. 配置する関数・SubVI

- `RS_DLL_GT150AllInit.vi`
- `RS_DLL_GT150GetSysInfo.vi`
- `Parse_SYSINFO_Array.vi`
- `RS_DLL_GT150PGT_SetMdlConfig.vi`
- `Error_To_TestStatus.vi`
- 名前でバンドル解除（Unbundle By Name）
- ケースストラクチャ（Case Structure）3個以上
- 配列初期化（Initialize Array）
- Forループ（For Loop）
- シフトレジスタ（Shift Register）3本
- 等しくない?（Not Equal?）
- 等しい?（Equal?）
- 複合演算（Compound Arithmetic）
- 文字列にフォーマット（Format Into String）2個
- 名前でバンドル（Bundle By Name）2個

##### 8. 配線順

###### A. AllInit、GetSysInfo、Parser

1. `UnitNo`と`error in`を`RS_DLL_GT150AllInit.vi`へ接続する。
2. AllInitの`error out`を`RS_DLL_GT150GetSysInfo.vi / error in`へ接続する。
3. `UnitNo`をGetSysInfo Wrapperへ接続する。
4. GetSysInfoの`SYSINFO Raw`を`Parse_SYSINFO_Array.vi / SYSINFO Raw`へ接続する。
5. `Byte Order`をParserへ接続する。
6. GetSysInfoの`error out`をParserの`error in`へ接続する。
7. ParserのModule List、MdlNo_RAM、MdlNo_CAN、Endian_RAM、Found Booleanを本VIの対応出力へ接続する。
8. Parserの`error out.status`を外側Case Structureのselectorへ接続する。

###### B. Trueケース（Parser error.status=True：Parserまでにエラーあり）

1. `RS_DLL_GT150PGT_SetMdlConfig.vi`とSlotErr走査処理を配置しない。
2. 配列初期化へI32定数`0`を`element`、I32定数`16`を`dimension size`として接続する。
3. I32ゼロ配列16要素を`SlotErr[16]`出力トンネルへ接続する。
4. Parserの`error out`をerror出力トンネルへそのまま接続する。

###### C. Falseケース（Parser error.status=False：Parser正常）

1. `RAM Module Found?`を内側Case Structureのselectorへ接続する。

###### D. Falseケース（RAM Module Found?=False：RAM未検出）

1. 配列初期化へI32定数`0`とI32定数`16`を接続し、I32ゼロ配列16要素を作る。
2. ゼロ配列を`SlotErr[16]`出力トンネルへ接続する。
3. 文字列にフォーマットへ次の全文を設定する。

```text
RAMScope_Init.vi: RAM monitor module was not found. PGT configuration was not executed. UnitNo=%d, MdlNo_RAM=%d
```

4. 1個目の`%d`へ`UnitNo` I32を接続する。
5. 2個目の`%d`へParserの`MdlNo_RAM` I32を接続する。
6. 名前でバンドルの基準クラスタへParserの正常な`error out`を接続する。
7. Boolean定数`True`を`status`へ接続する。
8. I32定数`-700140`を`code`へ接続する。
9. Format Into String出力を`source`へ接続する。
10. Bundle By Name出力をRAM Module Found? Caseのerror出力トンネルへ接続する。
11. このCaseにはPGT Wrapperを配置しない。

期待source例：

```text
RAMScope_Init.vi: RAM monitor module was not found. PGT configuration was not executed. UnitNo=0, MdlNo_RAM=-1
```

###### E. Trueケース（RAM Module Found?=True：RAM検出済み）

1. `RS_DLL_GT150PGT_SetMdlConfig.vi`を配置する。
2. `UnitNo`を同Wrapperの`UnitNo`へ接続する。
3. Parserの正常な`error out`を同Wrapperの`error in`へ接続する。
4. Wrapperの`SlotErr`を本VIの`SlotErr[16]`出力トンネルへ分岐する。
5. Wrapperの`error out.status`をPGT error Case Structureのselectorへ接続する。

###### F. Trueケース（PGT error.status=True：PGT Wrapperエラーあり）

1. SlotErr走査Forループを配置しない。
2. Wrapperの`error out`をerror出力トンネルへそのまま接続する。

###### G. Falseケース（PGT error.status=False：PGT Wrapper正常）

1. Forループを配置する。
2. Wrapperの`SlotErr[16]`をForループ左枠へ接続する。
3. 入力トンネルの指標付けを有効にし、1反復でSlotErr I32単体を処理する。
4. N端子は未配線にし、SlotErr配列の16要素で反復する。
5. Shift Registerを3本追加する。
6. 1本目の左外側へI32定数`-1`を接続し、`First Slot Index`とする。
7. 2本目の左外側へI32定数`0`を接続し、`First Slot Error`とする。
8. 3本目の左外側へWrapperの正常な`error out`を接続する。
9. 現在のSlotErr I32とI32定数`0`を等しくない?へ接続する。
10. `First Slot Index == -1`を作る。
11. 2条件をANDし、`First Nonzero?` Case Structureのselectorへ接続する。
12. Trueケース（First Nonzero?=True：最初の非ゼロ）で反復端子`i`をFirst Slot Index右内側へ、現在のSlotErrをFirst Slot Error右内側へ接続する。
13. Falseケース（First Nonzero?=False：非ゼロ未検出または既に検出済み）で各左内側の現在値を右内側へ接続する。初期値へ戻さない。
14. error Shift Registerは両Caseで左内側から右内側へそのまま接続する。
15. ループ右外側のFirst Slot IndexとI32定数`-1`を等しくない?へ接続し、`Slot Error Found?` Case Structureのselectorへ接続する。
16. Falseケース（Slot Error Found?=False：全Slot正常）でPGTの正常errorを出力する。
17. Trueケース（Slot Error Found?=True：SlotErr非ゼロあり）で次のFormat Stringを設定する。

```text
RAMScope_Init.vi: PGT module configuration reported a slot error. SlotIndex=%d, SlotError=%d
```

18. 1個目の`%d`へFirst Slot Index I32を接続する。
19. 2個目の`%d`へFirst Slot Error I32を接続する。
20. Bundle By Nameの基準クラスタへPGT Wrapperの正常な`error out`を接続する。
21. `status=True`、`code=I32 -700141`、`source=Format Into String出力`を接続する。
22. Bundle出力をSlot Error Found? Caseのerror出力トンネルへ接続する。
23. RAM Module Found? Case、Parser error Caseの順に、全error出力トンネルを外側へ接続する。
24. 最終errorを`Error_To_TestStatus.vi / error in`へ接続する。
25. 文字列定数`RAMScope`を`Device Name`へ接続する。
26. Status、TestError、error outを本VI出力へ接続する。

##### 9. 単体テスト

| 条件 | 期待結果 |
|---|---|
| Parser既存エラー | PGT未実行、SlotErrゼロ16要素、元エラー保持 |
| RAM Module Found?=False | code=-700140、PGT未実行、source全文一致 |
| RAM検出、SlotErr全0 | 正常 |
| SlotErr[3]=5 | code=-700141、sourceにSlotIndex=3、SlotError=5 |
| SlotErr[3]=5、SlotErr[7]=9 | 最初のSlot 3を返す |
| PGT Wrapperエラー | -700141で上書きせずWrapperエラー保持 |

---

#### 3. `RAMScope_Set_Cond.vi`

> **ロギング対応を含む最終順序**：`SetMeasCond → SetMeasCh → SetLoggingInfo`を固定する。SetMeasCondまたはSetMeasChは内部Bufferを再構成するため、保存用`logSize`と表示用`BuffSize`を設定するSetLoggingInfoを最後に実行する。


##### 0～5. 設計

Meas Config、Channel List、Module Log Configsを各BuilderでDLL用U8配列へ変換し、サイズが正しいことを確認してから、SetMeasCond→SetMeasCh→SetLoggingInfoの順に実行する。Builderエラーやサイズ不正時に後続APIを呼ばないため、error cluster直列接続とサイズ判定Caseを使う。

##### 6. 入出力

```text
入力 : UnitNo、MdlNo_RAM、Meas Config、Channel List、
       LogDevice、LimitHddSize、Module Log Configs、error in
出力 : ChNum、Status、TestError、error out
```

##### 7. 配置

`Build_MEASINFO_170_Raw.vi`、`Build_CHINFO_170_Raw.vi`、`Build_LOGINFO_Raw.vi`、3個のDLL Wrapper、Array Size、比較、Compound Arithmetic、Case Structure、Format Into String、Bundle By Name、`Error_To_TestStatus.vi`。

##### 8. 配線順

1. 3個のBuilderをMEASINFO→CHINFO→LOGINFOの順にerror clusterで直列接続する。
2. MEASINFO RawのArray Sizeが72、CHINFO Rawが`24×ChNum`、LOGINFO Rawが136か比較する。
3. 3条件をANDし、`Builder Size Valid?` Caseへ接続する。
4. Falseケース（Builder Size Valid?=False：Builder出力サイズ不正）では3個のDLL Wrapperを配置せず、次のFormat Stringを作る。

```text
RAMScope_Set_Cond.vi: Builder output size is invalid. MEASINFO=%d, CHINFO=%d, ExpectedCHINFO=%d, LOGINFO=%d
```

5. `%d`へ順にMEASINFO Array Size I32、CHINFO Array Size I32、`24×ChNum` I32、LOGINFO Array Size I32を接続する。
6. Bundle By Nameの基準へ最後のBuilderの正常errorを接続し、`status=True`、`code=I32 -700150`、`source=Format出力`を接続する。
7. Trueケース（Builder Size Valid?=True：サイズ正常）でSetMeasCond→SetMeasCh→SetLoggingInfoをerror clusterで直列接続する。
8. UnitNo、MdlNo、ChNum、各Raw配列を対応Wrapper端子へ接続する。
9. 最終errorを`Error_To_TestStatus.vi`へ接続し、Device Name=`RAMScope`とする。

##### 9. テスト

72、`24×ChNum`、136の正常値、各1byte不足、Builder既存エラー、ChNum=1/2を確認する。

---

#### 4. `RAMScope_Log_Start.vi`

##### 0～5. 設計

測定開始APIを1回呼ぶ1イベントVI。状態遷移は上位PoC/TestStandが管理する。

##### 6～8. 配線

1. `UnitNo`と`error in`を`RS_DLL_GT150MeasStart.vi`へ接続する。
2. Wrapper errorを`Error_To_TestStatus.vi`へ接続する。
3. Device Name=`RAMScope`とし、Status、TestError、error outを出力する。

##### 9. テスト

Set Cond後の正常開始、Set Cond前、二重開始、既存エラーを記録する。

---

#### `RAMScope_Read.vi`（GetBufferDataNum対応の最終仕様）

#### 0. 実現したい機能とVIの責務

測定中の表示用バッファから最新Packetを安全に取得し、実取得分だけをParserへ渡す。通信確認PoCとオンライン監視で使用する。停止後保存ログの取得は担当しない。

#### 1. 入力データの実体

```text
UnitNo I32
MdlNo_RAM I32
RequestedDataNum Limit I32
Channel List
Byte Order
Max Buffer Bytes I64
error in
```

#### 2. 出力データモデル

既存出力に次を追加する。

```text
AvailableDataNum I32
RequestedDataNum I32
Raw Buffer U8[]
DataNum I32
LostDataNum I32
Packets[]
Parsed Packet Count I32
Unused Byte Count I32
Status、TestError、error out
```

#### 3. 前提条件・異常条件

- Channel List非空。
- RequestedDataNum Limit > 0。
- Max Buffer Bytes > 0。
- I64計算後にI32上限以下。
- `0 <= DataNum <= RequestedDataNum`。

#### 4. 処理アルゴリズム

```text
AvailableDataNum = GetBufferDataNum(UnitNo, MdlNo_RAM)
RequestedDataNum = min(AvailableDataNum, RequestedDataNum Limit)

if RequestedDataNum == 0:
    空データを正常として返す
else:
    Packet Size = ChNum×4+12
    Required Bytes = RequestedDataNum×Packet Size
    上限検証
    GetBufferData
    Actual Bytes = DataNum×Packet Size
    RawをActual Bytesへ切詰め
    Parse
    Parsed CountとDataNumを照合
```

#### 5. LabVIEW構造の選定理由

GetBufferDataNumで実在Packet数を先に把握し、必要以上の配列確保を避ける。サイズ演算はI64、DLL配列長へ渡す直前だけI32へ変換する。

#### 6. 入出力と接続元・接続先

`PoC_RAMScope_Main.vi`はこのVIを1回または短時間反復して通信確認する。`PoC_RAMScope_Logging_Main.vi`はオンライン表示が必要な場合だけ呼び、正式保存データは停止後の`RAMScope_Read_Logging_Block.vi`から得る。

#### 7. 配置する関数およびSubVI

- `RS_DLL_GT150GetBufferDataNum.vi`。
- `RS_DLL_GT150GetBufferData.vi`。
- `RAMScope_Parse_Buffer.vi`。
- Min & Max、I64変換、Multiply、Add、Array Subset。
- Case Structure：Input Valid、No Data、Buffer Size Valid、Returned Count Valid、Parsed Count Match。
- `Error_To_TestStatus.vi`。

#### 8. 配線順

1. Channel ListのArray Size、Limit、Max Buffer Bytesを検証する。
2. GetBufferDataNumを呼ぶ。
3. AvailableDataNum負数なら`-700162`。
4. Min & Maxで`RequestedDataNum = min(max(AvailableDataNum,0), Limit)`を作る。
5. RequestedDataNum=0 CaseはDLL本体とParserを呼ばず安全出力。
6. ChNum、RequestedDataNumをI64化してRequired Bytesを求める。
7. `Required Bytes<=Max Buffer Bytes AND <=2147483647`を検証する。失敗は`-700163`。
8. GetBufferDataを呼ぶ。
9. DataNum範囲違反は`-700164`。
10. Array Subsetで`DataNum×Packet Size`へ切り詰める。
11. Parserへ渡す。
12. Parsed Count不一致は`-700165`。
13. 最終errorをError_To_TestStatusへ接続する。

#### 9. 単体テスト

- AvailableDataNum=0。
- LimitよりAvailableが少ない。
- LimitよりAvailableが多い。
- Required Bytesが上限超過。
- DataNumが要求数未満。
- Parser件数一致／不一致。

---

#### 6. `RAMScope_Release.vi`

> **ロギング対応を含む呼出位置**：通信確認PoCではStop後に呼ぶ。ロギングPoCでは`Log Stop → 全MeasNo／BlockNo取得 → TDMS Append完了 → Release`の順とし、保存ログ取得前にBufferを破棄しない。


##### 0～5. 設計

測定停止後のアイドル状態で保存用データバッファを解放する。測定中に発行不可なので、Readの直後へ内包しない。

##### 6～8. 配線

1. `UnitNo`と`error in`を`RS_DLL_GT150ReleaseBufferData.vi`へ接続する。
2. Wrapper errorを`Error_To_TestStatus.vi`へ接続する。
3. Device Name=`RAMScope`とする。

##### 9. テスト

オフライン、測定中、MeasStop後アイドル、二重Releaseを記録する。本番では`MeasStop成功 → Release → Close`とする。

---

#### 7. `RAMScope_Log_Stop.vi`

##### 0～5. 設計

測定を停止してアイドル状態へ移す。Releaseと分離し、Stop失敗時にReleaseを呼ばない判断を上位へ残す。

##### 6～8. 配線

1. `UnitNo`と`error in`を`RS_DLL_GT150MeasStop.vi`へ接続する。
2. Wrapper errorを`Error_To_TestStatus.vi`へ接続する。
3. Device Name=`RAMScope`とする。

##### 9. テスト

正常停止、未開始、二重停止、既存エラーを確認する。Cleanup専用経路では前段エラーがあってもStopを試す設計を別途用意する。

---

#### 8. `RAMScope_Close.vi`

##### 0～5. 設計

前段エラーがあってもDeviceExitを試み、最初のエラーを失わないCleanup VIである。正式方式はエラーをマージ（Merge Errors）へ固定する。Case Structureまたは他の相当処理を選択肢として残さない。

##### 6～8. 配線順

1. 本VIの`error in`を2方向へ分岐する。
2. 1本目を`Original Error`として、エラーをマージ（Merge Errors）の**上側1個目のerror入力**へ接続する。
3. 2本目を`RS_DLL_GT150DeviceExit.vi / error in`へ接続する。
4. Wrapperの`DeviceExit error`をMerge Errorsの**下側2個目のerror入力**へ接続する。
5. Merge Errors出力を`Final Error`として`Error_To_TestStatus.vi / error in`へ接続する。
6. 文字列定数へ全文`RAMScope`を入力し、同SubVIの`Device Name`へ接続する。
7. `Error_To_TestStatus.vi / Status`を本VIの`Status`出力へ接続する。
8. 同SubVIの`TestError`を本VIの`TestError`出力へ接続する。
9. 同SubVIの`error out`を本VIの`error out`へ接続する。

```text
Original Error ───────────────→ Merge Errors 上側入力1
error in → DeviceExit Wrapper → Merge Errors 下側入力2
Merge Errors出力              → Error_To_TestStatus.vi
```

上側と下側を逆にしない。両方にエラーがある場合も、前段で最初に発生したOriginal Errorを保持する。

##### 9. テスト

正常Close、既存エラー付きClose、DeviceExitエラー、両方エラー、二重Close、Close後の再Connectを確認する。詳細な配置場所、全端子および期待結果は直後の`10.11.9`を使用する。

### 10.11.9 `RAMScope_Close.vi`補足詳細

#### 0. 実現したい機能とVIの責務

`RAMScope_Close.vi`は、前段処理でエラーが発生していても`RAMScopeGT150DeviceExit()`を試行し、RAMScopeVP APIとの接続を終了するCleanup VIである。

同時に、前段で最初に発生したエラーをDeviceExitの結果で上書きしない。

```text
前段エラーあり
  → DeviceExitは実行する
  → 最終errorには前段エラーを残す

前段エラーなし
  → DeviceExitを実行する
  → DeviceExitが失敗した場合はDeviceExitエラーを返す
```

---

#### 1. 入力データの実体

本VIが扱うerror clusterは2個である。

| 名前 | 接続元 | 意味 |
|---|---|---|
| `Original Error` | 本VIの`error in` | Closeより前に発生したエラーまたは警告 |
| `DeviceExit Error` | `RS_DLL_GT150DeviceExit.vi / DeviceExit error` | DeviceExit呼出し自体の結果 |

`RS_DLL_GT150DeviceExit.vi`はCleanup用Wrapperである。入力された`error in`を内部で保持したまま、CLFNへ渡すerror wireだけをエラークリア（Clear Errors）して、前段エラーの有無にかかわらずDeviceExitを呼び出す。

---

#### 2. 出力データモデル

```text
Final Error
  → Error_To_TestStatus.vi
      ├─ Status
      ├─ TestError
      └─ error out
```

`Final Error`は次の優先順位で決定する。

```text
1. Original Errorにエラーがある場合はOriginal Error
2. Original Errorが正常でDeviceExit Errorにエラーがある場合はDeviceExit Error
3. 両方正常なら正常error cluster
```

警告についてはエラーをマージ（Merge Errors）の標準動作に従う。実エラーが存在する場合は警告より実エラーを優先する。

---

#### 3. 前提条件・異常条件

| Original Error | DeviceExit Error | Final Error |
|---|---|---|
| 正常 | 正常 | 正常 |
| 正常 | エラー | DeviceExit Error |
| エラー | 正常 | Original Error |
| エラー | エラー | Original Error |

重要なのは、どの組み合わせでも`RS_DLL_GT150DeviceExit.vi`を実行することである。

---

#### 4. 処理アルゴリズム

```text
Original Error = error in

DeviceExit Error = RS_DLL_GT150DeviceExit.vi(Original Error)

Final Error = Merge Errors(
    input 0 = Original Error,
    input 1 = DeviceExit Error
)

Status, TestError, error out
    = Error_To_TestStatus.vi(Final Error, "RAMScope")
```

---

#### 5. LabVIEW構造の選定理由

##### 5.1 エラーをマージ（Merge Errors）を使う理由

エラーをマージ（Merge Errors）は、複数のerror clusterを1個へまとめる関数である。

今回、上側の1個目の入力へ`Original Error`を接続し、下側の2個目の入力へ`DeviceExit Error`を接続する。これにより、両方にエラーがある場合は先に接続したOriginal Errorを保持できる。

また、Merge Errorsは両方の入力が到着してから実行される。このデータフローにより、`RAMScope_Close.vi`が終了する前にDeviceExit Wrapperの実行完了を待つことができる。

##### 5.2 Case Structureを使用しない理由

Case Structureでもerror clusterを選択できるが、選択されたCaseで`DeviceExit Error`を使用しない配線にすると、DeviceExit完了を待つ依存関係が図から読み取りにくくなる。

本VIの目的は「DeviceExitを必ず試行し、その後で最初のエラーを返す」ことであるため、2本のerror wireを直接Merge Errorsへ入れる構成を正式方式とする。

---

#### 6. 入出力

| 端子 | 方向 | 型 | 説明 |
|---|---|---|---|
| `error in` | 入力 | error cluster | Close前までのOriginal Error |
| `Status` | 出力 | `Status.ctl` | TestStand判定用ステータス |
| `TestError` | 出力 | `TestError.ctl` | 機器名、code、message等 |
| `error out` | 出力 | error cluster | Original Errorを優先して統合したFinal Error |

`DeviceExit Error`と`Final Error`はブロックダイアグラム内のワイヤ名であり、通常はフロントパネル端子にしない。

---

#### 7. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所・追加方法 |
|---:|---|---|---|
| 1 | `RS_DLL_GT150DeviceExit.vi` | SubVI | `30_RAMScope\10_DLL_Wrapper` |
| 1 | エラーをマージ | Merge Errors | プログラミング → ダイアログ＆ユーザインタフェース |
| 1 | `Error_To_TestStatus.vi` | SubVI | 共通エラー処理フォルダ |
| 1 | 文字列定数 | String Constant | プログラミング → 文字列 |

エラーをマージ（Merge Errors）がパレットで見つからない場合は、ブロックダイアグラムで`Ctrl + Space`を押し、Quick Dropへ`Merge Errors`と入力して配置する。

---

#### 8. 配線順

##### A. Original Errorのワイヤを分岐する

作業領域：ブロックダイアグラム左側。

1. 本VIの`error in`端子から右方向へerror wireを引く。
2. error wireを2方向へ分岐する。
3. 上側の分岐を`Original Error`として、後でエラーをマージ（Merge Errors）の上側入力へ接続する。
4. 下側の分岐を`RS_DLL_GT150DeviceExit.vi / error in`へ接続する。

この分岐により、同じ前段error clusterを、保持用とDeviceExit Wrapper入力用の両方へ渡す。

##### B. DeviceExit Wrapperを配置・配線する

1. `RS_DLL_GT150DeviceExit.vi`をOriginal Error分岐の右側へ配置する。
2. A-4で作った下側error wireをWrapperの`error in`へ接続する。
3. Wrapperの`DeviceExit error`出力から右方向へerror wireを引く。
4. このワイヤへ`DeviceExit Error`というラベルを付ける。
5. Wrapperの`API ReturnCode`はPublic VIの正式出力にしない。デバッグ時に確認したい場合だけ表示器を作成する。

`RS_DLL_GT150DeviceExit.vi`内部では前段errorをクリアしてCLFNを呼ぶため、本VI側にエラークリア（Clear Errors）を追加しない。

##### C. エラーをマージ（Merge Errors）を配置する

1. `RS_DLL_GT150DeviceExit.vi`の右側へエラーをマージ（Merge Errors）を配置する。
2. Merge Errorsが2入力表示になっていることを確認する。
3. 入力が1個しか見えない場合は、ノードの下辺を下方向へドラッグして2入力へ広げる。
4. A-3の`Original Error`をMerge Errorsの**上側1個目のerror入力**へ接続する。
5. B-3の`DeviceExit Error`をMerge Errorsの**下側2個目のerror入力**へ接続する。
6. Merge Errorsの右側出力へ`Final Error`というワイヤラベルを付ける。

配線の見取り図：

```text
error in
  ├──────────────────────────────→ Merge Errors 上側入力 1
  │                                  Original Error
  │
  └→ RS_DLL_GT150DeviceExit.vi
         error in
            ↓
         DeviceExit error ─────────→ Merge Errors 下側入力 2
                                      DeviceExit Error

Merge Errors出力
  → Final Error
```

この接続順を逆にしない。DeviceExit Errorを上側へ接続すると、両方がエラーの場合にCleanupエラーが前段エラーより先に選ばれる可能性がある。

##### D. Error_To_TestStatus.viへ接続する

1. `Error_To_TestStatus.vi`をMerge Errorsの右側へ配置する。
2. Merge Errorsの`Final Error`を`Error_To_TestStatus.vi / error in`へ接続する。
3. 文字列定数を配置し、全文として次を入力する。

```text
RAMScope
```

4. 文字列定数`RAMScope`を`Error_To_TestStatus.vi / Device Name`へ接続する。
5. 同SubVIの`Status`を本VIの`Status`出力へ接続する。
6. 同SubVIの`TestError`を本VIの`TestError`出力へ接続する。
7. 同SubVIの`error out`を本VIの`error out`へ接続する。

完成した主要error wireは次の形になる。

```text
error in ─┬──────────────────────────────┐
          │                              ↓
          └→ DeviceExit Wrapper ─→ Merge Errors ─→ Error_To_TestStatus.vi
                                         ↑
                          Original Error ─┘
```

---

#### 9. 単体テスト

##### 9.1 テスト1：前段正常、DeviceExit正常

```text
Original Error.status = False
Original Error.code   = 0
DeviceExit Error      = 正常
```

期待結果：

```text
Final Error.status = False
Final Error.code   = 0
Status             = OK
```

##### 9.2 テスト2：前段エラーあり、DeviceExit正常

`error in`へ次のダミーエラーを入力する。

```text
status = True
code   = -700999
source = RAMScope_Close.vi unit test: original error
```

期待結果：

```text
DeviceExitは実行される
Final Error.code   = -700999
Final Error.source = RAMScope_Close.vi unit test: original error
```

##### 9.3 テスト3：前段正常、DeviceExitエラー

DeviceExit Wrapperを単体試験用ダミーSubVIへ一時的に置き換えるか、WrapperのテストVIで次のDeviceExit Errorを生成する。

```text
status = True
code   = -700998
source = RAMScope_Close.vi unit test: DeviceExit error
```

期待結果：

```text
Final Error.code   = -700998
Final Error.source = RAMScope_Close.vi unit test: DeviceExit error
```

##### 9.4 テスト4：前段エラーとDeviceExitエラーが両方存在

```text
Original Error.code = -700999
DeviceExit Error.code = -700998
```

期待結果：

```text
Final Error.code = -700999
```

前段で最初に発生したOriginal Errorが保持されることを確認する。

##### 9.5 実機Cleanup試験

1. Connect成功後にCloseを実行し、再度Connectできることを確認する。
2. Connect後、意図的なローカルエラーを`error in`へ入れてCloseを実行する。
3. Original Errorが保持されても、次回Connectが成功することを確認する。
4. Closeを2回実行した場合のDeviceExit ReturnCodeを記録する。

---

#### 10. 完成チェックリスト

- [ ] `error in`がOriginal Error保持用とDeviceExit Wrapper用へ分岐されている。
- [ ] DeviceExit Wrapperは前段エラーがあっても実行される構成である。
- [ ] Merge Errors上側入力がOriginal Errorである。
- [ ] Merge Errors下側入力がDeviceExit Errorである。
- [ ] Merge Errors出力がError_To_TestStatus.viへ接続されている。
- [ ] Device Nameへ文字列全文`RAMScope`が接続されている。
- [ ] 前段エラーとDeviceExitエラーが両方あるテストで前段エラーが保持される。
- [ ] 前段エラーがある状態でもDeviceExitが完了し、再接続できる。

---

### 10.11.9 停止後保存ログ取得用の追加公開API

#### 10.11.9.1 `RAMScope_Get_Log_Summary.vi`

#### 0. 責務

Stop後の保存ログ列挙に必要なGapTimeMsとMeasNumを取得する。

#### 1. 入力データ

UnitNo、error in。

#### 2. 出力

GapTimeMs U32、MeasNum I32、Status、TestError、error out。

#### 3. 条件

Log Stop成功後、Release前。MeasNum<0は`-700170`。

#### 4. アルゴリズム

GetGapTime → GetMeasNum → MeasNum負数検証 → Error_To_TestStatus。

#### 5. 構造理由

error wireでAPI順序を固定し、負数だけCase Structureで止める。

#### 6. 入出力と接続

Logging PoCのStop直後に呼び、MeasNumを外側For LoopのNへ接続する。

#### 7. 配置するSubVI

`RS_DLL_GT150GetGapTime.vi`、`RS_DLL_GT150GetMeasNum.vi`、Less Than 0?、Case Structure、Format Into String、Bundle By Name、Error_To_TestStatus.vi。

#### 8. 配線順

1. GetGapTimeのerror outをGetMeasNumへ接続する。
2. MeasNum<0をCase selectorへ接続する。
3. Trueケース（MeasNum<0=True）でsource全文を作る。

```text
RAMScope_Get_Log_Summary.vi: MeasNum must not be negative. MeasNum=%d
```

4. status=True、code=-700170、sourceをBundle By Nameする。
5. FalseケースはWrapper errorを通す。
6. 最終errorをError_To_TestStatusへ接続する。

#### 9. テスト

MeasNum 0、1、複数、負数ダミー、GapTime APIエラー。

---

#### 10.11.9.2 `RAMScope_Get_Block_Count.vi`

#### 0. 責務

指定MeasNoのBlockNumを取得し、番号と戻り件数を検証する。

#### 1. 入力

UnitNo、MeasNo、error in。

#### 2. 出力

BlockNum、Status、TestError、error out。

#### 3. 条件

MeasNo>=0。BlockNum>=0。

#### 4. アルゴリズム

入力検証 → GetBlockNum → 戻り値検証 → Error_To_TestStatus。

#### 5. 構造理由

DLLへ不正番号を渡す前のCaseと、戻り値検証Caseを分ける。

#### 6. 接続

Logging PoC外側For LoopのiをMeasNoへ接続し、BlockNumを内側For LoopのNへ接続する。

#### 7. 配置

Greater Or Equal 0?、Case Structure×2、Wrapper、Format Into String、Bundle By Name、Error_To_TestStatus。

#### 8. 配線順

- MeasNo<0：Wrapper未実行、code=-700171。

```text
RAMScope_Get_Block_Count.vi: MeasNo must not be negative. MeasNo=%d
```

- Wrapper正常後BlockNum<0：code=-700172。

```text
RAMScope_Get_Block_Count.vi: BlockNum must not be negative. MeasNo=%d, BlockNum=%d
```

- 正常時はBlockNumとerrorを通す。

#### 9. テスト

MeasNo -1、0、末尾、BlockNum 0、1、複数、負数ダミー。

---

#### 10.11.9.3 `RAMScope_Read_Logging_Block.vi`

#### 0. 責務

指定MeasNo、BlockNoの保存Packet数を取得し、必要領域を確保してデータ本体を読み、実取得分へ切り詰め、既存Parserで1Blockを解析する。

#### 1. 入力データ

UnitNo、MdlNo_RAM、MeasNo、BlockNo、Channel List、Byte Order、Max Buffer Bytes I64、error in。

#### 2. 出力データモデル

```text
AvailableDataNum I32
RequestedDataNum I32
DataNum I32
LostDataNum I32
Raw Buffer U8[]
Packets RAMScope_Packet.ctl[]
Parsed Packet Count I32
Unused Byte Count I32
Status、TestError、error out
```

#### 3. 前提条件・異常条件

```text
ChNum>=1
MeasNo>=0
BlockNo>=0
Max Buffer Bytes>0
AvailableDataNum>=0
0<=DataNum<=RequestedDataNum
Required Bytes<=Max Buffer Bytes
Required Bytes<=2147483647
Parsed Packet Count==DataNum
```

#### 4. 処理アルゴリズム

```text
AvailableDataNum = GetLoggingDataNum
if AvailableDataNum == 0:
    空データを正常返却
else:
    RequestedDataNum = AvailableDataNum
    Packet Size = ChNum×4+12
    Required Bytes = RequestedDataNum×Packet Size  // I64
    上限検証
    GetLoggingData
    DataNum範囲検証
    Actual Bytes = DataNum×Packet Size
    Array SubsetでRaw切詰め
    Parse Buffer
    Parsed Count照合
```

#### 5. LabVIEW構造の選定理由

1Blockだけを扱い、MeasNo／BlockNoの反復はLogging PoCまたはTestStandへ任せる。これによりPublic VI内で巨大な全ログ配列を保持しない。

`RAMScopeGT150GetLoggingData()`で読み出したPacketはAPI内部バッファから削除されるため、取得後は同じBlockを再取得できる前提にしない。本VIが返したRaw BufferとPacketsを次Block取得前にTDMSへ保存する。

#### 6. 入出力と接続

Logging PoC内側For LoopからMeasNoとBlockNoを受け、出力Packetsを`RAMScope_File_Log_Append.vi`へ直結する。

#### 7. 配置する関数およびSubVI

- `RS_DLL_GT150GetLoggingDataNum.vi`。
- `RS_DLL_GT150GetLoggingData.vi`。
- `RAMScope_Parse_Buffer.vi`。
- Array Size、I64変換、Multiply、Add、Array Subset。
- Case Structure 5個以上。
- Format Into String、Bundle By Name、Error_To_TestStatus.vi。

#### 8. 配線順

1. 入力検証Case。失敗は`-700173`。

```text
RAMScope_Read_Logging_Block.vi: Input is invalid. ChNum=%d, MeasNo=%d, BlockNo=%d, MaxBufferBytes=%lld
```

2. GetLoggingDataNumを呼ぶ。
3. AvailableDataNum<0は`-700174`。
4. AvailableDataNum=0は本体DLLとParserを呼ばず空配列。
5. I64でRequired Bytesを計算する。
6. 上限違反は`-700175`。

```text
RAMScope_Read_Logging_Block.vi: Required buffer size is invalid or exceeds the limit. RequiredBytes=%lld, MaxBufferBytes=%lld, AvailableDataNum=%d, PacketSize=%lld
```

7. RequestedDataNum=AvailableDataNumをGetLoggingDataのpDataNum左端子へ渡す。
8. `0<=DataNum<=RequestedDataNum`を検証する。違反は`-700176`。
9. Raw BufferをActual Bytesへ切り詰める。
10. Parserへ渡す。
11. Parsed Count不一致は`-700177`。
12. 各Caseの全出力トンネルを配線し、Use default if unwiredを使わない。
13. 最終errorをError_To_TestStatusへ接続する。

#### 9. 単体テスト

Channel List空、番号負数、DataNum=0、上限超過、DataNum要求未満、DataNum範囲外、Parser不一致、LostDataNum非ゼロ。

---

## 10.12 LabVIEW側TDMS保存VI

### 10.12.1 TDMS構造

```text
Root Properties
  TestName
  MeasurementStartTime
  A2LFileName
  UnitNo
  MdlNo_RAM
  ByteOrder
  ChannelCount
  PacketSize
  GapTimeMs

Group: RAMScope_Meas0000_Block0000
  Properties
    MeasNo
    BlockNo
    RequestedDataNum
    DataNum
    LostDataNum
    PacketSize

  Channels
    Time_s
    Time_Raw
    Flag_Raw
    Status
    Skip
    LogTrigger
    Dummy
    EventBits
    DataLost
    <Channel Name 0>          Engineering Value DBL
    <Channel Name 0>__Raw     Raw Slot U32
    <Channel Name 1>          Engineering Value DBL
    <Channel Name 1>__Raw     Raw Slot U32
    ...
```

Boolean状態は解析ツール互換性を優先し、TDMS上ではU8の0／1として保存する。測定値はEngineering Value DBLとRaw Slot U32を別チャンネルで保存し、Address、Size、Sign、Scale、Offset、UnitはChannel Propertyへ保存する。

---

### 10.12.2 `RAMScope_File_Log_Open.vi`

#### 0. 責務

出力先TDMSを開き、後続VIへFile Referenceを返す。

#### 1. 入力

File Path、Overwrite?、error in。

#### 2. 出力

TDMS File Ref、File Open?、Status、TestError、error out。

#### 3. 条件

空Path不可。既存ファイルかつOverwrite?=Falseは`-700178`。

#### 4. アルゴリズム

Path検証 → Exists? → Overwrite Case → TDMS Open → File Open?更新。

#### 5. 構造理由

既存ファイル動作をCaseで明示し、暗黙上書きをしない。

#### 6. 入出力と接続

Logging PoCのSet Cond成功後、Log Start前に呼ぶ。File RefはPoCの通常ワイヤとCleanup Caseへ通す。

#### 7. 配置

Empty String/Path?、Check if File or Folder Exists、Case Structure、TDMS Open、Error_To_TestStatus。

#### 8. 配線順

- Path不正または上書き拒否時：TDMS Open未実行、Not A Refnum相当、安全なFile Open? False。
- 正常時：Operation=`create or replace`、File Open?=`NOT(error.status)`。
- source全文：

```text
RAMScope_File_Log_Open.vi: Output file already exists and overwrite is disabled. Path=%s
```

#### 9. テスト

新規Path、既存Path上書き有／無、書込権限なし、既存error。

---

### 10.12.3 `RAMScope_File_Log_Write_Metadata.vi`

#### 0. 責務

TDMS Rootへ試験全体情報とチャンネル定義を記録し、後のMF4変換で信号名、型、単位、換算情報を再構成できるようにする。

#### 1. 入力

TDMS Ref、TestName、Start Time、A2L File Name、UnitNo、MdlNo_RAM、Byte Order、Channel List、GapTimeMs、error in。

#### 2. 出力

同じTDMS Ref、Status、TestError、error out。

#### 3. 条件

File Ref有効、Channel List非空。A2L File Nameは空を許容する。

#### 4. アルゴリズム

Root Properties書込 → Channel List For Loopで`Channel_%03d_*`形式のRoot Propertyを書込 → Flush任意。

#### 5. 構造理由

チャンネルごとに同じProperty処理を行うためFor Loop。

#### 6. 入出力と接続

Log Stop後の`RAMScope_Get_Log_Summary.vi`成功直後、最初のBlockをTDMSへAppendする前に1回だけ呼ぶ。MeasurementStartTimeはLog Start直前に取得した値、GapTimeMsはSummary出力を接続する。

#### 7. 配置

TDMS Set Properties、For Loop、Unbundle By Name、Format Into String、Error_To_TestStatus。

#### 8. 配線順

1. RootへTestName等を設定する。
2. Channel Listを自動インデックスでFor Loopへ入れる。
3. 各チャンネルの情報をRoot Propertyへ次の固定キー形式で保存する。

```text
Channel_000_Name
Channel_000_Address
Channel_000_Size
Channel_000_Sign
Channel_000_Scale
Channel_000_Offset
Channel_000_Unit
```

4. `%03d`へChannel Indexを接続し、キー名を一意にする。
5. 既存error時は書込をスキップしてRefを通す。
6. Property書込失敗は元のTDMS errorを保持する。

#### 9. テスト

日本語TestName、空A2L名、複数Channel、書込失敗、既存error。

---

### 10.12.4 `RAMScope_File_Log_Append.vi`

#### 0. 責務

1Block分の解析済みPacketsと取得状態を、Block固有Groupへ追記する。

#### 1. 入力

TDMS Ref、MeasNo、BlockNo、RequestedDataNum、DataNum、LostDataNum、PacketSize、Packets、Channel List、Flush After Write?、error in。

#### 2. 出力

TDMS Ref、Written Packet Count、Status、TestError、error out。

#### 3. 条件

`Array Size(Packets)==DataNum`。Channel Listの順番がPackets内Channel Valuesと一致する。

#### 4. アルゴリズム

```text
Group Name = Format("RAMScope_Meas%04d_Block%04d")
Group Propertiesを書込
Packet共通配列を書込
for ChannelIndex:
    for PacketIndex:
        Packets[PacketIndex].Channel Values[ChannelIndex].Engineering Valueを抽出
    Channel NameでEngineering Value DBLをTDMS Write
    Channel Name + "__Raw"でRaw Slot U32をTDMS Write
    Address/Size/Sign/Scale/Offset/UnitをEngineering Value Channel Propertyへ保存
if Flush After Write?: TDMS Flush
```

#### 5. 構造理由

Block単位で即時保存し、全Blockをメモリへ蓄積しない。Channel×Packetの2重For Loopで列方向配列を作る。

#### 6. 入出力と接続

`RAMScope_Read_Logging_Block.vi`の直後に配置し、次Block取得前に完了させる。

#### 7. 配置

Format Into String、TDMS Set Properties、TDMS Write、For Loop×2、Index Array、Bundle/Unbundle、Select、TDMS Flush、Error_To_TestStatus。

#### 8. 配線順

1. `Array Size(Packets)==DataNum`を検証する。不一致は`-700180`。
2. Group Nameを`RAMScope_Meas%04d_Block%04d`で作る。
3. Group PropertyへMeasNo、BlockNo、RequestedDataNum、DataNum、LostDataNum、PacketSizeを設定する。
4. PacketsからTime、Flag各fieldの一次元配列を作り、それぞれTDMS Writeする。
5. BooleanはSelectでU8 1／0へ変換する。
6. Channel外側For LoopでEngineering Value DBL配列とRaw Slot U32配列を作る。
7. Engineering ValueはChannel名、Raw Slotは`<Channel名>__Raw`でTDMS Writeする。
8. Channel名が空の場合は`Channel_%03d`を使用する。
9. 同名Channelがある場合はIndexを付加して一意化する。
10. Address、Size、Sign、Scale、Offset、UnitをEngineering Value Channel Propertyへ設定する。
11. Flush入力がTrueならTDMS Flushする。
12. Written Packet Count=DataNumを返す。

source全文：

```text
RAMScope_File_Log_Append.vi: Packet count does not match DataNum. PacketCount=%d, DataNum=%d, MeasNo=%d, BlockNo=%d
```

#### 9. テスト

DataNum=0、1、複数、同名Channel、空Channel名、日本語名、Lost非ゼロ、Flush有／無、件数不一致。

---

### 10.12.5 `RAMScope_File_Log_Close.vi`

#### 0. 責務

前段errorの有無にかかわらずTDMS FlushとCloseを試行し、最初のerrorを保持するCleanup VI。

#### 1. 入力

TDMS Ref、File Open?、Original error。

#### 2. 出力

File Open? False、Status、TestError、Final error。

#### 3. 条件

File Open?=FalseならTDMS関数を呼ばない。Trueなら前段errorをClearしたCleanup用wireでFlush、Closeする。

#### 4. アルゴリズム

```text
if File Open?:
    Cleanup Error = Clear Errors(Original Error)
    TDMS Flush
    TDMS Close
    Final Error = Merge Errors(Original Error, Cleanup Error)
else:
    Final Error = Original Error
```

#### 5. 構造理由

File Open?をselectorとするCase Structure。Original Errorを優先するMerge Errors。

#### 6. 入出力と接続

Logging PoCの通常終了とCleanupの両方から呼ぶ。

#### 7. 配置

Case Structure、Clear Errors、TDMS Flush、TDMS Close、Merge Errors、Error_To_TestStatus。

#### 8. 配線順

TrueケースでOriginal Errorを保持用とCleanup用へ分岐する。Cleanup用だけClear Errorsし、Flush→Close。Merge Errorsの上側へOriginal、下側へClose Error。FalseケースはRefを使用せずOriginalを通す。両CaseでFile Open? Falseを出力する。

#### 9. テスト

正常Close、前段error付きClose、無効Ref、二重Close、Flush error、Close error。

---

## 10.13 通信確認PoC・ロギングPoC・TestStand

### 10.13.1 `PoC_RAMScope_Main.vi`

#### 0. 実現したい機能とVIの責務

`PoC_RAMScope_Main.vi`は、TestStandを使用せず、RAMScope公開APIを次の順で1回実行する通信確認用PoCである。

本VIへTDMS File Ref、MeasNo／BlockNoの二重For Loop、`GetLoggingData()`による停止後保存ログ回収を追加しない。ロギング検証は`PoC_RAMScope_Logging_Main.vi`へ分離する。

```text
Connect
  → Init
  → Set Cond
  → Log Start
  → Wait
  → Read
  → Log Stop
  → Release
  → Close
```

途中でエラーが発生しても、すでに成功した処理を状態として保持し、必要なCleanupだけを実行する。

```text
Connect成功後にエラー
  → Closeが必要

Log Start成功後にエラー
  → Stop、Release、Closeが必要

Stop成功後にエラー
  → Release、Closeが必要
```

---

#### 1. 入力データの実体

通常処理には2本の主要ワイヤを流す。

| ワイヤ | 型 | 意味 |
|---|---|---|
| `Main Error` | error cluster | 各公開APIを順番に実行するための通常error wire |
| `PoC State` | `RAMScope_PoC_State.ctl` | どの処理が正常終了したかを保持する状態クラスタ |

`PoC State`は現在の機器状態を直接読み取るものではなく、このPoC内で各処理が成功した履歴を保持する。

---

#### 2. 出力データモデル

##### 2.1 `RAMScope_PoC_State.ctl`

次のtypedefクラスタを作成する。

```text
30_RAMScope\00_Common\RAMScope_PoC_State.ctl
```

| フィールド | 型 | Trueの意味 |
|---|---|---|
| `Connected?` | Boolean | `RAMScope_Connect.vi`が正常終了した |
| `Measurement Started?` | Boolean | `RAMScope_Log_Start.vi`が正常終了した |
| `Stopped?` | Boolean | 通常経路またはCleanup経路の`RAMScope_Log_Stop.vi`が正常終了した |
| `Released?` | Boolean | `RAMScope_Release.vi`が正常終了した |
| `File Open?` | Boolean | 既存ctlとの互換性維持用予約項目。通信確認用PoCでは常にFalseとし、TDMS VIへ接続しない |

`Measurement Started?`はStop後もTrueのままとする。これは「現在測定中」という意味ではなく、「MeasStartが成功した履歴」である。

現在測定中かどうかは次で判定する。

```text
Measurement Active?
= Measurement Started? AND NOT Stopped?
```

---

#### 3. 前提条件・異常条件

```text
Connect失敗
  Connected?=False
  Init以降はerror wireによりスキップ
  Closeも呼ばない

Connect成功、Start前に失敗
  Connected?=True
  Measurement Started?=False
  StopとReleaseは呼ばない
  Closeだけ呼ぶ

Start成功後に失敗
  Measurement Started?=True
  Stopped?=False
  Cleanup Stopを試す

Stop成功
  Stopped?=True
  Releaseを試す

Release成功
  Released?=True
  Releaseを再度呼ばない
```

---

#### 4. 処理アルゴリズム

```text
State = all False
Main Error = error in

Connect
Connected? = NOT Connect Error.status

Init
Set Cond

Log Start
Measurement Started?
    = Connected? AND NOT Log Start Error.status

Wait
Read

Normal Log Stop
Stopped?
    = Measurement Started? AND NOT Log Stop Error.status

if Stopped? AND NOT Released?:
    Release
    Released? = NOT Release Error.status

Cleanup:
    Original Error = Main Error

    if Measurement Started? AND NOT Stopped?:
        Clear Errors
        Cleanup Log Stop
        Stopped? = NOT Cleanup Stop Error.status
        Main Error = Merge Errors(Original Error, Cleanup Stop Error)

    if Stopped? AND NOT Released?:
        Clear Errors
        Cleanup Release
        Released? = NOT Cleanup Release Error.status
        Main Error = Merge Errors(Main Error, Cleanup Release Error)

    if Connected?:
        RAMScope_Close.vi(Main Error)
```

---

#### 5. LabVIEW構造の選定理由

##### 5.1 状態クラスタを使う理由

4本以上のBooleanを別々に左から右へ引くと、配線が交差し、どの時点の値をCleanupが参照しているか分かりにくくなる。

```text
RAMScope_PoC_State.ctl
  → Bundle By Nameで1項目だけ更新
  → 他の項目は前の値を保持
  → 更新後クラスタを次の処理へ渡す
```

##### 5.2 Shift Registerを使用しない理由

このPoCは1回だけ左から右へ実行するため、外側Whileループを必要としない。したがって、状態クラスタを通常ワイヤで流す。

将来、ReadをWhileループで繰り返す場合は、同じ`RAMScope_PoC_State.ctl`をWhileループのShift Registerへ接続する。

##### 5.3 `error out.status`から成功判定を作る理由

公開APIは正常終了時に`error out.status=False`を返す。

```text
Succeeded? = NOT(error out.status)
```

前段エラーにより公開APIがスキップされた場合も`error out.status=True`が保持されるため、成功フラグが誤ってTrueにならない。

---

#### 6. 主な入出力

```text
入力：
  Byte Order
  Meas Config
  Channel List
  Module Log Configs
  MaxDataNum
  Wait Time
  error in

出力：
  UnitNum
  kind
  Module List
  MdlNo_RAM
  MdlNo_CAN
  Endian_RAM
  Raw Buffer
  DataNum
  LostDataNum
  Packets
  Final State
  Status
  TestError
  error out
```

`Final State`はデバッグ用出力として`RAMScope_PoC_State.ctl`を割り当てる。TestStand組込み時には内部状態として隠してよい。

---

#### 7. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 用途 |
|---:|---|---|---|
| 1 | `RAMScope_PoC_State.ctl`定数 | typedef cluster constant | 初期状態を作る |
| 4以上 | 名前でバンドル | Bundle By Name | 成功フラグを1項目ずつ更新する |
| 必要数 | 名前でバンドル解除 | Unbundle By Name | 状態Booleanとerror.statusを取り出す |
| 必要数 | 否定 | Not | `NOT(error.status)`を作る |
| 必要数 | 複合演算 | Compound Arithmetic | AND条件を作る |
| 3以上 | ケースストラクチャ | Case Structure | Cleanup Stop、Release、Closeの要否を分岐する |
| 2 | エラークリア | Clear Errors | 前段エラーがあってもCleanup APIを呼ぶ |
| 2以上 | エラーをマージ | Merge Errors | Original Errorを優先してCleanup Errorを追加する |
| 各1 | `RAMScope_*` Public VI | SubVI | 通常処理とCleanup |

---

#### 8. 配線順

#### A. `RAMScope_PoC_State.ctl`を作成する

1. 新規カスタム制御器を作成する。
2. クラスタを配置する。
3. Boolean制御器を5個入れる。
4. 上から次の順でラベルを付ける。

```text
Connected?
Measurement Started?
Stopped?
Released?
File Open?
```

5. すべての既定値をFalseにする。
6. typedefとして`RAMScope_PoC_State.ctl`へ保存する。

#### B. Initial Stateを配置する

作業領域：ブロックダイアグラム左端、`RAMScope_Connect.vi`の左側。

1. `RAMScope_PoC_State.ctl`をブロックダイアグラムへドラッグする。
2. 定数として配置する。
3. 5項目がすべてFalseであることを確認する。
4. 定数の右側出力ワイヤへ`Initial State`というラベルを付ける。
5. このクラスタ定数はフロントパネル制御器にしない。

初期状態：

```text
Connected?            = False
Measurement Started?  = False
Stopped?              = False
Released?             = False
File Open?            = False
```

#### C. Connect成功後に`Connected?`を更新する

作業領域：`RAMScope_Connect.vi`の直後。

1. `RAMScope_Connect.vi / error out`を名前でバンドル解除（Unbundle By Name）へ接続する。
2. `status`を選択する。
3. `status`出力を否定（Not）へ接続する。
4. Not出力へ`Connect Succeeded?`というラベルを付ける。
5. 名前でバンドル（Bundle By Name）を配置する。
6. B-4の`Initial State`をBundle By Nameのクラスタ入力へ接続する。
7. Bundle By Nameの項目を`Connected?`へ変更する。
8. `Connect Succeeded?`を`Connected?`入力へ接続する。
9. Bundle By Name出力へ`State After Connect`というラベルを付ける。

```text
Connected?
= NOT(RAMScope_Connect.vi.error out.status)
```

Bundle By Nameは、`Initial State`と`Connect Succeeded?`の両方が到着してから実行される。このため状態更新はConnect完了後に行われる。

#### D. InitとSet Condの区間

1. `RAMScope_Connect.vi / error out`を`RAMScope_Init.vi / error in`へ接続する。
2. `RAMScope_Init.vi / error out`を`RAMScope_Set_Cond.vi / error in`へ接続する。
3. `State After Connect`は変更せず、ワイヤをLog Start後の状態更新位置まで右方向へ引く。
4. InitまたはSet Condで新しい状態Booleanを更新しない。

#### E. Log Start成功後に`Measurement Started?`を更新する

作業領域：`RAMScope_Log_Start.vi`の直後。

1. `RAMScope_Log_Start.vi / error out`をUnbundle By Nameへ接続し、`status`を取り出す。
2. `status`をNotへ接続する。
3. `State After Connect`を別のUnbundle By Nameへ接続し、`Connected?`を取り出す。
4. `Connected?`とNot出力をANDへ接続する。
5. AND出力へ`Start Succeeded?`というラベルを付ける。
6. Bundle By Nameを配置する。
7. `State After Connect`をクラスタ入力へ接続する。
8. 項目を`Measurement Started?`へ設定する。
9. `Start Succeeded?`を同項目へ接続する。
10. Bundle出力へ`State After Start`というラベルを付ける。

```text
Measurement Started?
= Connected? AND NOT(RAMScope_Log_Start.vi.error out.status)
```

#### F. フラットシーケンスでLog Start後のWaitを保証し、Readを実行する

作業領域：`RAMScope_Set_Cond.vi`の右側から`RAMScope_Read.vi`の左側。

1. フラットシーケンスストラクチャ（Flat Sequence Structure）を配置する。
2. シーケンス枠を右クリックし、`後にフレームを追加（Add Frame After）`を選び、2フレームにする。
3. Frame 0へ`RAMScope_Log_Start.vi`を配置する。
4. `RAMScope_Set_Cond.vi / error out`をFrame 0左側のerror入力トンネルへ接続し、同VIの`error in`へ接続する。
5. `UnitNo` I32を`RAMScope_Log_Start.vi / UnitNo`へ接続する。
6. `RAMScope_Log_Start.vi / error out`をFrame 0右側のerrorトンネルへ接続し、Frame 1へ通す。
7. Frame 1へ待機（Wait (ms)）を配置する。
8. フロントパネル入力`Wait Time` U32を`Wait (ms) / milliseconds to wait`へ接続する。
9. Frame 1へ入ったerror wireを処理せず右側トンネルへ通し、シーケンス外へ出す。
10. シーケンス右側のerror wireを`RAMScope_Read.vi / error in`へ接続する。
11. `RAMScope_Read.vi / Raw Buffer`、`DataNum`、`LostDataNum`、`Packets`を、それぞれ同名のPoC表示器へ直接接続する。
12. `State After Start`は変更せず、通常Log Stop後の状態更新位置まで右方向へ引く。

```text
Set Cond error
  → Flat Sequence Frame 0：Log Start
  → Flat Sequence Frame 1：Wait (ms)
  → RAMScope_Read.vi
```

Waitにはerror端子がないため、フラットシーケンスのフレーム順で`Log Start完了 → Wait完了 → Read開始`を保証する。

#### G. 通常Log Stop成功後に`Stopped?`を更新する

作業領域：通常経路の`RAMScope_Log_Stop.vi`直後。

1. `RAMScope_Log_Stop.vi / error out.status`をUnbundle By Nameで取り出す。
2. `status`をNotへ接続する。
3. `State After Start`から`Measurement Started?`をUnbundle By Nameで取り出す。
4. `Measurement Started?`とNot出力をANDへ接続する。
5. AND出力へ`Normal Stop Succeeded?`というラベルを付ける。
6. Bundle By Nameを配置する。
7. `State After Start`をクラスタ入力へ接続する。
8. 項目を`Stopped?`へ設定する。
9. `Normal Stop Succeeded?`を`Stopped?`へ接続する。
10. Bundle出力へ`State After Normal Stop`というラベルを付ける。

```text
Stopped?
= Measurement Started? AND NOT(RAMScope_Log_Stop.vi.error out.status)
```

#### H. 通常Releaseを呼ぶ条件と`Released?`更新

作業領域：通常Stop状態更新の直後。

1. `State After Normal Stop`をUnbundle By Nameへ接続する。
2. `Stopped?`と`Released?`を表示する。
3. `Released?`をNotへ接続する。
4. `Stopped?`と`NOT Released?`をANDへ接続する。
5. AND出力をCase Structureのselectorへ接続する。

```text
Need Release?
= Stopped? AND NOT Released?
```

##### Falseケース（Need Release?=False：Release不要）

1. `RAMScope_Release.vi`を配置しない。
2. 入力StateをState出力トンネルへそのまま接続する。
3. 入力errorをerror出力トンネルへそのまま接続する。

##### Trueケース（Need Release?=True：Release必要）

1. `RAMScope_Release.vi`を配置する。
2. UnitNoを接続する。
3. 通常Stopの`error out`をReleaseの`error in`へ接続する。
4. Releaseの`error out.status`を取り出してNotへ接続する。
5. Not出力へ`Release Succeeded?`というラベルを付ける。
6. Bundle By Nameを配置する。
7. `State After Normal Stop`をクラスタ入力へ接続する。
8. 項目を`Released?`へ設定する。
9. `Release Succeeded?`を接続する。
10. 更新StateをCaseのState出力トンネルへ接続する。
11. Release errorをCaseのerror出力トンネルへ接続する。

#### I. Cleanup開始時にOriginal Errorを保持する

1. 通常経路の最後のerror wireを2方向へ分岐する。
2. 1本目へ`Original Error`というラベルを付ける。
3. 2本目をCleanup Stop判定へ引く。
4. 通常経路の最後のStateを`Cleanup Input State`としてCleanup Stop判定へ引く。

#### J. Cleanup Stopの要否を判定する

1. `Cleanup Input State`をUnbundle By Nameへ接続する。
2. `Measurement Started?`と`Stopped?`を表示する。
3. `Stopped?`をNotへ接続する。
4. `Measurement Started?`と`NOT Stopped?`をANDへ接続する。
5. AND出力をCleanup Stop Case Structureのselectorへ接続する。

```text
Need Cleanup Stop?
= Measurement Started? AND NOT Stopped?
```

##### Falseケース（Need Cleanup Stop?=False：Cleanup Stop不要）

1. Cleanup Stop VIを配置しない。
2. Cleanup Input StateをState出力へそのまま接続する。
3. Original Errorをerror出力へそのまま接続する。

##### Trueケース（Need Cleanup Stop?=True：Cleanup Stop必要）

1. エラークリア（Clear Errors）を配置する。
2. Original ErrorをClear Errorsへ接続する。
3. Clear Errors出力を`RAMScope_Log_Stop.vi / error in`へ接続する。
4. UnitNoをLog Stopへ接続する。
5. Log Stopの`error out.status`を取り出し、Notへ接続する。
6. Not出力へ`Cleanup Stop Succeeded?`というラベルを付ける。
7. Bundle By NameへCleanup Input Stateを接続する。
8. 項目を`Stopped?`へ設定する。
9. `Cleanup Stop Succeeded?`を接続する。
10. 更新StateをCaseのState出力へ接続する。
11. エラーをマージ（Merge Errors）を配置する。
12. Original ErrorをMerge Errorsの上側入力1へ接続する。
13. Cleanup Log Stopの`error out`を下側入力2へ接続する。
14. Merge Errors出力をCaseのerror出力へ接続する。

Original Errorを上側へ接続するため、両方がエラーでも最初のエラーを保持する。

#### K. Cleanup Releaseの要否を判定する

Jの出力Stateに対して、Hと同じ式を使用する。

```text
Need Cleanup Release?
= Stopped? AND NOT Released?
```

##### Falseケース（Need Cleanup Release?=False：Cleanup Release不要）

Stateとerrorをそのまま通過させる。

##### Trueケース（Need Cleanup Release?=True：Cleanup Release必要）

1. 入力errorをClear Errorsへ接続する。
2. Clear Errors出力を`RAMScope_Release.vi / error in`へ接続する。
3. UnitNoを接続する。
4. Release error.statusをNotし、`Cleanup Release Succeeded?`を作る。
5. Bundle By Nameで`Released?`を更新する。
6. Merge Errorsの上側入力1へCleanup Release前のerrorを接続する。
7. 下側入力2へReleaseの`error out`を接続する。
8. 更新StateとMerge Errors出力をCase外へ接続する。

#### L. Closeの要否を判定し、最終4出力を作る

1. Kの出力Stateから`Connected?`を名前でバンドル解除（Unbundle By Name）で取り出す。
2. `Connected?`をClose Case Structureのselectorへ接続する。
3. Close Case右側へ、次の4個の出力トンネルを作る。

```text
Final State : RAMScope_PoC_State.ctl
Status      : Status.ctl
TestError   : TestError.ctl
Final Error : error cluster
```

##### Falseケース（Connected?=False：DeviceInit未成功）

1. `RAMScope_Close.vi`を配置しない。
2. Kの出力Stateを`Final State`出力トンネルへそのまま接続する。
3. `Error_To_TestStatus.vi`を配置する。
4. KのMerge Errors出力を`Error_To_TestStatus.vi / error in`へ接続する。
5. 文字列定数へ全文`RAMScope`を入力し、同SubVIの`Device Name`へ接続する。
6. 同SubVIの`Status`をClose Caseの`Status`出力トンネルへ接続する。
7. 同SubVIの`TestError`を`TestError`出力トンネルへ接続する。
8. 同SubVIの`error out`を`Final Error`出力トンネルへ接続する。

```text
K出力State ─────────────────────────→ Final State
K出力error → Error_To_TestStatus.vi ─┬→ Status
                                      ├→ TestError
                                      └→ Final Error
```

##### Trueケース（Connected?=True：DeviceExitが必要）

1. `RAMScope_Close.vi`を配置する。
2. Kの出力Stateを`Final State`出力トンネルへそのまま接続する。
3. KのMerge Errors出力を`RAMScope_Close.vi / error in`へ接続する。
4. Closeの`Status`をClose Caseの`Status`出力トンネルへ接続する。
5. Closeの`TestError`を`TestError`出力トンネルへ接続する。
6. Closeの`error out`を`Final Error`出力トンネルへ接続する。
7. このCase内にはエラークリア（Clear Errors）を配置しない。

```text
K出力State ───────────────────→ Final State
K出力error → RAMScope_Close.vi ─┬→ Status
                                 ├→ TestError
                                 └→ Final Error
```

#### M. Close Case外からPoCの最終出力へ接続する

1. Close Caseの`Final State`出力をPoCの`Final State`表示器へ接続する。
2. Close Caseの`Status`出力をPoCの`Status`表示器へ接続する。
3. Close Caseの`TestError`出力をPoCの`TestError`表示器へ接続する。
4. Close Caseの`Final Error`出力をPoCの`error out`表示器およびコネクタペーン端子へ接続する。
5. True／False両ケースで4個の出力トンネルがすべて配線されていることを確認する。

---

#### 9. 単体テスト

##### 9.1 初期状態

期待：5項目すべてFalse。

##### 9.2 Connect成功、Init失敗

期待：

```text
Connected?           = True
Measurement Started? = False
Stopped?             = False
Released?            = False
Cleanup Stop         = 未実行
Cleanup Release      = 未実行
Close                = 実行
```

##### 9.3 Log Start失敗

期待：`Measurement Started?=False`、StopとReleaseを呼ばずCloseを実行する。

##### 9.4 Log Start成功後にRead失敗

期待：

```text
Connected?           = True
Measurement Started? = True
Stopped?             = Cleanup Stop成功時True
Released?            = Cleanup Release成功時True
Close                = 実行
Final Error           = ReadのOriginal Error
```

##### 9.5 通常Stop成功、Release成功

期待：Stopped?=True、Released?=True。Cleanup StopとCleanup Releaseは実行しない。

##### 9.6 Connect失敗

期待：全State=False。Init以降は通常error wireでスキップし、Stop、Release、Closeを呼ばない。

##### 9.7 推奨プローブ

次へプローブを置く。

```text
State After Connect
State After Start
State After Normal Stop
Cleanup Stop Succeeded?
Cleanup Release Succeeded?
Final State
Original Error
各Merge Errors出力
```

### 10.12.1 全フロントパネル出力の生成元

#### 1. 出力は2種類に分ける

```text
途中のPublic VIから直接保持する出力
  UnitNum / kind
  Module List / MdlNo_RAM / MdlNo_CAN / Endian_RAM
  Raw Buffer / DataNum / LostDataNum / Packets

Cleanup完了後に最後のClose Caseで確定する出力
  Final State / Status / TestError / error out
```

途中の値を、最後のClose Caseまで順番に通過させる必要はない。各Public VIの出力ワイヤを分岐し、その場でPoCの出力表示器へ直接接続する。

LabVIEWの出力表示器端子はブロックダイアグラムの任意位置へ置けるため、対応するPublic VIの近くへ配置してよい。ローカル変数は使用せず、元端子から直接ワイヤを引く。

---

#### 2. 全出力の接続元

| PoC出力 | 接続元 | 配線方法 | 注意 |
|---|---|---|---|
| `UnitNum` | `RAMScope_Connect.vi / UnitNum` | Connect出力ワイヤを分岐して表示器へ接続 | `UnitNo`制御器とは別物 |
| `kind` | `RAMScope_Connect.vi / kind` | Connect出力から直接接続 | 機種コード |
| `Module List` | `RAMScope_Init.vi / Module List` | Init出力から直接接続 | `RAMScope_Module_Info.ctl[]` |
| `MdlNo_RAM` | `RAMScope_Init.vi / MdlNo_RAM` | 3方向へ分岐 | PoC出力、Set Cond入力、Read入力 |
| `MdlNo_CAN` | `RAMScope_Init.vi / MdlNo_CAN` | Init出力から直接接続 | 現PoCでは表示・記録用 |
| `Endian_RAM` | `RAMScope_Init.vi / Endian_RAM` | Init出力から直接接続 | 0=Big、1=Littleのコード |
| `Raw Buffer` | `RAMScope_Read.vi / Raw Buffer` | Read出力から直接接続 | U8一次元配列 |
| `DataNum` | `RAMScope_Read.vi / DataNum` | Read出力から直接接続 | 実際に取得したPacket数 |
| `LostDataNum` | `RAMScope_Read.vi / LostDataNum` | Read出力から直接接続 | 欠落Packet数 |
| `Packets` | `RAMScope_Read.vi / Packets` | Read出力から直接接続 | 解析済みPacket配列 |
| `Final State` | Close CaseのState出力トンネル | Case外で表示器へ接続 | Cleanup Stop/Release反映後のState |
| `Status` | Close CaseのStatus出力トンネル | Case外で表示器へ接続 | True/False両Caseで生成 |
| `TestError` | Close CaseのTestError出力トンネル | Case外で表示器へ接続 | True/False両Caseで生成 |
| `error out` | Close Caseのerror出力トンネル | Case外で表示器へ接続 | Cleanup完了後の最終error |

---

#### 3. `UnitNum`と`UnitNo`を混同しない

```text
UnitNum
  = RAMScope_Connect.viが返す接続Unit数
  = PoCの出力表示器

UnitNo
  = 各APIへ渡す対象Unit番号
  = 現仕様では通常I32 0
  = PoCの入力制御器または内部定数
```

したがって、画面上の`UnitNo`制御器を`UnitNum`出力へ流用しない。

##### 配線

1. `RAMScope_Connect.vi / UnitNum`出力ワイヤを右クリックする。
2. `作成 → 表示器`を選ぶ。
3. 表示器名を`UnitNum`とする。
4. `RAMScope_Connect.vi / kind`も同様に`kind`表示器へ接続する。
5. `UnitNo`は別のI32制御器またはI32定数`0`として、Init、Set Cond、Start、Read、Stop、Releaseへ分岐する。

---

#### 4. Init出力の配線

`RAMScope_Init.vi`の出力は、同VIの直後でPoC表示器へ接続する。

```text
RAMScope_Init.vi
├─ Module List ─────────────→ PoC Module List
├─ MdlNo_RAM ─┬────────────→ PoC MdlNo_RAM
│             ├────────────→ RAMScope_Set_Cond.vi / MdlNo_RAM
│             └────────────→ RAMScope_Read.vi / MdlNo_RAM
├─ MdlNo_CAN ───────────────→ PoC MdlNo_CAN
└─ Endian_RAM ──────────────→ PoC Endian_RAM
```

##### `Endian_RAM`と`Byte Order`

現在のPoC入力には`Byte Order`が別に存在する。

```text
Byte Order制御器
  → RAMScope_Init.vi / Byte Order
  → RAMScope_Read.vi / Byte Order

RAMScope_Init.vi / Endian_RAM
  → PoC Endian_RAM表示器
```

`Endian_RAM` I32コードを`RAMScope_Read.vi / Byte Order`へ直接接続してはならない。自動設定する場合は、次の明示的な変換を追加する。

```text
Endian_RAM=0 → Big Endian
Endian_RAM=1 → Little Endian
```

この変換を追加していない現在のPoCでは、Readへは入力制御器`Byte Order`を接続する。

---

#### 5. Read出力の配線

`RAMScope_Read.vi`の右側へ、次の4表示器を配置する。

```text
RAMScope_Read.vi
├─ Raw Buffer ─────→ Raw Buffer表示器
├─ DataNum ────────→ DataNum表示器
├─ LostDataNum ────→ LostDataNum表示器
└─ Packets ────────→ Packets表示器
```

##### 配線順

1. `RAMScope_Read.vi / Raw Buffer`をU8一次元配列表示器へ接続する。
2. `DataNum`をI32表示器へ接続する。
3. `LostDataNum`をI32表示器へ接続する。
4. `Packets`を`RAMScope_Packet.ctl[]`表示器へ接続する。
5. これらのワイヤをStop、Release、Cleanup、Close Caseへ通さない。

Readが前段エラーでスキップされた場合は、`RAMScope_Read.vi`が定義した安全出力、空配列および0がそのままPoC出力になる。

---

#### 6. 最後のClose Caseに必要な4出力

Close Case Structureには、右側へ次の4個の出力トンネルを作る。

```text
上から推奨順：
1. Final State     RAMScope_PoC_State.ctl
2. Status          Status.ctl
3. TestError       TestError.ctl
4. Final Error     error cluster
```

TrueケースとFalseケースの両方で、4トンネルをすべて配線する。

---

#### 7. Falseケース（Connected?=False：DeviceInit未成功）

##### 7.1 配置するもの

- `Error_To_TestStatus.vi`
- 文字列定数`RAMScope`
- `RAMScope_Close.vi`は配置しない

##### 7.2 配線順

作業領域：Close CaseのFalseケース。

1. KのCleanup Release Caseから出たStateを、Close Case左側のState入力トンネルへ接続する。
2. 同じStateワイヤを、Close Case右側の`Final State`出力トンネルへそのまま接続する。
3. Kから出た最終errorをClose Case左側のerror入力トンネルへ接続する。
4. `Error_To_TestStatus.vi`をFalseケース内へ配置する。
5. 手順3の入力errorを`Error_To_TestStatus.vi / error in`へ接続する。
6. 文字列定数へ全文`RAMScope`を入力する。
7. 文字列定数`RAMScope`を`Error_To_TestStatus.vi / Device Name`へ接続する。
8. `Error_To_TestStatus.vi / Status`をClose Case右側の`Status`出力トンネルへ接続する。
9. `Error_To_TestStatus.vi / TestError`を`TestError`出力トンネルへ接続する。
10. `Error_To_TestStatus.vi / error out`を`Final Error`出力トンネルへ接続する。

##### 見取り図

```text
K出力State ─────────────────────────→ Final Stateトンネル

K出力error
  → Error_To_TestStatus.vi
      Device Name = "RAMScope"
      ├─ Status ────────────────────→ Statusトンネル
      ├─ TestError ─────────────────→ TestErrorトンネル
      └─ error out ─────────────────→ Final Errorトンネル
```

Falseケースで入力errorをFinal Errorへ直接接続するだけでは、StatusとTestErrorが作られず、Case Structureの出力トンネルが未配線になる。

---

#### 8. Trueケース（Connected?=True：DeviceExitが必要）

##### 8.1 配置するもの

- `RAMScope_Close.vi`
- `Clear Errors`は配置しない

##### 8.2 配線順

1. Close Case左側のState入力を、右側の`Final State`出力トンネルへそのまま接続する。
2. Kから出た最終errorを`RAMScope_Close.vi / error in`へ接続する。
3. `RAMScope_Close.vi / Status`をClose Caseの`Status`出力トンネルへ接続する。
4. `RAMScope_Close.vi / TestError`を`TestError`出力トンネルへ接続する。
5. `RAMScope_Close.vi / error out`を`Final Error`出力トンネルへ接続する。

```text
K出力State ─────────────────────────→ Final Stateトンネル

K出力error
  → RAMScope_Close.vi
      ├─ Status ────────────────────→ Statusトンネル
      ├─ TestError ─────────────────→ TestErrorトンネル
      └─ error out ─────────────────→ Final Errorトンネル
```

`RAMScope_Close.vi`内部でOriginal Errorを保持しながらDeviceExitを試すため、このCaseではClear Errorsを追加しない。

---

#### 9. Case外からPoC出力へ接続する

Close Caseの右側で、4本をPoCの最終出力へ接続する。

```text
Close Case.Final State → PoC Final State
Close Case.Status      → PoC Status
Close Case.TestError   → PoC TestError
Close Case.Final Error → PoC error out
```

Status、TestError、error outをTrueケース内の`RAMScope_Close.vi`から直接PoC表示器へ接続してはならない。Falseケースでも同じ出力型を生成する必要があるため、必ずCase Structureの出力トンネルを経由する。

---

#### 10. 完成時の全出力見取り図

```text
RAMScope_Connect.vi
├─ UnitNum ─────────────────────────────→ PoC UnitNum
└─ kind ────────────────────────────────→ PoC kind

RAMScope_Init.vi
├─ Module List ─────────────────────────→ PoC Module List
├─ MdlNo_RAM ───────────────────────────→ PoC MdlNo_RAM
├─ MdlNo_CAN ───────────────────────────→ PoC MdlNo_CAN
└─ Endian_RAM ──────────────────────────→ PoC Endian_RAM

RAMScope_Read.vi
├─ Raw Buffer ──────────────────────────→ PoC Raw Buffer
├─ DataNum ─────────────────────────────→ PoC DataNum
├─ LostDataNum ─────────────────────────→ PoC LostDataNum
└─ Packets ─────────────────────────────→ PoC Packets

Cleanup後State/error
  → Close Case
      ├─ Final State ───────────────────→ PoC Final State
      ├─ Status ────────────────────────→ PoC Status
      ├─ TestError ─────────────────────→ PoC TestError
      └─ Final Error ───────────────────→ PoC error out
```

---

#### 11. 画面確認チェックリスト

- [ ] `UnitNum`はConnect出力であり、`UnitNo`制御器ではない。
- [ ] `kind`表示器がConnect出力へ接続されている。
- [ ] `Module List`、`MdlNo_RAM`、`MdlNo_CAN`、`Endian_RAM`がInit出力へ接続されている。
- [ ] `MdlNo_RAM`はSet CondとReadにも分岐している。
- [ ] Raw Buffer、DataNum、LostDataNum、PacketsはRead出力へ直接接続されている。
- [ ] Close CaseにState、Status、TestError、errorの4出力トンネルがある。
- [ ] Close CaseのFalseケースに`Error_To_TestStatus.vi`がある。
- [ ] FalseケースのDevice Nameは文字列全文`RAMScope`である。
- [ ] Close CaseのTrueケースに`RAMScope_Close.vi`がある。
- [ ] True/False両ケースで4出力トンネルがすべて配線されている。
- [ ] Final State、Status、TestError、error outはCase外の各PoC出力へ接続されている。

---

### 10.13.2 `PoC_RAMScope_Logging_Main.vi`

#### 0. 実現したい機能とVIの責務

RAMScope機器側ロギングから停止後の全保存Block取得、Packet解析、TDMS保存、CleanupまでをTestStandなしで一度通し、ロギング機能を単独検証する。

既存`PoC_RAMScope_Main.vi`は変更せず、本VIだけにTDMSと保存ログ回収処理を置く。

#### 1. 入力データの実体

```text
UnitNo I32
Byte Order
Meas Config
Channel List
Module Log Configs
Measurement Duration ms
TDMS File Path
Overwrite?
TestName
A2L File Name
Max Buffer Bytes I64
Flush Every Block?
error in
```

#### 2. 出力データモデル

```text
UnitNum、kind
Module List、MdlNo_RAM、MdlNo_CAN、Endian_RAM
GapTimeMs、MeasNum
Total Block Count I32
Total Packet Count I64
Total LostDataNum I64  // 参考集計。Block別値もTDMSへ保存
Last MeasNo、Last BlockNo
Final State RAMScope_Logging_PoC_State.ctl
Status、TestError、error out
```

`Total LostDataNum`はAPI値の累積／差分仕様が実機で確定するまで参考表示とし、判定にはBlockごとの`LostDataNum`とPacketの`Data Lost?`を使用する。

#### 3. 前提条件・異常条件

- 既存通信PoCがDeviceInitからReadまで成功していること。
- TDMS Open成功前にLog Startしない。
- Log Stop成功前に保存ログ取得APIを呼ばない。
- 全Block取得前にReleaseしない。
- 途中errorでもFile Close、Release、DeviceExitを可能な範囲で試行する。

#### 4. 処理アルゴリズム

```text
State = all False
Main Error = error in

Connect
Connected?更新

Init
Set Cond

File Log Open
File Open?更新
MeasurementStartTimeを保存

Log Start
Measurement Started?更新
Wait Measurement Duration
Log Stop
Stopped?更新

Get Log Summary
Log Summary Read?更新
Write Metadata(Test情報、Channel定義、MeasurementStartTime、GapTimeMs)

for MeasNo = 0 ... MeasNum-1:
    Get Block Count
    Total Block Count += BlockNum

    for BlockNo = 0 ... BlockNum-1:
        Read Logging Block
        File Log Append
        Total Packet Count += DataNum
        Block別LostDataNumをTDMSへ保存

Logging Retrieved?更新

Release
Released?更新

File Log Close
File Open?=False

Close Device

Cleanup:
    if Measurement Started? AND NOT Stopped?:
        Clear ErrorsしてLog Stopを試行
    if Stopped? AND NOT Released?:
        Clear ErrorsしてReleaseを試行
    if File Open?:
        File Log Closeを試行
    if Connected?:
        RAMScope_Close.viを試行
    Original Errorを最優先でMerge
```

#### 5. LabVIEW構造の選定理由

- MeasNoとBlockNoは2重For Loop。
- Total Block／Packet数はShift Register。
- Stateは`RAMScope_Logging_PoC_State.ctl`を通常ワイヤとLoop Shift Registerで保持。
- Cleanup要否はCase Structure。
- 測定時間保証はFlat Sequenceまたはerror wire＋Wait。既存通信PoCと同じ正式方式へ合わせる。
- 1Block取得直後にTDMS Appendし、巨大配列を保持しない。

#### 6. フロントパネル入出力と接続元・接続先

| 出力 | 生成元 |
|---|---|
| UnitNum、kind | `RAMScope_Connect.vi` |
| Module List、MdlNo | `RAMScope_Init.vi` |
| GapTimeMs、MeasNum | `RAMScope_Get_Log_Summary.vi` |
| Total Block Count | 外側For Loop Shift Register |
| Total Packet Count | 内側For Loop DataNum累積 |
| Final State | Cleanup後State |
| Status、TestError、error out | 最後のClose Case出力トンネル |

#### 7. 配置する関数およびSubVI

- 既存公開API：Connect、Init、Set Cond、Log Start、Log Stop、Release、Close。
- 新規公開API：Get Log Summary、Get Block Count、Read Logging Block。
- TDMS VI：Open、Write Metadata、Append、Close。
- 現在の日時を秒で取得（Get Date/Time In Seconds）：プログラミング → タイミング。Log Start直前のMeasurementStartTimeを保持する。
- For Loop×2、Shift Register、Case Structure、Bundle By Name、Unbundle By Name、Clear Errors、Merge Errors、Error_To_TestStatus。
- `RAMScope_Logging_PoC_State.ctl`。

#### 8. 配線順

##### A. 専用State ctlを作る

```text
Connected?             Boolean False
File Open?             Boolean False
Measurement Started?   Boolean False
Stopped?               Boolean False
Log Summary Read?      Boolean False
Logging Retrieved?     Boolean False
Released?              Boolean False
```

`RAMScope_Logging_PoC_State.ctl`としてtypedef保存する。既存`RAMScope_PoC_State.ctl`を変更しない。

##### B. ConnectからSet Cond

既存通信PoCと同じ公開API、同じerror wire順を使用する。Connect成功時だけConnected?をTrueに更新する。

##### C. TDMS Openと測定開始時刻の保持

1. Set Cond error outをFile Log Openへ接続する。
2. Open成功時にFile Open?をTrueへ更新する。
3. Get Date/Time In Secondsを配置し、Log Start直前の値を`MeasurementStartTime`として保持する。
4. File Log Openのerror outをLog Startへ接続する。
5. File Ref、MeasurementStartTimeおよびStateをSummary後のMetadata書込位置まで通す。

##### D. Start、Wait、Stop

1. Log Start成功時にMeasurement Started?をTrue。
2. Measurement DurationをWaitへ接続する。
3. Wait後にLog Stop。
4. Stop成功時にStopped?をTrue。

##### E. Summaryと2重For Loop

1. Stop error outをGet Log Summaryへ接続する。
2. 成功時にLog Summary Read?をTrue。
3. SummaryのGapTimeMs、Cで保持したMeasurementStartTime、File Ref、Channel ListをFile Log Write Metadataへ接続する。
4. Write Metadataのerror outを外側For Loopへ接続する。
5. MeasNumを外側For Loop Nへ接続する。
6. 外側iをMeasNoへ接続する。
7. Get Block CountのBlockNumを内側For Loop Nへ接続する。
8. 内側iをBlockNoへ接続する。
9. Read Logging BlockのPackets、件数、LostをAppendへ接続する。
10. `GetLoggingData()`後はAPI内部の読出し済みPacketが削除されるため、Append完了前に次Blockへ進まない。
11. Append error outを次反復へShift Registerで渡す。
12. 各Block終了後にTotal Packet CountをI64加算する。
13. 両Loop正常終了時だけLogging Retrieved?をTrue。

##### F. ReleaseとFile Close

1. Logging Retrieved後にRelease。
2. Release成功時にReleased?をTrue。
3. Release後にFile Log Close。
4. File Open?をFalseへ更新する。
5. Device Closeへ進む。

##### G. Cleanup

Original Errorを別wireで保持する。

```text
Cleanup Stop条件
= Measurement Started? AND NOT Stopped?

Cleanup Release条件
= Stopped? AND NOT Released?

Cleanup File Close条件
= File Open?

Cleanup Device Close条件
= Connected?
```

各Cleanup APIへ渡すwireだけClear Errorsし、戻りerrorをMerge Errorsの後順位入力へ接続する。Original Errorを最上位入力に固定する。

#### 9. 単体テスト

1. 正常1Meas、1Block。
2. 正常1Meas、複数Block。
3. 複数Meas。
4. BlockNum=0。
5. DataNum=0。
6. TDMS既存ファイル上書き拒否。
7. Log Start失敗。
8. Log Stop失敗後Cleanup Stop。
9. Block取得途中エラー後Release、File Close、Device Close。
10. LostDataNum非ゼロとData Lost Flag非ゼロ。
11. 大容量BlockでMax Buffer Bytesガード。
12. TDMS再読込でGroup数、DataNum、チャンネル長、Time単調増加を照合。

---

### 10.13.3 TestStand組込み順

```text
Setup
  RAMScope_Connect.vi
  RAMScope_Init.vi
  RAMScope_Set_Cond.vi
  RAMScope_File_Log_Open.vi
  MeasurementStartTimeを保持

Main
  RAMScope_Log_Start.vi
  DUT試験
  RAMScope_Log_Stop.vi
  RAMScope_Get_Log_Summary.vi
  RAMScope_File_Log_Write_Metadata.vi

  For MeasNo
    RAMScope_Get_Block_Count.vi
    For BlockNo
      RAMScope_Read_Logging_Block.vi
      RAMScope_File_Log_Append.vi

Cleanup
  RAMScope_Release.vi
  RAMScope_File_Log_Close.vi
  RAMScope_Close.vi
```

TestStand側はMeasNo、BlockNoのLoop、試験条件、判定、レポートを担当する。DLL関数をTestStandから直接呼ばない。

---

### 10.13.4 2つのPoCの完成条件

### `PoC_RAMScope_Main.vi`

- [ ] 既存VI名と構成を維持。
- [ ] Connect、Init、Set Cond、Start、短時間Read、Stop、Release、Closeを確認。
- [ ] TDMS File Refを持たない。
- [ ] GetMeasNum／GetBlockNum／GetLoggingDataを呼ばない。
- [ ] 通信・DLL・Packet Parserの最小切り分けに使用。

### `PoC_RAMScope_Logging_Main.vi`

- [ ] TDMS Open後にStart。
- [ ] Stop後にSummaryを取得。
- [ ] MeasNoとBlockNoを全列挙。
- [ ] 1Block取得直後にTDMS Append。
- [ ] 全Block後にRelease。
- [ ] File CloseとDevice CloseをCleanupで試行。
- [ ] Packet CountとDataNumが一致。
- [ ] Flag Raw、Status、Skip、Log Trigger、Dummy、Event、Data Lostを保存。
- [ ] Time RawとTime Secondsを保存。
- [ ] LostDataNumをBlock Propertyへ保存。

---

## 10.14 単体試験・実機PoC・完了判定

### 10.14.1 レイヤ別の合格順

```text
ctl既定値とtypedef反映
  → 共通変換・Builder・Parser単体試験
  → WrapperのCLFN設定と安全値バイパス
  → 公開APIの入力／戻り値検証
  → TDMS Open／Metadata／Append／Close
  → 通信確認PoC回帰
  → ロギングPoC結合
  → TDMS再読込
  → MF4変換前提確認
```

作成順は10.5.2だけを正本とし、本節では合否判定だけを扱う。

### 10.14.2 実機PoCで最終確認する項目

- [ ] 使用DLL、同梱ヘッダ、APIマニュアルの関数宣言が一致。
- [ ] `GetLoggingData`は7引数。
- [ ] pDataNum左が要求数、右が実取得数。
- [ ] Data順がSetMeasCh順。
- [ ] 1byte／2byte／4byteが各4byteスロットで正しく復号。
- [ ] Flag各fieldがRAMScopeVP表示と一致。
- [ ] Time差分×20nsが実時間と一致。
- [ ] GetMeasNum、GetBlockNumが純正表示と一致。
- [ ] GetLoggingDataNumと実DataNumの関係が妥当。
- [ ] LostDataNumが差分か累積かを実機で確定し、本節へ追記。
- [ ] 全Block取得後までReleaseされない。
- [ ] TDMS再読込で全チャンネル長がDataNumと一致。
- [ ] MF4変換PoCでTime、単位、チャンネル数が維持される。

---

### 10.14.3 完了条件

- [ ] 10.5.2の全Phaseが順番どおり完了している。
- [ ] 既存通信PoCがロギング追加後も回帰試験に合格する。
- [ ] ロギングPoCが全BlockをRead→Parse→Appendし、Release前に保存を完了する。
- [ ] API ReturnCode、ローカルerror、Packet Status、LostDataNumを別情報として追跡できる。
- [ ] TDMS再読込で全チャンネル長、Block数、Packet数、メタデータが一致する。
- [ ] 次フェーズのMF4変換に必要なName、Address、Size、Sign、Scale、Offset、Unit、Time、Flagを保持できる。
