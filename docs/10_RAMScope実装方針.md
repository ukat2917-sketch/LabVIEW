# 10. RAMScope GT170 実装・学習ガイド

<!-- generated-vi-diagram -->
![RAMScope公開API接続](./assets/vi-diagrams/ramscope-public-api-flow.svg)

<!-- generated-vi-diagram -->
![RAMScopeロギング公開API接続](./assets/vi-diagrams/ramscope-logging-public-api-flow.svg)

**最終整理日：2026-08-06**

> 本章をRAMScope実装資料の唯一の正本とする。
>
> `RAMScope_Read.vi`および`PoC_RAMScope_Main.vi`の端子、Case Structure、数値型、エラー文字列、`Max Buffer Bytes`配線、単体試験は本章だけを参照する。
>
> 旧`MaxDataNum`、旧Read構造、子文書`10R`、独立したPoC作成手順は正本として使用しない。変更は対象VIの本節へ直接統合し、差分だけの別紙を増やさない。
>
> 2026-07-26時点の旧第10章全体は、履歴確認用として`docs/archive/10_RAMScope実装方針_2026-07-26_旧版.md`へ退避している。

---

## 10.1 適用範囲と確定方針

本章は、RAMScope GT170をLabVIEW 64bitから操作する実装のうち、オンラインReadと通信確認PoCを再現できる粒度で整理する。

```text
RAMScope_Read.vi
  GetBufferDataNum
  → 要求Packet数の決定
  → I64によるBufferサイズ検証
  → GetBufferData
  → 実取得分への切り詰め
  → Parser
  → 件数照合

PoC_RAMScope_Main.vi
  Connect
  → Init
  → Set Cond
  → Log Start
  → Wait
  → Read
  → Log Stop
  → Release
  → Close
```

確定ルールは次のとおり。

- Packet数はI32で扱う。
- Byte数の演算はI64で扱う。
- `RequestedDataNum Limit`と`Max Buffer Bytes`は別入力にする。
- `AvailableDataNum=0`はエラーではなく正常な空データとする。
- 前段、DLL Wrapper、Parserのエラーを後段のローカルエラーで上書きしない。
- LabVIEWの`Format Into String`ではI64も`%d`で表示し、`%lld`は使用しない。
- すべてのCaseで出力トンネルを明示配線し、`Use default if unwired`を使用しない。

---

## 10.2 関連ファイルと責務

```text
30_RAMScope\
├─ 00_Common\
│  ├─ RAMScope_Byte_Order.ctl
│  ├─ RAMScope_Channel.ctl
│  ├─ RAMScope_Packet.ctl
│  └─ RAMScope_PoC_State.ctl
├─ 10_DLL_Wrapper\
│  ├─ RS_DLL_GT150GetBufferDataNum.vi
│  └─ RS_DLL_GT150GetBufferData.vi
├─ 20_Parser\
│  └─ RAMScope_Parse_Buffer.vi
├─ 30_Public_API\
│  └─ RAMScope_Read.vi
└─ 40_PoC\
   └─ PoC_RAMScope_Main.vi
```

| VI | 責務 |
|---|---|
| `RS_DLL_GT150GetBufferDataNum.vi` | 表示Bufferに現在存在するPacket数を取得する |
| `RS_DLL_GT150GetBufferData.vi` | 指定Packet数以下を事前確保済みU8配列へ取得する |
| `RAMScope_Parse_Buffer.vi` | U8配列をChannel値、Flag、Timestampを持つPacket配列へ変換する |
| `RAMScope_Read.vi` | 件数取得、要求数決定、Buffer保護、取得、切り詰め、解析、整合性確認を統括する |
| `PoC_RAMScope_Main.vi` | 公開APIの実行順、状態遷移、表示、Cleanupを確認する |

---

## 10.3 `RAMScope_Read.vi` 最終仕様

<!-- generated-vi-diagram -->
![RAMScopeRead.vi 入出力イメージ](./assets/vi-diagrams/ramscoperead.svg)

### 10.3.1 責務

測定中の表示Bufferから取得可能Packet数を先に確認し、操作者が設定したPacket数上限とByte数上限の両方を守ってデータを取得する。取得後は実取得分だけへRaw Bufferを切り詰め、Parserへ渡し、Parserが生成したPacket数とAPIの`DataNum`を照合する。

旧構造の次の方式は使用しない。

```text
RequestedDataNum Limitをそのまま使用
  → 先にBuffer Byte Sizeを計算
  → GetBufferData
```

最終構造は次のとおり。

```text
前段error確認
  → 入力検証
  → GetBufferDataNum
  → Wrapper error確認
  → AvailableDataNum負数確認
  → RequestedDataNum決定
  → 0件正常終了
  → I64 Bufferサイズ検証
  → GetBufferData
  → Wrapper error確認
  → DataNum範囲確認
  → Raw Buffer切り詰め
  → Parser
  → Parser error確認
  → Parsed Packet Count照合
  → Error_To_TestStatus.vi
```

### 10.3.2 フロントパネル端子

#### 入力

| 端子 | 型 | 説明 |
|---|---|---|
| `UnitNo` | I32 | 対象Unit番号。通常0 |
| `MdlNo`または`MdlNo_RAM` | I32 | `RAMScope_Init.vi`が返すRAMモジュール番号 |
| `RequestedDataNum Limit` | I32 | 1回のReadで要求できるPacket数上限 |
| `Channel List` | `RAMScope_Channel.ctl[]` | SetMeasChへ渡したものと同じ順序の配列 |
| `Byte Order` | `RAMScope_Byte_Order.ctl` | ParserのEndian指定 |
| `Max Buffer Bytes` | I64 | 1回のReadで確保を許可するByte数上限 |
| `error in` | error cluster | 前段の標準error cluster |

#### 出力

| 端子 | 型 | 説明 |
|---|---|---|
| `AvailableDataNum` | I32 | GetBufferDataNumが返した取得可能Packet数 |
| `RequestedDataNum` | I32 | Limit適用後にGetBufferDataへ要求したPacket数 |
| `Raw Buffer` | U8[] | 実取得分へ切り詰めたU8配列 |
| `DataNum` | I32 | GetBufferDataが返した実取得Packet数 |
| `LostDataNum` | I32 | APIが返した欠落Packet数 |
| `Packets` | `RAMScope_Packet.ctl[]` | Parserが生成したPacket配列 |
| `Parsed Packet Count` | I32 | Parserが生成したPacket数 |
| `Unused Byte Count` | I32 | Parserが未使用として残したByte数 |
| `Status` | `Status.ctl` | TestStand判定用 |
| `TestError` | `TestError.ctl` | 装置エラー情報 |
| `error out` | error cluster | 最終error |

### 10.3.3 数値型ルール

```text
Packet数
  AvailableDataNum          I32
  RequestedDataNum Limit   I32
  RequestedDataNum         I32
  DataNum                  I32
  LostDataNum              I32

Byte数
  Packet Size              I64
  Required Bytes           I64
  Actual Bytes             I64
  Max Buffer Bytes         I64
```

`RequestedDataNum`はI32のまま決定し、Bufferサイズ計算へ分岐した後だけI64へ変換する。

```text
AvailableDataNum I32 ───────────────┐
                                    ├─ Min & Max → RequestedDataNum I32
RequestedDataNum Limit I32 ─────────┘

RequestedDataNum I32
  ├─ GetBufferDataのpDataNum入力
  ├─ DataNum範囲比較
  └─ To I64 → Required Bytes計算
```

### 10.3.4 外側の前段error Case

`error in.status`を最外周Case Structureのselectorへ接続する。

#### Trueケース `error in.status=True`

- DLL Wrapperを呼ばない。
- Parserを呼ばない。
- 元の`error in`をそのまま最終error経路へ返す。
- 配列出力は空配列、数値出力は0を安全値とする。

#### Falseケース `error in.status=False`

入力検証へ進む。

### 10.3.5 入力検証

```text
ChNum = Array Size(Channel List)

Input Valid?
= ChNum >= 1
  AND RequestedDataNum Limit > 0
  AND MdlNo >= 0
  AND Max Buffer Bytes > 0
```

`UnitNo=0`は有効になり得るため、`UnitNo>0`を条件にしない。

#### Falseケース `Input Valid?=False`

```text
status = True
code   = -700166
source = RAMScope_Read.vi: Input is invalid. ChNum=%d, RequestedDataNumLimit=%d, MdlNo=%d, MaxBufferBytes=%d
```

`Format Into String`入力順：

1. ChNum I32
2. RequestedDataNum Limit I32
3. MdlNo I32
4. Max Buffer Bytes I64

Bundle By Nameの基準クラスタは、このCaseへ入った正常なerror clusterとする。

#### Trueケース `Input Valid?=True`

`RS_DLL_GT150GetBufferDataNum.vi`へ進む。

### 10.3.6 `GetBufferDataNum`の呼出し

```text
UnitNo  → RS_DLL_GT150GetBufferDataNum.vi / UnitNo
MdlNo   → RS_DLL_GT150GetBufferDataNum.vi / MdlNo
error   → RS_DLL_GT150GetBufferDataNum.vi / error in
```

Wrapper出力：

```text
AvailableDataNum I32
API ReturnCode I32
error out
```

Wrapper直後に`error out.status` Caseを置く。

- Trueケース：Wrapper errorをそのまま返す。ローカルエラーを作らない。
- Falseケース：AvailableDataNumの検証へ進む。

### 10.3.7 `AvailableDataNum`負数確認

```text
AvailableDataNum < 0 ?
```

#### Trueケース

```text
status = True
code   = -700162
source = RAMScope_Read.vi: AvailableDataNum must not be negative. UnitNo=%d, MdlNo=%d, AvailableDataNum=%d
```

入力順：UnitNo、MdlNo、AvailableDataNum。基準クラスタはGetBufferDataNum Wrapperの正常な`error out`。

#### Falseケース

`RequestedDataNum`を決定する。

### 10.3.8 `RequestedDataNum`の決定

```text
RequestedDataNum
= min(max(AvailableDataNum, 0), RequestedDataNum Limit)
```

負数は直前でエラー化しているため、実装上は次でも同値になる。

```text
RequestedDataNum
= min(AvailableDataNum, RequestedDataNum Limit)
```

Min & Maxの入力と出力はI32のまま維持する。

### 10.3.9 0件の正常終了

```text
RequestedDataNum == 0 ?
```

#### Trueケース

GetBufferDataとParserを呼ばず、正常な空データを返す。

```text
AvailableDataNum       = 0
RequestedDataNum       = 0
Raw Buffer             = 空U8[]
DataNum                = 0
LostDataNum            = 0
Packets                = 空配列
Parsed Packet Count    = 0
Unused Byte Count      = 0
error                  = 正常
```

#### Falseケース

Bufferサイズ計算へ進む。

### 10.3.10 Packet SizeとRequired Bytes

掛け算の前にI64へ変換する。

```text
Packet Size I64
= I64(ChNum) × I64(4) + I64(12)

Required Bytes I64
= I64(RequestedDataNum) × Packet Size I64
```

Buffer不正条件：

```text
BufferSizeInvalid?
= Required Bytes <= 0
  OR Required Bytes > Max Buffer Bytes
  OR Required Bytes > 2147483647
```

#### Trueケース

```text
status = True
code   = -700163
source = RAMScope_Read.vi: Required buffer size is invalid or exceeds the limit. RequiredBytes=%d, MaxBufferBytes=%d, RequestedDataNum=%d, PacketSize=%d
```

入力順：

1. Required Bytes I64
2. Max Buffer Bytes I64
3. RequestedDataNum I32
4. Packet Size I64

LabVIEWではI64にも`%d`を使用する。

#### Falseケース

検証済みの`Required Bytes`だけをI32へ変換し、`Buffer Byte Size`としてGetBufferData Wrapperへ渡す。

### 10.3.11 `GetBufferData`の呼出し

```text
UnitNo                  → RS_DLL_GT150GetBufferData.vi / UnitNo
MdlNo                   → RS_DLL_GT150GetBufferData.vi / MdlNo
RequestedDataNum I32    → / RequestedDataNum
I32(Required Bytes)     → / Buffer Byte Size
正常error               → / error in
```

Wrapper出力：

```text
Allocated Raw Buffer U8[]
DataNum I32
LostDataNum I32
API ReturnCode I32
error out
```

Wrapper直後に`error out.status` Caseを置く。

- Trueケース：Wrapper errorをそのまま返す。
- Falseケース：DataNum範囲確認へ進む。

### 10.3.12 `DataNum`範囲確認

```text
Returned Count Valid?
= DataNum >= 0
  AND DataNum <= RequestedDataNum
```

#### Falseケース

```text
status = True
code   = -700164
source = RAMScope_Read.vi: DataNum is outside the requested range. DataNum=%d, RequestedDataNum=%d, AvailableDataNum=%d
```

入力順：DataNum、RequestedDataNum、AvailableDataNum。基準クラスタはGetBufferData Wrapperの正常な`error out`。

#### Trueケース

実取得分へRaw Bufferを切り詰める。

### 10.3.13 Raw Buffer切り詰めとParser

```text
Actual Bytes I64
= I64(DataNum) × Packet Size I64
```

前段で`DataNum <= RequestedDataNum`とRequired Bytes上限を確認済みのため、Actual Bytesは安全にI32へ変換できる。

```text
Array Subset
  array  = Allocated Raw Buffer
  index  = 0
  length = I32(Actual Bytes)
```

切り詰め後のRaw Bufferを次の両方へ接続する。

```text
RAMScope_Read.vi / Raw Buffer出力
RAMScope_Parse_Buffer.vi / Raw Buffer
```

Parser入力：

```text
Raw Buffer
DataNum
Channel List
Byte Order
GetBufferData後の正常error
```

Parser直後に`error out.status` Caseを置く。

- Trueケース：Parser errorをそのまま返す。
- Falseケース：Parsed Packet Countを照合する。

APIが要求数より少ない`DataNum=0`を返す可能性を許容する場合、Parser前に`DataNum==0` Caseを追加し、空データとして正常終了させてもよい。

### 10.3.14 Parser件数照合

```text
Parsed Packet Count == DataNum ?
```

#### Falseケース

```text
status = True
code   = -700165
source = RAMScope_Read.vi: Parsed packet count does not match DataNum. ParsedPacketCount=%d, DataNum=%d, UnusedByteCount=%d
```

入力順：Parsed Packet Count、DataNum、Unused Byte Count。基準クラスタはParserの正常な`error out`。

#### Trueケース

Parser出力と正常errorをそのまま返す。

### 10.3.15 エラーコード一覧

| code | 条件 |
|---:|---|
| `-700166` | Read入力が不正 |
| `-700162` | AvailableDataNumが負数 |
| `-700163` | Required Bytesが不正または上限超過 |
| `-700164` | DataNumが要求範囲外 |
| `-700165` | Parsed Packet CountとDataNumが不一致 |

前段、GetBufferDataNum Wrapper、GetBufferData Wrapper、Parserが返したエラーは、上表のローカルエラーで置き換えない。

### 10.3.16 全Caseの安全出力

すべてのCaseで次の出力トンネルを明示配線する。

```text
AvailableDataNum
RequestedDataNum
Raw Buffer
DataNum
LostDataNum
Packets
Parsed Packet Count
Unused Byte Count
error
```

エラーまたはバイパス側では、取得済みの診断値を残す必要がある場合を除き、空配列と0を安全値として使用する。

### 10.3.17 単体試験

1. 前段errorを入力し、code/sourceが変わらない。
2. Channel List空で`-700166`。
3. RequestedDataNum Limit=0で`-700166`。
4. MdlNo=-1で`-700166`。
5. Max Buffer Bytes=0で`-700166`。
6. AvailableDataNum<0で`-700162`。
7. AvailableDataNum=0で正常な空出力。
8. AvailableDataNumがLimitより多いときRequestedDataNum=Limit。
9. AvailableDataNumがLimitより少ないときRequestedDataNum=AvailableDataNum。
10. Required Bytes上限超過で`-700163`、GetBufferData未実行。
11. DataNum<0またはDataNum>RequestedDataNumで`-700164`。
12. Parser errorをローカルエラーで上書きしない。
13. Parsed Packet Count不一致で`-700165`。
14. 正常時に`Parsed Packet Count=DataNum`。

---

## 10.4 `PoC_RAMScope_Main.vi` 通信確認用の最終作成手順

<!-- generated-vi-diagram -->
![PoCRAMScopeMain.vi 入出力イメージ](./assets/vi-diagrams/pocramscopemain.svg)

### 10.4.1 目的と実行順

```text
Connect
  → Init
  → Set Cond
  → Log Start
  → Wait
  → Read
  → Log Stop
  → Release
  → Close
```

本VIでは測定中の表示Bufferを短時間取得し、DLL通信、Buffer取得、Packet解析、状態遷移、Cleanupを確認する。停止後の保存ログ回収、MeasNo／BlockNo列挙、TDMS保存は`PoC_RAMScope_Logging_Main.vi`へ分離する。

### 10.4.2 状態typedef

```text
30_RAMScope\00_Common\RAMScope_PoC_State.ctl
```

| フィールド | 初期値 | Trueの意味 |
|---|---:|---|
| `Connected?` | False | Connectが正常終了した |
| `Measurement Started?` | False | Log Startが正常終了した履歴がある |
| `Stopped?` | False | 通常またはCleanup Stopが正常終了した |
| `Released?` | False | Releaseが正常終了した |
| `File Open?` | False | 通信確認PoCでは予約項目としてFalseを維持する |

```text
Measurement Active?
= Measurement Started? AND NOT Stopped?
```

### 10.4.3 フロントパネル入力

| 入力 | 型 | 推奨初期値または用途 |
|---|---|---|
| `UnitNo` | I32 | 0 |
| `Byte Order` | typedef | 実機仕様に合わせる |
| `Meas Config` | typedef | PoC測定条件 |
| `Channel List` | typedef[] | 1要素以上 |
| `Module Log Configs` | typedef[] | Set Cond用 |
| `RequestedDataNum Limit` | I32 | 1回のReadで要求するPacket数上限 |
| `Max Buffer Bytes` | I64 | 1回のReadで確保を許可するByte数上限 |
| `Wait Time` | U32 | Start後からReadまでの待機時間ms |
| `error in` | error cluster | 標準error cluster |

旧`MaxDataNum`制御器がある場合は、ラベルを`RequestedDataNum Limit`へ変更し、I32のままReadの同名端子へ接続する。

`Max Buffer Bytes`は新規I64制御器として作成する。PoC初期値例は次のとおり。

```text
268435456 byte
= 256 MiB
```

役割を混同しない。

```text
RequestedDataNum Limit I32
  = 操作者が設定するPacket数上限

Max Buffer Bytes I64
  = 操作者が設定するByte数上限

Required Bytes I64
  = RAMScope_Read.vi内部で計算する実必要Byte数
```

### 10.4.4 フロントパネル出力

| 出力 | 生成元 |
|---|---|
| `UnitNum`、`kind` | `RAMScope_Connect.vi` |
| `Module List`、`MdlNo_RAM`、`MdlNo_CAN`、`Endian_RAM` | `RAMScope_Init.vi` |
| `AvailableDataNum`、`RequestedDataNum`、`Raw Buffer`、`DataNum`、`LostDataNum`、`Packets` | `RAMScope_Read.vi` |
| `Final State` | Cleanup後State |
| `Status`、`TestError`、`error out` | 最後のClose Case |

### 10.4.5 通常経路の配線

#### Connect

```text
error in → RAMScope_Connect.vi / error in
RAMScope_Connect.vi / UnitNum → PoC UnitNum
RAMScope_Connect.vi / kind    → PoC kind
```

```text
Connected?
= NOT(RAMScope_Connect.vi.error out.status)
```

Initial StateをBundle By Nameの基準クラスタとし、`Connected?`だけを更新する。

#### Init

```text
RAMScope_Connect.vi / error out
  → RAMScope_Init.vi / error in
```

```text
RAMScope_Init.vi / MdlNo_RAM
  ├─→ PoC MdlNo_RAM
  ├─→ RAMScope_Set_Cond.vi / MdlNo_RAM
  └─→ RAMScope_Read.vi / MdlNo_RAMまたはMdlNo
```

`Endian_RAM` I32をByte Order typedefへ自動変換していない場合、Readにはフロントパネルの`Byte Order`を接続する。

#### Set Cond

```text
RAMScope_Init.vi / error out
  → RAMScope_Set_Cond.vi / error in
```

Set Condへ渡したものと同じ`Channel List`を同じ順序でReadへ接続する。

#### Log StartとWait

Flat Sequence Structureを2フレームで配置する。

```text
Frame 0：RAMScope_Log_Start.vi
Frame 1：Wait (ms)
```

```text
Measurement Started?
= Connected?
  AND NOT(RAMScope_Log_Start.vi.error out.status)
```

Waitにはerror端子がないため、Flat Sequence Structureで`Start完了 → Wait完了 → Read開始`を保証する。

### 10.4.6 Readの全入力配線

```text
PoC UnitNo I32
  → RAMScope_Read.vi / UnitNo

RAMScope_Init.vi / MdlNo_RAM I32
  → RAMScope_Read.vi / MdlNo_RAM
  または実端子名がMdlNoの場合は / MdlNo

PoC RequestedDataNum Limit I32
  → RAMScope_Read.vi / RequestedDataNum Limit

PoC Max Buffer Bytes I64
  → RAMScope_Read.vi / Max Buffer Bytes

PoC Channel List
  → RAMScope_Read.vi / Channel List

PoC Byte Order
  → RAMScope_Read.vi / Byte Order

Flat Sequence出力error
  → RAMScope_Read.vi / error in
```

#### `Max Buffer Bytes`制御器の追加手順

1. `RAMScope_Read.vi / Max Buffer Bytes`端子を右クリックする。
2. `作成 → 制御器`を選ぶ。
3. ラベルを`Max Buffer Bytes`とする。
4. 表現形式がI64であることを確認する。
5. 0より大きい値を設定する。
6. 制御器からReadの同名端子へ直接I64ワイヤで接続する。
7. I32へ変換しない。
8. `RequestedDataNum Limit`のワイヤを分岐して接続しない。
9. DLL Wrapperの`Buffer Byte Size`へPoCから直接接続しない。
10. `Max Buffer Bytes`をGetBufferDataNum、RequestedDataNumまたはpDataNumへ接続しない。

### 10.4.7 Readの出力配線

```text
RAMScope_Read.vi
├─ AvailableDataNum ─→ PoC AvailableDataNum
├─ RequestedDataNum ─→ PoC RequestedDataNum
├─ Raw Buffer ───────→ PoC Raw Buffer
├─ DataNum ──────────→ PoC DataNum
├─ LostDataNum ──────→ PoC LostDataNum
└─ Packets ──────────→ PoC Packets
```

これらのワイヤをStop、Release、Cleanup、Close Caseへ通さない。Readの右側で各表示器へ直接接続する。

正常時の件数関係：

```text
0 <= DataNum
DataNum <= RequestedDataNum
RequestedDataNum <= RequestedDataNum Limit
RequestedDataNum <= AvailableDataNum
```

### 10.4.8 通常StopとRelease

```text
RAMScope_Read.vi / error out
  → RAMScope_Log_Stop.vi / error in
```

```text
Stopped?
= Measurement Started?
  AND NOT(RAMScope_Log_Stop.vi.error out.status)
```

Release条件：

```text
Need Release?
= Stopped? AND NOT Released?
```

FalseケースはStateとerrorをそのまま通す。Trueケースでは`RAMScope_Release.vi`を呼び、正常終了時だけ`Released?`をTrueへ更新する。

### 10.4.9 Cleanup

通常経路の最後のerrorを分岐し、`Original Error`として保持する。

Cleanup Stop条件：

```text
Need Cleanup Stop?
= Measurement Started? AND NOT Stopped?
```

Cleanup Release条件：

```text
Need Cleanup Release?
= Stopped? AND NOT Released?
```

各Cleanup APIへ渡すerrorだけをClear Errorsする。Merge Errorsの上側へCleanup前のerror、下側へCleanup API errorを接続し、最初のエラーを保持する。

```text
Original Error ─────────────→ Merge Errors 上側
Clear Errors → Cleanup API ─→ Merge Errors 下側
```

### 10.4.10 Close Case

```text
Need Device Close?
= Connected?
```

Close Caseには次の4出力トンネルを作る。

```text
Final State
Status
TestError
Final Error
```

#### Falseケース `Connected?=False`

`RAMScope_Close.vi`を呼ばない。入力StateをFinal Stateへ通し、入力errorを`Error_To_TestStatus.vi`へ接続してStatus、TestError、Final Errorを作る。Device Nameは文字列全文`RAMScope`とする。

#### Trueケース `Connected?=True`

入力StateをFinal Stateへ通し、入力errorを`RAMScope_Close.vi / error in`へ接続する。CloseのStatus、TestError、error outを各出力トンネルへ接続する。このCase内ではClear Errorsを追加しない。

TrueとFalseの両ケースで4出力トンネルをすべて配線する。

### 10.4.11 PoC全体見取り図

```text
RAMScope_Connect.vi
├─ UnitNum ───────────────────────────→ PoC UnitNum
└─ kind ──────────────────────────────→ PoC kind

RAMScope_Init.vi
├─ Module List ───────────────────────→ PoC Module List
├─ MdlNo_RAM ─┬──────────────────────→ PoC MdlNo_RAM
│             ├──────────────────────→ RAMScope_Set_Cond.vi
│             └──────────────────────→ RAMScope_Read.vi
├─ MdlNo_CAN ─────────────────────────→ PoC MdlNo_CAN
└─ Endian_RAM ────────────────────────→ PoC Endian_RAM

PoC RequestedDataNum Limit I32
  ───────────────────────────────────→ RAMScope_Read.vi

PoC Max Buffer Bytes I64
  ───────────────────────────────────→ RAMScope_Read.vi

RAMScope_Read.vi
├─ AvailableDataNum ──────────────────→ PoC AvailableDataNum
├─ RequestedDataNum ──────────────────→ PoC RequestedDataNum
├─ Raw Buffer ────────────────────────→ PoC Raw Buffer
├─ DataNum ───────────────────────────→ PoC DataNum
├─ LostDataNum ───────────────────────→ PoC LostDataNum
└─ Packets ───────────────────────────→ PoC Packets

Cleanup後State/error
  → Close Case
      ├─ Final State ─────────────────→ PoC Final State
      ├─ Status ──────────────────────→ PoC Status
      ├─ TestError ───────────────────→ PoC TestError
      └─ Final Error ─────────────────→ PoC error out
```

### 10.4.12 PoC試験

#### Connect失敗

全State=False。Init以降、Stop、Release、Closeを実行しない。

#### Connect成功、Init失敗

`Connected?=True`。StopとReleaseは実行せず、Closeだけを実行する。

#### Log Start失敗

`Measurement Started?=False`。StopとReleaseは実行せず、Closeを実行する。

#### Log Start成功後、Read失敗

Cleanup Stopを実行する。Stop成功時はCleanup Releaseを実行し、最後にCloseする。Final ErrorにはReadのOriginal Errorを保持する。

#### AvailableDataNum=0

```text
AvailableDataNum = 0
RequestedDataNum = 0
DataNum          = 0
Raw Buffer       = 空配列
Packets          = 空配列
error            = 正常
```

#### LimitよりAvailableが多い

```text
AvailableDataNum       = 1000
RequestedDataNum Limit = 100
RequestedDataNum       = 100
DataNum                <= 100
```

#### LimitよりAvailableが少ない

```text
AvailableDataNum       = 20
RequestedDataNum Limit = 100
RequestedDataNum       = 20
DataNum                <= 20
```

#### Max Buffer Bytes超過

`Required Bytes > Max Buffer Bytes`となる条件を作る。GetBufferDataを呼ばず、巨大配列を確保せず、`-700163`を返し、必要なCleanupを実行する。

---

## 10.5 完成チェックリスト

### Read

- [ ] `RequestedDataNum Limit`がI32である。
- [ ] `Max Buffer Bytes`がI64である。
- [ ] RequestedDataNumはI32のまま決定している。
- [ ] Byte計算へ分岐した後だけRequestedDataNumをI64化している。
- [ ] Packet SizeとRequired Bytesを掛け算前からI64で計算している。
- [ ] Required Bytes検証後だけI32へ変換している。
- [ ] GetBufferDataNum、GetBufferData、Parserの各直後にerror.status Caseがある。
- [ ] AvailableDataNum=0を正常な空データとして扱う。
- [ ] `0 <= DataNum <= RequestedDataNum`を確認している。
- [ ] Raw BufferをActual Bytesへ切り詰めてからParserへ渡している。
- [ ] Parsed Packet CountとDataNumを照合している。
- [ ] `-700166`、`-700162`、`-700163`、`-700164`、`-700165`のsource全文がある。
- [ ] I64のFormat Into Stringにも`%d`を使用している。
- [ ] 全Caseの全出力トンネルを明示配線している。

### PoC

- [ ] 旧`MaxDataNum`を`RequestedDataNum Limit`へ改名している。
- [ ] `Max Buffer Bytes` I64制御器を新規作成している。
- [ ] `Max Buffer Bytes`をReadの同名端子へ直接接続している。
- [ ] `RequestedDataNum Limit`と`Max Buffer Bytes`を同じワイヤで接続していない。
- [ ] DLL Wrapperの`Buffer Byte Size`へPoCから直接配線していない。
- [ ] UnitNo、MdlNo_RAM、Channel List、Byte OrderをReadへ接続している。
- [ ] AvailableDataNumとRequestedDataNumの表示器がある。
- [ ] Raw Buffer、DataNum、LostDataNum、PacketsをRead出力へ直接接続している。
- [ ] Connected?、Measurement Started?、Stopped?、Released?を各APIの成功結果から更新している。
- [ ] Original ErrorをCleanup Errorより優先している。
- [ ] Close Caseの両側でFinal State、Status、TestError、Final Errorを配線している。
- [ ] 正常終了後と異常終了後の両方で再Connectを確認している。

本章へ今後修正を加える場合も、対象VIの既存節へ直接統合する。差分だけを別Markdownへ追加しない。
