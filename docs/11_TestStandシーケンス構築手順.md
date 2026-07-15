# 11. TestStand シーケンス構築手順

> **本章の役割**：LabVIEW単体で確認済みの公開API VIをTestStandのSetup / Main / Cleanupへ組み込む。
>
> RAMScopeは[10](./10_RAMScope実装方針.md)の`PoC_RAMScope_Main.vi`完了後に組み込む。
> CANを使用する場合は、採用CAN方式の単体PoCも完了してから着手する。

---

## 11.1 TestStand着手条件

- [ ] RAMScope RAM計測単体PoCが完走する
- [ ] 既知RAM変数と解析値が一致する
- [ ] Start / Read / Stop / Closeを繰り返せる
- [ ] 公開APIのコネクタペインが固定されている
- [ ] Status / TestError / error clusterの仕様が固定されている
- [ ] CANを使用する場合は採用方式の単体PoCが完了している

TestStandは`RS_DLL_*`薄いDLLラッパや`20_Data_Conversion`内のVIを直接呼ばず、`30_Public`の`RAMScope_*`公開APIを呼ぶ。

---

## 11.2 基本構造

| 要素 | 役割 |
|---|---|
| Sequence File | 複数Sequenceを格納する`.seq`ファイル |
| Sequence | ステップの集合。`MainSequence`が起点 |
| Setup | 機器接続、初期化、試験前設定 |
| Main | 試験イベント、待ち、分岐、繰り返し |
| Cleanup | 正常・異常に関係なく実行する安全停止と終了 |
| Variables | 条件、状態、取得値、ファイルパス、結果を保持 |

---

## 11.3 LabVIEW Adapter

1. `Configure → Adapters`を開く。
2. LabVIEW Adapterを選択する。
3. 開発時はDevelopment System、配布時はRun-Time Engineを選ぶ。
4. LabVIEW、Run-Time Engine、呼び出すVIのbit数を揃える。
5. RAMScopeを使用するため64bit構成を使用する。

---

## 11.4 VI呼び出しステップ

1. 対象Step Groupで`Insert Step → Action`を追加する。
2. AdapterをLabVIEWにする。
3. `Specify Module`で`RAMScope_*`公開APIを選択する。
4. VIのコネクタペインとTestStand変数をマッピングする。
5. `error out`、`Status.ctl`、`TestError.ctl`を結果へ関連付ける。
6. Statusまたはerror clusterを用いてPass / Warning / Errorを判定する。

### 一般的なマッピング

| VI端子 | TestStand変数例 |
|---|---|
| 試験条件 | `Parameters.*`または`FileGlobals.*` |
| VISAリファレンス | `FileGlobals.<Device>_Ref` |
| Status | `Locals.Status` |
| TestError | `Locals.TestError` |
| error out | Step ResultまたはLocals |
| 計測値 | `Locals`またはFileGlobals |

---

## 11.5 RAMScopeの変数

RAMScopeVP APIはSessionハンドルを返さないため、RAMScopeリファレンスをFileGlobalsへ保持しない。

| 変数 | 型 | 用途 |
|---|---|---|
| `FileGlobals.RAMScope.UnitNum` | Number / I32相当 | 接続台数 |
| `FileGlobals.RAMScope.Kind` | Number / I32相当 | 機種コード |
| `FileGlobals.RAMScope.UnitNo` | Number / I32相当 | 初期構成では0 |
| `FileGlobals.RAMScope.MdlNo_RAM` | Number / I32相当 | RAMモジュール番号 |
| `FileGlobals.RAMScope.MdlNo_CAN` | Number / I32相当 | CANモジュール番号 |
| `FileGlobals.RAMScope.Endian_RAM` | Number / I32相当 | Parser用 |
| `FileGlobals.RAMScope.ChannelCount` | Number | 設定チャンネル数 |
| `FileGlobals.RAMScope.IsMeasuring` | Boolean | Cleanup判定 |
| `FileGlobals.RAMScope.IsConnected` | Boolean | Cleanup判定 |
| `Locals.RAMScope.Packets` | Array | 解析済みパケット |
| `Locals.RAMScope.LostDataNum` | Number | 取りこぼし監視 |

`RAMScope_Context.ctl`は使用しない。必要な値をTestStand変数へ個別に保持する。

---

## 11.6 RAMScopeの配置

### Setup

```text
RAMScope_Connect.vi
  → RAMScope_Init.vi
  → RAMScope_Set_Cond.vi
```

- Connect成功時に`UnitNum`と`kind`を保存する。
- InitでAllInit、GetSysInfo、SYSINFO解析、PGT設定を行う。
- Init出力の`MdlNo_RAM`、`MdlNo_CAN`、`Endian_RAM`を保存する。
- Set_Condへ測定周期、Channel List、ログ条件を渡す。
- `RAMScope_Config.vi`は使用しない。

### Main

```text
RAMScope_Log_Start.vi
  → Wait / 他の試験イベント
  → Loop:
       RAMScope_Read.vi
       ログ・判定
       Wait
  → RAMScope_Log_Stop.vi
```

- `RAMScope_Read.vi`はGetBufferDataとBuffer Parserを内部で行う。
- Start成功後に`IsMeasuring=True`。
- Stop成功後に`IsMeasuring=False`。
- Read周期はTestStandのWaitまたはLoopで管理する。
- `LostDataNum > 0`のWarning/Error基準を試験仕様で決める。

### ReleaseBufferData

`RAMScope_Release.vi`は必須性と位置が確定するまで標準Mainフローへ固定しない。

```text
候補A: Read後
候補B: Stop後
候補C: 使用しない
```

### Cleanup

```text
If RAMScope.IsMeasuring:
    RAMScope_Log_Stop.vi

RAMScope_Release.vi（採用が確定した場合のみ）
RAMScope_Close.vi
```

`RAMScope_Close.vi`は前段エラーがあっても実行する。

---

## 11.7 API ReturnCode

```text
DLLラッパ内
  API ReturnCode + CLFN error out
    → RAMScope_Code_To_Error.vi
    → error out

公開API末尾
  error out
    → Error_To_TestStatus.vi
    → Status / TestError / TestStand
```

TestStandでは公開APIの標準error clusterとStatusを使用する。PoC中または異常解析時はAPI ReturnCodeも結果へ記録する。

---

## 11.8 試験条件

| 条件 | 推奨格納先 |
|---|---|
| 電圧・電流条件 | Parameters / FileGlobals |
| 制御モード | Parameters / FileGlobals |
| Ramp時間 | Parameters / FileGlobals |
| RAMScope測定周期 | Parameters / FileGlobals |
| `RAMScope_Channel.ctl`配列 | Property Loader / FileGlobals |
| 最大取得パケット数 | Parameters / FileGlobals |
| ポーリング周期 | Parameters / FileGlobals |

CSV、Excel、Property Loader等から読み込み、シーケンスを変更せず条件を差し替えられるようにする。

---

## 11.9 同期・非同期・待ち・分岐

| 目的 | TestStandの手段 |
|---|---|
| 順序を守る | ステップを直列配置 |
| 待ち時間 | Waitステップ |
| 条件分岐 | If / Else / Precondition |
| 繰り返し | Loop / For / While |
| 並行実行 | Sequence CallをNew Threadで起動 |
| 合流 | Wait for Thread / Sequence |

RAMScopeVP APIのスレッドセーフ性は未確認のため、RAMScope公開APIを複数スレッドから同時実行しない。

---

## 11.10 CANとの組み合わせ

CANは[09](./09_CAN通信の実装.md)で方式を確定し、単体PoC済み公開APIを配置する。

```text
MainSequence
  ├─ RAMScope_Log_Start.vi
  ├─ CAN送受信イベント
  ├─ RAMScope_Read.vi
  └─ RAMScope_Log_Stop.vi
```

RAMScope CANを採用する場合もCAN薄いDLLラッパをTestStandから直接呼ばない。

---

## 11.11 サブシーケンス

```text
MainSequence
  ├─ SubSeq_Startup
  ├─ SubSeq_MeasurementSetup
  ├─ SubSeq_LoadScenario
  ├─ SubSeq_CANModeTransition
  ├─ SubSeq_DataCollection
  └─ SubSeq_StopAndSave
```

Connect / Init / Set_CondはSetupまたはMeasurementSetupへ置く。CloseはCleanupへ固定する。

---

## 11.12 結果・レポート

- 試験IDと試験条件
- 各ステップのStatus
- `TestError.ctl`
- RAMScope API ReturnCode（PoC中または異常時）
- UnitNum、kind、MdlNo
- DataNum、LostDataNum、Timestamp
- ReleaseBufferDataの使用有無
- 保存ファイルのパス
- Cleanup結果

---

## 11.13 エラー時の遷移

1. 公開APIがErrorを返したらMain後続を中断する。
2. Cleanupへ遷移する。
3. [12](./12_異常系処理とシャットダウン設計.md)の安全順序で停止する。
4. Cleanupエラーで元エラーを上書きしない。
5. 元エラーとCleanup結果をレポートへ残す。

---

## 11.14 完了条件

- [ ] RAMScope単体PoCが完了
- [ ] CAN使用時は採用方式の単体PoCが完了
- [ ] Setup / Main / Cleanupが本章どおり
- [ ] `RS_DLL_*`やParserを直接呼んでいない
- [ ] 全公開APIのerror in/outがマッピング済み
- [ ] StatusとTestErrorを記録できる
- [ ] MdlNo等を後段へ渡せる
- [ ] Read周期をTestStandから変更できる
- [ ] CleanupでCloseまで必ず実行できる
