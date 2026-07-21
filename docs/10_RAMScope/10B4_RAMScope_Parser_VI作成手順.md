# 10B-4. RAMScope Parser VI 作成手順

> **本章の役割**：`GetSysInfo`が返すU8[960]と、`GetBufferData`が返す測定バッファを、LabVIEWで扱いやすいクラスタ配列へ変換する手順を説明する。
>
> 構造体生成は [10B-3](./10B3_RAMScope_構造体生成VI作成手順.md)、DLLラッパは [10B-2](./10B2_RAMScope_DLLラッパVI_CLFN配線手順.md) を参照する。
>
> `SYSINFO`の構造は`docs/reference/RAMScopeVP.h`、モジュール種別と上限値は`docs/reference/GTHard.h`を正とする。

**最終整理日：2026-07-15**

---

# 1. 作成するファイル

```text
30_RAMScope\
├─ 00_Common\
│  ├─ RAMScope_Module_Info.ctl
│  ├─ RAMScope_Channel_Value.ctl
│  ├─ RAMScope_Packet.ctl
│  ├─ RAMScope_Byte_Order.ctl
│  ├─ U8x4_To_I32.vi
│  ├─ U8x4_To_U32.vi
│  └─ U8x8_To_U64.vi
│
└─ 20_Parser\
   ├─ Parse_SYSINFO_Array.vi
   └─ RAMScope_Parse_Buffer.vi
```

Parser VIはDLLを呼ばない。入力された生バイト列だけを処理する純粋処理とし、実機なしで単体テストできる構成にする。

---

# 2. 共通typedefを作成する

---

## 2.1 `RAMScope_Byte_Order.ctl`

1. 新規カスタム制御器を作成する。
2. Enumを配置する。
3. 次の2項目を登録する。

```text
Little Endian
Big Endian
```

4. typedefへ変更する。
5. `30_RAMScope\00_Common\RAMScope_Byte_Order.ctl`として保存する。

初期PoCは`Little Endian`で開始し、純正RAMScopeVP表示または既知RAM値と比較して確定する。

---

## 2.2 `RAMScope_Module_Info.ctl`

`SYSINFO`1レコードをLabVIEWクラスタへ変換した型。

| フィールド | 型 | 元フィールド |
|---|---|---|
| `Record Index` | I32 | U8[960]内の0..15 |
| `ModuleNo` | I32 | `SYSINFO.module` |
| `Module Type` | I32 | `SYSINFO.module_type` |
| `Probe ID` | I32 | `SYSINFO.probe_id` |
| `Interface ID` | I32 | `SYSINFO.interface_id` |
| `Version` | I32 | `SYSINFO.version` |
| `AddInfo` | I32 | `SYSINFO.addinfo` |
| `Endian` | I32 | `SYSINFO.endian` |
| `Probe Version` | I32 | `SYSINFO.probe_version` |
| `Security ID Required` | I32 | `SYSINFO.security_id_req` |
| `Security ID Size` | I32 | `SYSINFO.security_id_size` |
| `Flash Enable` | I32 | `SYSINFO.flash_enable` |
| `Name` | String | `SYSINFO.name[16]` |
| `Connected?` | Boolean | `Module Type != 0x0F` |

---

## 2.3 `RAMScope_Channel_Value.ctl`

1パケット内の1チャンネル値を表す。

| フィールド | 型 | 用途 |
|---|---|---|
| `Channel Index` | I32 | Channel List内の位置 |
| `Name` | String | `RAMScope_Channel.ctl.Name` |
| `Address` | U32 | 監視アドレス |
| `Raw U32` | U32 | 受信した32bitのビット列 |
| `Value` | DBL | 符号解釈後の数値 |
| `Engineering Value` | DBL | `Value × Scale + Offset` |
| `Unit` | String | 工学単位 |

---

## 2.4 `RAMScope_Packet.ctl`

1パケット分の解析結果。

| フィールド | 型 |
|---|---|
| `Packet Index` | I32 |
| `Channel Values` | `RAMScope_Channel_Value.ctl`一次元配列 |
| `Flag` | U32 |
| `Timestamp Raw` | U64 |
| `Timestamp Seconds` | DBL |

---

# 3. U8配列を数値へ戻す共通VI

---

## 3.1 `U8x4_To_U32.vi`

### 3.1.1 フロントパネル端子

| 端子 | 方向 | 型 |
|---|---|---|
| `Bytes` | 入力 | U8一次元配列 |
| `Byte Order` | 入力 | `RAMScope_Byte_Order.ctl` |
| `error in` | 入力 | error cluster |
| `Value` | 出力 | U32 |
| `error out` | 出力 | error cluster |

### 3.1.2 配置する関数

```text
Array Size
Equal?
Case Structure
Byte Array To String
Unflatten From String
Bundle By Name
```

### 3.1.3 サイズ判定

```text
Array Size(Bytes) == 4
```

Falseの場合は`Value=0`を出力し、ローカル検証エラーを生成する。

エラーメッセージ例：

```text
U8x4_To_U32.vi: Input size must be 4. Actual=<size>
```

### 3.1.4 数値変換

1. `Bytes`を`Byte Array To String`へ接続する。
2. `Unflatten From String`を配置する。
3. type入力へU32数値定数を接続する。
4. `Byte Order`をCase Structureへ接続する。
5. Little Endianケースでは`Unflatten From String`のbyte orderへlittle-endian定数を接続する。
6. Big Endianケースではbig-endian定数を接続する。
7. unflattened dataを`Value`へ出力する。
8. `Unflatten From String`のerror outをVIのerror outへ接続する。

---

## 3.2 `U8x4_To_I32.vi`

`U8x4_To_U32.vi`を別名保存し、`Unflatten From String`のtype入力をI32へ変更する。

単体テスト：

```text
Bytes = FF FF FF FF、Little Endian
期待Value = -1
```

---

## 3.3 `U8x8_To_U64.vi`

`U8x4_To_U32.vi`を別名保存し、次を変更する。

- サイズ判定：8
- type入力：U64
- 出力型：U64

単体テスト：

```text
Bytes = 32 00 00 00 00 00 00 00、Little Endian
期待Value = 50
```

---

# 4. `Parse_SYSINFO_Array.vi`

## 4.1 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `SYSINFO Raw` | 入力 | U8一次元配列 |
| `Byte Order` | 入力 | `RAMScope_Byte_Order.ctl` |
| `error in` | 入力 | error cluster |
| `Module List` | 出力 | `RAMScope_Module_Info.ctl`一次元配列 |
| `MdlNo_RAM` | 出力 | I32、初期値-1 |
| `MdlNo_CAN` | 出力 | I32、初期値-1 |
| `Endian_RAM` | 出力 | I32、初期値0 |
| `RAM Module Found?` | 出力 | Boolean |
| `CAN Module Found?` | 出力 | Boolean |
| `error out` | 出力 | error cluster |

## 4.2 SYSINFOレコード配置

1レコード60バイト、16レコード、合計960バイト。

| フィールド | レコード内offset | 長さ |
|---|---:|---:|
| `module` | 0 | 4 |
| `module_type` | 4 | 4 |
| `probe_id` | 8 | 4 |
| `interface_id` | 12 | 4 |
| `version` | 16 | 4 |
| `addinfo` | 20 | 4 |
| `endian` | 24 | 4 |
| `probe_version` | 28 | 4 |
| `security_id_req` | 32 | 4 |
| `security_id_size` | 36 | 4 |
| `flash_enable` | 40 | 4 |
| `name[16]` | 44 | 16 |

## 4.3 ブロックダイアグラムへ配置する関数

```text
Array Size
Equal?
Case Structure
For Loop（N=16）
Multiply
Array Subset
U8x4_To_I32.vi ×11
Search 1D Array
Byte Array To String
Bundle By Name
Shift Register
Equal?
Not Equal?
Select
```

## 4.4 入力サイズを確認する

```text
Array Size(SYSINFO Raw) == 960
```

Falseの場合：

- `Module List`は空配列
- `MdlNo_RAM=-1`
- `MdlNo_CAN=-1`
- Found?はFalse
- ローカル検証エラーを出力

エラーメッセージ例：

```text
Parse_SYSINFO_Array.vi: SYSINFO size must be 960. Actual=<size>
```

## 4.5 For Loopを作る

1. For Loopを配置する。
2. N端子へI32定数16を接続する。
3. ループ反復端子`i`へ60を掛ける。
4. `Array Subset`のindexへ`i × 60`を接続する。
5. lengthへ60を接続する。
6. 出力を1レコードU8[60]として使用する。

```text
Record Start = i × 60
```

## 4.6 各I32フィールドを取得する

レコードU8[60]から`Array Subset`で4バイトずつ取得し、`U8x4_To_I32.vi`へ接続する。

例：

```text
record → Array Subset(index=0, length=4) → module
record → Array Subset(index=4, length=4) → module_type
record → Array Subset(index=24, length=4) → endian
```

11フィールドすべて同様に作成する。

## 4.7 `name[16]`を文字列へ変換する

1. `Array Subset(index=44, length=16)`でName Bytesを取得する。
2. `Search 1D Array`でU8定数0を検索する。
3. 検索結果をCase Structureへ接続する。

### 検索結果が-1

NULL終端がないため16バイトすべてを使用する。

### 検索結果が0以上

検索結果をlengthとして`Array Subset`で先頭から切り出す。

4. 切り出したU8配列を`Byte Array To String`へ接続する。
5. 出力を`Name`へ使用する。

## 4.8 Module Infoクラスタを作る

`Bundle By Name`で`RAMScope_Module_Info.ctl`へ各値を格納する。

```text
Record Index = i
ModuleNo = module
Module Type = module_type
...
Name = 変換文字列
Connected? = module_type != 0x0F
```

For Loopの出力トンネルを自動インデックスにし、`Module List`を作る。

## 4.9 RAM/CANモジュール番号を抽出する

For Loopへ次のShift Registerを追加する。

```text
MdlNo_RAM 初期値 = -1
MdlNo_CAN 初期値 = -1
Endian_RAM 初期値 = 0
```

判定値：

```text
RAM module_type = 0x00
CAN module_type = 0x02
Disconnected    = 0x0F
```

### RAM判定

```text
module_type == 0x00
AND 現在のMdlNo_RAM == -1
```

Trueなら：

```text
MdlNo_RAM = module
Endian_RAM = endian
```

FalseならShift Register値を維持する。

### CAN判定

```text
module_type == 0x02
AND 現在のMdlNo_CAN == -1
```

Trueなら`MdlNo_CAN=module`とする。

For Loop終了後：

```text
RAM Module Found? = MdlNo_RAM >= 0
CAN Module Found? = MdlNo_CAN >= 0
```

CAN未搭載はParserエラーにしない。RAM未搭載を試験停止条件にするかは`RAMScope_Init.vi`で判断する。

## 4.10 単体テスト

ダミーU8[960]を作り、レコード1へ次を格納する。

```text
module = 1
module_type = 0x00
endian = 0
name = "RAM"
```

期待結果：

```text
MdlNo_RAM = 1
RAM Module Found? = True
Name = RAM
Module List要素数 = 16
```

別レコードへ`module_type=0x02`を入れ、CAN検出も確認する。

---

# 5. `RAMScope_Parse_Buffer.vi`

## 5.1 現時点のパケット定義

RAMモニタの1パケットを次として扱う。

```text
Channel Data[0]   4byte
Channel Data[1]   4byte
...
Channel Data[N-1] 4byte
Flag              4byte
Timestamp          8byte
```

```text
Packet Size = 4 × ChNum + 12
```

Timestampは現行資料では20ns単位として扱う。実機PoCで純正RAMScopeVPまたは既知値と比較し、最終確定する。

## 5.2 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Raw Buffer` | 入力 | U8一次元配列 |
| `DataNum` | 入力 | I32 |
| `Channel List` | 入力 | `RAMScope_Channel.ctl`一次元配列 |
| `Byte Order` | 入力 | `RAMScope_Byte_Order.ctl` |
| `error in` | 入力 | error cluster |
| `Packets` | 出力 | `RAMScope_Packet.ctl`一次元配列 |
| `Parsed Packet Count` | 出力 | I32 |
| `Unused Byte Count` | 出力 | I32 |
| `error out` | 出力 | error cluster |

## 5.3 配置する関数

```text
Array Size
Multiply
Add
Greater Or Equal?
Case Structure
For Loop ×2
Array Subset
U8x4_To_U32.vi
U8x4_To_I32.vi
U8x8_To_U64.vi
Unbundle By Name
Bundle By Name
Type Cast
To Double Precision Float
Select
```

## 5.4 サイズを計算する

```text
ChNum = Array Size(Channel List)
Packet Size = 4 × ChNum + 12
Expected Byte Count = Packet Size × DataNum
Actual Byte Count = Array Size(Raw Buffer)
Unused Byte Count = Actual Byte Count - Expected Byte Count
```

入力条件：

```text
ChNum > 0
DataNum >= 0
Actual Byte Count >= Expected Byte Count
```

DataNum=0は正常として空のPacketsを返す。

ActualがExpectedより小さい場合は解析を行わずエラーにする。

エラーメッセージ例：

```text
RAMScope_Parse_Buffer.vi: Buffer is shorter than expected. Expected=<n>, Actual=<n>
```

## 5.5 外側For Loopでパケットを処理する

N端子へ`DataNum`を接続する。

```text
Packet Start = packet index × Packet Size
```

各反復で1パケットを解析する。

## 5.6 内側For Loopでチャンネル値を処理する

`Channel List`を内側For Loopへ自動インデックス入力する。

```text
Value Start = Packet Start + channel index × 4
```

1. `Array Subset`で4バイトを取得する。
2. `U8x4_To_U32.vi`でRaw U32を取得する。
3. Channel clusterを`Unbundle By Name`し、Name、Address、Sign、Scale、Offset、Unitを取得する。
4. `Sign == 0`を判定する。

### Signが0

```text
Value = U32をDBLへ変換
```

### Signが0以外

```text
Raw U32をType CastでI32へ変換
I32をDBLへ変換
```

これはビット列を維持して符号付き値として解釈するためであり、通常の数値変換でU32をI32へ丸めない。

工学値：

```text
Engineering Value = Value × Scale + Offset
```

`Bundle By Name`で`RAMScope_Channel_Value.ctl`を作り、内側For Loopの自動インデックス出力からChannel Values配列を作る。

> `Sign`コードの正式な意味はベンダー資料で確認する。初期PoCでは`0=符号なし、0以外=符号あり`として既知RAM値と照合し、相違があればマッピングを修正する。

## 5.7 Flagを解析する

```text
Flag Start = Packet Start + 4 × ChNum
```

`Array Subset(length=4)`から`U8x4_To_U32.vi`でFlagを取得する。

## 5.8 Timestampを解析する

```text
Timestamp Start = Packet Start + 4 × ChNum + 4
```

`Array Subset(length=8)`から`U8x8_To_U64.vi`でTimestamp Rawを取得する。

秒換算：

```text
Timestamp Seconds = Timestamp Raw × 20e-9
```

## 5.9 Packetクラスタを作る

`Bundle By Name`で以下を格納する。

```text
Packet Index = 外側For Loopのi
Channel Values = 内側For Loop出力
Flag
Timestamp Raw
Timestamp Seconds
```

外側For Loopの自動インデックス出力を`Packets`へ接続する。

```text
Parsed Packet Count = Array Size(Packets)
```

## 5.10 エラー伝搬

数値変換VIのerror clusterをチャンネル順、Flag、Timestampの順に直列接続する。

For Loop内でエラーが発生した場合も、次反復を無条件に実行しないよう、ループ内のCase Structureで`error status=True`なら変換をスキップしてエラーを伝播する。

最小PoCで複雑になりすぎる場合は、事前のサイズ検証を通したうえで各変換VIを直列接続し、まず1パケットで動作確認してからループ化する。

---

# 6. Parser単体テスト

## 6.1 2チャンネル・1パケット

Channel List：

```text
Channel 0
  Name = UnsignedValue
  Sign = 0
  Scale = 1
  Offset = 0

Channel 1
  Name = SignedValue
  Sign = 1
  Scale = 1
  Offset = 0
```

Little EndianのダミーRaw Buffer：

```text
01 00 00 00             // Channel 0 = 1
FE FF FF FF             // Channel 1 = -2
A5 00 00 00             // Flag = 0x000000A5
32 00 00 00 00 00 00 00 // Timestamp = 50
```

入力：

```text
DataNum = 1
ChNum = 2
Packet Size = 20
Raw Buffer Size = 20
```

期待結果：

```text
Packets[0].Channel Values[0].Value = 1
Packets[0].Channel Values[1].Value = -2
Packets[0].Flag = 0xA5
Packets[0].Timestamp Raw = 50
Packets[0].Timestamp Seconds = 0.000001
Parsed Packet Count = 1
Unused Byte Count = 0
```

## 6.2 不完全バッファ

上記Raw Bufferの末尾を1バイト削除する。

期待結果：

```text
error out.status = True
Packets = 空配列
```

## 6.3 余剰バイト

上記Raw Bufferの末尾へ4バイト追加する。

期待結果：

```text
Parsed Packet Count = 1
Unused Byte Count = 4
error out.status = False
```

## 6.4 Big Endian

各数値のバイト順をBig Endianへ並べ替え、`Byte Order=Big Endian`で同じ値になることを確認する。

---

# 7. 公開APIでの接続

## 7.1 `RAMScope_Init.vi`

```text
RS_DLL_GT150GetSysInfo.vi
  ├─ SYSINFO Raw
  └─ error out
        ↓
Parse_SYSINFO_Array.vi
  ├─ Module List
  ├─ MdlNo_RAM
  ├─ MdlNo_CAN
  ├─ Endian_RAM
  ├─ RAM Module Found?
  └─ error out
```

RAM Module Found?がFalseの場合のエラー生成は`RAMScope_Init.vi`で行う。

## 7.2 `RAMScope_Read.vi`

```text
RS_DLL_GT150GetBufferData.vi
  ├─ Raw Buffer
  ├─ DataNum
  ├─ LostDataNum
  └─ error out
        ↓
RAMScope_Parse_Buffer.vi
  ├─ Channel List
  ├─ Byte Order
  ├─ Packets
  └─ error out
```

`Channel List`は`Build_CHINFO_170_Raw.vi`へ渡したものと同じ配列を使用する。順序を変更すると取得データと変数名の対応がずれる。

---

# 8. 実機PoCで確認する項目

- [ ] `SYSINFO Raw`が960バイト
- [ ] RAMモジュール番号が純正RAMScopeVP表示と一致
- [ ] Channel Listの順序と取得値の順序が一致
- [ ] 既知RAM変数の値が一致
- [ ] 符号あり／なしの解釈が一致
- [ ] Byte Order設定が一致
- [ ] Flagの変化が妥当
- [ ] Timestampが単調増加する
- [ ] Timestampの20ns換算が実測時間と一致
- [ ] `Parsed Packet Count == DataNum`
- [ ] `LostDataNum`を記録できる
- [ ] 不完全バッファでクラッシュせずエラーを返す

---

# 9. 完成チェックリスト

## SYSINFO Parser

- [ ] 入力サイズ960を検証
- [ ] 60バイト×16で処理
- [ ] 11個のI32フィールドを正しいoffsetで取得
- [ ] name[16]のNULL終端を除去
- [ ] Module Listが16要素
- [ ] RAM/CANの最初の該当モジュール番号を取得
- [ ] CAN未搭載をエラーにしない

## Buffer Parser

- [ ] ChNumをChannel Listから算出
- [ ] Packet Sizeが`4×ChNum+12`
- [ ] Expected Byte Countを事前検証
- [ ] 1パケットごとにChannel/Flag/Timestampを解析
- [ ] 符号付き変換でType Castを使用
- [ ] Engineering ValueをScale/Offsetで変換
- [ ] 余剰バイト数を出力
- [ ] 不完全バッファを検出
- [ ] 実機なしのダミーデータ試験を完了
- [ ] 実機PoCで純正表示または既知値と照合