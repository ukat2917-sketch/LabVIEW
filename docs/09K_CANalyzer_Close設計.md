# 09K. CANalyzer_Close.vi Final Design / Review Baseline

**Status:** FINAL / CLOSED  
**Implementation:** PENDING MANUAL IMPLEMENTATION  
**Static design review:** CLOSED  
**GUI construction review:** CLOSED  
**P0:** 0  
**P1:** 0  
**Runtime / Hardware E2E:** PENDING

> 本書は `CANalyzer_Close.vi` と、Closeを実行するための `CANalyzer_Execute_Command.vi / Close Session` 拡張についてのFinal Design正本である。完成後のAs-Built Reviewは本書と [`09KA_CANalyzer_Close実装手順.md`](./09KA_CANalyzer_Close実装手順.md) を基準に行う。
>
> `09D_CANalyzer_Execute_Command設計.md` はRead / Write初期Vertical Sliceの正本として残す。本書で定義するClose Session追加に関するCommand enum / Request / Resultの拡張は、本書を優先する。旧表記は最終統合時に整理する。

---

# 1. 目的

`CANalyzer_Close.vi` は、Registryに保持されたCANalyzer Sessionを安全にterminal化するPublic APIである。

CloseはRead / Writeとの競合を避けるため、Session-bound production APIとして `CANalyzer_Execute_Command.vi` のNon-reentrant境界を通す。

```text
Public CANalyzer_Close.vi
  ↓ Close Session Request
CANalyzer_Execute_Command.vi  [Non-reentrant]
  ↓
Registry Get
  ↓
Owned measurement stop / wait
  ↓
Reference cleanup
  ↓
Conditional Application Quit
  ↓
Registry Remove
  ↓
Result
```

`CANalyzer_Open.vi` はSession ID発行前のbootstrap APIであり、Execute_Commandを通さない。Open自身のNon-reentrant設定で直列化する。

---

# 2. Public I/O

## Inputs

| Terminal | Type | Meaning |
|---|---|---|
| `Session ID` | U32 | Close対象Session |
| `Measurement Timeout ms` | U32 | LabVIEWが開始したMeasurementの停止確認timeout |
| `error in` | error cluster | Caller primary error |

## Outputs

| Terminal | Type | Meaning |
|---|---|---|
| `Session Removed?` | Boolean | Registry Removeにより対象entryが削除されたか |
| `error out` | error cluster | `Original Error > Close Error` の優先規則で返すerror |

`Session Removed?=True` は**registry finalization only**であり、Stop / Wait / Ref Close / Quitの全成功を意味しない。

---

# 3. Public Wrapper Error Contract

Public `error in` は `Original Error` として保存する。

既存 `CANalyzer_Execute_Command.vi` は `error in.status=True` のときCommandをbypassするため、Public Closeはcaller errorをそのままdispatcherへ渡さない。

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

優先順位は固定する。

```text
Original Error > Close Error
```

incoming errorがある場合、Close中の詳細errorはPublic `error out`にはsurfacedしない。初版ではこれをdocumented limitationとし、追加Diagnostics outputは設けない。

---

# 4. Execute_Command Shared Typedef Amendment

## 4.1 Command Enum

`CANalyzer_Execute_Command_Type.ctl` は既存ordinalを変更せず末尾追加する。

```text
0 = Read SysVar
1 = Write SysVar
2 = Close Session
```

## 4.2 Request

`CANalyzer_Execute_Command_Request.ctl` の既存fieldは名前・型・順序・意味を変更しない。

末尾へ追加する。

| Field | Type |
|---|---|
| `Measurement Timeout ms` | U32 |

Human direct visual confirmationにより、command selectorのactual field labelは次である。

```text
CANalyzer_Execute_Command_Type
```

semantic roleはCommand selector。既存shared typedefの互換性を優先し、`Command`へのrenameは行わない。

## 4.3 Result

`CANalyzer_Execute_Command_Result.ctl` の既存fieldを変更せず末尾へ追加する。

| Field | Type |
|---|---|
| `Session Removed?` | Boolean |

Close SessionのResult contract:

| Field | Value |
|---|---|
| `Session ID` | `Request.Session ID` |
| `Requested Value` | default |
| `Read Value` | default |
| `Verified?` | False |
| `Session Removed?` | final Registry Remove result |

---

# 5. Serialization Boundary

Production serialization contract:

| API | Serialization |
|---|---|
| `CANalyzer_Open.vi` | Open自身のNon-reentrant。Execute_Command対象外 |
| Production Read | Execute_Command経由 |
| Production Write | Execute_Command経由 |
| Production Close | Execute_Command経由 |
| PoC / diagnostic wrapper direct-call | Production serialization guarantee対象外 |

Production codeでwrapper直呼びによりdispatcherをbypassしない。

---

# 6. Registry Get Contract

Close Sessionの最初のActionはRegistry Get。

```text
Action = Get
Session ID = Request.Session ID
error in = No Error
```

## Get error

- First Close ErrorへGet errorを保持。
- Session State取得不能のためActiveX cleanupをskip。
- Registry Removeだけは最後にbest-effortでattempt。

## Get success + Found=False

```text
status = True
code = -710102
source = CANalyzer_Close.vi / Session Not Found
```

ActiveX cleanupは実施しない。Registry Removeへ進む。

## Get success + Found=True

Session Stateをcleanup sourceとして使用する。

---

# 7. Measurement Stop Ownership

Stopのsource of truthはSession Stateの次のfieldだけである。

```text
Measurement Started By LabVIEW?
```

`Cached Measuring?` をStop ownership判定には使用しない。

| Started By LabVIEW? | Stop |
|---|---|
| False | 実行しない |
| True | attempt |

既存MeasurementをLabVIEWが開始していない場合は、Cached状態がMeasuringでもStopしない。

---

# 8. Timeout Contract

## Started=False

`Measurement Timeout ms=0`を許容。Stop / Waitは使用しない。

## Started=True + Timeout>0

```text
Stop
↓
Stop successなら Wait Measurement State
Expected Running? = False
Poll Interval ms = U32 100
Timeout ms = Request.Measurement Timeout ms
```

## Started=True + Timeout=0

```text
status = True
code = -710118
source = CANalyzer_Close.vi / Invalid Measurement Timeout
```

ただしStopはattemptし、Waitはskipする。その後のcleanupとRegistry Removeは継続する。

Final semantic:

> `Measurement Timeout ms = 0` is an invalid wait-confirmation contract, not an invalid stop-invocation contract.

---

# 9. Cleanup Order

Session State取得成功時の順序を固定する。

```text
optional Stop
↓
optional Wait False
↓
Close Measurement Ref
↓
Close System Ref
↓
if Application Ownership == LabVIEW:
    Quit Application
else:
    no Quit
↓
Close Application Ref
↓
Registry Remove
```

Application Ownership:

| Ownership | Quit |
|---|---|
| LabVIEW | attempt |
| External | Never |
| Unknown | Never |

Configuration rollbackは行わない。

pre-cleanup Ref validity probeは初版で追加しない。実際のStop / Quit / Close Reference errorからfailureを観測する。

---

# 10. Two-Error-Flow Model

Close Session内部では2本のerror flowを分離する。

## 10.1 First Close Error

診断保持用state。

```text
Previous Close Error = P
New Action Error = A

if P.status=True:
    Updated = P
else:
    Updated = A
```

**First Close Error Wins**。

## 10.2 Cleanup Sequence Error

実行順序専用のclean token。

```text
Previous Action.error out
  ├─→ First Close Error update
  └─→ Clear Errors
         ↓
     Next Action.error in
```

これにより、前Action完了後に次Actionを実行しつつ、前Actionがerrorでも後続cleanupをskipしない。

各cleanup actionへ独立したNo Error constantをばら撒いて順序を失わせる構造は禁止する。

---

# 11. Registry Remove Contract

Registry Removeは全経路共通の最後にattemptする。

```text
Action = Remove
Session ID = Request.Session ID
error in = cleanup sequence token
```

Get error / Found=False / Session cleanup success or failureのすべてがRemoveへ到達する。

## Remove result

| Remove error | Found? | Session Removed? | Close Error |
|---|---|---|---|
| True | any | False | prior errorがなければRemove error |
| False | True | True | prior First Close Errorを保持 |
| False | False | False | prior errorがなければlocal -710102 |

Remove success + Found=Falseのlocal anomaly:

```text
status = True
code = -710102
source = CANalyzer_Close.vi / Session Missing During Remove
```

prior First Close Errorがある場合はpriorを保持する。

Remove success後、そのSession IDはterminal。cleanup retryとして同じSession IDを再利用する契約は持たない。

---

# 12. First Close Error Priority

内部Close Errorの候補順:

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

実際の保持規則は候補順をhard-codeするのではなく、各ActionでFirst Error Wins operatorを適用する。

Publicではさらに:

```text
Original Error > Close Error
```

---

# 13. Production Result Semantics

`Session Removed?` は次でのみTrue。

```text
Registry Remove attempted
AND
Remove error.status=False
AND
Remove Found?=True
```

Result Build到達時はRemove attempted=Trueがinvariantなので、reachable stateでは次へ簡約可能。

```text
Session Removed? = NOT RemoveError AND RemoveFound
```

Close cleanupの成否とは独立である。

---

# 14. Compatibility / Regression Gate

Shared typedef amendment後、最低限次を確認する。

- `Read SysVar=0`, `Write SysVar=1`, `Close Session=2`。
- Request既存fieldの名前・型・順序・意味が不変。
- Result既存fieldの名前・型・順序・意味が不変。
- `CANalyzer_Execute_Command.vi` Broken Run Arrowなし。
- 既存Read caller / Write caller Broken Run Arrowなし。
- 既存Bundle By Name / Unbundle By Nameが有効。
- Read behavior不変。
- Write behavior不変。
- Read / Writeは従来どおりincoming error時にdispatcher bypass。
- Public CloseはOriginal Errorを保存し、clean errorでdispatcherを呼ぶ。

---

# 15. Static Acceptance Matrix

| Case | Expected |
|---|---|
| Get error | ActiveX cleanupなし、Remove attempt、Get error保持 |
| Get Found=False | -710102、ActiveX cleanupなし、Remove attempt |
| Started=False | Stop/Waitなし、Ref cleanup |
| Started=True + Timeout=0 | -710118保持、Stopあり、Waitなし、cleanup継続 |
| Started=True + Timeout>0 + Stop success | Wait False実行 |
| Started=True + Stop failure | Waitなし、後続cleanup継続 |
| Ownership=LabVIEW | Quit attempt |
| Ownership=External | Quitしない |
| Ownership=Unknown | Quitしない |
| Cleanup action failure | first error保持、後続cleanup継続 |
| Remove success + Found=True | Session Removed?=True |
| Remove error | Session Removed?=False |
| Remove success + Found=False | Session Removed?=False、必要なら-710102 |
| Original Error present + Close success | Close実行、public error out=Original Error |
| Original Error present + Close failure | Close実行、public error out=Original Error |
| concurrent Read / Write vs Close | Execute_Command境界で直列化 |
| double Close | 2回目はSession Not Foundへ収束 |

---

# 16. As-Built Review Baseline

完成後のReviewは次を基準にする。

1. 本書 `09K_CANalyzer_Close設計.md`
2. `09KA_CANalyzer_Close実装手順.md`
3. 実際のLocal VI / typedef

判定原則:

- Designと同じobservable semanticsなら構造差はContract Equivalentとして許容。
- 同じreachable stateでoutput / error / ownership / side effectが変わる場合は差分。
- VI側が誤りならVI修正。
- As-Builtの方が合理的かつContract Equivalentなら、理由を明記して資料側を更新。
- silent driftは禁止。

---

# 17. Closure

Final Design ReviewとGUI Construction Reviewのblocking findingはCLOSED。

```text
P0 = 0
P1 = 0
P2 = 0

CANalyzer_Close.vi
FINAL DESIGN = CLOSED
READY FOR MANUAL IMPLEMENTATION
```

Runtime / Hardware E2Eは実装後に別途実施する。
