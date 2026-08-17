# 09. CANalyzer ActiveX実装ガイド

<!-- generated-vi-diagram -->
![CANalyzer公開API接続](./assets/vi-diagrams/canalyzer-public-api-flow.svg)

> **本章の役割**：既存のPython COM APIロジックをLabVIEW 2026 Q1 64bitのActiveX機能へ置き換え、CANalyzerの接続・新規起動・Configuration確認・Measurement制御・System Variable読書き・故障注入・最小PoC・LabVIEW単体本番VI・TestStand組み込みまでを、画面操作で再現できる粒度で定義する。
>
> VI作成手順は[00A_LabVIEW実装資料の記述ルール.md](./00A_LabVIEW実装資料の記述ルール.md)を正とし、ActiveXの一般仕様とCANalyzer固有Type Libraryの確認順は[00C](./00C_一次資料とバージョン基準.md)に従う。
>
> CANalyzer COM APIのプロパティ名・メソッド名は、対象PCに登録されたCANalyzer Type Libraryを一次情報とする。CANalyzerの版によって表示名や引数が異なる場合は推測で固定せず、`実機確認待ち`として`10_ActiveX_Wrapper`だけを差し替える。
>
> **2026-08-17 実装追補**：LabVIEW 2026 Q3 / CANalyzer 12.0 Type Library Version 1.3bで実際に確認したInterface、作成済みWrapper / Serviceの具体的配線、参照所有権、error正規化、Coding Agent制約、次回再開位置は[`09A_CANalyzer_ActiveXラッパ実装実績.md`](./09A_CANalyzer_ActiveXラッパ実装実績.md)へ統合している。既存VIの手順は09A側で実型・実配線とマージして記録し、別の重複手順は作らない。

**最終整理日：2026-08-17**

---

# 9.1 採用方針と現在地

## 9.1.1 確定事項

| 項目 | 採用内容 | 状態 |
|---|---|---|
| LabVIEW | 2026 Q3 64bit | 確定 |
| TestStand | 2026 Q3 64bit | 確定 |
| CANalyzer | 64bit | 確定 |
| CANalyzer版 | 12.0 Type Library Version 1.3b | 開発PC確認済み |
| 制御方式 | LabVIEW ActiveX Automation | 採用 |
| ProgID | `CANalyzer.Application` | 既存ロジックで使用済み |
| 起動済み環境 | 既存CANalyzerを再利用 | 必須 |
| 未起動環境 | LabVIEWからCANalyzerを起動 | 必須 |
| Configuration | 指定cfgを開く、または実cfgと照合 | 必須 |
| Measurement | Running確認、Start、Stop、Timeout | 必須 |
| Tx/Rx | System VariableのValue読書き | 必須 |
| 周期送信 | CAPLのTimerで実施 | 確定 |
| Alive Counter | CAPLで生成 | 確定 |
| Checksum | CAPLで生成 | 確定 |
| 故障注入 | System Variable経由でCAPLへ指示 | 確定 |

## 9.1.2 本章の実装範囲

```text
LabVIEW / TestStand
  ↓
30_Public
  ↓ Session IDと通常の数値・文字列・Booleanだけを公開
20_Service
  ↓ ActiveX参照保持、型変換、待ち、直列化
10_ActiveX_Wrapper
  ↓ Property Node / Invoke Node
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

LabVIEWはCAN Payloadを直接組み立てない。通常送信用のAlive Counter生成VIとChecksum生成VIは作成しない。

---

# 9.2 既存COM APIロジックとの対応表

## 9.2.1 既存Python版の入力

既存ロジックは次の4列を持つExcelを読み込む。

| 列 | 意味 |
|---|---|
| `ID` | CANalyzer System VariableのNamespace |
| `Name` | Variable名 |
| `data` | Tx値 |
| `Wait` | 操作後の待ち時間、秒 |

基本アクセス：

```text
app.System.Namespaces("Namespace").Variables.Item("Variable").Value
```

RxはValueを読みログへ出す。TxはValueへ値を書き込む。

## 9.2.2 対応表

| 機能 | 既存Python COM API | LabVIEW ActiveX版 | ActiveX版で追加する理由 |
|---|---|---|---|
| Application取得 | `Dispatch("CANalyzer.Application")` | オートメーションを開く（Automation Open） | LabVIEW標準ActiveX機能へ統一 |
| 起動済み環境 | 起動済みを運用前提 | `Require Existing` | 未起動なら意図せず試験を始めない |
| 再利用または起動 | Dispatch挙動へ依存 | `Reuse Existing Or Launch` | 起動状態に関係なく自動準備 |
| 新規インスタンス要求 | なし | `Force New Instance` | PoC・複数構成の検証用 |
| 起動所有権 | なし | External / LabVIEW / Unknown | CleanupでQuit可否を判断 |
| cfg指定 | なし | Configuration Open | 試験対象cfgを自動準備 |
| cfg一致確認 | なし | Expected / Actual Path比較 | 誤cfg接続を検出 |
| Measurement確認 | なし | Running読出し | CAPL Timerが動く状態を確認 |
| Measurement開始 | 手動前提 | Start + Running待ち | Setupを自動化 |
| Measurement停止 | なし | 所有権付きStop | 手動開始Measurementを勝手に止めない |
| SysVar Tx | Valueへ代入 | `CANalyzer_Write_SysVar.vi` | 型検証、Verify、ログを追加 |
| SysVar Rx | Value読出し | `CANalyzer_Read_SysVar.vi` | 期待型と取得結果を明示 |
| 直列アクセス | 必須 | Resolver内へ集約 | 参照の取り違えを防ぐ |
| 行単位継続 | 例外時continue | Batch Policy | Stop / Continueを条件化 |
| Wait | 仕様書のみ | `Wait ms`を実装 | 仕様と実装を一致させる |
| Rx Excel書戻し | なし | 標準ではログのみ | 現行仕様を維持 |
| Session管理 | なし | Session Registry | ActiveX参照をTestStandへ出さない |
| 参照解放 | Python終了に依存 | Close Referenceを明示 | 長時間運転の参照リーク防止 |
| Version対応 | なし | Wrapper隔離 + Capability Probe | 別版で影響範囲を限定 |
| 故障注入 | 汎用SysVar書込 | 専用公開VI | TestStandの条件を分かりやすくする |
| Cleanup | なし | Fault Clear → Stop → Close | 次試験へ状態を残さない |

## 9.2.3 既存コードから引き継ぐ修正

- Txコードの列名`deta`は誤記であり、正式名を`data`とする。
- 互換Importerでは`deta`を検出した場合だけWarningを出して読込可能としてよい。
- 仕様書にある`Wait`は既存コードに未実装のため、LabVIEW版で初めて実装する。
- ExcelはCore層の必須依存にしない。標準入力はCluster配列またはCSVとする。

---

# 9.3 LabVIEW上で実施する動作

## 9.3.1 起動・接続

```text
A. 起動済みCANalyzerを再利用する
B. CANalyzerが未起動ならLabVIEWから起動する
C. 新規インスタンス作成を要求する
D. COM未登録、起動失敗、参照無効を区別する
E. Applicationを誰が起動したかを保持する
```

## 9.3.2 Configuration

```text
A. 指定cfgを開く
B. 起動済みCANalyzerの実cfgを取得する
C. Expected PathとActual Pathを比較する
D. 不一致時のError / WarningをPolicyで選ぶ
E. cfgをLabVIEWが開いたか保持する
```

## 9.3.3 Measurement

```text
A. Runningを読む
B. 停止中ならStartする
C. Running=Trueまでポーリングする
D. Timeoutで明確なエラーを返す
E. LabVIEWがStartしたMeasurementだけStopする
```

CAPLは`on start`で10、40、100、300、500、1000msのTimerを開始する。Mainへ進む前にMeasurementがRunningであることを確認する。

## 9.3.4 System Variable

```text
A. 1変数を書き込む
B. 1変数を読み取る
C. 複数変数を順番に処理する
D. Boolean / I32 / U32 / DBL / Stringを扱う
E. Namespace / Variable不存在を名称付きエラーにする
F. Write後にRead BackでVerifyできる
```

## 9.3.5 故障注入

```text
ALIVE_COUNTER = 0  → CAPLがAliveを正常更新
ALIVE_COUNTER != 0 → CAPLがAlive更新を停止

CHECKSUM = 0 → 正常Checksum
CHECKSUM = 1 → CAPLがChecksum+1を送信

TIMEOUT = 0 → output(message)
TIMEOUT != 0 → CAPLが対象フレームを送信しない
```

LabVIEWはこれらのSystem Variableを操作する。Alive Counter計算とChecksum計算はCAPLへ残す。

## 9.3.6 Cleanup

```text
故障注入System Variableを0へ戻す
  ↓
LabVIEWが開始したMeasurementだけStop
  ↓
子ActiveX参照をClose
  ↓
LabVIEW所有Applicationだけ必要に応じてQuit
  ↓
Application RefをClose
  ↓
Session Registryから削除
```

---

# 9.4 動作に必要なロジックとLabVIEW機能

| 必要ロジック | LabVIEW機能 | 主な用途 |
|---|---|---|
| ActiveX Server参照取得 | オートメーションを開く（Automation Open） | CANalyzer Application |
| Property読書き | プロパティノード（Property Node） | System、Measurement、Running、Value |
| Method呼出し | インボークノード（Invoke Node） | Start、Stop、cfg Open、Quit候補 |
| 参照解放 | リファレンスを閉じる（Close Reference） | ActiveX Ref解放 |
| LabVIEW値→Variant | バリアントへ変換（To Variant） | Wrapperへ渡す書込値 |
| Variant→LabVIEW値 | バリアントからデータに変換（Variant To Data） | Read値の型変換 |
| 型別処理 | ケースストラクチャ（Case Structure） | Value Type分岐 |
| Batch | Forループ（For Loop） | Request配列処理 |
| Measurement待ち | Tick Count + Wait (ms) | Timeout付きポーリング |
| Session保持 | 非初期化シフトレジスタを持つFGV | ActiveX参照保持 |
| 呼出し直列化 | 非再入Dispatcher | Thread競合防止 |
| 起動前後のプロセス確認 | System Execまたは実機で確定した検出方法 | Application所有権推定 |
| エラー情報追加 | 文字列にフォーマット（Format Into String） | 操作名、Namespace等をsourceへ追加 |

## 9.4.1 ActiveX機能の配置場所

| 日本語名 | 英語名 | 配置場所 |
|---|---|---|
| オートメーションを開く | Automation Open | 接続 → ActiveX |
| プロパティノード | Property Node | 接続 → ActiveX |
| インボークノード | Invoke Node | 接続 → ActiveX |
| リファレンスを閉じる | Close Reference | 接続 → ActiveX、またはプログラミング → アプリケーション制御 |
| バリアントへ変換 | To Variant | プログラミング → クラスタ、クラス、バリアント |
| バリアントからデータに変換 | Variant To Data | プログラミング → クラスタ、クラス、バリアント |

見つからない場合は`Ctrl + Space`で英語名を検索する。

---

# 9.5 Version依存と起動所有権

## 9.5.1 完全なVersion非依存ではない

Property NodeとInvoke Nodeは、開発時に選択したActiveX Type Libraryの型情報を保持する。すべてのCANalyzer版で無条件に動作することは保証できない。

```text
コンパイル時依存
  → 10_ActiveX_Wrapperだけへ閉じ込める

実行時判定
  → Version + Capability Probeで判定する
```

Public、Service、TestStandはCANalyzer固有ActiveX型へ依存させない。

## 9.5.2 Compatibility判定

| 判定 | 意味 |
|---|---|
| `Compatible` | 既知Versionで主要機能を確認済み |
| `Compatible With Warning` | 未知VersionだがCapability Probe成功 |
| `Unsupported` | 必須Capability不足 |
| `Unknown` | Version取得やProbe自体に失敗 |

---

# 9.6 以降の詳細設計

以降の詳細な既存設計、VI一覧、Phase、Public API、Fault、Cleanup、Standalone、TestStand統合は従来の`09_CAN通信の実装.md`を正とする。

**ただし、2026-08-17に実際に作成したVIの具体的な手順は、既存手順とマージした[`09A_CANalyzer_ActiveXラッパ実装実績.md`](./09A_CANalyzer_ActiveXラッパ実装実績.md)を実装時の追補正本とする。**

次回再開位置：

```text
Phase 6
PoC_CANalyzer_02_SysVar_Read_Write.vi
```
