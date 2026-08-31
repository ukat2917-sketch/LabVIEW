# 09O. CANalyzer Fault Injection Public API 設計正本

**制定日：2026-08-31**  
**最終更新日：2026-08-31**  
**Status:** FROZEN DESIGN / IMPLEMENTATION PENDING  
**Design Investigation:** PASS  
**P0:** 0  
**P1:** 0  
**Human Freeze Gate:** APPROVED  
**Runtime / Hardware E2E:** PENDING

> 本書を CANalyzer Fault Injection Public API の Public I/O、Fault authority、support matrix、0/1 mapping、cleanup safety、error policy、Frozen Algorithm、Static Acceptance の単一正本とする。  
> 既存 Single SysVar Public API は `09N_CANalyzer_Single_SysVar_Public_API設計.md`、共通AI協調開発プロセスは `00D_AI協調LabVIEW設計実装レビュープロセス.md` に従う。

---

# 0. Freeze Summary

```text
Feature
= CANalyzer Fault Injection Public API

Status
= FROZEN DESIGN / IMPLEMENTATION PENDING

Public Target Authority
= CANalyzer_Fault_Target.ctl typed enum

Public Fault Authority
= CANalyzer_Fault_Type.ctl typed enum

Set transport
= existing CANalyzer_Write_SysVar.vi

Fault OFF / Clear
= I32 0

Fault ON
= I32 1

Write verification
= TRUE fixed

Unsupported Target × Fault Type
= explicit pre-validation

Dedicated error
= -710119 Unsupported Fault Target / Fault Type

Cleanup
= dedicated CANalyzer_Clear_All_Faults.vi

Clear algorithm
= per-target Alive → Checksum → gated Timeout

Fault registry
= NONE

Execute_Command extension
= NONE

Existing Closed VI / typedef amendment
= NONE

TestStand sequence
= NOT IMPLEMENTED / FUTURE PHASE

P0
= 0

P1
= 0
```

Human Freeze Gateで次を承認済み。

1. Fault Targetはtyped enumとする。
2. unsupported Target × Fault TypeはPublic VIで明示pre-validationする。
3. dedicated error codeは `-710119` とする。
4. Target enum表示名はactual Namespaceに近いexact raw namespace表記とする。

---

# 1. Evidence Baseline

## 1.1 Current Configuration / CAPL authority

Human-confirmed current CANalyzer Configuration：

```text
C:\Program Files\Vector CANalyzer 12.0\設定ファイル\SVS_d2_rev4 1.cfg
```

Configuration actualからSystem Variable群とCAPL参照を確認済み。

```text
CAPL_CAN.can
CAPL_CAN.cbf
```

Current CAPL actualでFault behaviorを確認した。

## 1.2 Existing Production primitive

Fault control transportは既存Static Closed Public APIを再利用する。

```text
CANalyzer_Set_Fault.vi
        ↓
CANalyzer_Write_SysVar.vi
        ↓
CANalyzer_Execute_Command.vi
        ↓
Write SysVar
```

既存 `CANalyzer_Write_SysVar.vi` の責務・Request mapping・verify semanticsは09Nを正とする。

## 1.3 Existing cleanup state

TestStand sequenceはまだ未実装。

したがってcurrent actualでは：

```text
Existing TestStand Fault Cleanup
= NONE

Existing TestStand Abort Cleanup
= NONE

CANalyzer_Stop.vi Fault Clear Ownership
= NONE

CANalyzer_Close.vi Fault Clear Ownership
= NONE

CAPL explicit on-start Fault Clear
= NONE

Current Cleanup Owner
= NONE
```

このgapを埋めるPublic safety primitiveとして `CANalyzer_Clear_All_Faults.vi` を今回のFeatureに含める。

---

# 2. Confirmed CAPL Fault Contract

## 2.1 Alive Counter

Control System Variable：

```text
ALIVE_COUNTER
```

CAPL condition：

```text
ALIVE_COUNTER == 0
```

のときAlive Counterをincrementする。

Fault側ではControl SysVarがnon-zeroの場合、Alive increment処理を実行しない。

Public canonical mapping：

```text
Fault OFF / Clear = 0
Fault ON          = 1
```

CAPLはnon-zero全般をFault pathとして扱うが、Public APIは`1`だけを生成する。

## 2.2 Checksum

Control System Variable：

```text
CHECKSUM
```

Public / CAPL mapping：

```text
Normal / Clear = 0
Fault          = 1 exactly
```

Fault時は正常計算したChecksumを`checksum + 1`へ変更する。

## 2.3 Timeout

Control System Variable：

```text
TIMEOUT
```

CAPLでは：

```text
TIMEOUT == 0
→ output(message)

TIMEOUT != 0
→ output(message)を実行しない
```

Public canonical mapping：

```text
Fault OFF / Clear = 0
Fault ON          = 1
```

## 2.4 Value type

Configuration actual：

```text
type=int
bitcount=32
isSigned=true
```

LabVIEW mapping：

```text
CANalyzer_Value_Type = I32
Nurmeric Value       = DBL carrier 0.0 / 1.0
```

`Nurmeric Value` はcurrent actual exact labelでありrenameしない。

Existing conversion pipelineで`CANalyzer_Value_Type=I32`の場合、DBL carrierからLong Integerへ変換する。

---

# 3. Fault Support Matrix

## 3.1 Full Fault targets

次の11 targetはcurrent CAPL actualでAlive / Checksum / Timeoutすべてを確認済み。

| Fault Target | Namespace | Alive | Checksum | Timeout |
|---|---|---:|---:|---:|
| `ID03AD5D62` | `ID03AD5D62` | Yes | Yes | Yes |
| `ID158` | `ID158` | Yes | Yes | Yes |
| `ID03AD558E` | `ID03AD558E` | Yes | Yes | Yes |
| `ID03AD5D03` | `ID03AD5D03` | Yes | Yes | Yes |
| `ID03AD5D0A` | `ID03AD5D0A` | Yes | Yes | Yes |
| `ID212` | `ID212` | Yes | Yes | Yes |
| `ID0CD9AB55` | `ID0CD9AB55` | Yes | Yes | Yes |
| `ID0CD9AE3D` | `ID0CD9AE3D` | Yes | Yes | Yes |
| `ID0CD9AD07` | `ID0CD9AD07` | Yes | Yes | Yes |
| `ID408` | `ID408` | Yes | Yes | Yes |
| `ID579` | `ID579` | Yes | Yes | Yes |

## 3.2 Timeout-only targets

次の2 targetはcurrent CAPL actualでTimeout behaviorのみを確認済み。

| Fault Target | Namespace | Alive | Checksum | Timeout |
|---|---|---:|---:|---:|
| `ID14003807` | `ID14003807` | No | No | Yes |
| `ID14004807` | `ID14004807` | No | No | Yes |

Configurationに他のFault-like SysVarが存在しても、current CAPL behavior evidenceがないtargetをPublic support matrixへ追加しない。

---

# 4. New Typedef Contract

## 4.1 `CANalyzer_Fault_Type.ctl`

Enum。ordinalは次でFreezeする。

```text
0 Alive Counter
1 Checksum
2 Timeout
```

Policy：

- append-only
- ordinal変更禁止
- raw String / raw numericをPublic fault type authorityにしない

## 4.2 `CANalyzer_Fault_Target.ctl`

Enum。表示名はactual Namespaceと同じraw namespace表記とする。

```text
0  ID03AD5D62
1  ID158
2  ID03AD558E
3  ID03AD5D03
4  ID03AD5D0A
5  ID212
6  ID0CD9AB55
7  ID0CD9AE3D
8  ID0CD9AD07
9  ID408
10 ID579
11 ID14003807
12 ID14004807
```

Policy：

- append-only
- evidence-authorized only
- Configuration上の全Namespaceのmirrorにはしない
- CAPL behavior evidenceを確認したtargetだけ追加可能
- ordinal変更禁止

---

# 5. Error Contract

## 5.1 New error

```text
-710119 Unsupported Fault Target / Fault Type
```

Meaning：

> Requested Fault Type is not supported for the requested Fault Target under the current behavior-confirmed Fault support matrix.

Generation authority：

```text
CANalyzer_Set_Fault.vi
```

`CANalyzer_Clear_All_Faults.vi`はcallerからTarget / Fault Typeを受け取らないため、通常このerrorを生成しない。

## 5.2 Unsupported combination

例：

```text
Fault Target = ID14003807
Fault Type   = Alive Counter
```

はSysVar existenceへ委譲せず、Public Fault authority違反としてwrite前に`-710119`でrejectする。

Resolve SysVarが成功する可能性やSysVar存在有無は、Fault behavior support authorityの代わりにならない。

---

# 6. `CANalyzer_Set_Fault.vi` Public Contract

Path candidate：

```text
C:\LabVIEW work\SVS_AutoTestSystem\60_CAN\30_Public\CANalyzer_Set_Fault.vi
```

## 6.1 Inputs

| Terminal | Type | Default | Contract |
|---|---|---|---|
| `Session ID` | U32 | required | target CANalyzer session |
| `Fault Target` | `CANalyzer_Fault_Target.ctl` | ordinal 0 | typed target authority |
| `Fault Type` | `CANalyzer_Fault_Type.ctl` | ordinal 0 | typed fault authority |
| `Fault Active?` | Boolean | False | False=Clear, True=Fault ON |
| `error in` | error cluster | No Error | normal operation error chain |

## 6.2 Outputs

| Terminal | Type | Contract |
|---|---|---|
| `SysVar Verified?` | Boolean | System Variable write/readback verification result only |
| `error out` | error cluster | validation/write error |

## 6.3 Do not expose

Public I/Oへ次を出さない。

```text
Namespace String
Variable Name String
raw Fault Value
CANalyzer_SysVar_Value
Verify After Write?
DBL Verify Tolerance
Read Value
Requested Value
```

---

# 7. `CANalyzer_Set_Fault.vi` Frozen Algorithm

## 7.1 Incoming error

`error in.status=True`なら通常operationとしてshort-circuitする。

```text
SysVar Verified? = False
error out         = original error in
Write SysVar      = NOT CALLED
```

Fault cleanup用途は本VIではなく`CANalyzer_Clear_All_Faults.vi`が所有する。

## 7.2 Validate Target × Fault Type

Support MatrixをPublic authorityとする。

```text
11 full targets
→ Alive / Checksum / Timeout valid

ID14003807
ID14004807
→ Timeout only valid
```

unsupported combinationならwrite前に：

```text
error = -710119
SysVar Verified? = False
```

## 7.3 Target mapping

`Fault Target` → exact Namespace Stringを明示mappingする。

```text
ID03AD5D62 → "ID03AD5D62"
ID158      → "ID158"
...
ID14004807 → "ID14004807"
```

mappingをcaller input Stringへ委譲しない。

## 7.4 Fault Type mapping

```text
Alive Counter → "ALIVE_COUNTER"
Checksum      → "CHECKSUM"
Timeout       → "TIMEOUT"
```

## 7.5 Fault value construction

Default `CANalyzer_SysVar_Value`をseedとする。

```text
CANalyzer_Value_Type = I32
Nurmeric Value       = Fault Active? ? 1.0 : 0.0
Boolean Value        = default preserve
String Value         = default preserve
```

`Nurmeric Value`のactual carrierはDBL。

## 7.6 Write primitive call

`CANalyzer_Write_SysVar.vi`へ：

```text
Session ID            = public Session ID
Namespace             = mapped Namespace
Variable Name         = mapped Variable Name
Write Value            = built CANalyzer_SysVar_Value
Verify After Write?    = TRUE constant
DBL Verify Tolerance   = 0.0 constant
error in               = current no-error validation chain
```

## 7.7 Result mapping

```text
CANalyzer_Write_SysVar.Verified?
→ SysVar Verified?

CANalyzer_Write_SysVar.error out
→ error out
```

`SysVar Verified?`はCAN Bus behavior verificationではない。

意味は：

```text
System Variable write/readback verified
```

のみ。

---

# 8. `CANalyzer_Clear_All_Faults.vi` Public Contract

Path candidate：

```text
C:\LabVIEW work\SVS_AutoTestSystem\60_CAN\30_Public\CANalyzer_Clear_All_Faults.vi
```

## 8.1 Inputs

| Terminal | Type | Contract |
|---|---|---|
| `Session ID` | U32 | target session |
| `error in` | error cluster | original caller error; cleanupはerror有でも実行する |

## 8.2 Outputs

| Terminal | Type | Contract |
|---|---|---|
| `All Cleared?` | Boolean | frozen support matrix上の必要clearがすべて成功した場合のみTrue |
| `error out` | error cluster | Original Error > First Cleanup Error |

追加のfailed-array / count / detail clusterは今回Publicへ出さない。

---

# 9. `CANalyzer_Clear_All_Faults.vi` Safety Model

## 9.1 Why Timeout last

CAPL message processing orderは概ね：

```text
signal assignment
→ Alive fault condition
→ checksum calculation
→ Checksum fault condition
→ Timeout condition
→ output(message)
```

Timeout active時は最後の`output(message)`が抑止されるため、Alive / Checksum FaultをCAN Bus observable上maskし得る。

Timeoutを先にClearすると、Alive / Checksumが異常のままmessage transmissionを再開する可能性がある。

したがってTimeoutはsame-target prerequisite clear成功後のみ解除する。

## 9.2 Per-target gated clear

full targetごとに：

```text
1. Alive Counter clearをattempt
2. Checksum clearをattempt
3. AliveとChecksumの両方がsuccessならTimeout clearをattempt
4. どちらか失敗ならTimeout clearをSKIP
5. next targetへ進む
```

重要：

- Alive clear失敗後もChecksum clearはbest effortでattemptする。
- Checksum clear失敗後も他target cleanupは続行する。
- Timeoutをskipしたtargetは`All Cleared?=False`。
- first failureだけをFirst Cleanup Errorとして保持する。

Timeout-only target：

```text
ID14003807
ID14004807
```

はprerequisiteがないためTimeout clearを直接attemptする。

---

# 10. `CANalyzer_Clear_All_Faults.vi` Frozen Algorithm

## 10.1 Error initialization

開始時：

```text
Original Error
= error inを保存

Working Cleanup Error
= No Error

First Cleanup Error
= No Error

All Cleared?
= True candidate state
```

incoming `error in.status=True`でもcleanup operationをskipしない。

## 10.2 Clear write construction

全Fault Clear writeで：

```text
CANalyzer_Value_Type = I32
Nurmeric Value       = 0.0
Verify After Write?  = TRUE
DBL Verify Tolerance = 0.0
```

各writeは既存`CANalyzer_Write_SysVar.vi`を使用する。

cleanupをincoming errorで抑止しないため、各cleanup writeへ渡すoperation-side errorはNo Error pathとする。

## 10.3 Full target operation

各full targetについて：

### Step A: Alive

```text
write Namespace::<ALIVE_COUNTER> = I32 0
verify = TRUE
```

success flagを保持。

failure時：

- `All Cleared? = False`
- First Cleanup Errorが未設定ならこのerrorを保存
- 後続Checksumは実行する

### Step B: Checksum

```text
write Namespace::<CHECKSUM> = I32 0
verify = TRUE
```

success flagを保持。

failure時：

- `All Cleared? = False`
- First Cleanup Errorが未設定ならこのerrorを保存

### Step C: Timeout gate

```text
Alive success AND Checksum success
```

がTrueの場合のみ：

```text
write Namespace::<TIMEOUT> = I32 0
verify = TRUE
```

FalseならTimeout writeを実行せず：

```text
All Cleared? = False
```

Timeout write failure時もFirst Cleanup Error retention ruleを適用する。

## 10.4 Timeout-only target operation

`ID14003807`、`ID14004807`は：

```text
write Namespace::<TIMEOUT> = I32 0
verify = TRUE
```

を直接attemptする。

## 10.5 Best effort across targets

1 targetでfailureしても残りtarget cleanupを継続する。

一つのtarget failureが他target Timeout clearをglobalにblockしてはいけない。

per-target gateをauthorityとする。

## 10.6 Final error priority

最終：

```text
if Original Error.status == True
    error out = Original Error
else if First Cleanup Error.status == True
    error out = First Cleanup Error
else
    error out = No Error
```

`All Cleared?`はcleanup execution resultを表すため、Original Errorが存在していても全必要clearが成功した場合はTrueとなり得る。

Original Errorの存在だけを理由に`All Cleared?`をFalseへしない。

---

# 11. Fault Registry Policy

今回追加しない。

```text
Active Fault Registry
Fault History
Global Variable
FGV
Session State extension
```

理由：

- support matrixはbounded
- canonical clear valueは0
- Clear Allはhistoryではなくknown support matrixをdefensiveにclearできる
- registryは新しいstate authority、同期、stale state問題を増やす

Future optimizationとして必要になった場合は別Feature / Design Gateを通す。

---

# 12. Execute_Command / Existing Closed Boundary

今回変更しない。

```text
CANalyzer_Execute_Command_Type.ctl
CANalyzer_Execute_Command_Request.ctl
CANalyzer_Execute_Command_Result.ctl
CANalyzer_Execute_Command.vi
CANalyzer_Write_SysVar.vi
CANalyzer_Stop.vi
CANalyzer_Close.vi
```

Fault Set / Clearは既存Write SysVar primitive上の用途別Public abstractionとして実装する。

new Execute_Command commandは追加しない。

---

# 13. TestStand Future Contract Boundary

TestStand sequenceはcurrent actualでは未実装であり今回作成しない。

Future TestStand Design Candidateの責務境界：

```text
Setup / Main
→ CANalyzer_Set_Fault.vi

Cleanup / Abort-safe path
→ CANalyzer_Clear_All_Faults.vi
→ CANalyzer_Stop.vi
→ CANalyzer_Close.vi
```

ただしTestStand Error / Abort / Terminate時にどのCleanup sequence/groupが必ず実行されるかは、TestStand設計Phaseで一次資料とactual sequenceを基にFreezeする。

今回のLabVIEW Fault API設計からTestStand runtime semanticsを推測して固定しない。

---

# 14. Non-Goals

今回のFeatureでは次を実施しない。

- Batch Fault API
- auto-duration Fault API
- Fault registry
- CAN Bus behavior verificationをPublic Set Fault結果に含めること
- CAPL変更
- Configuration変更
- Stop / CloseへのFault Clear追加
- existing Execute_Command extension
- TestStand sequence実装
- unsupported evidence targetの自動support

---

# 15. Implementation Slices

00Dに従い、Design Freeze後は次の順でHuman implementationする。

```text
F1
CANalyzer_Fault_Type.ctl
CANalyzer_Fault_Target.ctl

F2
CANalyzer_Set_Fault.vi

F3
Nigel Focused As-Built Inspection
+ ChatGPT Drift Gate

F4
CANalyzer_Clear_All_Faults.vi

F5
Nigel Focused As-Built Inspection
+ ChatGPT Drift Gate

F6
Combined Final Algorithm-to-Wiring Audit

Post completion
Nigel Final Model Confirmation
→ Final As-Built GUI Reconstruction Procedure
→ Human Static Gate
→ STATIC IMPLEMENTATION CLOSED
```

GUI Construction ProcedureはこのFrozen Designを基にPhase 4でfresh生成する。

---

# 16. Static Acceptance

## 16.1 `CANalyzer_Fault_Type.ctl`

- ordinal 0=`Alive Counter`
- ordinal 1=`Checksum`
- ordinal 2=`Timeout`
- append-only

## 16.2 `CANalyzer_Fault_Target.ctl`

- 13 items exact
- ordinal / display textが§4.2と一致
- unsupported / evidence未確認targetなし
- append-only

## 16.3 `CANalyzer_Set_Fault.vi`

- incoming errorはoriginalをpreserveしwriteしない
- support matrix validationがwriteより前
- invalid combinationは`-710119`
- target enum → exact Namespace mapping
- fault enum → exact Variable Name mapping
- `CANalyzer_Value_Type=I32`
- `Nurmeric Value=0.0 / 1.0`
- Verify=True固定
- DBL tolerance=0.0固定
- `SysVar Verified?`はWrite `Verified?`のみ
- CAN behavior verifiedと表現しない
- existing Closed VI / typedef変更なし

## 16.4 `CANalyzer_Clear_All_Faults.vi`

- incoming errorありでもcleanup実行
- Original Error保存
- First Cleanup Error retention
- full targetでAlive / Checksumを両方attempt
- same-target Alive+Checksum成功時だけTimeout clear
- prerequisite failure時Timeout skip
- Timeout-only targetは直接Timeout clear
- target failure後も他targetをbest effortで継続
- clear value=I32 0
- Verify=True固定
- `All Cleared?`は必要clear全成功時のみTrue
- final priority Original Error > First Cleanup Error > No Error
- registryなし

---

# 17. Runtime / Hardware Validation Pending

Static Closure後に最低限次を確認する。

| Runtime Test | Expected |
|---|---|
| Alive ON → SysVar readback | 1 verified |
| Alive ON → CAN | Alive Counter freeze |
| Alive OFF | counter resumes |
| Checksum ON → readback | 1 verified |
| Checksum ON → CAN | invalid checksum (`normal + 1`) |
| Checksum OFF | normal checksum resumes |
| Timeout ON → readback | 1 verified |
| Timeout ON → CAN | target message disappears |
| Timeout OFF | next target timer cycleでmessage resumes |
| Alive + Checksum | both behavior observable while Timeout off |
| Timeout + other faults | Timeout masks CAN observability |
| Clear All mixed state | safe per-target restoration |
| partial clear failure | Timeout gate behavior |
| Measurement restart | Fault state persistence / recovery actual確認 |
| Future TestStand cleanup / abort | separate TestStand phase |

Static PASSはRuntime verifiedを意味しない。

---

# 18. Frozen Decisions

次はHuman Approval済みFrozen領域であり、実装途中に無言変更しない。

```text
Fault Target = typed enum
Fault Type = typed enum
Target labels = raw namespace style
Fault OFF/Clear = 0
Fault ON = 1
Value Type = I32
Nurmeric carrier = DBL
Verify = TRUE fixed
Unsupported combination = pre-validation
Unsupported error = -710119
Set transport = existing CANalyzer_Write_SysVar.vi
Clear All = dedicated Public VI
Clear order = per-target Alive → Checksum → gated Timeout
Timeout-only target = direct Timeout clear
Partial failure = best effort + same-target Timeout skip
Error retention = First Cleanup Error
Final cleanup error priority = Original Error > First Cleanup Error
Fault Registry = none
Execute_Command extension = none
Stop / Close amendment = none
```

Frozen Design変更が必要になった場合は00Dに従い実装を停止し、Design Reviewへ戻ってHuman Approval後にre-freezeする。

---

# 19. Design Freeze Gate

| Gate | Result |
|---|---|
| Evidence sufficient | PASS |
| Target authority | PASS |
| Fault authority | PASS |
| 0/1 mapping | PASS |
| I32 construction | PASS |
| Verify policy | PASS |
| Unsupported matrix | PASS |
| Error code | PASS (`-710119`) |
| Clear All necessity | PASS |
| Clear order | PASS |
| Partial failure behavior | PASS |
| Incoming error cleanup | PASS |
| Registry need | PASS |
| Execute_Command extension need | PASS |
| Existing Closed regression | PASS |
| Human Freeze Gate | PASS |
| P0 | 0 |
| P1 | 0 |

```text
CANalyzer Fault Injection Public API

DESIGN / ALGORITHM
= FROZEN

IMPLEMENTATION
= PENDING

NEXT
= Nigel GUI CONSTRUCTION INSTRUCTIONS
```
