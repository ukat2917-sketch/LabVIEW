# A1A.6 `FG420_Configure_Channel_Safe.vi` 詳細作成手順

**正本範囲**：1台のFG420の1チャネルについて、出力OFF、負荷設定、機器Min/Max取得、出力リミット判定、波形・周波数・振幅・オフセット設定を行う複合VIの作成手順。

参照：

- [A1A_FG420複数台2ch出力リミットPoC.md](./A1A_FG420複数台2ch出力リミットPoC.md)
- [A1A_05_FG420_Apply_Output_Limit_vi_詳細作成手順.md](./A1A_05_FG420_Apply_Output_Limit_vi_詳細作成手順.md)
- [00A_LabVIEW実装資料の記述ルール.md](./00A_LabVIEW実装資料の記述ルール.md)
- [00B_LabVIEW学習型VI設計ルール.md](./00B_LabVIEW学習型VI設計ルール.md)

既存VI名、typedef、呼出し順は変更しない。

---

## 0. 実現したい機能とVIの責務

`FG420_Channel_Config.ctl`に格納された1チャネル分の条件を読み取り、次の順で安全に設定する。

```text
Enabled?
  → FG420_Output.vi（OFF）
  → FG420_Set_Load.vi
  → FG420_Query_Ampl_Bound.vi（Minimum）
  → FG420_Query_Ampl_Bound.vi（Maximum）
  → FG420_Query_Offset_Bound.vi（Minimum）
  → FG420_Query_Offset_Bound.vi（Maximum）
  → FG420_Apply_Output_Limit.vi
  → FG420_Set_Func.vi
  → FG420_Set_Freq.vi
  → FG420_Set_Ampl.vi
  → FG420_Set_Offset.vi
```

本VIは出力ON、Wait、Close、複数台反復を担当しない。`Channel Config.Output On?`はPoC側で使用する。

---

## 1. 入力データの実体

`Channel Config`は単一`FG420_Channel_Config.ctl`である。配列ではない。

```text
FG420_Channel_Config.ctl
├─ Enabled?
├─ Channel
├─ Function
├─ Frequency Hz
├─ Load Infinity?
├─ Load Ohm
├─ Requested Amplitude Vpp
├─ Requested Offset V
├─ Output Limit Abs V
├─ Limit Mode
└─ Output On?  ※本VIでは機器出力へ接続しない
```

| 入力端子 | 型 | 用途 |
|---|---|---|
| `VISA reference in` | VISA session | 対象FG420のセッション |
| `Channel Config` | `FG420_Channel_Config.ctl` | 1チャネル分の設定 |
| `error in` | error cluster | 前段エラー |

---

## 2. 出力データモデル

| 出力端子 | 型 | 生成元 |
|---|---|---|
| `VISA reference out` | VISA session | 最後に実行またはバイパスしたWrapperのVISA出力 |
| `Applied Amplitude Vpp` | DBL | Limit VI出力 |
| `Applied Offset V` | DBL | Limit VI出力 |
| `Positive Peak V` | DBL | Limit VI出力 |
| `Negative Peak V` | DBL | Limit VI出力 |
| `Limited?` | Boolean | Limit VI出力 |
| `Status` | `Status.ctl` | 最終errorを`Error_To_TestStatus.vi`へ入力して生成 |
| `TestError` | `TestError.ctl` | 最終errorを`Error_To_TestStatus.vi`へ入力して生成 |
| `error out` | error cluster | 最初に発生したWrapper、Query、Limit、設定error |

---

## 3. 前提条件・異常条件

| 条件 | 動作 |
|---|---|
| `error in.status=True` | 全SubVIを呼ばず、VISAを素通り、DBL=0、Limited=False、元errorを返す |
| `Channel Config.Enabled?=False` | 対象チャネルを変更せず、VISAとerrorを素通りする |
| Output OFF～Query途中でerror | 後段Wrapperはerror in=Trueにより実ドライバを呼ばない |
| Limit VIがRejectまたは入力異常 | Function以降を呼ばず、Limit結果とLimit errorを返す |
| Function～Offset途中でerror | 後続Wrapperは実ドライバを呼ばず、最初のerrorを保持する |
| `Channel`がCh1 / Ch2以外 | 既存Wrapperの入力検証errorを返す |

---

## 4. 処理アルゴリズム

```text
if error in.status=True:
    VISAを素通り
    数値出力=0
    Limited=False
    error out=error in
elif Channel Config.Enabled?=False:
    VISAを素通り
    数値出力=0
    Limited=False
    error out=error in
else:
    対象ChannelをOFF
    Loadを設定
    Amplitude Minimumを取得
    Amplitude Maximumを取得
    Offset Minimumを取得
    Offset Maximumを取得
    Limit VIへ要求値、機器Min/Max、Limit、Modeを渡す

    if Limit VI error.status=True:
        Function以降を呼ばない
        VISA=Offset Query後のVISA
        Limit結果とLimit errorを返す
    else:
        Functionを設定
        Frequencyを設定
        Applied Amplitudeを設定
        Applied Offsetを設定

最終errorからStatus / TestErrorを生成
```

---

## 5. LabVIEW構造の選定理由

| 必要な処理 | 構造 | 理由 |
|---|---|---|
| 元error時に機器操作しない | 外側Case Structure | 元errorを保持する |
| Disabledチャネルを変更しない | Enabled Case Structure | VISA通信を完全にバイパスする |
| Limit error時に設定値を送らない | Limit Error Case Structure | Function以降を配置しない経路を作る |
| SubVI実行順を固定する | VISA wire + error wire直列 | Load、Query、Limit、設定の順序を保証する |

For LoopとShift Registerは使用しない。1回の呼出しで1チャネルだけを処理するためである。

### 5.1 完成時のCase階層

```text
error in.status Case
├─ True
│  └─ VISA in / 安全値 / 元error
└─ False
   └─ Enabled? Case
      ├─ False
      │  └─ VISA in / 安全値 / error in
      └─ True
         ├─ Output OFF
         ├─ Set Load
         ├─ Query Amp Min
         ├─ Query Amp Max
         ├─ Query Offset Min
         ├─ Query Offset Max
         ├─ Apply Limit
         └─ Limit error.status Case
            ├─ True  → 設定SubVIなし
            └─ False → Set Func → Set Freq → Set Ampl → Set Offset

外側Case右側
  → Error_To_TestStatus.vi
```

外側CaseとEnabled Caseへ次の7出力トンネルを上から同じ順序で作る。

1. VISA reference
2. Applied Amplitude Vpp
3. Applied Offset V
4. Positive Peak V
5. Negative Peak V
6. Limited?
7. Final Error

---

## 6. フロントパネル入出力と接続元・接続先

### 6.1 新規VIを作成する

1. `ファイル → 新規VI`を選択する。
2. `10_FG420\FG420_Configure_Channel_Safe.vi`として保存する。
3. フロントパネルを開く。

### 6.2 制御器と表示器

1. VISA resource name制御器を左上へ配置し、ラベルを`VISA reference in`にする。
2. `FG420_Channel_Config.ctl`を左中央へ配置し、ラベルを`Channel Config`にする。
3. error cluster制御器を左下へ配置し、ラベルを`error in`にする。
4. 右側へ`VISA reference out`表示器を配置する。
5. DBL表示器を4個配置し、Applied Amp、Applied Offset、Positive Peak、Negative Peakとする。
6. Boolean表示器を配置し、`Limited?`とする。
7. `Status.ctl`、`TestError.ctl`、error cluster表示器を配置する。

### 6.3 コネクタペイン

12端子以上のパターンを使用する。

```text
左上   VISA reference in          右上   VISA reference out
左中   Channel Config              右2    Applied Amplitude Vpp
左下   error in                    右3    Applied Offset V
                                      右4    Positive Peak V
                                      右5    Negative Peak V
                                      右6    Limited?
                                      右7    Status
                                      右8    TestError
                                      右下   error out
```

`VISA reference in`と`Channel Config`を必須、`error in`を推奨に設定する。

---

## 7. 配置する関数およびSubVI

| 数 | 日本語名 | 英語名 | 配置場所 |
|---:|---|---|---|
| 2 | 名前でアンバンドル | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 3 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 1 | `FG420_Output.vi` | SubVI | `10_FG420` |
| 1 | `FG420_Set_Load.vi` | SubVI | `10_FG420` |
| 2 | `FG420_Query_Ampl_Bound.vi` | SubVI | `10_FG420` |
| 2 | `FG420_Query_Offset_Bound.vi` | SubVI | `10_FG420` |
| 1 | `FG420_Apply_Output_Limit.vi` | SubVI | `10_FG420` |
| 1 | `FG420_Set_Func.vi` | SubVI | `10_FG420` |
| 1 | `FG420_Set_Freq.vi` | SubVI | `10_FG420` |
| 1 | `FG420_Set_Ampl.vi` | SubVI | `10_FG420` |
| 1 | `FG420_Set_Offset.vi` | SubVI | `10_FG420` |
| 1 | `Error_To_TestStatus.vi` | SubVI | `00_Common` |

### 7.1 配置順

1. 外側error Caseを配置する。
2. 外側Falseケース内へEnabled Caseを配置する。
3. Enabled=Trueケース内へ、左からOutput OFF、Set Load、Amp Min、Amp Max、Offset Min、Offset Max、Limit VIを配置する。
4. Limit VI右側へLimit Error Caseを配置する。
5. Limit Error=Falseケース内へSet Func、Set Freq、Set Ampl、Set Offsetを左から配置する。
6. 外側Caseの右へError_To_TestStatus.viを配置する。
7. VISA wireを上段、error wireを下段へ通す。

---

## 8. 配線順

### 8.1 Cluster展開と外側error Case

1. `Channel Config`を1個目のUnbundle By Nameの`cluster`へ接続する。
2. `Enabled?`、`Channel`、`Function`、`Frequency Hz`、`Load Infinity?`、`Load Ohm`、`Requested Amplitude Vpp`、`Requested Offset V`、`Output Limit Abs V`、`Limit Mode`、`Output On?`を表示する。
3. `Output On?`ワイヤへコメント`PoCで使用。本VIでは未使用`を置き、SubVIへ接続しない。
4. `error in`を2個目のUnbundle By Nameへ接続し、`status`を表示する。
5. `status`を外側Case selectorへ接続する。
6. Trueケースでは`VISA reference in`をVISA出力トンネルへ接続する。
7. TrueケースではDBL定数`0.0`を4個のDBLトンネルへ接続する。
8. TrueケースではBoolean定数`False`をLimitedトンネルへ接続する。
9. Trueケースでは`error in`をFinal Errorトンネルへ接続する。
10. Falseケースでは`Enabled?`をEnabled Case selectorへ接続する。

### 8.2 Enabled=False Case

11. Falseケースでは`VISA reference in`をVISA出力トンネルへ接続する。
12. DBL定数`0.0`をApplied Amp、Applied Offset、Positive Peak、Negative Peakへ接続する。
13. Boolean定数`False`をLimitedへ接続する。
14. `error in`をFinal Errorへ接続する。
15. Falseケースには機器操作SubVIを配置しない。

### 8.3 Enabled=True：Output OFF

16. `VISA reference in`を`FG420_Output.vi / VISA reference in`へ接続する。
17. `Channel`を`FG420_Output.vi / Channel`へ接続する。
18. Boolean定数`False`を`FG420_Output.vi / Output On?`へ接続する。
19. `error in`を`FG420_Output.vi / error in`へ接続する。
20. VISA出力を`VISA After Output OFF`、error outを`Error After Output OFF`とする。
21. WrapperのStatus / TestErrorは接続しない。

### 8.4 Load設定

22. `VISA After Output OFF`を`FG420_Set_Load.vi / VISA reference in`へ接続する。
23. `Channel`を`FG420_Set_Load.vi / Channel`へ接続する。
24. `Load Infinity?`を同名入力端子へ接続する。
25. `Load Ohm`を同名入力端子へ接続する。
26. `Error After Output OFF`を`FG420_Set_Load.vi / error in`へ接続する。
27. VISA出力を`VISA After Load`、error outを`Error After Load`とする。

### 8.5 Amplitude Minimum / Maximum

28. `VISA After Load`を1個目の`FG420_Query_Ampl_Bound.vi / VISA reference in`へ接続する。
29. `Channel`を`Channel`へ接続する。
30. Bound Enum定数`Minimum`を`Bound`へ接続する。
31. `Error After Load`を`error in`へ接続する。
32. `Bound Value Vpp`を`Device Amplitude Min Vpp`とする。
33. 1個目のVISA出力を2個目のQuery AmplのVISA入力へ接続する。
34. `Channel`を2個目の`Channel`へ接続する。
35. Bound Enum定数`Maximum`を2個目の`Bound`へ接続する。
36. 1個目のerror outを2個目のerror inへ接続する。
37. 2個目の`Bound Value Vpp`を`Device Amplitude Max Vpp`とする。
38. 2個目のVISA出力を`VISA After Amplitude Bounds`、error outを`Error After Amplitude Bounds`とする。

### 8.6 Offset Minimum / Maximum

39. `VISA After Amplitude Bounds`を1個目の`FG420_Query_Offset_Bound.vi / VISA reference in`へ接続する。
40. `Channel`を`Channel`へ接続する。
41. Bound Enum定数`Minimum`を`Bound`へ接続する。
42. `Error After Amplitude Bounds`を`error in`へ接続する。
43. `Bound Value V`を`Device Offset Min V`とする。
44. 1個目のVISA出力を2個目のQuery OffsetのVISA入力へ接続する。
45. `Channel`を2個目の`Channel`へ接続する。
46. Bound Enum定数`Maximum`を2個目の`Bound`へ接続する。
47. 1個目のerror outを2個目のerror inへ接続する。
48. 2個目の`Bound Value V`を`Device Offset Max V`とする。
49. 2個目のVISA出力を`VISA After Offset Bounds`、error outを`Error After Offset Bounds`とする。

### 8.7 Limit VI

50. `Requested Amplitude Vpp`をLimit VIの同名入力へ接続する。
51. `Requested Offset V`をLimit VIの同名入力へ接続する。
52. Device Amp Min / MaxをLimit VIの同名入力へ接続する。
53. Device Offset Min / MaxをLimit VIの同名入力へ接続する。
54. `Output Limit Abs V`をLimit VIの同名入力へ接続する。
55. `Limit Mode`をLimit VIの同名入力へ接続する。
56. `Error After Offset Bounds`をLimit VIの`error in`へ接続する。
57. Limit VIのApplied Amp、Applied Offset、Positive Peak、Negative Peak、Limitedを各データトンネルへ分岐する。
58. Limit VIの`error out`をUnbundle By Nameへ接続し、`status`を取り出す。
59. `status`をLimit Error Case selectorへ接続する。

### 8.8 Limit Error=True

60. `VISA After Offset Bounds`をVISA出力トンネルへ接続する。
61. Limit VIの5データ出力を対応する出力トンネルへ接続する。
62. Limit VIの`error out`をFinal Errorトンネルへ接続する。
63. Set Func、Set Freq、Set Ampl、Set OffsetをTrueケースへ配置しない。

### 8.9 Limit Error=False：設定チェーン

64. `VISA After Offset Bounds`を`FG420_Set_Func.vi / VISA reference in`へ接続する。
65. `Channel`をSet Funcの`Channel`へ接続する。
66. `Function`をSet Funcの`Function`へ接続する。
67. Limit VIのerror outをSet Funcの`error in`へ接続する。
68. Set FuncのVISA outをSet FreqのVISA inへ接続する。
69. `Channel`をSet Freqの`Channel`へ接続する。
70. `Frequency Hz`をSet Freqの同名入力へ接続する。
71. Set Funcのerror outをSet Freqのerror inへ接続する。
72. Set FreqのVISA outをSet AmplのVISA inへ接続する。
73. `Channel`をSet Amplの`Channel`へ接続する。
74. Limit VIの`Applied Amplitude Vpp`をSet Amplの`Amplitude Vpp`へ接続する。
75. Set Freqのerror outをSet Amplのerror inへ接続する。
76. Set AmplのVISA outをSet OffsetのVISA inへ接続する。
77. `Channel`をSet Offsetの`Channel`へ接続する。
78. Limit VIの`Applied Offset V`をSet Offsetの`Offset V`へ接続する。
79. Set Amplのerror outをSet Offsetのerror inへ接続する。
80. Set OffsetのVISA outをVISA出力トンネルへ接続する。
81. Set Offsetのerror outをFinal Errorトンネルへ接続する。
82. Limit VIの5データ出力を対応するデータトンネルへ接続する。

### 8.10 Status / TestError / error out

83. 外側CaseのFinal Error出力を`Error_To_TestStatus.vi / error in`へ接続する。
84. String定数`FG420`を`Device Name`へ接続する。
85. `Status`出力をフロントパネル`Status`へ接続する。
86. `TestError`出力をフロントパネル`TestError`へ接続する。
87. `error out`をフロントパネル`error out`へ接続する。
88. 外側CaseのVISAと5データ出力を各フロントパネル表示器へ接続する。

### 8.11 全Case出力

| 経路 | VISA out | Applied / Peak | Limited? | Final Error |
|---|---|---|---|---|
| error in=True | VISA in | 全DBL=0 | False | 元error |
| Enabled=False | VISA in | 全DBL=0 | False | error in |
| Output OFF～Query途中error | 最後のWrapper VISA | Limit未実行時は0 | False | 最初のWrapper error |
| Limit Reject / Limit入力異常 | Offset Query後VISA | Limit VI出力 | Limit VI出力 | Limit error |
| Function～Offset途中error | 最終WrapperのバイパスVISA | Limit VI出力 | Limit VI出力 | 最初の設定error |
| 正常 | Set Offset VISA out | Limit VI出力 | Limit VI出力 | no error |

---

## 9. 単体テスト

| No. | 条件 | 期待結果 |
|---:|---|---|
| 1 | Ch1 Enabled=True、Sin、1 kHz、1 Vpp、0 V、Limit=5 | 全SubVI正常、Applied=1/0 |
| 2 | Ch2 Enabled=True、Ch1と異なる周波数 | Ch2が全WrapperのChannelへ入る |
| 3 | Enabled=False | ドライバ未実行、VISA素通り、全DBL=0 |
| 4 | Amp=10 Vpp、Offset=0、Limit=5 | 境界通過、Limited=False |
| 5 | Reject超過 | Function以降未実行、-710112 |
| 6 | Clamp超過 | 縮小Applied AmpがSet Amplへ入る |
| 7 | Set Loadでerror注入 | Queryと設定Wrapperは実ドライバ未実行、元error保持 |
| 8 | Offset Maximum Queryでerror注入 | Limitはerror in=True、安全出力、設定未実行 |
| 9 | Set Freqでerror注入 | Set Ampl / Set Offset未実行、Freq error保持 |
| 10 | error in.status=True | 全SubVI未実行、VISA素通り、元error |

---

## 完了確認

- [ ] `Output On?`を本VIの機器操作へ接続していない。
- [ ] Enabled=Falseケースで7出力を全て配線した。
- [ ] VISAとerrorを全Wrapper間で省略せず直列接続した。
- [ ] Load設定をMin/Max Queryより前に配置した。
- [ ] Limit Error=Trueケースに設定Wrapperを配置していない。
- [ ] Status / TestErrorを最終errorから1回だけ生成した。
