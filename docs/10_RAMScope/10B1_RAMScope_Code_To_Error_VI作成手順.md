# 10B-1. `RAMScope_Code_To_Error.vi` 作成手順

> **本章の役割**：`RAMScope_Code_To_Error.vi`を、LabVIEWで初めてVIを作成する人でも再現できる粒度で説明する。
>
> 本VIは、RAMScope APIの戻り値をLabVIEW標準の`error cluster`へ変換する共通部品である。
> DLLのCLFNエラーが既に発生している場合はそのエラーを優先し、CLFNが正常でもAPI戻り値が0以外の場合にRAMScope APIエラーを生成する。
>
> 上位手順は [10B](./10B_RAMScope_VI作成手順_STEP3_STEP4詳細.md) を参照する。

**最終整理日：2026-07-14**

---

## 1. 完成時の動作

| `error in.status` | `API ReturnCode` | `error out` |
|---|---:|---|
| False | 0 | エラーなし |
| False | 0以外 | RAMScope APIエラーを新規作成 |
| True | 任意 | 元の`error in`を変更せず出力 |

優先順位は次のとおりとする。

```text
既存のCLFN／前段エラー
  ＞ RAMScope API ReturnCode
```

つまり、DLLロード失敗やCLFN引数エラーが既に存在する場合に、API戻り値で元エラーを上書きしない。

---

## 2. 新規VIを作成する

1. LabVIEWを起動する。
2. `ファイル → 新規VI`を選択する。
3. `ファイル → 名前を付けて保存`を選択する。
4. 次の名前で保存する。

```text
30_RAMScope\00_Common\RAMScope_Code_To_Error.vi
```

5. フロントパネルを開く。

---

## 3. フロントパネルを作成する

次の4端子を配置する。

| ラベル | 方向 | LabVIEW型 | 作成方法 |
|---|---|---|---|
| `API ReturnCode` | 入力 | I32数値制御器 | 数値制御器を配置し、表現形式をI32へ変更 |
| `Function Name` | 入力 | 文字列制御器 | 文字列制御器を配置 |
| `error in` | 入力 | error cluster制御器 | `制御器 → 配列、行列、クラスタ → エラー入力` |
| `error out` | 出力 | error cluster表示器 | `制御器 → 配列、行列、クラスタ → エラー出力` |

### 3.1 `API ReturnCode`をI32にする

1. 数値制御器を右クリックする。
2. `表現形式`を開く。
3. `I32`を選択する。
4. ラベルを`API ReturnCode`に変更する。

DBLのままにしない。RAMScope APIのC言語`long`はWindowsでは32bitである。

### 3.2 コネクタペイン

コネクタペインは、左側を入力、右側を出力にする。

推奨配置：

```text
左上   API ReturnCode
左中   Function Name
左下   error in
右下   error out
```

設定手順：

1. VIアイコンを右クリックする。
2. `コネクタを表示`を選択する。
3. 端子をクリックしてから、対応する制御器または表示器をクリックする。
4. `API ReturnCode`と`Function Name`は`必須`、`error in`は`推奨`に設定する。

---

## 4. ブロックダイアグラムへ配置する関数

ブロックダイアグラムを開き、次を配置する。

| No. | 関数／ストラクチャ | 配置場所の目安 | 用途 |
|---:|---|---|---|
| 1 | `Unbundle By Name` | `関数 → プログラミング → クラスタ、クラス、バリアント` | `error in.status`を取り出す |
| 2 | `Case Structure` ×2 | `関数 → プログラミング → ストラクチャ` | 既存エラー判定、ReturnCode判定 |
| 3 | `Equal?` | `関数 → プログラミング → 比較` | `API ReturnCode == 0`を判定 |
| 4 | I32数値定数`0` | `関数 → プログラミング → 数値` | 正常コードとの比較 |
| 5 | `Type Cast` | `関数 → プログラミング → 数値 → データ操作` | I32のビット列をU32として扱う |
| 6 | U32数値定数 | 数値定数の表現形式をU32へ変更 | `Type Cast`の出力型を指定 |
| 7 | `Format Into String` | `関数 → プログラミング → 文字列 → 文字列のフォーマット／スキャン` | 関数名、16進、10進を1本の文字列へ変換 |
| 8 | 文字列定数 | 文字列パレット | フォーマット文字列 |
| 9 | `Bundle By Name` | `関数 → プログラミング → クラスタ、クラス、バリアント` | 新しいerror clusterを作る |

LabVIEWのバージョンによりパレット名の日本語表記が少し異なる場合がある。その場合は、関数パレットの検索欄へ英語名を入力して配置する。

---

## 5. 完成形のブロックダイアグラム

全体は次の二重Case Structureにする。

```text
error in
  │
  ├─→ Unbundle By Name（status）
  │          │
  │          ▼
  │    外側Case Structure
  │    ├─ True：既存エラーあり
  │    │     └─ error inをそのままerror outへ
  │    │
  │    └─ False：既存エラーなし
  │          │
  │          ├─ API ReturnCode == 0 ?
  │          │            │
  │          │            ▼
  │          │      内側Case Structure
  │          │      ├─ True：API正常
  │          │      │     └─ error inをそのままerror outへ
  │          │      │
  │          │      └─ False：API異常
  │          │            ├─ ReturnCodeを16進／10進文字列化
  │          │            ├─ Bundle By Nameでerror cluster生成
  │          │            └─ error outへ
  │          │
  └──────────┴─────────────────────────────→ error out
```

---

## 6. 外側Case Structureを作成する

外側Case Structureは、**前段またはCLFNのエラーが既にあるか**を判定する。

### 6.1 `error in.status`を取り出す

1. `Unbundle By Name`を配置する。
2. `error in`を`Unbundle By Name`のクラスタ入力へ配線する。
3. `Unbundle By Name`の要素名をクリックする。
4. `status`を選択する。
5. 取り出したBooleanを外側Case Structureのセレクタ端子`?`へ配線する。

### 6.2 外側Trueケース

条件：

```text
error in.status == True
```

処理：

1. `error in`をCase Structure左側のトンネルから入れる。
2. そのまま右側の出力トンネルへ配線する。
3. 右側トンネルを`error out`へ配線する。

このケースではReturnCodeを評価しない。元エラーを最優先で保持する。

### 6.3 外側Falseケース

条件：

```text
error in.status == False
```

処理：

- `API ReturnCode == 0`を判定する。
- 判定結果を内側Case Structureへ渡す。

---

## 7. ReturnCodeが0か判定する

外側Falseケース内へ次を配置する。

1. `Equal?`を配置する。
2. 一方へ`API ReturnCode`を配線する。
3. もう一方へI32定数`0`を配線する。
4. 定数を右クリックし、表現形式が`I32`であることを確認する。
5. `Equal?`のBoolean出力を内側Case Structureのセレクタ端子へ配線する。

判定結果：

| 内側ケース | 条件 | 意味 |
|---|---|---|
| True | `API ReturnCode == 0` | RAMScope API正常 |
| False | `API ReturnCode != 0` | RAMScope API異常 |

TrueとFalseの意味を逆にしない。`Equal?`を使用しているため、**True側が正常**になる。

---

## 8. 内側Trueケースを作成する

条件：

```text
API ReturnCode == 0
```

処理：

1. 外側Caseへ入れた`error in`を内側Caseへ配線する。
2. 内側Trueケースでは`error in`をそのまま出力トンネルへ配線する。
3. 新しいエラーは生成しない。

この時点の`error in`は外側Falseケースを通っているため、`status=False`の正常クラスタである。

---

## 9. 内側Falseケースでエラー文字列を作る

条件：

```text
API ReturnCode != 0
```

作成する文字列：

```text
RAMScope RAMScopeGT150DeviceInit failed. ReturnCode=0x30100001 (806354945)
```

### 9.1 16進表示用にI32をU32へType Castする

`API ReturnCode`はI32だが、16進表示では32bitのビット列をそのまま8桁表示したい。

1. `Type Cast`を配置する。
2. `API ReturnCode`を`Type Cast`のデータ入力へ配線する。
3. U32数値定数を配置する。
4. U32定数を`Type Cast`の型指定入力へ配線する。
5. `Type Cast`出力がU32になったことをワイヤ色と詳細ヘルプで確認する。

通常の数値変換ではなく`Type Cast`を使う理由：

- 戻り値のビット列を変更せず、符号なし32bitとして16進表示するため。
- 上位ビットが1のコードでも`FFFFFFFF`のように正しく表示するため。

### 9.2 `Format Into String`を配置する

1. `Format Into String`を配置する。
2. ノードの下端を下へドラッグし、引数端子を3個表示する。
3. 文字列定数を配置する。
4. 次のフォーマット文字列を入力する。

```text
RAMScope %s failed. ReturnCode=0x%08X (%d)
```

### 9.3 `Format Into String`へ配線する順番

フォーマット指定と引数の対応は次のとおり。

| 順番 | フォーマット | 配線する値 | 型 |
|---:|---|---|---|
| 1 | `%s` | `Function Name` | String |
| 2 | `%08X` | Type Cast後のReturnCode | U32 |
| 3 | `%d` | 元の`API ReturnCode` | I32 |

配線イメージ：

```text
Format string:
"RAMScope %s failed. ReturnCode=0x%08X (%d)"

Function Name ───────────────→ 引数1 `%s`
Type Cast後のU32 ReturnCode ─→ 引数2 `%08X`
元のI32 ReturnCode ──────────→ 引数3 `%d`
```

各指定子の意味：

| 指定子 | 意味 |
|---|---|
| `%s` | 文字列 |
| `%08X` | 16進数、大文字、8桁、空き桁を0で埋める |
| `%d` | 符号付き10進整数 |

`0x`は`%08X`が自動で付けるものではないため、フォーマット文字列側へ直接記載する。

### 9.4 期待出力

入力：

```text
Function Name  = RAMScopeGT150DeviceInit
API ReturnCode = 806354945
```

出力：

```text
RAMScope RAMScopeGT150DeviceInit failed. ReturnCode=0x30100001 (806354945)
```

---

## 10. `Bundle By Name`でerror clusterを作る

内側Falseケースへ`Bundle By Name`を配置する。

### 10.1 基準クラスタを接続する

1. `error in`を`Bundle By Name`のクラスタ入力へ配線する。
2. `Bundle By Name`を下方向へ広げ、次の3要素を表示する。

```text
status
code
source
```

### 10.2 各要素へ配線する

| error cluster要素 | 配線する値 |
|---|---|
| `status` | Boolean定数`True` |
| `code` | `API ReturnCode`のI32値 |
| `source` | `Format Into String`の出力文字列 |

作成結果：

```text
status = True
code   = API ReturnCode
source = RAMScope <Function Name> failed. ReturnCode=0xXXXXXXXX (<decimal>)
```

`code`へU32を接続しない。error clusterの`code`はI32なので、元の`API ReturnCode`を配線する。

### 10.3 出力トンネル

1. `Bundle By Name`のクラスタ出力を内側Case Structureの右側トンネルへ配線する。
2. 内側Trueケースでも同じ出力トンネルへ`error in`を配線する。
3. 内側Caseの出力を外側Falseケースの出力トンネルへ配線する。
4. 外側Trueケースでも同じ出力トンネルへ`error in`を配線する。
5. 外側Caseの出力を`error out`へ配線する。

全ケースで出力トンネルを配線しないと、VIの実行矢印が壊れる。

---

## 11. ケースごとの最終配線

### 11.1 外側Trueケース

```text
error in.status=True

error in ─────────────────────────→ error out
```

### 11.2 外側False／内側Trueケース

```text
error in.status=False
API ReturnCode=0

error in ─────────────────────────→ error out
```

### 11.3 外側False／内側Falseケース

```text
error in.status=False
API ReturnCode!=0

API ReturnCode ─→ Type Cast(U32) ─┐
Function Name ────────────────────┼→ Format Into String ─→ source
API ReturnCode(I32) ──────────────┘

error in ─→ Bundle By Name
             status=True
             code=API ReturnCode
             source=生成文字列
                  ↓
              error out
```

---

## 12. VIアイコンと説明を設定する

### 12.1 VI説明

`ファイル → VIプロパティ → ドキュメント`へ次を記載する。

```text
RAMScope APIのI32戻り値をLabVIEW標準error clusterへ変換する。
error inに既存エラーがある場合は元エラーを優先して保持する。
ReturnCode=0は正常、0以外はstatus=Trueのエラーを生成する。
```

### 12.2 端子説明

| 端子 | 説明 |
|---|---|
| `API ReturnCode` | RAMScope API関数のI32戻り値 |
| `Function Name` | エラーメッセージへ表示するAPI関数名 |
| `error in` | CLFNまたは前段VIのエラー。存在する場合は優先する |
| `error out` | 既存エラーまたはAPI戻り値から生成したエラー |

---

## 13. 単体テスト

VI単体で次の4ケースを確認する。

### テスト1：正常

```text
error in.status = False
API ReturnCode  = 0
Function Name   = RAMScopeGT150DeviceInit
```

期待結果：

```text
error out.status = False
error out.code   = 0
```

### テスト2：RAMScope APIエラー

```text
error in.status = False
API ReturnCode  = 806354945
Function Name   = RAMScopeGT150DeviceInit
```

期待結果：

```text
error out.status = True
error out.code   = 806354945
error out.source = RAMScope RAMScopeGT150DeviceInit failed. ReturnCode=0x30100001 (806354945)
```

### テスト3：既存エラーを優先

`error in`へ次を与える。

```text
status = True
code   = 1234
source = Existing error
```

さらに、

```text
API ReturnCode = 806354945
```

を与える。

期待結果：

```text
status = True
code   = 1234
source = Existing error
```

RAMScope APIエラーで元エラーを上書きしないことを確認する。

### テスト4：上位ビットが1のコード

```text
API ReturnCode = -1
```

期待する16進表示：

```text
0xFFFFFFFF
```

これにより、I32からU32への`Type Cast`が正しく機能していることを確認できる。

---

## 14. DLLラッパでの接続方法

各`RS_DLL_*` VIでは、CLFNの後ろへ次のように接続する。

```text
CLFN
├─ 戻り値 I32 ─────────────→ API ReturnCode
├─ 戻り値 I32 ─────────────→ RAMScope_Code_To_Error.vi / API ReturnCode
├─ CLFN error out ─────────→ RAMScope_Code_To_Error.vi / error in
└─ 関数名文字列定数 ───────→ RAMScope_Code_To_Error.vi / Function Name

RAMScope_Code_To_Error.vi / error out ─→ DLLラッパのerror out
```

例：`RS_DLL_GT150DeviceInit.vi`

```text
Function Name = "RAMScopeGT150DeviceInit"
```

CLFNの`error out`にエラーがある場合は、そのエラーがそのまま返る。
CLFNは正常でもAPI ReturnCodeが0以外の場合は、RAMScope APIエラーへ変換される。

---

## 15. よくあるミス

| 症状 | 原因 | 対策 |
|---|---|---|
| 内側CaseのTrueでエラーになる | `Equal?`のTrue/Falseを逆に理解している | Trueは`ReturnCode==0`の正常ケース |
| 実行矢印が壊れる | Case Structureのどこかで出力トンネル未配線 | 外側・内側の全ケースでerror clusterを配線 |
| 16進が8桁にならない | `%X`のみ使用 | `%08X`を使用 |
| `0x`が付かない | フォーマット指定に含めていない | `0x%08X`と記載 |
| 上位ビットが1のコードが崩れる | I32をそのまま16進化 | I32をU32へ`Type Cast`してから`%08X` |
| `code`端子へ配線できない | U32をerror clusterのcodeへ接続している | 元のI32 ReturnCodeを接続 |
| 元のCLFNエラーが消える | ReturnCodeを常に新規エラー化 | 外側Caseで`error in.status=True`を最優先 |
| ReturnCode比較の0がDBL | 数値定数の表現形式が未設定 | 定数をI32へ変更 |
| メッセージの値が入れ替わる | Format Into Stringの引数順が違う | `%s`、`%08X`、`%d`の順に配線 |

---

## 16. 完了チェックリスト

- [ ] `API ReturnCode`がI32である
- [ ] `Function Name`がStringである
- [ ] `error in / error out`が標準error clusterである
- [ ] 外側Caseのセレクタが`error in.status`である
- [ ] 外側Trueケースが元エラーをそのまま出力する
- [ ] 内側Caseのセレクタが`API ReturnCode == 0`である
- [ ] 内側Trueケースが正常クラスタを出力する
- [ ] 内側Falseケースで`Bundle By Name`を使用している
- [ ] 16進表示前にI32をU32へ`Type Cast`している
- [ ] フォーマット文字列が`RAMScope %s failed. ReturnCode=0x%08X (%d)`である
- [ ] `status=True`、`code=API ReturnCode`、`source=生成文字列`になっている
- [ ] 全Case Structureの出力トンネルが配線されている
- [ ] 4パターンの単体テストが完了している
