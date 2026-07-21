# 10-04. Parser VIの個別作成手順

**監査日：2026-07-18**

詳細な関数配置と端子配線は[復元したParser個別手順](./10B4_RAMScope_Parser_VI作成手順.md)を参照する。本書は、なぜParser、Case Structure、Forループ、Shift Registerが必要なのかと、現行の確定仕様を補正する。

---

## 1. Parserが必要な理由

DLLが返すU8配列には型情報やフィールド名がない。人が扱いたいのは、モジュール、チャンネル値、Flag、Timestamp等の意味付きデータである。

```text
DLLのU8配列
  → バイト位置とEndianを仕様で解釈
  → 数値へ変換
  → typedefクラスタへ格納
```

ParserをDLL Wrapperから分離すると、GT170がなくてもダミーU8配列で解析ロジックを検証できる。

---

## 2. 数値変換VI

| VI | 入力 | 出力 | 構造 |
|---|---|---|---|
| `U8x4_To_U32.vi` | U8[4]、Byte Order | U32 | error Case、サイズCase、Endian Case、Join Numbers |
| `U8x4_To_I32.vi` | U8[4]、Byte Order | I32 | U32変換後にType Cast |
| `U8x8_To_U64.vi` | U8[8]、Byte Order | U64 | サイズCase、4byte分割、上下U32結合 |

### 2.1 U8x4サイズエラー

```text
U8x4_To_U32.vi: Input size must be 4. Actual=%d
```

```text
%d ← Array Size(Bytes) I32
status=True
code=I32 -700101
source=Format Into String出力
基準クラスタ=サイズ判定Caseへ入った正常error
```

### 2.2 U8x8サイズエラー

```text
U8x8_To_U64.vi: Input size must be 8. Actual=%d
```

```text
%d ← Array Size(Bytes) I32
status=True
code=I32 -700102
source=Format Into String出力
```

---

## 3. `Parse_SYSINFO_Array.vi`

### 3.1 入力データの実体

SYSINFO Rawは60byteのレコード16個を連結したU8[960]である。

```text
Record Start = Record Index × 60
Record 0     = index 0..59
Record 1     = index 60..119
...
Record 15    = index 900..959
```

1レコード内の主な位置：

```text
0  module
4  module_type
8  probe_id
12 interface_id
16 version
20 addinfo
24 endian
28 probe_version
32 security_id_req
36 security_id_size
40 flash_enable
44 name[16]
```

### 3.2 出力モデル

- `Module List`は`RAMScope_Module_Info.ctl[16]`。
- `MdlNo_RAM`、`MdlNo_CAN`、`Endian_RAM`は最初に検出した対象モジュールの値。
- `Connected? = module_type != 0x0F`。

### 3.3 アルゴリズムと構造選定

```text
if error in.status:
    安全出力、元エラー
elif Array Size(SYSINFO Raw) != 960:
    -700120
else:
    MdlNo_RAM=-1、MdlNo_CAN=-1、Endian_RAM=0で初期化
    for Record Index 0..15:
        Raw全体から60byteを切り出す
        各4byteをI32へ変換
        NameのNULL終端前を文字列化
        Module Infoを作る
        未検出かつRAMならMdlNo_RAMとEndianを保持
        未検出かつCANならMdlNo_CANを保持
```

Forループ入力ではSYSINFO Rawの自動指標付けを無効にする。毎反復でU8単体を受け取るのではなく、U8[960]全体から任意位置を切り出す必要があるためである。

MdlNo_RAM、MdlNo_CAN、Endian_RAM、errorにはShift Registerを使用する。Falseケースで初期値へ戻さず、左内側の現在値を右内側へ渡す。

### 3.4 サイズエラー

```text
Parse_SYSINFO_Array.vi: SYSINFO Raw size must be 960. Actual=%d
```

```text
%d ← Array Size(SYSINFO Raw) I32
status=True
code=I32 -700120
source=Format Into String出力
```

### 3.5 確定コード

```text
module_type=0x00 → RAM
module_type=0x02 → CAN
module_type=0x03 → Analog
module_type=0x0E → Power Communication
module_type=0x0F → Disconnected

endian=0 → Big Endian
endian=1 → Little Endian
```

### 3.6 単体テスト

U8[960]をInitialize Arrayで作り、Replace Array Subsetを直列接続して次を入れる。

```text
Record 0: module=0、module_type=0x00、endian=0、name=RAM0
Record 1: module=1、module_type=0x02、name=CAN0
Record 2..15: module_type=0x0F
```

期待：Module List=16、MdlNo_RAM=0、MdlNo_CAN=1、Endian_RAM=0、両Found=True。959byte、RAMなし、既存errorも確認する。

---

## 4. `RAMScope_Parse_Buffer.vi`

### 4.1 入力データの実体

```text
Raw Buffer
├─ Packet 0
│  ├─ Channel 0 : 4byte
│  ├─ Channel 1 : 4byte
│  ├─ ...
│  ├─ Flag      : 4byte
│  └─ Timestamp : 8byte
├─ Packet 1
└─ ...
```

```text
Packet Size         = 4 × ChNum + 12
Expected Byte Count = Packet Size × DataNum
Packet Start        = Packet Index × Packet Size
Value Start         = Packet Start + Channel Index × 4
Flag Start          = Packet Start + 4 × ChNum
Timestamp Start     = Flag Start + 4
```

### 4.2 出力データモデル

`Packets`は`RAMScope_Packet.ctl`の一次元配列である。1Packetクラスタ内にChannel Values配列、Flag、Timestamp Raw、Timestamp Secondsを持つ。

### 4.3 前提条件と多段Case

```text
error in.status?
├─ True  → 空Packets、0、0、元エラー
└─ False
    Input Valid? = ChNum>=1 AND DataNum>=0
    ├─ False → -700130
    └─ True
        Raw Buffer Sufficient? = Actual>=Expected
        ├─ False → -700131
        └─ True
            DataNum == 0?
            ├─ True  → 空Packets、正常
            └─ False → Packet解析
```

Caseを分ける理由は、どの前提で解析を中止したかをsourceとcodeで特定し、配列範囲外アクセスを防ぐためである。

### 4.4 ループ構造

- 外側ForループはDataNum個のPacketを処理する。N=DataNum。
- 内側ForループはChannel Listを自動指標付けし、1反復で1チャンネルを処理する。Nは未配線。
- 内側反復端子も画面上は`i`だが、資料では外側iと区別してChannel Indexとして説明する。
- Packet出力は外側Forループの条件付き指標付けを使う。`Append Packet?=NOT(最終error.status)`とし、途中エラーPacketを配列へ追加しない。

### 4.5 入力不正エラー

```text
RAMScope_Parse_Buffer.vi: ChNum must be >= 1 and DataNum must be >= 0. ChNum=%d, DataNum=%d
```

```text
1個目の%d ← ChNum I32
2個目の%d ← DataNum I32
status=True
code=I32 -700130
```

### 4.6 Raw Buffer不足エラー

```text
RAMScope_Parse_Buffer.vi: Raw Buffer is too small. Expected=%d, Actual=%d
```

```text
1個目の%d ← Expected Byte Count I32
2個目の%d ← Actual Byte Count I32
status=True
code=I32 -700131
```

`Expected=20`、`Actual=20`なら`Actual >= Expected=True`なので、Trueケース（Raw Buffer十分）へ進む。Falseケースへエラー生成回路を置かない。

### 4.7 Timestamp

```text
Timestamp Seconds = DBL(Timestamp Raw) × DBL定数20e-9
```

20nsは作業仮定ではなくベンダー資料で確定した仕様である。

### 4.8 単体テスト

Channel Listは2要素。

```text
Channel 0: Name=Unsigned、Sign=0、Scale=1、Offset=0
Channel 1: Name=Signed、Sign=1、Scale=1、Offset=0
```

Raw Buffer 20byte：

```text
01 00 00 00                    Channel 0 = 1
FE FF FF FF                    Channel 1 = -2
A5 00 00 00                    Flag = 0xA5
32 00 00 00 00 00 00 00       Timestamp Raw = 50
```

期待：Parsed Packet Count=1、Unused=0、Value=1/-2、Flag=165、Timestamp Raw=50、Timestamp Seconds=1e-6、error正常。

追加でChannel List空、DataNum=-1、19byte不足、DataNum=0、既存errorを確認する。
