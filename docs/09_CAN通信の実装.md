# 09. CAN 通信の実装

## 9.1 前提・課題

- **CANalyzer には LabVIEW 純正ドライバ（NI-XNET のようなネイティブ対応）は無い**が、
  **COM（ActiveX）API を経由すれば操作可能**であることが判明した（9.8 参照）。
  LabVIEW の ActiveX パレットから直接呼び出すことも、外部スクリプト（Python 等）経由でも可能。
- 一方、doc 01 の検討では「CANalyzer を無くし RAMScope の CAN モジュールに統合する」方針も
  併せて検討している。**両者はトレードオフの関係**にあり、機能ごとに使い分ける折衷案もありうる
  （9.8・9.9 参照）。

## 9.2 実装方式の候補

CANalyzer 無しで CAN 通信を行う手順（検討結果）：

1. **USB-CAN を使用する**
   - Contec 製は **ドライバあり**。LabVIEW から制御可能。
2. **CANdbc ファイルを XNET データベースエディタで編集**
   - 既存の dbc（信号定義）を NI-XNET の Database Editor で読み込み・編集する。
3. **VI で dbc ファイルを読み込み、計測・操作できるように VI を作成**
   - dbc に基づき信号名でフレームを送受信する VI を作る（※角田さん経由で確認）。

## 9.3 推奨アプローチ

| 方式 | ハードウェア | dbc 対応 | LabVIEW 対応 | 備考 |
|------|--------------|----------|--------------|------|
| **NI-XNET** | NI CAN インタフェース | ◎（XNET Database Editor で dbc 直接利用） | ◎（XNET VI が充実） | dbc・信号ベースで扱え最も実装しやすい |
| **Contec USB-CAN** | Contec USB-CAN | △（自前でデコード要の場合あり） | ○（メーカードライバ） | 既存資産・コスト次第 |

> dbc を信号名ベースでそのまま使い、VI を作りやすくする観点では **NI-XNET が有力**。
> Contec USB-CAN を使う場合は、dbc のデコード／エンコードを VI 側でどこまで作るか確認する。

## 9.4 NI-XNET を用いる場合の構築手順

### (1) dbc データベースの準備
1. **NI-XNET Database Editor** を起動。
2. 既存の `*.dbc` を読み込む（または新規作成）。
3. 供試体マイコンの「制御モード」フレーム・信号が定義されているか確認・編集する。
4. dbc をエイリアス登録（NI MAX / XNET）して LabVIEW から参照可能にする。

### (2) CAN 制御 VI の作成
共通入出力仕様（[05](./05_VI設計方針と共通仕様.md)）に従い以下を作る。

| VI | XNET 主要関数 | 処理 |
|----|---------------|------|
| `CAN_Open.vi` | `XNET Create Session`（Signal Output Single-Point / Frame Input 等） | dbc・インタフェース指定でセッション確立 |
| `CAN_Send_Mode.vi` | `XNET Write (Signal Single-Point)` | **制御モード番号** を信号値として書き込み送信 |
| `CAN_Read.vi` | `XNET Read (Signal/Frame)` | マイコンからの応答・状態を受信・デコード |
| `CAN_Close.vi` | `XNET Clear` | セッション解放 |

### (3) 制御モード番号の扱い
- **制御モード番号は TestStand の試験条件（変数）** として管理し、
  `CAN_Send_Mode.vi` の入力で受け取る。
- 試験条件に合わせて遷移条件（いつ・どのモードを送るか）を TestStand 側で設計する。

## 9.5 Contec USB-CAN を用いる場合の構築手順

1. Contec の CAN ドライバ（API/サンプル）をインストール。
2. メーカー提供の LabVIEW 用 VI / DLL ラッパで `Open / Send / Receive / Close` を実装。
3. dbc のエンコード／デコード（信号→生バイト、生バイト→信号）が必要なら、
   - XNET Database を「データベースとしてのみ」利用してデコードする、または
   - dbc 仕様に基づくスケーリング／ビット配置の変換 VI を自作する。
4. 入出力仕様は NI-XNET 版と揃え、TestStand から見て同じ使い勝手にする。

## 9.6 確認・検証

- 送信：`CAN_Send_Mode.vi` で送ったフレームが、CANalyzer / バスモニタで意図どおりの
  ID・データになっているか確認。
- 受信：マイコンの応答が信号値として正しくデコードされるか確認。
- タイミング：モード送信は他処理（負荷ランプ等）と並行する場面があるため、
  非同期実行時の送信遅延を確認する（[08](./08_負荷電流VIと並列処理.md)）。

## 9.7 未確定事項（要決定）

- NI-XNET か Contec USB-CAN か（ハードウェア選定）。
- dbc のデコード／エンコードをどの層で持つか。
- → 実装前に方式を確定する（角田さん経由の確認結果を反映）。

## 9.8 CANalyzer COM（ActiveX）API での操作方式

TEXIO/DTS インサイトのような公式 LabVIEW ドライバとは異なり、CANalyzer には
COM（ActiveX）経由でのみ外部から操作する手段がある。顧客から提供された実際の
Python 参考実装（`CAN_Tx.txt`／`CAN_Rx.txt`）を確認したところ、
**同じ COM API を LabVIEW の ActiveX パレットから直接呼び出すことも可能**と判断できる。

**COM 接続の仕様（提供されたPython参考実装より確定）：**

```python
canalyzer = win32com.client.Dispatch("CANalyzer.Application")   # ProgID確定。CANoeは明示的に禁止と明記
...
# 書き込み（Tx）
canalyzer.System.Namespaces(namespace).Variables.Item(variable_name).Value = value_to_send
# 読み取り（Rx）
value = canalyzer.System.Namespaces(namespace).Variables.Item(variable_name).Value
```

- **ProgID は `"CANalyzer.Application"` で確定**（`"CANoe.Application"`ではない。
  Pythonソースのコメントに「CANoeは禁止」と明記されている）。
- 既存プロセスへの接続が前提（新規起動は保証外。複数起動時は動作保証外）。
- Tx/Rxとも**Excelから読み込んだ表（列：`ID`＝Namespace名、`Name`＝変数名、
  Txのみ`deta`＝送信する値）を1行ずつループし、行ごとに`try/except`で
  エラーを握りつぶして次の行へ進む**（1行の失敗で全体を止めない設計）。
- COM接続自体の失敗時（`Dispatch`失敗）は即終了・リトライ無し。

### 9.8.1 利点

| 利点 | 内容 |
|------|------|
| **既存の CANalyzer 資産をそのまま使える** | CAPL・パネル・.dbc・残バスシミュレーション・ゲートウェイ模擬・ロギング設定を再利用。製作コストがほぼゼロ |
| **複雑な処理を CANalyzer に任せられる** | 残バスシミュレーション、周期送信、ノード模擬、.asc/.blf ロギング、解析等を CANalyzer 側が担当 |
| **System Variable という抽象化** | 生フレームのビット操作でなく「変数に値を入れると CAPL/パネルが反応」。テスト自動化と物理層の詳細を分離できる |

### 9.8.2 自動化上の課題

| 課題 | 詳細・影響 |
|------|-----------|
| **プロセス・タイムベースの跨ぎ** | 本体は LabVIEW+TestStand。そこに（Python 経由の場合）Python + CANalyzer が加わり、**3つのランタイム・タイムベースをまたぐ統合・同期**が必要になる。LabVIEW の ActiveX パレットから直接呼べば、この課題は Python 分だけ軽減できる |
| **事前起動・状態依存** | 「既存プロセスへ接続」前提＝CANalyzer を人が起動し測定開始済みにしておく必要。完全自動起動ではない |
| **接続の脆さ** | COM 接続失敗時は即終了・リトライ無し（Python 仕様書の設計）。長時間の自動試験では堅牢性の考慮が要る |
| **タイミング精度** | Python 版は行間の待ちが `time.sleep()`＝OS スケジューラ依存で sub-ms の決定性なし。本システムの「シビアなタイミング」試験には不向きな箇所がある |
| **🔴 Rx がテストフローに戻らない** | Python 仕様書は「ログ出力のみ」（Excel への書き戻し無し）。**ただしこれは COM の技術的制約ではなく、その実装の設計判断**。`Variables.Item("Variable").Value` は読み取りにも同じプロパティを使うため、**LabVIEW から直接 ActiveX で読み取れば、同一プロセス内で Rx 値を TestStand の判定に渡すことは技術的に可能**。ただし CAPL 側がその受信値を System Variable として公開している必要がある（公開されていない信号は読めない）|
| **System Variable 経由の制約** | 生フレームを直接ではなく CANalyzer 設定（CAPL）が公開した System Variable 経由でしか操作できない＝カバレッジが CANalyzer 設定に依存 |
| **ライセンス・コスト** | CANalyzer ライセンスが常時必要。RAMScope への CAN 統合（doc 01 検討）とは逆行する |

> **Rx が取れない場合の代替案**：CAPL 側で信号が公開されていない場合、
> **RAMScope の CAN モニタ機能で該当フレームを直接受信・確認**する保険的な設計にできる
> （doc 10 の `GetBufferData`／CAN パケット解析。9.9 とも役割分担できる）。

### 9.8.3 方式の比較検討（2案を並行して具体化中）

**役割分担ではなく、どちらか一方を採用する2つの候補方式として比較検討中**
（実運用で両方を同じCAN IDに対して同時に使うことはしない。同じIDを両方から
送信するとバス上で二重送信・衝突になるため）。

| # | 方式 | 内容 |
|---|------|------|
| 1 | **CANalyzer統合（COM/ActiveX）** | 9.8.4のVIでSystem Variableを読み書き。チェックサム／アライブカウンタは既存CAPLノードシミュレーションが自動計算（9.9.2で確認済み）。LabVIEW側での再実装は不要 |
| 2 | **CANalyzer不使用（RAMScopeでRAM・CANを一括管理）** | 9.9・10.4.11のとおりLabVIEW側でチェックサム／アライブカウンタを計算し、RAMScopeのCANモジュールから直接送信・受信する |

**比較の観点：**

| 観点 | 方式1（CANalyzer/COM）| 方式2（RAMScope一括）|
|------|----|----|
| チェックサム／カウンタ実装 | 不要（CAPLが自動計算）| LabVIEW側で実装・保守が必要（9.9.2/9.9.3）|
| ライセンス | CANalyzerライセンスが試験PC台数分必要 | 不要 |
| RAM計測とCANの時刻同期 | LabVIEW・CANalyzerが別プロセス→**別々のタイムベース**をまたぐ突き合わせが必要 | **同一RAMScopeデバイス・同一測定セッションで取得**するため、RAM値とCANフレームが自然に時刻同期される（doc10 10.4.2b「測定データパケット構成」がRAM/CAN共通） |
| 残バスシミュレーション・複雑なノード模擬 | CAPLの資産をそのまま使える（強み）| 自前実装が必要（対象メッセージが増えるほど手間が増える）|
| 起動・運用 | CANalyzerの事前起動・測定開始が前提（完全自動化ではない）| LabVIEW/TestStandのみで完結 |
| Rx（DUTからの受信）| CAPLが公開しているSystem Variableのみ読める | RAMScopeのCANモニタで生フレームを直接取得可能（範囲はRAMScope側の設定次第）|

どちらを最終的に採用するか、あるいは試験フェーズによって使い分けるかは未確定。
現時点では両案とも並行して具体化中（9.8.4＝方式1のVI設計、9.9・10.4.11＝方式2のVI設計）。

### 9.8.4 LabVIEW ActiveX 実装

`CAN_Tx.txt`／`CAN_Rx.txt`（提供された参考実装）をベースに、追加でChatGPTによる
詳細実装案（`CANalyzer_LabVIEW_ActiveX_Implementation.md`）も検討した。後者には
Python参考実装に無い**重要な指摘（Measurement起動確認）**が含まれる一方、
**本プロジェクトの設計方針（doc05・06）とは異なるアーキテクチャ**
（内部ステートマシンVI＋Excel＋独自ログ体系）を提案しているため、
**良い点だけ取り込み、アーキテクチャは本プロジェクトの流儀に合わせる**。

#### 9.8.4.1 ChatGPT草案との比較・採否

| 項目 | ChatGPT草案の提案 | 採否 | 理由 |
|---|---|---|---|
| **Measurement起動確認・自動開始** | `Measurement.Running`確認→未起動なら`Start`→`Running=True`までポーリング（100ms周期、10sタイムアウト） | ✅ **採用**（重要な訂正） | CAPLの`on timer`ハンドラは**測定中のみ実行される**。測定停止中にSystem Variableへ書き込んでもCAPL側が反応せず送信されない。Python参考実装はここを「事前に人手で測定開始しておく」前提にしていたが、**LabVIEW側で確認・自動開始する方が自動試験に向く**ため採用 |
| **LabVIEWが起動した場合のみ停止**（`MeasurementStartedByLabVIEW`）| Close時、自分が起動した場合のみ`Measurement.Stop`| ✅ **採用** | 他プロセス（人・別試験）が使用中の測定を意図せず止める事故を防げる、妥当な設計 |
| **Direction列（Tx/Rx統合）／DataType列（型指定）** | 1つの表でTx/Rxを混在させ、型も明示 | ✅ **採用**（簡略化として） | Tx用・Rx用で表を分けなくてよくなり、型の暗黙変換ミスも防げる |
| **Wait列（行ごとの待ち時間）** | 行実行後に指定秒数待機。不正値はログ＋スキップ、上限あり | 🟡 **一部採用** | 待ち時間の概念自体は有用。ただし本プロジェクトでは「待ち時間はTestStand側で明示する」方針（doc05 5.2）のため、**LabVIEW VI内蔵ではなくTestStand側のWaitステップに任せる**のが本来の流儀。バッチ処理VIとして一括実行する場合に限り、VI内部にWait列を持たせてよい |
| **行エラー／システムエラーの2階層** | 行エラー＝ログして継続、システムエラー（COM接続失敗等）＝終了 | ✅ **採用**（考え方のみ）| 妥当な分類。ただし独自の`CAN_State`/ログCSVではなく、**本プロジェクト標準の`Status.ctl`/`TestError.ctl`/`Error_To_TestStatus.vi`（doc06 6.1.2）で表現**する |
| **内部ステートマシンVI（`CAN_State.ctl`で13状態）＋`CAN_Auto_Main.vi`が全体を統括** | 1本の大きなVIがExcel読込〜ログ出力まで全部内包 | ❌ **不採用** | 本プロジェクトは「1イベント1VI、TestStandが順序を制御する」設計（doc05 5.1）。ステートマシンをLabVIEW側に作ると**TestStandと役割が重複**し、他機器群（FG420・RAMScope）と設計思想が食い違う。各状態はそのまま薄いVI（`CAN_COM_Connect.vi`等）またはTestStandのステップ・ループに対応させれば同じことができる |
| **Excel（`pandas`相当）を直接読む** | `.xlsx`をそのまま読み込み | ❌ **不採用（CSVに統一）**| doc05の既定方針（試験条件はCSV/プロパティファイルで管理）に合わせる。LabVIEWのレポート生成ツールキット無しでExcel読込は依存が増える |
| **独自ログCSV形式（Timestamp,Level,RowIndex,...）** | 専用の`Log_Write.vi` | 🟡 **一部採用**| ログに残すこと自体はよいが、**実行結果ステータス／エラー情報は`Status.ctl`/`TestError.ctl`のままTestStandへ返す**（doc05 5.3/5.4）。追加のCSVログは任意の補助出力として残す分には問題ない |
| **cfg一致確認**（開いている設定ファイルパスの検証）| 期待するcfgと現在のcfgを比較 | ✅ **採用（任意機能として）**| 誤ったCANalyzer設定を開いたまま試験してしまう事故を防げる、安価で有効な保険 |
| **bit数一致（32/64bit）・複数起動不可の明記** | 運用上の注意点 | ✅ **採用（運用注意として記載）**| 妥当な注意点。9.8.4.4に記載 |
| **Rxの値をExcelへ書き戻さない（ログのみ）** | 元Python仕様の踏襲 | ❌ **不採用（本プロジェクトでは戻り値として返す）**| 9.8.2で既述のとおり、**LabVIEWから直接読めばTestStandの判定にRx値を渡せる**のが本プロジェクトの狙い。ログのみに留める理由が無い |

#### 9.8.4.2 VI構成（確定）

```
CAN_COM_Connect.vi              … Automation Open（ProgID "CANalyzer.Application"）
CAN_COM_Check_Measurement.vi    … Measurement.Running を読むだけ（NEW）
CAN_COM_Start_Measurement.vi    … 未測定なら Start → Running=True までポーリング（NEW）
CAN_COM_Write_SysVar.vi         … Tx（1行分）
CAN_COM_Read_SysVar.vi          … Rx（1行分）
CAN_COM_Close.vi                … Measurementは「自分が起動した場合のみ」Stop、参照はClose
```

`CAN_COM_Connect.vi`：

- **Automation Open**（関数パレット→通信→ActiveX）で ProgID `"CANalyzer.Application"` を開く。
- 出力：Application の ActiveX 参照（後続VIへ引き回す。VISA参照と同じ考え方、[05](./05_VI設計方針と共通仕様.md) 5.6）。
- **既存プロセスへの接続が前提**（CANalyzerを事前に人手で起動しておく）。
  接続失敗時はリトライせずエラーを返す（Python参考実装と同じ設計）。

`CAN_COM_Check_Measurement.vi`／`CAN_COM_Start_Measurement.vi`：

- `Application参照`→プロパティノード`.Measurement`→`MeasurementRef`取得。
- `MeasurementRef`のプロパティノード`.Running`（Bool）を読む。
- `False`の場合、呼び出しノード`.Start`をInvokeし、`Running=True`になるまで
  **100ms周期でポーリング、10秒でタイムアウト**（タイムアウトは`実行結果ステータス=Timeout`、
  [05](./05_VI設計方針と共通仕様.md) 5.3）。
- 出力に`起動済みフラグ`（このVIが起動させたか、元々測定中だったか）を持たせ、
  `CAN_COM_Close.vi`まで引き回す。

`CAN_COM_Write_SysVar.vi`（Tx。1行分）：

| 端子 | 型 | 内容 |
|------|----|----|
| `Application参照`（in/out）| ActiveX参照 | |
| `Namespace` | String（入力）| 例：`"ID03AD5D62"` |
| `変数名` | String（入力）| 例：`"CORE_SVS_OPE_MODE_COM"` |
| `値` | Variant（入力）| 書き込む値。呼び出し側でI32/DBL/Boolean/String等、System Variableの実際の型に合わせて渡す |

配線：プロパティノード `Application.System` → 呼び出しノード `Namespaces(Namespace)` →
プロパティノード `.Variables` → 呼び出しノード `Item(変数名)` →
プロパティノード `.Value`（**書き込み＝Set**）に`値`を配線。

`CAN_COM_Read_SysVar.vi`（Rx。1行分）：

`CAN_COM_Write_SysVar.vi`と同じ配線で、最後の `.Value` プロパティノードを
**読み取り＝Get**にする。**読み取った値は出力として返し、TestStandの判定にそのまま渡せる**
（9.8.2で確認済みの改善点。Python参考実装のようにログ出力のみに留めない）。

`CAN_COM_Close.vi`：

**Close Reference** で ActiveX 参照を解放する。**CANalyzerプロセス自体は終了させない**。
Measurementは`CAN_COM_Start_Measurement.vi`が返した`起動済みフラグ`が`True`の場合のみ
`.Stop`をInvokeする（元々測定中だった場合や、他プロセスが起動した場合は止めない）。

#### 9.8.4.3 型定義（`00_Common`または`60_CAN`に配置）

ChatGPT草案の型定義群は妥当なので、本プロジェクトの命名・配置方針に合わせて採用する。

| 型定義 | 内容 |
|---|---|
| `CAN_SysVar_Direction.ctl`（Enum）| `Tx` / `Rx` |
| `CAN_SysVar_DataType.ctl`（Enum）| `Auto` / `I32` / `DBL` / `Boolean` / `String` |
| `CAN_SysVar_Command.ctl`（Cluster）| `Namespace`(String) / `変数名`(String) / `値`(Variant) / `DataType`(上記Enum) / `Direction`(上記Enum) / `Wait_s`(DBL) / `Enable`(Bool) |

`Status.ctl`／`TestError.ctl`は使い回す（doc06 6.1〜6.1.2）。CANalyzer固有の追加型定義は
この3つのみで足りる。

#### 9.8.4.4 複数行の一括Tx/Rx

CSV（`CAN_SysVar_Command.ctl`配列に変換）を読み込み、`For Loop`で1行ずつ
`Direction`に応じて`CAN_COM_Write_SysVar.vi`または`CAN_COM_Read_SysVar.vi`を呼ぶ。
待ち時間は**原則TestStand側のWaitステップで明示**する（doc05 5.2）が、1つのバッチを
1ステップとして扱いたい場合はVI内の`For Loop`に`Wait_s`を組み込んでもよい
（その場合、doc06 6.4.1同様フラットシーケンス等でタイミングを保証すること、A1.6.1 STEP4参照）。

```
CSV読込 → CAN_SysVar_Command.ctl配列
  → For Loop（各行）
      Enable=False の行はスキップ
      Direction=Tx → CAN_COM_Write_SysVar.vi
      Direction=Rx → CAN_COM_Read_SysVar.vi（結果を配列で持ち帰りTestStandへ）
      → 行エラーは Status.ctl=Warning 相当としてログ配列に追記、次の行へ進む
```

> ⚠️ **標準のエラー伝播（[05](./05_VI設計方針と共通仕様.md) 5.5）からの意図的な逸脱**：
> 通常は`error in`にエラーがあれば後続処理をスキップするが、この一括Tx/Rxループは
> **1行の失敗で他の行を止めない**（参考実装・ChatGPT草案とも共通の設計判断）。
> `For Loop`内でエラークラスタを毎回リセットし、`TestError.ctl`配列に行番号付きで
> 追記する（ループを止めるための`error in`配線はしない）。
> **COM接続失敗・Measurement起動失敗などのシステムエラーはこの限りでなく、
> 通常どおりerror inで後続をスキップし試験を中断する**（ChatGPT草案の
> 「行エラー／システムエラー」の2階層区分をそのまま採用）。

#### 9.8.4.5 運用上の注意点（ChatGPT草案より採用）

- **32bit/64bit を LabVIEW と CANalyzer で揃える**（不一致だとActiveX接続で問題が出うる）。
- **CANalyzerは1プロセスのみ起動**（複数起動時の動作は保証外）。
- 任意機能として、`CAN_COM_Connect.vi`実行後に**現在開いているcfgファイルパス**
  （`Application.Configuration.FullName`等）を取得し、期待するパスと一致するか確認する
  チェックを追加してもよい（誤った設定ファイルのまま試験してしまう事故を防止）。

## 9.9 アライブカウンタ・チェックサム付きフレームの実装（RAMScope 直叩き版）

RAMScope の CAN 送信関数（`RAMScopeGT170SendCANDataFrame` / `ScenarioSendSet`、doc 10）は
**与えたバイト列をそのまま送るのみ**で、アライブカウンタのインクリメントや CRC 計算を
ハードウェア側で自動計算する機能は無い。**カウンタ値・チェックサムは送信バイトを組み立てる
LabVIEW 側で計算する**必要がある。実現方法は 2 通り。

### 方式A：ペイロード事前展開＋シナリオ送信（推奨・高精度）

アライブカウンタが取りうる値の**組み合わせを全て事前計算**（各カウンタ値に対応する
チェックサムも計算済み）し、`RAMScopeGT170ScenarioSendSet` の複数ステップとして登録、
`WaitTime`（周期）でループ送信させる。

- `SEND_SCENARIO` は `Step[64]` まで持てる（doc 10 確定）ため、
  **カウンタが 4bit（0〜15＝16通り）なら余裕で収まる**。
- **RAMScope ハードウェアが正確なタイミングで送信**するため、周期ジッタが小さい。
- **カウンタが 8bit（256通り）以上だと `Step[64]` の上限を超え方式Aでは不可**
  → 方式Bへ切り替える。
- 前提条件：**カウンタ・チェックサム以外の全バイトが試験を通じて固定値**であること。
  他の信号も同時に変化させる要件があると、組み合わせが掛け算で増え破綻する
  （その場合は該当信号が変わるたびにシナリオを再登録する設計か、方式Bを使う）。

### 方式B：毎周期 LabVIEW で計算して送信（汎用・値可変に対応）

LabVIEW のタイムドループ内で毎周期：カウンタ値をインクリメント → チェックサム計算 →
`RAMScopeGT170SendCANDataFrame` で送信。

- ペイロードを試験中に変化させる（信号スイープ等）場合も対応可能。
- 送信周期は Windows/LabVIEW ループのタイミングに依存しジッタが乗る
  （10ms 周期程度なら通常許容範囲だが、ECU の E2E タイムアウトが厳しい場合は要検証）。

### VI 設計方針：ECU 仕様が未確定でも骨格は先行着手可能

チェックサムのアルゴリズム・カウンタ幅は `.can`（CAPL）ソースより確定済み（9.9.2）。
残るはバイト・ビット位置のみで、これは dbc 入手待ち。
**その部分を独立したサブVIに閉じ込めれば、他の配線（CLFN・バッファ構築・ループ構造）は
dbc 確定前に着手できる**。

| 分類 | 内容 | 着手可否 |
|------|------|:---:|
| 分かっている部分 | RAMScope CLFN 配線、`SEND_SCENARIO`/`CANSEND_170_DATA` バッファ組み立て、ループ構造、TestStand I/O、共通仕様（[05](./05_VI設計方針と共通仕様.md)）、**チェックサム計算式・カウンタのビット幅とラップ挙動（9.9.2）**| ✅ 先行着手可 |
| 未確定な部分 | カウンタ／チェックサムのバイト・ビット位置（dbc 待ち） | ❌ dbc 入手後に位置だけ差し替え |

**推奨構成：**

- **`CAN_Alive_Checksum_Calc.vi`（アルゴリズムは確定済みなので先行で本実装可能）**：
  入力＝CAN ID・カウンタ値・ペイロードバイト配列（チェックサムバイトは0埋め）、
  出力＝カウンタバイト・チェックサムバイト。
  中身は 9.9.2 の「IDニブル和（種別マーカーOR）＋各ペイロードバイトのニブル和＋カウンタ値の
  総和を2の補数化」で実装してよい。**バイト位置（どのバイトがカウンタ/チェックサムか）だけ
  入力端子でパラメータ化**し、dbc 入手後に配線するバイト配列の組み方だけ差し替える。
- **`CAN_Send_Alive_Frame.vi` の骨格**：カウンタは2bit（0〜3）と判明したため、
  **方式A（`SEND_SCENARIO` 事前展開。4通り分の Step で足りる）を採用してよい**。
  `For i = 0 to 3` でこのサブVIを呼び、`SEND_SCENARIO_STEP` 配列に格納 →
  `ScenarioSendSet` へ CLFN 配線。
- ダミーのバイト位置（仮配置）で先に `ScenarioSendSet`→`ScenarioSendStart` を発行し、
  CLFN 配線自体の動作を **CAN バスモニタ（CANalyzer 等）で意図通りのフレームが
  出るか**先に検証しておける（dbc 確定前でも配線経路の検証は可能）。
- フォールト注入（アライブカウンタ停止／チェックサム異常／通信途絶）は、9.9.2 で判明した
  CANoe システム変数（`ALIVE_COUNTER`/`CHECKSUM`/`TIMEOUT`）を CANalyzer COM 経由で
  切り替える方式も選択肢に入る。LabVIEW側でわざと壊れたフレームを作る方式と比べて、
  実際のECU側ノードシミュレーションの挙動に忠実という利点がある（9.8.3 で比較検討）。

### 9.9.1 ECU 仕様の確認チェックリスト（実装前に確認する項目）

| # | 確認項目 | 内容 | 状況 |
|---|---------|------|:---:|
| ① | CAN ID・DLC・送信周期 | 標準/拡張ID・ペイロード長・周期(ms) | 🟡 CAPLから周期・ID(enum名)は判明。DLCはdbc待ち |
| ① | バイトレイアウト | ペイロード内のカウンタ・チェックサム・固定値のバイト/ビット位置マップ | ❌ dbc待ち（週明け入手予定） |
| ② | カウンタのビット幅 | 4bit(16通り)か8bit(256通り)か等。**方式A/Bの選択に直結**（`Step[64]`上限）| ✅ **2bit（0〜3）と確認済み**（9.9.2） |
| ② | カウンタの初期値・ラップ挙動 | 0開始か、最大値からのロールオーバーか | ✅ **3の次に0へラップと確認済み**（9.9.2） |
| ③ | チェックサムのアルゴリズム | 単純XOR/加算か、CRC(多項式指定)か、AUTOSAR E2E(Profile 1/2/5/6/11等)か | ✅ **加算＋2の補数と確認済み**（9.9.2。CRCではない）|
| ③ | CRC使用時のパラメータ | 多項式・初期値・最終XOR値・ビット順（MSB/LSB first）| － CRC方式ではないため対象外 |
| ③ | チェックサムの保護範囲 | 計算対象バイト。CAN ID自体を含むか（AUTOSAR E2Eでは含むケースが多い）| ✅ **CAN IDを含む**（種別マーカーOR後にニブル和。9.9.2）|
| ④ | 固定値の前提確認 | カウンタ・チェックサム以外の全バイトが試験を通じて固定か（方式Aの成立条件）| 🟡 個別試験条件次第。方式A採用は9.9.2参照 |
| ⑤ | RAMScope側の設定 | 送信対象 `MdlNo`・物理チャンネル（Ch1/Ch2）、CAN 2.0B/FD（`isUseFDFormat`）| ❌ 未確認 |

### 9.9.2 CAPL（CANoeノードシミュレーション`.can`）ソースより確定した仕様

顧客／ECU側から提供された `.can` ファイル（CANoe/CANalyzer の CAPL スクリプト。dbc ではなく
**ノードシミュレーションの実ソースコード**）に、送信メッセージ組み立てロジックがそのまま
記述されていたため、チェックサム・アライブカウンタの**アルゴリズムそのもの**が確認できた。
dbc は信号のビット位置は分かってもアルゴリズムまでは分からないため、**この `.can` は dbc の
上位互換の情報源**になっている。

#### アライブカウンタ

```c
byte ALIVE_add(byte counter)
{
  if (counter == 3) { counter = 0; }
  else              { counter += 1; }
  return counter;
}
```

- **2bit幅（0→1→2→3→0…）**。4bit(16通り)ではない。
- メッセージ（CAN ID）ごとに独立したカウンタ。呼び出し時に**自メッセージの現在値**を渡して
  インクリメントするため、送信周期どおりに毎回 +1 されるだけの単純な挙動。
- **4通りしか無いため、doc9.9 の方式A（`SEND_SCENARIO` 事前展開）が Step[64] 上限に
  余裕をもって収まる**。他の全バイトが固定なら、方式A一択でよい。

#### チェックサム

```c
checksum = ~sum_all + 1;                       // 2の補数（＝ 256 - sum_all のバイト内演算）
msg.CHECKSUM_xxx = checksum;
```

`sum_all` は次の3種を単純加算した値：

1. **`id_check(ID)`**：CAN ID に種別マーカーを OR してからニブル和（4bitずつの総和）を取る。
   - 標準ID（11bit、`0 < ID < 0x7FF`）→ `ID | 0x800`
   - 拡張ID（29bit、`0x800 < ID < 0xFFFFFFFF`）→ `ID | 0xE0000000`
   - **CAN ID 自体がチェックサムの保護範囲に含まれる**（マーカー付きで）。
2. **ペイロード各信号の重み付き加算**：各信号を`信号値 × 固定の係数`または`sum_plus()`
   （複数bit信号の場合）で加算する。
3. **アライブカウンタの値**（そのまま加算）。

> 🔴 **訂正（dbc入手後に判明）**：当初「係数はバイト内ビット位置から決まる（`2^bit位置`）」
> と推測していたが、これは誤り。例えば `CORE_SVS_OPE_MODE_COM`（ID03AD5D62）は
> dbc上では **byte0のbit7:5**（3bit信号）に配置されているにもかかわらず、CAPLでの
> 重みは`*2`（＝`2^1`）であり、`2^5`ではない。**つまり係数はビット位置から機械的に
> 導出されるものではなく、ECU側の仕様として個別に決められた値**であり、
> **CAPLソースに書かれている係数をそのまま転記する必要がある**（推測で汎用化しない）。
> 「バイト単位のニブル和で代用できる」という以前の記述は撤回する。

ニブル和関数：

```c
byte sum_plus(dword value)
{
  dword sum = 0;
  for (count = 0; count < 8; count++) {   // 4bitずつ8回＝32bit分
    sum += value % 16;
    value = value / 16;
  }
  return sum;
}
```

**LabVIEW実装への翻訳（確定方針）**：上記の訂正により、**メッセージIDごとにCAPLの
加算式をそのまま転記する**（汎用的なニブル和ショートカットは使わない）。
`checksum = 256 − (id_check(ID) ＋ Σ(各信号値 × CAPLに書かれた係数、または sum_plus(信号値)) ＋ カウンタ値) mod 256`。
9.9.3 に、dbc（本編から提供された「main」側）と付き合わせて確定した、Tx対象6メッセージの
信号位置・係数をそのまま実装できる形でまとめた。

### 9.9.3 dbc突き合わせにより確定した Tx対象メッセージの仕様（main側）

提供された「main」dbc（Sub側は別途）と 9.9.2 のCAPLを突き合わせ、RAMScopeから**送信する
必要がある**メッセージ（dbc上の送信元が `SVS` 以外＝DUT以外のノードをシミュレートする側）の
バイト位置を確定した。**全メッセージ共通で、byte7の下位6bitがアライブカウンタ・
チェックサム専用**という統一パターンになっている点に注目。

| メッセージ（周期）| ID（16進）| DLC | 信号配置 | チェックサム計算の重み（CAPL確定）|
|---|---|:---:|---|---|
| ID03AD5D62（10ms）| `0x03AD5D62`（拡張）| 8 | `CORE_SVS_OPE_MODE_COM`=byte0[7:5]（3bit）／`CORE_ALIVE_COUNTER`=byte7[5:4]／`CORE_CHECKSUM`=byte7[3:0] | `id_check(ID) + OPE_MODE_COM×2 + counter` |
| ID0CD9AB55（100ms）| `0x0CD9AB55`（拡張）| 8 | `CORE_SVS_ACTION_MODE`=byte0[7:0]+byte1[7:0]（16bit）／`ALIVE_COUNTER`=byte7[5:4]／`CHECKSUM`=byte7[3:0] | `id_check(ID) + sum_plus(ACTION_MODE) + counter` |
| ID158（10ms）| `0x158`（標準）| 8 | `EAT_TRANS_SPEED`=byte4[7:0]+byte5[7:0]（16bit）／`EAT_REF_DISTANCE_TRAVELLED`=byte6[7:0]（8bit）／`ALIVE_COUNTER`=byte7[5:4]／`CHECKSUM`=byte7[3:0] | `id_check(ID) + sum_plus(TRANS_SPEED) + sum_plus(REF_DISTANCE) + counter` |
| ID212（40ms）| `0x212`（標準）| 8 | `ENG_IGSW_212`=byte5[5]（1bit）／`ENG_DTCCLINH_212`=byte5[3]（1bit）／`ENG_SYSTEM_READY_S`=byte6[7]（1bit）／`ALIVE_COUNTER`=byte7[5:4]／`CHECKSUM`=byte7[3:0] | `id_check(ID) + IGSW×2 + DTCCLINH×8 + SYSTEM_READY_S×8 + counter` |
| ID408（300ms）| `0x408`（標準）| 8 | `ENG_OBD_REQ`=byte4[7:0]（8bit）／`ALIVE_COUNTER`=byte7[5:4]／`CHECKSUM`=byte7[3:0] | `id_check(ID) + sum_plus(OBD_REQ) + counter` |
| ID579（1000ms）| `0x579`（標準）| 8 | `OTA_STATUS`=byte0[7:0]（8bit）／`ALIVE_COUNTER`=byte7[5:4]／`CHECKSUM`=byte7[3:0] | `id_check(ID) + sum_plus(OTA_STATUS) + counter` |
| ID14003807（500ms）| `0x14003807`（拡張）| 8 | `FRONT_NMFRAME`＝全8byte。**アライブカウンタ・チェックサム無し**（byte(0)/(1)/(2)/(4)/(6)への直接フラグ書き込みのみ、9.9のCAPL参照）| 対象外（NMフレーム）|

> ⚠️ **転記ミスに注意**：係数（`×2`／`×8`等）は信号ごとに個別の値であり、
> 同じメッセージ内でも信号によって異なる（9.9.2で確認済みのとおり、ビット位置からの
> 機械的な導出はできない）。上表はCAPL原文から書き写したものだが、
> **実装時は必ずCAPL原文と1行ずつ突き合わせて転記すること**
> （他のメッセージ用の行と混同しての転記ミスが起きやすい箇所）。

> **Rx側（dbc上の送信元が`SVS`）**：`ID03AD5D63`／`ID0CD9AB57`／`ID1400388D`は
> DUT自身が送信するメッセージで、RAMScopeのCAN受信（`GetBufferData`系、10.4.11 STEP7以降で
> 別途設計）で読み取る対象。Tx側の設計（9.9.2・10.4.11）とは別の実装になる。

> **共通パターンの発見**：**全メッセージでbyte7の[5:4]がアライブカウンタ、[3:0]が
> チェックサム**、という配置は完全に一致している（byte7[7:6]は未使用/予約）。
> `CAN_Alive_Checksum_Calc.vi`（10.4.11 STEP2）の出力側（カウンタ・チェックサムを
> ペイロードへ書き戻す処理）は、**この共通パターンにより全メッセージで同一ロジックに
> できる**（byte7を`(未使用2bit)(counter 2bit)(checksum 4bit)`に固定で組み立てるだけでよい）。
> 差分が出るのは入力側（`sum_all`に何を足すか）の信号ごとの部分のみ。

#### フォールト注入用システム変数（重要な副産物）

CAPL 中で各 CAN ID ごとに次の CANoe システム変数が参照されている。

| システム変数 | 意味 |
|---|---|
| `@sysvar::<ID>::ALIVE_COUNTER` | 非0にするとカウンタのインクリメントを止める（**アライブカウンタ異常の注入**）|
| `@sysvar::<ID>::CHECKSUM` | 1にすると送信直前にチェックサムへ+1（**チェックサム異常の注入**）|
| `@sysvar::<ID>::TIMEOUT` | 非0にすると当該メッセージの送信自体を止める（**通信途絶の注入**）|

これは [9.8](#98-canalyzer-comactivex-api-での操作方式) で検討した **CANalyzer COM API 経由の
System Variable 操作**（`app.System.Namespaces("Namespace").Variables.Item("Variable").Value`）で
そのまま制御できる。つまり **異常系試験（[12](./12_異常系処理とシャットダウン設計.md)）の
アライブカウンタ異常・チェックサム異常・通信途絶は、LabVIEW側でフレームを壊さずとも、
CANoe/CANalyzer側のこの仕組みを COM 経由で切り替えるだけで注入できる**。実装の選択肢が
広がったため、9.8.3 の役割分担（LabVIEW vs CANalyzer）を検討する際に反映する。

#### 残る未確定事項（dbc 入手待ち）

- 各信号（カウンタ・チェックサム含む）の**ペイロード内バイト/ビット位置**（CAPLは信号名でしか
  参照しておらず、位置情報は dbc 側にある）
- 各メッセージの **DLC（ペイロード長）**
- CAPL中の enum 名（`eID03AD5D62` 等）と**実際の16進CAN ID**の対応（dbcのメッセージ定義で確認）

dbc 入手後、この2つを組み合わせれば `CAN_Alive_Checksum_Calc.vi`・`CAN_Send_Alive_Frame.vi`
（9.9 記載）をそのまま完成させられる。
