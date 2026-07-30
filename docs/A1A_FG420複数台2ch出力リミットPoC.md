# 付録 A1A. FG420 複数台・2ch・出力リミット対応 PoC 実装手順（統合正本）

**最終整理日：2026-07-30**

> 本ファイルをFG420拡張実装の唯一の正本とする。旧`A1A_04`～`A1A_08`の分冊内容は本章へ統合し、分冊は削除する。
>
> 横河ドライバVIの端子、Query／Set動作および制限値は`IMFG410-63JA`と対象PCの実VIで照合し、証跡は[00C](./00C_一次資料とバージョン基準.md)に従う。
>
> LabVIEW画面を再現できる記述粒度は[00A](./00A_LabVIEW実装資料の記述ルール.md)、機能要求をデータモデル・アルゴリズム・LabVIEW構造へ変換する規則は[00B](./00B_LabVIEW学習型VI設計ルール.md)を正とする。

---

## A1A.0 本章の位置づけ

[A1_付録_FG420基盤単体試験自動化.md](./A1_付録_FG420基盤単体試験自動化.md)に記載した1台・基本通信PoCは実機通信確認済みである。

既存PoCの成立済みフローは次のとおり。

```text
Initialize
  → FUNC
  → FREQ
  → OUTP Load
  → VOLT
  → VOLT Offs
  → OUTP ON
  → Wait
  → OUTP OFF
  → Close
```

本章では次の3機能を追加する。

1. 設定した絶対電圧リミットを超える条件をFG420へ送信しない。
2. 複数台のFG420を接続し、機器ごとに異なる条件を設定できる。
3. FG420のCh1／Ch2を独立して設定できる。

横河提供の`YKFG400 *.vi`は変更しない。自作VIは`10_FG420`配下へ置き、薄いラッパVI、純粋ロジックVI、複合VI、PoC VIへ分ける。

---

## A1A.1 マニュアルから確定している仕様

### A1A.1.1 VISAとerror

- 全操作VIは標準`error in`／`error out`を持つ。
- `Close`以外の操作VIはVISA session in／outを持つ。
- VISA wireとerror wireを左から右へ直列接続して実行順序を固定する。
- 設定VIの`Ch(Ch1)`または`Ch?(Ch1)`へCh1／Ch2を明示的に渡す。

### A1A.1.2 2ch独立設定

```text
CHAN Mode = INDependent
INST Coup  = NONE
```

- `INDependent`：Ch1とCh2を独立設定する。
- `NONE`：Ch1へ送った設定をCh2へ自動反映しない。

### A1A.1.3 振幅・オフセット・負荷

| 負荷条件 | 振幅範囲 | オフセット範囲 |
|---|---:|---:|
| 開放／Hi-Z | 0～20 Vp-p | -10～+10 V |
| 50 Ω | 0～10 Vp-p | -5～+5 V |

`YKFG400 OUTP Load.vi`は1 Ω～10 kΩの数値負荷または`INFinity`を扱う。

負荷によって振幅・オフセット範囲が変わるため、チャネル設定順を次で固定する。

```text
OUTP Load
  → Amplitude Minimum / Maximum取得
  → Offset Minimum / Maximum取得
  → 出力リミット判定
  → VOLT
  → VOLT Offs
```

### A1A.1.4 機器識別

`YKFG400 IDN.vi`は次の形式を返す。

```text
YOKOGAWA,FG4xx,シリアル番号,ファームウェアバージョン
```

複数台PoCではVISA ResourceとIDNをindex単位で保持する。

### A1A.1.5 複数台同期

本章の標準PoCは複数台を1つのVIから個別設定するが、VISAによる順次Output ONの時刻差を保証しない。

厳密同期が必要な場合だけ、外部基準周波数、共通外部トリガ、`ROSC Sour`、`TRIG Sour`、`TRIG`を別途実機確認する。

---

## A1A.2 実装レイヤと呼出し関係

```text
PoC_FG420_Multi_Device.vi
  ├─ FG420_Prepare_Device.vi
  ├─ FG420_Configure_Channel_Safe.vi × Ch1 / Ch2
  ├─ FG420_Output.vi
  ├─ Wait (ms)
  ├─ FG420_Output.vi（Cleanup OFF）
  └─ FG420_Close.vi

FG420_Prepare_Device.vi
  ├─ FG420_Init.vi
  ├─ FG420_Get_ID.vi
  ├─ FG420_Set_PowerOn_Output.vi
  ├─ FG420_Set_ChanMode.vi
  └─ FG420_Set_Coupling.vi

FG420_Configure_Channel_Safe.vi
  ├─ FG420_Output.vi（OFF）
  ├─ FG420_Set_Load.vi
  ├─ FG420_Query_Ampl_Bound.vi ×2
  ├─ FG420_Query_Offset_Bound.vi ×2
  ├─ FG420_Apply_Output_Limit.vi
  ├─ FG420_Set_Func.vi
  ├─ FG420_Set_Freq.vi
  ├─ FG420_Set_Ampl.vi
  └─ FG420_Set_Offset.vi
```

| レイヤ | 責務 |
|---|---|
| 薄いラッパVI | 横河ドライバVIを1個だけ呼ぶ |
| 純粋ロジックVI | 数値計算、入力検証、Reject／Clampを行う |
| 複合VI | 1機器または1チャネルの操作を安全な順序で完結する |
| PoC VI | 複数台反復、2ch処理、Wait、Cleanup、結果集計を行う |

---

## A1A.3 typedef作成

### A1A.3.1 `FG420_Limit_Mode.ctl`

Enum typedef。

| 値 | 意味 |
|---|---|
| `Reject` | 超過時にエラーを返し設定を送らない |
| `Clamp` | オフセットを維持して振幅を縮小する |

既定値は`Reject`。

### A1A.3.2 `FG420_Channel_Config.ctl`

| フィールド | 型 | 初期値 |
|---|---|---:|
| Enabled? | Boolean | False |
| Channel | ドライバCh Enum | Ch1 |
| Function | ドライバ波形Enum | Sin |
| Frequency Hz | DBL | 1000 |
| Load Infinity? | Boolean | True |
| Load Ohm | DBL | 50 |
| Requested Amplitude Vpp | DBL | 1.0 |
| Requested Offset V | DBL | 0.0 |
| Output Limit Abs V | DBL | 5.0 |
| Limit Mode | `FG420_Limit_Mode.ctl` | Reject |
| Output On? | Boolean | False |

### A1A.3.3 `FG420_Device_Config.ctl`

| フィールド | 型 | 初期値 |
|---|---|---:|
| Enabled? | Boolean | False |
| Logical Name | String | FG420_01 |
| VISA Resource | VISA resource name | 空 |
| ID Check? | Boolean | True |
| Reset? | Boolean | True |
| Ch1 Config | `FG420_Channel_Config.ctl` | Channel=Ch1 |
| Ch2 Config | `FG420_Channel_Config.ctl` | Channel=Ch2 |

### A1A.3.4 `FG420_Device_State.ctl`

| フィールド | 型 | 初期値 |
|---|---|---:|
| Initialized? | Boolean | False |
| ID Read? | Boolean | False |
| Independent Mode? | Boolean | False |
| Coupling Disabled? | Boolean | False |
| Ch1 Configured? | Boolean | False |
| Ch2 Configured? | Boolean | False |
| Ch1 Output On? | Boolean | False |
| Ch2 Output On? | Boolean | False |
| Closed? | Boolean | False |
| IDN | String | 空 |

全ctlは`10_FG420\TypeDefs`へ保存し、`Advanced → Customize → Type Def.`でtypedef化する。

---

## A1A.4 薄いラッパVI

### A1A.4.1 共通ルール

1. 横河ドライバVIを1個だけ呼ぶ。
2. VISA reference in／outとerror in／outを公開する。
3. 通常設定ラッパは`error in.status=True`時にドライバVIを呼ばず安全出力を返す。
4. Cleanup用Output OFFとCloseは、上位VIがClear Errorsしたcleanup wireで呼ぶ。
5. `Error_To_TestStatus.vi`は各薄いラッパ末尾で1回だけ呼ぶ。
6. `Device Name`はString定数`FG420`。
7. Query無効時の不要出力は公開しない。

### A1A.4.2 追加ラッパ一覧

| 自作VI | 呼ぶドライバVI | 主な入力 | 主な出力・固定値 |
|---|---|---|---|
| `FG420_Set_ChanMode.vi` | `YKFG400 CHAN Mode.vi` | VISA、Channel Mode、error | Read=False。標準値INDependent |
| `FG420_Set_Coupling.vi` | `YKFG400 INST Coup.vi` | VISA、Couple、error | Read=False。標準値NONE |
| `FG420_Get_ID.vi` | `YKFG400 IDN.vi` | VISA、error | IDN String |
| `FG420_Set_PowerOn_Output.vi` | `YKFG400 OUTP Pon.vi` | VISA、Mode、error | Read=False。標準値OFF |
| `FG420_Query_Ampl_Bound.vi` | `YKFG400 VOLT.vi` | VISA、Channel、Bound、error | Units=VPP、Read=True、Bound Value Vpp |
| `FG420_Query_Offset_Bound.vi` | `YKFG400 VOLT Offs.vi` | VISA、Channel、Bound、error | Units=V、Read=True、Bound Value V |
| `FG420_Read_System_Error.vi` | `YKFG400 SYST Err.vi` | VISA、error | 機器error queue |

既存ラッパとして`FG420_Init.vi`、`FG420_Output.vi`、`FG420_Set_Load.vi`、`FG420_Set_Func.vi`、`FG420_Set_Freq.vi`、`FG420_Set_Ampl.vi`、`FG420_Set_Offset.vi`、`FG420_Close.vi`を使用する。

### A1A.4.3 ラッパ共通配線

```text
error in
  → Unbundle By Name(status)
  → Case Structure

True Case:
  VISA out = VISA in
  値出力 = 0 / 空文字列 / False
  error out = error in

False Case:
  VISA in → YKFG400 driver VISA in
  各設定端子 → driver同名端子
  error in → driver error in
  driver VISA out → VISA out
  driver error out → Error_To_TestStatus.vi → Status / TestError / error out
```

---

# A1A.5 `FG420_Apply_Output_Limit.vi` 詳細作成手順

## 0. 実現したい機能とVIの責務

要求振幅と要求オフセットから正側ピークと負側ピークを別々に計算し、設定した絶対電圧リミットを超える条件を後段へ流さない。

```text
Positive Peak = Offset + Amplitude Vpp / 2
Negative Peak = Offset - Amplitude Vpp / 2
```

Rejectは設定を拒否する。Clampはオフセットを維持し、振幅だけを縮小する。本VIはVISAとFG420ドライバを呼ばない。

## 1. 入力データの実体

| 端子 | 型 |
|---|---|
| Requested Amplitude Vpp | DBL |
| Requested Offset V | DBL |
| Device Amplitude Min Vpp | DBL |
| Device Amplitude Max Vpp | DBL |
| Device Offset Min V | DBL |
| Device Offset Max V | DBL |
| Output Limit Abs V | DBL |
| Limit Mode | `FG420_Limit_Mode.ctl` |
| error in | error cluster |

## 2. 出力データモデル

| 端子 | 型 | 異常時安全値 |
|---|---|---:|
| Applied Amplitude Vpp | DBL | 0.0 |
| Applied Offset V | DBL | 0.0 |
| Positive Peak V | DBL | 0.0。入力検証後のReject／Clamp異常では要求ピークを返す |
| Negative Peak V | DBL | 0.0。入力検証後のReject／Clamp異常では要求ピークを返す |
| Limited? | Boolean | False。Reject／Clamp対象時True |
| error out | error cluster | 元errorまたはローカルerror |

## 3. 前提条件・異常条件

| Code | 条件 |
|---:|---|
| -710110 | Output Limit Abs V <= 0 |
| -710111 | Clamp時にオフセット単独でLimit超過 |
| -710112 | Reject時に正側または負側ピークがLimit超過 |
| -710113 | Device Min/Maxが逆転、またはClamp後安全性を満たさない |
| -710114 | 要求振幅／オフセットが機器範囲外 |

## 4. 処理アルゴリズム

```text
if error in.status=True:
    全数値出力=0
    Limited=False
    error out=error in
else:
    Output Limit > 0を確認
    Device Amplitude Min <= Maxを確認
    Device Offset Min <= Maxを確認
    Requested Amplitude >= 0を確認
    Requested AmplitudeがDevice範囲内か確認
    Requested OffsetがDevice範囲内か確認

    Half Amplitude = Requested Amplitude / 2
    Positive Peak = Requested Offset + Half Amplitude
    Negative Peak = Requested Offset - Half Amplitude
    Positive Exceeded = Positive Peak > Output Limit
    Negative Exceeded = Negative Peak < -Output Limit
    Limit Exceeded = Positive Exceeded OR Negative Exceeded

    case Limit Mode:
        Reject:
            if Limit Exceeded:
                Applied値=0
                Limited=True
                -710112
            else:
                Applied値=Requested値
                Limited=False
                no error

        Clamp:
            if Limit Exceeded=False:
                Applied値=Requested値
                Limited=False
                no error
            elif abs(Requested Offset) > Output Limit:
                Applied値=0
                Limited=True
                -710111
            else:
                Allowed Amplitude = 2 × (Output Limit - abs(Requested Offset))
                Applied Amplitude = min(Requested Amplitude, Allowed Amplitude, Device Amplitude Max)
                Applied Offset = Requested Offset
                Clamp後ピークを再計算して安全確認
```

## 5. LabVIEW構造の選定理由

- 外側`error in.status` Case Structureで元errorを最優先する。
- Limit正値、Device Bounds、Requested Boundsを別Caseにする。
- `Limit Mode` Enum CaseでReject／Clampを分離する。
- Reject／Clamp内部で`Limit Exceeded?` Boolean Caseを使う。
- Clamp内部で`Offset Alone Exceeded?`と`Clamp Result Safe?`を別Caseにする。
- For Loop、While Loop、Shift Registerは使用しない。

全Caseへ次の6トンネルを同じ上下順で作り、`Use default if unwired`を無効にする。

1. Applied Amplitude Vpp
2. Applied Offset V
3. Positive Peak V
4. Negative Peak V
5. Limited?
6. Final Error

## 6. フロントパネル入出力

`10_FG420\FG420_Apply_Output_Limit.vi`として保存する。

左へ9入力、右へ6出力を配置する。全数値はDBL、Limit Modeはtypedef、errorは標準clusterとする。16端子以上のコネクタペインを使い、全端子を割り当てる。

## 7. 配置する関数およびSubVI

- Unbundle By Name
- Case Structure
- In Range and Coerce ×2
- Absolute Value
- Divide ×2
- Add ×2
- Subtract ×3
- Multiply
- Negate
- Min & Max ×2
- Greater?、Less?、Greater Or Equal?、Less Or Equal?
- Compound Arithmetic（AND／OR）
- Format Into String
- Bundle By Name

## 8. 配線順

### 8.1 error in Case

1. `error in`をUnbundle By Nameへ接続し、`status`を外側Case selectorへ接続する。
2. True CaseはDBL`0.0`×4、Boolean`False`、元`error in`を6トンネルへ接続する。
3. False Caseへ全入力をトンネルで渡す。

### 8.2 入力検証

4. `Output Limit Abs V`とDBL`0.0`をGreater?へ接続する。Falseで-710110を生成する。
5. Device Amp Min／MaxをLess Or Equal?へ接続する。
6. Device Offset Min／Maxを別のLess Or Equal?へ接続する。
7. 2結果をANDし、Falseで-710113を生成する。
8. Requested AmpとDBL`0.0`をGreater Or Equal?へ接続する。
9. Requested AmpをIn Range and Coerceの`x`、Amp Minをlower、Amp Maxをupperへ接続し、両包含端子をTrueにする。
10. Requested Offsetを2個目のIn Range and Coerceへ同じ方法で接続する。
11. 3結果をANDし、Falseで-710114を生成する。

各ローカルerrorは`error in`をBundle By Nameの基準clusterへ接続し、status=True、I32 code、Format Into String出力をsourceへ接続する。

### 8.3 ピーク計算と超過判定

12. Requested AmpをDivideの`x`、DBL`2.0`を`y`へ接続しHalf Amplitudeを作る。
13. Requested OffsetとHalf AmplitudeをAddへ接続しPositive Peakを作る。
14. Requested OffsetとHalf AmplitudeをSubtractへ接続しNegative Peakを作る。
15. Positive PeakとOutput LimitをGreater?へ接続しPositive Exceededを作る。
16. Output LimitをNegateへ接続しNegative Limitを作る。
17. Negative PeakとNegative LimitをLess?へ接続しNegative Exceededを作る。
18. 2結果をORしLimit Exceededを作る。
19. Limit ModeをEnum Case selectorへ接続する。

### 8.4 Reject Case

20. Limit ExceededをBoolean Case selectorへ接続する。
21. False：Requested Amp→Applied Amp、Requested Offset→Applied Offset、要求ピーク、Limited=False、error inを出力する。
22. True：Applied値=DBL`0.0`、要求ピーク、Limited=True、-710112を出力する。

### 8.5 Clamp Case

23. Limit Exceeded=FalseはReject正常時と同じ出力にする。
24. TrueではRequested OffsetをAbsolute Valueへ接続する。
25. Absolute OffsetとOutput LimitをGreater?へ接続する。
26. Offset単独超過=TrueはApplied値=0、要求ピーク、Limited=True、-710111を出力する。
27. FalseではOutput Limit - Absolute OffsetをSubtractで作る。
28. 結果へDBL`2.0`をMultiplyしAllowed Amplitudeを作る。
29. Requested AmpとAllowed AmpをMin & Maxへ接続し`min`を取得する。
30. その値とDevice Amp Maxを2個目のMin & Maxへ接続しApplied Amp候補を作る。
31. Applied OffsetはRequested Offsetをそのまま接続する。
32. Applied Amp候補／2、Requested Offset±Applied HalfからClamp後ピークを再計算する。
33. Clamp後Positive <= Output LimitとClamp後Negative >= Negative Limitを別比較で作りANDする。
34. 安全=TrueはApplied候補、Requested Offset、要求ピーク、Limited=True、error inを出力する。
35. 安全=FalseはApplied値=0、要求ピーク、Limited=True、-710113を出力する。

## 9. 単体テスト

- 正常：2 Vpp、0 V、Limit 5 V。
- 境界：10 Vpp、0 V、Limit 5 V。
- Reject超過：10.0002 Vpp、0 V、Limit 5 V。
- Clamp超過：8 Vpp、2 V、Limit 5 VでApplied=6 Vpp。
- Offset境界：0 Vpp、5 V、Limit 5 V。
- Offset単独超過：0 Vpp、5.0001 V、Limit 5 V。
- Device範囲逆転。
- Requested値がDevice範囲外。
- 既存error in。

---

# A1A.6 `FG420_Configure_Channel_Safe.vi` 詳細作成手順

## 0. 実現したい機能とVIの責務

1台のFG420の1チャネルについて、出力OFF、負荷、機器Min／Max取得、リミット判定、波形、周波数、振幅、オフセットを安全な順序で設定する。

本VIはOutput ON、Wait、Close、複数台反復を担当しない。`Channel Config.Output On?`はPoCで使用する。

## 1. 入力データの実体

| 端子 | 型 |
|---|---|
| VISA reference in | VISA session |
| Channel Config | `FG420_Channel_Config.ctl` |
| error in | error cluster |

Channel ConfigはEnabled?、Channel、Function、Frequency、Load、要求Amp／Offset、Limit、Mode、Output On?を持つ単一clusterである。

## 2. 出力データモデル

| 端子 | 型 |
|---|---|
| VISA reference out | VISA session |
| Applied Amplitude Vpp | DBL |
| Applied Offset V | DBL |
| Positive Peak V | DBL |
| Negative Peak V | DBL |
| Limited? | Boolean |
| Status | `Status.ctl` |
| TestError | `TestError.ctl` |
| error out | error cluster |

安全出力はVISA素通り、DBL`0.0`×4、Limited=False、元errorである。

## 3. 前提条件・異常条件

- `error in.status=True`：全SubVIを呼ばず安全出力。
- `Enabled?=False`：チャネルを変更せずバイパス。
- Output OFF～Query途中error：後段Wrapperはerror in=Trueにより実ドライバを呼ばない。
- Limit error：Function以降を呼ばない。
- Function～Offset途中error：後続Wrapperは実ドライバを呼ばず最初のerrorを保持する。

## 4. 処理アルゴリズム

次を本章の唯一の正本アルゴリズムとする。

```text
if error in.status=True:
    安全出力を返す
else if Channel Config.Enabled?=False:
    チャネルを変更せずバイパスする
else:
    対象ChannelをOutput OFFにする
    対象ChannelのLoadを設定する
    対象ChannelのAmplitude Minimumを取得する
    対象ChannelのAmplitude Maximumを取得する
    対象ChannelのOffset Minimumを取得する
    対象ChannelのOffset Maximumを取得する
    要求値、Device Min/Max、Limit、ModeをLimit VIへ渡す

    if Limit VI error=True:
        設定VIを呼ばずLimit結果とerrorを返す
    else:
        Functionを設定する
        Frequencyを設定する
        Applied Amplitudeを設定する
        Applied Offsetを設定する

最終errorからStatus / TestErrorを生成する
```

この表現における「安全出力」は第2節の安全出力を指す。「バイパス」はVISA reference inとerror inをそのまま出力することを指す。

## 5. LabVIEW構造の選定理由

- 外側error Case Structure。
- 外側False内にEnabled? Case Structure。
- Enabled=True内にWrapper／Query／LimitをVISA・error直列で配置。
- Limit VIのerror.statusをselectorとするCase Structure。
- Limit error=False CaseだけにSet Func／Freq／Ampl／Offsetを配置。
- For LoopとShift Registerは使用しない。

外側CaseとEnabled Caseへ次の7トンネルを同じ順で作る。

1. VISA reference
2. Applied Amplitude Vpp
3. Applied Offset V
4. Positive Peak V
5. Negative Peak V
6. Limited?
7. Final Error

## 6. フロントパネル入出力

`10_FG420\FG420_Configure_Channel_Safe.vi`として保存する。

左にVISA reference in、Channel Config、error in。右にVISA reference out、4 DBL、Limited?、Status、TestError、error outを配置する。12端子以上のコネクタペインへ全端子を割り当てる。

## 7. 配置する関数およびSubVI

- Unbundle By Name：Channel Config全フィールド、error status、Limit error status。
- Case Structure：error、Enabled、Limit error。
- `FG420_Output.vi`
- `FG420_Set_Load.vi`
- `FG420_Query_Ampl_Bound.vi`×2
- `FG420_Query_Offset_Bound.vi`×2
- `FG420_Apply_Output_Limit.vi`
- `FG420_Set_Func.vi`
- `FG420_Set_Freq.vi`
- `FG420_Set_Ampl.vi`
- `FG420_Set_Offset.vi`
- `Error_To_TestStatus.vi`

VISA wireを上段、error wireを下段へ通す。

## 8. 配線順

### 8.1 Cluster展開と外側error Case

1. Channel ConfigをUnbundle By Nameへ接続し、全11フィールドを表示する。
2. `Output On?`へ「PoCで使用。本VIでは未使用」のコメントを置く。
3. error in.statusを外側Case selectorへ接続する。
4. True Case：VISA in、DBL`0.0`×4、False、error inを7トンネルへ接続する。
5. False Case：Enabled?をEnabled Case selectorへ接続する。

### 8.2 Enabled=False

6. VISA inをVISAトンネルへ接続する。
7. DBL`0.0`×4を数値トンネルへ接続する。
8. Boolean`False`をLimited?へ接続する。
9. error inをFinal Errorへ接続する。
10. 機器操作SubVIを配置しない。

### 8.3 Output OFF

11. VISA in→`FG420_Output.vi / VISA reference in`。
12. Channel→`Channel`。
13. Boolean定数`False`→`Output On?`。
14. error in→`error in`。
15. VISA outとerror outを次段へ接続する。

### 8.4 Load

16. Output OFF VISA out→`FG420_Set_Load.vi / VISA reference in`。
17. Channel→`Channel`。
18. Load Infinity?→同名端子。
19. Load Ohm→同名端子。
20. Output OFF error out→Set Load error in。

### 8.5 Amplitude Min／Max

21. Set Load VISA out→1個目Query Ampl VISA in。
22. Channel→Channel、Bound Enum`Minimum`→Bound、Set Load error→error in。
23. `Bound Value Vpp`をDevice Amplitude Minとする。
24. 1個目VISA／error out→2個目Query Ampl VISA／error in。
25. Channel→Channel、Bound Enum`Maximum`→Bound。
26. `Bound Value Vpp`をDevice Amplitude Maxとする。

### 8.6 Offset Min／Max

27. 2個目Query Ampl VISA／error out→1個目Query Offset VISA／error in。
28. Channel→Channel、Bound Enum`Minimum`→Bound。
29. `Bound Value V`をDevice Offset Minとする。
30. 1個目Query Offset VISA／error out→2個目Query Offset VISA／error in。
31. Channel→Channel、Bound Enum`Maximum`→Bound。
32. `Bound Value V`をDevice Offset Maxとする。

### 8.7 Limit VI

33. Requested Amp、Requested Offset、Device Amp Min／Max、Device Offset Min／Max、Output Limit、Limit ModeをLimit VIの同名入力へ接続する。
34. 2個目Query Offset error out→Limit VI error in。
35. Limit VIの5データ出力を出力トンネルへ分岐する。
36. Limit VI error.status→Limit Error Case selector。

### 8.8 Limit Error=True

37. 2個目Query Offset VISA out→VISAトンネル。
38. Limit VIの5データ出力→対応トンネル。
39. Limit VI error out→Final Error。
40. Function／Frequency／Amplitude／Offset設定VIを配置しない。

### 8.9 Limit Error=False

41. Query Offset VISA out→Set Func VISA in。
42. Channel→Set Func Channel、Function→Function、Limit error out→error in。
43. Set Func VISA／error out→Set Freq VISA／error in。
44. Channel→Set Freq Channel、Frequency Hz→Frequency Hz。
45. Set Freq VISA／error out→Set Ampl VISA／error in。
46. Channel→Set Ampl Channel、Applied Amplitude→Amplitude Vpp。
47. Set Ampl VISA／error out→Set Offset VISA／error in。
48. Channel→Set Offset Channel、Applied Offset→Offset V。
49. Set Offset VISA out→VISAトンネル、error out→Final Error。
50. Limit VIの5データ出力→対応トンネル。

### 8.10 Status／TestError

51. 外側Case Final Error→`Error_To_TestStatus.vi / error in`。
52. String定数`FG420`→Device Name。
53. Status、TestError、error outを表示器へ接続する。
54. 外側CaseのVISAと5データを表示器へ接続する。

## 9. 単体テスト

- 正常値。
- Amp／Offset境界値。
- Reject超過。
- Clamp超過。
- Ch1のみEnabled。
- Ch2のみEnabled。
- Enabled=False。
- Set Load途中error。
- Query途中error。
- Set Freq途中error。
- 既存error in。

---

# A1A.7 `FG420_Prepare_Device.vi` 詳細作成手順

## 0. 実現したい機能とVIの責務

```text
FG420_Init.vi
  → FG420_Get_ID.vi
  → IDN文字列検証
  → FG420_Set_PowerOn_Output.vi（OFF）
  → FG420_Set_ChanMode.vi（INDependent）
  → FG420_Set_Coupling.vi（NONE）
```

成功段階をDevice Stateへ保存する。本VIはチャネル設定、Output ON、Wait、Closeを担当しない。

## 1. 入力データの実体

| 端子 | 型 |
|---|---|
| Device Config | `FG420_Device_Config.ctl` |
| error in | error cluster |

本VIではVISA Resource、ID Check?、Reset?、Logical Nameを使用する。Enabled?とCh1／Ch2 ConfigはPoC側で使用する。

## 2. 出力データモデル

| 端子 | 型 |
|---|---|
| VISA reference out | VISA session |
| IDN | String |
| Device State | `FG420_Device_State.ctl` |
| Status | `Status.ctl` |
| TestError | `TestError.ctl` |
| error out | error cluster |

## 3. 前提条件・異常条件

- error in=True：Wrapper未実行、無効VISA定数、空IDN、初期State、元error。
- Init失敗：Initialized?=False、Close不要。
- Init成功後失敗：Initialized?=Trueを保持、PoC CleanupでClose。
- IDNが`^YOKOGAWA,FG420,`へ一致しない：-710130。
- ChanMode失敗：Independent Mode?=False。
- Coupling失敗：Independent Mode?=True、Coupling Disabled?=False。

## 4. 処理アルゴリズム

```text
if error in.status=True:
    安全出力を返す
else:
    Stateをtypedef初期値で作る
    Initを呼ぶ
    Init成功ならInitialized?=True
    Get IDを呼ぶ
    Get ID成功かつIDN非空ならID Read?=True
    IDNをStateへ保存
    Get ID errorが無ければIDNをFG420形式で検証
    PowerOn OutputをOFFへ設定
    ChanModeをINDependentへ設定
    成功ならIndependent Mode?=True
    CouplingをNONEへ設定
    成功ならCoupling Disabled?=True
    VISA、IDN、State、errorを返す
```

## 5. LabVIEW構造の選定理由

- 外側error Case。
- Get ID error Case。
- IDN Valid Case。
- StateはBundle By Nameを4段直列にする。
- VISAとerrorを全Wrapperで直列接続する。
- LoopとShift Registerは使用しない。

## 6. フロントパネル入出力

`10_FG420\FG420_Prepare_Device.vi`として保存する。

左にDevice Config、error in。右にVISA reference out、IDN、Device State、Status、TestError、error outを配置し、8端子以上のコネクタペインへ割り当てる。

## 7. 配置する関数およびSubVI

- Unbundle By Name
- Bundle By Name ×4
- Case Structure ×3
- Match Regular Expression
- String Length
- Greater?、Not、AND
- Format Into String
- `FG420_Init.vi`
- `FG420_Get_ID.vi`
- `FG420_Set_PowerOn_Output.vi`
- `FG420_Set_ChanMode.vi`
- `FG420_Set_Coupling.vi`
- `Error_To_TestStatus.vi`

## 8. 配線順

1. Device ConfigをUnbundle By Nameへ接続し、VISA Resource、ID Check?、Reset?、Logical Nameを取り出す。
2. `FG420_Device_State.ctl`定数を配置し、全Boolean=False、IDN空を確認する。
3. error in.status→外側Case selector。
4. True Case：無効VISA定数、空String、初期State、元errorを4トンネルへ接続する。
5. False Case：VISA Resource、ID Check?、Reset?、error inをFG420_Initへ接続する。
6. Init error.statusをNotし、Initial Stateを基準clusterとするBundle By NameのInitialized?へ接続する。
7. Init VISA／error out→FG420_Get_ID VISA／error in。
8. IDN StringをString Lengthへ接続し、長さ>0を作る。
9. Get ID error.statusをNotし、長さ>0とANDしてID Read?を作る。
10. State After Initを基準clusterとするBundle By NameへID Read?とIDNを接続する。
11. Get ID error.status→Get ID Error Case selector。
12. True：Get ID errorを通過。
13. False：IDNと正規表現`^YOKOGAWA,FG420,`をMatch Regular Expressionへ接続する。
14. 一致False：Logical NameとIDNをFormat Into Stringへ接続し、error inを基準clusterとしてstatus=True、I32`-710130`、sourceをBundle By Nameへ接続する。
15. ID検証後VISA／error→Set PowerOn Output。Mode Enum`OFF`を接続する。
16. Set PowerOn VISA／error→Set ChanMode。Enum`INDependent`を接続する。
17. ChanMode error.statusをNotし、State After IDを基準clusterとしてIndependent Mode?へ接続する。
18. ChanMode VISA／error→Set Coupling。Enum`NONE`を接続する。
19. Coupling error.statusをNotし、State After ChanModeを基準clusterとしてCoupling Disabled?へ接続する。
20. Coupling VISA、IDN、最終State、Coupling errorを外側Caseトンネルへ接続する。
21. Final Error→Error_To_TestStatus、Device Name=`FG420`。

### Close要否

| 失敗位置 | Initialized? | Close |
|---|---|---|
| error in／Init失敗 | False | 不要 |
| Get ID以降 | True | PoC Cleanupで必要 |
| 正常 | True | PoC終了時に必要 |

## 9. 単体テスト

- 正常FG420。
- ID Check／ResetのTrue／False。
- FG410 IDNで-710130。
- Init途中error。
- Get ID途中error。
- ChanMode途中error。
- Coupling途中error。
- 既存error in。

---

# A1A.8 `PoC_FG420_Multi_Device.vi` 詳細作成手順

## 0. 実現したい機能とVIの責務

Device Config一次元配列をFor Loopへ入力し、1反復で1台を処理する。

```text
Prepare Device
  → Ch1 Configure
  → Ch2 Configure
  → Ch1 / Ch2 Output ON
  → Wait
  → Ch1 / Ch2 Output OFF
  → Close
```

Disabled Deviceは操作しないが、結果配列のindexを維持するため1反復を実行する。一部機器失敗時も全機器Cleanupを行う。

## 1. 入力データの実体

| 端子 | 型 |
|---|---|
| Device Configs | `FG420_Device_Config.ctl[]` |
| Output Duration ms | U32 |
| Enable Output Phase? | Boolean |
| Stop On First Error? | Boolean |
| error in | error cluster |

Device Configs入力トンネルは自動指標付けを有効にする。

- Loop外：一次元配列。
- Loop内：単一Device Config cluster。
- N端子：未配線。
- Parallel Iterations：無効。

## 2. 出力データモデル

| 端子 | 型 |
|---|---|
| Device States | `FG420_Device_State.ctl[]` |
| Applied Ch1 Configs | `FG420_Channel_Config.ctl[]` |
| Applied Ch2 Configs | `FG420_Channel_Config.ctl[]` |
| Device Errors | error cluster[] |
| Status | `Status.ctl` |
| TestError | `TestError.ctl` |
| error out | error cluster |

内部ではVISA References[]もindex対応で保持する。

## 3. 前提条件・異常条件

| Code | 条件 |
|---:|---|
| -710120 | Enabled DeviceのVISA Resource重複 |
| -710121 | Enabled DeviceでCh1／Ch2が両方Disabled |
| -710122 | Device Configs空、またはEnabled Deviceが0台 |

- Disabled Device：初期State、入力Ch Config、No Errorを結果へ追加。
- Prepare途中error：Configure／ONをスキップ。
- Ch設定途中error：ONをスキップ。
- Output ON後error：Original Errorを保存しOFF／Closeを継続。
- Cleanup error：OriginalがあればOriginalを優先する。

## 4. 処理アルゴリズム

```text
Original Error = error in

Precheck For Loop:
    Enabled Device数を数える
    Enabled DeviceのCh1 OR Ch2 Enabledを確認する
    VISA Resource重複を確認する
    最初のValidation Errorを保持する

Main For Loop（1反復=1台）:
    Disabled Deviceなら結果だけ追加
    Precheck errorまたはStop On First Errorによる中止なら機器操作をスキップ
    それ以外はPrepare Device
    Ch1 Configure
    Ch2 Configure
    条件を満たすCh1 / Ch2をOutput ON
    1ch以上ONならWait
    Original Device Errorを保存
    cleanup wireでCh1 OFF
    cleanup wireでCh2 OFF
    cleanup wireでClose
    Original ErrorとCleanup ErrorをMerge
    Current結果を各配列へ追加

Cleanup For Loop:
    全indexを再走査する
    Initialized=True AND Closed=Falseだけ再Cleanup
    Ch1 OFF、Ch2 OFF、Closeを個別に試行する
    Original Errorを第1入力、Cleanup Errorを第2入力としてMergeする

最初の全体errorからStatus / TestErrorを生成する
```

## 5. LabVIEW構造の選定理由

- Precheck For Loop：機器操作前の全入力検証。
- Main For Loop：1反復1台。
- Flat Sequence Structure：ON→Wait→OFF→Close順を固定。
- Cleanup For Loop：Main Loopのerror経路と独立して全機器を再走査。
- 配列Shift Register：VISA、State、Applied Ch1／Ch2、Device Errorをindex順に蓄積。
- First Error Shift Register：全体最初のerror保持。
- Abort New Devices? Shift Register：Stop On First Error状態保持。
- Clear Errors＋Merge Errors：Cleanupを止めずOriginal Errorを優先。

Main Loop Shift Registerを上から次の順で追加する。

1. VISA References[]
2. Device States[]
3. Applied Ch1 Configs[]
4. Applied Ch2 Configs[]
5. Device Errors[]
6. First Error
7. Abort New Devices?

## 6. フロントパネル入出力

`10_FG420\PoC_FG420_Multi_Device.vi`として保存する。

Device Config配列、U32 Duration、2 Boolean、error inを左へ配置する。State配列、Applied Ch1／Ch2配列、error配列、Status、TestError、error outを右へ配置する。12端子以上のコネクタペインへ割り当てる。

## 7. 配置する関数およびSubVI

- For Loop ×3
- Flat Sequence Structure（3フレーム）
- Case Structure
- Shift Register
- Unbundle By Name／Bundle By Name
- Build Array（Concatenate Inputs有効）
- Search 1D Array
- Array Size
- Clear Errors
- Merge Errors
- Wait (ms)
- `FG420_Prepare_Device.vi`
- `FG420_Configure_Channel_Safe.vi`×2
- `FG420_Output.vi`
- `FG420_Close.vi`
- `Error_To_TestStatus.vi`

## 8. 配線順

### 8.1 Precheck For Loop

1. Device ConfigsをFor Loopへ接続し自動指標付けを有効にする。Nは未配線。
2. Seen VISA Resources、Enabled Count、Validation ErrorのShift Registerを追加する。
3. 左初期値はVISA空配列、U32`0`、error in。
4. Disabled Deviceは3値をそのまま右内側へ接続する。
5. Enabled DeviceはCountへU32`1`を加算する。
6. Ch1 Config.Enabled?とCh2 Config.Enabled?をORする。
7. FalseでFor LoopのiとLogical Nameから-710121を作りValidation ErrorへMergeする。
8. Seen VISAとCurrent VISA ResourceをSearch 1D Arrayへ接続する。
9. index>=I32`0`なら重複として-710120を作る。
10. 非重複ならBuild ArrayでSeen VISA末尾へCurrent VISAを追加する。
11. Loop後、Enabled Count=0なら-710122をValidation ErrorへMergeする。
12. 結果をPrecheck Errorとする。

### 8.2 Main For Loop入力とShift Register

13. Device ConfigsをMain For Loopへ接続し自動指標付けを有効にする。Nは未配線。
14. Duration、Enable Output Phase?、Stop On First Error?、Precheck Errorは指標付けを無効にする。
15. 5配列Shift Registerへ各型の空配列を左初期値として接続する。
16. First Error左初期値へPrecheck Errorを接続する。
17. Abort左初期値へPrecheck Error.statusを接続する。
18. 左内側は前反復結果、右内側はCurrent追加後、右外側は全反復結果である。

### 8.3 Disabled／Abortバイパス

19. NOT Device Enabled?、`Abort AND Stop On First Error?`、Precheck Error.statusをORしBypass Device?を作る。
20. True CaseでDisabled Deviceの場合、Current VISA=無効VISA、Current State=初期State、Applied Ch1／Ch2=入力Config、Current Error=No Error。
21. Precheck／Abortの場合、Current Error=First Error左内側とする。
22. Prepare、Configure、Output、Wait、CloseをTrue Caseへ配置しない。
23. True／False両CaseでCurrent VISA、State、Applied Ch1、Applied Ch2、Device Errorの5トンネルを配線する。

### 8.4 Prepare

24. Current Device Config→Prepare Device Config。
25. No Error定数→Prepare error in。別機器のFirst Errorを接続しない。
26. VISA、State、error outを次段へ接続する。

### 8.5 Ch1 Configure

27. Prepare VISA→Ch1 Configure VISA in。
28. Ch1 Config→Channel Config。
29. Prepare error→error in。
30. Configure Applied Amp／Offsetを、入力Ch1 Configを基準clusterとするBundle By NameのRequested Amp／Offsetへ接続する。
31. Ch1 Enabled=Falseは元Ch1 ConfigをApplied Ch1結果とする。
32. Ch1 Enabled AND NOT Configure error.statusをCh1 Configured?としてStateへBundle By Name更新する。

### 8.6 Ch2 Configure

33. Ch1 Configure VISA／error→Ch2 Configure VISA／error in。
34. Ch2 Config→Channel Config。
35. Applied Amp／Offsetを入力Ch2 ConfigへBundle By Name更新する。
36. Ch2 Enabled=Falseは元Configを結果とする。
37. Ch2 Enabled AND NOT error.statusをCh2 Configured?としてStateへ更新する。

### 8.7 Flat Sequence Frame 0：Output ON

38. Enable Output Phase?、Ch1 Enabled?、Ch1 Output On?、NOT Current error.statusをANDする。
39. TrueでFG420_OutputへCurrent VISA、Ch1 Channel、Boolean`True`、Current errorを接続する。
40. ON成功時だけState.Ch1 Output On?をTrueへ更新する。
41. Ch1結果のVISA／error／StateをCh2 ON Caseへ渡す。
42. Ch2について同じ4条件をANDし、TrueでCh2をOutput ONする。
43. ON成功時だけState.Ch2 Output On?をTrueへ更新する。

### 8.8 Frame 1：Wait

44. StateのCh1 Output On?とCh2 Output On?をORする。
45. Any Output On? AND NOT Current error.statusをWait Required?とする。
46. True CaseでOutput Duration ms→Wait (ms)へ接続する。
47. VISA、error、StateはTrue／False両Caseで素通りする。
48. Frame 1 errorをOriginal Device Errorとして分岐保存する。

### 8.9 Frame 2：通常Cleanup

49. Original Device ErrorをClear ErrorsしCh1 OFF用errorを作る。
50. Ch1 Enabled=TrueならFG420_OutputへVISA、Ch1 Channel、False、cleanup errorを接続する。
51. Ch1 OFF errorをNo Error accumulatorへMergeする。
52. accumulatorをClear ErrorsしてCh2 OFFを試行する。
53. Ch2 OFF errorをaccumulatorへMergeする。
54. accumulatorをClear ErrorsしてFG420_Closeを試行する。
55. Close errorをaccumulatorへMergeしCleanup Error Finalを作る。
56. Original Device Error→Merge Errors第1入力、Cleanup Error Final→第2入力。
57. OFF成功時は各Output On?をFalse、Close成功時はClosed?をTrueへState更新する。

### 8.10 Main Loop結果蓄積

58. 5個のCurrent単一要素を各左内側配列とBuild Arrayで連結し、右内側へ接続する。
59. First Error左内側→Merge Errors第1入力、Current Device Error→第2入力、結果→右内側。
60. `Stop On First Error? AND Current Device Error.status`をAbort左内側とORし右内側へ接続する。

### 8.11 Cleanup For Loop

61. Main LoopのVISA[]、State[]、Device Errors[]とDevice Configs[]をCleanup Loopへ接続し、4トンネルの自動指標付けを有効にする。
62. Loop内では4つとも単一要素となる。Nは未配線。
63. Final First Error Shift Register左初期値へMain Loop First Errorを接続する。
64. `Initialized? AND NOT Closed?`をNeeds Cleanup? selectorへ接続する。
65. False CaseはCurrent State／Current Errorを出力する。
66. True CaseはCurrent ErrorをOriginal Errorとして保存する。
67. Clear Errorsした別wireでCh1 OFF、Ch2 OFF、Closeを個別に試行する。
68. 各Cleanup errorをaccumulatorへMergeし、次操作前にClear Errorsする。
69. Original Error→最終Merge第1入力、Cleanup Error→第2入力。
70. 更新StateとMerged Device Errorの出力トンネルで自動指標付けを有効にする。
71. Final First ErrorとCurrent Merged ErrorをMergeしShift Register右内側へ接続する。

### 8.12 最終出力

72. Cleanup State配列→Device States。
73. Main Applied Ch1／Ch2配列→各表示器。
74. Cleanup Error配列→Device Errors。
75. Final First Error→Error_To_TestStatus、Device Name=`FG420`。
76. Status、TestError、error outを表示器へ接続する。

## 9. 単体テスト

- 1台有効、Ch1のみ。
- 1台有効、Ch2のみ。
- 1台、2ch有効。
- 複数台有効。
- Disabled Deviceを含む配列。
- 空配列／Enabled 0台。
- 両ch Disabled。
- VISA重複。
- Prepare Init失敗。
- PrepareのInit成功後エラー。
- Ch設定途中error。
- Reject／Clamp。
- Output ON後error。
- Ch1 OFF error。
- Close error。
- Original error＋Cleanup error。
- Stop On First Error=True。
- Enable Output Phase=False。
- 既存error in。

---

## A1A.9 PoCフロントパネル設定例

```text
Device Configs[0]
  Logical Name = FG420_A
  VISA Resource = USB0::...A...::INSTR
  Ch1: Enabled=True, Frequency=1000 Hz, Amp=2 Vpp, Offset=0 V, Limit=3 V
  Ch2: Enabled=True, Frequency=2000 Hz, Amp=1 Vpp, Offset=1 V, Limit=3 V

Device Configs[1]
  Logical Name = FG420_B
  VISA Resource = USB0::...B...::INSTR
  Ch1: Enabled=True, Frequency=500 Hz, Amp=4 Vpp, Offset=0 V, Limit=2.5 V, Mode=Clamp
  Ch2: Enabled=False
```

---

## A1A.10 実装順

```text
STEP 1  typedef
STEP 2  薄いラッパ
STEP 3  FG420_Apply_Output_Limit.vi
STEP 4  FG420_Prepare_Device.vi
STEP 5  FG420_Configure_Channel_Safe.vi
STEP 6  PoC_FG420_Multi_Device.vi
STEP 7  1台1ch → 1台2ch → 複数台の順で実機確認
STEP 8  必要時のみ外部同期拡張
```

---

## A1A.11 完了条件

- [ ] 本ファイルだけでFG420拡張VIの作成順を追える。
- [ ] `FG420_Apply_Output_Limit.vi`の全入力、全出力、Reject／Clamp Caseを再現できる。
- [ ] `FG420_Configure_Channel_Safe.vi`のアルゴリズムが本章内で一意である。
- [ ] Ch1／Ch2を`INDependent`＋`NONE`で個別設定できる。
- [ ] Limit error時にFunction以降を呼ばない。
- [ ] Device Config配列の自動指標付けとLoop内外の型を説明できる。
- [ ] Main Loopの7 Shift Registerを再現できる。
- [ ] Disabled Deviceでも結果配列indexが維持される。
- [ ] 一部機器失敗時も全機器Cleanupを実行する。
- [ ] Original ErrorをCleanup Errorより優先する。
- [ ] 全Initialized機器でCloseを試行する。
- [ ] 正常、境界、Reject、Clamp、1ch、2ch、複数台、途中error、Cleanup error、既存errorを試験する。

---

## A1A.12 00A／00B／00C自己レビュー

- [x] FG420拡張の正本を本ファイル1つへ統合した。
- [x] 4つの主要VIすべてに0～9の節を設けた。
- [x] フロントパネル端子を配線順へ登場させた。
- [x] Case Structureのselectorと全出力を記載した。
- [x] For Loopの自動指標付けと配列／単一clusterの型変化を記載した。
- [x] Shift Registerの左初期値、反復中の更新、右出力を記載した。
- [x] Original Error、Cleanup Error、Clear Errors、Merge Errorsの接続順を記載した。
- [x] A1A.6のアルゴリズム表現を旧A1A正本へ統一した。
- [x] VI名、typedef、処理順、設計レイヤを変更していない。
- [x] ベンダーVIの端子は対象PCでCtrl+H照合する方針を維持した。
