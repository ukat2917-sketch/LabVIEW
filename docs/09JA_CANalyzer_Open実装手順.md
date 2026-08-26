# 09JA. CANalyzer_Open.vi 実装・再構築手順

**最終整理日：2026-08-26**

> **本章の役割**：`CANalyzer_Open.vi` を、LabVIEW GUI上で第三者が再構築できる粒度で説明する作業手順の正本。
>
> Final semantic contractは [`09J_CANalyzer_Open設計.md`](./09J_CANalyzer_Open設計.md) を正とし、本章は「何を、どこへ、どう配線するか」を扱う。
>
> 本章ではNigel AIの内部解析番号、内部wire番号、内部node番号を一切使用しない。作業者がLabVIEW画面で確認できるControl / Indicator名、SubVI名、端子名、Case名、定数値だけで記述する。

---

## 完成状態

`CANalyzer_Open.vi` は `60_CAN\30_Public` のSession bootstrap Public APIである。

```text
Incoming Error Guard
→ Public Input Validation
→ Launch / Detect / Application Open
→ Ownership Resolution
→ Compatibility Phase 1
→ Optional Configuration Open
→ Configuration Verify
→ Compatibility Phase 2
→ Policy
→ Final System / Measurement Ref Acquisition
→ Initial Running Read
→ Optional Measurement Start / Wait
→ Session State Build
→ Registry Create
→ Success

任意のOperation Failure
→ Best-effort Rollback / Cleanup
→ Operation Error > Cleanup Error
```

As-Built確認状態：

| 項目 | 状態 |
|---|---|
| Design | FINAL / CLOSED |
| Implementation | COMPLETE |
| Static Model Check | CLOSED |
| Human Non-reentrant Check | PASS |
| Human Broken Run Arrow Check | PASS |
| Human Typedef Direct Check | PASS |
| P0 | 0 |
| P1 | 0 |
| Runtime / Hardware E2E | PENDING |

---

## 作業時の重要ルール

- Nigel AI内部の内部解析番号を探さない。
- 配線先は、この文書に記載する画面表示名で探す。
- 既存SubVIのconnector paneは、対象PCの実VIを `Ctrl+H` で確認し、存在しない端子名を推測しない。
- `Use default if unwired` に依存せず、主要出力は全Caseで明示配線する。
- Boolean式やCaseの形が本書の図示と異なっても、全reachable stateで同じ結果ならsemantic contractを優先する。
- ActiveX RefはRegistry Create成功まではOpen側が所有し、Registry Create成功後だけSessionへ所有権を移す。
- Cleanupは前段errorで止めない。各cleanup actionはclean error inputから実行する。

---

## Public I/O

### Front Panel Controls

左側へ次のControlを配置する。

| 契約名 | 現行GUIで見える名前の例 | 型 | Default | 用途 |
|---|---|---|---|---|
| `Launch Mode` | `CANalyzer_Launch_Mode` | `CANalyzer_Launch_Mode.ctl` | `Require Existing` | 起動戦略 |
| `Process Name Candidates` | `Process Name Candidates` | 1D String Array | `[]` | Process Detect候補 |
| `Configuration Path` | `Configuration Path` | Path | empty | Expected Configuration |
| `Open Configuration?` | `Open Configuration?` | Boolean | False | 指定cfgをOpenするか |
| `Start Measurement?` | `Start Measurement?` | Boolean | False | Measurement Start要求 |
| `Measurement Timeout ms` | `Measurement Timeout ms` | U32 | 0 | Start/Wait timeout |
| `Compatibility Policy` | `policy` | `CANalyzer_Compatibility_Policy.ctl` | `Require Compatible` | Phase2 statusの受入Policy |
| `error in` | `エラー入力 (エラーなし)` | error cluster | No Error | caller error |

`Startup Timeout ms` は作成しない。

### Front Panel Indicators

右側へ次のIndicatorを配置する。

| 契約名 | 現行GUIで見える名前の例 | 型 | 用途 |
|---|---|---|---|
| `Session ID` | `Session ID` | U32 | Registry発行ID |
| `Version String` | `Version String` | String | Phase2 Version |
| `Actual Configuration Path` | `Actual Configuration Path` | Path | Verify actual path |
| `Application Ownership` | `CANalyzer_Application_Ownership` | `CANalyzer_Application_Ownership.ctl` | Quit可否 |
| `Measurement Started By LabVIEW?` | 同名 | Boolean | Start Invoke成功履歴 |
| `Running?` | `Running?` | Boolean | 最後に観測したRunning |
| `Compatibility Status` | `CANalyzer_Compatibility_Status` | `CANalyzer_Compatibility_Status.ctl` | Phase2 final status |
| `error out` | `エラー出力` | error cluster | 最終error |

Current As-Builtに内部確認用Indicatorがある場合、次はConnector Paneへ割り当てない。

- `Application Ref Current`
- `App Ref Acquired?`
- `System Ref current`
- `Measurement Ref current`
- `System Ref Acquired?`
- `Measurement Ref Acquired?`

これらはデバッグ補助でありPublic Contractではない。

### Connector Pane

Public Connector Paneへは8 inputs / 8 outputsだけを割り当てる。ActiveX Refとacquired flagは公開しない。

---

## VI Properties

`VI Properties → Execution` で **Non-reentrant** にする。

確認済みのHuman Gate：

- Reentrant executionは無効。
- Broken Run Arrowなし。
- `CANalyzer_Compatibility_Policy.ctl` は `Require Compatible / Allow Warning / Allow Unknown` の順。

---

## 配置する主な関数・SubVI

| 画面で探す名前 | 種別 / 配置方法 | 用途 |
|---|---|---|
| ケースストラクチャ（Case Structure） | プログラミング → ストラクチャ | 入力ガード、Launch、Policy、Start、Cleanup |
| 名前でバンドル解除（Unbundle By Name） | プログラミング → クラスタ、クラス、バリアント | error.status取得 |
| 名前でバンドル（Bundle By Name） | プログラミング → クラスタ、クラス、バリアント | Session cluster / local error生成 |
| Path To String | Quick Dropで`Path To String` | Public PathをService用Stringへ変換 |
| Trim Whitespace | Quick Dropで`Trim Whitespace` | Path入力の前後空白除去 |
| 空文字列/パス判定（Empty String/Path?） | Quick Dropで`Empty String/Path?` | empty path判定 |
| 等しい?（Equal?） | プログラミング → 比較 | Timeout=0判定等 |
| 否定（Not） | プログラミング → ブール | `NOT Initial Running` |
| AND | プログラミング → ブール | Start needed判定 |
| String To Path | Quick Dropで`String To Path` | Verify actual StringをPublic Pathへ変換 |
| Format Into String | プログラミング → 文字列 | Policy reject source |
| Clear Errors | Quick Dropで`Clear Errors` | advisory error / cleanup error chain分離 |
| Close Reference | 接続 → ActiveX、またはQuick Drop | acquired ActiveX Refの解放 |
| `CANalyzer_Detect_Process.vi` | `60_CAN\20_Service` | Process Detect |
| `CAN_AX_Open_Application.vi` | `60_CAN\10_ActiveX_Wrapper` | Application Ref取得 |
| `CANalyzer_Check_Compatibility.vi` | `60_CAN\20_Service` | Phase1 / Phase2 |
| `CAN_AX_Open_Configuration.vi` | `60_CAN\10_ActiveX_Wrapper` | optional cfg Open |
| `CANalyzer_Verify_Configuration.vi` | `60_CAN\20_Service` | cfg一致確認 |
| `CAN_AX_Get_System.vi` | `60_CAN\10_ActiveX_Wrapper` | final System Ref |
| `CAN_AX_Get_Measurement.vi` | `60_CAN\10_ActiveX_Wrapper` | final Measurement Ref |
| `CAN_AX_Get_Measurement_Running.vi` | `60_CAN\10_ActiveX_Wrapper` | Initial Running |
| `CAN_AX_Start_Measurement.vi` | `60_CAN\10_ActiveX_Wrapper` | Start |
| `CANalyzer_Wait_Measurement_State.vi` | `60_CAN\20_Service` | Running state待ち |
| `CANalyzer_Session_Registry.vi` | `60_CAN\20_Service` | Session Create |
| `CAN_AX_Stop_Measurement.vi` | `60_CAN\10_ActiveX_Wrapper` | rollback Stop |
| `CAN_AX_Quit_Application.vi` | `60_CAN\10_ActiveX_Wrapper` | LabVIEW-owned App Quit |

パレット位置が環境で見つからない場合は `Ctrl + Space` で英語名を検索する。SubVIはProject上の実ファイルを配置する。

---

## 最外周 Incoming Error Guard

`error in`を`Unbundle By Name`へ接続し、`status`を最外周Case Structureのselectorへ接続する。

### error in.status = True

ActiveX / Detect / Compatibility / Registryを実行しない。次を明示出力する。

| Output | Value |
|---|---|
| Session ID | 0 |
| Version String | `""` |
| Actual Configuration Path | default Path |
| Application Ownership | Unknown |
| Measurement Started By LabVIEW? | False |
| Running? | False |
| Compatibility Status | Unknown |
| error out | original error in |

### error in.status = False

Public input validationへ進む。

---

## Configuration Path Validation

この検証は**すべてのActiveX side effectより前**に置く。

配線：

```text
Configuration Path
→ Path To String
→ Trim Whitespace
→ Empty String/Path?
→ Case Structure
```

empty / whitespace-onlyの場合は`Bundle By Name`で次のerrorを作る。

```text
status = True
code   = -710116
source = CANalyzer_Open.vi / Invalid Expected Configuration Path
```

このCaseではDetect / Automation Openへ進まない。

relative path検証、file existence検証、拡張子検証、`.` / `..` 解決はこのVIへ追加しない。

---

## Measurement Timeout Validation

この検証も**Detect / Automation Openより前**に置く。

期待真理値：

| Start Measurement? | Measurement Timeout ms | 結果 |
|---|---:|---|
| False | 0 | Valid |
| False | >0 | Valid |
| True | 0 | Invalid |
| True | >0 | Valid |

`Start Measurement?=True AND Measurement Timeout ms=0` の場合：

```text
status = True
code   = -710118
source = CANalyzer_Open.vi / Invalid Measurement Timeout
```

このCaseでもActiveX side effectへ進まない。

LabVIEW上では、`Start Measurement?`をCase selectorとしてTrue Caseだけで`Measurement Timeout ms == 0`を判定してもよいし、Boolean式で同じ真理値を作ってもよい。reachable behaviorが同一なら契約等価である。

---

## Launch Mode Case Structure

`Launch Mode`をCase Structure selectorへ接続し、次の3 Caseを作る。

- `Require Existing`
- `Reuse Existing Or Launch`
- `Force New Instance`

各Caseから最低限、次を共通トンネルへ出す。

- launch/open後のOperation Error
- resolved Application Ownership
- Application Ref
- App Ref Acquired?

`App Ref Acquired?` はAutomation Openが成功し、有効なApplication RefをOpen側が所有した時だけTrueにする。

---

## Require Existing

### Process Detect

`CANalyzer_Detect_Process.vi`へ次を配線する。

| SubVI terminal | Source |
|---|---|
| `Process Name Candidates` | Public Control |
| error input | validation後のcurrent error |

Detect `error out`のstatusをCase selectorへ接続する。

### Detect error

Detect mechanism errorはfatal。

- Automation Openを呼ばない。
- Detectの元errorをそのままOperation Errorへ出す。
- Ownership=Unknown。
- App Ref=empty。
- App Ref Acquired?=False。

### Detect成功、Found?=False

Automation Openを呼ばず、次のerrorを生成する。

```text
status = True
code   = -710109
source = CANalyzer_Open.vi / Required Existing Process Not Found
```

Ownership=Unknown、App Ref=empty、App Ref Acquired?=False。

### Detect成功、Found?=True

`CAN_AX_Open_Application.vi`を配置し、次を配線する。

| Terminal | Source |
|---|---|
| Application class/ref constant input | empty `CANalyzer.IApplication10` typed ref constant |
| `Open New Instance?` | False |
| error input | Detect success error wire |

Automation Open成功時：

- Ownership=`External`
- Application Ref=wrapper output
- App Ref Acquired?=True

Automation Open failure時：

- wrapper / ActiveX original errorを保持
- `-710100`へ強制変換しない
- App Ref Acquired?は実際の取得成否に従う

---

## Reuse Existing Or Launch

このCaseは「pre detect → open → 必要な場合だけpost detect」の順に組む。

### Pre Detect

`CANalyzer_Detect_Process.vi`へProcess Name Candidatesとcurrent errorを接続する。

### Pre Detect error

Pre Detect errorはadvisory。

- Detect errorをOperation Errorへ残したままAutomation Openをskipさせない。
- `Clear Errors`でAutomation Open用のerror chainをNo Errorへ戻す。
- `CAN_AX_Open_Application.vi`へ`Open New Instance?=False`を渡す。
- Open成功後のOwnershipは`Unknown`。
- Pre Detectが失敗しているためPost Detectは実行しない。
- Open failureならそのwrapper / ActiveX errorをOperation Errorとして返す。

### Pre Detect成功、Found?=True

- `Open New Instance?=False`
- Automation Openを実行
- Open成功ならOwnership=`External`
- Post Detectは実行しない

### Pre Detect成功、Found?=False

Automation Openを`Open New Instance?=False`で実行する。

Open failureなら元wrapper errorを保持し、Post Detectへ進まない。

Open成功後だけOwnership推定用Post Detectを実行する。

Post Detectはadvisoryなので、Open成功error chainとは分離する。Post Detect用にはclean errorを渡す。

| Post Detect結果 | Ownership | Operation Error |
|---|---|---|
| success + Found=True | LabVIEW | Automation Open successのNo Errorを維持 |
| success + Found=False | Unknown | No Errorを維持 |
| detect error | Unknown | Post Detect errorはadvisoryとして隔離し、No Errorを維持 |

Post Detect errorをPublic `error out`へfatal errorとして流さない。

---

## Force New Instance

Process Detectは配置しない。

`CAN_AX_Open_Application.vi`へ：

| Terminal | Source |
|---|---|
| Application class/ref constant | empty `CANalyzer.IApplication10` typed ref constant |
| `Open New Instance?` | True |
| error input | current error |

Automation Open成功後も、初版のApplication Ownershipは **Unknown** とする。

理由：`open new instance=True`と「このProcessを安全にLabVIEW-ownedと断定できること」は同義ではなく、runtime evidence取得前はQuit安全側へ倒すため。

- Ownership=Unknown
- App Ref Acquired?=Open成功時True
- CleanupではQuitしない
- Application RefのClose Referenceはacquiredなら試行する

---

## Compatibility Phase 1

Launch Mode Caseの共通出力を`CANalyzer_Check_Compatibility.vi`へ接続する。

| Terminal | Source / Constant |
|---|---|
| Application Ref | Launch Case output |
| `Enable Configuration-Dependent Probe?` | False |
| `Probe Namespace` | `""` |
| `Probe Variable Name` | `""` |
| Expected Value Type | Boolean |
| `Known Version Full Names[]` | Productionで使用するKnown Version配列。未登録なら空配列 |
| error input | launch/open Operation Error |

Phase1 mandatory capability failureは`Unsupported / -710101`を保持し、Configuration Openへ進まない。

Version取得不能だけでmandatory capabilityが成功している場合はUnknownのまま後段へ進める。

---

## Compatibility Policy Case

`Compatibility Policy`をCase Structure selectorへ接続し、次の3 Caseを作る。

- `Require Compatible`
- `Allow Warning`
- `Allow Unknown`

各Caseの内部処理順は同じ。

```text
Optional Configuration Open
→ Verify
→ Phase2
→ Policy判定
→ Final Refs
→ Initial Running / Start
→ Session Build
→ Registry Create
```

構造を3 Caseへ複製する場合でも、Session Stateのsource-of-truthは3 Caseで統一する。

---

## Optional Configuration Open と Verify

### Open Configuration? = False

`CANalyzer_Verify_Configuration.vi`を直接呼ぶ。

| Verify terminal | Source |
|---|---|
| Application Ref | resolved App Ref |
| `Expected Configuration Path` | Trim済みConfiguration Path String |
| error input | current No Error |

出力：

- Actual Configuration Path String = Verify output
- Configuration Opened By LabVIEW? = False
- Verify error = operation errorへ

### Open Configuration? = True

先に`CAN_AX_Open_Configuration.vi`を呼ぶ。

| Open Configuration terminal | Source |
|---|---|
| Application Ref | resolved App Ref |
| Configuration Path | Trim済みConfiguration Path String |
| `AutoSave?` | False |
| `Prompt User?` | False |
| error input | current No Error |

既存Wrapperの端子表示に誤記がある場合は、`Ctrl+H`でConfiguration Path入力端子を確認して接続する。

Open wrapperの`error out.status`からhistoryを作る。

| Open result | Configuration Opened By LabVIEW? |
|---|---|
| Success | True |
| Failure | False |

このhistoryは**current invocationだけ**を表す。Feedback Nodeなどでprevious invocation valueを保持しない。

Open error outをVerify error inへ接続する。Open失敗時は通常のerror dataflowによりVerify実処理は進まない。

Verify成功時のActual Stringを保持する。

`Open Configuration?`のTrue/Falseに関係なく、Open処理が成功して後段へ進む場合はVerifyを必ず通過する。

---

## Compatibility Phase 2

Verify PASS後だけ`CANalyzer_Check_Compatibility.vi`を再度呼ぶ。

Production固定値：

| Terminal | Value |
|---|---|
| `Enable Configuration-Dependent Probe?` | True |
| `Probe Namespace` | `ID03AD5D62` |
| `Probe Variable Name` | `CORE_SVS_OPE_MODE_COM` |
| Expected Value Type | `I32` |
| `Known Version Full Names[]` | Production Known Version配列 |

Phase2はResolve / Read / Type conversionによるread-only capability probeとして扱う。

VerifyのActual Configuration Path Stringを`String To Path`へ接続し、Public `Actual Configuration Path`とSession State `Configuration Path`のsourceにする。

---

## Compatibility Policy判定

Phase2 final statusを現在のPolicy Caseに従って判定する。

| Phase2 Status | Require Compatible | Allow Warning | Allow Unknown |
|---|---:|---:|---:|
| Compatible | Accept | Accept | Accept |
| Compatible With Warning | Reject | Accept | Accept |
| Unknown | Reject | Reject | Accept |
| Unsupported | Reject | Reject | Reject |

`Unsupported`はPhase2 Serviceの`-710101`を保持する。

Phase2自体は成功したがWarning / UnknownをPolicyが拒否するときだけ`-710117`を生成する。

```text
status = True
code   = -710117
source = CANalyzer_Open.vi / Compatibility Policy Rejected
         Policy=<policy>
         Status=<status>
         Version=<version>
```

`Format Into String`を使用する場合、Policy / Status / Versionをsourceへ埋め込む。

---

## Final System Ref と Measurement Ref

Policy ACCEPT後だけSession用Refを新規取得する。

```text
CAN_AX_Get_System.vi
→ CAN_AX_Get_Measurement.vi
```

Compatibility Service内部で使ったtemporary RefはSessionへ再利用しない。

### System Ref

Application Refとcurrent errorを`CAN_AX_Get_System.vi`へ接続する。

- success → `System Ref Acquired?=True`
- failure → `System Ref Acquired?=False`

### Measurement Ref

Application RefとSystem取得後のcurrent errorを`CAN_AX_Get_Measurement.vi`へ接続する。

- success → `Measurement Ref Acquired?=True`
- failure → `Measurement Ref Acquired?=False`

acquired flagはCleanup gateに使用する。単に「SubVIを呼んだ」ことをTrueの根拠にしない。

---

## Initial Running と Start

Final Measurement Ref取得後、Start判定より先に`CAN_AX_Get_Measurement_Running.vi`を1回呼ぶ。

この出力を`Initial Running`および`Running?` historyの最初の観測値とする。

Start条件：

```text
Start Needed
=
Start Measurement?
AND
NOT Initial Running
```

期待動作：

| Start Measurement? | Initial Running | Start | Started history | Running |
|---|---|---|---|---|
| False | False | No | False | False |
| False | True | No | False | True |
| True | True | No | False | True |
| True | False | Yes | Start成功時True | WaitのActual Running |

Measurement Timeoutのinvalid判定はすでにActiveX処理前に完了しているため、ここで重複してPublic input validationを作らない。

### Start Needed = False

- `CAN_AX_Start_Measurement.vi`を呼ばない。
- `Measurement Started By LabVIEW?=False`
- `Running?=Initial Running`

### Start Needed = True

`CAN_AX_Start_Measurement.vi`へMeasurement Refとcurrent errorを接続する。

Start success直後に`Measurement Started By LabVIEW?=True`とする。Wait成功をStarted historyの条件にしない。

Start success後：

`CANalyzer_Wait_Measurement_State.vi`へ次を接続する。

| Terminal | Value / Source |
|---|---|
| Measurement Ref | final Measurement Ref |
| `Expected Running?` | True |
| `Timeout ms` | Measurement Timeout ms |
| `Poll Interval ms` | U32 100 |
| error input | Start error out |

`Actual Running?`を最後に観測したRunningとして保持する。

Start failureではStarted=False。Waitは通常error chainで実処理されない。

---

## Session Stateを構築する

`CANalyzer_Session_State.ctl`の定数または既定clusterを`Bundle By Name`へ接続し、13 fieldsを明示設定する。

| Session Field | Source |
|---|---|
| Session ID | U32 0 |
| Application Ref | final Application Ref |
| System Ref | final System Ref |
| Measurement Ref | final Measurement Ref |
| Version String | Phase2 Version String |
| Configuration Path | verified Actual Path |
| Launch Mode | Public Launch Mode |
| Application Ownership | resolved ownership |
| Configuration Opened By LabVIEW? | current invocationのConfig Open success history |
| Measurement Started By LabVIEW? | Start Invoke success history |
| Cached Connected? | True |
| Cached Measuring? | final observed Running |
| Compatibility Status | Phase2 final status |

`Cached Connected?` / `Cached Measuring?`はcacheであり、後続runtime判断のsource-of-truthではない。

---

## Registry Create

`CANalyzer_Session_Registry.vi`へ次を接続する。

| Terminal | Source |
|---|---|
| Action | `Create` |
| Session ID | U32 0 |
| Session In | completed Session State |
| error input | current operation error |

Create成功時：

- `Session ID Out`をPublic `Session ID`へ接続する。
- Session IDは`>0`。
- Application / System / Measurement Ref ownershipはOpenからSessionへ移る。
- success pathでこれらのRefをCloseしない。

Registry Create failure時：

- Session ID=0。
- OpenがRefとside effectのrollback ownerのまま。
- Cleanupへ進む。

---

## Failure Rollbackの入口

最初のOperation Errorを保存する。

Cleanup actionがOperation Errorによってskipされないよう、cleanup用error chainは`Clear Errors`または明示No Errorから開始する。

Rollbackは取得済みresourceだけを対象にする。

```text
if Started By LabVIEW:
    Stop
    if Stop success:
        Wait False
if Measurement Ref Acquired:
    Close Measurement Ref
if System Ref Acquired:
    Close System Ref
if Application Ownership = LabVIEW:
    Quit Application
if App Ref Acquired:
    Close Application Ref
```

Configuration Openが成功していてもprevious Configurationへrestoreしない。

---

## Rollback Stop と Wait False

Stop selectorは`Measurement Started By LabVIEW?`だけ。

`Running?`や`Cached Measuring?`をStop ownership判定に使用しない。

### Started=False

Stop / Wait Falseを実行しない。

### Started=True

`CAN_AX_Stop_Measurement.vi`へMeasurement Refを接続し、clean error inputから実行する。

Stop errorをCleanup Error accumulatorへ反映する。

Stop成功時だけ`CANalyzer_Wait_Measurement_State.vi`を実行する。

| Terminal | Value / Source |
|---|---|
| Measurement Ref | final Measurement Ref |
| `Expected Running?` | False |
| `Timeout ms` | Measurement Timeout ms |
| `Poll Interval ms` | U32 100 |
| error input | clean cleanup chain |

Running history：

| 状態 | Running? |
|---|---|
| Wait False success | False |
| Wait False failure | それ以前のlast observed Runningを保持 |
| Stop failure | Waitを行わず、それ以前のlast observed Runningを保持 |

Stop error statusそのものをRunning stateとして扱わない。

Current As-Builtでは、Stop成功Caseへ入った時点で`StopError=False`が保証される。そのためRunning更新判定はWait Errorだけでよい。

```text
StopError OR WaitError
= False OR WaitError
= WaitError
```

これは数学的に等価な簡略化である。

---

## Measurement RefをCloseする

`Measurement Ref Acquired?`をCase selectorへ接続する。

FalseではCloseしない。

Trueでは：

- clean error inputを`Close Reference`へ渡す。
- final Measurement Refを`Close Reference.reference`へ接続する。
- Close errorをCleanup Error accumulatorへ反映する。

Measurement Close failureでも後続System cleanupを止めない。

---

## System RefをCloseする

`System Ref Acquired?`をCase selectorへ接続する。

Trueの場合だけSystem Refを`Close Reference`へ接続する。

System Close failureでもApplication cleanupを止めない。

---

## Application Quit

`Application Ownership`をCase selectorへ接続する。

| Ownership | Quit |
|---|---|
| Unknown | Do not call |
| External | Do not call |
| LabVIEW | `CAN_AX_Quit_Application.vi`をattempt |

LabVIEW CaseではApplication Refとclean cleanup errorをQuitへ接続する。

Quit failureでもApplication Ref Closeへ進む。

Force New InstanceのOwnershipは初版Unknownなので、Force Newだけを理由にQuitしない。

---

## Application RefをCloseする

`App Ref Acquired?`をCase selectorへ接続する。

Trueの場合だけApplication Refを`Close Reference`へ接続する。

Ownership=External / UnknownでもApplication Ref自体はborrowed/owned lifecycle契約に従ってClose attemptする。QuitとClose Referenceを混同しない。

---

## Cleanup Errorを保持する

Cleanupは途中のerrorで後続actionを止めない。

各cleanup actionの後で：

```text
if Previous Cleanup Error.status = True:
    Previous Cleanup Errorを保持
else:
    Current Cleanup Action Errorを採用
```

これをStop、Wait False、Measurement Close、System Close、Quit、Application Closeへ適用する。

つまり **First Cleanup Error Wins**。

Case Structure / Selectの形は自由だが、全真理値で同じ結果になること。

---

## Final Error Merge

最終errorは次の真理値で固定する。

| Operation Error | Cleanup Error | Final Error |
|---|---|---|
| No Error | No Error | No Error |
| No Error | Error | Cleanup Error |
| Error | No Error | Operation Error |
| Error | Error | Operation Error |

**Operation Error > Cleanup Error**。

Operation Error.statusをselectorにして、

- False → Cleanup Error
- True → Operation Error

としてもよい。

---

## Public Outputs

Success時：

| Indicator | Source |
|---|---|
| Session ID | Registry `Session ID Out` |
| Version String | Phase2 Version String |
| Actual Configuration Path | Verify Actual StringをPath化した値 |
| Application Ownership | resolved ownership |
| Measurement Started By LabVIEW? | Started history |
| Running? | final observed Running |
| Compatibility Status | Phase2 final status |
| error out | final merged error |

Failure時も診断値を不用意にdefaultへ戻さない。

| Output | Failure contract |
|---|---|
| Session ID | 常に0 |
| Version String | 取得済みなら保持 |
| Actual Configuration Path | 取得済みなら保持 |
| Application Ownership | 判定済みなら保持 |
| Measurement Started By LabVIEW? | historyとして保持 |
| Running? | last observed value |
| Compatibility Status | 最後に確定したstatus |
| error out | primary Operation Error |

Incoming error guardとinput validation failureだけは、ActiveX処理前なのでsafe defaultを返す。

---

## Error Code確認

| Code | Meaning | Origin |
|---:|---|---|
| -710101 | Required Capability Missing | Compatibility Service |
| -710103 | Configuration Mismatch | Verify Service |
| -710104 | Measurement State Timeout | Wait Service |
| -710109 | Required Existing CANalyzer Process Not Found | Open生成 |
| -710116 | Invalid Expected Configuration Path | Open input validation |
| -710117 | Compatibility Policy Rejected | Open生成 |
| -710118 | Invalid Measurement Timeout | Open input validation |

Automation Open failureは元wrapper / ActiveX errorを保持し、`-710100`へ強制normalizeしない。

---

## 作成完了後の静的チェック

| 確認 | 合格条件 |
|---|---|
| Public I/O | 8 inputs / 8 outputs、Startup Timeoutなし |
| Incoming Error | side effectなし、original error |
| Configuration Path | trim後emptyで-710116、ActiveX前 |
| Timeout | Start=True + 0だけ-710118、ActiveX前 |
| Require Existing | Detect error fatal、Found=Falseで-710109、Openしない |
| Reuse | Detect error advisory、Ownership matrix一致 |
| Force New | Detectなし、Open New Instance=True、Ownership=Unknown |
| Phase order | Phase1 → optional Config Open → Verify → Phase2 → Policy |
| Config history | current invocationのみ |
| Production Probe | `ID03AD5D62 / CORE_SVS_OPE_MODE_COM / I32` |
| Policy | 3×4 matrix一致 |
| Final Refs | Policy PASS後に新規取得 |
| Start matrix | 4ケース一致 |
| Started history | Start Invoke成功直後True |
| Registry | success時だけownership transfer |
| Stop ownership | Started historyだけ |
| Running history | last observed state |
| Cleanup | Stop/Wait/Close/Quit failureでも後続継続 |
| Cleanup error | First Cleanup Error Wins |
| Final error | Operation Error > Cleanup Error |
| Application Quit | LabVIEWのみ |
| Configuration rollback | なし |
| Broken Run Arrow | なし |
| Execution | Non-reentrant |

---

## Runtime / Hardware E2E

Static / Human Model CheckはCLOSEDだが、実CANalyzerを使用するruntimeはPENDING。

実機では最低限次を確認する。

- Require Existingで既存CANalyzerへ接続
- Require Existingで未起動時に-710109
- Reuse Existing Or Launchの既存再利用
- Reuseで未起動から起動した場合のOwnership evidence
- Force New Instanceの実挙動
- Configuration Open / Verify
- Production Phase2 Probe
- Start / Running=True
- rollback Stop / Running=False
- Registry Create failure時のresource cleanup
- External / UnknownをQuitしない
- LabVIEW ownership時のQuit
- 参照Close後のresource残留なし

---

## Source / Version / State

| 項目 | 内容 |
|---|---|
| Source | Current local `CANalyzer_Open.vi`、使用SubVI群、登録済みCANalyzer Type Library、Final Design / As-Built Review |
| Environment | LabVIEW 2026 Q3 64-bit / TestStand 2026 Q3 64-bit。Repository内の古いQ1記載は環境正本ではない |
| Verified by | Final Full As-Built Model Check + Human Non-reentrant / Broken Run Arrow / Typedef checks |
| State | **STATIC + HUMAN MODEL CHECK CLOSED / Runtime Hardware E2E PENDING** |
