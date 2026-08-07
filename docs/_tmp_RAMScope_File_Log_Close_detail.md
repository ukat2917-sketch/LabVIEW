<!-- ramscope-close-detail-start -->
#### 10.12.5A `RAMScope_File_Log_Close.vi`確定仕様・詳細作成手順

> 本項は直前の10.12.5概要を削除せず、[00A_LabVIEW実装資料の記述ルール.md](./00A_LabVIEW実装資料の記述ルール.md)と[00B_LabVIEW学習型VI設計ルール.md](./00B_LabVIEW学習型VI設計ルール.md)に従って、Cleanupの責務、error優先順位、関数配置、端子単位の配線および単体テストを具体化する。
>
> Nigel補足手順は採用する。特に`Clear Errors → TDMS Flush → TDMS Close`の直列構造は正しい。NI LabVIEW API Reference上、`TDMS Flush`は標準error in動作である一方、`TDMS Close`は例外的に、入力errorが既に存在していてもClose処理を実行する。そのためFlushで新たにerrorが発生しても、同じerror wireを`TDMS Close`へ接続したままCloseを試行できる。

##### 0. 実現したい機能とVIの責務

`RAMScope_File_Log_Close.vi`は、Logging PoCまたはTestStandの終了処理で、TDMS Fileが開かれている場合にFlushとCloseを試行するCleanup VIである。

前段でerrorが発生していてもCleanupを止めない。同時に、前段で最初に発生したerrorをCleanup中のerrorで上書きしない。

```text
File Open?=True
  → Original errorを保持
  → Cleanup用errorだけClear
  → TDMS Flush
  → TDMS Close
  → Original errorとCleanup結果をMerge

File Open?=False
  → TDMS関数を呼ばない
  → Original errorをそのまま返す

両ケース
  → File Open? out=False
  → 最終errorをError_To_TestStatus.viへ渡す
```

本VIはTDMS Fileを閉じる最終責務を持つため、呼出元で別途`TDMS Flush`や`TDMS Close`を重複実行しない。

##### 1. 入力データの実体

| 端子名 | 方向 | 型 | 用途 |
|---|---|---|---|
| `TDMS Ref` | 入力 | TDMS File Refnum | `RAMScope_File_Log_Open.vi`で取得したFile参照 |
| `File Open?` | 入力 | Boolean | 呼出元が保持するFile Open成功履歴 |
| `Original error` | 入力 | error cluster | Close以前に発生した最初のerrorまたは正常cluster |

`File Open?`はPoC／上位処理が`RAMScope_File_Log_Open.vi`成功後に保持する状態Booleanである。

##### 2. 出力データモデル

| 端子名 | 方向 | 型 | 用途 |
|---|---|---|---|
| `File Open? out` | 出力 | Boolean | Cleanup後状態。両CaseでFalse |
| `Status` | 出力 | `Status.ctl` | TestStand継続・異常判定 |
| `TestError` | 出力 | `TestError.ctl` | Device名、code、message等 |
| `Final error` | 出力 | error cluster | Original errorを最優先した最終結果 |

`TDMS Ref out`は設けない。Close後のRefを後段処理へ再利用させないためである。

##### 3. 前提条件・異常条件とerror優先順位

error優先順位を次で固定する。

```text
1. Original error
2. TDMS Flushで新たに発生したerror
3. TDMS Closeで新たに発生したerror
```

`Merge Errors`は上側入力から順に最初のerrorを返すため、`Original error`を最上位入力へ接続する。

| 条件 | 動作 |
|---|---|
| `File Open?=False` | TDMS Flush／Closeを呼ばず、Original errorをそのまま返す |
| `File Open?=True`、Original正常 | Flush→Closeを実行し、最初のCleanup errorがあれば返す |
| `File Open?=True`、Original errorあり | Cleanup用wireだけClearし、Flush→Closeを実行。Final errorはOriginalを優先 |
| Flush error | 同じerror wireをTDMS Closeへ接続する。TDMS Closeは入力errorがあっても実行される |
| Close error | Original errorがなければCleanup側errorとしてFinal errorへ反映する |
| 無効TDMS Refかつ`File Open?=True` | TDMS側のNI標準errorを独自`-700xxx`へ変換しない |

Cleanup用の独自ローカルerror codeは追加しない。TDMS標準errorを保持する。

##### 4. 処理アルゴリズム

```text
if File Open? == False:
    Final cleanup result = Original error
else:
    Preserved Error = Original error
    Cleanup Start Error = Clear Errors(Original error)

    Flush Error = TDMS Flush(TDMS Ref, Cleanup Start Error)
    Close Error = TDMS Close(TDMS Ref, Flush Error)

    Final cleanup result = Merge Errors(
        Original error,
        Close Error
    )

File Open? out = False

Error_To_TestStatus(
    Final cleanup result,
    Device Name="RAMScope"
)
```

`Close Error`には、Flushで発生してそのまま流れてきたerror、またはFlush正常後にCloseで発生したerrorが含まれる。したがって`Original error`と`TDMS Close error out`をMergeすれば、Original優先を保ちながらCleanup側の最初のerrorも保持できる。

##### 5. LabVIEW構造の選定理由

- `File Open?`によりCleanup実行有無を分けるため、Case Structureを使用する。
- 前段errorがあってもFlushを実行するため、Original errorから分岐したCleanup用wireだけに`Clear Errors`を適用する。
- Original errorを失わないよう、保持用wireには`Clear Errors`を入れない。
- Flush後に必ずClose試行へ進めるため、`TDMS Flush`と`TDMS Close`を同じRef／error wireで直列接続する。
- NI標準`TDMS Close`は入力errorがTrueでもClose処理を実行するため、Flush error後に再度`Clear Errors`を追加しない。
- Original errorをCleanup errorより優先するため、`Merge Errors`の上側入力へOriginal error、下側入力へ`TDMS Close error out`を接続する。
- TestStand形式への変換を1か所へ集約するため、Case Structureの外で`Error_To_TestStatus.vi`を1回だけ呼ぶ。

##### 6. フロントパネル入出力と接続元・接続先

| 本VI端子 | 接続元 | 接続先 |
|---|---|---|
| `TDMS Ref` | Logging PoCで保持しているFile Ref | True CaseのTDMS Flush |
| `File Open?` | `RAMScope_Logging_PoC_State.ctl / File Open?`等 | Case selector |
| `Original error` | 通常処理またはCleanup途中までのMain Error | False Case通過、True Case保持用／Cleanup用分岐 |
| `File Open? out` | 両CaseでBoolean False | PoC State更新または最終表示 |
| `Status` | `Error_To_TestStatus.vi / Status` | 呼出元 |
| `TestError` | `Error_To_TestStatus.vi / TestError` | 呼出元 |
| `Final error` | `Error_To_TestStatus.vi / error out` | 呼出元最終error |

##### 7. 配置する関数およびSubVI

| 数 | 日本語名 | 英語名 | 用途 |
|---:|---|---|---|
| 1 | ケースストラクチャ | Case Structure | `File Open?`でCleanup要否を分岐 |
| 1 | エラーをクリア | Clear Errors | Cleanup用wireからOriginal errorを一時除去 |
| 1 | TDMSフラッシュ | TDMS Flush | 未書込BufferをFileへ反映 |
| 1 | TDMSを閉じる | TDMS Close | File RefをClose |
| 1 | エラーをマージ | Merge Errors | Original errorとCleanup側errorを優先順位付きで統合 |
| 1 | `Error_To_TestStatus.vi` | SubVI | 最終Status/TestError生成 |
| 2 | Boolean定数False | Boolean Constant | 両Caseの`File Open? out` |
| 1 | String定数`RAMScope` | String Constant | `Error_To_TestStatus.vi / Device Name` |

##### 8. 配線順

###### A. フロントパネル端子を作成する

1. `TDMS Ref`をTDMS File Refnum入力として作る。
2. Boolean入力`File Open?`を作る。
3. error cluster入力`Original error`を作る。
4. Boolean出力`File Open? out`を作る。
5. `Status.ctl`出力`Status`を作る。
6. `TestError.ctl`出力`TestError`を作る。
7. error cluster出力`Final error`を作る。

###### B. `File Open?` Case Structureを先に配置する

1. Case Structureを配置する。
2. `File Open?`をselector端子へ接続する。
3. `False`ケースと`True`ケースが存在することを確認する。
4. `Original error`をCase左枠へ入れるトンネルを作る。
5. Final cleanup error用と`File Open? out`用の右側トンネルを作る。
6. `Use default if unwired`を使用しない。

###### C. Falseケース（`File Open?=False`：Cleanup不要）

1. `Original error`をFinal cleanup error出力トンネルへ直接接続する。
2. Boolean False定数を`File Open? out`出力トンネルへ接続する。
3. `TDMS Ref`はこのCase内で使用しない。
4. TDMS Flush、TDMS Close、Clear Errors、Merge Errorsを配置しない。

###### D. Trueケース（`File Open?=True`：Cleanup実行）

1. `Original error`を2方向へ分岐する。
2. 1本目を`Merge Errors`の上側1個目のerror入力へ接続する。
3. 2本目を`Clear Errors / error in`へ接続する。
4. `specific error code to clear`は未配線とし、既定値0で全errorをClearする。
5. `Clear Errors / error out`を`TDMS Flush / error in`へ接続する。
6. `TDMS Ref`を`TDMS Flush / tdms file`へ接続する。
7. `TDMS Flush / tdms file out`を`TDMS Close / tdms file`へ接続する。
8. `TDMS Flush / error out`を`TDMS Close / error in`へ接続する。
9. `TDMS Close / error out`を`Merge Errors`の下側2個目のerror入力へ接続する。
10. `Merge Errors / error out`をFinal cleanup error出力トンネルへ接続する。
11. Boolean False定数を`File Open? out`出力トンネルへ接続する。

重要：`TDMS Flush / error out`と`TDMS Close / error in`の間へ`Clear Errors`を追加しない。`TDMS Close`はNI仕様上、error inがTrueでも実行される。

```text
Original error ───────────────→ Merge Errors 上側入力1
       │
       └→ Clear Errors
              ↓
TDMS Ref → TDMS Flush
              │ tdms file out
              │ error out
              ↓
          TDMS Close
              │ error out
              ↓
          Merge Errors 下側入力2
              ↓
        Final cleanup error

False定数 → File Open? out
```

###### E. Case Structure外で`Error_To_TestStatus.vi`へ接続する

1. Case StructureのFinal cleanup errorを`Error_To_TestStatus.vi / error in`へ接続する。
2. String定数`RAMScope`を`Device Name`へ接続する。
3. `Status`、`TestError`、`error out`を本VIの対応出力へ接続する。
4. Case Structureの`File Open? out`を本VIの同名出力へ接続する。
5. `Error_To_TestStatus.vi`は最後に1回だけ呼ぶ。

##### 9. Cleanup時のerror解釈

```text
Original errorあり + Cleanup正常
  → Final = Original error

Original正常 + Flush error
  → TDMS Closeも実行
  → Final = Flush側の最初のCleanup error

Original正常 + Flush正常 + Close error
  → Final = Close error

Original errorあり + Cleanup errorあり
  → Final = Original error
```

##### 10. 単体テスト

| No. | 条件 | 期待結果 |
|---:|---|---|
| 1 | `File Open?=False`, Original正常 | TDMS未実行、Final正常、File Open? out=False |
| 2 | `File Open?=False`, Original error | TDMS未実行、Original code/source保持 |
| 3 | `File Open?=True`, Original正常、正常Ref | Flush→Close実行、Final正常 |
| 4 | `File Open?=True`, Original error、正常Ref | Flush→Closeを実行しつつFinalはOriginal保持 |
| 5 | `File Open?=True`, 無効Ref | NI標準TDMS errorをFinalへ反映 |
| 6 | Flush error | TDMS Closeまで到達することをHighlight Execution／Probeで確認 |
| 7 | Close error | Original正常ならClose errorをFinalへ反映 |
| 8 | Original errorとCleanup error両方 | Originalを優先 |
| 9 | Close済み後に`File Open?=False`で再呼出し | TDMSを再実行しない |
| 10 | 配線監査 | Flush→Close間にClear Errorsなし |
| 11 | 最終Status | `Error_To_TestStatus.vi`を1回だけ経由、Device Name=`RAMScope` |

推奨プローブ位置：`Original error`、`File Open?`、`Clear Errors error out`、`TDMS Flush error out`、`TDMS Close error out`、`Merge Errors error out`、`File Open? out`、`Final error`。

##### 11. 完成チェックリスト

- [ ] `File Open?` Case Structureを実処理より先に配置。
- [ ] FalseケースでTDMS関数を呼ばない。
- [ ] TrueケースでOriginal errorを保持用／Cleanup用へ分岐。
- [ ] `Clear Errors`はCleanup用wireだけ。
- [ ] `TDMS Ref → TDMS Flush → TDMS Close`を直列接続。
- [ ] `Clear Errors → TDMS Flush → TDMS Close`をerror wireで直列接続。
- [ ] Flush→Close間でerrorを再Clearしない。
- [ ] `Merge Errors`上側へOriginal、下側へTDMS Close error out。
- [ ] 両Caseで`File Open? out=False`を明示配線。
- [ ] `TDMS Ref out`を追加しない。
- [ ] Cleanup側TDMS errorを独自`-700xxx`へ変換しない。
- [ ] `Error_To_TestStatus.vi`をCase外で1回だけ呼ぶ。
- [ ] `Use default if unwired`に依存しない。
- [ ] 正常Close、前段error付きClose、無効Ref、二重Close、Flush error、Close errorをテスト。
<!-- ramscope-close-detail-end -->
