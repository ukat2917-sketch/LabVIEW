# 09KA. CANalyzer_Close.vi GUI実装手順

**Status:** FINAL MANUAL IMPLEMENTATION BASELINE  
**Design source:** [`09K_CANalyzer_Close設計.md`](./09K_CANalyzer_Close設計.md)  
**Target:** LabVIEW GUIで第三者が再構築できること  
**Runtime / Hardware E2E:** PENDING

> 本書は作業者がLabVIEW画面で確認できるVI名、SubVI名、Control / Indicator名、cluster field名、Case名、visible terminal名だけで記述する。Nigel等の内部解析UID、node番号、wire番号、tunnel番号は参照キーにしない。
>
> 実装完了後のAs-Built Reviewは本書と09Kを基準に行う。

---

# 0. 実装前の確定事項

## Request selector actual label

Human direct visual confirmation済み。

| Item | Value |
|---|---|
| Field label | `Execute_Command_Type` |
| Field type | `CANalyzer_Execute_Command_Type.ctl` |
| Semantic role | Command selector |
| Close value | `Close Session` |

既存shared typedefの互換性を優先し、`Command`や別名へのrenameは行わない。

> 2026-08-26 correction: 先行版でfield labelを `CANalyzer_Execute_Command_Type` と転記していたが、Front PanelのHuman direct visual evidenceとlocal reflected typeの再確認により、actual field labelは `Execute_Command_Type` と確定した。`CANalyzer_Execute_Command_Type.ctl` はfield type名でありfield labelではない。

## 実装順序

```text
Shared typedef amendment
↓
Read / Write regression check
↓
CANalyzer_Execute_Command.vi / Close Session case
↓
CANalyzer_Close.vi Public wrapper
↓
Compile / Broken Run Arrow check
↓
As-Built Review
```

---

# 1. Shared Typedef Amendment

## CANalyzer_Execute_Command_Type.ctl

Project Explorerから `CANalyzer_Execute_Command_Type.ctl` を開く。

既存項目を変更せず末尾へ追加する。

```text
Read SysVar
Write SysVar
Close Session
```

数値ordinalは次を保持する。

```text
0 Read SysVar
1 Write SysVar
2 Close Session
```

保存後、既存Read / Write caseが同じ名前で表示されることを確認する。

## CANalyzer_Execute_Command_Request.ctl

cluster末尾へ数値Controlを追加する。

| Label | Type |
|---|---|
| `Measurement Timeout ms` | U32 |

既存fieldの名前・型・順序を変更しない。

command selector fieldのactual labelは `Execute_Command_Type` のまま維持する。

## CANalyzer_Execute_Command_Result.ctl

cluster末尾へBooleanを追加する。

| Label | Type |
|---|---|
| `Session Removed?` | Boolean |

保存後、既存Result fieldを変更していないことを確認する。

## Typedef propagation gate

ここで一度停止して確認する。

- `CANalyzer_Execute_Command.vi` にBroken Run Arrowがない。
- 既存Read callerにBroken Run Arrowがない。
- 既存Write callerにBroken Run Arrowがない。
- 既存Bundle By Name / Unbundle By Nameがbrokenになっていない。
- Connector Paneが変わっていない。
- Read / Write既存fieldの型と意味が変わっていない。

問題があればClose実装へ進まない。

---

# 2. Close Session Caseの基本構造

`CANalyzer_Execute_Command.vi` のBlock Diagramを開き、既存dispatcher Case Structureで `Close Session` caseを表示する。

Close Session内部は次の2本を並行して運ぶ。

| Wire | Type | Role |
|---|---|---|
| `First Close Error` | error cluster | 最初のClose errorを保持するdiagnostic state |
| `Cleanup Sequence Error` | error cluster | cleanup実行順序を保証するclean token |

初期値は両方No Error。

## First Close Error更新のGUI共通パターン

このパターンを各Action後で繰り返す。

入力:

- `Previous First Close Error`
- `New Action Error`

配置:

- 名前で束を外す（Unbundle By Name）
- ケースストラクチャ（Case Structure）

配線:

| From | To | Meaning |
|---|---|---|
| `Previous First Close Error` | `Unbundle By Name.status` | 既にerror保持済みか判定 |
| `Previous First Close Error.status` | Case Structure selector | Trueならprevious優先 |
| `Previous First Close Error` | TRUE case output tunnel | 既存errorを保持 |
| `New Action Error` | FALSE case output tunnel | まだerrorがないため新error採用 |
| Case output | `Updated First Close Error` | 次工程へ渡す |

TRUE / FALSEの両Caseでerror cluster output tunnelを明示配線し、`Use Default If Unwired`へ依存しない。

この構造は次の式と同じ。

```text
if Previous.status=True:
    Updated = Previous
else:
    Updated = New Action Error
```

## Cleanup Sequence ErrorのGUI共通パターン

Actionの`error out`を2方向へ分岐する。

```text
Action error out
  ├─→ First Close Error更新のNew Action Error
  └─→ Clear Errors
         ↓
     次Action.error in
```

標準関数:

- エラーをクリア（Clear Errors）

前Actionがerrorでも次Actionをskipしない一方、次Actionは前Action完了後にだけ実行される。

各cleanup actionへ独立したNo Error constantを直接配る構造は禁止する。

---

# 3. Request Unpack

Close Session case内で `Request` clusterを `Unbundle By Name` へ接続する。

最低限取り出すfield:

- `Session ID`
- `Measurement Timeout ms`

`Execute_Command_Type` はdispatcher Case selectorで既にClose Sessionが選択されているため、case内部の処理条件として再判定しない。

---

# 4. Registry Get

Project Explorerから `CANalyzer_Session_Registry.vi` を配置する。

Action enum constantを `Get` にする。

| From | To | Type | Meaning |
|---|---|---|---|
| `Get` constant | Registry `Action` | Action enum | Get実行 |
| `Request.Session ID` | Registry `Session ID` | U32 | target session |
| No Error constant | Registry `error in` | error cluster | 最初のordered token |

出力:

- `Session Out`
- `Found?`
- `error out`

Registry Get `error out`から2本作る。

1. First Close Error更新の`New Action Error`
2. `Clear Errors`を通した`Cleanup Sequence Error after Get`

First Close ErrorのPreviousはNo Error。

---

# 5. Registry Get Error Case

Registry Get `error out.status`を `Unbundle By Name` で取り出し、Case Structure selectorへ接続する。

## TRUE: Get error

- `First Close Error after Get`を保持。
- ActiveX cleanupへ進まない。
- `Session State`はdefault。
- `Session obtained?=False`。
- `Cleanup Sequence Error after Get`をRegistry Remove側へ渡す。

## FALSE: Get success

`Found?`判定へ進む。

主要output tunnel:

| Tunnel | TRUE | FALSE |
|---|---|---|
| First Close Error | First Close Error after Get | First Close Error after Get |
| Cleanup Sequence Error | after Get token | after Get token |
| Session State | default | actual Session Out |
| Session obtained? | False | Found判定結果 |

すべて明示配線する。

---

# 6. Found? Case

Get success branch内でRegistry `Found?` をselectorへ接続する。

## FALSE: Found=False

local error clusterを作る。

```text
status = True
code = -710102
source = CANalyzer_Close.vi / Session Not Found
```

First Close Error更新:

- Previous = First Close Error after Get
- New = local -710102
- Updated = First Close Error after Found

ActiveX cleanupは実行しない。

Cleanup Sequence ErrorはGet後tokenをそのままRegistry Remove側へ渡す。local diagnostic errorをsequence tokenに使わない。

## TRUE: Found=True

- actual Session Stateをsession cleanupへ渡す。
- First Close Errorはそのままpass。
- Cleanup Sequence Error after Getをcleanup開始tokenにする。
- `Session obtained?=True`。

---

# 7. Measurement Started By LabVIEW? Case

Session Stateから `Measurement Started By LabVIEW?` を `Unbundle By Name` で取り出し、Case Structure selectorへ接続する。

`Cached Measuring?`はselectorに使用しない。

## FALSE

- Stopなし。
- Waitなし。
- First Close Errorをpass。
- Cleanup Sequence ErrorをClose Measurementへpass。

## TRUE

Timeout判定へ進む。

---

# 8. Timeout判定

`Request.Measurement Timeout ms` とU32 `0`を `Equal?` で比較し、そのBooleanをCase Structure selectorにする。

## TRUE: Timeout=0

local error cluster:

```text
status = True
code = -710118
source = CANalyzer_Close.vi / Invalid Measurement Timeout
```

First Close Error更新:

- Previous = incoming First Close Error
- New = local -710118
- Updated = First Close Error after Timeout

Cleanup Sequence Errorはlocal errorから作らず、incoming clean tokenをそのままStopへ渡す。

Stopは実行する。Waitは後段でskipする。

## FALSE: Timeout>0

First Close ErrorとCleanup Sequence ErrorをそのままStopへpassする。

StopはTimeout条件に依存しないため、Timeout両branchの後段へ共通Stopを1個置く。

---

# 9. Stop Measurement

Project Explorerから `CAN_AX_Stop_Measurement.vi` を配置する。

| From | To | Type |
|---|---|---|
| `Session State.Measurement Ref` | Stop `Measurement Ref` | ActiveX Ref |
| Timeout Case output Cleanup Sequence Error | Stop `error in` | error cluster |

Stop `error out`を分岐する。

- First Close Error更新のNew Action Error
- `Clear Errors` → `Cleanup Sequence Error after Stop`

First Close Error更新:

- Previous = Timeout Case output First Close Error
- New = Stop error out
- Updated = First Close Error after Stop

---

# 10. Wait Decision

Stop `error out.status`を取り出し、Stop successを作る。

```text
Stop success = NOT Stop error.status
Wait condition = Timeout>0 AND Stop success
```

Wait conditionをCase Structure selectorへ接続する。

## TRUE: Wait実行

Project Explorerから `CANalyzer_Wait_Measurement_State.vi` を配置する。

| Terminal | Value |
|---|---|
| Measurement Ref / `CANalyzer.IMeasurement5` | Session State.Measurement Ref |
| `Expected Running?` | False |
| `Timeout ms` | Request.Measurement Timeout ms |
| `Poll Interval ms` | U32 100 |
| `error in` | Cleanup Sequence Error after Stop |

Wait `error out`をFirst Close Error更新とClear Errorsへ分岐する。

- Previous = First Close Error after Stop
- New = Wait error out
- Updated = First Close Error after Wait
- Sequence = Wait error out → Clear Errors

## FALSE: Wait skip

First Close Error after StopとCleanup Sequence Error after StopをそのままClose Measurementへpassする。

---

# 11. Close Measurement Ref

標準関数 `Close Reference` を配置する。

| From | To |
|---|---|
| Session State.Measurement Ref | reference input |
| Wait Decision output Cleanup Sequence Error | error in |

error outを分岐する。

- First Close Error更新
- Clear Errors → Cleanup Sequence Error after Close Measurement

Previous = Wait Decision output First Close Error。

---

# 12. Close System Ref

2個目の `Close Reference` を配置する。

| From | To |
|---|---|
| Session State.System Ref | reference input |
| Cleanup Sequence Error after Close Measurement | error in |

error out:

- First Close Error更新
- Clear Errors → Cleanup Sequence Error after Close System

Previous = First Close Error after Close Measurement。

---

# 13. Application Ownership / Quit

Session Stateから `Application Ownership` を取り出しCase Structure selectorへ接続する。

Cases:

- `LabVIEW`
- `External`
- `Unknown`

## LabVIEW

Project Explorerから `CAN_AX_Quit_Application.vi` を配置する。

| From | To |
|---|---|
| Session State.Application Ref | `CANalyzer.IApplication10` |
| Cleanup Sequence Error after Close System | error in |

Quit error out:

- First Close Error更新
- Clear Errors → Cleanup Sequence Error after Quit

Previous = First Close Error after Close System。

## External

Quitを置かない。

- First Close Errorをpass。
- Cleanup Sequence Error after Close Systemをpass。

## Unknown

Externalと同じ。

Ownership Caseには最低限次の2本のoutput tunnelを全Case明示配線する。

- First Close Error after Ownership
- Cleanup Sequence Error after Ownership

---

# 14. Close Application Ref

3個目の `Close Reference` をOwnership Caseの後段へ配置する。

| From | To |
|---|---|
| Session State.Application Ref | reference input |
| Cleanup Sequence Error after Ownership | error in |

error out:

- First Close Error更新
- Clear Errors → Cleanup Sequence Error after Close Application

Previous = First Close Error after Ownership。

Quit errorがあってもApplication Ref Closeをskipしない。

---

# 15. Registry Remove

全経路共通の最後へ2個目の `CANalyzer_Session_Registry.vi` を配置する。

Action enum constant = `Remove`。

| From | To | Type |
|---|---|---|
| `Remove` constant | Registry `Action` | Action enum |
| `Request.Session ID` | Registry `Session ID` | U32 |
| branch-final Cleanup Sequence Error | Registry `error in` | error cluster |

branch-final tokenは次のどちらか。

- Get error / Found=False: Registry Get完了後のclean token
- Session cleanup path: Close Application完了後のclean token

したがってRemoveは必ずRegistry Getより後、Session取得時はApplication Closeより後に実行される。

Remove `error out`でFirst Close Errorを更新する。

- Previous = branch-final First Close Error
- New = Remove error out
- Updated = First Close Error after Remove

---

# 16. Remove Result / Session Removed?

Remove `error out.status`を判定する。

## Remove error=True

- `Session Removed?=False`
- First Close Error after Removeを保持

## Remove error=False

Registry `Found?`を判定する。

### Found=True

- `Session Removed?=True`
- First Close Error after Removeを保持

### Found=False

- `Session Removed?=False`

local anomaly error:

```text
status = True
code = -710102
source = CANalyzer_Close.vi / Session Missing During Remove
```

Final First Close Error更新:

- Previous = First Close Error after Remove
- New = local anomaly error
- Updated = Final First Close Error

prior errorがある場合はpriorを保持する。

`Session Removed?=True`はRemove success + Found=Trueのときだけ。

---

# 17. Internal Result Build

Close Session case内にdefault `CANalyzer_Execute_Command_Result` cluster constantと `Bundle By Name` を配置する。

Result contract:

| Field | Value |
|---|---|
| `Session ID` | Request.Session ID |
| `Requested Value` | default |
| `Read Value` | default |
| `Verified?` | False |
| `Session Removed?` | final Session Removed? |

Bundle By Nameで最低限次を設定する。

| From | To |
|---|---|
| default Result cluster | Bundle By Name base |
| Request.Session ID | `Session ID` |
| False | `Verified?` |
| final Session Removed? | `Session Removed?` |

`Requested Value`と`Read Value`はdefault Result clusterをそのまま保持する。

Bundle outputを `CANalyzer_Execute_Command.vi` の `Result`へ接続する。

Final First Close Errorを `CANalyzer_Execute_Command.vi` の `error out`へ接続する。

---

# 18. Public CANalyzer_Close.vi Front Panel

Public `CANalyzer_Close.vi` を作成 / 開く。

Front Panel:

| Label | Type | Direction |
|---|---|---|
| `Session ID` | U32 | Control |
| `Measurement Timeout ms` | U32 | Control |
| `error in` | error cluster | Control |
| `Session Removed?` | Boolean | Indicator |
| `error out` | error cluster | Indicator |

Connector Paneは既存Public API patternに合わせる。

左側:

- Session ID
- Measurement Timeout ms
- error in

右側:

- Session Removed?
- error out

---

# 19. Public Original Error

`error in` wireをOriginal Errorとして保持する。

Feedback Node等は不要。

Original Errorの使用先:

- `Unbundle By Name.status`によるfinal priority判定
- Final Error CaseのTRUE branch

Original Errorを `CANalyzer_Execute_Command.vi.error in`へ接続しない。

---

# 20. Public Close Request Build

Block Diagramへdefault `CANalyzer_Execute_Command_Request` cluster constantと `Bundle By Name` を配置する。

設定:

| Field | Value |
|---|---|
| `Execute_Command_Type` | `Close Session` |
| `Session ID` | Public Session ID |
| `Measurement Timeout ms` | Public Measurement Timeout ms |

その他fieldはdefaultのまま。

配線:

| From | To |
|---|---|
| default Request cluster | Bundle By Name base |
| `Close Session` enum constant | `Execute_Command_Type` |
| Public Session ID | `Session ID` |
| Public Measurement Timeout ms | `Measurement Timeout ms` |
| Bundle output | `CANalyzer_Execute_Command.vi.Request` |

---

# 21. Public Execute_Command Call

Project Explorerから `CANalyzer_Execute_Command.vi` を配置する。

| Terminal | Input |
|---|---|
| Request | built Close Session Request |
| error in | No Error constant |

Original Errorをdispatcherへ渡さない。

これによりcaller errorがあってもClose Sessionを実行する。

---

# 22. Public Session Removed? Output

`CANalyzer_Execute_Command.vi.Result` を `Unbundle By Name`へ接続し、`Session Removed?`を取り出す。

`Result.Session Removed?`をPublic `Session Removed?` indicatorへ接続する。

`Session Removed?=True`はregistry finalization only。cleanup全成功の意味ではない。

---

# 23. Public Final Error Merge

Original Errorを `Unbundle By Name`へ接続し、`status`を取り出す。

`Original Error.status`をCase Structure selectorへ接続する。

## TRUE

Original Errorをoutput tunnelへ接続。

## FALSE

`CANalyzer_Execute_Command.vi.error out`をoutput tunnelへ接続。

Case outputをPublic `error out`へ接続する。

```text
Final Error = Original Error.status ? Original Error : Close Error
```

両Caseでerror cluster tunnelを明示配線し、Use Default If Unwiredは使わない。

---

# 24. Compile / Regression Check

Shared typedefとVI変更後に確認する。

- `CANalyzer_Execute_Command.vi` Broken Run Arrowなし。
- `CANalyzer_Close.vi` Broken Run Arrowなし。
- Read caller Broken Run Arrowなし。
- Write caller Broken Run Arrowなし。
- Connector Pane不変。
- 意図しないcoercion dotなし。
- unwired tunnelなし。
- `Execute_Command_Type` actual field labelを使用。
- Close Session enumは末尾。
- Request `Measurement Timeout ms`は末尾U32。
- Result `Session Removed?`は末尾Boolean。

---

# 25. Human Static Checklist

- [ ] First Close Errorはprevious / new / updatedを全Actionで追跡できる。
- [ ] Cleanup Sequence Errorは各Action完了後のClear Errors出力から次Actionへ流れる。
- [ ] Registry Getより前にRemoveが実行できない。
- [ ] Started=FalseでStop / Waitしない。
- [ ] Timeout=0でもStopする。
- [ ] Stop failure時はWaitしない。
- [ ] Stop / Wait errorでもMeasurement Ref Closeへ進む。
- [ ] Measurement Close後にSystem Close。
- [ ] System Close後にOwnership判定。
- [ ] QuitはLabVIEW ownershipのみ。
- [ ] Quit failureでもApplication Ref Closeへ進む。
- [ ] Application Close後にRegistry Remove。
- [ ] Remove success + Found=TrueのみSession Removed?=True。
- [ ] Result.Session ID=Request.Session ID。
- [ ] Result.Requested Value / Read Valueはdefault。
- [ ] Result.Verified?=False。
- [ ] Public Execute_Command.error in=No Error。
- [ ] Public Original Error > Close Error。
- [ ] consumerのないwireなし。
- [ ] Use Default If Unwired依存なし。
- [ ] Broken Run Arrowなし。

---

# 26. As-Built Review用停止点

Manual Implementationが完了したら、その時点でRuntime / Hardware E2Eへ進まず、まずFocused As-Built Reviewを行う。

Review基準:

1. [`09K_CANalyzer_Close設計.md`](./09K_CANalyzer_Close設計.md)
2. 本書
3. Local actual VI / typedef

重点確認:

- shared typedef append-only変更
- Read / Write regressionなし
- First Close Error priority
- Cleanup Sequence ordering
- timeout / stop / wait reachability
- ownership / Quit
- Remove-last
- Session Removed semantics
- Public clean-error dispatcher call
- Original Error priority

Static reviewでblocking findingがなければRuntime / Hardware E2Eへ進む。
