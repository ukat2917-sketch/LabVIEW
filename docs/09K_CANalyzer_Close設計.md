# 09K. CANalyzer_Close / Execute_Command Close Session 最終設計・実装正本

**Status:** FINAL CANONICAL / INTERNAL AS-BUILT CLOSED  
**Design:** FINAL / CLOSED  
**`CANalyzer_Execute_Command.vi / Close Session`:** IMPLEMENTED / AS-BUILT CLOSED  
**Internal Design Drift Review:** P0=0 / P1=0 / P2=0 / observable DESIGN DRIFT=0  
**Human Static Check:** PASS  
**Public `CANalyzer_Close.vi`:** DESIGN FINAL / AS-BUILT REVIEW PENDING  
**Runtime / Hardware E2E:** PENDING  

> 本書を `CANalyzer_Close.vi` と `CANalyzer_Execute_Command.vi / Close Session` の設計思想、契約、LabVIEW GUI実装手順、As-Built差分、Static Acceptanceの**単一正本**とする。  
> 旧 `09KA_CANalyzer_Close実装手順.md` の詳細手順は本書へ統合済みであり、以後の変更は本書へ集約する。  
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

概念フロー：

```text
Public CANalyzer_Close.vi
  ↓ Close Session Request
CANalyzer_Execute_Command.vi  [Non-reentrant]
  ↓
Registry Get
  ↓
Owned Measurement Stop / Wait
  ↓
Reference Cleanup
  ↓
Conditional Application Quit
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

これにより「誰がCloseするか」を一か所へ固定できる。

## 1.3 なぜownershipをSession Stateへ記録するか

Cleanupで最も危険なのは、利用者が手動で開始したMeasurementや既存CANalyzer ApplicationをLabVIEWが勝手に停止・Quitすることである。

Stop source of truth：

```text
Measurement Started By LabVIEW?
```

Quit source of truth：

```text
Application Ownership
```

`Cached Measuring?` はStop ownership判定に使わない。

| Ownership / History | Action |
|---|---|
| Measurement Started By LabVIEW? = False | Stopしない |
| Measurement Started By LabVIEW? = True | Stop attempt |
| Application Ownership = LabVIEW | Quit attempt |
| Application Ownership = External | Quitしない |
| Application Ownership = Unknown | Quitしない |

## 1.4 なぜFirst Close ErrorとCleanup Sequence Errorを分離するか

通常のerror wire一本だけでcleanupを直列接続すると、前段errorにより後続SubVIがbypassされる可能性がある。

一方、各cleanupへ独立したNo Errorを配ると、実行順序が失われる。

そこでClose内部では2本を明確に分離する。

| Wire | Role |
|---|---|
| `First Close Error` | 最初のClose errorを保持するdiagnostic state |
| `Cleanup Sequence Error` | cleanup actionの実行順序だけを保証するclean token |

基本形：

```text
Action.error out
  ├─→ First Close Error update
  └─→ Clear Errors
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

Registry entryはApplication/System/Measurement Refのlifecycle authorityである。

cleanup途中でRegistryから削除すると、後続cleanupでSession Stateへ到達できなくなる。

したがってRemoveは全経路共通の最後にattemptする。

## 1.6 なぜSession Removed?はcleanup成功ではないか

`Session Removed?` は次の意味だけを持つ。

> Registry Removeにより対象Session entryをfinalizeできたか。

Stop / Wait / Ref Close / Quitの全成功を意味しない。

```text
Session Removed?
= NOT RemoveError
  AND RemoveFound
```

cleanup errorが先に発生していても、Remove success + Found=Trueなら `Session Removed?=True` になり得る。

## 1.7 なぜTimeout=0でもStopする場合があるか

`Measurement Timeout ms=0` はStop invocationが不正なのではなく、停止確認Waitの契約が不正である。

Started By LabVIEW=TrueならStopはattemptする。

```text
Started=True + Timeout=0
→ -710118 diagnostic
→ Stop attempt
→ Wait skip
→ cleanup続行
```

Final semantic：

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
- Registry Remove
- First Close Error
- Cleanup Sequence Error
- internal Result build

## 2.2 Public `CANalyzer_Close.vi`

責務：

- Public I/O
- `Close Session` Request build
- caller `error in` を `Original Error` として保持
- Execute_Commandを**clean error**でcall
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

既存fieldの末尾へ追加：

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

`Command`や別名へrenameしない。

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

初版ではcaller errorが存在するとClose中の追加diagnosticはPublic `error out`へsurfacedしない。これはdocumented limitationとする。

---

# 5. Final Internal Algorithm

LabVIEW関数名を除いた機能ロジック：

```text
function CloseSession(Request):
    firstError = NoError
    sequenceError = NoError

    get = Registry.Get(Request.SessionID, sequenceError)
    firstError = FirstErrorWins(firstError, get.error)
    sequenceError = Clear(get.error)

    if get.error:
        sessionObtained = false

    else if not get.found:
        firstError = FirstErrorWins(
            firstError,
            Error(-710102, "CANalyzer_Close.vi / Session Not Found"))
        sessionObtained = false

    else:
        sessionObtained = true
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

            if not timeoutIsZero and not stop.error:
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

    remove = Registry.Remove(Request.SessionID, sequenceError)
    firstError = FirstErrorWins(firstError, remove.error)

    sessionRemoved = (not remove.error.status) and remove.found

    if not remove.error.status and not remove.found:
        firstError = FirstErrorWins(
            firstError,
            Error(-710102,
                  "CANalyzer_Close.vi / Session Missing During Remove"))

    result.SessionID = Request.SessionID
    result.RequestedValue = default
    result.ReadValue = default
    result.Verified = false
    result.SessionRemoved = sessionRemoved

    return result, firstError
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
| Measurement Ref Close failure | ownership条件どおり | ownership条件どおり | System/Appへ続行 | ownership依存 | Yes | Measurement Close errorがfirst候補 | Remove resultによる |
| System Ref Close failure | ownership条件どおり | ownership条件どおり | Appへ続行 | ownership依存 | Yes | System Close errorがfirst候補 | Remove resultによる |
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

本節を再構築手順の正本とする。画面に見えないNigel内部UID、Node ID、Wire ID、Tunnel IDは使用しない。

## 8.1 Shared Typedef Amendment

### `CANalyzer_Execute_Command_Type.ctl`

1. Project Explorerからtypedefを開く。
2. enumの既存`Read SysVar`、`Write SysVar`を変更しない。
3. 末尾へ`Close Session`を追加する。
4. ordinalが`0 / 1 / 2`であることを確認する。
5. 保存する。

### `CANalyzer_Execute_Command_Request.ctl`

1. Request clusterを開く。
2. 既存fieldの順序を記録する。
3. cluster末尾へNumeric Controlを追加する。
4. Label=`Measurement Timeout ms`。
5. Representation=`U32`。
6. selector field label=`Execute_Command_Type`を変更しない。
7. 保存する。

### `CANalyzer_Execute_Command_Result.ctl`

1. Result clusterを開く。
2. 既存fieldを変更しない。
3. cluster末尾へBooleanを追加する。
4. Label=`Session Removed?`。
5. Default=False。
6. 保存する。

### Typedef propagation gate

- `CANalyzer_Execute_Command.vi` Broken Run Arrowなし。
- Read / Write callerがbrokenになっていない。
- existing Bundle By Name / Unbundle By Nameが有効。
- Connector Pane不変。

## 8.2 Close Session Caseを表示する

1. `CANalyzer_Execute_Command.vi` Block Diagramを開く。
2. incoming-error guardの通常処理側にあるdispatcher Case Structureを確認する。
3. Case selectorで`Close Session`を表示する。
4. Read / Write caseを変更しない。

## 8.3 Request Unpack

配置：名前で束を外す（Unbundle By Name）。

| From | To | Type | Meaning |
|---|---|---|---|
| `Request` | Unbundle By Name input | Request cluster | Close request |
| `Request.Session ID` | 後続Registry Session ID | U32 | target session |
| `Request.Measurement Timeout ms` | timeout判定 / Wait | U32 | wait confirmation timeout |

`Execute_Command_Type`はdispatcher selectorで既に消費済みなのでClose内部で再判定しない。

## 8.4 Initial Error State

Close Session開始時に2本のNo Error stateを用意する。

```text
First Close Error initial    = No Error
Cleanup Sequence Error initial = No Error
```

役割を混同しない。

## 8.5 Registry Get

Project Explorerから `CANalyzer_Session_Registry.vi` を配置する。

設定：

| From | To | Type | Meaning |
|---|---|---|---|
| `Get` enum constant | Registry `Action` | Registry Action enum | Get |
| `Request.Session ID` | Registry `Session ID` | U32 | target |
| `Cleanup Sequence Error initial` | Registry `error in` | error cluster | first ordered token |

Registry `error out`を2分岐する。

```text
Registry Get.error out
  ├─→ First Close Error Update
  └─→ Clear Errors → Cleanup Sequence Error after Get
```

## 8.6 First Close Error Update共通パターン

配置：

- 名前で束を外す（Unbundle By Name）
- ケースストラクチャ（Case Structure）

入力：

- Previous First Close Error
- New Action Error

配線：

| From | To | Meaning |
|---|---|---|
| Previous First Close Error | Unbundle By Name | status取得 |
| `status` | Case selector | previous error有無 |
| Previous First Close Error | TRUE Case output | first error保持 |
| New Action Error | FALSE Case output | 新error採用 |

両Caseのoutput tunnelを明示配線する。`Use Default If Unwired`へ依存しない。

## 8.7 Registry Get Error Case

Registry Get `error out.status`をCase selectorへ接続する。

### TRUE: Get error

- First Close Error after Getを保持。
- ActiveX cleanupへ進まない。
- Session State=default。
- Session obtained?=False。
- Cleanup Sequence Error after GetをRemove共通後段へ渡す。

### FALSE: Get success

- `Found?` Caseへ進む。

主要outputは両Case明示配線する。

## 8.8 Found? Case

### FALSE

local error cluster：

```text
status = True
code   = -710102
source = CANalyzer_Close.vi / Session Not Found
```

このlocal errorはFirst Close Errorだけへ入れる。Cleanup Sequence Errorへ入れない。

ActiveX cleanupはskipし、Remove共通後段へ進む。

### TRUE

- Session Outをactual Session Stateとして使用。
- Session obtained?=True。
- First Close ErrorとCleanup Sequence Errorをcleanup pathへ渡す。

## 8.9 Measurement Ownership Case

Session StateをUnbundle By Nameし、`Measurement Started By LabVIEW?`をCase selectorへ接続する。

### FALSE

- Stopなし。
- Waitなし。
- First Close Error / Cleanup Sequence ErrorをClose Measurementへpass。

### TRUE

Timeout判定へ進む。

`Cached Measuring?`をselectorに使用しない。

## 8.10 Timeout Case

配置：等しい?（Equal?）、U32定数0、Case Structure。

```text
Request.Measurement Timeout ms == U32 0
```

### TRUE: Timeout=0

local error：

```text
status = True
code   = -710118
source = CANalyzer_Close.vi / Invalid Measurement Timeout
```

First Close ErrorへFirst Error Winsで反映する。

Cleanup Sequence ErrorはそのままStopへpassする。

### FALSE: Timeout>0

First Close Error / Cleanup Sequence ErrorをそのままStopへpassする。

StopはTimeout両branch共通後段に置く。

## 8.11 Stop Measurement

Project Explorerから `CAN_AX_Stop_Measurement.vi` を配置する。

| From | To | Type |
|---|---|---|
| `Session State.Measurement Ref` | Stop Measurement Ref | ActiveX Ref |
| Timeout Case Cleanup Sequence Error | Stop `error in` | error cluster |

Stop.error out：

```text
├─→ First Close Error update
└─→ Clear Errors → Cleanup Sequence Error after Stop
```

## 8.12 Wait Decision

Stop.error outから`status`を取り出し、NOTでStop successを作る。

```text
Wait condition = Timeout>0 AND Stop success
```

Case selectorへ接続する。

### TRUE

`CANalyzer_Wait_Measurement_State.vi`を配置する。

| Terminal | Value |
|---|---|
| Measurement Ref | `Session State.Measurement Ref` |
| `Expected Running?` | False |
| `Timeout ms` | `Request.Measurement Timeout ms` |
| `Poll Interval ms` | U32 100 |
| `error in` | Cleanup Sequence Error after Stop |

Wait.error outをFirst Error UpdateとClear Errorsへ分岐する。

### FALSE

Waitを置かない。

- First Close Error after Stopをpass。
- Cleanup Sequence Error after Stopをpass。

このFALSEにはTimeout=0とStop failureの両方が入る。

## 8.13 Close Measurement Ref

標準 `Close Reference` を配置する。

| From | To |
|---|---|
| `Session State.Measurement Ref` | reference input |
| Wait Decision Cleanup Sequence Error | error in |

error outをFirst Error UpdateとClear Errorsへ分岐する。

## 8.14 Close System Ref

2個目の `Close Reference`。

| From | To |
|---|---|
| `Session State.System Ref` | reference input |
| Cleanup Sequence Error after Measurement Close | error in |

error outをFirst Error UpdateとClear Errorsへ分岐する。

## 8.15 Application Ownership / Quit

Session State `Application Ownership`をCase selectorへ接続する。

Cases：

```text
LabVIEW
External
Unknown
```

### LabVIEW

`CAN_AX_Quit_Application.vi`を配置する。

| From | To |
|---|---|
| `Session State.Application Ref` | Application Ref |
| Cleanup Sequence Error after System Close | error in |

Quit.error outをFirst Error UpdateとClear Errorsへ分岐する。

### External / Unknown

Quitを置かない。

First Close Error / Cleanup Sequence Errorをそのままpassする。

## 8.16 Close Application Ref

3個目の `Close Reference`。

| From | To |
|---|---|
| `Session State.Application Ref` | reference input |
| Cleanup Sequence Error after Ownership | error in |

Quit errorがあってもApplication Ref Closeへ到達する。

error outをFirst Error UpdateとClear Errorsへ分岐する。

## 8.17 Registry Remove

全経路共通の最後へ `CANalyzer_Session_Registry.vi` を配置する。

| From | To | Type |
|---|---|---|
| `Remove` constant | Registry `Action` | Registry Action enum |
| `Request.Session ID`由来値 | Registry `Session ID` | U32 |
| branch-final Cleanup Sequence Error | Registry `error in` | error cluster |

RemoveはGet error / Found=False / cleanup success / cleanup failureの全経路から到達する。

Remove後にActiveX cleanupを置かない。

Remove.error outをFirst Error Updateへ入れる。

## 8.18 Session Removed? / Remove anomaly

Remove.error out `status`とRemove `Found?`から次を作る。

```text
Session Removed?
= NOT RemoveError.status
  AND RemoveFound
```

Remove success + Found=Falseの場合：

```text
status = True
code   = -710102
source = CANalyzer_Close.vi / Session Missing During Remove
```

このanomaly errorを最後のFirst Error Winsへ入力する。

prior First Close Errorが存在すればpriorを保持する。

## 8.19 Internal Result Build

default `CANalyzer_Execute_Command_Result` cluster + Bundle By Nameを使用する。

| Field | Source |
|---|---|
| `Session ID` | Request.Session ID由来値 |
| `Requested Value` | default clusterのまま |
| `Read Value` | default clusterのまま |
| `Verified?` | False |
| `Session Removed?` | final Session Removed? |

Result出力へBundle結果を接続する。

`error out`へFinal First Close Errorを接続する。

---

# 9. Public `CANalyzer_Close.vi` GUI Procedure

> **Status:** DESIGN FINAL / AS-BUILT REVIEW PENDING。Public wrapper完成後は本節を基準にFocused As-Built Reviewする。

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

次の構造差はContract Equivalentとして承認する。

| Design Description | Actual As-Built | Why Equivalent | Observable Semantics |
|---|---|---|---|
| Remove Session IDをRequestから直接配線 | internal result chain経由でRequest起源値をRemoveへ渡す | 値の起点がRequest.Session IDで同一 | Remove対象Session IDは同じ |
| Internal Result.Session IDをRequestから直接Bundle | Request起源値をintermediate chain経由でBundle | reachable stateで値が同一 | Result.Session ID contract同一 |
| First Error Winsを概念上の共通operatorとして記述 | 複数の段階Case Structureで実装 | 各段階がPrevious優先 / New採用を維持 | final diagnostic priority同一 |

構造差を理由にVIへ不要なrewireを行わない。observable semanticsが変わる場合だけdesign driftとして扱う。

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
- [x] Stop failureではWaitなし
- [x] Wait Expected Running=False
- [x] Poll Interval=U32 100
- [x] First Close Error / Cleanup Sequence Error分離
- [x] action failure後もcleanup継続
- [x] Measurement Ref Close
- [x] System Ref Close
- [x] External / UnknownはQuitしない
- [x] LabVIEW ownershipだけQuit
- [x] Quit failureでもApplication Ref Close
- [x] Registry Removeが最後
- [x] Remove errorをfinal diagnosticへ反映
- [x] Remove success + Found=False anomaly
- [x] `Session Removed? = NOT RemoveError AND RemoveFound`
- [x] Result.Session ID=Request.Session ID semantics
- [x] Result.Requested Value default
- [x] Result.Read Value default
- [x] Result.Verified?=False
- [x] Result.Session Removed?=final registry result

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

Final Whole-Implementation Review + Human Static Check：

```text
P0 = 0
P1 = 0
P2 = 0
Observable Design Drift = 0
Contract Equivalent Differences = accepted
State Matrix = PASS
Read / Write Regression = PASS
Human Static IDE Check = PASS

CANalyzer_Execute_Command.vi / Close Session
FINAL AS-BUILT REVIEW = PASS
DESIGN INTENT PRESERVED
INTERNAL CLOSE IMPLEMENTATION = CLOSED
```

---

# 13. Public Wrapper Closure Gate

Public `CANalyzer_Close.vi` は次を満たした後にAs-Built Closedとする。

- [ ] Front Panel / Connector Paneが4節契約どおり
- [ ] Request.Command=`Close Session`
- [ ] Request.Session ID=Public Session ID
- [ ] Request.Measurement Timeout ms=Public input
- [ ] Execute_Command.error in=No Error
- [ ] caller Original Errorをdispatcherへ渡さない
- [ ] Result.Session Removed?をPublicへ返す
- [ ] Final Error=`Original Error > Close Error`
- [ ] Broken Run Arrowなし
- [ ] coercion / unwired tunnel / broken typedefなし

Public wrapper完成後のReviewも本書を基準とする。

---

# 14. Runtime / Hardware E2E

Static design / internal As-Built closureとRuntime E2Eを混同しない。

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

以後、Close関連の詳細手順を別文書へ複製しない。

```text
CANalyzer_Close Architecture / Design = FINAL / CLOSED
CANalyzer_Execute_Command Close Session = IMPLEMENTED / AS-BUILT CLOSED
Observable Design Drift = NONE
Public CANalyzer_Close.vi = DESIGN FINAL / AS-BUILT REVIEW PENDING
Runtime / Hardware E2E = PENDING
```
