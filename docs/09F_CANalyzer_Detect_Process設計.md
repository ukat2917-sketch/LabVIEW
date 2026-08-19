# 09F. CANalyzer_Detect_Process.vi 最終設計

**最終整理日：2026-08-19**

> **本章の役割**：`CANalyzer_Detect_Process.vi` のProduction向け最終設計と、人手実装時の作業契約を定義する。
>
> 本VIは `CANalyzer_Open.vi` の前段で使用する補助Serviceであり、Windows上の対象process image name存在確認だけを担当する。Process存在はCANalyzer COM接続成功を保証しない。
>
> VI作成完了後は本章と実VIを差分レビューし、As-Built差分があれば設計変更か実装修正かを明示して確定する。

---

# 1. 目的

`CANalyzer_Detect_Process.vi` は、Automation Open前後にWindows上のCANalyzer関連process存在状態を確認する同期1-shot Service VIとする。

主用途：

1. `Launch Mode = Require Existing` の事前ガード
2. `Application Ownership` 推定の補助情報

ただし本VIはOwnershipを確定しない。

```text
Process exists
≠
CANalyzer COM connection guaranteed
```

最終接続判定は `CANalyzer_Open.vi` のAutomation Open結果で行う。

---

# 2. Responsibility Boundary

配置：

```text
60_CAN\20_Service\CANalyzer_Detect_Process.vi
```

本VIが行うこと：

- callerから候補process image name配列を受け取る
- 現在のWindows process一覧を1回取得する
- exact / case-insensitiveで候補と照合する
- 一致process instance数と一致名一覧を返す

本VIが行わないこと：

- CANalyzer Automation Open
- ActiveX Property / Invoke
- Session Registry操作
- Application Ownership確定
- Application Quit
- Measurement Start / Stop
- persistent state保持
- background monitoring

---

# 3. Detection Method

採用方式：

```text
System Exec VI
+
tasklist /FO CSV /NH
```

`cmd /c` は使用しない。

理由：

- Windows 11標準機能
- 追加ソフト不要
- .NET Ref cleanup不要
- process image nameを `.exe` 付きで扱える
- GUI実装が単純
- responsibilityが明確

System Exec設定：

```text
command line = tasklist /FO CSV /NH
wait until completion? = TRUE
run minimized? = TRUE
expected output size = 32768以上
working directory = 未配線
```

---

# 4. Final I/O Contract

## Inputs

| 端子 | 型 | 契約 |
|---|---|---|
| `Process Name Candidates` | 1D String Array | callerがWindows上の正式process image nameを渡す |
| `error in` | error cluster | prior error時は処理bypass |

## Outputs

| 端子 | 型 | 契約 |
|---|---|---|
| `Found?` | Boolean | `Process Count > 0` |
| `Process Count` | I32 | 一致したrunning process instance数 |
| `Matched Names` | 1D String Array | 一致したprocess image nameをinstanceごとに1要素 |
| `error out` | error cluster | incoming / detection errorを返す |

Connector Paneは標準patternを使用し、左に `Process Name Candidates` / `error in`、右に `Found?` / `Process Count` / `Matched Names` / `error out` を配置する。error in/outは下段に寄せる。

---

# 5. Process Matching Contract

候補文字列の扱い：

- 前後空白はTrimする
- 空文字 / whitespace-only candidateは無視する
- extensionは自動追加しない
- substring matchは禁止
- case-insensitive exact match
- callerが正式process image nameを渡す

例：

| candidate | running | 結果 |
|---|---|---|
| `CANalyzer.exe` | `CANalyzer.exe` | match |
| `CANalyzer.exe` | `canalyzer.exe` | match |
| `CANalyzer.exe` | `MyCANalyzer.exe` | no match |
| `CANalyzer.exe` | `CANalyzer64.exe` | no match |

1 running process instanceは最大1件として数える。複数candidateが同一processへ一致しても重複追加しない。

同一exeが2 instance存在する場合：

```text
Process Count = 2
Matched Names = ["CANalyzer.exe", "CANalyzer.exe"]
```

---

# 6. Incoming Error Contract

```text
error in.status = TRUE
```

の場合：

```text
System Execを実行しない
Found? = False
Process Count = 0
Matched Names = []
error out = error in
```

元errorをpass-throughする。

---

# 7. Empty Candidate Contract

Trim / 空文字除外後のcandidate arrayが空の場合：

```text
Found? = False
Process Count = 0
Matched Names = []
error out = success
```

candidate未設定はService errorとしない。

上位 `CANalyzer_Open.vi` が必要に応じてPolicy Errorへ変換する。

---

# 8. Mechanism Error Contract

## 8.1 System Exec自身が失敗

```text
System Exec.error out.status = TRUE
```

の場合：

```text
Found? = False
Process Count = 0
Matched Names = []
error out = System Exec.error out
```

元error codeを変更しない。

## 8.2 System Execは成功したがtasklist結果が不正

条件：

```text
System Exec.error out.status = FALSE
AND
(
  return code != 0
  OR
  stderr non-empty
)
```

の場合：

```text
status = True
code = -710114
source = CANalyzer_Detect_Process.vi\ntasklist return code=<n>
```

external process return codeをそのままLabVIEW error cluster.codeへ入れない。

stderrは必要に応じてsourceへ追記してよい。

Process 0件はerrorにしない。

---

# 9. Error Code Allocation

| Code | 意味 |
|---:|---|
| `-710102` | Session Not Found / Update Not Found |
| `-710104` | Measurement Timeout |
| `-710106` | Value Conversion Error |
| `-710108` | Verify Mismatch |
| `-710110` | Session ID Exhausted |
| `-710112` | Invalid DBL Verify Tolerance |
| `-710114` | tasklist mechanism failure |
| `-710115` | tasklist output parse failure |

`-710114` / `-710115` は `CANalyzer_Detect_Process.vi` で新規採用する。

---

# 10. Row Split Contract

`tasklist /FO CSV /NH` のstdoutは以下の順で処理する。

```text
System Exec.standard output
↓
Normalize End Of Line
↓
While Loop
↓
Match Pattern
```

重要：

- Row delimiterにString Constant `"\n"` を使わない
- **LabVIEWの `End of Line Constant` を使用する**
- comma splitしない

配線契約：

```text
Normalize End Of Line output
→ While Loop shift register initial value

shift register current text
→ Match Pattern.string

End of Line Constant
→ Match Pattern.pattern

Match Pattern.before substring
→ Current Row

Match Pattern.after substring
→ shift register next value
```

最後のremainderが空でなければ最終rowとして扱う。

---

# 11. Row Guard

各rowを以下の順で判定する。

| row | 動作 |
|---|---|
| empty row | skip |
| `INFO: No tasks are running...` | skip、0件扱い、非エラー |
| その他 | quoted first field抽出へ進む |

INFO行はlocale差があり得るため、最終実機確認ではtasklistが0件相当を返す条件を確認する。通常環境でprocess一覧が空になることは稀だが、本VIではINFO行を非エラーとして扱う。

---

# 12. CSV First Field Extraction

正常row例：

```text
"CANalyzer.exe","1234","Console","1","100,000 K"
```

今回必要なのは先頭quoted fieldだけ。

抽出手順：

1. row先頭が `"` であることを確認
2. 先頭quoteを除外
3. 次の `"` を検索
4. closing quote直前までを `Running Image Name` とする

PID / Session Name / Memory Usage等は解析しない。

CSVのcomma splitは禁止。

---

# 13. Parse Error Contract

以下をparse failureとする：

- row先頭がquoteではない
- closing quoteが見つからない
- first field抽出不能

parse failure時：

```text
Found? = False
Process Count = 0
Matched Names = []
status = True
code = -710115
source = CANalyzer_Detect_Process.vi\ntasklist output parse failure
```

必要に応じてrow先頭の短いprefixをsourceへ追記してよい。

---

# 14. Matching Core

各 `Running Image Name` に対して：

```text
To Lower Case(running image name)
↓
Normalized Candidate Array For Loop
↓
To Lower Case(candidate)
↓
Equal?
```

`Equal?` だけを使ってexact matchする。

substring searchは禁止。

1つでもcandidateに一致した場合、そのrunning process instanceを `Matched Names` に1要素だけ追加する。

---

# 15. Final Result Contract

```text
Matched Names Final Array
↓
Array Size
↓
Process Count
```

```text
Found? = Process Count > 0
```

成功pathでは `error out = no error`。

---

# 16. Resource / Ownership Contract

本VIは以下を使用しない：

- ActiveX Ref
- .NET Ref
- Session State
- Registry
- persistent state
- background task

したがってRef cleanup対象なし。

同期1-shot Service VIとする。

---

# 17. VI Execution Contract

```text
Execution = Non-reentrant
Auto error handling = Off
Show Front Panel When Called = Off
```

推奨Description：

```text
Detects whether any of the specified Windows process image names are currently running. Advisory only; does not guarantee CANalyzer COM connectivity.
```

---

# 18. Final Processing Order

```text
1. error in確認
2. candidate Trim / empty除外
3. empty candidate guard
4. System Exec: tasklist /FO CSV /NH
5. mechanism error guard
6. Normalize End Of Line
7. End of Line Constantでrow split
8. row guard
9. quoted first field抽出
10. parse error guard
11. case-insensitive exact match
12. Matched Names build
13. Process Count = Array Size
14. Found? = Process Count > 0
15. error out
```

---

# 19. Static Review Checklist

- [ ] Process Name Candidatesをハードコードしていない
- [ ] candidateをTrimしている
- [ ] empty / whitespace candidateを無視している
- [ ] empty candidate arrayはFalse / 0 / empty / success
- [ ] `tasklist /FO CSV /NH` を直接実行している
- [ ] `cmd /c` を使用していない
- [ ] incoming errorでSystem Execをbypassする
- [ ] `System Exec.error out.status=True` は元errorを保持する
- [ ] `return code != 0` またはstderr non-emptyは `-710114`
- [ ] external return codeをLabVIEW error codeへ直接流用していない
- [ ] `Normalize End Of Line` を使用している
- [ ] row delimiterに `End of Line Constant` を使用している
- [ ] row delimiterとしてString Constant `"\n"` を使用していない
- [ ] CSVをcomma splitしていない
- [ ] INFO rowを0件扱いにしている
- [ ] quoted first fieldだけをImage Nameとして抽出する
- [ ] malformed rowは `-710115`
- [ ] case-insensitive exact match
- [ ] substring matchなし
- [ ] 1 process instanceを重複カウントしない
- [ ] `Matched Names size = Process Count`
- [ ] `Found? = Process Count > 0`
- [ ] process 0件をerrorにしていない
- [ ] Process存在をCOM接続成功とみなしていない
- [ ] ActiveX操作なし
- [ ] .NETなし
- [ ] Session Registryなし
- [ ] persistent stateなし
- [ ] Execution = Non-reentrant
- [ ] Connector Pane明示
- [ ] Broken Run Arrow = NO

---

# 20. As-Built Review Gate

VI作成完了後、少なくとも以下を実VIでSpot Checkする。

| Check | 必須 |
|---|---|
| System Exec direct tasklist | PASS |
| Incoming Error Bypass | PASS |
| Candidate Normalize / Empty Guard | PASS |
| Normalize End Of Line | PASS |
| End of Line Constant row split | PASS |
| `-710114` mechanism failure | PASS |
| `-710115` parse failure | PASS |
| Quoted First Field Parse | PASS |
| Case-insensitive exact match | PASS |
| Duplicate process count防止 | PASS |
| Process Count / Found? relation | PASS |
| ActiveX / persistent stateなし | PASS |
| Non-reentrant | PASS |
| Broken Run Arrow | NO |

全項目PASSなら本章との**方針差分なし**としてAs-Built確定する。

---

# 21. Next Step

本VIのAs-Built Review PASS後に `CANalyzer_Open.vi` の詳細設計・人手実装へ進む。
