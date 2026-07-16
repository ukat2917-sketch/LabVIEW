# 09. CAN 通信の実装方針

> **本章の役割**：CAN通信方式の候補を比較し、採用方式を決めた後に、1方式だけを公開APIとして実装するための判断基準とPoC手順を定義する。
>
> 本章は方式選定の正本である。方式決定後の各VI作成手順は[00A](./00A_LabVIEW実装資料の記述ルール.md)の「目的 → 入出力 → 配置関数 → 配線順 → 単体テスト」に従う。

**最終整理日：2026-07-16**

---

## 9.1 現在地と決定方針

RAMScopeのRAM計測は64bit API直呼び方式で確定している。一方、CAN送受信をどのインタフェースで行うかは未確定である。

方式決定までは、共通I/O、評価項目、PoC条件だけを定義する。複数方式の本番VIを並行して量産しない。同一CAN IDを複数の送信主体から同時送信しない。

| 方式 | 主な用途 | 強み | 主な制約 |
|---|---|---|---|
| CANalyzer COM / ActiveX | 既存CAPL、残バス、System Variableを再利用 | 既存資産を活用しやすい | ライセンス、cfg、Measurement状態へ依存 |
| NI-XNET | DBC信号ベースの送受信 | LabVIEWとの統合が素直 | NI対応ハードウェアが必要 |
| メーカーUSB-CAN | 既存USB-CAN資産を利用 | 調達コストを抑えられる可能性 | APIラップとDBC変換が必要な場合あり |
| RAMScope GT170 CAN | RAM計測とCANを同一機器へ集約 | Timestampを合わせやすい | 構造体、ペイロード、排他制御の実装量が多い |

---

## 9.2 TestStandから見える共通API

物理インタフェースが変わっても、可能な範囲で次のイベントへ統一する。

```text
CAN_Open.vi
CAN_Send.vi
CAN_Read.vi
CAN_Close.vi
```

必要に応じて追加する。

```text
CAN_Start.vi
CAN_Stop.vi
CAN_Load_Config.vi
CAN_Send_Scenario.vi
```

### 共通入出力

| 区分 | 端子例 | 記載上の注意 |
|---|---|---|
| 入力 | Channel、CAN ID、DLC、Payload、信号値、周期、Timeout、error in | 数値型、bit幅、単位を明記 |
| 出力 | Rx Frame、信号値、Timestamp、Status、TestError、error out | Raw値と物理値を区別 |
| 参照 | Session / ActiveX Reference | 採用APIが参照を返す場合だけin/outを持つ |

### 共通設計

- 試験条件はTestStandまたは外部条件ファイルで管理する。
- 待ち、繰り返し、送信タイミング、異常時分岐はTestStandで管理する。
- Alive CounterとChecksumは独立した変換VIへ閉じ込める。
- 送信前後の生ペイロードをログへ残す。
- CAN ID、DLC、Timestamp、Channel、受信エラーを記録する。
- 同一バスへ複数の送信主体を接続する場合は、ID重複と周期送信の衝突を確認する。

---

# 9.3 方式A：CANalyzer COM / ActiveX

## 9.3.1 採用理由となる条件

既存CAPL、残バス、System Variable、パネル、ロギング設定を継続利用する場合に有力となる。

CANalyzerはCOM Automationを公開しており、LabVIEWのActiveX機能から操作する。

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

## 9.3.2 作成候補VI

| VI | 主な入力 | 主な出力 | 役割 |
|---|---|---|---|
| `CAN_COM_Connect.vi` | ProgID、error in | Application参照、cfgパス、error out | CANalyzerへ接続 |
| `CAN_COM_Check_Measurement.vi` | Application参照 | Running | Measurement状態取得 |
| `CAN_COM_Start_Measurement.vi` | Application参照、Timeout | StartedByLabVIEW、error out | 必要時だけMeasurement開始 |
| `CAN_COM_Write_SysVar.vi` | Namespace、Variable Name、Variant Value | 書込結果 | System Variable書込 |
| `CAN_COM_Read_SysVar.vi` | Namespace、Variable Name | Variant Value | System Variable読出し |
| `CAN_COM_Close.vi` | Application参照、StartedByLabVIEW | error out | 必要時だけStopし参照解放 |

方式採用後は、各VIについてActiveXノード名、プロパティ名、Invoke Node、参照ワイヤ、Variant変換を00Aの形式で記載する。

## 9.3.3 実装上の注意

- 複数のCANalyzerプロセスを不用意に起動しない。
- 現在開いているcfgファイルのパスを取得し、期待するcfgと一致するか確認する。
- `Measurement.Running=False`ではCAPLタイマーやノードシミュレーションが動作しない可能性がある。
- Measurement開始後は一定周期でRunningを読み、Timeoutを設定する。
- Close時は`MeasurementStartedByLabVIEW=True`の場合だけStopする。
- ValueはVariantで扱われるため、期待する型への変換方法を手順へ明記する。

## 9.3.4 PoCテスト

| テスト | 入力方法 | 期待結果 |
|---|---|---|
| 接続 | 既存CANalyzerを起動してConnect | Application参照取得、cfg一致 |
| Measurement | Running=FalseからStart | 上限時間内にTrue |
| SysVar Write | 既知変数へ値を書込 | CANalyzer画面またはバスで一致 |
| SysVar Read | 既知変数を読出し | 期待Variant値 |
| 不正変数名 | 存在しない名前 | 変数名を含むエラー |
| Cleanup | LabVIEWが開始したMeasurement | Stop後に参照解放 |

---

# 9.4 方式B：NI-XNET

## 9.4.1 採用理由となる条件

DBCを中心に信号名で試験条件を管理し、LabVIEW内でCAN処理を完結させたい場合に有力となる。

## 9.4.2 基本構成

1. NI-XNETと対応CANインタフェースを導入する。
2. NI MAXでインタフェースを確認する。
3. XNET Database EditorでDBCを登録する。
4. Signal SessionまたはFrame Sessionを選択する。
5. TestStandからOpen / Send / Read / Closeを呼ぶ。

## 9.4.3 作成候補VI

| VI | XNET処理 | 単体テストで確認する値 |
|---|---|---|
| `CAN_XNET_Open.vi` | Create Session | Session Ref、Database、Cluster、Interface |
| `CAN_XNET_Send.vi` | SignalまたはFrame Write | 送信値、Raw Payload、Timestamp |
| `CAN_XNET_Read.vi` | SignalまたはFrame Read | 受信値、Timeout、Timestamp |
| `CAN_XNET_Close.vi` | Clear Session | 参照解放、再Open可否 |

### Session選択

- ECU試験条件を信号名で扱う場合はSignal Sessionを優先する。
- 生フレーム、E2E、故障注入を細かく制御する場合はFrame Sessionを検討する。
- DBCにないChecksumは送信前のペイロード生成VIで処理する。

## 9.4.4 PoCテスト

- 代表信号を送信し、CANalyzer等の別モニタで値を確認する。
- 代表フレームを受信し、CAN ID、DLC、Payload、Timestampを確認する。
- DBCのIntel / Motorola、Scale、Offsetを既知値で確認する。
- Timeout、バスオフ、ケーブル切断を確認する。

---

# 9.5 方式C：メーカーUSB-CAN

## 9.5.1 採用理由となる条件

既存USB-CANを流用でき、メーカーAPI仕様と64bit対応が十分な場合に候補とする。

## 9.5.2 基本構成

1. メーカーのドライバとテストツールを導入する。
2. テストツールで代表Tx/Rxを確認する。
3. メーカー提供LabVIEW VIまたはDLL APIを確認する。
4. DLLの場合は関数プロトタイプ、Calling Convention、bit数を確認する。
5. DBCのエンコード・デコード方法を決める。
6. 薄いラッパと公開APIへ分ける。

## 9.5.3 作成手順で明記するもの

- DLLまたはドライバVIの正式名称
- 入力・出力端子とC型 / LabVIEW型
- Payload配列の長さと初期化方法
- Channel、Bitrate、CAN FD設定
- ReturnCodeと標準error clusterの統合方法
- ポーリング周期とTimeout
- Cleanupでの送信停止とClose

## 9.5.4 PoCテスト

メーカーのテストツールと同じ条件でTx/Rxを実行し、CAN ID、DLC、Payload、周期、Timestampが一致することを確認する。

---

# 9.6 方式D：RAMScope GT170 CAN

## 9.6.1 採用理由となる条件

RAM値とCANフレームを同じ機器・Timestamp系で扱う必要があり、API構造体と排他制御を自前保守できる場合に候補とする。

使用候補API：

```c
RAMScopeGT170SendCANDataFrame(...)
RAMScopeGT170ScenarioSendSet(...)
RAMScopeGT170ScenarioSendStart(...)
RAMScopeGT170ScenarioSendStop(...)
```

関数プロトタイプと構造体は`RAMScopeVP.h`を正とする。

## 9.6.2 制約

- C構造体をLabVIEWのU8配列へ正しく変換する必要がある。
- Alive Counter、Checksum、故障注入用Payloadを原則LabVIEW側で生成する。
- RAMScopeVP APIのスレッドセーフ性は未確認である。
- RAMの`GetBufferData`とCAN送信APIを複数ループから同時実行しない。
- 必要ならDLLアクセスを1つのDevice Accessループへ集約する。

## 9.6.3 単発送信とScenario送信

### 単発送信

```text
試験条件
  → Alive / Checksum計算
  → Payload生成
  → SendCANDataFrame
```

毎回変化するPayload、手動イベント、故障注入に向く。周期精度はWindows、LabVIEW、TestStandの実行タイミングに依存する。

### Scenario送信

```text
カウンタ全パターンを事前生成
  → ScenarioSendSet
  → ScenarioSendStart
  → ハードウェア側で周期送信
  → ScenarioSendStop
```

最大ステップ数、周期単位、繰り返し仕様は使用API版のヘッダと外部仕様書で確認する。

## 9.6.4 PoCテスト

- RAM計測だけ、CAN送信だけを個別に確認する。
- 同一セッション内でRAM取得とCAN送信を直列に実行する。
- Scenario開始・停止、再設定、DeviceExitを確認する。
- CAN送信中のRAM欠測、LostDataNum、Timestampを記録する。

---

# 9.7 Alive Counter・Checksum

## 9.7.1 分離するVI

```text
CAN_E2E_Encode.vi
CAN_E2E_Check.vi
```

インタフェース方式とE2E計算を分けることで、DBCやECU仕様変更時に計算VIだけを修正できる。

### 入出力例

| 方向 | 端子 |
|---|---|
| 入力 | CAN ID、元Payload、Alive値、bit位置、bit長、Checksum方式 |
| 出力 | 送信用Payload、次Alive値、計算Checksum、検証結果、error out |

方式決定後は、bit位置の数え方、Intel / Motorola、除外バイト、初期値、XOR値を一次資料から確定し、既知Payloadで単体テストする。

## 9.7.2 単体テスト

- Alive Counterの最小値、最大値、ラップを確認する。
- 既知CAPLまたは実測フレームとChecksumを比較する。
- Checksum異常、Alive停止、Timeout用Payloadを生成する。
- Motorola / Intelのbit配置を混同していないことを確認する。

---

# 9.8 方式選定

| 観点 | CANalyzer COM | NI-XNET | USB-CAN | RAMScope CAN |
|---|---|---|---|---|
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
4. 要件で候補を2つ以下へ絞る。
5. 同じ代表Tx / Rx / 周期 / 異常条件でPoCする。
6. 結果を入力条件、測定方法、期待値、実測値で比較する。
7. 採用方式を1つ決め、未採用方式の本番VI量産を止める。

---

# 9.9 PoC共通手順と完了条件

## 9.9.1 PoC記録フォーマット

| 項目 | 記録内容 |
|---|---|
| 環境 | PC、OS、LabVIEW、ドライバ、機器FW |
| 接続条件 | Channel、Bitrate、Termination、DBC / cfg |
| 入力 | CAN ID、DLC、Payload、周期、回数 |
| 測定方法 | 別モニタ、オシロ、ログ、Timestamp基準 |
| 期待結果 | Payload、周期、受信値、Timeout |
| 実測結果 | 値、周期、ジッタ、エラー |
| 判定 | 合格、要修正、不採用 |

## 9.9.2 完了条件

- [ ] 接続・Openができる
- [ ] 代表CAN IDを送信できる
- [ ] DUTまたは別バスモニタでPayloadを確認できる
- [ ] 代表RxをLabVIEWへ返せる
- [ ] 周期とジッタが試験要件を満たす
- [ ] Alive / Checksumが既知値と一致する
- [ ] Timeout、切断、バスオフ等を検出できる
- [ ] Cleanupで周期送信を停止し、参照・セッションを解放できる
- [ ] TestStandなしの単体PoCが再現できる

## 9.9.3 方式決定後

- [ ] 採用方式を本章冒頭へ記載する
- [ ] `CAN_Open / Send / Read / Close`の正本を1方式へ固定する
- [ ] 各VIを00Aの標準書式で詳細化する
- [ ] 未採用方式は参考案として明記し、本番シーケンスから除外する
- [ ] TestStandの変数、サブシーケンス、Cleanupを採用方式へ合わせる
- [ ] RAMScope CANを採用する場合、第10章のAPI状態と排他ルールに従う
