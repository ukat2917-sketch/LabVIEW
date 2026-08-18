# 09B. CANalyzer Session Registry 設計

**最終整理日：2026-08-18**

> **本章の役割**：`09_CAN通信の実装.md` のSession管理設計を補足し、Nigel AIによる設計レビュー結果を反映したProduction向けの最終I/O契約、Action契約、Session State、ActiveX Reference ownership、Concurrency、Error Policyを確定する。
>
> 本章は `CANalyzer_Session_State.ctl`、`CANalyzer_Session_Registry_Action.ctl`、`CANalyzer_Session_Registry.vi` の実装前設計正本として扱う。

---

# 1. 設計目的

CANalyzerのActiveX参照をLabVIEW内部だけで保持し、Public API / TestStandにはSession IDだけを公開する。

```text
TestStand / Public API
        ↓
    Session ID
        ↓
CANalyzer_Session_Registry.vi
        ↓
CANalyzer_Session_State.ctl
├─ Application Ref
├─ System Ref
├─ Measurement Ref
└─ Session状態情報
```

境界ルール：

- TestStandへ公開するのはSession IDのみ。
- Public APIからActiveX Refを公開しない。
- Raw VariantをPublic / TestStandへ公開しない。
- `CANalyzer_Session_State.ctl` はService内部専用。

---

# 2. Nigel AI Design Review結果

総合判定：**PASS WITH CHANGES**

レビューでProduction向けに修正が推奨された主要項目：

1. Clear AllでSession IDを1へ戻さない。
2. Found?と`-710102`の二重通知を整理する。
3. Remove / Clear Allへincoming error時の特殊動作を混在させない。
4. `Is Connected?` / `Is Measuring?`を真実源として扱わない。

最終設計では上記を反映する。

---

# 3. Registryの責務

`CANalyzer_Session_Registry.vi` は **ActiveX ReferenceのHolder** とする。

Registry自身は次を実行しない。

```text
Close Reference
Application Quit
Measurement Start
Measurement Stop
```

Refのライフサイクル操作はPublic Close / Cleanup側の責務とする。

標準Cleanup：

```text
Registry Get
  ↓
必要ならMeasurement Stop
  ↓
Measurement Ref Close
  ↓
System Ref Close
  ↓
Application Ownership = LabVIEW の場合だけ必要に応じてQuit
  ↓
Application Ref Close
  ↓
Registry Remove
```

Registry RemoveはRegistry記録の削除だけを担当する。

---

# 4. `CANalyzer_Session_State.ctl`

以下で確定する。

| フィールド | 型 | 用途 |
|---|---|---|
| `Session ID` | U32 | Registry内部識別子 |
| `Application Ref` | `IApplication10` ActiveX Ref | Application参照 |
| `System Ref` | `ISystem3` ActiveX Ref | SysVarアクセス用参照 |
| `Measurement Ref` | `IMeasurement5` ActiveX Ref | Start / Stop / Running確認用参照 |
| `Version String` | String | CANalyzer実Version |
| `Configuration Path` | Path | 実Configuration |
| `Launch Mode` | `CANalyzer_Launch_Mode.ctl` | Open条件 |
| `Application Ownership` | `CANalyzer_Application_Ownership.ctl` | Quit可否 |
| `Configuration Opened By LabVIEW?` | Boolean | cfg所有権 |
| `Measurement Started By LabVIEW?` | Boolean | Stop所有権 |
| `Cached Connected?` | Boolean | 接続状態キャッシュ |
| `Cached Measuring?` | Boolean | Measurement状態キャッシュ |
| `Compatibility Status` | `CANalyzer_Compatibility_Status.ctl` | 互換性状態 |

## 4.1 Cached Statusルール

`Cached Connected?` と `Cached Measuring?` は利便性のため保持するが、**source of truthではない**。

実状態が必要な場合は次を正とする。

```text
接続状態
→ ActiveX Refの実状態 / Health Check

Measurement状態
→ CAN_AX_Get_Measurement_Running.vi
   または CANalyzer_Wait_Measurement_State.vi の実取得結果
```

Session State内のcached statusだけを根拠にStop / Close / Health判定を行わない。

## 4.2 今回追加しない項目

Nigel AIから以下の追加案があったが、現段階では採用しない。

```text
Session Generation
Last Access UTC / Tick
Closed? / Removed?
```

理由：

- Session IDをLabVIEWプロセス存続中は再利用しない。
- まずは必要最小限のSession管理でProduction APIを成立させる。
- 必要性が発生した時点で拡張可能。

---

# 5. `CANalyzer_Session_Registry_Action.ctl`

Enum順を以下で固定する。

```text
Create
Get
Update
Remove
Clear All
```

Registry ActionはService内部専用とする。

---

# 6. `CANalyzer_Session_Registry.vi` I/O

## 6.1 Input

| 端子 | 型 | 備考 |
|---|---|---|
| `Action` | `CANalyzer_Session_Registry_Action.ctl` | 実行Action |
| `Session ID` | U32 | Default=0 |
| `Session In` | `CANalyzer_Session_State.ctl` | Create / Update時に使用 |
| `error in` | error cluster | 標準error入力 |

## 6.2 Output

| 端子 | 型 | 備考 |
|---|---|---|
| `Session ID Out` | U32 | 対象または発行ID |
| `Session Out` | `CANalyzer_Session_State.ctl` | Service内部のみ |
| `Found?` | Boolean | 検索 / 削除結果 |
| `error out` | error cluster | Registry処理結果 |

Connector Pane推奨：

```text
左                         右

Action              → Session ID Out
Session ID          → Session Out
Session In          → Found?
error in             → error out
```

---

# 7. 内部保持状態

Registry内部で以下を保持する。

```text
Session Array
  1D Array of CANalyzer_Session_State.ctl

Next Session ID
  U32
```

初期値：

```text
Session Array    = []
Next Session ID  = 1
```

実装方式：

```text
1回だけ実行するWhile Loop
  ↓
非初期化Shift Register
├─ Session Array
└─ Next Session ID
  ↓
Action Case Structure
```

VI Executionは **Non-reentrant** とする。

---

# 8. Session ID Policy

## 8.1 基本ルール

```text
0 = Invalid / Unassigned
最初の発行ID = 1
```

Session IDはRegistryのみが発行する。

呼出側からCreate時に渡された`Session In.Session ID`は信用しない。

## 8.2 ID再利用禁止

LabVIEWプロセス存続中は、一度発行したSession IDを再利用しない。

そのためClear Allでも、

```text
Next Session ID = 1
```

へ戻してはいけない。

Clear AllはSession ArrayのみEmptyにし、`Next Session ID`は維持する。

## 8.3 U32 wraparound

`Next Session ID`が0へwrapする状態は未定義にしない。

Create時に次IDが0になる場合は、Session作成を拒否しerrorを返す。

```text
Next Session ID == 0
または
increment結果 == 0
↓
Create拒否
```

具体的な専用error codeは実装時にError Code一覧へ追加する。

---

# 9. Action Contract

# 9.1 Create

入力：

```text
Action = Create
Session ID = 無視
Session In = 新規Session
```

処理：

```text
Next Session ID取得
  ↓
Session In.Session IDを発行IDで上書き
  ↓
Session Arrayへ追加
  ↓
Next Session ID increment
```

出力：

```text
Session ID Out = 発行ID
Session Out    = 登録済みSession
Found?         = True
error out      = Success
```

`Session In.Session ID`は信用しない。

incoming errorありの場合はbypassする。

---

# 9.2 Get

入力：

```text
Action = Get
Session ID = 検索対象
Session In = 無視
```

存在時：

```text
Session ID Out = Session ID
Session Out    = 該当Session
Found?         = True
error out      = Success
```

不存在時：

```text
Session ID Out = Session ID
Session Out    = Default Session
Found?         = False
error out      = Success
```

**GetではNot Foundをerrorにしない。**

Session存在必須のService / Public API側で、

```text
Found? = False
↓
error code = -710102
```

へ変換する。

これにより`Found?`と`error=-710102`の二重通知を避ける。

incoming errorありの場合はbypassする。

---

# 9.3 Update

入力：

```text
Action = Update
Session ID = 更新対象
Session In = 更新内容
```

検索キーは外側の`Session ID`入力だけとする。

```text
Session In.Session ID
↓
入力Session IDで強制上書き
↓
Registryへ保存
```

存在時：

```text
Session ID Out = Session ID
Session Out    = 更新後Session
Found?         = True
error out      = Success
```

不存在時：

```text
Found?         = False
error status   = True
error code     = -710102
```

Updateで存在しないIDを自動Createしない。

**Fail Closed** とする。

incoming errorありの場合はbypassする。

---

# 9.4 Remove

入力：

```text
Action = Remove
Session ID = 削除対象
```

存在時：

```text
Session Arrayから削除
Session ID Out = Session ID
Session Out    = 削除直前Session
Found?         = True
error out      = Success
```

不存在時：

```text
Session ID Out = Session ID
Session Out    = Default Session
Found?         = False
error out      = Success
```

Removeは **idempotent cleanup** を優先し、不存在をerrorにしない。

Registry RemoveではActiveX RefをCloseしない。

incoming errorありの場合は通常どおりbypassする。

Cleanup中に前段errorがあってもRemoveを実行したい場合は、Registryに特殊Policyを持たせず、`CANalyzer_Close.vi`側で元error保存 → cleanup用error処理 → Registry Remove → error mergeを行う。

---

# 9.5 Clear All

用途：

```text
Unit Test
開発時Reset
Registry状態初期化
```

Productionの通常Cleanupでは使用しない。

処理：

```text
Session Array = Empty
Next Session ID = 維持
```

ActiveX RefはCloseしない。

Clear AllはSession Arrayの管理情報だけを消すため、ActiveX Refが生存している状態で通常運用から実行してはいけない。

incoming errorありの場合はbypassする。

`Found?`には強い意味を持たせず、Clear Allの通常制御判断には使用しない。

将来必要になれば`Cleared Count`専用出力またはTest専用VIへの分離を検討する。

---

# 10. Error Policy

基本ルール：

```text
error in.status = True
↓
Registry Actionを実行しない
↓
元errorをerror outへpass-through
```

対象Action：

```text
Create
Get
Update
Remove
Clear All
```

Cleanup時だけincoming errorを無視する特殊ActionはRegistryへ追加しない。

Cleanup責務はPublic `CANalyzer_Close.vi`側へ集約する。

`-710102`はSession存在必須箇所で使用する。

```text
Get
→ Not FoundはFound?=Falseのみ

Update
→ Not Foundは-710102

Public / ServiceのRequire Session操作
→ Get Found?=Falseを-710102へ変換
```

---

# 11. Reference Ownership

| Ref | Registryの立場 | Close責務 |
|---|---|---|
| Application Ref | Holder | Public Close / Cleanup |
| System Ref | Holder | Public Close / Cleanup |
| Measurement Ref | Holder | Public Close / Cleanup |

Getで返された`Session Out`は、Service内部でRefを一時利用するための借用コピーとして扱う。

Getした側は勝手にClose / Quit / Stopしない。

Refを破棄する操作は、所有権Policyを確認するPublic Cleanup経路だけで行う。

---

# 12. Concurrency Policy

`CANalyzer_Session_Registry.vi`をNon-reentrantにすることで、Registry内部のSession Array / Next Session ID更新は直列化する。

ただし、これだけではGetで返された同一SessionのActiveX操作競合は防げない。

そのため本番ActiveX操作は、後続の

```text
CANalyzer_Execute_Command.vi
```

を非再入の一本化ポイントとして使用する。

```text
Public API
  ↓
CANalyzer_Execute_Command.vi
  ↓
Registry / Service / Wrapper
```

RegistryへActiveX操作ロック責務は持たせない。

---

# 13. Production Safety Rules

1. Session IDをプロセス内で再利用しない。
2. Session ID=0をInvalidとして予約する。
3. Updateは不存在SessionをCreateしない。
4. Removeは不存在でもerrorにしない。
5. Registry自身はRefをCloseしない。
6. Registry自身はStart / Stop / Quitしない。
7. Clear AllをProduction Cleanupに使用しない。
8. Cached statusを真実源として使用しない。
9. Public / TestStandへActiveX Refを公開しない。
10. 本番ActiveX操作は`CANalyzer_Execute_Command.vi`で直列化する。
11. Session必須処理ではGet後にFound?を確認し、不存在なら`-710102`を生成する。
12. U32 Session ID wraparound時はCreateを拒否する。

---

# 14. 実装順

以下の順で作成する。

```text
CANalyzer_Launch_Mode.ctl
  ↓
CANalyzer_Application_Ownership.ctl
  ↓
CANalyzer_Compatibility_Status.ctl
  ↓
CANalyzer_Session_Registry_Action.ctl
  ↓
CANalyzer_Session_State.ctl
  ↓
CANalyzer_Session_Registry.vi
```

---

# 15. 実装前確定事項

| 項目 | 確定内容 |
|---|---|
| Registry実装方式 | FGV / Action Engine |
| Reentrancy | Non-reentrant |
| State保持 | 非初期化Shift Register |
| Registry role | ActiveX Ref Holder |
| TestStand境界 | Session IDのみ |
| Session ID 0 | Invalid予約 |
| 初回Session ID | 1 |
| ID再利用 | LabVIEWプロセス内では禁止 |
| Clear All時ID Reset | 禁止 |
| Get Not Found | `Found?=False`, errorなし |
| Update Not Found | `-710102` |
| Remove Not Found | `Found?=False`, errorなし |
| incoming error | 全Actionでbypass |
| Cached Connected / Measuring | 補助状態のみ |
| ActiveX操作直列化 | `CANalyzer_Execute_Command.vi`で実施 |

この契約を基準としてtypedefおよび`CANalyzer_Session_Registry.vi`の実装へ進む。
