# 付録 A1A. FG420 複数台・2ch・出力リミット対応 PoC 実装手順（統合正本）

**最終整理日：2026-07-31**

> 本ファイルをFG420拡張実装の唯一の正本とする。旧`A1A_04`～`A1A_08`の分冊内容は本章へ統合し、分冊は削除する。
>
> 横河ドライバVIの端子、Query／Set動作および制限値は`IMFG410-63JA`と対象PCの実VIで照合し、証跡は[00C](./00C_一次資料とバージョン基準.md)に従う。
>
> LabVIEW画面を再現できる記述粒度は[00A](./00A_LabVIEW実装資料の記述ルール.md)、機能要求をデータモデル・アルゴリズム・LabVIEW構造へ変換する規則は[00B](./00B_LabVIEW学習型VI設計ルール.md)を正とする。

---

## A1A.0 本章の位置づけ

[A1_付録_FG420基盤単体試験自動化.md](./A1_付録_FG420基盤単体試験自動化.md)に記載した1台・基本通信PoCは実機通信確認済みである。

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

本章では次を追加する。

1. 設定した絶対電圧リミットを超える条件をFG420へ送信しない。
2. 複数台のFG420を接続し、機器ごとに異なる条件を設定する。
3. FG420のCh1／Ch2を独立して設定する。

横河提供の`YKFG400 *.vi`は変更しない。自作VIは`10_FG420`配下へ置き、薄いラッパVI、純粋ロジックVI、複合VI、PoC VIへ分ける。

---

## A1A.1 マニュアルと実VIから確定している仕様

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

`YKFG400 OUTP Load.vi`は1 Ω～10 kΩの数値負荷または`INFinity`を扱う。実VIの`Set Load`端子はU16表現の列挙型であり、少なくとも`Input`、`INFinity`、`MINimum`、`MAXimum`を持つ。`Read`端子だけがBooleanである。

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

本PoCではFG420だけを許可するため、`^YOKOGAWA,FG420,`へ一致するか検証する。

### A1A.1.5 複数台同期

本章の標準PoCは複数台を1つのVIから個別設定するが、VISAによる順次Output ONの時刻差を保証しない。厳密同期が必要な場合だけ外部基準周波数、共通外部トリガ、`ROSC Sour`、`TRIG Sour`、`TRIG`を別途実機確認する。

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

Enum typedef。既定値は`Reject`。

| 値 | 意味 |
|---|---|
| `Reject` | 超過時にエラーを返し設定を送らない |
| `Clamp` | オフセットを維持して振幅を縮小する |

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

`Channel`はBooleanへ変更しない。`Enabled?`は処理するかどうかを表すBoolean、`Channel`はCh1／Ch2の選択値であり責務が異なる。

`Channel`には、自作した見た目だけ同じEnumではなく、横河ドライバVIの`Ch`入力端子を右クリックして`作成 → 制御器`または`作成 → 定数`で生成した型を使用する。内部表現が同じU16でも別Enum型は破線になる場合がある。

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
7. ドライバ端子の実名と自作ラッパの公開端子名を区別する。

### A1A.4.2 追加ラッパ一覧

| 自作VI | 呼ぶドライバVI | 自作入力 | ドライバへの固定値・対応 | 自作出力 |
|---|---|---|---|---|
| `FG420_Set_ChanMode.vi` | `YKFG400 CHAN Mode.vi` | VISA、Channel Mode、error | `Read=False` | VISA、error |
| `FG420_Set_Coupling.vi` | `YKFG400 INST Coup.vi` | VISA、Couple、error | `Read=False` | VISA、error |
| `FG420_Get_ID.vi` | `YKFG400 IDN.vi` | VISA、error | なし | VISA、IDN String、error |
| `FG420_Set_PowerOn_Output.vi` | `YKFG400 OUTP Pon.vi` | VISA、Mode、error | `Read=False` | VISA、error |
| `FG420_Query_Ampl_Bound.vi` | `YKFG400 VOLT.vi` | VISA、Channel、Bound、error | `Channel→Ch`、`Bound→Set Amplitude`、`Units=VPP`、`Amplitude=0.0`、`Read=True` | `Query Amplitude→Bound Value Vpp` |
| `FG420_Query_Offset_Bound.vi` | `YKFG400 VOLT Offs.vi` | VISA、Channel、Bound、error | `Channel→Ch`、`Bound→Set Offset`、`Units=V`、`Offset=0.0`、`Read=True` | `Query Offset→Bound Value V` |
| `FG420_Read_System_Error.vi` | `YKFG400 SYST Err.vi` | VISA、error | Read動作 | 機器error queue |

### A1A.4.3 `FG420_Set_Load.vi`の実端子対応

`FG420_Channel_Config.ctl`はPoCで必要な数値負荷とHi-Zだけを公開するため、`Load Infinity?`をドライバの`Set Load`列挙型へ変換する。

```text
Load Infinity? = False → Set Load = Input
Load Infinity? = True  → Set Load = INFinity
```

内部配線は次で固定する。

| 自作ラッパ／固定値 | `YKFG400 OUTP Load.vi`実端子 |
|---|---|
| `VISA reference in` | `VISA Session` |
| `Channel` | `Ch` |
| Enum定数`OHM` | `Units` |
| `Load Ohm` | `Load` |
| `Load Infinity?`をselectorとするSelect出力 | `Set Load` |
| Boolean定数`False` | `Read` |
| `error in` | `Error IN` |
| `Copy VISA Session` | `VISA reference out` |
| `Error OUT` | `error out` |

SelectのFalse入力にはドライバ端子から作成した`Input`定数、True入力には同じ型の`INFinity`定数を接続する。`MINimum`と`MAXimum`は本PoCのChannel Configからは選択しない。将来公開する場合は`Load Infinity?`を廃止し、ドライバと同じ`Set Load` Enumをtypedefへ持たせる。

### A1A.4.4 ラッパ共通配線

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
  各設定端子 → driver実端子
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

`10_FG420\FG420_Apply_Output_Limit.vi`として保存する。左へ9入力、右へ6出力を配置する。全数値はDBL、Limit Modeはtypedef、errorは標準clusterとする。

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

1. `error in.status`を外側Case selectorへ接続する。TrueはDBL`0.0`×4、False、元errorを出力する。
2. `Output Limit Abs V > 0`を確認し、Falseで-710110を生成する。
3. Device Amp Min<=MaxとDevice Offset Min<=MaxをANDし、Falseで-710113を生成する。
4. Requested Amp>=0、Amp範囲内、Offset範囲内をANDし、Falseで-710114を生成する。
5. Half Amplitude、Positive Peak、Negative Peak、Positive／Negative Exceeded、Limit Exceededを計算する。
6. Rejectで超過=TrueならApplied=0、要求Peak、Limited=True、-710112を返す。超過=Falseは要求値を返す。
7. Clampで超過=Falseは要求値を返す。
8. Clampで`abs(Requested Offset)>Limit`ならApplied=0、要求Peak、Limited=True、-710111を返す。
9. それ以外はAllowed Amplitudeを算出し、要求Amp、Allowed Amp、Device Amp Maxの最小値をApplied Ampとする。
10. Clamp後Peakを再計算し、範囲内ならApplied値、要求Peak、Limited=True、元errorを返す。範囲外なら-710113を返す。

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

本VIはOutput ON、Wait、Close、複数台反復を担当しない。`Channel Config.Output On?`はPoCで使用し、本VIでは未使用とする。

## 1. 入力データの実体

| 端子 | 型 |
|---|---|
| VISA reference in | VISA session |
| Channel Config | `FG420_Channel_Config.ctl` |
| error in | error cluster |

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

`10_FG420\FG420_Configure_Channel_Safe.vi`として保存する。左にVISA reference in、Channel Config、error in。右にVISA reference out、4 DBL、Limited?、Status、TestError、error outを配置する。

## 7. 配置する関数およびSubVI

- Unbundle By Name：Channel Config全11フィールド、error status、Limit error status
- Case Structure：error、Enabled、Limit error
- Select：Load Infinity?からSet Load Enumを作る場合
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

11. `VISA reference in`→`FG420_Output.vi / VISA reference in`。
12. `Channel Config.Channel`→`FG420_Output.vi / Channel`。
13. Boolean定数`False`→`FG420_Output.vi / Output On?`入力端子。
14. `error in`→`FG420_Output.vi / error in`。
15. VISA outとerror outを次段へ接続する。

`Output On?`は`FG420_Output.vi`の入力端子であり、本VIの出力表示器ではない。Falseを入力することで設定前の強制Output OFFを行う。

### 8.4 Load

16. Output OFF VISA out→`FG420_Set_Load.vi / VISA reference in`。
17. `Channel Config.Channel`→`FG420_Set_Load.vi / Channel`。
18. `Channel Config.Load Infinity?`→`FG420_Set_Load.vi / Load Infinity?`。
19. `Channel Config.Load Ohm`→`FG420_Set_Load.vi / Load Ohm`。
20. Output OFF error out→Set Load error in。

`FG420_Set_Load.vi`内部では、`Load Infinity?`をSelectのselectorへ接続し、False=`Input`、True=`INFinity`を選択して横河ドライバのU16 Enum端子`Set Load`へ接続する。Boolean定数Falseはドライバの`Read`へ接続する。`Load Infinity?`を`Read`へ接続してはならない。

### 8.5 Amplitude Min／Max

この節でChannel Configから使用する値は`Channel`だけである。Minimum／Maximumはクラスタ値ではなくQuery Wrapperへ接続するEnum定数である。

21. Set Load VISA out→1個目`FG420_Query_Ampl_Bound.vi / VISA reference in`。
22. `Channel Config.Channel`→1個目`Channel`、Bound Enum`Minimum`→`Bound`、Set Load error→`error in`。
23. 1個目`Bound Value Vpp`を`Device Amplitude Min Vpp`ワイヤとして後段Limit VIへ持つ。
24. 1個目VISA／error out→2個目Query Ampl VISA／error in。
25. `Channel Config.Channel`→2個目`Channel`、Bound Enum`Maximum`→`Bound`。
26. 2個目`Bound Value Vpp`を`Device Amplitude Max Vpp`ワイヤとして後段Limit VIへ持つ。

`FG420_Query_Ampl_Bound.vi`内部の実端子対応は次である。

```text
Channel          → YKFG400 VOLT.vi / Ch
Bound            → YKFG400 VOLT.vi / Set Amplitude
VPP Enum定数     → Units
DBL 0.0定数      → Amplitude
Boolean True定数 → Read
Query Amplitude  → Bound Value Vpp
```

### 8.6 Offset Min／Max

27. 2個目Query Ampl VISA／error out→1個目`FG420_Query_Offset_Bound.vi` VISA／error in。
28. `Channel Config.Channel`→1個目`Channel`、Bound Enum`Minimum`→`Bound`。
29. 1個目`Bound Value V`を`Device Offset Min V`として後段へ持つ。
30. 1個目Query Offset VISA／error out→2個目Query Offset VISA／error in。
31. `Channel Config.Channel`→2個目`Channel`、Bound Enum`Maximum`→`Bound`。
32. 2個目`Bound Value V`を`Device Offset Max V`として後段へ持つ。

`FG420_Query_Offset_Bound.vi`内部は`Bound→YKFG400 VOLT Offs.vi / Set Offset`、`Units=V`、`Offset=0.0`、`Read=True`、`Query Offset→Bound Value V`とする。

### 8.7 Limit VI

33. `Requested Amplitude Vpp`、`Requested Offset V`、4本のDevice Min／Max、`Output Limit Abs V`、`Limit Mode`をLimit VIの同名入力へ接続する。
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
- 数値LoadとINFinity。
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

- error in=True：Wrapper未実行、空のVISA resource name定数、空IDN、初期State、元error。
- Init失敗：Initialized?=False、Close不要。
- Init成功後失敗：Initialized?=Trueを保持、PoC CleanupでClose。
- IDNが`^YOKOGAWA,FG420,`へ一致しない：-710130。
- ChanMode失敗：Independent Mode?=False。
- Coupling失敗：Independent Mode?=True、Coupling Disabled?=False。

「空のVISA resource name定数」は、`VISA reference out`トンネルを右クリックして`作成 → 定数`で作り、機器アドレスを選択しない空のまま使用する。実在するUSB／GPIB Resourceを入力しない。

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
    Get ID errorが無ければID Check?を考慮してFG420形式を検証
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

`10_FG420\FG420_Prepare_Device.vi`として保存する。左にDevice Config、error in。右にVISA reference out、IDN、Device State、Status、TestError、error outを配置する。

## 7. 配置する関数およびSubVI

- Unbundle By Name
- Bundle By Name ×4
- Case Structure ×3
- Match Regular Expression
- String Length
- Greater?、Not Equal?、Not、AND、OR
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
4. True Case：空のVISA resource name定数、空String、初期State、元errorを4トンネルへ接続する。
5. False Case：VISA Resource、ID Check?、Reset?、error inをFG420_Initへ接続する。
6. Init error.statusをNotし、Initial Stateを基準clusterとするBundle By NameのInitialized?へ接続する。
7. Init VISA／error out→FG420_Get_ID VISA／error in。
8. IDN StringをString Lengthへ接続し、長さ>0を作る。
9. Get ID error.statusをNotし、長さ>0とANDしてID Read?を作る。
10. State After Initを基準clusterとするBundle By NameへID Read?とIDNを接続する。
11. Get ID error.status→Get ID Error Case selector。
12. True Case：Get ID error、現在VISA、IDN、Stateをそのまま終端へ通す。後続設定Wrapperを呼ばない。
13. False Case：IDNを`Match Regular Expression / input string`、文字列定数`^YOKOGAWA,FG420,`を`regular expression`、I32`0`を`offset`へ接続する。
14. `offset past match`とI32`-1`をNot Equal?へ接続し、`Pattern Matched?` Booleanを作る。Match Regular ExpressionからBooleanは直接出ない。
15. `ID Check?`をNotし、`Pattern Matched?`とORして`IDN Valid? = NOT(ID Check?) OR Pattern Matched?`を作る。
16. `IDN Valid?`をIDN Valid Case selectorへ接続する。
17. True Case：Get ID VISA／errorをSet PowerOn Outputへ通す。
18. False Case：次のFormat Stringを`Format Into String`へ設定する。

```text
FG420_Prepare_Device.vi: IDN validation failed. Logical Name="%s", IDN="%s", expected pattern="^YOKOGAWA,FG420,"
```

19. Format引数1へLogical Name、引数2へIDNを接続する。
20. Get ID error outを基準clusterとしてBundle By Nameへ接続し、status=True、code=I32`-710130`、source=Format出力を設定する。元の外側`error in`ではなく、直近のGet ID error outを基準にする。
21. ID検証後VISA／error→Set PowerOn Output。Mode Enum`OFF`を接続する。
22. Set PowerOn VISA／error→Set ChanMode。Enum`INDependent`を接続する。
23. ChanMode error.statusをNotし、State After IDを基準clusterとしてIndependent Mode?へ接続する。
24. ChanMode VISA／error→Set Coupling。Enum`NONE`を接続する。
25. Coupling error.statusをNotし、State After ChanModeを基準clusterとしてCoupling Disabled?へ接続する。
26. Coupling VISA、IDN、最終State、Coupling errorを外側Caseトンネルへ接続する。
27. Final Error→Error_To_TestStatus、Device Name=`FG420`。

### Close要否

| 失敗位置 | Initialized? | Close |
|---|---|---|
| error in／Init失敗 | False | 不要 |
| Get ID以降 | True | PoC Cleanupで必要 |
| 正常 | True | PoC終了時に必要 |

## 9. 単体テスト

- 正常FG420。
- ID Check=Falseで形式不一致を許可する。
- ID Check=TrueかつFG410 IDNで-710130。
- Init途中error。
- Get ID途中error。
- 空IDN。
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

| Code | 条件 | source文字列 |
|---:|---|---|
| -710120 | Enabled DeviceのVISA Resource重複 | `PoC_FG420_Multi_Device.vi: Duplicate VISA Resource detected. Current Index=%d, Previous Index=%d, Logical Name="%s", VISA Resource="%s"` |
| -710121 | Enabled DeviceでCh1／Ch2が両方Disabled | `PoC_FG420_Multi_Device.vi: Enabled device has no enabled channels. Index=%d, Logical Name="%s"` |
| -710122 | Device Configs空、またはEnabled Deviceが0台 | `PoC_FG420_Multi_Device.vi: No enabled devices were found. Device Config Count=%d` |

- Disabled Device：初期State、入力Ch Config、No Errorを結果へ追加。
- Prepare途中error：Configure／ONをスキップ。
- Ch設定途中error：ONをスキップ。
- Output ON後error：Original Errorを保存しOFF／Closeを継続。
- Cleanup error：OriginalがあればOriginalを優先する。

## 4. 処理アルゴリズム

```text
Original Error = error in

Precheck For Loop:
    前反復までに見たVISA Resource配列を保持する
    Enabled Device数を保持する
    最初のValidation Errorを保持する
    Disabled Deviceなら3値を変更しない
    Enabled DeviceならCountを1増やす
    Ch1 OR Ch2 Enabledを確認する
    VISA Resource重複を確認する

Main For Loop（1反復=1台）:
    5種類の結果配列をShift Registerで蓄積する
    First Errorを保持する
    Abort New Devices?を保持する
    Disabled Deviceなら結果だけ追加
    Precheck errorまたはStop On First Errorによる中止なら機器操作をスキップ
    それ以外はPrepare、Ch1／Ch2 Configure、Output ON、Wait、Cleanupを行う
    Current結果を5配列へ追加する

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
- 5配列Shift Register：VISA、State、Applied Ch1、Applied Ch2、Device Errorをindex順に蓄積。
- First Error Shift Register：全体最初のerror保持。
- Abort New Devices? Shift Register：Precheck errorまたはStop On First Error後の新規機器操作中止状態を保持。
- Clear Errors＋Merge Errors：Cleanupを止めずOriginal Errorを優先。

Main Loop Shift Registerを上から次の順で追加する。合計7本である。

1. VISA References[]
2. Device States[]
3. Applied Ch1 Configs[]
4. Applied Ch2 Configs[]
5. Device Errors[]
6. First Error
7. Abort New Devices?

`Output Duration ms`、`Enable Output Phase?`、`Stop On First Error?`、`Precheck Error`は5配列ではない。これらは全反復で同じ値を使う、指標付け無効の通常入力トンネルである。

## 6. フロントパネル入出力

`10_FG420\PoC_FG420_Multi_Device.vi`として保存する。Device Config配列、U32 Duration、2 Boolean、error inを左へ配置する。State配列、Applied Ch1／Ch2配列、error配列、Status、TestError、error outを右へ配置する。

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

### 8.1 Precheck For Loopの入力と3本のShift Register

1. Device ConfigsをPrecheck For Loopへ接続し、自動指標付けを有効にする。Nは未配線とする。
2. For Loop枠を右クリックしてShift Registerを3本追加し、上から`Seen VISA Resources[]`、`Enabled Count`、`Validation Error`として扱う。
3. 左外側初期値は次とする。

```text
Seen VISA Resources[] = 空のVISA resource name一次元配列
Enabled Count         = U32 0
Validation Error      = error in
```

空VISA配列はArray Constant内へVISA resource name定数を入れ、要素を持たない空配列として作る。単体VISA定数を接続しない。

4. 左内側端子は前反復までの値、右内側端子は今回反復後の値、右外側端子はLoop全反復終了後の値である。
5. Current Device Configの`Enabled?`をselectorとするCase Structureを配置する。

### 8.2 Enabled=False Case

6. Disabled Deviceは検査対象に含めないため、次の3本を左内側から右内側へ直結する。

```text
Seen VISA Resources left → right
Enabled Count left       → right
Validation Error left    → right
```

7. False CaseにはAdd、OR、Search 1D Array、Build Array、エラー生成処理を配置しない。

### 8.3 Enabled=True CaseのCountとChannel検証

8. Enabled Count左内側とU32定数`1`をAddへ接続し、出力をEnabled Count右内側へ接続する。
9. Ch1 ConfigとCh2 Configを各Unbundle By Nameへ接続し、各`Enabled?`をORする。OR出力を`Any Channel Enabled?`とする。
10. `Any Channel Enabled?`を内側Case Structureのselectorへ接続する。
11. True Caseは新しいChannel errorを作らず、現在のValidation Errorを次のVISA重複検証へ通す。
12. False Caseは次のFormat Stringを使用する。

```text
PoC_FG420_Multi_Device.vi: Enabled device has no enabled channels. Index=%d, Logical Name="%s"
```

13. Format引数1へFor Loopの`i`、引数2へLogical Nameを接続する。
14. Validation Errorを基準clusterとしてBundle By Nameでstatus=True、code=I32`-710121`、source=Format出力のローカルerrorを作る。
15. Validation Error左内側をMerge Errors第1入力、ローカルerrorを第2入力へ接続し、既存の最初のerrorを優先する。

### 8.4 VISA Resource重複検証

16. Seen VISA Resources左内側→`Search 1D Array / array`、Current DeviceのVISA Resource→`element`へ接続する。
17. Search出力indexとI32`0`をGreater Or Equal?へ接続し、`Duplicate?` Booleanを作る。
18. Duplicate?をCase selectorへ接続する。
19. True Caseは次のFormat Stringを使用する。

```text
PoC_FG420_Multi_Device.vi: Duplicate VISA Resource detected. Current Index=%d, Previous Index=%d, Logical Name="%s", VISA Resource="%s"
```

20. 引数1=For Loopの`i`、引数2=Search 1D Arrayのindex、引数3=Logical Name、引数4=VISA Resourceとする。
21. Bundle By Nameで-710120を作り、直前までのValidation ErrorをMerge Errors第1入力、ローカルerrorを第2入力へ接続する。
22. 重複TrueではSeen VISA Resourcesを変更せず右内側へ通す。
23. False CaseではBuild ArrayでSeen VISA Resources末尾へCurrent VISA Resourceを追加し、右内側へ接続する。

### 8.5 Precheck Loop後のEnabled 0台検証

24. Device Configs配列はPrecheck For Loopへ入る前に分岐し、Loop外のArray Sizeへ接続する。Array Size出力を`Device Config Count`として保持する。
25. Loop右外側のEnabled CountとU32`0`をEqual?へ接続し、`Enabled Count = 0?` Case selectorへ接続する。
26. False CaseはValidation ErrorをそのままPrecheck Errorへ通す。
27. True Caseは次のFormat Stringを使用する。

```text
PoC_FG420_Multi_Device.vi: No enabled devices were found. Device Config Count=%d
```

28. Device Config CountをFormat引数1へ接続し、Bundle By Nameで-710122を作る。
29. Loop後Validation ErrorをMerge Errors第1入力、-710122ローカルerrorを第2入力へ接続し、結果をPrecheck Errorとする。

### 8.6 Main For Loop入力

30. Device ConfigsをMain For Loopへ接続し自動指標付けを有効にする。Nは未配線とする。
31. `Output Duration ms`、`Enable Output Phase?`、`Stop On First Error?`、`Precheck Error`は通常入力トンネルへ接続し、右クリックして指標付けを無効にする。
32. Loop内ではDevice Configだけが単一clusterとなり、他4入力は全反復で同じ単一値となる。

### 8.7 Main For Loopの7本のShift Register

33. 次の5種類は結果をindex順に蓄積する配列Shift Registerである。

| Shift Register | 左外側初期値 | 各反復で追加するCurrent値 |
|---|---|---|
| VISA References[] | 空VISA reference配列 | Current VISA |
| Device States[] | 空`FG420_Device_State.ctl`配列 | Current State |
| Applied Ch1 Configs[] | 空`FG420_Channel_Config.ctl`配列 | Current Applied Ch1 Config |
| Applied Ch2 Configs[] | 空`FG420_Channel_Config.ctl`配列 | Current Applied Ch2 Config |
| Device Errors[] | 空error cluster配列 | Current Device Error |

34. 各反復末尾で左内側配列とCurrent単一値をBuild Arrayへ接続し、出力を右内側へ接続する。
35. 6本目の`First Error`はerror cluster 1個を保持するShift Registerであり、左外側初期値へPrecheck Errorを接続する。
36. 7本目の`Abort New Devices?`はBoolean Shift Registerであり、左外側初期値へ`Precheck Error.status`を接続する。
37. Abortの更新式は次である。

```text
Abort Next
= Abort Previous
  OR (Stop On First Error? AND Current Device Error.status)
```

38. `Abort New Devices?`はフロントパネル入力ではなく、Main Loop内部で新しく作る状態Booleanである。Trueになった後の新しいEnabled Deviceは機器操作を開始しないが、結果配列のindex維持のためCurrent結果は追加する。

### 8.8 Disabled／Abortバイパス

39. `NOT Device Enabled?`、`Abort New Devices?`、`Precheck Error.status`からBypass Device?を作る。AbortはすでにStop On First Error条件を反映しているため、再度`Abort AND Stop On First Error?`としない。
40. Disabled Deviceの場合、Current VISA=空のVISA resource name定数、Current State=初期State、Applied Ch1／Ch2=入力Config、Current Error=No Errorとする。
41. Precheck／Abortの場合は機器操作を行わず、Current Error=First Error左内側とする。
42. Prepare、Configure、Output、Wait、CloseをBypass=True Caseへ配置しない。
43. True／False両CaseでCurrent VISA、State、Applied Ch1、Applied Ch2、Device Errorの5トンネルを配線する。

### 8.9 Prepare、Configure、Output、Wait、通常Cleanup

44. Bypass=False CaseでCurrent Device Config→Prepare Device Config、No Error定数→Prepare error inとする。別機器のFirst ErrorをPrepareへ接続しない。
45. Prepare VISA／error→Ch1 Configure、Ch1 Configure VISA／error→Ch2 Configureを直列接続する。
46. Applied Amp／Offsetを各入力Channel ConfigへBundle By Name更新してApplied Ch1／Ch2結果を作る。
47. Enable Output Phase?、各Ch Enabled?、各Ch Output On?、NOT Current error.statusをANDし、条件成立時だけFG420_OutputへBoolean Trueを渡す。
48. 1ch以上ONならOutput Duration msだけWaitする。
49. Wait後errorをOriginal Device Errorとして保存する。
50. Original Device ErrorをClear Errorsしたcleanup wireでCh1 OFF、Ch2 OFF、Closeを個別に試行する。
51. 各Cleanup errorをaccumulatorへMergeし、次操作前にClear Errorsする。
52. Original Device Error→最終Merge Errors第1入力、Cleanup Error Final→第2入力とする。
53. OFF成功時は各Output On?をFalse、Close成功時はClosed?をTrueへState更新する。

### 8.10 Main Loop結果蓄積

54. 5個のCurrent単一要素を各配列Shift RegisterへBuild Arrayで追加する。
55. First Error左内側→Merge Errors第1入力、Current Device Error→第2入力、結果→First Error右内側とする。
56. Current Device Error.statusとStop On First Error?をANDし、Abort左内側とORしてAbort右内側へ接続する。

### 8.11 Cleanup For Loop

57. Main LoopのVISA[]、State[]、Device Errors[]とDevice Configs[]をCleanup Loopへ接続し、4トンネルの自動指標付けを有効にする。
58. `Initialized? AND NOT Closed?`をNeeds Cleanup? selectorへ接続する。
59. False CaseはCurrent State／Current Errorをそのまま出力する。
60. True CaseはCurrent ErrorをOriginal Errorとして保存し、Clear Errorsした別wireでCh1 OFF、Ch2 OFF、Closeを個別に試行する。
61. Original Error→最終Merge第1入力、Cleanup Error→第2入力とする。
62. 更新StateとMerged Device Errorの出力トンネルで自動指標付けを有効にする。
63. Final First ErrorとCurrent Merged ErrorをMergeし、最初の全体errorを維持する。

### 8.12 最終出力

64. Cleanup State配列→Device States。
65. Main Applied Ch1／Ch2配列→各表示器。
66. Cleanup Error配列→Device Errors。
67. Final First Error→Error_To_TestStatus、Device Name=`FG420`。
68. Status、TestError、error outを表示器へ接続する。

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
- [ ] Channel EnumとEnabled? Booleanの違いを説明できる。
- [ ] Set Load EnumとRead Booleanの違いを説明できる。
- [ ] Query Wrapperの公開端子と横河ドライバ実端子の対応を再現できる。
- [ ] Match Regular Expressionのoffset past matchからBoolean一致判定を作れる。
- [ ] Precheckの3 Shift Registerを再現できる。
- [ ] Main Loopの5配列＋First Error＋Abortの7 Shift Registerを再現できる。
- [ ] Disabled Deviceでも結果配列indexが維持される。
- [ ] 一部機器失敗時も全機器Cleanupを実行する。
- [ ] Original ErrorをCleanup Errorより優先する。
- [ ] 全Initialized機器でCloseを試行する。

---

## A1A.12 00A／00B／00C自己レビュー

- [x] FG420拡張の正本を本ファイル1つへ統合した。
- [x] 4つの主要VIすべてに0～9の節を設けた。
- [x] 横河ドライバ実端子と自作ラッパ公開端子を区別した。
- [x] Channel、Set Load、Read、Query端子の型と役割を明記した。
- [x] Match Regular Expressionの一致Boolean生成方法と-710130 source全文を記載した。
- [x] Precheckの3 Shift Registerの初期値、False／True Case、エラー文字列を記載した。
- [x] Main Loopの5配列、First Error、Abort New Devices?の役割と更新式を記載した。
- [x] For Loop外のArray Size、指標付けON／OFF、Loop内外の型変化を記載した。
- [x] Original Error、Cleanup Error、Clear Errors、Merge Errorsの接続順を記載した。
