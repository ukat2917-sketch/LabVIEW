# 00D. AI協調LabVIEW設計・実装・レビュープロセス

**制定日：2026-08-28**  
**Status:** CANONICAL PROCESS / ACTIVE

> 本書を、ChatGPT、Nigel AI、人間実装者を用いてLabVIEW / TestStand関連VIを設計、実装、レビューする際の共通開発プロセスの正本とする。  
> VIの具体的な記述方法は[00A_LabVIEW実装資料の記述ルール.md](./00A_LabVIEW実装資料の記述ルール.md)、設計理由とアルゴリズムの説明方法は[00B_LabVIEW学習型VI設計ルール.md](./00B_LabVIEW学習型VI設計ルール.md)、一次資料とVersionの優先順位は[00C_一次資料とバージョン基準.md](./00C_一次資料とバージョン基準.md)に従う。

---

# 0. 目的

本プロセスの目的は、生成AIへLabVIEW実装を丸投げすることではない。

次の責務を分離し、設計とactual wiringのドリフトを早期に検出しながら、人間がGUI上で安全にVIを構築できる状態を作る。

```text
GitHub正本・一次資料
        ↓
ChatGPT Design Candidate
        ↓
Nigel Design Investigation / Review
        ↓
Design Algorithm Freeze
        ↓
Nigel GUI Construction Instructions
        ↓
Human Implementation
        ↓
Nigel As-Built Inspection
        ↓
ChatGPT Drift Gate
        ↓
Final Algorithm-to-Wiring Audit
        ↓
STATIC CLOSED
        ↓
Runtime / Hardware E2E
```

基本思想は次の3点である。

1. **設計、施工手順、実装、レビューを混ぜない。**
2. **Nigelの強みはlocal LabVIEW VIのactual構造確認に使い、設計正本はGitHubで管理する。**
3. **Slice単位のPASSだけで完成扱いせず、最後にFrozen Algorithmとactual wiringを全経路で照合する。**

---

# 1. 適用範囲

本プロセスは原則として次へ適用する。

- Public API VI
- Service VI
- ActiveX / DLL Wrapper
- Session / State管理VI
- Builder / Parser
- File Logging VI
- Device Control VI
- PoCからProductionへ昇格するVI
- TestStandから呼び出すVI
- 複数Case、state mutation、cleanup、timeout、retry、error priorityを持つVI

単純な1入力1出力変換VIではPhaseを統合してよい。ただし、設計根拠、actual確認、Static Acceptanceを省略してよいという意味ではない。

---

# 2. 役割分担

## 2.1 ChatGPT：設計統括 / 正本管理 / Drift Gate

ChatGPTの担当：

- GitHub既存資料を読む。
- 既決契約、Frozen領域、依存VI、error code、state modelを整理する。
- Design Candidateを作る。
- Nigelの調査結果を設計へ反映する。
- 設計とactual implementationの差分を判定する。
- P0 / P1 / P2のclosureを管理する。
- Design Freeze、As-Built、Static ClosedをGitHub正本へ反映する。

ChatGPTが行ってはいけないこと：

- 未確認のVI端子、ActiveX member、driver signatureを推測で確定する。
- Nigelのactual VI evidenceより一般知識を優先する。
- Frozen Designを実装途中に無言で変更する。
- Runtime未確認をStatic PASSと混同する。

## 2.2 Nigel AI：現場調査 / GUI施工図 / As-Built Inspector

Nigelの担当：

- local LabVIEW Project / VIをREAD ONLYで調査する。
- actual Case、terminal、wire、typedef、SubVI、enum、cluster fieldを確認する。
- Frozen AlgorithmをLabVIEW GUIへ落とす施工指示を作る。
- 実装途中のactual VIを確認し、As-Built Reportを返す。
- Final Algorithm-to-Wiring Auditでsource-to-destination traceを行う。

原則としてNigelへ既存VIの直接編集を依頼しない。

Nigelが行ってはいけないこと：

- Frozen Designを独断で変更する。
- prior PASSをactual evidenceの代わりにする。
- node名や画面位置だけから配線意味を推測する。
- 「明示wireがない」だけでBundle By Name等のpreserve semanticsを否定する。
- GitHubへアクセスできる前提の指示を受ける。

NigelにGitHub資料を参照させる必要がある場合は、必要な契約・アルゴリズムをPrompt内へ埋め込む。

## 2.3 Human：実装 / Human Approval Gate

人間実装者の担当：

- LabVIEW GUI上で実際にVIを構築・修正する。
- Frozen Designと施工指示の採否を確認する。
- Broken Run Arrow、connector pane、coercion、typedef、visible wiringを確認する。
- 設計変更が必要な場合にHuman Approvalを与える。

AIが生成した修正案をそのまま適用するのではなく、対象branchと変更範囲を確認してから実装する。

---

# 3. Status語彙

各設計正本では、進捗を次のStatusへ統一する。

```text
DRAFT
DESIGN CANDIDATE
DESIGN REVIEW
FROZEN DESIGN / IMPLEMENTATION PENDING
IMPLEMENTATION IN PROGRESS
STATIC REVIEW IN PROGRESS
STATIC IMPLEMENTATION CLOSED
RUNTIME / HARDWARE PENDING
RUNTIME VERIFIED
```

`STATIC IMPLEMENTATION CLOSED`はRuntime動作確認済みを意味しない。

---

# 4. Phase 0：Evidence Gate

設計開始前にEvidenceを固定する。

確認対象：

- GitHubの対象正本
- 00A / 00B / 00C
- 依存VIの設計正本
- local project上のactual VI / typedef
- installed driver / Help / COM Type Library / DLL header
- 既存error code
- 既存state model
- 既存Public I/O
- Frozen / Closed領域
- Runtime / Hardware未確認事項

出力：

```text
Evidence Baseline
Known Contract
Unknown / Human Choice Required
Frozen Area
Allowed Change Scope
```

一次資料の優先順位は00Cに従う。

### Gate 0

次のどれかが不明で設計を左右する場合はSTOPする。

- terminal名 / 型
- enum item
- ActiveX member
- ownership authority
- error priority
- state truth source
- public responsibility boundary

---

# 5. Phase 1：ChatGPT Design Candidate

ChatGPTはEvidence Gateを基に最初の設計案を作る。

最低限含める項目：

1. Purpose / Responsibility
2. Public / Internal I/O Contract
3. Preconditions
4. State Authority
5. Processing Algorithm
6. Reachable State Matrix
7. Error Policy
8. State Mutation Policy
9. Result Semantics
10. LabVIEW Structure Mapping案
11. Implementation Slices案
12. Static Acceptance
13. Runtime / Hardware Pending

この段階は`DESIGN CANDIDATE`であり、実装開始禁止。

---

# 6. Phase 2：Nigel Design Investigation / Review

ChatGPTのDesign CandidateをPrompt内へ埋め込み、Nigelにlocal環境で検証させる。

Nigelが確認するもの：

- 既存VIとの責務重複
- 実在するSubVI / terminal / typedef
- Case / error guardとの整合
- current enum / cluster field
- 既存実装とのbackward compatibility
- GUI上で実現可能な構造か
- 設計曖昧性

Nigelの出力は、少なくとも次へ分類する。

```text
CONFIRMED
DESIGN QUESTION
ACTUAL CONSTRAINT
CONFLICT
HUMAN CHOICE REQUIRED
```

このPhaseではVIを編集しない。

---

# 7. Phase 3：Design Iteration / Algorithm Freeze

ChatGPT、Nigel、人間で数回往復し、意味論を固定する。

Freeze前に必ず確定するもの：

## 7.1 Functional Algorithm

LabVIEW node名を使わない擬似コードを先に固定する。

## 7.2 State Authority

各状態について次を明記する。

```text
Truth Source
Cached State
Ownership / History
Valid Observation条件
Preserve条件
Mutation条件
```

## 7.3 Error Contract

各reachable pathについて次を固定する。

```text
Error Code
Source
Primary / Secondary
Priority
Cleanup継続有無
Update failureの扱い
```

## 7.4 Reachable State Matrix

最低限、正常、境界、error、ownership差、timeout、update failureを列挙する。

## 7.5 Final Result / Error Matrix

各pathの最終observable outputを固定する。

| Path | Result | State Mutation | Final Error |
|---|---|---|---|
| ... | ... | ... | ... |

## 7.6 LabVIEW Structure Mapping

Frozen AlgorithmをCase / Loop / Bundle / Select / Shift Register等へ対応付ける。

### Freeze Gate

以下を満たした場合だけ`FROZEN DESIGN / IMPLEMENTATION PENDING`へ移行する。

- P0=0
- P1=0
- Observable Design Ambiguity=0
- Human Choiceが必要な項目が明示済み
- Reachable State Matrix complete
- Result / Error Matrix complete
- GitHub正本へ保存済み

---

# 8. Phase 4：Nigel GUI Construction Instructions

Frozen DesignをNigelへ渡し、人間実装用のGUI施工手順を作らせる。

Nigelは設計を変更しない。

施工手順は00Aに従い、少なくとも次を含める。

- Front Panel controls / indicators
- connector pane
- 使用するSubVI / primitive
- Case Structure階層
- selector source
- source terminal
- destination terminal
- wire type
- constant type / value
- Bundle / Unbundle field
- 全branch output
- error wire
- tunnel
- `Use Default If Unwired`禁止箇所
- Human Choice Required

各手順は`Current Structure`ではなく、Frozen Designから導かれる`Required Structure`を基準にする。

---

# 9. Phase 5：Incremental Human Implementation

大きなVIはSliceへ分割して実装する。

標準ループ：

```text
Frozen Design
    ↓
Slice GUI Instruction
    ↓
Human Implementation
    ↓
Nigel READ ONLY As-Built Review
    ↓
ChatGPT Drift Gate
    ├─一致 → Slice CLOSED
    ├─実装ミス → Local GUI Correction
    └─設計問題 → STOP / Phase 3へ戻る
```

### 9.1 Sliceの原則

- Shared typedef変更を先にする。
- Base / guard / source-of-truthを先にする。
- side effectは後段Sliceにする。
- public wrapperはinternal semantics closure後にする。
- Slice境界を超えた先行実装があっても、observable semanticsに干渉しない限りprocess findingとして扱える。
- ただし先行実装がcurrent Slice contractを壊す場合はP1として扱う。

### 9.2 Nigel As-Built Review

Nigelはactual VIをREAD ONLYで確認し、次を返す。

```text
Expected
Actual
Source Trace
Verdict
P0
P1
P2
Human Static Checks
```

### 9.3 ChatGPT Drift Gate

NigelのPASSだけではSlice CLOSEDにしない。

ChatGPTがFrozen DesignとAs-Built evidenceを比較し、次へ分類する。

```text
CLOSED
CHANGES REQUIRED
DESIGN CHANGE REQUIRED
BLOCKED
```

---

# 10. Review Severity

## P0

安全性、ownership、resource lifecycle、既存command破壊、誤ったphysical action等、即STOPすべき問題。

例：

- incoming errorでもside effectを実行
- wrong resourceをStop / Close
- ownership gate破壊
- existing enum ordinal drift
- cleanup lifecycle破壊

## P1

Frozen observable semanticsとの不一致。

例：

- wrong branch selector
- Result mismatch
- Final Error root mismatch
- Registry Update policy違反
- timeout priority違反
- state preserve違反
- required Update欠落

## P2

observable semanticsに影響しない可読性、配置、label、documentation上の軽微事項。

### Style / Documentation Drift

配線sourceがFrozen文言と異なっていても、reachable control flowによりobservable semanticsが完全等価な場合はP1へ昇格させない。

例：success-only branch内の`No Error constant`とprior success wire。

ただし、正本の記述が実装と恒常的にずれる場合はAs-Built時に文書を修正する。

---

# 11. False Positive Adjudication

Nigel review間で結果が揺れた場合や、node semanticsの誤認が疑われる場合は、すぐ修正しない。

Targeted Adjudicationを行う。

確認方法：

1. selector sourceを追う。
2. reachable branchを確定する。
3. Bundle By Name等のLabVIEW semanticsを考慮する。
4. root sourceからfinal outputまでwire traceする。
5. prior PASSを根拠にしない。
6. current active VIに存在しないUID / nodeを根拠にしない。

分類：

```text
CONFIRMED IMPLEMENTATION P1
FALSE POSITIVE
STYLE / DOCUMENTATION DRIFT ONLY
DUPLICATE ROOT CAUSE
```

修正はroot cause単位で行い、症状を別々に修正しない。

---

# 12. Phase 6：Final Algorithm-to-Wiring Conformance Audit

全SliceがCLOSEDしても、まだ完成ではない。

Final AuditではFrozen AlgorithmのStep 0から最終outputまでactual wiringを通しで照合する。

各Design Stepについて記録する。

```text
Design Step
Actual Node / Structure
Selector Source
Input Source
State Source
Result Source
Error Source
Next Destination
Verdict
```

必須監査：

- Incoming Error Guard
- command dispatch
- Base Result
- truth source
- all side effects
- state mutation
- timeout / retry / wait
- error classification
- error priority
- cleanup / update
- all final Result roots
- all final Error roots
- all reachable paths
- existing command regression

### Final Reachable State Matrix

各pathで次をactual wiringから評価する。

```text
Side Effect Invoked?
Wait / Retry?
Registry / State Update?
Ownership After
Cache After
Result
Final Error
```

### Final Gate

```text
P0 = 0
P1 = 0
All Frozen Steps Map to Actual Wiring
All Reachable Result Sources Match
All Reachable Final Error Sources Match
State Mutation Policy Match
Error Priority Match
No Existing Regression
```

成立時のみ：

```text
DESIGN ALGORITHM = ACTUAL WIRING
STATIC IMPLEMENTATION CLOSED
```

---

# 13. Phase 7：Public Wrapper Closure

Internal serviceを持つ設計では、Public wrapperはinternal static closure後に実装する。

Public wrapper reviewでは次を確認する。

- Public I/O
- Request build
- command enum
- error in policy
- internal service call
- Result extraction
- error out policy
- Public側へ内部resource logicが漏れていないこと
- connector pane

Thin wrapperにRegistry / ActiveX / ownership / cache / retry / waitを再実装しない。

---

# 14. Human Static Gate

Nigel Static PASS後、人間が最低限次を確認する。

- [ ] Broken Run Arrowなし
- [ ] connector pane正しい
- [ ] typedef brokenなし
- [ ] unexpected coercion dotなし
- [ ] required tunnel unwiredなし
- [ ] `Use Default If Unwired`へ依存していない
- [ ] enum item / ordinal正しい
- [ ] Case selector正しい
- [ ] Public I/O正しい
- [ ] Frozen Design外のlogicを追加していない

Human Static Gate後にGitHubのAs-Built状態を更新する。

---

# 15. GitHub正本管理

## 15.1 Single Canonical Document

1機能の詳細設計、アルゴリズム、GUI施工手順、As-Built状態は可能な限り1つのcanonical documentへ統合する。

別資料を作る場合は、役割とsuperseded関係を明示する。

## 15.2 Freeze時

GitHubへ最低限記録する。

```text
Status
Design Review Result
Frozen Algorithm
Reachable State Matrix
Result / Error Matrix
Implementation Slices
Static Acceptance
Runtime Pending
```

## 15.3 Implementation中

Frozen Algorithmを書き換えて実装へ合わせない。

設計変更が必要な場合：

```text
STOP
→ Design Change Candidate
→ Human Approval
→ Re-Freeze
→ Implementation再開
```

## 15.4 Closure時

actual implementationを基に次を更新する。

```text
IMPLEMENTED / AS-BUILT CLOSED
Human Static Check
Observable Design Drift
GUI Documentation Gap
Runtime / Hardware E2E status
```

---

# 16. Nigel Prompt共通ヘッダ

Nigelへレビューまたは施工指示を依頼する際は、原則としてPrompt冒頭へ次を入れる。

```text
READ ONLY / NO EDIT

対象Project:
<actual project path>

対象VI:
<VI path/name>

Design Authority:
このPrompt内に記載したFrozen Contract

重要:
NigelはGitHubへアクセスできない。
必要な契約はPrompt内へ埋め込む。

禁止:
VI編集
保存
typedef変更
設計変更
未確認memberの推測
```

実装手順作成時は`GUI INSTRUCTION GENERATION ONLY`を追加する。

---

# 17. STOP条件

次の場合は次Phaseへ進まない。

- P0 > 0
- P1 > 0
- Frozen Algorithmとactual wiringが不一致
- Design Authorityが競合
- unknown terminal / memberが設計を左右する
- current active VIを特定できない
- Nigel reviewが通信失敗などで途中終了
- root causeが未裁定
- Human Choice Requiredが未解決

通信失敗時は、返却済みevidenceだけを確定範囲とし、未返却部分を推測でPASS扱いしない。

---

# 18. 完成定義

VIの「完成」は次の3段階を区別する。

## 18.1 Design Closed

```text
FROZEN DESIGN
P0=0
P1=0
Observable Design Ambiguity=0
```

## 18.2 Static Closed

```text
Design Closed
Implementation Completed
As-Built Review PASS
Final Algorithm-to-Wiring Audit PASS
Human Static Gate PASS
DESIGN ALGORITHM = ACTUAL WIRING
```

## 18.3 Runtime Verified

```text
Static Closed
+ Runtime Test
+ Hardware / Driver / CANalyzer / TestStand E2E
+ Recovery / Timeout / Error scenario evidence
```

Static ClosedをRuntime Verifiedと表現しない。

---

# 19. 標準チェックリスト

## Design

- [ ] Evidence Gate完了
- [ ] GitHub既存正本確認
- [ ] local actual evidence確認
- [ ] Responsibility Boundary確定
- [ ] Functional Algorithm確定
- [ ] State Authority確定
- [ ] Error Contract確定
- [ ] Reachable State Matrix確定
- [ ] Result / Error Matrix確定
- [ ] P0=0 / P1=0
- [ ] GitHub Freeze済み

## Implementation

- [ ] Nigel GUI施工指示
- [ ] Human実装
- [ ] Incremental As-Built Review
- [ ] ChatGPT Drift Gate
- [ ] Slice P0=0 / P1=0

## Final

- [ ] Full Algorithm-to-Wiring Audit
- [ ] all Result roots一致
- [ ] all Error roots一致
- [ ] State mutation policy一致
- [ ] existing regressionなし
- [ ] Human Static Gate
- [ ] GitHub As-Built同期
- [ ] Runtime Pending / Verifiedを明記

---

# 20. 標準プロセス要約

```text
1. ChatGPTがGitHub資料ベースでDesign Candidate作成
2. Nigelがlocal actual環境を確認し設計検証
3. ChatGPT / Nigel / HumanでAlgorithmを反復しFreeze
4. Frozen AlgorithmをGitHub正本へ保存
5. NigelがFrozen DesignからGUI施工指示を作成
6. HumanがSlice単位で実装
7. Nigelがactual VIをREAD ONLY確認
8. ChatGPTがFrozen DesignとのDrift Gate
9. 全Slice完了後にFinal Algorithm-to-Wiring Audit
10. P0=0 / P1=0ならSTATIC CLOSED
11. GitHubをAs-Builtへ同期
12. Runtime / Hardware E2Eへ進む
```

この順序を崩す場合は、理由を対象設計正本へ記録する。
