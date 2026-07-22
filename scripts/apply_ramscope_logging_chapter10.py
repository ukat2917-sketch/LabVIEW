from pathlib import Path

DOC = Path("docs/10_RAMScope実装方針.md")
DRAFT = Path("docs/drafts/10_RAMScopeロギング取得VI現行API改訂案.md")
SELF = Path("scripts/apply_ramscope_logging_chapter10.py")
WORKFLOW = Path(".github/workflows/apply-ramscope-logging-chapter10.yml")

text = DOC.read_text(encoding="utf-8")


def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"replacement target count must be 1, got {count}: {old[:80]!r}")
    text = text.replace(old, new, 1)


replace_once("**最終整理日：2026-07-21**", "**最終整理日：2026-07-22**")
replace_once(
    "> 本章の整理によってVIまたはctlの構成は変更しない。資料に存在しないVIまたはctlを追加しない。",
    "> 既存の`PoC_RAMScope_Main.vi`は通信確認用PoCとして維持する。測定停止後の保存ログ回収、TDMS保存および欠落検証は、別構成の`PoC_RAMScope_Logging_Main.vi`で検証する。ロギング機能の追加・修正対象は10.13を正本とする。",
)
replace_once(
    "本章の整理では、次に示す既存ファイルだけを使用する。",
    "本章では既存ファイルを維持しつつ、10.13で確定したロギング用Wrapper、公開API、TDMS保存VIおよび専用PoCを追加する。通信確認用PoCとロギング用PoCは統合しない。",
)
replace_once(
    "| `RAMScope_PoC_State.ctl` | Connect、Start、Stop、Release等の成功履歴 |",
    "| `RAMScope_PoC_State.ctl` | 通信確認用PoCのConnect、Start、Stop、Release等の成功履歴 |\n| `RAMScope_Logging_PoC_State.ctl` | ロギング専用PoCのFile Open、Start、Stop、保存ログ回収、Release等の成功履歴 |",
)
replace_once(
    """RS_DLL_GT150MeasStart.vi
RS_DLL_GT150GetBufferData.vi
RS_DLL_GT150ReleaseBufferData.vi
RS_DLL_GT150MeasStop.vi""",
    """RS_DLL_GT150MeasStart.vi
RS_DLL_GT150GetGapTime.vi
RS_DLL_GT150GetMeasNum.vi
RS_DLL_GT150GetBlockNum.vi
RS_DLL_GT150GetBufferDataNum.vi
RS_DLL_GT150GetBufferData.vi
RS_DLL_GT150GetLoggingDataNum.vi
RS_DLL_GT150GetLoggingData.vi
RS_DLL_GT150ReleaseBufferData.vi
RS_DLL_GT150MeasStop.vi""",
)
replace_once(
    """RAMScope_Log_Start.vi
RAMScope_Read.vi
RAMScope_Log_Stop.vi
RAMScope_Release.vi
RAMScope_Close.vi""",
    """RAMScope_Log_Start.vi
RAMScope_Read.vi
RAMScope_Log_Stop.vi
RAMScope_Get_Log_Summary.vi
RAMScope_Get_Block_Count.vi
RAMScope_Read_Logging_Block.vi
RAMScope_Release.vi
RAMScope_Close.vi""",
)
replace_once(
    """### 10.2.5 PoC・単体操作・TestStand

```text
PoC_RAMScope_Main.vi
```

現時点では`PoC_RAMScope_Main.vi`が、TestStandなしでConnectからCleanupまでを一度通して操作するVIを兼ねる。Standalone専用VIを別名で追加しない。

TestStandは上記8個の公開APIを呼ぶ。資料にないTestStand専用ラッパVIを追加しない。""",
    """### 10.2.5 PoC・単体操作・TestStand

```text
PoC_RAMScope_Main.vi
PoC_RAMScope_Logging_Main.vi
```

`PoC_RAMScope_Main.vi`は既存の通信確認用PoCとして残す。DeviceInit、初期化、条件設定、測定開始、短時間の最新値取得、停止、Release、Closeまでの疎通を確認し、長時間TDMS保存および測定停止後の保存ログ回収は実装しない。

`PoC_RAMScope_Logging_Main.vi`はロギング専用PoCとして新規作成する。機器側保存バッファの測定、停止後のMeasNo／BlockNo列挙、全Block取得、Packet解析、TDMS追記、欠落情報保存、Cleanupを検証する。

TestStandは公開APIを呼び、MeasNoとBlockNoの反復、試験条件、レポートおよび全体Cleanupを管理する。TestStand専用のDLL Wrapperは追加しない。""",
)
replace_once(
    """TestStand または PoC_RAMScope_Main.vi
  → RAMScope_* 公開API""",
    """TestStand、PoC_RAMScope_Main.vi または PoC_RAMScope_Logging_Main.vi
  → RAMScope_* 公開API""",
)

marker = "## 10.13 ロギング・TestStand組込み・Cleanup"
if marker not in text:
    raise RuntimeError("10.13 marker was not found")
text = text[: text.index(marker)] + r'''## 10.13 ロギング機能の修正・追加VI・専用PoC

### 10.13.1 この節の適用範囲

本節は、次の2系統を明確に分離して実装する。

```text
通信確認系
  PoC_RAMScope_Main.vi
    → 接続、初期化、条件設定、短時間の最新値取得、停止、解放、終了
    → 既存VI構成を維持する
    → TDMS長時間保存と停止後保存ログ回収は担当しない

ロギング検証系
  PoC_RAMScope_Logging_Main.vi
    → 接続、初期化、条件設定、TDMS Open、測定、停止
    → MeasNo／BlockNo列挙
    → 保存ログ全Block取得
    → Packet解析、TDMS追記、欠落情報保存
    → Release、TDMS Close、DeviceExit
```

既存`PoC_RAMScope_Main.vi`へロギング用の二重For Loop、TDMS参照、保存ログ回収処理を追加しない。通信確認PoCの役割を膨らませると、DLL疎通不良とファイル保存不良の切り分けが困難になるためである。

---

### 10.13.2 公式APIとPacket仕様の確定事項

#### 10.13.2.1 保存ログ取得API

```c
long RAMScopeGT150GetGapTime(
    long UnitNo,
    unsigned long *pGapTime
);

long RAMScopeGT150GetMeasNum(
    long UnitNo,
    long *pMeasNum
);

long RAMScopeGT150GetBlockNum(
    long UnitNo,
    long MeasNo,
    long *pBlockNum
);

long RAMScopeGT150GetBufferDataNum(
    long UnitNo,
    long MdlNo,
    long *pDataNum
);

long RAMScopeGT150GetBufferData(
    long UnitNo,
    long MdlNo,
    void *pData,
    long *pDataNum,
    long *pLostDataNum
);

long RAMScopeGT150GetLoggingDataNum(
    long UnitNo,
    long MdlNo,
    long MeasNo,
    long BlockNo,
    long *pDataNum
);

long RAMScopeGT150GetLoggingData(
    long UnitNo,
    long MdlNo,
    long MeasNo,
    long BlockNo,
    void *pData,
    long *pDataNum,
    long *pLostDataNum
);
```

`GetBufferData()`と`GetLoggingData()`の`pDataNum`は入出力である。

```text
呼出し前のpDataNum
  = 要求Packet数

正常終了後のpDataNum
  = 実際に読み出したPacket数
```

独立した`MaxDataNum`引数は存在しない。CLFNに存在しない引数を追加しない。

#### 10.13.2.2 RAMモニタPacket

```text
Packet[k]
├─ Data[0]      4byte
├─ Data[1]      4byte
├─ ...
├─ Data[N-1]    4byte
├─ Flag         4byte
└─ Time         8byte
```

```text
Packet Size = N × 4 + 12 byte
```

- `N`は測定有効チャンネル数。
- Dataの順番は`RAMScopeGT1x0SetMeasCh()`へ設定した順番。
- 設定データサイズが1byte、2byte、4byteのいずれでも、Packet内では1チャンネル4byte固定。
- Timeは測定開始を0とする64bitカウンタで、1countは20ns。

```text
Timestamp Seconds = Time Raw U64 × 20e-9
```

#### 10.13.2.3 RAMモニタFlag

| フィールド | bit | 抽出式 |
|---|---:|---|
| Status | 0～7 | `Flag Raw AND 0x000000FF` |
| Skip | 8 | `((Flag Raw >> 8) AND 1) != 0` |
| Log Trigger | 10～11 | `(Flag Raw >> 10) AND 3` |
| Dummy | 12 | `((Flag Raw >> 12) AND 1) != 0` |
| Event Bits | 16～23 | `(Flag Raw >> 16) AND 0xFF` |
| Data Lost | 28 | `((Flag Raw >> 28) AND 1) != 0` |

予約bitは値不定のため、0であることを正常条件にしない。

`Skip`、`Data Lost`、`Status != 0`は測定Packet内の状態情報であり、Parser自身の配列エラーとは分ける。該当Packetを捨てず、Raw値と解析結果をTDMSへ保存する。

---

## 10.13.3 既存ctlと既存VIの修正

### 10.13.3.1 `RAMScope_Packet.ctl`修正

#### 0. 実現したい機能とctlの責務

1PacketのRaw Flagを保持したまま、RAMモニタ用Flagの各フィールドを上位VIとTDMS保存VIへ渡せるようにする。

#### 1. 入力データの実体

ParserがPacket内のFlag 4byteをU32へ変換した値を使用する。

#### 2. 出力データモデル

既存項目を削除せず、次の順へ整理する。

```text
Packet Index          I32
Channel Values        RAMScope_Channel_Value.ctl[]
Flag Raw              U32
Status                U8
Skip?                 Boolean
Log Trigger           U8
Dummy?                 Boolean
Event Bits            U8
Data Lost?             Boolean
Timestamp Raw         U64
Timestamp Seconds     DBL
```

既存項目名が`Flag`の場合は、型をU32のまま維持して`Flag Raw`へ名称変更する。既存VIの破損を避けるためtypedef更新後に全呼出し元を一括確認する。

#### 3. 前提条件・異常条件

- 予約bit専用Booleanを追加しない。
- StatusをEnumだけに変換してRawコードを失わない。
- Dummy Packetもctlへ格納する。

#### 4. 処理アルゴリズム

ctlはデータ型定義だけを担当し、bit演算を持たない。bit演算は`RAMScope_Parse_Buffer.vi`で行う。

#### 5. LabVIEW構造の選定理由

既存ctlを拡張し、新規Packet ctlを並立させない。最新値取得と保存ログ取得で同じPacket構造を共有できるためである。

#### 6. フロントパネル入出力と接続元・接続先

| 項目 | 生成元 | 接続先 |
|---|---|---|
| Flag Raw～Data Lost? | `RAMScope_Parse_Buffer.vi` | Read系公開API、TDMS Append、PoC表示 |
| Timestamp | `RAMScope_Parse_Buffer.vi` | Read系公開API、TDMS Append |

#### 7. 配置する要素

既存clusterへU8、Boolean、U32表示器を追加し、typedefとして保存する。

#### 8. 作成順

1. `RAMScope_Packet.ctl`を開く。
2. typedef編集モードであることを確認する。
3. 既存`Flag`を`Flag Raw`へ変更する。
4. Status、Skip?、Log Trigger、Dummy?、Event Bits、Data Lost?を上記順で追加する。
5. 既定値を数値0、Boolean Falseに設定する。
6. typedefを保存し、変更を全インスタンスへ適用する。
7. 壊れた`Bundle By Name`と`Unbundle By Name`を修正する。

#### 9. 単体テスト

`Flag Raw=0x10FF1D00`を入力し、各フィールドが独立して保持できることを確認する。ctl単体ではbit演算を行わない。

---

### 10.13.3.2 `RAMScope_Parse_Buffer.vi`修正

#### 0. 実現したい機能とVIの責務

最新値取得と保存ログ取得の両方から渡されるU8配列を、チャンネル値、RAM用Flag、20ns Timeを持つPacket配列へ変換する。

#### 1. 入力データの実体

```text
Raw Buffer U8[]
DataNum I32
Channel List RAMScope_Channel.ctl[]
Byte Order RAMScope_Byte_Order.ctl
```

Packet内の各Dataスロットは4byte固定だが、有効値幅は`RAMScope_Channel.ctl.Size`で決まる。

```text
Size=0 → 1byte有効
Size=1 → 2byte有効
Size=2 → 4byte有効
```

#### 2. 出力データモデル

```text
Packets RAMScope_Packet.ctl[]
Parsed Packet Count I32
Unused Byte Count I32
error out error cluster
```

#### 3. 前提条件・異常条件

```text
ChNum > 0
DataNum >= 0
Actual Byte Count >= DataNum × Packet Size
```

- `DataNum=0`は正常な空データ。
- Buffer不足はParserエラー。
- Status、Skip、Data LostはPacket状態でありParserエラーにしない。
- Sizeが0、1、2以外ならローカルエラー`-700160`。

source全文：

```text
RAMScope_Parse_Buffer.vi: Unsupported channel Size. ChannelIndex=%d, Size=%d
```

#### 4. 処理アルゴリズム

```text
ChNum = Array Size(Channel List)
Packet Size = ChNum × 4 + 12
Expected Bytes = DataNum × Packet Size
Actual Bytes = Array Size(Raw Buffer)

for PacketIndex in 0 ... DataNum-1:
    Packet Start = PacketIndex × Packet Size

    for ChannelIndex in 0 ... ChNum-1:
        Data Start = Packet Start + ChannelIndex × 4
        Raw Slot U32 = U8x4_To_U32(Data Start, Byte Order)
        Value = DecodeBySizeAndSign(Raw Slot U32, Size, Sign)
        Engineering Value = Value × Scale + Offset

    Flag Start = Packet Start + ChNum × 4
    Flag Raw = U8x4_To_U32(Flag Start, Byte Order)
    Flag fields = mask and shift

    Time Start = Flag Start + 4
    Time Raw = U8x8_To_U64(Time Start, Byte Order)
    Time Seconds = DBL(Time Raw) × 20e-9

    Bundle RAMScope_Packet.ctl
```

#### 5. LabVIEW構造の選定理由

- Packet反復は外側For Loop。
- Channel反復は内側For Loop。
- Size別の値幅はCase Structure。
- 4byte、8byte切出しはArray Subset。
- 符号付き値はType Castでbit列を維持する。
- FlagはLogical ShiftとANDで抽出する。

#### 6. フロントパネル入出力と接続元・接続先

| 端子 | 方向 | 型 | 接続元・接続先 |
|---|---|---|---|
| Raw Buffer | 入力 | U8[] | `RAMScope_Read.vi`または`RAMScope_Read_Logging_Block.vi` |
| DataNum | 入力 | I32 | 各DLL Wrapperの実取得数 |
| Channel List | 入力 | `RAMScope_Channel.ctl[]` | SetMeasChへ渡した同一配列 |
| Byte Order | 入力 | typedef | Init結果を明示変換した値 |
| Packets | 出力 | `RAMScope_Packet.ctl[]` | PoC、TDMS Append、TestStand |
| Parsed Packet Count | 出力 | I32 | 件数照合 |
| Unused Byte Count | 出力 | I32 | デバッグ・品質判定 |

#### 7. 配置する関数およびSubVI

- For Loop ×2。
- Case Structure：Size 0、1、2、Default。
- Array Size、Array Subset。
- U8x4_To_U32.vi、U8x8_To_U64.vi。
- AND、Logical Shift、Not Equal To 0?。
- Type Cast、To Double Precision Float。
- Bundle By Name。
- Format Into String、Bundle By Nameによるローカルerror生成。

#### 8. 配線順

##### A. サイズ検証

1. Channel ListをArray Sizeへ接続してChNumを得る。
2. ChNum、DataNumを先にI64へ変換する。
3. `Packet Size I64 = ChNum I64 × 4 + 12`を作る。
4. `Expected Bytes I64 = DataNum I64 × Packet Size I64`を作る。
5. Raw BufferのArray SizeをI64へ変換する。
6. `ChNum>0 AND DataNum>=0 AND Actual>=Expected`をCase selectorへ接続する。
7. Falseケースは空Packets、Count 0、Unused 0と`-700161`を返す。

source全文：

```text
RAMScope_Parse_Buffer.vi: Buffer is shorter than expected or input is invalid. ChNum=%d, DataNum=%d, Expected=%lld, Actual=%lld
```

##### B. Channel DataのSize別解析

1. 内側For LoopでChannel clusterからSizeとSignをUnbundleする。
2. Raw Slot U32をSize Caseへ接続する。
3. Size=0では`AND 0x000000FF`後にU8へ変換する。
4. Size=1では`AND 0x0000FFFF`後にU16へ変換する。
5. Size=2ではU32全体を使う。
6. 各Case内でSign=0なら符号なし数値をDBL化する。
7. Sign!=0なら同じbit幅のI8、I16、I32へType CastしてDBL化する。
8. `Value × Scale + Offset`をEngineering Valueへ接続する。
9. Defaultケースは`-700160`を生成する。

##### C. Flag解析

1. `Flag Start = Packet Start + ChNum×4`を作る。
2. 4byteをArray Subsetし、U8x4_To_U32.viへ接続する。
3. Flag Rawを次へ分岐する。

```text
Status      = U8(Flag Raw AND 0x000000FF)
Skip?       = ((Flag Raw >> 8) AND 1) != 0
Log Trigger = U8((Flag Raw >> 10) AND 3)
Dummy?      = ((Flag Raw >> 12) AND 1) != 0
Event Bits  = U8((Flag Raw >> 16) AND 0xFF)
Data Lost?  = ((Flag Raw >> 28) AND 1) != 0
```

4. 予約bitは解析しない。

##### D. Time解析

1. `Time Start = Flag Start + 4`。
2. 8byteをArray Subsetする。
3. U8x8_To_U64.viでTime Rawを取得する。
4. DBLへ変換して`20e-9`を乗算する。

##### E. Packet Bundle

1. 既存`RAMScope_Packet.ctl`定数をBundle By Nameの基準クラスタへ接続する。
2. Packet Index、Channel Values、Flag全項目、Time全項目を接続する。
3. 外側For Loopを自動インデックス出力にする。
4. Array Size(Packets)をParsed Packet Countへ接続する。

#### 9. 単体テスト

- 1byte unsigned `0xFF` → 255。
- 1byte signed `0xFF` → -1。
- 2byte unsigned `0xFFFF` → 65535。
- 2byte signed `0xFFFF` → -1。
- 4byte signed `0xFFFFFFFE` → -2。
- Flag各bitを1個ずつ立てて抽出結果を確認。
- Time Raw=50 → 1us。
- Buffer末尾1byte不足 → Parserエラー。
- DataNum=0 → 正常な空配列。

---

### 10.13.3.3 `RS_DLL_GT150GetBufferData.vi`修正確認

#### 0. 実現したい機能とVIの責務

測定中の表示用バッファから要求Packet数以下を取得する既存Wrapperである。関数引数は変更せず、`pDataNum`の入出力と配列事前確保を正す。

#### 1. 入力データの実体

```c
long RAMScopeGT150GetBufferData(
    long UnitNo,
    long MdlNo,
    void *pData,
    long *pDataNum,
    long *pLostDataNum
);
```

#### 2. 出力データモデル

```text
Allocated Raw Buffer U8[]
DataNum I32
LostDataNum I32
API ReturnCode I32
error out
```

#### 3. 前提条件・異常条件

- RequestedDataNum > 0。
- Buffer Byte Size > 0。
- error in.status=TrueならCLFNを呼ばない。

#### 4. 処理アルゴリズム

RequestedDataNumを`pDataNum`左端子へ渡し、右端子からDataNumを受け取る。

#### 5. LabVIEW構造の選定理由

既存エラー時のCLFN実行を防ぐCase Structureと、U8配列確保用Initialize Arrayを使用する。

#### 6. 入出力

既存端子`MaxDataNum`は意味を明確にするため`RequestedDataNum`へ名称変更する。コネクタ位置と型は維持する。

#### 7. CLFN Parameters

| 順 | 名前 | Type | Data Type | Pass |
|---:|---|---|---|---|
| Return | return | Numeric | Signed 32-bit | Value |
| 1 | UnitNo | Numeric | Signed 32-bit | Value |
| 2 | MdlNo | Numeric | Signed 32-bit | Value |
| 3 | pData | Array | Unsigned 8-bit、1D | Array Data Pointer |
| 4 | pDataNum | Numeric | Signed 32-bit | Pointer to Value |
| 5 | pLostDataNum | Numeric | Signed 32-bit | Pointer to Value |

Function Name：`RAMScopeGT150GetBufferData`

#### 8. 配線順

1. U8 0をBuffer Byte Size個Initialize Arrayする。
2. 配列をpData左端子へ接続する。
3. RequestedDataNumをpDataNum左端子へ接続する。
4. I32 0をpLostDataNum左端子へ接続する。
5. pData、pDataNum、pLostDataNumの右端子を各出力へ接続する。
6. ReturnCodeとCLFN errorを`RAMScope_Code_To_Error.vi`へ接続する。
7. bypassケースは空U8[]、DataNum=0、LostDataNum=0、ReturnCode=0、元errorを返す。

#### 9. 単体テスト

1Packet、複数Packet、実取得数が要求数未満、既存error、表示用バッファ空を確認する。

---

### 10.13.3.4 `RAMScope_Read.vi`修正

#### 0. 実現したい機能とVIの責務

測定中の表示用バッファから最新Packetを安全に取得し、実取得分だけをParserへ渡す。通信確認PoCとオンライン監視で使用する。停止後保存ログの取得は担当しない。

#### 1. 入力データの実体

```text
UnitNo I32
MdlNo_RAM I32
RequestedDataNum Limit I32
Channel List
Byte Order
Max Buffer Bytes I64
error in
```

#### 2. 出力データモデル

既存出力に次を追加する。

```text
AvailableDataNum I32
RequestedDataNum I32
Raw Buffer U8[]
DataNum I32
LostDataNum I32
Packets[]
Parsed Packet Count I32
Unused Byte Count I32
Status、TestError、error out
```

#### 3. 前提条件・異常条件

- Channel List非空。
- RequestedDataNum Limit > 0。
- Max Buffer Bytes > 0。
- I64計算後にI32上限以下。
- `0 <= DataNum <= RequestedDataNum`。

#### 4. 処理アルゴリズム

```text
AvailableDataNum = GetBufferDataNum(UnitNo, MdlNo_RAM)
RequestedDataNum = min(AvailableDataNum, RequestedDataNum Limit)

if RequestedDataNum == 0:
    空データを正常として返す
else:
    Packet Size = ChNum×4+12
    Required Bytes = RequestedDataNum×Packet Size
    上限検証
    GetBufferData
    Actual Bytes = DataNum×Packet Size
    RawをActual Bytesへ切詰め
    Parse
    Parsed CountとDataNumを照合
```

#### 5. LabVIEW構造の選定理由

GetBufferDataNumで実在Packet数を先に把握し、必要以上の配列確保を避ける。サイズ演算はI64、DLL配列長へ渡す直前だけI32へ変換する。

#### 6. 入出力と接続元・接続先

`PoC_RAMScope_Main.vi`はこのVIを1回または短時間反復して通信確認する。`PoC_RAMScope_Logging_Main.vi`はオンライン表示が必要な場合だけ呼び、正式保存データは停止後の`RAMScope_Read_Logging_Block.vi`から得る。

#### 7. 配置する関数およびSubVI

- `RS_DLL_GT150GetBufferDataNum.vi`。
- `RS_DLL_GT150GetBufferData.vi`。
- `RAMScope_Parse_Buffer.vi`。
- Min & Max、I64変換、Multiply、Add、Array Subset。
- Case Structure：Input Valid、No Data、Buffer Size Valid、Returned Count Valid、Parsed Count Match。
- `Error_To_TestStatus.vi`。

#### 8. 配線順

1. Channel ListのArray Size、Limit、Max Buffer Bytesを検証する。
2. GetBufferDataNumを呼ぶ。
3. AvailableDataNum負数なら`-700162`。
4. Min & Maxで`RequestedDataNum = min(max(AvailableDataNum,0), Limit)`を作る。
5. RequestedDataNum=0 CaseはDLL本体とParserを呼ばず安全出力。
6. ChNum、RequestedDataNumをI64化してRequired Bytesを求める。
7. `Required Bytes<=Max Buffer Bytes AND <=2147483647`を検証する。失敗は`-700163`。
8. GetBufferDataを呼ぶ。
9. DataNum範囲違反は`-700164`。
10. Array Subsetで`DataNum×Packet Size`へ切り詰める。
11. Parserへ渡す。
12. Parsed Count不一致は`-700165`。
13. 最終errorをError_To_TestStatusへ接続する。

#### 9. 単体テスト

- AvailableDataNum=0。
- LimitよりAvailableが少ない。
- LimitよりAvailableが多い。
- Required Bytesが上限超過。
- DataNumが要求数未満。
- Parser件数一致／不一致。

---

### 10.13.3.5 `RAMScope_Set_Cond.vi`確認事項

`SetMeasCond → SetMeasCh → SetLoggingInfo`の順序を維持する。SetMeasCondまたはSetMeasCh後にSetLoggingInfoを実行し、保存用`logSize`と表示用`BuffSize`の両方を設定する。順序が既存資料どおりならVI内部の変更は不要である。

---

### 10.13.3.6 `RAMScope_Release.vi`呼出し位置

`ReleaseBufferData()`は表示用・保存用バッファを破棄する。ロギング専用PoCでは次の順へ固定する。

```text
Log Stop
→ 保存ログ全Block取得
→ TDMS追記完了
→ Release
```

`Log Stop → Release → GetLoggingData`の順にしない。

---

## 10.13.4 新規DLL Wrapper VI

全WrapperはC関数1個をCLFNで1回だけ呼ぶ。通常Wrapperは`error in.status=True`でCLFNを呼ばず、安全値と元errorを返す。

### 10.13.4.1 `RS_DLL_GT150GetGapTime.vi`

#### 0. 責務

MeasStart発行直後からハードウェアへの測定開始要求直前までの時間をms単位で取得する。

#### 1. 入力データ

```c
long RAMScopeGT150GetGapTime(long UnitNo, unsigned long *pGapTime);
```

#### 2. 出力

GapTimeMs U32、API ReturnCode I32、error out。

#### 3. 条件

UnitNoは現仕様0。既存error時はGapTimeMs=0。

#### 4. アルゴリズム

pGapTime左端子へU32 0を入れ、右端子から値を得る。

#### 5. 構造理由

Case Structureで既存error時のCLFN呼出しを止める。

#### 6. 入出力

UnitNo、error in／GapTimeMs、API ReturnCode、error out。

#### 7. CLFN Parameters

| 順 | 名前 | Type | Data Type | Pass |
|---:|---|---|---|---|
| Return | return | Numeric | Signed 32-bit | Value |
| 1 | UnitNo | Numeric | Signed 32-bit | Value |
| 2 | pGapTime | Numeric | Unsigned 32-bit | Pointer to Value |

Function Name：`RAMScopeGT150GetGapTime`

#### 8. 配線

UnitNo、U32 0、error inをCLFNへ接続し、pGapTime右端子をGapTimeMsへ接続する。ReturnCodeとCLFN errorを`RAMScope_Code_To_Error.vi`へ接続する。bypass側は0、0、元error。

#### 9. テスト

Start前、Start直後、Stop後、既存errorを確認する。

---

### 10.13.4.2 `RS_DLL_GT150GetMeasNum.vi`

#### 0. 責務

MeasStartからMeasStopまでに成立した測定回数を取得する。

#### 1. 入力データ

```c
long RAMScopeGT150GetMeasNum(long UnitNo, long *pMeasNum);
```

#### 2. 出力

MeasNum I32、API ReturnCode、error out。

#### 3. 条件

Stop後に使用する。既存error時はMeasNum=0。

#### 4. アルゴリズム

pMeasNum左端子へI32 0、右端子からMeasNum。

#### 5. 構造理由

既存errorバイパス用Case Structure。

#### 6. 入出力

UnitNo、error in／MeasNum、API ReturnCode、error out。

#### 7. CLFN Parameters

| 順 | 名前 | Type | Data Type | Pass |
|---:|---|---|---|---|
| Return | return | Numeric | Signed 32-bit | Value |
| 1 | UnitNo | Numeric | Signed 32-bit | Value |
| 2 | pMeasNum | Numeric | Signed 32-bit | Pointer to Value |

Function Name：`RAMScopeGT150GetMeasNum`

#### 8. 配線

I32 0をPointer左端子へ接続し、右端子をMeasNumへ接続する。ReturnCodeとerrorを共通変換する。

#### 9. テスト

測定0回、1回、複数回、測定中発行、既存error。

---

### 10.13.4.3 `RS_DLL_GT150GetBlockNum.vi`

#### 0. 責務

指定MeasNoのロギングBlock数を取得する。

#### 1. 入力データ

```c
long RAMScopeGT150GetBlockNum(long UnitNo, long MeasNo, long *pBlockNum);
```

#### 2. 出力

BlockNum I32、API ReturnCode、error out。

#### 3. 条件

`0 <= MeasNo < MeasNum`。既存error時は0。

#### 4. アルゴリズム

pBlockNum左端子0、右端子からBlockNum。

#### 5. 構造理由

通常Wrapper共通Case Structure。

#### 6. 入出力

UnitNo、MeasNo、error in／BlockNum、ReturnCode、error out。

#### 7. CLFN Parameters

| 順 | 名前 | Type | Data Type | Pass |
|---:|---|---|---|---|
| Return | return | Numeric | Signed 32-bit | Value |
| 1 | UnitNo | Numeric | Signed 32-bit | Value |
| 2 | MeasNo | Numeric | Signed 32-bit | Value |
| 3 | pBlockNum | Numeric | Signed 32-bit | Pointer to Value |

Function Name：`RAMScopeGT150GetBlockNum`

#### 8. 配線

Cプロトタイプ順に接続し、Pointer右端子をBlockNumへ接続する。bypass側は0、0、元error。

#### 9. テスト

先頭／末尾MeasNo、-1、MeasNum、BlockNum=0。

---

### 10.13.4.4 `RS_DLL_GT150GetBufferDataNum.vi`

#### 0. 責務

測定中の表示用バッファに現在保存されているPacket数を取得する。

#### 1. 入力データ

```c
long RAMScopeGT150GetBufferDataNum(long UnitNo, long MdlNo, long *pDataNum);
```

#### 2. 出力

AvailableDataNum I32、API ReturnCode、error out。

#### 3. 条件

RAMモニタMdlNoを指定する。既存error時は0。

#### 4. アルゴリズム

pDataNum左端子0、右端子からAvailableDataNum。

#### 5. 構造理由

通常Wrapper共通Case Structure。

#### 6. 入出力

UnitNo、MdlNo、error in／AvailableDataNum、ReturnCode、error out。

#### 7. CLFN Parameters

| 順 | 名前 | Type | Data Type | Pass |
|---:|---|---|---|---|
| Return | return | Numeric | Signed 32-bit | Value |
| 1 | UnitNo | Numeric | Signed 32-bit | Value |
| 2 | MdlNo | Numeric | Signed 32-bit | Value |
| 3 | pDataNum | Numeric | Signed 32-bit | Pointer to Value |

Function Name：`RAMScopeGT150GetBufferDataNum`

#### 8. 配線

Pointer左0、右AvailableDataNum。ReturnCodeを共通変換する。

#### 9. テスト

測定開始直後、Wait後、GetBufferData実行後、既存error。

---

### 10.13.4.5 `RS_DLL_GT150GetLoggingDataNum.vi`

#### 0. 責務

指定MeasNo、BlockNo、MdlNoの保存Packet数を取得する。

#### 1. 入力データ

```c
long RAMScopeGT150GetLoggingDataNum(
    long UnitNo,
    long MdlNo,
    long MeasNo,
    long BlockNo,
    long *pDataNum
);
```

#### 2. 出力

AvailableDataNum I32、API ReturnCode、error out。

#### 3. 条件

Stop後、Release前に使用する。MeasNoとBlockNoは上位APIで検証する。

#### 4. アルゴリズム

pDataNum左端子0、右端子から保存Packet数。

#### 5. 構造理由

通常Wrapper共通Case Structure。

#### 6. 入出力

UnitNo、MdlNo、MeasNo、BlockNo、error in／AvailableDataNum、ReturnCode、error out。

#### 7. CLFN Parameters

| 順 | 名前 | Type | Data Type | Pass |
|---:|---|---|---|---|
| Return | return | Numeric | Signed 32-bit | Value |
| 1 | UnitNo | Numeric | Signed 32-bit | Value |
| 2 | MdlNo | Numeric | Signed 32-bit | Value |
| 3 | MeasNo | Numeric | Signed 32-bit | Value |
| 4 | BlockNo | Numeric | Signed 32-bit | Value |
| 5 | pDataNum | Numeric | Signed 32-bit | Pointer to Value |

Function Name：`RAMScopeGT150GetLoggingDataNum`

#### 8. 配線

引数順を変更しない。Pointer右端子をAvailableDataNumへ接続する。bypass側は0、0、元error。

#### 9. テスト

Block先頭／末尾、DataNum=0、MeasNo不正、BlockNo不正、測定中発行。

---

### 10.13.4.6 `RS_DLL_GT150GetLoggingData.vi`

#### 0. 責務

指定Blockの保存PacketをU8一次元配列へコピーする。Packet解析は行わない。

#### 1. 入力データ

```c
long RAMScopeGT150GetLoggingData(
    long UnitNo,
    long MdlNo,
    long MeasNo,
    long BlockNo,
    void *pData,
    long *pDataNum,
    long *pLostDataNum
);
```

#### 2. 出力

Allocated Raw Buffer U8[]、DataNum I32、LostDataNum I32、ReturnCode、error out。

#### 3. 条件

RequestedDataNum>0、Buffer Byte Size>0、Stop後、Release前。

#### 4. アルゴリズム

- Buffer Byte Size分のU8配列をInitialize Array。
- RequestedDataNumをpDataNum左端子へ入力。
- pLostDataNum左端子はI32 0。
- CLFN後にpDataNum右端子から実取得数。

#### 5. 構造理由

Case Structure、Initialize Array、Array Data Pointer、Pointer to Valueを使用する。

#### 6. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| UnitNo、MdlNo、MeasNo、BlockNo | 入力 | I32 |
| RequestedDataNum | 入力 | I32 |
| Buffer Byte Size | 入力 | I32 |
| error in | 入力 | error cluster |
| Allocated Raw Buffer | 出力 | U8[] |
| DataNum、LostDataNum、ReturnCode | 出力 | I32 |
| error out | 出力 | error cluster |

#### 7. CLFN Parameters

| 順 | 名前 | Type | Data Type | Pass |
|---:|---|---|---|---|
| Return | return | Numeric | Signed 32-bit | Value |
| 1 | UnitNo | Numeric | Signed 32-bit | Value |
| 2 | MdlNo | Numeric | Signed 32-bit | Value |
| 3 | MeasNo | Numeric | Signed 32-bit | Value |
| 4 | BlockNo | Numeric | Signed 32-bit | Value |
| 5 | pData | Array | Unsigned 8-bit、1D | Array Data Pointer |
| 6 | pDataNum | Numeric | Signed 32-bit | Pointer to Value |
| 7 | pLostDataNum | Numeric | Signed 32-bit | Pointer to Value |

Function Name：`RAMScopeGT150GetLoggingData`

#### 8. 配線

1. Initialize Array出力をpData左端子へ接続する。
2. RequestedDataNumをpDataNum左端子へ接続する。
3. I32 0をpLostDataNum左端子へ接続する。
4. pData右端子をAllocated Raw Bufferへ接続する。
5. pDataNum右端子をDataNumへ接続する。
6. pLostDataNum右端子をLostDataNumへ接続する。
7. ReturnCodeとCLFN errorを共通変換する。
8. bypass側は空U8[]、DataNum=0、Lost=0、Return=0、元error。

#### 9. テスト

Requested=1、全件要求、実取得数が要求未満、DataNum=0、不正番号、既存error。引数7個であることをCLFN画面で再確認する。

---

## 10.13.5 新規公開API VI

### 10.13.5.1 `RAMScope_Get_Log_Summary.vi`

#### 0. 責務

Stop後の保存ログ列挙に必要なGapTimeMsとMeasNumを取得する。

#### 1. 入力データ

UnitNo、error in。

#### 2. 出力

GapTimeMs U32、MeasNum I32、Status、TestError、error out。

#### 3. 条件

Log Stop成功後、Release前。MeasNum<0は`-700170`。

#### 4. アルゴリズム

GetGapTime → GetMeasNum → MeasNum負数検証 → Error_To_TestStatus。

#### 5. 構造理由

error wireでAPI順序を固定し、負数だけCase Structureで止める。

#### 6. 入出力と接続

Logging PoCのStop直後に呼び、MeasNumを外側For LoopのNへ接続する。

#### 7. 配置するSubVI

`RS_DLL_GT150GetGapTime.vi`、`RS_DLL_GT150GetMeasNum.vi`、Less Than 0?、Case Structure、Format Into String、Bundle By Name、Error_To_TestStatus.vi。

#### 8. 配線順

1. GetGapTimeのerror outをGetMeasNumへ接続する。
2. MeasNum<0をCase selectorへ接続する。
3. Trueケース（MeasNum<0=True）でsource全文を作る。

```text
RAMScope_Get_Log_Summary.vi: MeasNum must not be negative. MeasNum=%d
```

4. status=True、code=-700170、sourceをBundle By Nameする。
5. FalseケースはWrapper errorを通す。
6. 最終errorをError_To_TestStatusへ接続する。

#### 9. テスト

MeasNum 0、1、複数、負数ダミー、GapTime APIエラー。

---

### 10.13.5.2 `RAMScope_Get_Block_Count.vi`

#### 0. 責務

指定MeasNoのBlockNumを取得し、番号と戻り件数を検証する。

#### 1. 入力

UnitNo、MeasNo、error in。

#### 2. 出力

BlockNum、Status、TestError、error out。

#### 3. 条件

MeasNo>=0。BlockNum>=0。

#### 4. アルゴリズム

入力検証 → GetBlockNum → 戻り値検証 → Error_To_TestStatus。

#### 5. 構造理由

DLLへ不正番号を渡す前のCaseと、戻り値検証Caseを分ける。

#### 6. 接続

Logging PoC外側For LoopのiをMeasNoへ接続し、BlockNumを内側For LoopのNへ接続する。

#### 7. 配置

Greater Or Equal 0?、Case Structure×2、Wrapper、Format Into String、Bundle By Name、Error_To_TestStatus。

#### 8. 配線順

- MeasNo<0：Wrapper未実行、code=-700171。

```text
RAMScope_Get_Block_Count.vi: MeasNo must not be negative. MeasNo=%d
```

- Wrapper正常後BlockNum<0：code=-700172。

```text
RAMScope_Get_Block_Count.vi: BlockNum must not be negative. MeasNo=%d, BlockNum=%d
```

- 正常時はBlockNumとerrorを通す。

#### 9. テスト

MeasNo -1、0、末尾、BlockNum 0、1、複数、負数ダミー。

---

### 10.13.5.3 `RAMScope_Read_Logging_Block.vi`

#### 0. 責務

指定MeasNo、BlockNoの保存Packet数を取得し、必要領域を確保してデータ本体を読み、実取得分へ切り詰め、既存Parserで1Blockを解析する。

#### 1. 入力データ

UnitNo、MdlNo_RAM、MeasNo、BlockNo、Channel List、Byte Order、Max Buffer Bytes I64、error in。

#### 2. 出力データモデル

```text
AvailableDataNum I32
RequestedDataNum I32
DataNum I32
LostDataNum I32
Raw Buffer U8[]
Packets RAMScope_Packet.ctl[]
Parsed Packet Count I32
Unused Byte Count I32
Status、TestError、error out
```

#### 3. 前提条件・異常条件

```text
ChNum>=1
MeasNo>=0
BlockNo>=0
Max Buffer Bytes>0
AvailableDataNum>=0
0<=DataNum<=RequestedDataNum
Required Bytes<=Max Buffer Bytes
Required Bytes<=2147483647
Parsed Packet Count==DataNum
```

#### 4. 処理アルゴリズム

```text
AvailableDataNum = GetLoggingDataNum
if AvailableDataNum == 0:
    空データを正常返却
else:
    RequestedDataNum = AvailableDataNum
    Packet Size = ChNum×4+12
    Required Bytes = RequestedDataNum×Packet Size  // I64
    上限検証
    GetLoggingData
    DataNum範囲検証
    Actual Bytes = DataNum×Packet Size
    Array SubsetでRaw切詰め
    Parse Buffer
    Parsed Count照合
```

#### 5. LabVIEW構造の選定理由

1Blockだけを扱い、MeasNo／BlockNoの反復はLogging PoCまたはTestStandへ任せる。これによりPublic VI内で巨大な全ログ配列を保持しない。

#### 6. 入出力と接続

Logging PoC内側For LoopからMeasNoとBlockNoを受け、出力Packetsを`RAMScope_File_Log_Append.vi`へ直結する。

#### 7. 配置する関数およびSubVI

- `RS_DLL_GT150GetLoggingDataNum.vi`。
- `RS_DLL_GT150GetLoggingData.vi`。
- `RAMScope_Parse_Buffer.vi`。
- Array Size、I64変換、Multiply、Add、Array Subset。
- Case Structure 5個以上。
- Format Into String、Bundle By Name、Error_To_TestStatus.vi。

#### 8. 配線順

1. 入力検証Case。失敗は`-700173`。

```text
RAMScope_Read_Logging_Block.vi: Input is invalid. ChNum=%d, MeasNo=%d, BlockNo=%d, MaxBufferBytes=%lld
```

2. GetLoggingDataNumを呼ぶ。
3. AvailableDataNum<0は`-700174`。
4. AvailableDataNum=0は本体DLLとParserを呼ばず空配列。
5. I64でRequired Bytesを計算する。
6. 上限違反は`-700175`。

```text
RAMScope_Read_Logging_Block.vi: Required buffer size is invalid or exceeds the limit. RequiredBytes=%lld, MaxBufferBytes=%lld, AvailableDataNum=%d, PacketSize=%lld
```

7. RequestedDataNum=AvailableDataNumをGetLoggingDataのpDataNum左端子へ渡す。
8. `0<=DataNum<=RequestedDataNum`を検証する。違反は`-700176`。
9. Raw BufferをActual Bytesへ切り詰める。
10. Parserへ渡す。
11. Parsed Count不一致は`-700177`。
12. 各Caseの全出力トンネルを配線し、Use default if unwiredを使わない。
13. 最終errorをError_To_TestStatusへ接続する。

#### 9. 単体テスト

Channel List空、番号負数、DataNum=0、上限超過、DataNum要求未満、DataNum範囲外、Parser不一致、LostDataNum非ゼロ。

---

## 10.13.6 LabVIEW側TDMS保存VI

### 10.13.6.1 TDMS構造

```text
Root Properties
  TestName
  MeasurementStartTime
  A2LFileName
  UnitNo
  MdlNo_RAM
  ByteOrder
  ChannelCount
  PacketSize
  GapTimeMs

Group: RAMScope_Meas0000_Block0000
  Properties
    MeasNo
    BlockNo
    RequestedDataNum
    DataNum
    LostDataNum
    PacketSize

  Channels
    Time_s
    Time_Raw
    Flag_Raw
    Status
    Skip
    LogTrigger
    Dummy
    EventBits
    DataLost
    <Channel Name 0>
    <Channel Name 1>
    ...
```

Boolean状態は解析ツール互換性を優先し、TDMS上ではU8の0／1として保存する。測定値チャンネルはEngineering Value DBLを保存し、Raw値、Address、Size、Sign、Scale、Offset、UnitはChannel Propertyへ保存する。

---

### 10.13.6.2 `RAMScope_File_Log_Open.vi`

#### 0. 責務

出力先TDMSを開き、後続VIへFile Referenceを返す。

#### 1. 入力

File Path、Overwrite?、error in。

#### 2. 出力

TDMS File Ref、File Open?、Status、TestError、error out。

#### 3. 条件

空Path不可。既存ファイルかつOverwrite?=Falseは`-700178`。

#### 4. アルゴリズム

Path検証 → Exists? → Overwrite Case → TDMS Open → File Open?更新。

#### 5. 構造理由

既存ファイル動作をCaseで明示し、暗黙上書きをしない。

#### 6. 入出力と接続

Logging PoCのSet Cond成功後、Log Start前に呼ぶ。File RefはPoCの通常ワイヤとCleanup Caseへ通す。

#### 7. 配置

Empty String/Path?、Check if File or Folder Exists、Case Structure、TDMS Open、Error_To_TestStatus。

#### 8. 配線順

- Path不正または上書き拒否時：TDMS Open未実行、Not A Refnum相当、安全なFile Open? False。
- 正常時：Operation=`create or replace`、File Open?=`NOT(error.status)`。
- source全文：

```text
RAMScope_File_Log_Open.vi: Output file already exists and overwrite is disabled. Path=%s
```

#### 9. テスト

新規Path、既存Path上書き有／無、書込権限なし、既存error。

---

### 10.13.6.3 `RAMScope_File_Log_Write_Metadata.vi`

#### 0. 責務

TDMS Rootおよび各測定チャンネルに、後のMF4変換へ必要なメタデータを記録する。

#### 1. 入力

TDMS Ref、TestName、Start Time、A2L File Name、UnitNo、MdlNo_RAM、Byte Order、Channel List、GapTimeMs、error in。

#### 2. 出力

同じTDMS Ref、Status、TestError、error out。

#### 3. 条件

File Ref有効、Channel List非空。A2L File Nameは空を許容する。

#### 4. アルゴリズム

Root Properties書込 → Channel List For LoopでChannel Property書込 → Flush任意。

#### 5. 構造理由

チャンネルごとに同じProperty処理を行うためFor Loop。

#### 6. 入出力と接続

Open直後、Log Start前に1回だけ呼ぶ。

#### 7. 配置

TDMS Set Properties、For Loop、Unbundle By Name、Format Into String、Error_To_TestStatus。

#### 8. 配線順

1. RootへTestName等を設定する。
2. Channel Listを自動インデックスでFor Loopへ入れる。
3. Group名テンプレートではなく、Channel Propertyテンプレート用の一時Group名`RAMScope_Metadata`を使用するか、Rootへ`Channel_<index>_<property>`形式で保存する。
4. 既存error時は書込をスキップしてRefを通す。
5. Property書込失敗は元のTDMS errorを保持する。

#### 9. テスト

日本語TestName、空A2L名、複数Channel、書込失敗、既存error。

---

### 10.13.6.4 `RAMScope_File_Log_Append.vi`

#### 0. 責務

1Block分の解析済みPacketsと取得状態を、Block固有Groupへ追記する。

#### 1. 入力

TDMS Ref、MeasNo、BlockNo、RequestedDataNum、DataNum、LostDataNum、PacketSize、Packets、Channel List、Flush After Write?、error in。

#### 2. 出力

TDMS Ref、Written Packet Count、Status、TestError、error out。

#### 3. 条件

`Array Size(Packets)==DataNum`。Channel Listの順番がPackets内Channel Valuesと一致する。

#### 4. アルゴリズム

```text
Group Name = Format("RAMScope_Meas%04d_Block%04d")
Group Propertiesを書込
Packet共通配列を書込
for ChannelIndex:
    for PacketIndex:
        Packets[PacketIndex].Channel Values[ChannelIndex].Engineering Valueを抽出
    Channel NameでTDMS Write
    Raw/Address/Size/Sign/Scale/Offset/UnitをChannel Propertyへ保存
if Flush After Write?: TDMS Flush
```

#### 5. 構造理由

Block単位で即時保存し、全Blockをメモリへ蓄積しない。Channel×Packetの2重For Loopで列方向配列を作る。

#### 6. 入出力と接続

`RAMScope_Read_Logging_Block.vi`の直後に配置し、次Block取得前に完了させる。

#### 7. 配置

Format Into String、TDMS Set Properties、TDMS Write、For Loop×2、Index Array、Bundle/Unbundle、Select、TDMS Flush、Error_To_TestStatus。

#### 8. 配線順

1. `Array Size(Packets)==DataNum`を検証する。不一致は`-700180`。
2. Group Nameを`RAMScope_Meas%04d_Block%04d`で作る。
3. Group PropertyへMeasNo、BlockNo、RequestedDataNum、DataNum、LostDataNum、PacketSizeを設定する。
4. PacketsからTime、Flag各fieldの一次元配列を作り、それぞれTDMS Writeする。
5. BooleanはSelectでU8 1／0へ変換する。
6. Channel外側For LoopでEngineering Value配列を作る。
7. Channel名が空の場合は`Channel_%03d`を使用する。
8. 同名Channelがある場合はIndexを付加して一意化する。
9. Flush入力がTrueならTDMS Flushする。
10. Written Packet Count=DataNumを返す。

source全文：

```text
RAMScope_File_Log_Append.vi: Packet count does not match DataNum. PacketCount=%d, DataNum=%d, MeasNo=%d, BlockNo=%d
```

#### 9. テスト

DataNum=0、1、複数、同名Channel、空Channel名、日本語名、Lost非ゼロ、Flush有／無、件数不一致。

---

### 10.13.6.5 `RAMScope_File_Log_Close.vi`

#### 0. 責務

前段errorの有無にかかわらずTDMS FlushとCloseを試行し、最初のerrorを保持するCleanup VI。

#### 1. 入力

TDMS Ref、File Open?、Original error。

#### 2. 出力

File Open? False、Status、TestError、Final error。

#### 3. 条件

File Open?=FalseならTDMS関数を呼ばない。Trueなら前段errorをClearしたCleanup用wireでFlush、Closeする。

#### 4. アルゴリズム

```text
if File Open?:
    Cleanup Error = Clear Errors(Original Error)
    TDMS Flush
    TDMS Close
    Final Error = Merge Errors(Original Error, Cleanup Error)
else:
    Final Error = Original Error
```

#### 5. 構造理由

File Open?をselectorとするCase Structure。Original Errorを優先するMerge Errors。

#### 6. 入出力と接続

Logging PoCの通常終了とCleanupの両方から呼ぶ。

#### 7. 配置

Case Structure、Clear Errors、TDMS Flush、TDMS Close、Merge Errors、Error_To_TestStatus。

#### 8. 配線順

TrueケースでOriginal Errorを保持用とCleanup用へ分岐する。Cleanup用だけClear Errorsし、Flush→Close。Merge Errorsの上側へOriginal、下側へClose Error。FalseケースはRefを使用せずOriginalを通す。両CaseでFile Open? Falseを出力する。

#### 9. テスト

正常Close、前段error付きClose、無効Ref、二重Close、Flush error、Close error。

---

## 10.13.7 `PoC_RAMScope_Logging_Main.vi`

### 0. 実現したい機能とVIの責務

RAMScope機器側ロギングから停止後の全保存Block取得、Packet解析、TDMS保存、CleanupまでをTestStandなしで一度通し、ロギング機能を単独検証する。

既存`PoC_RAMScope_Main.vi`は変更せず、本VIだけにTDMSと保存ログ回収処理を置く。

### 1. 入力データの実体

```text
UnitNo I32
Byte Order
Meas Config
Channel List
Module Log Configs
Measurement Duration ms
TDMS File Path
Overwrite?
TestName
A2L File Name
Max Buffer Bytes I64
Flush Every Block?
error in
```

### 2. 出力データモデル

```text
UnitNum、kind
Module List、MdlNo_RAM、MdlNo_CAN、Endian_RAM
GapTimeMs、MeasNum
Total Block Count I32
Total Packet Count I64
Total LostDataNum I64  // 参考集計。Block別値もTDMSへ保存
Last MeasNo、Last BlockNo
Final State RAMScope_Logging_PoC_State.ctl
Status、TestError、error out
```

`Total LostDataNum`はAPI値の累積／差分仕様が実機で確定するまで参考表示とし、判定にはBlockごとの`LostDataNum`とPacketの`Data Lost?`を使用する。

### 3. 前提条件・異常条件

- 既存通信PoCがDeviceInitからReadまで成功していること。
- TDMS Open成功前にLog Startしない。
- Log Stop成功前に保存ログ取得APIを呼ばない。
- 全Block取得前にReleaseしない。
- 途中errorでもFile Close、Release、DeviceExitを可能な範囲で試行する。

### 4. 処理アルゴリズム

```text
State = all False
Main Error = error in

Connect
Connected?更新

Init
Set Cond

File Log Open
File Open?更新
Write Metadata

Log Start
Measurement Started?更新
Wait Measurement Duration
Log Stop
Stopped?更新

Get Log Summary
Log Summary Read?更新

for MeasNo = 0 ... MeasNum-1:
    Get Block Count
    Total Block Count += BlockNum

    for BlockNo = 0 ... BlockNum-1:
        Read Logging Block
        File Log Append
        Total Packet Count += DataNum
        Block別LostDataNumをTDMSへ保存

Logging Retrieved?更新

Release
Released?更新

File Log Close
File Open?=False

Close Device

Cleanup:
    if Measurement Started? AND NOT Stopped?:
        Clear ErrorsしてLog Stopを試行
    if Stopped? AND NOT Released?:
        Clear ErrorsしてReleaseを試行
    if File Open?:
        File Log Closeを試行
    if Connected?:
        RAMScope_Close.viを試行
    Original Errorを最優先でMerge
```

### 5. LabVIEW構造の選定理由

- MeasNoとBlockNoは2重For Loop。
- Total Block／Packet数はShift Register。
- Stateは`RAMScope_Logging_PoC_State.ctl`を通常ワイヤとLoop Shift Registerで保持。
- Cleanup要否はCase Structure。
- 測定時間保証はFlat Sequenceまたはerror wire＋Wait。既存通信PoCと同じ正式方式へ合わせる。
- 1Block取得直後にTDMS Appendし、巨大配列を保持しない。

### 6. フロントパネル入出力と接続元・接続先

| 出力 | 生成元 |
|---|---|
| UnitNum、kind | `RAMScope_Connect.vi` |
| Module List、MdlNo | `RAMScope_Init.vi` |
| GapTimeMs、MeasNum | `RAMScope_Get_Log_Summary.vi` |
| Total Block Count | 外側For Loop Shift Register |
| Total Packet Count | 内側For Loop DataNum累積 |
| Final State | Cleanup後State |
| Status、TestError、error out | 最後のClose Case出力トンネル |

### 7. 配置する関数およびSubVI

- 既存公開API：Connect、Init、Set Cond、Log Start、Log Stop、Release、Close。
- 新規公開API：Get Log Summary、Get Block Count、Read Logging Block。
- TDMS VI：Open、Write Metadata、Append、Close。
- For Loop×2、Shift Register、Case Structure、Bundle By Name、Unbundle By Name、Clear Errors、Merge Errors、Error_To_TestStatus。
- `RAMScope_Logging_PoC_State.ctl`。

### 8. 配線順

#### A. 専用State ctlを作る

```text
Connected?             Boolean False
File Open?             Boolean False
Measurement Started?   Boolean False
Stopped?               Boolean False
Log Summary Read?      Boolean False
Logging Retrieved?     Boolean False
Released?              Boolean False
```

`RAMScope_Logging_PoC_State.ctl`としてtypedef保存する。既存`RAMScope_PoC_State.ctl`を変更しない。

#### B. ConnectからSet Cond

既存通信PoCと同じ公開API、同じerror wire順を使用する。Connect成功時だけConnected?をTrueに更新する。

#### C. TDMS OpenとMetadata

1. Set Cond error outをFile Log Openへ接続する。
2. Open成功時にFile Open?をTrueへ更新する。
3. File RefとerrorをWrite Metadataへ接続する。
4. Write Metadata error outをLog Startへ接続する。

#### D. Start、Wait、Stop

1. Log Start成功時にMeasurement Started?をTrue。
2. Measurement DurationをWaitへ接続する。
3. Wait後にLog Stop。
4. Stop成功時にStopped?をTrue。

#### E. Summaryと2重For Loop

1. Stop error outをGet Log Summaryへ接続する。
2. 成功時にLog Summary Read?をTrue。
3. MeasNumを外側For Loop Nへ接続する。
4. 外側iをMeasNoへ接続する。
5. Get Block CountのBlockNumを内側For Loop Nへ接続する。
6. 内側iをBlockNoへ接続する。
7. Read Logging BlockのPackets、件数、LostをAppendへ接続する。
8. Append error outを次反復へShift Registerで渡す。
9. 各Block終了後にTotal Packet CountをI64加算する。
10. 両Loop正常終了時だけLogging Retrieved?をTrue。

#### F. ReleaseとFile Close

1. Logging Retrieved後にRelease。
2. Release成功時にReleased?をTrue。
3. Release後にFile Log Close。
4. File Open?をFalseへ更新する。
5. Device Closeへ進む。

#### G. Cleanup

Original Errorを別wireで保持する。

```text
Cleanup Stop条件
= Measurement Started? AND NOT Stopped?

Cleanup Release条件
= Stopped? AND NOT Released?

Cleanup File Close条件
= File Open?

Cleanup Device Close条件
= Connected?
```

各Cleanup APIへ渡すwireだけClear Errorsし、戻りerrorをMerge Errorsの後順位入力へ接続する。Original Errorを最上位入力に固定する。

### 9. 単体テスト

1. 正常1Meas、1Block。
2. 正常1Meas、複数Block。
3. 複数Meas。
4. BlockNum=0。
5. DataNum=0。
6. TDMS既存ファイル上書き拒否。
7. Log Start失敗。
8. Log Stop失敗後Cleanup Stop。
9. Block取得途中エラー後Release、File Close、Device Close。
10. LostDataNum非ゼロとData Lost Flag非ゼロ。
11. 大容量BlockでMax Buffer Bytesガード。
12. TDMS再読込でGroup数、DataNum、チャンネル長、Time単調増加を照合。

---

## 10.13.8 通信確認PoCとロギングPoCの完成条件

### `PoC_RAMScope_Main.vi`

- [ ] 既存VI名と構成を維持。
- [ ] Connect、Init、Set Cond、Start、短時間Read、Stop、Release、Closeを確認。
- [ ] TDMS File Refを持たない。
- [ ] GetMeasNum／GetBlockNum／GetLoggingDataを呼ばない。
- [ ] 通信・DLL・Packet Parserの最小切り分けに使用。

### `PoC_RAMScope_Logging_Main.vi`

- [ ] TDMS Open後にStart。
- [ ] Stop後にSummaryを取得。
- [ ] MeasNoとBlockNoを全列挙。
- [ ] 1Block取得直後にTDMS Append。
- [ ] 全Block後にRelease。
- [ ] File CloseとDevice CloseをCleanupで試行。
- [ ] Packet CountとDataNumが一致。
- [ ] Flag Raw、Status、Skip、Log Trigger、Dummy、Event、Data Lostを保存。
- [ ] Time RawとTime Secondsを保存。
- [ ] LostDataNumをBlock Propertyへ保存。

---

## 10.13.9 TestStand組込み順

```text
Setup
  RAMScope_Connect.vi
  RAMScope_Init.vi
  RAMScope_Set_Cond.vi
  RAMScope_File_Log_Open.vi
  RAMScope_File_Log_Write_Metadata.vi

Main
  RAMScope_Log_Start.vi
  DUT試験
  RAMScope_Log_Stop.vi
  RAMScope_Get_Log_Summary.vi

  For MeasNo
    RAMScope_Get_Block_Count.vi
    For BlockNo
      RAMScope_Read_Logging_Block.vi
      RAMScope_File_Log_Append.vi

Cleanup
  RAMScope_Release.vi
  RAMScope_File_Log_Close.vi
  RAMScope_Close.vi
```

TestStand側はMeasNo、BlockNoのLoop、試験条件、判定、レポートを担当する。DLL関数をTestStandから直接呼ばない。

---

## 10.13.10 実機PoCで最終確認する項目

- [ ] 使用DLL、同梱ヘッダ、APIマニュアルの関数宣言が一致。
- [ ] `GetLoggingData`は7引数。
- [ ] pDataNum左が要求数、右が実取得数。
- [ ] Data順がSetMeasCh順。
- [ ] 1byte／2byte／4byteが各4byteスロットで正しく復号。
- [ ] Flag各fieldがRAMScopeVP表示と一致。
- [ ] Time差分×20nsが実時間と一致。
- [ ] GetMeasNum、GetBlockNumが純正表示と一致。
- [ ] GetLoggingDataNumと実DataNumの関係が妥当。
- [ ] LostDataNumが差分か累積かを実機で確定し、本節へ追記。
- [ ] 全Block取得後までReleaseされない。
- [ ] TDMS再読込で全チャンネル長がDataNumと一致。
- [ ] MF4変換PoCでTime、単位、チャンネル数が維持される。

---

## 10.13.11 実装順

```text
Phase 1：既存ParserとRead修正
  1. RAMScope_Packet.ctl
  2. RAMScope_Parse_Buffer.vi
  3. RS_DLL_GT150GetBufferData.vi確認
  4. RS_DLL_GT150GetBufferDataNum.vi
  5. RAMScope_Read.vi

Phase 2：停止後保存ログ取得
  6. RS_DLL_GT150GetGapTime.vi
  7. RS_DLL_GT150GetMeasNum.vi
  8. RS_DLL_GT150GetBlockNum.vi
  9. RS_DLL_GT150GetLoggingDataNum.vi
  10. RS_DLL_GT150GetLoggingData.vi
  11. RAMScope_Get_Log_Summary.vi
  12. RAMScope_Get_Block_Count.vi
  13. RAMScope_Read_Logging_Block.vi

Phase 3：TDMS
  14. RAMScope_File_Log_Open.vi
  15. RAMScope_File_Log_Write_Metadata.vi
  16. RAMScope_File_Log_Append.vi
  17. RAMScope_File_Log_Close.vi

Phase 4：専用PoC
  18. RAMScope_Logging_PoC_State.ctl
  19. PoC_RAMScope_Logging_Main.vi
```

各Phase終了時に単体テストを完了し、通信確認用`PoC_RAMScope_Main.vi`が従来どおり動くことを回帰確認する。
'''

DOC.write_text(text, encoding="utf-8", newline="\n")
DRAFT.unlink(missing_ok=True)
SELF.unlink(missing_ok=True)
WORKFLOW.unlink(missing_ok=True)
