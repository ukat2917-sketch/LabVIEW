# 10-06B. `PoC_RAMScope_Main.vi` Close Case False側の出力配線補正

**最終整理日：2026-07-21**

> 本書は、[06A_PoC_RAMScope_Main_VI詳細作成手順.md](./06A_PoC_RAMScope_Main_VI詳細作成手順.md)の「L. Closeの要否を判定する」と「M. Final Stateを出力する」を置き換える補正手順である。
>
> 旧手順ではFalseケースに`error out`しか記載されておらず、`Status`および`TestError`の出力トンネルが未配線となる。本補正ではFalseケースに`Error_To_TestStatus.vi`を配置し、Trueケースと同じ4種類の出力を必ず配線する。

---

## 1. Close Caseが出力する値

Close Case Structureは、True／Falseの両ケースで次の4出力を返す。

| 出力 | 型 | Falseケースの接続元 | Trueケースの接続元 |
|---|---|---|---|
| `State` | `RAMScope_PoC_State.ctl` | Kから入ったStateをそのまま通過 | Kから入ったStateをそのまま通過 |
| `Status` | `Status.ctl` | `Error_To_TestStatus.vi / Status` | `RAMScope_Close.vi / Status` |
| `TestError` | `TestError.ctl` | `Error_To_TestStatus.vi / TestError` | `RAMScope_Close.vi / TestError` |
| `error out` | error cluster | `Error_To_TestStatus.vi / error out` | `RAMScope_Close.vi / error out` |

Case Structure右側の各出力トンネルは、True／False両ケースで同じ型を接続する。`Use default if unwired`は使用しない。

---

## 2. Close Case Structureを配置する

作業領域：

```text
Cleanup Release Case Structureの後段
  → Close Case Structure
```

1. Kの出力Stateを名前でバンドル解除（Unbundle By Name）へ接続する。
2. `Connected?`を選択する。
3. `Connected?`をClose Case Structureのselectorへ接続する。
4. Kの出力StateをClose Case左側のState入力トンネルへ接続する。
5. Kの出力errorをClose Case左側のerror入力トンネルへ接続する。
6. Case右側へ次の4個の出力トンネルを作る。

```text
State
Status
TestError
error out
```

---

## 3. Falseケース（Connected?=False：DeviceInit未成功）

### 3.1 このケースの意味

`RAMScope_Connect.vi`が成功していないため、`RAMScope_Close.vi`および`DeviceExit`は呼ばない。

ただし、Kから入ってきたerror clusterにはConnect失敗などのOriginal Errorが入っている可能性がある。そのerror clusterを`Status.ctl`と`TestError.ctl`へ変換しなければ、PoCの最終出力を作れない。

### 3.2 配置する関数およびSubVI

- `Error_To_TestStatus.vi`
- 文字列定数（String Constant）1個

### 3.3 配線順

1. Falseケースへ`Error_To_TestStatus.vi`を配置する。
2. Close Case左側のerror入力トンネルから入ったKの出力errorを、`Error_To_TestStatus.vi / error in`へ接続する。
3. 文字列定数を配置し、全文として次を入力する。

```text
RAMScope
```

4. 文字列定数`RAMScope`を`Error_To_TestStatus.vi / Device Name`へ接続する。
5. Close Case左側のState入力トンネルから入ったStateを、右側の`State`出力トンネルへそのまま接続する。
6. `Error_To_TestStatus.vi / Status`を、右側の`Status`出力トンネルへ接続する。
7. `Error_To_TestStatus.vi / TestError`を、右側の`TestError`出力トンネルへ接続する。
8. `Error_To_TestStatus.vi / error out`を、右側の`error out`出力トンネルへ接続する。
9. このFalseケースには`RAMScope_Close.vi`、`Clear Errors`および`DeviceExit Wrapper`を配置しない。

配線の見取り図：

```text
Kの出力State ─────────────────────────→ State出力トンネル

Kの出力error
  → Error_To_TestStatus.vi
       Device Name = "RAMScope"
       ├─ Status    ──────────────────→ Status出力トンネル
       ├─ TestError ──────────────────→ TestError出力トンネル
       └─ error out ──────────────────→ error out出力トンネル
```

### 3.4 Default値を使わない理由

Falseケースで`Status=OK`、空の`TestError`または既定error clusterを接続してはならない。

Connected?がFalseになる代表例はConnect失敗であり、入力errorには接続失敗の情報が入っている。この情報を`Error_To_TestStatus.vi`で変換して最終出力へ残す必要がある。

---

## 4. Trueケース（Connected?=True：DeviceExitが必要）

1. `RAMScope_Close.vi`を配置する。
2. Close Case左側のerror入力トンネルから入ったKの出力errorを、`RAMScope_Close.vi / error in`へ接続する。
3. Close Case左側のState入力トンネルから入ったStateを、右側の`State`出力トンネルへそのまま接続する。
4. `RAMScope_Close.vi / Status`を、右側の`Status`出力トンネルへ接続する。
5. `RAMScope_Close.vi / TestError`を、右側の`TestError`出力トンネルへ接続する。
6. `RAMScope_Close.vi / error out`を、右側の`error out`出力トンネルへ接続する。
7. `RAMScope_Close.vi`は前段エラーを保持したままDeviceExitを試すため、このケース内に`Clear Errors`を配置しない。

配線の見取り図：

```text
Kの出力State ─────────────────────────→ State出力トンネル

Kの出力error
  → RAMScope_Close.vi
       ├─ Status    ──────────────────→ Status出力トンネル
       ├─ TestError ──────────────────→ TestError出力トンネル
       └─ error out ──────────────────→ error out出力トンネル
```

---

## 5. Case Structure外の最終配線

1. Close Caseの`State`出力トンネルを`Final State`表示器へ接続する。
2. Close Caseの`Status`出力トンネルをPoCの`Status`出力へ接続する。
3. Close Caseの`TestError`出力トンネルをPoCの`TestError`出力へ接続する。
4. Close Caseの`error out`出力トンネルをPoCの`error out`へ接続する。

```text
Close Case
  ├─ State      → Final State
  ├─ Status     → 実行結果ステータス
  ├─ TestError  → エラー情報
  └─ error out  → エラー出力
```

---

## 6. 単体テスト

### 6.1 Connect失敗

```text
Connected? = False
Kの出力error.status = True
Kの出力error.code = Connect失敗コード
```

期待結果：

- `RAMScope_Close.vi`は実行されない。
- Falseケースの`Error_To_TestStatus.vi`が実行される。
- PoCの`error out`にConnect失敗errorが保持される。
- `Status=Error`となる。
- `TestError`に機器名`RAMScope`とConnect失敗コードが入る。
- Final Stateは入力Stateと同じで、Connected?=Falseである。

### 6.2 Connect成功、後段正常

```text
Connected? = True
Kの出力error.status = False
```

期待結果：`RAMScope_Close.vi`を実行し、Close出力をCase外へ返す。

### 6.3 Connect成功、後段エラーあり

```text
Connected? = True
Kの出力error.status = True
```

期待結果：`RAMScope_Close.vi`がDeviceExitを試行し、Original Errorを優先して返す。
