# 09C. CANalyzer Session Registry 実装手順

**最終整理日：2026-08-18**

> **本章の役割**：作成完了した `CANalyzer_Session_Registry.vi` について、人手実装手順と最終As-Built動作を記録する。
>
> 設計上の正本は [`09B_CANalyzer_Session_Registry設計.md`](./09B_CANalyzer_Session_Registry設計.md) とする。Nigel AIによる設計差分レビュー後、実VIを09Bの確定設計へ合わせて修正済みであり、本章もその最終契約へ統一した。

---

# 1. 目的

`CANalyzer_Session_Registry.vi` は、**CANalyzer セッション情報を VI 内で保持・参照・更新・削除するための FGV（Functional Global Variable）** として作成した。

`Action` に応じて以下の操作を切り替える。

| Action | 内容 |
|---|---|
| **Create** | 新しいセッションを登録する |
| **Get** | Session ID を指定して取得する |
| **Update** | Session ID を指定して内容を更新する |
| **Remove** | Session ID を指定して削除する |
| **Clear All** | Session Array を初期化する。Next Session IDは維持する |

FGV を使う理由は、**共有状態を1カ所に集約し、配線だけで実行順序を明確にできる**ためである。LabVIEWではローカル変数やグローバル変数の多用でレースコンディションが起こりやすいため、この方法を採用した。

参考：
- NI: Using Local and Global Variables Carefully
- NI: Local, Global, or Network Shared Variable Can Cause Race Conditions

---

# 2. フロントパネルの入出力

## 2.1 Controls

| 名前 | 役割 |
|---|---|
| **Action** | 実行する処理種別 |
| **Session ID** | 対象セッション ID |
| **Session In** | 登録または更新するセッション情報 |
| **エラー入力 (エラーなし)** | 上流から受け取る error cluster |

## 2.2 Indicators

| 名前 | 役割 |
|---|---|
| **Session ID Out** | 実際に処理対象となった Session ID |
| **Session Out** | 取得・登録・更新・削除結果として返すセッション |
| **Found?** | 対象 Session ID が見つかったか |
| **エラー出力** | 下流へ渡す error cluster |
| **Session Array Out** | 現在のセッション配列 |
| **Next Session ID Out** | 次回 Create 用の採番値 |

`Session Array Out` と `Next Session ID Out` は実装・デバッグ確認用の状態出力として扱い、Public / TestStand境界へActiveX Refを含むSession Stateを公開しない。

---

# 3. 全体構成

## 3.1 エラー入力の先行判定

最初に `error in.status` を `Unbundle By Name` で取り出し、**error status = TRUE の場合は内部処理を行わずに既定値を返す構成**にした。

### エラー時の返却値

| 出力 | 値 |
|---|---|
| **Session Out** | default session |
| **Session ID Out** | 0 |
| **Found?** | false |
| **Session Array Out** | 空配列 |
| **Next Session ID Out** | 0 |
| **エラー出力** | 入力 error をそのまま pass-through |

この返却値は呼出し結果の表示値であり、**FGV内部のSession Array / Next Session IDは変更しない**。上流エラー時はAction処理そのものを実行しない。

---

## 3.2 FGV 本体

エラーがない場合のみ、**While Loop + 未初期化 Shift Register** を使って状態を保持する構成にした。

### 保持している内部状態

| 状態 | 保持方法 | 内容 |
|---|---|---|
| **Session Array** | Shift Register | 登録済みセッション配列 |
| **Next Session ID** | Shift Register | 次回 Create で使う採番値 |

While Loop は1回で停止する。この形で **FGVの呼び出しごとに内部状態を読み書き**する。

VI Executionは **Non-reentrant** とし、Registry内部の状態更新を直列化する。

Session clusterにはActiveX参照が含まれるため、Registryは参照のHolderとして扱い、参照のClose / Quit / Start / Stopは別のCleanup / Public経路で実施する。

---

# 4. Action ごとの作成内容

# 4.1 Create の作成手順

## 目的

新しいセッションを配列へ追加し、Session ID を採番する。

## 処理方針

| 項目 | 内容 |
|---|---|
| 登録先 | Session Array の末尾 |
| 採番元 | Next Session ID |
| 0 の扱い | 0 は Invalid / Unassigned。初回のみ有効 ID **1** を使用 |
| ID再利用 | LabVIEWプロセス存続中は禁止 |
| 枯渇判定 | `4294967295 (U32 max)` を使用不可として扱う |

## 実装手順

`Current Next Session ID` を入力として受ける。未初期化Shift Registerの初回値0を判定し、0の場合は **1** を使用し、それ以外は現在値をそのまま使用する。この出力を **Effective Session ID** とした。

次に `Effective Session ID == 4294967295` を `Equal?` で判定する。ここでCreate成功系と枯渇系に分岐させた。

### Create 成功時

| 処理 | 使用ノード |
|---|---|
| Session ID を session cluster に埋め込む | **Bundle By Name(Session ID)** |
| 末尾 index を求める | **Array Size** |
| 配列末尾に追加する | **Insert Into Array** |
| 次 ID を計算する | **Add** |

`Session In.Session ID` は信用せず、Registryが発行した `Effective Session ID` で上書きした **Registered Session** を作成する。

### Create 成功時の返却値

| 出力 | 値 |
|---|---|
| **Found?** | true |
| **Session Array Out** | Registered Session追加後配列 |
| **Session ID Out** | Effective Session ID |
| **Next Session ID Out** | Effective Session ID + 1 |
| **Session Out** | **Registered Session** |
| **エラー出力** | incoming error pass-through |

これにより `Session ID Out` と `Session Out.Session ID` は一致する。

### Create 枯渇時

セッションは追加しない。`Found? = false` とし、専用エラーを `Bundle By Name(status, code, source)` で組み立てる。

### Create 枯渇時のエラー内容

| 項目 | 値 |
|---|---|
| **status** | true |
| **code** | -710110 |
| **source** | `CANalyzer_Session_Registry.vi / Action=Create / Session ID exhausted` |

### Create 枯渇時の返却値

| 出力 | 値 |
|---|---|
| **Session Array Out** | 変更なし |
| **Session ID Out** | 0 |
| **Next Session ID Out** | 変更なし |
| **Session Out** | default session |
| **Found?** | false |
| **エラー出力** | 上記エラー cluster |

---

# 4.2 Get の作成手順

## 目的

指定した `Session ID` に一致するセッションを返す。

## 処理方針

Session Arrayから **Session IDだけを抜き出した配列**を作り、その配列に対して `Search 1D Array` を使って検索する。

## 実装手順

`Current Session Array` を **For Loop の indexing tunnel** に入れる。ループ内で `Unbundle By Name(Session ID)` を使い、各要素のSession IDを取り出す。For Loopのauto-indexed outputで **Session IDの1D配列**を作る。

その後、`Search 1D Array` で入力 `Session ID` を検索する。戻りindexが `0以上` であることを `Greater Or Equal?` で判定し、Found / Not FoundのCase Structureに分岐する。

### Found 時

| 処理 | 使用ノード |
|---|---|
| 元の Session Array から要素取得 | **Index Array** |

### Found 時の返却値

| 出力 | 値 |
|---|---|
| **Found?** | true |
| **Session Out** | 見つかった session |
| **Session ID Out** | 入力 Session ID |
| **Session Array Out** | 変更なし |
| **Next Session ID Out** | 変更なし |
| **エラー出力** | incoming error pass-through |

### Not Found 時の返却値

| 出力 | 値 |
|---|---|
| **Found?** | false |
| **Session Out** | default session |
| **Session ID Out** | 入力 Session ID |
| **Session Array Out** | 変更なし |
| **Next Session ID Out** | 変更なし |
| **エラー出力** | incoming error pass-through |

Getでは、**見つからないこと自体は通常状態**と考え、追加エラーは立てない。Session存在必須の上位Service / Public API側で `Found?=False` を `-710102` へ変換する。

---

# 4.3 Update の作成手順

## 目的

指定した `Session ID` に一致する既存セッションを更新する。

## 処理方針

検索ロジックはGetと同じにし、Found時だけ `Replace Array Subset` で配列要素を置換する。

## 実装手順

Getと同じ方法でSession ID配列を作り、`Search 1D Array` でindexを求める。`index >= 0` を `Greater Or Equal?` で判定し、Found / Not Foundに分岐する。

### Found 時

入力 `Session In` の `Session ID` がずれていても、外から指定したIDを正とするため、まず `Bundle By Name(Session ID)` で **入力 Session ID を session cluster に上書き**する。その後、`Replace Array Subset` で該当indexの要素を更新する。

### Found 時に使うノード

| 処理 | 使用ノード |
|---|---|
| Session ID を強制反映 | **Bundle By Name(Session ID)** |
| 配列要素更新 | **Replace Array Subset** |

### Found 時の返却値

| 出力 | 値 |
|---|---|
| **Found?** | true |
| **Session Out** | 更新後 session cluster |
| **Session ID Out** | 入力 Session ID |
| **Session Array Out** | 更新後配列 |
| **Next Session ID Out** | 変更なし |
| **エラー出力** | incoming error pass-through |

### Not Found 時の返却値

| 出力 | 値 |
|---|---|
| **Found?** | false |
| **Session Out** | default session |
| **Session ID Out** | 入力 Session ID |
| **Session Array Out** | 変更なし |
| **Next Session ID Out** | 変更なし |
| **エラー status** | true |
| **エラー code** | **-710102** |

Updateは「存在するSessionを更新する命令」であるため、不存在をsilent successにはしない。**Fail Closed** とし、不存在Sessionを自動Createしない。

---

# 4.4 Remove の作成手順

## 目的

指定した `Session ID` に一致するセッションを配列から削除する。

## 処理方針

検索ロジックはGet / Updateと同じにし、Found時だけ `Delete From Array` で1要素削除する。

## 実装手順

Get / Updateと同じく、Session ArrayからSession ID配列を作る。`Search 1D Array` で対象indexを求め、`index >= 0` で分岐する。

### Found 時

削除前のsessionを返したいため、まず `Index Array` で該当要素を取得する。その後 `Delete From Array` に `length = 1` を与えて、該当要素を削除する。

### Found 時に使うノード

| 処理 | 使用ノード |
|---|---|
| 削除対象の取得 | **Index Array** |
| 1 要素削除 | **Delete From Array** |

### Found 時の返却値

| 出力 | 値 |
|---|---|
| **Found?** | true |
| **Session Out** | 削除された session |
| **Session ID Out** | 入力 Session ID |
| **Session Array Out** | 削除後配列 |
| **Next Session ID Out** | 変更なし |
| **エラー出力** | incoming error pass-through |

### Not Found 時の返却値

| 出力 | 値 |
|---|---|
| **Found?** | false |
| **Session Out** | default session |
| **Session ID Out** | 入力 Session ID |
| **Session Array Out** | 変更なし |
| **Next Session ID Out** | 変更なし |
| **エラー出力** | incoming error pass-through |

Removeは **idempotent cleanup** を優先し、不存在をerrorにしない。Registry RemoveではActiveX RefをCloseしない。

---

# 4.5 Clear All の作成手順

## 目的

内部保持しているSession Arrayを初期化する。Clear AllはUnit Test / 開発時Reset用途であり、Productionの通常Cleanupには使用しない。

## 実装内容

| 出力 | 値 |
|---|---|
| **Session Array Out** | 空配列 |
| **Session Out** | default session |
| **Found?** | false |
| **Session ID Out** | 0 |
| **Next Session ID Out** | **Current Next Session IDを維持** |
| **エラー出力** | incoming error pass-through |

Clear Allで初期化するのはSession Arrayだけであり、**Next Session IDは0または1へ戻さない**。LabVIEWプロセス存続中は一度発行したSession IDを再利用しない。

また、Clear AllではActiveX RefをCloseしない。ActiveX Refが生存している通常Production経路からClear Allを使用しない。

---

# 5. 実装上のポイント

## 5.1 状態の持ち方

| 項目 | 方針 |
|---|---|
| **セッション集合** | 配列で保持 |
| **検索キー** | Session ID |
| **採番状態** | Next Session ID を別管理 |
| **初回状態** | 未初期化SRの0を初回Create時のみ1へ正規化 |
| **Clear All** | Session ArrayのみEmpty、Next Session ID維持 |

## 5.2 Session ID の扱い

| ルール | 内容 |
|---|---|
| **0 は未使用** | Invalid / Unassignedとして予約 |
| **初回ID** | 1 |
| **採番は単調増加** | Remove / Clear Allしても詰めない・戻さない |
| **ID再利用禁止** | LabVIEWプロセス存続中は再利用しない |
| **U32 max は使用しない** | 枯渇扱いで `-710110` を返す |

## 5.3 error の扱い

| 場面 | 方針 |
|---|---|
| **上流 error あり** | Actionをスキップ、内部状態不変、元errorをpass-through |
| **Get Not Found** | Found?=false、追加errorなし |
| **Update Not Found** | Found?=false、**-710102** |
| **Remove Not Found** | Found?=false、追加errorなし |
| **Create 枯渇** | **-710110** |

---

# 6. 動作確認観点

## 6.1 基本シナリオ

| 手順 | 期待結果 |
|---|---|
| 初回 **Create A** | Found=true、Session ID Out=1、Session Out.Session ID=1、Next Session ID Out=2 |
| **Create B** | Found=true、Session ID Out=2、Session Out.Session ID=2、Next Session ID Out=3 |
| **Get(ID=1)** | Session Aを取得 |
| **Update(ID=1)** | 対象sessionが更新される |
| **Get(ID=1)** | 更新後sessionが取得できる |
| **Remove(ID=1)** | Found=true、削除したsessionが返る |
| **Get(ID=1)** | Found=false、errorなし |
| **Clear All** | Session Arrayは空、Next Session IDは3を維持 |
| Clear All後 **Create C** | Session ID Out=3。ID=1へ戻らない |

## 6.2 例外シナリオ

| 手順 | 期待結果 |
|---|---|
| 上流 error を入れて呼ぶ | Actionスキップ、内部状態不変、error pass-through |
| Create を ID 枯渇状態で呼ぶ | `-710110` を返す |
| 存在しない ID で Get | Found=false、error追加なし |
| 存在しない ID で Update | Found=false、`-710102` |
| 存在しない ID で Remove | Found=false、error追加なし |

---

# 7. Reference Ownership / Concurrency

Registryは `Application Ref` / `System Ref` / `Measurement Ref` の **Holder** であり、ownerではない。

Registry内では以下を行わない。

- Close Reference
- Application Quit
- Measurement Start
- Measurement Stop

`Get`で返した `Session Out` のRefはService内部で一時利用する借用コピーとして扱う。

Registry自体はNon-reentrantとし、Session Array / Next Session IDの更新を直列化する。一方、Get後の同一Sessionに対するActiveX操作競合はRegistryでは防がない。本番ActiveX操作は後続の `CANalyzer_Execute_Command.vi` を非再入の一本化ポイントとして使用する。

---

# 8. 確定状態

Nigel AIによる設計差分レビューで、旧As-Builtとの差分として以下3点を検出した。

1. Clear All時のNext Session ID reset
2. Update Not Foundのsilent miss
3. Create成功時のSession Outが元Session In

Production Safetyを優先し、**09Bの確定設計を維持して実VIを修正**した。

最終状態は以下で確定する。

| 項目 | 最終契約 |
|---|---|
| Clear All時のNext Session ID | **維持する。ID再利用禁止** |
| UpdateでSession ID Not Found | `Found?=False` + `error=-710102` |
| Create成功時のSession Out | Session IDを書き込んだ **Registered Session** |
| Get Not Found | `Found?=False`、errorなし |
| Remove Not Found | `Found?=False`、errorなし |
| Create exhausted | `-710110` |
| Registry ownership | ActiveX Ref Holder。Close / Quit / Start / Stopしない |
| Concurrency | Registry stateはNon-reentrant。ActiveX操作は後続 `CANalyzer_Execute_Command.vi` で直列化 |

以上を `CANalyzer_Session_Registry.vi` の最終As-Builtとして扱う。
