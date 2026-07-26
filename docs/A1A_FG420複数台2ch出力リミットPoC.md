# 付録 A1A. FG420 複数台・2ch・出力リミット対応 PoC 実装手順

**最終整理日：2026-07-26**

> 横河ドライバVIの端子、Query／Set動作および制限値は`IMFG410-63JA`と対象PCの実VIで照合し、証跡は[00C](./00C_一次資料とバージョン基準.md)に従う。既決のtypedef、Wrapper、Service、PoC構成は変更しない。

## A1A.0 本章の位置づけ

本章は、[A1_付録_FG420基盤単体試験自動化.md](./A1_付録_FG420基盤単体試験自動化.md) の通信確認 PoC 完了後に実施する拡張実装を扱う。

既存 PoC では、1 台の FG420 に対して次の通信・出力フローが成立している。

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

1. 設定した電圧リミットを超える条件を FG420 へ送信しない。
2. 複数台の FG420 を接続し、機器ごとに異なる条件を設定できる。
3. FG420 の Ch1 / Ch2 を独立して設定できる。

本章の実装では、横河提供の `YKFG400 *.vi` を変更しない。自作 VI は `10_FG420` 配下に置き、ドライバ VI を1個だけ呼ぶ薄いラッパ VI、純粋ロジック VI、PoC オーケストレーション VI に分ける。

---

## A1A.1 マニュアルから確定している仕様

参照資料は `IMFG410-63JA FG410/FG420 LabVIEW ドライバ ユーザーズマニュアル` とする。

### A1A.1.1 VISA と error の接続

- 全ての操作 VI は標準 error in / error out を持つ。
- `Close` 以外の操作 VI は VISA session in と複製 VISA session out を持つ。
- 各操作 VI は VISA と error を直列接続して実行順序を確定する。
- ほとんどの設定 VI は `Ch(Ch1)` または `Ch?(Ch1)` 入力を持つ。

### A1A.1.2 2ch 独立設定

`YKFG400 CHAN Mode.vi` の `Channel Mode` を `INDependent` に設定すると、Ch1 と Ch2 を独立して設定できる。

`YKFG400 INST Coup.vi` の `Couple` は次の意味を持つ。

| 値 | 意味 |
|---|---|
| `ALL` | Ch1 に送った設定を Ch2 にも同時反映する |
| `NONE` | 同時設定を無効にし、Ch1 / Ch2 を個別設定する |

本 PoC では、個別設定を実現するため次を標準設定とする。

```text
CHAN Mode = INDependent
INST Coup  = NONE
```

### A1A.1.3 振幅・オフセット・負荷

`YKFG400 VOLT.vi` の振幅範囲は次のとおり。

| 負荷条件 | 振幅範囲 |
|---|---:|
| 開放 / Hi-Z | 0 ～ 20 Vp-p |
| 50 Ω | 0 ～ 10 Vp-p |

`YKFG400 VOLT Offs.vi` のオフセット範囲は次のとおり。

| 負荷条件 | オフセット範囲 |
|---|---:|
| 開放 / Hi-Z | -10 ～ +10 V |
| 50 Ω | -5 ～ +5 V |

`YKFG400 OUTP Load.vi` は負荷インピーダンスを設定する。数値指定は 1 Ω ～ 10 kΩ、`INFinity` で Hi-Z を設定する。

振幅とオフセットの設定可能範囲は負荷設定に依存するため、必ず次の順で呼ぶ。

```text
OUTP Load
  → 振幅・オフセットの設定可能範囲取得
  → 出力リミット判定
  → VOLT
  → VOLT Offs
```

### A1A.1.4 機器識別

`YKFG400 IDN.vi` は次の形式の ID 文字列を返す。

```text
YOKOGAWA,FG4xx,シリアル番号,ファームウェアバージョン
```

複数台 PoC では VISA リソース名だけでなく IDN のシリアル番号も記録し、設定対象の取り違えを防ぐ。

### A1A.1.5 複数台の厳密な同期

複数台へ VISA コマンドを順番に送る方式では、出力 ON の時刻は完全には一致しない。

- 「複数台を接続して同一 PoC から個別設定する」ことは本章の標準機能とする。
- 「複数台の出力開始エッジを厳密に一致させる」ことは別要件とする。
- 厳密同期が必要な場合は、`ROSC Sour=EXTernal` による外部基準周波数、共通外部トリガ、`TRIG` 系 VI を組み合わせて実機確認する。

---

## A1A.2 実装レイヤ

```text
PoC_FG420_Multi_Device.vi
  ├─ FG420_Prepare_Device.vi
  ├─ FG420_Configure_Channel_Safe.vi
  ├─ FG420_Output.vi
  ├─ FG420_Close.vi
  └─ Cleanup

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

### レイヤごとの責務

| レイヤ | 責務 |
|---|---|
| 薄いラッパ VI | 横河ドライバ VI を1個だけ呼び、VISA / error / Status / TestError を接続する |
| 純粋ロジック VI | 電圧ピーク計算、範囲判定、Clamp / Reject を行う。VISA を呼ばない |
| 複合公開 VI | 複数の薄いラッパを安全な順序で接続し、1イベントを完結する |
| PoC VI | 複数台・複数chの反復、状態管理、Wait、Cleanup、結果集計を行う |

---

## A1A.3 追加する typedef

### A1A.3.1 `FG420_Limit_Mode.ctl`

Enum typedef とする。

| 値 | 意味 |
|---|---|
| `Reject` | リミット超過時はエラーを返し、設定を FG420 へ送らない |
| `Clamp` | オフセットを維持し、振幅を安全値まで縮小する |

安全性を優先し、既定値は `Reject` とする。

### A1A.3.2 `FG420_Channel_Config.ctl`

Cluster typedef とする。

| フィールド | 型 | 初期値 | 意味 |
|---|---|---:|---|
| Enabled? | Boolean | False | このチャネルを設定対象にする |
| Channel | ドライバ Ch Enum | Ch1 | Ch1 / Ch2 |
| Function | ドライバ波形 Enum | Sin | 波形種別 |
| Frequency Hz | DBL | 1000 | 出力周波数 |
| Load Infinity? | Boolean | True | True の場合 Hi-Z |
| Load Ohm | DBL | 50 | 数値負荷を使う場合の値 |
| Requested Amplitude Vpp | DBL | 1.0 | 要求振幅 |
| Requested Offset V | DBL | 0.0 | 要求オフセット |
| Output Limit Abs V | DBL | 5.0 | 正負共通の絶対電圧リミット |
| Limit Mode | FG420_Limit_Mode.ctl | Reject | 超過時の動作 |
| Output On? | Boolean | False | 出力開始対象 |

### A1A.3.3 `FG420_Device_Config.ctl`

Cluster typedef とする。

| フィールド | 型 | 初期値 | 意味 |
|---|---|---:|---|
| Enabled? | Boolean | False | この機器を PoC 対象にする |
| Logical Name | String | FG420_01 | ログ表示用名称 |
| VISA Resource | VISA resource name | 空 | 機器固有 VISA リソース |
| ID Check? | Boolean | True | Initialize の ID 照合 |
| Reset? | Boolean | True | Initialize 時のリセット |
| Ch1 Config | FG420_Channel_Config.ctl | Channel=Ch1 | Ch1 条件 |
| Ch2 Config | FG420_Channel_Config.ctl | Channel=Ch2 | Ch2 条件 |

### A1A.3.4 `FG420_Device_State.ctl`

Cluster typedef とする。

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

---

## A1A.4 追加する薄いラッパ VI

全ラッパで次を共通とする。

1. VISA session in / out を直列配線する。
2. error in.status=True の場合は、設定系ドライバ VI を呼ばず安全出力を返す。
3. ドライバ error out を `Error_To_TestStatus.vi` へ接続する。
4. Device Name は `FG420` とする。
5. `Read=False` で無効になる Query 出力は、設定専用ラッパでは公開しない。
6. Cleanup 用の `Output OFF` と `Close` は、通常処理の error を Clear Errors した別ワイヤで実行し、Original Error を Merge Errors の先頭入力へ保持する。

### A1A.4.1 `FG420_Set_ChanMode.vi`

#### 0. 責務

FG420 を 2ch 独立モードへ設定する。

#### 1. 呼ぶドライバ VI

`YKFG400 CHAN Mode.vi`

#### 2. 入力

| 入力 | 型 |
|---|---|
| VISA reference in | VISA session |
| Channel Mode | ドライバ Enum |
| error in | error cluster |

#### 3. 内部固定値

```text
Read = False
```

PoC の標準入力は `INDependent` とする。

#### 4. 出力

VISA reference out、Status、TestError、error out。

#### 5. 単体テスト

- `INDependent` を設定してエラーなし。
- `Read=True` の一時確認版で `INDEPENDENT` が返る。
- 既存 error 時にドライバを実行しない。

### A1A.4.2 `FG420_Set_Coupling.vi`

#### 0. 責務

Ch1 設定を Ch2 へ自動反映するかを選択する。

#### 1. 呼ぶドライバ VI

`YKFG400 INST Coup.vi`

#### 2. 入力

VISA reference in、Couple Enum、error in。

#### 3. PoC 標準値

```text
Couple = NONE
Read   = False
```

Ch1 / Ch2 を個別設定する場合、必ず `NONE` を設定する。

#### 4. 単体テスト

- `NONE` 後に Ch1 の周波数を変更しても Ch2 が変化しない。
- `ALL` 後に Ch1 の設定が Ch2 へ反映される。
- PoC の通常経路では `NONE` を使用する。

### A1A.4.3 `FG420_Get_ID.vi`

#### 0. 責務

機器 ID とシリアル番号を取得し、複数台の論理名と実機を対応付ける。

#### 1. 呼ぶドライバ VI

`YKFG400 IDN.vi`

#### 2. 入出力

入力：VISA reference in、error in。

出力：VISA reference out、IDN String、Status、TestError、error out。

#### 3. 検証

- 文字列先頭が `YOKOGAWA,FG4` であること。
- 複数台の IDN が重複していないこと。
- 期待シリアル番号を条件に持つ場合は一致を検証する。

### A1A.4.4 `FG420_Set_PowerOn_Output.vi`

#### 0. 責務

電源投入時の出力状態を OFF に固定する。

#### 1. 呼ぶドライバ VI

`YKFG400 OUTP Pon.vi`

#### 2. 内部固定値

```text
Mode = OFF
Read = False
```

#### 3. 単体テスト

電源再投入後に Ch1 / Ch2 が自動で ON にならないことを実機確認する。

### A1A.4.5 `FG420_Query_Ampl_Bound.vi`

#### 0. 責務

現在の負荷・波形・チャネル条件に対する振幅の Minimum または Maximum を問い合わせる。

#### 1. 呼ぶドライバ VI

`YKFG400 VOLT.vi`

#### 2. 入力

VISA reference in、Channel、Bound Enum（Minimum / Maximum）、error in。

#### 3. 内部設定

```text
Units         = VPP
Set Amplitude = Bound 入力
Read          = True
Amplitude     = 0 DBL（問合せ時は設定値として使用しない）
```

#### 4. 出力

VISA reference out、Bound Value Vpp、Status、TestError、error out。

#### 5. 単体テスト

- Hi-Z と 50 Ω で Maximum が変化すること。
- Ch1 / Ch2 の各条件で問い合わせできること。
- Minimum <= Maximum を確認すること。

### A1A.4.6 `FG420_Query_Offset_Bound.vi`

`YKFG400 VOLT Offs.vi` を1回だけ呼び、Minimum または Maximum を問い合わせる。

内部設定は次のとおり。

```text
Units      = V
Set Offset = Bound 入力
Read       = True
Offset     = 0 DBL
```

出力は Bound Value V とする。

### A1A.4.7 `FG420_Read_System_Error.vi`

`YKFG400 SYST Err.vi` を1回呼び、FG420 のエラーキューを取得する。

設定後のデバッグおよび PoC の最終検証で使用する。通常ラッパの error cluster と機器内部エラーは別情報として記録する。

### A1A.4.8 同期拡張用ラッパ（任意）

厳密な複数台同期が必要な場合だけ次を追加する。

| 作成 VI | ドライバ VI | 責務 |
|---|---|---|
| `FG420_Set_Reference_Source.vi` | `YKFG400 ROSC Sour.vi` | Internal / External 基準周波数源を選ぶ |
| `FG420_Trigger.vi` | `YKFG400 TRIG.vi` | トリガボタン相当の動作を行う |
| `FG420_Set_Trigger_Source.vi` | `YKFG400 TRIG Sour.vi` | Internal / External 等のトリガ源を設定する |

VISA 経由で各台へ `TRIG.vi` を順番に呼ぶだけでは同時性を保証できない。厳密同期は共通外部トリガ配線を正式方式とする。

---

## A1A.5 出力リミット純粋処理 VI

### A1A.5.1 `FG420_Apply_Output_Limit.vi`

#### 0. 責務

要求振幅・オフセットから波形の正側ピークと負側ピークを計算し、設定した絶対電圧リミットを超える条件を FG420 へ送信しない。

本 VI は VISA やドライバ VI を呼ばない純粋処理 VI とする。

#### 1. 入力

| 入力 | 型 |
|---|---|
| Requested Amplitude Vpp | DBL |
| Requested Offset V | DBL |
| Output Limit Abs V | DBL |
| Limit Mode | FG420_Limit_Mode.ctl |
| Device Amplitude Min Vpp | DBL |
| Device Amplitude Max Vpp | DBL |
| Device Offset Min V | DBL |
| Device Offset Max V | DBL |
| error in | error cluster |

#### 2. 出力

| 出力 | 型 |
|---|---|
| Applied Amplitude Vpp | DBL |
| Applied Offset V | DBL |
| Positive Peak V | DBL |
| Negative Peak V | DBL |
| Limited? | Boolean |
| error out | error cluster |

#### 3. ピーク計算

振幅単位を Vp-p、オフセット単位を V に固定する。

```text
Positive Peak = Offset + Amplitude / 2
Negative Peak = Offset - Amplitude / 2
```

リミット条件は次のとおり。

```text
Positive Peak <=  Output Limit Abs V
Negative Peak >= -Output Limit Abs V
```

同値な簡易条件は次のとおり。

```text
abs(Offset) + Amplitude / 2 <= Output Limit Abs V
```

#### 4. 入力検証

次を全て検証する。

1. Requested Amplitude Vpp >= 0。
2. Output Limit Abs V > 0。
3. Device Amplitude Min <= Device Amplitude Max。
4. Device Offset Min <= Device Offset Max。
5. Requested Offset が Device Offset 範囲内。
6. Requested Amplitude が Device Amplitude 範囲内。

#### 5. Reject モード

リミット超過時はローカルエラーを作成し、Applied Amplitude / Offset は安全値 0 を返す。

```text
code   = -710112
source = FG420_Apply_Output_Limit.vi: Requested output exceeds the configured absolute voltage limit. AmplitudeVpp=%f, OffsetV=%f, PositivePeakV=%f, NegativePeakV=%f, LimitAbsV=%f
```

後段の `FG420_Set_Ampl.vi` / `FG420_Set_Offset.vi` は error in.status=True により実処理を行わない。

#### 6. Clamp モード

オフセットは変更せず、振幅だけを縮小する。

```text
Allowed Amplitude Vpp = 2 × (Output Limit Abs V - abs(Requested Offset V))
Applied Amplitude Vpp = min(Requested Amplitude Vpp, Allowed Amplitude Vpp, Device Amplitude Max Vpp)
```

`abs(Requested Offset V) > Output Limit Abs V` の場合、振幅を 0 にしても安全条件を満たせないため Clamp 不可としてエラーを返す。

```text
code   = -710111
source = FG420_Apply_Output_Limit.vi: Offset alone exceeds the configured absolute voltage limit. OffsetV=%f, LimitAbsV=%f
```

Clamp を行った場合は `Limited?=True` とする。

#### 7. その他のローカルエラー

| Code | 条件 |
|---:|---|
| -710110 | Output Limit Abs V <= 0 |
| -710111 | オフセット単独でリミット超過 |
| -710112 | Reject モードでピーク値がリミット超過 |
| -710113 | ドライバから取得した Min / Max が逆転または不正 |
| -710114 | 振幅またはオフセットが FG420 の設定可能範囲外 |

#### 8. LabVIEW 構造

- error in.status の外側 Case Structure。
- 入力検証用 Case Structure。
- Limit Mode の Case Structure。
- `Abs`、`Add`、`Subtract`、`Divide`、`Multiply`、`Min & Max`。
- `Bundle By Name` でローカル error cluster を生成。

#### 9. 単体テスト

| No. | 条件 | 期待結果 |
|---:|---|---|
| 1 | Amp=2Vpp, Offset=0V, Limit=5V | そのまま通過 |
| 2 | Amp=8Vpp, Offset=2V, Limit=5V, Reject | -710112 |
| 3 | Amp=8Vpp, Offset=2V, Limit=5V, Clamp | Applied Amp=6Vpp、Limited=True |
| 4 | Amp=0Vpp, Offset=6V, Limit=5V | -710111 |
| 5 | Amp=-1Vpp | 入力範囲エラー |
| 6 | Device Max=10Vpp に対して Requested=12Vpp | -710114 |
| 7 | 既存 error | 元 error と安全値を保持 |

> 重要：本機能はソフトウェアガードであり、ハードウェアの過電圧保護ではない。ラッパを介さない手動操作、別ソフトからの操作、VI 不具合を防ぐものではない。供試体破損や安全上の危険がある場合は、外付けクランプ、アッテネータ、保護回路、ヒューズ等を併用する。

---

## A1A.6 チャネル安全設定 VI

### A1A.6.1 `FG420_Configure_Channel_Safe.vi`

#### 0. 責務

1台の FG420 の1チャネルについて、出力 OFF を確認してから負荷、範囲取得、リミット判定、波形、周波数、振幅、オフセットを安全な順序で設定する。

#### 1. 入力

VISA reference in、FG420_Channel_Config.ctl、error in。

#### 2. 出力

VISA reference out、Applied Amplitude Vpp、Applied Offset V、Positive Peak V、Negative Peak V、Limited?、Status、TestError、error out。

#### 3. アルゴリズム

```text
if error in.status=True:
    安全出力を返す
elif Channel Config.Enabled?=False:
    VISA / error を素通り
else:
    FG420_Output(Channel, OFF)
    FG420_Set_Load(Channel)
    FG420_Query_Ampl_Bound(Channel, Minimum)
    FG420_Query_Ampl_Bound(Channel, Maximum)
    FG420_Query_Offset_Bound(Channel, Minimum)
    FG420_Query_Offset_Bound(Channel, Maximum)
    FG420_Apply_Output_Limit
    if limit error:
        設定を中止
    else:
        FG420_Set_Func(Channel)
        FG420_Set_Freq(Channel)
        FG420_Set_Ampl(Channel, Applied Amplitude)
        FG420_Set_Offset(Channel, Applied Offset)
最後に Error_To_TestStatus
```

#### 4. LabVIEW 構造の選定理由

- Enabled? は Case Structure で分岐し、未使用 Ch を完全にスキップする。
- 出力 OFF を先頭に置き、設定中の過渡出力を防ぐ。
- Limit 判定を VOLT / VOLT Offs より前に置き、超過値を機器へ送信しない。
- VISA reference と error は全 SubVI で直列接続する。

#### 5. 単体テスト

- Ch1 Enabled / Ch2 Disabled。
- Ch1 Disabled / Ch2 Enabled。
- Ch1 / Ch2 両方 Enabled で異なる周波数・振幅。
- Ch1 は通過、Ch2 は Reject エラー。
- Clamp 時の Applied 値が FG420 の読み戻しと一致。

---

## A1A.7 機器準備 VI

### A1A.7.1 `FG420_Prepare_Device.vi`

#### 0. 責務

1台の FG420 を初期化し、機器識別、安全な電源投入設定、2ch独立設定を完了する。

#### 1. アルゴリズム

```text
FG420_Init
  → FG420_Get_ID
  → IDN検証
  → FG420_Set_PowerOn_Output(OFF)
  → FG420_Set_ChanMode(INDependent)
  → FG420_Set_Coupling(NONE)
```

#### 2. 出力

VISA reference out、IDN、FG420_Device_State.ctl、Status、TestError、error out。

#### 3. 単体テスト

- FG420 を1台接続して正常。
- FG410 を接続した場合は 2ch PoC の対象外としてエラーまたは警告。
- VISA リソース誤り。
- IDN のシリアル番号不一致。
- CHAN Mode / Coupling 設定エラー。

---

## A1A.8 複数台 PoC

### A1A.8.1 作成 VI

`PoC_FG420_Multi_Device.vi`

### A1A.8.2 フロントパネル入力

| 入力 | 型 |
|---|---|
| Device Configs | FG420_Device_Config.ctl 配列 |
| Output Duration ms | U32 |
| Enable Output Phase? | Boolean |
| Stop On First Error? | Boolean |
| error in | error cluster |

### A1A.8.3 出力

| 出力 | 型 |
|---|---|
| Device States | FG420_Device_State.ctl 配列 |
| Applied Ch1 Configs | 結果配列 |
| Applied Ch2 Configs | 結果配列 |
| Device Errors | error cluster 配列 |
| Status | Status.ctl |
| TestError | TestError.ctl |
| error out | error cluster |

### A1A.8.4 重要な設計方針

#### 1. VISA session は機器ごとに分離する

`Device Configs` の各要素から個別に Initialize し、VISA session 配列として保持する。1本の VISA wire を複数台で共有しない。

#### 2. エラーも機器ごとに分離する

1台目のエラーで2台目以降の Cleanup がスキップされないよう、機器ごとの error cluster を配列で保持する。

通常の設定フェーズでは `Stop On First Error?` により後続設定を止めてもよいが、Cleanup フェーズでは全ての機器・全てのチャネルに対して OFF / Close を試行する。

#### 3. 同一 VISA Resource の重複を禁止する

開始前に Device Configs の VISA Resource を走査し、Enabled な要素に重複があればローカルエラーとする。

```text
code   = -710120
source = PoC_FG420_Multi_Device.vi: Duplicate VISA resource was found. Resource=%s, FirstIndex=%d, DuplicateIndex=%d
```

### A1A.8.5 処理アルゴリズム

```text
Original Error = error in

入力検証:
    Enabled Device Count >= 1
    VISA Resource重複なし
    各DeviceでCh1またはCh2のどちらかがEnabled

Phase 1: Prepare Devices
for each enabled Device Config:
    FG420_Prepare_Device
    VISA session / IDN / Device State / Device Error を配列へ保存

Phase 2: Configure Channels
for each prepared Device:
    FG420_Configure_Channel_Safe(Ch1 Config)
    FG420_Configure_Channel_Safe(Ch2 Config)
    Applied値とStateを保存

Phase 3: Output ON
if Enable Output Phase? AND 全設定が許可された機器:
    for each Device:
        if Ch1 Enabled and Ch1 Output On?: FG420_Output(Ch1, ON)
        if Ch2 Enabled and Ch2 Output On?: FG420_Output(Ch2, ON)

Phase 4: Wait / Measurement
    Wait Output Duration ms
    必要に応じて測定器 / RAMScope を実行

Phase 5: Normal Output OFF
for each Device:
    Enabled Ch1をOFF
    Enabled Ch2をOFF

Cleanup（必ず実行）:
for each Device State:
    Clear Errorsしたcleanup wireを使用
    if Initialized?:
        Ch1 OFFを試行
        Ch2 OFFを試行
        Closeを試行
    Original Errorを最優先でMerge

最後に全Device Errorを集計し、最初のerrorをPoC error outへ返す
Error_To_TestStatusはPoC末尾で1回だけ実行
```

### A1A.8.6 LabVIEW 構造

- Device Config 配列：外側 For Loop、自動指標付け。
- Ch1 / Ch2：固定2要素配列を作り、内側 For Loopで処理してもよい。
- VISA session、Device State、Device Error：For Loop の出力自動指標付け、または Shift Register。
- 集計値：Shift Register。
- Cleanup：通常経路とは別の For Loop。
- Wait：Flat Sequence Structure または error wire を持つ待ち用 SubVI で順序保証。

### A1A.8.7 並列実行について

PoC 初版はデバッグ性を優先し、複数台の設定を外側 For Loop で順次実行する。

複数台を並列実行する場合は、次の全条件を満たした後に For Loop の Parallel Iterations を検討する。

1. 各反復で VISA session と error が完全に独立している。
2. 横河ドライバ VI の再入可能性を確認済み。
3. 同一機器の Ch1 / Ch2 を異なる反復から同時操作しない。
4. Cleanup の競合が発生しない。

条件が未確認のまま並列化しない。

---

## A1A.9 PoC フロントパネル例

```text
Device Configs[0]
  Logical Name = FG420_A
  VISA Resource = USB0::...A...::INSTR
  Ch1: Enabled=True,  Freq=1000Hz, Amp=2Vpp, Offset=0V, Limit=3V
  Ch2: Enabled=True,  Freq=2000Hz, Amp=1Vpp, Offset=1V, Limit=3V

Device Configs[1]
  Logical Name = FG420_B
  VISA Resource = USB0::...B...::INSTR
  Ch1: Enabled=True,  Freq=500Hz, Amp=4Vpp, Offset=0V, Limit=2.5V, Mode=Clamp
  Ch2: Enabled=False
```

この条件では FG420_A の Ch1 / Ch2 は個別設定される。FG420_B Ch1 は要求ピークがリミットを超える場合、Clamp モードにより Applied Amplitude が縮小される。

---

## A1A.10 単体試験・結合試験

### A1A.10.1 薄いラッパ

- CHAN Mode=INDependent。
- INST Coup=NONE / ALL。
- IDN取得とシリアル抽出。
- OUTP Pon=OFF。
- Ampl / Offset の Minimum / Maximum 問合せ。
- SYST Err取得。

### A1A.10.2 1台・1ch

- Ch1のみ。
- Ch2のみ。
- Rejectでリミット超過時にOUTP ONしない。
- ClampでApplied値を確認。
- 途中エラー時に両ch OFF、Close。

### A1A.10.3 1台・2ch

- `INDependent` + `NONE`。
- Ch1 / Ch2 に異なる波形、周波数、振幅、オフセット。
- Ch1設定後もCh2設定が変化しない。
- Ch1だけリミットエラー、Ch2の出力方針を確認。
- Cleanupで両ch OFF。

### A1A.10.4 複数台

- 2台に異なるVISA Resourceを設定。
- IDNシリアルを機器ごとに記録。
- 1台目正常、2台目Initialize失敗。
- 1台目設定失敗、2台目Cleanup実行。
- 重複VISA Resourceで-710120。
- 全台、全chがCleanup後OFF。

### A1A.10.5 同期要件

- ソフトウェア順次ONの時間差を測定。
- 要求時間差を満たさない場合は外部基準 / 外部トリガ方式へ移行。
- 共通トリガ時は各機器の出力条件を事前設定し、トリガ待ち状態から一斉開始する。

---

## A1A.11 実装順

```text
STEP 1  typedef作成
  FG420_Limit_Mode.ctl
  FG420_Channel_Config.ctl
  FG420_Device_Config.ctl
  FG420_Device_State.ctl

STEP 2  追加薄いラッパ
  FG420_Set_ChanMode.vi
  FG420_Set_Coupling.vi
  FG420_Get_ID.vi
  FG420_Set_PowerOn_Output.vi
  FG420_Query_Ampl_Bound.vi
  FG420_Query_Offset_Bound.vi
  FG420_Read_System_Error.vi

STEP 3  純粋ロジック
  FG420_Apply_Output_Limit.vi

STEP 4  複合VI
  FG420_Prepare_Device.vi
  FG420_Configure_Channel_Safe.vi

STEP 5  PoC
  PoC_FG420_Multi_Device.vi

STEP 6  1台1ch → 1台2ch → 2台複数ch の順で実機確認

STEP 7  必要な場合のみ同期拡張
  FG420_Set_Reference_Source.vi
  FG420_Set_Trigger_Source.vi
  FG420_Trigger.vi
```

---

## A1A.12 完了条件

- [ ] `CHAN Mode=INDependent` と `INST Coup=NONE` で Ch1 / Ch2 を個別設定できる。
- [ ] Ch1 / Ch2 に異なる周波数・振幅・オフセットを設定できる。
- [ ] 複数の VISA Resource を配列で受け取り、各 FG420 の IDN を記録できる。
- [ ] 設定した絶対電圧リミットを超える要求は Reject または Clamp される。
- [ ] リミットエラー時に VOLT / VOLT Offs / OUTP ON が実行されない。
- [ ] 設定前と Cleanup で全ch OUTP OFFを実行する。
- [ ] 1台のエラーが他の機器の Cleanup を妨げない。
- [ ] 全ての Initialized 機器で Close を試行する。
- [ ] VISA Resource 重複を開始前に検出する。
- [ ] ソフトウェア順次ONと厳密同期の違いを試験仕様へ明記する。
- [ ] 厳密同期が必要な場合、外部基準 / 外部トリガ構成で実機確認する。
