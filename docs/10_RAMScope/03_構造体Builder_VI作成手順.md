# 10-03. 数値変換・typedef・構造体Builderの個別作成手順

**監査日：2026-07-18**

詳細な関数配置と端子配線は[復元したBuilder個別手順](./10B3_RAMScope_構造体生成VI作成手順.md)を参照する。本書は00A・00B監査後の設計理由と、ベンダー資料で確定したコードを補正する。

---

## 1. なぜBuilderと数値変換VIが必要か

LabVIEW上の設定はクラスタやI32/U32で保持するが、DLLはC構造体へのPointerを要求する。Builderは意味付き設定をC構造体と同じバイト配置のU8一次元配列へ変換する。

```text
LabVIEW設定クラスタ
  → 各数値を4byte Little Endianへ変換
  → 構造体offsetへ書込
  → DLLへ渡すU8配列
```

同じ4byte変換を各Builderへ複製すると、Endianと符号の修正が複数箇所へ散る。そのため変換VIへ分離する。

---

## 2. 個別VI一覧

| VI | 責務 | 必要な構造 |
|---|---|---|
| `U32_To_LE_U8x4.vi` | U32をb0,b1,b2,b3へ分解 | 既存error Case、Split Number、Build Array |
| `I32_To_LE_U8x4.vi` | I32のビット列を保ってU32経由で変換 | Type Cast、`U32_To_LE_U8x4.vi` |
| `Build_MEASINFO_170_Raw.vi` | 72byte MEASINFOを生成 | error Case、U8[72]初期化、offset 0/4/8へ書込 |
| `Build_CHINFO_170_Raw.vi` | 24byte×ChNumのCHINFO配列を生成 | 入力検証Case、For、配列とerrorのShift Register |
| `Build_LOGINFO_Raw.vi` | 136byte LOGINFOを生成 | For、更新配列・Seen・errorのShift Register |

Parser側で使用する`U8x4_To_U32.vi`、`U8x4_To_I32.vi`、`U8x8_To_U64.vi`は[Parser詳細](./04_Parser_VI作成手順.md)を参照する。

---

## 3. `Build_CHINFO_170_Raw.vi`の現行補正

### 3.1 入力データと出力モデル

`Channel List`は`RAMScope_Channel.ctl`の一次元配列で、1要素が1チャンネルである。出力は次の24byteレコードをChNum個連結したU8配列である。

```text
offset  0 : enable  U32
       4 : core    U32
       8 : address U32
      12 : size    U32
      16 : sign    U32
      20 : speed   U32
```

### 3.2 正式コード

```text
enable : 0 / 1
core   : 0
size   : 0=1byte、1=2byte、2=4byte
sign   : 0=unsigned、1=signed
speed  : 0
```

```text
size=0 → Address任意
size=1 → Address mod 2 = 0
size=2 → Address mod 4 = 0
```

### 3.3 アルゴリズム

```text
ChNum = Array Size(Channel List)
if ChNum < 1 or ChNum > 2048:
    -700111
else:
    U8[24×ChNum]を0初期化
    for each Channel:
        コードとAddress境界を検証
        6個のU32を各4byteへ変換
        Write Index = Channel Index × 24
        累積配列へ書込
```

Forループは同じ24byte変換を全チャンネルへ適用するために必要である。配列Shift Registerは前反復までに書き込んだU8配列を保持する。error Shift Registerは最初の変換エラーを後続反復で上書きしないために必要である。

### 3.4 エラー全文

ChNum不正：

```text
Build_CHINFO_170_Raw.vi: Channel count must be 1..2048. ChNum=%d
```

```text
%d ← ChNum I32
status=True
code=I32 -700111
source=Format Into String出力
基準クラスタ=対象Caseへ入った正常error
```

チャンネル設定不正：

```text
Build_CHINFO_170_Raw.vi: Channel setting is invalid. ChannelIndex=%d, Size=%d, Sign=%d, Core=%d, Speed=%d, Address=%u
```

```text
1: Channel Index I32
2: Size U32
3: Sign U32
4: Core U32
5: Speed U32
6: Address U32
status=True
code=I32 -700112
```

旧手順の`Size=4`、`Speed=2`はバイト位置を識別するダミー値としてのみ使用し、実機設定値として使用しない。

---

## 4. `Build_LOGINFO_Raw.vi`の現行補正

### 4.1 データモデル

```text
index 0..3   LogDevice I32
index 4..7   LimitHddSize I32
各MdlNoの領域:
  Base Offset = 8 + MdlNo × 8
  Base+0..3   LogSize I32
  Base+4..7   BufferSize I32
全体136byte
```

### 4.2 構造選定

- Module Log Configsを1要素ずつ処理するためForループ。
- U8[136]更新結果を保持する配列Shift Register。
- MdlNo重複を検出するBoolean[16] Seen Shift Register。
- 最初のエラーを保持するerror Shift Register。

### 4.3 エラー全文

MdlNo範囲外：

```text
Build_LOGINFO_Raw.vi: MdlNo must be 0..15. MdlNo=%d
```

```text
%d ← MdlNo I32
status=True
code=I32 -700113
```

MdlNo重複：

```text
Build_LOGINFO_Raw.vi: Duplicate MdlNo is not allowed. MdlNo=%d
```

```text
%d ← MdlNo I32
status=True
code=I32 -700114
```

両エラーともBundle By Nameの基準クラスタ、status、code、source、error出力トンネルまで配線する。

---

## 5. 単体テスト

- MEASINFOはArray Size=72、index 0/4/8の値を確認する。
- CHINFOはChNum=1/2、Array Size=24/48、正式コード、Address境界、0要素、2049要素、既存errorを確認する。
- LOGINFOはMdlNo=0/1/15、範囲外、重複、複数要素、既存errorを確認する。
- 配線順確認には異なる識別値を使うが、実機コード試験と区別する。
