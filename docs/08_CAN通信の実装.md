# 08. CAN 通信の実装

## 8.1 前提・課題

- **CANalyzer は LabVIEW から操作するためのドライバ（API）が無い**。
  → CANalyzer をそのまま LabVIEW 制御に使うのは不可。
- そのため、CANalyzer を使わずに CAN 通信を行う方式を選定する必要がある。

## 8.2 実装方式の候補

CANalyzer 無しで CAN 通信を行う手順（検討結果）：

1. **USB-CAN を使用する**
   - Contec 製は **ドライバあり**。LabVIEW から制御可能。
2. **CANdbc ファイルを XNET データベースエディタで編集**
   - 既存の dbc（信号定義）を NI-XNET の Database Editor で読み込み・編集する。
3. **VI で dbc ファイルを読み込み、計測・操作できるように VI を作成**
   - dbc に基づき信号名でフレームを送受信する VI を作る（※角田さん経由で確認）。

## 8.3 推奨アプローチ

| 方式 | ハードウェア | dbc 対応 | LabVIEW 対応 | 備考 |
|------|--------------|----------|--------------|------|
| **NI-XNET** | NI CAN インタフェース | ◎（XNET Database Editor で dbc 直接利用） | ◎（XNET VI が充実） | dbc・信号ベースで扱え最も実装しやすい |
| **Contec USB-CAN** | Contec USB-CAN | △（自前でデコード要の場合あり） | ○（メーカードライバ） | 既存資産・コスト次第 |

> dbc を信号名ベースでそのまま使い、VI を作りやすくする観点では **NI-XNET が有力**。
> Contec USB-CAN を使う場合は、dbc のデコード／エンコードを VI 側でどこまで作るか確認する。

## 8.4 NI-XNET を用いる場合の構築手順

### (1) dbc データベースの準備
1. **NI-XNET Database Editor** を起動。
2. 既存の `*.dbc` を読み込む（または新規作成）。
3. 供試体マイコンの「制御モード」フレーム・信号が定義されているか確認・編集する。
4. dbc をエイリアス登録（NI MAX / XNET）して LabVIEW から参照可能にする。

### (2) CAN 制御 VI の作成
共通入出力仕様（[04](./04_VI設計方針と共通仕様.md)）に従い以下を作る。

| VI | XNET 主要関数 | 処理 |
|----|---------------|------|
| `CAN_Open.vi` | `XNET Create Session`（Signal Output Single-Point / Frame Input 等） | dbc・インタフェース指定でセッション確立 |
| `CAN_Send_Mode.vi` | `XNET Write (Signal Single-Point)` | **制御モード番号** を信号値として書き込み送信 |
| `CAN_Read.vi` | `XNET Read (Signal/Frame)` | マイコンからの応答・状態を受信・デコード |
| `CAN_Close.vi` | `XNET Clear` | セッション解放 |

### (3) 制御モード番号の扱い
- **制御モード番号は TestStand の試験条件（変数）** として管理し、
  `CAN_Send_Mode.vi` の入力で受け取る。
- 試験条件に合わせて遷移条件（いつ・どのモードを送るか）を TestStand 側で設計する。

## 8.5 Contec USB-CAN を用いる場合の構築手順

1. Contec の CAN ドライバ（API/サンプル）をインストール。
2. メーカー提供の LabVIEW 用 VI / DLL ラッパで `Open / Send / Receive / Close` を実装。
3. dbc のエンコード／デコード（信号→生バイト、生バイト→信号）が必要なら、
   - XNET Database を「データベースとしてのみ」利用してデコードする、または
   - dbc 仕様に基づくスケーリング／ビット配置の変換 VI を自作する。
4. 入出力仕様は NI-XNET 版と揃え、TestStand から見て同じ使い勝手にする。

## 8.6 確認・検証

- 送信：`CAN_Send_Mode.vi` で送ったフレームが、CANalyzer / バスモニタで意図どおりの
  ID・データになっているか確認。
- 受信：マイコンの応答が信号値として正しくデコードされるか確認。
- タイミング：モード送信は他処理（負荷ランプ等）と並行する場面があるため、
  非同期実行時の送信遅延を確認する（[07](./07_負荷電流VIと並列処理.md)）。

## 8.7 未確定事項（要決定）

- NI-XNET か Contec USB-CAN か（ハードウェア選定）。
- dbc のデコード／エンコードをどの層で持つか。
- → 実装前に方式を確定する（角田さん経由の確認結果を反映）。
