# 09N. CANalyzer Single SysVar Public API 最終設計正本

**最終更新日：2026-08-31**  
**Status:** FINAL DESIGN / FROZEN / IMPLEMENTATION PENDING  
**Design Review:** P0=0 / P1=0  
**Observable Design Ambiguity:** 0  
**GUI Reconstruction Procedure:** PENDING  
**Public `CANalyzer_Read_SysVar.vi`:** NOT IMPLEMENTED  
**Public `CANalyzer_Write_SysVar.vi`:** NOT IMPLEMENTED  
**Runtime / Hardware E2E:** PENDING

> 本書を Production Public `CANalyzer_Read_SysVar.vi` / `CANalyzer_Write_SysVar.vi` のPublic I/O、Request mapping、Result mapping、error flow、責務境界、Static Acceptanceの単一正本とする。  
> Internal Read / Write semanticsは current actual `CANalyzer_Execute_Command.vi` を正とし、本書ではPublic thin wrapperだけをFreezeする。  
> Dispatcher基盤は `09D_CANalyzer_Execute_Command設計.md`、AI協調開発プロセスは `00D_AI協調LabVIEW設計実装レビュープロセス.md` を参照する。

---

# 0. Freeze Summary

```text
CANalyzer Single SysVar Public API

P0 = 0
P1 = 0
Observable Design Ambiguity = 0

Architecture = SEPARATE PUBLIC VI

CANalyzer_Read_SysVar.vi
= FINAL DESIGN / FROZEN

CANalyzer_Write_SysVar.vi
= FINAL DESIGN / FROZEN

GUI Reconstruction Procedure = PENDING
Implementation = PENDING
Runtime / Hardware E2E = PENDING
```

Phase 0 / 0.5 actual evidenceおよびPhase 2 Design Investigationで、Read / Writeのcurrent internal path、exact Request / Result fields、verify semantics、cleanup/error priority、thin-wrapper feasibilityを確認済み。Public APIはReadとWriteを分離する。

---

# 1. Responsibility Boundary

Public VIの責務は次だけとする。

- callerが扱いやすい用途別Public I/O
- default `CANalyzer_Execute_Command_Request`生成
- `Bundle By Name`による必要field設定
- typed command enum設定
- `CANalyzer_Execute_Command.vi` call
- Result必要fieldの抽出
- direct `error in / error out`

Public VIへ持ち込まないもの：

- Session Registry
- ActiveX
- Resolve SysVar
- Variant変換
- Variable Ref cleanup
- DBL negative tolerance validation
- verify comparison
- verify mismatch error生成
- Clear Errors / Merge Errors
- local error生成
- Measurement / ownership / cache logic

Production ActiveX操作は `CANalyzer_Execute_Command.vi` のNon-reentrant境界を通す。

---

# 2. Shared Current Typedef Contract

## 2.1 `CANalyzer_Execute_Command_Type.ctl`

```text
0 Read SysVar
1 Write SysVar
2 Close Session
3 Start Measurement
4 Stop Measurement
```

既存ordinalを変更しない。

## 2.2 `CANalyzer_Execute_Command_Request.ctl`

current exact fields：

```text
Execute_Command_Type
Session ID
Namespace
Variable Name
CANalyzer_SysVar_Value
CANalyzer_Value_Type
Verify After Write?
DBL Verify Tolerance
Measurement Timeout ms
```

Public Read / Write追加によるtypedef amendmentは行わない。

## 2.3 `CANalyzer_Execute_Command_Result.ctl`

current exact fields：

```text
Session ID
Requested Value
Read Value
Verified?
Session Removed?
Measurement Running?
```

Public Read / Write追加によるtypedef amendmentは行わない。

## 2.4 `CANalyzer_SysVar_Value.ctl`

current exact fields：

```text
CANalyzer_Value_Type
Boolean Value
Nurmeric Value
String Value
```

`Nurmeric Value` はcurrent actual exact labelである。今回renameしない。

## 2.5 `CANalyzer_Value_Type.ctl`

```text
0 Boolean
1 I32
2 U32
3 DBL
4 String
```

---

# 3. Public API Architecture

Read / Writeを別Public VIとする。

```text
CANalyzer_Read_SysVar.vi
  ↓ Read SysVar Request
CANalyzer_Execute_Command.vi
```

```text
CANalyzer_Write_SysVar.vi
  ↓ Write SysVar Request
CANalyzer_Execute_Command.vi
```

Unified `CANalyzer_SysVar_Command.vi` は採用しない。

理由：

- existing Public patternがoperation別thin wrapper
- Read / WriteでRequest subsetが異なる
- Result semanticsが異なる
- TestStand上で用途が明確
- future Batchのsingle-item primitiveとして自然

---

# 4. `CANalyzer_Read_SysVar.vi` Public Contract

## Inputs

| Terminal | Type | Contract |
|---|---|---|
| `Session ID` | U32 | target session |
| `Namespace` | String | SysVar Namespace |
| `Variable Name` | String | SysVar name |
| `Expected Value Type` | `CANalyzer_Value_Type.ctl` | read conversion target |
| `error in` | error cluster | standard direct error flow |

## Outputs

| Terminal | Type | Contract |
|---|---|---|
| `Read Value` | `CANalyzer_SysVar_Value.ctl` | `Result.Read Value` |
| `error out` | error cluster | Execute_Command final error |

Publicへ出さないResult field：`Session ID`, `Requested Value`, `Verified?`, `Session Removed?`, `Measurement Running?`。

### `Expected Value Type` default

Front Panel control defaultは current typedef defaultに従い `Boolean` でよい。ただしproduction operationではcallerが対象SysVarに合わせて明示設定することを運用契約とする。

---

# 5. Frozen Read Algorithm

```text
if caller invokes CANalyzer_Read_SysVar:

    request = default CANalyzer_Execute_Command_Request

    request.Execute_Command_Type = Read SysVar
    request.Session ID = Public Session ID
    request.Namespace = Public Namespace
    request.Variable Name = Public Variable Name
    request.CANalyzer_Value_Type = Public Expected Value Type

    result, executeError =
        CANalyzer_Execute_Command(
            request,
            Public error in)

    Public Read Value = result.Read Value
    Public error out = executeError
```

Unused Request fieldsはdefault preserveとする。

Public側でincoming error Caseを作らない。`error in`はExecute_Commandへ直接接続する。

---

# 6. `CANalyzer_Write_SysVar.vi` Public Contract

## Inputs

| Terminal | Type | Contract |
|---|---|---|
| `Session ID` | U32 | target session |
| `Namespace` | String | SysVar Namespace |
| `Variable Name` | String | SysVar name |
| `Write Value` | `CANalyzer_SysVar_Value.ctl` | requested write payload |
| `Verify After Write?` | Boolean | write後readback verifyを要求 |
| `DBL Verify Tolerance` | DBL | DBL verify absolute tolerance |
| `error in` | error cluster | standard direct error flow |

## Outputs

| Terminal | Type | Contract |
|---|---|---|
| `Read Value` | `CANalyzer_SysVar_Value.ctl` | verify readback。Verify=Falseではdefault |
| `Verified?` | Boolean | verify successのみTrue |
| `error out` | error cluster | Execute_Command final error |

`Requested Value`はPublic outputへ出さない。callerが入力した`Write Value`のechoに近く、TestStand側でもinput loggingで保持できるため。

### Public defaults

```text
Verify After Write? = False
DBL Verify Tolerance = 0.0
```

`DBL Verify Tolerance`はinternal contractどおり、Verify=Trueかつtype=DBLの場合だけ意味を持つ。

---

# 7. Write Type Derivation Contract

Public callerへValue Typeを二重指定させない。

```text
request.CANalyzer_Value_Type
=
Public Write Value.CANalyzer_Value_Type
```

これをFrozenとする。

`Write Value.CANalyzer_Value_Type` と別のpublic `CANalyzer_Value_Type` inputを追加しない。

理由：current actual Write pipelineではRequest.`CANalyzer_Value_Type`をDBL validation、verify readback conversion、type match、comparison dispatchに使用する。Write payload側typeと異なる値を意図的に指定する正当なProduction use caseは認めない。

---

# 8. Frozen Write Algorithm

```text
if caller invokes CANalyzer_Write_SysVar:

    request = default CANalyzer_Execute_Command_Request

    request.Execute_Command_Type = Write SysVar
    request.Session ID = Public Session ID
    request.Namespace = Public Namespace
    request.Variable Name = Public Variable Name
    request.CANalyzer_SysVar_Value = Public Write Value
    request.CANalyzer_Value_Type =
        Public Write Value.CANalyzer_Value_Type
    request.Verify After Write? = Public Verify After Write?
    request.DBL Verify Tolerance = Public DBL Verify Tolerance

    result, executeError =
        CANalyzer_Execute_Command(
            request,
            Public error in)

    Public Read Value = result.Read Value
    Public Verified? = result.Verified?
    Public error out = executeError
```

`Measurement Timeout ms`その他unused fieldsはdefault preserve。

---

# 9. Public Observable Verify Semantics

## Verify=False

```text
Read Value = default
Verified? = False
error out = Write / Cleanup final error
```

`Verified?=False`は「verify disabled」でも成立する。callerは自身が渡した`Verify After Write?`と`error out`を合わせて解釈する。

## Verify=True

| Scenario | Read Value | Verified? | error out |
|---|---|---:|---|
| verify success | readback value | True | No Error |
| verify mismatch | readback value | False | verify mismatch error |
| readback error | default / incomplete | False | original error |
| conversion error | default / conversion-failed state | False | conversion error |
| invalid negative DBL tolerance | default | False | `-710112` |
| cleanup error only | prior readback/default | prior state | cleanup error |

Public VIでこれらを再判定しない。

---

# 10. Direct Error Flow Contract

Read / Writeとも：

```text
Public error in
→ CANalyzer_Execute_Command.error in

CANalyzer_Execute_Command.error out
→ Public error out
```

Public側禁止：

- No Error constant injection
- Case gate
- Clear Errors
- Merge Errors
- local validation
- local error generation
- original error restore

---

# 11. Thin Wrapper Topology

Read：

```text
Default Request
   ↓
Bundle By Name
   ↓
CANalyzer_Execute_Command.vi
   ↓
Unbundle By Name(Result.Read Value)
   ↓
Read Value

error in → Execute_Command → error out
```

Write：

```text
Write Value ──┬──────────────→ Request.CANalyzer_SysVar_Value
              └─Unbundle CANalyzer_Value_Type
                    ↓
              Request.CANalyzer_Value_Type

Default Request
   ↓
Bundle By Name
   ↓
CANalyzer_Execute_Command.vi
   ↓
Unbundle By Name(Read Value, Verified?)
   ↓
Public outputs

error in → Execute_Command → error out
```

---

# 12. Connector Pane Design Constraint

Readは5 inputs / 2 outputs、Writeは7 inputs / 3 outputs。

- Inputs = left
- Outputs = right
- `error in` / `error out` = conventional lower terminals
- exact visual positionはGUI Reconstruction Procedure作成時にcurrent Public conventionを確認しHuman choiceとして確定する

この時点ではconnector indexを推測でFreezeしない。

---

# 13. TestStand Contract

PublicにActiveX Refを出さない。

TestStand LabVIEW Adapterから扱う主型：U32 / String / Boolean / DBL / enum / cluster / error cluster。

`CANalyzer_SysVar_Value.ctl` clusterはprimitive-only APIより設定量が多いがProduction contractとして許容する。必要なら将来TestStand convenience wrapperを上位に追加する。今回のPublic VIへTestStand専用変換責務を混ぜない。

---

# 14. Future Batch Compatibility

今回のsingle-item contractはfuture Batchの実装方式を拘束しない。

可能な将来形：

- single-item Public VIをloop
- Batch ServiceからExecute_Commandを順次call
- 専用Batch dispatcher

今回のRead expected type、Write type derivation、Verify semanticsをsingle-item primitiveとして再利用できる。

---

# 15. GUI Construction Freeze Inputs

NigelがGUI Reconstruction Procedureを作る際のauthority：

1. 本書のFrozen Public Contract
2. current actual Request / Result typedef
3. current actual `CANalyzer_Execute_Command.vi` connector
4. current actual `CANalyzer_Start.vi` / `CANalyzer_Stop.vi` Public pattern

実装前手順ではinternal Read / Write logicをPublic側へ複製しない。

特にWriteでは、`Write Value.CANalyzer_Value_Type`をUnbundleしてRequest.`CANalyzer_Value_Type`へ配線する施工を明示する。

---

# 16. Static Acceptance Gate

## Read

- [ ] File = `CANalyzer_Read_SysVar.vi`
- [ ] Public layer `60_CAN/30_Public`
- [ ] Inputs exact: Session ID / Namespace / Variable Name / Expected Value Type / error in
- [ ] Outputs exact: Read Value / error out
- [ ] typed command = Read SysVar
- [ ] Request.Session ID exact
- [ ] Request.Namespace exact
- [ ] Request.Variable Name exact
- [ ] Request.CANalyzer_Value_Type = Expected Value Type
- [ ] error in direct
- [ ] Result.Read Value direct
- [ ] error out direct
- [ ] Registry/ActiveX/Resolve/cleanupなし

## Write

- [ ] File = `CANalyzer_Write_SysVar.vi`
- [ ] Public layer `60_CAN/30_Public`
- [ ] Inputs exact: Session ID / Namespace / Variable Name / Write Value / Verify After Write? / DBL Verify Tolerance / error in
- [ ] Outputs exact: Read Value / Verified? / error out
- [ ] typed command = Write SysVar
- [ ] Request.Session ID exact
- [ ] Request.Namespace exact
- [ ] Request.Variable Name exact
- [ ] Request.CANalyzer_SysVar_Value = Write Value
- [ ] Request.CANalyzer_Value_Type = Write Value.CANalyzer_Value_Type
- [ ] Request.Verify After Write? exact
- [ ] Request.DBL Verify Tolerance exact
- [ ] no separate public Value Type input
- [ ] no Public Requested Value output
- [ ] error in direct
- [ ] Result.Read Value direct
- [ ] Result.Verified? direct
- [ ] error out direct
- [ ] Registry/ActiveX/Resolve/validation/compare/cleanupなし

## Regression

- [ ] Execute_Command typedef amendmentなし
- [ ] Read/Write internal Cases amendmentなし
- [ ] Start / Stop / Close unchanged
- [ ] command enum ordinal unchanged
- [ ] `Nurmeric Value` renameなし
- [ ] Broken Run Arrowなし
- [ ] unintended coercionなし
- [ ] broken typedefなし

---

# 17. Freeze Record

```text
CANalyzer Single SysVar Public API
FINAL DESIGN REVIEW = PASS

P0 = 0
P1 = 0
Observable Design Ambiguity = 0

Architecture = Separate Read / Write Public VI

Read Label = Expected Value Type
Read Outputs = Read Value + error out

Write Type Mapping = Derived from Write Value.CANalyzer_Value_Type
Write Outputs = Read Value + Verified? + error out
Requested Value Public Output = OMIT

Verify After Write? default = False
DBL Verify Tolerance default = 0.0
Expected Value Type control default = Boolean
Expected Value Type operational expectation = caller explicitly selects target type

NO PUBLIC ERROR LOGIC
NO PUBLIC INTERNAL SERVICE LOGIC

FINAL DESIGN = FROZEN
GUI RECONSTRUCTION PROCEDURE = PENDING
IMPLEMENTATION = PENDING
RUNTIME / HARDWARE E2E = PENDING
```

次工程は00D Phase 4として、Nigelがcurrent actual Public patternと本Frozen Designを基にGUI Construction Instructionsを作成する。