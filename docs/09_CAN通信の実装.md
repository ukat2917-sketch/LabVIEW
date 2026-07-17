# 09. CANalyzer ActiveX実装ガイド

> **本章の役割**：既存のPython COM APIロジックをLabVIEW 2026 Q1 64bitのActiveX機能へ置き換え、CANalyzerの接続・新規起動・Configuration確認・Measurement制御・System Variable読書き・故障注入・単体PoC・TestStand組み込みまでを、画面操作で再現できる粒度で定義する。
>
> VI作成手順の書き方は[00A_LabVIEW実装資料の記述ルール.md](./00A_LabVIEW実装資料の記述ルール.md)を正とする。
>
> CANalyzer COM APIのプロパティ名・メソッド名は、対象PCへ登録されたCANalyzer Type Libraryを一次情報とする。CANalyzerの版によって表示名や引数が異なる場合は、推測で固定せず`実機確認待ち`としてWrapper層だけを差し替える。

**最終整理日：2026-07-17**

---

# 9.1 採用方針と現在地

## 9.1.1 確定事項

| 項目 | 採用内容 | 状態 |
|---|---|---|
| LabVIEW | 2026 Q1 64bit | 確定 |
| TestStand | 2026 Q1 64bit | 確定 |
| CANalyzer | 64bit | 確定 |
| CANalyzer版 | 確認中 | 実機確認待ち |
| 制御方式 | LabVIEW ActiveX Automation | 採用 |
| ProgID | `CANalyzer.Application` | 既存ロジックで使用済み |
| 接続 | 起動済みCANalyzerへの接続 | 必須 |
| 起動 | CANalyzer未起動時のLabVIEWからの起動 | 必須 |
| Configuration | 指定cfgのOpenまたは一致確認 | 必須 |
| Measurement | Running確認、Start、Stop、Timeout | 必須 |
| Tx/Rx | System VariableのValue読書き | 必須 |
| 周期送信 | CAPLのTimerで実施 | 確定 |
| Alive Counter | CAPLで生成 | 確定 |
| Checksum | CAPLで生成 | 確定 |
| 故障注入 | System Variable経由でCAPLへ指示 | 確定 |

## 9.1.2 本章で実現する範囲

```text
LabVIEW / TestStand
  ↓
CANalyzer公開API VI
  ↓ Session ID
ActiveX Service
  ↓
ActiveX Wrapper
  ↓
CANalyzer.Application
  ├─ Configuration
  ├─ Measurement
  └─ System
       └─ Namespaces
            └─ Variables
                 └─ Item(...).Value
  ↓
CAPL
  ├─ 信号値をCANメッセージへ反映
  ├─ Alive Counter生成
  ├─ Checksum生成
  ├─ 周期送信
  └─ 故障注入
```

LabVIEWはCAN Payloadを直接組み立てない。通常のAlive CounterとChecksumをLabVIEW側へ重複実装しない。

---

# 9.2 既存COM APIロジックとの対応表

## 9.2.1 既存Python版の処理

既存ロジックは次の4列を持つExcelを読み込む。

| 列 | 意味 |
|---|---|
| `ID` | CANalyzer System VariableのNamespace |
| `Name` | Variable名 |
| `data` | Tx値 |
| `Wait` | 実行後の待ち時間、秒 |

基本アクセスは次の直列形式である。

```text
app.System.Namespaces("Namespace").Variables.Item("Variable").Value
```

RxはValueを読んでログへ出す。TxはValueへ値を書き込む。

## 9.2.2 対応表

| 機能 | 既存Python COM API | LabVIEW ActiveX版 | ActiveX版での追加理由 |
|---|---|---|---|
| CANalyzer接続 | `Dispatch("CANalyzer.Application")` | オートメーションを開く（Automation Open） | LabVIEW標準機能でActiveX参照を取得する |
| 既存プロセス接続 | 前提 | `Attach Existing`モード | 手動起動環境を継続利用する |
| 未起動時の新規起動 | Dispatch挙動へ依存 | `Launch If Needed`モード | 起動状態を明示的に管理する |
| 新規インスタンス要求 | なし | `Force New Instance`モード | 複数環境PoC用。正式対応は実機確認後 |
| cfg指定 | なし | Configuration Open / Verify | 誤ったcfgで試験しないため |
| cfg一致確認 | なし | Actual Path比較 | 起動済みCANalyzerへの誤接続を検出する |
| Measurement確認 | なし | `Running`読出し | CAPL Timerが動作可能な状態か確認する |
| Measurement開始 | 手動前提 | Start + Running待ち | TestStand Setupから自動開始する |
| Measurement停止 | なし | Stop +所有権判定 | 手動開始したMeasurementを勝手に止めない |
| SysVar Tx | Valueへ代入 | `CANalyzer_Write_SysVar.vi` | Variant型とエラー情報をLabVIEWへ統合する |
| SysVar Rx | Value読出し | `CANalyzer_Read_SysVar.vi` | 型指定、値、Namespace、Variableを記録する |
| 直列アクセス | 必須 | Resolver内で直列参照取得 | 分割参照の取り違えを防止する |
| 行単位継続 | 例外時continue | Batch Policyで選択 | Stop / Continue / Warningを試験ごとに変更する |
| Wait | 仕様書にはあり、コード未実装 | Wait msを明示実装 | 仕様と実装を一致させる |
| RxのExcel書戻し | なし | 標準ではログのみ | 現行仕様を維持する |
| ログ | 文字列ログ | Result Cluster + TestStand結果 | 自動判定と追跡性を上げる |
| Session管理 | なし | Session Registry | ActiveX参照をTestStandへ直接渡さない |
| ActiveX参照解放 | Python実行終了に依存 | Close Referenceを明示 | 長時間実行時の参照リークを防ぐ |
| Version確認 | なし | Version / Capability Probe | 別環境・別版での使用可否を判定する |
| 故障注入 | SysVar名を直接指定 | 専用公開VI | TestStandからAlive/Checksum/Timeoutを安全に操作する |
| Cleanup | なし | Fault Clear → Stop → Close | 次の試験へ状態を残さない |

## 9.2.3 既存コードの修正点

既存Txコードでは列名が`deta`となっているが、仕様書の正式列名は`data`である。LabVIEW版の互換Importerでは`data`を正とし、`deta`は旧入力互換Warningとしてのみ扱う。

既存仕様書には`Wait`があるが、現在のPythonコードには待機処理が入っていない。LabVIEW版では`Wait ms`をRequest要素へ持たせ、Batch処理内で実行する。

---

# 9.3 LabVIEW上で実施したい動作

## 9.3.1 起動・接続

```text
A. 起動済みCANalyzerへ接続する
B. CANalyzerが未起動ならLabVIEWから起動する
C. 新しいインスタンス作成を要求する
D. ActiveX Classが未登録なら明確なエラーを返す
```

## 9.3.2 Configuration

```text
A. 指定cfgを開く
B. 起動済みCANalyzerが開いているcfgを確認する
C. 期待cfgと実cfgが異なる場合はErrorまたはWarningにする
D. cfg OpenをLabVIEWが行ったか所有権を記録する
```

## 9.3.3 Measurement

```text
A. Running状態を読む
B. 停止中ならStartする
C. Running=Trueまで待つ
D. Timeoutで終了する
E. LabVIEWがStartしたMeasurementだけCleanupでStopする
```

CAPLは`on start`で10、40、100、300、500、1000msのTimerを開始するため、Main処理へ進む前にMeasurementがRunningであることを確認する。

## 9.3.4 System Variable

```text
A. 1変数を書き込む
B. 1変数を読み取る
C. 複数変数を順番に書き込む
D. 複数変数を順番に読み取る
E. Boolean / I32 / DBL / Stringを扱う
F. NamespaceまたはVariableが存在しない場合に名称付きエラーを返す
```

## 9.3.5 故障注入

```text
ALIVE_COUNTER = 0  → CAPLがAliveを正常更新
ALIVE_COUNTER != 0 → Alive更新を止める

CHECKSUM = 0 → 正常Checksum
CHECKSUM = 1 → CAPLがChecksum+1を送る

TIMEOUT = 0 → output(message)
TIMEOUT != 0 → 送信停止
```

LabVIEWは上記System Variableを操作する。Alive CounterやChecksumの計算式はCAPL側へ残す。

## 9.3.6 終了・Cleanup

```text
Fault用System Variableを正常値へ戻す
  ↓
LabVIEWが開始したMeasurementだけStop
  ↓
LabVIEWが起動したApplicationだけ必要に応じてQuit
  ↓
子参照から順にClose Reference
  ↓
Session Registryから削除
```

---

# 9.4 動作に必要なロジックとLabVIEW機能

| 必要ロジック | LabVIEW上の機能 | 主な用途 |
|---|---|---|
| ActiveX Serverを開く | オートメーションを開く（Automation Open） | CANalyzer Application参照取得 |
| プロパティを読む・書く | プロパティノード（Property Node） | System、Measurement、Running、Value |
| メソッドを呼ぶ | インボークノード（Invoke Node） | Start、Stop、Configuration Open、Quit候補 |
| ActiveX参照を解放 | リファレンスを閉じる（Close Reference） | 参照リーク防止 |
| Variantへ変換 | バリアントへ変換（To Variant） | 型の異なる書込値を共通化 |
| Variantから変換 | バリアントからデータに変換（Variant To Data） | 読出値を期待型へ変換 |
| 型別分岐 | ケースストラクチャ（Case Structure） | Boolean / I32 / DBL / String |
| 複数要求の繰返し | Forループ（For Loop） | Batch Read / Write |
| Timeout待ち | 経過時間を取得（Tick Count）+ 待機（Wait） | Measurement Running待ち |
| 参照と状態を保持 | 非初期化シフトレジスタを持つFGV | Session Registry |
| 直列化 | 非再入実行のDispatcher | 複数スレッドからのActiveX競合防止 |
| エラー文生成 | 文字列にフォーマット（Format Into String） | Namespace、Variable、操作名をsourceへ追加 |

## 9.4.1 ActiveX関数の配置場所

| 日本語名 | 英語名 | 配置場所 |
|---|---|---|
| オートメーションを開く | Automation Open | 接続 → ActiveX |
| プロパティノード | Property Node | 接続 → ActiveX |
| インボークノード | Invoke Node | 接続 → ActiveX |
| リファレンスを閉じる | Close Reference | 接続 → ActiveX、またはプログラミング → アプリケーション制御 |
| バリアントへ変換 | To Variant | プログラミング → クラスタ、クラス、バリアント → バリアント |
| バリアントからデータに変換 | Variant To Data | プログラミング → クラスタ、クラス、バリアント → バリアント |

LabVIEW 2026 Q1日本語版でパレット名が異なる場合は`Ctrl + Space`を開き、英語名で検索する。

---

# 9.5 Version依存を局所化する設計

## 9.5.1 完全な版非依存にはしない

LabVIEWのProperty NodeとInvoke Nodeは、開発時に選択したActiveX Type Libraryの型情報を保持する。そのため、すべてのCANalyzer版で無条件に動くことは保証できない。

本設計では、次の2段階で影響を限定する。

```text
コンパイル時依存
  → 10_ActiveX_Wrapperだけに閉じ込める

実行時判定
  → Version文字列とCapability Probeで可否を判断する
```

## 9.5.2 Compatibility判定

| 判定 | 意味 |
|---|---|
| `Compatible` | 検証済み版で必須機能がすべて使用可能 |
| `Compatible With Warning` | 未検証版だがCapability Probe成功 |
| `Unsupported` | 必須プロパティまたはメソッドが使用不可 |
| `Unknown` | Version取得不可。接続のみ確認できた状態 |

未知版だから即Errorにはしない。次の必須機能を実際に呼び、すべて成功した場合はWarning付きで続行する。

```text
Application参照取得
System参照取得
Measurement参照取得
Running読出し
既知System VariableのRead
必要なら既知System VariableのWrite
```

## 9.5.3 実機確認待ちのActiveXメンバ

次は対象CANalyzer版のType Libraryで正式名称と引数を確認してから固定する。

| Wrapperの目的 | 候補メンバ | 状態 |
|---|---|---|
| Version取得 | Application配下のVersion関連Property | 実機確認待ち |
| cfg Open | ApplicationまたはConfigurationのOpen Method | 実機確認待ち |
| cfg Path取得 | Configuration配下のPath / FullName相当Property | 実機確認待ち |
| Application終了 | Quit相当Method | 実機確認待ち |
| Force New Instance | Automation Open `open new instance=True`時の実挙動 | 実機確認待ち |

未確認メンバを資料だけで推測して実装しない。

---

# 9.6 フォルダとVI構成

```text
40_CANalyzer\
├─ 00_Common\
│  ├─ CANalyzer_Launch_Mode.ctl
│  ├─ CANalyzer_Compatibility_Policy.ctl
│  ├─ CANalyzer_Compatibility_Status.ctl
│  ├─ CANalyzer_Value_Type.ctl
│  ├─ CANalyzer_SysVar_Request.ctl
│  ├─ CANalyzer_SysVar_Result.ctl
│  ├─ CANalyzer_Session_State.ctl
│  ├─ CANalyzer_Fault_Request.ctl
│  └─ CANalyzer_Error_Code.ctl
│
├─ 10_ActiveX_Wrapper\
│  ├─ CAN_AX_Open_Application.vi
│  ├─ CAN_AX_Get_System.vi
│  ├─ CAN_AX_Get_Measurement.vi
│  ├─ CAN_AX_Get_Measurement_Running.vi
│  ├─ CAN_AX_Start_Measurement.vi
│  ├─ CAN_AX_Stop_Measurement.vi
│  ├─ CAN_AX_Get_Namespace.vi
│  ├─ CAN_AX_Get_Variables.vi
│  ├─ CAN_AX_Get_Variable_Item.vi
│  ├─ CAN_AX_Read_Variable_Value.vi
│  ├─ CAN_AX_Write_Variable_Value.vi
│  ├─ CAN_AX_Get_Version.vi
│  ├─ CAN_AX_Get_Configuration_Path.vi
│  ├─ CAN_AX_Open_Configuration.vi
│  └─ CAN_AX_Quit_Application.vi
│
├─ 20_Service\
│  ├─ CANalyzer_Session_Registry.vi
│  ├─ CANalyzer_Execute_Command.vi
│  ├─ CANalyzer_Resolve_SysVar.vi
│  ├─ CANalyzer_Wait_Measurement_State.vi
│  ├─ CANalyzer_Check_Compatibility.vi
│  ├─ CANalyzer_Verify_Configuration.vi
│  ├─ CANalyzer_Read_Typed_Value.vi
│  ├─ CANalyzer_Write_Typed_Value.vi
│  ├─ CANalyzer_Batch_Read.vi
│  ├─ CANalyzer_Batch_Write.vi
│  └─ CANalyzer_Clear_All_Faults_Core.vi
│
├─ 30_Public\
│  ├─ CANalyzer_Open.vi
│  ├─ CANalyzer_Start.vi
│  ├─ CANalyzer_Read_SysVar.vi
│  ├─ CANalyzer_Write_SysVar.vi
│  ├─ CANalyzer_Batch_Read_SysVar.vi
│  ├─ CANalyzer_Batch_Write_SysVar.vi
│  ├─ CANalyzer_Set_Message_Fault.vi
│  ├─ CANalyzer_Clear_Message_Faults.vi
│  ├─ CANalyzer_Clear_All_Faults.vi
│  ├─ CANalyzer_Health_Check.vi
│  ├─ CANalyzer_Stop.vi
│  └─ CANalyzer_Close.vi
│
├─ 40_PoC\
│  ├─ PoC_CANalyzer_01_Open_Close.vi
│  ├─ PoC_CANalyzer_02_SysVar_Read_Write.vi
│  ├─ PoC_CANalyzer_03_Launch_Config_Start.vi
│  ├─ PoC_CANalyzer_04_Fault_Control.vi
│  └─ PoC_CANalyzer_05_Compatibility.vi
│
├─ 50_Standalone\
│  ├─ CANalyzer_Standalone_Main.vi
│  └─ CANalyzer_Standalone_Config.ctl
│
└─ 90_TestStand\
   └─ CANalyzer_TestStand_Mapping.md
```

## 9.6.1 レイヤ責務

| レイヤ | 責務 | 含めないもの |
|---|---|---|
| `00_Common` | typedef、要求・結果・Session状態 | ActiveXノード |
| `10_ActiveX_Wrapper` | PropertyまたはMethodを1操作だけ実行 | Session ID、Batch、TestStand状態 |
| `20_Service` | 参照解決、型変換、待ち、直列化、Session保持 | TestStand固有変数 |
| `30_Public` | 1イベント1VIで外部へ公開 | 生ActiveX参照の公開 |
| `40_PoC` | 下位から順に単体確認 | 本番試験ロジック |
| `50_Standalone` | TestStandなしの本番実行 | ActiveX詳細の直接操作 |
| `90_TestStand` | 変数マッピングとシーケンス例 | ActiveX Wrapperの直接呼出し |

---

# 9.7 typedef作成

## 9.7.1 `CANalyzer_Launch_Mode.ctl`

### 0. 目的と処理概要

Application取得方法を明示し、既存プロセスへ接続したのか、LabVIEWが起動したのかを後段で判断できるようにする。

### 1. 要素

```text
Attach Existing
Launch If Needed
Force New Instance
```

`Force New Instance`は実機確認が完了するまでPoC専用とする。

## 9.7.2 `CANalyzer_Value_Type.ctl`

```text
Boolean
I32
U32
DBL
String
Variant Raw
```

TestStand本番では`Variant Raw`を原則使用しない。

## 9.7.3 `CANalyzer_SysVar_Request.ctl`

| 要素 | 型 | 用途 |
|---|---|---|
| `Namespace` | String | System Variable Namespace |
| `Variable Name` | String | Variable名 |
| `Value Type` | `CANalyzer_Value_Type.ctl` | 期待型 |
| `Value` | Variant | Tx値または比較用値 |
| `Wait ms` | U32 | 操作後の待ち時間 |
| `Continue On Error?` | Boolean | Batch内の継続可否 |
| `Tag` | String | TestStand条件名や行番号 |

## 9.7.4 `CANalyzer_SysVar_Result.ctl`

| 要素 | 型 |
|---|---|
| `Namespace` | String |
| `Variable Name` | String |
| `Value Type` | Enum |
| `Value` | Variant |
| `Success?` | Boolean |
| `Skipped?` | Boolean |
| `Elapsed ms` | U32 |
| `Tag` | String |
| `error` | error cluster |

## 9.7.5 `CANalyzer_Session_State.ctl`

| 要素 | 型 | 用途 |
|---|---|---|
| `Session ID` | U32 | TestStandが保持する識別子 |
| `Application Ref` | ActiveX Refnum | LabVIEW内部のみ |
| `System Ref` | ActiveX Refnum | LabVIEW内部のみ |
| `Measurement Ref` | ActiveX Refnum | LabVIEW内部のみ |
| `Version String` | String | 実際の版 |
| `Configuration Path` | Path | 実cfg |
| `Launch Mode` | Enum | Open時の指定 |
| `Attached Existing?` | Boolean | 既存接続 |
| `Application Started By LabVIEW?` | Boolean | Application所有権 |
| `Configuration Opened By LabVIEW?` | Boolean | cfg所有権 |
| `Measurement Started By LabVIEW?` | Boolean | Measurement所有権 |
| `Is Connected?` | Boolean | 接続状態 |
| `Is Measuring?` | Boolean | Running状態 |
| `Compatibility Status` | Enum | 互換性判定 |

ActiveX Refnumを含むため、このClusterをTestStandへ直接渡さない。

---

# 9.8 ActiveX Wrapper作成

# 9.8.1 `CAN_AX_Open_Application.vi`

### 0. 目的と処理概要

CANalyzer ApplicationのActiveX参照を取得する。既存接続、新規起動、新規インスタンス要求の差は`Open New Instance?`へ変換する。

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Open New Instance?` | 入力 | Boolean |
| `error in` | 入力 | error cluster |
| `Application Ref` | 出力 | CANalyzer Application ActiveX Refnum |
| `error out` | 出力 | error cluster |

### 2. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所 |
|---:|---|---|---|
| 1 | オートメーションrefnum制御器 | Automation Refnum | フロントパネル → Refnum |
| 1 | オートメーションを開く | Automation Open | 接続 → ActiveX |
| 1 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |

### 3. 配線順

1. フロントパネルへオートメーションrefnum制御器を配置する。
2. 制御器を右クリックし、`ActiveXクラスを選択 → 参照`を開く。
3. CANalyzerのType LibraryからApplicationクラスを選択する。
4. ブロックダイアグラムへオートメーションを開くを配置する。
5. Application型refnumを`automation refnum`入力へ接続する。
6. `Open New Instance?`を`open new instance`入力へ接続する。
7. `error in`を同名入力へ接続する。
8. 出力refnumを`Application Ref`へ接続する。
9. `error out`を本VIの`error out`へ接続する。

通常VIのため、`error in.status=True`ではAutomation Openを実行せず、無効refnumと元エラーを返す外側Caseを設ける。

### 4. 単体テスト

| 条件 | Open New Instance? | 期待結果 |
|---|---:|---|
| CANalyzer起動済み | False | Application参照取得 |
| CANalyzer未起動 | False | CANalyzer起動または参照取得。実挙動を記録 |
| CANalyzer起動済み | True | 新規インスタンス要求。実挙動は版ごとに記録 |
| COM未登録 | 任意 | Automation Openエラー |
| 既存エラー | 任意 | 実処理スキップ、元エラー保持 |

推奨プローブ：Automation Openの`error out`、Application Ref。

# 9.8.2 `CAN_AX_Get_System.vi`

### 0. 目的と処理概要

Application参照からSystem参照を取得する。

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Application Ref` | 入力 | ActiveX Refnum |
| `error in` | 入力 | error cluster |
| `System Ref` | 出力 | ActiveX Refnum |
| `error out` | 出力 | error cluster |

### 2. 配置する関数

| 数 | 日本語名 | 英語名 |
|---:|---|---|
| 1 | プロパティノード | Property Node |

### 3. 配線順

1. Application RefをProperty Nodeの`reference`入力へ接続する。
2. Property Nodeをクリックし、`System`を選択する。
3. `System`の参照出力を`System Ref`へ接続する。
4. error clusterを直列接続する。

### 4. 単体テスト

Application取得後に実行し、System Refが有効であることを確認する。Application RefをClose後に呼び出した場合は無効参照エラーになることを確認する。

# 9.8.3 `CAN_AX_Get_Measurement.vi`

Application RefからMeasurement RefをProperty Nodeで取得する。作り方は`CAN_AX_Get_System.vi`と同じで、選択するPropertyだけを`Measurement`へ変更する。

# 9.8.4 `CAN_AX_Get_Measurement_Running.vi`

### 0. 目的と処理概要

Measurementが実行中かをBooleanで取得する。

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Measurement Ref` | 入力 | ActiveX Refnum |
| `error in` | 入力 | error cluster |
| `Running?` | 出力 | Boolean |
| `error out` | 出力 | error cluster |

### 3. 配線順

1. Measurement RefをProperty Nodeへ接続する。
2. 読取Propertyとして`Running`を選択する。
3. Boolean出力を`Running?`へ接続する。
4. error clusterを直列接続する。

### 4. 単体テスト

CANalyzer画面でMeasurement停止中と実行中の両方を確認し、表示とBooleanが一致することを確認する。

# 9.8.5 `CAN_AX_Start_Measurement.vi`

Measurement RefをInvoke Nodeへ接続し、Type Libraryに表示される`Start` Methodを選択する。Method名または引数が異なる場合はその版のType Libraryを正とする。

出力は`error out`のみとし、Running待ちは本VIへ入れず`CANalyzer_Wait_Measurement_State.vi`へ分離する。

# 9.8.6 `CAN_AX_Stop_Measurement.vi`

`CAN_AX_Start_Measurement.vi`と同じ構造で、Invoke NodeのMethodを`Stop`へ変更する。

# 9.8.7 System Variable参照取得の4段階

System Variableは次の参照を順に取得する。

```text
System Ref
  → Namespace Ref
  → Variables Ref
  → Variable Ref
  → Value
```

## `CAN_AX_Get_Namespace.vi`

1. System RefをProperty NodeまたはInvoke Nodeへ接続する。
2. Type Libraryに表示される`Namespaces`のindexed accessを選択する。
3. `Namespace` Stringをindexまたは引数へ接続する。
4. Namespace Refを出力する。

## `CAN_AX_Get_Variables.vi`

1. Namespace RefをProperty Nodeへ接続する。
2. `Variables`を選択する。
3. Variables Refを出力する。

## `CAN_AX_Get_Variable_Item.vi`

1. Variables RefをProperty NodeまたはInvoke Nodeへ接続する。
2. `Item`を選択する。
3. `Variable Name` Stringをindexまたは引数へ接続する。
4. Variable Refを出力する。

CANalyzer Type Library上で`Namespaces(name)`がPropertyとして表示されるかMethodとして表示されるかは、接続されたRefnumから選択可能なメンバを正とする。

# 9.8.8 `CAN_AX_Read_Variable_Value.vi`

### 0. 目的と処理概要

Variable Refの`Value`をVariantで読み出す。

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Variable Ref` | 入力 | ActiveX Refnum |
| `error in` | 入力 | error cluster |
| `Value Variant` | 出力 | Variant |
| `error out` | 出力 | error cluster |

### 3. 配線順

1. Variable RefをProperty Nodeへ接続する。
2. `Value`を選択する。
3. 読取モードであることを確認する。
4. Value出力を`Value Variant`へ接続する。
5. error clusterを直列接続する。

# 9.8.9 `CAN_AX_Write_Variable_Value.vi`

### 0. 目的と処理概要

Variable Refの`Value`へVariantを書き込む。

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Variable Ref` | 入力 | ActiveX Refnum |
| `Value Variant` | 入力 | Variant |
| `error in` | 入力 | error cluster |
| `error out` | 出力 | error cluster |

### 3. 配線順

1. Variable RefをProperty Nodeへ接続する。
2. `Value`を選択する。
3. Property Nodeを右クリックして書込モードへ変更する。
4. `Value Variant`をValue入力へ接続する。
5. error clusterを直列接続する。

### 4. 単体テスト

既知System VariableへI32値を書き込み、CANalyzer画面または直後のReadで一致することを確認する。

# 9.8.10 Version・Configuration・Quit Wrapper

次のVIはCANalyzer版確定後に、Type Libraryの正式メンバへ合わせて同じ形式で作成する。

```text
CAN_AX_Get_Version.vi
CAN_AX_Get_Configuration_Path.vi
CAN_AX_Open_Configuration.vi
CAN_AX_Quit_Application.vi
```

各VIは1 Propertyまたは1 Methodだけを持つ。Configuration OpenとQuitを`CANalyzer_Open.vi`や`CANalyzer_Close.vi`へ直接埋め込まない。

---

# 9.9 Service VI作成

# 9.9.1 `CANalyzer_Resolve_SysVar.vi`

### 0. 目的と処理概要

SessionのSystem RefとNamespace、Variable NameからVariable Refを取得する。既存Python版の直列アクセスを1VIへ閉じ込める。

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `System Ref` | 入力 | ActiveX Refnum |
| `Namespace` | 入力 | String |
| `Variable Name` | 入力 | String |
| `error in` | 入力 | error cluster |
| `Variable Ref` | 出力 | ActiveX Refnum |
| `error out` | 出力 | error cluster |

### 2. 配置するSubVI

```text
CAN_AX_Get_Namespace.vi
CAN_AX_Get_Variables.vi
CAN_AX_Get_Variable_Item.vi
Close Reference × 2
```

### 3. 配線順

1. System Ref、Namespaceを`CAN_AX_Get_Namespace.vi`へ接続する。
2. Namespace Refを`CAN_AX_Get_Variables.vi`へ接続する。
3. Variables RefとVariable Nameを`CAN_AX_Get_Variable_Item.vi`へ接続する。
4. error clusterを3VIへ直列接続する。
5. Variable Refを本VI出力へ接続する。
6. Namespace RefとVariables Refは、Variable Ref取得後にClose Referenceで閉じる。
7. エラーsourceへNamespaceとVariable Nameを追加する。

Variable Refは呼出側が使用後に閉じる。

### 4. 単体テスト

| 条件 | 期待結果 |
|---|---|
| 正しいNamespace / Variable | 有効Variable Ref |
| 不正Namespace | Namespace名付きエラー |
| 不正Variable | Variable名付きエラー |
| 空文字 | 入力検証エラー |

# 9.9.2 `CANalyzer_Read_Typed_Value.vi`

### 0. 目的と処理概要

Variant Valueを指定型へ変換し、変換不能を明確なエラーにする。

### 3. 配線順

1. `Value Type`をCase Structureへ接続する。
2. BooleanケースではBoolean定数Falseを`バリアントからデータに変換`の`type`へ接続する。
3. I32ケースではI32定数0を`type`へ接続する。
4. U32、DBL、Stringも対応型定数を接続する。
5. `Value Variant`を各ケースの`variant`へ接続する。
6. 変換値をVariantへ再変換して共通出力へ接続するか、型別出力を持つ公開VIへ渡す。
7. 変換エラーsourceへ期待型を追加する。

# 9.9.3 `CANalyzer_Write_Typed_Value.vi`

入力値を`Value Type`に従って検証し、バリアントへ変換して`CAN_AX_Write_Variable_Value.vi`へ渡す。

TestStandからの数値はDBLで渡されやすいため、I32指定時は小数部が0で範囲内であることを検証してからI32へ変換する。

# 9.9.4 `CANalyzer_Wait_Measurement_State.vi`

### 0. 目的と処理概要

MeasurementのRunningが期待値になるまでポーリングし、Timeoutで終了する。

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Measurement Ref` | 入力 | ActiveX Refnum |
| `Expected Running?` | 入力 | Boolean |
| `Timeout ms` | 入力 | U32 |
| `Poll Interval ms` | 入力 | U32 |
| `error in` | 入力 | error cluster |
| `Actual Running?` | 出力 | Boolean |
| `Elapsed ms` | 出力 | U32 |
| `error out` | 出力 | error cluster |

### 2. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 |
|---:|---|---|
| 1 | Whileループ | While Loop |
| 2以上 | 経過時間を取得 | Tick Count |
| 1 | 待機 | Wait (ms) |
| 1 | `CAN_AX_Get_Measurement_Running.vi` | SubVI |
| 複数 | 比較・複合演算 | Comparison / Compound Arithmetic |

### 3. 配線順

1. ループ開始前にTick Countを取得し`Start Tick`とする。
2. While Loop内でRunningを読む。
3. `Actual Running? == Expected Running?`を作る。
4. 現在TickとStart Tickの差を`Elapsed ms`とする。
5. `Elapsed ms >= Timeout ms`を作る。
6. 状態一致、Timeout、error.statusのORをLoop停止条件へ接続する。
7. 継続時だけ`Poll Interval ms`をWaitへ接続する。
8. Timeout時はcode=`-710104`を生成する。

Poll Intervalの推奨初期値は100ms。TimeoutはTestStand条件から変更可能にする。

# 9.9.5 `CANalyzer_Session_Registry.vi`

### 0. 目的と処理概要

ActiveX参照をLabVIEW内部に保持し、外部へU32 Session IDだけを公開する。

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Action` | 入力 | Enum：Create / Get / Update / Remove / Clear All |
| `Session ID` | 入力 | U32 |
| `Session In` | 入力 | `CANalyzer_Session_State.ctl` |
| `error in` | 入力 | error cluster |
| `Session ID Out` | 出力 | U32 |
| `Session Out` | 出力 | Session Cluster |
| `Found?` | 出力 | Boolean |
| `error out` | 出力 | error cluster |

### 2. 実装方式

- VI実行方式を`非再入実行`にする。
- While Loopを1回だけ実行する構造にする。
- 非初期化シフトレジスタへSession配列とNext Session IDを保持する。
- Removeは配列から削除するだけとし、ActiveX参照のCloseは`CANalyzer_Close.vi`で先に実施する。

### 3. 単体テスト

Create → Get → Update → Get → Remove → Getの順に実行し、Session IDとFound?を確認する。

# 9.9.6 `CANalyzer_Execute_Command.vi`

### 0. 目的と処理概要

すべてのActiveX操作を1本の非再入VIへ通し、TestStandの複数Threadから異なる公開VIが同時実行されてもActiveX呼出しを直列化する。

Public VIは直接Wrapperを呼ばず、原則として本VIへCommandを渡す。

```text
Public VI
  → Command Cluster
  → CANalyzer_Execute_Command.vi（非再入）
  → Session Registry
  → ActiveX Wrapper / Service
  → Result Cluster
```

初期PoCではWrapperを直接呼んでもよい。本番化前にDispatcher経由へ統一する。

---

# 9.10 Public API VI作成

# 9.10.1 `CANalyzer_Open.vi`

### 0. 目的と処理概要

CANalyzer Application取得、Version確認、Configuration確認、Measurement Ref取得、Session登録を1イベントとして実行する。

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Launch Mode` | 入力 | Enum |
| `Configuration Path` | 入力 | Path |
| `Open Configuration?` | 入力 | Boolean |
| `Start Measurement?` | 入力 | Boolean |
| `Startup Timeout ms` | 入力 | U32 |
| `Measurement Timeout ms` | 入力 | U32 |
| `Compatibility Policy` | 入力 | Enum |
| `error in` | 入力 | error cluster |
| `Session ID` | 出力 | U32 |
| `Version String` | 出力 | String |
| `Actual Configuration Path` | 出力 | Path |
| `Attached Existing?` | 出力 | Boolean |
| `Application Started By LabVIEW?` | 出力 | Boolean |
| `Measurement Started By LabVIEW?` | 出力 | Boolean |
| `Running?` | 出力 | Boolean |
| `Compatibility Status` | 出力 | Enum |
| `error out` | 出力 | error cluster |

### 3. 処理順

```text
error in確認
  ↓
Launch ModeをOpen New Instance?へ変換
  ↓
CAN_AX_Open_Application.vi
  ↓
Version取得
  ↓
Compatibility確認
  ↓
必要ならConfiguration Open
  ↓
Actual cfg Path取得・比較
  ↓
System Ref取得
  ↓
Measurement Ref取得
  ↓
Running確認
  ↓
Start Measurement?かつ停止中ならStart
  ↓
Running=True待ち
  ↓
所有権FlagをSession Clusterへ格納
  ↓
Session Registry Create
  ↓
Session ID出力
```

途中失敗時は、その時点までに取得した子参照を閉じる。LabVIEWが新規起動したApplicationでOpenが失敗した場合、Quit可否を確認したうえで終了処理を行う。

### 4. 単体テスト

| 条件 | 期待結果 |
|---|---|
| 手動起動、正しいcfg、Running中 | Attach Existing、Start所有権=False |
| 未起動、Launch If Needed | CANalyzer起動、Application所有権=True |
| 停止中、Start=True | Running=True、Measurement所有権=True |
| cfg不一致 | Policyに従いErrorまたはWarning |
| 未検証版、Probe成功 | Compatible With Warning |
| COM未登録 | Openエラー、Session未作成 |

# 9.10.2 `CANalyzer_Write_SysVar.vi`

### 入出力

```text
Session ID       U32
Namespace        String
Variable Name    String
Value Type       Enum
Value            Variant
Verify After Write? Boolean
error in

Written Value    Variant
Verified?        Boolean
error out
```

### 処理順

1. Session IDでRegistryをGetする。
2. System Refを取得する。
3. NamespaceとVariable Nameを検証する。
4. `CANalyzer_Resolve_SysVar.vi`でVariable Refを取得する。
5. Typed ValueをVariantへ変換する。
6. Valueを書き込む。
7. Verify=Trueなら同じVariableを読み戻す。
8. 期待値と読戻し値を型に応じて比較する。
9. Variable RefをClose Referenceで閉じる。
10. error sourceへSession ID、Namespace、Variable Nameを追加する。

# 9.10.3 `CANalyzer_Read_SysVar.vi`

Writeと同じ参照解決を行い、ValueをVariantで取得した後、Value Typeに従って検証する。

# 9.10.4 Batch Read / Write

`CANalyzer_SysVar_Request.ctl`一次元配列をFor Loopへ自動指標付けし、1反復で1System Variableを処理する。

```text
N端子：未配線
自動指標付け：有効
反復数：Request配列の要素数
```

各反復でResult Clusterを作り、For Loop右枠の自動指標付け出力からResult配列を作る。

`Wait ms > 0`の場合だけ操作後にWaitする。エラー時は`Continue On Error?`に従い、継続または後続をSkippedとして出力する。

# 9.10.5 `CANalyzer_Set_Message_Fault.vi`

### 0. 目的と処理概要

CAPLが使用する故障注入System Variableをまとめて設定する。

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Session ID` | 入力 | U32 |
| `Namespace` | 入力 | String |
| `Alive Fault?` | 入力 | Boolean |
| `Checksum Fault?` | 入力 | Boolean |
| `Timeout Fault?` | 入力 | Boolean |
| `Verify?` | 入力 | Boolean |
| `error in` | 入力 | error cluster |
| `error out` | 出力 | error cluster |

### 3. 書込値

```text
ALIVE_COUNTER = Alive Fault?    False→0 / True→1
CHECKSUM      = Checksum Fault? False→0 / True→1
TIMEOUT       = Timeout Fault?  False→0 / True→1
```

3要素のRequest配列を作り、`CANalyzer_Batch_Write_SysVar.vi`を呼ぶ。

# 9.10.6 `CANalyzer_Clear_Message_Faults.vi`

指定Namespaceの`ALIVE_COUNTER`、`CHECKSUM`、`TIMEOUT`へ0を書き込む。

# 9.10.7 `CANalyzer_Clear_All_Faults.vi`

CAPLで使用する全Namespace一覧を入力配列または外部条件ファイルから受け取り、各Namespaceの3変数を0へ戻す。

Namespace一覧をVIへ固定しない。試験環境ごとにTestStand変数またはCSVで差し替える。

# 9.10.8 `CANalyzer_Health_Check.vi`

次を返す。

```text
Session Found?
Application Ref Valid?
Measurement Running?
Actual Configuration Path
Version String
Known SysVar Read Result
Compatibility Status
```

# 9.10.9 `CANalyzer_Stop.vi`

Measurement Started By LabVIEW?がTrueの場合だけStopする。Falseの場合はRunning状態を読むだけで、手動開始Measurementを停止しない。

# 9.10.10 `CANalyzer_Close.vi`

### 処理順

```text
Session Registry Get
  ↓
必要ならClear All Faults
  ↓
Measurement Started By LabVIEW?ならStop
  ↓
Measurement Ref Close Reference
  ↓
System Ref Close Reference
  ↓
Application Started By LabVIEW?かつQuit有効ならQuit
  ↓
Application Ref Close Reference
  ↓
Session Registry Remove
```

Cleanup用VIのため、前段`error in.status=True`でも終了処理を試みる。元エラーとCleanupエラーはMerge Errorsで統合し、元エラーを優先して保持する。

---

# 9.11 最小PoC用VI

PoCは単純なActiveX疎通と、新規機能を分ける。

# 9.11.1 `PoC_CANalyzer_01_Open_Close.vi`

## 目的

ActiveX Class選択、Automation Open、Property Node、Close Referenceの最小経路を確認する。

## 構成

```text
CAN_AX_Open_Application.vi
  → CAN_AX_Get_System.vi
  → System Ref Close Reference
  → Application Ref Close Reference
```

## 合格条件

- CANalyzer起動済みで参照取得できる。
- CANalyzer未起動で`open new instance=False`の実挙動を記録できる。
- 実行後に参照エラーやプロセス残留異常がない。

# 9.11.2 `PoC_CANalyzer_02_SysVar_Read_Write.vi`

## 入力例

```text
Namespace     = ID03AD5D62
Variable Name = CORE_SVS_OPE_MODE_COM
Write Value   = 2
Value Type    = I32
```

## 構成

```text
Open Application
  → Get System
  → Resolve SysVar
  → Read Before
  → Write
  → Read After
  → Close Variable / System / Application Ref
```

## 合格条件

- Read Beforeを表示できる。
- Write後のCANalyzer画面値が2になる。
- Read Afterが2になる。
- 不正Variable名で名称付きエラーになる。

# 9.11.3 `PoC_CANalyzer_03_Launch_Config_Start.vi`

## 確認項目

```text
CANalyzer未起動から起動
指定cfg Open
Actual cfg Path一致
Measurement Start
Running=True待ち
Stop
LabVIEWが起動したCANalyzerだけQuit
```

ConfigurationとVersion関連メンバが確定してから作成する。

# 9.11.4 `PoC_CANalyzer_04_Fault_Control.vi`

## テスト順

```text
1. ALIVE_COUNTER=0、CHECKSUM=0、TIMEOUT=0
2. Alive Fault=True
3. DUTまたはCANalyzer TraceでAlive固定を確認
4. Alive Fault=False
5. Checksum Fault=True
6. Checksum異常を確認
7. Checksum Fault=False
8. Timeout Fault=True
9. 対象フレーム停止を確認
10. Clear Message Faults
```

# 9.11.5 `PoC_CANalyzer_05_Compatibility.vi`

Version文字列とCapability Probe結果を表示し、検証済み版・未知版・必須機能不足の3条件を確認する。

---

# 9.12 TestStandなしの本番環境VI

# 9.12.1 `CANalyzer_Standalone_Main.vi`

## 0. 目的と処理概要

LabVIEW単体でCANalyzer起動、cfg確認、Measurement開始、SysVar操作、故障注入、Cleanupまで実行する。本番公開APIを順に呼び、ActiveX Wrapperを直接呼ばない。

## 状態

```text
Initialize
Open
Verify
Start
Run Sequence
Clear Faults
Stop
Close
Done
Error Cleanup
```

## 基本フロー

```text
CANalyzer_Open.vi
  ↓
CANalyzer_Health_Check.vi
  ↓
CANalyzer_Batch_Write_SysVar.vi
  ↓
Wait / 判定
  ↓
CANalyzer_Batch_Read_SysVar.vi
  ↓
必要ならCANalyzer_Set_Message_Fault.vi
  ↓
CANalyzer_Clear_All_Faults.vi
  ↓
CANalyzer_Stop.vi
  ↓
CANalyzer_Close.vi
```

## 条件入力

`CANalyzer_Standalone_Config.ctl`へ次を持たせる。

```text
Launch Mode
Configuration Path
Open Configuration?
Start Measurement?
Timeout ms
Poll Interval ms
SysVar Request配列
Fault対象Namespace配列
Stop On First Error?
Log Path
```

Excel直接読込をCore機能へ入れない。標準はCSVまたはLabVIEW Cluster配列とし、既存Excel互換が必要な場合だけ`CANalyzer_Import_Legacy_Excel.vi`を追加する。

---

# 9.13 TestStand利用時の構成

# 9.13.1 Adapter

- TestStand 2026 Q1 64bitを使用する。
- LabVIEW AdapterはLabVIEW 2026 Q1 64bit Development Systemまたは64bit Run-Time Engineへ合わせる。
- TestStandから`10_ActiveX_Wrapper`と`20_Service`を直接呼ばない。
- `30_Public`だけを呼ぶ。

# 9.13.2 変数

| TestStand変数 | 型 | 用途 |
|---|---|---|
| `FileGlobals.CANalyzer.SessionID` | Number / U32相当 | Session識別子 |
| `FileGlobals.CANalyzer.IsConnected` | Boolean | Cleanup判定 |
| `FileGlobals.CANalyzer.IsMeasuring` | Boolean | Stop判定 |
| `FileGlobals.CANalyzer.AppStartedByLabVIEW` | Boolean | Quit判定 |
| `FileGlobals.CANalyzer.MeasStartedByLabVIEW` | Boolean | Stop所有権 |
| `FileGlobals.CANalyzer.ConfigPath` | String | 実cfg |
| `FileGlobals.CANalyzer.Version` | String | 実版 |
| `FileGlobals.CANalyzer.Compatibility` | String / Number | 判定 |
| `Locals.CANalyzer.Requests` | Array of Container | Batch条件 |
| `Locals.CANalyzer.Results` | Array of Container | Batch結果 |
| `Locals.CANalyzer.FaultNamespaces` | Array of String | Cleanup対象 |

ActiveX RefnumとVariant RawをFileGlobalsへ保存しない。

# 9.13.3 Setup

```text
CANalyzer_Open.vi
  Launch Mode          = Launch If Needed
  Configuration Path   = Parameters.CfgPath
  Open Configuration?  = True
  Start Measurement?   = True

保存：
  Session ID
  Version
  Actual Config Path
  Ownership Flags
  Running
  Compatibility
```

Open成功後に`IsConnected=True`、Running確認後に`IsMeasuring=True`とする。

# 9.13.4 Main

```text
CANalyzer_Batch_Write_SysVar.vi
  → Wait
  → DUT操作
  → CANalyzer_Batch_Read_SysVar.vi
  → 判定
```

故障注入試験：

```text
CANalyzer_Set_Message_Fault.vi
  → Wait
  → DUT異常検出確認
  → CANalyzer_Clear_Message_Faults.vi
```

WaitはTestStandで管理するのを基本とする。既存4列テーブル互換の`Wait ms`はBatch単体PoCまたはデータ駆動シナリオ用に使用する。

# 9.13.5 Cleanup

```text
If IsConnected:
    CANalyzer_Clear_All_Faults.vi

If IsMeasuring:
    CANalyzer_Stop.vi

CANalyzer_Close.vi
```

前段エラーがあってもCleanupを続行する。Clear All Faults失敗だけでStopとCloseを打ち切らない。

# 9.13.6 並列実行

TestStandからCANalyzer公開APIを複数Threadで同時実行しない。

必要な場合は次の両方を使用する。

```text
LabVIEW側：CANalyzer_Execute_Command.viを非再入実行
TestStand側：同一Session操作をNamed Lockで直列化
```

Named Lock例：

```text
CANalyzer.ActiveX.Session.<SessionID>
```

---

# 9.14 Errorとログ

## 9.14.1 ローカルエラーコード

| code | 用途 |
|---:|---|
| `-710100` | CANalyzer ActiveX Open失敗 |
| `-710101` | 必須Capability不足 |
| `-710102` | Session ID未登録 |
| `-710103` | Configuration不一致 |
| `-710104` | Measurement状態待ちTimeout |
| `-710105` | Namespace / Variable解決失敗 |
| `-710106` | Variant型変換失敗 |
| `-710107` | Batch Request不正 |
| `-710108` | Fault Clear失敗 |

## 9.14.2 error sourceへ含める情報

```text
Public VI名
ActiveX Wrapper名
Session ID
Launch Mode
CANalyzer Version
Configuration Path
Namespace
Variable Name
Value Type
Batch Index
元のActiveX error source
```

## 9.14.3 ログ項目

```text
日時
試験ID
Session ID
CANalyzer Version
Configuration Path
Measurement Running
Namespace
Variable Name
操作 Read / Write
要求値
読戻し値
Wait ms
結果
error code / source
```

---

# 9.15 完了条件

## 9.15.1 ActiveX基盤

- [ ] CANalyzer ApplicationクラスをLabVIEWで選択できる
- [ ] 起動済みCANalyzerへ接続できる
- [ ] CANalyzer未起動から起動できる
- [ ] System Refを取得できる
- [ ] Measurement Runningを読める
- [ ] Start / Stopできる
- [ ] 子参照とApplication参照を明示Closeできる

## 9.15.2 System Variable

- [ ] 既知I32をRead / Writeできる
- [ ] Boolean / DBL / Stringを確認できる
- [ ] 不正Namespaceを検出できる
- [ ] 不正Variableを検出できる
- [ ] Batchで行単位Resultを返せる
- [ ] Wait msを実行できる

## 9.15.3 CAPL連携

- [ ] System Variable値がCAN信号へ反映される
- [ ] Alive CounterがCAPLで0→1→2→3と更新される
- [ ] ChecksumがCAPLで生成される
- [ ] Alive Faultでカウンター固定を確認できる
- [ ] Checksum Faultで異常値を確認できる
- [ ] Timeout Faultで対象フレーム停止を確認できる
- [ ] Cleanupで全Faultを正常値へ戻せる

## 9.15.4 Version・別環境

- [ ] CANalyzer Versionを取得できる
- [ ] 検証済み版をCompatibleと判定できる
- [ ] 未知版でCapability Probeできる
- [ ] Wrapper以外がCANalyzer ActiveX型へ依存していない
- [ ] 別PCでCOM登録とType Libraryを確認できる

## 9.15.5 TestStand

- [ ] 64bit Adapterで公開APIを呼べる
- [ ] Session IDをFileGlobalsへ保持できる
- [ ] SetupでOpen / Startできる
- [ ] MainでRead / Write / Fault操作できる
- [ ] CleanupでFault Clear / Stop / Closeできる
- [ ] 手動起動CANalyzerを勝手にQuitしない
- [ ] LabVIEW起動CANalyzerだけ必要に応じてQuitできる

---

# 9.16 今後必要な実機情報

次が判明した時点で本章の`実機確認待ち`を更新する。

1. CANalyzerの製品版・Service Pack・Build番号。
2. Type Library上のApplication Version取得Property。
3. Configuration Open Methodの正式名称と引数。
4. Actual Configuration Path取得Property。
5. Application Quit Methodの正式名称。
6. `open new instance=True`時のCANalyzer実挙動。
7. PoCに使用するcfgの絶対パス。
8. PoCに使用するRead専用・Read/Write可能System Variable各1個。

---

# 9.17 他方式との関係

CANalyzer ActiveXを本方式として実装するが、物理CANインタフェースの代替候補は残す。

| 方式 | 使用条件 |
|---|---|
| CANalyzer ActiveX | 既存CAPL、残バス、System Variableを再利用する場合 |
| NI-XNET | DBC信号中心でLabVIEW内へCANを閉じる場合 |
| メーカーUSB-CAN | 既存USB-CAN資産を利用する場合 |
| RAMScope GT170 CAN | RAM計測とCANを同一Timestamp系へ集約する場合 |

複数方式を同じ本番試験で同一CAN IDの送信主体として同時使用しない。
