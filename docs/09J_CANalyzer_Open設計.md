# 09J. CANalyzer_Open.vi 最終設計 / As-Built Baseline

**最終整理日：2026-08-26**

> **本章の役割**：`CANalyzer_Open.vi` のFinal semantic contractとAs-Built closure状態を正本化する。
>
> GUI上の具体的な再構築手順は [`09JA_CANalyzer_Open実装手順.md`](./09JA_CANalyzer_Open実装手順.md) を正とし、本章へ配線手順を重複させない。
>
> VI作成資料の共通規則は [`00A_LabVIEW実装資料の記述ルール.md`](./00A_LabVIEW実装資料の記述ルール.md)、設計理由は [`00B_LabVIEW学習型VI設計ルール.md`](./00B_LabVIEW学習型VI設計ルール.md)、一次資料の優先順位は [`00C_一次資料とバージョン基準.md`](./00C_一次資料とバージョン基準.md) に従う。

---

## Status

```text
CANalyzer_Open.vi
Design Status              = FINAL / CLOSED
Implementation             = COMPLETE
Static Model Check         = CLOSED
Human Model Check          = CLOSED
P0                         = 0
P1                         = 0
Runtime / Hardware E2E     = PENDING
```

Human確認済み：

- VI Execution Property = Non-reentrant
- Broken Run Arrow = 問題なし
- `CANalyzer_Compatibility_Policy.ctl` direct確認 = PASS

---

## 責務

`CANalyzer_Open.vi` は `60_CAN\30_Public` に属するSession ID発行前bootstrap Public API。

担当：

- incoming error guard
- Public input validation
- Process Detect / Automation Open
- Application Ownership解決
- Compatibility Phase 1
- optional Configuration Open
- Configuration Verify
- Compatibility Phase 2
- Compatibility Policy適用
- final System / Measurement Ref取得
- Initial Running読出し
- optional Measurement Start / Wait
- Session State構築
- Registry Create
- Registry成功前failureのrollback / cleanup

担当しない：

- normal SysVar Read / Write
- Batch
- Fault Injection
- TestStand変数操作
- previous Configurationの自動restore
- persistent Session state保持

---

## Final Public I/O

### Inputs

| Name | Type | Contract |
|---|---|---|
| `Launch Mode` | `CANalyzer_Launch_Mode.ctl` | Require Existing / Reuse Existing Or Launch / Force New Instance |
| `Process Name Candidates` | 1D String Array | Process Detect候補 |
| `Configuration Path` | Path | Open有無に関係なく必須 |
| `Open Configuration?` | Boolean | Trueなら指定cfgをOpenしてVerify |
| `Start Measurement?` | Boolean | TrueかつInitial Running=FalseでStart |
| `Measurement Timeout ms` | U32 | Start=True時だけ>0必須 |
| `Compatibility Policy` | `CANalyzer_Compatibility_Policy.ctl` | Phase2 statusの受入Policy |
| `error in` | error cluster | status=Trueでは全side effect bypass |

`Startup Timeout ms`は存在しない。

Measurement Poll IntervalはPublicへ出さずProduction内部定数 **100 ms**。

### Outputs

| Name | Type | Contract |
|---|---|---|
| `Session ID` | U32 | success=`>0`、failure=`0` |
| `Version String` | String | Phase2 output。failureでも取得済みなら保持 |
| `Actual Configuration Path` | Path | Verify actual path |
| `Application Ownership` | `CANalyzer_Application_Ownership.ctl` | resolved ownership |
| `Measurement Started By LabVIEW?` | Boolean | Start Invoke成功履歴 |
| `Running?` | Boolean | last observed Running |
| `Compatibility Status` | `CANalyzer_Compatibility_Status.ctl` | Phase2 final status |
| `error out` | error cluster | final primary error |

---

## Public Input Validation

incoming errorが最外側。

### Configuration Path

```text
Configuration Path
→ Path To String
→ Trim Whitespace
→ Empty String/Path?
```

trim後emptyなら：

```text
status = True
code   = -710116
source = CANalyzer_Open.vi / Invalid Expected Configuration Path
```

ActiveX side effectへ進まない。

### Measurement Timeout

```text
Start Measurement? = True
AND Measurement Timeout ms = 0
```

だけinvalid。

```text
status = True
code   = -710118
source = CANalyzer_Open.vi / Invalid Measurement Timeout
```

これもActiveX side effectより前に判定する。Start=FalseならTimeout=0を許可する。

---

## Final Bootstrap Sequence

```text
Incoming Error Guard
↓
Input Validation
↓
Launch Mode / Detect
↓
Automation Open
↓
Ownership
↓
Compatibility Phase 1
↓
Optional Configuration Open
↓
Configuration Verify
↓
Compatibility Phase 2
↓
Compatibility Policy
↓
Final System Ref
↓
Final Measurement Ref
↓
Initial Running
↓
Optional Start / Wait True
↓
Session State
↓
Registry Create
```

順序固定：

```text
Phase 1
→ optional Configuration Open
→ Verify
→ Phase 2
→ Policy
```

---

## Launch / Detect / Ownership

| Launch Mode | Pre Detect | Post Detect | Open New Instance? | Final Ownership |
|---|---|---|---:|---|
| Require Existing | Required | Skip | False | Found=True + Open success → External |
| Reuse Existing Or Launch | Run | Pre success + Found=False + Open successのみ | False | Pre Found=True→External、Post Found=True→LabVIEW、ambiguous→Unknown |
| Force New Instance | Skip | Skip | True | **Unknown** |

Require Existing：

- Pre Detect errorはfatalで元error保持。
- Detect success + Found=FalseはAutomation Openせず`-710109`。
- Found=True + Open successはExternal。

Reuse：

- Pre Detect errorはadvisory。Open継続、Ownership=Unknown、Post Detect skip。
- Pre Found=TrueはExternal。
- Pre Found=False + Open success後だけPost Detect。
- Post Found=TrueはLabVIEW。
- Post Found=False / Post Detect errorはUnknown。
- Post Detect errorはadvisoryでOperation Errorへ昇格しない。

Force New：

- Detectしない。
- `Open New Instance?=True`。
- static contractではOwnership=Unknown。
- runtime evidenceなしにLabVIEWへ昇格しない。

Automation Open failureは元wrapper / ActiveX errorを保持し、`-710100`へ強制normalizeしない。

---

## Compatibility Phase 1

`CANalyzer_Check_Compatibility.vi`：

```text
Enable Configuration-Dependent Probe? = False
```

mandatory fail：

```text
Compatibility Status = Unsupported
error = -710101
```

Version取得不可だけでmandatory capabilityがpassしている場合はUnknownとして後段へ進める。

---

## Configuration Contract

Public / Session StateではPathを維持し、Wrapper / Verify境界だけStringへ変換。

`Open Configuration?=True`：

```text
AutoSave?    = False
Prompt User? = False
```

`Configuration Opened By LabVIEW?` は**current invocationのOpen成功履歴**。

| Condition | History |
|---|---|
| Open Configuration?=False | False |
| True + Open success | True |
| True + Open failure | False |

previous invocation stateを使用しない。

`Open Configuration?=False`でもVerifyを必ず実行する。

**NO AUTOMATIC CONFIGURATION ROLLBACK**。Open success後に後段failureしてもprevious cfgへrestoreしない。

---

## Compatibility Phase 2

Verify PASS後だけ実行。

```text
Enable Configuration-Dependent Probe? = True
```

Production Probe：

| Item | Value |
|---|---|
| Namespace | `ID03AD5D62` |
| Variable | `CORE_SVS_OPE_MODE_COM` |
| Expected Type | `I32` |

3 Policy branchで同一contract。

---

## Compatibility Policy

`CANalyzer_Compatibility_Policy.ctl` enum order：

```text
0 Require Compatible
1 Allow Warning
2 Allow Unknown
```

| Status | Require Compatible | Allow Warning | Allow Unknown |
|---|---:|---:|---:|
| Compatible | Accept | Accept | Accept |
| Compatible With Warning | Reject | Accept | Accept |
| Unknown | Reject | Reject | Accept |
| Unsupported | Reject | Reject | Reject |

Unsupportedは`-710101`保持。

Phase2成功後のWarning / Unknown rejectだけ：

```text
code = -710117
source = CANalyzer_Open.vi / Compatibility Policy Rejected
         Policy=<policy>
         Status=<status>
         Version=<version>
```

---

## Final Session Refs

Policy ACCEPT後だけ：

```text
CAN_AX_Get_System.vi
→ final System Ref
→ CAN_AX_Get_Measurement.vi
→ final Measurement Ref
```

Compatibility内部temporary RefはSession Refへ再利用しない。

Registry Create成功前：

```text
Ref owner = CANalyzer_Open.vi
```

Registry Create成功後：

```text
Ref owner = Session / Registry lifecycle
```

---

## Measurement Contract

Final Measurement Ref取得後、Start decisionより前にInitial Runningを読む。

| Start? | Initial Running | Action | Started history | Running |
|---|---|---|---|---|
| False | False | No Start | False | False |
| False | True | No Start | False | True |
| True | True | No Start | False | True |
| True | False | Start | Start成功直後True | Wait Actual Running |

Wait True：

```text
Expected Running? = True
Timeout ms         = Measurement Timeout ms
Poll Interval ms   = 100
```

`Measurement Started By LabVIEW?`はcurrent stateではなくhistory。

`Running?`はlast observed state。

---

## Session State Mapping

Registry Create直前の13 fields：

| Session Field | Source |
|---|---|
| Session ID | 0 |
| Application Ref | final Application Ref |
| System Ref | final System Ref |
| Measurement Ref | final Measurement Ref |
| Version String | Phase2 Version |
| Configuration Path | verified Actual Path |
| Launch Mode | input |
| Application Ownership | resolved ownership |
| Configuration Opened By LabVIEW? | current invocation open history |
| Measurement Started By LabVIEW? | Start Invoke history |
| Cached Connected? | True |
| Cached Measuring? | final observed Running |
| Compatibility Status | Phase2 final status |

Cached statusはsource-of-truthではない。

---

## Registry Create

```text
Action = Create
Session ID = 0
Session In = completed Session State
```

成功：

- Public Session ID=`Session ID Out > 0`
- Ref ownershipをSessionへtransfer
- Open success pathでRefをCloseしない

failure：

- Public Session ID=0
- Openがrollback owner

---

## Failure Rollback

```text
Original Operation Errorを保持
↓
if Measurement Started By LabVIEW?:
    Stop
    if Stop success:
        Wait False
↓
if Measurement Ref acquired:
    Close Measurement Ref
↓
if System Ref acquired:
    Close System Ref
↓
if Ownership = LabVIEW:
    Quit
↓
if Application Ref acquired:
    Close Application Ref
↓
Operation Error > Cleanup Error
```

Stop判定はStarted historyだけ。Initial Running=Trueだったpreexisting MeasurementはStopしない。

Wait False：

```text
Expected Running? = False
Timeout ms         = Measurement Timeout ms
Poll Interval ms   = 100
```

Running history：

| Rollback | Running |
|---|---|
| Wait False success | False |
| Wait False failure | previous last observed Running |
| Stop failure | previous last observed Running |

Stop errorをRunning stateとして扱わない。

---

## Cleanup Error Contract

cleanup actionはclean error inputで実行し、後続cleanupを止めない。

**First Cleanup Error Wins**：

```text
Previous Cleanup Errorがある
→ そのerrorを保持

Previous Cleanup Errorがない
→ Current Cleanup Errorを採用
```

Final error：

```text
Operation Error > Cleanup Error
```

| Operation | Cleanup | Final |
|---|---|---|
| OK | OK | OK |
| OK | Error | Cleanup |
| Error | OK | Operation |
| Error | Error | Operation |

---

## Application Quit Contract

| Ownership | Quit | Application Ref Close |
|---|---|---|
| LabVIEW | Attempt | Attempt |
| External | Do not call | Attempt |
| Unknown | Do not call | Attempt |

Quit failureでもApplication Ref Closeをskipしない。

Force New InstanceもOwnership=Unknownのため、runtime evidenceで契約変更するまでQuitしない。

---

## Failure Output Semantics

| Output | Failure |
|---|---|
| Session ID | 0 fixed |
| Version String | acquiredなら保持 |
| Actual Configuration Path | acquiredなら保持 |
| Application Ownership | resolvedなら保持 |
| Measurement Started By LabVIEW? | historyを保持 |
| Running? | last observed value |
| Compatibility Status | last determined status |
| error out | primary Operation Error |

incoming error / pre-side-effect input validation failureではsafe default。

---

## Error Code Contract

| Code | Meaning | Origin |
|---:|---|---|
| -710101 | Required Capability Missing | Compatibility |
| -710103 | Configuration Mismatch | Verify |
| -710104 | Measurement State Timeout | Wait |
| -710109 | Required Existing CANalyzer Process Not Found | Open |
| -710116 | Invalid Expected Configuration Path | Open validation / Verify |
| -710117 | Compatibility Policy Rejected | Open |
| -710118 | Invalid Measurement Timeout | Open validation |

---

## Semantic / Mathematical Equivalence

As-Built reviewではnode形状ではなくobservable semanticsを判定する。

確認済みのsimplification：

### Configuration Open history

previous-state Feedback Nodeを使用せず、current invocationのOpen success BooleanをSession Stateへ直接供給する。

### Rollback Running selector

Stop成功branch内では`StopError=False`が構造的に保証される。

```text
StopError OR WaitError
= False OR WaitError
= WaitError
```

したがってWaitError単独selectorはFinal Contractと等価。

---

## As-Built Closure Evidence

| Item | State |
|---|---|
| Final Full As-Built / Model Check | PASS WITH NON-BLOCKING FINDINGS |
| P0 | 0 |
| P1 | 0 |
| Static Model Check | CLOSED |
| Human Non-reentrant Check | PASS |
| Human Broken Run Arrow Check | PASS |
| Human Typedef Direct Check | PASS |

Non-blocking P2：

- debug用`TEMP_TEST_LABEL`等が残る場合はcleanup対象だがContract外。
- `-710103 / -710104`の詳細生成は各Serviceの正本資料を参照する。

---

## Runtime / Hardware E2E

**PENDING**。

Static / Human Closureはruntime成功を意味しない。

Runtimeで確認する主項目：

- Launch Mode 3種の実挙動
- Force New InstanceのProcess / ownership evidence
- actual Configuration Open / Verify
- Production Phase2 Probe
- Measurement Start / Stop / Wait
- Registry lifecycle
- rollback cleanup
- Application Quit / Ref Close

---

## Source / Version / State

| Item | Value |
|---|---|
| Source | Current local VI / existing wrappers and services / registered CANalyzer Type Library / Final As-Built review |
| Environment | LabVIEW 2026 Q3 64-bit / TestStand 2026 Q3 64-bit |
| State | FINAL / AS-BUILT CLOSED / Runtime E2E PENDING |
| Manual Procedure | [`09JA_CANalyzer_Open実装手順.md`](./09JA_CANalyzer_Open実装手順.md) |
