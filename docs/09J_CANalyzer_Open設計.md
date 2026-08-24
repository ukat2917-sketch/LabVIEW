# 09J. CANalyzer_Open.vi 最終統合設計

**最終整理日：2026-08-24**

> **本章の役割**：`CANalyzer_Open.vi` のProduction向けFinal Integration Design Closureを正本化し、実装完了後のFocused As-Built / Model Check Reviewで照合する設計Baselineを定義する。
>
> `CANalyzer_Open.vi` は `60_CAN\30_Public` に属するSession ID発行前bootstrap Public APIである。既にClosure済みのProcess Detect、Compatibility、Configuration Verify、Measurement Wait、Session Registry等を統合し、成功時だけSession RegistryへActiveX Ref所有権を移管する。
>
> VI作成手順の記述規則は [`00A_LabVIEW実装資料の記述ルール.md`](./00A_LabVIEW実装資料の記述ルール.md) と [`00B_LabVIEW学習型VI設計ルール.md`](./00B_LabVIEW学習型VI設計ルール.md) に従い、一次資料と確認状態は [`00C_一次資料とバージョン基準.md`](./00C_一次資料とバージョン基準.md) に従う。CANalyzer全体のレイヤ構成は [`09_CAN通信の実装.md`](./09_CAN通信の実装.md) を参照する。
>
> 2026-08-24のFinal Integration Design Closure AmendmentおよびImplementation-Blocking Final Closure Spot Checkにより、**P0=0 / P1=0 / READY FOR MANUAL IMPLEMENTATION** と確定した。実機runtimeで未証明の項目は安全側Contractへ固定し、As-Built Reviewでは本章との差分を判定する。

---

# 1. Status

```text
CANalyzer_Open.vi
Design Status              = FINAL / CLOSED
P0 Design Findings         = 0
P1 Design Findings         = 0
Implementation Readiness   = READY FOR MANUAL IMPLEMENTATION
Implementation             = PENDING
As-Built Review            = PENDING
Runtime / Hardware E2E     = PENDING
```

実装完了後は本章をModel Check Reviewの正本とし、P0/P1差分をCloseするまで次工程へ進めない。

---

# 2. 責務

`CANalyzer_Open.vi` はSession ID発行前のbootstrap Public APIとして次を担当する。

1. incoming error guard
2. Public input validation
3. Launch Modeに応じたProcess Detect
4. `Open New Instance?`導出
5. CANalyzer Application Ref取得
6. Application Ownership判定
7. Configuration-independent Compatibility Phase 1
8. optional Configuration Open
9. Configuration Verify
10. Configuration-dependent Compatibility Phase 2
11. Compatibility Policy適用
12. final System Ref取得
13. final Measurement Ref取得
14. current Running取得
15. optional Measurement Start
16. Running=True待機
17. Session State構築
18. Session Registry Create
19. Session ID出力
20. failure時の逆順rollback / cleanup

本VIは通常Session操作用Dispatcherではない。Session ID発行前bootstrap処理であるため、初版では`CANalyzer_Execute_Command.vi`へ載せない。

本VIでは次を行わない。

- 通常SysVar Read / Write
- Batch Read / Write
- Fault Injection
- TestStand変数操作
- persistent Session state保持
- previous Configurationの自動restore

---

# 3. Final Public I/O

## 3.1 Inputs

| Name | Type | Contract |
|---|---|---|
| `Launch Mode` | `CANalyzer_Launch_Mode.ctl` | `Require Existing / Reuse Existing Or Launch / Force New Instance` |
| `Process Name Candidates` | 1D String Array | Process Detectへ渡す候補image name群。Require Existingでは実質必須 |
| `Configuration Path` | Path | Open有無に関係なく必須。Expected Configurationとして使用 |
| `Open Configuration?` | Boolean | Trueなら指定cfgをOpenしてからVerify。Falseでも現在cfgを必ずVerify |
| `Start Measurement?` | Boolean | TrueかつInitial Running=FalseのときだけStart + Wait |
| `Measurement Timeout ms` | U32 | Start=True時だけ`>0`必須。Wait True/rollback Wait Falseのtimeout |
| `Compatibility Policy` | `CANalyzer_Compatibility_Policy.ctl` | Final Compatibility Statusの受入Policy |
| `error in` | error cluster | status=Trueでは副作用なしでpass-through |

### 3.1.1 削除したInput

`Startup Timeout ms` は初版Public I/Oから削除する。Detectは1-shot、Automation Openは同期Wrapperであり、現行Closed designに使用先がないdead inputだからである。

### 3.1.2 Poll Interval

Measurement Poll IntervalはPublicへ公開しない。`CANalyzer_Wait_Measurement_State.vi`へ渡すProduction内部定数を **100 ms** とする。

## 3.2 Outputs

| Name | Type | Success | Failure |
|---|---|---|---|
| `Session ID` | U32 | Registry発行値 `>0` | **0 fixed** |
| `Version String` | String | Compatibility出力 | 取得済みなら保持、未取得なら`""` |
| `Actual Configuration Path` | Path | Verify Actual StringをPath化 | 取得済みなら保持、未取得ならdefault Path |
| `Application Ownership` | `CANalyzer_Application_Ownership.ctl` | 判定値 | 判定済み値を保持、未判定ならUnknown |
| `Measurement Started By LabVIEW?` | Boolean | 今回のOpenでStart Invoke成功ならTrue | rollback後もhistory flagとして保持 |
| `Running?` | Boolean | 最終観測Running | 最後に実観測した値。未観測ならFalse |
| `Compatibility Status` | `CANalyzer_Compatibility_Status.ctl` | Phase 2 final status | 最後に確定したstatus、未判定ならUnknown |
| `error out` | error cluster | No Error | primary Operation Error |

`Measurement Started By LabVIEW?` は現在状態ではなく**今回のOpen処理がStartを実行した履歴**である。`Running?`とは意味を分離する。

---

# 4. Typedef Contract

## 4.1 `CANalyzer_Compatibility_Policy.ctl`

local Projectには2026-08-24時点で同typedef / 同等typedefの実装Evidenceがなかったため、Production contractとして次のEnumを新規固定する。

```text
0 Require Compatible
1 Allow Warning
2 Allow Unknown
```

順番を変更しない。

## 4.2 Compatibility Policy Matrix

| Compatibility Status | Require Compatible | Allow Warning | Allow Unknown |
|---|---:|---:|---:|
| `Compatible` | Accept | Accept | Accept |
| `Compatible With Warning` | Reject | Accept | Accept |
| `Unknown` | Reject | Reject | Accept |
| `Unsupported` | Reject | Reject | Reject |

`Allow Unknown`で受け入れるUnknownは、mandatory capabilityが成功しているUnknownだけである。Phase 1 / Phase 2 mandatory failureをUnknownへ格下げして通さない。

`Unsupported`は全PolicyでRejectし、Compatibility Serviceが返した`-710101`を保持する。

Phase 2自体は成功したがPolicyがWarning / Unknownを拒否した場合だけ`-710117 Compatibility Policy Rejected`を生成する。

---

# 5. Public Input Validation

## 5.1 Incoming Error

`error in.status=True`の場合は次で終了する。

```text
Session ID                         = 0
Version String                     = ""
Actual Configuration Path          = default Path
Application Ownership              = Unknown
Measurement Started By LabVIEW?    = False
Running?                           = False
Compatibility Status               = Unknown
error out                          = original error in
```

この経路ではProcess Detect、ActiveX、Configuration、Compatibility、Registryを一切実行しない。

## 5.2 Configuration Path

`Configuration Path`は`Open Configuration?`に関係なく必須。

```text
Configuration Path
→ Path To String
→ Trim Whitespace
→ Empty String/Path?
```

Trim後empty / whitespace-onlyなら：

```text
status = True
code   = -710116
source = CANalyzer_Open.vi / Invalid Expected Configuration Path
```

ActiveX side effectへ進まない。

初版ではrelative path検出、file existence検査、extension検査、`.`/`..`解決、mapped drive / UNC変換、canonicalizationをOpen側へ追加しない。caller contractはfully-qualified absolute Windows configuration pathとする。

## 5.3 Measurement Timeout

```text
Start Measurement? = True
AND Measurement Timeout ms = 0
```

の場合だけinvalid inputとする。

```text
status = True
code   = -710118
source = CANalyzer_Open.vi / Invalid Measurement Timeout
```

Start/Waitは呼ばない。

`Start Measurement?=False`なら`Measurement Timeout ms=0`を許可する。

---

# 6. Final Bootstrap Sequence

```text
error in guard
↓
input validation
↓
Launch Mode別 Process Detect
↓
Launch Mode guard
↓
derive Open New Instance?
↓
CAN_AX_Open_Application.vi
↓
必要な場合だけPost Detect
↓
resolve Application Ownership
↓
CANalyzer_Check_Compatibility.vi Phase 1
↓
Phase 1 mandatory pass gate
↓
if Open Configuration? = True:
    CAN_AX_Open_Configuration.vi
↓
CANalyzer_Verify_Configuration.vi   ← always
↓
Verify PASS gate
↓
CANalyzer_Check_Compatibility.vi Phase 2
↓
Phase 2 mandatory pass gate
↓
Compatibility Policy
↓
CAN_AX_Get_System.vi
↓
CAN_AX_Get_Measurement.vi
↓
CAN_AX_Get_Measurement_Running.vi
↓
if Start Measurement? = True and Running=False:
    CAN_AX_Start_Measurement.vi
    Measurement Started By LabVIEW? = True
    CANalyzer_Wait_Measurement_State.vi(Expected=True)
↓
build CANalyzer_Session_State.ctl
↓
CANalyzer_Session_Registry.vi Action=Create
↓
Session ID Out
↓
success
```

**順序固定：Phase 1 → optional Config Open → Verify → Phase 2 → Policy。** Verify前にPhase 2を実行しない。

Version Stringは`CANalyzer_Check_Compatibility.vi`のoutputだけを使用し、Open側でVersion wrapperを二重実装しない。

---

# 7. Launch Mode / Process Detection / Ownership

## 7.1 `Open New Instance?`

| Launch Mode | `Open New Instance?` |
|---|---:|
| Require Existing | False |
| Reuse Existing Or Launch | False |
| Force New Instance | True |

## 7.2 Detect Execution Matrix

| Launch Mode | Pre Detect | Post Detect | Final Ownership Logic |
|---|---|---|---|
| Require Existing | **Required** | Skip | Pre Found=True + Open success → `External` |
| Reuse Existing Or Launch | **Run** | Pre Detect success + Found=Falseのときだけ | Pre Found=True → `External`; Pre False + Post True → `LabVIEW`; Post False/error → `Unknown` |
| Force New Instance | Skip | Skip | Open successでも初版は`Unknown` |

### Require Existing

Pre Detect errorはfatalで、元Detect errorをそのまま返す。

Pre Detect成功かつ`Found?=False`なら：

```text
status = True
code   = -710109
source = CANalyzer_Open.vi / Required Existing Process Not Found
```

Automation Openを呼ばない。

### Reuse Existing Or Launch

- Pre Detect成功 + Found=True → Open後`External`、Post Detect不要。
- Pre Detect成功 + Found=False → Automation Open後にPost Detect。
- Post Found=True → `LabVIEW`。
- Post Found=False / Post Detect error → `Unknown`。Post Detect errorはadvisoryとして隔離しOpenを継続。
- Pre Detect error → advisory。Automation Openを継続し、Ownership=`Unknown`。Post Detectは行わない。

advisory Detect errorをAutomation Openのerror chainへ流してOpenをskipさせない。

### Force New Instance

Process DetectをOwnership判定へ使用しない。Pre/Postともskipし、Automation Open成功でも初版Ownershipは`Unknown`とする。runtime evidence取得後にのみ`LabVIEW`への昇格を検討する。

---

# 8. Automation Open Contract

使用：`CAN_AX_Open_Application.vi`

Automation Open failureはWrapper / ActiveXの元errorを保持する。`-710100`へ強制normalizeしない。

Application RefはRegistry Create成功前はOpenの管理下にある。Registry Create成功後にSessionへ所有権を移す。

---

# 9. Compatibility Phase 1

`CANalyzer_Check_Compatibility.vi`を次で呼ぶ。

```text
Enable Configuration-Dependent Probe? = False
```

Phase 1はConfiguration-independent mandatory capabilityだけを確認する。

Mandatory failure：

```text
Compatibility Status = Unsupported
error = -710101
```

Configuration Openへ進まずrollbackする。

Version取得不可だけでmandatory probeが成功している場合は`Compatibility Status=Unknown / Capability Probe Passed?=True`として次へ進む。

---

# 10. Configuration Contract

## 10.1 Path Type Boundary

| Boundary | Type |
|---|---|
| Public `Configuration Path` | Path |
| Session State `Configuration Path` | Path |
| `CAN_AX_Open_Configuration.vi` | String |
| `CANalyzer_Verify_Configuration.vi` Expected / Actual | String |
| Public `Actual Configuration Path` | Path |

Public / Session StateはPathを維持し、Open内部でWrapper / Service呼出し直前にStringへ変換する。

## 10.2 Optional Configuration Open

`Open Configuration?=True`の場合だけ`CAN_AX_Open_Configuration.vi`を呼ぶ。

Production固定値：

| Wrapper Input | Value | State |
|---|---:|---|
| `AutoSave?` | **False** | argument name / wrapper pass-through確認済み。既存cfgを勝手に保存しないProduction方針 |
| `Prompt User?` | **False** | argument name / wrapper pass-through確認済み。unattended bootstrapでmodal promptを出さない方針 |

2026-08-24時点ではType Library / local Helpの引数説明文そのものは保存Evidence化できていない。As-Built / runtime reviewではこの点をP2保守Evidenceとして補足してよいが、Production constantは上記で固定する。

Open failure時：

```text
Configuration Opened By LabVIEW? = False
error = original wrapper error
```

Open success直後：

```text
Configuration Opened By LabVIEW? = True
```

後段Verify等が失敗しても、この内部diagnostic flagはTrueのままとする。

## 10.3 Verify Always

`Open Configuration?`に関係なく`CANalyzer_Verify_Configuration.vi`を必ず実行する。

Verify failure (`-710103`, `-710116`, wrapper error) ではPhase 2へ進まない。

Verify成功時のraw Actual Stringを`String To Path`でPath化し、Public `Actual Configuration Path`とSession State `Configuration Path`へ使用する。

## 10.4 Documented Limitation

**NO AUTOMATIC CONFIGURATION ROLLBACK**

Configuration Open成功後にVerify / Phase 2 / Policy / final Ref / Measurement / Registryで失敗してもprevious Configurationへ自動restoreしない。安全なprevious configuration snapshot / restore contractが存在しないためである。

Application rollbackとは別責務として扱う。

---

# 11. Compatibility Phase 2 / Policy

Phase 2はVerify PASS後だけ実行する。

```text
Enable Configuration-Dependent Probe? = True
```

Mandatory failureは`Unsupported / -710101`としてrollbackする。

Phase 2成功後だけPolicyを適用する。

Policy拒否時：

```text
status = True
code   = -710117
source = CANalyzer_Open.vi / Compatibility Policy Rejected
         Policy=<policy>
         Status=<status>
         Version=<version>
```

`Unsupported / -710101`を`-710117`へ変換しない。

---

# 12. Final Session Ref Acquisition

Compatibility Service内部で取得したSystem / Measurement等のRefはtemporaryで内部Close済み。Session Registryへ保存するRefとして再利用しない。

Policy PASS後に次を新規取得する。

```text
CAN_AX_Get_System.vi
↓
final System Ref
↓
CAN_AX_Get_Measurement.vi
↓
final Measurement Ref
```

System取得failureではApplicationをrollback。

Measurement取得failureではSystem → Applicationの順にrollbackする。

---

# 13. Measurement Contract

## 13.1 Initial Running

final Measurement Ref取得後に`CAN_AX_Get_Measurement_Running.vi`でInitial Runningを取得する。

`Start Measurement?=False`：

- Startしない
- `Measurement Started By LabVIEW?=False`
- Running=FalseでもOpen成功を許可
- `Running?=Initial Running`

`Start Measurement?=True`かつInitial Running=True：

- Startしない
- `Measurement Started By LabVIEW?=False`
- `Running?=True`

## 13.2 Start

`Start Measurement?=True`かつInitial Running=Falseの場合：

```text
CAN_AX_Start_Measurement.vi
↓ success
Measurement Started By LabVIEW? = True
↓
CANalyzer_Wait_Measurement_State.vi
Expected Running? = True
Timeout ms         = Measurement Timeout ms
Poll Interval ms   = 100
```

`Measurement Started By LabVIEW?`はWait成功後ではなく**Start Invoke成功直後**にTrueとする。これによりWait timeoutでもrollback Stop対象と判定できる。

Waitの`Actual Running?`をPublic `Running?`へ反映する。

---

# 14. Session State Mapping

Registry Create直前に13 fieldsを完成する。

| Session Field | Source |
|---|---|
| `Session ID` | 0。Registry Createが発行IDへ上書き |
| `Application Ref` | final Application Ref |
| `System Ref` | final System Ref |
| `Measurement Ref` | final Measurement Ref |
| `Version String` | Check Compatibility output |
| `Configuration Path` | verified Actual Path |
| `Launch Mode` | Public input |
| `Application Ownership` | resolved ownership |
| `Configuration Opened By LabVIEW?` | actual Configuration Open result |
| `Measurement Started By LabVIEW?` | actual Start Invoke result |
| `Cached Connected?` | True |
| `Cached Measuring?` | final observed Running |
| `Compatibility Status` | Phase 2 final status |

`Cached Connected? / Cached Measuring?`は後続runtimeのsource of truthではなくcacheである。

---

# 15. Registry Create / Ownership Transfer

`CANalyzer_Session_Registry.vi`：

```text
Action       = Create
Session ID   = 0 / ignored
Session In   = completed Session State
error in     = no prior error
```

Success時は`Session ID Out`をPublic `Session ID`へ返す。

Registry Create成功をRef ownership transfer pointとする。

```text
Before Registry Create:
Application / System / Measurement Ref owner = CANalyzer_Open.vi

After Registry Create success:
Application / System / Measurement Ref owner = Session / Registry lifecycle
```

Open success pathではRefをCloseしない。

Registry Create failureではSessionは成立していないため、Openが全Ref / side effect rollback責務を持つ。

---

# 16. Failure Rollback

基本原則：取得済みresourceだけを逆順cleanupする。

```text
Original Operation Errorを保持
↓
if Measurement Started By LabVIEW? = True:
    CAN_AX_Stop_Measurement.vi
    if Stop success:
        CANalyzer_Wait_Measurement_State.vi
            Expected Running? = False
            Timeout ms         = Measurement Timeout ms
            Poll Interval ms   = 100
↓
if Measurement Ref acquired:
    Close Measurement Ref
↓
if System Ref acquired:
    Close System Ref
↓
if Application Ownership = LabVIEW:
    CAN_AX_Quit_Application.vi
↓
if Application Ref acquired:
    Close Application Ref
↓
Final Error Select
Operation Error > Cleanup Error
```

Initial Running=TrueだったMeasurementはOpen失敗時にもStopしない。Stop判定は現在Runningではなく`Measurement Started By LabVIEW?`だけを使う。

### 16.1 Rollback Running

`Running?`は最後に実際に観測できたRunning値。

| Rollback状態 | `Running?` |
|---|---|
| Stop success + Wait False success | False |
| rollback中にTrueを最後に観測 | True |
| rollbackで再観測不能 | それ以前の最後の観測値 |
| 一度も観測なし | False |

### 16.2 Application Quit / Close

| Ownership | Quit | Application Ref Close |
|---|---|---|
| LabVIEW | Attempt | Always attempt after Quit |
| External | Do not call | Attempt |
| Unknown | Do not call | Attempt |

Quit failureでもApplication Ref Closeをskipしない。

### 16.3 Error Priority

```text
Operation Error > Cleanup Error
```

最初のOperation failureをprimaryに固定する。Stop / rollback Wait / Close / Quit等のCleanup errorでprimary codeを上書きしない。

Operation Errorがないcleanup-only failureではCleanup Errorをprimaryとして返してよい。

---

# 17. Error Code Contract

本Open設計で重要なcodeは次のとおり。

| Code | Meaning | Open Contract |
|---:|---|---|
| `-710101` | Required Capability Missing | Compatibility mandatory failure。元Service errorを保持 |
| `-710103` | Configuration Mismatch | Verifyからpass-through |
| `-710104` | Measurement State Timeout | Waitからpass-through |
| `-710109` | Required Existing CANalyzer Process Not Found | Require Existing + Detect成功 + Found=False |
| `-710116` | Invalid Expected Configuration Path | Open input validation / Verify contract |
| `-710117` | Compatibility Policy Rejected | Phase 2 success後にPolicyがWarning / Unknownを拒否 |
| `-710118` | Invalid Measurement Timeout | Start=True AND Timeout=0 |

`-710109 / -710117 / -710118`は2026-08-24 local Project search evidence上、既存使用なしとして採用した。

Automation Open failureは元Wrapper / ActiveX errorを保持し、`-710100`へ強制normalizeしない。

Detect mechanism failure (`-710114 / -710115`等) を`-710109`へ変換しない。

---

# 18. Serialization Contract

`CANalyzer_Open.vi`は**Non-reentrant**とする。

理由：Session作成前bootstrap ActiveX操作をOpen単位で直列化するため。

初版では十分なOpen API内serializationとするが、他VIが同じCOM/Applicationへ同時アクセスするsystem-wide競合まではOpenのNon-reentrantだけで保証しない。

---

# 19. Reference Ownership Baseline

| Resource | Acquisition | Owner before Registry | Owner after Registry | Failure Cleanup |
|---|---|---|---|---|
| Application Ref | `CAN_AX_Open_Application.vi` | Open | Session | conditional Quit + Close |
| Configuration temp Ref | Verify internal | Verify | none | Verify internal |
| Compatibility temp refs | Check Compatibility internal | Check Compatibility | none | Service internal |
| final System Ref | `CAN_AX_Get_System.vi` | Open | Session | Close |
| final Measurement Ref | `CAN_AX_Get_Measurement.vi` | Open | Session | Stop if Open-started, then Close |

Application `Quit`とApplication Ref `Close Reference`を混同しない。

---

# 20. Side Effect Ownership Baseline

| Side Effect | Ownership / Flag | Rollback Contract |
|---|---|---|
| Application launch / attach | `Application Ownership` | `LabVIEW`だけQuit候補。External / UnknownはQuit禁止 |
| Configuration Open | `Configuration Opened By LabVIEW?` | previous cfg restoreなし。Documented Limitation |
| Measurement Start | `Measurement Started By LabVIEW?` | TrueのときだけStop + Wait False |

---

# 21. Static Acceptance Baseline

実装後のModel Check Reviewでは最低限以下を追跡する。

| Case | Expected |
|---|---|
| Incoming error | 副作用なし、Session ID=0、original error |
| Empty / whitespace-only Configuration Path | `-710116`、ActiveX side effectなし |
| Start=True + Timeout=0 | `-710118`、Start/Waitなし |
| Start=False + Timeout=0 | Accept |
| Require Existing + Detect Found=False | `-710109`、Automation Openなし |
| Require Existing + Found=True + Open success | Ownership=External、Post Detect skip |
| Reuse + Pre Found=True | Ownership=External、Post Detect skip |
| Reuse + Pre Found=False + Post Found=True | Ownership=LabVIEW |
| Reuse + Post Detect failure | Ownership=Unknown、Open継続 |
| Reuse + Pre Detect failure | advisory、Ownership=Unknown、Open継続 |
| Force New + Open success | Ownership=Unknown |
| Automation Open failure | Sessionなし、元Wrapper error primary |
| Phase 1 mandatory failure | `Unsupported / -710101`、Configへ進まない |
| Phase 1 Version unavailable + mandatory pass | 継続可能 |
| Open Configuration=True | `AutoSave=False / Prompt User=False`、Open後必ずVerify |
| Open Configuration=False | Openしないが現在cfgを必ずVerify |
| Verify mismatch | `-710103`、Phase 2へ進まない |
| Phase 2 mandatory failure | `Unsupported / -710101` |
| Compatible + Require Compatible | Accept |
| Warning + Require Compatible | `-710117` |
| Warning + Allow Warning | Accept |
| Unknown + Allow Warning | `-710117` |
| Unknown + Allow Unknown + mandatory probe pass | Accept |
| Unsupported + any policy | Reject、`-710101`保持 |
| Get final System failure | Application rollback |
| Get final Measurement failure | System → Application rollback |
| Initial Running=True + Start=True | Startしない、Started=False |
| Initial Running=False + Start=False | Running=FalseでもOpen成功可 |
| Start success + Wait True success | Started=True、Running=True |
| Start success + Wait True timeout | `-710104` primary、Started=True、rollback Stop + Wait False |
| rollback Stop + Wait False success | Running=False |
| Registry Create failure after Start | Session ID=0、Stop/Wait False → Close Measurement → Close System → conditional Quit → Close App |
| External failure rollback | Quit禁止、App Ref Close |
| Unknown failure rollback | Quit禁止、App Ref Close |
| LabVIEW failure rollback | Quit attempt、App Ref Close |
| Quit failure | App Ref Closeを引き続きattempt |
| Operation + Cleanup failure | Operation Error primary |

---

# 22. Model Check Review Gate

実装完了後のFocused As-Built / Model Check Reviewでは、実VIのFront Panel、Connector Pane、Block Diagram、SubVI、Case Structure、error wire、ref wire、constants、VI PropertiesをREAD ONLYで照合する。

## 22.1 P0

- Verify前にPhase 2を実行
- UnsupportedをPolicyでaccept
- Registry Create前のApplication/System/Measurement Ref leak
- Registry Create failure時Ref leak
- External / Unknown ApplicationをQuit
- Initial Running=TrueだったMeasurementをrollback Stop
- Start後Wait failureでOpen-started Measurementを放置
- Operation ErrorをCleanup Errorで上書き
- failureなのにRegistry Sessionが残る
- Session ID=0でsuccess扱い
- Application/System/Measurement ownership transferが不明
- Broken Run Arrow confirmed

## 22.2 P1

- Public I/Oが本章と不一致
- `Startup Timeout ms`が残る
- Poll IntervalをPublic input化、または100 ms contractと不一致
- Configuration PathのPath/String境界不一致
- empty Configuration Pathで`-710116`にならない
- Start=True + Timeout=0で`-710118`にならない
- Require Existing + Found=Falseで`-710109`にならない、またはAutomation Openする
- Detect fatal/advisory policy不一致
- Launch Mode / Ownership matrix不一致
- Phase 1 → optional Config Open → Verify → Phase 2順序不一致
- Configuration Openで`AutoSave=False / Prompt User=False`になっていない
- Open Configuration?=FalseでVerifyをskip
- Compatibility Policy enum order / matrix不一致
- Policy Rejectが`-710117`でない
- Start success直後にStarted flagをTrueにしない
- rollback Stop + Wait Falseを行わない
- Failure diagnostic output semantics不一致
- Session State 13 fields mapping不一致
- Registry Create成功前にRef ownershipを放棄
- Operation Error > Cleanup Error不一致

## 22.3 P2

- Type Libraryの`autoSave / promptUser`説明文Evidence未保存
- source string formatting統一
- diagram readability / cosmetic labels
- Force New Ownershipの将来runtime昇格Evidence

Closure条件：

```text
P0 = 0
P1 = 0
Functional Design Alignment = PASS
Broken Run Arrow = NO
```

---

# 23. Documented Limitations / Runtime Follow-up

1. `Force New Instance`成功時も初版Ownership=`Unknown`。runtime proof取得後だけLabVIEWへの昇格を検討する。
2. Configuration Open後のprevious cfg自動restoreは行わない。
3. `autoSave / promptUser`はwrapper argument名とProduction方針を根拠にFalse固定。Type Library / local Help説明文のEvidence保存はP2 follow-up。
4. Open Non-reentrantはOpen API内bootstrapを直列化するが、system-wide ActiveX serializationを単独で保証しない。
5. 実機CANalyzerを使用したruntime/hardware E2EはStatic As-Built Reviewとは別工程で確認する。

---

# 24. Review Baseline Summary

```text
CANalyzer_Open.vi
Final Design Baseline = 09J_CANalyzer_Open設計.md
Design                = FINAL / CLOSED
Implementation        = PENDING
As-Built Review       = PENDING
P0                     = 0
P1                     = 0
Readiness              = READY FOR MANUAL IMPLEMENTATION
```

実装完了後にReview Promptを作成する際は、本章のI/O、sequence、ownership、error code、rollback、Static Acceptance、P0/P1 gateをそのまま照合項目として使用する。
