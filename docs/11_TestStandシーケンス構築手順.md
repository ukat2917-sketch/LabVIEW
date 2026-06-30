# 11. TestStand シーケンス構築手順

LabVIEW VI を呼び出し、試験全体のフロー・条件・タイミングを管理する。

## 11.1 TestStand の基本構造

| 要素 | 説明 |
|------|------|
| **Sequence File（.seq）** | シーケンスの入れ物。複数のシーケンスを含む |
| **Sequence** | ステップの集まり。MainSequence が起点 |
| **Step Group** | `Setup` / `Main` / `Cleanup` の3グループ |
| **Step** | 1つの操作（VI 呼び出し・待ち・条件分岐 等） |
| **Variables** | `Locals`（ローカル）/`Parameters`（引数）/`FileGlobals`（ファイル共通）/`StationGlobals`（PC共通） |

### Step Group の役割
- **Setup**：機器接続・初期化（リファレンス確立）。Main の前に必ず実行。
- **Main**：試験本体（手順）。
- **Cleanup**：**異常時も含め必ず実行**される。→ 安全シャットダウンをここに置く（[12](./12_異常系処理とシャットダウン設計.md)）。

## 11.2 LabVIEW Adapter の設定

1. TestStand メニュー `Configure` → `Adapters`。
2. **LabVIEW Adapter** を選び、使用する LabVIEW バージョン／実行方式（Development System / Runtime）を設定。
3. ビット数（32/64bit）を VI・Runtime と一致させる。

## 11.3 VI を呼び出すステップの作り方

1. シーケンスの `Main` で右クリック → `Insert Step` → `Action`（または LabVIEW Adapter のステップ）。
2. ステップの **Adapter を「LabVIEW」** に設定。
3. `Specify Module` で対象 VI（例：`RZX_Voltage_Set.vi`）を選択。
4. **パラメータのマッピング**：VI のコネクタペイン端子と TestStand 変数を対応付ける。
   - 入力：`電圧条件` ← `Parameters.電圧条件` または `FileGlobals.電圧条件`
   - 入出力：機器リファレンス ← `FileGlobals.RZX_Ref`
   - 出力：`実行結果ステータス` → `Locals.Status`、`エラー情報` → `Locals.TestError`
5. **結果判定**：ステップの `Status Expression` で、VI 出力ステータスに応じて
   Pass/Fail/Error を判定（例：`Locals.Status == "OK"` で Pass）。

## 11.4 試験条件の変数管理

試験条件はすべて TestStand で変数化する。VI にハードコードしない。

| 試験条件 | 推奨格納先 | 例 |
|----------|------------|-----|
| 電圧条件 | FileGlobals / Parameters | `FileGlobals.電圧条件` |
| 電流（負荷条件） | FileGlobals / Parameters | `FileGlobals.目標電流` |
| 制御モード番号 | FileGlobals / Parameters | `FileGlobals.モード番号` |
| Ramp 時間 | FileGlobals / Parameters | `FileGlobals.Ramp時間` |
| 高圧使用台数 | FileGlobals | `FileGlobals.HV使用台数` |
| 機器リファレンス | FileGlobals | `FileGlobals.RZX_Ref[]`, `DLM_Ref` 等 |

### 条件をファイルから読む（再利用性）
- 試験条件を **CSV / プロパティファイル / Excel** で管理し、Setup で読み込んで FileGlobals に展開すると、
  条件変更がシーケンス改変なしで行える。
- `Property Loader` ステップを使うと、外部ファイルから変数値を一括ロードできる。

## 11.5 サブシーケンス化と並び替え（再利用設計）

> 「イベント順序を試験条件ごとに並び替える場合、各イベントをサブシーケンス化して、
> メインシーケンスで呼び出し順序を変更する」という方針でよい。

### 手順
1. イベントのまとまり（例：`電源投入`, `計測開始`, `負荷シナリオ`, `計測停止保存`）を
   それぞれ **サブシーケンス** として作成する。
   - サブシーケンスは VI 呼び出しステップの集合。引数（Parameters）で条件を受ける。
2. **MainSequence** は、これらサブシーケンスを **`Sequence Call` ステップ** で呼び出す。
3. 試験条件ごとに **呼び出し順序を並び替える** ／ 引数を変えることで、
   別条件・別試験へ流用する。

```
MainSequence
 ├ Sequence Call: SubSeq_電源投入(条件)
 ├ Sequence Call: SubSeq_計測開始(条件)
 ├ Sequence Call: SubSeq_負荷シナリオ(条件)   ← 並び替え対象
 ├ Sequence Call: SubSeq_CANモード遷移(条件)   ← 並び替え対象
 └ Sequence Call: SubSeq_計測停止保存(条件)
```

> 1イベント1VI ＋ イベント単位のサブシーケンス化により、
> 「並び替え容易・仕様変更に強い・別試験へ流用容易」が実現する。

## 11.6 同期／非同期・待ち時間・条件分岐の設定

これらは **TestStand 側で明示的に管理** する（VI には埋め込まない）。

| やりたいこと | TestStand の手段 |
|--------------|------------------|
| 順序を守る（同期） | ステップを直列に並べる（既定） |
| 並行実行（非同期） | `Sequence Call` を **New Thread** で起動 / ステップの実行オプションで並列化 |
| 非同期の完了待ち（合流） | `Wait` ステップ（Thread / Sequence の完了を待つ） |
| 待ち時間 | `Wait` ステップ（時間指定） |
| 条件分岐 | `If` / `Else` / `Select` ステップ、`Precondition`（前提条件式） |
| ループ | `For` / `While` / `Loop` オプション |

### 非同期の例（負荷ランプと割り込み）
1. `Sequence Call: SubSeq_負荷ランプ` を **非同期（New Thread）** で起動。
2. 続けて `Sequence Call: SubSeq_CANモード遷移` を実行（ランプ中に割り込み）。
3. 後で `Wait`（負荷ランプ Thread 完了）で同期させる。
（[08_負荷電流VIと並列処理.md](./08_負荷電流VIと並列処理.md) と対応）

## 11.7 結果・レポート管理

- TestStand は各ステップの結果（Pass/Fail/Error・測定値）を自動収集する。
- `Report Options` でレポート形式（HTML/XML/ATML/CSV）と保存先を設定。
- 計測値（電流値・RAM 値・温度）や、保存した波形ファイルのパスをレポートに残し、
  試験条件と結果を紐付けて管理する。

## 11.8 プロセスモデル（任意）

- 既定の **Sequential Model** で十分。各ステップが順次実行され、Setup/Main/Cleanup が回る。
- 複数 DUT を並行試験する将来要件があれば Parallel/Batch Model を検討（現時点では不要）。

## 11.9 エラー時のフロー（概要）

- ステップが Error/Fail を返したら、`On Run-Time Error` 設定または
  ステップの `Post Action` で **Main を中断 → Cleanup へジャンプ** させる。
- Cleanup で安全シャットダウン（[12](./12_異常系処理とシャットダウン設計.md)）を必ず実行する。
