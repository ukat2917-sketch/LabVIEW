# 09M. CANalyzer_Stop / Execute_Command Stop Measurement 最終設計正本

**Status:** FINAL DESIGN / FROZEN / IMPLEMENTATION PENDING  
**Design Review:** P0=0 / P1=0  
**Observable Design Ambiguity:** 0  
**GUI Reconstruction Procedure:** PENDING  
**`CANalyzer_Execute_Command.vi / Stop Measurement`:** NOT IMPLEMENTED  
**Public `CANalyzer_Stop.vi`:** NOT IMPLEMENTED  
**Runtime / Hardware E2E:** PENDING

> 本書を `CANalyzer_Stop.vi` と `CANalyzer_Execute_Command.vi / Stop Measurement` の設計、契約、状態遷移、error priority、Static Acceptanceの単一正本とする。  
> Production StopのPublic I/O、Command拡張、explicit stop authority、observation validity、ownership/cache更新、failure policyは本書を優先する。  
> Session Registry契約は `09B_CANalyzer_Session_Registry設計.md`、Close cleanup契約は `09K_CANalyzer_Close設計.md`、Start ownership契約は `09L_CANalyzer_Start設計.md` を参照する。

---

# 0. 目的

既存Sessionに紐づくCANalyzer Measurementを、Productionの直列化境界を守りながら明示的にStopし、actual Runningの観測結果に基づいてSession Stateを安全に収束させる。

重要な設計目標：

1. Production Stopを `CANalyzer_Execute_Command.vi` のNon-reentrant境界へ通す。
2. Standalone Stopをnormal operational APIとして扱う。
3. Stop authorityはPublic Stopの明示callに与え、`Measurement Started By LabVIEW?`をauthorization gateにしない。
4. Stop要否はactual `Measurement.Running`で判断し、`Cached Measuring?`を真実源にしない。
5. ownership clearはvalid actual False observationがある場合だけ行う。
6. cache更新はvalid actual observationに基づく。
7. Stop Invoke errorやunverified Wait error時はstate mutationを最小化する。
8. Public APIへActiveX Ref、Session State、ownership/cache logicを露出しない。

```text
Public CANalyzer_Stop.vi
  ↓ Stop Measurement Request
CANalyzer_Execute_Command.vi [Non-reentrant]
  ↓
Registry Get
  ↓
Found?
  ↓
Get actual Running
  ↓
Running=False ?
├─ Yes → self-heal state → Registry Update → Result=False
└─ No
    ↓
    Timeout validate
    ↓
    Stop Invoke
    ↓
    Wait Running=False
    ↓
    Observation validity classify
    ├─ Success → state update
    ├─ Timeout -710104 → last actual state update
    └─ Other Wait Error → no Registry Update / preserve state
```

---

# 1. Responsibility Boundary

## 1.1 Public `CANalyzer_Stop.vi`

担当：

- Public I/O
- `Stop Measurement` Request build
- `CANalyzer_Execute_Command.vi` call
- `Result.Measurement Running?` extraction
- standard `error in / error out`

担当しない：

- Session Registry直接操作
- ActiveX Stop / Running Property直接操作
- Measurement Wait
- ownership判定
- cache更新
- special cleanup error merge

Public wrapperはActiveX Ref、Variant、Session Stateを公開しない。

## 1.2 Internal `CANalyzer_Execute_Command.vi / Stop Measurement`

担当：

- Session Get / Found判定
- actual Running read
- Stop要否判定
- timeout validation
- Stop Invoke
- Wait Running=False
- observation validity分類
- ownership/cache state transition
- Registry Update
- Result build
- error priority

---

# 2. Public API Contract

## Inputs

| Terminal | Type | Contract |
|---|---|---|
| `Session ID` | U32 | Stop対象Session |
| `Measurement Timeout ms` | U32 | Stop後Running=False確認timeout |
| `error in` | error cluster | status=TrueではStop commandをbypass |

## Outputs

| Terminal | Type | Contract |
|---|---|---|
| `Measurement Running?` | Boolean | last valid actual Running。未観測ならFalse |
| `error out` | error cluster | Stop command final error |

`Measurement Stopped?`は追加しない。

---

# 3. Shared Typedef Contract

変更はappend-only。既存Read / Write / Close / Startのordinal、field順序、型、意味を変更しない。

## 3.1 `CANalyzer_Execute_Command_Type.ctl`

```text
0 = Read SysVar
1 = Write SysVar
2 = Close Session
3 = Start Measurement
4 = Stop Measurement
```

`Stop Measurement`は末尾追加。

## 3.2 `CANalyzer_Execute_Command_Request.ctl`

**NO AMENDMENT**。

Stopで使用：

| Field | Use |
|---|---|
| `Execute_Command_Type` | `Stop Measurement` |
| `Session ID` | target session |
| `Measurement Timeout ms` | Running=False wait timeout |

その他fieldはunused/default。

## 3.3 `CANalyzer_Execute_Command_Result.ctl`

**NO AMENDMENT**。

既存 `Measurement Running?` をStop結果にも使用する。

---

# 4. Common Error Contract / Base Result

Stopはcleanup APIではない。

```text
error in.status=True
→ existing Execute_Command outer guard
→ Stop Measurement Caseを実行しない
→ Result=Default Result
→ error out=original error
```

Stop Caseへ入った直後にBase Resultを作る。

```text
default CANalyzer_Execute_Command_Result
+ Bundle By Name
    Session ID = Request.Session ID
    Measurement Running? = False
```

Registry Get成功後、initial actual Running観測成功時に`Measurement Running?`をinitial actualへ更新する。

---

# 5. Stop Authority Contract

Standalone Stopのauthorityは次で固定する。

> **Explicit Stop Always Authorized**

`Measurement Started By LabVIEW?`はStandalone Stopのauthorization gateに使わない。

| Actual Running | Existing ownership | Standalone Stop |
|---:|---:|---|
| False | False | physical Stop不要 |
| False | True | physical Stop不要 |
| True | False | Stop可 |
| True | True | Stop可 |

役割分離：

- `Measurement Started By LabVIEW?` = cleanup/history contract
- Standalone Stop authority = explicit Public API call contract

Closeではownership-aware cleanupを維持する。Standalone Stopだけexplicit authorityを持つ。

---

# 6. Final Stop Algorithm

```text
if incoming error:
    return DefaultResult, incoming error

result = DefaultResult
result.SessionID = Request.SessionID
result.MeasurementRunning = false

get = Registry.Get(Request.SessionID)
if get.error:
    return result, get.error

if not get.found:
    return result, -710102 Session Not Found

initial = GetMeasurementRunning(get.SessionOut.MeasurementRef)
if initial.error:
    return result, initial.error

result.MeasurementRunning = initial.running

if initial.running == false:
    healed = get.SessionOut
    healed.MeasurementStartedByLabVIEW = false
    healed.CachedMeasuring = false

    update = Registry.Update(
        Request.SessionID,
        healed,
        NoError)

    result.MeasurementRunning = false
    return result, update.error

if Request.MeasurementTimeoutMs == 0:
    result.MeasurementRunning = true
    return result,
        Error(-710118,
              "CANalyzer_Execute_Command.vi / Invalid Measurement Timeout")

stop = StopMeasurementInvoke(
    get.SessionOut.MeasurementRef,
    initial.error /* status=False */)

if stop.error:
    result.MeasurementRunning = true
    return result, stop.error

wait = WaitMeasurementState(
    MeasurementRef=get.SessionOut.MeasurementRef,
    ExpectedRunning=false,
    TimeoutMs=Request.MeasurementTimeoutMs,
    PollIntervalMs=100,
    errorIn=stop.error /* status=False */)

if wait.error.status == false:
    // Wait Success: Expected=Falseなのでvalid actual False
    finalState = get.SessionOut
    finalState.MeasurementStartedByLabVIEW = false
    finalState.CachedMeasuring = false

    update = Registry.Update(
        Request.SessionID,
        finalState,
        NoError)

    result.MeasurementRunning = false
    return result, update.error

if wait.error.code == -710104:
    // Timeout: Actual Running?はvalid last observation
    finalState = get.SessionOut

    if wait.ActualRunning == false:
        finalState.MeasurementStartedByLabVIEW = false
        finalState.CachedMeasuring = false
    else:
        // ownership preserve
        finalState.CachedMeasuring = true

    update = Registry.Update(
        Request.SessionID,
        finalState,
        NoError)

    result.MeasurementRunning = wait.ActualRunning
    return result, wait.error

// Other Wait Error
// new valid observationなし
// W2: Registry Updateしない
// ownership/cache preserve
result.MeasurementRunning = true
return result, wait.error
```

上記は機能意味論を示す。GUIではCase Structureで同じobservable semanticsを成立させる。

---

# 7. Registry / Found Contract

Registry Get：

| Terminal | Source |
|---|---|
| Action | `Get` |
| Session ID | Request.Session ID |
| Session In | default Session State |
| error in | outer guard success wire |

Registry Get errorではActiveXへ進まない。

Found=False：

```text
status=True
code=-710102
source="CANalyzer_Execute_Command.vi / Session Not Found"
```

Found=FalseでGet Running / Timeout / Stop / Wait / Updateへ進まない。

---

# 8. Actual Running Contract

truth source：

```text
Session Out.Measurement Ref
→ CAN_AX_Get_Measurement_Running.vi
```

`Cached Measuring?`をStop decisionに使用しない。

Get Running error：

- Timeout判定なし
- Stopなし
- Waitなし
- Registry Updateなし
- Result Running=False
- final error=Get Running error

---

# 9. Initial Running=False Self-Heal

initial actual Running=Falseはvalid observation。

physical Stop、Timeout validation、Waitは不要。

Session Outをbaseに：

```text
Measurement Started By LabVIEW? = False
Cached Measuring? = False
others = preserve
```

Registry Update：

```text
Action = Update
Session ID = Request.Session ID
Session In = self-healed state
error in = No Error constant
```

Final：

```text
Measurement Running? = False
error out = Registry Update.error out
```

---

# 10. Timeout Contract

Timeoutはinitial actual Running=Trueの場合だけ評価する。

```text
Measurement Timeout ms == 0
→ status=True
→ code=-710118
→ source="CANalyzer_Execute_Command.vi / Invalid Measurement Timeout"
→ Stop Invokeなし
→ Waitなし
→ Registry Updateなし
→ Result Running=True
```

Closeのcleanup special contractとは意図的に異なる。

---

# 11. Stop Invoke Contract

`CAN_AX_Stop_Measurement.vi`：

| Terminal | Source |
|---|---|
| Measurement Ref | Session Out.Measurement Ref |
| error in | Get Running success pathのstatus=False wire |

Stop Invoke error policyはA1で固定：

```text
Wait = No
Registry Update = No
ownership = preserve
cache = preserve
Result Running = True
Final Error = Stop error
```

physical Stop自体がerrorの場合は後続state mutationを最小化する。

---

# 12. Wait Running=False Contract

Stop Invoke success後だけ実行する。

`CANalyzer_Wait_Measurement_State.vi`：

| Terminal | Value |
|---|---|
| Measurement Ref | Session Out.Measurement Ref |
| Expected Running? | False |
| Timeout ms | Request.Measurement Timeout ms |
| Poll Interval ms | U32 100 |
| error in | Stop success status=False wire |

---

# 13. Observation Validity Contract

3-class modelで固定する。

| Class | Wait outcome | Observation validity | Registry Update |
|---|---|---|---|
| 1 | Success | VALID | Yes |
| 2 | Timeout `-710104` | VALID LAST OBSERVATION | Yes |
| 3 | Other Wait Error | INVALID / UNVERIFIED FOR NEW STATE | No |

## 13.1 Wait Success

Expected=FalseでsuccessなのでActual Running=Falseをvalid observationとして扱う。

```text
ownership=False
cache=False
Result Running=False
Registry Update=Yes / No Error constant
```

## 13.2 Wait Timeout `-710104`

Wait implementation evidence上、timeout判定前にRunning Property readが成立し、`Actual Running?`はtimeout時のlast observationを表す。

Actual=False：

```text
ownership=False
cache=False
Result Running=False
```

Actual=True：

```text
ownership=preserve
cache=True
Result Running=True
```

どちらもRegistry UpdateをNo Error constantでattemptする。

Final errorはWait timeoutを優先する。

## 13.3 Other Wait Error / W2

Successでも`-710104`でもないWait error。

```text
new valid observation = none
Registry Update = No
ownership = preserve
cache = preserve
Result Running = True
Final Error = Wait error
```

`Actual Running?`をownership/cache mutationの根拠に使わない。

---

# 14. Ownership Transition Contract

`Measurement Started By LabVIEW?`はvalid actual False observationがある場合だけFalseへclearする。

| Observation | Ownership After |
|---|---|
| Initial Running=False | False |
| Wait success False | False |
| Wait timeout Actual=False | False |
| Wait timeout Actual=True | preserve |
| Other Wait Error | preserve |
| Stop Invoke error | preserve |
| Timeout=0 after initial True | preserve |

---

# 15. Cache Persistence Contract

`Cached Measuring?`はcache only。

valid actual observationがある場合だけ更新する。

| Observation | Cache After |
|---|---|
| Initial Running=False | False |
| Wait success False | False |
| Wait timeout Actual=False | False |
| Wait timeout Actual=True | True |
| Other Wait Error | preserve |
| Stop Invoke error | preserve |
| Timeout=0 after initial True | preserve |

---

# 16. Registry Update Contract

| Path | Update? | `error in` |
|---|---:|---|
| Initial Running=False self-heal | Yes | No Error constant |
| Wait Success | Yes | No Error constant |
| Wait Timeout `-710104` | Yes | No Error constant |
| Other Wait Error | No | n/a |
| Stop Invoke Error | No | n/a |
| Timeout=0 | No | n/a |

Wait timeout errorをRegistry Update.error inへ渡さない。state persistは独立commitとしてattemptする。

physical Stop後のRegistry Update failureはrollback不能なので、retry / automatic Start rollbackは行わない。

---

# 17. Error Priority

全体到達順：

1. incoming error
2. Registry Get error
3. Session Not Found `-710102`
4. Get Running error
5. Invalid Measurement Timeout `-710118`
6. Stop Invoke error
7. Wait False error
8. Registry Update error

Path-specific：

| Path | Final Error |
|---|---|
| Initial Running=False + Update error | Registry Update error |
| Wait Success + Update success | No Error |
| Wait Success + Update error | Registry Update error |
| Wait Timeout + Update success | Wait timeout |
| Wait Timeout + Update error | Wait timeout |
| Other Wait Error | Wait error only |
| Stop Invoke Error | Stop error only |

---

# 18. Result Semantics

`Measurement Running?`：

> last valid actual Measurement Running state

| Scenario | Result Running |
|---|---:|
| incoming error bypass | False default |
| Registry/Get failure before observation | False |
| Initial Running=False | False |
| Timeout=0 after initial True | True |
| Stop Invoke error | True |
| Wait success | False |
| Wait timeout Actual=False | False |
| Wait timeout Actual=True | True |
| Other Wait Error | True |

---

# 19. Reachable State Matrix

| # | Scenario | Stop | Wait | Update | ownership after | cache after | Result Running | Final Error |
|---|---|---:|---:|---:|---|---|---:|---|
| 1 | incoming error | No | No | No | preserve | preserve | False | incoming error |
| 2 | Registry Get error | No | No | No | unknown | unknown | False | Registry error |
| 3 | Session missing | No | No | No | unknown | unknown | False | -710102 |
| 4 | Get Running error | No | No | No | preserve | preserve | False | Get Running error |
| 5 | Initial False / ownership=False | No | No | Yes | False | False | False | Update error / success |
| 6 | Initial False / ownership=True | No | No | Yes | False | False | False | Update error / success |
| 7 | Initial True / ownership=False / Timeout=0 | No | No | No | preserve | preserve | True | -710118 |
| 8 | Initial True / ownership=True / Timeout=0 | No | No | No | preserve | preserve | True | -710118 |
| 9 | Stop Invoke error | Yes | No | No | preserve | preserve | True | Stop error |
| 10 | Wait Success | Yes | Yes | Yes | False | False | False | Update error / success |
| 11 | Wait Timeout Actual=False | Yes | Yes | Yes | False | False | False | Wait timeout |
| 12 | Wait Timeout Actual=True | Yes | Yes | Yes | preserve | True | True | Wait timeout |
| 13 | Other Wait Error | Yes | Yes | No | preserve | preserve | True | Wait error |
| 14 | Wait Success + Update error | Yes | Yes | Yes | False | False | False | Update error |
| 15 | Wait Timeout + Update error | Yes | Yes | Yes | per timeout observation | per timeout observation | per timeout observation | Wait timeout |

---

# 20. Public `CANalyzer_Stop.vi`

Public wrapperはthin wrapperのみ。

```text
default Request
+ Bundle By Name
    Execute_Command_Type = Stop Measurement
    Session ID = Public Session ID
    Measurement Timeout ms = Public input
↓
CANalyzer_Execute_Command.vi
↓
Result.Measurement Running?
↓
Public Measurement Running?
```

`public error in`はExecute_Command.error inへ直接接続し、Execute_Command.error outをPublic error outへ直接返す。

Public側禁止：

- Registry
- ActiveX
- Wait
- ownership/cache logic
- Close-style special error merge

---

# 21. Serialization / Regression Contract

変更禁止：

```text
Read SysVar       = 0
Write SysVar      = 1
Close Session     = 2
Start Measurement = 3
Stop Measurement  = 4
```

- existing incoming-error outer guard変更なし
- Request existing fields変更なし
- Result existing fields変更なし
- Start ownership semantics変更なし
- Close ownership-aware cleanup semantics変更なし
- Standalone Stopだけexplicit authority

---

# 22. Recommended GUI Implementation Slices

| Slice | Scope |
|---|---|
| 1 | enum append `Stop Measurement=4` + typedef propagation review |
| 2 | Stop Case Base Result + Registry Get + Found + Get Running |
| 3 | Initial Running=False self-heal + Running=True Timeout + Stop Invoke |
| 4 | Wait False + observation validity classification + state persist + error priority |
| 5 | Public `CANalyzer_Stop.vi` thin wrapper |

各Slice後にFocused As-Built reviewを行い、P0/P1があれば次Sliceへ進まない。

---

# 23. Static Acceptance Gate

## Shared typedef

- [ ] Read=0 / Write=1 / Close=2 / Start=3 / Stop=4
- [ ] Request amendmentなし
- [ ] Result amendmentなし

## Stop Measurement Case

- [ ] Base Result.Session ID=Request.Session ID
- [ ] Base Result.Measurement Running?=False
- [ ] incoming-error outer guard unchanged
- [ ] Registry Get first
- [ ] Found=False=-710102
- [ ] actual Runningをtruth sourceに使用
- [ ] Cached Measuring?でStop decisionしない
- [ ] Explicit Stop authority
- [ ] Initial Running=False self-heal
- [ ] self-heal Update.error in=No Error constant
- [ ] TimeoutはInitial Running=Trueだけ
- [ ] Timeout=0=-710118 / no Stop / no Wait / no Update
- [ ] Stop Invoke errorでWaitなし
- [ ] Stop Invoke errorでRegistry Updateなし
- [ ] Stop successだけWait False
- [ ] Wait Expected=False
- [ ] Poll=100 U32
- [ ] Wait Successはvalid False observation
- [ ] Wait Timeout -710104はvalid last observation
- [ ] Other Wait ErrorはW2 / Registry Updateなし
- [ ] ownership clearはvalid actual Falseのみ
- [ ] cache更新はvalid actual observationのみ
- [ ] Wait Success/Timeout Update.error in=No Error constant
- [ ] Wait timeout error > Registry Update error
- [ ] Result Running=last valid actual observation
- [ ] all Case output tunnels explicit
- [ ] Use Default If Unwiredなし

## Public Stop

- [ ] Public I/O正しい
- [ ] Request command=Stop Measurement
- [ ] public error inをExecute_Commandへ直接接続
- [ ] Result.Measurement Running?をPublicへ返す
- [ ] Public側Registry/ActiveX/Wait/ownership/cacheなし

## Regression / IDE

- [ ] Read SysVar intact
- [ ] Write SysVar intact
- [ ] Close Session intact
- [ ] Start Measurement intact
- [ ] Broken Run Arrowなし
- [ ] broken typedefなし
- [ ] unintended coercion dotなし
- [ ] required tunnel unwiredなし

---

# 24. Freeze Record

```text
CANalyzer_Stop
FINAL DESIGN REVIEW = PASS

P0 = 0
P1 = 0
Observable Design Ambiguity = 0
Regression Risk = 0

Other Wait Error Policy = W2
Registry Update = No
Ownership = Preserve
Cache = Preserve
Result Running = True
Final Error = Wait Error

FINAL DESIGN = FROZEN
IMPLEMENTATION = PENDING
RUNTIME / HARDWARE E2E = PENDING
```

次は本書を基準にGUI Reconstruction Procedureを確定し、その後Slice単位で手動実装する。