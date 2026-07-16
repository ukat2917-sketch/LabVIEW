# Build_CHINFO_170_Raw.vi：Forループとシフトレジスタ詳細手順（第10章への統合用ドラフト）

> このファイルは、第10章 `Build_CHINFO_170_Raw.vi` 節へ統合するための一時ドラフトである。単独の正本として残さず、第10章へ反映後に削除する。

## 目的

`Channel List`の各要素は、監視RAM変数1個分の`RAMScope_Channel.ctl`である。Forループは配列から1チャンネルずつ取り出し、各チャンネルを24バイトの`CHINFO_170`レコードへ変換する。

シフトレジスタは、ループの前回反復で作成した値を次の反復へ渡すために使用する。本VIでは次の2本を使用する。

1. CHINFO出力バッファ用シフトレジスタ
2. error cluster用シフトレジスタ

## 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所・追加方法 |
|---:|---|---|---|
| 1 | Forループ | For Loop | プログラミング → ストラクチャ |
| 2 | シフトレジスタ | Shift Register | Forループ枠を右クリック → シフトレジスタを追加（Add Shift Register） |
| 1 | 配列初期化 | Initialize Array | プログラミング → 配列 |
| 2 | 乗算 | Multiply | プログラミング → 数値 |
| 1 | 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 1 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 6 | `U32_To_LE_U8x4.vi` | SubVI | `30_RAMScope\00_Common` |
| 1 | 配列連結追加 | Build Array | プログラミング → 配列 |
| 1 | 部分配列置換 | Replace Array Subset | プログラミング → 配列 |

## 配線順

### 1. Forループを配置する

1. チャンネル数判定のTrueケース内へForループを配置する。
2. Forループの`N`端子は未配線にする。
3. `Channel List`をForループ左枠へ配線する。
4. 作成された入力トンネルを右クリックし、`指標付けを有効（Enable Indexing）`にする。
5. トンネルに`[]`記号が表示されることを確認する。
6. ループ外では`Channel List`配列、ループ内では1反復につき`RAMScope_Channel.ctl`単体が出力される。
7. `N`端子を未配線にしているため、ForループはChannel Listの要素数と同じ回数だけ実行される。

### 2. CHINFO出力バッファ用シフトレジスタを追加する

1. Forループの左右どちらかの枠を右クリックする。
2. `シフトレジスタを追加（Add Shift Register）`を選択する。
3. 左右の枠へ対になった端子が追加されることを確認する。
4. ループ外で`ChNum × 24`を乗算し、必要な総バイト数を作る。
5. U8定数`0`を配列初期化の`element`へ接続する。
6. `ChNum × 24`を配列初期化の`dimension size`へ接続し、U8[`24 × ChNum`]のゼロ配列を作る。
7. ゼロ配列を、CHINFO出力バッファ用シフトレジスタの左外側端子へ接続する。

シフトレジスタの各端子の意味：

```text
左外側端子 : ループ開始前の初期値
左内側端子 : 前回反復までに作成した配列
右内側端子 : 今回反復で更新した配列
右外側端子 : 全反復終了後の最終配列
```

### 3. error cluster用シフトレジスタを追加する

1. Forループ枠をもう一度右クリックする。
2. `シフトレジスタを追加（Add Shift Register）`を選択する。
3. `error in`をerror cluster用シフトレジスタの左外側端子へ接続する。

error用シフトレジスタの各端子の意味：

```text
左外側端子 : ループ開始時のerror in
左内側端子 : 前回反復までのerror
右内側端子 : 今回反復後のerror
右外側端子 : ループ全体終了後のerror out
```

### 4. 各反復の先頭で既存エラーを確認する

1. error用シフトレジスタの左内側端子を`名前でバンドル解除（Unbundle By Name）`へ接続する。
2. 要素を`status`へ変更する。
3. `status`をケースストラクチャへ接続する。
4. Trueケースでは、CHINFO配列用とerror用の左内側端子を、それぞれ右内側端子へ変更せず接続する。
5. Falseケースにチャンネル変換処理を作る。

### 5. 1チャンネル分を24バイトへ変換する

1. 自動指標付けトンネルのループ内出力を`名前でバンドル解除（Unbundle By Name）`へ接続する。
2. `Enable`、`Core`、`Address`、`Size`、`Sign`、`Speed`を表示する。
3. `U32_To_LE_U8x4.vi`を6個配置する。
4. 各フィールドを対応するSubVIの`Value`へ接続する。
5. error用シフトレジスタの左内側端子を1個目SubVIの`error in`へ接続する。
6. 6個のSubVIのerror clusterを左から右へ直列接続する。
7. `配列連結追加（Build Array）`を6入力へ広げ、右クリックして`入力を連結（Concatenate Inputs）`を有効にする。
8. 次の順で各U8[4]を接続し、Current Channel Bytes U8[24]を作る。

```text
Enable Bytes
Core Bytes
Address Bytes
Size Bytes
Sign Bytes
Speed Bytes
```

### 6. 今回の24バイトを累積バッファへ書き込む

1. Forループの反復端子`i`とI32定数`24`を乗算し、書込開始位置`Write Index`を作る。
2. `部分配列置換（Replace Array Subset）`を配置する。
3. CHINFO配列用シフトレジスタの左内側端子を、部分配列置換の`array`へ接続する。
4. `Write Index`を`index`へ接続する。
5. Current Channel Bytes U8[24]を`new element/subarray`へ接続する。
6. 更新後の配列をCHINFO配列用シフトレジスタの右内側端子へ接続する。
7. 6個目の`U32_To_LE_U8x4.vi`の`error out`をerror用シフトレジスタの右内側端子へ接続する。

### 7. Forループ終了後の出力を接続する

1. CHINFO配列用シフトレジスタの右外側端子を`CHINFO_170 Raw`へ接続する。
2. error用シフトレジスタの右外側端子を`error out`へ接続する。
3. `ChNum`はケースストラクチャの外側で本VIの`ChNum`出力へ接続する。

## なぜシフトレジスタが必要か

Forループの各反復は、何もしなければ前回反復で作成した配列を保持しない。CHINFO出力バッファ用シフトレジスタにより、チャンネル0を書き込んだ配列をチャンネル1の反復へ渡し、最後に全チャンネル分のU8一次元配列を取得できる。

error cluster用シフトレジスタは、前のチャンネル変換で発生したエラーを次の反復へ伝える。エラー発生後は残りチャンネルの変換をスキップし、最初のエラーを保持する。

## 単体テスト

### 1チャンネル

```text
Channel List要素数 = 1
期待ChNum          = 1
期待Rawサイズ      = 24
```

### 2チャンネル

```text
Channel List要素数 = 2
期待ChNum          = 2
期待Rawサイズ      = 48
```

確認用として、2チャンネルのAddressを異なる値にし、次を確認する。

```text
CHINFO Raw index 8..11  : Channel 0 Address
CHINFO Raw index 32..35 : Channel 1 Address
```

### 既存エラー

```text
error in.status = True
期待結果：変換処理をスキップし、既存エラーを保持
```
