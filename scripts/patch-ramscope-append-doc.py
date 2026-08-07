from pathlib import Path

path = Path('docs/10_RAMScope実装方針.md')
text = path.read_text(encoding='utf-8')
start_marker = '<!-- ramscope-append-detail-start -->'
end_marker = '<!-- ramscope-append-detail-end -->'
if start_marker in text or end_marker in text:
    raise SystemExit('append detail block already exists')
anchor = '\n---\n\n### 10.12.5 `RAMScope_File_Log_Close.vi`'
if anchor not in text:
    raise SystemExit('10.12.5 anchor not found')
block = r'''

<!-- ramscope-append-detail-start -->
#### 10.12.4A `RAMScope_File_Log_Append.vi`確定仕様・詳細作成手順

> 本項は直前の10.12.4概要を削除せず、[00A_LabVIEW実装資料の記述ルール.md](./00A_LabVIEW実装資料の記述ルール.md)と[00B_LabVIEW学習型VI設計ルール.md](./00B_LabVIEW学習型VI設計ルール.md)に従って、入力データ、異常条件、構造選定、関数配置、端子単位の配線および単体テストを具体化する。
>
> Nigel補足手順は基本方針として採用するが、実装時の誤配線を防ぐため次を補正する。
>
> 1. `error in.status`を最外周Case Structureで最優先し、既存errorを`-700180`で上書きしない。
> 2. `RAMScope_Packet.ctl`の正式フィールド名は`Log Trigger`であり、`Log Triger`は使用しない。
> 3. Group Nameは文字列ワイヤを各`TDMS Set Properties`／`TDMS Write`へ直接分岐する。存在しない`group name out`を前提に直列接続しない。
> 4. Channel名は、空名では`Channel_%03d`を最終名とし、非空名では`%s_%03d`でIndexを付ける。空名をさらに`%s_%03d`へ通して`Channel_000_000`のような二重Indexにしない。
> 5. `Written Packet Count=DataNum`は全TDMS書込と任意Flushが正常終了した場合だけとし、最終errorがTrueなら0を返す。

##### 0. 実現したい機能とVIの責務

`RAMScope_File_Log_Append.vi`は、`RAMScope_Read_Logging_Block.vi`が返した1Block分の`Packets`を、Block固有のTDMS Groupへ直ちに保存する。

```text
Read Logging Block
  → Packet件数整合性確認
  → Group情報保存
  → Packet共通Channel保存
  → 各測定ChannelのEngineering/Raw保存
  → 必要時Flush
  → Written Packet Count返却
```

全Blockをメモリへ蓄積してから一括保存しない。1Block取得ごとに本VIを完了させ、次Block取得へ進む。

##### 1. 入力データの実体

###### 1.1 フロントパネル入力

| 端子名 | 方向 | 型 | 用途 |
|---|---|---|---|
| `TDMS Ref` | 入力 | TDMS File Refnum | `RAMScope_File_Log_Open.vi`が返した参照 |
| `MeasNo` | 入力 | I32 | 保存ログの測定番号 |
| `BlockNo` | 入力 | I32 | 測定内Block番号 |
| `RequestedDataNum` | 入力 | I32 | DLLへ要求したPacket数 |
| `DataNum` | 入力 | I32 | DLLが実際に返したPacket数 |
| `LostDataNum` | 入力 | I32 | DLLが返した破棄Packet数 |
| `PacketSize` | 入力 | I32 | `ChannelCount × 4 + 12` |
| `Packets` | 入力 | `RAMScope_Packet.ctl[]` | Parser済みPacket配列 |
| `Channel List` | 入力 | `RAMScope_Channel.ctl[]` | SetMeasChへ渡した測定Channel定義 |
| `Flush After Write?` | 入力 | Boolean | このBlock直後にディスクへFlushするか |
| `error in` | 入力 | error cluster | 前段error |

###### 1.2 `RAMScope_Packet.ctl`で使用する正式フィールド

`Packets`の各要素から次を使用する。

| フィールド | 型 | TDMS側 |
|---|---|---|
| `Timestamp Seconds` | DBL | `Time` |
| `Flag Raw` | U32 | `FlagRaw` |
| `Status` | U8 | `Status` |
| `Skip?` | Boolean | U8化して`Skip` |
| `Dummy?` | Boolean | U8化して`Dummy` |
| `Data Lost?` | Boolean | U8化して`DataLost` |
| `Log Trigger` | U8 | `Log Trigger` |
| `Event Bits` | U8 | `Event Bits` |
| `Channel Values` | `RAMScope_Channel_Value.ctl[]` | 各測定Channelの縦方向配列生成に使用 |

`Log Triger`という綴りは使用しない。typedefの正式名は`Log Trigger`である。

###### 1.3 `RAMScope_Channel.ctl`で使用する正式フィールド

外側Channel For Loopでは次を`Unbundle By Name`する。

```text
Name
Address
Size
Sign
Scale
Offset
Unit
```

##### 2. 出力データモデル

| 端子名 | 方向 | 型 | 用途 |
|---|---|---|---|
| `TDMS Ref out` | 出力 | TDMS File Refnum | 次BlockまたはCloseへ渡す |
| `Written Packet Count` | 出力 | I32 | Block保存成功時のPacket数。書込失敗時は0 |
| `Status` | 出力 | `Status.ctl` | TestStand判定 |
| `TestError` | 出力 | `TestError.ctl` | エラー情報 |
| `error out` | 出力 | error cluster | 最初に成立したerror |

全Caseで`TDMS Ref out`、`Written Packet Count`、最終errorを明示配線する。`Use default if unwired`に依存しない。

##### 3. 前提条件・異常条件

処理優先順位を次で固定する。

```text
1. error inの既存error
2. PacketCount != DataNum のローカルerror -700180
3. Group Property書込時の最初のNI標準TDMS error
4. Packet共通Channel書込時の最初のNI標準TDMS error
5. Channel Property／Engineering／Raw書込時の最初のNI標準TDMS error
6. TDMS Flush時のNI標準TDMS error
```

`error in.status=True`ではPacket数検証、TDMS Property、TDMS Write、TDMS Flushをすべてスキップし、元errorをそのまま返す。

Packet件数不一致時のsource全文を次で固定する。

```text
RAMScope_File_Log_Append.vi: Packet count does not match DataNum. PacketCount=%d, DataNum=%d, MeasNo=%d, BlockNo=%d
```

Format Into Stringの入力順：

```text
1. PacketCount = Array Size(Packets) I32
2. DataNum I32
3. MeasNo I32
4. BlockNo I32
```

ローカルerror：

```text
基準クラスタ = error in.status=Falseで本判定へ入った正常error
status       = Boolean True
code         = I32 -700180
source       = Format Into String出力
```

`Channel List`の順番と各`Packet.Channel Values[]`の順番は、`RAMScopeGT170SetMeasCh()`へ設定した順番と一致していることを前提とする。順序を入れ替えない。

##### 4. 処理アルゴリズム

```text
if error inあり:
    TDMS Refを通す
    Written Packet Count = 0
    元errorを返す
else:
    PacketCount = Array Size(Packets)
    if PacketCount != DataNum:
        -700180
        Written Packet Count = 0
    else:
        Group Name = RAMScope_Meas%04d_Block%04d
        Group Property 6項目を書込

        Packetsから共通8配列を生成
        共通8ChannelをTDMSへ直列書込

        for Channel Index, Channel in Channel List:
            Channel名を一意化
            Packetsから対象ChannelのEngineering Value[]とRaw U32[]を生成
            Engineering Channel Property 6項目を設定
            Engineering Value[]を書込
            Raw U32[]を書込

        if Flush After Write?:
            TDMS Flush

        if 最終errorなし:
            Written Packet Count = DataNum
        else:
            Written Packet Count = 0

最後にError_To_TestStatus.viを1回だけ呼ぶ
```

##### 5. LabVIEW構造の選定理由

- 既存errorをローカル検証errorで上書きしないため、`error in.status` Caseを最外周へ置く。
- `PacketCount==DataNum`の成立後だけTDMSへ書くため、件数一致Booleanをselectorとする内側Case Structureを使用する。
- 全Packetから同じ共通fieldを抽出するため、Packets自動指標付けFor Loopを使用する。
- 各測定Channelへ同じ処理を行うため、Channel List自動指標付けの外側For Loopを使用する。
- 各Channelについて全Packetから縦方向データを作るため、その内側へPackets自動指標付けFor Loopを置く。
- TDMS Refと最初のerrorをChannel反復間で保持するため、外側Channel For LoopへTDMS Refとerror clusterのShift Registerを置く。
- Booleanの`Skip?`、`Dummy?`、`Data Lost?`を型付きU8 Channelへ保存するため、SelectでU8 1/0へ明示変換する。
- `Flush After Write?`だけでFlush有無を切り替えるため、Channel Loop完了後へCase Structureを置く。

##### 6. 配置する関数およびSubVI

| 数 | 日本語名 | 英語名 | 用途 |
|---:|---|---|---|
| 2以上 | 配列サイズ | Array Size | PacketCount、必要に応じChannelCount確認 |
| 2以上 | 等しい? | Equal? | PacketCountとDataNum等の比較 |
| 3以上 | Case Structure | Case Structure | error in、件数一致、Flush、最終成功判定 |
| 3 | Forループ | For Loop | Packet共通抽出、Channel反復、Channel内Packet反復 |
| 2 | シフトレジスタ | Shift Register | TDMS Ref、error cluster |
| 必要数 | 名前でアンバンドル | Unbundle By Name | Packet、Channel、Channel Value field抽出 |
| 4以上 | 文字列にフォーマット | Format Into String | error source、Group名、Channel名 |
| 3 | 選択 | Select | Boolean→U8 1/0 |
| 12以上 | バリアントへ変換 | To Variant | Group/Channel Property値 |
| 4以上 | 配列作成 | Build Array | Property Name/Value配列 |
| 2以上 | TDMSプロパティを設定 | TDMS Set Properties | Group/Channel Property |
| 10以上 | TDMS書き込み | TDMS Write | 共通8Channel、Engineering、Raw |
| 1 | TDMSフラッシュ | TDMS Flush | 任意Flush |
| 1 | `Error_To_TestStatus.vi` | SubVI | 最終Status/TestError生成 |

関数名やパレット位置は00Aの記述ルールに従い、日本語版LabVIEWで見つからない場合はQuick Dropへ英語名を入力する。

##### 7. フロントパネルとCase Structureを先に作る

1. 1.1記載の入力端子と2記載の出力端子をフロントパネルへ配置する。
2. `error in`を`Unbundle By Name`へ接続し、`status`を取り出す。
3. ブロックダイアグラム全体を囲む最外周Case Structureを配置し、`error in.status`をselectorへ接続する。
4. Trueケース（既存errorあり）では、入力`TDMS Ref`を`TDMS Ref out`側トンネルへ通し、I32 0を`Written Packet Count`へ通し、元`error in`を最終errorトンネルへ通す。TDMS関数は配置しない。
5. Falseケース（既存errorなし）内に、以降のPacket件数検証とTDMS処理を作る。

##### 8. 配線順

###### A. Packet数一致チェック

1. `Packets`を配列サイズ（Array Size）の`array`へ接続する。
2. 出力を`PacketCount I32`として扱う。
3. `PacketCount`を等しい?（Equal?）の一方へ接続する。
4. `DataNum`をもう一方へ接続する。
5. Equal?出力を内側Case Structureのselectorへ接続する。

Falseケース（PacketCount!=DataNum）：

1. Format Into Stringへ固定source全文を設定する。
2. `PacketCount`、`DataNum`、`MeasNo`、`BlockNo`をこの順で接続する。
3. Bundle By Nameの基準クラスタへ、このCaseへ入った正常`error in`を接続する。
4. `status=True`、`code=I32 -700180`、`source=Format Into String出力`を接続する。
5. Bundle出力を最終errorトンネルへ接続する。
6. 入力`TDMS Ref`を`TDMS Ref out`側トンネルへ通す。
7. I32 0を`Written Packet Count`へ接続する。

Trueケース（PacketCount==DataNum）：以降のB～Jを作る。

###### B. Group Nameを作る

1. 文字列にフォーマット（Format Into String）を配置する。
2. format stringへ次を設定する。

```text
RAMScope_Meas%04d_Block%04d
```

3. 1個目へ`MeasNo I32`、2個目へ`BlockNo I32`を接続する。
4. 出力を`Group Name String`として扱う。
5. `Group Name`は後続の全`TDMS Set Properties`／`TDMS Write`の`group name`入力へ必要な箇所で直接分岐する。
6. `group name out`という出力を前提に直列接続しない。

###### C. Group Property 6項目を書き込む

Property Nameと保存型を次で固定する。

| 順 | Property Name | 値 | 型 |
|---:|---|---|---|
| 1 | `RequestedDataNum` | RequestedDataNum | I32 |
| 2 | `DataNum` | DataNum | I32 |
| 3 | `LostDataNum` | LostDataNum | I32 |
| 4 | `PacketSize` | PacketSize | I32 |
| 5 | `MeasNo` | MeasNo | I32 |
| 6 | `BlockNo` | BlockNo | I32 |

1. 上記6値をそれぞれ`To Variant`へ接続する。
2. Property Name String 6個をBuild ArrayでString[]へする。
3. Variant 6個をBuild ArrayでVariant[]へする。
4. `TDMS Ref`を`TDMS Set Properties / tdms file`へ接続する。
5. `Group Name`を`group name`へ接続する。
6. Channel Nameは空Stringを接続するか、使用Versionの端子仕様に従いGroup Levelとなるよう未指定とする。Group Propertyであることを画面上で確認する。
7. Property Name[]とProperty Value[]を対応する端子へ接続する。
8. 正常`error in`を`error in`へ接続する。
9. 出力TDMS Refとerrorを次工程へ直列接続する。

###### D. PacketsからPacket共通8配列を作る

1. For Loopを配置し、`Packets`を左枠へ接続する。
2. 入力トンネルを右クリックし、`指標付けを有効（Enable Indexing）`にする。
3. ループ内の単一`RAMScope_Packet.ctl`を`Unbundle By Name`へ接続する。
4. 次を取り出す。

```text
Timestamp Seconds
Flag Raw
Status
Skip?
Dummy?
Data Lost?
Log Trigger
Event Bits
```

5. `Skip?`、`Dummy?`、`Data Lost?`へSelectを1個ずつ置く。
6. 各SelectのTrue値をU8 1、False値をU8 0とする。
7. 8個の出力トンネルを自動指標付けにし、次の配列を得る。

```text
Time       DBL[]
FlagRaw    U32[]
Status     U8[]
Skip       U8[]
Dummy      U8[]
DataLost   U8[]
Log Trigger U8[]
Event Bits  U8[]
```

###### E. Packet共通8ChannelをTDMS Writeする

次の順で8個の`TDMS Write`を直列接続する。

| 順 | TDMS Channel Name | Data |
|---:|---|---|
| 1 | `Time` | Timestamp Seconds DBL[] |
| 2 | `FlagRaw` | Flag Raw U32[] |
| 3 | `Status` | Status U8[] |
| 4 | `Skip` | Skip U8[] |
| 5 | `Dummy` | Dummy U8[] |
| 6 | `DataLost` | DataLost U8[] |
| 7 | `Log Trigger` | Log Trigger U8[] |
| 8 | `Event Bits` | Event Bits U8[] |

配線ルール：

1. 直前ノードの`tdms file out`を次ノードの`tdms file`へ接続する。
2. 直前ノードの`error out`を次ノードの`error in`へ接続する。
3. `Group Name` Stringは各ノードの`group name`へ直接分岐する。
4. 各固定Channel名Stringを対応する`channel name(s)`へ接続する。
5. `Group Name`を前ノードの出力から受け取る構造にはしない。

###### F. Channel外側For Loopを作る

1. Packet共通8Channelの最後の`tdms file out`と`error out`の右側へFor Loopを配置する。
2. `Channel List`をFor Loop左枠へ接続し、自動指標付けを有効にする。
3. For LoopへTDMS Ref用Shift Registerを追加する。
4. 左外側端子へPacket共通8Channel書込後のTDMS Refを接続する。
5. error cluster用Shift Registerを追加する。
6. 左外側端子へPacket共通8Channel書込後のerrorを接続する。
7. `Packets`を別トンネルでループ内へ渡し、`指標付けを無効（Disable Indexing）`とする。
8. `Group Name`もnon-index tunnelでループ内へ渡す。
9. 反復端子`i`を`Channel Index I32`として使用する。

###### G. Channel名を決定する

1. 現在の`RAMScope_Channel.ctl`をUnbundle By Nameへ接続する。
2. `Name`、`Address`、`Size`、`Sign`、`Scale`、`Offset`、`Unit`を取り出す。
3. `Name`を空文字列/パス?（Empty String/Path?）で判定する。
4. 空名用Format Into Stringへ`Channel_%03d`を設定し、`Channel Index`を接続する。
5. 非空名用Format Into Stringへ`%s_%03d`を設定し、`Name`、`Channel Index`の順で接続する。
6. Case StructureまたはSelectで次を選ぶ。

```text
Nameが空   → Channel_%03d
Nameが非空 → %s_%03d
```

7. 出力を最終`UniqueChannelName`とする。
8. Raw Channel名は`UniqueChannelName + "__Raw"`とする。

例：

```text
Name="RPM", i=0  → RPM_000
Name="",    i=1  → Channel_001
Name="RPM", i=2  → RPM_002
```

この方式は非空名へ常にIndexを付けるため、同名Channelも追加の重複探索なしで一意になる。空名は`Channel_%03d`自体を最終名とし、二重Indexを付けない。

###### H. Channel内側For LoopでEngineering/Raw配列を作る

1. Channel外側For Loop内へ、もう1個For Loopを配置する。
2. `Packets`全体を内側Loop左枠へ接続し、自動指標付けを有効にする。
3. 外側Loopの`Channel Index`をnon-index tunnelで内側Loopへ渡す。
4. 1PacketをUnbundle By Nameし、`Channel Values`を取り出す。
5. `Channel Values`をIndex Arrayの`array`へ接続する。
6. `Channel Index`をIndex Arrayの`index`へ接続する。
7. 取得した`RAMScope_Channel_Value.ctl`をUnbundle By Nameへ接続する。
8. `Engineering Value`と`Raw U32`を取り出す。
9. 2個の出力トンネルを自動指標付けとし、次を得る。

```text
Engineering Value DBL[]
Raw U32 U32[]
```

###### I. Engineering Channel Propertyを設定する

Propertyを次で固定する。

| 順 | Property Name | 値 | 型 |
|---:|---|---|---|
| 1 | `Address` | Address | U32 |
| 2 | `Size` | Size | U32 |
| 3 | `Sign` | Sign | U32 |
| 4 | `Scale` | Scale | DBL |
| 5 | `Offset` | Offset | DBL |
| 6 | `Unit` | Unit | String |

1. 6値をそれぞれTo Variantへ接続する。
2. Property Name[]とVariant[]をBuild Arrayで作る。
3. Shift Register左内側のTDMS Refを`TDMS Set Properties / tdms file`へ接続する。
4. `Group Name`を`group name`へ接続する。
5. `UniqueChannelName`を`channel name`へ接続する。
6. Shift Register左内側のerrorを`error in`へ接続する。
7. Property Name[]とProperty Value[]を対応端子へ接続する。

`TDMS Set Properties`はGroup/Channelを指定してPropertyを保存するために使用し、数値PropertyをStringへ変換しない。

###### J. Engineering／RawをTDMS Writeし、Shift Registerへ戻す

1. `TDMS Set Properties`のTDMS Ref/error出力を`TDMS Write`（Engineering）の入力へ接続する。
2. `Group Name`を同Writeのgroup nameへ直接接続する。
3. `UniqueChannelName`をchannel nameへ接続する。
4. `Engineering Value DBL[]`をdataへ接続する。
5. Engineering WriteのTDMS Ref/error出力を`TDMS Write`（Raw）へ接続する。
6. `Group Name`をRaw Writeのgroup nameへ直接接続する。
7. `UniqueChannelName + "__Raw"`をchannel nameへ接続する。
8. `Raw U32[]`をdataへ接続する。
9. Raw Writeの`tdms file out`を外側For LoopのTDMS Ref Shift Register右内側端子へ戻す。
10. Raw Writeの`error out`をerror Shift Register右内側端子へ戻す。

TDMS APIのerror wireを直列接続し、最初のTDMS errorを後段処理で独自errorへ置き換えない。

###### K. Flush分岐を作る

1. Channel外側For Loopの右外側TDMS Refとerrorを取り出す。
2. その右側へCase Structureを配置する。
3. `Flush After Write?`をselectorへ接続する。

Falseケース（Flush After Write?=False）：

```text
TDMS Ref → そのまま出力
error    → そのまま出力
```

Trueケース（Flush After Write?=True）：

1. TDMS Flushを配置する。
2. Loop完了後のTDMS Refとerrorを接続する。
3. FlushのTDMS Ref/errorをCase出力へ接続する。

###### L. Written Packet CountとStatus/TestErrorを作る

1. Flush Case後の最終errorから`status`をUnbundle By Nameする。
2. 最終error.statusをselectorとするCase Structureを配置する。
3. Trueケース（最終書込errorあり）はI32 0を`Written Packet Count`へ接続する。
4. Falseケース（最終書込errorなし）は`DataNum I32`を`Written Packet Count`へ接続する。
5. Flush Case後のTDMS Refを`TDMS Ref out`へ接続する。
6. 最終errorを`Error_To_TestStatus.vi / error in`へ接続する。
7. String定数`RAMScope`を`Device Name`へ接続する。
8. 同SubVIの`Status`、`TestError`、`error out`を本VIの同名出力へ接続する。
9. `Error_To_TestStatus.vi`はCase Structure外で最後に1回だけ呼ぶ。

##### 9. 単体テスト

| No. | 条件 | 期待結果 |
|---:|---|---|
| 1 | `error in.status=True`、Packets件数不一致 | TDMS処理なし、元error code/source保持、Written Packet Count=0 |
| 2 | `Packets` 2要素、`DataNum=1` | `-700180`、Property/Write/Flushなし、Written Packet Count=0 |
| 3 | `Packets`空、`DataNum=0` | 件数一致。後段TDMS処理がエラーなく完了すれば正常 |
| 4 | Group名 | `MeasNo=2, BlockNo=3`で`RAMScope_Meas0002_Block0003` |
| 5 | Group Property | 6キーの名前・値・型が一致 |
| 6 | Packet共通field | `Log Trigger`の綴りとU8値がctlと一致 |
| 7 | Boolean | True→U8 1、False→U8 0 |
| 8 | `Name="RPM"`, index=0 | Engineering=`RPM_000`、Raw=`RPM_000__Raw` |
| 9 | `Name=""`, index=1 | Engineering=`Channel_001`。`Channel_001_001`にならない |
| 10 | 同名`Name="RPM"`がindex 0/2 | `RPM_000`、`RPM_002`となり一意 |
| 11 | Channel Value | `Engineering Value[]`と`Raw U32[]`がPacket順に縦配列化される |
| 12 | `Flush After Write?=False` | TDMS Flush未実行 |
| 13 | `Flush After Write?=True` | 全Channel書込後に1回だけFlush |
| 14 | Group/Packet/Channel Write途中でTDMS error | 最初のNI標準TDMS error保持、Written Packet Count=0 |
| 15 | 全TDMS処理正常 | Written Packet Count=`DataNum` |
| 16 | TDMS再読込 | Group、共通8Channel、Engineering/Raw Channel、Propertyの名前と型が期待どおり |

推奨プローブ位置：

```text
error in
PacketCount
PacketCount == DataNum?
Group Name
Group Property書込後error
Packet共通8Channel書込後error
Channel Index
UniqueChannelName
Engineering Value Array Size
Raw U32 Array Size
Channel Loop終了後error
Flush後error
Written Packet Count
最終error
```

<!-- ramscope-append-detail-end -->
'''
text = text.replace(anchor, block + anchor, 1)
path.write_text(text, encoding='utf-8')
print('inserted RAMScope append detail block')
