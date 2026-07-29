# A1A.7 `FG420_Prepare_Device.vi` 詳細作成手順

**正本範囲**：1台のFG420をInitializeし、IDNを検証し、電源投入時出力OFF、2ch独立モード、カップリング無効を設定する複合VIの作成手順。

参照：

- [A1A_FG420複数台2ch出力リミットPoC.md](./A1A_FG420複数台2ch出力リミットPoC.md)
- [00A_LabVIEW実装資料の記述ルール.md](./00A_LabVIEW実装資料の記述ルール.md)
- [00B_LabVIEW学習型VI設計ルール.md](./00B_LabVIEW学習型VI設計ルール.md)

既存VI名、typedef、処理順は変更しない。

---

## 0. 実現したい機能とVIの責務

1台分の`FG420_Device_Config.ctl`を受け取り、次の順序で機器準備を行う。

```text
FG420_Init.vi
  → FG420_Get_ID.vi
  → IDN文字列検証
  → FG420_Set_PowerOn_Output.vi（OFF）
  → FG420_Set_ChanMode.vi（INDependent）
  → FG420_Set_Coupling.vi（NONE）
```

処理の成功履歴を`FG420_Device_State.ctl`へ記録する。

本VIはチャネル設定、出力ON、Wait、Close、複数台反復を担当しない。Initialize成功後に途中エラーが起きた場合も本VI内ではCloseせず、VISA参照、State、Original ErrorをPoCへ返す。

---

## 1. 入力データの実体

`Device Config`は単一`FG420_Device_Config.ctl`である。

```text
FG420_Device_Config.ctl
├─ Enabled?          ※PoC側で使用。本VIへ入った時点では有効機器として扱う
├─ Logical Name      ※ID不一致error sourceへ使用
├─ VISA Resource     ※FG420_Init.viへ接続
├─ ID Check?         ※FG420_Init.viへ接続
├─ Reset?            ※FG420_Init.viへ接続
├─ Ch1 Config        ※本VIでは未使用
└─ Ch2 Config        ※本VIでは未使用
```

| 入力端子 | 型 | 用途 |
|---|---|---|
| `Device Config` | `FG420_Device_Config.ctl` | 1台分の初期化条件 |
| `error in` | error cluster | 前段エラー |

---

## 2. 出力データモデル

| 出力端子 | 型 | 生成元 |
|---|---|---|
| `VISA reference out` | VISA session | 最後に実行またはバイパスしたWrapperのVISA出力 |
| `IDN` | String | `FG420_Get_ID.vi / IDN String` |
| `Device State` | `FG420_Device_State.ctl` | Bundle By Nameを直列更新したState |
| `Status` | `Status.ctl` | 最終errorから生成 |
| `TestError` | `TestError.ctl` | 最終errorから生成 |
| `error out` | error cluster | 元error、Init error、ID error、ローカルID不一致error、設定error |

### 2.1 State更新規則

| フィールド | Trueへ更新する条件 | 本VIでの初期値 |
|---|---|---:|
| `Initialized?` | `FG420_Init.vi / error out.status=False` | False |
| `ID Read?` | Get ID成功かつIDNが空文字列でない | False |
| `Independent Mode?` | Set ChanMode成功 | False |
| `Coupling Disabled?` | Set Coupling成功 | False |
| `IDN` | Get IDが返した文字列 | 空文字列 |
| `Ch1 Configured?` | 本VIでは更新しない | False |
| `Ch2 Configured?` | 本VIでは更新しない | False |
| `Ch1 Output On?` | 本VIでは更新しない | False |
| `Ch2 Output On?` | 本VIでは更新しない | False |
| `Closed?` | 本VIでは更新しない | False |

---

## 3. 前提条件・異常条件

| 条件 | 動作 |
|---|---|
| `error in.status=True` | Initを呼ばず、初期State、空IDN、元errorを返す |
| Init失敗 | `Initialized?=False`。Close対象外 |
| Init成功後に後段失敗 | `Initialized?=True`を維持。PoC CleanupでClose対象 |
| Get ID失敗 | ID検証と後段設定Wrapperはerror in=Trueで実処理をスキップ |
| IDNがFG420でない | -710130を生成。Initialized=True、ID Read=Trueを維持 |
| Set ChanMode失敗 | Independent Mode?=False、Coupling Disabled?=False |
| Set Coupling失敗 | Independent Mode?=True、Coupling Disabled?=False |

IDNは次の正規表現へ一致する必要がある。

```text
^YOKOGAWA,FG420,
```

ローカルエラーsource全文：

```text
FG420_Prepare_Device.vi: Unexpected instrument ID. LogicalName=%s, IDN=%s, ExpectedPrefix=YOKOGAWA,FG420,
```

CodeはI32`-710130`とする。

---

## 4. 処理アルゴリズム

```text
if error in.status=True:
    VISA out = Device Config.VISA Resource
    IDN = empty
    Device State = typedef initial value
    error out = error in
else:
    State = typedef initial value

    Initを呼ぶ
    Initialized? = NOT Init error.status

    Get IDを呼ぶ
    ID Read? = NOT Get ID error.status AND IDN is not empty
    State.IDN = IDN

    if Get ID error.status=False:
        IDNが^YOKOGAWA,FG420,へ一致するか判定
        不一致なら-710130

    Set PowerOn OutputをOFFで呼ぶ
    Set ChanModeをINDependentで呼ぶ
    Independent Mode? = NOT ChanMode error.status
    Set CouplingをNONEで呼ぶ
    Coupling Disabled? = NOT Coupling error.status

    VISA、IDN、State、Final Errorを返す
```

---

## 5. LabVIEW構造の選定理由

| 必要な処理 | 構造 | 理由 |
|---|---|---|
| 元error時にInitializeしない | 外側Case Structure | 元errorを最優先する |
| Get ID error時にIDNローカルerrorを作らない | Get ID Error Case | 既存ドライバerrorを保持する |
| FG420以外を拒否する | IDN Valid Case | 2ch PoCへ異機種を進めない |
| 成功段階をStateへ残す | Bundle By Name直列更新 | 未変更フィールドを保持する |
| Init→ID→安全設定の順序 | VISA + error直列配線 | 実行順を固定する |

LoopとShift Registerは使用しない。1回の呼出しで1台を処理し、StateはBundle By Nameで左から右へ更新するためである。

### 5.1 完成時の構造

```text
error in.status Case
├─ True
│  ├─ VISA out = Device Config.VISA Resource
│  ├─ IDN = empty String
│  ├─ State = FG420_Device_State.ctl initial value
│  └─ Final Error = error in
└─ False
   ├─ FG420_Init.vi
   ├─ Bundle By Name：Initialized?
   ├─ FG420_Get_ID.vi
   ├─ Bundle By Name：ID Read? / IDN
   ├─ Get ID Error? Case
   │  ├─ True  → ID検証をスキップ
   │  └─ False
   │     └─ IDN Valid? Case
   │        ├─ False → -710130
   │        └─ True  → errorを通過
   ├─ FG420_Set_PowerOn_Output.vi（OFF）
   ├─ FG420_Set_ChanMode.vi（INDependent）
   ├─ Bundle By Name：Independent Mode?
   ├─ FG420_Set_Coupling.vi（NONE）
   ├─ Bundle By Name：Coupling Disabled?
   └─ VISA / IDN / State / Final Error

Final Error → Error_To_TestStatus.vi
```

外側Case右側へ次の4トンネルを作る。

1. VISA reference
2. IDN String
3. Device State
4. Final Error

---

## 6. フロントパネル入出力と接続元・接続先

### 6.1 新規VIを作成する

1. `ファイル → 新規VI`を選択する。
2. `10_FG420\FG420_Prepare_Device.vi`として保存する。
3. フロントパネルを開く。

### 6.2 制御器と表示器

1. `FG420_Device_Config.ctl`を左上へ配置し、ラベルを`Device Config`にする。
2. error cluster制御器を左下へ配置し、ラベルを`error in`にする。
3. VISA resource name表示器を右上へ配置し、ラベルを`VISA reference out`にする。
4. 文字列表示器を配置し、ラベルを`IDN`にする。
5. `FG420_Device_State.ctl`表示器を配置し、ラベルを`Device State`にする。
6. `Status.ctl`、`TestError.ctl`、error cluster表示器を右側へ配置する。

### 6.3 コネクタペイン

8端子以上のパターンを使用する。

```text
左上   Device Config          右上   VISA reference out
左下   error in               右2    IDN
                                右3    Device State
                                右4    Status
                                右5    TestError
                                右下   error out
```

`Device Config`を必須、`error in`を推奨に設定する。

---

## 7. 配置する関数およびSubVI

| 数 | 日本語名 | 英語名 | 配置場所 |
|---:|---|---|---|
| 2以上 | 名前でアンバンドル | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 4 | 名前でバンドル | Bundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 3 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 1 | 正規表現に一致 | Match Regular Expression | プログラミング → 文字列 |
| 1 | 文字列長 | String Length | プログラミング → 文字列 |
| 1 | 空文字列?判定用等しい? | Equal? | プログラミング → 比較 |
| 必要数 | 否定、AND | Not / Compound Arithmetic | プログラミング → Boolean |
| 1 | 文字列にフォーマット | Format Into String | プログラミング → 文字列 |
| 1 | `FG420_Init.vi` | SubVI | `10_FG420` |
| 1 | `FG420_Get_ID.vi` | SubVI | `10_FG420` |
| 1 | `FG420_Set_PowerOn_Output.vi` | SubVI | `10_FG420` |
| 1 | `FG420_Set_ChanMode.vi` | SubVI | `10_FG420` |
| 1 | `FG420_Set_Coupling.vi` | SubVI | `10_FG420` |
| 1 | `Error_To_TestStatus.vi` | SubVI | `00_Common` |

### 7.1 配置順

```text
列1：Device Config Unbundle / State初期値 / error status
列2：外側error Case
列3：FG420_Init.vi + Initialized? Bundle
列4：FG420_Get_ID.vi + ID Read?/IDN Bundle
列5：Get ID Error Case + IDN Valid Case
列6：Set PowerOn Output.vi
列7：Set ChanMode.vi + Independent Mode? Bundle
列8：Set Coupling.vi + Coupling Disabled? Bundle
列9：Error_To_TestStatus.vi
```

VISA wireを上段、State wireを中央、error wireを下段へ通す。

---

## 8. 配線順

### 8.1 Device Config展開とState初期値

1. `Device Config`をUnbundle By Nameの`cluster`端子へ接続する。
2. `VISA Resource`、`ID Check?`、`Reset?`、`Logical Name`を表示する。
3. `Enabled?`、`Ch1 Config`、`Ch2 Config`は本VIで使用しないため、表示しないかコメント`PoC側で使用`を付ける。
4. ブロックダイアグラムへ`FG420_Device_State.ctl`定数を配置する。
5. typedef定数を既定値に戻し、全Boolean=False、IDN=空文字列であることを確認する。
6. State定数出力を`Initial Device State`とする。
7. `error in`をUnbundle By Nameへ接続し、`status`を取り出す。
8. `status`を外側Case selectorへ接続する。

### 8.2 外側True Case

9. `VISA Resource`をVISA出力トンネルへ接続する。
10. 空文字列定数`""`をIDNトンネルへ接続する。
11. `Initial Device State`をStateトンネルへ接続する。
12. `error in`をFinal Errorトンネルへ接続する。
13. TrueケースにはFG420 Wrapperを配置しない。

### 8.3 Init

14. 外側Falseケースへ`FG420_Init.vi`を配置する。
15. `VISA Resource`を`FG420_Init.vi / VISA Resource`へ接続する。
16. `ID Check?`を`FG420_Init.vi / ID Check?`へ接続する。
17. `Reset?`を`FG420_Init.vi / Reset?`へ接続する。
18. `error in`を`FG420_Init.vi / error in`へ接続する。
19. InitのVISA出力を`VISA After Init`、error outを`Error After Init`とする。
20. `Error After Init`をUnbundle By Nameへ接続し、`status`を取り出す。
21. `status`を否定（Not）へ接続する。
22. Not出力を`Init Succeeded?`とする。
23. `Initial Device State`を1個目のBundle By Nameの基準clusterへ接続する。
24. `Init Succeeded?`を`Initialized?`へ接続する。
25. Bundle出力を`State After Init`とする。

### 8.4 Get IDとID Read? / IDN更新

26. `VISA After Init`を`FG420_Get_ID.vi / VISA reference in`へ接続する。
27. `Error After Init`を`FG420_Get_ID.vi / error in`へ接続する。
28. Get IDのVISA outを`VISA After ID`、IDN Stringを`Read IDN`、error outを`Error After ID`とする。
29. `Read IDN`を文字列長（String Length）の`string`へ接続する。
30. String Length出力を大きい?（Greater?）の`x`へ接続する。
31. I32定数`0`をGreater?の`y`へ接続する。
32. Greater?出力を`IDN Not Empty?`とする。
33. `Error After ID`のstatusをNotへ接続し、`ID Read Call Succeeded?`を作る。
34. `ID Read Call Succeeded?`と`IDN Not Empty?`をANDへ接続する。
35. AND出力を`ID Read?`とする。
36. `State After Init`を2個目のBundle By Nameの基準clusterへ接続する。
37. `ID Read?`を同名フィールドへ接続する。
38. `Read IDN`を`IDN`フィールドへ接続する。
39. Bundle出力を`State After ID`とする。

### 8.5 Get ID Error CaseとIDN検証

40. `Error After ID.status`をGet ID Error Caseのselectorへ接続する。
41. Trueケースでは`Error After ID`をID Validation Error出力トンネルへ接続する。
42. TrueケースではIDN検証関数を配置しない。
43. Falseケースでは`Read IDN`を正規表現に一致（Match Regular Expression）の`string`へ接続する。
44. 文字列定数`^YOKOGAWA,FG420,`を`regular expression`へ接続する。
45. `offset past match`出力を大きい?（Greater?）の`x`へ接続する。
46. I32定数`0`をGreater?の`y`へ接続する。
47. Greater?出力を`IDN Valid?` Case selectorへ接続する。
48. IDN Valid=Trueケースでは`Error After ID`をValidation Errorトンネルへ接続する。
49. IDN Valid=Falseケースでは`Logical Name`と`Read IDN`をFormat Into Stringへ順に接続する。
50. 書式文字列へ-710130のsource全文を設定する。
51. `Error After ID`をBundle By Nameの基準clusterへ接続する。
52. Boolean定数`True`をstatus、I32定数`-710130`をcode、生成文字列をsourceへ接続する。
53. Bundle出力をValidation Errorトンネルへ接続する。
54. Get ID Error Case出力を`Error After ID Validation`とする。

### 8.6 PowerOn Output OFF

55. `VISA After ID`を`FG420_Set_PowerOn_Output.vi / VISA reference in`へ接続する。
56. PowerOn Mode Enum定数`OFF`を`Mode`へ接続する。
57. `Error After ID Validation`を`error in`へ接続する。
58. VISA outを`VISA After PowerOn OFF`、error outを`Error After PowerOn OFF`とする。

### 8.7 ChanModeとIndependent Mode?更新

59. `VISA After PowerOn OFF`を`FG420_Set_ChanMode.vi / VISA reference in`へ接続する。
60. Channel Mode Enum定数`INDependent`を`Channel Mode`へ接続する。
61. `Error After PowerOn OFF`を`error in`へ接続する。
62. VISA outを`VISA After ChanMode`、error outを`Error After ChanMode`とする。
63. `Error After ChanMode.status`をNotへ接続する。
64. Not出力を`Independent Mode Set?`とする。
65. `State After ID`を3個目のBundle By Nameの基準clusterへ接続する。
66. `Independent Mode Set?`を`Independent Mode?`へ接続する。
67. Bundle出力を`State After ChanMode`とする。

### 8.8 Coupling NONEとState更新

68. `VISA After ChanMode`を`FG420_Set_Coupling.vi / VISA reference in`へ接続する。
69. Couple Enum定数`NONE`を`Couple`へ接続する。
70. `Error After ChanMode`を`error in`へ接続する。
71. VISA outをVISA出力トンネルへ接続する。
72. error outを`Final Error`トンネルへ接続する。
73. Coupling error statusをNotへ接続する。
74. Not出力を`Coupling Disabled Set?`とする。
75. `State After ChanMode`を4個目のBundle By Nameの基準clusterへ接続する。
76. `Coupling Disabled Set?`を`Coupling Disabled?`へ接続する。
77. Bundle出力をStateトンネルへ接続する。
78. `Read IDN`をIDNトンネルへ接続する。

### 8.9 Status / TestError

79. 外側CaseのFinal Error出力を`Error_To_TestStatus.vi / error in`へ接続する。
80. String定数`FG420`を`Device Name`へ接続する。
81. Status、TestError、error outを各表示器へ接続する。
82. 外側CaseのVISA、IDN、Stateを各表示器へ接続する。

### 8.10 途中失敗時のClose要否

| 失敗位置 | Initialized? | ID Read? | Independent? | Coupling Disabled? | Close要否 |
|---|---|---|---|---|---|
| error in=True | False | False | False | False | 不要 |
| Init失敗 | False | False | False | False | 不要 |
| Get ID失敗 | True | False | False | False | 必要 |
| IDN不一致 | True | True | False | False | 必要 |
| PowerOn OFF失敗 | True | True | False | False | 必要 |
| ChanMode失敗 | True | True | False | False | 必要 |
| Coupling失敗 | True | True | True | False | 必要 |
| 正常 | True | True | True | True | PoC終了時に必要 |

本VIでは`FG420_Close.vi`を呼ばない。PoCは`Initialized?=True AND Closed?=False`をCleanup条件にする。

---

## 9. 単体テスト

| No. | 条件 | 期待結果 |
|---:|---|---|
| 1 | 正常FG420、ID Check=True、Reset=True | 4状態True、IDN取得、no error |
| 2 | ID Check=False、Reset=False | Init端子へ値が渡り後続正常 |
| 3 | FG410 IDN | -710130、Initialized=True、ID Read=True、Close必要 |
| 4 | 空IDN | ID Read=False、Get ID errorまたはID不正error |
| 5 | Initでerror注入 | Initialized=False、Close不要 |
| 6 | Get IDでerror注入 | Initialized=True、後続Wrapper実処理スキップ、Close必要 |
| 7 | Set ChanModeでerror注入 | Independent=False、Coupling=False、Close必要 |
| 8 | Set Couplingでerror注入 | Independent=True、Coupling=False、Close必要 |
| 9 | error in.status=True、code=-123 | Init未実行、初期State、元error |

---

## 完了確認

- [ ] State初期値をtypedef定数から作成した。
- [ ] Bundle By Nameを4段直列に接続した。
- [ ] 各Bundleの基準clusterへ直前の更新後Stateを接続した。
- [ ] IDN不一致時にInitialized?とID Read?を保持した。
- [ ] Prepare内へCloseを配置していない。
- [ ] Final ErrorからStatus / TestErrorを1回だけ生成した。
