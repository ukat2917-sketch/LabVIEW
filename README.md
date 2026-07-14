# LabVIEW + TestStand 自動テストシステム構築資料

NI社製 LabVIEW と TestStand を利用し、複数機器を連携させる自動テストシステムの構築手順をまとめた資料です。

> **最終整理日：2026-07-14**
>
> RAMScope は **64bit版 RAMScopeVP API を LabVIEW 64bit の CLFN から直接呼び出す方式**を採用する。
> 過去に検討していた「32bit DLLを使う」「マックシステムズ製ドライバと比較してから方式決定する」という記述は、現在の実装ルートには使用しない。

---

## 1. この資料の目的

複数の操作者が手動で実施している以下の操作を自動化し、**再現性の高い試験**と**工数削減・試験品質向上**を実現する。

- 模擬電源（高圧／低圧）の制御
- 供試体マイコンの CAN 操作
- 測定機器（オシロ／ロガー／RAMScope）の操作・ログ取得
- 上記を指定した条件・順序・タイミングで実行

---

## 2. 最初に読む順番

資料を行き来して迷わないよう、実装は次の一本道で進める。

```text
1. 01 システム概要
   ↓
2. 02 LabVIEW / TestStand の役割分担
   ↓
3. 03 開発PC・試験PCの環境構築
   ↓
4. 04 → 05 → 06 で VI の基礎・共通ルール・雛形を作成
   ↓
5. 機器別実装
   ├─ 一般機器：07 / 08 / 09
   └─ RAMScope：10A → 10B
        ※ 10 は API仕様・構造体を調べるためのリファレンス
   ↓
6. 11 TestStand へ組み込み
   ↓
7. 12 Cleanup・異常系を実装
   ↓
8. 13 ロードマップと完了条件を確認
```

### RAMScope資料の役割分担

| 資料 | 役割 | 読むタイミング |
|------|------|----------------|
| [10](./docs/10_RAMScope実装方針.md) | API関数、構造体、定数、ライフサイクルの**技術リファレンス** | 関数・型を確認するとき |
| [10A](./docs/10A_RAMScope実装手順_DLL準備とCLFN疎通確認.md) | DLL配置、VC++ランタイム、x64/x86混在対策、CLFN疎通確認 | RAMScope実装の最初 |
| [10B](./docs/10B_RAMScope_VI作成手順_STEP3_STEP4詳細.md) | 共通エラー変換と各RAMScope VIの具体的な作成手順 | 10AのPoC完了後 |
| [11](./docs/11_TestStandシーケンス構築手順.md) | 作成済みVIをSetup/Main/Cleanupへ配置 | LabVIEW単体フロー確認後 |

> `07_機器別VI構築手順.md` のRAMScope記述は概要のみとし、実装時は **10A / 10Bを正本**とする。

---

## 3. ドキュメント構成

| No. | ファイル | 内容 |
|-----|----------|------|
| 00 | [README.md](./README.md) | 本書。正本ルールと推奨実装ルート |
| 01 | [docs/01_システム概要と構成.md](./docs/01_システム概要と構成.md) | 目的・機器構成・接続方式 |
| 02 | [docs/02_役割分担とアーキテクチャ.md](./docs/02_役割分担とアーキテクチャ.md) | LabVIEWとTestStandの責務 |
| 03 | [docs/03_LabVIEW環境構築.md](./docs/03_LabVIEW環境構築.md) | 開発PC・試験PC・ドライバ・DLLの準備 |
| 04 | [docs/04_VIの仕組み_LabVIEW基礎.md](./docs/04_VIの仕組み_LabVIEW基礎.md) | VI、コネクタペイン、型定義、エラー伝搬の基礎 |
| 05 | [docs/05_VI設計方針と共通仕様.md](./docs/05_VI設計方針と共通仕様.md) | 1イベント1VI、共通入出力、エラー仕様 |
| 06 | [docs/06_VIの作り方_手順.md](./docs/06_VIの作り方_手順.md) | 共通型定義・VI雛形の作成 |
| 07 | [docs/07_機器別VI構築手順.md](./docs/07_機器別VI構築手順.md) | オシロ、ロガー、電源等の機器別実装 |
| 08 | [docs/08_負荷電流VIと並列処理.md](./docs/08_負荷電流VIと並列処理.md) | 負荷電流ランプと並列処理 |
| 09 | [docs/09_CAN通信の実装.md](./docs/09_CAN通信の実装.md) | CANalyzer / NI-XNET / USB-CAN / RAMScope CANの方式検討 |
| 10 | [docs/10_RAMScope実装方針.md](./docs/10_RAMScope実装方針.md) | RAMScope API技術リファレンス |
| 10A | [docs/10A_RAMScope実装手順_DLL準備とCLFN疎通確認.md](./docs/10A_RAMScope実装手順_DLL準備とCLFN疎通確認.md) | RAMScope環境準備とDLL疎通確認 |
| 10B | [docs/10B_RAMScope_VI作成手順_STEP3_STEP4詳細.md](./docs/10B_RAMScope_VI作成手順_STEP3_STEP4詳細.md) | RAMScope各VIの作成手順 |
| 11 | [docs/11_TestStandシーケンス構築手順.md](./docs/11_TestStandシーケンス構築手順.md) | TestStandへの組み込み |
| 12 | [docs/12_異常系処理とシャットダウン設計.md](./docs/12_異常系処理とシャットダウン設計.md) | Cleanup、安全停止、データ退避 |
| 13 | [docs/13_構築ロードマップ.md](./docs/13_構築ロードマップ.md) | 現在地、残作業、完了条件 |
| 付録A1 | [docs/A1_付録_FG420基盤単体試験自動化.md](./docs/A1_付録_FG420基盤単体試験自動化.md) | FG420基盤単体試験の別案件 |
| 参考 | [docs/reference/RAMScopeVP.h](./docs/reference/RAMScopeVP.h) | RAMScope APIヘッダ。関数プロトタイプの一次情報 |
| 参考 | [docs/reference/GTHard.h](./docs/reference/GTHard.h) | 機種・モジュール・上限値の一次情報 |
| 参考 | [docs/reference/samp_simple.cpp](./docs/reference/samp_simple.cpp) | ベンダー提供サンプル。呼び出し順序の一次情報 |
| ツール | [scripts/Test-RAMScopeDll.ps1](./scripts/Test-RAMScopeDll.ps1) | x64 DLLとエクスポート関数の疎通確認 |

---

## 4. システム全体像

```text
TestStand
  └─ 試験条件、順序、待ち、分岐、レポート、Cleanup
        ↓ LabVIEW Adapter
LabVIEW VI群
  └─ 1イベント1VIで機器を即時操作
        ├─ Ethernet / VISA：オシロ、ロガー、電源
        ├─ USB3.0 / DLL：RAMScope GT170
        └─ CAN IF：方式選定結果に応じて実装
```

---

## 5. 現在確定している設計

1. **1イベント = 1VI**とする。
2. 試験条件、待ち時間、繰り返し、分岐はTestStandで管理する。
3. 全VIに標準`error in / error out`、`Status.ctl`、`TestError.ctl`を持たせる。
4. RAMScope APIの戻り値はCLFNの`error out`とは別に判定する。
5. RAMScopeはハンドルを返さないグローバル状態型APIのため、VISAリファレンスをVI間で引き回さない。
6. RAMScopeの終了はCleanupで`RAMScope_Close.vi`（`RAMScopeGT150DeviceExit`）を必ず実行する。
7. 高圧停止を最優先し、データ退避、DUT低圧停止、RAMScope終了の順で安全停止する。

---

## 6. 未確定・実機確認待ち

- GT170実機接続時の`DeviceInit`正常戻り値、`UnitNum`、`kind`
- `0x30100001`のベンダー正式定義
- `AllInit`以降の通し動作
- `ReleaseBufferData`を必須とするか
- CANの最終方式とRAMScope CAN機能の使用範囲

未確定事項は推測で確定扱いせず、実機結果またはベンダー一次資料を得た時点で更新する。