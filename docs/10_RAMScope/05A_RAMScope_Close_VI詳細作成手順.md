# 10-05A. `RAMScope_Close.vi` 詳細作成手順

**最終整理日：2026-07-21**

> 本書は、[05_Public_API_8個_監査済み作成手順.md](./05_Public_API_8個_監査済み作成手順.md)の`RAMScope_Close.vi`節を置き換える詳細手順である。
>
> 旧節にある「2入力のCaseまたはMerge Errors相当処理」という記述は使用しない。本VIでは**エラーをマージ（Merge Errors）**を使用する。

---

## 0. 実現したい機能とVIの責務

`RAMScope_Close.vi`は、前段処理でエラーが発生していても`RAMScopeGT150DeviceExit()`を試行し、RAMScopeVP APIとの接続を終了するCleanup VIである。

同時に、前段で最初に発生したエラーをDeviceExitの結果で上書きしない。

```text
前段エラーあり
  → DeviceExitは実行する
  → 最終errorには前段エラーを残す

前段エラーなし
  → DeviceExitを実行する
  → DeviceExitが失敗した場合はDeviceExitエラーを返す
```

---

## 1. 入力データの実体

本VIが扱うerror clusterは2個である。

| 名前 | 接続元 | 意味 |
|---|---|---|
| `Original Error` | 本VIの`error in` | Closeより前に発生したエラーまたは警告 |
| `DeviceExit Error` | `RS_DLL_GT150DeviceExit.vi / DeviceExit error` | DeviceExit呼出し自体の結果 |

`RS_DLL_GT150DeviceExit.vi`はCleanup用Wrapperである。入力された`error in`を内部で保持したまま、CLFNへ渡すerror wireだけをエラークリア（Clear Errors）して、前段エラーの有無にかかわらずDeviceExitを呼び出す。

---

## 2. 出力データモデル

```text
Final Error
  → Error_To_TestStatus.vi
      ├─ Status
      ├─ TestError
      └─ error out
```

`Final Error`は次の優先順位で決定する。

```text
1. Original Errorにエラーがある場合はOriginal Error
2. Original Errorが正常でDeviceExit Errorにエラーがある場合はDeviceExit Error
3. 両方正常なら正常error cluster
```

警告についてはエラーをマージ（Merge Errors）の標準動作に従う。実エラーが存在する場合は警告より実エラーを優先する。

---

## 3. 前提条件・異常条件

| Original Error | DeviceExit Error | Final Error |
|---|---|---|
| 正常 | 正常 | 正常 |
| 正常 | エラー | DeviceExit Error |
| エラー | 正常 | Original Error |
| エラー | エラー | Original Error |

重要なのは、どの組み合わせでも`RS_DLL_GT150DeviceExit.vi`を実行することである。

---

## 4. 処理アルゴリズム

```text
Original Error = error in

DeviceExit Error = RS_DLL_GT150DeviceExit.vi(Original Error)

Final Error = Merge Errors(
    input 0 = Original Error,
    input 1 = DeviceExit Error
)

Status, TestError, error out
    = Error_To_TestStatus.vi(Final Error, "RAMScope")
```

---

## 5. LabVIEW構造の選定理由

### 5.1 エラーをマージ（Merge Errors）を使う理由

エラーをマージ（Merge Errors）は、複数のerror clusterを1個へまとめる関数である。

今回、上側の1個目の入力へ`Original Error`を接続し、下側の2個目の入力へ`DeviceExit Error`を接続する。これにより、両方にエラーがある場合は先に接続したOriginal Errorを保持できる。

また、Merge Errorsは両方の入力が到着してから実行される。このデータフローにより、`RAMScope_Close.vi`が終了する前にDeviceExit Wrapperの実行完了を待つことができる。

### 5.2 Case Structureを使用しない理由

Case Structureでもerror clusterを選択できるが、選択されたCaseで`DeviceExit Error`を使用しない配線にすると、DeviceExit完了を待つ依存関係が図から読み取りにくくなる。

本VIの目的は「DeviceExitを必ず試行し、その後で最初のエラーを返す」ことであるため、2本のerror wireを直接Merge Errorsへ入れる構成を正式方式とする。

---

## 6. 入出力

| 端子 | 方向 | 型 | 説明 |
|---|---|---|---|
| `error in` | 入力 | error cluster | Close前までのOriginal Error |
| `Status` | 出力 | `Status.ctl` | TestStand判定用ステータス |
| `TestError` | 出力 | `TestError.ctl` | 機器名、code、message等 |
| `error out` | 出力 | error cluster | Original Errorを優先して統合したFinal Error |

`DeviceExit Error`と`Final Error`はブロックダイアグラム内のワイヤ名であり、通常はフロントパネル端子にしない。

---

## 7. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所・追加方法 |
|---:|---|---|---|
| 1 | `RS_DLL_GT150DeviceExit.vi` | SubVI | `30_RAMScope\10_DLL_Wrapper` |
| 1 | エラーをマージ | Merge Errors | プログラミング → ダイアログ＆ユーザインタフェース |
| 1 | `Error_To_TestStatus.vi` | SubVI | 共通エラー処理フォルダ |
| 1 | 文字列定数 | String Constant | プログラミング → 文字列 |

エラーをマージ（Merge Errors）がパレットで見つからない場合は、ブロックダイアグラムで`Ctrl + Space`を押し、Quick Dropへ`Merge Errors`と入力して配置する。

---

## 8. 配線順

### A. Original Errorのワイヤを分岐する

作業領域：ブロックダイアグラム左側。

1. 本VIの`error in`端子から右方向へerror wireを引く。
2. error wireを2方向へ分岐する。
3. 上側の分岐を`Original Error`として、後でエラーをマージ（Merge Errors）の上側入力へ接続する。
4. 下側の分岐を`RS_DLL_GT150DeviceExit.vi / error in`へ接続する。

この分岐により、同じ前段error clusterを、保持用とDeviceExit Wrapper入力用の両方へ渡す。

### B. DeviceExit Wrapperを配置・配線する

1. `RS_DLL_GT150DeviceExit.vi`をOriginal Error分岐の右側へ配置する。
2. A-4で作った下側error wireをWrapperの`error in`へ接続する。
3. Wrapperの`DeviceExit error`出力から右方向へerror wireを引く。
4. このワイヤへ`DeviceExit Error`というラベルを付ける。
5. Wrapperの`API ReturnCode`はPublic VIの正式出力にしない。デバッグ時に確認したい場合だけ表示器を作成する。

`RS_DLL_GT150DeviceExit.vi`内部では前段errorをクリアしてCLFNを呼ぶため、本VI側にエラークリア（Clear Errors）を追加しない。

### C. エラーをマージ（Merge Errors）を配置する

1. `RS_DLL_GT150DeviceExit.vi`の右側へエラーをマージ（Merge Errors）を配置する。
2. Merge Errorsが2入力表示になっていることを確認する。
3. 入力が1個しか見えない場合は、ノードの下辺を下方向へドラッグして2入力へ広げる。
4. A-3の`Original Error`をMerge Errorsの**上側1個目のerror入力**へ接続する。
5. B-3の`DeviceExit Error`をMerge Errorsの**下側2個目のerror入力**へ接続する。
6. Merge Errorsの右側出力へ`Final Error`というワイヤラベルを付ける。

配線の見取り図：

```text
error in
  ├──────────────────────────────→ Merge Errors 上側入力 1
  │                                  Original Error
  │
  └→ RS_DLL_GT150DeviceExit.vi
         error in
            ↓
         DeviceExit error ─────────→ Merge Errors 下側入力 2
                                      DeviceExit Error

Merge Errors出力
  → Final Error
```

この接続順を逆にしない。DeviceExit Errorを上側へ接続すると、両方がエラーの場合にCleanupエラーが前段エラーより先に選ばれる可能性がある。

### D. Error_To_TestStatus.viへ接続する

1. `Error_To_TestStatus.vi`をMerge Errorsの右側へ配置する。
2. Merge Errorsの`Final Error`を`Error_To_TestStatus.vi / error in`へ接続する。
3. 文字列定数を配置し、全文として次を入力する。

```text
RAMScope
```

4. 文字列定数`RAMScope`を`Error_To_TestStatus.vi / Device Name`へ接続する。
5. 同SubVIの`Status`を本VIの`Status`出力へ接続する。
6. 同SubVIの`TestError`を本VIの`TestError`出力へ接続する。
7. 同SubVIの`error out`を本VIの`error out`へ接続する。

完成した主要error wireは次の形になる。

```text
error in ─┬──────────────────────────────┐
          │                              ↓
          └→ DeviceExit Wrapper ─→ Merge Errors ─→ Error_To_TestStatus.vi
                                         ↑
                          Original Error ─┘
```

---

## 9. 単体テスト

### 9.1 テスト1：前段正常、DeviceExit正常

```text
Original Error.status = False
Original Error.code   = 0
DeviceExit Error      = 正常
```

期待結果：

```text
Final Error.status = False
Final Error.code   = 0
Status             = OK
```

### 9.2 テスト2：前段エラーあり、DeviceExit正常

`error in`へ次のダミーエラーを入力する。

```text
status = True
code   = -700999
source = RAMScope_Close.vi unit test: original error
```

期待結果：

```text
DeviceExitは実行される
Final Error.code   = -700999
Final Error.source = RAMScope_Close.vi unit test: original error
```

### 9.3 テスト3：前段正常、DeviceExitエラー

DeviceExit Wrapperを単体試験用ダミーSubVIへ一時的に置き換えるか、WrapperのテストVIで次のDeviceExit Errorを生成する。

```text
status = True
code   = -700998
source = RAMScope_Close.vi unit test: DeviceExit error
```

期待結果：

```text
Final Error.code   = -700998
Final Error.source = RAMScope_Close.vi unit test: DeviceExit error
```

### 9.4 テスト4：前段エラーとDeviceExitエラーが両方存在

```text
Original Error.code = -700999
DeviceExit Error.code = -700998
```

期待結果：

```text
Final Error.code = -700999
```

前段で最初に発生したOriginal Errorが保持されることを確認する。

### 9.5 実機Cleanup試験

1. Connect成功後にCloseを実行し、再度Connectできることを確認する。
2. Connect後、意図的なローカルエラーを`error in`へ入れてCloseを実行する。
3. Original Errorが保持されても、次回Connectが成功することを確認する。
4. Closeを2回実行した場合のDeviceExit ReturnCodeを記録する。

---

## 10. 完成チェックリスト

- [ ] `error in`がOriginal Error保持用とDeviceExit Wrapper用へ分岐されている。
- [ ] DeviceExit Wrapperは前段エラーがあっても実行される構成である。
- [ ] Merge Errors上側入力がOriginal Errorである。
- [ ] Merge Errors下側入力がDeviceExit Errorである。
- [ ] Merge Errors出力がError_To_TestStatus.viへ接続されている。
- [ ] Device Nameへ文字列全文`RAMScope`が接続されている。
- [ ] 前段エラーとDeviceExitエラーが両方あるテストで前段エラーが保持される。
- [ ] 前段エラーがある状態でもDeviceExitが完了し、再接続できる。
