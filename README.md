# LabVIEW + TestStand 自動テストシステム構築資料

NI社製LabVIEWとTestStandを利用し、複数機器を連携させる自動テストシステムの構築手順をまとめた資料です。

> **最終整理日：2026-08-05**
>
> 画面を見ながら再現できる実装手順は[00A_LabVIEW実装資料の記述ルール.md](./docs/00A_LabVIEW実装資料の記述ルール.md)を正とする。
> 機能要求をデータモデル、アルゴリズムおよびLabVIEW構造へ落とし込む設計意図は[00B_LabVIEW学習型VI設計ルール.md](./docs/00B_LabVIEW学習型VI設計ルール.md)を正とする。
> すべてのVI作成・改訂資料は00Aと00Bの両方へ従う。
> 製品Version、NI公式Help、ベンダー仕様書および実機確認状態は[00C_一次資料とバージョン基準.md](./docs/00C_一次資料とバージョン基準.md)を正とする。
> RAMScopeの環境準備、DLLラッパ、構造体生成、Parser、公開API、PoCは[10_RAMScope実装方針.md](./docs/10_RAMScope実装方針.md)を上位正本とし、`RAMScope_Read.vi`の端子・Case・配線単位の詳細は[10R_RAMScope_Read_vi_作成手順.md](./docs/10R_RAMScope_Read_vi_作成手順.md)を使用する。

---

## 1. この資料の目的

複数の操作者が手動で実施している次の操作を自動化し、再現性、試験品質、作業効率を向上させる。

- 模擬電源の制御
- 供試体マイコンのCAN操作
- オシロ、ロガー、RAMScopeの操作とログ取得
- 試験条件、順序、タイミング、繰り返し、異常時処理の自動化

---

## 2. 最初に読む順番

```text
00  資料の読み方と正本ルール
  ↓
00A LabVIEW実装資料の記述ルール
  ↓
00B LabVIEW学習型VI設計ルール
  ↓
00C 一次資料とバージョン基準
  ↓
01  システム概要
  ↓
02  LabVIEW / TestStandの役割分担
  ↓
03  開発PC・試験PCの環境構築
  ↓
04  LabVIEW基礎
  ↓
05  VI設計方針と共通仕様
  ↓
06  共通部品とVI雛形
  ↓
07 / 08 一般機器
  ↓
09  CAN方式検討
  ↓
10  RAMScope GT170実装ガイド
  ├─ 環境準備・DLL疎通
  ├─ RAMScope_Code_To_Error.vi
  ├─ 薄いDLLラッパ18個
  ├─ typedef・数値⇔U8変換
  ├─ 構造体Builder
  ├─ SYSINFO / Buffer Parser
  ├─ 公開API
  ├─ 10R RAMScope_Read.vi詳細作成手順
  └─ RAMScope単体PoC
  ↓
CAN方式確定・CAN単体PoC
  ↓
11  TestStand組み込み
  ↓
12  Cleanup・異常系
  ↓
13  ロードマップと完了条件
```

RAMScope実装では旧`10A`、`10B`、`10B-1`から`10B-4`を参照しない。第10章を上位正本とし、`RAMScope_Read.vi`の詳細作業だけは子文書`10R`を併用する。

---

## 3. 実装資料の読み方

### 設計章

01、02、05、13は「なぜその構成にするか」「責務をどこへ置くか」を説明する。画面操作の正本にはしない。

### 操作手順章

03、06～12、付録A1でVIやTestStandを作る場合は、原則として次の学習型構成を使用する。

```text
0. 実現したい機能とVIの責務
1. 入力データの実体
2. 出力データモデル
3. 前提条件・異常条件
4. 処理アルゴリズム
5. LabVIEW構造の選定理由
6. 入出力
7. 配置する関数およびSubVI等
8. 配線順
9. 単体テスト
```

単純なVIでは節を統合してよい。ただし、Case Structure、Forループ、Whileループ、Shift Register、配列処理または状態管理を使用する場合は、なぜその構造が欲しい機能のロジックに必要なのかを省略しない。

接続元、接続先、関数名、端子名、数値型、自動指標付け、シフトレジスタ、テストデータ生成方法は[00A](./docs/00A_LabVIEW実装資料の記述ルール.md)に従う。機能要求、データモデル、擬似コード、構造の選定理由および設計ロジックと単体テストの対応は[00B](./docs/00B_LabVIEW学習型VI設計ルール.md)に従う。

---

## 4. RAMScope実装レイヤ

```text
TestStand
  → RAMScope_* 公開API
      → Builder / Parser / Common
          → RS_DLL_* 薄いDLLラッパ
              → CLFN
                  → RAMScopeVP_API_x64.dll
```

| レイヤ | 役割 |
|---|---|
| `RS_DLL_*` | DLL関数を1個だけ呼び、ReturnCodeとerror clusterを返す |
| Common / Data Conversion | typedef、数値変換、構造体U8生成、SYSINFO・測定バッファ解析 |
| `RAMScope_*` | 下位VIを接続し、1イベントを完結させる公開API |
| `PoC_*` | TestStandなしで公開APIを順番に確認する |
| TestStand | 条件、順序、Wait、Loop、分岐、レポート、Cleanupを管理する |

TestStandは`RS_DLL_*`を直接呼ばない。

---

## 5. ドキュメント構成

| No. | ファイル | 内容 |
|---|---|---|
| Index | [README.md](./README.md) | 全体索引と採用方針 |
| 00 | [docs/00_資料の読み方と正本ルール.md](./docs/00_資料の読み方と正本ルール.md) | 情報の優先順位、確定・未確定、更新ルール |
| 00A | [docs/00A_LabVIEW実装資料の記述ルール.md](./docs/00A_LabVIEW実装資料の記述ルール.md) | 初心者が画面を見ながら再現できる手順記載の共通ルール |
| 00B | [docs/00B_LabVIEW学習型VI設計ルール.md](./docs/00B_LabVIEW学習型VI設計ルール.md) | 機能要求をデータモデル、アルゴリズム、LabVIEW構造へ変換する共通ルール |
| 00C | [docs/00C_一次資料とバージョン基準.md](./docs/00C_一次資料とバージョン基準.md) | NI公式・ベンダー一次資料、採用Version、確認証跡の共通ルール |
| 01 | [docs/01_システム概要と構成.md](./docs/01_システム概要と構成.md) | 目的、機器構成、接続方式 |
| 02 | [docs/02_役割分担とアーキテクチャ.md](./docs/02_役割分担とアーキテクチャ.md) | LabVIEWとTestStandの責務 |
| 03 | [docs/03_LabVIEW環境構築.md](./docs/03_LabVIEW環境構築.md) | 開発PC、試験PC、ドライバ、DLL準備 |
| 04 | [docs/04_VIの仕組み_LabVIEW基礎.md](./docs/04_VIの仕組み_LabVIEW基礎.md) | VI、コネクタペイン、typedef、error cluster |
| 05 | [docs/05_VI設計方針と共通仕様.md](./docs/05_VI設計方針と共通仕様.md) | 1イベント1VI、共通端子、エラー仕様 |
| 06 | [docs/06_VIの作り方_手順.md](./docs/06_VIの作り方_手順.md) | 共通型定義、VI雛形 |
| 07 | [docs/07_機器別VI構築手順.md](./docs/07_機器別VI構築手順.md) | 一般機器の実装 |
| 08 | [docs/08_負荷電流VIと並列処理.md](./docs/08_負荷電流VIと並列処理.md) | 負荷電流ランプ、並列処理 |
| 09 | [docs/09_CAN通信の実装.md](./docs/09_CAN通信の実装.md) | CAN方式選定と実装方針 |
| 10 | [docs/10_RAMScope実装方針.md](./docs/10_RAMScope実装方針.md) | RAMScope環境準備からPoCまでの上位実装ガイド |
| 10R | [docs/10R_RAMScope_Read_vi_作成手順.md](./docs/10R_RAMScope_Read_vi_作成手順.md) | GetBufferDataNum対応後のRead公開APIを端子・Case・配線単位で再現する詳細手順 |
| 11 | [docs/11_TestStandシーケンス構築手順.md](./docs/11_TestStandシーケンス構築手順.md) | TestStandへの組み込み |
| 12 | [docs/12_異常系処理とシャットダウン設計.md](./docs/12_異常系処理とシャットダウン設計.md) | Cleanup、安全停止、データ退避 |
| 13 | [docs/13_構築ロードマップ.md](./docs/13_構築ロードマップ.md) | 現在地、残作業、完了条件 |
| 14 | [docs/14_VI入出力イメージ図.md](./docs/14_VI入出力イメージ図.md) | VI単体の入出力と公開API接続を示すSVG索引 |
| 付録A1 | [docs/A1_付録_FG420基盤単体試験自動化.md](./docs/A1_付録_FG420基盤単体試験自動化.md) | FG420基盤単体試験 |
| 参考 | [docs/reference/RAMScopeVP.h](./docs/reference/RAMScopeVP.h) | RAMScope APIヘッダ |
| 参考 | [docs/reference/GTHard.h](./docs/reference/GTHard.h) | ハードウェア定数 |
| 参考 | [docs/reference/samp_simple.cpp](./docs/reference/samp_simple.cpp) | ベンダーサンプル |
| ツール | [scripts/Test-RAMScopeDll.ps1](./scripts/Test-RAMScopeDll.ps1) | x64 DLLとエクスポート関数の疎通確認 |
| ツール | [scripts/generate-vi-svg-diagrams.py](./scripts/generate-vi-svg-diagrams.py) | VI入出力・公開API接続SVGの再生成 |

---

## 6. 現在確定している設計

1. 1イベントを1公開API VIにする。
2. DLL層は1関数を1個の薄い`RS_DLL_*`ラッパにする。
3. 試験条件、待ち、繰り返し、分岐はTestStandで管理する。
4. DLLラッパは標準error clusterとAPI ReturnCodeを分けて扱う。
5. 公開APIだけが`Status.ctl`と`TestError.ctl`を出力する。
6. `RAMScope_Set_Cond.vi`を測定開始前に実行する。
7. `ChNum`は`RAMScope_Channel.ctl`配列の配列サイズ（Array Size）から算出する。
8. BuilderとParserはDLLを呼ばない純粋処理VIにする。
9. `ReleaseBufferData`は要否確定まで独立VIとする。
10. `RAMScope_Close.vi`はCleanupで必ず実行する。
11. `RAMScope_Config.vi`は作成せず、PGT設定は`RAMScope_Init.vi`へ統合する。
12. `RAMScope_Context.ctl`はPoC完了まで作成しない。
13. すべてのVI作成・改訂資料は00Aと00Bの両方へ従う。
14. Case StructureやLoopを使用するVIは、欲しい機能のロジックからその構造が必要になる理由を説明する。
15. `RAMScope_Read.vi`は`GetBufferDataNum → RequestedDataNum決定 → I64 Buffer検証 → GetBufferData → 切り詰め → Parser`の順とし、前段・Wrapper・Parser errorを後段のローカルerrorで上書きしない。

---

## 7. 未確定・実機確認待ち

- GT170接続時のDeviceInit正常値
- `0x30100001`の正式定義
- AllInit以降の通し動作
- EndianとTimestamp単位
- `Size`、`Sign`、`Speed`コード
- 既存RAMScopeコンフィグの正式読込仕様
- `ReleaseBufferData`の必須性と位置
- APIのスレッドセーフ性
- CANの最終方式

未確定事項は推測で固定せず、実機結果またはベンダー一次資料を得た時点で第10章、第10章の子文書および第13章を更新する。
