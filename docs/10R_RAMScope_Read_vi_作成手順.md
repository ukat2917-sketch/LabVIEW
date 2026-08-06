# 10R. `RAMScope_Read.vi` 詳細作成手順

**最終整理日：2026-08-05**

> 本書は[10_RAMScope実装方針.md](./10_RAMScope実装方針.md)の`RAMScope_Read.vi`節を、LabVIEW画面上で再現できる端子・Case・配線単位へ展開した子文書である。
>
> 上位のAPI責務、Packet仕様およびレイヤ分担は第10章を正とし、本書では`GetBufferDataNum`対応後の最終ブロックダイアグラムだけを扱う。
>
> 旧構造の`ChNum × RequestedDataNum Limit`から先にBufferサイズを算出する方式は使用しない。

---

## 0. 実現したい機能とVIの責務

`RAMScope_Read.vi`は、測定中の表示用バッファから取得可能Packet数を先に問い合わせ、操作者が指定した上限以下のPacketだけを安全に取得してParserへ渡す公開APIである。

```text
GetBufferDataNum
  → AvailableDataNumを取得
  → RequestedDataNumを決定
  → 必要BufferサイズをI64で検証
  → GetBufferData
  → 実取得分へRaw Bufferを切り詰め
  → RAMScope_Parse_Buffer.vi
  → Parsed Packet Countを照合
```

本VIは停止後保存ログを扱わない。停止後保存ログは`RAMScope_Read_Logging_Block.vi`が担当する。

最重要ルールは、**前段エラー、DLL Wrapperエラー、Parserエラーを後段のローカル検証エラーで上書きしないこと**である。

---

## 1. 入力データの実体

| 端子 | 型 | 意味 |
|---|---|---|
| `UnitNo` | I32 | 操作対象Unit番号。現構成では通常0 |
| `MdlNo` | I32 | `RAMScope_Init.vi`が返したRAMモジュール番号 |
| `RequestedDataNum Limit` | I32 | 1回のReadで要求するPacket数の上限 |
| `Channel List` | `RAMScope_Channel.ctl[]` | `SetMeasCh`へ渡したものと同一順序のチャンネル配列 |
| `Byte Order` | `RAMScope_Byte_Order.ctl` | Parserで使用するEndian |
| `Max Buffer Bytes` | I64 | 1回の配列確保に許容する最大Byte数 |
| `error in` | error cluster | 前段処理のエラー |

上位PoCに旧名称`MaxDataNum`が残っている場合でも、接続先は`RequestedDataNum Limit`である。意味を明確にするため、上位制御器も`RequestedDataNum Limit`へ改名する。

`UnitNum`はDeviceInitが返す接続Unit数であり、`UnitNo`とは別物である。

---

## 2. 出力データモデル

| 端子 | 型 | 意味 |
|---|---|---|
| `AvailableDataNum` | I32 | GetBufferDataNumが返した取得可能Packet数 |
| `RequestedDataNum` | I32 | 実際にGetBufferDataへ要求したPacket数 |
| `Raw Buffer` | U8[] | 実取得Packet分へ切り詰めた生データ |
| `DataNum` | I32 | GetBufferDataが返した実取得Packet数 |
| `LostDataNum` | I32 | APIが返した欠落Packet数 |
| `Packets` | `RAMScope_Packet.ctl[]` | Parserが生成したPacket配列 |
| `Parsed Packet Count` | I32 | `Array Size(Packets)`相当 |
| `Unused Byte Count` | I32 | Parserが未使用として残したByte数 |
| `Status` | `Status.ctl` | TestStand判定用状態 |
| `TestError` | `TestError.ctl` | 機器名、code、message等 |
| `error out` | error cluster | 最初に発生したエラーを保持した最終結果 |

---

## 3. 数値型の固定ルール

Packet件数はI32、Byte数計算はI64で扱う。

```text
AvailableDataNum        I32
RequestedDataNum Limit  I32
RequestedDataNum        I32
DataNum                 I32
LostDataNum             I32

ChNum                    I32 → サイズ計算側だけI64化
Packet Size              I64
Required Bytes           I64
Actual Bytes             I64
Max Buffer Bytes         I64
```

`RequestedDataNum Limit`をMin & Maxへ入れる前にI64化しない。I32同士で`RequestedDataNum`を決め、Bufferサイズ計算へ分岐した後だけI64へ変換する。

```text
AvailableDataNum I32 ───────────────┐
                                     ├─ Min & Max minimum → RequestedDataNum I32
RequestedDataNum Limit I32 ─────────┘

RequestedDataNum I32
  ├─ GetBufferDataのRequestedDataNumへ接続
  ├─ DataNum範囲比較へ接続
  └─ To 64-bit Integer
       ↓
     Required Bytes計算
```

I64からI32へ変換するのは、上限検証を通過した`Required Bytes`または`Actual Bytes`を配列lengthへ渡す直前だけとする。

---

## 4. 前提条件・ローカルエラーコード

| code | 条件 | sourceの意味 |
|---:|---|---|
| `-700166` | Read入力値不正 | ChNum、Limit、MdlNoまたはMax Buffer Bytesが不正 |
| `-700162` | `AvailableDataNum < 0` | GetBufferDataNum戻り件数が負数 |
| `-700163` | 必要Bufferサイズ不正または上限超過 | Required Bytesが0以下、設定上限超過、またはI32上限超過 |
| `-700164` | `DataNum`が要求範囲外 | `0 <= DataNum <= RequestedDataNum`を満たさない |
| `-700165` | Parser件数不一致 | Parsed Packet CountとDataNumが一致しない |

`-700162`から`-700165`は既存の第10章コード体系を維持する。入力不正には意味衝突を避けるため`-700166`を割り当てる。

---

## 5. 配置する関数およびSubVI

| 数 | 関数／SubVI | 用途 |
|---:|---|---|
| 1 | Array Size | Channel ListからChNumを得る |
| 1 | Unbundle By Name | `error in.status`を取得する |
| 必要数 | Case Structure | 既存error、入力、Wrapper、件数、サイズ、Parserの各分岐 |
| 1 | `RS_DLL_GT150GetBufferDataNum.vi` | 取得可能Packet数を問い合わせる |
| 1 | Min & Max | RequestedDataNumを決める |
| 2以上 | To 64-bit Integer | ChNum、RequestedDataNum、DataNumをByte計算側だけI64化 |
| 2 | Multiply | Packet Size、Required/Actual Bytesを計算 |
| 1 | Add | Packet Sizeの固定12byteを加算 |
| 1 | `RS_DLL_GT150GetBufferData.vi` | Raw Buffer、DataNum、LostDataNumを取得する |
| 1 | Array Subset | 実取得分だけRaw Bufferを切り詰める |
| 1 | `RAMScope_Parse_Buffer.vi` | Raw BufferをPacket配列へ変換する |
| 5 | Format Into String | `-700166`、`-700162`、`-700163`、`-700164`、`-700165`のsource生成 |
| 5 | Bundle By Name | ローカルerror cluster生成 |
| 1 | `Error_To_TestStatus.vi` | 最終errorをStatus/TestErrorへ変換する |

各Caseの全出力トンネルを明示配線し、`Use default if unwired`を使用しない。

---

## 6. Case Structureの全体構成

```text
Case 1: error in.status?
├─ True  前段エラーあり
│    └─ 元errorと安全出力を返す
└─ False 前段エラーなし
     ↓
     Case 2: Input Valid?
     ├─ False → -700166
     └─ True
          ↓
          GetBufferDataNum
          ↓
          Case 3: GetBufferDataNum error.status?
          ├─ True  → Wrapper errorをそのまま返す
          └─ False
               ↓
               Case 4: AvailableDataNum < 0?
               ├─ True  → -700162
               └─ False
                    ↓
                    RequestedDataNumを算出
                    ↓
                    Case 5: RequestedDataNum == 0?
                    ├─ True  → 空データ正常終了
                    └─ False
                         ↓
                         Required BytesをI64計算
                         ↓
                         Case 6: Buffer Size Invalid?
                         ├─ True  → -700163
                         └─ False
                              ↓
                              GetBufferData
                              ↓
                              Case 7: GetBufferData error.status?
                              ├─ True  → Wrapper errorをそのまま返す
                              └─ False
                                   ↓
                                   Case 8: Returned Count Valid?
                                   ├─ False → -700164
                                   └─ True
                                        ↓
                                        Actual Bytesへ切詰め
                                        ↓
                                        Parse Buffer
                                        ↓
                                        Case 9: Parser error.status?
                                        ├─ True  → Parser errorをそのまま返す
                                        └─ False
                                             ↓
                                             Case 10: Parsed Count Match?
                                             ├─ False → -700165
                                             └─ True  → 正常終了
```

Case selectorへ接続するBooleanの意味とTrue／Falseを逆にしない。

---

## 7. 配線順

### A. 外側Caseで前段エラーを最優先する

1. `error in`をUnbundle By Nameへ接続し、`status`を表示する。
2. `status`を最外周Case Structureのselectorへ接続する。

#### Trueケース（`error in.status=True`：前段エラーあり）

- DLL Wrapper、入力検証、Parserを実行しない。
- `error in`をそのままerror出力トンネルへ接続する。
- データ出力は安全値とする。

```text
AvailableDataNum     = 0
RequestedDataNum     = 0
Raw Buffer           = 空U8[]
DataNum              = 0
LostDataNum          = 0
Packets              = 空RAMScope_Packet.ctl[]
Parsed Packet Count  = 0
Unused Byte Count    = 0
error                = 元のerror in
```

このCaseにローカルerror用Bundle By Nameを配置しない。これによりConnect、Init、Set Cond、Log Start等の最初のエラーをReadが上書きしない。

#### Falseケース（`error in.status=False`：前段エラーなし）

入力検証へ進む。

---

### B. 入力値を検証する

1. `Channel List`をArray Sizeへ接続し、`ChNum` I32を得る。
2. 次を比較する。

```text
ChNum >= 1
RequestedDataNum Limit > 0
MdlNo >= 0
Max Buffer Bytes > 0
```

3. 4条件をCompound ArithmeticのANDへ接続し、`Input Valid?`を作る。
4. `UnitNo > 0`は条件に入れない。UnitNo=0は先頭Unit番号として有効である。

#### Falseケース（`Input Valid?=False`）

source全文：

```text
RAMScope_Read.vi: Input is invalid. ChNum=%d, RequestedDataNumLimit=%d, MdlNo=%d, MaxBufferBytes=%d
```

Format Into Stringの入力順：

1. ChNum I32
2. RequestedDataNum Limit I32
3. MdlNo I32
4. Max Buffer Bytes I64

LabVIEWのFormat Into StringではI64にも`%d`を使用する。C言語形式の`%lld`は使用しない。

Bundle By Name：

```text
基準クラスタ = Input Valid? Caseへ入った正常error
status       = True
code         = I32 -700166
source       = Format Into String出力
```

全データ出力は安全値を返す。

#### Trueケース（`Input Valid?=True`）

GetBufferDataNumへ進む。

---

### C. `RS_DLL_GT150GetBufferDataNum.vi`を呼ぶ

接続：

```text
UnitNo        → Wrapper UnitNo
MdlNo         → Wrapper MdlNo
正常error     → Wrapper error in
```

出力：

```text
AvailableDataNum I32
Wrapper error out
```

Wrapper直後に`error out.status` Caseを置く。

#### Trueケース（Wrapper errorあり）

- `Wrapper error out`をそのまま返す。
- `-700162`を作らない。
- データ出力は安全値とする。ただし`AvailableDataNum`表示用出力はWrapperが返した安全値0を使用する。

#### Falseケース（Wrapper正常）

`AvailableDataNum < 0`判定へ進む。

---

### D. `AvailableDataNum`の負数を検証する

selector：

```text
AvailableDataNum < 0
```

#### Trueケース

source全文：

```text
RAMScope_Read.vi: AvailableDataNum must not be negative. UnitNo=%d, MdlNo=%d, AvailableDataNum=%d
```

Format Into Stringの入力順：UnitNo I32、MdlNo I32、AvailableDataNum I32。

```text
基準クラスタ = GetBufferDataNumの正常error out
status       = True
code         = I32 -700162
source       = Format Into String出力
```

#### Falseケース

RequestedDataNumを算出する。

---

### E. `RequestedDataNum`をI32で決定する

`AvailableDataNum`と`RequestedDataNum Limit`をI32のままMin & Maxへ接続する。

```text
RequestedDataNum
= min(AvailableDataNum, RequestedDataNum Limit)
```

負数は直前でエラーにしているため、`max(AvailableDataNum,0)`は必須ではない。使用する場合も結果型をI32のまま維持する。

Min & Maxのminimum出力を`RequestedDataNum` I32として3方向へ分岐する。

```text
RequestedDataNum I32
├─ RequestedDataNum == 0判定
├─ GetBufferData.vi / RequestedDataNum
└─ To 64-bit Integer → Required Bytes計算
```

---

### F. データ0件を正常終了させる

selector：

```text
RequestedDataNum == 0
```

#### Trueケース（取得対象なし）

GetBufferDataとParserを呼ばない。

```text
AvailableDataNum     = GetBufferDataNumの値
RequestedDataNum     = 0
Raw Buffer           = 空U8[]
DataNum              = 0
LostDataNum          = 0
Packets              = 空配列
Parsed Packet Count  = 0
Unused Byte Count    = 0
error                = GetBufferDataNumの正常error
```

0件はエラーではない。

#### Falseケース

Byte数計算へ進む。

---

### G. Packet SizeとRequired BytesをI64で計算する

掛け算前にI64へ変換する。

```text
Packet Size I64
= I64(ChNum) × I64(4) + I64(12)

Required Bytes I64
= I64(RequestedDataNum) × Packet Size I64
```

定数4と12もI64へ設定する。

`Buffer Size Invalid?`は次のOR条件で作る。

```text
Required Bytes <= 0
OR Required Bytes > Max Buffer Bytes
OR Required Bytes > 2147483647
```

#### Trueケース（サイズ不正）

source全文：

```text
RAMScope_Read.vi: Required buffer size is invalid or exceeds the limit. RequiredBytes=%d, MaxBufferBytes=%d, RequestedDataNum=%d, PacketSize=%d
```

入力順と型：

1. Required Bytes I64
2. Max Buffer Bytes I64
3. RequestedDataNum I32
4. Packet Size I64

LabVIEWではI64も`%d`を使用し、`%lld`を使用しない。

```text
基準クラスタ = GetBufferDataNumの正常error
status       = True
code         = I32 -700163
source       = Format Into String出力
```

#### Falseケース（サイズ正常）

上限確認済みの`Required Bytes I64`をTo 32-bit IntegerでI32へ変換し、`Buffer Byte Size`としてGetBufferDataへ渡す。

---

### H. `RS_DLL_GT150GetBufferData.vi`を呼ぶ

接続：

```text
UnitNo                 → UnitNo
MdlNo                  → MdlNo
RequestedDataNum I32   → RequestedDataNum
Required Bytes I32     → Buffer Byte Size
正常error              → error in
```

出力：

```text
Allocated Raw Buffer U8[]
DataNum I32
LostDataNum I32
Wrapper error out
```

Wrapper直後に`error out.status` Caseを置く。

#### Trueケース（GetBufferDataエラー）

Wrapper errorをそのまま返す。`-700164`を生成しない。

#### Falseケース（Wrapper正常）

戻り件数検証へ進む。

---

### I. `DataNum`の範囲を検証する

```text
Returned Count Valid?
= DataNum >= 0
AND DataNum <= RequestedDataNum
```

#### Falseケース

source全文：

```text
RAMScope_Read.vi: DataNum is outside the requested range. DataNum=%d, RequestedDataNum=%d, AvailableDataNum=%d
```

入力順：DataNum I32、RequestedDataNum I32、AvailableDataNum I32。

```text
基準クラスタ = GetBufferDataの正常error
status       = True
code         = I32 -700164
source       = Format Into String出力
```

#### Trueケース

実取得Byte数を計算する。

---

### J. Raw Bufferを実取得分へ切り詰める

```text
Actual Bytes I64
= I64(DataNum) × Packet Size I64
```

前段で`DataNum <= RequestedDataNum`かつRequired Bytes上限確認済みなので、Actual BytesをI32へ安全に変換できる。

Array Subset：

```text
array  = GetBufferDataのAllocated Raw Buffer
index  = I32 0
length = Actual Bytes I32
```

Array Subset出力を2方向へ分岐する。

```text
切り詰め済みRaw Buffer
├─ RAMScope_Read.vi / Raw Buffer出力
└─ RAMScope_Parse_Buffer.vi / Raw Buffer入力
```

確保時の余剰Byteを含む配列をParserへ渡さない。

---

### K. `RAMScope_Parse_Buffer.vi`を呼ぶ

接続：

```text
切り詰め済みRaw Buffer → Raw Buffer
DataNum I32             → DataNum
Channel List            → Channel List
Byte Order              → Byte Order
GetBufferData正常error  → error in
```

Parser出力：Packets、Parsed Packet Count、Unused Byte Count、error out。

Parser直後に`error out.status` Caseを置く。

#### Trueケース（Parserエラー）

Parser errorをそのまま返す。`-700165`を生成しない。

#### Falseケース（Parser正常）

件数照合へ進む。

---

### L. Parser件数を照合する

selector：

```text
Parsed Packet Count == DataNum
```

#### Falseケース

source全文：

```text
RAMScope_Read.vi: Parsed packet count does not match DataNum. ParsedPacketCount=%d, DataNum=%d, UnusedByteCount=%d
```

入力順：Parsed Packet Count I32、DataNum I32、Unused Byte Count I32。

```text
基準クラスタ = Parserの正常error out
status       = True
code         = I32 -700165
source       = Format Into String出力
```

#### Trueケース

Parser出力と正常errorをそのまま最終出力へ通す。

---

### M. `Error_To_TestStatus.vi`へ接続する

全Caseを抜けた最終errorを`Error_To_TestStatus.vi / error in`へ接続する。

```text
Device Name = RAMScope
```

同SubVIのStatus、TestError、error outを`RAMScope_Read.vi`の同名出力へ接続する。

途中Case内でStatus/TestErrorを個別生成しない。

---

## 8. Caseごとの安全出力

エラーまたはバイパスCaseでは、次を基本安全値とする。

```text
AvailableDataNum     = 取得済みならその値、未取得なら0
RequestedDataNum     = 算出済みならその値、未算出なら0
Raw Buffer           = 空U8[]
DataNum              = 取得済みならその値、未取得なら0
LostDataNum          = 取得済みならその値、未取得なら0
Packets              = 空RAMScope_Packet.ctl[]
Parsed Packet Count  = 0
Unused Byte Count    = 0
error                = その地点で最初に成立したerror
```

Parser成功後の`-700165`だけは、取得済みRaw Buffer、DataNum、LostDataNum、Packets、Parsed Packet Count、Unused Byte Countを保持して返す。解析結果の調査に必要なため、0で潰さない。

---

## 9. 完成時のerror優先順位

```text
1. error inの前段エラー
2. GetBufferDataNum Wrapperエラー
3. -700162 AvailableDataNum負数
4. -700163 Bufferサイズ不正
5. GetBufferData Wrapperエラー
6. -700164 DataNum範囲外
7. Parserエラー
8. -700165 Parser件数不一致
```

後順位のローカルerrorで前順位errorを上書きしない。

---

## 10. 単体テスト

### 10.1 前段エラー保持

入力：

```text
error in.status = True
error in.code   = -12345
error in.source = Existing upstream error
Channel List    = 空
Limit           = 0
```

期待：code/sourceが完全に同一。`-700166`等へ変わらない。

### 10.2 入力不正

- Channel List空。
- RequestedDataNum Limit=0。
- MdlNo=-1。
- Max Buffer Bytes=0。

期待：`-700166`、GetBufferDataNum未実行。

### 10.3 GetBufferDataNum

- Wrapperエラー時は元のAPI/CLFNエラー保持。
- AvailableDataNum=-1は`-700162`。
- AvailableDataNum=0は正常な空出力。

### 10.4 Limit処理

```text
Available=5、Limit=10 → Requested=5
Available=10、Limit=5 → Requested=5
Available=1、Limit=1 → Requested=1
```

RequestedDataNumがI32であることを確認する。

### 10.5 Bufferサイズ

- Required Bytes=Max Buffer Bytesは正常。
- Required Bytes>Max Buffer Bytesは`-700163`。
- Required Bytes>2147483647は`-700163`。
- 形式文字列に`%lld`を入れるとVIが壊れるため、全整数を`%d`で表示する。

### 10.6 GetBufferData戻り件数

- DataNum=-1 → `-700164`。
- DataNum=RequestedDataNum+1 → `-700164`。
- DataNum=RequestedDataNum → 正常。
- DataNumが要求未満かつ0以上 → 正常。

### 10.7 Parser

- Parserエラーはそのまま保持。
- Parsed Packet Count=DataNum → 正常。
- 不一致 → `-700165`。

### 10.8 推奨プローブ位置

```text
error in
Input Valid?
GetBufferDataNum error out
AvailableDataNum
RequestedDataNum
Packet Size I64
Required Bytes I64
GetBufferData error out
DataNum
Actual Bytes I64
切り詰め済みRaw Buffer Array Size
Parser error out
Parsed Packet Count
最終error
```

---

## 11. よくあるミス

| 症状 | 原因 | 対応 |
|---|---|---|
| ConnectエラーがReadエラーへ変わる | 最外周に`error in.status` Caseがない | 前段error Caseを一番外側へ置く |
| `-700164`が入力0で発生する | 旧Read構造を使用 | GetBufferDataNum対応構造へ置換 |
| RequestedDataNumがI64になる | LimitをMin前にI64化 | MinまではI32、サイズ計算側だけI64化 |
| Required Bytesが負数になる | I32で掛け算後にI64化 | 掛け算前にChNum／RequestedDataNumをI64化 |
| Format Into StringでVIが壊れる | `%lld`を使用 | I64にも`%d`を使用 |
| Wrapper APIエラーがローカルerrorへ変わる | Wrapper直後のerror Caseがない | Wrapper errorを先に分岐して保持 |
| Parserが余剰Byteを読む | 確保配列をそのまま渡している | `DataNum × Packet Size`へArray Subset |
| Parserエラーが`-700165`へ変わる | Parser error確認前に件数照合 | Parser error Caseを先に置く |
| 壊れた実行矢印 | Caseトンネル未配線 | 全Caseの全出力を明示配線 |
| 0件取得をエラー扱い | RequestedDataNum=0 Case不足 | 空データ正常終了Caseを作る |

---

## 12. 完成チェックリスト

- [ ] `error in.status` Caseが最外周にある。
- [ ] 前段エラーCaseで元code/sourceをそのまま返す。
- [ ] Input Valid?がChNum、Limit、MdlNo、Max Buffer Bytesを検証する。
- [ ] 入力不正は`-700166`である。
- [ ] GetBufferDataNum Wrapper errorをローカルerrorで上書きしない。
- [ ] AvailableDataNum負数は`-700162`である。
- [ ] RequestedDataNumはI32のMinで決める。
- [ ] RequestedDataNum=0は正常な空データである。
- [ ] Packet SizeとRequired Bytesは掛け算前からI64である。
- [ ] Required Bytes上限違反は`-700163`である。
- [ ] Format Into Stringで`%lld`を使用していない。
- [ ] 上限検証後だけRequired BytesをI32化する。
- [ ] GetBufferData Wrapper errorを保持する。
- [ ] DataNum範囲外は`-700164`である。
- [ ] Actual BytesをI64計算後にI32化する。
- [ ] Array Subset後のRaw BufferをParserへ渡す。
- [ ] Parser errorを保持する。
- [ ] Parser件数不一致は`-700165`である。
- [ ] `Error_To_TestStatus.vi`は最後に1回だけ呼ぶ。
- [ ] 全Caseの全出力トンネルを明示配線している。
- [ ] 単体テストと推奨プローブ確認が完了している。
