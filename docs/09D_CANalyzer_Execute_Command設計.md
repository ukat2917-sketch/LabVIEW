# 09D. CANalyzer_Execute_Command.vi 最終設計

**最終整理日：2026-08-18**

> **本章の役割**：`CANalyzer_Execute_Command.vi` のProduction向け最終設計と、人手実装時の作業契約を定義する。
>
> `CANalyzer_Session_Registry.vi` の状態管理契約は [`09B_CANalyzer_Session_Registry設計.md`](./09B_CANalyzer_Session_Registry設計.md) を正とし、Registry実装実績は [`09C_CANalyzer_Session_Registry実装手順.md`](./09C_CANalyzer_Session_Registry実装手順.md) を参照する。
>
> 本章は `CANalyzer_Execute_Command.vi` 作成前の設計正本とする。VI作成完了後は本章と実VIを差分レビューし、As-Built差分があれば設計変更か実装修正かを明示して確定する。

---

# 1. 目的

`CANalyzer_Execute_Command.vi` は、**CANalyzer本番ActiveX操作を1本の非再入VIへ集約し、LabVIEW内で同期直列化するためのService Dispatcher** とする。

基本構造：

```text
Public API
  ↓
CANalyzer_Execute_Command.vi
  ↓
Session Registry / Service / ActiveX Wrapper
  ↓
Result
```

`CANalyzer_Session_Registry.vi` のNon-reentrant設定はRegistry内部のSession Array / Next Session ID更新を直列化するが、Registry `Get` 後に取得した同一SessionのActiveX Refへ複数Public VIが同時アクセスする競合までは防げない。

そのため、Production Public APIから行うActiveX操作は `CANalyzer_Execute_Command.vi` のNon-reentrant境界内へ通す。

PoCではWrapper直呼びを許容するが、Production APIはDispatcher経由へ統一する。

---

# 2. 採用Architecture

## 2.1 採用案

**Session単位Serialized Service Dispatcher方式** を採用する。

```text
Public CANalyzer_Read_SysVar.vi
  ↓ Request
CANalyzer_Execute_Command.vi（Non-reentrant）
  ↓ Read SysVar Case
Registry Get
  ↓
Resolve SysVar
  ↓
Wrapper Read
  ↓
Variant To Value
  ↓
Cleanup
  ↓
Result
```

```text
Public CANalyzer_Write_SysVar.vi
  ↓ Request
CANalyzer_Execute_Command.vi（Non-reentrant）
  ↓ Write SysVar Case
Registry Get
  ↓
Resolve SysVar
  ↓
Validation
  ↓
Value To Variant
  ↓
Wrapper Write
  ↓
Optional Verify
  ↓
Cleanup
  ↓
Result
```

## 2.2 不採用

### Public API単位巨大Dispatcher

Public相当処理をすべて巨大Caseへ抱え込みやすく、Request / Resultの肥大化と責務重複を招くため採用しない。

### 低レベルActiveX Operation Dispatcher

Property / Invoke単位だけを直列化すると、Read SysVar / Write SysVarの一連処理全体が同一Non-reentrant境界へ載らず、複合処理のatomicityが弱くなるため採用しない。

## 2.3 初期直列化粒度

初期版は **Global serialization** とする。

```text
CANalyzer_Execute_Command.vi = Non-reentrant
```

Sessionごとの並列化は初期版では行わない。

理由：

- CANalyzer COM / ActiveXのThread競合回避を優先する。
- 初期Session数は小規模想定。
- Production Safetyを性能より優先する。
- TestStand側では将来Named Lockも併用可能。

---

# 3. Responsibility Boundary

| レイヤ | 責務 |
|---|---|
| **CANalyzer_Execute_Command.vi** | Production ActiveX操作の同期直列化。一連処理をService / Wrapperへ委譲 |
| **CANalyzer_Session_Registry.vi** | Session State保持。ActiveX Ref holder。Create / Get / Update / Remove / Clear All |
| **Public API** | 呼出しやすい用途別I/O、既定値補完、Execute_Command呼出し、結果整形 |
| **Service** | SysVar Resolve、Variant変換、Measurement待ち等 |
| **ActiveX Wrapper** | CANalyzer ActiveX Property / Invoke呼出し |

Execute_Command自身へActiveX Property Node / Invoke Nodeを乱造せず、原則として既存Service / Wrapperを再利用する。

---

# 4. Initial Vertical Slice

初期版Commandは **2値のみ** とする。

## 4.1 `CANalyzer_Execute_Command_Type.ctl`

Enum順を固定する。

```text
0 = Read SysVar
1 = Write SysVar
```

後続Commandは必ず **末尾追加** とし、既存numeric valueを変更しない。

将来候補：

```text
Start Measurement
Stop Measurement
Open Session
Close Session
```

初期版ではこれらをEnumへ入れない。

---

# 5. Request / Result Typedef

## 5.1 `CANalyzer_Execute_Command_Request.ctl`

| Field | 型 | 用途 |
|---|---|---|
| `Command` | `CANalyzer_Execute_Command_Type.ctl` | Command selector |
| `Session ID` | U32 | 対象Session。0はInvalid |
| `Namespace` | String | SysVar Namespace |
| `Variable Name` | String | SysVar名 |
| `Value` | `CANalyzer_SysVar_Value.ctl` | Write要求値 |
| `Expected Value Type` | `CANalyzer_Value_Type.ctl` | Read変換期待型 |
| `Verify After Write?` | Boolean | Write後Read Back実施可否 |
| `DBL Verify Tolerance` | DBL | DBL Verify用absolute tolerance |

### 契約

- `error in` はRequestへ入れない。VI端子のerror in/outだけを正とする。
- ActiveX RefをRequestへ入れない。
- Read SysVarでは `DBL Verify Tolerance` は未使用。
- Write Verify=Falseでは `DBL Verify Tolerance` は未使用。
- Write Verify=TrueかつValue Type=DBLの場合のみToleranceを評価する。
- Tolerance=0はexact compare。
- Tolerance<0はFail Closed。

## 5.2 `CANalyzer_Execute_Command_Result.ctl`

| Field | 型 | 意味 |
|---|---|---|
| `Session ID` | U32 | 対象Session |
| `Requested Value` | `CANalyzer_SysVar_Value.ctl` | Write要求値 |
| `Read Value` | `CANalyzer_SysVar_Value.ctl` | Read結果またはVerify Read Back値 |
| `Verified?` | Boolean | Verify比較結果 |

`Requested Value` は **実際の書込み成功を保証する値ではなく、Callerが要求した値** を意味する。

Command別意味：

| Command | Session ID | Requested Value | Read Value | Verified? |
|---|---|---|---|---|
| Read SysVar | 対象ID | default | 読み取り値 | False |
| Write SysVar / Verify=False | 対象ID | Request.Value | default | False |
| Write SysVar / Verify=True | 対象ID | Request.Value | Read Back値 | 比較結果 |

---

# 6. `CANalyzer_Execute_Command.vi` I/O

## Input

| 端子 | 型 |
|---|---|
| `Request` | `CANalyzer_Execute_Command_Request.ctl` |
| `error in` | error cluster |

## Output

| 端子 | 型 |
|---|---|
| `Result` | `CANalyzer_Execute_Command_Result.ctl` |
| `error out` | error cluster |

Connector PaneはRequest / Resultとerror in / error outを左右対称に配置する。

VI Properties：

```text
Execution = Non-reentrant
Auto error handling = Off
Show front panel when called = Off
```

---

# 7. Error Code Allocation

現時点で使用を確認しているCANalyzer系error code：

| Code | 意味 |
|---:|---|
| `-710102` | Session Not Found / Update Not Found |
| `-710104` | Measurement Timeout |
| `-710106` | Value Conversion Error |
| `-710108` | Verify Mismatch |
| `-710110` | Session ID Exhausted |
| `-710112` | Invalid DBL Verify Tolerance |

`-710108` と `-710112` は今回のExecute_Command設計で採用する。

GitHub上の現行コード検索では `-710108` / `-710112` の既存使用は確認されていないため、初期版のCANalyzer error codeとして登録する。

---

# 8. Common Error Policy

```text
error in.status = True
  ↓
Commandを実行しない
  ↓
Result = default
  ↓
error out = original error
```

Session必須Commandでは：

```text
Registry Get
  ↓
Found? = False
  ↓
-710102
```

Service / Wrapperから既存errorが返った場合は元error codeを保持する。

必要に応じてsourceへ以下を追記する。

```text
CANalyzer_Execute_Command.vi
Command=<Command Name>
Session ID=<id>
<Original Source>
```

元error codeを別codeで潰さない。

---

# 9. Read SysVar Contract

処理順：

```text
error in確認
  ↓
Registry Get
  ↓
Found?確認
  ↓
Session.System Ref取得
  ↓
Resolve SysVar
  ↓
Variable Ref validity判定
  ↓
CAN_AX_Read_Variable_Value.vi
  ↓
CANalyzer_Variant_To_Value.vi
  ↓
Variable Ref cleanup
  ↓
Operation Error / Close Error merge
  ↓
Result
```

## 9.1 Registry Not Found

```text
Found? = False
Result.Session ID = Request.Session ID
Requested Value = default
Read Value = default
Verified? = False
error = -710102
```

## 9.2 Found

- Registryから取得したSystem RefはBorrowed。
- `CANalyzer_Resolve_SysVar.vi`へSystem Ref / Namespace / Variable Nameを渡す。
- Resolve内部のNamespace / Variables RefはResolve側でClose。
- Resolveが返したVariable RefはExecute_CommandがCleanupする。
- Read ValueをExpected Value Typeへ変換する。
- `Requested Value=default`, `Verified?=False`。

---

# 10. Write SysVar Contract

最終処理順：

```text
1. Registry Get
2. Resolve SysVar
3. Variable Ref validity判定
4. Write事前入力Validation
5. Value To Variant
6. CANalyzer Write
7. Verify分岐
8. Prior Error Guard
9. Compare
10. Cleanup
11. Error Merge
12. Result
```

---

# 11. 追加設計: Write事前入力Validation

## 11.1 目的

`Write SysVar` では、**CANalyzerへ実際にWriteする前にRequestを検証する**。

無効なDBL Verify Toleranceを検出した後にCANalyzer値が変更されることを防止する。

## 11.2 Validation条件

以下のときだけ `DBL Verify Tolerance` を評価する。

| 条件 | 必須 |
|---|---|
| `Verify After Write? = True` | Yes |
| `Request.Value.Value Type = DBL` | Yes |

Validation Needed：

```text
Verify After Write?
AND
(Value Type == DBL)
```

## 11.3 事前判定

| 条件 | 動作 |
|---|---|
| Validation Needed=False | Tolerance未使用、Writeへ進む |
| Validation Needed=True かつ Tolerance>=0 | Writeへ進む |
| Validation Needed=True かつ Tolerance<0 | Fail Closed |

## 11.4 Fail Closed

`DBL Verify Tolerance < 0` の場合：

```text
status = True
code = -710112
source = CANalyzer_Execute_Command.vi / Write SysVar / Invalid DBL Verify Tolerance
```

さらに：

- `CANalyzer_Value_To_Variant.vi` を実行しない。
- `CAN_AX_Write_Variable_Value.vi` を実行しない。
- Read Backを実行しない。
- Compareを実行しない。
- Variable Ref取得済みかつValidならCleanup。
- Cleanup後、Operation Errorを優先して返す。

Result：

```text
Session ID = Request.Session ID
Requested Value = Request.Value
Read Value = default
Verified? = False
```

## 11.5 実装位置

Write Caseの **Resolve + Variable Ref validity判定直後、Value To Variantより前** に配置する。

このValidationをVerify後段へ重複配置しない。

---

# 12. Write Verify=False

Validation通過後：

```text
Value To Variant
  ↓
Write
  ↓
Cleanup
  ↓
Error Merge
  ↓
Result
```

Result：

```text
Session ID = Request.Session ID
Requested Value = Request.Value
Read Value = default
Verified? = False
```

Write errorが発生してもVariable RefがValidならCleanupする。

---

# 13. Write Verify=True

Validation通過後：

```text
Value To Variant
  ↓
Write
  ↓
Read Back
  ↓
Variant To Value
  ↓
Prior Error Guard
  ↓
Type Match
  ↓
Value Match
  ↓
Verified?
  ↓
必要なら -710108
  ↓
Cleanup
  ↓
Error Merge
```

---

# 14. Prior Error Guard

`CANalyzer_Variant_To_Value.vi.error out.status` を比較前に確認する。

| status | 動作 |
|---|---|
| True | Compareしない、Verified?=False、元errorを保持、Cleanupへ進む |
| False | Type / Value Compareへ進む |

これにより、Read Back失敗や`-710106`等の変換errorをVerify mismatch errorで上書きしない。

Verify mismatch errorは **prior operation errorが存在しない場合だけ** 生成する。

---

# 15. Verify Comparison

## 15.1 Type Match

比較前に必ず：

```text
Request.Value.Value Type
==
Read Back Value.Value Type
```

を確認する。

最終判定：

```text
Verified? = Type Match AND Value Match
```

## 15.2 Value Match

| Value Type | 比較 |
|---|---|
| Boolean | Boolean Value完全一致 |
| I32 | Numeric Value完全一致 |
| U32 | Numeric Value完全一致 |
| String | String Value完全一致 |
| DBL | absolute tolerance比較 |

I32 / U32は`CANalyzer_SysVar_Value.ctl`のNumeric ValueがDBL保持であるため、Value Type一致を前提としてNumeric Valueを比較する。

## 15.3 DBL

```text
abs(Request.Numeric Value - Read.Numeric Value)
<=
Request.DBL Verify Tolerance
```

Tolerance=0ならexact compare。

Tolerance<0はWrite前Validationで`-710112`として拒否済みであり、Compare段では再Validationしない。

## 15.4 Verify Mismatch

prior errorなしでType mismatchまたはValue mismatchの場合：

```text
status = True
code = -710108
source = CANalyzer_Execute_Command.vi / Write SysVar / Verify mismatch
Verified? = False
```

一致時：

```text
Verified? = True
error = Success
```

---

# 16. Variable Ref Validity / Cleanup Contract

Variable Ref validityはLabVIEW標準の `Not A Number/Path/Refnum?` を使用して判定する。

```text
Variable Ref
  ↓
Not A Number/Path/Refnum?
  ↓
Not
  ↓
Variable Ref Valid?
```

## Cleanup Policy

| Variable Ref Valid? | 動作 |
|---|---|
| True | Operation errorの有無に関係なくClose |
| False | Closeしない |

Application Ref / System Ref / Measurement RefはBorrowedであり、通常Read / Write CommandではCloseしない。

---

# 17. Cleanup-safe Pattern

Operation処理とCleanup処理のerrorを分離する。

```text
Operation Error保持
  ↓
Variable Ref Valid?判定
  ↓
True:
  Clear Errors
    ↓
  Close Reference
    ↓
  Close Error

False:
  Close Error = no error

Operation Error + Close Error
  ↓
Merge Errors
```

Merge Priority：

| 状態 | Primary Error |
|---|---|
| Operation Errorあり + Close Errorあり | Operation Error |
| Operation Errorなし + Close Errorあり | Close Error |
| Operation Errorあり + Close Errorなし | Operation Error |

`Merge Errors.error in 1 = Operation Error`

`Merge Errors.error in 2 = Close Error`

とする。

Close ErrorがOperation Errorのcodeを上書きしない。

---

# 18. Reference Ownership

| Ref | Ownership | Close責務 |
|---|---|---|
| Application Ref | Borrowed | Execute_CommandではCloseしない |
| System Ref | Borrowed | Execute_CommandではCloseしない |
| Measurement Ref | Borrowed | Execute_CommandではCloseしない |
| Namespace Ref | Resolve内部temporary | Resolve側 |
| Variables Ref | Resolve内部temporary | Resolve側 |
| Variable Ref | Resolve後caller-owned temporary | Execute_Command |

RegistryはRef holderであり、Registry自身はClose / Quit / Start / Stopを行わない。

---

# 19. Manual Implementation Order

実装は以下の順で行う。

```text
STEP 1  既存VI / typedef重複確認
STEP 2  CANalyzer_Execute_Command_Type.ctl
STEP 3  CANalyzer_Execute_Command_Request.ctl
STEP 4  CANalyzer_Execute_Command_Result.ctl
STEP 5  CANalyzer_Execute_Command.vi Front Panel / Connector Pane / Non-reentrant
STEP 6  Outer error bypass
STEP 7  Command Case骨格
STEP 8  Read SysVar
STEP 9  Write SysVar: Registry Get / Resolve / Ref validity
STEP 9A Write事前入力Validation
STEP 10 Write Verify=False
STEP 11 Write Verify=True Read Back / Variant To Value
STEP 12 Prior Error Guard
STEP 13 Type Match / Value Compare / Verify mismatch
STEP 14 Cleanup-safe Close / Error Merge
STEP 15 Result確定
STEP 16 Static Review
```

---

# 20. STEP 9A Manual Work Instruction

## 目的

`Write SysVar` 実行前にDBL verify toleranceの事前検証を行う。

## 作成対象

`CANalyzer_Execute_Command.vi`

## 配置Primitive

- `Unbundle By Name` ×2
- `Equal?` ×1
- `And` ×1
- `Less?` ×1
- `Case Structure` ×1
- `Bundle By Name` ×1以上

## 配置位置

Write Caseの **Resolve + Ref validity判定直後、`CANalyzer_Value_To_Variant.vi` の前**。

## 判定ロジック

```text
Request.Verify After Write?
AND
(Request.Value.Value Type == DBL)
  ↓
Validation Needed?
```

さらに：

```text
Request.DBL Verify Tolerance < 0
```

を判定する。

Case selector：

```text
Validation Needed?
AND
(Tolerance < 0)
```

### FALSE

Value To Variantへ進む。

### TRUE

```text
status = True
code = -710112
source = CANalyzer_Execute_Command.vi / Write SysVar / Invalid DBL Verify Tolerance
```

Result：

```text
Session ID = Request.Session ID
Requested Value = Request.Value
Read Value = default
Verified? = False
```

Write / Read Back / Compareへ進まず、Variable Ref Valid?に従ってCleanupへ進む。

## 完了条件

- Negative toleranceでWriteへ進まない。
- `CANalyzer_Value_To_Variant.vi`を実行しない。
- `CAN_AX_Write_Variable_Value.vi`を実行しない。
- Valid Variable RefはCleanupされる。
- error code=`-710112`。

---

# 21. Production Safety Rules

1. Execute_CommandはNon-reentrant。
2. 初期版は全CANalyzer ActiveX操作をGlobal serial化する。
3. PublicへActiveX Refを公開しない。
4. error in.status=TrueならCommandを実行しない。
5. Registry Get Not Foundは`-710102`。
6. Service / Wrapper error codeをVerify errorで上書きしない。
7. Verify前にPrior Error Guardを入れる。
8. `Verified? = Type Match AND Value Match`。
9. DBL toleranceはCaller指定absolute toleranceを使う。
10. Negative toleranceはWrite前に`-710112`でFail Closed。
11. Verify mismatchは`-710108`。
12. Variable Ref validityをCleanup条件にする。
13. Operation ErrorをClose Errorより優先する。
14. Application / System / Measurement Refは通常CommandでCloseしない。
15. Variable Refのみcaller-owned temporaryとしてCloseする。
16. `Use Default If Unwired` に重要制御を依存しない。
17. ActiveX Property / Invoke NodeをExecute_Command内へ直接乱造しない。
18. Read / Write全体を同一Non-reentrant境界へ置く。

---

# 22. Static Review Checklist

- [ ] `CANalyzer_Execute_Command.vi = Non-reentrant`
- [ ] Global serializationが成立している
- [ ] PublicへActiveX Refを公開していない
- [ ] `error in.status=True`でbypass
- [ ] Registry Get Not Foundを`-710102`へ変換
- [ ] Command Enumは初期版2値のみ
- [ ] 後続Enum追加は末尾のみ
- [ ] RequestにActiveX Ref / error clusterを含めない
- [ ] Resultの`Requested Value`は要求値であり成功保証値ではない
- [ ] Read SysVarは`Read Value`を返す
- [ ] Write SysVarは`Requested Value`を返す
- [ ] Write前にRequest Validationを実施
- [ ] `Verify=True AND ValueType=DBL AND Tolerance<0`でWriteしない
- [ ] Invalid DBL toleranceは`-710112`
- [ ] Invalid DBL tolerance時もVariable Ref ValidならCleanup
- [ ] Verify=FalseまたはValueType!=DBLではToleranceを評価しない
- [ ] Verify comparison前にPrior Errorを確認
- [ ] Prior ErrorありならCompareしない
- [ ] 元error codeをVerify errorで潰さない
- [ ] `Verified? = Type Match AND Value Match`
- [ ] DBLはCaller指定Toleranceを使用
- [ ] Verify mismatchは`-710108`
- [ ] Variable Ref validityを基準にCleanup
- [ ] Operation ErrorをClose Errorより優先
- [ ] Borrowed Application/System/Measurement RefはCloseしない
- [ ] Variable RefのみClose
- [ ] `CANalyzer_Resolve_SysVar.vi`を再利用
- [ ] `CANalyzer_Value_To_Variant.vi`を再利用
- [ ] `CANalyzer_Variant_To_Value.vi`を再利用
- [ ] `CAN_AX_Read_Variable_Value.vi`を再利用
- [ ] `CAN_AX_Write_Variable_Value.vi`を再利用
- [ ] Execute_CommandにActiveX Nodeを直接乱造しない
- [ ] `Use Default If Unwired`へ重要制御を依存しない
- [ ] Connector Pane明示
- [ ] Broken Run Arrow = NO

---

# 23. 作成後の設計差分レビュー

`CANalyzer_Execute_Command.vi` および関連typedef作成完了後、**必ず実VIと本章を比較する設計差分レビュー**を行う。

最低確認対象：

```text
CANalyzer_Execute_Command_Type.ctl
CANalyzer_Execute_Command_Request.ctl
CANalyzer_Execute_Command_Result.ctl
CANalyzer_Execute_Command.vi
```

差分レビュー項目：

| 項目 | 設計期待 |
|---|---|
| Enum | Read SysVar=0 / Write SysVar=1 |
| Request Field | 本章5.1と一致 |
| Result Field | 本章5.2と一致 |
| Non-reentrant | Yes |
| Outer error bypass | Yes |
| Registry Not Found | -710102 |
| Write事前Validation | Write前 |
| Negative DBL tolerance | -710112 / Writeなし |
| Prior Error Guard | Compare前 |
| Verify mismatch | -710108 |
| Type Match | 必須 |
| DBL tolerance | Caller指定 |
| Ref validity | Cleanup条件 |
| Error merge | Operation優先 |
| Borrowed Ref Close | なし |
| Variable Ref Close | あり |
| Broken Run Arrow | NO |

差分が存在した場合は、以下のどれかで処理する。

```text
A. 本設計を維持し、実VIを修正
B. 実装を正とし、本設計を更新
C. 手順書の記載だけ修正
D. 追加設計Reviewを実施
```

Production Safetyに関わる差分をAs-Built優先で黙認しない。

---

# 24. Stop Point

本章の設計対象は初期Vertical Sliceの：

```text
Read SysVar
Write SysVar
```

まで。

以下は後続設計で追加する。

```text
Start Measurement
Stop Measurement
Open Session
Close Session
Batch Read / Write
Fault Set / Clear
```

初期版Execute_Command完成後に設計差分レビューを完了し、その後Public API実装へ進む。
