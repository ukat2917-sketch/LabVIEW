# 09K. CANalyzer_Close / Execute_Command Close Session 最終設計・実装正本

**Status:** FINAL CANONICAL / STATIC IMPLEMENTATION CLOSED  
**Design:** FINAL / CLOSED  
**`CANalyzer_Execute_Command.vi / Close Session`:** IMPLEMENTED / AS-BUILT CLOSED  
**Internal Design Drift Review:** P0=0 / P1=0 / P2=0 / observable DESIGN DRIFT=0  
**Human Static Check:** PASS  
**GUI Reconstruction Procedure:** FINAL / COMPLETE  
**Public `CANalyzer_Close.vi`:** IMPLEMENTED / AS-BUILT CLOSED  
**Public Design Drift Review:** P0=0 / P1=0 / observable DESIGN DRIFT=0  
**Runtime / Hardware E2E:** PENDING  

> 本書を `CANalyzer_Close.vi` と `CANalyzer_Execute_Command.vi / Close Session` の設計思想、契約、LabVIEW GUI実装手順、As-Built差分、Static Acceptanceの**単一正本**とする。  
> 旧 `09KA_CANalyzer_Close実装手順.md` は本書へ統合済み。以後、Close関連の詳細手順を別文書へ複製しない。  
> `09D_CANalyzer_Execute_Command設計.md` はRead / Write初期Vertical Sliceの正本として残すが、Close Session追加に関するCommand enum / Request / Result / cleanup / finalization契約は本書を優先する。

---

# 0. この設計で実現したいこと

`CANalyzer_Close.vi` の目的は「CANalyzerを閉じること」だけではない。

ProductionでSession IDに紐づくCANalyzer resourceを、次の条件を守りながら安全にterminal化することが責務である。

1. Read / Write / Closeを同じ直列化境界へ通す。
2. LabVIEWが所有するものだけを停止・Quitする。
3. 途中cleanupが失敗しても残りのcleanupを続ける。
4. 最初に発生したClose errorを診断情報として失わない。
5. Registry Removeを全経路共通のfinalizationにする。
6. Public APIへActiveX Refを露出しない。
7. `Session Removed?` をcleanup成功フラグと混同しない。

```text
Public CANalyzer_Close.vi
  ↓ Close Session Request
CANalyzer_Execute_Command.vi [Non-reentrant]
  ↓
Registry Get
  ↓
Owned Measurement Stop / Wait
  ↓
Reference Cleanup
  ↓
Conditional Application Quit
  ↓
Common Remove Merge
  ↓
Registry Remove
  ↓
Result
```

`CANalyzer_Open.vi` はSession ID発行前のbootstrap APIなのでExecute_Commandを通さない。Open自身をNon-reentrantとして直列化する。

---

# 1. 設計思想

## 1.1 なぜCloseをExecute_Command内へ入れるか

Production Read / Write / Closeが別々にActiveXへ触ると、同一Sessionへ複数Threadからアクセスした場合に、Read中にCloseされる、Write中にMeasurement Refが解放される等の競合が起こり得る。

そのためSession-bound production operationは共通の `CANalyzer_Execute_Command.vi` を通す。

```text
Read SysVar  ┐
Write SysVar ├→ CANalyzer_Execute_Command.vi [Non-reentrant] → ActiveX
Close Session┘
```

PoCやdiagnostic wrapperのdirect-callはproduction serialization guaranteeの対象外とする。

## 1.2 なぜPublic APIからActiveXを隠すか

ActiveX RefをTestStandや上位VIへ公開すると、Refのownershipとlifetimeが分散する。

Public APIはSession IDと通常型だけを公開し、Application/System/Measurement RefはSession Registry内部へ閉じ込める。

## 1.3 なぜownershipをSession Stateへ記録するか

Cleanupでは「Refが存在するか」ではなく「誰が開始・所有したか」を使う。

Stop source of truth：

```text
Measurement Started By LabVIEW?
```

Quit source of truth：

```text
Application_Ownership
```

`Cached Measuring?` はStop ownership判定に使わない。

| Ownership / History | Action |
|---|---|
| Measurement Started By LabVIEW? = False | Stopしない |
| Measurement Started By LabVIEW? = True | Stop attempt |
| Application_Ownership = LabVIEW | Quit attempt |
| Application_Ownership = External | Quitしない |
| Application_Ownership = Unknown | Quitしない |

## 1.4 なぜFirst Close ErrorとCleanup Sequence Errorを分離するか

通常のerror wire一本だけでcleanupを直列接続すると、前段errorにより後続SubVIがbypassされる可能性がある。一方、各cleanupへ独立したNo Errorを配ると、実行順序が失われる。

Close内部では2本を明確に分離する。

| Wire | Role |
|---|---|
| `First Close Error` | 最初のClose errorを保持するdiagnostic state |
| `Cleanup Sequence Error` | cleanup actionの実行順序だけを保証するclean token |

基本形：

```text
Action.error out
  ├─→ First Close Error Update
  └─→ Clear Errors
         ↓
     Cleanup Sequence Error after Action
         ↓
     Next Action.error in
```

First Close Error更新：

```text
if Previous.status=True:
    Updated = Previous
else:
    Updated = New Action Error
```

これにより**First Error Wins**と**best-effort cleanup**を同時に成立させる。

## 1.5 なぜRegistry Removeを最後にするか

Registry entryはApplication/System/Measurement Refのlifecycle authorityである。先にRemoveすると、後続cleanupでSession Stateへ到達できない。

したがってRemoveはGet error / Found=False / cleanup success / cleanup failureを含む全経路共通の最後にattemptする。

## 1.6 なぜSession Removed?はcleanup成功ではないか

`Session Removed?` はRegistry finalizationの成否だけを表す。

```text
Session Removed?
= NOT Registry Remove.error out.status
  AND Registry Remove.Found?
```

Stop / Wait / Ref Close / Quitにerrorがあっても、Remove success + Found=Trueなら `Session Removed?=True` になり得る。

`First Close Error after Remove`や`Final First Close Error`をこの式に使用しない。

## 1.7 なぜTimeout=0でもStopする場合があるか

`Measurement Timeout ms=0` はStop invocationが不正なのではなく、停止確認Waitの契約が不正である。

```text
Started=True + Timeout=0
→ -710118 diagnostic
→ Stop attempt
→ Wait skip
→ cleanup続行
```

> `Measurement Timeout ms = 0` is an invalid wait-confirmation contract, not an invalid stop-invocation contract.

---

# 2. Responsibility Boundary

## 2.1 Internal `CANalyzer_Execute_Command.vi / Close Session`

責務：

- Registry Get
- Session存在判定
- ownership-aware Stop / Wait
- Measurement/System/Application Ref cleanup
- conditional Quit
- Common Remove Merge
- Registry Remove
- First Close Error
- Cleanup Sequence Error
- internal Result build

## 2.2 Public `CANalyzer_Close.vi`

責務：

- Public I/O
- `Close Session` Request build
- caller `error in` を `Original Error` として保持
- Execute_Commandをclean errorでcall
- `Session Removed?` extraction
- `Original Error > Close Error` final merge

Public wrapperはActiveX Refを扱わない。

---

# 3. Shared Typedef Contract

Shared typedef変更はappend-onlyとする。既存Read / Writeのordinal、field名、型、順序、意味を変更しない。

## 3.1 `CANalyzer_Execute_Command_Type.ctl`

```text
0 = Read SysVar
1 = Write SysVar
2 = Close Session
```

## 3.2 `CANalyzer_Execute_Command_Request.ctl`

既存field末尾へ追加：

| Field | Type |
|---|---|
| `Measurement Timeout ms` | U32 |

command selector actual field label：

```text
Execute_Command_Type
```

field type：

```text
CANalyzer_Execute_Command_Type.ctl
```

## 3.3 `CANalyzer_Execute_Command_Result.ctl`

既存field末尾へ追加：

| Field | Type |
|---|---|
| `Session Removed?` | Boolean |

Close Session Result contract：

| Field | Value |
|---|---|
| `Session ID` | `Request.Session ID` |
| `Requested Value` | default |
| `Read Value` | default |
| `Verified?` | False |
| `Session Removed?` | final Registry Remove result |

## 3.4 Actual GUI field labels

正本ではactual `Unbundle By Name` 表示を優先する。

| Concept | Exact GUI label |
|---|---|
| Request command selector | `Execute_Command_Type` |
| Request session | `Session ID` |
| Request timeout | `Measurement Timeout ms` |
| Session state Application ref | `ApplicationRef` |
| Session state ownership | `Application_Ownership` |
| Session state System ref | `System Ref` |
| Session state Measurement ref | `Measurement Ref` |
| Session state started flag | `Measurement Started By LabVIEW?` |
| Result verified | `Verified?` |
| Result session removed | `Session Removed?` |

自然語へ勝手にrenameしない。未確認labelは推測で固定しない。

---

# 4. Public `CANalyzer_Close.vi` Contract

## 4.1 Inputs

| Terminal | Direction | Type | Meaning |
|---|---|---|---|
| `Session ID` | Input | U32 | Close対象Session |
| `Measurement Timeout ms` | Input | U32 | LabVIEW開始Measurementの停止確認timeout |
| `error in` | Input | error cluster | caller primary error |

## 4.2 Outputs

| Terminal | Direction | Type | Meaning |
|---|---|---|---|
| `Session Removed?` | Output | Boolean | Registry finalization result |
| `error out` | Output | error cluster | `Original Error > Close Error` |

## 4.3 Public Error Contract

既存Execute_Commandはincoming error時にdispatcher処理をbypassする。

Closeはcaller errorがあってもcleanupを実行しなければならないため、Public Closeはcaller errorをdispatcherへ直接渡さない。

```text
Original Error = public error in
Execute_Command.error in = No Error
Command = Close Session
Close Error = Execute_Command.error out

if Original Error.status=True:
    public error out = Original Error
else:
    public error out = Close Error
```

優先順位：

```text
Original Error > Close Error
```

初版ではcaller errorが存在するとClose中の追加diagnosticはPublic `error out`へsurfacedしない。documented limitationとする。

---

# 5. Final Internal Algorithm

```text
function CloseSession(Request):
    firstError = NoError
    sequenceError = NoError

    get = Registry.Get(Request.SessionID, sequenceError)
    firstError = FirstErrorWins(firstError, get.error)
    sequenceError = Clear(get.error)

    if get.error:
        firstBeforeRemove = firstError
        sequenceBeforeRemove = sequenceError

    else if not get.found:
        firstError = FirstErrorWins(
            firstError,
            Error(-710102, "CANalyzer_Close.vi / Session Not Found"))
        firstBeforeRemove = firstError
        sequenceBeforeRemove = sequenceError

    else:
        session = get.session

        if session.MeasurementStartedByLabVIEW:
            timeoutIsZero = (Request.MeasurementTimeoutMs == 0)

            if timeoutIsZero:
                firstError = FirstErrorWins(
                    firstError,
                    Error(-710118, "CANalyzer_Close.vi / Invalid Measurement Timeout"))

            stop = StopMeasurement(session.MeasurementRef, sequenceError)
            firstError = FirstErrorWins(firstError, stop.error)
            sequenceError = Clear(stop.error)

            if not timeoutIsZero and not stop.error.status:
                wait = WaitMeasurementState(
                    MeasurementRef=session.MeasurementRef,
                    ExpectedRunning=false,
                    TimeoutMs=Request.MeasurementTimeoutMs,
                    PollIntervalMs=100,
                    errorIn=sequenceError)
                firstError = FirstErrorWins(firstError, wait.error)
                sequenceError = Clear(wait.error)

        closeMeasurement = CloseRef(session.MeasurementRef, sequenceError)
        firstError = FirstErrorWins(firstError, closeMeasurement.error)
        sequenceError = Clear(closeMeasurement.error)

        closeSystem = CloseRef(session.SystemRef, sequenceError)
        firstError = FirstErrorWins(firstError, closeSystem.error)
        sequenceError = Clear(closeSystem.error)

        if session.ApplicationOwnership == LabVIEW:
            quit = QuitApplication(session.ApplicationRef, sequenceError)
            firstError = FirstErrorWins(firstError, quit.error)
            sequenceError = Clear(quit.error)

        closeApplication = CloseRef(session.ApplicationRef, sequenceError)
        firstError = FirstErrorWins(firstError, closeApplication.error)
        sequenceError = Clear(closeApplication.error)

        firstBeforeRemove = firstError
        sequenceBeforeRemove = sequenceError

    remove = Registry.Remove(Request.SessionID, sequenceBeforeRemove)
    firstAfterRemove = FirstErrorWins(firstBeforeRemove, remove.error)

    sessionRemoved =
        (not remove.error.status) and
        remove.found

    if not remove.error.status and not remove.found:
        finalFirstError = FirstErrorWins(
            firstAfterRemove,
            Error(-710102,
                  "CANalyzer_Close.vi / Session Missing During Remove"))
    else:
        finalFirstError = firstAfterRemove

    result.SessionID = Request.SessionID
    result.RequestedValue = default
    result.ReadValue = default
    result.Verified = false
    result.SessionRemoved = sessionRemoved

    return result, finalFirstError
```

---

# 6. Reachable State Matrix

| State | Stop | Wait | ActiveX Ref Cleanup | Quit | Remove | Close Error | Session Removed? |
|---|---:|---:|---:|---:|---:|---|---|
| Registry Get error | No | No | No | No | Yes | Get error | Remove resultによる |
| Get success + Found=False | No | No | No | No | Yes | `-710102 Session Not Found` | Remove resultによる |
| Started=False | No | No | Yes | ownership依存 | Yes | cleanup依存 | Remove resultによる |
| Started=True + Timeout=0 | Yes | No | Yes | ownership依存 | Yes | `-710118`がfirst候補 | Remove resultによる |
| Started=True + Timeout>0 + Stop success | Yes | Yes | Yes | ownership依存 | Yes | action error依存 | Remove resultによる |
| Stop failure | Yes | No | Yes | ownership依存 | Yes | Stop errorがfirst候補 | Remove resultによる |
| Wait failure | Yes | Yes | Yes | ownership依存 | Yes | Wait errorがfirst候補 | Remove resultによる |
| Measurement Ref Close failure | 状態依存 | 状態依存 | System/Appへ続行 | ownership依存 | Yes | Measurement Close errorがfirst候補 | Remove resultによる |
| System Ref Close failure | 状態依存 | 状態依存 | Appへ続行 | ownership依存 | Yes | System Close errorがfirst候補 | Remove resultによる |
| Ownership=LabVIEW | 状態依存 | 状態依存 | Yes | Yes | Yes | Quit error依存 | Remove resultによる |
| Ownership=External | 状態依存 | 状態依存 | Yes | No | Yes | cleanup依存 | Remove resultによる |
| Ownership=Unknown | 状態依存 | 状態依存 | Yes | No | Yes | cleanup依存 | Remove resultによる |
| Quit failure | 状態依存 | 状態依存 | App Ref Close続行 | attempted | Yes | Quit errorがfirst候補 | Remove resultによる |
| Application Ref Close failure | 状態依存 | 状態依存 | attempted | ownership依存 | Yes | App Close errorがfirst候補 | Remove resultによる |
| Remove error | 状態依存 | 状態依存 | 完了/skip済み | ownership依存 | attempted | Remove errorがpriorなしなら採用 | False |
| Remove success + Found=False | 状態依存 | 状態依存 | 完了/skip済み | ownership依存 | success | priorなしなら`-710102 anomaly` | False |
| Remove success + Found=True | 状態依存 | 状態依存 | 完了/skip済み | ownership依存 | success | priorを保持 | True |

---

# 7. First Close Error Priority

候補の到達順：

1. Registry Get error
2. Session Not Found
3. Invalid Measurement Timeout
4. Stop error
5. Wait error
6. Measurement Ref Close error
7. System Ref Close error
8. Quit error
9. Application Ref Close error
10. Registry Remove error
11. Remove Found=False anomaly

priority numberを比較する実装にはしない。各Action後のFirst Error Wins operatorで自然に成立させる。

---

# 8. Detailed LabVIEW GUI Implementation Procedure

本節をClose Session再構築手順の正本とする。Nigel内部UID、Node ID、Wire ID、Tunnel IDは使用しない。

## 8.1 Shared Typedef Amendment

### `CANalyzer_Execute_Command_Type.ctl`

1. enumの既存`Read SysVar`、`Write SysVar`を変更しない。
2. 末尾へ`Close Session`を追加する。
3. ordinalが`0 / 1 / 2`であることを確認する。

### `CANalyzer_Execute_Command_Request.ctl`

1. cluster末尾へNumeric Controlを追加する。
2. Label=`Measurement Timeout ms`。
3. Representation=`U32`。
4. selector label=`Execute_Command_Type`を変更しない。

### `CANalyzer_Execute_Command_Result.ctl`

1. cluster末尾へBooleanを追加する。
2. Label=`Session Removed?`。
3. Default=False。

### Typedef propagation gate

- `CANalyzer_Execute_Command.vi` Broken Run Arrowなし。
- Read / Write callerがbrokenになっていない。
- existing Bundle By Name / Unbundle By Nameが有効。
- Connector Pane不変。

## 8.2 Dispatcher / Request Unpack

1. `CANalyzer_Execute_Command.vi` Block Diagramを開く。
2. incoming-error guardの通常処理側でRequestを`Unbundle By Name`する。
3. `Execute_Command_Type`をdispatcher Case selectorへ接続する。
4. `Close Session` Case内部で主に使用するfieldは`Session ID`と`Measurement Timeout ms`。
5. Read / Write Caseを変更しない。

## 8.3 Initial Error State

Close Session開始時にNo Error clusterを2本用意する。

```text
First Close Error initial = No Error
Cleanup Sequence Error initial = No Error
```

## 8.4 First Close Error Update 共通GUIパターン

Inputs：

| Input | Meaning |
|---|---|
| `Previous First Close Error` | それまでのdiagnostic state |
| `New Action Error` | current action errorまたはlocal error |

GUI操作：

1. `Previous First Close Error`を`Unbundle By Name`へ接続。
2. field=`status`。
3. `status`をCase Structure selectorへ接続。
4. TRUE CaseではPrevious First Close Errorをoutput tunnelへ接続。
5. FALSE CaseではNew Action Errorをoutput tunnelへ接続。
6. Case outputを`Updated First Close Error`として扱う。
7. TRUE/FALSEともoutput tunnelを明示配線し、`Use Default If Unwired`へ依存しない。

このパターンを次で使用する。

- Registry Get
- Session Not Found
- Invalid Timeout
- Stop
- Wait
- Measurement Close
- System Close
- Quit
- Application Close
- Registry Remove
- Remove anomaly

## 8.5 Local Error Construction

local errorはbase No Error cluster + `Bundle By Name(status, code, source)`で作る。

| Event | status | code | source |
|---|---:|---:|---|
| Session Not Found | True | -710102 | `CANalyzer_Close.vi / Session Not Found` |
| Invalid Measurement Timeout | True | -710118 | `CANalyzer_Close.vi / Invalid Measurement Timeout` |
| Session Missing During Remove | True | -710102 | `CANalyzer_Close.vi / Session Missing During Remove` |

## 8.6 Registry Get

`CANalyzer_Session_Registry.vi`を配置する。

| From | To | Type |
|---|---|---|
| `Get` enum constant | `Action` | Registry Action enum |
| `Request.Session ID` | `Session ID` | U32 |
| default `CANalyzer_Session_State` | `Session In` | Session State cluster |
| `Cleanup Sequence Error initial` | `error in` | error cluster |

`Registry Get.error out`は必ず2分岐する。

```text
Registry Get.error out
  ├─→ First Close Error Update
  └─→ Clear Errors → Cleanup Sequence Error after Get
```

## 8.7 Get Error Gate

selector=`Registry Get.error out.status`。

### TRUE

- Get errorをFirst Close Errorとして保持。
- `Session Out`を使用しない。
- Found?を評価しない。
- ActiveX cleanupへ進まない。
- `First Close Error after Get`と`Cleanup Sequence Error after Get`をCommon Remove Mergeへ渡す。

### FALSE

Found? Caseへ進む。

主要output tunnelは両Case明示配線する。

## 8.8 Found? Case

selector=`Registry Get.Found?`。

### FALSE

- `-710102 / CANalyzer_Close.vi / Session Not Found`を生成。
- First Error Winsへ反映。
- ActiveX cleanupしない。
- `First Close Error after Found`と`Cleanup Sequence Error after Found`をCommon Remove Mergeへ渡す。

### TRUE

- `Session Out`をactual Session Stateとして使用。
- ActiveX cleanup pathへ進む。

## 8.9 Measurement Started By LabVIEW? Case

Session Stateのactual GUI label `Measurement Started By LabVIEW?`をselectorへ接続する。

### FALSE

- Stopなし。
- Waitなし。
- First Close Error / Cleanup Sequence Errorをpass。

### TRUE

Timeout Case → Stop → Wait Decisionへ進む。

## 8.10 Timeout Case

selector：

```text
Request.Measurement Timeout ms == U32 0
```

| Output | Timeout=0 TRUE | Timeout>0 FALSE |
|---|---|---|
| `First Close Error after Timeout` | `-710118`をFirst Error Wins反映 | incoming First Close Error pass |
| `Cleanup Sequence Error after Timeout` | incoming Cleanup Sequence Error pass | incoming Cleanup Sequence Error pass |

`-710118`はdiagnostic only。Cleanup Sequence Errorへ入れない。両Caseでsequence tunnelを明示配線する。

## 8.11 Stop Measurement

`CAN_AX_Stop_Measurement.vi`を配置する。

| From | To | Type |
|---|---|---|
| `Measurement Ref` | Measurement Ref | ActiveX Ref |
| `Cleanup Sequence Error after Timeout` | `error in` | error cluster |

`First Close Error`をStop.error inへ接続しない。

Stop.error out：

```text
├─→ First Close Error Update
└─→ Clear Errors → Cleanup Sequence Error after Stop
```

## 8.12 Wait Decision

```text
Wait condition
= NOT Stop.error out.status
  AND NOT TimeoutZero
```

### TRUE

`CANalyzer_Wait_Measurement_State.vi`を実行。

| Terminal | Value / Source |
|---|---|
| Measurement Ref | `Measurement Ref` |
| Expected Running? | False |
| Timeout ms | Request.Measurement Timeout ms |
| Poll Interval ms | U32 100 |
| error in | Cleanup Sequence Error after Stop |

Wait.error out：

```text
├─→ First Close Error Update
└─→ Clear Errors → Cleanup Sequence Error after Wait
```

### FALSE

- Waitなし。
- First Close Error after Stopをpass。
- Cleanup Sequence Error after Stopをpass。

TRUE/FALSE両Caseのoutput tunnelを明示配線する。

## 8.13 Close Measurement Ref

`Close Reference`を配置。

| From | To |
|---|---|
| `Measurement Ref` | reference input |
| Cleanup Sequence Error after Wait Decision | error in |

error out：

```text
├─→ First Close Error Update
└─→ Clear Errors → Cleanup Sequence Error after Measurement Close
```

## 8.14 Close System Ref

2個目の`Close Reference`。

| From | To |
|---|---|
| `System Ref` | reference input |
| Cleanup Sequence Error after Measurement Close | error in |

error out：

```text
├─→ First Close Error Update
└─→ Clear Errors → Cleanup Sequence Error after System Close
```

## 8.15 Application Ownership / Quit

selector=actual GUI label `Application_Ownership`。

### Unknown / External

- Quitなし。
- First Close Error after System Closeをpass。
- Cleanup Sequence Error after System Closeをpass。
- `ApplicationRef`をpass。

### LabVIEW

`CAN_AX_Quit_Application.vi`を配置。

| From | To |
|---|---|
| `ApplicationRef` | `CANalyzer.IApplication10` |
| Cleanup Sequence Error after System Close | error in |

Quit.error out：

```text
├─→ First Close Error Update
└─→ Clear Errors → Cleanup Sequence Error after Ownership
```

全ownership CaseでFirst Close Error / Cleanup Sequence Error / ApplicationRef tunnelを明示配線する。

## 8.16 Close Application Ref

3個目の`Close Reference`。

| From | To |
|---|---|
| `ApplicationRef` | reference input |
| Cleanup Sequence Error after Ownership | error in |

Close Application Ref.error out：

```text
├─→ First Close Error Update
│      Previous = First Close Error after Ownership
│      New      = Close Application Ref.error out
│      Updated  = First Close Error after Application Close
│
└─→ Clear Errors
       ↓
   Cleanup Sequence Error after Application Close
```

Application Close failureでもRegistry Removeを止めない。

## 8.17 Common Remove Merge

Registry Remove直前に3経路を共通後段へmergeする。

共通出力：

```text
First Close Error before Remove
Cleanup Sequence Error before Remove
```

| Path | First Close Error before Remove | Cleanup Sequence Error before Remove |
|---|---|---|
| Get error | First Close Error after Get | Cleanup Sequence Error after Get |
| Found=False | First Close Error after Found | Cleanup Sequence Error after Found |
| Found=True cleanup | First Close Error after Application Close | Cleanup Sequence Error after Application Close |

Get Error Case / Found? Case / Found=True cleanup pathの各経路からCase Structure output tunnelで共通後段へmergeする。

両wireを全pathで明示配線する。`Use Default If Unwired`は禁止。

## 8.18 Registry Remove

`CANalyzer_Session_Registry.vi` Action=Removeを全経路共通の最後へ配置する。

| From | To | Type |
|---|---|---|
| `Remove` constant | `Action` | Registry Action enum |
| Request.Session ID起源値 | `Session ID` | U32 |
| default Session State | `Session In` | Session State cluster |
| `Cleanup Sequence Error before Remove` | `error in` | error cluster |

Remove後にActiveX cleanupを置かない。

Remove error diagnostic update：

| Role | Value |
|---|---|
| Previous | First Close Error before Remove |
| New | Registry Remove.error out |
| Updated | First Close Error after Remove |

## 8.19 Session Removed? / Remove anomaly

`Session Removed?`はraw Registry Remove outputsだけから算出する。

```text
Session Removed?
= NOT Registry Remove.error out.status
  AND Registry Remove.Found?
```

次は使用しない。

- First Close Error after Remove
- Final First Close Error

Remove success + Found=False時：

```text
status = True
code   = -710102
source = CANalyzer_Close.vi / Session Missing During Remove
```

anomaly First Error Update：

| Role | Value |
|---|---|
| Previous | First Close Error after Remove |
| New | Session Missing During Remove local error |
| Updated | Final First Close Error |

## 8.20 Internal Result Build

default `CANalyzer_Execute_Command_Result` cluster constant + Bundle By Nameを使用する。

| Field | Source |
|---|---|
| `Session ID` | Request.Session ID起源値 |
| `Requested Value` | default |
| `Read Value` | default |
| `Verified?` | False |
| `Session Removed?` | final raw Remove result式 |

Result outputへupdated clusterを接続し、error outへFinal First Close Errorを接続する。

## 8.21 Complete Error-Flow Wiring Table

| Action | error in | Diagnostic branch | Sequence branch | Next Action |
|---|---|---|---|---|
| Registry Get | clean initial token | Get.error out → First Error Update | Get.error out → Clear Errors | Get Error Gate |
| Stop | Cleanup Sequence after Timeout | Stop.error out → First Error Update | Stop.error out → Clear Errors | Wait Decision |
| Wait | Cleanup Sequence after Stop | Wait.error out → First Error Update | Wait.error out → Clear Errors | Measurement Close |
| Measurement Close | Cleanup Sequence after Wait Decision | Close error out → First Error Update | Close error out → Clear Errors | System Close |
| System Close | Cleanup Sequence after Measurement Close | Close error out → First Error Update | Close error out → Clear Errors | Ownership |
| Quit | Cleanup Sequence after System Close | Quit.error out → First Error Update | Quit.error out → Clear Errors | Application Close |
| Application Close | Cleanup Sequence after Ownership | App Close.error out → First Error Update | App Close.error out → Clear Errors | Common Remove Merge |
| Registry Remove | Cleanup Sequence before Remove | Remove.error out → First Error Update | finalization終端 | Remove anomaly / Result |

---

# 9. Public `CANalyzer_Close.vi` GUI Procedure

> **Status:** DESIGN FINAL / AS-BUILT CLOSED。Public wrapperのFocused As-Built Re-CheckはP0=0 / P1=0、observable design driftなしでPASS。

## 9.1 Front Panel

| Label | Type | Direction |
|---|---|---|
| `Session ID` | U32 | Control |
| `Measurement Timeout ms` | U32 | Control |
| `error in` | error cluster | Control |
| `Session Removed?` | Boolean | Indicator |
| `error out` | error cluster | Indicator |

Connector Paneは既存Public API patternに合わせ、左に3 inputs、右に2 outputsを配置する。

## 9.2 Original Error保持

`error in` wireをOriginal Errorとして分岐する。

Original ErrorはExecute_Command.error inへ接続しない。

## 9.3 Close Request Build

default `CANalyzer_Execute_Command_Request` cluster + Bundle By Nameを配置する。

| Field | Value |
|---|---|
| `Execute_Command_Type` | `Close Session` |
| `Session ID` | Public Session ID |
| `Measurement Timeout ms` | Public Measurement Timeout ms |

その他fieldはdefault。

## 9.4 Execute_Command Call

Project Explorerから `CANalyzer_Execute_Command.vi` を配置する。

| Terminal | Input |
|---|---|
| Request | built Close Session Request |
| error in | No Error |

caller Original Errorを渡さない。

## 9.5 Session Removed? Output

Execute_Command ResultをUnbundle By Nameし、`Session Removed?`をPublic indicatorへ接続する。

## 9.6 Final Error Merge

Original ErrorをUnbundle By Nameし`status`をCase selectorへ接続する。

### TRUE

Original Error → output tunnel。

### FALSE

Execute_Command.error out → output tunnel。

Case output → Public `error out`。

`Use Default If Unwired`へ依存しない。

---

# 10. As-Built Contract-Equivalent Differences

Internal Close final whole-implementation reviewでobservable design driftは0。

| Design Description | Actual As-Built | Why Equivalent | Observable Semantics |
|---|---|---|---|
| Remove Session IDをRequestから直接配線 | internal result chain経由でRequest起源値をRemoveへ渡す | 値の起点がRequest.Session IDで同一 | Remove対象Session IDは同じ |
| Internal Result.Session IDをRequestから直接Bundle | Request起源値をintermediate chain経由でBundle | reachable stateで値が同一 | Result.Session ID contract同一 |
| First Error Winsを概念上の共通operatorとして記述 | 複数の段階Case Structureで実装 | 各段階がPrevious優先 / New採用を維持 | final diagnostic priority同一 |

構造差を理由に不要なrewireを行わない。observable semanticsが変わる場合だけdesign driftとして扱う。

---

# 11. Static Acceptance Checklist

## 11.1 Shared Typedef

- [x] Read SysVar=0
- [x] Write SysVar=1
- [x] Close Session=2
- [x] Request existing fields不変
- [x] `Execute_Command_Type` label維持
- [x] `Measurement Timeout ms`末尾U32
- [x] Result existing fields不変
- [x] `Session Removed?`末尾Boolean

## 11.2 Internal Close Semantics

- [x] Registry Getが最初のside effect
- [x] Get errorでもRemove attempt
- [x] Found=FalseでもRemove attempt
- [x] Stop ownership=`Measurement Started By LabVIEW?`
- [x] Started=FalseでStop/Waitなし
- [x] Started=True + Timeout=0で-710118
- [x] Timeout=0でもStop
- [x] Timeout=0ではWaitなし
- [x] Timeout CaseでCleanup Sequence Errorを両Case pass
- [x] Stop.error inはCleanup Sequence Error
- [x] Stop failureではWaitなし
- [x] Wait Expected Running=False
- [x] Poll Interval=U32 100
- [x] First Close Error / Cleanup Sequence Error分離
- [x] 全cleanup Action.error outにDiagnostic branchあり
- [x] 全cleanup Action.error outにClear Errors branchあり
- [x] Measurement Ref Close
- [x] System Ref Close
- [x] External / UnknownはQuitしない
- [x] LabVIEW ownershipだけQuit
- [x] Quit failureでもApplication Ref Close
- [x] Application Close errorをdiagnosticへ保持
- [x] Application Close failureでもRemoveへ進む
- [x] Common Remove Mergeで3経路を合流
- [x] Registry Remove.error inはcommon sequence token
- [x] Registry Removeが最後
- [x] Remove errorをfinal diagnosticへ反映
- [x] Remove success + Found=False anomaly
- [x] anomalyはRemove error update後に反映
- [x] `Session Removed? = NOT RemoveError.status AND RemoveFound`
- [x] Session Removed?はFirst Close Errorから独立
- [x] Result.Session ID=Request.Session ID semantics
- [x] Result.Requested Value default
- [x] Result.Read Value default
- [x] Result.Verified?=False
- [x] Result.Session Removed?=final registry result
- [x] Use Default If Unwired依存なし

## 11.3 Read / Write Regression

- [x] Read SysVar Case intact
- [x] Write SysVar Case intact
- [x] incoming-error bypass intact
- [x] existing Bundle By Name valid
- [x] existing Unbundle By Name valid
- [x] observable Read semantics unchanged
- [x] observable Write semantics unchanged

## 11.4 Human Static IDE Check

- [x] Broken Run Arrowなし
- [x] required tunnel unwiredなし
- [x] Use Default If Unwired依存なし
- [x] unintended coercion dotなし
- [x] broken SubVIなし
- [x] broken typedefなし
- [x] Connector Pane問題なし
- [x] `CANalyzer_Execute_Command.vi` Non-reentrant

---

# 12. Internal Review Closure

```text
P0 = 0
P1 = 0
P2 = 0
Observable Design Drift = 0
Contract Equivalent Differences = accepted
State Matrix = PASS
Read / Write Regression = PASS
Human Static IDE Check = PASS
GUI Reconstruction Documentation Gap = 0

CANalyzer_Execute_Command.vi / Close Session
FINAL AS-BUILT REVIEW = PASS
DESIGN INTENT PRESERVED
INTERNAL CLOSE IMPLEMENTATION = CLOSED
GUI RECONSTRUCTION PROCEDURE = COMPLETE
```

---

# 13. Public Wrapper Closure Gate

Public `CANalyzer_Close.vi` Focused As-Built Re-Check：

- [x] Front Panel / Connector Paneが4節契約どおり
- [x] Request.Execute_Command_Type=`Close Session`
- [x] Request.Session ID=Public Session ID
- [x] Request.Measurement Timeout ms=Public input
- [x] Execute_Command.error in=No Error
- [x] caller Original Errorをdispatcherへ渡さない
- [x] Result.Session Removed?をPublicへ返す
- [x] Final Error=`Original Error > Close Error`
- [x] Broken Run Arrowなし
- [x] coercion / unwired tunnel / broken typedefなし
- [x] Public側にActiveX / Registry cleanup logicなし
- [x] 4-state reachable matrixがcontract一致

Review result：

```text
P0 = 0
P1 = 0
Observable Design Drift = 0
Public I/O = PASS
Request Build = PASS
Execute_Command clean call = PASS
Session Removed semantics = PASS
Original Error > Close Error = PASS
Responsibility Boundary = PASS
Reachable State Matrix = PASS

CANalyzer_Close.vi
PUBLIC AS-BUILT REVIEW = PASS
PUBLIC CLOSE IMPLEMENTATION = CLOSED
CANalyzer_Close STATIC IMPLEMENTATION = CLOSED
```

---

# 14. Runtime / Hardware E2E

Static design / As-Built closureとRuntime E2Eを混同しない。

Runtime / Hardwareでは最低限次を確認する。

1. LabVIEW-started MeasurementをCloseするとStop→Running=Falseへ収束する。
2. pre-existing MeasurementはCloseでStopされない。
3. External / Unknown ApplicationはQuitされない。
4. LabVIEW-owned ApplicationだけQuitされる。
5. Close後にRegistry GetするとFound=Falseへ収束する。
6. double CloseはSession Not Foundへ収束する。
7. Stop / Wait / Close / Quit failure injection時も後続cleanupとRemoveが継続する。
8. Read / WriteとCloseの競合がNon-reentrant dispatcherで直列化される。

**Runtime / Hardware E2E = PENDING**。

---

# 15. Authority / Final Status

本書のAuthority：

1. Close Session architecture / lifecycle / error / result contract
2. Shared typedefのClose拡張
3. Internal `CANalyzer_Execute_Command.vi / Close Session` GUI再構築手順
4. Public `CANalyzer_Close.vi` GUI再構築手順
5. As-Built Contract Equivalent差分
6. Static Acceptance / Review Gate

```text
CANalyzer_Close Architecture / Design = FINAL / CLOSED
CANalyzer_Execute_Command Close Session = IMPLEMENTED / AS-BUILT CLOSED
Observable Design Drift = NONE
GUI Reconstruction Procedure = FINAL / COMPLETE
Public CANalyzer_Close.vi = IMPLEMENTED / AS-BUILT CLOSED
CANalyzer_Close Static Implementation = CLOSED
Runtime / Hardware E2E = PENDING
```