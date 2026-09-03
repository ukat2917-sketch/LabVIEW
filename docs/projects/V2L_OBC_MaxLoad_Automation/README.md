# V2L / OBC / DCDC 最大負荷 自動試験システム

**Project:** V2L_OBC_MaxLoad_Automation  
**Status:** Design draft / API調査進行中  
**最終整理日:** 2026-09-03

このProjectは、既存のLabVIEW資料本編とは別案件として管理する。既存RAMScope実装、CANalyzer ActiveXモデル、TestStand構成、Cleanup方針など、汎用化済みの資産は参照して流用するが、本Project固有の要求を本編正本へ混在させない。

---

## 1. Project目的

V2L / OBC / 12V DCDCを含むDUTについて、Chroma電源・負荷装置、横河計測器、CANalyzer、RAMScopeまたはINCA/ETKをLabVIEW + TestStandから自動制御し、試験条件、計測データ、イベント、判定結果を**1つのRunとして一貫管理**する。

Chroma ATSは試験シーケンス用途として利用可能でも、今回必要な多機器の時系列データ統合・同期・Run単位管理には不足があるため、ATSをシステム中核には置かない。

---

## 2. 設計資料

| No. | File | 内容 |
|---|---|---|
| 01 | [01_システム要求とアーキテクチャ.md](./01_システム要求とアーキテクチャ.md) | 対象構成、LabVIEW/TestStand責務、Direct/IS8000/Hybrid案 |
| 02 | [02_機器Adapter_API要求.md](./02_機器Adapter_API要求.md) | Chroma、WT5000、MX100、CANalyzer、RAMScope、IS8000、INCAの必須API |
| 03 | [03_データ統合と時刻同期.md](./03_データ統合と時刻同期.md) | TDMS/MDF/MF4、Run Manifest、同期イベント、保存構成 |
| 04 | [04_既存資産流用と外注仕様.md](./04_既存資産流用と外注仕様.md) | 本編から流用する設計、外注成果物、PoC/受入条件 |
| 05 | [05_一次資料と未確定事項.md](./05_一次資料と未確定事項.md) | 入手済み一次資料、Source Authority、API調査Gap、実機確認項目 |

---

## 3. 本Projectで流用する共通正本

詳細を複製せず、以下を参照する。

- LabVIEW実装資料の書き方: [`../../00A_LabVIEW実装資料の記述ルール.md`](../../00A_LabVIEW実装資料の記述ルール.md)
- 設計意図の書き方: [`../../00B_LabVIEW学習型VI設計ルール.md`](../../00B_LabVIEW学習型VI設計ルール.md)
- 一次資料優先順位: [`../../00C_一次資料とバージョン基準.md`](../../00C_一次資料とバージョン基準.md)
- CANalyzer設計正本: [`../../09_CAN通信の実装.md`](../../09_CAN通信の実装.md)
- CANalyzer実Type Library確認結果: [`../../09A_CANalyzer_ActiveXラッパ実装実績.md`](../../09A_CANalyzer_ActiveXラッパ実装実績.md)
- CANalyzer Session Registry: [`../../09B_CANalyzer_Session_Registry設計.md`](../../09B_CANalyzer_Session_Registry設計.md)
- RAMScope正本: [`../../10_RAMScope実装方針.md`](../../10_RAMScope実装方針.md)
- TestStand組込み原則: [`../../11_TestStandシーケンス構築手順.md`](../../11_TestStandシーケンス構築手順.md)
- Cleanup原則: [`../../12_異常系処理とシャットダウン設計.md`](../../12_異常系処理とシャットダウン設計.md)

---

## 4. 現時点の推奨構成

本Projectでは、全データをLabVIEWへ無理に集約するのではなく、各メーカーの高性能Recorderを活用しつつ、LabVIEW/TestStandでRunとイベントを統合する**Hybrid構成**を第一候補とする。

```text
                         TestStand
                Sequence / Condition / Judge
                             │
                             ▼
                      LabVIEW Core
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
   Chroma / VISA       IS8000 gRPC       CANalyzer / INCA
   Device Adapter      Control Adapter      Automation API
          │                  │                  │
          ▼            WT5000 / MX100          ├─ CAN / MF4
      DUT I/O            / optional             └─ ETK / MF4
                         RAMScope

                         Run Manifest
                             │
          TDMS / MDF / MF4 / Test Result / Event Timeline
```

物理ファイルを必ず1本にすることよりも、**同一Run ID・時刻基準・条件Snapshot・同期イベントで追跡可能であること**を優先する。最終的な単一MF4化はPost Processとして別途評価する。

---

## 5. Project固有ルール

1. TestStandは試験順序、条件、繰返し、判定、Cleanupを担当する。
2. LabVIEWはDevice Adapter、非同期DAQ、同期Event、Run Manifest、保存Orchestrationを担当する。
3. TestStandからベンダーDLL、COM Ref、gRPC stubを直接呼ばない。
4. 各機器は単体PoCを完了してからTestStandへ組み込む。
5. Software Trigger送信時刻のみを精密同期の真実源にしない。
6. 各Recorderに同一`Run ID`と可能な限り同一`Sync Event ID`を残す。
7. Project固有Adapterの公開APIは、ベンダーAPIを隠蔽し、TestStandへ安定した型だけを公開する。
8. 実機・対象Versionで未確認のAPI名、ファイル形式、時刻基準は`未確定`として扱う。
