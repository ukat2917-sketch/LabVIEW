# 09G. CANalyzer_Detect_Process.vi 実装確認（As-Built）

**確認日：2026-08-20**

> `CANalyzer_Detect_Process.vi` のFinal Closure Static Review結果を記録する。
> 設計正本は `09F_CANalyzer_Detect_Process設計.md`。

---

## 1. Overall Verdict

**PASS / READY**

`CANalyzer_Detect_Process.vi` は確定設計との方針差分なし。
Aggregation / Sticky Error / Final Error Gate の修正完了。
As-Built確定可能。

---

## 2. Final Fix Verification

| Check | Result | Evidence |
|---|---|---|
| Final Error Gate Exists | PASS | `Case Structure 2362` after `For Loop 1065` |
| Final Error.status Selector | PASS | `Unbundle By Name 642`, `290.value -> 642.status -> 2362` |
| Error TRUE → Found False | PASS | `CaseFrame 2376`, false constant to output |
| Error TRUE → Count 0 | PASS | `CaseFrame 2376`, zero constant to output |
| Error TRUE → Matched [] | PASS | `CaseFrame 2376`, empty string array to output |
| Error TRUE → Original Error Preserved | PASS | `CaseFrame 2376`, final operation error passed through |
| Success Result Builder Only On Error FALSE | PASS | `CaseFrame 2383` only uses `Array Size 1097` / `Greater? 1987` |
| Parse Failure Partial Results Suppressed | PASS | sticky `-710115` drives Final Error Gate TRUE and forces `False/0/[]` |
| Sticky -710115 Preserved | PASS | `ShiftReg 204` + sticky guard `3258` |
| Aggregation Preserved | PASS | `ShiftReg 196` accumulates matched names |
| Multiple Match Preserved | PASS | `Build Array 745` appends current image to previous array |
| Last-Value Bug Eliminated | PASS | final matched names originate from `ShiftReg 196.Right` |
| Output Consistency | PASS | success uses Array Size / >0; error forces default public result |
| Matched Names 1D String Array | PASS | output and accumulator are 1D String Array |

---

## 3. Regression Check

| Check | Result |
|---|---|
| Candidate Normalize | PASS |
| Incoming Error Bypass | PASS |
| System Exec | PASS |
| `-710114` | PASS |
| Normalize EOL / Row Split | PASS |
| INFO Handling | PASS |
| First Field Parse | PASS |
| `-710115` Generation | PASS |
| Search 1D Array | PASS |
| Exact Lowercase Match | PASS |

---

## 4. Edge Case Static Simulation

| Case | Result | Expected Outcome |
|---|---|---|
| Match → Non-Match | PASS | prior match preserved |
| Match → Match | PASS | count 2 / duplicate names retained |
| Match → Non-Match → Match | PASS | count 2 |
| Match → Parse Failure → Normal | PASS | `False / 0 / [] / -710115` |
| Match → Match → Parse Failure | PASS | `False / 0 / [] / -710115` |
| Zero Match | PASS | `False / 0 / [] / success` |
| Empty Candidates | PASS | `False / 0 / [] / success` |

---

## 5. Confirmed As-Built Architecture

```text
error in guard
↓
candidate Trim / lowercase / empty filter
↓
empty candidate guard
↓
System Exec: tasklist /FO CSV /NH
↓
mechanism error guard (-710114)
↓
Normalize End Of Line
↓
row split
↓
empty / INFO guard
↓
quoted first field parse
↓
parse error guard (-710115)
↓
running image lower case
↓
Search 1D Array exact match
↓
Matched Names accumulator (Shift Register)
↓
Sticky Operation Error accumulator
↓
Final Error Output Gate
  ├─ error → False / 0 / [] / original error
  └─ success → Array Size → Count → Found?
```

---

## 6. Findings Closed

### P0: Last-value bug
**CLOSED**

Normal loop output tunnelsからShift Register accumulatorへ変更され、途中のmatchが後続non-matchで消えない。

### P0: Multiple match未対応
**CLOSED**

Matched Namesをappend方式で保持し、同一exe複数instanceも複数要素として保持できる。

### P0: Sticky Error不足
**CLOSED**

Operation ErrorをShift Registerで保持し、`-710115`が後続正常rowで消えない。

### P1: Parse failure partial result leak
**CLOSED**

For Loop後のFinal Error Output Gateにより、error時のpublic outputは必ず `False / 0 / []` へ正規化される。

---

## 7. Remaining Findings

**None**

---

## 8. Final Status

```text
CANalyzer_Detect_Process.vi
Status = AS-BUILT CONFIRMED
Design Alignment = PASS
Critical / High / Medium open findings = 0
```

次工程：`CANalyzer_Open.vi` の詳細設計・人手実装。
