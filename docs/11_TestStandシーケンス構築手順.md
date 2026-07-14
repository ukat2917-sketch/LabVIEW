# 11. TestStand シーケンス構築手順

> **本章の役割**：LabVIEW単体で確認済みのVIをTestStandのSetup / Main / Cleanupへ組み込む。
> RAMScope VIは [10B](./10B_RAMScope_VI作成手順_STEP3_STEP4詳細.md) のFlow Test完了後に組み込む。

## 11.1 基本構造

| 要素 | 役割 |
|------|------|
| Sequence File | 複数のSequenceを格納する`.seq`ファイル |
| Sequence | ステップの集合。`MainSequence`が起点 |
| Setup | 機器接続、初期化、試験前設定 |
| Main | 試験イベント、待ち、分岐、繰り返し |
| Cleanup | 正常・異常に関係なく実行する安全停止と終了処理 |
| Variables | 条件、状態、取得値、ファイルパス、結果を保持 |

## 11.2 LabVIEW Adapter

1. `Configure → Adapters`を開く。
2. LabVIEW Adapterを選択する。
3. 開発時はDevelopment System、配布時はRun-Time Engineを選ぶ。
4. LabVIEW、Run-Time Engine、呼び出すVIのbit数を揃える。
5. RAMScopeを使用するため、64bit構成を使用する。

## 11.3 VI呼び出しステップ

1. 対象Step Groupで`Insert Step → Action`を追加する。
2. AdapterをLabVIEWにする。
3. `Specify Module`でVIを選択する。
4. VIのコネクタペインとTestStand変数をマッピングする。
5. `error out`、`Status.ctl`、`TestError.ctl`を結果へ関連付ける。
6. Statusまたはerror clusterを用いてPass / Warning / Errorを判定する。

### 一般的なマッピング

| VI端子 | TestStand変数例 |
|--------|-----------------|
| 試験条件 | `Parameters.*`または`FileGlobals.*` |
| VISAリファレンス | `FileGlobals.<Device>_Ref` |
| 実行結果ステータス | `Locals.Status` |
| エラー情報 | `Locals.TestError` |
| error out | Step ResultまたはLocalsのerror cluster |
| 計測値 | `Locals`またはFileGlobals |

## 11.4 RAMScopeの変数

RAMScopeVP APIはセッションハンドルを返さないため、RAMScopeリファレンスをFileGlobalsへ保持しない。

推奨変数：

| 変数 | 型 | 用途 |
|------|----|------|
| `FileGlobals.RAMScope.UnitNum` | Number / I32相当 | 接続台数 |
| `FileGlobals.RAMScope.Kind` | Number / I32相当 | 機種コード。GT170は2 |
| `FileGlobals.RAMScope.MdlNo_RAM` | Number / I32相当 | RAMモジュール番号 |
| `FileGlobals.RAMScope.MdlNo_CAN` | Number / I32相当 | CANモジュール番号 |
| `FileGlobals.RAMScope.Endian_RAM` | Number / I32相当 | パケット解析用 |
| `FileGlobals.RAMScope.ChannelCount` | Number | 設定チャンネル数 |
| `FileGlobals.RAMScope.IsMeasuring` | Boolean | Cleanup判定用 |
| `Locals.RAMScope.RawBytes` | Array | 取得バイト列 |
| `Locals.RAMScope.Values` | Array | 解析済みRAM値 |
| `Locals.RAMScope.LostDataNum` | Number | 取りこぼし監視 |

## 11.5 RAMScopeの配置

### Setup

```text
RAMScope_Connect.vi
  → RAMScope_Init.vi
  → RAMScope_Config.vi
  → RAMScope_Set_Cond.vi
```

- Connect成功時は`UnitNum`と`kind`を保存する。
- Initで`MdlNo_RAM`、`MdlNo_CAN`、`Endian_RAM`を保存する。
- Configで`SlotErr[MdlNo_RAM]`が正常であることを確認する。
- Set_Condへ測定周期、チャンネル一覧、ログ条件を渡す。

### Main

```text
RAMScope_Log_Start.vi
  → Wait / 他の試験イベント
  → Loop:
       RAMScope_Read.vi
       RAMScope_Parse_Buffer.vi
       ログ・判定
  → RAMScope_Log_Stop.vi
  → RAMScope_Release.vi（要否は実機検証中）
```

- Start成功後に`IsMeasuring=True`。
- Stop成功後に`IsMeasuring=False`。
- `Read.vi`の呼び出し周期はTestStandのWaitまたはLoop設定で管理する。
- `LostDataNum > 0`をWarningまたはErrorとして扱う基準を試験仕様で決める。

### Cleanup

```text
If RAMScope.IsMeasuring:
    RAMScope_Log_Stop.vi

RAMScope_Release.vi（採用する場合）
RAMScope_Close.vi
```

`RAMScope_Close.vi`は前段エラーがあっても実行する。元エラーを保持しつつ、DeviceExitエラーも記録する。

## 11.6 API ReturnCodeの扱い

CLFNの`error out`とRAMScope API ReturnCodeは別物である。

```text
ReturnCode
  → RAMScope_Code_To_Error.vi
  → Error_To_TestStatus.vi
  → TestStand
```

TestStandではVIから返された標準error clusterとStatusを使用する。PoC中はAPI ReturnCodeも追加結果として記録すると切り分けしやすい。

## 11.7 試験条件

試験条件をVIへハードコードしない。

| 条件 | 推奨格納先 |
|------|------------|
| 電圧・電流条件 | Parameters / FileGlobals |
| 制御モード | Parameters / FileGlobals |
| Ramp時間 | Parameters / FileGlobals |
| RAMScope測定周期 | Parameters / FileGlobals |
| RAMアドレス一覧 | Property Loader / FileGlobals配列 |
| RAMデータ型・符号 | チャンネル条件クラスタ |
| 最大取得パケット数 | Parameters / FileGlobals |
| ポーリング周期 | Parameters / FileGlobals |

CSV、Excel、Property Loader等から読み込み、シーケンスを変更せず条件を差し替えられるようにする。

## 11.8 同期・非同期・待ち・分岐

| 目的 | TestStandの手段 |
|------|-----------------|
| 順序を守る | ステップを直列配置 |
| 待ち時間 | Waitステップ |
| 条件分岐 | If / Else / Precondition |
| 繰り返し | Loop / For / While |
| 別処理を並行実行 | Sequence CallをNew Threadで起動 |
| 非同期処理の合流 | Wait for Thread / Sequence |

RAMScopeVP APIのスレッドセーフ性は未確認であるため、RAMScopeのCLFN呼び出しを複数スレッドから同時実行しない。

## 11.9 サブシーケンス

イベントのまとまりをサブシーケンス化する。

```text
MainSequence
  ├─ SubSeq_Startup
  ├─ SubSeq_MeasurementSetup
  ├─ SubSeq_LoadScenario
  ├─ SubSeq_CANModeTransition
  ├─ SubSeq_DataCollection
  └─ SubSeq_StopAndSave
```

RAMScopeのConnect / Init / Config / Set_CondはSetupまたは`SubSeq_MeasurementSetup`へ置く。CloseはMainのサブシーケンスへ含めずCleanupへ固定する。

## 11.10 結果・レポート

レポートへ次を残す。

- 試験IDと試験条件
- 各ステップのStatus
- `TestError.ctl`の内容
- RAMScope API ReturnCode（PoC中または異常時）
- UnitNum、kind、MdlNo
- LostDataNum
- 保存した波形・ログファイルのパス
- Cleanupの実行結果

## 11.11 エラー時の遷移

1. VIがErrorを返したらMainの後続試験ステップを中断する。
2. TestStandのCleanupへ遷移する。
3. [12](./12_異常系処理とシャットダウン設計.md) の安全順序で停止する。
4. Cleanup中のエラーで元エラーを上書きしない。
5. 元エラーとCleanup結果をレポートへ残す。

## 11.12 TestStand組み込み完了条件

- [ ] LabVIEW単体のFlow Testが完了している
- [ ] Setup / Main / Cleanupの配置が本章どおりである
- [ ] 全VIのerror in / outがマッピングされている
- [ ] StatusとTestErrorを結果へ記録できる
- [ ] RAMScopeのMdlNo等を後段へ渡せる
- [ ] Readのポーリング周期をTestStandから変更できる
- [ ] 異常時にMainが止まりCleanupが実行される
- [ ] `RAMScope_Close.vi`が必ず実行される