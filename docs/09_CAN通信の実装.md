# 09. CAN 通信の実装方針

> **本章の役割**：CAN通信方式の候補を比較し、方式決定後に採用ルートだけを実装するための判断資料。
>
> RAMScopeのRAM計測実装はすでに64bit API直呼び方式で確定しているが、**CAN送受信をどのインタフェースで行うかは未決定**である。
> 同じCAN IDを複数方式から同時送信しない。

**最終整理日：2026-07-14**

---

## 9.1 現在の候補

| 方式 | 主な用途 | 強み | 主な制約 |
|------|----------|------|----------|
| CANalyzer COM / ActiveX | 既存CAPL、残バス、System Variableを再利用 | 既存資産を最も活用できる | CANalyzerライセンス、事前状態、別プロセス |
| NI-XNET | DBC信号ベースの送受信 | LabVIEWとの統合が素直 | NIハードウェアが必要 |
| メーカーUSB-CAN | 既存USB-CAN資産を利用 | 導入コストを抑えられる場合がある | DBC変換やAPIラップが必要な場合あり |
| RAMScope GT170 CAN | RAM計測とCANを同一機器へ集約 | RAM/CANの時刻を合わせやすい | APIラップ、ペイロード生成、排他制御が必要 |

方式決定までは共通I/Oと評価項目だけを定義し、本番VIを複数方式で並行量産しない。

---

## 9.2 共通要件

方式にかかわらず、TestStandから見える操作は可能な範囲で統一する。

```text
CAN_Open.vi
CAN_Send.vi
CAN_Read.vi
CAN_Close.vi
```

必要に応じて次を追加する。

```text
CAN_Start.vi
CAN_Stop.vi
CAN_Load_Config.vi
CAN_Send_Scenario.vi
```

### 共通端子

| 区分 | 端子例 |
|------|--------|
| 入力 | CAN ID、チャンネル、周期、ペイロード、信号値、タイムアウト、error in |
| 出力 | 受信値、受信フレーム、Timestamp、Status、TestError、error out |
| 参照 | 採用APIが参照を返す場合だけin/outを持つ |

### 共通設計

- 試験条件はTestStandまたは外部条件ファイルで管理する。
- 待ち、繰り返し、送信タイミング、異常時分岐はTestStandで管理する。
- アライブカウンタとチェックサムは独立した変換VIへ閉じ込める。
- 送信前後の生ペイロードをログへ残す。
- 受信値だけでなく、CAN ID、DLC、Timestamp、受信エラーも記録する。
- 同一バスへ複数の送信主体を接続する場合は、ID重複と周期送信の衝突を確認する。

---

# 9.3 方式A：CANalyzer COM / ActiveX

## 9.3.1 確認済みの接続方式

CANalyzerはCOM Automationを公開しており、LabVIEWのActiveX機能から操作できる。

```text
ProgID: CANalyzer.Application
```

System Variableの基本アクセス：

```text
Application
  → System
    → Namespaces(<Namespace>)
      → Variables
        → Item(<VariableName>)
          → Value
```

- Valueへ書き込むとTx操作。
- Valueを読み取るとRxまたは状態取得。
- 対象の値がCANalyzer側でSystem Variableとして公開されていることが前提。

## 9.3.2 作成するVI

| VI | 役割 |
|----|------|
| `CAN_COM_Connect.vi` | CANalyzer Application参照を取得 |
| `CAN_COM_Check_Measurement.vi` | Measurement.Runningを確認 |
| `CAN_COM_Start_Measurement.vi` | 未測定なら開始し、Running=Trueまで確認 |
| `CAN_COM_Write_SysVar.vi` | 1つのSystem Variableへ値を書き込む |
| `CAN_COM_Read_SysVar.vi` | 1つのSystem Variableを読み取る |
| `CAN_COM_Close.vi` | 参照解放。自分が開始したMeasurementだけ停止 |

### Connect

- `Automation Open`で`CANalyzer.Application`へ接続する。
- 複数プロセス起動を避ける。
- 現在開いているcfgファイルのパスを取得し、期待する設定と一致するか確認する機能を推奨する。

### Measurement

- `Measurement.Running=False`ではCAPLタイマーやノードシミュレーションが動作しない可能性がある。
- 未開始なら`Measurement.Start`を実行する。
- 100ms程度でRunningをポーリングし、上限時間でTimeoutを返す。
- Close時は`MeasurementStartedByLabVIEW=True`の場合だけStopする。

### System Variable

`CAN_COM_Write_SysVar.vi`入力例：

| 端子 | 型 |
|------|----|
| Application参照 | ActiveX Reference |
| Namespace | String |
| Variable Name | String |
| Value | Variant |
| error in | error cluster |

Read VIはValueをVariantで返し、呼び出し側で期待型へ変換する。

## 9.3.3 バッチ実行

多数のSystem Variableを操作する場合でも、本番の順序管理はTestStandを優先する。

CSV等から行一覧を読み、一括VIで処理する場合は、次の2階層に分ける。

- COM接続・Measurement開始失敗：システムエラーとして中断。
- 1行の変数名不正等：行番号付きWarningとして記録し、継続するか試験仕様で決める。

## 9.3.4 採用に向く条件

- 既存CAPL、残バス、パネル、ロギング設定を再利用したい。
- チェックサムやアライブカウンタを既存CAPLが生成している。
- CANalyzerライセンスと運用手順を許容できる。
- RAMデータとのTimestamp統合を後処理で行える。

---

# 9.4 方式B：NI-XNET

## 9.4.1 基本構成

1. NI-XNETと対応CANインタフェースを導入する。
2. XNET Database EditorでDBCを登録する。
3. 信号またはフレームセッションを作成する。
4. TestStandから1イベント1VIでOpen / Send / Read / Closeを呼ぶ。

## 9.4.2 作成するVI

| VI | XNET処理 |
|----|----------|
| `CAN_XNET_Open.vi` | Create Session |
| `CAN_XNET_Send.vi` | SignalまたはFrame Write |
| `CAN_XNET_Read.vi` | SignalまたはFrame Read |
| `CAN_XNET_Close.vi` | Clear Session |

### 設計上の選択

- ECU試験条件を信号名で扱うならSignal Sessionを優先する。
- 生フレーム、E2E、故障注入を細かく制御するならFrame Sessionを検討する。
- DBCに無い独自チェックサムは送信前のペイロード生成VIで処理する。

## 9.4.3 採用に向く条件

- NIハードウェアを導入できる。
- DBCを中心に信号名で試験条件を管理したい。
- LabVIEW内でCAN処理を完結させたい。
- CANalyzerの残バス資産を必須としない。

---

# 9.5 方式C：メーカーUSB-CAN

## 9.5.1 基本構成

1. メーカーのドライバとテストツールを導入する。
2. テストツールで送受信を確認する。
3. メーカー提供LabVIEW VIまたはDLL APIをラップする。
4. DBCのエンコード・デコード方法を決める。

## 9.5.2 注意

- DLL方式ではLabVIEWとDLLのbit数を揃える。
- 受信コールバックよりポーリングAPIを優先するとLabVIEW実装が簡単になる。
- メーカーAPIが生フレームだけを扱う場合、DBC変換層を別VIとして用意する。
- TestStandから見えるI/OはXNET版と可能な範囲で合わせる。

## 9.5.3 採用に向く条件

- 既存USB-CANを流用できる。
- メーカーのLabVIEW対応またはAPI仕様が十分である。
- NI-XNETよりコスト・調達面で有利である。

---

# 9.6 方式D：RAMScope GT170 CAN

## 9.6.1 使用候補API

```c
RAMScopeGT170SendCANDataFrame(...)
RAMScopeGT170ScenarioSendSet(...)
RAMScopeGT170ScenarioSendStart(...)
RAMScopeGT170ScenarioSendStop(...)
```

関数プロトタイプと構造体は`RAMScopeVP.h`を正とする。

## 9.6.2 利点

- RAM計測とCANフレームを同一RAMScope機器へ集約できる。
- 同一測定セッションのTimestampでRAMとCANを関連付けやすい。
- 別のCANインタフェースを減らせる可能性がある。
- Scenario送信を使用するとWindowsループより安定した周期送信を期待できる。

## 9.6.3 制約

- LabVIEW側でC構造体を正しく組み立てる必要がある。
- アライブカウンタ、チェックサム、故障注入用ペイロードは原則LabVIEW側で生成する。
- RAMScopeVP APIのスレッドセーフ性は未確認。
- RAMの`GetBufferData`とCAN送信APIを複数ループから同時実行しない。
- 必要ならDLLアクセスを1つのDevice Accessループへ集約する。

## 9.6.4 単発送信とScenario送信

### 単発送信

毎回変化するペイロード、手動イベント、故障注入に向く。

```text
試験条件
  → Alive / Checksum計算
  → ペイロード生成
  → SendCANDataFrame
```

周期精度はWindows、LabVIEW、TestStandの実行タイミングに依存する。

### Scenario送信

事前に展開できる周期フレームに向く。

```text
カウンタ全パターンを事前生成
  → ScenarioSendSet
  → ScenarioSendStart
  → ハードウェア側で周期送信
  → ScenarioSendStop
```

Scenarioの最大ステップ数、周期単位、繰り返し仕様は使用API版のヘッダと外部仕様書で確認する。

## 9.6.5 採用に向く条件

- RAM値とCANを同じTimestampで取得したい。
- 残バス対象が限定されている。
- CAPL資産へ依存せず、自前実装を保守できる。
- RAMScope APIアクセスを直列化できる。

---

# 9.7 アライブカウンタ・チェックサム

アルゴリズム、ビット位置、初期値、除外バイト、CAN IDの含め方はECU仕様、DBC、CAPL等の一次情報で確定する。

## 9.7.1 分離するVI

```text
CAN_E2E_Encode.vi
CAN_E2E_Check.vi
```

入力例：

- CAN ID
- 元ペイロード
- Alive値
- Aliveの開始bit・bit長
- Checksumの開始bit・bit長
- アルゴリズム種別

出力例：

- 送信用ペイロード
- 次のAlive値
- 計算Checksum
- 検証結果

### 分離する理由

- CANインタフェース方式とE2E計算を独立させられる。
- DBCやECU仕様変更時に計算VIだけを修正できる。
- ダミーペイロードで単体テストできる。
- CANalyzer、XNET、USB-CAN、RAMScopeのどの送信方式にも再利用できる。

## 9.7.2 単体テスト

- カウンタのラップを確認する。
- 既知のCAPLまたは実測フレームとChecksumが一致する。
- Checksum異常、Alive停止、Timeout用ペイロードを生成できる。
- Motorola / Intelのbit配置を混同しない。

---

# 9.8 方式選定表

| 観点 | CANalyzer COM | NI-XNET | USB-CAN | RAMScope CAN |
|------|---------------|---------|---------|--------------|
| 既存CAPL活用 | ◎ | × | × | × |
| DBC信号操作 | ○ | ◎ | △ | △ |
| RAMとのTimestamp統合 | △ | △ | △ | ◎ |
| LabVIEW単独運用 | △ | ◎ | ○ | ◎ |
| 周期送信精度 | CAPL次第 | HW機能次第 | API次第 | Scenarioで○ |
| 導入コスト | ライセンス | NI HW | 機器次第 | 既存GT170活用 |
| 自前実装量 | 小～中 | 中 | 中～大 | 大 |
| 残バス拡張性 | ◎ | ○ | △ | △ |

## 9.8.1 決定手順

1. 必須CAN ID数、周期、残バス、故障注入、ログ要件を一覧化する。
2. 既存CAPLで実現済みの範囲を確認する。
3. RAMデータとのTimestamp同期が必須か決める。
4. 4方式で最小PoCを行う必要はなく、要件で候補を2つ以下へ絞る。
5. 代表Tx / Rx / 周期送信 / 異常注入をPoCする。
6. 採用方式を1つ決め、未採用方式の本番VI量産を止める。

---

# 9.9 PoCと完了条件

## PoC

- [ ] 接続・Openができる
- [ ] 代表CAN IDを送信できる
- [ ] DUTまたはバスモニタでペイロードを確認できる
- [ ] 代表RxをTestStandへ返せる
- [ ] 周期とジッタが試験要件を満たす
- [ ] Alive / Checksumが既知値と一致する
- [ ] Timeout、切断、バスオフ等を検出できる
- [ ] Cleanupで周期送信を停止し、参照・セッションを解放できる

## 方式決定後

- [ ] 採用方式を本章冒頭へ記載する
- [ ] `CAN_Open / Send / Read / Close`の正本を1方式へ固定する
- [ ] 未採用方式は参考案として明記し、本番シーケンスから除外する
- [ ] TestStandの変数、サブシーケンス、Cleanupを採用方式へ合わせる
- [ ] RAMScope CANを採用する場合、[10](./10_RAMScope実装方針.md)のAPI状態と排他ルールに従う
