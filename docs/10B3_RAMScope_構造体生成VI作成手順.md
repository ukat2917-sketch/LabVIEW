# 10B-3. RAMScope 構造体生成VI 作成手順

> **本章の役割**：RAMScope APIへ渡す`MEASINFO_170`、`CHINFO_170[]`、`LOGINFO`を、LabVIEWの設定値からC構造体と同じバイト配置のU8一次元配列へ変換する手順を説明する。
>
> DLLラッパの作成は [10B-2](./10B2_RAMScope_DLLラッパVI_CLFN配線手順.md)、取得データの解析は [10B-4](./10B4_RAMScope_Parser_VI作成手順.md) を参照する。
>
> 構造体の一次情報は`docs/reference/RAMScopeVP.h`を正とする。

**最終整理日：2026-07-15**

---

# 1. 作成するファイル

```text
30_RAMScope\
├─ 00_Common\
│  ├─ RAMScope_Meas_Config.ctl
│  ├─ RAMScope_Channel.ctl
│  ├─ RAMScope_Module_Log_Config.ctl
│  ├─ I32_To_LE_U8x4.vi
│  └─ U32_To_LE_U8x4.vi
│
└─ 20_Parser\
   ├─ Build_MEASINFO_170_Raw.vi
   ├─ Build_CHINFO_170_Raw.vi
   └─ Build_LOGINFO_Raw.vi
```

構造体生成VIはDLLを呼ばない。入力された設定値をU8配列へ変換する純粋処理とする。

---

# 2. 共通ルール

## 2.1 C構造体はWindowsのメモリ配置で生成する

今回使用するフィールドはすべて4バイト境界で並び、ヘッダ上の`long`、`unsigned long`、`DWORD`はいずれも4バイトである。

構造体生成では次の順序を守る。

1. 構造体全体をU8の0で必要サイズ分初期化する。
2. 各I32/U32を4バイトのLittle Endian配列へ変換する。
3. `Replace Array Subset`でヘッダ記載のオフセットへ格納する。
4. 最後に`Array Size`で想定サイズを確認する。

## 2.2 使用する主なLabVIEW関数

| 関数 | パレットの目安 | 用途 |
|---|---|---|
| `Initialize Array` | プログラミング → 配列 | U8配列を必要サイズで初期化 |
| `Replace Array Subset` | プログラミング → 配列 | 指定オフセットへ4バイト配列を格納 |
| `Array Size` | プログラミング → 配列 | 配列要素数の取得 |
| `For Loop` | プログラミング → ストラクチャ | チャンネル、モジュール設定を順に処理 |
| `Shift Register` | For Loop枠を右クリック | U8配列を1次元のまま連結 |
| `Build Array` | プログラミング → 配列 | 配列の連結。`Concatenate Inputs`を使用 |
| `Unbundle By Name` | プログラミング → クラスタ | typedefクラスタから設定値を取得 |
| `Flatten To String` | プログラミング → 文字列 | I32/U32を指定Byte Orderで4バイト化 |
| `String To Byte Array` | プログラミング → 文字列 | 4バイト文字列をU8配列へ変換 |
| `Case Structure` | プログラミング → ストラクチャ | 既存エラー、入力値不正の分岐 |
| `Bundle By Name` | プログラミング → クラスタ | ローカル検証エラーの生成 |

---

# 3. I32/U32をLittle Endian U8[4]へ変換する共通VI

構造体生成VI内で同じ処理を何度も複製しないため、2つの共通VIを先に作る。

---

## 3.1 `I32_To_LE_U8x4.vi`

### 3.1.1 フロントパネル端子

| 端子 | 方向 | 型 |
|---|---|---|
| `Value` | 入力 | I32 |
| `error in` | 入力 | error cluster |
| `Bytes` | 出力 | U8一次元配列 |
| `error out` | 出力 | error cluster |

### 3.1.2 ブロックダイアグラムへ配置する関数

```text
Unbundle By Name（error in.status）
Case Structure
Flatten To String
String To Byte Array
Array Size
```

### 3.1.3 Case Structure

`error in.status`をCase Structureのセレクタへ接続する。

#### Trueケース

```text
error in → error out
空のU8配列 → Bytes
```

#### Falseケース

1. `Value`を`Flatten To String`のanything入力へ接続する。
2. `Flatten To String`の`byte order`端子を表示する。
3. byte orderへ`little-endian`定数を接続する。
4. 出力文字列を`String To Byte Array`へ接続する。
5. U8配列を`Bytes`へ出力する。
6. `Array Size`が4であることをデバッグ時に確認する。
7. `error in`をそのまま`error out`へ出力する。

完成イメージ：

```text
I32 Value
   ↓
Flatten To String（little-endian）
   ↓
String To Byte Array
   ↓
U8[4]
```

### 3.1.4 単体テスト

```text
Value = 100
期待Bytes = 64 00 00 00

Value = -1
期待Bytes = FF FF FF FF
```

---

## 3.2 `U32_To_LE_U8x4.vi`

`I32_To_LE_U8x4.vi`を別名保存し、`Value`の表現形式だけU32へ変更する。

### 単体テスト

```text
Value = 0x00001000
期待Bytes = 00 10 00 00

Value = 0xFFFFFFFF
期待Bytes = FF FF FF FF
```

---

# 4. typedefを作成する

---

## 4.1 `RAMScope_Meas_Config.ctl`

### 4.1.1 作成方法

1. 新規カスタム制御器を作成する。
2. Clusterを配置する。
3. 以下のI32数値制御器をClusterへ入れる。
4. 制御器を`typedef`へ変更する。
5. `30_RAMScope\00_Common\RAMScope_Meas_Config.ctl`として保存する。

### 4.1.2 フィールド

| フィールド | 型 | 初期PoC例 | 用途 |
|---|---|---:|---|
| `DummyInterval` | I32 | 100 | ダミー測定間隔 |
| `MeasPeri` | I32 | 100 | 測定周期 |
| `MeasUnit` | I32 | 2 | 測定周期の単位コード |

`MeasUnit`の数値定義は使用中APIの外部仕様書を正とし、未確認の値を推測で固定しない。

---

## 4.2 `RAMScope_Channel.ctl`

このtypedefは1個のRAM監視対象を表す。`RAMScope_Channel.ctl`の配列要素数が、そのまま`ChNum`になる。

### 4.2.1 フィールド

| フィールド | 型 | DLLへ渡すか | 用途 |
|---|---|---|---|
| `Name` | String | いいえ | 変数名、Parser表示名 |
| `Enable` | U32 | はい | `CHINFO_RAM170.enable` |
| `Core` | U32 | はい | `CHINFO_RAM170.core` |
| `Address` | U32 | はい | 監視RAMアドレス |
| `Size` | U32 | はい | APIのデータサイズコード |
| `Sign` | U32 | はい | APIの符号コード |
| `Speed` | U32 | はい | APIの速度コード |
| `Scale` | DBL | いいえ | Parserの工学値変換。初期値1.0 |
| `Offset` | DBL | いいえ | Parserの工学値変換。初期値0.0 |
| `Unit` | String | いいえ | 工学単位表示 |

`Size`、`Sign`、`Speed`はベンダーAPIコードをそのまま保持する。意味が正式資料で確定するまでは独自変換しない。

### 4.2.2 `ChNum`の決定方法

```text
RAMScope_Channel.ctl 配列
           ↓
       Array Size
           ↓
         ChNum
```

`ChNum`を操作者が別入力で手入力しない。設定配列の要素数から自動算出する。

### 4.2.3 既存RAMScopeコンフィグとの接続

PoCでは、既存RAMScope設定に登録されている監視変数を`RAMScope_Channel.ctl`配列へ転記する。

将来の自動読込は次の責務分担とする。

```text
RAMScope設定ファイルまたはエクスポートCSV
           ↓
Load_RAMScope_Channel_Config.vi
           ↓
RAMScope_Channel.ctl 配列
           ├─ Array Size → ChNum
           ├─ Build_CHINFO_170_Raw.vi
           └─ RAMScope_Parse_Buffer.vi
```

ベンダー設定ファイルが非公開形式の場合、バイナリ構造を推測で解析しない。ベンダーの仕様書を入手するか、CSV/テキストへエクスポートした中間ファイルを正本にする。

---

## 4.3 `RAMScope_Module_Log_Config.ctl`

`LOGINFO.mdl[16]`のうち、設定するモジュールだけを記述するtypedef。

| フィールド | 型 | 用途 |
|---|---|---|
| `MdlNo` | I32 | 0から15のモジュール番号 |
| `LogSize` | I32 | ログ容量設定 |
| `BufferSize` | I32 | バッファ容量設定 |

---

# 5. `Build_MEASINFO_170_Raw.vi`

## 5.1 C構造体

```c
typedef struct MEASINFO_RAM170 {
    long DummyInterval;       // offset 0
    long MeasPeri;            // offset 4
    long MeasUnit;            // offset 8
    long MeasPeri_reserve[2]; // offset 12, 16
} MEASINFO_RAM170;

typedef union MEASINFO_170 {
    MEASINFO_RAM170 RAM;
    MEASINFO_ADC170 ADC;
    MEASINFO_CAN170 CAN;
} MEASINFO_170;
```

union全体は72バイト。RAM設定では先頭20バイトを使用し、残りを0で初期化する。

## 5.2 フロントパネル端子

| 端子 | 方向 | 型 |
|---|---|---|
| `Meas Config` | 入力 | `RAMScope_Meas_Config.ctl` |
| `error in` | 入力 | error cluster |
| `MEASINFO_170 Raw` | 出力 | U8一次元配列 |
| `error out` | 出力 | error cluster |

## 5.3 ブロックダイアグラムへ配置する関数

```text
Unbundle By Name
Initialize Array
I32_To_LE_U8x4.vi ×3
Replace Array Subset ×3
Case Structure
Array Size
```

## 5.4 初期配列を作る

```text
U8定数 0 ─────────→ Initialize Array element
I32定数 72 ────────→ Initialize Array dimension size
```

出力はU8[72]になる。

## 5.5 各フィールドを4バイト化する

`Meas Config`を`Unbundle By Name`へ接続し、以下を取り出す。

```text
DummyInterval
MeasPeri
MeasUnit
```

それぞれを`I32_To_LE_U8x4.vi`へ接続する。

## 5.6 `Replace Array Subset`で格納する

`Replace Array Subset`を3個直列にする。

| 順番 | 格納値 | index |
|---:|---|---:|
| 1 | `DummyInterval Bytes` | 0 |
| 2 | `MeasPeri Bytes` | 4 |
| 3 | `MeasUnit Bytes` | 8 |

```text
U8[72]初期配列
  → Replace(index=0, DummyInterval U8[4])
  → Replace(index=4, MeasPeri U8[4])
  → Replace(index=8, MeasUnit U8[4])
  → MEASINFO_170 Raw
```

offset 12以降は初期値0のままにする。

## 5.7 エラー分岐

`error in.status`をCase Structureのセレクタへ接続する。

- True：U8[72]のゼロ配列と元の`error in`を出力する。
- False：構造体生成処理を実行し、正常な`error out`を出力する。

## 5.8 単体テスト

入力：

```text
DummyInterval = 100
MeasPeri      = 100
MeasUnit      = 2
```

先頭20バイト期待値：

```text
64 00 00 00
64 00 00 00
02 00 00 00
00 00 00 00
00 00 00 00
```

確認項目：

- `Array Size = 72`
- offset 0、4、8が期待値
- offset 12から71が0

---

# 6. `Build_CHINFO_170_Raw.vi`

## 6.1 C構造体

```c
typedef struct CHINFO_RAM170 {
    DWORD enable;  // offset 0
    DWORD core;    // offset 4
    DWORD address; // offset 8
    DWORD size;    // offset 12
    DWORD sign;    // offset 16
    DWORD speed;   // offset 20
} CHINFO_RAM170;
```

1チャンネル24バイト。`CHINFO_170[]`の配列長は`ChNum`と一致させる。

## 6.2 フロントパネル端子

| 端子 | 方向 | 型 |
|---|---|---|
| `Channel List` | 入力 | `RAMScope_Channel.ctl`一次元配列 |
| `error in` | 入力 | error cluster |
| `ChNum` | 出力 | I32 |
| `CHINFO_170 Raw` | 出力 | U8一次元配列 |
| `error out` | 出力 | error cluster |

## 6.3 ブロックダイアグラムへ配置する関数

```text
Array Size
Greater Than 0?
Less Or Equal?
Compound Arithmetic（AND）
Case Structure
For Loop
Unbundle By Name
U32_To_LE_U8x4.vi ×6
Build Array（Concatenate Inputs）
Shift Register
```

## 6.4 `ChNum`を自動算出する

```text
Channel List → Array Size → ChNum
```

`ChNum`をI32へ変換して出力する。

初期PoCの有効範囲：

```text
1 <= ChNum <= 2048
```

範囲外の場合はCLFNへ渡さない。

## 6.5 For Loopを作る

1. `Channel List`をFor Loopへ自動インデックス入力する。
2. For LoopへU8空配列のShift Registerを追加する。
3. 左Shift Registerへ空のU8配列定数を接続する。
4. 1反復で1チャンネル分の24バイトを生成する。
5. 生成した24バイトを累積配列へ連結する。
6. 最終Shift Registerを`CHINFO_170 Raw`へ接続する。

## 6.6 1チャンネル分の24バイトを作る

For Loop内で`Unbundle By Name`を使用し、以下を取り出す。

```text
Enable
Core
Address
Size
Sign
Speed
```

各U32を`U32_To_LE_U8x4.vi`へ接続する。

`Build Array`を配置し、右クリックして`Concatenate Inputs`を有効にする。入力を6個まで増やし、次の順番で接続する。

```text
Enable Bytes
Core Bytes
Address Bytes
Size Bytes
Sign Bytes
Speed Bytes
```

出力がU8[24]になる。

## 6.7 全チャンネルを1次元配列へ連結する

別の`Build Array`を配置し、`Concatenate Inputs`を有効にする。

```text
左Shift Registerの累積U8配列
+ 今回のU8[24]
        ↓
右Shift Register
```

2次元配列にしない。`Build Array`の`Concatenate Inputs`が有効であることを確認する。

## 6.8 入力不正時のCase

`ChNum`範囲判定をCase Structureへ接続する。

- True：For LoopでRaw配列を生成する。
- False：空のU8配列を出力し、`Bundle By Name`でローカル検証エラーを作成する。

エラーメッセージ例：

```text
Build_CHINFO_170_Raw.vi: Channel count must be 1..2048. ChNum=<value>
```

エラーコードはプロジェクトで定義したユーザーエラー範囲から一意に割り当て、数値を複数VIへ直書きしない。

## 6.9 単体テスト

1チャンネル入力例：

```text
Name    = TestValue
Enable  = 1
Core    = 0
Address = 0x00001000
Size    = 0
Sign    = 0
Speed   = 0
```

期待値：

```text
ChNum = 1
Array Size(CHINFO_170 Raw) = 24

01 00 00 00  // Enable
00 00 00 00  // Core
00 10 00 00  // Address
00 00 00 00  // Size
00 00 00 00  // Sign
00 00 00 00  // Speed
```

3チャンネルの場合：

```text
ChNum = 3
Array Size = 72
```

---

# 7. `Build_LOGINFO_Raw.vi`

## 7.1 C構造体

```c
typedef struct LOGINFO {
    long logDevice;       // offset 0
    long limitHddSize;    // offset 4
    struct {
        long logSize;     // offset 8 + i*8
        long BuffSize;    // offset 12 + i*8
    } mdl[16];
} LOGINFO;
```

合計136バイト。

## 7.2 フロントパネル端子

| 端子 | 方向 | 型 |
|---|---|---|
| `LogDevice` | 入力 | I32 |
| `LimitHddSize` | 入力 | I32 |
| `Module Log Configs` | 入力 | `RAMScope_Module_Log_Config.ctl`一次元配列 |
| `error in` | 入力 | error cluster |
| `LOGINFO Raw` | 出力 | U8一次元配列 |
| `error out` | 出力 | error cluster |

## 7.3 初期配列とヘッダを作る

```text
U8 0 × 136 → Initialize Array
```

`LogDevice`、`LimitHddSize`を`I32_To_LE_U8x4.vi`へ接続し、次の位置へ格納する。

| 値 | index |
|---|---:|
| `LogDevice` | 0 |
| `LimitHddSize` | 4 |

## 7.4 モジュールごとの設定を格納する

`Module Log Configs`をFor Loopへ自動インデックス入力する。

各反復で次を取り出す。

```text
MdlNo
LogSize
BufferSize
```

MdlNoを検証する。

```text
0 <= MdlNo <= 15
```

格納位置を計算する。

```text
LogSize index    = 8  + MdlNo × 8
BufferSize index = 12 + MdlNo × 8
```

`LogSize`、`BufferSize`をI32の4バイトへ変換し、`Replace Array Subset`で累積配列へ格納する。

For LoopにはU8[136]のShift Registerを使用する。

## 7.5 重複MdlNoの確認

同じMdlNoが複数回入力されると後の値で上書きされる。正式実装では次のどちらかを採用する。

- `Seen` Boolean[16]をShift Registerで持ち、2回目をエラーにする。
- 事前にMdlNo配列を作成し、重複検出VIで確認する。

最小PoCでRAMモジュール1個だけを入力する場合も、将来の複数モジュール化を考慮し、重複を許可しない。

## 7.6 単体テスト

入力：

```text
LogDevice   = 0
LimitHddSize = 0

Module Log Configs[0]
  MdlNo      = 1
  LogSize    = 1
  BufferSize = 1
```

期待値：

```text
Array Size = 136
offset 0  = 0
offset 4  = 0
offset 16 = 1  // 8 + 1*8
offset 20 = 1  // 12 + 1*8
その他は0
```

---

# 8. `RAMScope_Set_Cond.vi`での接続

構造体生成とDLLラッパを次の順で接続する。

```text
Meas Config
  → Build_MEASINFO_170_Raw.vi
  → RS_DLL_GT170SetMeasCond.vi

Channel List
  → Build_CHINFO_170_Raw.vi
      ├─ ChNum
      └─ CHINFO_170 Raw
  → RS_DLL_GT170SetMeasCh.vi

Module Log Configs
  → Build_LOGINFO_Raw.vi
  → RS_DLL_GT150SetLoggingInfo.vi
```

エラー線は直列に接続する。

```text
error in
 → Build_MEASINFO
 → SetMeasCond
 → Build_CHINFO
 → SetMeasCh
 → Build_LOGINFO
 → SetLoggingInfo
 → Error_To_TestStatus.vi
 → error out
```

`ChNum`は`Build_CHINFO_170_Raw.vi`の出力をそのまま`RS_DLL_GT170SetMeasCh.vi`へ接続する。別の手入力端子から入力しない。

---

# 9. 完成チェックリスト

## 共通変換VI

- [ ] I32/U32の出力が必ずU8[4]
- [ ] byte orderがLittle Endian
- [ ] `-1`が`FF FF FF FF`になる

## MEASINFO

- [ ] 出力サイズ72
- [ ] offset 0、4、8へ正しい値
- [ ] reserveと未使用領域が0

## CHINFO

- [ ] `ChNum = Array Size(Channel List)`
- [ ] 1チャンネル24バイト
- [ ] 出力が1次元U8配列
- [ ] フィールド順がEnable/Core/Address/Size/Sign/Speed
- [ ] `Array Size = 24 × ChNum`
- [ ] 0チャンネルと2048超を拒否

## LOGINFO

- [ ] 出力サイズ136
- [ ] MdlNoが0..15
- [ ] offset計算が`8+i*8`、`12+i*8`
- [ ] 未指定モジュールは0
- [ ] 重複MdlNoを拒否

## 公開API接続

- [ ] BuilderのRaw出力を対応DLLラッパへ接続
- [ ] BuilderとDLLラッパのerror clusterを直列接続
- [ ] ChNumを手入力せずBuilder出力から接続
- [ ] 同じChannel ListをParserにも渡せる構成