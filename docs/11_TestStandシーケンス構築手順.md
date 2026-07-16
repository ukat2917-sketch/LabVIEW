# 11. TestStand シーケンス構築手順

> **本章の役割**：LabVIEW単体で確認済みの公開API VIを、TestStandのSetup / Main / Cleanupへ組み込む。
>
> RAMScopeは[10](./10_RAMScope実装方針.md)の`PoC_RAMScope_Main.vi`完了後に組み込む。操作手順は[00A](./00A_LabVIEW実装資料の記述ルール.md)に従い、操作場所、選択項目、変数名、期待結果を省略しない。

---

## 11.1 なぜTestStand組み込みを最後に行うのか

LabVIEW VIとTestStand設定を同時に作ると、失敗原因がVI、Adapter、変数マッピング、シーケンス条件のどこにあるか切り分けにくい。次の順で確認する。

```text
下位SubVI単体
  → 公開API単体
  → LabVIEWだけのPoC
  → TestStandから公開APIを1個呼ぶ
  → Setup / Main / Cleanupへ展開
```

## 11.2 TestStand着手条件

- [ ] RAMScope RAM計測単体PoCが完走する
- [ ] 既知RAM変数と解析値が一致する
- [ ] Start / Read / Stop / Closeを繰り返せる
- [ ] 公開APIのコネクタペインが固定されている
- [ ] Status / TestError / error clusterの仕様が固定されている
- [ ] CANを使用する場合は採用方式の単体PoCが完了している

TestStandは`RS_DLL_*`、Builder、Parserを直接呼ばず、`30_Public`の公開APIだけを呼ぶ。

---

## 11.3 TestStand基本構造

| 要素 | 役割 |
|---|---|
| Sequence File | 複数Sequenceを格納する`.seq`ファイル |
| Sequence | ステップの集合。`MainSequence`が起点 |
| Setup | 機器接続、初期化、試験前設定 |
| Main | 試験イベント、待ち、分岐、繰り返し |
| Cleanup | 正常・異常に関係なく行う安全停止と終了 |
| Variables | 条件、状態、取得値、ファイルパス、結果を保持 |

---

## 11.4 LabVIEW Adapterの設定

### 0. 目的

TestStandがどのLabVIEW実行環境でVIを呼ぶかを固定する。

### 1. 操作手順

1. TestStand Sequence Editorを開く。
2. メニューから`Configure → Adapters`を開く。
3. Adapter一覧から`LabVIEW`を選択する。
4. 開発PCでは`Development System`を選択する。
5. 試験用PCでは配布方式に応じて`Run-Time Engine`を選択する。
6. LabVIEW、Run-Time Engine、TestStandプロセス、RAMScope DLLが64bit構成であることを確認する。
7. 設定画面を閉じ、Sequence Editorを再起動する必要がある場合は再起動する。

### 2. 確認

- 64bit LabVIEWで保存した単純な加算VIをActionステップから呼べる。
- Adapterエラーが発生しない。
- 別bit数のVIまたはDLLを混在させていない。

---

## 11.5 1個の公開APIを呼ぶ手順

### 0. 目的

最初に`RAMScope_Connect.vi`等の1個だけを呼び、Adapterと端子マッピングを確認する。

### 1. 配置するステップ

| 項目 | 設定 |
|---|---|
| Step Type | Action |
| Adapter | LabVIEW |
| Module | `30_RAMScope\30_Public\RAMScope_Connect.vi`等 |
| Step Name | 公開API名と一致させる |

### 2. 操作手順

1. 対象のStep Groupを選択する。
2. `Insert Step → Action`を追加する。
3. 追加したステップを選択する。
4. Adapterを`LabVIEW`へ変更する。
5. `Specify Module`を開く。
6. 対象公開API VIを選択する。
7. 表示されたVI端子とTestStand変数をマッピングする。
8. `error out`、Status、TestError、主要出力を結果変数へ割り当てる。
9. Module画面を閉じ、ステップを保存する。
10. ステップ単体を実行し、値とエラーを確認する。

### 3. 一般的なマッピング

| VI端子 | TestStand変数例 |
|---|---|
| 試験条件 | `Parameters.*`または`FileGlobals.*` |
| VISAリファレンス | `FileGlobals.<Device>_Ref` |
| Status | `Locals.Status` |
| TestError | `Locals.TestError` |
| error out | `Locals.LabVIEWError`またはStep Result |
| 計測値 | `Locals.*`または`FileGlobals.*` |

### 4. 単体確認

- VIの入力値がTestStandから変更できる。
- VIの出力がTestStand変数へ反映される。
- error outのstatus、code、sourceを確認できる。
- StatusとTestErrorをレポート対象へ追加できる。

---

## 11.6 RAMScope変数

RAMScopeVP APIはSessionハンドルを返さないため、RAMScopeリファレンスをFileGlobalsへ保持しない。

| 変数 | TestStand型 | 用途 | 設定元 |
|---|---|---|---|
| `FileGlobals.RAMScope.UnitNum` | Number | 接続台数 | Connect出力 |
| `FileGlobals.RAMScope.Kind` | Number | 機種コード | Connect出力 |
| `FileGlobals.RAMScope.UnitNo` | Number | 使用Unit番号 | 条件。初期構成では0 |
| `FileGlobals.RAMScope.MdlNo_RAM` | Number | RAMモジュール番号 | Init出力 |
| `FileGlobals.RAMScope.MdlNo_CAN` | Number | CANモジュール番号 | Init出力 |
| `FileGlobals.RAMScope.Endian_RAM` | Number | Parser用Endian | Init出力 |
| `FileGlobals.RAMScope.ChannelCount` | Number | 設定チャンネル数 | Set_Cond出力 |
| `FileGlobals.RAMScope.IsMeasuring` | Boolean | Cleanup判定 | Start/Stop成功時 |
| `FileGlobals.RAMScope.IsConnected` | Boolean | Cleanup判定 | Connect/Close成功時 |
| `Locals.RAMScope.Packets` | Array/Container | 解析済みパケット | Read出力 |
| `Locals.RAMScope.LostDataNum` | Number | 取りこぼし監視 | Read出力 |
| `Locals.RAMScope.ApiStatus` | Container | Status.ctl相当 | 各公開API |
| `Locals.RAMScope.TestError` | Container | TestError.ctl相当 | 各公開API |

`RAMScope_Context.ctl`は使用しない。必要な値を個別に保持する。

---

## 11.7 Setupの作成

### 0. 目的

Main開始前に、RAMScopeを接続・初期化し、測定条件を設定する。

### 1. ステップ順

```text
RAMScope_Connect.vi
  → RAMScope_Init.vi
  → RAMScope_Set_Cond.vi
```

### 2. `RAMScope_Connect.vi`

1. SetupへActionステップを追加する。
2. Moduleへ`RAMScope_Connect.vi`を指定する。
3. UnitNum出力を`FileGlobals.RAMScope.UnitNum`へ割り当てる。
4. kind出力を`FileGlobals.RAMScope.Kind`へ割り当てる。
5. Status、TestError、error outをLocalsへ割り当てる。
6. 成功条件で`FileGlobals.RAMScope.IsConnected=True`を設定する。
7. Error時は後続Setupを実行せずCleanupへ遷移する。

### 3. `RAMScope_Init.vi`

1. UnitNo入力へ`FileGlobals.RAMScope.UnitNo`を割り当てる。
2. Byte Orderへ初期解析用設定を割り当てる。
3. MdlNo_RAM、MdlNo_CAN、Endian_RAM出力を各FileGlobalsへ割り当てる。
4. Module ListとSlotErrを結果へ保存する。
5. `RAM Module Found?=False`またはStatus=ErrorでSetupを中断する。

### 4. `RAMScope_Set_Cond.vi`

1. UnitNoとMdlNo_RAMをFileGlobalsから入力する。
2. Meas Config、Channel List、Module Log Configsを条件ファイルまたはFileGlobalsから入力する。
3. ChNum出力を`FileGlobals.RAMScope.ChannelCount`へ割り当てる。
4. Status=OKを確認してMainへ進む。

### 5. Setup単体テスト

- Connectだけを実行する。
- Connect → Initまでを実行する。
- Connect → Init → Set_Condを実行する。
- 各段階でFileGlobals値を確認する。
- Init失敗時にSet_Condが呼ばれないことを確認する。

---

## 11.8 Mainの作成

### 0. 目的

計測開始後、試験イベントと読出しを実行し、最後に計測停止する。

### 1. 基本順序

```text
RAMScope_Log_Start.vi
  → 試験イベント
  → Read Loop
       RAMScope_Read.vi
       ログ・判定
       Wait
  → RAMScope_Log_Stop.vi
```

### 2. Start

1. UnitNoをFileGlobalsから入力する。
2. Start成功時だけ`IsMeasuring=True`へ変更する。
3. Error時はRead Loopへ入らずCleanupへ遷移する。

### 3. Read Loop

1. LoopまたはWhile相当のステップを配置する。
2. 反復条件、最大回数、Timeoutを試験条件として定義する。
3. ReadステップへUnitNo、MdlNo_RAM、MaxDataNum、Channel List、Endianを入力する。
4. Packets、DataNum、LostDataNumをLocalsへ保存する。
5. LostDataNumが0より大きい場合のWarning/Error基準を試験仕様で定義する。
6. Waitステップへポーリング周期を入力する。
7. Read Status=ErrorでLoopを終了しCleanupへ遷移する。

### 4. Stop

1. UnitNoを入力する。
2. Stop成功時に`IsMeasuring=False`へ変更する。
3. Stop失敗時もCleanupで再試行できるよう、状態とエラーを記録する。

### 5. Main単体テスト

- Start → 1回Read → Stopを実行する。
- Read Loop回数を2、10へ変更する。
- DataNum=0を正常として扱えることを確認する。
- LostDataNumをレポートへ保存できることを確認する。
- Read失敗時に後続試験イベントを停止できることを確認する。

---

## 11.9 ReleaseBufferDataの扱い

`RAMScope_Release.vi`は必須性と呼出位置が確定するまで標準Mainフローへ固定しない。

```text
候補A: 各Read後
候補B: Stop後
候補C: 使用しない
```

A/B/Cの比較では、長時間取得、再計測、メモリ使用量、ReturnCode、データ欠損を同じ条件で記録する。

---

## 11.10 Cleanupの作成

### 0. 目的

Mainの成功・失敗に関係なく、計測停止とDeviceExitを実行する。

### 1. RAMScope Cleanup順

```text
If FileGlobals.RAMScope.IsMeasuring:
    RAMScope_Log_Stop.vi

RAMScope_Release.vi（採用が確定した場合のみ）
RAMScope_Close.vi
```

### 2. 配置手順

1. Cleanup Step GroupへIfステップを追加する。
2. 条件へ`FileGlobals.RAMScope.IsMeasuring`を設定する。
3. True側へ`RAMScope_Log_Stop.vi`を配置する。
4. Stop成功時にIsMeasuring=Falseへ変更する。
5. Release採用時だけReleaseステップを配置する。
6. 条件分岐の外側へ`RAMScope_Close.vi`を配置する。
7. Close成功時にIsConnected=Falseへ変更する。
8. StopまたはReleaseが失敗してもCloseを実行するよう、ステップのエラー動作を設定する。
9. Cleanup中エラーを元エラーとは別に記録する。

### 3. Cleanup単体テスト

- Main正常終了後にStop/Closeが実行される。
- Main途中エラーでもStop/Closeが実行される。
- IsMeasuring=FalseではStopを飛ばしてCloseする。
- Close失敗時も後続機器のCleanupが続行される。

---

## 11.11 試験条件の管理

| 条件 | 推奨格納先 |
|---|---|
| 電圧・電流条件 | Parameters / FileGlobals |
| 制御モード | Parameters / FileGlobals |
| Ramp時間 | Parameters / FileGlobals |
| RAMScope測定周期 | Parameters / FileGlobals |
| Channel List | Property Loader / FileGlobals |
| 最大取得パケット数 | Parameters / FileGlobals |
| ポーリング周期 | Parameters / FileGlobals |
| Timeout | Parameters / FileGlobals |

CSV、Excel、Property Loader等から読み込み、シーケンスを変更せず条件を差し替えられるようにする。外部ファイルの列名、型、単位、既定値、範囲外時の扱いを資料へ記載する。

---

## 11.12 同期・非同期・待ち・分岐

| 目的 | TestStandの手段 | 記載する内容 |
|---|---|---|
| 順序を守る | ステップを直列配置 | 前後条件、エラー時遷移 |
| 待ち時間 | Waitステップ | 単位、入力変数、Timeout |
| 条件分岐 | If / Else / Precondition | Boolean式と各分岐の処理 |
| 繰り返し | Loop / For / While | 回数、終了条件、上限時間 |
| 並行実行 | Sequence CallをNew Thread | Thread参照、共有資源、合流方法 |
| 合流 | Wait for Thread / Sequence | Timeout、Thread側エラー取得 |

RAMScopeVP APIのスレッドセーフ性は未確認のため、RAMScope公開APIを複数Threadから同時実行しない。

---

## 11.13 CANとの組み合わせ

CANは[09](./09_CAN通信の実装.md)で方式を確定し、単体PoC済み公開APIを配置する。

```text
MainSequence
  ├─ RAMScope_Log_Start.vi
  ├─ CAN送受信イベント
  ├─ RAMScope_Read.vi
  └─ RAMScope_Log_Stop.vi
```

RAMScope CANを採用する場合も、CAN薄いDLLラッパをTestStandから直接呼ばない。

---

## 11.14 サブシーケンス

```text
MainSequence
  ├─ SubSeq_Startup
  ├─ SubSeq_MeasurementSetup
  ├─ SubSeq_LoadScenario
  ├─ SubSeq_CANModeTransition
  ├─ SubSeq_DataCollection
  └─ SubSeq_StopAndSave
```

各サブシーケンスについて、Parameters、Locals、戻り値、呼出条件、Cleanup責務を表で記載する。

---

## 11.15 結果・レポート

最低限、次を保存する。

- 試験IDと試験条件
- 各ステップのStatus
- `TestError.ctl`
- 標準error cluster
- RAMScope API ReturnCode（PoC中または異常時）
- UnitNum、kind、MdlNo
- DataNum、LostDataNum、Timestamp
- ReleaseBufferDataの使用有無
- 保存ファイルのパス
- Cleanup結果

---

## 11.16 エラー時の遷移

1. 公開APIがErrorを返したらMain後続を中断する。
2. 元エラーをLocalsまたはResultへ保存する。
3. Cleanupへ遷移する。
4. [12](./12_異常系処理とシャットダウン設計.md)の安全順序で停止する。
5. Cleanupエラーで元エラーを上書きしない。
6. 元エラーとCleanup結果をレポートへ残す。

---

## 11.17 完了条件

- [ ] RAMScope単体PoCが完了
- [ ] CAN使用時は採用方式の単体PoCが完了
- [ ] Setup / Main / Cleanupが本章どおり
- [ ] `RS_DLL_*`やParserを直接呼んでいない
- [ ] 全公開APIのerror in/outがマッピング済み
- [ ] StatusとTestErrorを記録できる
- [ ] MdlNo等を後段へ渡せる
- [ ] Read周期をTestStandから変更できる
- [ ] CleanupでCloseまで必ず実行できる
- [ ] 各手順に操作場所、変数名、期待結果が記載されている
