# LabVIEW + TestStand 自動テストシステム構築資料

NI社製 LabVIEW と TestStand を利用し、複数機器を連携させる自動テストシステムの構築手順をまとめた資料です。

> **最終整理日：2026-07-14**
>
> RAMScope は **64bit版 RAMScopeVP APIをLabVIEW 64bitのCLFNから直接呼び出す方式**を採用する。
> 実装は「薄いDLLラッパ → 公開API → RAMScope単体PoC → CAN単体PoC → TestStand」の順で進める。

---

## 1. この資料の目的

複数の操作者が手動で実施している以下の操作を自動化し、**再現性の高い試験**と**工数削減・試験品質向上**を実現する。

- 模擬電源（高圧／低圧）の制御
- 供試体マイコンのCAN操作
- 測定機器（オシロ／ロガー／RAMScope）の操作・ログ取得
- 上記を指定した条件・順序・タイミングで実行

---

## 2. 最初に読む順番

最初に [00_資料の読み方と正本ルール.md](./docs/00_資料の読み方と正本ルール.md) を読み、その後は次の一本道で進める。

```text
0. 資料の正本ルールを確認
   ↓
1. 01 システム概要
   ↓
2. 02 LabVIEW / TestStandの役割分担
   ↓
3. 03 開発PC・試験PCの環境構築
   ↓
4. 04 → 05 → 06でVIの基礎・共通ルール・雛形を作成
   ↓
5. 機器別実装
   ├─ 一般機器：07 / 08
   ├─ CAN方式検討：09
   └─ RAMScope：10A → 10B → 10B-1 / 10B-2
        10A：DLL準備・疎通確認
        10B：DLLラッパ → 公開API → PoC_RAMScope_Main.vi
        10B-1：RAMScope_Code_To_Error.viの詳細作成手順
        10B-2：各RS_DLLラッパのCLFN設定・配線手順
   ↓
6. RAMScope RAM計測単体PoCを完了
   ↓
7. CAN方式を確定し、採用方式のCAN単体PoCを完了
   ↓
8. 11 TestStandへ組み込み
   ↓
9. 12 Cleanup・異常系を実装
   ↓
10. 13 ロードマップと完了条件を確認
```

### RAMScope資料の役割分担

| 資料 | 役割 | 読むタイミング |
|------|------|----------------|
| [10](./docs/10_RAMScope実装方針.md) | API関数、構造体、定数、ライフサイクルの**技術リファレンス** | 関数・型を確認するとき |
| [10A](./docs/10A_RAMScope実装手順_DLL準備とCLFN疎通確認.md) | DLL配置、VC++ランタイム、x64/x86混在対策、CLFN疎通確認 | RAMScope実装の最初 |
| [10B](./docs/10B_RAMScope_VI作成手順_STEP3_STEP4詳細.md) | 薄いDLLラッパ、Parser、公開API、`PoC_RAMScope_Main.vi`、CAN/TestStandへの移行条件 | 10A完了後 |
| [10B-1](./docs/10B1_RAMScope_Code_To_Error_VI作成手順.md) | `RAMScope_Code_To_Error.vi`の配置関数、Case条件、文字列変換、単体テスト | 共通エラー変換VIを作るとき |
| [10B-2](./docs/10B2_RAMScope_DLLラッパVI_CLFN配線手順.md) | 全`RS_DLL_*`ラッパのCLFNパラメータ、配列初期化、端子配線 | DLLラッパを1本ずつ作るとき |
| [09](./docs/09_CAN通信の実装.md) | CANalyzer / NI-XNET / USB-CAN / RAMScope CANの方式選定 | RAM計測PoC後、CAN着手前 |
| [11](./docs/11_TestStandシーケンス構築手順.md) | PoC済み公開APIをSetup/Main/Cleanupへ配置 | RAM/CAN単体PoC後 |

> `07_機器別VI構築手順.md`のRAMScope記述は概要のみとし、実装時は**10A / 10B / 10B-1 / 10B-2を正本**とする。

---

## 3. RAMScope実装のレイヤ

```text
TestStand
  → RAMScope_* 公開API
      → RS_DLL_* 薄いDLLラッパ
          → CLFN
              → RAMScopeVP_API_x64.dll
```

| レイヤ | 役割 |
|--------|------|
| `RS_DLL_*` | DLL関数を1個だけ呼び、ReturnCodeとerror clusterを返す |
| Parser / Common | SYSINFO・測定バッファ解析、APIコード変換 |
| `RAMScope_*` | 複数ラッパを接続し、1イベントを完結させる公開API |
| `PoC_*` | 公開APIを順番に呼び、TestStandなしで単体確認する |
| TestStand | 条件、順序、Wait、Loop、分岐、レポート、Cleanupを管理する |

TestStandは`RS_DLL_*`を直接呼ばない。

---

## 4. ドキュメント構成

| No. | ファイル | 内容 |
|-----|----------|------|
| Index | [README.md](./README.md) | 全体索引と現在の採用方針 |
| 00 | [docs/00_資料の読み方と正本ルール.md](./docs/00_資料の読み方と正本ルール.md) | 情報の優先順位、確定/未確定の扱い、更新ルール |
| 01 | [docs/01_システム概要と構成.md](./docs/01_システム概要と構成.md) | 目的・機器構成・接続方式 |
| 02 | [docs/02_役割分担とアーキテクチャ.md](./docs/02_役割分担とアーキテクチャ.md) | LabVIEWとTestStandの責務 |
| 03 | [docs/03_LabVIEW環境構築.md](./docs/03_LabVIEW環境構築.md) | 開発PC・試験PC・ドライバ・DLLの準備 |
| 04 | [docs/04_VIの仕組み_LabVIEW基礎.md](./docs/04_VIの仕組み_LabVIEW基礎.md) | VI、コネクタペイン、型定義、エラー伝搬の基礎 |
| 05 | [docs/05_VI設計方針と共通仕様.md](./docs/05_VI設計方針と共通仕様.md) | 1イベント1VI、共通入出力、エラー仕様 |
| 06 | [docs/06_VIの作り方_手順.md](./docs/06_VIの作り方_手順.md) | 共通型定義・VI雛形の作成 |
| 07 | [docs/07_機器別VI構築手順.md](./docs/07_機器別VI構築手順.md) | オシロ、ロガー、電源等の機器別実装 |
| 08 | [docs/08_負荷電流VIと並列処理.md](./docs/08_負荷電流VIと並列処理.md) | 負荷電流ランプと並列処理 |
| 09 | [docs/09_CAN通信の実装.md](./docs/09_CAN通信の実装.md) | CAN方式選定と採用方式の実装方針 |
| 10 | [docs/10_RAMScope実装方針.md](./docs/10_RAMScope実装方針.md) | RAMScope API技術リファレンス |
| 10A | [docs/10A_RAMScope実装手順_DLL準備とCLFN疎通確認.md](./docs/10A_RAMScope実装手順_DLL準備とCLFN疎通確認.md) | RAMScope環境準備とDLL疎通確認 |
| 10B | [docs/10B_RAMScope_VI作成手順_STEP3_STEP4詳細.md](./docs/10B_RAMScope_VI作成手順_STEP3_STEP4詳細.md) | DLLラッパ、公開API、最小PoC、CAN/TestStandへの移行手順 |
| 10B-1 | [docs/10B1_RAMScope_Code_To_Error_VI作成手順.md](./docs/10B1_RAMScope_Code_To_Error_VI作成手順.md) | API戻り値をerror clusterへ変換するVIの初心者向け作成手順 |
| 10B-2 | [docs/10B2_RAMScope_DLLラッパVI_CLFN配線手順.md](./docs/10B2_RAMScope_DLLラッパVI_CLFN配線手順.md) | 全DLLラッパのCLFN設定、初期配列、入力・出力配線の詳細 |
| 11 | [docs/11_TestStandシーケンス構築手順.md](./docs/11_TestStandシーケンス構築手順.md) | TestStandへの組み込み |
| 12 | [docs/12_異常系処理とシャットダウン設計.md](./docs/12_異常系処理とシャットダウン設計.md) | Cleanup、安全停止、データ退避 |
| 13 | [docs/13_構築ロードマップ.md](./docs/13_構築ロードマップ.md) | 現在地、残作業、完了条件 |
| 付録A1 | [docs/A1_付録_FG420基盤単体試験自動化.md](./docs/A1_付録_FG420基盤単体試験自動化.md) | FG420基盤単体試験の別案件 |
| 参考 | [docs/reference/RAMScopeVP.h](./docs/reference/RAMScopeVP.h) | RAMScope APIヘッダ。関数プロトタイプの一次情報 |
| 参考 | [docs/reference/GTHard.h](./docs/reference/GTHard.h) | 機種・モジュール・上限値の一次情報 |
| 参考 | [docs/reference/samp_simple.cpp](./docs/reference/samp_simple.cpp) | ベンダー提供サンプル。呼び出し順序の一次情報 |
| ツール | [scripts/Test-RAMScopeDll.ps1](./scripts/Test-RAMScopeDll.ps1) | x64 DLLとエクスポート関数の疎通確認 |

---

## 5. 現在確定している設計

1. **1イベント = 1公開API VI**とする。
2. DLL層は**1関数 = 1薄いラッパVI**とする。
3. 試験条件、待ち時間、繰り返し、分岐はTestStandで管理する。
4. DLLラッパは`error in / error out`と`API ReturnCode`を持つ。
5. 公開APIは`Status.ctl`、`TestError.ctl`、標準error clusterを出力する。
6. RAMScope APIの戻り値はCLFNの`error out`とは別に判定する。
7. RAMScopeはネイティブSessionハンドルを返さないグローバル状態型APIである。
8. `RAMScope_Set_Cond.vi`を測定開始前に必ず実行する。
9. `ReleaseBufferData`は必須性が確定するまで独立VIとして検証する。
10. RAMScopeの終了はCleanupで`RAMScope_Close.vi`を必ず実行する。
11. 高圧停止を最優先し、データ退避、DUT低圧停止、RAMScope終了の順で安全停止する。

---

## 6. 未確定・実機確認待ち

- GT170実機接続時の`DeviceInit`正常戻り値、`UnitNum`、`kind`
- `0x30100001`のベンダー正式定義
- `AllInit`以降の通し動作
- 実データのEndianとTimestamp
- `ReleaseBufferData`の必須性と呼び出し位置
- APIのスレッドセーフ性
- CANの最終方式とRAMScope CAN機能の使用範囲

未確定事項は推測で確定扱いせず、実機結果またはベンダー一次資料を得た時点で更新する。