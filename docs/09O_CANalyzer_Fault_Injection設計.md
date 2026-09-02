# 09O. CANalyzer Fault Injection Public API 設計正本

**制定日：2026-08-31**  
**最終更新日：2026-09-02**  
**Status:** STATIC IMPLEMENTATION CLOSED / RUNTIME PENDING  
**Design Investigation:** PASS  
**Design / Algorithm Freeze:** PASS  
**Combined Final Algorithm-to-Wiring Audit:** PASS  
**Final Actual Model:** CONFIRMED  
**Final As-Built Reconstruction:** PASS  
**Human Static Gate:** PASS  
**P0:** 0  
**P1:** 0  
**Runtime / Hardware E2E:** PENDING

> 本書を CANalyzer Fault Injection Public API の Public I/O、Fault authority、support matrix、0/1 mapping、cleanup safety、error policy、Frozen Algorithm、Static Closure、Runtime Pending 状態の単一正本とする。  
> 既存 Single SysVar Public API は `09N_CANalyzer_Single_SysVar_Public_API設計.md`、共通AI協調開発プロセスは `00D_AI協調LabVIEW設計実装レビュープロセス.md` に従う。

---

# 0. Closure Summary

```text
Feature
= CANalyzer Fault Injection Public API

Status
= STATIC IMPLEMENTATION CLOSED / RUNTIME PENDING

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

Stop / Close Fault Clear ownership
= NONE

Set Fault static implementation
= PASS

Clear All static implementation
= PASS

F6 Combined Final Algorithm-to-Wiring Audit
= PASS

Final Actual Model
= CONFIRMED

Final As-Built GUI Reconstruction
= PASS

Human Static Gate
= PASS

Runtime / Hardware E2E
= PENDING

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

Human Static Gateで次を確認済み。

1. `CANalyzer_Set_Fault.vi` / `CANalyzer_Clear_All_Faults.vi` のRun ArrowがBrokenでない。
2. 意図しないcoercion dotがない。特に `CANalyzer_Value_Type=I32` はexplicit enum接続である。
3. relevant Case出力の `Use Default If Unwired` はOFF。
4. relevant typedef linkageが維持されている。
5. Connector PaneのPublic terminal割当が完了している。

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

## 1.3 Existing cleanup state before this feature

TestStand sequenceはまだ未実装。

Feature開始時actualでは：

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

このgapを埋めるPublic safety primitiveとして `CANalyzer_Clear_All_Faults.vi` を本Featureで実装した。

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

Static Closure時actualではSet Fault / Clear Allの双方で `CANalyzer_Value_Type` はplain numericではなくexplicit enum `I32` ordinal 1へ接続され、Human Static Gateで意図しないcoercion dotなしを確認済み。

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

# 4. Typedef Contract

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

## 5.1 Dedicated error

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

# 6. `CANalyzer_Set_Fault.vi` Public Contract / As-Built

Path：

```text
C:\LabVIEW work\SVS_AutoTestSystem\60_CAN\30_Public\CANalyzer_Set_Fault.vi
```

## 6.1 Inputs

| Terminal | Type | Default | Contract |
|---|---|---|---|
| `Session ID` | U32 | required | target CANalyzer session |
| `CANalyzer_Fault_Target` | `CANalyzer_Fault_Target.ctl` | ordinal 0 | typed target authority |
| `CANalyzer_Fault_Type` | `CANalyzer_Fault_Type.ctl` | ordinal 0 | typed fault authority |
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

## 6.4 Connector Pane

Human Static Gateで全Public terminalの割当済み、未割当・重複なしを確認済み。

---

# 7. `CANalyzer_Set_Fault.vi` Frozen Algorithm / Final Actual Model

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
error.status = True
error.code   = -710119
error.source = "CANalyzer_Set_Fault.vi / Unsupported Fault Target / Fault Type"
SysVar Verified? = False
```

## 7.3 Target mapping

`CANalyzer_Fault_Target` → exact Namespace Stringを明示mappingする。

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
CANalyzer_Value_Type = explicit enum I32, ordinal 1
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
Write Value           = built CANalyzer_SysVar_Value
Verify After Write?   = TRUE constant
DBL Verify Tolerance  = 0.0 constant
error in              = incoming no-error operation path
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

# 8. `CANalyzer_Clear_All_Faults.vi` Public Contract / As-Built

Path：

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
| `error out` | error cluster | Original Error > First Cleanup Error > No Error |

追加のfailed-array / count / detail clusterはPublicへ出さない。

## 8.3 Connector Pane

Human Static Gateで全Public terminalの割当済み、未割当・重複なしを確認済み。

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

# 10. `CANalyzer_Clear_All_Faults.vi` Frozen Algorithm / Final Actual Model

## 10.1 Error initialization

開始時：

```text
Original Error
= error inを保存

First Cleanup Error
= No Error

All Cleared Candidate
= True
```

incoming `error in.status=True`でもcleanup operationをskipしない。

## 10.2 Clear write construction

全Fault Clear writeで：

```text
CANalyzer_Value_Type = explicit enum I32, ordinal 1
Nurmeric Value       = 0.0
Verify After Write?  = TRUE
DBL Verify Tolerance = 0.0
```

各writeは既存`CANalyzer_Write_SysVar.vi`を使用する。

各cleanup writeの `error in` はfresh No Errorとし、Original Error、First Cleanup Error、previous write error outを実行制御へ流さない。

## 10.3 Support matrix representation

current actualは次の4配列を固定13行で保持する。

```text
Namespace[]
Supports Alive?[]
Supports Checksum?[]
Supports Timeout?[]
```

全配列length=13、§3と同じindex orderをauthorityとする。

## 10.4 Full target operation

各full targetについて：

### Step A: Alive

```text
write Namespace::<ALIVE_COUNTER> = I32 0
Verify = TRUE
Tolerance = 0.0
error in = fresh No Error
```

success predicate：

```text
Alive Success
= Verified? AND NOT(error out.status)
```

failure時も後続Checksumは実行する。

### Step B: Checksum

```text
write Namespace::<CHECKSUM> = I32 0
Verify = TRUE
Tolerance = 0.0
error in = fresh No Error
```

success predicate：

```text
Checksum Success
= Verified? AND NOT(error out.status)
```

### Step C: Timeout gate

```text
TimeoutEligible
= Alive Success
  AND Checksum Success
  AND Supports Timeout?
```

Trueの場合のみ：

```text
write Namespace::<TIMEOUT> = I32 0
Verify = TRUE
Tolerance = 0.0
error in = fresh No Error
```

success predicate：

```text
Timeout Success
= Verified? AND NOT(error out.status)
```

FalseならTimeout writeを実行せず：

```text
Timeout Success = False
synthetic error = NONE
```

## 10.5 Timeout-only target operation

`ID14003807`、`ID14004807`はunsupported Alive / Checksumをsuccess=Trueへ正規化するため：

```text
Alive Success    = True
Checksum Success = True
Supports Timeout = True
```

となりTimeout clearを直接attemptする。

## 10.6 Current Target Cleared

```text
Current Target Cleared
= Alive Success
  AND Checksum Success
  AND Timeout Success
```

## 10.7 All Cleared sticky state

initial：

```text
All Cleared Candidate = True
```

update：

```text
Next All Cleared
= Previous All Cleared
  AND Current Target Cleared
```

一度Falseになった後、later successでTrueへ戻らない。

## 10.8 First Cleanup Error sticky state

initial：

```text
First Cleanup Error = No Error
```

execution order：

```text
Alive
→ Checksum
→ Timeout
```

最初のcleanup failureだけを保持し、later failureでoverwriteしない。

このretained stateはwrite `error in`へ接続しない。

## 10.9 Best effort across targets

1 targetでfailureしても残りtarget cleanupを継続する。

一つのtarget failureが他target Timeout clearをglobalにblockしてはいけない。

per-target gateをauthorityとする。

## 10.10 Final error priority

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

本Featureでは変更しない契約。

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

F6 local static auditではFault Injection VIs内にRegistry / Execute_Command extension / Stop / Close cleanup ownershipを導入した evidence はなかった。既存Infrastructureファイル自体の変更有無はlocal static inspectionだけではNOT OBSERVABLEであり、Fault Injection wiring authorityとしては導入されていないことを確認した。

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

本Featureでは次を実施しない。

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

# 15. Implementation / Review Closure

00DのPhase分離に従い、次を完了した。

```text
F1
CANalyzer_Fault_Type.ctl
CANalyzer_Fault_Target.ctl
= IMPLEMENTED

F2
CANalyzer_Set_Fault.vi
= IMPLEMENTED

F3 / F3.1
Nigel Focused As-Built Inspection
+ ChatGPT Drift Gate
= PASS

F4
CANalyzer_Clear_All_Faults.vi
= IMPLEMENTED

F5 / F5.1 / F5.2
Nigel Focused As-Built Inspection
+ root-drift closure re-review
+ ChatGPT Drift Gate
= PASS

F6
Combined Final Algorithm-to-Wiring Audit
= PASS

Post completion
Final Model Confirmation
= CONFIRMED

Final As-Built GUI Reconstruction Procedure
= PASS

Human Static Gate
= PASS

Final Feature Status
= STATIC IMPLEMENTATION CLOSED / RUNTIME PENDING
```

## 15.1 F5 closure history

F5 initial reviewで次のroot driftを検出し、Human修正後にclosureした。

```text
1. CANalyzer_Value_Type plain numeric → explicit enum I32
2. Verify After Write? dynamic state → TRUE fixed
3. Clear All write error in retained error → fresh No Error
4. All Cleared equation → Previous AND Current Target Cleared
```

F5.2 final closure：

```text
ROOT-1 = CLOSED
Set Fault Regression = NONE
Clear All Regression = NONE
P0 = 0
P1 = 0
F4 AS-BUILT = PASS
Observable Design Drift = 0
```

## 15.2 F6 combined final audit

```text
Fault Injection Combined Wiring = PASS
Set Fault = PASS
Clear All = PASS
Safety Invariants = PASS
Cross-VI Consistency = PASS
Observable Design Drift = 0
P0 = 0
P1 = 0
P2 = 0
```

## 15.3 Final Model Confirmation

```text
Final Actual Model = CONFIRMED
Internal Contradiction = 0
Unresolved Actual Ambiguity = 0
Observable Design Drift = 0
P0 = 0
P1 = 0
```

## 15.4 Final As-Built Reconstruction

current actual onlyをauthorityとして、completed actualからGUI reconstruction procedureをfresh生成し、次を確認した。

```text
Final As-Built Reconstruction = PASS
Missing Actual Node = 0
Invented Node = 0
Wrong Terminal = 0
Wrong Constant = 0
Wrong Type = 0
Wrong Case Behavior = 0
Wrong State Equation = 0
Documentation Ambiguity = 0
Observable Design Drift = 0
```

## 15.5 Human Static Gate

HumanがLabVIEW Editor上で次を確認しPASSした。

```text
H1 Broken Run Arrow = PASS
H2 Coercion Dots = PASS
H3 Use Default If Unwired = PASS
H4 Typedef Linkage = PASS
H5 Connector Pane = PASS
```

---

# 16. Static Acceptance

## 16.1 `CANalyzer_Fault_Type.ctl`

- ordinal 0=`Alive Counter`
- ordinal 1=`Checksum`
- ordinal 2=`Timeout`
- append-only
- Static Acceptance = PASS

## 16.2 `CANalyzer_Fault_Target.ctl`

- 13 items exact
- ordinal / display textが§4.2と一致
- unsupported / evidence未確認targetなし
- append-only
- Static Acceptance = PASS

## 16.3 `CANalyzer_Set_Fault.vi`

- incoming errorはoriginalをpreserveしwriteしない
- support matrix validationがwriteより前
- invalid combinationは`-710119`
- target enum → exact Namespace mapping
- fault enum → exact Variable Name mapping
- `CANalyzer_Value_Type=explicit enum I32`
- `Nurmeric Value=0.0 / 1.0`
- Verify=True固定
- DBL tolerance=0.0固定
- `SysVar Verified?`はWrite `Verified?`のみ
- CAN behavior verifiedと表現しない
- Human Static Gate PASS
- Static Acceptance = PASS

## 16.4 `CANalyzer_Clear_All_Faults.vi`

- incoming errorありでもcleanup実行
- Original Error保存
- operation-side write error in=fresh No Error
- First Cleanup Error sticky-first retention
- full targetでAlive / Checksumを両方attempt
- same-target Alive+Checksum成功時だけTimeout clear
- prerequisite failure時Timeout skip
- Timeout-only targetは直接Timeout clear
- target failure後も他targetをbest effortで継続
- clear value=explicit enum I32 + DBL 0.0
- Verify=True固定
- `Current Target Cleared = Alive Success AND Checksum Success AND Timeout Success`
- `Next All Cleared = Previous All Cleared AND Current Target Cleared`
- `All Cleared?`は必要clear全成功時のみTrue
- final priority Original Error > First Cleanup Error > No Error
- registryなし
- Human Static Gate PASS
- Static Acceptance = PASS

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

Current canonical runtime status：

```text
Runtime / Hardware E2E
= PENDING
```

---

# 18. Frozen Decisions

次はHuman Approval済みFrozen領域であり、今後も別Design Gateなしに無言変更しない。

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

Design Freeze時の承認結果を履歴として保持する。

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
= STATIC CLOSED

RUNTIME / HARDWARE E2E
= PENDING

NEXT
= Runtime / Hardware Validation or downstream TestStand Design Phase
```

---

# 20. Static Implementation Closure Gate

| Gate | Result |
|---|---|
| F1 Typedef implementation | PASS |
| F2 Set Fault implementation | PASS |
| F3 Set Fault As-Built / Drift Gate | PASS |
| F4 Clear All implementation | PASS |
| F5 Clear All As-Built / closure re-review | PASS |
| F6 Combined Final Algorithm-to-Wiring Audit | PASS |
| Final Actual Model | CONFIRMED |
| Final As-Built GUI Reconstruction | PASS |
| Human Static Gate | PASS |
| Broken Run Arrow | PASS |
| Coercion dots | PASS |
| Use Default If Unwired | PASS |
| Typedef linkage | PASS |
| Connector Pane | PASS |
| Observable Design Drift | 0 |
| P0 | 0 |
| P1 | 0 |
| Runtime / Hardware E2E | PENDING |

```text
CANalyzer Fault Injection Public API

STATIC IMPLEMENTATION
= CLOSED

RUNTIME / HARDWARE E2E
= PENDING

TESTSTAND INTEGRATION
= FUTURE PHASE
```
