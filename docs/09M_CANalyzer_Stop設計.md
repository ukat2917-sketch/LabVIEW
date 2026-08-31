# 09M. CANalyzer_Stop / Execute_Command Stop Measurement 最終設計・As-Built正本

**最終更新日：2026-08-31**  
**Status:** FINAL CANONICAL / STATIC IMPLEMENTATION CLOSED  
**Design Review:** P0=0 / P1=0  
**Observable Design Ambiguity:** 0  
**Observable Design Drift:** 0  
**`CANalyzer_Execute_Command.vi / Stop Measurement`:** IMPLEMENTED / AS-BUILT CLOSED  
**Public `CANalyzer_Stop.vi`:** IMPLEMENTED / AS-BUILT CLOSED  
**Internal Final Model Confirmation:** PASS  
**Public Final Model Confirmation:** PASS  
**Internal GUI Reconstruction Procedure:** FINAL / AS-BUILT  
**Public GUI Reconstruction Procedure:** FINAL / AS-BUILT  
**Documentation Gap:** 0  
**Human Static Gate:** PASS  
**Runtime / Hardware E2E:** PENDING

> 本書を `CANalyzer_Stop.vi` と `CANalyzer_Execute_Command.vi / Stop Measurement` の設計、Frozen Algorithm、状態遷移、error priority、最終actual wiring、GUI再構築手順、Static Closureの単一正本とする。  
> Session Registry契約は `09B_CANalyzer_Session_Registry設計.md`、Close cleanup契約は `09K_CANalyzer_Close設計.md`、Start契約は `09L_CANalyzer_Start設計.md`、AI協調開発プロセスは `00D_AI協調LabVIEW設計実装レビュープロセス.md` を参照する。

---

# 0. Closure Summary

```text
CANalyzer_Stop

P0 = 0
P1 = 0
Observable Design Ambiguity = 0
Observable Design Drift = 0

Internal Stop Measurement
= IMPLEMENTED / AS-BUILT CLOSED

Public CANalyzer_Stop.vi
= IMPLEMENTED / AS-BUILT CLOSED

Internal Final Model Confirmation = PASS
Public Final Model Confirmation = PASS
Internal Final As-Built GUI Reconstruction = PASS
Public Final As-Built GUI Reconstruction = PASS
Documentation Gap = 0
Human Static Gate = PASS

DESIGN ALGORITHM = ACTUAL WIRING
STATIC IMPLEMENTATION = CLOSED

Runtime / Hardware E2E = PENDING
```

Human Static Gateでは、Public `CANalyzer_Stop.vi` のconnector paneを `CANalyzer_Start.vi` と目視比較し、5端子のvisual assignmentが同一であることを確認済み。machine-readable `conIdx` も `11 / 10 / 8 / 3 / 0` で一致している。

`STATIC IMPLEMENTATION CLOSED`はRuntime動作確認済みを意味しない。CANalyzer実機、Configuration、Measurement、TestStandを含むRuntime / Hardware E2Eは未実施であり、引き続きPENDINGとする。

---

# 1. Terminology Contract

Stop設計では次の3概念を分離する。

| 正式用語 | Session State field | 意味 |
|---|---|---|
| **Application Ownership** | `Application_Ownership` | CANalyzer Application自体の起動・所有関係 |
| **Measurement Start Ownership / Start History** | `Measurement Started By LabVIEW?` | MeasurementをLabVIEWが開始した履歴、cleanup authorityの根拠 |
| **Running Cache** | `Cached Measuring?` | 最後に有効観測したMeasurement Runningのcache |

単独の `ownership` という語は、どのstateを指すか曖昧になるため原則使用しない。

Standalone Stopは `Application_Ownership` を変更しない。valid actual False observation時に変更され得るのは `Measurement Started By LabVIEW?` と `Cached Measuring?` である。

---

# 2. 目的 / Responsibility Boundary

既存Sessionに紐づくCANalyzer Measurementを、Productionの直列化境界を守りながら明示的にStopし、actual `Measurement.Running` の観測結果に基づいてSession Stateを安全に収束させる。

設計目標：

1. Production Stopを `CANalyzer_Execute_Command.vi` のNon-reentrant境界へ通す。
2. Standalone Stopをnormal operational APIとして扱う。
3. Stop authorityはPublic Stopの明示callに与え、`Measurement Started By LabVIEW?`をauthorization gateにしない。
4. Stop要否はactual `Measurement.Running`で判断し、Running Cacheをtruth sourceにしない。
5. valid actual False observation時だけStart HistoryをFalseへclearする。
6. Running Cacheはvalid actual observationに基づいて更新する。
7. Stop Invoke errorやunverified Wait error時はstate mutationを最小化する。
8. Public APIへActiveX Ref、Session State、Application Ownership、Start History、Running Cache logicを露出しない。

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
    ├─ Timeout -710104 → last valid actual state update
    └─ Other Wait Error → no Registry Update / preserve state
```

## 2.1 Public `CANalyzer_Stop.vi`

担当：Public I/O、Stop Request build、`CANalyzer_Execute_Command.vi` call、`Result.Measurement Running?` extraction、direct error flow。

担当しない：Registry、ActiveX、Measurement Ref、Wait、Application Ownership、Start History、Running Cache、timeout validation、local error生成、Close-style special error merge。

## 2.2 Internal `CANalyzer_Execute_Command.vi / Stop Measurement`

担当：Session Get / Found、actual Running read、Stop要否、timeout validation、Stop Invoke、Wait、observation validity分類、Start History / Running Cache transition、Registry Update、Result、error priority。

---

# 3. Public API / Shared Typedef Contract

## Public Inputs

| Terminal | Type | Contract |
|---|---|---|
| `Session ID` | U32 | Stop対象Session |
| `Measurement Timeout ms` | U32 | Running=False確認timeout |
| `error in` | error cluster | status=TrueではExecute_Command outer guardがbypass |

## Public Outputs

| Terminal | Type | Contract |
|---|---|---|
| `Measurement Running?` | Boolean | last valid actual Running。未観測ならFalse |
| `error out` | error cluster | Stop command final error |

Public connector pane final actual：`Session ID=11`, `Measurement Timeout ms=10`, `error in=8`, `Measurement Running?=3`, `error out=0`。

## `CANalyzer_Execute_Command_Type.ctl`

```text
0 = Read SysVar
1 = Write SysVar
2 = Close Session
3 = Start Measurement
4 = Stop Measurement
```

Stopはappend-only。

## Request / Result

`CANalyzer_Execute_Command_Request.ctl`：**NO AMENDMENT**。Stopでは `Execute_Command_Type`, `Session ID`, `Measurement Timeout ms` のみ使用し、その他fieldはdefault preserve。

`CANalyzer_Execute_Command_Result.ctl`：**NO AMENDMENT**。既存 `Measurement Running?` を使用する。

---

# 4. Common Error / Base Result / Stop Authority

Stopはcleanup APIではない。

```text
error in.status=True
→ existing Execute_Command outer guard
→ Stop Caseを実行しない
→ Result=Default Result
→ error out=original incoming error
```

Stop Case entry：

```text
default Result
+ Session ID = Request.Session ID
+ Measurement Running? = False
```

Standalone authorityは **Explicit Stop Always Authorized**。`Measurement Started By LabVIEW?` はStandalone Stopのauthorization gateに使用しない。

| Actual Running | Measurement Started By LabVIEW? | Standalone Stop |
|---:|---:|---|
| False | False | physical Stop不要 |
| False | True | physical Stop不要 |
| True | False | Stop可 |
| True | True | Stop可 |

Closeのcleanupでは既存のStart History契約を維持する。

---

# 5. Frozen Final Stop Algorithm

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
    update = Registry.Update(Request.SessionID, healed, NoError)
    result.MeasurementRunning = false
    return result, update.error

if Request.MeasurementTimeoutMs == 0:
    result.MeasurementRunning = true
    return result,
        Error(-710118,
              "CANalyzer_Execute_Command.vi / Invalid Measurement Timeout")

stop = StopMeasurementInvoke(get.SessionOut.MeasurementRef, NoError)
if stop.error:
    result.MeasurementRunning = true
    return result, stop.error

wait = WaitMeasurementState(
    MeasurementRef = get.SessionOut.MeasurementRef,
    ExpectedRunning = false,
    TimeoutMs = Request.MeasurementTimeoutMs,
    PollIntervalMs = 100,
    errorIn = NoError)

if wait.error.status == false:
    finalState = get.SessionOut
    finalState.MeasurementStartedByLabVIEW = false
    finalState.CachedMeasuring = false
    update = Registry.Update(Request.SessionID, finalState, NoError)
    result.MeasurementRunning = false
    return result, update.error

if wait.error.code == -710104:
    finalState = get.SessionOut
    if wait.ActualRunning == false:
        finalState.MeasurementStartedByLabVIEW = false
        finalState.CachedMeasuring = false
    else:
        finalState.MeasurementStartedByLabVIEW = preserve
        finalState.CachedMeasuring = true
    update = Registry.Update(Request.SessionID, finalState, NoError)
    result.MeasurementRunning = wait.ActualRunning
    return result, original wait.error

// Other Wait Error W2
// Registry Updateなし
// Application Ownership / Start History / Running Cache preserve
result.MeasurementRunning = true
return result, wait.error
```

final actual wiringのexact node / wire sourceは後述As-Built Reconstructionを正とする。

---

# 6. Path Contracts

## Registry / Found

Registry Get first。Found=Falseは `status=True`, `code=-710102`, `source="CANalyzer_Execute_Command.vi / Session Not Found"`。Found=FalseではGet Running / Timeout / Stop / Wait / Updateへ進まない。

## Actual Running

truth source：`Session Out.Measurement Ref → CAN_AX_Get_Measurement_Running.vi → Running`。Running CacheをStop decisionに使用しない。

Get Running errorではStop / Wait / Updateなし、Result Running=False、Final Error=Get Running.error。

## Initial Running=False Self-Heal

```text
Application_Ownership = preserve
Measurement Started By LabVIEW? = False target
Cached Measuring? = False target
Registry Action = Update
Registry error in = No Error
Result Running = False
Final Error = Registry Update.error
```

Timeout / Stop / Waitなし。

## Timeout=0

Initial Running=Trueだけで評価。`-710118`, source `CANalyzer_Execute_Command.vi / Invalid Measurement Timeout`。Stop / Wait / Updateなし。Result Running=True。

## Stop Invoke Error A1

Waitなし、Updateなし、state mutationなし、Result Running=True、Final Error=Stop.error。

## Wait

`Expected Running?=False`, `Timeout=Request.Measurement Timeout ms`, `Poll Interval ms=U32 100`。

3-class：

| Class | Outcome | Observation | Update |
|---|---|---|---|
| 1 | Success | VALID False | Yes |
| 2 | `-710104` timeout | VALID LAST OBSERVATION | Yes |
| 3 | Other Wait Error | INVALID for new state | No |

Wait Success：Application Ownership preserve、Start History=False target、Running Cache=False target、Result False、Final Error=Update.error。

Timeout Actual=False：Application Ownership preserve、Start History=False target、Running Cache=False target、Update Yes、Result False、Final Error=original Wait.error。

Timeout Actual=True：Application Ownership preserve、Start History preserve target、Running Cache=True target、Update Yes、Result True、Final Error=original Wait.error。

Other Wait Error W2：Updateなし、state mutationなし、Result True、Final Error=Wait.error。

---

# 7. Registry Update / Error Priority / Result Semantics

| Path | Update? | Update error in | Final Error |
|---|---:|---|---|
| Initial False | Yes | No Error | Update.error / No Error |
| Wait Success | Yes | No Error | Update.error / No Error |
| Wait Timeout | Yes | No Error | original Wait timeout |
| Other Wait Error | No | n/a | Wait.error |
| Stop Error | No | n/a | Stop.error |
| Timeout=0 | No | n/a | -710118 |

到達順：incoming error → Registry Get → -710102 → Get Running → -710118 → Stop → Wait → path-dependent Update。

`Measurement Running?` はlast valid actual Running。actual observation前のfailureはFalse default。

---

# 8. Final Reachable State Matrix

| Scenario | Stop | Wait | Update | Application Ownership After | Measurement Started By LabVIEW? Target | Cached Measuring? Target | Persistence | Result Running | Final Error |
|---|---:|---:|---:|---|---|---|---|---:|---|
| incoming error | No | No | No | preserve | preserve | preserve | n/a | False | incoming error |
| Registry error | No | No | No | unknown | unknown | unknown | n/a | False | Registry.error |
| Session missing | No | No | No | no state | no state | no state | n/a | False | -710102 |
| Get Running error | No | No | No | preserve | preserve | preserve | unchanged | False | Get Running.error |
| Initial False | No | No | Yes | preserve | False target | False target | if Update success | False | Update.error / No Error |
| Initial True Timeout=0 | No | No | No | preserve | preserve | preserve | unchanged | True | -710118 |
| Stop error | Yes | No | No | preserve | preserve | preserve | unchanged | True | Stop.error |
| Wait Success | Yes | Yes | Yes | preserve | False target | False target | if Update success | False | Update.error / No Error |
| Timeout Actual=False | Yes | Yes | Yes | preserve | False target | False target | if Update success | False | original Wait.error |
| Timeout Actual=True | Yes | Yes | Yes | preserve | preserve target | True target | if Update success | True | original Wait.error |
| Other Wait Error W2 | Yes | Yes | No | preserve | preserve | preserve | unchanged | True | Wait.error |

Update failure時はtarget stateとpersisted stateを混同しない。

---

# 9. Public `CANalyzer_Stop.vi` Frozen / As-Built Contract

```text
default CANalyzer_Execute_Command_Request
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

public error in → Execute_Command.error in DIRECT
Execute_Command.error out → public error out DIRECT
```

Public側にRegistry / ActiveX / Wait / Session State / Application Ownership / Start History / Running Cache / timeout validation / local error / Case / Select / Merge Errors / Clear Errorsを追加しない。

---

# 10. Serialization / Regression Contract

```text
Read SysVar       = 0
Write SysVar      = 1
Close Session     = 2
Start Measurement = 3
Stop Measurement  = 4
```

Request / Result既存field、incoming-error outer guard、Read / Write / Close / Start、Start public wrapper、Close cleanup semanticsを変更しない。Final reviewでregressionなしを確認済み。

---

# 11. Internal FINAL AS-BUILT GUI Reconstruction

**Status:** FINAL / AS-BUILT  
**Final Model Confirmation:** PASS  
**P0=0 / P1=0 / Documentation Gap=0**

完成後のcurrent actual `CANalyzer_Execute_Command.vi / Stop Measurement` をfresh確認した再構築情報。UIDは補助情報であり、field / terminal / selector / source-to-destinationを優先する。

## 11.1 Actual Case Topology

| Stage | Actual structure / node |
|---|---|
| Base Result | `Result 2` constant `11672` → `Bundle By Name 8421` |
| Registry Get | `CANalyzer_Session_Registry.vi 8444`, Action `Get` |
| Registry error gate | Case `8502`, selector `8489.status` |
| Found gate | Case `8582`, selector `8444.Found?` |
| Get Actual Running | `CAN_AX_Get_Measurement_Running.vi 8778` |
| Get Running error gate | Case `8841`, selector `9762.status` |
| Initial Running split | Case `8948`, selector `8899.value` |
| Timeout split | `Equal? 9050` → Case `9065` |
| Stop Invoke | `CAN_AX_Stop_Measurement.vi 10145` |
| Stop error gate | Case `10210`, selector `10201.status` |
| Wait | `CANalyzer_Wait_Measurement_State.vi 10374` |
| Wait success/error | Case `6063`, selector `6062.status` |
| Timeout vs W2 | `Equal? 10787` → Case `12249` |
| Timeout Actual split | Case `8381`, selector `20648.value` |

## 11.2 Case / Tunnel Table

| Case Structure | Selector | Case label | Result output | Error output | Session State output |
|---|---|---|---|---|---|
| `8502` | `8489.status` | FALSE / TRUE | `8538 / 8533` | `8531 / 8539` | `8570 / 8571` |
| `8582` | `8444.Found?` | FALSE / TRUE | `8632 / 8629` | `8605 / 8607` | `8652 / 8653` |
| `8841` | `9762.status` | FALSE / TRUE | `8905 / 8907` | `8893 / 8895` | `8938 / 8939` |
| `8948` | `8899.value` | FALSE / TRUE | `8977 / 8980` | `8970 / 8975` | `9024 / 9027` |
| `9065` | `9050.x = y?` | FALSE / TRUE | `9109 / 9108` | `9094 / 9100` | `9156 / 9152` |
| `10210` | `10201.status` | FALSE / TRUE | `10222 / 10227` | `10248 / 10252` | `12376 / 12372` |
| `6063` | `6062.status` | FALSE / TRUE | `18386` | `19198` | case-local |
| `12249` | `10787.x = y?` | FALSE / TRUE | `18271` | `19217` | `18777` |
| `8381` | `20648.value` | FALSE / TRUE | `18289` | `13484` | `18801` |

Audited pathでは `Use Default If Unwired` 依存なし。

## 11.3 Complete Internal Wiring Table

| # | Source | Source Terminal | Destination | Destination Terminal | Type | Meaning |
|---|---|---|---|---|---|---|
| 1 | `11672` | value | `8421` | input cluster | result cluster | base result |
| 2 | `8385` | value | `8421` | Session ID | U32 | request session ID |
| 3 | `11653` | value | `8421` | Measurement Running? | bool | default false |
| 4 | `11626` | value | `8444` | Action | enum | Registry Get |
| 5 | `8385` | value | `8444` | Session ID | U32 | lookup target |
| 6 | `11416` | value | `8444` | Session In | session state | default state |
| 7 | `11286` | value | `8444` | エラー入力 | error cluster | No Error |
| 8 | `8444` | エラー出力 | `8489` | input cluster | error cluster | Registry error gate |
| 9 | `8444` | Found? | `8582` | selector | bool | Found gate |
| 10 | `8623` | value | `8822` | input cluster | session state | Session Out |
| 11 | `8822` | Measurement Ref | `8778` | Measurement Ref | ActiveX ref | actual Running |
| 12 | `8600` | value | `8778` | エラー入力 | error cluster | success path |
| 13 | `8778` | Running | `8899` | value | bool | Initial Running selector |
| 14 | `8778` | エラー出力 | `9762` | input cluster | error cluster | Get Running error gate |
| 15 | `9023` | value | `7664` | input cluster | session state | self-heal base |
| 16 | `11969` | value | `7664` | Measurement Started By LabVIEW? | bool | False target |
| 17 | `12146` | value | `7664` | Cached Measuring? | bool | False target |
| 18 | `14072` | value | `12744` | Action | enum | Update |
| 19 | `15409` | Session ID | `12744` | Session ID | U32 | update ID |
| 20 | `7664` | output cluster | `12744` | Session In | session state | self-healed state |
| 21 | `13016` | value | `12744` | エラー入力 | error cluster | No Error |
| 22 | `13724` | value | `13377` | Measurement Running? | bool | result false |
| 23 | `8990` | value | `9050` | x | U32 | timeout |
| 24 | `9040` | value | `9050` | y | U32 | zero |
| 25 | `9469` | value | `9515` | status | bool | invalid timeout |
| 26 | `9483` | value | `9515` | code | I32 | -710118 |
| 27 | `9501` | value | `9515` | source | string | invalid timeout source |
| 28 | `8567` | value | `10192` | input cluster | session state | stop base |
| 29 | `10192` | Measurement Ref | `10145` | Measurement Ref | ActiveX ref | Stop invoke |
| 30 | `10090` | value | `10145` | エラー入力 | error cluster | No Error |
| 31 | `10266` | value | `10374` | CANalyzer.IMeasurement5 | ActiveX ref | Wait Measurement Ref |
| 32 | `10290` | value | `10374` | Expected Running? | bool | False |
| 33 | `10271` | value | `10374` | Timeout ms | U32 | request timeout |
| 34 | `10311` | value | `10374` | エラー入力 | error cluster | No Error |
| 35 | `10361` | value | `10374` | Poll Interval ms | U32 | 100 |
| 36 | `6062` | status | `6063` | selector | bool | Wait success/error |
| 37 | `11099` | value | `10787` | x | I32 | Wait error code |
| 38 | `11246` | value | `10787` | y | I32 | -710104 |
| 39 | `10787` | x = y? | `12249` | selector | bool | timeout vs W2 |
| 40 | `12515` | value | `12613` | input cluster | session state | Wait success base |
| 41 | `13005` | value | `12613` | Measurement Started By LabVIEW? | bool | False target |
| 42 | `13110` | value | `12613` | Cached Measuring? | bool | False target |
| 43 | `14567` | value | `14463` | Action | enum | Update |
| 44 | `15587` | Session ID | `14463` | Session ID | U32 | update ID |
| 45 | `12613` | output cluster | `14463` | Session In | session state | Wait success state |
| 46 | `14513` | value | `14463` | エラー入力 | error cluster | No Error |
| 47 | `12455` | value | `12332` | input cluster | error cluster | original Wait error base |
| 48 | `12757` | value | `12332` | status | bool | timeout status |
| 49 | `12973` | value | `12332` | code | I32 | -710104 |
| 50 | `13976` | value | `14078` | input cluster | session state | timeout False base |
| 51 | `14587` | value | `14078` | Measurement Started By LabVIEW? | bool | False target |
| 52 | `14682` | value | `14078` | Cached Measuring? | bool | False target |
| 53 | `14990` | value | `14784` | Action | enum | Update |
| 54 | `15323` | Session ID | `14784` | Session ID | U32 | update ID |
| 55 | `14078` | output cluster | `14784` | Session In | session state | timeout False state |
| 56 | `15589` | value | `14784` | エラー入力 | error cluster | No Error |
| 57 | `16449` | value | `16194` | Measurement Running? | bool | result false |
| 58 | `13979` | value | `17107` | input cluster | session state | timeout True base |
| 59 | `17440` | value | `17107` | Cached Measuring? | bool | True target |
| 60 | `16913` | value | `16714` | Action | enum | Update |
| 61 | `17107` | output cluster | `16714` | Session In | session state | timeout True state |
| 62 | `17693` | value | `16714` | エラー入力 | error cluster | No Error |
| 63 | `18083` | value | `17827` | Measurement Running? | bool | result true |
| 64 | `19747` | value | `19477` | Measurement Running? | bool | W2 result true |

## 11.4 GUI Construction Order

1. Command enumとStop Caseを確認。
2. Base Result。
3. Registry Get。
4. Registry error gate。
5. Found gate。
6. Measurement Ref → Get Actual Running。
7. Get Running error gate。
8. Initial Running Case。
9. FALSE側Self-Heal Update。
10. TRUE側Timeout compare。
11. Timeout=0 local error。
12. Stop Invoke。
13. Stop error gate。
14. Stop success側Wait。
15. Wait.status classification。
16. Wait Success dedicated Update。
17. Wait.code == -710104 classification。
18. W2。
19. Timeout branch Actual Running? Case。
20. Timeout Actual=False persist。
21. Timeout Actual=True persist。
22. Final Result / Error tunnel収束。
23. required tunnel総点検。
24. Read / Write / Close / Start regression確認。

---

# 12. Public FINAL MODEL CONFIRMATION / FINAL AS-BUILT GUI Reconstruction

**PUBLIC FINAL MODEL CONFIRMATION = PASS**  
**P0=0 / P1=0**  
**PUBLIC DESIGN ALGORITHM = ACTUAL WIRING**  
**GUI Reconstruction Procedure = FINAL / AS-BUILT**  
**Documentation Gap=0**  
**Human Static Gate=PASS**

## 12.1 Construction Strategy / Path

Final actualは `CANalyzer_Start.vi` と同系統のthin wrapper。再構築時はStartをSave Asし、typed command enumだけ `Start Measurement → Stop Measurement` に変更する方法を推奨する。元Startを上書きしない。

```text
C:\LabVIEW work\SVS_AutoTestSystem\60_CAN\30_Public\CANalyzer_Stop.vi
```

## 12.2 Front Panel / Connector Pane

| Name | Direction | Type | conIdx |
|---|---|---|---:|
| `Session ID` | Input | U32 | 11 |
| `Measurement Timeout ms` | Input | U32 | 10 |
| `error in` | Input | error cluster | 8 |
| `Measurement Running?` | Output | Boolean | 3 |
| `error out` | Output | error cluster | 0 |

exact visual placementはHumanがStartと比較し、同一を確認済み。

## 12.3 Required Nodes

| Actual node | 日本語名 | English name | Type | 用途 |
|---|---|---|---|---|
| `551` | 定数 | Constant | `CANalyzer_Execute_Command_Request` | request seed |
| `854` | 列挙型定数 | Enum Constant | `CANalyzer_Execute_Command_Type` | typed Stop command |
| `807` | 名前で束ねる | Bundle By Name | request cluster | Request build |
| `938` | サブVI | `CANalyzer_Execute_Command.vi` | subVI | serialized command |
| `1084` | 名前で取り出す | Unbundle By Name | result cluster | Running extraction |

## 12.4 Request / Result / Error

`Bundle By Name 807`：`Execute_Command_Type ← 854 Stop Measurement`, `Session ID ← 49`, `Measurement Timeout ms ← 102`, other fields default preserve。

`938.Request ← 807.output cluster`。

Public `error in 204 → 938.エラー入力` direct。No Error constant / Case / Selectなし。

`938.Result → 1084 → Measurement Running? → 166` direct。

`938.エラー出力 → error out 311` direct。Merge / Clear / original-error restoreなし。

## 12.5 Complete Public Wiring Table

| # | Source | Source Terminal | Destination | Destination Terminal | Type | Meaning |
|---|---|---|---|---|---|---|
| 1 | `551` | value | `807` | input cluster | request cluster | default Request |
| 2 | `854` | value | `807` | Execute_Command_Type | enum | Stop Measurement |
| 3 | `49` | value | `807` | Session ID | U32 | public Session ID |
| 4 | `102` | value | `807` | Measurement Timeout ms | U32 | public timeout |
| 5 | `807` | output cluster | `938` | Request | request cluster | Stop Request |
| 6 | `204` | value | `938` | エラー入力 (エラーなし) | error cluster | direct error in |
| 7 | `938` | Result | `1084` | input cluster | result cluster | Execute Result |
| 8 | `1084` | Measurement Running? | `166` | value | Boolean | public Running |
| 9 | `938` | エラー出力 | `311` | value | error cluster | direct error out |

## 12.6 Forbidden Public Logic

Registry、ActiveX、Wait、Session State、Application Ownership、Start History、Running Cache、Timeout==0、`-710118` / `-710102`生成、Case、Loop、Select、Clear Errors、Merge Errorsを置かない。

---

# 13. Static Acceptance / Human Static Gate

## Internal

- [x] enum Read=0 / Write=1 / Close=2 / Start=3 / Stop=4
- [x] Request / Result amendmentなし
- [x] Base Result exact
- [x] Registry Get first
- [x] Found=False=-710102
- [x] actual Running truth source
- [x] Initial False self-heal only
- [x] Timeout=0=-710118, no Stop/Wait/Update
- [x] Stop error A1
- [x] Wait Expected=False / Poll=100 U32
- [x] Wait status → code 3-class classification
- [x] Wait Success dedicated Update
- [x] Timeout False final error=original Wait.error
- [x] Timeout True Action=Update / Cached=True
- [x] W2 no Update / no mutation
- [x] Application Ownership never written by Stop Case
- [x] all required tunnels explicit
- [x] Use Default If Unwired依存なし

## Public

- [x] Public I/O exact
- [x] typed Stop Measurement
- [x] direct error in
- [x] direct Result.Measurement Running?
- [x] direct error out
- [x] forbidden internal logicなし
- [x] connector `conIdx`一致
- [x] connector visual placement Human確認済み

## IDE / Regression

- [x] Read / Write / Close / Start intact
- [x] Broken Run Arrowなし
- [x] broken typedefなし
- [x] unintended coercion dotなし
- [x] required tunnel unwiredなし

---

# 14. Final Closure Record

```text
CANalyzer_Stop
FINAL DESIGN REVIEW = PASS

P0 = 0
P1 = 0
Observable Design Ambiguity = 0
Observable Design Drift = 0
Regression Risk = 0

Internal Stop Measurement
FINAL MODEL CONFIRMATION = PASS
FINAL AS-BUILT GUI RECONSTRUCTION = PASS
DOCUMENTATION GAP = 0
STATIC IMPLEMENTATION = CLOSED

Public CANalyzer_Stop.vi
FINAL MODEL CONFIRMATION = PASS
FINAL AS-BUILT GUI RECONSTRUCTION = PASS
DOCUMENTATION GAP = 0
HUMAN CONNECTOR PANE CHECK = PASS
STATIC IMPLEMENTATION = CLOSED

DESIGN ALGORITHM = ACTUAL WIRING
CANalyzer_Stop Overall = STATIC IMPLEMENTATION CLOSED

Runtime / Hardware E2E = PENDING
```

以降、設計変更が必要になった場合は `00D_AI協調LabVIEW設計実装レビュープロセス.md` に従い、Design Change Candidate → Human Approval → Re-Freezeを経る。Runtime / Hardware確認結果はStatic Closureと分離して追記する。