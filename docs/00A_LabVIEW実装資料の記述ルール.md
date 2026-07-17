# 00A. LabVIEW実装資料の記述ルール

**最終整理日：2026-07-17**

本書は、本リポジトリ内のLabVIEW VI、TestStand、機器設定、単体テスト、データ保存手順を記述する際の共通ルールである。

読者は「LabVIEWを初めて操作する人」を基準とする。作成者には分かる省略表現でも、第三者が画面を見ながら同じVIを再現できない場合は不十分と判断する。

---

## 1. 基本原則

### 1.1 構成やVI一覧の前に必要性を書く

フォルダ構成やVI一覧を先に並べず、次を説明してから構成を示す。

1. 何を実現するのか。
2. 元のAPIや機器仕様にはどの扱いにくさがあるのか。
3. なぜ処理を分割するのか。
4. 各VIがどの問題を解決するのか。
5. 測定結果をどこへ、どの形式で保存するのか。

```text
C言語DLLは構造体ポインタと生バイト列を使用する
  ↓
LabVIEWのクラスタや数値へ直接接続できない
  ↓
DLL Wrapper、Builder、Parser、Public API、File Loggerへ責務を分ける
```

### 1.2 正本を1か所にする

- 同じ詳細手順を複数章へ複製しない。
- 他章には概要と正本へのリンクだけを書く。
- 旧手順を残す場合は、`旧情報`、`参考`、`不採用`のいずれかを明記する。
- 未確認値は`実機確認待ち`、`未確定`、`作業仮定`のいずれかを付ける。

### 1.3 抽象説明と操作手順を分ける

設計方針だけを説明する節では、無理に画面操作を書かない。実際にVIを作る節では、設計概念だけで終わらせず、関数配置、端子、配線、文字列、ファイル操作、テストまで書く。

### 1.4 画面上の作業順と同じ順番で書く

手順書は完成後の論理順ではなく、読者がLabVIEW画面上で作業する順に記載する。

```text
1. 入れ物となるCase Structure、Forループ、Whileループを配置する
2. selector、N端子、停止条件、トンネルを配線する
3. 作業対象のケースへ切り替える
4. そのケース内へ関数やSubVIを配置する
5. 内側のストラクチャが必要なら、先にそのストラクチャを配置する
6. その後で内側処理を作る
7. 全ケースの出力トンネルを配線する
```

後から登場するCase Structureの中身を、Case Structureの配置前に説明してはならない。

悪い例：

```text
Packet Sizeを計算する。
Expected Byte Countを計算する。
Input Valid? Case Structureを配置する。
```

良い例：

```text
1. Input Valid? Case Structureを配置する。
2. Input Valid?をselectorへ接続する。
3. Trueケースへ切り替える。
4. Trueケース内でPacket Sizeを計算する。
5. 同じTrueケース内でExpected Byte Countを計算する。
```

---

## 2. VI作成手順の標準構成

新規VIの作成手順は原則として次の順番に統一する。

```text
0. 目的と処理概要
1. 入出力
2. 配置する関数およびSubVI等
3. 配線順
4. 単体テスト
```

ファイル保存VIでは、次も追加する。

```text
5. 保存ファイル仕様
6. Cleanup時の保証
```

### 2.1 目的と処理概要

- このVIが必要な理由を書く。
- 入力を何へ変換し、何を出力するかを書く。
- Forループを使う場合は、何を1反復で処理するかを書く。
- シフトレジスタを使う場合は、何を反復間で保持するかを書く。
- エラー時にどの安全値を返すかを書く。
- ファイルを扱う場合は、Open、Append、Flush、Closeの責務を書く。

### 2.2 入出力

全端子を表で記載する。

| 端子名 | 方向 | 型 | 用途 |
|---|---|---|---|
| `Channel List` | 入力 | `RAMScope_Channel.ctl`一次元配列 | チャンネル設定一覧 |
| `error in` | 入力 | error cluster | 前段エラー |
| `CHINFO_170 Raw` | 出力 | U8一次元配列 | DLLへ渡す構造体バイト列 |
| `error out` | 出力 | error cluster | 処理結果 |

ここで定義した全端子は、配線順の中で接続先を必ず説明する。

ファイルVIでは次も記載する。

| 端子 | 必須記載内容 |
|---|---|
| File Path | 絶対パスか相対パスか、フォルダ未存在時の処理 |
| Open Mode | 新規作成、追記、上書き、重複時の動作 |
| File Ref / Log Session | 生成元VI、保持方法、Close元VI |
| Flush Policy | 毎回、件数単位、時間単位、Close時のみ |

### 2.3 配置する関数およびSubVI等

次の列を使用する。

| 数 | 日本語名 | 英語名 | 配置場所・追加方法 |
|---:|---|---|---|
| 1 | 配列サイズ | Array Size | プログラミング → 配列 |
| 1 | Forループ | For Loop | プログラミング → ストラクチャ |
| 2 | シフトレジスタ | Shift Register | Forループ枠を右クリック → シフトレジスタを追加 |
| 1 | `U32_To_LE_U8x4.vi` | SubVI | `30_RAMScope\00_Common` |

関数名は必ず**日本語名（英語名）**の順で記載する。パレット位置は日本語版LabVIEWを基準とする。

```text
Ctrl + Space
  → クイックドロップ（Quick Drop）
  → 英語名を入力
```

### 2.4 配線順

配線順は番号付きで記載し、入力から出力まで追えるようにする。

次の省略表現は禁止する。

```text
8を加える。
Valueへ接続する。
比較を作る。
更新後配列を右へ渡す。
エラーを返す。
エラー文字列を作る。
正常ケースへ進む。
Raw不足ケースへ入る。
ファイルへ保存する。
ログを閉じる。
```

接続元、接続先、関数名、端子名を明記する。

```text
1. `MdlNo × 8`の乗算出力を`Base Offset`として扱う。
2. `Base Offset`を加算（Add）の上側入力へ接続する。
3. I32定数`8`を同じ加算の下側入力へ接続する。
4. 加算出力を`Log Index`として扱う。
5. `LogSize`を`I32_To_LE_U8x4.vi`の`Value`入力端子へ接続する。
```

一時値へ名前を付ける場合は、作った直後に定義する。

```text
部分配列置換 #1の出力を`LogSize書込後LOGINFO`として扱う。
```

### 2.5 作業領域を住所のように明記する

Case Structureやループが入れ子になる場合、各節の冒頭に作業領域を記載する。

```text
作業領域：
外側error Case Structure
  → Falseケース（error in.status=False：既存エラーなし）
    → Input Valid? Case Structure
      → Trueケース（Input Valid?=True：入力値正常）
        → Raw Buffer Sufficient? Case Structure
          → Falseケース（Raw Buffer Sufficient?=False：Raw Buffer不足）
```

見出しにも可能な限り作業領域を含める。

悪い見出し：

```text
サイズ計算
FlagとTimestamp
Raw不足ケース
```

良い見出し：

```text
Input Valid? Trueケース内：Packet Sizeを計算する
外側Forループ内・Packet Error? Falseケース内・内側Forループ外：FlagとTimestampを解析する
Raw Buffer Sufficient? Falseケース（Raw Buffer不足）：-700131エラーを作る
```

### 2.6 CaseはTrue／Falseを先に書く

`正常ケース`、`不正ケース`、`Raw不足ケース`等の意味名だけで表記してはならない。LabVIEW画面上のCaseラベルと一対一で照合できるように、必ず**True／Falseを先に書き、意味を括弧内へ書く**。

| selector | Falseケース | Trueケース |
|---|---|---|
| `error in.status` | Falseケース（既存エラーなし：処理継続） | Trueケース（既存エラーあり：安全出力） |
| `Input Valid?` | Falseケース（入力値不正：ローカルエラー） | Trueケース（入力値正常：次の判定へ進む） |
| `Raw Buffer Sufficient?` | Falseケース（Raw Buffer不足） | Trueケース（Raw Buffer十分） |
| `DataNum == 0?` | Falseケース（DataNum>0：解析する） | Trueケース（DataNum=0：空配列を返す） |
| `packet error.status` | Falseケース（エラーなし：現在Packetを解析） | Trueケース（既存エラーあり：解析をスキップ） |

Case Structureを説明する直前に、selectorの式と評価例を書く。

```text
selector = Actual Byte Count >= Expected Byte Count
20 >= 20 → True
したがってTrueケース（Raw Buffer十分）へ進む。
```

### 2.7 文字列定数とFormat Stringは全文を書く

文字列定数、文字列にフォーマット（Format Into String）、文字列連結（Concatenate Strings）を使用する場合、資料には実際に入力する文字列を全文記載する。

次の項目を必ず書く。

1. 配置する文字列関数の日本語名と英語名。
2. Format Stringまたは文字列定数へ入力する全文。
3. 改行を含める場合は改行位置。
4. `%d`、`%s`、`%X`等のプレースホルダの個数と順序。
5. 各プレースホルダへ接続する値の名前と型。
6. 生成文字列を接続する先の関数名と端子名。
7. 単体テスト時の期待source全文または主要部分。

```text
Format String：
RAMScope_Parse_Buffer.vi: ChNum must be >= 1 and DataNum must be >= 0. ChNum=%d, DataNum=%d

1個目の%d ← ChNum I32
2個目の%d ← DataNum I32
```

```text
Format String：
RAMScope_Parse_Buffer.vi: Raw Buffer is too small. Expected=%d, Actual=%d

1個目の%d ← Expected Byte Count I32
2個目の%d ← Actual Byte Count I32
```

`-700130`用の入力検証文字列を、`-700131`のRaw Buffer不足ケースへ流用してはならない。

### 2.8 error cluster生成手順を省略しない

ローカル検証エラーを作る場合は、`code=-700130を返す`だけで終わらせない。名前でバンドル（Bundle By Name）を使う場合、次をすべて記載する。

```text
1. 名前でバンドル（Bundle By Name）を配置する。
2. 元の正常なerror clusterを基準クラスタ入力へ接続する。
3. 表示フィールドをstatus、code、sourceへ設定する。
4. Boolean定数Trueをstatusへ接続する。
5. I32定数-700130をcodeへ接続する。
6. Format Into Stringの出力をsourceへ接続する。
7. Bundle By Name出力を対象Case Structureのerror出力トンネルへ接続する。
```

資料には、基準クラスタとしてどのerror clusterを使用するかも明記する。

```text
基準クラスタ = 外側error Case StructureのFalseケースへ入ってきた正常なerror in
```

| 条件 | code | sourceに含める値 |
|---|---:|---|
| 入力値不正 | `-700130` | ChNum、DataNum |
| Raw Buffer不足 | `-700131` | Expected Byte Count、Actual Byte Count |

---

## 3. 数値型・表示形式・配列

### 3.1 数値型を省略しない

```text
U8定数 0
I32定数 24
U32定数 x12345678
DBL定数 20e-9
```

I32ワイヤへDBL定数を接続して強制変換ドットを発生させない。

### 3.2 16進数表示

U8配列のバイト値を確認するときは、配列枠ではなく配列内の数値セルを右クリックする。

```text
表示形式 → 16進数
表示項目 → 基数
```

LabVIEW画面上の`x78`は資料中の`0x78`と同じ値である。10進表示で`78`を入力した後に表示だけ16進へ変更すると`x4E`になるため、16進表示へ変更した後に再入力する。

### 3.3 表示数と実要素数を区別する

- 表示器に3行見えていても、実配列が3要素とは限らない。
- 要素追加・削除は`データ操作 → 要素を挿入／要素を削除`で行う。
- 配列サイズ（Array Size）を一時接続し、実要素数を確認する。
- 配列左上の数字は表示開始indexであり、配列要素数ではない。

### 3.4 単一クラスタとクラスタ配列を区別する

```text
RAMScope_Channel.ctl = 1チャンネル分の単体クラスタ
Channel List         = RAMScope_Channel.ctlを要素に持つ一次元配列
RAMScope_Packet.ctl  = 1パケット分の単体クラスタ
Packets              = RAMScope_Packet.ctlを要素に持つ一次元配列
```

typedefをフロントパネルへ直接ドラッグすると単体クラスタになる。配列を作る場合は、空の配列枠へtypedefを入れるか、既存の配列ワイヤから`作成 → 制御器／表示器`を選ぶ。

### 3.5 配列の型と要素数を区別する

Case Structureの各ケースで一致させる必要があるのはデータ型であり、実行時の要素数ではない。

```text
Trueケース  = RAMScope_Packet.ctl一次元配列、0要素
Falseケース = RAMScope_Packet.ctl一次元配列、DataNum要素
```

次は型が異なるため接続できない。

```text
Trueケース  = RAMScope_Packet.ctl単体クラスタ
Falseケース = RAMScope_Packet.ctl一次元配列
```

---

## 4. Case Structure

### 4.1 通常VIの基本順序

```text
外側Case：error in.status
├─ Trueケース（既存エラーあり）
│   ├─ 実処理をスキップ
│   ├─ 安全な初期出力
│   └─ error out = 元のerror in
└─ Falseケース（既存エラーなし）
    └─ 入力値検証Case
        ├─ Falseケース（入力値不正）→ ローカル検証エラー
        └─ Trueケース（入力値正常）→ 本処理
```

既存エラー確認を入力値検証より外側へ置く。

### 4.2 ストラクチャ先行ルール

```text
1. Case Structureを配置する。
2. selectorへBoolean、Enum、数値等を接続する。
3. 対象ケースへ切り替える。
4. 対象ケース内へ処理を作る。
5. 各ケースで同じ出力トンネルを使用する。
```

Caseを切り替えたときに枠上のトンネル位置が同じであることを確認する。各ケースで別の位置へ新しいトンネルを作らない。

### 4.3 各ケースの全出力を書く

- 主要データ出力。
- 件数出力。
- Boolean検出フラグ。
- Unused等の補助値。
- error out。
- シフトレジスタ右内側へ戻す値。

`Use default if unwired`へ依存しない。

### 4.4 Cleanup VI

Cleanup VIは前段エラーがあっても終了処理を試みる。元エラーとCleanupエラーをどの関数で統合するかを書く。

---

## 5. Forループと自動指標付け

### 5.1 何を繰り返すかを書く

入れ子のForループでは、LabVIEW画面上の反復端子はどちらも`i`と表示されることを記載する。

```text
外側Forループのi = Packet Index
内側Forループのi = Channel Index
資料中では区別のため内側をjと表記する場合がある
```

### 5.2 自動指標付け

```text
1. 配列をForループ左枠へ接続する。
2. 入力トンネルを右クリックする。
3. 指標付けを有効（Enable Indexing）を選ぶ。
4. トンネルに[]が表示されたことを確認する。
5. ループ外の配列型とループ内の単一要素型を記載する。
```

配列全体から任意位置を切り出す場合は、入力トンネルの指標付けを無効にする。

### 5.3 出力の自動指標付け

```text
ループ内  = RAMScope_Packet.ctl単体
ループ外  = RAMScope_Packet.ctl一次元配列
```

### 5.4 条件付き指標付け

解析成功時だけ要素を配列へ追加する場合は条件付き指標付けを使用する。

```text
Packet単体クラスタ → 条件付き出力トンネル
Append Packet?      → 条件端子
```

`Append Packet?`はLabVIEW標準端子名ではなく、資料中で定義する内部Boolean信号である。

```text
最終error.status=False
  → NOT=True
  → Append Packet?=True
  → Packetを配列へ追加
```

---

## 6. シフトレジスタ

```text
Forループ枠を右クリック
  → シフトレジスタを追加（Add Shift Register）
```

```text
左外側端子 : ループ開始前の初期値
左内側端子 : 前回反復までの値
右内側端子 : 今回反復後の値
右外側端子 : 全反復終了後の最終値
```

初期値`-1`は左外側端子へ一度だけ接続する。判定Falseケースでは左内側端子の現在値を右内側端子へそのまま渡す。

単一の最終値を返す場合は、通常の自動指標付け出力トンネルではなくシフトレジスタ右外側端子を使う。

---

## 7. 比較条件

数式風の省略だけで終わらせない。比較関数では上側入力と下側入力へ何を接続するかを書く。特に`>=`、`>`、`-`は接続順で意味が変わる。

```text
1. 等しくない?（Not Equal?）を配置する。
2. 変換済みmodule_type I32を上側入力へ接続する。
3. I32定数x0Fを下側入力へ接続する。
4. Boolean出力をConnected?へ接続する。
5. module_type=x0FならFalse、それ以外ならTrueとなる。
```

---

## 8. SubVI接続

- `1個目のSubVI`だけでなく、可能な限りVI名を書く。
- `Value`だけでなく、どのVIのどの端子かを書く。
- 出力へ用途名を付ける。
- error clusterの直列接続を省略しない。

```text
内側Forループerror右外側
  → Flag変換VI error in
  → Flag変換VI error out
  → Timestamp変換VI error in
  → Timestamp変換VI error out
  → 外側Forループerror右内側
```

---

## 9. 単体テスト

### 9.1 論理値だけでなく入力方法を書く

- どのフロントパネル入力へ入れるか。
- 直接入力できない場合、どの関数でテスト配列を生成するか。
- 書込index。
- 書き込む値の型と要素数。
- 表示形式。
- 実配列サイズ。

### 9.2 テスト配列生成

```text
配列初期化（Initialize Array）でU8配列を作る
  → 部分配列置換（Replace Array Subset）を直列接続
  → Parserへ入力
```

Raw Bufferを直接入力する場合は、全要素をindex順の表または連続したバイト列で記載する。

### 9.3 正常・境界・異常・既存エラー

可能な範囲で次を含める。

- 正常値。
- 0要素・不足サイズ。
- 最大値・範囲外。
- 重複。
- 既存error in。
- 配線順を確認できる識別値。

### 9.4 期待結果とプローブ位置

配列サイズ、error code、error source、検出フラグ、ファイル行数、保存値まで記載する。

```text
ChNum
Actual Byte Count
Expected Byte Count
Packet Size
最後のReplace Array Subset出力
シフトレジスタ右外側
```

---

## 10. データ保存・ロギング

### 10.1 機器側ロギングとアプリ側保存を区別する

次の2つを同じ意味で扱わない。

```text
機器／API側ロギング設定
  例：SetLoggingInfo、LOGINFO、バッファサイズ、ログデバイス

LabVIEW側測定結果保存
  例：解析済みPacketsをTDMSまたはCSVへ保存
```

機器側のロギング設定を実装しただけで、TestStandや解析担当者が使用できる測定結果ファイルが作成されると断定してはならない。

### 10.2 LoggerはOpen／Append／Closeへ分ける

```text
File_Log_Open.vi
  → ファイル生成、メタデータ書込、File RefまたはLog Session生成

File_Log_Append.vi
  → 解析済みPacketsを追記

File_Log_Close.vi
  → Flush、Close、参照無効化
```

トップVI内へファイル処理を一塊で埋め込まず、単体試験可能なSubVIへ分ける。

### 10.3 保存形式を明記する

本番測定では、型保持、追記性能、長時間測定を考慮しTDMSを第一候補とする。CSVは確認・受け渡し用の任意出力とする。

資料には次を記載する。

- ファイル形式。
- ファイル名規則。
- 保存先。
- 既存ファイル時の動作。
- 1Packetを何行または何サンプルとして保存するか。
- Timestamp RawとTimestamp Secondsの両方を保存するか。
- Raw U32、Value、Engineering Valueのどれを保存するか。
- Flag、LostDataNum、Unused Byte Countを保存するか。
- メタデータとして保存する設定値。

### 10.4 測定ループ内の作業順

```text
RAMScope_Read.vi
  → Packets / Parsed Packet Count / LostDataNumを取得
  → File_Log_Append.vi
  → 必要なWait
  → 次のRead
```

File LoggerのOpenはMeasStart前、CloseはMeasStopとReleaseBufferDataの後に行う。Cleanupでは前段エラーがあってもCloseを試みる。

### 10.5 ロギング単体テスト

ハードウェアを使用せず、Parser単体試験で作成したPacketsをLoggerへ入力する。

期待結果には次を含める。

- ファイルが作成された。
- Packet数と保存サンプル数が一致した。
- Channel 0=`1`、Channel 1=`-2`、Flag=`165`、Timestamp Raw=`50`、Timestamp Seconds=`1E-6`が保存された。
- Close後にファイルを再度開ける。
- 既存error in時に新規書込せず、Closeは実行できる。

---

## 11. 検証済み・未確定の表記

| 表記 | 意味 |
|---|---|
| **確定** | 一次情報または再現可能な実測で確認済み |
| **PoC済み** | 最小条件で動作確認済み |
| **実機確認待ち** | 実装済みだが対象機器で未確認 |
| **未確定** | 推測で固定しない |
| **作業仮定** | 単体テスト用の暫定値 |
| **参考** | 未採用案または代替手段 |

---

## 12. 資料更新時の確認表

- [ ] VIやフォルダが必要な理由を先に説明した
- [ ] 入出力の全端子を記載した
- [ ] 関数を日本語名（英語名）で記載した
- [ ] パレット位置または追加方法を記載した
- [ ] 数値定数の型を記載した
- [ ] 接続元と接続先の双方を記載した
- [ ] ストラクチャを先に配置してから内部処理を説明した
- [ ] 各処理の作業領域をCase名とTrue／Falseまで記載した
- [ ] CaseはTrue／Falseを先に、意味を括弧内へ記載した
- [ ] selectorの式と評価例を記載した
- [ ] 既存エラー確認を入力検証より外側へ置いた
- [ ] Caseの全出力を記載した
- [ ] 各Caseで同じ出力トンネルを使用している
- [ ] Format Stringまたは文字列定数の全文を記載した
- [ ] プレースホルダの順序と接続元を記載した
- [ ] Bundle By Nameの基準クラスタ、status、code、sourceを記載した
- [ ] error codeとsourceの内容が一致している
- [ ] Forループの反復対象とN端子を記載した
- [ ] 外側と内側の反復端子を区別した
- [ ] 自動指標付けの有効・無効を記載した
- [ ] 条件付き指標付けの条件Booleanを定義した
- [ ] シフトレジスタの目的、初期値、4端子を記載した
- [ ] 配列と単一クラスタを区別した
- [ ] 配列型と実行時要素数を区別した
- [ ] 表示数、表示index、実要素数を区別した
- [ ] 単体テストの入力方法まで記載した
- [ ] 期待バイト位置、配列サイズ、error code、error sourceを記載した
- [ ] 推奨プローブ位置を記載した
- [ ] 機器側ロギングとLabVIEW側データ保存を区別した
- [ ] LoggerのOpen／Append／CloseとCleanupを記載した
- [ ] ファイル形式、保存先、命名、追記・上書き条件を記載した
- [ ] 保存値とファイル単体テストを記載した
- [ ] 未確定事項を断定していない
- [ ] 他章とVI名、フォルダ名、責務が一致している
