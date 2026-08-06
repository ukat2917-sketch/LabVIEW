from __future__ import annotations

from pathlib import Path
import sys

DOC = Path("docs/10_RAMScope実装方針.md")
MARKER_START = "<!-- ramscope-metadata-detail-start -->"
MARKER_END = "<!-- ramscope-metadata-detail-end -->"

DETAIL = r'''

<!-- ramscope-metadata-detail-start -->
#### 10.12.3A `RAMScope_File_Log_Write_Metadata.vi`確定仕様・詳細作成手順

> 本項は直前の概要を削除せず、[00A_LabVIEW実装資料の記述ルール.md](./00A_LabVIEW実装資料の記述ルール.md)と[00B_LabVIEW学習型VI設計ルール.md](./00B_LabVIEW学習型VI設計ルール.md)に従って、データモデル、構造選定、端子、配線および単体テストを具体化する。

##### 0. 実現したい機能とVIの責務

`RAMScope_File_Log_Write_Metadata.vi`は、開かれているTDMS FileのRootへ、試験全体情報と測定Channel定義を1回だけ記録する。

```text
Log Stop
  → Get Log Summary
  → Write Metadata
  → 最初のBlockをAppend
```

このVIは次を担当しない。

- TDMS Groupや測定データChannelの作成。
- Packet値の追記。
- TDMS Flush。
- TDMS Close。

MetadataをRootへ保存する理由は、後段のDIAdem処理やMF4変換で、信号名、Address、型、単位および工学値換算を再構成できるようにするためである。

##### 1. 入力データの実体

`Channel List`は`RAMScope_Channel.ctl`を要素に持つ一次元配列であり、1要素が1測定Channelを表す。

```text
Channel List : RAMScope_Channel.ctl[]
├─ [0] Channel Index 0
├─ [1] Channel Index 1
└─ ...
```

`RAMScope_Channel.ctl`のフィールド名と型を次で固定する。

| フィールド | 型 | Metadataで使用 | 用途 |
|---|---|---|---|
| `Name` | String | 使用 | 信号名 |
| `Enable` | U32 | 使用しない | CHINFOの有効設定 |
| `Core` | U32 | 使用しない | CHINFOのCore設定 |
| `Address` | U32 | 使用 | RAM Address |
| `Size` | U32 | 使用 | `0=1byte`、`1=2byte`、`2=4byte` |
| `Sign` | U32 | 使用 | `0=unsigned`、`1=signed` |
| `Speed` | U32 | 使用しない | CHINFOの速度コード |
| `Scale` | DBL | 使用 | 工学値換算係数 |
| `Offset` | DBL | 使用 | 工学値換算オフセット |
| `Unit` | String | 使用 | 工学単位 |

Forループ内の`Unbundle By Name`では、typedefと同じ大文字小文字で次の7項目を選択する。

```text
Name
Address
Size
Sign
Scale
Offset
Unit
```

全入力端子は次とする。

| 端子名 | 方向 | 型 | 用途 |
|---|---|---|---|
| `TDMS Ref` | 入力 | TDMS File Refnum | `RAMScope_File_Log_Open.vi`が返した参照 |
| `TestName` | 入力 | String | 試験名 |
| `Start Time` | 入力 | Timestamp | Log Start直前に取得した絶対時刻 |
| `A2L File Name` | 入力 | String | 使用したA2Lファイル名。空文字を許容 |
| `UnitNo` | 入力 | I32 | 操作対象Unit番号 |
| `MdlNo_RAM` | 入力 | I32 | RAMモジュール番号 |
| `Byte Order` | 入力 | `RAMScope_Byte_Order.ctl` | Parserに使用したEndian |
| `Channel List` | 入力 | `RAMScope_Channel.ctl[]` | 測定Channel定義 |
| `GapTimeMs` | 入力 | U32 | `RAMScope_Get_Log_Summary.vi`の出力 |
| `error in` | 入力 | error cluster | 前段エラー |

##### 2. 出力データモデル

| 端子名 | 方向 | 型 | 用途 |
|---|---|---|---|
| `TDMS Ref out` | 出力 | TDMS File Refnum | 入力Refを後続AppendまたはCloseへ渡す |
| `Status` | 出力 | `Status.ctl` | TestStand判定用状態 |
| `TestError` | 出力 | `TestError.ctl` | 機器名、code、message等 |
| `error out` | 出力 | error cluster | 最初に成立したエラー |

`TDMS Ref out`は全Caseで明示配線し、`Use default if unwired`を使用しない。

Root Property名とTDMS保存型を次で固定する。

| 書込順 | Property Name | 値 | TDMS保存型 |
|---:|---|---|---|
| 1 | `TestName` | `TestName`入力 | String |
| 2 | `MeasurementStartTime` | `Start Time`入力 | Timestamp |
| 3 | `A2LFileName` | `A2L File Name`入力 | String |
| 4 | `UnitNo` | `UnitNo`入力 | I32 |
| 5 | `MdlNo_RAM` | `MdlNo_RAM`入力 | I32 |
| 6 | `ByteOrder` | 明示変換した表示文字列 | String |
| 7 | `ChannelCount` | `Array Size(Channel List)` | I32 |
| 8 | `PacketSize` | `ChannelCount × 4 + 12` | I32 |
| 9 | `GapTimeMs` | `GapTimeMs`入力 | U32 |

`StartTime`という別名を使用しない。固定キーは`MeasurementStartTime`とする。Timestampを文字列またはUnix timeへ変換しない。

数値Propertyは文字列化せず、数値型のまま保存する。

##### 3. 前提条件・異常条件

処理の優先順位を次で固定する。

```text
1. error inの既存エラー
2. TDMS Ref無効
3. Channel List空
4. Root Property書込中に最初に発生したNI標準TDMS error
5. Channel Property書込中に最初に発生したNI標準TDMS error
```

| 条件 | 処理 |
|---|---|
| `error in.status=True` | 入力検証とTDMS書込を完全にスキップし、Refと元errorを通す |
| TDMS Ref無効 | `-700179`を返し、Property書込を実行しない |
| `Array Size(Channel List)<=0` | `-700181`を返し、Property書込を実行しない |
| `A2L File Name`が空 | `A2LFileName=""`としてProperty自体は書く |
| TDMS Set Propertiesが失敗 | NI標準TDMS errorをそのまま保持し、独自errorへ変換しない |

TDMS Ref無効時のsource全文：

```text
RAMScope_File_Log_Write_Metadata.vi: TDMS file reference is invalid.
```

```text
基準クラスタ = error inの正常クラスタ
status       = Boolean True
code         = I32 -700179
source       = 上記固定文字列
```

Channel List空時のsource全文：

```text
RAMScope_File_Log_Write_Metadata.vi: Channel List must not be empty. ChannelCount=%d
```

```text
%d           = ChannelCount I32
基準クラスタ = TDMS Ref有効判定を通過した正常error
status       = Boolean True
code         = I32 -700181
source       = Format Into String出力
```

##### 4. 処理アルゴリズム

LabVIEW関数へ落とし込む前の処理を次とする。

```text
if error inあり:
    TDMS Refと元errorを返す
else if TDMS Ref無効:
    -700179を返す
else:
    ChannelCount = Channel List要素数
    if ChannelCount == 0:
        -700181を返す
    else:
        PacketSize = ChannelCount × 4 + 12
        Byte Orderを表示文字列へ変換する
        Root Property 9項目を順番に書く

        for Channel Index, Channel in Channel List:
            Prefix = Channel_%03d
            Channel Property 7項目をRootへ順番に書く

        最初に発生したerrorを返す
```

各Channel DataはPacket内で4byte固定であり、その後ろへFlag 4byteとTimestamp 8byteが続く。そのため次となる。

```text
PacketSize = ChannelCount × 4 + 4 + 8
           = ChannelCount × 4 + 12
```

##### 5. LabVIEW構造の選定理由

- 既存errorを最優先するため、`error in.status`をselectorとする最外周Case Structureを使用する。
- TDMS Ref無効とChannel List空を別の原因として識別するため、入力検証を多段Case Structureに分ける。
- Channel Listの全要素へ同じ7 Property書込を適用するため、Forループを使用する。
- Forループ反復間で同じTDMS Refと最初のerrorを保持するため、TDMS Refとerror clusterのShift Registerを使用する。
- Byte OrderのEnum登録順とSYSINFOの数値コードを混同しないため、Case Structureで表示文字列へ明示変換する。
- Property書込順を固定し、最初のNI標準TDMS errorで後続処理を止めるため、TDMS Set PropertiesをRef wireとerror wireで直列接続する。
- Metadata直後にAppendを実行し、AppendまたはCloseがFlushを担当するため、このVIにはTDMS Flushを配置しない。

##### 6. フロントパネル入出力と接続元・接続先

| 本VI端子 | 接続元 | 接続先 |
|---|---|---|
| `TDMS Ref` | `RAMScope_File_Log_Open.vi / TDMS Ref` | 本VI内のRoot書込、Channel Forループ、`TDMS Ref out` |
| `Start Time` | Log Start直前の`Get Date/Time In Seconds` | Root `MeasurementStartTime` |
| `GapTimeMs` | `RAMScope_Get_Log_Summary.vi / GapTimeMs` | Root `GapTimeMs` |
| `Channel List` | SetMeasChへ渡した同一配列 | Channel Property書込、ChannelCount、PacketSize |
| `TDMS Ref out` | 本VIの最終Ref | `RAMScope_File_Log_Append.vi`または`RAMScope_File_Log_Close.vi` |
| `error out` | 本VIの最終error | 最初の`RAMScope_File_Log_Append.vi / error in` |

##### 7. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所・追加方法 | 用途 |
|---:|---|---|---|---|
| 1 | 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント | `error in.status`を取得 |
| 3以上 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ | 既存error、Ref、ChannelCount、Byte Order分岐 |
| 1 | 数値／パス／Refnumではない? | Not A Number/Path/Refnum? | プログラミング → 比較 | TDMS Ref無効判定 |
| 1 | 配列サイズ | Array Size | プログラミング → 配列 | ChannelCount算出 |
| 1 | 以下? | Less Or Equal? | プログラミング → 比較 | `ChannelCount<=0`判定 |
| 1 | 乗算 | Multiply | プログラミング → 数値 | `ChannelCount×4` |
| 1 | 加算 | Add | プログラミング → 数値 | PacketSizeへ12を加算 |
| 1 | Forループ | For Loop | プログラミング → ストラクチャ | 1反復で1Channelを処理 |
| 2 | シフトレジスタ | Shift Register | Forループ枠を右クリック | Refとerrorを反復間で保持 |
| 1 | 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント | Channel 7フィールドを取得 |
| 1以上 | 文字列にフォーマット | Format Into String | プログラミング → 文字列 | `Channel_%03d`とローカルerror source |
| 7 | 文字列連結 | Concatenate Strings | プログラミング → 文字列 | PrefixへSuffixを追加 |
| 16 | TDMSプロパティ設定 | TDMS Set Properties | ストレージ／ファイルI/O → TDMストリーミング | Root 9項目とChannel 7項目を書込 |
| 2 | 名前でバンドル | Bundle By Name | プログラミング → クラスタ、クラス、バリアント | `-700179`、`-700181`を生成 |
| 1 | `Error_To_TestStatus.vi` | SubVI | 共通エラー処理フォルダ | 最終errorをStatus/TestErrorへ変換 |

LabVIEW Versionにより日本語パレット名が異なる場合は、`Ctrl + Space`でQuick Dropを開き、英語名を入力して配置する。

##### 8. 配線順

###### A. 最外周Case Structureを作る

1. `error in`を`Unbundle By Name`のクラスタ入力へ接続する。
2. `Unbundle By Name`の要素を`status`へ設定する。
3. `status` Booleanを最外周Case Structureのselector端子へ接続する。
4. `TDMS Ref`と`error in`をCase左枠の入力トンネルへ接続する。
5. `TDMS Ref out`と最終error用の出力トンネルをCase右枠へ作る。

**Trueケース（`error in.status=True`：既存エラーあり）**

1. `TDMS Ref`入力トンネルを`TDMS Ref out`出力トンネルへそのまま接続する。
2. `error in`入力トンネルをerror出力トンネルへそのまま接続する。
3. TDMS Ref判定、Array Size、TDMS Set Properties、Forループを配置しない。

**Falseケース（`error in.status=False`：既存エラーなし）**

TDMS Ref有効判定へ進む。

###### B. TDMS Ref有効判定を作る

1. `Not A Number/Path/Refnum?`を配置する。
2. `TDMS Ref`を同関数の入力へ接続する。
3. Boolean出力を`TDMS Ref Invalid?` Case Structureのselectorへ接続する。

**Trueケース（`TDMS Ref Invalid?=True`：無効Ref）**

1. 文字列定数へ次の全文を入力する。

```text
RAMScope_File_Log_Write_Metadata.vi: TDMS file reference is invalid.
```

2. `Bundle By Name`の基準クラスタへ最外周Falseケースへ入った正常な`error in`を接続する。
3. Boolean定数`True`を`status`へ接続する。
4. I32定数`-700179`を`code`へ接続する。
5. 固定文字列を`source`へ接続する。
6. `Bundle By Name`出力をerror出力トンネルへ接続する。
7. 入力`TDMS Ref`を`TDMS Ref out`へそのまま接続する。
8. TDMS Set Propertiesを配置しない。

**Falseケース（`TDMS Ref Invalid?=False`：Ref有効）**

ChannelCount検証へ進む。

###### C. ChannelCountを算出・検証する

1. `Channel List`を`Array Size`へ接続する。
2. `Array Size`出力を`ChannelCount` I32として扱う。
3. `ChannelCount`を`Less Or Equal?`の一方へ接続する。
4. I32定数`0`をもう一方へ接続する。
5. 比較結果を`Channel List Empty?` Case Structureのselectorへ接続する。

**Trueケース（`Channel List Empty?=True`：ChannelCountが0以下）**

1. `Format Into String`へ次を設定する。

```text
RAMScope_File_Log_Write_Metadata.vi: Channel List must not be empty. ChannelCount=%d
```

2. `%d`入力へ`ChannelCount` I32を接続する。
3. `Bundle By Name`の基準クラスタへRef有効判定を通過した正常errorを接続する。
4. `status=True`、`code=I32 -700181`、`source=Format Into String出力`を接続する。
5. Bundle出力をerror出力トンネルへ接続する。
6. 入力`TDMS Ref`を`TDMS Ref out`へ接続する。
7. RootおよびChannel Propertyを書かない。

**Falseケース（`Channel List Empty?=False`：1要素以上）**

Root Property書込へ進む。

###### D. PacketSizeをI32で作る

1. `ChannelCount` I32を乗算（Multiply）の一方へ接続する。
2. I32定数`4`をもう一方へ接続する。
3. 乗算出力を加算（Add）の一方へ接続する。
4. I32定数`12`をもう一方へ接続する。
5. 加算出力を`PacketSize` I32として扱う。

###### E. Byte OrderをStringへ明示変換する

1. `Byte Order`をCase Structureのselectorへ接続する。
2. `Little Endian`ケースへString定数`Little Endian`を配置する。
3. `Big Endian`ケースへString定数`Big Endian`を配置する。
4. 両Stringを同じ出力トンネルへ接続し、出力を`ByteOrder String`として扱う。
5. EnumをI32へ数値変換して保存しない。

###### F. Root Property 9項目を直列に書く

`TDMS Set Properties`を9個左から右へ配置し、TDMS Ref wireとerror wireを直列接続する。

```text
TDMS Ref
  → TestName
  → MeasurementStartTime
  → A2LFileName
  → UnitNo
  → MdlNo_RAM
  → ByteOrder
  → ChannelCount
  → PacketSize
  → GapTimeMs
```

各ノードでRootを対象とし、Property NameとValueを次のとおり接続する。

| 順 | Property Name定数 | Value接続元 | 型 |
|---:|---|---|---|
| 1 | `TestName` | `TestName` | String |
| 2 | `MeasurementStartTime` | `Start Time` | Timestamp |
| 3 | `A2LFileName` | `A2L File Name` | String |
| 4 | `UnitNo` | `UnitNo` | I32 |
| 5 | `MdlNo_RAM` | `MdlNo_RAM` | I32 |
| 6 | `ByteOrder` | `ByteOrder String` | String |
| 7 | `ChannelCount` | `ChannelCount` | I32 |
| 8 | `PacketSize` | `PacketSize` | I32 |
| 9 | `GapTimeMs` | `GapTimeMs` | U32 |

`A2L File Name`が空でも3番目のノードを省略せず、空StringをValueへ接続する。

###### G. Channel List Forループを作る

1. ForループをRoot Property 9番目の右側へ配置する。
2. `Channel List`をForループ左枠へ接続する。
3. 入力トンネルを右クリックし、`指標付けを有効（Enable Indexing）`を選択する。
4. トンネルに`[]`が表示されたことを確認する。
5. N端子は未配線とし、Channel Listの要素数だけ反復させる。
6. TDMS Ref用Shift Registerを追加する。
7. 左外側端子へRoot Property書込後のTDMS Refを接続する。
8. error cluster用Shift Registerを追加する。
9. 左外側端子へRoot Property書込後のerrorを接続する。
10. ループ内の単一`RAMScope_Channel.ctl`を`Unbundle By Name`へ接続する。
11. `Name`、`Address`、`Size`、`Sign`、`Scale`、`Offset`、`Unit`を表示する。

###### H. Channel Property名を作る

1. Forループ反復端子`i`を`Format Into String`へ接続する。
2. Format Stringを次に設定する。

```text
Channel_%03d
```

3. 出力を`Channel Prefix`として扱う。
4. `Concatenate Strings`を7個配置する。
5. 各ノードの左入力へ`Channel Prefix`を分岐して接続する。
6. 各右入力へ次のSuffixを接続する。

```text
_Name
_Address
_Size
_Sign
_Scale
_Offset
_Unit
```

最初の反復では次となる。

```text
Channel_000_Name
Channel_000_Address
Channel_000_Size
Channel_000_Sign
Channel_000_Scale
Channel_000_Offset
Channel_000_Unit
```

Channel IndexはForループの`i`を使用するため0開始である。001開始へ補正する加算を入れない。

###### I. Channel Property 7項目を直列に書く

1. `TDMS Set Properties`をForループ内へ7個配置する。
2. 左Shift RegisterのTDMS Refを1個目のRef入力へ接続する。
3. 左Shift Registerのerrorを1個目のerror入力へ接続する。
4. 7個をRef wireとerror wireで直列接続する。
5. 7個目のRef出力を右内側Shift Registerへ接続する。
6. 7個目のerror出力を右内側Shift Registerへ接続する。

| 順 | Property Name | Value | 型 |
|---:|---|---|---|
| 1 | `Channel_%03d_Name` | `Name` | String |
| 2 | `Channel_%03d_Address` | `Address` | U32 |
| 3 | `Channel_%03d_Size` | `Size` | U32 |
| 4 | `Channel_%03d_Sign` | `Sign` | U32 |
| 5 | `Channel_%03d_Scale` | `Scale` | DBL |
| 6 | `Channel_%03d_Offset` | `Offset` | DBL |
| 7 | `Channel_%03d_Unit` | `Unit` | String |

前反復または現在反復のTDMS書込でerrorが発生した場合は、そのerrorを次ノードと次反復へ渡す。NI標準TDMS errorを`-700xxx`へ置換せず、後続Propertyで上書きしない。

###### J. Forループ後の出力を接続する

1. TDMS Ref Shift Registerの右外側端子を`TDMS Ref out`出力トンネルへ接続する。
2. error Shift Registerの右外側端子を最終error出力トンネルへ接続する。
3. このVI内へ`TDMS Flush`を配置しない。

###### K. `Error_To_TestStatus.vi`へ接続する

1. 最外周Case Structureを抜けた最終errorを`Error_To_TestStatus.vi / error in`へ接続する。
2. String定数`RAMScope`を`Device Name`へ接続する。
3. `Status`出力を本VIの`Status`へ接続する。
4. `TestError`出力を本VIの`TestError`へ接続する。
5. `error out`を本VIの`error out`へ接続する。
6. `Error_To_TestStatus.vi`は最後に1回だけ呼ぶ。

##### 9. 単体テスト

| No. | 入力・条件 | 期待結果 |
|---:|---|---|
| 1 | `error in.status=True` | TDMS書込なし、元code/source保持、Refをそのまま出力 |
| 2 | 無効TDMS Ref | `code=-700179`、source全文一致、Property書込なし |
| 3 | Channel List空 | `code=-700181`、sourceに`ChannelCount=0` |
| 4 | Channel 1要素 | `ChannelCount=1`、`PacketSize=16`、`Channel_000_*`が7項目 |
| 5 | Channel 2要素 | `ChannelCount=2`、`PacketSize=20`、`Channel_000_*`と`Channel_001_*`が存在 |
| 6 | A2L File Name空 | `A2LFileName` Propertyが存在し、値が空String |
| 7 | Little Endian | `ByteOrder="Little Endian"` |
| 8 | Big Endian | `ByteOrder="Big Endian"` |
| 9 | 型確認 | Address/Size/Sign=U32、Scale/Offset=DBL、GapTimeMs=U32、Start Time=Timestamp |
| 10 | Root書込途中でTDMS error | 最初のNI標準TDMS errorを保持し、後続書込で上書きしない |
| 11 | Channel書込途中でTDMS error | 最初のNI標準TDMS errorを保持し、後続反復で上書きしない |
| 12 | ブロックダイアグラム監査 | `TDMS Flush`が存在しない |

TDMSを閉じた後に再読込し、Root Propertyの名前、値、型およびChannel Indexが期待どおりであることを確認する。
<!-- ramscope-metadata-detail-end -->
'''


def main() -> int:
    text = DOC.read_text(encoding="utf-8")

    if MARKER_START in text or MARKER_END in text:
        print("Metadata detail already present; no changes needed.")
        return 0

    old_errors = """| `-700178` | `RAMScope_File_Log_Open.vi` | 既存ファイル上書き禁止 |\n| `-700180` | `RAMScope_File_Log_Append.vi` | Packet件数とDataNumが不一致 |"""
    new_errors = """| `-700178` | `RAMScope_File_Log_Open.vi` | 既存ファイル上書き禁止 |\n| `-700179` | `RAMScope_File_Log_Write_Metadata.vi` | TDMS File Refが無効 |\n| `-700180` | `RAMScope_File_Log_Append.vi` | Packet件数とDataNumが不一致 |\n| `-700181` | `RAMScope_File_Log_Write_Metadata.vi` | Channel Listが空 |"""

    if old_errors not in text:
        raise RuntimeError("Error-code table anchor not found or already changed unexpectedly")
    text = text.replace(old_errors, new_errors, 1)

    section_start = text.index("### 10.12.3 `RAMScope_File_Log_Write_Metadata.vi`")
    next_section = text.index("\n---\n\n### 10.12.4 `RAMScope_File_Log_Append.vi`", section_start)
    text = text[:next_section] + DETAIL + text[next_section:]

    required = [
        MARKER_START,
        MARKER_END,
        "`MeasurementStartTime`",
        "`-700179`",
        "`-700181`",
        "Channel_%03d_Name",
        "TDMS Flush`が存在しない",
    ]
    missing = [item for item in required if item not in text]
    if missing:
        raise RuntimeError(f"Required text missing after patch: {missing}")

    DOC.write_text(text, encoding="utf-8", newline="\n")
    print(f"Updated {DOC}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
