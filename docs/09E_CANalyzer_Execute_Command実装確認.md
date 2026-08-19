# 09E. CANalyzer_Execute_Command.vi 実装確認

**最終整理日：2026-08-19**

> **本章の役割**：`CANalyzer_Execute_Command.vi` の実装完了後に、設計正本 [`09D_CANalyzer_Execute_Command設計.md`](./09D_CANalyzer_Execute_Command設計.md) と実VIの方針差分をSpot Checkした結果を記録する。
>
> 設計上の正本は09D。本章はAs-Built確認記録であり、設計契約を上書きしない。

---

# 1. Overall Verdict

**PASS**

`CANalyzer_Execute_Command.vi` は、09D確定設計との方針差分なしと判定した。

---

# 2. Spot Check結果

| Check | Result | Evidence |
|---|---|---|
| Non-reentrant | **PASS** | ユーザー目視確認済み。 |
| Pre-Write Validation | **PASS** | Write SysVarで `Registry Get → Resolve SysVar → Variable Ref validity → DBL Verify Tolerance Validation → Value To Variant → Write` の順を確認。`Verify=True AND Value Type=DBL AND Tolerance<0` では `-710112` を生成し、Value To Variant / Write / Read Back / Compareへ進まない。Variable Refはcleanup-safe pathへ進む。 |
| Prior Error Guard | **PASS** | Verify=Trueで `Write → Read Back → Variant To Value` の後にerror.statusで分岐し、prior error時はCompareを実行せず、`Verified?=False`、元Operation Errorを保持してcleanupへ進む。 |
| Verify Mismatch | **PASS** | prior errorなしの場合だけType Match / Value Matchを評価し、mismatch時は `-710108`、match時のみ `Verified?=True`。prior error時は `-710108` を生成しない。 |
| Ref Cleanup | **PASS** | Application/System/Measurement RefはCloseせず、Variable Refのみvalid時にClose。`Clear Errors → Close Reference → Merge Errors`でcleanupし、Operation ErrorをClose Errorより優先。 |

---

# 3. 確認済み最終契約

## 3.1 Concurrency

- `CANalyzer_Execute_Command.vi` は **Non-reentrant**。
- 初期版は **Global serialization**。
- Read / Writeの一連処理全体を同一Non-reentrant境界内で実行する。

## 3.2 Command

初期版は2値のみ。

```text
0 = Read SysVar
1 = Write SysVar
```

後続Commandは末尾追加とする。

## 3.3 Write事前Validation

```text
Verify After Write? = True
AND
Value Type = DBL
AND
DBL Verify Tolerance < 0
```

の場合：

```text
status = True
code = -710112
source = CANalyzer_Execute_Command.vi / Write SysVar / Invalid DBL Verify Tolerance
```

その後CANalyzerへWriteしない。

## 3.4 Prior Error Guard

Read Back / Variant変換などでprior errorが発生した場合：

- Compareしない。
- `Verified?=False`。
- 元error codeを保持する。
- cleanupへ進む。

## 3.5 Verify Mismatch

prior errorがない場合のみ比較を実行。

```text
Verified? = Type Match AND Value Match
```

mismatch時：

```text
status = True
code = -710108
```

## 3.6 Reference Ownership

| Ref | 扱い |
|---|---|
| Application Ref | Borrowed、Closeしない |
| System Ref | Borrowed、Closeしない |
| Measurement Ref | Borrowed、Closeしない |
| Variable Ref | Temporary、valid時にClose |

CleanupはOperation ErrorをPrimaryとする。

---

# 4. 設計差分判定

**09D確定設計との方針差分なし。**

`CANalyzer_Execute_Command.vi` はこの時点で初期Vertical Slice実装完了として扱う。

---

# 5. 次工程

次の依存VIとして `CANalyzer_Detect_Process.vi` の設計・人手実装へ進む。

目的はAutomation Open前後のCANalyzerプロセス状態を確認し、`Require Existing`のガードとApplication Ownership推定の補助情報として利用すること。

Process検出はCOM Running Object Tableへの登録を完全に証明するものではないため、Ownership判定の補助情報としてのみ使用する。曖昧な場合は `Application Ownership = Unknown` を維持する。
