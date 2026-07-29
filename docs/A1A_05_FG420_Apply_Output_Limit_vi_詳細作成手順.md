# A1A.5 `FG420_Apply_Output_Limit.vi` 詳細作成手順

**正本範囲**：`FG420_Apply_Output_Limit.vi` のフロントパネル、コネクタペイン、LabVIEW構造、全Case出力、端子単位配線、単体テスト。

参照：

- [A1A_FG420複数台2ch出力リミットPoC.md](./A1A_FG420複数台2ch出力リミットPoC.md)
- [00A_LabVIEW実装資料の記述ルール.md](./00A_LabVIEW実装資料の記述ルール.md)
- [00B_LabVIEW学習型VI設計ルール.md](./00B_LabVIEW学習型VI設計ルール.md)
- [00C_一次資料とバージョン基準.md](./00C_一次資料とバージョン基準.md)

既存VI名、typedef、入出力、エラーコード、Reject / Clamp方針は変更しない。

---

## 0. 実現したい機能とVIの責務

要求振幅と要求オフセットから、FG420が出力しようとする正側ピーク電圧と負側ピーク電圧を別々に計算する。

```text
Positive Peak = Offset + Amplitude Vpp / 2
Negative Peak = Offset - Amplitude Vpp / 2
```

正側ピークが`+Output Limit Abs V`以下、かつ負側ピークが`-Output Limit Abs V`以上なら要求値を通過させる。

超過時は`Limit Mode`で処理を分ける。

- `Reject`：設定を拒否し、後段へ安全値とローカルエラーを返す。
- `Clamp`：要求オフセットを維持し、振幅だけを安全範囲まで縮小する。

本VIは純粋処理VIである。VISA、FG420ドライバ、出力ON/OFF、Close、Waitを呼ばない。

---

## 1. 入力データの実体

入力は全て単一値である。配列、ループ、VISA参照は使用しない。

| 端子名 | 型 | 実体 |
|---|---|---|
| `Requested Amplitude Vpp` | DBL | FG420へ設定したいピーク・ツー・ピーク振幅 |
| `Requested Offset V` | DBL | 波形中心を0 Vから移動するDCオフセット |
| `Device Amplitude Min Vpp` | DBL | 現在の負荷・チャネル条件における機器最小振幅 |
| `Device Amplitude Max Vpp` | DBL | 現在の負荷・チャネル条件における機器最大振幅 |
| `Device Offset Min V` | DBL | 現在の負荷・チャネル条件における機器最小オフセット |
| `Device Offset Max V` | DBL | 現在の負荷・チャネル条件における機器最大オフセット |
| `Output Limit Abs V` | DBL | 正負共通の絶対電圧リミット。正側は`+Limit`、負側は`-Limit` |
| `Limit Mode` | `FG420_Limit_Mode.ctl` | `Reject`または`Clamp` |
| `error in` | error cluster | 前段エラー。status=True時は本処理を開始しない |

---

## 2. 出力データモデル

| 端子名 | 型 | 生成元 |
|---|---|---|
| `Applied Amplitude Vpp` | DBL | 正常時は要求振幅、Clamp時は縮小振幅、Reject・入力異常時は0.0 |
| `Applied Offset V` | DBL | 正常時とClamp時は要求オフセット、Reject・入力異常時は0.0 |
| `Positive Peak V` | DBL | リミット適用前の要求正側ピーク |
| `Negative Peak V` | DBL | リミット適用前の要求負側ピーク |
| `Limited?` | Boolean | RejectまたはClamp対象になった場合True |
| `error out` | error cluster | 元errorまたは本VIのローカルエラー |

`Positive Peak V`と`Negative Peak V`は要求値の診断用であり、Clamp後のピークではない。Clamp後ピークは内部で再計算し、安全確認だけに使用する。

---

## 3. 前提条件・異常条件

| 条件 | 不成立時 | Code |
|---|---|---:|
| `error in.status=False` | 全計算をスキップし、元errorと安全出力を返す | 元error |
| `Output Limit Abs V > 0` | Limit不正 | -710110 |
| `Device Amplitude Min Vpp <= Device Amplitude Max Vpp` | 機器範囲不正 | -710113 |
| `Device Offset Min V <= Device Offset Max V` | 機器範囲不正 | -710113 |
| `Requested Amplitude Vpp >= 0` | 要求値不正 | -710114 |
| 要求振幅がDevice Min/Max内 | 要求値不正 | -710114 |
| 要求オフセットがDevice Min/Max内 | 要求値不正 | -710114 |
| Clamp時に`abs(Requested Offset V) <= Output Limit Abs V` | オフセット単独超過 | -710111 |
| Reject時に正負ピークがLimit内 | リミット超過 | -710112 |

ローカルエラーsource全文は次を使用する。

```text
-710110:
FG420_Apply_Output_Limit.vi: Output Limit Abs V must be greater than zero. LimitAbsV=%f

-710111:
FG420_Apply_Output_Limit.vi: Offset alone exceeds the configured absolute voltage limit. OffsetV=%f, LimitAbsV=%f

-710112:
FG420_Apply_Output_Limit.vi: Requested output exceeds the configured absolute voltage limit. AmplitudeVpp=%f, OffsetV=%f, PositivePeakV=%f, NegativePeakV=%f, LimitAbsV=%f

-710113:
FG420_Apply_Output_Limit.vi: Device bounds are invalid. AmpMinVpp=%f, AmpMaxVpp=%f, OffsetMinV=%f, OffsetMaxV=%f

-710114:
FG420_Apply_Output_Limit.vi: Requested value is outside the FG420 device bounds. AmplitudeVpp=%f, AmpMinVpp=%f, AmpMaxVpp=%f, OffsetV=%f, OffsetMinV=%f, OffsetMaxV=%f
```

---

## 4. 処理アルゴリズム

```text
if error in.status=True:
    Applied Amplitude = 0
    Applied Offset = 0
    Positive Peak = 0
    Negative Peak = 0
    Limited = False
    error out = error in
else:
    if Output Limit Abs V <= 0:
        -710110
    elif Device Min/Maxが逆転:
        -710113
    elif Requested値がDevice範囲外:
        -710114
    else:
        Half Amplitude = Requested Amplitude / 2
        Positive Peak = Requested Offset + Half Amplitude
        Negative Peak = Requested Offset - Half Amplitude

        Positive Exceeded = Positive Peak > Output Limit Abs V
        Negative Exceeded = Negative Peak < -Output Limit Abs V
        Limit Exceeded = Positive Exceeded OR Negative Exceeded

        case Limit Mode of
            Reject:
                if Limit Exceeded:
                    Applied値 = 0
                    Limited = True
                    -710112
                else:
                    Applied値 = Requested値
                    Limited = False
                    no error

            Clamp:
                if Limit Exceeded=False:
                    Applied値 = Requested値
                    Limited = False
                    no error
                elif abs(Requested Offset) > Output Limit:
                    Applied値 = 0
                    Limited = True
                    -710111
                else:
                    Allowed Amplitude = 2 × (Output Limit - abs(Requested Offset))
                    Applied Amplitude = min(Requested Amplitude, Allowed Amplitude, Device Amplitude Max)
                    Applied Offset = Requested Offset
                    Clamp後の正負ピークを再計算
                    Clamp後ピークがLimit内ならLimited=True、no error
                    Limit外ならApplied値=0、-710113
```

---

## 5. LabVIEW構造の選定理由

| 必要な処理 | 採用構造 | 理由 |
|---|---|---|
| 前段errorを最優先する | 外側Case Structure | 入力検証errorで元errorを上書きしない |
| Limit正値、Device範囲、要求値を順に保証する | 多段Case Structure | エラーコードと停止位置を1対1にする |
| Reject / Clampを分離する | Enum Case Structure | モードごとの全出力を明示する |
| 超過あり / なしを分離する | Boolean Case Structure | 正常通過と制限処理を混在させない |
| ローカルerrorを作る | Format Into String + Bundle By Name | status、code、sourceを端子単位で生成する |

For Loop、While Loop、Shift Registerは使用しない。入力が単一条件であり、反復状態を保持しないためである。

### 5.1 完成時のCase階層

```text
error in.status Case
├─ True
│  └─ 安全出力 + 元error
└─ False
   └─ Limit Positive? Case
      ├─ False → -710110
      └─ True
         └─ Device Bounds Valid? Case
            ├─ False → -710113
            └─ True
               └─ Requested Values Valid? Case
                  ├─ False → -710114
                  └─ True
                     └─ Limit Mode Case
                        ├─ Reject
                        │  └─ Limit Exceeded? Case
                        └─ Clamp
                           └─ Limit Exceeded? Case
                              └─ True
                                 └─ Offset Alone Exceeded? Case
                                    └─ False
                                       └─ Clamp Result Safe? Case
```

各Case右側へ次の6トンネルを上から同じ順序で作る。

1. `Applied Amplitude Vpp` DBL
2. `Applied Offset V` DBL
3. `Positive Peak V` DBL
4. `Negative Peak V` DBL
5. `Limited?` Boolean
6. `Final Error` error cluster

`Use default if unwired`を有効にしない。

---

## 6. フロントパネル入出力と接続元・接続先

### 6.1 新規VIを作成する

1. LabVIEWを起動する。
2. `ファイル → 新規VI`を選択する。
3. `ファイル → 名前を付けて保存`を選択する。
4. `10_FG420\FG420_Apply_Output_Limit.vi`として保存する。
5. フロントパネルを開く。

### 6.2 制御器と表示器を配置する

左側へ9入力、右側へ6出力を配置する。

```text
左上   Requested Amplitude Vpp        右上   Applied Amplitude Vpp
左2    Requested Offset V             右2    Applied Offset V
左3    Device Amplitude Min Vpp       右3    Positive Peak V
左4    Device Amplitude Max Vpp       右4    Negative Peak V
左5    Device Offset Min V            右5    Limited?
左6    Device Offset Max V            右下   error out
左7    Output Limit Abs V
左8    Limit Mode
左下   error in
```

- 数値制御器・表示器は全てDBLにする。
- `Limit Mode`は`FG420_Limit_Mode.ctl`を配置する。空のEnumを新規作成しない。
- `error in`と`error out`は標準error clusterを使用する。

### 6.3 コネクタペイン

1. VIアイコンを右クリックし、`コネクタを表示`を選択する。
2. 16端子以上のパターンを選択する。
3. 左側へ全入力、右側へ全出力を割り当てる。
4. `Requested Amplitude Vpp`、`Requested Offset V`、`Output Limit Abs V`、`Limit Mode`を必須端子にする。
5. Device Min/Maxと`error in`を推奨端子にする。
6. 6出力を全てコネクタペインへ割り当てる。

---

## 7. 配置する関数およびSubVI

| 数 | 日本語名 | 英語名 | 配置場所 |
|---:|---|---|---|
| 1 | 名前でアンバンドル | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 8以上 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 2 | 範囲内と強制 | In Range and Coerce | プログラミング → 比較 |
| 1 | 絶対値 | Absolute Value | プログラミング → 数値 |
| 2 | 除算 | Divide | プログラミング → 数値 |
| 2 | 加算 | Add | プログラミング → 数値 |
| 3 | 減算 | Subtract | プログラミング → 数値 |
| 1 | 乗算 | Multiply | プログラミング → 数値 |
| 1 | 符号反転 | Negate | プログラミング → 数値 |
| 2 | 最小＆最大 | Min & Max | プログラミング → 比較 |
| 必要数 | 大きい?、小さい?、以上?、以下? | Greater? / Less? / Greater Or Equal? / Less Or Equal? | プログラミング → 比較 |
| 2 | 複合演算 | Compound Arithmetic | プログラミング → Boolean |
| 5 | 文字列にフォーマット | Format Into String | プログラミング → 文字列 |
| 5 | 名前でバンドル | Bundle By Name | プログラミング → クラスタ、クラス、バリアント |

### 7.1 配置順

1. `error in`右側へUnbundle By Nameを配置する。
2. その右へ外側Case Structureを配置する。
3. 外側Falseケース内へLimit正値Caseを配置する。
4. Limit正値Trueケース内へDevice Bounds Caseを配置する。
5. Device Bounds Trueケース内へRequested Values Caseを配置する。
6. Requested Values Trueケース内へLimit Mode Caseを配置する。
7. Rejectケース内へLimit Exceeded Caseを配置する。
8. Clampケース内へLimit Exceeded Caseを配置する。
9. Clamp超過Trueケース内へOffset Alone Exceeded Caseを配置する。
10. Offset Alone Exceeded Falseケース内へClamp Result Safe Caseを配置する。
11. 数値検証関数を上段、ピーク計算を中央、エラー生成を下段へ配置する。

---

## 8. 配線順

### 8.1 外側error Case

1. `error in`をUnbundle By Nameの`cluster`端子へ接続する。
2. Unbundle By Nameの要素を`status`へ変更する。
3. `status`出力を外側Case Structureのselector端子`?`へ接続する。
4. TrueケースではDBL定数`0.0`を4個のDBL出力トンネルへ接続する。
5. TrueケースではBoolean定数`False`を`Limited?`トンネルへ接続する。
6. Trueケースでは`error in`を`Final Error`トンネルへ接続する。
7. Falseケースへ全入力ワイヤをトンネルで入れる。

### 8.2 Limit正値検証

8. `Output Limit Abs V`を大きい?（Greater?）の`x`入力へ接続する。
9. DBL定数`0.0`を同関数の`y`入力へ接続する。
10. Greater?出力を`Limit Positive?` Caseのselectorへ接続する。
11. Falseケースでは`Output Limit Abs V`をFormat Into Stringの第1引数へ接続する。
12. 書式文字列定数へ-710110のsource全文を設定する。
13. `error in`をBundle By Nameの基準clusterへ接続する。
14. Boolean定数`True`を`status`へ接続する。
15. I32定数`-710110`を`code`へ接続する。
16. Format Into String出力を`source`へ接続する。
17. Bundle By Name出力を`Final Error`トンネルへ接続する。
18. Falseケースの他の出力はDBL`0.0`×4、Boolean`False`とする。

### 8.3 Device Min/Max検証

19. `Device Amplitude Min Vpp`を以下?（Less Or Equal?）の`x`へ接続する。
20. `Device Amplitude Max Vpp`を同関数の`y`へ接続する。
21. 出力を`Amplitude Bounds Valid?`とする。
22. `Device Offset Min V`を2個目のLess Or Equal?の`x`へ接続する。
23. `Device Offset Max V`を同関数の`y`へ接続する。
24. 出力を`Offset Bounds Valid?`とする。
25. 2個のBooleanをAND設定のCompound Arithmeticへ接続する。
26. AND出力を`Device Bounds Valid?` Caseのselectorへ接続する。
27. FalseケースではFormat Into Stringへ、Amp Min、Amp Max、Offset Min、Offset Maxの順で接続する。
28. `error in`を基準clusterとしてstatus=True、code=I32`-710113`、source=生成文字列をBundle By Nameへ接続する。
29. Falseケースのデータ出力はDBL`0.0`×4、Limited=Falseとする。

### 8.4 Requested値のDevice範囲検証

30. `Requested Amplitude Vpp`を以上?（Greater Or Equal?）の`x`へ接続する。
31. DBL定数`0.0`を同関数の`y`へ接続する。
32. 出力を`Amplitude Nonnegative?`とする。
33. `Requested Amplitude Vpp`を1個目のIn Range and Coerceの`x`へ接続する。
34. Device Amp Minを`lower limit`、Device Amp Maxを`upper limit`へ接続する。
35. `include lower limit?`と`include upper limit?`へBoolean定数`True`を接続する。
36. `In Range?`出力を`Amplitude In Device Range?`とする。
37. `Requested Offset V`を2個目のIn Range and Coerceの`x`へ接続する。
38. Device Offset Minを`lower limit`、Device Offset Maxを`upper limit`へ接続する。
39. 両包含端子へBoolean定数`True`を接続する。
40. `In Range?`出力を`Offset In Device Range?`とする。
41. 3個のBooleanをAND設定のCompound Arithmeticへ接続する。
42. AND出力を`Requested Values Valid?` Caseのselectorへ接続する。
43. FalseケースではFormat Into Stringへ、Requested Amp、Amp Min、Amp Max、Requested Offset、Offset Min、Offset Maxの順で接続する。
44. `error in`を基準clusterとしてstatus=True、code=I32`-710114`、source=生成文字列をBundle By Nameへ接続する。
45. Falseケースのデータ出力はDBL`0.0`×4、Limited=Falseとする。

### 8.5 正側ピーク・負側ピーク・超過判定

46. `Requested Amplitude Vpp`を除算（Divide）の`x`へ接続する。
47. DBL定数`2.0`を同関数の`y`へ接続する。
48. Divide出力を`Requested Half Amplitude V`とする。
49. `Requested Offset V`を加算（Add）の`x`へ接続する。
50. `Requested Half Amplitude V`をAddの`y`へ接続する。
51. Add出力を`Requested Positive Peak V`とする。
52. `Requested Offset V`を減算（Subtract）の`x`へ接続する。
53. `Requested Half Amplitude V`をSubtractの`y`へ接続する。
54. Subtract出力を`Requested Negative Peak V`とする。
55. Positive Peakを大きい?（Greater?）の`x`へ接続する。
56. `Output Limit Abs V`を同関数の`y`へ接続する。
57. 出力を`Positive Exceeded?`とする。
58. `Output Limit Abs V`を符号反転（Negate）へ接続する。
59. Negate出力を`Negative Limit V`とする。
60. Negative Peakを小さい?（Less?）の`x`へ接続する。
61. Negative Limitを同関数の`y`へ接続する。
62. 出力を`Negative Exceeded?`とする。
63. Positive ExceededとNegative ExceededをOR設定のCompound Arithmeticへ接続する。
64. OR出力を`Limit Exceeded?`とする。
65. Requested Positive Peakを全後続Caseの`Positive Peak V`トンネルへ接続する。
66. Requested Negative Peakを全後続Caseの`Negative Peak V`トンネルへ接続する。
67. `Limit Mode`をEnum Case Structureのselectorへ接続する。

### 8.6 Rejectケース

68. `Limit Exceeded?`をReject内Caseのselectorへ接続する。
69. FalseケースではRequested AmpをApplied Amp、Requested OffsetをApplied Offsetへ接続する。
70. FalseケースではLimited=False、Final Error=`error in`とする。
71. TrueケースではApplied Amp=DBL`0.0`、Applied Offset=DBL`0.0`、Limited=Trueとする。
72. TrueケースのFormat Into Stringへ、Requested Amp、Requested Offset、Positive Peak、Negative Peak、Output Limitの順で接続する。
73. `error in`を基準clusterとしてstatus=True、code=I32`-710112`、source=生成文字列をBundle By Nameへ接続する。
74. Bundle By Name出力をTrueケースのFinal Errorへ接続する。

### 8.7 Clampケース

75. `Limit Exceeded?`をClamp内Caseのselectorへ接続する。
76. Falseケースでは要求値をApplied値へ接続し、Limited=False、Final Error=`error in`とする。
77. Trueケースでは`Requested Offset V`を絶対値（Absolute Value）の`x`へ接続する。
78. Absolute Value出力を`Absolute Offset V`とする。
79. Absolute Offsetを大きい?（Greater?）の`x`へ接続する。
80. Output Limitを同関数の`y`へ接続する。
81. 出力を`Offset Alone Exceeded?` Caseのselectorへ接続する。
82. TrueケースではApplied値=DBL`0.0`、Limited=Trueとする。
83. TrueケースのFormat Into StringへRequested Offset、Output Limitの順で接続する。
84. `error in`を基準clusterとしてstatus=True、code=I32`-710111`、source=生成文字列をBundle By Nameへ接続する。
85. Offset Alone Exceeded=FalseケースではOutput LimitをSubtractの`x`へ接続する。
86. Absolute OffsetをSubtractの`y`へ接続する。
87. 出力を`Available Peak Margin V`とする。
88. Available Peak MarginをMultiplyの`x`へ接続する。
89. DBL定数`2.0`をMultiplyの`y`へ接続する。
90. 出力を`Allowed Amplitude Vpp`とする。
91. Requested AmpとAllowed Ampを1個目のMin & Maxへ接続する。
92. `min`出力を`Requested Or Limit Min Vpp`とする。
93. Requested Or Limit MinとDevice Amp Maxを2個目のMin & Maxへ接続する。
94. `min`出力を`Applied Amplitude Candidate Vpp`とする。
95. Applied Amplitude CandidateをApplied Ampトンネルへ接続する。
96. Requested OffsetをApplied Offsetトンネルへ接続する。
97. Limited=True、Final Error=`error in`とする。
98. Applied Amplitude Candidateを2個目のDivideの`x`へ接続する。
99. DBL定数`2.0`を同関数の`y`へ接続する。
100. Divide出力を`Applied Half Amplitude V`とする。
101. Requested OffsetとApplied Halfを2個目のAddへ接続し、`Applied Positive Peak V`を作る。
102. Requested OffsetとApplied Halfを3個目のSubtractへ接続し、`Applied Negative Peak V`を作る。
103. Applied Positive Peakを以下?（Less Or Equal?）の`x`へ接続する。
104. Output Limitを同関数の`y`へ接続する。
105. Applied Negative Peakを以上?（Greater Or Equal?）の`x`へ接続する。
106. Negative Limitを同関数の`y`へ接続する。
107. 2個の比較出力をAND設定のCompound Arithmeticへ接続する。
108. AND出力を`Clamp Result Safe?` Caseのselectorへ接続する。
109. Trueケースでは手順95～97の出力を維持する。
110. FalseケースではApplied値=DBL`0.0`、Limited=True、error=-710113とする。

### 8.8 最終出力

111. 外側CaseのApplied Ampトンネルをフロントパネル`Applied Amplitude Vpp`へ接続する。
112. Applied Offsetトンネルを`Applied Offset V`へ接続する。
113. Positive Peakトンネルを`Positive Peak V`へ接続する。
114. Negative Peakトンネルを`Negative Peak V`へ接続する。
115. Limitedトンネルを`Limited?`へ接続する。
116. Final Errorトンネルを`error out`へ接続する。

### 8.9 全Case出力表

| 経路 | Applied Amp | Applied Offset | Positive Peak | Negative Peak | Limited? | error |
|---|---:|---:|---:|---:|---|---|
| error in=True | 0 | 0 | 0 | 0 | False | 元error |
| Limit<=0 | 0 | 0 | 0 | 0 | False | -710110 |
| Bounds不正 | 0 | 0 | 0 | 0 | False | -710113 |
| Requested範囲外 | 0 | 0 | 0 | 0 | False | -710114 |
| Reject・範囲内 | Requested | Requested | Requested | Requested | False | no error |
| Reject・超過 | 0 | 0 | Requested | Requested | True | -710112 |
| Clamp・範囲内 | Requested | Requested | Requested | Requested | False | no error |
| Clamp・Offset単独超過 | 0 | 0 | Requested | Requested | True | -710111 |
| Clamp・縮小成功 | 計算値 | Requested | Requested | Requested | True | no error |

---

## 9. 単体テスト

| No. | 入力 | 期待結果 |
|---:|---|---|
| 1 | Amp=2、Offset=0、Device Amp=0～20、Device Offset=-10～10、Limit=5、Reject | Applied=2/0、Peak=+1/-1、Limited=False、no error |
| 2 | Amp=10、Offset=0、Limit=5、Reject | 境界通過、Peak=+5/-5、Limited=False |
| 3 | Amp=10.0002、Offset=0、Limit=5、Reject | Applied=0/0、Limited=True、-710112 |
| 4 | Amp=8、Offset=2、Limit=5、Clamp | Allowed=6、Applied Amp=6、Applied Offset=2、Limited=True |
| 5 | Amp=0、Offset=5、Limit=5、Clamp | 境界通過、Applied=0/5、Limited=False |
| 6 | Amp=0、Offset=5.0001、Limit=5、Clamp | -710111、安全出力 |
| 7 | Amp=-1 | -710114、安全出力 |
| 8 | Device Amp Min=20、Max=10 | -710113、安全出力 |
| 9 | Device Amp Max=10、Requested Amp=12 | -710114、安全出力 |
| 10 | error in.status=True、code=-123 | 全DBL=0、Limited=False、error out.code=-123 |

---

## 完了確認

- [ ] フロントパネル15端子をコネクタペインへ割り当てた。
- [ ] 全Caseで6出力トンネルを配線した。
- [ ] Positive Peak、Negative Peak、Positive Exceeded、Negative Exceededを別々に生成した。
- [ ] RejectとClampを別Caseへ配置した。
- [ ] Clamp時にOffsetを変更していない。
- [ ] Clamp後ピークを再計算した。
- [ ] 全ローカルerrorで基準cluster、status、I32 code、source全文を配線した。
- [ ] error in.status=True時に安全出力と元errorを返した。
