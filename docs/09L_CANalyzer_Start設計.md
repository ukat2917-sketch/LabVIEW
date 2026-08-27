# 09L. CANalyzer_Start / Execute_Command Start Measurement 最終設計正本

**Status:** FINAL DESIGN / FROZEN / IMPLEMENTATION PENDING  
**Design Review:** P0=0 / P1=0  
**Public `CANalyzer_Start.vi`:** NOT IMPLEMENTED  
**`CANalyzer_Execute_Command.vi / Start Measurement`:** NOT IMPLEMENTED  
**Runtime / Hardware E2E:** PENDING

> 本書を `CANalyzer_Start.vi` と `CANalyzer_Execute_Command.vi / Start Measurement` の設計正本とする。  
> Production StartのPublic I/O、Command拡張、ownership/cache契約、failure policy、error priorityは本書を優先する。  
> `09D_CANalyzer_Execute_Command設計.md` はRead / Write初期Vertical Sliceの正本として残し、Start Measurement追加に関する差分は本書を優先する。  
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

概念フロー：

```text
Public CANalyzer_Start.vi
  ↓ Start Measurement Request
CANalyzer_Execute_Command.vi [Non-reentrant]
  ↓
Registry Get
  ↓
actual Running read
  ↓
Running=True ?
├─ Yes → no-op / ownership preserve / Result Running=True
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
- Start Measurement Request build
- `CANalyzer_Execute_Command.vi` call
- `Result.Measurement Running?` extraction
- standard `error in / error out` pass-through

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

## 2.1 Inputs

| Terminal | Type | Contract |
|---|---|---|
| `Session ID` | U32 | Start対象Session |
| `Measurement Timeout ms` | U32 | Start後Running=True確認timeout |
| `error in` | error cluster | status=TrueではStart commandをbypass |

## 2.2 Outputs

| Terminal | Type | Contract |
|---|---|---|
| `Measurement Running?` | Boolean | 最後に観測できたactual Running状態。actual観測が一度も成立していない場合はFalse |
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

既存末尾`Session Removed?`の後へ追加：

| Field | Type |
|---|---|
| `Measurement Running?` | Boolean |

Start Measurement Result：

| Field | Value |
|---|---|
| `Session ID` | Request.Session ID |
| `Requested Value` | default |
| `Read Value` | default |
| `Verified?` | False |
| `Session Removed?` | False/default |
| `Measurement Running?` | last observed actual Running、未観測ならFalse |

既存Result fieldをStart用の別意味へ流用しない。

---

# 4. Common Error Contract

Startはcleanup APIではない。

```text
error in.status=True
→ existing Execute_Command outer guard
→ Start Measurement Caseを実行しない
→ Result=default
→ error out=original error
```

Closeのような「caller errorでもcleanup実行」の特殊契約はStartへコピーしない。

Public `CANalyzer_Start.vi` はpublic `error in`を通常どおり `CANalyzer_Execute_Command.vi.error in`へ渡す。

---

# 5. Final Start Algorithm

```text
function StartMeasurement(Request, errorIn):
    if errorIn.status:
        return DefaultResult, errorIn

    result = DefaultResult
    result.SessionID = Request.SessionID
    running = false

    get = Registry.Get(Request.SessionID)
    if get.error:
        result.MeasurementRunning = running
        return result, get.error

    if not get.found:
        return result,
            Error(-710102,
                  "CANalyzer_Execute_Command.vi / Session Not Found")

    session = get.session

    initial = GetMeasurementRunning(session.MeasurementRef)
    if initial.error:
        result.MeasurementRunning = running
        return result, initial.error

    running = initial.running
    result.MeasurementRunning = running

    if running:
        // pure no-op path
        // preserve ownership
        // no Registry Update
        return result, NoError

    if Request.MeasurementTimeoutMs == 0:
        return result,
            Error(-710118,
                  "CANalyzer_Execute_Command.vi / Invalid Measurement Timeout")

    start = StartMeasurementInvoke(session.MeasurementRef)
    if start.error:
        return result, start.error

    // Start Invoke success establishes new LabVIEW ownership history.
    ownedState = session
    ownedState.MeasurementStartedByLabVIEW = true
    ownedState.CachedMeasuring = running   // initial actual false

    ownershipUpdate = Registry.Update(
        Request.SessionID,
        ownedState,
        cleanError)

    if ownershipUpdate.error:
        primary = ownershipUpdate.error

        stop = StopMeasurement(session.MeasurementRef, cleanError)
        if not stop.error:
            waitFalse = WaitMeasurementState(
                MeasurementRef=session.MeasurementRef,
                ExpectedRunning=false,
                TimeoutMs=Request.MeasurementTimeoutMs,
                PollIntervalMs=100,
                errorIn=cleanError)
            if waitFalse produced an actual observation:
                running = waitFalse.ActualRunning

        result.MeasurementRunning = running
        return result, primary

    waitTrue = WaitMeasurementState(
        MeasurementRef=session.MeasurementRef,
        ExpectedRunning=true,
        TimeoutMs=Request.MeasurementTimeoutMs,
        PollIntervalMs=100,
        errorIn=cleanError)

    running = waitTrue.ActualRunning
    result.MeasurementRunning = running

    finalState = ownershipUpdate.SessionOut
    finalState.MeasurementStartedByLabVIEW = true
    finalState.CachedMeasuring = running

    cacheUpdate = Registry.Update(
        Request.SessionID,
        finalState,
        cleanError)

    if waitTrue.error:
        return result, waitTrue.error

    if cacheUpdate.error:
        return result, cacheUpdate.error

    return result, NoError
```

上記は機能意味論を示す。GUI実装では既存SubVIのincoming-error behaviorとCase Structureを使って同じobservable semanticsを成立させる。

---

# 6. Validation / State Decision Order

順序固定：

```text
Incoming Error Guard
↓
Registry Get
↓
Found?
↓
Get actual Running
↓
Running=True ?
├─ Yes → success no-op
└─ No
    ↓
    Measurement Timeout ms == 0 ?
    ├─ Yes → -710118 / no Start
    └─ No  → Start
```

Timeout validationをRegistry Getより前へ置かない。

理由：

- Session不存在は`-710102`を優先する。
- TimeoutはStart side effectが必要なbranchでだけ意味を持つ。
- Running=Trueのno-opではTimeout=0でも成功できる。

---

# 7. Initial Running=True No-op Contract

actual Running=TrueならStartしない。

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

Running=Trueだけを理由にFalse→Trueへ変更しない。

`Cached Measuring?` refreshだけのためにRegistry Updateをmandatoryにしない。Final designではno-op pathのRegistry writeはskipする。

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
```

Result `Measurement Running?`はinitial actual observationのFalseを保持する。

---

# 9. Start Ownership Contract

new ownership=Trueの根拠はStart Invoke successだけ。

```text
Start Invoke success
→ Measurement Started By LabVIEW? = True
```

Start Invoke failureでは既存ownershipを変更しない。

Start Invoke successだけを理由に`Cached Measuring?=True`としてはいけない。

ownership-first persist時：

```text
Measurement Started By LabVIEW? = True
Cached Measuring? = Initial actual Running = False
```

これをWaitより先にRegistryへ保存する。

---

# 10. Two-stage Persistence

## Stage 1: ownership persist

Start Invoke success直後、Wait前にRegistry Update。

目的：

- Wait中のfailureでもClose / Stopがownershipを知れるようにする。
- Start済みMeasurementをuntrackedにしない。

## Stage 2: actual cache persist

Wait後：

```text
Measurement Started By LabVIEW? = True
Cached Measuring? = Wait.Actual Running?
```

Wait errorが存在してもcache Updateはclean errorでattemptする。

Wait errorをRegistry Update.error inへ直接渡してbypassさせない。

---

# 11. Ownership Persist Failure Rollback

Start Invoke success後、Stage 1 Registry Updateが失敗した場合はownership tracking failure。

Measurementをそのまま残さない。

```text
Primary Error = Registry Update error
↓
Stop attempt [clean error]
↓
Stop successならWait False [clean error]
Expected Running? = False
Timeout ms = Request.Measurement Timeout ms
Poll Interval ms = 100
```

Final error priority：

```text
Ownership Persist Error > Rollback Error
```

rollback errorでprimaryを上書きしない。

Registry SessionはRemoveしない。

---

# 12. Wait Running=True Failure Policy

Stage 1 ownership persist成功後のWait failureではautomatic Stop rollbackしない。

```text
Start Invoke = success
ownership persist = success
Wait Running=True = error
→ ownership=TrueをRegistryへ残す
→ Actual Running?をResultへ保持
→ cache updateをattempt
→ Wait errorをcallerへ返す
→ automatic Stopなし
```

理由：

- Wait timeoutはStart Invoke failureではない。
- 実MeasurementがRunningになっている可能性がある。
- ownershipが追跡済みなので、後続`CANalyzer_Stop.vi` / `CANalyzer_Close.vi`で安全に停止できる。

Open時のStart failure rollbackとは異なる。OpenはRegistry Create前でSessionが未成立のためrollback ownerになるが、Standalone Startは既存Sessionを利用する。

---

# 13. Final Cache Update Error Policy

Stage 1 ownership persist後なので、Stage 2 cache Update失敗だけではrollback Stopしない。

Error priority：

| Wait | Cache Update | Final Error |
|---|---|---|
| success | success | success |
| success | error | Cache Update error |
| error | success | Wait error |
| error | error | Wait error |

ownershipはStage 1で追跡済み。

---

# 14. Error Priority

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

Stage 1 ownership persist failure後のrollback errorはprimary errorを上書きしない。

---

# 15. Result Semantics

`Measurement Running?`：

> last successfully observed actual Measurement Running state

ルール：

- actual観測が一度も成立していない場合はFalse。
- Initial Running=True no-opではTrue。
- Initial Running=False + Timeout=0ではFalse。
- Start Invoke成功だけを理由にTrueへ推定しない。
- Wait後はWait serviceのactual observationを採用する。
- rollback Wait Falseがactual観測できた場合はその値を採用する。

`Measurement Running?`はownershipではない。

---

# 16. Reachable State Matrix

| Case | Expected |
|---|---|
| incoming error | command bypass / original error / Running=False default |
| Session missing + Timeout=0 | `-710102` / no ActiveX |
| Found + Running=True + Timeout=0 | success no-op / ownership preserve / Running=True |
| Found + Running=False + Timeout=0 | `-710118` / no Start / Running=False |
| Running=True + ownership=False | no Start / ownership remains False / Running=True |
| Running=True + ownership=True | no Start / ownership remains True / Running=True |
| Running=False + Start failure | ownership unchanged / Start error / Running=False last observation |
| Start success + Stage1 persist success + Wait success | ownership=True / cache=True / Running=True / success |
| Start success + Stage1 persist success + Wait timeout + Actual=False | ownership=True / cache=False / Running=False / Wait error / no rollback |
| Start success + Stage1 persist success + Wait timeout + Actual=True | ownership=True / cache=True / Running=True / Wait error / no rollback |
| Start success + Stage1 persist failure + rollback success | primary=Registry Update error / Running=False if confirmed |
| Start success + Stage1 persist failure + rollback failure | primary=Registry Update error / rollback secondary / Running=last observation |
| Wait success + Stage2 cache Update failure | ownership tracked / Running=True / Cache Update error |
| Wait failure + Stage2 cache Update failure | ownership tracked / Running=Wait actual / Wait error |

---

# 17. Regression Contract

Shared typedef変更後も次を固定する。

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

# 18. Static Acceptance Gate

実装後は最低限次を確認する。

## Shared Typedef

- [ ] Read=0 / Write=1 / Close=2 / Start=3
- [ ] Request existing fields不変
- [ ] Result existing fields不変
- [ ] `Measurement Running?`末尾Boolean

## Start Measurement Case

- [ ] incoming error outer guard unchanged
- [ ] Registry GetがStart Case最初のsession side effect
- [ ] Found=False=`-710102`
- [ ] actual RunningをStart要否に使用
- [ ] Cached Measuring?をStart要否に使用しない
- [ ] Running=TrueでStartなし
- [ ] Running=Trueでownership変更なし
- [ ] Running=TrueでRegistry Updateなし
- [ ] Running=False branchだけTimeout検証
- [ ] Timeout=0=`-710118`
- [ ] Timeout source=`CANalyzer_Execute_Command.vi / Invalid Measurement Timeout`
- [ ] Start successだけownership=True
- [ ] ownership-first Registry UpdateはWaitより前
- [ ] Stage1 persist時Cached Measuring?=initial actual False
- [ ] Stage1 failureでrollback Stop attempt
- [ ] Stop successならWait False / Poll=100
- [ ] rollback errorはStage1 errorを上書きしない
- [ ] Stage1 success後Wait True / Poll=100
- [ ] Wait failureでautomatic Stopなし
- [ ] Wait後Actual RunningをResultへ反映
- [ ] Stage2 cache Updateはclean errorでattempt
- [ ] Wait error > Stage2 cache Update error

## Public Start

- [ ] I/O=`Session ID`, `Measurement Timeout ms`, `error in` → `Measurement Running?`, `error out`
- [ ] Request command=`Start Measurement`
- [ ] Request Session ID / Timeout source正しい
- [ ] Public error inをExecute_Commandへ通常接続
- [ ] Result.Measurement Running?をPublicへ返す
- [ ] Public側にRegistry / ActiveX / Wait / ownership logicなし

## Regression

- [ ] Read SysVar intact
- [ ] Write SysVar intact
- [ ] Close Session intact
- [ ] Broken Run Arrowなし
- [ ] broken typedefなし
- [ ] unintended coercion dotなし
- [ ] required tunnel unwiredなし
- [ ] Use Default If Unwired依存なし

---

# 19. Design Freeze Decision

Final Design CandidateのP1指摘だった次を反映済み。

1. Timeout validationを`Registry Get → Found? → actual Running → Running=False branch`へ移動。
2. Initial Running=True no-op pathのRegistry cache Updateをskip。
3. `-710118` sourceをerror生成層`CANalyzer_Execute_Command.vi`へ整合。
4. `Measurement Running?`未観測時default=Falseを明文化。

Final decision：

```text
P0 = 0
P1 = 0
Production Serialization = PRESERVED
Ownership Tracking = PRESERVED
Pre-existing Ownership = PRESERVED
Actual Running Source = PRESERVED
Registry Failure Safety = DEFINED
Wait Failure Policy = DEFINED
Append-only Regression Contract = DEFINED

CANalyzer_Start / Start Measurement
FINAL DESIGN = FROZEN
IMPLEMENTATION = PENDING
RUNTIME / HARDWARE E2E = PENDING
```

---

# 20. Next Gate

次は本書を基準に、LabVIEW GUIで第三者が再構築可能な詳細実装手順を作成する。

実装完了後は本書とのFocused As-Built Reviewを実施し、P0=0 / P1=0、observable design drift=0を確認してStatic ImplementationをCloseする。
