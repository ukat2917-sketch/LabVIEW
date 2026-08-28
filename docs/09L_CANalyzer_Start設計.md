# 09L. CANalyzer_Start / Execute_Command Start Measurement 最終設計・実装正本

**Status:** FINAL CANONICAL / STATIC IMPLEMENTATION CLOSED  
**Design Review:** P0=0 / P1=0  
**GUI Documentation Gap:** 0  
**`CANalyzer_Execute_Command.vi / Start Measurement`:** IMPLEMENTED / AS-BUILT CLOSED  
**Public `CANalyzer_Start.vi`:** IMPLEMENTED / AS-BUILT CLOSED  
**Human Static Check:** PASS  
**Observable Design Drift:** 0  
**Runtime / Hardware E2E:** PENDING

> 本書を `CANalyzer_Start.vi` と `CANalyzer_Execute_Command.vi / Start Measurement` の設計、契約、LabVIEW GUI再構築手順、Static Acceptance、As-Built状態の単一正本とする。  
> Production StartのPublic I/O、Command拡張、ownership/cache契約、failure policy、error priority、GUI実装手順は本書を優先する。  
> `09D_CANalyzer_Execute_Command設計.md` はRead / Write初期Vertical Sliceの正本として残すが、Start Measurement追加に関する差分は本書を優先する。  
> Session RegistryのAction契約は `09B_CANalyzer_Session_Registry設計.md`、Open時のStart/rollback意味論は `09J_CANalyzer_Open設計.md`、Close時のownership消費契約は `09K_CANalyzer_Close設計.md` を参照する。

---

# 0. 目的

既存Sessionに紐づくCANalyzer Measurementを、Productionの直列化境界とownership契約を守りながらStartする。

重要な設計目標：

1. Production Startを `CANalyzer_Execute_Command.vi` のNon-reentrant境界へ通す。
2. Start要否はactual `Measurement.Running`で判断し、`Cached Measuring?`を真実源にしない。
3. pre-existing Running MeasurementのownershipをLabVIEWへ奪わない。
4. Start Invoke成功だけを新しい`Measurement Started By LabVIEW?=True`の根拠にする。
5. ownershipとRunning cacheを分離してpersistする。
6. Start成功後にownershipをuntracked状態へ残さない。
7. Wait failureとStart failureを区別する。
8. Public APIへActiveX RefやSession Stateを露出しない。

```text
Public CANalyzer_Start.vi
  ↓ Start Measurement Request
CANalyzer_Execute_Command.vi [Non-reentrant]
  ↓
Registry Get
  ↓
Found?
  ↓
Get actual Running
  ↓
Get Running Error Gate
  ↓
Running=True ?
├─ Yes → pure no-op / ownership preserve / Result Running=True
└─ No
    ↓
    Timeout validate
    ↓
    Start Invoke
    ↓
    ownership=True persist
    ↓
    Wait Running=True
    ↓
    actual Running cache persist
    ↓
    Result
```

---

# 1. Responsibility Boundary

## 1.1 Public `CANalyzer_Start.vi`

担当：

- Public I/O
- `Start Measurement` Request build
- `CANalyzer_Execute_Command.vi` call
- `Result.Measurement Running?` extraction
- standard `error in / error out`

担当しない：

- Session Registry直接操作
- ActiveX Start / Running Property直接操作
- Measurement Wait
- ownership判定
- Session State更新

Public wrapperはActiveX Ref、Variant、Session Stateを公開しない。

## 1.2 Internal `CANalyzer_Execute_Command.vi / Start Measurement`

担当：

- Session Get / Found判定
- actual Running read
- Get Running Error Gate
- Start要否判定
- timeout validation
- Start Invoke
- ownership-first Registry Update
- Running=True Wait
- final cache Registry Update
- ownership persist failure時のrollback Stop / Wait False
- Start Result build
- error priority

---

# 2. Public API Contract

## Inputs

| Terminal | Type | Contract |
|---|---|---|
| `Session ID` | U32 | Start対象Session |
| `Measurement Timeout ms` | U32 | Start後Running=True確認timeout |
| `error in` | error cluster | status=TrueではStart commandをbypass |

## Outputs

| Terminal | Type | Contract |
|---|---|---|
| `Measurement Running?` | Boolean | 最後に正常観測できたactual Running。観測未成立ならFalse |
| `error out` | error cluster | Start command final error |

Publicへ`Start Invoked?`、`Measurement Started By LabVIEW?`、`Cached Measuring?`は出さない。

---

# 3. Shared Typedef Amendment

変更はappend-only。既存Read / Write / Closeのordinal、field順序、型、意味を変更しない。

## 3.1 `CANalyzer_Execute_Command_Type.ctl`

```text
0 = Read SysVar
1 = Write SysVar
2 = Close Session
3 = Start Measurement
```

`Start Measurement`は末尾追加。

## 3.2 `CANalyzer_Execute_Command_Request.ctl`

追加fieldなし。

Start Measurement Caseで使用：

| Field | Use |
|---|---|
| `Execute_Command_Type` | `Start Measurement` |
| `Session ID` | target session |
| `Measurement Timeout ms` | Running=True wait timeout |

その他fieldはunused/default。

## 3.3 `CANalyzer_Execute_Command_Result.ctl`

既存末尾`Session Removed?`の後へappend：

| Field | Type | Default |
|---|---|---|
| `Measurement Running?` | Boolean | False |

Start Measurement Result：

| Field | Value |
|---|---|
| `Session ID` | Request.Session ID |
| `Requested Value` | default |
| `Read Value` | default |
| `Verified?` | False |
| `Session Removed?` | False/default |
| `Measurement Running?` | last successfully observed actual Running、未観測ならFalse |

既存Result fieldをStart用の別意味へ流用しない。

---

# 4. Common Error Contract / Base Result

Startはcleanup APIではない。

```text
error in.status=True
→ existing Execute_Command outer guard
→ Start Measurement Caseを実行しない
→ Result=default
→ error out=original error
```

Public `CANalyzer_Start.vi` はpublic `error in`を通常どおり `CANalyzer_Execute_Command.vi.error in`へ渡す。

Start Measurement Caseへ入った直後にBase Resultを作る。

```text
default CANalyzer_Execute_Command_Result
+ Bundle By Name
    Session ID = Request.Session ID
    Measurement Running? = False
```

その他fieldはdefault。Start Measurement Case内の全branchでこのResult stateをpassする。

したがってStart Caseへ入った後はRegistry Get error、Session Not Found、Get Running error、Invalid Timeout、Start error、Stage1 Update error、Wait error、Stage2 Update errorでも`Result.Session ID=Request.Session ID`を保持する。

outer incoming-error bypassだけは既存契約どおりDefault Resultのまま。

---

# 5. Final Start Algorithm

```text
function StartMeasurement(Request, errorIn):
    if errorIn.status:
        return DefaultResult, errorIn

    result = DefaultResult
    result.SessionID = Request.SessionID
    result.MeasurementRunning = false
    running = false

    get = Registry.Get(Request.SessionID, errorIn /* status=False */)
    if get.error:
        return result, get.error

    if not get.found:
        return result,
            Error(-710102,
                  "CANalyzer_Execute_Command.vi / Session Not Found")

    session = get.session

    initial = GetMeasurementRunning(
        session.MeasurementRef,
        get.error /* status=False */)

    if initial.error:
        return result, initial.error

    running = initial.running
    result.MeasurementRunning = running

    if running:
        // pure no-op
        // ownership preserve
        // no Registry Update
        return result, NoError

    if Request.MeasurementTimeoutMs == 0:
        return result,
            Error(-710118,
                  "CANalyzer_Execute_Command.vi / Invalid Measurement Timeout")

    start = StartMeasurementInvoke(
        session.MeasurementRef,
        initial.error /* status=False */)

    if start.error:
        return result, start.error

    ownedState = session
    ownedState.MeasurementStartedByLabVIEW = true
    ownedState.CachedMeasuring = false

    ownershipUpdate = Registry.Update(
        Request.SessionID,
        ownedState,
        NoError)

    if ownershipUpdate.error:
        primary = ownershipUpdate.error

        stop = StopMeasurement(session.MeasurementRef, NoError)
        if not stop.error:
            waitFalse = WaitMeasurementState(
                MeasurementRef=session.MeasurementRef,
                ExpectedRunning=false,
                TimeoutMs=Request.MeasurementTimeoutMs,
                PollIntervalMs=100,
                errorIn=NoError)

            if waitFalse produced an actual observation:
                running = waitFalse.ActualRunning

        result.MeasurementRunning = running
        return result, primary

    waitTrue = WaitMeasurementState(
        MeasurementRef=session.MeasurementRef,
        ExpectedRunning=true,
        TimeoutMs=Request.MeasurementTimeoutMs,
        PollIntervalMs=100,
        errorIn=ownershipUpdate.error /* status=False */)

    running = waitTrue.ActualRunning
    result.MeasurementRunning = running

    finalState = ownershipUpdate.SessionOut
    finalState.MeasurementStartedByLabVIEW = true
    finalState.CachedMeasuring = running

    cacheUpdate = Registry.Update(
        Request.SessionID,
        finalState,
        NoError)

    if waitTrue.error:
        return result, waitTrue.error

    if cacheUpdate.error:
        return result, cacheUpdate.error

    return result, NoError
```

上記は機能意味論を示す。GUIではCase Structureで同じobservable semanticsを成立させる。

---

# 6. Validation / State Decision Order

順序固定：

```text
Incoming Error Guard
↓
Registry Get
↓
Registry Get Error Gate
↓
Found?
↓
Get actual Running
↓
Get Running Error Gate
↓
Running=True ?
├─ Yes → success no-op
└─ No
    ↓
    Measurement Timeout ms == 0 ?
    ├─ Yes → -710118 / no Start
    └─ No  → Start
```

Timeout validationをRegistry Getより前へ置かない。Get Running error時にTimeout判定やStartへ進まない。

---

# 7. Initial Running=True No-op Contract

actual Running=Trueなら：

```text
Start Invoke = No
Registry Update = No
Measurement Running? = True
```

ownershipは既存値をpreserveする。

| Existing `Measurement Started By LabVIEW?` | After Start API |
|---:|---:|
| False | False |
| True | True |

Running=Trueだけを理由にFalse→Trueへ変更しない。cache refreshだけのRegistry writeもskipする。

---

# 8. Initial Running=False / Timeout Contract

Running=FalseでだけTimeoutを評価する。

```text
Measurement Timeout ms == 0
→ status=True
→ code=-710118
→ source="CANalyzer_Execute_Command.vi / Invalid Measurement Timeout"
→ Start Invokeなし
→ Registry Updateなし
→ Waitなし
→ rollback Stopなし
```

Result `Measurement Running?`はinitial actual observationのFalseを保持する。

---

# 9. Start Ownership / Two-stage Persistence

new ownership=Trueの根拠はStart Invoke successだけ。

```text
Start Invoke success
→ Measurement Started By LabVIEW? = True
```

Start Invoke failureではexisting ownershipを変更しない。

## Stage 1: ownership persist

Start成功直後、Waitより前にworking copyを作る。

```text
Measurement Started By LabVIEW? = True
Cached Measuring? = False
その他field = existing session preserve
```

Registry Update：

```text
Action = Update
Session ID = Request.Session ID
Session In = ownership working copy
error in = No Error constant
```

## Stage 2: actual cache persist

Wait後：

```text
Measurement Started By LabVIEW? = True
Cached Measuring? = Wait.Actual Running?
```

Stage2 Registry UpdateはWait errorを直接渡さずNo Error constantでattemptする。

---

# 10. Ownership Persist Failure Rollback

Stage1 Registry Update failureはownership tracking failure。

```text
Primary Error = Stage1 Registry Update error
↓
Rollback Stop [error in = No Error]
↓
Stop successなら Wait False [error in = No Error]
Expected Running? = False
Timeout ms = Request.Measurement Timeout ms
Poll Interval ms = 100
```

Final error priority：

```text
Ownership Persist Error > Rollback Error
```

Registry SessionはRemoveしない。

Rollback Wait Falseでは`Actual Running?`をcaptureする。

- actual observationが成立した場合：`Measurement Running? = Wait False.Actual Running?`
- actual observationが成立しなかった場合：それ以前のlast successfully observed Runningを保持
- Wait False errorの有無だけを理由にActual Runningを捨てない

---

# 11. Wait Running=True Failure Policy

Stage1 ownership persist成功後のWait failureではautomatic Stop rollbackしない。

```text
Start Invoke = success
ownership persist = success
Wait Running=True = error
→ ownership=TrueをRegistryへ残す
→ Wait Actual Running?をResultへ保持
→ Stage2 cache Updateをattempt
→ Wait errorをcallerへ返す
→ automatic Stopなし
```

Open時のStart failure rollbackとは異なる。Standalone Startは既存Sessionを利用しownershipが追跡済みなので、後続Stop / Closeで安全に停止できる。

---

# 12. Final Cache Update Error Policy

| Wait | Cache Update | Final Error |
|---|---|---|
| success | success | success |
| success | error | Cache Update error |
| error | success | Wait error |
| error | error | Wait error |

Wait errorとStage2 Update errorのmergeはpriority selectを明示する。

```text
Wait error.status = True  → Final Error = Wait error
Wait error.status = False → Final Error = Stage2 Update error
```

---

# 13. Error Priority

到達順：

1. incoming error outer guard
2. Registry Get error
3. Session Not Found `-710102`
4. Get Running error
5. Invalid Measurement Timeout `-710118`
6. Start Invoke error
7. Ownership Registry Update error
8. Wait Running=True error
9. Final Cache Registry Update error

Stage1 ownership persist failure後のrollback errorはprimaryを上書きしない。

---

# 14. Result Semantics

`Measurement Running?`：

> last successfully observed actual Measurement Running state

- actual観測が一度も成立していない場合はFalse。
- Initial Running=True no-opではTrue。
- Initial Running=False + Timeout=0ではFalse。
- Start Invoke成功だけを理由にTrueへ推定しない。
- Wait True後はWait serviceのactual observationを採用する。
- rollback Wait Falseがactual観測できた場合はその値を採用する。

`Measurement Running?`はownershipではない。

---

# 15. Detailed LabVIEW GUI Reconstruction Procedure

本節をStart Measurement GUI再構築手順の正本とする。Nigel内部UID / Node ID / Wire IDは使用しない。

## 15.1 Shared Typedef Amendment

### `CANalyzer_Execute_Command_Type.ctl`

1. enumの既存`Read SysVar`、`Write SysVar`、`Close Session`を変更しない。
2. 末尾へ`Start Measurement`を追加。
3. ordinalが`0 / 1 / 2 / 3`であることを確認。

### `CANalyzer_Execute_Command_Request.ctl`

変更なし。

### `CANalyzer_Execute_Command_Result.ctl`

1. cluster末尾、`Session Removed?`の後へBooleanを追加。
2. Label=`Measurement Running?`。
3. Default=False。
4. existing field順序・label・型を変更しない。

## 15.2 Dispatcher / Base Result

1. `CANalyzer_Execute_Command.vi`を開く。
2. `Execute_Command_Type` Case Structureへ`Start Measurement` caseを追加。
3. outer incoming-error guardは変更しない。
4. Start Case先頭にdefault Result constant + Bundle By Nameを置く。
5. `Session ID=Request.Session ID`、`Measurement Running?=False`を設定。
6. このBase ResultをStart Case内の全branchへpassする。

## 15.3 Registry Get

`CANalyzer_Session_Registry.vi`：

| Terminal | Source |
|---|---|
| Action | `Get` constant |
| Session ID | Request.Session ID |
| Session In | default Session State |
| error in | Execute_Command outer guardを通過したincoming error wire（status=False） |

Registry Get error outはまずError Gateへ入れる。

### Registry Get Error Gate

selector=`Registry Get.error out.status`。

TRUE：

- ActiveXへ進まない。
- Base Resultをpass。
- Measurement Running state=False/last observed。
- final error=`Registry Get.error out`。

FALSE：

- `Session Out`をpass。
- `Registry Get.error out`（status=False）をFound Gateへpass。

全output tunnelを明示配線し`Use Default If Unwired`は禁止。

## 15.4 Found Gate

selector=`Registry Get.Found?`。

FALSE：

```text
status=True
code=-710102
source="CANalyzer_Execute_Command.vi / Session Not Found"
```

ActiveXへ進まない。Base Result / running state / final errorをfinal Result pathへ出す。

TRUE：

`Session Out`をGet Runningへ渡す。

## 15.5 Get actual Running

Session Outからactual GUI field `Measurement Ref`をUnbundle By Name。

`CAN_AX_Get_Measurement_Running.vi`：

| Terminal | Source |
|---|---|
| Measurement Ref | Session Out.Measurement Ref |
| error in | Registry Get success pathの`Registry Get.error out`（status=False） |

`Running`はInitial Running候補。`Cached Measuring?`をStart decisionに使わない。

### Get Running Error Gate

selector=`CAN_AX_Get_Measurement_Running.vi.error out.status`。

TRUE：

- Start Invokeしない。
- Timeout判定しない。
- Registry Updateしない。
- Waitしない。
- Measurement Running stateはそれ以前のlast observed。初回観測失敗ならFalse。
- final error=`Get Running.error out`。

FALSE：

- `Running`をInitial Runningとして採用。
- `Get Running.error out`（status=False）を後段へpass。

## 15.6 Initial Running Case

selector=Initial Running。

TRUE：

- Startなし。
- Registry Updateなし。
- Waitなし。
- ownership preserve。
- Measurement Running state=True。
- Base Resultをfinal Result pathへpass。

FALSE：Timeout Caseへ。

## 15.7 Timeout Case

Running=False branch内でのみ`Request.Measurement Timeout ms == U32 0`を評価。

TRUE：

```text
status=True
code=-710118
source="CANalyzer_Execute_Command.vi / Invalid Measurement Timeout"
```

- Measurement Running=False。
- no Start。
- no Registry Update。
- no Wait。
- no rollback Stop。
- final Result / Error pathへ。

FALSE：Start Invokeへ。

## 15.8 Start Invoke

`CAN_AX_Start_Measurement.vi`：

| Terminal | Source |
|---|---|
| Measurement Ref | Session Out.Measurement Ref |
| error in | Get Running success pathの`Get Running.error out`（status=False） |

Start error.status=True：ownership変更なし、Updateなし、Waitなし、Result Running=Falseを保持してfinal path。

Start success：ownership working stateへ。

## 15.9 Ownership Working State

Session OutをbaseにBundle By Name。

| Field | Value |
|---|---|
| `Measurement Started By LabVIEW?` | True |
| `Cached Measuring?` | False |
| others | preserve |

## 15.10 Stage1 Registry Update

`CANalyzer_Session_Registry.vi`：

| Terminal | Source |
|---|---|
| Action | Update |
| Session ID | Request.Session ID |
| Session In | ownership working state |
| error in | No Error constant |

success時は`Session Out`をStage2 base stateとして保持。

## 15.11 Stage1 Update Error Case / Rollback

selector=`Stage1 Registry Update.error out.status`。

TRUE：

- Primary Error=Stage1 Update error。
- `CAN_AX_Stop_Measurement.vi`をNo Error constantで実行。
- Stop errorならWait Falseをskipし、primary errorを保持。
- Stop successならWait Falseを実行。

Rollback Wait False：

| Terminal | Value |
|---|---|
| Measurement Ref | same Session Out.Measurement Ref |
| Expected Running? | False |
| Timeout ms | Request.Measurement Timeout ms |
| Poll Interval ms | U32 100 |
| error in | No Error constant |

Wait Falseがactual observationを成立できた場合は`Actual Running?`をrunning stateへ反映する。観測未成立なら以前のlast observedを保持。rollback errorでprimaryを上書きしない。

FALSE：Wait Running=Trueへ。

## 15.12 Wait Running=True

`CANalyzer_Wait_Measurement_State.vi`：

| Terminal | Value |
|---|---|
| Measurement Ref | Session Out.Measurement Ref |
| Expected Running? | True |
| Timeout ms | Request.Measurement Timeout ms |
| Poll Interval ms | U32 100 |
| error in | Stage1 Registry Update success pathの`error out`（status=False） |

`Actual Running?`をrunning stateへ反映。Wait errorでもautomatic Stopしない。

## 15.13 Stage2 Cache Update

Stage1 Update success時のSession OutをbaseにBundle By Name。

| Field | Value |
|---|---|
| `Measurement Started By LabVIEW?` | True |
| `Cached Measuring?` | Wait Actual Running? |

Registry Update：

| Terminal | Source |
|---|---|
| Action | Update |
| Session ID | Request.Session ID |
| Session In | Stage2 state |
| error in | No Error constant |

Wait errorをStage2 Update.error inへ渡さない。

## 15.14 Wait / Cache Error Priority

`Wait error.status`をCase selectorへ。

TRUE：Wait errorをfinal errorへ。  
FALSE：Stage2 Update.error outをfinal errorへ。

両Case output tunnelを明示配線する。

## 15.15 Result Build

Base ResultをBundle By Name。

| Field | Source |
|---|---|
| Session ID | 既にBase ResultでRequest.Session ID |
| Measurement Running? | final running state |
| others | default |

final Resultとfinal errorをExecute_Command出力へ。

---

# 16. Complete Tunnel Tables

| Gate / Case | Branch | Result state | Running state | Session state | Primary error | Next |
|---|---|---|---|---|---|---|
| Registry Get Error | TRUE | Base Result | False/last observed | default/pass | Get error | final |
| Registry Get Error | FALSE | Base Result | unchanged | Session Out | no-error | Found Gate |
| Found? | FALSE | Base Result | False/last observed | default/pass | -710102 | final |
| Found? | TRUE | Base Result | unchanged | Session Out | no-error | Get Running |
| Get Running Error | TRUE | Base Result | last observed/False | Session Out | Get Running error | final |
| Get Running Error | FALSE | Base Result | Running→Initial | Session Out | no-error | Initial Running |
| Initial Running | TRUE | Base Result | True | preserve | no-error | final |
| Initial Running | FALSE | Base Result | False | preserve | no-error | Timeout |
| Timeout | TRUE | Base Result | False | preserve | -710118 | final |
| Timeout | FALSE | Base Result | False | preserve | no-error | Start |
| Start Error | TRUE | Base Result | False/last observed | ownership unchanged | Start error | final |
| Start Error | FALSE | Base Result | False | working state | no-error | Stage1 Update |
| Stage1 Update Error | TRUE | Base Result | last observed False | persisted state不成立 | Stage1 error | Rollback Stop |
| Stage1 Update Error | FALSE | Base Result | False | persisted ownership state | no-error | Wait True |
| Rollback Stop Error | TRUE | Base Result | last observed | session unchanged | Stage1 error | final |
| Rollback Stop Error | FALSE | Base Result | pending Wait False | session unchanged | Stage1 error | Wait False |
| Wait / Cache Merge | Wait error TRUE | Base Result | Wait Actual | Stage2 attempted | Wait error | final |
| Wait / Cache Merge | Wait error FALSE | Base Result | Wait Actual | Stage2 attempted | Stage2 error/No Error | final |

全Caseで必要なoutput tunnelを明示配線し`Use Default If Unwired`は禁止。

---

# 17. Complete Wiring Table

| From | To | Type | Meaning |
|---|---|---|---|
| Request.Session ID | Base Result.Session ID | U32 | Start target identity |
| False | Base Result.Measurement Running? | Boolean | default unobserved state |
| Request.Session ID | Registry Get.Session ID | U32 | target session |
| default Session State | Registry Get.Session In | cluster | required unused content |
| outer guard success error wire | Registry Get.error in | error cluster | status=False |
| Registry Get.Session Out.Measurement Ref | Get Running.Measurement Ref | ActiveX Ref | actual state source |
| Registry Get.error out success wire | Get Running.error in | error cluster | status=False |
| Get Running.Running | Initial Running selector | Boolean | Start decision |
| Request.Measurement Timeout ms | Equal? | U32 | timeout compare |
| U32 0 | Equal? | U32 | invalid timeout threshold |
| Session Out.Measurement Ref | Start.Measurement Ref | ActiveX Ref | Start target |
| Get Running.error out success wire | Start.error in | error cluster | status=False |
| Session Out | Stage1 Bundle input | Session State | ownership working copy base |
| True | Stage1 Measurement Started By LabVIEW? | Boolean | ownership history |
| False | Stage1 Cached Measuring? | Boolean | initial actual state |
| Request.Session ID | Stage1 Update.Session ID | U32 | update key |
| Stage1 working state | Stage1 Update.Session In | Session State | persist ownership |
| No Error | Stage1 Update.error in | error cluster | clean execution |
| Measurement Ref | Rollback Stop.Measurement Ref | ActiveX Ref | rollback target |
| No Error | Rollback Stop.error in | error cluster | primary isolation |
| Measurement Ref | Rollback Wait False.Measurement Ref | ActiveX Ref | stopped confirmation |
| False | Rollback Wait False.Expected Running? | Boolean | target state |
| Request Timeout | Rollback Wait False.Timeout ms | U32 | timeout |
| U32 100 | Rollback Wait False.Poll Interval ms | U32 | poll |
| No Error | Rollback Wait False.error in | error cluster | clean execution |
| Measurement Ref | Wait True.Measurement Ref | ActiveX Ref | running confirmation |
| True | Wait True.Expected Running? | Boolean | target state |
| Request Timeout | Wait True.Timeout ms | U32 | timeout |
| U32 100 | Wait True.Poll Interval ms | U32 | poll |
| Stage1 Update success error out | Wait True.error in | error cluster | status=False |
| Stage1 persisted Session Out | Stage2 Bundle input | Session State | cache state base |
| Wait True.Actual Running? | Stage2 Cached Measuring? | Boolean | actual cache |
| True | Stage2 Measurement Started By LabVIEW? | Boolean | preserve ownership |
| Request.Session ID | Stage2 Update.Session ID | U32 | update key |
| Stage2 state | Stage2 Update.Session In | Session State | persist actual cache |
| No Error | Stage2 Update.error in | error cluster | do not bypass on Wait error |
| final running state | Result.Measurement Running? | Boolean | public useful result |
| final start error | Execute_Command.error out | error cluster | command status |

---

# 18. Public `CANalyzer_Start.vi` GUI Procedure

**As-Built Path:** `C:\LabVIEW work\SVS_AutoTestSystem\60_CAN\30_Public\CANalyzer_Start.vi`

## Front Panel

| Label | Type | Direction |
|---|---|---|
| `Session ID` | U32 | Control |
| `Measurement Timeout ms` | U32 | Control |
| `error in` | error cluster | Control |
| `Measurement Running?` | Boolean | Indicator |
| `error out` | error cluster | Indicator |

## Request Build

default `CANalyzer_Execute_Command_Request` cluster + Bundle By Name。

| Field | Value |
|---|---|
| `Execute_Command_Type` | Start Measurement |
| `Session ID` | Public Session ID |
| `Measurement Timeout ms` | Public input |

## Execute_Command Call

| Terminal | Source |
|---|---|
| Request | built request |
| error in | Public error in |

CloseのようにNo Errorへ置換しない。

## Result Extract

`Execute_Command.Result`をUnbundle By Nameし`Measurement Running?`をPublic indicatorへ。

`Execute_Command.error out`をPublic `error out`へ直結。

Public側にRegistry、ActiveX、Wait、ownership logicを置かない。

## Connector Pane

3 inputs / 2 outputs。exact visual placementは既存Public API patternへ合わせて人手確認する。

---

# 19. Reachable State Matrix

| Case | Expected |
|---|---|
| incoming error | command bypass / original error / Default Result Running=False |
| Registry Get error | no ActiveX / Result.Session ID=Request.Session ID / Get error |
| Session missing + Timeout=0 | `-710102` / no ActiveX |
| Get Running error | no Timeout / no Start / Get Running error |
| Found + Running=True + Timeout=0 | success no-op / ownership preserve / Running=True |
| Found + Running=False + Timeout=0 | `-710118` / no Start / no rollback / Running=False |
| Running=False + Start failure | ownership unchanged / Start error / Running=False |
| Start success + Stage1 persist success + Wait success | ownership=True / cache=True / Running=True / success |
| Start success + Stage1 persist success + Wait timeout + Actual=False | ownership=True / cache=False / Running=False / Wait error / no rollback |
| Start success + Stage1 persist success + Wait timeout + Actual=True | ownership=True / cache=True / Running=True / Wait error / no rollback |
| Start success + Stage1 persist failure + rollback Wait False Actual=False | primary=Registry Update error / Running=False |
| Start success + Stage1 persist failure + rollback failure | primary=Registry Update error / rollback secondary / Running=last observation |
| Wait success + Stage2 Update failure | ownership tracked / Running=True / Cache Update error |
| Wait failure + Stage2 Update failure | ownership tracked / Running=Wait Actual / Wait error |

---

# 20. Regression Contract

```text
Read SysVar       = 0
Write SysVar      = 1
Close Session     = 2
Start Measurement = 3
```

- existing incoming-error guard変更なし。
- Read / Write observable semantics変更なし。
- Close Session observable semantics変更なし。
- Request existing fields変更なし。
- Result existing fields変更なし。
- `Measurement Running?`だけ末尾append。

---

# 21. Static Acceptance Gate

## Shared Typedef

- [x] Read=0 / Write=1 / Close=2 / Start=3
- [x] Request existing fields不変
- [x] Result existing fields不変
- [x] `Measurement Running?`末尾Boolean

## Start Measurement Case

- [x] Base Result.Session ID=Request.Session ID
- [x] incoming error outer guard unchanged / bypass時Default Result
- [x] Registry Get first
- [x] Registry Get errorでActiveXへ進まない
- [x] Found=False=`-710102`
- [x] actual RunningをStart要否に使用
- [x] Get Running errorでTimeout/Startへ進まない
- [x] Cached Measuring?をStart要否に使用しない
- [x] Running=True pure no-op
- [x] Running=True ownership preserve
- [x] Running=True Registry Updateなし
- [x] TimeoutはRunning=Falseだけ
- [x] Timeout=0=`-710118`
- [x] Timeout=0でrollback Stopなし
- [x] Start successだけownership=True
- [x] Stage1 persistはWait前
- [x] Stage1 Cached Measuring=False
- [x] Stage1 failure rollback Stop
- [x] Stop successならWait False
- [x] Rollback Wait False Actualをcapture
- [x] Primary persist error保持
- [x] Wait True Expected=True
- [x] Poll=100
- [x] Wait failure automatic Stopなし
- [x] Wait ActualをResultへ
- [x] Stage2 cache actual値
- [x] Stage2 Update clean error
- [x] Wait error > cache error
- [x] 全Case output tunnel明示
- [x] Use Default If Unwiredなし

## Public Start

- [x] I/O=`Session ID`, `Measurement Timeout ms`, `error in` → `Measurement Running?`, `error out`
- [x] Request command=`Start Measurement`
- [x] Public error inをExecute_Commandへ通常接続
- [x] Result.Measurement Running?をPublicへ返す
- [x] Public側にRegistry / ActiveX / Wait / ownership logicなし

## Regression / IDE

- [x] Read SysVar intact
- [x] Write SysVar intact
- [x] Close Session intact
- [x] Broken Run Arrowなし
- [x] broken typedefなし
- [x] unintended coercion dotなし
- [x] required tunnel unwiredなし

---

# 22. Documentation Closure / Next Gate

Final GUI Documentation Gap Closure：

```text
Get Running error gate = DEFINED
Base Result State = DEFINED
Rollback Wait False Actual Running = DEFINED
Timeout tunnel = CORRECTED
Exact error wire sources = DEFINED
Complete tunnel tables = DEFINED
Use Default If Unwired = FORBIDDEN

GUI DOCUMENTATION GAP = 0
GUI RECONSTRUCTION PROCEDURE = FINAL / COMPLETE
```

Design / As-Built Closure：

```text
P0 = 0
P1 = 0
Observable Design Drift = 0
Production Serialization = PRESERVED
Ownership Tracking = PRESERVED
Pre-existing Ownership = PRESERVED
Actual Running Source = PRESERVED
Registry Failure Safety = CLOSED
Wait Failure Policy = CLOSED
Append-only Regression Contract = PRESERVED
Shared Typedef Amendment = CLOSED
Start Measurement Internal = IMPLEMENTED / AS-BUILT CLOSED
Public CANalyzer_Start.vi = IMPLEMENTED / AS-BUILT CLOSED
Human Static Check = PASS

CANalyzer_Start / Start Measurement
FINAL DESIGN = FROZEN
GUI RECONSTRUCTION PROCEDURE = COMPLETE
STATIC IMPLEMENTATION = CLOSED
RUNTIME / HARDWARE E2E = PENDING
```

Static Closureまで完了した。以後、本書をStart系のFinal Canonical / As-Built Baselineとして扱う。

次のStart固有GateはRuntime / Hardware E2E。実機確認までは、runtime成功、CANalyzer実機接続成功、Measurement実状態遷移成功を断定しない。
