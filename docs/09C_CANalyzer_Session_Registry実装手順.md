# 09C. CANalyzer Session Registry 実装手順

**最終整理日：2026-08-18**

> **本章の役割**：作成完了した `CANalyzer_Session_Registry.vi` について、Nigel AIで整理した人手実装手順と現状のAs-Built動作を記録する。
>
> 設計上の正本は [`09B_CANalyzer_Session_Registry設計.md`](./09B_CANalyzer_Session_Registry設計.md) とする。本章は実装実績を記録するため、設計正本との差分がある箇所は末尾の「設計正本との差分」に明示する。

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
| **Clear All** | 全セッションを初期化する |

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
| **Session Out** | 取得・更新・削除結果として返すセッション |
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

これにより、上流エラー時に状態管理ロジックへ入らないようにしている。

---

## 3.2 FGV 本体

エラーがない場合のみ、**While Loop + 未初期化 Shift Register** を使って状態を保持する構成にした。

### 保持している内部状態

| 状態 | 保持方法 | 内容 |
|---|---|---|
| **Session Array** | Shift Register | 登録済みセッション配列 |
| **Next Session ID** | Shift Register | 次回 Create で使う採番値 |

While Loop は1回で停止する。この形で **FGVの呼び出しごとに内部状態を読み書き**する。

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
| 0 の扱い | 0 は未使用とし、最初の有効 ID は **1** |
| 枯渇判定 | `4294967295 (U32 max)` を使用不可として扱う |

## 実装手順

`Current Next Session ID` を入力として受ける。まず `Equal?` で **0かどうか**を判定する。0の場合は小さい Case Structure で **1** を出し、それ以外はそのまま通す。この出力を **Effective Session ID** とした。

次に `Effective Session ID == 4294967295` を `Equal?` で判定する。ここでCreate成功系と枯渇系に分岐させた。

### Create 成功時

| 処理 | 使用ノード |
|---|---|
| Session ID を session cluster に埋め込む | **Bundle By Name(Session ID)** |
| 末尾 index を求める | **Array Size** |
| 配列末尾に追加する | **Insert Into Array** |
| 次 ID を計算する | **Add** |

### Create 成功時の返却値

| 出力 | 値 |
|---|---|
| **Found?** | true |
| **Session Array Out** | 追加後配列 |
| **Session ID Out** | Effective Session ID |
| **Next Session ID Out** | Effective Session ID + 1 |
| **Session Out** | 入力 `Session In` |
| **エラー出力** | incoming error pass-through |

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

Getでは、**見つからないこと自体は通常状態**と考え、追加エラーは立てない方針にした。

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
| **エラー出力** | incoming error pass-through |

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

---

# 4.5 Clear All の作成手順

## 目的

内部保持しているセッション状態を完全に初期化する。

## 実装内容

定数で以下を返すだけのシンプルな構成にした。

| 出力 | 値 |
|---|---|
| **Session Array Out** | 空配列 |
| **Session Out** | default session |
| **Found?** | false |
| **Session ID Out** | 0 |
| **Next Session ID Out** | 0 |
| **エラー出力** | incoming error pass-through |

このケースでShift Registerの中身が初期状態へ戻る。

---

# 5. 実装上のポイント

## 5.1 状態の持ち方

| 項目 | 方針 |
|---|---|
| **セッション集合** | 配列で保持 |
| **検索キー** | Session ID |
| **採番状態** | Next Session ID を別管理 |
| **初期状態** | Session Array = 空、Next Session ID = 0 |

## 5.2 Session ID の扱い

| ルール | 内容 |
|---|---|
| **0 は未使用** | 初回 Create で1を割り当てる |
| **採番は単調増加** | Removeしても詰めない |
| **U32 max は使用しない** | 枯渇扱いでエラー返却 |

## 5.3 error の扱い

| 場面 | 方針 |
|---|---|
| **上流 error あり** | 処理をスキップして pass-through |
| **Get / Update / Remove で Not Found** | 追加エラーなし |
| **Create 枯渇** | 専用エラーを返す |

---

# 6. 動作確認観点

## 6.1 基本シナリオ

| 手順 | 期待結果 |
|---|---|
| **Clear All** | 配列空、Next Session ID = 0 |
| **Create** | Found=true、Session ID Out=1、Next Session ID Out=2 |
| **Get(ID=1)** | 作成した session を取得 |
| **Update(ID=1)** | 対象 session が更新される |
| **Get(ID=1)** | 更新後の session が取得できる |
| **Remove(ID=1)** | Found=true、削除した session が返る |
| **Get(ID=1)** | Found=false |

## 6.2 例外シナリオ

| 手順 | 期待結果 |
|---|---|
| 上流 error を入れて呼ぶ | 処理スキップ、error pass-through |
| Create を ID 枯渇状態で呼ぶ | `-710110` を返す |
| 存在しない ID で Get / Update / Remove | Found=false、error 追加なし |

---

# 7. 補足

このVIは **FGVパターンで共有状態を管理するためのレジストリVI** として作成した。

今後セッション数が増える場合は、線形検索のままでも小規模なら十分だが、件数が大きくなる場合は **Map風の構造**や **DVR（Data Value Reference）** を検討余地として残している。現時点では、**可読性と保守性を優先して配列 + Search 1D Array** を採用した。

---

# 8. 設計正本との差分

本章は作成済みVIのAs-Built手順をそのまま記録しているため、`09B_CANalyzer_Session_Registry設計.md` と以下の差分がある。

| 項目 | 09B 設計正本 | 09C As-Built記録 |
|---|---|---|
| Clear All時のNext Session ID | **維持する**。ID再利用禁止 | **0へ戻す** |
| UpdateでSession ID Not Found | `Found?=False` + `error=-710102` | `Found?=False` + 追加errorなし |
| Create成功時のSession Out | Session IDを書き込んだ**登録済みSession** | 記録上は入力`Session In` |

特にClear AllでNext Session IDを0へ戻す実装は、Clear All後の次回CreateでSession IDを1から再利用する動作になる。Production契約としてどちらを採用するかは、Public API実装へ進む前に09Bと実VIを再確認して確定する。

また、Update Not Foundのerror policyも09BとAs-Builtで異なるため、上位Service / Public APIが期待するNot Found契約を確定してから統合する。
