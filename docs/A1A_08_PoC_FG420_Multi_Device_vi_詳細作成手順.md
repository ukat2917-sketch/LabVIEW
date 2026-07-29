# A1A.8 `PoC_FG420_Multi_Device.vi` 詳細作成手順

**正本範囲**：複数台のFG420を配列で受け取り、1反復で1台をPrepare、Ch1設定、Ch2設定、Output ON、Wait、Output OFF、Closeし、全機器Cleanupを保証するPoC VIの作成手順。

参照：

- [A1A_FG420複数台2ch出力リミットPoC.md](./A1A_FG420複数台2ch出力リミットPoC.md)
- [A1A_06_FG420_Configure_Channel_Safe_vi_詳細作成手順.md](./A1A_06_FG420_Configure_Channel_Safe_vi_詳細作成手順.md)
- [A1A_07_FG420_Prepare_Device_vi_詳細作成手順.md](./A1A_07_FG420_Prepare_Device_vi_詳細作成手順.md)
- [00A_LabVIEW実装資料の記述ルール.md](./00A_LabVIEW実装資料の記述ルール.md)
- [00B_LabVIEW学習型VI設計ルール.md](./00B_LabVIEW学習型VI設計ルール.md)

既存VI名、typedef、処理順、Stop On First Error方針、Cleanup方針は変更しない。

---

## 0. 実現したい機能とVIの責務

`FG420_Device_Config.ctl`一次元配列を受け取り、1反復で1台を処理する。

```text
Prepare Device
  → Ch1 Configure
  → Ch2 Configure
  → Ch1 Output ON
  → Ch2 Output ON
  → Wait
  → Ch1 Output OFF
  → Ch2 Output OFF
  → Close
```

Disabled Deviceは機器操作を行わない。ただし出力配列のindex対応を維持するため、Main For Loopの1反復は実行する。

1台のエラーが別機器のCleanupを妨げないよう、VISA reference、Device State、Applied Ch1 Config、Applied Ch2 Config、Device Errorを機器数と同じ要素数の配列で保持する。

PoC初版ではFor LoopのParallel Iterationsを有効にしない。複数台を個別設定できるが、Output ONエッジの厳密同時性は保証しない。

---

## 1. 入力データの実体

```text
Device Configs[]
├─ index 0：FG420_Device_Config.ctl
│  ├─ Device情報
│  ├─ Ch1 Config
│  └─ Ch2 Config
├─ index 1：2台目
└─ ...
```

| 入力端子 | 型 | 用途 |
|---|---|---|
| `Device Configs` | `FG420_Device_Config.ctl[]` | 機器設定配列 |
| `Output Duration ms` | U32 | 1台のOutput ON後待機時間 |
| `Enable Output Phase?` | Boolean | False時は設定だけ行いOutput ONしない |
| `Stop On First Error?` | Boolean | True時は最初の機器error後、新しい機器の通常処理を開始しない |
| `error in` | error cluster | PoC開始前の既存error |

Main For Loopの`Device Configs`入力トンネルで自動指標付けを有効にする。

- ループ外：`FG420_Device_Config.ctl[]`
- ループ内：単一`FG420_Device_Config.ctl`
- N端子：未配線
- 反復回数：Device Configsの実要素数

---

## 2. 出力データモデル

| 出力端子 | 型 | index対応 |
|---|---|---|
| `Device States` | `FG420_Device_State.ctl[]` | Device Configsと同じindex |
| `Applied Ch1 Configs` | `FG420_Channel_Config.ctl[]` | 同じindexのCh1結果 |
| `Applied Ch2 Configs` | `FG420_Channel_Config.ctl[]` | 同じindexのCh2結果 |
| `Device Errors` | error cluster[] | 同じindexのOriginal + Cleanup結果 |
| `Status` | `Status.ctl` | 全体の最初のerrorから生成 |
| `TestError` | `TestError.ctl` | 全体の最初のerrorから生成 |
| `error out` | error cluster | Original errorをCleanup errorより優先した最初のerror |

内部で`VISA References[]`も保持する。フロントパネルへ公開せず、Cleanup For Loopへ渡す。

`Applied Ch1 Configs`と`Applied Ch2 Configs`は新しいtypedefを追加しない。入力`FG420_Channel_Config.ctl`を基準clusterとし、Enabledなチャネルだけ`Requested Amplitude Vpp`と`Requested Offset V`をApplied値へ置換する。

---

## 3. 前提条件・異常条件

| 条件 | 動作 |
|---|---|
| `error in.status=True` | 機器操作を開始せず元errorを最終出力へ保持 |
| Device Configsが0要素 | -710122 |
| Enabled Deviceが0台 | -710122 |
| Enabled DeviceでCh1/Ch2が両方Disabled | -710121 |
| Enabled DeviceのVISA Resource重複 | -710120 |
| Device Enabled=False | 1反復をバイパスし、初期Stateと入力Configを出力配列へ追加 |
| Prepare途中error、Init失敗 | Configure / ONをスキップ。Initialized=FalseならClose不要 |
| Prepare途中error、Init成功後 | Configure / ONをスキップ。CleanupでOFF / Closeを試行 |
| Ch設定途中error | Output ONをスキップ。CleanupでOFF / Closeを試行 |
| Output ON後error | Original Device Errorを保持し、OFF / Closeを別error wireで試行 |
| Cleanup error | Originalがある場合はOriginalを優先。Originalがない場合はCleanup errorを返す |

ローカルエラーsource全文：

```text
-710120:
PoC_FG420_Multi_Device.vi: Duplicate VISA resource was found. Resource=%s, FirstIndex=%d, DuplicateIndex=%d

-710121:
PoC_FG420_Multi_Device.vi: Enabled device has no enabled channel. DeviceIndex=%d, LogicalName=%s

-710122:
PoC_FG420_Multi_Device.vi: No enabled FG420 device was provided.
```

---

## 4. 処理アルゴリズム

```text
Original Error = error in

Precheck Loop:
    Device Configsを1台ずつ読む
    Disabled Deviceは検証対象から除外
    Enabled Device数を数える
    Ch1 Enabled OR Ch2 Enabledを判定
    Enabled DeviceのVISA Resource重複を判定
    最初のValidation Errorを保持

Main Loop（1反復=1台）:
    if Disabled Device:
        初期State、入力Ch Config、No Errorを配列へ追加
    elif Precheck Errorあり:
        機器操作せずValidation Errorを結果へ追加
    elif Stop On First Error=True and 前Device errorあり:
        機器操作せずFirst Errorを結果へ追加
    else:
        Prepare Device
        Ch1 Configure
        Ch2 Configure
        Ch1 Output ON条件を判定
        Ch2 Output ON条件を判定
        1ch以上ONならWait
        Original Device Errorを保存
        Ch1 OFFをCleanup wireで試行
        Ch2 OFFをCleanup wireで試行
        CloseをCleanup wireで試行
        Original ErrorとCleanup ErrorをMerge
        5個のCurrent結果を配列へ追加

Cleanup Loop（1反復=1台）:
    Initialized=True and Closed=FalseのDeviceだけ再Cleanup
    Ch1 OFF
    Ch2 OFF
    Close
    Original ErrorとCleanup ErrorをMerge
    State[]とDevice Errors[]を生成

全Device Errorの最初のerrorからStatus / TestErrorを生成
```

---

## 5. LabVIEW構造の選定理由

| 構造 | 理由 |
|---|---|
| Precheck For Loop | ハードウェア操作前に全Configを検証する |
| Main For Loop | 1反復で1台を有限回処理する |
| Device Config入力自動指標付け | 配列から単一Device clusterを取り出す |
| 配列Shift Register | VISA、State、Applied、errorをindex順に蓄積する |
| First Error Shift Register | Device errorを別機器のerror wireへ直接流さず、全体の最初のerrorを保持する |
| Abort Shift Register | Stop On First Error状態を次反復へ保持する |
| Flat Sequence Structure | Output ON、Wait、通常OFF / Closeの順序を固定する |
| Cleanup For Loop | Main Loop結果を全index再走査し、未完了資源を解放する |
| Clear Errors + Merge Errors | Cleanupを続行し、Original Errorを優先する |

### 5.1 ブロックダイアグラムの配置

```text
上段：Precheck For Loop
  Device Configs[]
    → Enabled Count
    → Channel有効確認
    → VISA重複確認
    → Precheck Error

中段：Main For Loop
  Device Configs[] 自動指標付け
    → Bypass Device? Case
    → Prepare
    → Ch1 Configure
    → Ch2 Configure
    → Flat Sequence Frame 0：Ch1 ON → Ch2 ON
    → Flat Sequence Frame 1：Wait
    → Flat Sequence Frame 2：Ch1 OFF → Ch2 OFF → Close
    → 配列Shift Register更新

下段：Cleanup For Loop
  VISA[] / State[] / Error[] / Device Configs[] 自動指標付け
    → Needs Cleanup? Case
    → Ch1 OFF → Ch2 OFF → Close
    → State[] / Device Error[]

右端：Error_To_TestStatus.vi
```

---

## 6. フロントパネル入出力と接続元・接続先

### 6.1 新規VIを作成する

1. `ファイル → 新規VI`を選択する。
2. `10_FG420\PoC_FG420_Multi_Device.vi`として保存する。
3. フロントパネルを開く。

### 6.2 入力制御器

1. 空の配列制御器を配置する。
2. 配列枠内へ`FG420_Device_Config.ctl`を配置する。
3. 配列ラベルを`Device Configs`にする。
4. U32数値制御器を配置し、`Output Duration ms`、既定値U32`1000`にする。
5. Boolean制御器`Enable Output Phase?`を配置し、既定値Falseにする。
6. Boolean制御器`Stop On First Error?`を配置し、既定値Trueにする。
7. error cluster制御器`error in`を配置する。

### 6.3 出力表示器

1. 空の配列表示器へ`FG420_Device_State.ctl`を入れ、`Device States`とする。
2. 空の配列表示器へ`FG420_Channel_Config.ctl`を入れ、`Applied Ch1 Configs`とする。
3. 同じ型の配列表示器をもう1個作り、`Applied Ch2 Configs`とする。
4. 空の配列表示器へerror cluster表示器を入れ、`Device Errors`とする。
5. `Status.ctl`、`TestError.ctl`、error cluster表示器を配置する。

### 6.4 コネクタペイン

12端子以上のパターンを使用する。

```text
左上   Device Configs             右上   Device States
左2    Output Duration ms          右2    Applied Ch1 Configs
左3    Enable Output Phase?        右3    Applied Ch2 Configs
左4    Stop On First Error?        右4    Device Errors
左下   error in                    右5    Status
                                      右6    TestError
                                      右下   error out
```

`Device Configs`を必須、他の入力を推奨に設定する。

---

## 7. 配置する関数およびSubVI

| 数 | 日本語名 | 英語名 | 配置場所 |
|---:|---|---|---|
| 3 | Forループ | For Loop | プログラミング → ストラクチャ |
| 1 | フラットシーケンスストラクチャ | Flat Sequence Structure | プログラミング → ストラクチャ |
| 必要数 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 8 | シフトレジスタ | Shift Register | For Loop枠を右クリック |
| 必要数 | 名前でアンバンドル | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 必要数 | 名前でバンドル | Bundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 必要数 | 配列作成 | Build Array | プログラミング → 配列 |
| 1 | 1次元配列を検索 | Search 1D Array | プログラミング → 配列 |
| 1 | 配列サイズ | Array Size | プログラミング → 配列 |
| 必要数 | エラークリア | Clear Errors | ダイアログ＆ユーザインタフェース → エラー処理 |
| 必要数 | エラーをマージ | Merge Errors | ダイアログ＆ユーザインタフェース → エラー処理 |
| 1 | 待機（ミリ秒） | Wait (ms) | プログラミング → タイミング |
| 1 | `FG420_Prepare_Device.vi` | SubVI | `10_FG420` |
| 2 | `FG420_Configure_Channel_Safe.vi` | SubVI | `10_FG420` |
| 4以上 | `FG420_Output.vi` | SubVI | `10_FG420` |
| 1以上 | `FG420_Close.vi` | SubVI | `10_FG420` |
| 1 | `Error_To_TestStatus.vi` | SubVI | `00_Common` |

### 7.1 ストラクチャを先に配置する

1. 上段へPrecheck For Loopを配置する。
2. 中段へMain For Loopを配置する。
3. Main Loop内へBypass Device? Caseを配置する。
4. Bypass=Falseケース内へ3フレームのFlat Sequence Structureを配置する。
5. 下段へCleanup For Loopを配置する。
6. 各For Loopを配置した直後に自動指標付けを設定する。
7. Main Loopへ7個、Cleanup Loopへ1個のShift Registerを追加する。
8. SubVIはストラクチャ完成後に各Case / Frameへ配置する。

### 7.2 Main Loop Shift Registerの上下順

```text
1. VISA References[]
2. Device States[]
3. Applied Ch1 Configs[]
4. Applied Ch2 Configs[]
5. Device Errors[]
6. First Error
7. Abort New Devices?
```

左右のShift Registerを同じ上下順にする。

---

## 8. 配線順

## 8.1 Precheck For Loop

1. 1個目のFor Loopを配置する。
2. `Device Configs`を左枠入力トンネルへ接続する。
3. 入力トンネルを右クリックし、`指標付けを有効（Enable Indexing）`を選択する。
4. トンネルへ`[]`が表示されたことを確認する。
5. N端子を未配線にする。
6. ループ内の単一Configを`Current Device Config`とする。
7. `Seen VISA Resources`用Shift Registerを追加する。
8. 左外側へVISA resource name型の空一次元配列定数を接続する。
9. `Enabled Device Count`用Shift Registerを追加し、左外側へU32定数`0`を接続する。
10. `Validation Error`用Shift Registerを追加し、左外側へ`error in`を接続する。
11. Current Device ConfigをUnbundle By Nameへ接続し、Enabled?、Logical Name、VISA Resource、Ch1 Config、Ch2 Configを表示する。
12. Enabled?をCase selectorへ接続する。
13. Enabled=Falseケースでは3個のShift Register左内側を対応する右内側へ接続する。
14. Enabled=TrueケースではEnabled Count左内側を加算（Add）の`x`へ接続する。
15. U32定数`1`をAddの`y`へ接続する。
16. Add出力をEnabled Count右内側へ接続する。
17. Ch1 ConfigとCh2 Configを各Unbundle By Nameへ接続し、Enabled?を取り出す。
18. 2個のEnabled?をORへ接続し、`Any Channel Enabled?`を作る。
19. Any Channel Enabled?をCase selectorへ接続する。
20. FalseケースではFor Loopの`i`端子とLogical NameをFormat Into Stringへ接続し、-710121を作る。
21. 現在のValidation ErrorをMerge Errors第1入力、-710121 errorを第2入力へ接続する。
22. Trueケースでは現在のValidation Errorを通過させる。
23. Seen VISA左内側をSearch 1D Arrayの`array`へ接続する。
24. VISA Resourceを`element`へ接続する。
25. Search出力indexを以上?（Greater Or Equal?）の`x`へ接続する。
26. I32定数`0`を同関数の`y`へ接続する。
27. Greater Or Equal?出力を`Duplicate?` Case selectorへ接続する。
28. Duplicate=TrueではVISA Resource、Search index、現在の`i`をFormat Into Stringへ順に接続し、-710120を作る。
29. 現在Validation ErrorをMerge Errors第1入力、-710120を第2入力へ接続する。
30. Duplicate=TrueではSeen VISA左内側を右内側へ接続する。
31. Duplicate=FalseではSeen VISA左内側とVISA ResourceをBuild Arrayへ接続する。
32. Build Arrayを右クリックし、`入力を連結（Concatenate Inputs）`を有効にする。
33. Build Array出力をSeen VISA右内側へ接続する。
34. Precheck Loop右外側のEnabled Countを等しい?（Equal?）の`x`へ接続する。
35. U32定数`0`をEqual?の`y`へ接続する。
36. Equal?=Trueでは-710122を作り、Validation Error右外側とMerge Errorsする。
37. Merge結果を`Precheck Error`とする。

## 8.2 Main For Loopと入力トンネル

38. 2個目のFor Loopを配置する。
39. `Device Configs`を左入力トンネルへ接続し、自動指標付けを有効にする。
40. N端子を未配線にする。
41. 1反復で単一`FG420_Device_Config.ctl`を処理する。
42. `Output Duration ms`を別入力トンネルへ接続し、指標付けを無効にする。
43. `Enable Output Phase?`を別入力トンネルへ接続し、指標付けを無効にする。
44. `Stop On First Error?`を別入力トンネルへ接続し、指標付けを無効にする。
45. `Precheck Error`を別入力トンネルへ接続し、指標付けを無効にする。

## 8.3 Main Loop Shift Register

46. VISA References Shift Registerの左外側へVISA型空配列を接続する。
47. Device States Shift Registerの左外側へState型空配列を接続する。
48. Applied Ch1 Configs Shift Registerの左外側へChannel Config型空配列を接続する。
49. Applied Ch2 Configs Shift Registerへ同じ型の空配列を接続する。
50. Device Errors Shift Registerへerror cluster空配列を接続する。
51. First Error Shift Registerの左外側へ`Precheck Error`を接続する。
52. Abort New Devices? Shift Registerの左外側へ`Precheck Error.status`を接続する。
53. 配列Shift Registerの左内側は前反復までの配列、右内側はCurrent要素追加後の配列、右外側は全Device結果となる。

## 8.4 Bypass Device? Case

54. Current Device ConfigをUnbundle By Nameへ接続し、Enabled?、VISA Resource、Ch1 Config、Ch2 Configを表示する。
55. Enabled?をNotへ接続し、`Disabled Device?`を作る。
56. Abort New Devices?左内側とStop On First Error?をANDへ接続し、`Abort This Device?`を作る。
57. Precheck Errorのstatusを取り出す。
58. Disabled Device?、Abort This Device?、Precheck Error.statusをOR設定のCompound Arithmeticへ接続する。
59. OR出力を`Bypass Device?` Case selectorへ接続する。
60. TrueケースでDisabled Device=TrueかつPrecheck Error=Falseの場合、Current VISA=VISA Resource、Current State=初期State、Current Applied Ch1=入力Ch1 Config、Current Applied Ch2=入力Ch2 Config、Current Device Error=No Errorとする。
61. TrueケースでPrecheck Error=TrueまたはAbort This Device=Trueの場合、Current VISA=VISA Resource、Current State=初期State、Applied Ch1/Ch2=入力Config、Current Device Error=First Error左内側とする。
62. TrueケースではPrepare、Configure、Output、Wait、Closeを配置しない。
63. Falseケースへ手順8.5以降を配置する。
64. Bypass Case右側へCurrent VISA、Current State、Current Applied Ch1、Current Applied Ch2、Current Device Errorの5トンネルを作る。
65. True / False両ケースで5トンネルを全て配線する。

## 8.5 Prepare Device

66. Current Device Configを`FG420_Prepare_Device.vi / Device Config`へ接続する。
67. No Error定数を`FG420_Prepare_Device.vi / error in`へ接続する。
68. 別DeviceのFirst ErrorをPrepareのerror inへ接続しない。
69. PrepareのVISA outを`VISA After Prepare`とする。
70. PrepareのDevice Stateを`State After Prepare`とする。
71. Prepareのerror outを`Error After Prepare`とする。
72. PrepareのStatus / TestErrorは接続しない。

## 8.6 Ch1 Configure

73. `VISA After Prepare`を1個目のConfigure VIの`VISA reference in`へ接続する。
74. Ch1 Configを`Channel Config`へ接続する。
75. `Error After Prepare`を`error in`へ接続する。
76. VISA outを`VISA After Ch1 Configure`、error outを`Error After Ch1 Configure`とする。
77. Ch1 ConfigをBundle By Nameの基準clusterへ接続する。
78. ConfigureのApplied Ampを`Requested Amplitude Vpp`へ接続する。
79. ConfigureのApplied Offsetを`Requested Offset V`へ接続する。
80. Ch1 Config.Enabled?をCase selectorへ接続する。
81. TrueケースではBundle出力をCurrent Applied Ch1 Configとする。
82. Falseケースでは元Ch1 ConfigをCurrent Applied Ch1 Configとする。
83. Error After Ch1 Configure.statusをNotへ接続する。
84. Not出力とCh1 Enabled?をANDへ接続し、`Ch1 Configured?`を作る。
85. State After PrepareをBundle By Nameの基準clusterへ接続する。
86. Ch1 Configured?をStateの同名フィールドへ接続する。
87. Bundle出力を`State After Ch1 Configure`とする。

## 8.7 Ch2 Configure

88. `VISA After Ch1 Configure`を2個目のConfigure VIのVISA入力へ接続する。
89. Ch2 Configを`Channel Config`へ接続する。
90. `Error After Ch1 Configure`をerror inへ接続する。
91. VISA outを`VISA After Ch2 Configure`、error outを`Error After Ch2 Configure`とする。
92. Ch2 ConfigをBundle By Nameの基準clusterへ接続する。
93. ConfigureのApplied AmpとApplied Offsetを対応フィールドへ接続する。
94. Ch2 Enabled? CaseのTrueでBundle出力、Falseで元Ch2 ConfigをCurrent Applied Ch2 Configとする。
95. Error After Ch2 Configure.statusをNotへ接続する。
96. Not出力とCh2 Enabled?をANDへ接続し、`Ch2 Configured?`を作る。
97. State After Ch1 ConfigureをBundle By Nameの基準clusterへ接続する。
98. Ch2 Configured?をStateの同名フィールドへ接続する。
99. Bundle出力を`State After Configure`とする。

## 8.8 Flat Sequence Frame 0：Output ON

100. 3フレームのFlat Sequence Structureを配置する。
101. VISA After Ch2 Configure、Error After Ch2 Configure、State After ConfigureをFrame 0へ入れる。
102. Enable Output Phase?、Ch1 Enabled?、Ch1 Output On?、NOT Error After Ch2 Configure.statusをANDへ接続する。
103. AND出力を`Ch1 Output Request?` Case selectorへ接続する。
104. Ch1 Output Request=FalseではVISA、error、Stateを素通りする。
105. TrueではVISAを`FG420_Output.vi / VISA reference in`へ接続する。
106. Ch1 Config.Channelを`Channel`へ接続する。
107. Boolean定数`True`を`Output On?`へ接続する。
108. 現在errorを`error in`へ接続する。
109. Output error.status=Falseの場合、State.Ch1 Output On?をTrueへBundle By Name更新する。
110. Ch1 Case出力VISA、error、StateをCh2 ON判定へ渡す。
111. Enable Output Phase?、Ch2 Enabled?、Ch2 Output On?、NOT Ch1 Case error.statusをANDへ接続する。
112. AND出力を`Ch2 Output Request?` Case selectorへ接続する。
113. FalseではVISA、error、Stateを素通りする。
114. TrueではCh2 Channel、Output=True、現在VISA、現在errorを2個目のFG420_Output.viへ接続する。
115. Output error.status=Falseの場合、State.Ch2 Output On?をTrueへ更新する。
116. Frame 0のVISA、error、StateをFrame 1へ渡す。

## 8.9 Flat Sequence Frame 1：Wait

117. StateからCh1 Output On?とCh2 Output On?をUnbundle By Nameで取り出す。
118. 2個のBooleanをORへ接続し、`Any Output On?`を作る。
119. Any Output On?とNOT Current Error.statusをANDへ接続する。
120. AND出力を`Wait Required?` Case selectorへ接続する。
121. Trueケースへ待機（ミリ秒）（Wait (ms)）を配置する。
122. `Output Duration ms`を`milliseconds to wait`へ接続する。
123. True / False両ケースでVISA、error、Stateを素通りする。
124. Frame 1のerrorを`Original Device Error Before Cleanup`として分岐保存する。

## 8.10 Flat Sequence Frame 2：通常OFFとClose

125. `Original Device Error Before Cleanup`をClear Errorsへ接続する。
126. Clear Errors出力をCh1 OFF呼出し用errorとする。
127. No Error定数を`Cleanup Error Accumulator 0`とする。
128. Ch1 Enabled?をCase selectorへ接続する。
129. FalseではVISAを素通りし、No Errorを`Ch1 OFF Error`とする。
130. TrueではVISA、Ch1 Channel、Boolean False、クリア済みerrorをFG420_Output.viへ接続する。
131. Output error outを`Ch1 OFF Error`とする。
132. Accumulator 0をMerge Errors第1入力、Ch1 OFF Errorを第2入力へ接続する。
133. Merge出力を`Cleanup Error Accumulator 1`とする。
134. Accumulator 1をClear Errorsへ接続する。
135. Ch2 Enabled? CaseでVISA、Ch2 Channel、Boolean False、クリア済みerrorをFG420_Output.viへ接続する。
136. FalseではVISAを素通りし、No Errorを`Ch2 OFF Error`とする。
137. Accumulator 1とCh2 OFF ErrorをMerge Errorsし、`Cleanup Error Accumulator 2`を作る。
138. Accumulator 2をClear Errorsへ接続する。
139. Ch2 OFF後VISAを`FG420_Close.vi / VISA reference in`へ接続する。
140. クリア済みerrorを`FG420_Close.vi / error in`へ接続する。
141. Close error outを`Close Error`とする。
142. Accumulator 2をMerge Errors第1入力、Close Errorを第2入力へ接続する。
143. Merge出力を`Cleanup Error Final`とする。
144. Original Device ErrorをMerge Errors第1入力、Cleanup Error Finalを第2入力へ接続する。
145. Merge出力を`Merged Device Error`とする。
146. Original Errorを第1入力に置く。
147. Ch1 OFF成功時にState.Ch1 Output On?をFalseへ更新する。
148. Ch2 OFF成功時にState.Ch2 Output On?をFalseへ更新する。
149. Close成功時にState.Closed?をTrueへ更新する。
150. Close直前のVISAをCurrent VISA Resultとする。

## 8.11 Main Loop Shift Register更新

151. Bypass Caseから5個のCurrent結果を出す。
152. VISA References左内側配列とCurrent VISAをBuild Arrayへ接続する。
153. Build Arrayで`入力を連結`を有効にする。
154. 出力をVISA References右内側へ接続する。
155. State、Applied Ch1、Applied Ch2、Device Errorも各左内側配列へCurrent単一要素を末尾追加する。
156. First Error左内側をMerge Errors第1入力へ接続する。
157. Current Device Errorを第2入力へ接続する。
158. Merge出力をFirst Error右内側へ接続する。
159. Stop On First Error?とCurrent Device Error.statusをANDへ接続する。
160. AND出力とAbort New Devices?左内側をORへ接続する。
161. OR出力をAbort New Devices?右内側へ接続する。

## 8.12 Cleanup For Loop

162. 3個目のFor LoopをMain Loop下段へ配置する。
163. Main Loop右外側のVISA References[]、Device States[]、Device Errors[]とフロントパネルDevice Configs[]を左枠へ接続する。
164. 4入力トンネル全てで自動指標付けを有効にする。
165. N端子を未配線にする。
166. ループ内ではCurrent VISA、Current State、Current Error、Current Device Configの単一要素になる。
167. Final First Error Shift Registerを追加し、左外側へMain Loop First Error右外側を接続する。
168. State.Initialized?とNOT State.Closed?をANDへ接続する。
169. AND出力を`Needs Cleanup?` Case selectorへ接続する。
170. FalseケースではCurrent StateとCurrent Errorを出力トンネルへ接続する。
171. TrueケースではCurrent ErrorをOriginal Device Errorとして保存する。
172. Original Device ErrorをClear Errorsへ接続する。
173. Ch1 Enabled? CaseでCh1 OFFを試行する。
174. Ch1 OFF errorをCleanup accumulatorへMergeする。
175. accumulatorをClear ErrorsしてCh2 Enabled? CaseでCh2 OFFを試行する。
176. Ch2 OFF errorをaccumulatorへMergeする。
177. accumulatorをClear ErrorsしてCloseを試行する。
178. Original Device ErrorをMerge Errors第1入力へ接続する。
179. Cleanup Errorを第2入力へ接続する。
180. Merge出力を`Cleanup Merged Device Error`とする。
181. OFF / Close成功結果でStateをBundle By Name更新する。
182. Cleanup LoopのState出力トンネルで自動指標付けを有効にする。
183. Error出力トンネルで自動指標付けを有効にする。
184. Final First Error左内側とCleanup Merged Device ErrorをMergeし、右内側へ接続する。
185. Shift Register右外側を`Final Error`とする。

## 8.13 フロントパネル出力

186. Cleanup LoopのState配列出力を`Device States`へ接続する。
187. Main LoopのApplied Ch1 Configs右外側を`Applied Ch1 Configs`へ接続する。
188. Main LoopのApplied Ch2 Configs右外側を`Applied Ch2 Configs`へ接続する。
189. Cleanup LoopのError配列出力を`Device Errors`へ接続する。
190. Final Errorを`Error_To_TestStatus.vi / error in`へ接続する。
191. String定数`FG420`を`Device Name`へ接続する。
192. Status、TestError、error outを各表示器へ接続する。

## 8.14 全Case出力

| 経路 | State | Applied Ch1/Ch2 | Device Error | Cleanup |
|---|---|---|---|---|
| Disabled Device | 初期State | 入力Config | No Error | 対象外 |
| Precheck error | 初期State | 入力Config | Validation Error | VISA未Open |
| Stop On First Error skip | 初期State | 入力Config | First Error | 対象外 |
| Prepare Init失敗 | Prepare State | 入力または安全値 | Prepare Error | Close不要 |
| Prepare Init成功後失敗 | Initialized=True | 入力または安全値 | Prepare Error | OFF / Close実行 |
| Ch設定途中error | 成功分だけState更新 | 成功値 / 安全値 | 最初のCh error | OFF / Close実行 |
| Output ON後error | ON成功分をState記録 | Applied値 | Output error | OFF / Close実行 |
| Cleanup errorのみ | 成功分だけState更新 | Applied値 | Cleanup error | Cleanup Loopで再試行 |
| Original + Cleanup error | 成功分だけState更新 | Applied値 | Original優先 | Cleanup errorも配列へ保持 |
| 正常 | Closed=True | Applied値 | No Error | 完了 |

---

## 9. 単体テスト

| No. | 条件 | 期待結果 |
|---:|---|---|
| 1 | 1台有効、Ch1のみ、Output On=True | 1反復、Ch1設定・ON・Wait・OFF・Close、配列1要素 |
| 2 | 1台有効、Ch2のみ | Ch1バイパス、Ch2設定・ON・OFF |
| 3 | 1台有効、2ch有効 | Ch1とCh2に異なる条件を設定、両ch Cleanup |
| 4 | 2台有効 | Main Loop 2反復、出力配列2要素、IDN別管理 |
| 5 | Device[0] Disabled、Device[1] Enabled | index 0は初期State、index 1は通常処理 |
| 6 | Device Configs空配列 | -710122、機器操作なし |
| 7 | Enabled DeviceでCh1/Ch2両方Disabled | -710121、機器操作なし |
| 8 | VISA Resource重複 | -710120、機器操作なし |
| 9 | Prepare Init失敗 | Initialized=False、Close不要、他Device Cleanup継続 |
| 10 | Prepare Get ID失敗 | Initialized=True、Configure/ONスキップ、Close実行 |
| 11 | Ch1 Set Freq失敗 | Ch2 Wrapperはerror伝播で実処理スキップ、OFF/Close実行 |
| 12 | Ch2 Limit Reject | Output ONなし、-710112、Cleanup実行 |
| 13 | Ch1 Clamp | Applied Ch1 Configへ縮小振幅を保存 |
| 14 | Ch1 ON成功後にCh2 ON error | Ch1 OFF、Ch2 OFF試行、Close、Original error保持 |
| 15 | Ch1 OFF Cleanup error | Ch2 OFFとCloseを継続、Cleanup error記録 |
| 16 | Original error + Close error | Device ErrorはOriginalを優先 |
| 17 | `Stop On First Error?=True` | 最初の失敗後の有効Deviceは通常処理を開始しないがCleanup Loopは全index反復 |
| 18 | `Enable Output Phase?=False` | Prepare / Configure後にON・Waitをスキップ、Close実行 |
| 19 | error in.status=True | 機器操作なし、元errorを最終出力へ保持 |

---

## 完了確認

- [ ] Device Configs入力トンネルで自動指標付けを有効にした。
- [ ] ループ外配列型とループ内単一型を確認した。
- [ ] Main Loopに7個のShift Registerを追加した。
- [ ] 全配列Shift Registerで空配列初期値、Current要素追加、右外側出力を配線した。
- [ ] Disabled Device側でも5個のCurrent結果を生成した。
- [ ] Ch1 / Ch2 Enabled?を別Caseへ接続した。
- [ ] Output ON後にWaitし、通常OFF / Closeへ進むFlat Sequenceを作成した。
- [ ] CleanupでOriginal Errorを第1入力、Cleanup Errorを第2入力としてMergeした。
- [ ] Cleanup error後も次のOFF / Closeを試行するためClear Errorsを使用した。
- [ ] Cleanup Loopで全機器indexを再走査した。
- [ ] Status / TestErrorをPoC末尾で1回だけ生成した。
