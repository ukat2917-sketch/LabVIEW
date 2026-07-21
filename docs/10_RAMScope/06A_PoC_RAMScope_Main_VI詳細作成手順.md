# 10-06A. `PoC_RAMScope_Main.vi` 詳細作成手順

**最終整理日：2026-07-21**

> 本書は、[06_PoC_ロギング_TestStand.md](./06_PoC_ロギング_TestStand.md)の`PoC_RAMScope_Main.vi`節を置き換える詳細手順である。
>
> 旧節にある「Boolean Falseで初期化する」「成功時だけTrueへ更新する」という記述だけでは、配置する関数、接続元、接続先およびCleanup判定が不足している。本書では、`RAMScope_PoC_State.ctl`を左から右へ流す方式へ一本化する。

---

## 0. 実現したい機能とVIの責務

`PoC_RAMScope_Main.vi`は、TestStandを使用せず、RAMScope公開APIを次の順で1回実行するPoCである。

```text
Connect
  → Init
  → Set Cond
  → Log Start
  → Wait
  → Read
  → Log Stop
  → Release
  → Close
```

途中でエラーが発生しても、すでに成功した処理を状態として保持し、必要なCleanupだけを実行する。

```text
Connect成功後にエラー
  → Closeが必要

Log Start成功後にエラー
  → Stop、Release、Closeが必要

Stop成功後にエラー
  → Release、Closeが必要
```

---

## 1. 入力データの実体

通常処理には2本の主要ワイヤを流す。

| ワイヤ | 型 | 意味 |
|---|---|---|
| `Main Error` | error cluster | 各公開APIを順番に実行するための通常error wire |
| `PoC State` | `RAMScope_PoC_State.ctl` | どの処理が正常終了したかを保持する状態クラスタ |

`PoC State`は現在の機器状態を直接読み取るものではなく、このPoC内で各処理が成功した履歴を保持する。

---

## 2. 出力データモデル

### 2.1 `RAMScope_PoC_State.ctl`

次のtypedefクラスタを作成する。

```text
30_RAMScope\00_Common\RAMScope_PoC_State.ctl
```

| フィールド | 型 | Trueの意味 |
|---|---|---|
| `Connected?` | Boolean | `RAMScope_Connect.vi`が正常終了した |
| `Measurement Started?` | Boolean | `RAMScope_Log_Start.vi`が正常終了した |
| `Stopped?` | Boolean | 通常経路またはCleanup経路の`RAMScope_Log_Stop.vi`が正常終了した |
| `Released?` | Boolean | `RAMScope_Release.vi`が正常終了した |
| `File Open?` | Boolean | 将来、`RAMScope_File_Log_Open.vi`が正常終了した |

`Measurement Started?`はStop後もTrueのままとする。これは「現在測定中」という意味ではなく、「MeasStartが成功した履歴」である。

現在測定中かどうかは次で判定する。

```text
Measurement Active?
= Measurement Started? AND NOT Stopped?
```

---

## 3. 前提条件・異常条件

```text
Connect失敗
  Connected?=False
  Init以降はerror wireによりスキップ
  Closeも呼ばない

Connect成功、Start前に失敗
  Connected?=True
  Measurement Started?=False
  StopとReleaseは呼ばない
  Closeだけ呼ぶ

Start成功後に失敗
  Measurement Started?=True
  Stopped?=False
  Cleanup Stopを試す

Stop成功
  Stopped?=True
  Releaseを試す

Release成功
  Released?=True
  Releaseを再度呼ばない
```

---

## 4. 処理アルゴリズム

```text
State = all False
Main Error = error in

Connect
Connected? = NOT Connect Error.status

Init
Set Cond

Log Start
Measurement Started?
    = Connected? AND NOT Log Start Error.status

Wait
Read

Normal Log Stop
Stopped?
    = Measurement Started? AND NOT Log Stop Error.status

if Stopped? AND NOT Released?:
    Release
    Released? = NOT Release Error.status

Cleanup:
    Original Error = Main Error

    if Measurement Started? AND NOT Stopped?:
        Clear Errors
        Cleanup Log Stop
        Stopped? = NOT Cleanup Stop Error.status
        Main Error = Merge Errors(Original Error, Cleanup Stop Error)

    if Stopped? AND NOT Released?:
        Clear Errors
        Cleanup Release
        Released? = NOT Cleanup Release Error.status
        Main Error = Merge Errors(Main Error, Cleanup Release Error)

    if Connected?:
        RAMScope_Close.vi(Main Error)
```

---

## 5. LabVIEW構造の選定理由

### 5.1 状態クラスタを使う理由

4本以上のBooleanを別々に左から右へ引くと、配線が交差し、どの時点の値をCleanupが参照しているか分かりにくくなる。

```text
RAMScope_PoC_State.ctl
  → Bundle By Nameで1項目だけ更新
  → 他の項目は前の値を保持
  → 更新後クラスタを次の処理へ渡す
```

### 5.2 Shift Registerを使用しない理由

このPoCは1回だけ左から右へ実行するため、外側Whileループを必要としない。したがって、状態クラスタを通常ワイヤで流す。

将来、ReadをWhileループで繰り返す場合は、同じ`RAMScope_PoC_State.ctl`をWhileループのShift Registerへ接続する。

### 5.3 `error out.status`から成功判定を作る理由

公開APIは正常終了時に`error out.status=False`を返す。

```text
Succeeded? = NOT(error out.status)
```

前段エラーにより公開APIがスキップされた場合も`error out.status=True`が保持されるため、成功フラグが誤ってTrueにならない。

---

## 6. 主な入出力

```text
入力：
  Byte Order
  Meas Config
  Channel List
  Module Log Configs
  MaxDataNum
  Wait Time
  error in

出力：
  UnitNum
  kind
  Module List
  MdlNo_RAM
  MdlNo_CAN
  Endian_RAM
  Raw Buffer
  DataNum
  LostDataNum
  Packets
  Final State
  Status
  TestError
  error out
```

`Final State`はデバッグ用出力として`RAMScope_PoC_State.ctl`を割り当てる。TestStand組込み時には内部状態として隠してよい。

---

## 7. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 用途 |
|---:|---|---|---|
| 1 | `RAMScope_PoC_State.ctl`定数 | typedef cluster constant | 初期状態を作る |
| 4以上 | 名前でバンドル | Bundle By Name | 成功フラグを1項目ずつ更新する |
| 必要数 | 名前でバンドル解除 | Unbundle By Name | 状態Booleanとerror.statusを取り出す |
| 必要数 | 否定 | Not | `NOT(error.status)`を作る |
| 必要数 | 複合演算 | Compound Arithmetic | AND条件を作る |
| 3以上 | ケースストラクチャ | Case Structure | Cleanup Stop、Release、Closeの要否を分岐する |
| 2 | エラークリア | Clear Errors | 前段エラーがあってもCleanup APIを呼ぶ |
| 2以上 | エラーをマージ | Merge Errors | Original Errorを優先してCleanup Errorを追加する |
| 各1 | `RAMScope_*` Public VI | SubVI | 通常処理とCleanup |

---

## 8. 配線順

## A. `RAMScope_PoC_State.ctl`を作成する

1. 新規カスタム制御器を作成する。
2. クラスタを配置する。
3. Boolean制御器を5個入れる。
4. 上から次の順でラベルを付ける。

```text
Connected?
Measurement Started?
Stopped?
Released?
File Open?
```

5. すべての既定値をFalseにする。
6. typedefとして`RAMScope_PoC_State.ctl`へ保存する。

## B. Initial Stateを配置する

作業領域：ブロックダイアグラム左端、`RAMScope_Connect.vi`の左側。

1. `RAMScope_PoC_State.ctl`をブロックダイアグラムへドラッグする。
2. 定数として配置する。
3. 5項目がすべてFalseであることを確認する。
4. 定数の右側出力ワイヤへ`Initial State`というラベルを付ける。
5. このクラスタ定数はフロントパネル制御器にしない。

初期状態：

```text
Connected?            = False
Measurement Started?  = False
Stopped?              = False
Released?             = False
File Open?            = False
```

## C. Connect成功後に`Connected?`を更新する

作業領域：`RAMScope_Connect.vi`の直後。

1. `RAMScope_Connect.vi / error out`を名前でバンドル解除（Unbundle By Name）へ接続する。
2. `status`を選択する。
3. `status`出力を否定（Not）へ接続する。
4. Not出力へ`Connect Succeeded?`というラベルを付ける。
5. 名前でバンドル（Bundle By Name）を配置する。
6. B-4の`Initial State`をBundle By Nameのクラスタ入力へ接続する。
7. Bundle By Nameの項目を`Connected?`へ変更する。
8. `Connect Succeeded?`を`Connected?`入力へ接続する。
9. Bundle By Name出力へ`State After Connect`というラベルを付ける。

```text
Connected?
= NOT(RAMScope_Connect.vi.error out.status)
```

Bundle By Nameは、`Initial State`と`Connect Succeeded?`の両方が到着してから実行される。このため状態更新はConnect完了後に行われる。

## D. InitとSet Condの区間

1. `RAMScope_Connect.vi / error out`を`RAMScope_Init.vi / error in`へ接続する。
2. `RAMScope_Init.vi / error out`を`RAMScope_Set_Cond.vi / error in`へ接続する。
3. `State After Connect`は変更せず、ワイヤをLog Start後の状態更新位置まで右方向へ引く。
4. InitまたはSet Condで新しい状態Booleanを更新しない。

## E. Log Start成功後に`Measurement Started?`を更新する

作業領域：`RAMScope_Log_Start.vi`の直後。

1. `RAMScope_Log_Start.vi / error out`をUnbundle By Nameへ接続し、`status`を取り出す。
2. `status`をNotへ接続する。
3. `State After Connect`を別のUnbundle By Nameへ接続し、`Connected?`を取り出す。
4. `Connected?`とNot出力をANDへ接続する。
5. AND出力へ`Start Succeeded?`というラベルを付ける。
6. Bundle By Nameを配置する。
7. `State After Connect`をクラスタ入力へ接続する。
8. 項目を`Measurement Started?`へ設定する。
9. `Start Succeeded?`を同項目へ接続する。
10. Bundle出力へ`State After Start`というラベルを付ける。

```text
Measurement Started?
= Connected? AND NOT(RAMScope_Log_Start.vi.error out.status)
```

## F. WaitとRead

1. `RAMScope_Log_Start.vi / error out`を`RAMScope_Read.vi / error in`へ接続する前に、待機（Wait (ms)）を必要なデータフローへ組み込む。
2. `RAMScope_Read.vi`からRaw Buffer、DataNum、LostDataNum、Packetsを各表示器へ接続する。
3. `State After Start`は変更せず、Stop後の状態更新位置まで引く。

## G. 通常Log Stop成功後に`Stopped?`を更新する

作業領域：通常経路の`RAMScope_Log_Stop.vi`直後。

1. `RAMScope_Log_Stop.vi / error out.status`をUnbundle By Nameで取り出す。
2. `status`をNotへ接続する。
3. `State After Start`から`Measurement Started?`をUnbundle By Nameで取り出す。
4. `Measurement Started?`とNot出力をANDへ接続する。
5. AND出力へ`Normal Stop Succeeded?`というラベルを付ける。
6. Bundle By Nameを配置する。
7. `State After Start`をクラスタ入力へ接続する。
8. 項目を`Stopped?`へ設定する。
9. `Normal Stop Succeeded?`を`Stopped?`へ接続する。
10. Bundle出力へ`State After Normal Stop`というラベルを付ける。

```text
Stopped?
= Measurement Started? AND NOT(RAMScope_Log_Stop.vi.error out.status)
```

## H. 通常Releaseを呼ぶ条件と`Released?`更新

作業領域：通常Stop状態更新の直後。

1. `State After Normal Stop`をUnbundle By Nameへ接続する。
2. `Stopped?`と`Released?`を表示する。
3. `Released?`をNotへ接続する。
4. `Stopped?`と`NOT Released?`をANDへ接続する。
5. AND出力をCase Structureのselectorへ接続する。

```text
Need Release?
= Stopped? AND NOT Released?
```

### Falseケース（Need Release?=False：Release不要）

1. `RAMScope_Release.vi`を配置しない。
2. 入力StateをState出力トンネルへそのまま接続する。
3. 入力errorをerror出力トンネルへそのまま接続する。

### Trueケース（Need Release?=True：Release必要）

1. `RAMScope_Release.vi`を配置する。
2. UnitNoを接続する。
3. 通常Stopの`error out`をReleaseの`error in`へ接続する。
4. Releaseの`error out.status`を取り出してNotへ接続する。
5. Not出力へ`Release Succeeded?`というラベルを付ける。
6. Bundle By Nameを配置する。
7. `State After Normal Stop`をクラスタ入力へ接続する。
8. 項目を`Released?`へ設定する。
9. `Release Succeeded?`を接続する。
10. 更新StateをCaseのState出力トンネルへ接続する。
11. Release errorをCaseのerror出力トンネルへ接続する。

## I. Cleanup開始時にOriginal Errorを保持する

1. 通常経路の最後のerror wireを2方向へ分岐する。
2. 1本目へ`Original Error`というラベルを付ける。
3. 2本目をCleanup Stop判定へ引く。
4. 通常経路の最後のStateを`Cleanup Input State`としてCleanup Stop判定へ引く。

## J. Cleanup Stopの要否を判定する

1. `Cleanup Input State`をUnbundle By Nameへ接続する。
2. `Measurement Started?`と`Stopped?`を表示する。
3. `Stopped?`をNotへ接続する。
4. `Measurement Started?`と`NOT Stopped?`をANDへ接続する。
5. AND出力をCleanup Stop Case Structureのselectorへ接続する。

```text
Need Cleanup Stop?
= Measurement Started? AND NOT Stopped?
```

### Falseケース（Need Cleanup Stop?=False：Cleanup Stop不要）

1. Cleanup Stop VIを配置しない。
2. Cleanup Input StateをState出力へそのまま接続する。
3. Original Errorをerror出力へそのまま接続する。

### Trueケース（Need Cleanup Stop?=True：Cleanup Stop必要）

1. エラークリア（Clear Errors）を配置する。
2. Original ErrorをClear Errorsへ接続する。
3. Clear Errors出力を`RAMScope_Log_Stop.vi / error in`へ接続する。
4. UnitNoをLog Stopへ接続する。
5. Log Stopの`error out.status`を取り出し、Notへ接続する。
6. Not出力へ`Cleanup Stop Succeeded?`というラベルを付ける。
7. Bundle By NameへCleanup Input Stateを接続する。
8. 項目を`Stopped?`へ設定する。
9. `Cleanup Stop Succeeded?`を接続する。
10. 更新StateをCaseのState出力へ接続する。
11. エラーをマージ（Merge Errors）を配置する。
12. Original ErrorをMerge Errorsの上側入力1へ接続する。
13. Cleanup Log Stopの`error out`を下側入力2へ接続する。
14. Merge Errors出力をCaseのerror出力へ接続する。

Original Errorを上側へ接続するため、両方がエラーでも最初のエラーを保持する。

## K. Cleanup Releaseの要否を判定する

Jの出力Stateに対して、Hと同じ式を使用する。

```text
Need Cleanup Release?
= Stopped? AND NOT Released?
```

### Falseケース（Need Cleanup Release?=False：Cleanup Release不要）

Stateとerrorをそのまま通過させる。

### Trueケース（Need Cleanup Release?=True：Cleanup Release必要）

1. 入力errorをClear Errorsへ接続する。
2. Clear Errors出力を`RAMScope_Release.vi / error in`へ接続する。
3. UnitNoを接続する。
4. Release error.statusをNotし、`Cleanup Release Succeeded?`を作る。
5. Bundle By Nameで`Released?`を更新する。
6. Merge Errorsの上側入力1へCleanup Release前のerrorを接続する。
7. 下側入力2へReleaseの`error out`を接続する。
8. 更新StateとMerge Errors出力をCase外へ接続する。

## L. Closeの要否を判定する

1. Kの出力Stateから`Connected?`をUnbundle By Nameで取り出す。
2. `Connected?`をClose Case Structureのselectorへ接続する。

### Falseケース（Connected?=False：DeviceInit未成功）

1. `RAMScope_Close.vi`を配置しない。
2. 入力errorを最終error出力へそのまま接続する。

### Trueケース（Connected?=True：DeviceExitが必要）

1. `RAMScope_Close.vi`を配置する。
2. KのMerge Errors出力を`RAMScope_Close.vi / error in`へ接続する。
3. CloseのStatus、TestError、error outをPoCの最終出力へ接続する。

`RAMScope_Close.vi`は前段エラーを保持したままDeviceExitを試すため、このCase内ではClear Errorsを配置しない。

## M. Final Stateを出力する

1. Close CaseのState入力ワイヤをCase右側のState出力トンネルへ接続する。
2. 両Caseで同じState型を接続する。
3. Case外のStateワイヤを`Final State`表示器へ接続する。

---

## 9. 単体テスト

### 9.1 初期状態

期待：5項目すべてFalse。

### 9.2 Connect成功、Init失敗

期待：

```text
Connected?           = True
Measurement Started? = False
Stopped?             = False
Released?            = False
Cleanup Stop         = 未実行
Cleanup Release      = 未実行
Close                = 実行
```

### 9.3 Log Start失敗

期待：`Measurement Started?=False`、StopとReleaseを呼ばずCloseを実行する。

### 9.4 Log Start成功後にRead失敗

期待：

```text
Connected?           = True
Measurement Started? = True
Stopped?             = Cleanup Stop成功時True
Released?            = Cleanup Release成功時True
Close                = 実行
Final Error           = ReadのOriginal Error
```

### 9.5 通常Stop成功、Release成功

期待：Stopped?=True、Released?=True。Cleanup StopとCleanup Releaseは実行しない。

### 9.6 Connect失敗

期待：全State=False。Init以降は通常error wireでスキップし、Stop、Release、Closeを呼ばない。

### 9.7 推奨プローブ

次へプローブを置く。

```text
State After Connect
State After Start
State After Normal Stop
Cleanup Stop Succeeded?
Cleanup Release Succeeded?
Final State
Original Error
各Merge Errors出力
```
