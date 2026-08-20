# 09F. CANalyzer_Detect_Process.vi 最終設計

**最終整理日：2026-08-20**

> **本章の役割**：`CANalyzer_Detect_Process.vi` のProduction向け確定設計を定義する。
> 本VIは `CANalyzer_Open.vi` の前段で使用する補助Serviceであり、Windows上の対象process image name存在確認だけを担当する。Process存在はCANalyzer COM接続成功を保証しない。
>
> 2026-08-20のAs-Built review結果を反映し、実装と一致する最終契約へ更新した。

---

## 1. 目的

`CANalyzer_Detect_Process.vi` は、Automation Open前後にWindows上のCANalyzer関連process存在状態を確認する同期1-shot Service VIとする。

主用途：

1. `Launch Mode = Require Existing` の事前ガード
2. `Application Ownership` 推定の補助情報

本VIはOwnershipを確定しない。

```text
Process exists != CANalyzer COM connection guaranteed
```

最終接続判定は `CANalyzer_Open.vi` のAutomation Open結果で行う。

---

## 2. 配置と責務

```text
60_CAN\20_Service\CANalyzer_Detect_Process.vi
```

本VIが行うこと：

- callerから候補process image name配列を受け取る
- Windows process一覧を1回取得する
- candidateをTrim / lowercase正規化する
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

## 3. Detection Method

採用方式：

```text
System Exec VI
+
tasklist /FO CSV /NH
```

`cmd /c` は使用しない。

System Exec設定：

```text
command line = tasklist /FO CSV /NH
wait until completion? = TRUE
run minimized? = TRUE
working directory = 未配線
```

---

## 4. I/O Contract

### Inputs

| 端子 | 型 | 契約 |
|---|---|---|
| `Process Name Candidates` | 1D String Array | callerが正式process image nameを渡す |
| `error in` | error cluster | prior error時は処理bypass |

### Outputs

| 端子 | 型 | 契約 |
|---|---|---|
| `Found?` | Boolean | 成功時 `Process Count > 0` |
| `Process Count` | I32 | 一致したrunning process instance数 |
| `Matched Names` | 1D String Array | 一致したprocess image nameをinstanceごとに1要素 |
| `error out` | error cluster | incoming / detection / parse error |

成功時は必ず：

```text
Process Count = Array Size(Matched Names)
Found? = Process Count > 0
```

error時は必ず：

```text
Found? = False
Process Count = 0
Matched Names = []
```

---

## 5. Candidate Normalize Contract

各candidateへ以下を適用する。

```text
Trim Whitespace
↓
To Lower Case
↓
empty / whitespace-onlyを除外
```

正規化後candidate arrayが空の場合：

```text
Found? = False
Process Count = 0
Matched Names = []
error out = success
```

extension自動追加なし、substring match禁止。

---

## 6. Incoming Error Contract

`error in.status = TRUE` の場合：

```text
System Execを実行しない
Found? = False
Process Count = 0
Matched Names = []
error out = error in
```

元errorをpass-throughする。

---

## 7. Mechanism Error Contract

### 7.1 System Exec自身が失敗

`System Exec.error out.status = TRUE` の場合：

```text
Found? = False
Process Count = 0
Matched Names = []
error out = System Exec.error out
```

元error codeを変更しない。

### 7.2 tasklist異常終了

条件：

```text
System Exec.error out.status = FALSE
AND
(return code != 0 OR stderr non-empty)
```

の場合：

```text
status = True
code = -710114
source contains: tasklist return code=<n>
```

external return codeをLabVIEW error codeへ直接流用しない。

Process 0件はerrorにしない。

---

## 8. Error Code Allocation

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

---

## 9. stdout Normalize / Row Split Contract

`standard output` は以下で処理する。

```text
System Exec.standard output
↓
Normalize End Of Line
↓
While Loop
↓
Match Pattern
```

As-Built確定仕様：

- `Normalize End Of Line` を通す
- row splitは改行 `\n` を `Match Pattern` のpatternとして使用する
- comma splitは禁止
- empty rowはskip
- `INFO: No tasks are running...` は結果対象外かつ非エラー

このVIではCSV全列parserを作らず、processごとのrow分割だけを行う。

---

## 10. CSV First Field Extraction Contract

正常row例：

```text
"CANalyzer.exe","1234","Console","1","100,000 K"
```

必要なのは先頭quoted fieldのみ。

抽出手順：

1. row先頭が `"` か確認
2. 先頭quoteを除去
3. 次のclosing quoteを検索
4. closing quote直前までを `Running Image Name` とする

comma splitは禁止。

以下はparse failure：

- row先頭がquoteでない
- closing quoteが見つからない
- first field抽出不能

parse failure時：

```text
status = True
code = -710115
source = CANalyzer_Detect_Process.vi\ntasklist output parse failure
```

---

## 11. Matching Contract

`Running Image Name` を `To Lower Case` し、正規化済みcandidate arrayへ `Search 1D Array` を行う。

```text
Running Image Name
↓
To Lower Case
↓
Search 1D Array(Normalized Candidate Array)
↓
index != -1 ならmatch
```

これによりcase-insensitive exact matchとする。

substring検索は禁止。

同一exeが2 instance存在する場合は2件として保持する。

---

## 12. Loop Aggregation Contract

row処理For Loopではlast-value出力を禁止する。

最低限以下をloop全体で保持する：

### Matched Names accumulator

- 型：1D String Array
- 初期値：`[]`
- match時：previous arrayへcurrent nameをappend
- non-match / INFO / empty row：previous arrayを保持

### Operation Error accumulator

- 型：error cluster
- sticky error
- 一度 `status=True` になったら後続rowでsuccessへ戻さない
- parse failure `-710115` を後続iterationで上書きしない

---

## 13. Final Error Output Gate

For Loop終了後、Final Operation Error.statusでCase分岐する。

### TRUE

```text
Found? = False
Process Count = 0
Matched Names = []
error out = Final Operation Error
```

内部Matched Names accumulatorにpartial resultが残っていても、public outputへ出さない。

### FALSE

```text
Final Matched Names
↓
Array Size
↓
Process Count
↓
> 0
↓
Found?
```

`Matched Names = Final Matched Names`、`error out = success`。

---

## 14. Resource / Execution Contract

本VIは以下を使用しない：

- ActiveX Ref
- .NET Ref
- Session Registry
- persistent state
- background task

VI Properties：

```text
Execution = Non-reentrant
Auto error handling = Off
Show Front Panel When Called = Off
```

---

## 15. Final Processing Order

```text
1. error in確認
2. candidate Trim / lowercase / empty除外
3. empty candidate guard
4. System Exec: tasklist /FO CSV /NH
5. System Exec error guard
6. return code / stderr guard (-710114)
7. Normalize End Of Line
8. \nでrow split
9. empty / INFO row guard
10. quoted first field抽出
11. parse error guard (-710115)
12. running name lowercase
13. Search 1D Array exact match
14. Matched Names accumulator更新
15. Sticky Error accumulator更新
16. Final Error Output Gate
17. success時 Array Size → Process Count
18. success時 Process Count > 0 → Found?
```

---

## 16. As-Built Review Gate

全項目PASSを必須とする。

- [x] Candidate Normalize
- [x] Incoming Error Bypass
- [x] `tasklist /FO CSV /NH` direct execution
- [x] `-710114` mechanism failure
- [x] Normalize End Of Line
- [x] row split
- [x] INFO handling
- [x] quoted first field parse
- [x] `-710115` parse failure
- [x] lowercase exact match
- [x] Search 1D Array
- [x] Matched Names accumulator
- [x] Multiple match accumulation
- [x] Sticky error accumulator
- [x] Last-value bug eliminated
- [x] Final Error Output Gate
- [x] parse failure partial result suppression
- [x] `Process Count = Array Size(Matched Names)`
- [x] `Found? = Process Count > 0`
- [x] Matched Names = 1D String Array

As-Built Review結果は `09G_CANalyzer_Detect_Process実装確認.md` を参照する。

---

## 17. Next Step

`CANalyzer_Detect_Process.vi` はAs-Built確定済み。

次は `CANalyzer_Open.vi` の詳細設計・人手実装へ進む。
