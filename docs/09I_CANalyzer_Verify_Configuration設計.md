# 09I. CANalyzer_Verify_Configuration.vi 最終設計

**最終整理日：2026-08-24**

> **本章の役割**：`CANalyzer_Verify_Configuration.vi` のProduction向け確定設計と設計判断の根拠を定義する。
> 本VIは `20_Service` に属するread-only Verify Serviceであり、現在CANalyzerで有効なConfiguration Pathを取得し、callerが要求したExpected Configuration Pathと照合することだけを担当する。
>
> CANalyzer全体のレイヤ構成と呼出順、および**作成・再構築手順の正本**は [`09_CAN通信の実装.md`](./09_CAN通信の実装.md) の `9.9.8 CANalyzer_Verify_Configuration.vi` とする。本章は設計根拠を保持し、同じ詳細作成手順を複製しない。VI作成手順の記述規則は [`00A_LabVIEW実装資料の記述ルール.md`](./00A_LabVIEW実装資料の記述ルール.md)、仕様根拠と確認状態は [`00C_一次資料とバージョン基準.md`](./00C_一次資料とバージョン基準.md) に従う。
>
> Final Design Closure、Focused As-Built Review、Closure Spot Checkを完了し、2026-08-24時点で `P0=0 / P1=0`、Functional Design Alignment=`PASS`。Broken Run Arrowは人間確認で問題なし。残件は内部定数名のP2 cosmetic事項のみで、機能Closureを阻害しない。

---

## 1. 目的

`CANalyzer_Verify_Configuration.vi` は、callerがすでに取得しているCANalyzer Application ActiveX Refを借用し、**現在開かれているConfigurationが期待するConfigurationと一致するかを検証する**。

ConfigurationのOpenとVerifyを同じVIへ混在させない。

```text
CANalyzer_Open.vi
  ├─ 必要ならConfiguration Open
  └─ CANalyzer_Verify_Configuration.vi
       └─ 現在開かれているConfigurationをread-onlyで照合
```

この責務分離により、次を明確にする。

1. `CANalyzer_Open.vi` は状態を変更してよい。
2. `CANalyzer_Verify_Configuration.vi` は状態を変更しない。
3. Configuration mismatchとActiveX機構failureを別エラーとして扱う。
4. Configurationが正しいことを確認してからConfiguration-dependent Compatibility Probeへ進む。

---

## 2. 配置と責務

配置先：

```text
60_CAN\20_Service\CANalyzer_Verify_Configuration.vi
```

本VIが行うこと：

- Application Refから現在のConfiguration Refを取得する
- Configuration RefからActual Configuration Pathを取得する
- Expected / Actual Pathを同一規則でnormalizeする
- normalized stringをexact compareする
- 一致時に`Configuration Match? = True`を返す
- 不一致時に`-710103`を返す
- temporary Configuration RefをCloseする
- Operation ErrorとCleanup Errorを既決優先順位で統合する

本VIが行わないこと：

- Configuration Open / Save
- Measurement Start / Stop
- SysVar Read / Write
- Version判定
- Compatibility Probe
- Session Registry操作
- Application Quit
- Application Ref Close
- persistent state保持
- relative path canonicalization
- mapped drive / UNC alias resolution

---

## 3. 一次Evidenceと確認状態

Final Design Closure時にlocal Projectの既存WrapperをREAD ONLYで確認した結果を採用する。

| 項目 | 確認結果 | State |
|---|---|---|
| `CAN_AX_Get_Configuration.vi` | Application RefからConfiguration Refを取得 | 実VI確認済み |
| Configuration Ref型 | `CANalyzer.IConfiguration16` | 実VI確認済み |
| `CAN_AX_Get_Configuration_Path.vi` | Configuration Refから`Path` Propertyを読む | 実VI確認済み |
| Configuration Path出力型 | **String** | 実VI確認済み |
| Wrapper error端子 | standard `error in / error out` | 実VI確認済み |
| Wrapper内Configuration Ref Close | 行わない | 実VI確認済み |
| `CAN_AX_Open_Configuration.vi` | Application Refへ`Open` Invokeを行う | 実VI確認済み。ただし本VIでは使用禁止 |

### 3.1 Source / Version / Symbol / Signature / Verified by / State

| 項目 | 内容 |
|---|---|
| Source | 対象PCの既存CANalyzer ActiveX Wrapper / 登録済みCANalyzer Type Library / `09_CAN通信の実装.md` |
| Version | RepositoryのCANalyzer実装基準に従う。製品Version固有差はWrapper層へ閉じ込める |
| Symbol | `CAN_AX_Get_Configuration.vi`, `CAN_AX_Get_Configuration_Path.vi`, `Configuration.Path` |
| Signature | Application ActiveX Ref → Configuration Ref、Configuration Ref → Path String、各Wrapperにerror in/out |
| Verified by | local ProjectのFront Panel / Block Diagram / Connector PaneをREAD ONLY確認、Focused As-Built Review、Closure Spot Check |
| State | **AS-BUILT CONFIRMED / Functional Design Alignment PASS** |

未確認のCANalyzer製品Version固有表現を本Service側で推測して補完しない。

---

## 4. I/O Contract

### 4.1 Inputs

| 端子 | 型 | 契約 |
|---|---|---|
| `Application Ref` | `CANalyzer.IApplication10` ActiveX Ref | caller-owned / borrowed。本VIではCloseしない |
| `Expected Configuration Path` | String | callerが要求するfully-qualified absolute Windows configuration file path |
| `error in` | error cluster | prior error時はActiveX処理をbypass |

`Require Match?`入力は**持たせない**。

Verify Serviceを呼ぶ以上、一致確認を必須とする。比較をskipしたい場合は上位の`CANalyzer_Open.vi`側で本VIを呼ばない。

### 4.2 Outputs

| 端子 | 型 | 契約 |
|---|---|---|
| `Actual Configuration Path` | String | CANalyzer `Configuration.Path`から取得したraw string。正常取得時はnormalize前の値を返す |
| `Configuration Match?` | Boolean | normalized Expected / Actualのexact compare結果 |
| `error out` | error cluster | mismatch=`-710103`、Expected入力不正=`-710116`、Wrapper failure=元error、Cleanup-only failure=Close error |

### 4.3 Connector Pane方針

3-in / 3-outとする。

```text
Left upper   : Application Ref
Left middle  : Expected Configuration Path
Left lower   : error in

Right upper  : Actual Configuration Path
Right middle : Configuration Match?
Right lower  : error out
```

---

## 5. Incoming Error Contract

`error in.status = True` の場合は最外周でbypassする。

```text
Actual Configuration Path = ""
Configuration Match?       = False
error out                  = original error in
```

この経路では次を実行しない。

- `CAN_AX_Get_Configuration.vi`
- `CAN_AX_Get_Configuration_Path.vi`
- Configuration Ref取得
- Path compare
- Close Reference

Application Refはcaller-ownedのため、どの経路でもCloseしない。

---

## 6. Expected Configuration Path Contract

### 6.1 Supported input

初版でサポートするExpected Pathは**fully-qualified absolute Windows file path string**に限定する。

例：

```text
C:\CANalyzer\Config\Test.cfg
\\server\share\config\Test.cfg
```

absolute UNC pathは使用可能とする。

### 6.2 Empty / whitespace-only

`Expected Configuration Path`へ`Trim Whitespace`を適用し、結果がemptyならcaller input errorとする。

```text
Actual Configuration Path = ""
Configuration Match?       = False
error.status               = True
error.code                 = -710116
error.source               = CANalyzer_Verify_Configuration.vi / Invalid Expected Configuration Path
```

この場合はActiveX処理を開始しない。

### 6.3 Unsupported / deferred forms

初版では次を自動canonicalizationしない。

- relative pathからabsolute pathへの変換
- `.` 解決
- `..` 解決
- short path / long path同一視
- junction / symbolic link解決
- mapped driveとUNCの同一視
- network alias解決

例：

```text
Z:\Config.cfg
```

と

```text
\\server\share\Config.cfg
```

は初版では同一視しない。

Relative pathはcaller contract violationとし、本VIへ推測的なrelative判定ロジックを追加しない。

---

## 7. Path Normalization Contract

Expected / Actualの両方へ**同じ順序**で次を適用する。

```text
1. Trim Whitespace
2. "/" を "\" へ統一
3. 英字をlowercase化
4. exact string compare
```

概念：

```text
Normalize(Expected)
Normalize(Actual)
        ↓
      Equal?
```

### 7.1 採用する理由

既存`CAN_AX_Get_Configuration_Path.vi`の出力はLabVIEW Path型ではなくStringであるため、Serviceの比較契約もStringへ統一する。

### 7.2 採用しない比較

- Path型`Equal?`
- Path To Stringを前提とした比較
- substring / Containsによる一致
- filenameだけの比較
- case-sensitive raw string compare

### 7.3 Deferred canonicalization

次はruntime evidenceが必要になるまで追加しない。

- CANalyzer Path Propertyがrelative pathを返す場合の補正
- drive letter canonicalization
- UNC canonical formの変換
- trailing separator吸収

Configurationはfile pathであるため、`...\file.cfg\`のようなtrailing separatorを有効な同一表現として積極的に吸収しない。

---

## 8. Configuration取得Dataflow

Expected Pathがvalidな場合のみActiveX処理へ進む。

```text
Application Ref
  ↓
CAN_AX_Get_Configuration.vi
  ↓
Configuration Ref
  ↓
CAN_AX_Get_Configuration_Path.vi
  ↓
Actual Configuration Path (raw String)
```

Configuration Refは本VIが取得したtemporary refである。Get Configuration成功時のみacquiredとして扱い、Get Path failure / Match / Mismatchではcleanupする。Get Configuration failureではunacquired RefをCloseしない。

---

## 9. Match / Mismatch Contract

### 9.1 Match

```text
Normalize(Expected) == Normalize(Actual)
```

の場合：

```text
Actual Configuration Path = raw Actual Path
Configuration Match?       = True
Operation Error            = No Error
```

### 9.2 Mismatch

```text
Normalize(Expected) != Normalize(Actual)
```

の場合：

```text
Actual Configuration Path = raw Actual Path
Configuration Match?       = False
error.status               = True
error.code                 = -710103
```

error source：

```text
CANalyzer_Verify_Configuration.vi / Configuration Mismatch
Expected=<expected path>
Actual=<actual path>
```

診断用sourceではExpectedにtrim済みpath、Actualにraw pathを使用する。lowercase化したnormalized値だけへ置換しない。

### 9.3 Actual Path empty

Expectedがvalidで、`CAN_AX_Get_Configuration_Path.vi`自体はsuccessしたがActual Pathがemptyの場合は、特別な別errorを作らずmismatchとして扱う。

```text
Actual Configuration Path = ""
Configuration Match?       = False
error.code                 = -710103
```

現時点のstatic evidenceでは、Wrapper success時のempty Actual Pathに別の意味がある根拠はない。

---

## 10. Wrapper Failure Contract

次のfailureをConfiguration mismatchへnormalizeしない。

### 10.1 Get Configuration failure

```text
Actual Configuration Path = ""
Configuration Match?       = False
error out                  = original ActiveX / Wrapper error
Configuration Ref Acquired?= False
Close Reference            = 実行しない
```

元error code / sourceを保持する。

### 10.2 Get Configuration Path failure

```text
Actual Configuration Path = ""
Configuration Match?       = False
Operation Error            = original ActiveX / Wrapper error
Configuration Ref Acquired?= True
Configuration Ref          = cleanup対象
```

元error code / sourceを保持する。

理由：

```text
Configurationが違う
!=
Configuration Property自体を読めない
```

この2種類を同じ`-710103`へ潰さない。

---

## 11. Error Code Allocation

本VIで直接生成するローカルエラーは次の2つ。

| Code | 意味 | 発生条件 |
|---:|---|---|
| `-710103` | Configuration Mismatch | valid Expectedと取得済みActualのnormalized exact compareが不一致 |
| `-710116` | Invalid Expected Configuration Path | Expected PathがTrim後empty |

Final Design Closure Amendment時のREAD ONLY collision確認では`-710116`は未使用であったため採用する。

Wrapper自身が返したActiveX / conversion等のerror codeは本VIで別codeへnormalizeしない。

---

## 12. Reference Ownership Contract

| Ref | Owner | 本VIでClose | Timing |
|---|---|---:|---|
| `Application Ref` | caller | **No** | never |
| `Configuration Ref` | Verify temporary | **取得成功時のみYes** | Get Path後またはacquired後のfailure cleanup |

追加temporary ActiveX RefはFinal Design Closure時のWrapper evidenceでは確認されていない。

### 12.1 Cleanup Gate

| Path | Ref Acquired? | Close |
|---|---:|---:|
| Get Config Failure | No | No |
| Get Path Failure | Yes | Yes |
| Match | Yes | Yes |
| Mismatch | Yes | Yes |

### 12.2 禁止

- Application RefをClose Referenceへ接続しない
- caller-owned refをcleanup対象へ含めない
- unacquired Configuration Refを無条件Closeしない
- acquired Configuration Refをfailure pathでリークさせない

---

## 13. Cleanup Error Priority

採用原則：

```text
Operation Error > Cleanup Error
```

### 13.1 Required behavior

| Operation | Cleanup | Final Error |
|---|---|---|
| success | success | No Error |
| success | failure | Cleanup Error |
| failure | success | Operation Error |
| failure | failure | Operation Error |

### 13.2 Cleanup chain

Operation Errorをそのまま`Close Reference.error in`へ接続してcleanupをskipさせない。

概念：

```text
Operation処理
  ↓
Operation Errorを保持

Configuration Ref Acquired?
  ├─ False → Close skip / Cleanup Error = No Error
  └─ True
       ↓
       No Error / Clear Errors
       ↓
       Close Reference(Configuration Ref)
       ↓
       Cleanup Error

Operation Error.status?
  ├─ True  → Final Error = Operation Error
  └─ False → Final Error = Cleanup Error
```

Close-only failureを捨てない。

---

## 14. Final Dataflow

```text
error in.status?
├─ TRUE
│   ├─ Actual Path = ""
│   ├─ Match? = False
│   └─ error out = original error
│
└─ FALSE
    ↓
    Trim Expected Path
    ↓
    Expected empty?
    ├─ TRUE
    │   ├─ Actual Path = ""
    │   ├─ Match? = False
    │   ├─ error = -710116
    │   └─ ActiveX not called
    │
    └─ FALSE
        ↓
        Get Configuration
        ↓
        failure?
        ├─ YES
        │   ├─ original operation error保持
        │   ├─ Acquired=False
        │   └─ Close skip
        └─ NO
            ↓
            Acquired=True
            ↓
            Get Configuration Path
            ↓
            failure?
            ├─ YES → original operation error保持 → cleanup
            └─ NO
                ↓
                Normalize Expected
                Normalize Actual
                ↓
                exact compare
                ├─ Match
                │   ├─ Match? = True
                │   └─ Operation Error = No Error
                └─ Mismatch
                    ├─ Match? = False
                    └─ Operation Error = -710103
        ↓
        Acquired=Trueの場合だけConfiguration Ref Close
        ↓
        Final Error Select
        Operation Error > Cleanup Error
        ↓
        outputs
```

---

## 15. `CANalyzer_Open.vi`との責務境界

確定境界：

```text
CANalyzer_Open.vi
  ├─ Application取得
  ├─ 必要ならConfiguration Open
  ├─ CANalyzer_Verify_Configuration.vi
  ├─ Verify PASS確認
  ├─ CANalyzer_Check_Compatibility.vi Phase 2
  └─ Session Registry Createへ進む
```

`CANalyzer_Verify_Configuration.vi`から`CAN_AX_Open_Configuration.vi`を呼ばない。

Configurationを開くかどうかは上位`CANalyzer_Open.vi`が決定する。

---

## 16. `CANalyzer_Check_Compatibility.vi`との責務境界

| VI | 責務 |
|---|---|
| `CANalyzer_Verify_Configuration.vi` | 正しいConfigurationが開いているか確認 |
| `CANalyzer_Check_Compatibility.vi` | その環境で必要Capabilityが実際に使用可能か確認 |

Verify内では次を行わない。

- Resolve SysVar
- Read SysVar
- Variant conversion
- Version recognition

Configuration-dependent Compatibility Probeは**Verify PASS後のみ**実行する。

---

## 17. Serialization Contract

本VIはSession Registry Create前のbootstrap Serviceとして使用する。

初期Vertical Slice：

```text
CANalyzer_Open.vi
  = Non-reentrant / bootstrap sequenceの直列化責務

CANalyzer_Verify_Configuration.vi
  = Open内部Service
```

この段階では`CANalyzer_Execute_Command.vi`へ載せない。

将来Open Session commandをdispatcherへ追加する場合はOpen全体のserializationへ移行可能だが、本VI単独でpersistent stateやdispatcher依存を持たせない。

---

## 18. Static Acceptance Contract

| Case | Expected | As-Built |
|---|---|---|
| Incoming Error | Actual=`""`, Match=False, original error、ActiveX未実行 | PASS |
| Expected Path empty after trim | Actual=`""`, Match=False, `-710116`、ActiveX未実行 | PASS |
| Get Configuration failure | Actual=`""`, Match=False, original Wrapper error、Closeなし | PASS |
| Get Path failure | Actual=`""`, Match=False, original Wrapper error、Configuration Ref cleanup | PASS |
| `C:\Test\Config.cfg` vs `c:\test\config.cfg` | Match=True | PASS |
| `C:/Test/Config.cfg` vs `c:\test\config.cfg` | Match=True | PASS |
| Different cfg | Match=False, `-710103` | PASS |
| Wrapper success + Actual=`""` | Match=False, `-710103` | PASS |
| `Z:\Config.cfg` vs `\\server\share\Config.cfg` | Match=False | PASS |
| Operation success + Close failure | Final error=Cleanup Error | PASS |
| Mismatch `-710103` + Close failure | Primary=`-710103` | PASS |
| Wrapper failure + Close failure | Primary=original Wrapper operation error | PASS |
| Application Ref ownership | never closed | PASS |

---

## 19. Focused As-Built Review Gate

### P0

- Application RefをCloseしている
- Configuration Ref leak
- mismatchを検出できない
- operation error時にacquired Ref cleanupがskipする
- Cleanup ErrorがOperation Errorを上書きする
- Close-only errorを捨てる
- Verify内でConfiguration Open / Measurement制御 / SysVar操作を行う
- Broken Run Arrowが確認された

### P1

- Expected empty時の`-710116`契約違反
- Expected emptyでもActiveX処理を実行する
- Expected / Actualでnormalize規則が異なる
- `/`→`\`統一がない
- lowercase化がない
- exact compareでない
- mismatchが`-710103`にならない
- raw Actual Pathを出力へ保持しない
- Wrapper failureを`-710103`へ誤normalizeする
- Get Configuration failureでunacquired RefをCloseする
- Connector Pane契約違反

### P2

- label / layout / cosmetic readability

Closure条件：

```text
P0 = 0
P1 = 0
Functional Design Alignment = PASS
Broken Run Arrow = NO（人間確認可）
```

**2026-08-24 Closure結果：条件達成。**

---

## 20. 実装完了条件

- [x] 3 inputs / 3 outputs
- [x] incoming errorでActiveX bypass
- [x] Expected Path Trim後emptyで`-710116`
- [x] empty Expected時にActiveX未実行
- [x] `CAN_AX_Get_Configuration.vi`を使用
- [x] `CAN_AX_Get_Configuration_Path.vi`を使用
- [x] Expected / Actualへ同一normalize
- [x] Trim Whitespace
- [x] `/` → `\`
- [x] lowercase
- [x] exact compare
- [x] mismatchで`-710103`
- [x] Wrapper failureの元error保持
- [x] raw Actual Pathを出力
- [x] Get Configuration成功時だけConfiguration Ref acquired
- [x] acquired Configuration Ref cleanup
- [x] Application Ref never close
- [x] Operation Error > Cleanup Error
- [x] Close-only errorを保持
- [x] Configuration Openなし
- [x] SysVar操作なし
- [x] Measurement制御なし
- [x] Session Registry操作なし
- [x] Broken Run Arrowなし（人間確認済み）

実機CANalyzerを使用したruntime/hardware E2Eは、このstatic As-Built Closureとは別工程で確認・記録する。

---

## 21. Final Status

```text
CANalyzer_Verify_Configuration.vi
Design Status              = FINAL / CLOSED
Implementation             = COMPLETE
As-Built Status            = CONFIRMED
Functional Design Alignment= PASS
Focused Review P0          = 0
Focused Review P1          = 0
Remaining                  = P2 cosmetic only
Broken Run Arrow           = NO / HUMAN VERIFIED
Runtime / Hardware E2E     = NOT RECORDED HERE
```

本VIの設計・static As-Built Closureは完了。**作成・再構築手順の正本は `09_CAN通信の実装.md` §9.9.8** とし、本章は設計判断とClosure根拠を保持する。
