# 10. RAMScope（GT170）実装方針

RAMScope（GT170、CAM モジュール付）で **RAM の計測** と **CAN 操作** を LabVIEW から行うための
実装方式を比較・選定する。

## 10.0 前提知識：「API」「DLL」「LabVIEW」はどういう関係か

以降の章では「API 仕様書」「DLL」「CLFN」といった言葉が頻出するため、
実装に入る前に、これらが何であり、なぜこの組み合わせで LabVIEW から RAMScope を
動かせるのかを整理しておく。

### そもそも RAMScope はどうやって PC から制御されるのか

RAMScope 本体（ハードウェア）は USB でPCに接続される。しかし USB でつながっているだけでは、
PC 上のどんなソフトからも自由に「測定開始」「データ取得」のような命令を送れるわけではない。
そこで RAMScope の製造元（DTS インサイト）は、次の2点セットを提供している。

```
[ RAMScope ハードウェア ]
        │  USB
        ▼
[ RAMScopeVP_API.dll / GT170.dll 等 ]  ← ①DLL本体（機械語の塊。実際の通信処理はここが行う）
        ▲
        │  CLFN（Call Library Function Node）で関数を呼ぶ
        │
[ LabVIEW の VI（ブロックダイアグラム） ]
        │
        ▼
[ TestStand シーケンス ]
```

### ① DLL（Dynamic Link Library）とは何か

DLL は、あらかじめコンパイルされた**機械語の実行コード**を1つのファイルにまとめたもの。
中身は「USB 経由で RAMScope と通信し、測定を開始・停止し、データを読み出す」といった
処理そのもの（C/C++ 等で書かれ、コンパイル済み）。

- DLL 単体は「ブラックボックスの部品」。中でどう処理しているかはソースコードが無い限り分からない。
- しかし Windows の仕組み上、DLL は「この名前の関数を、これこれの引数で呼べますよ」という
  **入り口（エクスポート関数）** を外部に公開している。
- 別のプログラム（今回でいう LabVIEW）は、その入り口の名前と引数の形さえ分かれば、
  DLL の中身を知らなくても関数を呼び出し、結果を受け取れる。

### ② API（Application Programming Interface）とは何か

API は DLL が公開している「呼び出せる関数の一覧とその仕様（関数名・引数の型と順序・戻り値・
呼び出す順序・エラーコード）」という**取り決め（仕様）そのもの**を指す。

- DLL ＝ 実体（機械語のファイル）
- API 仕様書 ＝ その実体をどう呼べばよいかを説明した**取扱説明書**

今回入手した「RAMScopeVP API 仕様書」には、`RAMScopeGT150DeviceInit()` のような
関数の宣言（C言語の書式）・引数の意味・呼び出し順序・エラーコードが記載されている。
本ドキュメント（10.4.2a 以降）で各関数のプロトタイプや構造体を1つずつ確定させているのは、
この仕様書の内容を LabVIEW が理解できる形（後述の CLFN 設定）に翻訳する作業に相当する。

### ③ なぜ LabVIEW からその DLL を呼び出せるのか（CLFN の役割）

LabVIEW は本来グラフィカルにワイヤーをつないでプログラムを組む環境であり、
C言語で書かれた外部の DLL を直接は理解できない。そこで LabVIEW には
**Call Library Function Node（CLFN）** という特別なノードが用意されている。

CLFN は「任意の Windows DLL の、任意のエクスポート関数を、指定した引数の型・順序・
呼び出し規約で呼び出す」ための汎用的な橋渡し役。CLFN の設定ダイアログに

- DLL のファイルパス
- 呼び出したい関数名（例：`RAMScopeGT150DeviceInit`）
- 各引数の型（`long` → I32、`long*` → Pointer to Value 等）と入出力方向
- 呼び出し規約（`__stdcall` か `__cdecl` か。ただし 64bit では区別なし）

を人間が仕様書を読んで正しく設定してやることで、LabVIEW のブロックダイアグラム上から
あたかも普通の VI を呼ぶのと同じ感覚で、RAMScope の DLL 内の処理（＝ハードウェア制御）を
直接実行できるようになる。**つまり LabVIEW 側に "RAMScope専用の機能" が元から
入っているわけではなく、CLFN という汎用のリモコンを使って、外部 DLL の力を借りている**
というのが実態である。

### ④ なぜ「手動での解読」が必要なのか（`.h`・サンプルが無い今回のケース）

多くのメーカーは、DLL・API仕様書に加えて `.h`（ヘッダファイル：関数プロトタイプや
構造体定義がそのままコードとして書かれたファイル）やサンプルプログラムを同梱しており、
その場合はほぼコピー＆ペーストで CLFN の型を決められる。

今回は `.h` やサンプルが同梱されておらず、**PDF形式の API 仕様書に書かれた
関数宣言・構造体定義の「表」を読み取って、人力で CLFN の設定値に変換する必要がある**。
これが 10.4 章以降で行っている「関数プロトタイプの確定」「構造体のバイトオフセット計算」
「エラーコード表の整理」の作業の目的である。

### ⑤ 32bit / 64bit の不一致が問題になる理由

DLL も LabVIEW も、実行時には Windows 上で「32bit 版のプログラムとして動くか、
64bit 版のプログラムとして動くか」のどちらかに固定されている。
**32bit のプログラムは 64bit の DLL を、64bit のプログラムは 32bit の DLL を
直接メモリ上に読み込めない**（CPU 命令の解釈やメモリ番地の扱いが根本的に異なるため）。

今回、開発環境の LabVIEW が 64bit 版であるのに対し、入手した RAMScope の DLL が
32bit 版であることが判明した（10.6 章「重大な問題」参照）。これは CLFN の設定を
どれだけ正しく行っても解決できない、**アーキテクチャレベルの制約**であるため、
32bit 版 LabVIEW を使うか、64bit 版 DLL の提供を受けるかのいずれかで解消する必要がある。

## 10.1 実装方式の候補

### 方式1：RAMScope の API を呼び出す
- **メリット**：費用がかからない（**DLL の使用は無償**）。
- **デメリット**：**DLL の解読・ラップが必要**（関数仕様の把握、引数・戻り値の型解析）。
- LabVIEW からは **Call Library Function Node（CLFN）** で DLL を呼び出す。
- **DLL 仕様は入手可能（確定）**：DTS インサイト提供の **RAMScopeVP API** を使用する。
  - 適用範囲：**RAMScope-EXG（GT170）**、RAMScope-EX（GT150, GT121/122）。本システムは GT170 で該当。
  - 付属物：**DLL 本体／ハードウェア制御用 API 外部仕様書／インクルードファイル（.h）／サンプルプログラム**。
  - 格納場所（既定）：
    - `C:\DTSinsight\RAMScopeVP_API\lib`（RAMScopeVP **Rev.1.15.00 以降**）
    - `C:\YDC\RAMScopeVP_API\lib`（**Rev.1.15.00 未満**）
  - **DLL の使用は無償。ただし API のサポートは有償**
    （窓口：DTS インサイト RAMScope お問い合わせ `support-mvi@dts-insight.co.jp`）。
  - → 外部仕様書・ヘッダ・サンプルが揃うため、**方式1 の実装は現実的**。具体手順は 10.4 を参照。

### 方式2：マックシステムズのドライバを使用する
- **メリット**：RAMScope の機能を **簡単に LabVIEW で利用** できる（一番早い）。
- **デメリット**：**費用が高額の可能性**。**CAN 操作が可能かは要確認**。

## 10.2 比較表

| 観点 | 方式1：API(DLL) 直叩き | 方式2：マックシステムズ製ドライバ |
|------|------------------------|-----------------------------------|
| 費用 | かからない | 高額の可能性 |
| 実装難易度 | 高（DLL 解読） | 低（提供 VI を使う） |
| 開発期間 | 長い | 短い（最速） |
| RAM 計測 | 可（仕様解読次第） | 可 |
| CAN 操作 | 可（API にあれば） | **要確認** |
| 保守性 | 自前依存 | ベンダ依存 |

## 10.3 選定の進め方（推奨）

1. **まず情報収集**
   - マックシステムズ製ドライバの **価格・対応機能（特に CAN 操作可否）・対応 LabVIEW バージョン** を確認。
   - RAMScope API（DLL）の **関数仕様書／ヘッダの入手可否** を確認。
2. **判断基準**
   - ドライバで CAN 操作まで賄え、費用が許容範囲 → **方式2（最速・確実）**。
   - 費用を抑えたい／DLL 仕様が入手でき解読可能 → **方式1**。
3. **方式1を採る場合の検証**
   - DLL のエクスポート関数を確認（依存関係ツール等）。
   - 1 関数（例：初期化・1 変数読み出し）を CLFN で呼べることを PoC で実証。
   - 呼べれば、本資料の VI 群（`RAMScope_Init/Log_Start/Read/Stop/Reset`）を実装。

## 10.4 Call Library Function Node（CLFN）実装手順（方式1）

RAMScopeVP API（DLL）を **Call Library Function Node（CLFN）** で呼び出し、
本資料の RAMScope VI 群（`RAMScope_Init/Log_Start/Read/Log_Stop/Reset` 等）として実装する手順。

### 10.4.1 STEP0：入手物の確認と準備

`RAMScopeVP_API\lib`（10.1 の格納場所）の中身を確認する。

| 入手物 | 用途 | 入手状況 |
|--------|------|---------|
| **DLL 本体**（`*.dll`） | CLFN から呼び出す実体 | **✅ 入手済み** |
| **API 外部仕様書** | 関数一覧・呼び出し順序・引数/戻り値・エラーコード | **✅ 入手済み**（確認中） |
| **インクルードファイル（`*.h`）** | 関数プロトタイプ・構造体・定数の正確な定義 | ❌ 未同梱（要対応→下記） |
| **サンプルプログラム（C 等）** | 正しい呼び出し順序・引数の渡し方の実例 | ❌ 未同梱（要対応→下記） |

> **`.h` ／サンプルが同梱されていない場合の対処**
> - 関数プロトタイプは **API 外部仕様書の「関数宣言」表**から読み取れる（C 言語宣言がそのまま掲載）。
>   仕様書が手元にあれば `.h` なしで CLFN 設定は可能。
> - 構造体のパディング問題は、**仕様書のメンバ列と `long`/`short` 等のサイズから手動計算**するか、
>   PoC で実測して確認する。
> - サンプルが必要な場合は **DTS インサイトサポート**（`support-mvi@dts-insight.co.jp`）に依頼、
>   または API 仕様書の「発行タイミング」節の呼び出しフローを参照する。

**確認済み DLL ファイル構成**（実機から確認）：

| ファイル | 役割 |
|----------|------|
| `RAMScopeVP_API.dll` | RAMScopeVP API 本体（CLFN から直接呼ぶ） |
| `GT150.dll` / `GT170.dll` / `GT170USB.dll` | 機種別ハードウェア制御（`RAMScopeVP_API.dll` が内部で使用） |
| `PGTMgrVP.dll` / `PGTMgrVP_ENG.dll` | 管理モジュール |
| `mfc140u.dll` / `msvcp140.dll` / `vcruntime140.dll` | Visual C++ ランタイム（依存）|
| `utillc.dll` | ユーティリティ |
| `pgtlib\` フォルダ | ライブラリ補助ファイル |

準備：
1. **対象 PC に RAMScopeVP（API）をインストール**し、DLL のフルパスを確定。
2. DLL の **ビット数（32bit / 64bit）を確認**（後述 10.4.6。最重要）。
   → ✅ **解決済み**：当初入手した DLL は32bitで64bit LabVIEWとアーキテクチャ不一致だったが、
   　 その後 **64bit版DLLを入手済み**（10.4.10 STEP0参照）。以降はこの64bit DLLを前提に進める。
3. 依存 DLL・必要ランタイムの有無を確認（仕様書／`Dependencies` 等のツール）。

### 10.4.2 STEP1：仕様の読み解き（実装前の机上作業）

CLFN を置く前に、外部仕様書とヘッダから次を表にまとめる（これが解読の本体）。

1. **関数一覧とライフサイクル**（→ 10.4.2a で確認済み分を記載）。
2. **各関数のプロトタイプ**：戻り値型・引数型・引数の入出力方向（in / out）・
   呼び出し規約マクロ（`WINAPI`/`__stdcall` か `__cdecl` か）。
3. **データ型の対応付け**：整数サイズ（`int`/`unsigned long`/`short` 等）、ポインタ、文字列、
   構造体、配列（RAM 値バッファ）を LabVIEW 型へどう写すか（10.4.4・10.4.5）。
4. **定数の洗い出し**：エラーコード、動作モード値、RAM 型（符号/サイズ）等の `#define`/`enum`
   → LabVIEW 側の定数表／Enum 型定義にして可読化。

#### 10.4.2a 確認済み API 仕様（仕様書スクリーンショットより）

**関数プレフィックスの規則**：
- `RAMScopeGT150*`：全機種共通（GT150/GT17x/GT12x 全てに適用）
- `RAMScopeGT170*`：GT170 固有機能（RAM 計測条件設定・CAN 操作 等）

**GT150_IF 完全関数一覧（確定）：**

```
■システム系
  RAMScopeGT150DeviceInit()          6.2  接続デバイス初期化（オフライン→アイドル）
  RAMScopeGT150DeviceExit()          6.3  接続デバイス終了（アイドル→オフライン）
  RAMScopeGT150AllInit()             6.4  初期化処理（設定全クリア。測定/アイドル→アイドル）
  RAMScopeGT150GetSysInfo()          6.5  システム情報取得（アイドルのみ可）
  RAMScopeGT150SetMdlConfig()        6.6  モジュール構成設定 ★非推奨→PGT版を使うこと
  RAMScopeGT150PGT_SetMdlConfig()    6.7  モジュール構成設定（PGT使用）★推奨版
  RAMScopeGT150PGT_ModifyMdlConfig() 6.8  モジュール構成編集（PGT使用）

■測定制御
  RAMScopeGT150MeasStart()           6.9  測定開始処理（アイドル→測定中）★確定
  RAMScopeGT150MeasStop()            6.10 測定停止処理（測定中→アイドル）★確定

■測定設定
  RAMScopeGT150SetMeasCond()         6.11 測定条件設定（GT150基本版）
  RAMScopeGT150SetMeasCondEx()       6.12 測定条件拡張設定
  RAMScopeGT170SetMeasCond()         6.13 測定条件設定（GT170専用版）★GT170では本関数を使う
  RAMScopeGT150SetMeasCh()           6.14 測定チャネル設定（GT150基本版）
  RAMScopeGT170SetMeasCh()           6.15 測定チャネル設定（GT170専用版）★GT170では本関数を使う
  RAMScopeGT150SetLoggingInfo()      6.16 ロギング情報設定処理
  RAMScopeGT150ReleaseBufferData()   6.17 測定データ解放処理（読み出し後に呼ぶ）

■イベント/トリガ設定
  RAMScopeGT150SetEventCond()        6.18 イベント設定（GT150版）
  RAMScopeGT170SetEventCond()        6.19 イベント設定（GT170専用版）
  RAMScopeGT150SetriggerRange()      6.20 ロギングトリガ範囲設定
  RAMScopeGT150SetriggerPoint()      6.21 ロギングトリガポイント設定
  RAMScopeGT150SetExternalTrigger()  6.22 外部トリガ設定（GT150版）
  RAMScopeGT170SetExternalTrigger()  6.23 外部トリガ設定（GT170専用版）
  RAMScopeGT170SetMeasTrigger()      6.24 測定トリガ設定（GT170専用）

  RAMScopeGT150GetBufferData()       6.29 データ読み出し★プロトタイプ確定

■RAM書き込み/CAN（GT170専用）
  RAMScopeGT170ScenarioWriteStart()  6.36
  RAMScopeGT170ScenarioWriteStop()   6.37
  RAMScopeGT170SendCANDataFrame()    6.39
  RAMScopeGT170ScenarioSendSet()     6.40
  RAMScopeGT170ScenarioSendStart()   6.41
  RAMScopeGT170ScenarioSendStop()    6.42
  RAMScopeGT170SetAdcRange()         6.44
```

**呼び出しライフサイクル（確定・ベンダー提供サンプル `samp_simple.cpp` で完全一致確認済み）：**

```
[オフライン]
    ↓ RAMScopeGT150DeviceInit()                     ← USB接続・ハードウェア検出
[アイドル]
    ↓ RAMScopeGT150AllInit(UnitNo=0)                ← API+HW初期化（設定全クリア）
    ↓ RAMScopeGT150GetSysInfo(UnitNo=0, buf[16])    ← モジュール構成・endian取得
    ↓ RAMScopeGT150PGT_SetMdlConfig(...)            ← プローブ接続情報設定（必須！）
    ↓ RAMScopeGT170SetMeasCond(0, MdlNo, *MEASINFO) ← 測定条件（モジュール毎に発行）
    ↓ RAMScopeGT170SetMeasCh(...)                   ← チャネル設定
    ↓ RAMScopeGT150SetLoggingInfo(...)              ← ロギング設定（必須！MeasStart前に）
    ↓ RAMScopeGT150MeasStart(UnitNo=0)             ← 測定開始
[測定中]
    ↓ RAMScopeGT150GetBufferData(...)               ← データ読み出し（★確定）
    ↓ RAMScopeGT150MeasStop(UnitNo=0)              ← 測定停止
[アイドル]
    ↓ (RAMScopeGT150GetLoggingData(...))            ← 保持済みデータの追加取得（サンプルではMeasStop後に発行）
    ↓ RAMScopeGT150DeviceExit()                    ← 接続破棄
[オフライン]
```

> **GT170 での関数選択ルール**：
> - 測定条件・チャネル・トリガ設定：GT170専用版（`RAMScopeGT170*`）を使う
> - ライフサイクル・測定開始停止・バッファ解放：GT150共通版（`RAMScopeGT150*`）を使う
> - GT150_IF 共通関数は GT170 でも必須（ライフサイクル管理の主体）。

> **`SetMdlConfig` の注意**：`RAMScopeGT150SetMdlConfig()` は非推奨。
> **`RAMScopeGT150PGT_SetMdlConfig()`（PGT使用版）を使うこと**。

### 10.4.2d ベンダー提供サンプルコード（`samp_simple.cpp`）による検証結果

DTS インサイト提供の実サンプル（[docs/reference/samp_simple.cpp](./reference/samp_simple.cpp)、
「Simple sample for RAMScopeVP API」、対象構成は `GT170U01+GT171M01`）を入手し、
これまでの記述内容を検証した。**呼び出し順序・引数の与え方は 10.4.2a のライフサイクル図と完全一致**。
以下、サンプルから新たに読み取れた実装上の重要ポイントをまとめる。

**① DLL のロード方式（`GetProcAddress` 方式）：**
```c
HINSTANCE Inst = ::LoadLibraryEx(L".\\RAMScopeVP_API.dll", 0, 0);
RAMScopeGT150DeviceInitPtr GT150DeviceInitFunc =
    (RAMScopeGT150DeviceInitPtr)::GetProcAddress(Inst, "RAMScopeGT150DeviceInit");
```
ヘッダの関数ポインタ型定義（`typedef long (*XxxPtr)(...)`）は、この
`LoadLibraryEx` + `GetProcAddress` パターンで使うための型であることが確定した。
**LabVIEW の CLFN は内部で同様に「DLL パス＋エクスポート関数名」を指定して直接呼び出す**ため、
この構造は CLFN 利用上の障害にはならない（GetProcAddress 相当の処理は CLFN が自動で行う）。

**② `MdlNo` の実例：RAM モジュールは `MdlNo=1`（`0` ではない）**

サンプルでは `SetMeasCond(0, 1, &GTMeasInfo)`・`SetMeasCh(0, 1, 1, GTChInfo)`・
`GetBufferData(0, 1, ...)`・`GetLoggingData(0, 1, 0, 0, ...)` と、一貫して
**`MdlNo=1`** を使っている。`UnitNo` は常に `0` だが、`MdlNo` は
`GetSysInfo` で取得した `SYSINFO[].module` の実際の値（環境依存）を使う必要があり、
本サンプルの構成（`GT170U01+GT171M01`）では RAM モニタモジュールが `module=1` だったと分かる。
**`MdlNo` を `0` 固定にしないこと**（`UnitNo` と混同しないよう注意）。

**③ `SetMeasCh` の `ChNum` 引数の意味＝チャンネル「個数」**
```c
CHINFO_170 GTChInfo[1];   // 要素数1の配列
memset(GTChInfo, 0, sizeof(CHINFO_170)*1);
GTChInfo[0].RAM.enable  = 1;
GTChInfo[0].RAM.address = 0x1000;
GTChInfo[0].RAM.size    = 0;
GTChInfo[0].RAM.sign    = 0;
GT170SetMeasChFunc(0, 1, 1, GTChInfo);   // (UnitNo, MdlNo, ChNum, pChInfo)
```
第3引数 `ChNum` は「配列 `pChInfo` の要素数（設定するチャンネル数）」であり、
特定のチャンネル番号を指すインデックスではないことが確定した。
複数チャンネル設定時は `CHINFO_170` 配列を必要数分確保し、`ChNum` にその個数を渡す。
また `CHINFO_RAM170` の `core`・`speed` フィールドはサンプルでは未設定（0 のまま）であり、
最低限 `enable`／`address`／`size`／`sign` の設定で動作する模様。

**④ `LOGINFO.mdl[]` は使用モジュール以外も含めて全要素を初期化する**
```c
for (int i = 0; i < NUM_MODULE_MAX_170; i++) {
    GTLogInfo.mdl[i].BuffSize = 1;
    GTLogInfo.mdl[i].logSize  = 1;
}
```
サンプルは使用する `MdlNo=1` だけでなく、**GT170 の最大モジュール数（`NUM_MODULE_MAX_170=10`）分すべて**
`BuffSize`/`logSize` に `1` を設定してから `SetLoggingInfo` を呼んでいる。
未使用モジュールも含め全スロットを最低値で初期化しておくのが安全な実装パターン。

**⑤ 🔴 実装上の注意：`GetBufferData` の `pDataNum` 事前設定について（サンプルの矛盾点）**
```c
long GTDataNum;       // ローカル変数、初期化されていない
long GTLostDataNum;
...
GT150GetBufferDataFunc(0, 1, GTPackData, &GTDataNum, &GTLostDataNum);
```
仕様書では `pDataNum` は **in/out**（呼び出し前に要求パケット数を書き込む）と説明されているが、
本サンプルでは `GTGetBufferData` 呼び出し直前に `GTDataNum` を**明示的に初期化していない**
（ローカル変数の不定値のまま渡している）。一方、後段の `GetLoggingData` 呼び出しでは
```c
GTDataNum = 100;   // ← こちらは明示的に設定している
GT150GetLoggingDataFunc(0, 1, 0, 0, GTPackData, &GTDataNum, &GTLostDataNum);
```
と正しく初期化しており、**同一サンプル内で扱いが一貫していない**。
`GetBufferData` 側の書き方はサンプルの単純化・省略の可能性が高く、**そのまま真似ることは推奨しない**。
LabVIEW 実装では **必ず `pDataNum` に「バッファが受け止められる最大パケット数」を明示的に
書き込んでから呼び出す**こと（`GTPackData` のようなバッファサイズ ÷ 1パケットサイズ で計算した
安全な上限値を使う）。

**⑥ `ReleaseBufferData` はこの簡易サンプルでは呼ばれていない**
サンプルは `GetLoggingData` の直後に `DeviceExit()` を呼んでおり、`ReleaseBufferData()` を
経由していない。10.4.2a のライフサイクル図で必須ステップとしていたが、少なくとも
簡易な単発測定シーケンスでは省略可能な可能性がある（`DeviceExit` が内部で解放処理を
兼ねている可能性）。ただし正式な用途・必須性は仕様書 6.17 章の本文で別途確認が望ましい。

**⑦ 呼び出し規約について（`samp_simple.vcxproj` の確認により `__cdecl` の可能性が高いと判明）**

ベンダー提供のプロジェクト設定ファイル（[docs/reference/samp_simple.vcxproj](./reference/samp_simple.vcxproj)）を
確認したところ、以下が判明した。

- **`ProjectConfigurations` は `Debug|Win32` と `Release|Win32` のみ**。x64 構成は存在しない
  （ファイルの更新日時が新しかったのは `PlatformToolset` を `v143`＝Visual Studio 2022 に
  上げただけで、ビット数とは無関係。**32bit 専用というこれまでの結論を追認**）。
- `<ClCompile>` 設定に **呼び出し規約を明示的に上書きする指定（`/Gz` 等）が存在しない**。
  ヘッダ・サンプル・プロジェクト設定のいずれにも `__stdcall`／`WINAPI` のキーワードが
  一切登場しないことと合わせ、**MSVC のデフォルト規約である `__cdecl` でビルドされている
  可能性が高い**と判断できる。

> ⚠️ ただし、これは**サンプル側（呼び出し元 exe）のビルド設定**であり、
> `RAMScopeVP_API.dll` 自体を DTS インサイトがどの規約でビルドしたかを直接証明するものではない。
> 一般的に、同一ベンダーが両方のプロジェクトで規約を明示的に変えるケースは考えにくいため、
> **`__cdecl` を最有力候補として CLFN の Calling Convention 設定を試す**ことを推奨する。
> 呼び出し規約の指定を誤った場合、コンパイル時エラーにはならず
> **実行時にスタック破壊で不定動作（クラッシュ等）になる**タイプの問題のため、
> 最終的には **実機での動作確認による実証が必要**。
> 64bit 版 DLL が入手できれば、この論点自体が消滅する（10.6 参照。x64 ABI には規約の区別がない）。
> AllInit + GetSysInfo 後、測定条件設定の前に発行する。`endian` は GetSysInfo の結果を渡す。

**確認済み関数プロトタイプ：**

```c
/* 接続デバイス初期化（6.2章）：オフライン→アイドル */
long RAMScopeGT150DeviceInit(
    long  *pUnitNum,   /* [out] 接続成功台数（現仕様では常に 1） */
    long  *kind        /* [out] 機種コード：0=GT150, 1=GT12x, 2=GT17x */
);

/* 初期化処理（6.4章）：アイドル/測定中→アイドル。設定を全クリア */
long RAMScopeGT150AllInit(
    long  UnitNo       /* [in]  発行対象ユニット（現仕様では常に 0） */
);

/* システム情報取得（6.5章）：アイドルのみ可 */
long RAMScopeGT150GetSysInfo(
    long     UnitNo,      /* [in]  発行対象ユニット（現仕様では常に 0） */
    SYSINFO  *pSysInfo    /* [out] SYSINFO 型、要素数 16 の配列先頭ポインタ */
);

/* 接続デバイス終了（6.3章） */
long RAMScopeGT150DeviceExit(
    void
);

/* 測定開始処理（6.9章）：アイドル→測定中。SetLoggingInfo完了後に発行 */
long RAMScopeGT150MeasStart(
    long  UnitNo    /* [in] 常に 0 */
);

/* 測定停止処理（6.10章）：測定中→アイドル。MeasStop でシナリオ書き込み/送信も同時停止 */
long RAMScopeGT150MeasStop(
    long  UnitNo    /* [in] 常に 0 */
);

/* ---- 測定データ取得 API（表6-5 GT150_IF 一覧より確定）---- */
/* RAMScopeGT150GetGapTime()        6.25章 測定開始時間取得処理  */
/* RAMScopeGT150GetMeasNum()        6.26章 測定回数取得処理      */
/* RAMScopeGT150GetBlockNum()       6.27章 ブロック取得処理      */
/* RAMScopeGT150GetBufferDataNum()  6.28章 最新データ数取得処理  */
/* RAMScopeGT150GetBufferData()     6.29章 最新データ取得処理    ← ★引数は6.29章で要確認 */
/* RAMScopeGT150GetLoggingDataNum() 6.30章 測定データ数取得処理  */
/* RAMScopeGT150GetLoggingData()    6.31章 測定データ取得処理    */

/* 測定条件設定・GT170専用版（6.13章）：モジュール別に発行 */
long RAMScopeGT170SetMeasCond(
    long           UnitNo,       /* [in] 常に 0 */
    long           MdlNo,        /* [in] SYSINFO.module の値（モジュール番号）*/
    MEASINFO_170   *pMeasInfo    /* [in] 測定条件 union ポインタ（下記 MEASINFO_170 参照）*/
);
```

**MEASINFO_170 共用体・構造体定義（`SetMeasCond` 用、表 6-74〜6-76／`.h` ヘッダで完全一致確認済み）：**

> 🔴 **ヘッダファイル（`RAMScopeVP.h`、[docs/reference/RAMScopeVP.h](./reference/RAMScopeVP.h)）入手により、
> 以下 2 点の誤りが判明・修正済み：**
> 1. `MEASINFO_RAM170.MeasPeri_reserve` は単一の `long` ではなく **`long MeasPeri_reserve[2]`（配列）**。
>    サイズは 16 バイトではなく **20 バイト**が正しい。
> 2. `MEASINFO_CAN170.isUseFDFormat` は `char` ではなく **`long`（4バイト）**。
>    そのため **パディングは発生しない**（旧記述の「3バイトパディング」は誤り）。
>    union 全体のサイズは偶然にも変わらず 72 バイト（後述）。

```c
/* 共用体：モジュール種別に応じたメンバを使う */
typedef union MEASINFO_170 {
    MEASINFO_RAM170  RAM;   /* RAMモニタモジュール用（module_type=0x00） */
    MEASINFO_ADC170  ADC;   /* アナログ入力モジュール用（module_type=0x03。旧記述の 0xE は誤り。GTHard.h で確定）*/
    MEASINFO_CAN170  CAN;   /* CAN モジュール用（module_type=0x02） */
} MEASINFO_170;

/* RAM モニタモジュール用（表 6-75。.h では MeasPeri_reserve[2] の配列） */
typedef struct MEASINFO_RAM170 {
    long DummyInterval;         /* [将来拡張用] ダミーパケット生成周期(usec)。常に 100 を指定 */
    long MeasPeri;              /* 測定周期：1〜999999 */
    long MeasUnit;               /* 測定周期の単位：1=usec / 2=msec */
    long MeasPeri_reserve[2];   /* [将来拡張用] 要素数2の配列。現版数では常に {1, 0} 等を指定（詳細仕様書要再確認）*/
} MEASINFO_RAM170;
/* サイズ = long×3 + long[2] = 12 + 8 = 20 バイト（.h ヘッダで確定） */

/* アナログ入力モジュール用（表 6-76）*/
typedef struct MEASINFO_ADC170 {
    long DummyInterval;      /* ダミーパケット生成周期(usec)。常に 100 を指定 */
    long MeasPeri;           /* 測定周期：1〜999999 */
    long MeasUnit;           /* 測定周期の単位：1=usec / 2=msec */
} MEASINFO_ADC170;
/* サイズ = long×3 = 12 バイト */

/* CAN モジュール用（表 6-77。.h では isUseFDFormat は long） */
typedef struct MEASINFO_CAN170 {
    long             DummyInterval;  /* [将来拡張用] ダミーパケット生成周期(usec)。常に 100 */
    long             isUseFDFormat;  /* パケットフォーマット：0=CAN 2.0B(GT150互換) / 1=CAN FD(推奨) */
    MEAS_CAN_CH_170  Ch[2];          /* 物理 Ch 毎の設定（Ch[0]=Ch1, Ch[1]=Ch2）*/
} MEASINFO_CAN170;
/* サイズ = 4(long) + 4(long) + 32×2(Ch[2]) = 72 バイト（パディングなし・.h ヘッダで確定） */

typedef struct MEAS_CAN_CH_170 {
    long Enable;        /* CAN Ch 有効無効：0=無効 / 1=有効 */
    long Terminate;     /* バスターミネータ挿入：0=挿入なし / 1=挿入あり */
    long MonitorOnly;   /* 受信パケット応答：0=Ack応答（通常通信）/ 1=応答なし（モニタのみ） */
    long BaudRate;      /* CAN 2.0B ボーレート or CAN FD アービトレーションレート：
                           0x7=125kbps / 0x8=250kbps / 0x9=500kbps / 0xA=1Mbps / 0xB=800kbps */
    long BaudRateHigh;  /* CAN FD データレート（FD のみ有効）：
                           0x1=1Mbps / 0x2=2Mbps / 0x4=4Mbps / 0x5=5Mbps / 0x8=8Mbps */
    long SmpCnt;        /* サンプリングポジション：0=60% / 1=65% / 2=70% / 3=75% / 4=80% */
    long SmpCntHigh;    /* FD データレート用サンプリングポジション（SmpCnt と同範囲）*/
    long BusMode;       /* バス動作モード：0=CAN 2.0B / 2=CAN FD(ISO) */
} MEAS_CAN_CH_170;
/* サイズ = long×8 = 32 バイト */
```

> **測定周期設定範囲（6.13.4節・確定）：**
> | モジュール | 周期設定範囲 |
> |-----------|-------------|
> | RAMモニタ | 5µsec 〜 65sec（MeasPeri + MeasUnit で指定）|
> | アナログ入力 | 1µsec 〜 65sec |
>
> **SmpCnt / SmpCntHigh の有効値（6.13.5節 表6-80）：**
> BaudRateHigh によって指定できる値が異なる（BusMode=2 の CAN FD のみ適用）。
>
> | BaudRateHigh 指定値 | SmpCnt・SmpCntHigh に指定可能な値 |
> |---------------------|-----------------------------------|
> | 1（1Mbps）、2（2Mbps）、4（4Mbps）| 0(60%)、1(65%)、2(70%)、3(75%)、4(80%) |
> | 5（5Mbps） | 3(75%) のみ |
> | 8（8Mbps） | 0(60%)、2(70%)、4(80%) |
>
> ※ SmpCnt と SmpCntHigh には同じ値を指定すること。

> **互換性注記（6.13.7節）：**
> - `isUseFDFormat=1` → CAN FD フォーマット（GT170 推奨）
> - `isUseFDFormat=0` → GT150 互換フォーマット（CAN 2.0B）
> - **`isUseFDFormat=0` のとき `BusMode=0` 以外は設定エラーとなる**（CAN 2.0B 時は BusMode=0 固定）
> - CAN FD 使用時（`isUseFDFormat=1`）は `BusMode=2`（CANFD ISO）を指定すること

> **MEASINFO_170 union サイズ（`.h` ヘッダで確定・修正済み）：**
> - MEASINFO_RAM170 = **20 バイト**（旧: 16バイトは誤り。`MeasPeri_reserve[2]` の配列のため）
> - MEASINFO_ADC170 = 12 バイト
> - MEASINFO_CAN170 = **72 バイト**（最大。`isUseFDFormat` は long のためパディングなし）
> - **union サイズ = 72 バイト**（CAN が最大のまま。CLFN で確保する U8 配列のサイズ）

> **使い方例：**
> ```c
> /* RAM モニタの測定条件設定（module_type=0x0 のモジュールに対して発行）*/
> MEASINFO_170 info;
> memset(&info, 0, sizeof(info));
> info.RAM.DummyInterval       = 100;  // 固定
> info.RAM.MeasPeri            = 1000; // 1000 usec = 1ms 周期
> info.RAM.MeasUnit            = 1;    // 1=usec
> info.RAM.MeasPeri_reserve[0] = 0;    // [将来拡張用] 詳細仕様は仕様書側で要再確認
> info.RAM.MeasPeri_reserve[1] = 0;    // 同上
> RAMScopeGT170SetMeasCond(0, mdlNo_RAM, &info);
>
> /* CAN モジュールの測定条件設定（module_type=0x2 のモジュールに対して発行）*/
> memset(&info, 0, sizeof(info));
> info.CAN.DummyInterval    = 100;       // 固定
> info.CAN.isUseFDFormat    = 1;         // CAN FD フォーマット推奨（long型）
> info.CAN.Ch[0].Enable     = 1;         // Ch1 有効
> info.CAN.Ch[0].MonitorOnly= 1;         // モニタのみ（Ack なし）
> info.CAN.Ch[0].BaudRate   = 0x9;       // 500kbps（対象バスに合わせる）
> info.CAN.Ch[0].BusMode    = 0;         // CAN 2.0B（isUseFDFormat=0時は必ず0）
> RAMScopeGT170SetMeasCond(0, mdlNo_CAN, &info);
> ```

> **CLFN での union の扱い（`.h` ヘッダで確定・修正済み）**：
> LabVIEW では **`Initialize Array`（U8 配列、72 要素）** を確保して各フィールドを
> バイト順に埋め（`Insert Into Array` / 直接配線）、`Array Data Pointer` で渡す。
> フィールドのオフセット計算は下記の通り（little-endian, 32bit long 前提。**パディングなし**）：
>
> | フィールド | オフセット | サイズ |
> |-----------|-----------|--------|
> | DummyInterval（RAM/ADC/CAN 共通先頭）| 0 | 4 |
> | RAM: MeasPeri | 4 | 4 |
> | RAM: MeasUnit | 8 | 4 |
> | RAM: MeasPeri_reserve[0] | 12 | 4 |
> | RAM: MeasPeri_reserve[1] | 16 | 4 |
> | CAN: isUseFDFormat（long, 修正済み）| 4 | 4 |
> | CAN: Ch[0].Enable | 8 | 4 |
> | CAN: Ch[0].Terminate | 12 | 4 |
> | CAN: Ch[0].MonitorOnly | 16 | 4 |
> | CAN: Ch[0].BaudRate | 20 | 4 |
> | CAN: Ch[0].BaudRateHigh | 24 | 4 |
> | CAN: Ch[0].SmpCnt | 28 | 4 |
> | CAN: Ch[0].SmpCntHigh | 32 | 4 |
> | CAN: Ch[0].BusMode | 36 | 4 |
> | CAN: Ch[1].Enable | 40 | 4 |
> | （以降 Ch[1] メンバが +8〜+68）| … | … |
>
> ※ CAN のオフセットは isUseFDFormat のサイズ変更後も偶然一致（char+padding=4byte 相当だったため）、
> 　旧版からの変更なし。RAM 側のみ offset 12 以降が変わる点に注意。

**SYSINFO 構造体定義（`GetSysInfo` 用）：**

```c
typedef struct SYSINFO {
    long module;            /* モジュール番号 */
    long module_type;       /* モジュールタイプ（`GTHard.h` で確定）:
                               0x00=RAMモニタ / 0x02=CAN / 0x03=アナログ入力(AD) /
                               0x0E=電源通信(CTRL_USB) / 0x0F=非接続 */
    long probe_id;          /* 接続プローブID（RAMモニタのみ） */
    long interface_id;      /* 将来拡張用（値は不定） */
    long version;           /* FPGAバージョン番号 */
    long addinfo;           /* Firmwareバージョン番号 */
    long endian;            /* エンディアン：0=Big / 1=Little */
    long probe_version;     /* 接続プローブFPGAバージョン番号 */
    long security_id_req;   /* セキュリティID有無（0/1）*/
    long security_id_size;  /* セキュリティIDサイズ（security_id_req=1のみ有効）*/
    long flash_enable;      /* 将来拡張用（値は不定） */
    char name[16];          /* モジュール識別名称（RAMモニタ: プローブ識別名）*/
} SYSINFO;
/* サイズ = long×11 + char×16 = 44 + 16 = 60 バイト（アライン次第で確認要） */
/* GetSysInfo には要素数 16 の配列（= 16×60 = 960 バイト）を渡す */
```

> **CLFN での `GetSysInfo` の扱い**：`pSysInfo` は要素 16 の配列ポインタ。
> LabVIEW では **`Initialize Array`（サイズ 960 の U8 配列）** を先に確保して
> `Array Data Pointer` で渡し、後段で `Type Cast` / `Unflatten` して各フィールドを取り出す。

**関連定数一覧（`GTHard.h`、[docs/reference/GTHard.h](./reference/GTHard.h) に保存済み）：**

```c
/* DeviceInit() の kind 出力パラメータ（機種判定） */
#define TYPE_GTKIND_150   0   /* GT150 */
#define TYPE_GTKIND_12x   1   /* GT12x */
#define TYPE_GTKIND_170   2   /* GT170（本システムで使用）*/

/* SYSINFO.module_type（上記で確定・修正済み） */
#define TYPE_RAMMONITOR_MODULE   0x00
#define TYPE_CAN_MODULE          0x02
#define TYPE_AD_MODULE           0x03   /* アナログ入力。旧ドキュメントの「0xE相当」は誤り */
#define TYPE_CTRL_USB_MODULE     0x0E   /* 電源通信モジュール（GT170U01 等）*/
#define TYPE_MODULE_DISCONNECT   0x0F   /* 非接続 */

/* モジュール数上限（GetSysInfo/SlotErr が要素数16を使う理由 = 全機種共通の最大値）*/
#define NUM_MODULE_MAX       16   /* 全機種共通の配列サイズ（SYSINFO[16]、SlotErr[16] 等）*/
#define NUM_MODULE_MAX_150   5    /* GT150 の実際の最大モジュール数 */
#define NUM_MODULE_MAX_170   10   /* GT170 の実際の最大モジュール数（本システムで使用）*/

/* チャンネル数上限（SetMeasCh のループ回数の上限チェックに使用）*/
#define NUM_CH_MAX_RAM150   1024
#define NUM_CH_MAX_ADC150   6
#define NUM_CH_MAX_RAM170   2048  /* GT170 RAMモニタの最大チャンネル数 */
#define NUM_CH_MAX_ADC170   4     /* GT170 アナログ入力の最大チャンネル数 */
```

> `DeviceInit()` の `kind` 出力値（10.4.2a で `0=GT150, 1=GT12x, 2=GT17x` と記載済み）は
> この `TYPE_GTKIND_*` 定数と完全一致することが確定した。
> また `GetSysInfo`／`PGT_SetMdlConfig`／`ScenarioSendSet` 等で配列サイズ **16** を
> 一律使っていた理由は、`NUM_MODULE_MAX=16`（全機種共通の上限）を採用しているためと判明した
> （GT170 自体の実際の上限は `NUM_MODULE_MAX_170=10`）。

**MDLCFG 構造体定義（`SetMdlConfig` 用）：**

```c
typedef struct MDLCFG {
    long      scan_cycle;   /* 使用しません。0 を格納してください。*/
    long      jtag_clk;     /* デバッグIF動作クロックID（プローブ種別で異なる）(*1) */
    long      da_bit_width; /* 使用しません。0 を格納してください。*/
    long      da_ch_num;    /* 使用しません。0 を格納してください。*/
    long      da_type;      /* 使用しません。0 を格納してください。*/
    long      endian;       /* GetSysInfo() の pSysInfo[i].endian の値を格納 */
    long      ice_time_en;  /* 使用しません。0 を格納してください。*/
    long      ice_time;     /* 使用しません。0 を格納してください。*/
    MDLPSMCFG psm;          /* 固有情報（プローブごとの接続情報）(*1) */
} MDLCFG;
/* サイズ = long×8 + sizeof(MDLPSMCFG) */

typedef struct MDLPSMCFG {
    struct {
        unsigned long id[3];       /* セキュリティID（ターゲットマイコンのデバッグIF用）(*1)(*2) */
        unsigned long area[2][2];  /* 使用しません。0 を格納してください。*/
    } nexus_jtag;
    struct {
        unsigned char moe;         /* 使用しません。0 を格納してください。*/
        unsigned char mcd;         /* 使用しません。0 を格納してください。*/
    } nexus_aux;
    struct {
        unsigned long clk_high;    /* カスタム通信クロック設定（一部プローブのみ）(*1) */
        unsigned long clk_low;     /* 同上 */
    } serial;
} MDLPSMCFG;
/* (*1) 非公開情報：値は別途 DTS インサイトサポートへ請求 */
/* (*2) セキュリティID不要なマイコンでは 0 を設定 */
```

> `SetMdlConfig` は非推奨。代わりに **`PGT_SetMdlConfig()`** を使う。
> `PGT_SetMdlConfig()` は PGT ツールが生成する設定ファイルを読み込む方式のため、
> プローブ固有の非公開パラメータ（`jtag_clk` / `psm` 等）を自分で調べる必要がなくなる。

**`RAMScopeGT150PGT_SetMdlConfig` 関数仕様（6.7章・確定）：**

```c
/* モジュール構成設定処理（PGT使用）
   RAMモニタモジュール用のプローブ固有設定情報を RAMScope HW へ通知する。
   発行対象モジュール：RAMモニタ（API関数内自動定義）
   発行タイミング：AllInit・GetSysInfo の後、SetMeasCond の前 */
long RAMScopeGT150PGT_SetMdlConfig(
    long   UnitNo,    /* [in]  発行対象ユニット（将来拡張用。現仕様では常に 0）*/
    long   *SlotErr   /* [out] パラメータ通知時のエラー情報。モジュールごとに返す。
                               要素数 16 の配列を用意して先頭アドレスを渡す。
                               SlotErr[MdlNo] = 該当モジュールのエラー情報。
                               例）MdlNo=1 のエラーは SlotErr[1] に格納 */
);
```

> **LabVIEW CLFN での `PGT_SetMdlConfig` の扱い**：
> - `UnitNo` : I32（値 0）
> - `SlotErr` : `Initialize Array`（I32、16 要素）を確保 → `Array Data Pointer` で渡す
> - 各スロットの戻り値は `SlotErr[MdlNo]` の値で確認する（0 = 正常）

**MeasStart エラーコード（確認済み）：**

| 戻り値 | 意味 |
|--------|------|
| `0x00000000` | 正常終了 |
| `0x30000001` | 関数内部で例外を検出 |
| `0x30000004` | 測定動作状態で呼び出された |
| `0x30000109` | **ロギング情報が未設定**（`SetLoggingInfo` を先に呼ぶ） |
| `0x30000500` | UnitNo の指定値に誤り |
| `0x3000050E` | オフライン状態で呼び出された |

**MeasStop エラーコード（確認済み）：**

| 戻り値 | 意味 |
|--------|------|
| `0x00000000` | 正常終了 |
| `0x30000001` | 関数内部で例外を検出 |
| `0x30000105` | 測定処理スレッドの停止に失敗（DLL インスタンス破棄 + HW 電源 OFF） |
| `0x30000500` | UnitNo の指定値に誤り |
| `0x3000050E` | オフライン状態で呼び出された |

> **MeasStop でエラー（特に `0x30000105`）が出た場合**は、アプリの DLL インスタンスを
> 破棄して RAMScope ハードウェアの電源を OFF にすること（仕様書の指示）。
> TestStand の Cleanup ではこのエラーコードを別途ハンドリングする。

**`RAMScopeGT150GetBufferData` 関数仕様（6.29章・確定）：**

```c
/* 最新データ取得処理
   RAMScopeVP API 内部の表示用データバッファに保存されている測定データを
   パケット単位で取得する。
   発行対象モジュール：RAM モニタ / CAN / アナログ入力
   発行可否：オフライン=× / 測定中=○ / アイドル=○ */
long RAMScopeGT150GetBufferData(
    long   UnitNo,          /* [in]  発行対象ユニット（将来拡張用。現仕様では常に 0）*/
    long   MdlNo,           /* [in]  発行対象モジュールのモジュール番号 */
    void   *pData,          /* [out] 測定データの格納先。
                                     (*pDataNum) * パケットサイズ分の容量を持つ
                                     バッファの先頭アドレスを指定する */
    long   *pDataNum,       /* [in/out] 要求パケット数(In) / 取得パケット数(Out)。
                                     読み出し要求パケット数を格納した long 値への
                                     ポインタを指定する。関数の正常終了後、
                                     本引数には実際に読み出したパケット数を返す */
    long   *pLostDataNum    /* [out] 測定動作中に表示用データバッファがあふれた
                                     場合に、破棄したパケット数を返す */
);
```

> **注意・制限事項（6.29.3節）：**
> - 本関数の処理対象は `RAMScopeGT150SetLoggingInfo()` 関数で容量指定する **表示用データバッファ**。
> - 取得する測定データはロギングトリガの有効/無効・動作状況に影響を受けない。
> - パケットの構成は「7 測定データの構成」章を参照。
> - DLL から取得したデータは、表示用データバッファがあふれないよう、
>   **測定動作中に定期的に本関数を発行**すること（ポーリング必須）。
>
> **応答（6.29.5節）：**
> | 戻り値 | 意味 |
> |--------|------|
> | `0x00000000` | 正常終了 |
> | `0x30000001` | 関数内部で例外を検出 |
> | `0x30000005` | `MdlNo` の指定値に誤りがある |
> | `0x30000006` | （同上・詳細未記載）|
> | `0x30000500` | `UnitNo` の指定値に誤りがある |
> | `0x3000050E` | オフラインの状態で関数が呼び出された |
> | `0x30100001` | 下位 DLL 内に必要な処理が見つからない（DLL ファイルのバージョン確認）|

> **LabVIEW CLFN での `GetBufferData` の扱い**：
> - `UnitNo` : I32（値 0）
> - `MdlNo` : I32（対象モジュール番号）
> - `pData` : `void *` → **Array Data Pointer**（U8 配列、`要求パケット数 × パケットサイズ` バイト分を事前確保）。
>   パケットサイズはモジュール種別（RAM/CAN/ADC）ごとに「7 測定データの構成」章の定義に従う（別途確認要）。
> - `pDataNum` : **Pointer to Value I32**（in/out）。呼び出し前に要求パケット数を書き込み、
>   呼び出し後に実際の取得パケット数が上書きされる。
> - `pLostDataNum` : **Pointer to Value I32**（out）。バッファあふれで破棄されたパケット数。
> - `RAMScope_Read.vi` はループ内で本関数を定期ポーリングし、`pLostDataNum > 0` の場合は
>   ロギング設定の見直し（バッファ容量拡大 or ポーリング周期短縮）を検討する。

**AllInit エラーコード（確認済み）：**

| 戻り値 | 意味 |
|--------|------|
| `0x00000000` | 正常終了 |
| `0x30000001` | 関数内部で例外を検出 |
| `0x30000518` | （GT17x）対応不可なモジュール構成を検出 |
| `0x30100001` | 下位 DLL に必要な処理が見つからない（DLL バージョン確認） |
| `0x30000504` | ハードウェアとの通信に失敗 |
| `0x30000506` | 電源・USB 接続・ドライバ・発行手順を確認 |

**GT170 固有機能（機能別）：**

| カテゴリ | 関数名 | 章 | プロトタイプ・構造体 |
|---------|--------|-----|---------------------|
| 測定設定 | `RAMScopeGT170SetMeasCond()` | 6.13 | ✅ 確定（`.h`で修正2件反映済み）|
| 測定設定 | `RAMScopeGT170SetMeasCh()` | 6.15 | ✅ 確定（`.h`。`CHINFO_170`）|
| トリガ設定 | `RAMScopeGT170SetEventCond()` | 6.19 | ✅ 確定（`.h`。`EVENTINFO_170`）|
| トリガ設定 | `RAMScopeGT170SetExternalTrigger()` | 6.23 | ✅ 確定（`.h`。`EXTTRG_INFO_170`）|
| トリガ設定 | `RAMScopeGT170SetMeasTrigger()` | 6.24 | ✅ 確定（`.h`。`MEASTRG_INFO_170`）|
| RAM 書き込み | `RAMScopeGT170ScenarioWriteStart()` | 6.36 | ✅ 確定（`.h`。`WRITE_SCENARIO`）|
| RAM 書き込み | `RAMScopeGT170ScenarioWriteStop()` | 6.37 | ✅ 確定（`.h`）|
| **CAN 送信** | **`RAMScopeGT170SendCANDataFrame()`** | 6.39 | ✅ 確定（仕様書+`.h`一致）|
| **CAN シナリオ** | **`RAMScopeGT170ScenarioSendSet()`** | 6.40 | ✅ 確定（仕様書+`.h`一致）|
| **CAN シナリオ** | **`RAMScopeGT170ScenarioSendStart()`** | 6.41 | ✅ 確定（仕様書+`.h`一致）|
| **CAN シナリオ** | **`RAMScopeGT170ScenarioSendStop()`** | 6.42 | ✅ 確定（仕様書+`.h`一致）|
| アナログ入力 | `RAMScopeGT170SetAdcRange()` | 6.44 | ✅ 確定（`.h`）|

> 上記全関数の完全プロトタイプ・構造体定義は 10.4.2c 参照。

> **CAN 操作は RAMScopeVP API で確定**（`RAMScopeGT170SendCANDataFrame` / `ScenarioSend*`）。
> 10.6 の「未確定事項」から除去。

**`RAMScopeGT170SendCANDataFrame` 関数仕様（6.39章・確定）：**

```c
/* CAN データフレーム送信処理
   CAN モジュールから測定対象の CAN バスへデータフレームを送信する。
   発行対象モジュール：CAN */
long RAMScopeGT170SendCANDataFrame(
    long              UnitNo,      /* [in] 発行対象ユニット（将来拡張用。現仕様では常に 0）*/
    long              MdlNo,       /* [in] 発行対象モジュールのモジュール番号 */
    long              ChNo,        /* [in] データフレーム送信に使用する CAN モジュールの物理Ch番号。0=Ch1／1=Ch2 */
    CANSEND_170_INFO  *pSendInfo   /* [in] 送信情報を格納した CANSEND_170_INFO 型変数のポインタ */
);
```

**`CANSEND_170_INFO` / `CANSEND_170_DATA` 構造体定義（6.39.3章・表6-223、6-224）：**

```c
typedef struct CANSEND_170_INFO {
    long              IdFormat;    /* ID フォーマット：0=標準ID／1=拡張ID */
    long              Count;       /* 送信データフレーム数（1〜30）*/
    CANSEND_170_DATA  *pSendData;  /* 送信データフレーム情報。
                                       設定値を格納した CANSEND_170_DATA 型配列
                                       （要素数 Count）の先頭ポインタを渡す */
} CANSEND_170_INFO;

typedef struct CANSEND_170_DATA {
    unsigned long  DataLength;  /* 送信データ長。
                                    0〜8: 0〜8Byte／12:12Byte／16:16Byte／20:20Byte／
                                    24:24Byte／32:32Byte／48:48Byte／64:64Byte
                                    （CAN FD の非線形DLC対応値をそのままByte数で指定）*/
    unsigned long  CanID;       /* データフレーム送信時のメッセージ ID */
    unsigned char  Data[64];    /* 送信データ。DataLength で設定した分のデータを
                                    先頭から詰めて格納する */
} CANSEND_170_DATA;
```

> **LabVIEW CLFN での `SendCANDataFrame` の扱い**：
> - `UnitNo`/`MdlNo`/`ChNo` : I32
> - `pSendInfo` : ネストしたポインタを持つ構造体のため、二段階で組み立てる。
>   1. `CANSEND_170_DATA` 配列（要素数 = 送信フレーム数、1要素 = 4+4+64 = **72バイト**）を
>      U8 配列として `Initialize Array` で確保し、`Array Data Pointer` を取得。
>   2. `CANSEND_170_INFO` 本体（IdFormat(4)+Count(4)+pSendData(ポインタ4/8byte) = 環境依存サイズ）
>      を別の U8 配列として確保し、`pSendData` 位置に手順1で得たポインタ値を書き込む。
>   3. 手順2の配列の `Array Data Pointer` を `CLFN` の `pSendInfo` 引数に渡す。
> - `pSendInfo` 自体は CLFN 上で `Pointer to Value` 相当（構造体を指すポインタ1個）として渡す。

> **注意・制限事項（6.39.4節）：**
> - アイドル中に本関数を発行する場合、事前に **`RAMScopeGT170SetMeasCond()`** 関数によりバス設定を行うこと。
> - `DataLength=0` のデータフレームを要求した場合、本関数は該当のデータフレーム送信を実施しない
>   （**エラーとはしない**）。
>
> **発行タイミング（6.39.5節）**：オフライン=×／測定中=○／アイドル=○
>
> **応答（6.39.6節 表6-226）：**
> | 戻り値 | 意味 |
> |--------|------|
> | `0x00000000` | 正常終了 |
> | `0x30000001` | 関数内部で例外を検出 |
> | `0x30000005` | `MdlNo` の指定値に誤りがある |
> | `0x30000006` | （同上・詳細未記載）|
> | `0x30000500` | `UnitNo` の指定値に誤りがある |
> | `0x3000050E` | オフラインの状態で関数が呼び出された |
> | `0x30000900` | 動作指定値に誤りがある |
> | `0x30100001` | 下位DLL内に必要な処理が見つからない（DLLバージョン確認）／GT150・GT12xに対して関数が呼び出された |
> | `0x30000504` | RAMScopeハードウェアとの通信に失敗 |
> | `0x3000050D` | 電源・ホストPCとの接続・USBドライバのインストール状況・API関数の発行手順などを確認 |
> | `0x30000512`〜`0x30000515` | 上記確認後も現象が改善しない場合は弊社まで問い合わせ |

**`RAMScopeGT170ScenarioSendSet` 関数仕様（6.40章・確定）：**

```c
/* シナリオ送信設定処理
   CAN モジュールのシナリオ送信機能を設定する。
   発行対象モジュール：CAN */
long RAMScopeGT170ScenarioSendSet(
    long            UnitNo,       /* [in] 発行対象ユニット（将来拡張用。現仕様では常に 0）*/
    long            MdlNo,        /* [in] 発行対象モジュールのモジュール番号 */
    long            ChNo,         /* [in] データフレームの送信に使用する CAN モジュールの物理Ch番号。0=Ch1／1=Ch2 */
    long            ScenarioNum,  /* [in] 設定シナリオ数。0〜1 の範囲で指定 */
    SEND_SCENARIO   *pScenario    /* [in] シナリオ送信情報。設定済み、要素数 ScenarioNum の
                                          SEND_SCENARIO 型配列の先頭ポインタを渡す */
);
```

**`SEND_SCENARIO` / `SEND_SCENARIO_STEP` 構造体定義（6.40.3章・表6-229、6-230）：**

```c
typedef struct SEND_SCENARIO {
    long                 Mode;       /* シナリオの動作モード：
                                         0=本関数の発行と連動してシナリオ開始
                                         1=開始イベント成立でシナリオ開始 ＆ 停止イベント成立でシナリオ停止
                                         2=開始イベントが成立でシナリオ開始、開始イベントが非成立でシナリオ停止 */
    long                 Repeat;     /* シナリオの繰り返し指示：
                                         0=最終ステップ終了後、シナリオ停止
                                         1=最終ステップ終了後、最初のステップからシナリオを再開 */
    long                 StartEvNo;  /* 開始イベント番号。Mode=1,2 の場合、動作開始のキーとするイベント番号を指定 */
    long                 StopEvNo;   /* 停止イベント番号。Mode=1 の場合、動作停止のキーとするイベント番号を指定 */
    long                 StepNum;    /* シナリオのステップ数。1〜64 の範囲で指定 */
    SEND_SCENARIO_STEP   Step[64];   /* シナリオのステップ情報 */
} SEND_SCENARIO;

typedef struct SEND_SCENARIO_STEP {
    long              IdFormat;   /* ID フォーマット：0=標準ID／1=拡張ID */
    long              Count;      /* 該当ステップの繰り返し回数（0〜）*/
    long              WaitTime;   /* ステップ実行間の待ち時間（msec単位）。0〜4095msec の間で指定 */
    CANSEND_170_DATA  SendData;   /* 送信データフレーム情報（表6-223 CANSEND_170_DATA 参照・上記で確定済み）*/
} SEND_SCENARIO_STEP;
```

> **注意・制限事項（6.40.4節）：**
> - RAMScopeVP アプリケーションの**有償ライセンス**が適用されていない状態で本関数を発行した場合、エラーを応答する。
> - アイドル中に本関数を発行する場合、事前に `RAMScopeGT170SetMeasCond()` 関数によりバス設定を行うこと。
> - 本関数の発行時点では**まだ CAN データフレームのシナリオ送信を開始しない**。
>   別途 `RAMScopeGT170ScenarioSendStart()` 関数を発行すること。
> - シナリオ送信の実施中に本関数を発行した場合、本関数はエラーを応答する。
> - 本関数で設定した情報は RAMScopeVP API 内部で保持し続ける。情報を破棄するには
>   以下いずれかの関数を実行すること：`RAMScopeGT150AllInit()` ／ `RAMScopeGT150DeviceExit()` ／
>   本関数を `ScenarioNum=0` で発行。
>
> **発行タイミング（6.40.5節）**：オフライン=×／測定中=○／アイドル=○
>
> **応答（6.40.6節 表6-232）：**
> | 戻り値 | 意味 |
> |--------|------|
> | `0x00000000` | 正常終了 |
> | `0x30000001` | 関数内部で例外を検出 |
> | `0x30000003` | 関数の呼び出し順序に誤りがある |
> | `0x30000005` | `MdlNo` の指定値に誤りがある |
> | `0x30000006` | （同上・詳細未記載）|
> | `0x30000500` | `UnitNo` の指定値に誤りがある |
> | `0x3000050E` | オフラインの状態で関数が呼び出された |
> | `0x30000900` | 動作指定値に誤りがある |
> | `0x30100001` | 下位DLL内に必要な処理が見つからない（DLLバージョン確認）／GT150・GT12xに対して関数が呼び出された |
> | `0xE0000004`／`0xE0000010` | 有効なライセンスが見つからない |

> **LabVIEW CLFN での `ScenarioSendSet` の扱い**：
> - `CANSEND_170_DATA` はすでに定義済み（4+4+64=72バイト）。
> - `SEND_SCENARIO_STEP` = IdFormat(4)+Count(4)+WaitTime(4)+SendData(72) = **84バイト**。
> - `SEND_SCENARIO` = Mode(4)+Repeat(4)+StartEvNo(4)+StopEvNo(4)+StepNum(4)+Step[64](84×64=5376) = **5396バイト**。
> - `pScenario` は `ScenarioNum`（0〜1）要素の `SEND_SCENARIO` 配列。U8 配列（5396×ScenarioNum バイト）を
>   `Initialize Array` で確保し `Array Data Pointer` で渡す。

**`RAMScopeGT170ScenarioSendStart` 関数仕様（6.41章・確定）：**

```c
/* シナリオ送信開始処理
   CAN モジュールへシナリオ送信機能の起動を指示する。
   発行対象モジュール：CAN */
long RAMScopeGT170ScenarioSendStart(
    long  UnitNo,   /* [in] 発行対象ユニット（将来拡張用。現仕様では常に 0）*/
    long  MdlNo     /* [in] 発行対象モジュールのモジュール番号 */
);
```

> **注意・制限事項（6.41.3節）：**
> - RAMScopeVP アプリケーションの**有償ライセンス**が適用されていない状態で本関数を発行した場合、エラーを応答する。
> - 本関数を発行する場合、事前に `RAMScopeGT170ScenarioSendSet()` 関数を発行し、送信シナリオを定義しておくこと。
> - 既にシナリオ送信が機能している CAN モジュールに対して本関数を発行した場合、エラーとする。
> - シナリオ送信は**測定動作中にのみ機能**する。**アイドル中に本関数を発行した場合、
>   実際の動作は次回の測定状態への遷移後に起動する。**
>
> **発行タイミング（6.41.4節）**：オフライン=×／測定中=○／アイドル=○
>
> **応答（6.41.5節 表6-236）：**
> | 戻り値 | 意味 |
> |--------|------|
> | `0x00000000` | 正常終了 |
> | `0x30000001` | 関数内部で例外を検出 |
> | `0x30000003` | 関数の呼び出し順序に誤りがある |
> | `0x30000005` | `MdlNo` の指定値に誤りがある |
> | `0x30000006` | （同上・詳細未記載）|
> | `0x30000500` | `UnitNo` の指定値に誤りがある |
> | `0x3000050E` | オフラインの状態で関数が呼び出された |
> | `0x30100001` | 下位DLL内に必要な処理が見つからない（DLLバージョン確認）／GT150・GT12xに対して関数が呼び出された |
> | `0x30000504` | RAMScopeハードウェアとの通信に失敗 |
> | `0x30000506` | RAMScopeハードウェアの電源、ホストPCとの接続、USBドライバのインストール状況、API関数の発行手順などを確認 |
> | `0x30000512`〜`0x30000515` | 上記確認後も現象が改善しない場合は弊社まで問い合わせ |
> | `0xE0000004`／`0xE0000010` | 有効なライセンスが見つからない |

**`RAMScopeGT170ScenarioSendStop` 関数仕様（6.42章・確定）：**

```c
/* シナリオ送信停止処理
   CAN モジュールへシナリオ送信機能の停止を指示する。
   発行対象モジュール：CAN */
long RAMScopeGT170ScenarioSendStop(
    long  UnitNo,   /* [in] 発行対象ユニット（将来拡張用。現仕様では常に 0）*/
    long  MdlNo     /* [in] 発行対象モジュールのモジュール番号 */
);
```

> **注意・制限事項（6.42.3節）：**
> - シナリオ送信機能が起動していない CAN モジュールに対して本関数を発行した場合、エラーとはしない。
> - シナリオ送信は測定動作中にのみ機能する。本関数を発行しなかった場合でも、以下の関数の発行により
>   RAMScopeVP API はシナリオ送信を停止する：
>   - `RAMScopeGT150DeviceExit()`
>   - `RAMScopeGT150AllInit()`
>   - `RAMScopeGT170MeasStop()`
>
> **発行タイミング（6.42.4節）**：オフライン=×／測定中=○／アイドル=○
>
> **応答（6.42.5節 表6-240）：**
> | 戻り値 | 意味 |
> |--------|------|
> | `0x00000000` | 正常終了 |
> | `0x30000001` | 関数内部で例外を検出 |
> | `0x30000005` | `MdlNo` の指定値に誤りがある |
> | `0x30000006` | （同上・詳細未記載）|
> | `0x30000007` | アイドル状態で関数が呼び出された |
> | `0x30000500` | `UnitNo` の指定値に誤りがある |
> | `0x3000050E` | オフラインの状態で関数が呼び出された |
> | `0x30100001` | 下位DLL内に必要な処理が見つからない（DLLバージョン確認）／GT150・GT12xに対して関数が呼び出された |
> | `0x30000504` | RAMScopeハードウェアとの通信に失敗 |
> | `0x30000506` | RAMScopeハードウェアの電源、ホストPCとの接続、USBドライバのインストール状況、API関数の発行手順などを確認 |
> | `0x30000512`〜`0x30000515` | 上記確認後も現象が改善しない場合は弊社まで問い合わせ |

> **CAN シナリオ送信の全体フロー（確定）：**
> ```
> ① RAMScopeGT170ScenarioSendSet(0, MdlNo, ChNo, ScenarioNum, &scenario)   ← シナリオ定義（アイドル/測定中どちらでも可）
> ② RAMScopeGT170ScenarioSendStart(0, MdlNo)                              ← 送信起動指示
>      ※ アイドル中に発行した場合、実際の起動は測定開始後になる
> ③ [測定中：シナリオに従って自動送信]
> ④ RAMScopeGT170ScenarioSendStop(0, MdlNo)                               ← 送信停止指示
>      ※ MeasStop / AllInit / DeviceExit でも自動停止する
> ```

**DeviceInit のエラーコード（確認済み）：**

| 戻り値 | 意味 |
|--------|------|
| `0x00000000` | 正常終了 |
| `0x30000001` | 関数内部で例外を検出 |
| `0x30000503` | 同一種類の RAMScope が複数台接続されている |
| `0x30100000` | 必要な DLL ファイルが見つからない |
| `0x30000504` | RAMScope ハードウェアとの通信に失敗 |
| `0x30000506` | 電源・USB 接続・ドライバ・発行手順を確認 |

**DeviceExit のエラーコード：**

| 戻り値 | 意味 |
|--------|------|
| `0x00000000` | 正常終了 |
| `0x30000001` | 関数内部で例外を検出 |

**注意事項（仕様書より）：**
- `DeviceInit` は **DLL ロード後、全ての処理に先立って最初に発行**する。
- `DeviceInit` はオフライン状態でのみ有効（測定中・アイドル中は応答するが実処理なし）。
- `DeviceExit` 発行時、RAMScopeVP API が保持していた**測定設定・測定データは全て破棄**される。
- 測定状態で `DeviceExit` を発行すると**自動停止してから切断**される。

**まだ未確認の共通関数**（仕様書の追加ページで確認が必要）：
- 呼び出し規約（`__stdcall` か `__cdecl` か）

#### 10.4.2b 測定データパケット構成（7章・確定）

`GetBufferData` / `GetLoggingData` の `pData` に格納される **1パケット分のバイナリ構成**。
モジュール種別（RAM モニタ / CAN）ごとにフォーマットが異なる。

**① RAM モニタモジュール（7.1章・表7-1、表7-2）**

```
pData → [ Packet[0] | Packet[1] | ... | Packet[M-1] ]   ※M = pDataNum（取得パケット数）

1パケットの内訳：
[ Data[0] | Data[1] | ... | Data[N-1] | Flag(4byte) | Time(8byte) ]
```

| フィールド | サイズ | 説明 |
|-----------|--------|------|
| `Data[0..N-1]` | 4byte × N | ロギング対象チャンネルの測定値。N = `SetMeasCh()` で設定した**測定有効チャンネル数**。各チャンネルは `SetMeasCh()` で設定した順序で格納。全チャンネル共通で 4byte（データサイズは `SetMeasCh()` 指定に依存するがすべて4byte）|
| `Flag` | 4byte | ステータスフラグ（下記フラグ情報 参照）|
| `Time` | 8byte（64bit）| タイムスタンプ。測定開始(0)基準、20nsec周期のカウントアップ値。実時間 = 本値 × 20nsec |

**1パケットサイズ = 4×N + 4 + 8 = `4N + 12` バイト**（N=測定有効チャンネル数）

> **RAM モニタ フラグ情報（表7-2、32bit）：**
>
> | ビット位置 | ビット数 | フィールド | 説明 |
> |-----------|---------|-----------|------|
> | 0-7 | 8 | `status` | 測定ステータス。`0x00`=正常 / `0xFF`=バスエラー / `0xFE`=オフライン / `0xFA`=セキュリティIDエラー / `0xF9`=リンクエラー / `0xF8`=パラメータ未設定エラー（`0xF9`,`0xF8` は光RAMモニタ限定の異常ステータス。`9.2 Firmware内部エラーコード一覧` の `0x10000970`/`0x10000971` に対応）|
> | 8 | 1 | `skip` | スキップ現象検出フラグ。0=未発生／1=発生（測定周期・チャンネル数・メモリ操作関数の処理時間兼ね合いで発生）|
> | 10-11 | 2 | `log_trg` | ロギングトリガ実行フラグ。0=無効時／1=開始位置（トリガ待受中消失あり）／2=センター位置（トリガ成立パケットのみ）／3=終了位置 |
> | 12 | 1 | `dummy` | ダミーフラグ。0=メッセージ受信に伴う測定データパケット／1=情報通知目的の内部生成ダミーパケット |
> | 16-23 | 8 | `event` | イベント成立フラグ。LSBから e1,e2,...,e8。0=不成立／1=成立 |
> | 28 | 1 | `datalost` | データ欠落検出フラグ。0=正常通信／1=本パケット以前にデータ欠落発生 |
> | それ以外 | - | 予約 | 値不定 |

**② CAN モジュール（7.3章・表7-5、表7-6）**

```
pData → [ Packet[0] | Packet[1] | ... | Packet[M-1] ]

1パケットの内訳（GT17x、CAN FD 64byte最大長を考慮した固定フォーマット）：
[ Flag(4byte) | Time(8byte) | FD_Flag(4byte) | ID(4byte) | Data[0..63](64byte固定) ]
```

| フィールド | サイズ | 説明 |
|-----------|--------|------|
| `Flag` | 4byte | ステータスフラグ（下記 7.3.2 参照）|
| `Time` | 8byte（64bit）| タイムスタンプ。20nsec周期カウント値 ×20nsec = 経過時間 |
| `FD_Flag` | 4byte | CAN FD フォーマット関連の追加フラグ（下記 7.3.3 参照）|
| `ID` | 4byte | CAN ID（受信メッセージの識別ID）|
| `Data[0..63]` | 64byte 固定 | CAN受信データ。DLCに関わらず常に64byte固定（未使用分は不定）|

**1パケットサイズ = 4+8+4+4+64 = 固定 84 バイト**

> **CAN モジュール フラグ情報（`Flag` フィールド、表7-6、32bit）：**
>
> | ビット位置 | ビット数 | フィールド | 説明 |
> |-----------|---------|-----------|------|
> | 0-3 | 4 | `dlc` | データ長コード。受信メッセージのDLC |
> | 4 | 1 | `format` | 受信メッセージのIDフォーマット。0=標準ID／1=拡張ID |
> | 5 | 1 | `port` | メッセージを受信したCANモジュールの物理Ch番号。0=Ch1／1=Ch2 |
> | 8 | 1 | `valid` | パケットの有効性。0=無効パケット／1=有効パケット |
> | 10-11 | 2 | `log_trg` | ロギングトリガ実行フラグ（RAM同様。1=開始位置／2=センター位置／3=終了位置）|
> | 12 | 1 | `dummy` | ダミーフラグ。0=メッセージ受信に伴う測定データパケット／1=内部生成ダミーパケット |
> | 16-23 | 8 | `event` | イベント成立フラグ（e1〜e8、RAMと同様）|
> | 24 | 1 | `FD` | 受信メッセージフォーマット。0=CAN 2.0B／1=CAN FD |
> | 28 | 1 | `datalost` | データ欠落検出フラグ。0=正常通信／1=データ欠落発生 |
> | それ以外 | - | 予約 | 値不定 |
>
> **CAN モジュール フラグ情報(FD)（`FD_Flag` フィールド、表7-7、32bit）：**
>
> | ビット位置 | ビット数 | フィールド | 説明 |
> |-----------|---------|-----------|------|
> | 0-7 | 8 | `PayloadLen` | データ長。DLC をデコードした、受信メッセージのデータ長（Byte単位）|
> | それ以外 | - | 予約 | 値不定 |
>
> `PayloadLen` を使うことで `Data[0..63]` のうち **実際に有効なバイト数**が判別できる
> （DLC 自体は CAN FD で長さ→バイト数の対応が非線形なため、`dlc` 生値ではなく
> `PayloadLen` を使って有効データ範囲を切り出すこと）。

> **LabVIEW CLFN でのパケット解析方針**：
> - `pData` の U8 配列を `GetBufferData` から受け取った後、`Type Cast` でパケットサイズ分ずつ
>   切り出し（RAM: `4N+12`byte／CAN: 固定84byte）、`For Loop` で `pDataNum`（取得パケット数）分ループ処理する。
> - フラグは 32bit 値として取得後、`Boolean Array (Number To Boolean Array)` や
>   シフト/マスク演算でビットフィールドへ分解する。
> - タイムスタンプ（64bit, 20nsec単位）は `U64` として取り出し、`×20e-9` で秒に変換。
> - RAM モニタの `N`（測定有効チャンネル数）は `SetMeasCh()` で設定した値と一致させて
>   パケットサイズを計算する（アプリ側で保持しておく必要あり）。

### 10.4.2c ヘッダファイル入手により新規確定した関数・構造体（`.h` ヘッダより）

RAMScopeVP API のヘッダファイル `RAMScopeVP.h`（本リポジトリ [docs/reference/RAMScopeVP.h](./reference/RAMScopeVP.h) に保存済み）が入手できたため、
これまで仕様書 PDF の表からのみ関数名・章番号を把握していた関数群のプロトタイプ・構造体が
全て確定した。ヘッダは関数ポインタ型（`typedef long (*XxxPtr)(...)`）として宣言されており、
実行時に `GetProcAddress` 等で解決する設計だが、CLFN で使う分にはこの型定義から
戻り値・引数の型と順序をそのまま読み取ればよい。

> **注意**：ヘッダにも `__stdcall`／`WINAPI` 等の呼び出し規約マクロは明記されていない
>（プレーンな関数ポインタ宣言のみ）。呼び出し規約は依然として実機・DLL側で確認が必要
>（64bit DLL 入手待ちのため実質的には保留でよい。10.6 参照）。

**`RAMScopeGT170SetMeasCh` 関数仕様 + `CHINFO_170` 構造体（6.15章）：**

```c
long RAMScopeGT170SetMeasCh(
    long          UnitNo,   /* [in] 常に 0 */
    long          MdlNo,    /* [in] モジュール番号 */
    long          ChNum,    /* [in] チャンネル番号 */
    CHINFO_170    *pChInfo  /* [in] チャンネル情報 union ポインタ */
);

typedef struct CHINFO_RAM170 {
    DWORD enable;         /* 0=無効 / 1=有効 */
    DWORD core;           /* 測定対象コア番号 */
    DWORD address;        /* 測定対象アドレス */
    DWORD size;           /* データサイズ */
    DWORD sign;           /* 符号有無 */
    DWORD speed;          /* 測定速度区分 */
} CHINFO_RAM170;   /* 24 バイト（DWORD×6） */

typedef struct CHINFO_ADC170 {
    DWORD enable;         /* 0=無効 / 1=有効 */
    DWORD magnification;  /* 倍率 */
} CHINFO_ADC170;   /* 8 バイト（DWORD×2） */

typedef union CHINFO_170 {
    CHINFO_RAM170  RAM;
    CHINFO_ADC170  ADC;
} CHINFO_170;   /* union サイズ = 24 バイト（RAM が最大） */
```

**`RAMScopeGT150SetLoggingInfo` 関数仕様 + `LOGINFO` 構造体（6.16章）：**

```c
long RAMScopeGT150SetLoggingInfo(
    long      UnitNo,    /* [in] 常に 0 */
    LOGINFO   *pLogInfo  /* [in] ロギング容量設定情報 */
);

typedef struct LOGINFO {
    long  logDevice;       /* ロギング先デバイス */
    long  limitHddSize;    /* HDD使用量上限 */
    struct {
        long  logSize;     /* モジュール毎のロギングサイズ */
        long  BuffSize;    /* モジュール毎の表示用バッファサイズ（GetBufferData 対象）*/
    } mdl[16];              /* モジュール番号でインデックス（要素数16）*/
} LOGINFO;
/* サイズ = long×2 + (long×2)×16 = 8 + 128 = 136 バイト */
```

> `mdl[MdlNo].BuffSize` が `GetBufferData` で読み出す**表示用データバッファ**の容量に対応する
> （10.4.2a の「注意・制限事項」で確認済みの「`SetLoggingInfo` で容量指定する表示用データバッファ」はこの構造体のこと）。

**`RAMScopeGT170SetEventCond` 関数仕様 + `EVENTINFO_170` 構造体（6.19章）：**

```c
long RAMScopeGT170SetEventCond(
    long           UnitNo,   /* [in] 常に 0 */
    EVENTINFO_170  *pEvtInfo /* [in] イベント条件情報 */
);

typedef union EV_DATA_4 { DWORD ulData; long slData; } EV_DATA_4;      /* 4バイト */
typedef union EV_DATA_8 { ULONGLONG ullData; LONGLONG sllData; } EV_DATA_8; /* 8バイト */

typedef struct EVENTINFO_RAM170 {
    long        ChNo;
    EV_DATA_4   Data1;
    EV_DATA_4   Data2;
} EVENTINFO_RAM170;   /* 12 バイト */

typedef struct EVENTINFO_CAN170 {
    long           ChNo;
    unsigned long  CanID;
    long           Format;
    long           Endian;
    long           SigLen;
    long           SigStartByte;
    long           SigStartBit;
    long           SigSigned;
    EV_DATA_8      Data1;
    EV_DATA_8      Data2;
} EVENTINFO_CAN170;   /* long×8(32) + EV_DATA_8×2(16) = 48 バイト */

typedef struct EVENTINFO_ADC170 {
    long ChNo;
    long Data1;
    long Data2;
} EVENTINFO_ADC170;   /* 12 バイト */

typedef union MDL_EVENTINFO_170 {
    EVENTINFO_RAM170  RAM;
    EVENTINFO_CAN170  CAN;
    EVENTINFO_ADC170  ADC;
} MDL_EVENTINFO_170;   /* union サイズ = 48 バイト（CAN が最大）*/

typedef struct EVENTINFO_170 {
    long                Enable;
    long                MdlNo;
    long                EventType;
    MDL_EVENTINFO_170   MdlUnq;
} EVENTINFO_170;   /* 4+4+4+48 = 60 バイト */
```

**`RAMScopeGT170SetExternalTrigger` 関数仕様 + `EXTTRG_INFO_170` 構造体（6.23章）：**

```c
long RAMScopeGT170SetExternalTrigger(
    long              UnitNo,      /* [in] 常に 0 */
    long              MdlNo,       /* [in] モジュール番号 */
    EXTTRG_INFO_170   *pExtTrgInfo /* [in] 外部トリガ設定情報 */
);

typedef struct SOFTTRG_INFO {
    long relay;
    struct { long ptn; long relay; } GROUP[2];
} SOFTTRG_INFO;   /* 4 + (4+4)×2 = 20 バイト */

typedef struct EXTTRG_IN_INFO {
    long Mode;
    long FilterTime;
} EXTTRG_IN_INFO;   /* 8 バイト */

typedef struct EXTTRG_OUT_INFO {
    long           Mode;
    long           Level;
    long           Cycle;
    SOFTTRG_INFO   Event;
} EXTTRG_OUT_INFO;   /* 4+4+4+20 = 32 バイト */

typedef struct EXTTRG_INFO_170 {
    EXTTRG_IN_INFO   ExtIn;
    EXTTRG_OUT_INFO  ExtOut;
} EXTTRG_INFO_170;   /* 8 + 32 = 40 バイト */
```

**`RAMScopeGT170SetMeasTrigger` 関数仕様 + `MEASTRG_INFO_170` 構造体（6.24章）：**

```c
long RAMScopeGT170SetMeasTrigger(
    long                UnitNo,       /* [in] 常に 0 */
    long                Mode,         /* [in] 動作モード */
    MEASTRG_INFO_170    *pMeasTrgInfo /* [in] 測定制御設定情報 union */
);

typedef struct MEASTRG_CANBUS_COND {
    long MdlNo;
    long ChNo;
    long Mode;
    long ID;
    long Format;
    long WaitTime;
} MEASTRG_CANBUS_COND;   /* 24 バイト */

typedef struct MEASTRG_CANBUS_PARAM {
    MEASTRG_CANBUS_COND Start;
    MEASTRG_CANBUS_COND End;
} MEASTRG_CANBUS_PARAM;   /* 48 バイト */

typedef struct MEASTRG_LEVEL_PARAM {
    long LeaderModule;
} MEASTRG_LEVEL_PARAM;   /* 4 バイト */

typedef union MEASTRG_INFO_170 {
    MEASTRG_LEVEL_PARAM   Level;
    MEASTRG_CANBUS_PARAM  CanBus;
} MEASTRG_INFO_170;   /* union サイズ = 48 バイト（CanBus が最大）*/
```

**`RAMScopeGT170ScenarioWriteStart`/`Stop` 関数仕様 + `WRITE_SCENARIO` 構造体（6.36/6.37章）：**

```c
long RAMScopeGT170ScenarioWriteStart(
    long             UnitNo,      /* [in] 常に 0 */
    long             MdlNo,       /* [in] モジュール番号 */
    long             ScenarioNum, /* [in] 設定シナリオ数 */
    WRITE_SCENARIO   *pScenario   /* [in] シナリオ情報配列の先頭ポインタ */
);
long RAMScopeGT170ScenarioWriteStop(
    long  UnitNo,   /* [in] 常に 0 */
    long  MdlNo     /* [in] モジュール番号 */
);

typedef struct WRITE_SCENARIO_STEP {
    unsigned long  WriteValue;   /* 書き込み値 */
    unsigned long  Count;        /* 繰り返し回数 */
} WRITE_SCENARIO_STEP;   /* 8 バイト */

typedef struct WRITE_SCENARIO {
    long                  Mode;
    long                  Repeat;
    long                  StartEvNo;
    long                  StopEvNo;
    unsigned long         Address;    /* 書き込み対象アドレス */
    unsigned long         Size;       /* 書き込みサイズ */
    long                  StepNum;    /* ステップ数：1〜64 */
    WRITE_SCENARIO_STEP   Step[64];
} WRITE_SCENARIO;
/* サイズ = long×7(28) + WRITE_SCENARIO_STEP[64](8×64=512) = 540 バイト */
```

> `RAMScopeGT170ScenarioSendSet`/`SEND_SCENARIO`（CAN送信シナリオ、6.40章で既出）と構造が類似するが、
> こちらは **RAM モニタモジュールへの値書き込みシナリオ**であり別機能（CAN 用ではない）。

**測定データ取得 API 全プロトタイプ（6.25〜6.31章。関数名・章番号のみだった箇所を完全確定）：**

```c
long RAMScopeGT150GetGapTime(       long UnitNo, unsigned long *pGapTime);
long RAMScopeGT150GetMeasNum(       long UnitNo, long *pMeasNum);
long RAMScopeGT150GetBlockNum(      long UnitNo, long MeasNo, long *pBlockNum);
long RAMScopeGT150GetBufferDataNum( long UnitNo, long MdlNo, long *pDataNum);
long RAMScopeGT150GetBufferData(    long UnitNo, long MdlNo, void *pData,
                                     long *pDataNum, long *pLostDataNum);      /* 既出・完全一致確認 */
long RAMScopeGT150GetLoggingDataNum(long UnitNo, long MdlNo, long MeasNo,
                                     long BlockNo, long *pDataNum);
long RAMScopeGT150GetLoggingData(   long UnitNo, long MdlNo, long MeasNo, long BlockNo,
                                     void *pData, long *pDataNum, long *pLostDataNum);
```

> `GetLoggingData` は `GetBufferData` と異なり `MeasNo`（測定回数）・`BlockNo`（ブロック番号）を
> 指定する点に注意。表示用バッファのリアルタイム取得（`GetBufferData`）とは別に、
> **測定終了後にロギング済みデータをブロック単位で読み出す**用途と考えられる（詳細は仕様書要確認）。

**RAM モニタ固有機能：メモリ読み書き（6.32〜6.35章）：**

```c
long RAMScopeGT150MemoryRead(
    long UnitNo, long MdlNo, unsigned long Address,
    long Size, long Count, char *Buffer, long Tmout
);
long RAMScopeGT150MemoryWrite(
    long UnitNo, long MdlNo, unsigned long Address,
    long Size, long Count, char *Buffer, long Tmout
);
long RAMScopeGT150ContinualyMemoryRead( long UnitNo, long MdlNo, long Count,
                                         CONT_MEM_RD *Buffer, long Tmout);
long RAMScopeGT150ContinualyMemoryWrite(long UnitNo, long MdlNo, long Count,
                                         CONT_MEM_WR *Buffer, long Tmout);

typedef struct CONT_MEM_WR {
    unsigned long  Size;      /* 1要素あたりのサイズ */
    unsigned long  Address;   /* 書き込み/読み込みアドレス */
    char           Data[4];   /* データ */
} CONT_MEM_WR;
typedef CONT_MEM_WR CONT_MEM_RD;   /* 同一構造体を読み込み用に流用 */
/* サイズ = 4+4+4 = 12 バイト */
```

**新規発見：`RAMScopeGT150PGT_ModifyMdlConfig`（6.8章相当。既存の 6.7 `PGT_SetMdlConfig` とは別関数）：**

```c
long RAMScopeGT150PGT_ModifyMdlConfig(
    long  UnitNo,    /* [in]  常に 0 */
    long  *SlotErr   /* [out] エラー情報配列（要素数16。PGT_SetMdlConfig と同じ形式）*/
);
```

> `SetMdlConfig` は初期設定、`ModifyMdlConfig` は設定変更用と推測される
> （章タイトル「モジュール構成編集（PGT使用）」より）。詳細な用途の違いは仕様書 6.8 章の
> 本文で要確認。

**`RAMScopeGT150/GT170SetAdcRange`（アナログ入力レンジ設定。6.43/6.44章）：**

```c
long RAMScopeGT150SetAdcRange(long UnitNo, long MdlNo, long ChNum, long *pRange);
long RAMScopeGT170SetAdcRange(long UnitNo, long MdlNo, long ChNum, long *pRange);
```

### 10.4.3 STEP2：1 関数あたりの CLFN 設定手順

関数ごとに次を行う（雛形化して量産する）。

1. ブロックダイアグラムに **CLFN** を配置 → 右クリック `Configure`。
2. **Library name**：RAMScopeVP API の DLL パスを指定
   （配布時に解決できるよう、相対パス or 環境変数 or インストール固定パスにする）。
3. **Function name**：`.h` のエクスポート名どおりに設定。
4. **Calling convention**：仕様書／ヘッダのマクロに合わせる
   （`WINAPI`/`__stdcall` → **stdcall**、無印/`__cdecl` → **C**）。誤ると呼び出し直後にクラッシュするので厳守。
5. **Parameters**：`.h` のプロトタイプどおりに 1 引数ずつ型と受け渡し方法を設定（10.4.4）。
6. **Return type**：戻り値（多くはエラーコードの整数）を設定。
7. **スレッド**：既定の「UI スレッドで実行」で開始。スレッドセーフが仕様書で保証され、
   並行性が必要なら「任意のスレッドで実行（reentrant）」に変更（10.4.6）。

### 10.4.4 STEP3：引数の型・受け渡しマッピング（CLFN 設定の肝）

| C の引数 | CLFN 設定 | LabVIEW 側の扱い |
|----------|-----------|------------------|
| `int` / `unsigned long` など（入力） | Numeric、対応サイズ（I32/U32/I16/U8…）、**Pass: Value** | 制御器から値を配線 |
| 出力ポインタ `int*`（値を受け取る） | Numeric、**Pass: Pointer to Value** | 出力端子で受ける |
| 文字列 `char*`（NULL 終端） | String、**C String Pointer** | 文字列を配線（入力）/ 事前確保（出力） |
| 配列 `T*`（RAM 値バッファ等） | Array＋要素型、**Array Data Pointer** | **先に `Initialize Array` でサイズ確保**してから渡す |
| 構造体 `struct*` | Adapt to Type（Cluster）または **バイト配列で受けて後段で分解** | 10.4.5 参照 |
| ハンドル（`HANDLE`/`void*`/`int`） | Numeric（ポインタ幅に注意：64bit は **U64/Pointer-sized**） | VI 間で引き回す |

> 注意：**出力配列・出力文字列は、呼び出し前に LabVIEW 側で十分なサイズを確保**しておく。
> 確保不足は **メモリ破壊・LabVIEW クラッシュ**の典型原因。仕様書の最大長に合わせる。

### 10.4.5 STEP4：構造体・ポインタ・文字列（解読の主な難所）

- **構造体（struct）**：メンバの順序と **アラインメント／パディング** が一致しないと値がずれる。
  - 安全策A：構造体を **バイト配列（U8 Array）で受け取り**、`Unflatten From String` /
    `Type Cast` で LabVIEW Cluster に分解（パディングを意識して手当て）。
  - 安全策B：構造体を使わず **1 メンバずつ別引数で渡す関数**があればそちらを使う。
- **コールバック関数**を要求する API は、LabVIEW から関数ポインタを渡すのが困難
  → **ポーリング型（値を取りに行く）関数**を優先して使う。
- **文字列**：C 文字列（NULL 終端）。エンコーディング（ASCII/Shift_JIS）に注意。
- まず **サンプルプログラムと同じ呼び出し順・同じ引数**を LabVIEW で再現することから始めると確実。

### 10.4.6 STEP5：ビット数・スレッド・配置

- **ビット数の一致は必須**：LabVIEW（32/64bit）・LabVIEW Runtime・**DLL** をすべて揃える。
  32bit DLL は 32bit LabVIEW からしか呼べない。混在は不可。
- **スレッド**：DLL がスレッドセーフでない場合は CLFN を「UI スレッド」に固定し、
  同一 DLL への同時呼び出しを避ける（TestStand で非同期化する場合は特に注意）。
- **配置**：DLL と依存物を実行 PC に配置（またはインストーラで導入）。
  CLFN のパス解決が運用環境で破綻しないようにする。

### 10.4.7 STEP6：RAMScope VI 群へのラップ（対応表）

仕様の関数を、本資料の 1 イベント 1VI（[05](./05_VI設計方針と共通仕様.md)）に対応させる。

| VI | TestStand の配置 | ラップする API（確定分） | 入出力 |
|----|-----------------|--------------------------|--------|
| `RAMScope_Connect.vi` | Setup ① | `RAMScopeGT150DeviceInit()` | out: kind（機種コード）・Status・TestError |
| `RAMScope_Init.vi` | Setup ② | `RAMScopeGT150AllInit(0)` + `RAMScopeGT150GetSysInfo(0, buf[16])` | out: endian値（後段に渡す）・Status・TestError |
| `RAMScope_Config.vi` | Setup ③ | `RAMScopeGT150PGT_SetMdlConfig()` | in: endian（Init.viの出力）/ out: Status・TestError |
| `RAMScope_Set_Cond.vi` | Setup ④ | `RAMScopeGT170SetMeasCond()` + `RAMScopeGT170SetMeasCh()` + `RAMScopeGT150SetLoggingInfo()` | in: 測定条件（TestStand変数）/ out: Status・TestError |
| `RAMScope_Log_Start.vi` | Main | **`RAMScopeGT150MeasStart()`** ✅ | out: Status・TestError |
| `RAMScope_Read.vi` | Main（ポーリング） | `RAMScopeGT150GetBufferData()` ✅ + パケット解析（10.4.2b 参照）| out: 測定値配列・タイムスタンプ・フラグ・Status・TestError |
| `RAMScope_Log_Stop.vi` | Main | **`RAMScopeGT150MeasStop()`** ✅ | out: Status・TestError |
| `RAMScope_Release.vi` | Main（Stop直後） | **`RAMScopeGT150ReleaseBufferData()`** | out: Status・TestError |
| `RAMScope_Close.vi` | Cleanup（最後段） | `RAMScopeGT150DeviceExit()` | out: Status・TestError |
| `CAN_Send.vi`（RAMScope 経由） | Main | `RAMScopeGT170SendCANDataFrame()` | [09](./09_CAN通信の実装.md) の入出力に整合 |
| `CAN_Scenario_Start.vi` | Main | `RAMScopeGT170ScenarioSendSet()` ✅ + `RAMScopeGT170ScenarioSendStart()` ✅ | in: シナリオ設定（SEND_SCENARIO）/ out: Status・TestError |
| `CAN_Scenario_Stop.vi` | Main | `RAMScopeGT170ScenarioSendStop()` ✅ | out: Status・TestError |

> **ハンドルなし構造**：`DeviceInit` はセッションハンドルを返さない（グローバル状態管理）。
> VISA のようなリファレンス引き回しは不要。VI 間でつなぐのはエラークラスタのみ。
>
> **AllInit の注意**：呼ぶたびに全測定設定がクリアされる。再試験で条件を変えたい場合は
> `AllInit` → `Config` → `SetCond` を再度実行すること。

### 10.4.8 STEP7：エラー処理

- 各関数の **戻り値（エラーコード）を判定** → 成功（多くは 0）以外は `TestError.ctl` に変換
  （機器名 `RAMScope`、コード、メッセージ、時刻）し、`error out` にも反映（[05](./05_VI設計方針と共通仕様.md) 5.4/5.5）。
- `.h` のエラーコード定数を **LabVIEW の定数表／Enum 型定義**にして、メッセージを可読化。

### 10.4.9 STEP8：PoC（最小実証 → 本実装）

1. **最小経路を実証**：Init → 1 変数 Read → Close を CLFN で呼べること。
2. 読めた値が **実機と一致**するか確認。
3. **安定性**：連続読み出し・長時間・スレッドでクラッシュしないか。
4. **CAN API の有無と動作**を仕様書・実機で確認（CAN を RAMScope 経由で行うか、[09](./09_CAN通信の実装.md) の別 IF にするか判断）。
5. PoC が通れば、10.4.7 の VI 群を量産（雛形化）。

> 解読・実装で詰まった場合は、**RAMScopeVP API の有償サポート**（`support-mvi@dts-insight.co.jp`）の
> 利用を検討する（DLL 使用自体は無償だがサポートは有償）。

## 10.4.9a RAM計測システムの設計まとめ（全体像）

付録A1（FG420）の A1.6.1 と同じ「段階的に作る」考え方を、RAMScope（CLFN方式）向けに具体化する。
**FG420 はベンダー製ドライバ VI を呼ぶだけだったが、RAMScope は関数プロトタイプ・構造体を
手動で CLFN 設定する必要があるため、作り方が根本的に異なる**。CAN 送受信（アライブカウンタ等、
[09](./09_CAN通信の実装.md) 9.9、10.4.11）はいったん対象外とし、**RAM 計測のみ**に絞って進める。

### (1) 必要な機能とVIの一覧

初期化・設定・測定条件設定・ロギング開始／停止・クローズの6系統＋共通土台1本＋
パケット解析1本、計10本のVIで足りる。

| # | 機能 | VI | 対応するCLFN |
|---|------|----|--------------|
| 0 | エラー変換（共通土台）| `RAMScope_Code_To_Error.vi` | なし（生のI32エラーコード→標準errorクラスタへの変換のみ）|
| 1 | 接続（機種検出）| `RAMScope_Connect.vi` | `RAMScopeGT150DeviceInit` |
| 2 | 初期化＋モジュール番号自動判定 | `RAMScope_Init.vi` | `RAMScopeGT150AllInit` + `GetSysInfo` |
| 3 | プローブ接続設定 | `RAMScope_Config.vi` | `RAMScopeGT150PGT_SetMdlConfig` |
| 4 | 測定条件・チャンネル・ロギング設定 | `RAMScope_Set_Cond.vi` | `SetMeasCond` + `SetMeasCh` + `SetLoggingInfo` |
| 5 | 計測開始 | `RAMScope_Log_Start.vi` | `RAMScopeGT170MeasStart` |
| 6 | データ取得（ポーリング。CLFN呼び出しのみ）| `RAMScope_Read.vi` | `RAMScopeGT150GetBufferData` |
| 6a | パケット解析（`Read.vi`から分離。実機無しでも単体テスト可能）| `RAMScope_Parse_Buffer.vi` | なし（純粋な計算処理）|
| 7 | 計測停止 | `RAMScope_Log_Stop.vi` | `RAMScopeGT170MeasStop` |
| 8 | バッファ解放（要否は現時点未検証）| `RAMScope_Release.vi` | `RAMScopeGT150ReleaseBufferData` |
| 9 | クローズ | `RAMScope_Close.vi` | `RAMScopeGT150DeviceExit` |

> 🔴 **DLLアクセスの排他制御**：RAMScopeVP APIのDLLがスレッドセーフかどうかは未確認のため、
> **RAM計測のポーリング（`RAMScope_Read.vi`）とCAN送信（10.4.11のシナリオ送信）を
> 同じRAMScopeデバイスに対して同時に別ループから呼び出さない**こと。TestStandのステップとして
> 順番に呼ぶだけなら問題ないが、将来どちらかを並列ループ（例：RAM計測を継続ポーリングする
> 専用ループ）にする場合は、**DLL呼び出しは常に1つのループ（Device Accessループ）に
> 集約し、他のループはメッセージ（キュー等）でその1ループに処理を依頼する**設計にする。

**質問：現在のRAMScopeのコンフィグファイルから設定を抽出・流用できるか？** → 機能によって答えが違う。

- **③プローブ接続設定（`PGT_SetMdlConfig`）は、既存の設定をそのまま流用できる**。
  この関数は**引数にファイルパスを取らず**（`UnitNo`とエラー配列のみ）、
  ベンダー提供の **PGTツール（`PGTMgrVP.dll`等）が事前に保存した設定を暗黙に読みに行く**方式
  （10.4.2c）。つまり、**今までRAMScope純正アプリで動作確認済みの環境であれば、
  そのPC上でPGTツールの設定はすでに存在しており、LabVIEWからは`PGT_SetMdlConfig`を
  呼ぶだけで同じ設定が適用される**。プローブ固有の非公開パラメータ（セキュリティID・
  クロック設定等）をLabVIEW側で調べ直す必要はない。
- **④測定条件・チャンネル一覧・ロギング設定（`SetMeasCond`/`SetMeasCh`/`SetLoggingInfo`）は、
  試験ごとに変わる「試験条件」なので流用ではなく、TestStand側の試験条件（CSV等、
  [05](./05_VI設計方針と共通仕様.md)の方針）として都度指定する**設計にする。
  ただし、もし既存のRAMScope純正アプリ側で「この基板ではこのRAMアドレス一覧を測定する」
  という**チャンネルリストを保存したファイル**が既にあるなら、その内容（アドレス一覧）を
  試験条件CSVの初期値として転記するのは有効。そのようなファイルが手元にあれば、
  フォーマットを教えてもらえれば変換方法を検討できる。

### (2) VI対応表（入力・出力・機能）

| VI | 入力 | 出力 | 機能 |
|---|---|---|---|
| `RAMScope_Code_To_Error.vi` | `エラーコード`(I32)／`関数名`(String) | `error out`（標準クラスタ）| 生のI32エラーコードを標準errorクラスタに変換する共通アダプタ |
| `RAMScope_Connect.vi` | `error in` | `UnitNum`(I32)／`機種コード`(I32)／`実行結果ステータス`／`エラー情報`／`error out` | RAMScope本体の検出・機種判定 |
| `RAMScope_Init.vi` | `error in` | `MdlNo_RAM`(I32)／`MdlNo_CAN`(I32)／`実行結果ステータス`／`エラー情報`／`error out` | 全体初期化とモジュール構成の取得。RAM/CANのモジュール番号を実行時に自動判定 |
| `RAMScope_Config.vi` | `MdlNo_RAM`／`error in` | `実行結果ステータス`／`エラー情報`／`error out` | プローブ接続情報の設定（PGTツールの既存設定を適用）|
| `RAMScope_Set_Cond.vi` | `MdlNo_RAM`／`測定周期`(DBL)／`周期単位`(Enum)／`RAMチャンネル一覧`(配列)／`error in` | `実行結果ステータス`／`エラー情報`／`error out` | 測定条件・チャンネル・ロギングバッファの設定（3つのCLFNをまとめて実行）|
| `RAMScope_Log_Start.vi` | `MdlNo_RAM`／`error in` | `実行結果ステータス`／`エラー情報`／`error out` | 計測開始 |
| `RAMScope_Read.vi` | `MdlNo_RAM`／`error in` | `raw bytes`(U8配列)／`取得パケット数`／`lostDataNum`／`実行結果ステータス`／`エラー情報`／`error out` | 表示用バッファから最新データをポーリング取得（CLFN呼び出しのみ）|
| `RAMScope_Parse_Buffer.vi` | `raw bytes`(U8配列)／`取得パケット数`／`チャンネル数N`／`error in` | `測定値`(2次元配列)／`タイムスタンプ配列`／`フラグ配列`／`実行結果ステータス`／`エラー情報`／`error out` | 生バイト列をチャンネル値・タイムスタンプ・フラグに解析（`Read.vi`から分離。実機無しでもテスト可能）|
| `RAMScope_Log_Stop.vi` | `MdlNo_RAM`／`error in` | `実行結果ステータス`／`エラー情報`／`error out` | 計測停止 |
| `RAMScope_Release.vi` | `error in` | `実行結果ステータス`／`エラー情報`／`error out` | バッファ解放（STEP4のフローテストで要否を検証）|
| `RAMScope_Close.vi` | `error in` | `実行結果ステータス`／`エラー情報`／`error out` | 切断・終了 |

### (3) 各VIの作成手順

以下の STEP 0〜3 で詳細化する。特に④`RAMScope_Set_Cond.vi`（測定条件・チャンネル・
ロギング設定）は3つのCLFNをまとめる必要があり構成が複雑なため、STEP 3.4で
バイト単位の組み立て手順まで具体的に記載している。

### (4) フローテスト用VI

STEP 4（`RAMScope_Flow_Test.vi`）で、TestStand無しの単体確認を行う。

### (5) EXEファイルの作成

FG420と同じ手順（[03](./03_LabVIEW環境構築.md) 3.6）でよいが、**1点重要な違いがある**。
FG420のドライバはVISA/SCPIベースの計装ドライバVIだったため依存VIの自動埋め込みだけで
完結したが、**RAMScopeはCLFNで生のDLL（`RAMScopeVP_API.dll`等）を直接パス指定で
呼んでいる**ため、**そのDLLファイル自体はApplication Builderが自動的にEXEへ
埋め込んでくれない**。ビルド仕様の「ソースファイル」設定で、DLL一式
（`RAMScopeVP_API.dll`/`GT150.dll`/`GT170.dll`/`GT170USB.dll`/`PGTMgrVP.dll`/
`PGTMgrVP_ENG.dll`/`mfc140u.dll`/`msvcp140.dll`/`vcruntime140.dll`/`utillc.dll`/
`pgtlib\`フォルダ、10.4.1確認済み一覧）を**「常にインクルード」に追加し、
CLFNのライブラリパスが試験用PC上でも解決できる相対配置**にしておく必要がある。

### (6) 試験用PC側の追加インストール

FG420（[03](./03_LabVIEW環境構築.md) 3.6.2）のLabVIEW Run-Time EngineとNI-VISAに加えて、
RAMScopeでは以下が追加で必要。

| # | 項目 | 内容 |
|---|------|------|
| 1 | **RAMScopeVP（API）本体のインストール** | 10.4.1確認済みのDLL一式・USBドライバ・PGTツールを含む純正インストーラを試験用PCでも実行する（DLLだけコピーするのではなく、正規のインストーラを使うのが確実。USBドライバとPGT設定はインストーラ経由でないと入らない）|
| 2 | **PGTツールでのプローブ設定** | ③`RAMScope_Config.vi`が暗黙に読みに行く設定（(1)参照）は、**試験用PCでもPGTツールで一度設定しておく必要がある**（開発PCの設定は自動的には移行されない。設定内容自体はプローブ・ターゲット基板が同じなら同じ値でよい）|
| 3 | **USB3.0ポート** | RAMScopeVP APIでの接続はUSB3.0必須（Ethernet不可。10.6確定事項）。試験用PCにUSB3.0ポートがあることを確認 |
| 4 | **Visual C++ ランタイム** | `mfc140u.dll`等はVC++再頒布可能パッケージに含まれる。RAMScopeVPインストーラが導入するはずだが、EXE単体配布の場合は別途確認 |
| 5 | **DLLのbit数** | 64bit版DLL（入手済み）と、LabVIEW Run-Time Engineのbit数を揃える（32/64bit不一致は不可）|

### (7) 試験用PCでの操作手順（フロントパネルの説明）

`RAMScope_Flow_Test.vi`のフロントパネル構成が固まり次第、FG420で作成した
1枚の操作説明シートと同じ形式で作成する（本編ではまだVI未完成のため、フロントパネルの
確定後に着手する）。想定される操作項目は、`測定周期`／`周期単位`／`RAMチャンネル一覧`／
`待ち時間`／`実行結果ステータス`／`エラー情報`（STEP4のフロー構成より）。

---

## 10.4.10 段階的なVI構築手順（RAM計測のみ。CAN送受信は別途）

### STEP 0：プロジェクトの準備（実体は本編メインプロジェクトに1つだけ。基盤試験プロジェクトからは参照）

**基盤試験（FG420＋RAMScope）とベンチ試験（本編メインプロジェクト）は別の試験・別プロジェクトだが、
RAMScope は両方から使われる**ため、実体を1つだけ本編メインプロジェクトに作り、
基盤試験プロジェクトからは**コピーせず参照**する（3.5.1 に追記した考え方）。

> 🔴 **`基盤試験プロジェクト`側に作った `20_RAMScope` フォルダは使わない**：
> もし空フォルダのまま（VI未作成）なら削除してよい。既に何かVIを作成済みの場合は、
> そのVIファイルを本編メインプロジェクトの `30_RAMScope` へ移動する。

1. **本編メインプロジェクト**の `30_RAMScope` フォルダ（無ければ本編 3.5.1〜3.5.3 の要領で作成）を開く。
   以降の RAMScope 系 VI は**すべてここに実体を作る**。
2. 共通サブVI（`Status.ctl`／`TestError.ctl`／`Error_To_TestStatus.vi`、[06](./06_VIの作り方_手順.md) 6.1〜6.1.2）が
   本編メインプロジェクトの `00_Common` に無ければ、FG420 プロジェクトからコピーする
   （こちらは 3.5.1 の使い分け基準どおり「独立した別案件どうし」なのでコピーでよい）。
3. RAMScopeVP API の **64bit DLL**（入手済み）を配置し、CLFN のライブラリパスから
   到達できる場所に置く（絶対パス、または `.lvproj` からの相対パスで解決できる場所）。
   64bit 版のため、**呼び出し規約（stdcall/cdecl）は事実上問わない**（10.0 ⑤・10.6 参照。
   x64 ABI には規約の区別が無いため、CLFN の Calling Convention 設定は "C" のままで良い）。
4. **基盤試験プロジェクト側で RAMScope を使う VI を作るときは**、関数パレット→「VIを選択…」で
   本編メインプロジェクトの `30_RAMScope\RAMScope_*.vi` を直接選んで配置する（3.5.1参照）。
   これで基盤試験プロジェクトの「依存項目」に自動的に現れ、**実体は本編側の1箇所のみ**に保たれる。

### STEP 1：CLFN 疎通確認（実機・VI 抜きで最初に確認すること）

FG420 の `*IDN?`（VISA Test Panel）に相当する事前確認は無いため、
**最初の CLFN 呼び出し自体を疎通試験とする**。

1. 空の VI を1つ作り、`RAMScopeGT150DeviceInit` の CLFN を1個だけ配置して設定（10.4.3 STEP2）。
2. 実行し、**LabVIEW がクラッシュしないこと**を確認する（呼び出し規約や引数の型を間違えると
   ここで LabVIEW ごと落ちることがある。64bit DLL 入手によりこのリスクは大幅に下がっている）。
3. 実機が繋がっていなくても、`DeviceInit` は「オフライン→アイドル」の遷移を試みるだけなので、
   エラーコードが返る（またはハングする）だけで済むはず。**実機が無い場合はここで得られる
   戻り値がエラーコードになることを確認するだけでよい**（FG420 の「天然のエラー注入」と同じ考え方）。

### STEP 2：共通の土台を先に作る（全RAMScope系VIで使い回す）

#### `RAMScope_Code_To_Error.vi`（`30_RAMScope` に新規作成）

RAMScope の CLFN 呼び出しは **戻り値が生の I32 エラーコード**であり、
FG420 のドライバ VI のような標準 error cluster では返ってこない。そのため
`Error_To_TestStatus.vi`（FG420 用に作った共通サブVI、06 6.1.2）にそのまま渡せない。
**まず I32 エラーコード → 標準 error cluster に変換するアダプタ**を挟む。

| 端子 | 型 | 説明 |
|------|----|------|
| `エラーコード` | I32（入力）| CLFN の戻り値をそのまま渡す |
| `関数名` | String（入力）| `"DeviceInit"` 等、どの関数の戻り値かを示す文字列 |
| `error out` | error cluster（標準・出力）| `status = (エラーコード ≠ 0)`／`code = エラーコード`／`source = "RAMScope " + 関数名 + " エラー"` |

呼び出し側では、この`error out`をさらに`Error_To_TestStatus.vi`（`機器名="RAMScope"`）に渡す
**2段変換**にする：

```
CLFN戻り値(I32) ──▶ RAMScope_Code_To_Error.vi(関数名="DeviceInit")
                              │
                              ▼ error out（標準クラスタ）
                    Error_To_TestStatus.vi(機器名="RAMScope")
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
      実行結果ステータス   エラー情報      error out
```

> `0x30000001`のような16進エラーコードもI32としてそのまま扱える
> （`TestError.ctl`の`コード`をU32にした場合はさらに正確。doc06 6.1.1参照）。

#### CLFN 設定の共通テンプレート

各関数のCLFN設定で毎回変わるのは「関数名」「引数」「戻り値の型」だけ。
10.4.3 STEP2の手順（Library name／Function name／Calling convention="C"固定でよい／
Parameters／Return type=Long）をそのままコピーして量産する。

### STEP 3：VI ごとの構築（10.4.7 の対応表を1つずつ具体化）

以下、確定済みの関数プロトタイプ（10.4.2a〜10.4.2c）に基づく CLFN 設定の要点のみ記載
（構造体の完全な定義・バイトオフセットは各参照先を見る）。

#### STEP 3.1：`RAMScope_Connect.vi`（`RAMScopeGT150DeviceInit`）

```c
long RAMScopeGT150DeviceInit(long *pUnitNum, long *kind);
```

| CLFN パラメータ | 設定 |
|----------------|------|
| `pUnitNum` | Numeric, Long, **Pointer to Value**（出力：`UnitNum`）|
| `kind` | Numeric, Long, **Pointer to Value**（出力：`機種コード`。`0`=GT150/`1`=GT12x/`2`=GT17x）|
| 戻り値 | Numeric, Long（`エラーコード`）|

`エラーコード` → `RAMScope_Code_To_Error.vi`（関数名`"DeviceInit"`）→ `Error_To_TestStatus.vi`
（機器名`"RAMScope"`）→ 3出力。`UnitNum`／`機種コード`はログ用に出力しておく程度でよい
（10.4.7 の「ハンドルなし構造」注記のとおり、後続 VI へリファレンスとして引き回す必要は無い）。

#### STEP 3.2：`RAMScope_Init.vi`（`AllInit` + `GetSysInfo`）＋ **MdlNo の自動判定**

```c
long RAMScopeGT150AllInit(long UnitNo);                        // UnitNo=0
long RAMScopeGT150GetSysInfo(long UnitNo, SYSINFO *pSysInfo);   // SYSINFO[16]
```

1. `AllInit(0)` を CLFN で呼ぶ（引数は `UnitNo` 定数 `0` のみ）。戻り値をエラー変換。
2. `GetSysInfo(0, buf[16])` を CLFN で呼ぶ。
   - `pSysInfo`：**`Initialize Array`（U8、960要素）**を先に確保 → **Array Data Pointer** で渡す
     （SYSINFO 1個=60バイト×16 = 960バイト。10.4.2a 参照）。
3. 受け取った960バイトの配列を **For Loop（16回）** で60バイトずつ切り出し
   （`Array Subset`）、各60バイトを `Type Cast` で `SYSINFO` クラスタに変換
   （クラスタは 10.4.2a の定義どおり作っておく：`module`/`module_type`/`probe_id`/…/`name[16]`）。
4. ループ内で **`module_type = 0x00`（RAM モニタ）のスロットを探し、その `module` の値を
   `MdlNo_RAM` として出力**する（サンプルコードでは `MdlNo=1` だったが、これは環境依存の実測値。
   **ハードコードせず、必ずこの実行時判定で取得する**こと。10.4.2d ②の教訓）。
   同様に `module_type = 0x02`（CAN）のスロットも見つけておけば、後日 CAN 実装時にそのまま使える。

出力：`MdlNo_RAM`（I32。後続の `Set_Cond`／`Set_Ch`／`Read` 等 RAM 系全 VI で使う）、
`実行結果ステータス`、`エラー情報`、`error out`。

> 🔴 **10.4.7 の対応表の訂正**：同表は「`RAMScope_Config.vi` の入力に endian（Init.viの出力）」と
> 記載していたが、`.h` ヘッダで確定した `PGT_SetMdlConfig` の実際のシグネチャは
> `(UnitNo, SlotErr*)` のみで **endian を直接引数に取らない**（10.4.2c）。
> この記載は `.h` 入手前の古い想定のため、`RAMScope_Config.vi` は endian 入力無しで設計する。

#### STEP 3.3：`RAMScope_Config.vi`（`PGT_SetMdlConfig`）

```c
long RAMScopeGT150PGT_SetMdlConfig(long UnitNo, long *SlotErr);  // SlotErr[16]
```

| CLFN パラメータ | 設定 |
|----------------|------|
| `UnitNo` | Numeric, Long, Pass: Value（定数 `0`）|
| `SlotErr` | Array, I32[16]、**Array Data Pointer**（`Initialize Array` で16要素確保）|

戻り値をエラー変換。`SlotErr[MdlNo_RAM]`（STEP3.2で得た値をインデックスに使用）が `0` であることを
確認すると、RAM モジュールのプローブ接続設定が正しく通ったかピンポイントで分かる（10.4.2a）。

#### STEP 3.4：`RAMScope_Set_Cond.vi`（`SetMeasCond` + `SetMeasCh` + `SetLoggingInfo`）— 最も複雑

3つの CLFN 呼び出しを1つの VI にまとめる（10.4.7 の設計どおり）。

**① `RAMScopeGT170SetMeasCond(0, MdlNo_RAM, pMeasInfo)`**

`pMeasInfo` は72バイトの `MEASINFO_170` union（10.4.2a）。RAM モニタ用途では先頭の
`MEASINFO_RAM170`（20バイト。`MeasPeri_reserve[2]` の配列サイズ修正済み、10.4.2a）だけ埋める。

構築手順：
1. `Initialize Array`（U8、72要素、初期値0）で72バイトのゼロ埋め配列を用意。
2. `DummyInterval`（固定100）を I32→U8配列変換（`Type Cast`）し、オフセット`0`に`Replace Array Subset`。
3. `MeasPeri`（試験条件。周期）をオフセット`4`に同様に埋め込む。
4. `MeasUnit`（`1`=usec/`2`=msec）をオフセット`8`に埋め込む。
5. `MeasPeri_reserve[0]`／`[1]`はオフセット`12`／`16`に`0`を埋める（詳細仕様は要再確認、10.4.2a参照）。
6. この72バイト配列を `Array Data Pointer` で `pMeasInfo` に渡す。

入力：`測定周期`（DBL or I32、`MeasPeri`）、`周期単位`（Enum: usec/msec、`MeasUnit`）。

**② `RAMScopeGT170SetMeasCh(0, MdlNo_RAM, ChNum, pChInfo)`**

`pChInfo` は `CHINFO_170` の配列（1要素24バイト、RAM用途は `CHINFO_RAM170`：
`enable`/`core`/`address`/`size`/`sign`/`speed` の6×DWORD、10.4.2c）。

> 🔴 **`ChNum` はチャンネル「個数」**（配列要素数）であり、チャンネル番号のインデックスではない
> （10.4.2d③で実サンプルから確定済み）。

構築手順：
1. 測定したい RAM チャンネルの一覧（アドレス等）を試験条件（配列）として受け取る。
2. チャンネル数 `N` 分の24バイトブロックを連結した `N×24` バイトの配列を組み立てる。
   各ブロックは `enable=1`、`address`＝該当アドレス、`size`／`core`／`sign`／`speed`＝
   サンプルコードでは `0`（10.4.2d③。最低限 `enable`/`address`/`size`/`sign` の設定で動作する模様）。
3. `ChNum` にはこの `N` を渡す（配列の要素数と必ず一致させる）。

入力：`RAMチャンネル一覧`（アドレス配列などの試験条件）。

**③ `RAMScopeGT150SetLoggingInfo(0, pLogInfo)`**

`pLogInfo` は136バイトの `LOGINFO` 構造体（`logDevice`/`limitHddSize`/`mdl[16]`、
各16要素は`logSize`/`BuffSize`の2×I32＝8バイト、10.4.2c）。

構築手順：
1. `logDevice=0`、`limitHddSize=0` を埋める。
2. **`mdl[]` は使用モジュールだけでなく全16スロットに最低値（`logSize=1`,`BuffSize=1`）を
   埋めるのが安全なパターン**（10.4.2d④、サンプルコードでの実装に準拠。
   `NUM_MODULE_MAX_170=10` 分だけでなく、`mdl[]` の要素数自体は16固定なので16スロット全て埋める）。
3. `BuffSize` は次の `RAMScope_Read.vi` が読み出す表示用バッファの容量に対応するため、
   試験のポーリング頻度・パケットサイズから逆算した値を試験条件で渡せるようにしてもよい
   （まずは全て`1`で動作確認し、後から調整する方針でよい）。

出力（①②③共通）：`実行結果ステータス`、`エラー情報`、`error out`（3つのCLFN呼び出しをこの順で
連結し、途中でエラーが出たら以降をスキップする Case Structure にする。doc05 5.5 と同じ考え方）。

#### STEP 3.5：`RAMScope_Log_Start.vi`（`RAMScopeGT150MeasStart(0)`）

単純な1引数CLFN（`UnitNo`のみ）。`RAMScope_Connect.vi`と同じ粒度。

#### STEP 3.6：`RAMScope_Read.vi`（`GetBufferData` のCLFN呼び出しのみ）

```c
long RAMScopeGT150GetBufferData(long UnitNo, long MdlNo, void *pData,
                                 long *pDataNum, long *pLostDataNum);
```

| CLFN パラメータ | 設定 |
|----------------|------|
| `pData` | Array, U8[]、**Array Data Pointer**。事前に十分なサイズを確保（下記）|
| `pDataNum` | Numeric, Long, **Pointer to Value**（in/out）。**呼び出し前に必ず「バッファが
  受け止められる最大パケット数」を明示的に書き込む**（10.4.2d⑤。ベンダーサンプルの
  「未初期化のまま呼ぶ」実装は不具合の可能性がありそのまま真似ないこと）|
| `pLostDataNum` | Numeric, Long, Pointer to Value（出力）|

**バッファ確保**：RAM パケット1個 = `4×N + 12` バイト（`N`=STEP3.4②で設定したチャンネル数、
10.4.2a）。例えば1000パケット分を受け止めたいなら `Initialize Array`（U8、`(4N+12)×1000`要素）を
確保し、`pDataNum` にはあらかじめ `1000` を書き込んでから呼ぶ。

このVIの責務は**CLFN呼び出しと生バイト列の取得まで**とし、パケット解析は
STEP3.6a（`RAMScope_Parse_Buffer.vi`）に分離する（理由は3.6aの冒頭を参照）。

出力：`raw bytes`（U8配列。生のまま）、`取得パケット数`（`pDataNum`の戻り値）、
`lostDataNum`、`実行結果ステータス`、`エラー情報`、`error out`。

> **Watchdog的な使い方**：`pLostDataNum > 0` は表示用バッファが溢れたことを意味する
> （10.4.2a）。この VI をポーリングする周期・`SetLoggingInfo` の `BuffSize` を見直す指標にする。

> 🔧 **PoC段階のデバッグ推奨**：フロントパネルに一時的に
> `buffer size`（確保したバイト数）／`dataNum returned`（戻ってきた値）／`lostDataNum`／
> `raw bytesの先頭32byte`を表示器として出しておくと、`pDataNum`が実際に
> 「パケット数」を返しているのか等の解釈をログを見ながら実測で確認できる
> （仕様書の記載どおりのはずだが、**実測で必ず裏取りする**）。動作確認が取れたら
> 本番のVIからはこれらの一時的な表示器を外してよい。

#### STEP 3.6a：`RAMScope_Parse_Buffer.vi`（パケット解析。`RAMScope_Read.vi`から分離）

**RAMScope_Read.vi に埋め込まず、独立したVIにする**。理由：パケット解析（バイト列の
切り出し・`Type Cast`・ビットフィールド分解）は間違えやすく複雑な処理なので、
**実機・DLLが無い状態でもダミーのバイト配列を入力して単体テストできるようにしておくと
デバッグが大幅に楽になる**（実機接続時にしか動作確認できない設計にしない）。

入力：`raw bytes`（U8配列）、`取得パケット数`、`チャンネル数N`、`error in`
出力：`測定値`（チャンネル数×パケット数の2次元配列）、`タイムスタンプ配列`、
`フラグ配列`、`実行結果ステータス`、`エラー情報`、`error out`

内部処理：
1. `取得パケット数`分、`For Loop` を回す。
2. ループ内で `raw bytes` から `(4N+12)` バイトずつ `Array Subset` で切り出す。
3. 各パケットを：`Data[0..N-1]`（I32×N、チャンネル値）＋`Flag`（I32）＋`Time`（U64）に分解
   （`Type Cast` または `Unflatten From String`。10.4.2b参照）。
4. `Flag` は32bitのビットフィールド（`status`/`skip`/`log_trg`/`dummy`/`event`/`datalost`。
   10.4.2b の RAM フラグ表）。`論理積`（AND）とシフト演算でビット単位に分解する。
5. `Time` は20nsec単位のカウント値。`×20e-9` で秒に変換。

> **エンディアン注意**：`Type Cast`はプラットフォームのバイト順に依存する。
> Windowsは通常リトルエンディアンだが、`GetSysInfo`が返す`endian`フィールド
> （10.4.2a）と矛盾しないか、実測データで必ず確認すること。

#### STEP 3.7：`RAMScope_Log_Stop.vi`（`RAMScopeGT150MeasStop(0)`）

単純な1引数CLFN。`RAMScope_Log_Start.vi`と同じ粒度。

#### STEP 3.8：`RAMScope_Release.vi`（`RAMScopeGT150ReleaseBufferData(0)`）

単純な1引数CLFN。ただし **ベンダーサンプル（`samp_simple.cpp`）ではこの関数を呼んでいない**
（10.4.2d⑥）。作成はしておくが、STEP4のフローVIで実際に必要か・省略可能かを検証する。

#### STEP 3.9：`RAMScope_Close.vi`（`RAMScopeGT150DeviceExit()`）

引数無しのCLFN（戻り値のみ）。`FG420_Close.vi`同様、Cleanupの最後に1回だけ呼ぶ。

### STEP 4：`RAMScope_Flow_Test.vi`（TestStand 無しで通しフロー確認）

**本編メインプロジェクトの `30_RAMScope`** に新規作成し、STEP3のVIを以下の順で呼ぶ。
**FG420のSTEP4（A1.6.1）と同じ考え方**で、まずTestStandを使わず単体で一連の流れが通ることを確認する。

> このフローVI自体はベンチ試験（本編メインプロジェクト）用の確認VI。
> 基盤試験（FG420＋RAMScope）側で使うフローは、基盤試験プロジェクト内に
> **別途** `Board_Flow_Test.vi` 等として作り、その中で本編側の `RAMScope_*.vi`（STEP0④のとおり参照）と
> FG420 側の `FG420_*.vi` を組み合わせる（試験の目的・組み合わせ方が異なるため、
> フローVI自体は共用しない。共用するのは個々の `RAMScope_*.vi` の実体のみ）。

```
RAMScope_Connect
  → RAMScope_Init（MdlNo_RAM を取得。以降のVIへ渡す）
  → RAMScope_Config
  → RAMScope_Set_Cond（測定周期・チャンネル一覧を試験条件として入力）
  → RAMScope_Log_Start
  → Wait
  → RAMScope_Read（ループでポーリング。取得値をログ表示）
  → RAMScope_Log_Stop
  → （RAMScope_Release：STEP3.8の検証結果次第で要否判断）
  → RAMScope_Close
```

- **実機無しでの検証**：`RAMScope_Connect`（`DeviceInit`）の時点でエラーコードが返る
  （オフライン扱い）ため、以降の VI がそのエラーを引き継いで `Close` まで安全に抜けるかを
  FG420 と同じ「天然のエラー注入テスト」で確認できる。
- **実機ありでの検証**：`RAMScope_Init` で得た `MdlNo_RAM` が実際の構成と一致するか
  （`GetSysInfo` の `module_type=0x00` のスロットが本当に1個だけか等）を必ず確認する。
- フロントパネルの制御器（測定周期・チャンネル一覧・待ち時間等）が、
  そのまま TestStand 変数化の対象リストになる。

### STEP 5：TestStand への移行

STEP4で問題なければ、10.4.7 の対応表どおり Setup/Main/Cleanup にVIを配置する
（[11](./11_TestStandシーケンス構築手順.md)）。CAN 送受信（`CAN_Send.vi`等）は
以下 10.4.11 で扱う。

## 10.4.11 段階的なVI構築手順（CAN送信。RAMScopeのCANモジュールから送る）

RAM計測用VI（10.4.10）と同じ `30_RAMScope` プロジェクトに追加する。`DeviceInit`／`AllInit`／
`GetSysInfo`（`RAMScope_Connect.vi`／`RAMScope_Init.vi`）は**RAM計測と共用**でよい
（同じRAMScope本体に対し、RAM用モジュールとCAN用モジュールが別の`MdlNo`として同時に存在する
だけなので、接続・初期化は1回で済む）。チェックサム／アライブカウンタのアルゴリズムは
[09](./09_CAN通信の実装.md) 9.9.2 で確定済み。

> 🔴 **着手前に必ず確認**：`RAMScopeGT170ScenarioSendSet`／`ScenarioSendStart` は
> **RAMScopeVPアプリケーションの有償ライセンスが無いとエラー応答になる**（6.40.4節/6.41.3節）。
> ライセンスが無い場合はシナリオ送信が使えないため、後述の代替（単発送信 + LabVIEWタイムドループ、
> doc09 9.9 方式B相当）に切り替える必要がある。**まずライセンス状況を確認すること。**

### STEP 0：前提（新規プロジェクト作業は無し）

- 10.4.10 STEP0（プロジェクトは本編メインプロジェクトの `30_RAMScope` に一本化。
  基盤試験側からは参照のみ）がそのまま適用される。
- 10.4.10 STEP3.2 の `RAMScope_Init.vi`（`MdlNo` 自動判定）を**そのまま流用**し、
  `module_type=0x02`（CANモジュール）の `MdlNo` も同時に取得できるよう、
  戻り値に `MdlNo_CAN` を追加する（`MdlNo_RAM` と並べて出力するだけでよい）。

### STEP 1：`RAMScope_CAN_Set_Cond.vi`（`SetMeasCond`。CANモジュール用）

10.4.10 STEP3.3（`RAMScope_Config.vi`）と同じ`SetMeasCond`のCLFNを、
`MEASINFO_CAN170`（10.4.2c確定）を使って呼ぶ。

| 端子 | 型 | 内容 |
|------|----|----|
| `MdlNo_CAN` | I32（入力）| STEP0で取得したCANモジュール番号 |
| `isUseFDFormat?` | Bool（入力）| True＝CAN FD、False＝CAN 2.0B互換 |
| `Ch1有効?`／`Ch2有効?` | Bool（入力）| 使用する物理チャンネル |
| `BaudRate`（Ch1/Ch2）| I32（入力、Enum推奨）| ボーレート設定値（仕様書表の設定値番号）|
| `BusMode`（Ch1/Ch2）| I32（入力）| `isUseFDFormat=False`なら**必ず0固定**（6.4.10で確認済みの制約）|

`isUseFDFormat=0`のとき`BusMode`を0以外にするとエラー、という制約をVI内部でガード
（`Case Structure`で`isUseFDFormat=False`なら`BusMode`を強制的に0にする）しておくと安全。

### STEP 2：`CAN_Alive_Checksum_Calc.vi`（RAMScopeのCLFNと無関係に先行実装可能）

[09](./09_CAN通信の実装.md) 9.9.2／9.9.3 で確定したアルゴリズムを実装する。

> 🔴 **重要（9.9.2訂正済み）**：信号ごとの係数（重み）は**ビット位置から機械的に
> 導出できない**（OEM側の仕様として個別に決まっている）。そのため本VIは
> 「ペイロードのバイトをニブル和する」という汎用処理では作らず、**呼び出し側が
> 信号値と係数のペアを渡し、本VIは単純にその重み付き総和を取るだけ**、という設計にする
> （信号ごとの知識＝どの信号にどの係数を使うかは、9.9.3の対応表を見ながら
> メッセージ別の呼び出し側VI〈STEP4〉に持たせる）。

| 端子 | 型 | 内容 |
|------|----|------|
| `CAN ID` | U32（入力）| `id_check`相当（標準/拡張マーカーOR＋ニブル和は本VI内部で共通処理）|
| `拡張ID?` | Bool（入力）| 標準ID／拡張IDの判定（`0x800`境界で自動判定も可）|
| `信号値×係数の配列`（呼び出し側が9.9.3の表どおりに計算済みの値、または複数bit信号は`sum_plus`適用済みの値を渡す）| I32配列（入力）| 例：ID212なら `[IGSW×2, DTCCLINH×8, SYSTEM_READY_S×8]` を渡す |
| `アライブカウンタ値` | U8（入力、0〜3）| |
| `チェックサム` | U8（出力）| |
| `カウンタ・チェックサム格納バイト（byte7）` | U8（出力）| 9.9.3で確認した共通パターン`[未使用2bit][counter 2bit][checksum 4bit]`をそのまま組み立てて出力 |

内部処理：①IDに標準/拡張マーカーをOR→ニブル和（`id_check`相当、これは全メッセージ共通）
②入力配列の総和　③①＋②＋カウンタ値　④`256 - 総和`の下位1バイトがチェックサム
⑤`(0<<6) | (カウンタ<<4) | チェックサム`でbyte7を組み立てて出力（9.9.3で確認した
全メッセージ共通のbyte7パターンを利用）。
RAMScope本体のCLFNとは無関係な純粋計算VIなので、**今すぐ作れる**。

### STEP 3：`RAMScope_CAN_Send_Frame.vi`（単発送信。`SendCANDataFrame`）

まずシナリオ無しの単発送信から動作確認する（10.4.2b確定の構造体を使用）。

| 端子 | 型 | 内容 |
|------|----|------|
| `MdlNo_CAN`／`ChNo`（0=Ch1/1=Ch2）| I32（入力）| |
| `IdFormat`（0=標準/1=拡張）| I32（入力）| |
| `CAN ID` | U32（入力）| |
| `送信データ`（DataLength込み）| U8配列＋長さ（入力）| `CANSEND_170_DATA`1件分 |

CLFN配線は10.4.2b「LabVIEW CLFNでのSendCANDataFrameの扱い」の2段階組み立て
（`CANSEND_170_DATA`配列→`CANSEND_170_INFO`本体へポインタ書き込み）に従う。
**この単発送信で、まずCANバスモニタ（CANalyzer等）に意図通りのフレームが出ることを確認**
してから、シナリオ送信（STEP4以降）に進む。

> 🔧 **送信前バリデーション（推奨）**：CLFNへ渡す前に、次の範囲チェックを入れておくと
> 誤ったCAN IDやデータ長による意図しない送信・エラーを早期に検出できる。
> - 標準ID：`0〜0x7FF`の範囲か
> - 拡張ID：`0〜0x1FFFFFFF`の範囲か
> - `DataLength`と実際のデータ配列長が一致しているか
> - CAN 2.0B（Classic）は`DataLength`が0〜8byteの範囲内か
> 範囲外の場合はCLFNを呼ばずに`Status.ctl=Error`を返す（doc06 6.1.2の設計と同じ考え方）。

### STEP 4：シナリオ配列の組み立て（メッセージごとに専用の `CAN_Build_<ID>_Scenario.vi`）

1メッセージ分の**アライブカウンタが2bit（0〜3）で巡回する**ことを利用し、
`For i = 0 to 3` で `CAN_Alive_Checksum_Calc.vi`（STEP2）を呼んで
`SEND_SCENARIO_STEP`配列（4要素）を組み立てる。

> STEP2の設計変更により、**信号ごとの係数はメッセージ固有**（9.9.3参照）なので、
> このVI自体もメッセージごとに個別に作る（`CAN_Build_212_Scenario.vi`／
> `CAN_Build_03AD5D62_Scenario.vi`等）。共通化できるのはSTEP2の重み付き総和計算までで、
> 「どの信号にどの係数か」はここで9.9.3の表どおりに配線する。

| 端子 | 型 | 内容 |
|------|----|------|
| `CAN ID` | U32（入力）| 9.9.3の該当行の値を定数配線 |
| `試験条件として可変にしたい信号値`（例：ID03AD5D62なら`CORE_SVS_OPE_MODE_COM`）| 入力 | 9.9.3のバイト位置どおりペイロードへ配置し、係数を掛けて`CAN_Alive_Checksum_Calc.vi`の重み付き総和配列へ渡す |
| `WaitTime`（該当メッセージの周期。9.9.3の周期をms単位で）| I32（入力）| |
| `SEND_SCENARIO_STEP[4]` | 出力 | `StepNum=4`として`RAMScope_CAN_Scenario_Set.vi`へ渡す |

> **複数のCAN IDを同時に周期送信したい場合**：`SEND_SCENARIO`は`ScenarioNum`が0〜1、
> つまり**1回のCLFN発行で有効にできるシナリオは1系統のみ**だが、その中の`Step[64]`には
> **異なるCAN IDを混在させられる**ため、複数メッセージを1本のシナリオに時分割で
> 織り込むことは可能（例：10ms周期のIDを複数、100ms周期のIDを1つ、といった構成を
> `WaitTime`の積み上げで再現）。ただし周期が異なるメッセージを1本のシナリオに
> 正しく織り込むにはステップの並び・`WaitTime`を手計算する必要があり、64ステップの
> 制約と合わせて設計が複雑になる。**試験で実際に周期送信が必要なCAN IDが何個あるか
> によって設計方針が変わる**ため、次回までに対象IDを整理してもらえると具体化しやすい。

### STEP 5：`RAMScope_CAN_Scenario_Set.vi`（`ScenarioSendSet`）

10.4.2b「LabVIEW CLFNでのScenarioSendSetの扱い」の構造体サイズ
（`SEND_SCENARIO`=5396バイト）に従ってCLFN設定。`StepNum`・`Mode=0`・`Repeat=1`
（最終ステップ後は先頭へループ＝周期送信を継続）を基本とする。

- **アイドル中に発行しても即座には送信開始しない**（測定中に遷移して初めて動く）ため、
  STEP7のフロー確認では呼び出し順序に注意する。
- シナリオ送信中に本関数を再発行するとエラーになる（6.40.4節）。条件を変えて送り直す場合は
  先に`RAMScope_CAN_Scenario_Stop.vi`を呼ぶ。

### STEP 6：`RAMScope_CAN_Scenario_Start.vi` / `RAMScope_CAN_Scenario_Stop.vi`

`ScenarioSendStart`／`ScenarioSendStop`（10.4.2b確定）をそれぞれ薄くラップするだけ。
`Start`は**測定中でないと実際には動作しない**（アイドル中に発行すると次回測定開始まで
待機）ことを呼び出し側のコメントに明記しておく。

### STEP 7：`RAMScope_CAN_Flow_Test.vi`（フロー確認）

```
RAMScope_Connect → RAMScope_Init（MdlNo_RAM・MdlNo_CAN 取得）
  → RAMScope_Config（RAM）→ RAMScope_CAN_Set_Cond（CAN）
  → RAMScope_Set_Cond（RAM測定条件）→ RAMScope_Log_Start（＝測定中に遷移）
  → RAMScope_CAN_Scenario_Set → RAMScope_CAN_Scenario_Start
  → Wait（試験時間）
  → RAMScope_CAN_Scenario_Stop
  → RAMScope_Log_Stop → RAMScope_Close
```

**`RAMScopeGT170MeasStart`（測定開始）を挟んでから`ScenarioSendStart`を呼ぶ**のが要点
（シナリオ送信は測定動作中にのみ機能するため）。CANバスモニタ側で、
①アライブカウンタが0→1→2→3→0…と巡回、②チェックサムが受信側で不正判定されないこと、
の2点を確認する。

### STEP 8：TestStand への移行

STEP7で確認できたら、10.4.7の対応表と同様にSetup/Main/Cleanupへ配置する。
`Scenario_Stop`はCleanupで**条件によらず必ず通す**（FG420の`Output(OFF)`と同じ考え方、
[06](./06_VIの作り方_手順.md) 6.4.1／A1.6.1 STEP4）。

## 10.5 異常系での扱い（重要）

- RAMScope はエラー発生時、**一番最後にリセット**する。
- 順序：**DUT の電源を落としてから、RAMScope を落とす（リセット）**。
- `RAMScope_Reset.vi` を Cleanup の最後段に配置する（[12](./12_異常系処理とシャットダウン設計.md)）。

## 10.6 状況まとめと残課題

### 確定済み事項

| 項目 | 状況 |
|------|------|
| 実装方式 | **方式1（RAMScopeVP API / CLFN）** で進める |
| DLL 入手 | ✅ `RAMScopeVP_API.dll` / `GT170.dll` 等 入手済み |
| API 仕様書 | ✅ 入手済み（PDF。確認中） |
| `.h` / サンプル | ✅ **入手済み**（`RAMScopeVP.h`。[docs/reference/RAMScopeVP.h](./reference/RAMScopeVP.h) に保存）。全構造体・全関数プロトタイプが確定し、仕様書からの手動転記による誤りを2件修正（10.4.2c 参照）|
| **CAN 操作 API** | ✅ **全確定**：`SendCANDataFrame`(6.39)／`ScenarioSendSet`(6.40)／`ScenarioSendStart`(6.41)／`ScenarioSendStop`(6.42) 全プロトタイプ・構造体・エラーコード確定 |
| 接続・切断 API | ✅ `RAMScopeGT150DeviceInit` / `DeviceExit` 確定（プロトタイプ・エラーコード済） |
| GT170 機能一覧 | ✅ 測定設定・トリガ・RAM 書込・CAN・アナログの関数名確定 |

### 残課題（仕様書の追加ページ確認）

| 確認項目 | 仕様書の場所 | 状況 |
|----------|-------------|------|
| `DeviceInit` プロトタイプ・エラーコード | 6.2 章 | ✅ 確定 |
| `DeviceExit` プロトタイプ・エラーコード | 6.3 章 | ✅ 確定 |
| `AllInit` プロトタイプ・エラーコード・タイミング | 6.4 章 | ✅ 確定 |
| `GetSysInfo` プロトタイプ・SYSINFO 構造体 | 6.5 章 | ✅ 確定 |
| `SetMdlConfig` MDLCFG/MDLPSMCFG 構造体 | 6.6 章 | ✅ 確定（非推奨→PGT版使用）|
| GT150_IF 完全関数一覧 | 6.1.1 章 | ✅ 確定 |
| GT170_IF 完全関数一覧 | 6.1.2 章 | ✅ 確定 |
| **測定開始 `RAMScopeGT150MeasStart(long)`** | 6.9 章 | ✅ プロトタイプ・エラーコード確定 |
| **測定停止 `RAMScopeGT150MeasStop(long)`** | 6.10 章 | ✅ プロトタイプ・エラーコード確定 |
| **データ読み出し `RAMScopeGT150GetBufferData`** | 6.29 章（表 6-178〜180） | ✅ プロトタイプ・エラーコード確定 |
| `RAMScopeGT170SetMeasCond` 引数・`MEASINFO_170` union | 6.13 章（表 6-74〜78） | ✅ RAM/ADC/CAN 構造体確定・周期範囲・SmpCnt 制約・互換性注記すべて確定 |
| **`PGT_SetMdlConfig` 引数** | 6.7 章（表 6-38） | ✅ プロトタイプ確定（UnitNo/SlotErr[16]）|
| **データ取得 API 一覧** | GT150_IF 表6-5 | ✅ GetBufferData(6.29)・GetLoggingData(6.31) ほか7関数確定 |
| **測定データパケット構造（RAM・CAN）** | 7.1 章（表7-1,7-2）・7.3 章（表7-5,7-6）| ✅ パケットサイズ・フラグ情報すべて確定（RAM: `4N+12`byte／CAN: 固定84byte）|
| 測定データパケット構造（アナログ入力）| 「7 測定データの構成」章（ADC節）| ⬜ 未確認 |
| **`RAMScopeGT170SendCANDataFrame` 引数詳細** | 6.39 章（表6-221〜226）| ✅ プロトタイプ・`CANSEND_170_INFO/DATA`構造体・エラーコード確定（.h でも一致確認）|
| **`RAMScopeGT170ScenarioSendSet` 引数詳細** | 6.40 章（表6-227〜232）| ✅ プロトタイプ・`SEND_SCENARIO`構造体・エラーコード確定（関数名誤り修正済み・.h でも一致確認）|
| **`RAMScopeGT170ScenarioSendStart` 引数詳細** | 6.41 章（表6-233〜236）| ✅ プロトタイプ・エラーコード確定 |
| **`RAMScopeGT170ScenarioSendStop` 引数詳細** | 6.42 章（表6-237〜240）| ✅ プロトタイプ・エラーコード確定 |
| **`RAMScopeGT170SetMeasCh` + `CHINFO_170` 構造体** | 6.15 章 | ✅ `.h` ヘッダで確定（10.4.2c）|
| **`RAMScopeGT150SetLoggingInfo` + `LOGINFO` 構造体** | 6.16 章 | ✅ `.h` ヘッダで確定（10.4.2c）|
| **`RAMScopeGT170SetEventCond` + `EVENTINFO_170` 構造体** | 6.19 章 | ✅ `.h` ヘッダで確定（10.4.2c）|
| **`RAMScopeGT170SetExternalTrigger` + `EXTTRG_INFO_170` 構造体** | 6.23 章 | ✅ `.h` ヘッダで確定（10.4.2c）|
| **`RAMScopeGT170SetMeasTrigger` + `MEASTRG_INFO_170` 構造体** | 6.24 章 | ✅ `.h` ヘッダで確定（10.4.2c）|
| **`RAMScopeGT170ScenarioWriteStart/Stop` + `WRITE_SCENARIO` 構造体** | 6.36/6.37 章 | ✅ `.h` ヘッダで確定（10.4.2c）|
| **測定データ取得API全プロトタイプ**（GetGapTime/GetMeasNum/GetBlockNum/GetLoggingDataNum/GetLoggingData）| 6.25〜6.31 章 | ✅ `.h` ヘッダで確定（10.4.2c）|
| **RAM モニタ メモリ読み書き**（MemoryRead/Write/ContinualyMemoryRead/Write）+ `CONT_MEM_WR/RD` | 6.32〜6.35 章 | ✅ `.h` ヘッダで確定（10.4.2c）|
| **`RAMScopeGT150PGT_ModifyMdlConfig`**（未発見だった関数）| 6.8 章 | ✅ `.h` ヘッダで新規発見・プロトタイプ確定（用途の詳細は仕様書本文要確認）|
| `RAMScopeGT150/GT170SetAdcRange` | 6.43/6.44 章 | ✅ `.h` ヘッダで確定（10.4.2c）|
| **呼び出し規約**（`__stdcall` か `__cdecl` か） | `samp_simple.vcxproj` のビルド設定 | 🟡 **`__cdecl` の可能性が高いと判明**（規約明示指定なし＝MSVCデフォルト。断定はできず実機確認要。32bit版でのみ必要。10.4.2d ⑦・下記「重大な問題」参照）|
| DLL の **ビット数**（32 / 64bit） | Python スクリプトで PE ヘッダの Machine フィールドを直接確認 | 🔴 **確認済み：全て32bit**（下記参照）|

> 🔴 **`.h` ヘッダ入手による誤り修正（重要）**：
> - `MEASINFO_RAM170.MeasPeri_reserve` は `long` 単体ではなく **`long[2]`（配列）** ＝ 20バイト（旧: 16バイトは誤り）
> - `MEASINFO_CAN170.isUseFDFormat` は `char` ではなく **`long`** ＝ パディングなし（旧: 3バイトパディングは誤り）
> - `SYSINFO.module_type` の**アナログ入力モジュールは `0x03`**（`GTHard.h` で確定）。
>   旧記述の「`0xE` 相当」は誤りで、`0x0E` は実際には**電源通信(CTRL_USB)モジュール**の値だった。
> - 詳細・修正版の構造体定義は 10.4.2a 内 `MEASINFO_170`／`SYSINFO` セクション参照。

### ✅ 解決済み：DLL が 32bit・LabVIEW が 64bit（アーキテクチャ不一致）だった問題

当初入手した DLL（`RAMScopeVP_API.dll` / `GT170.dll` / `GT170USB.dll`）を PE ヘッダの
`Machine` フィールドで確認したところ、**全て `0x014c`（x86 / 32bit）** であることが確認され、
64bit版LabVIEWとのアーキテクチャ不一致が問題となっていた。

**その後、DTSインサイトから64bit版DLLを入手し、この問題は解消済み**（10.4.10 STEP0参照）。
64bit版のため、呼び出し規約（`__stdcall`/`__cdecl`）の論点も消滅している
（x64 ABIには区別が無いため）。以降の実装はすべてこの64bit DLLを前提とする。
32bit版LabVIEWの併用やサロゲートEXE経由の代替案は不要になった。

### 🔴 確定：RAMScope（GT170U01）は RAMScopeVP API 用に USB3.0 接続が必須（LAN 接続不可）

製品ページ（電源通信モジュール `GT170U01` のスペック表）にて **PC-I/F の仕様が確定**した。

| インターフェース | 用途 |
|-----------------|------|
| **Ethernet（GbEthernet）** | **XCP on Ethernet 用**（RAMScopeVP API とは別プロトコル） |
| **USB3.0** | **RAMScopeVP 用**、Ethernet メンテ用 |

つまり、**RAMScopeVP API（本ドキュメントで解読している一連の関数群）を使う場合、
GT170U01 との接続は USB3.0 一択であり、Ethernet では代替できない**ことが確定した。
GT170U01 の Ethernet ポートは XCP（Universal Measurement and Calibration Protocol）という
**別のプロトコル・別の実装が必要な通信方式**専用であり、今回実装している
RAMScopeGT150/GT170 系 API とは互換性がない。

**結論として、システム構成図の「全機器イーサネット化」方針からは RAMScope のみ除外し、
USB3.0 接続を前提に設計する。** 上記 10.6 の代替案のうち **案A（RAMScope のみ PC1 に
USB3.0 直結）で構成確定**。

**最終システム構成（確定）：**

```
オシロ(DLM5058)/ロガー(MX100)/BTS×4/制御電源(PPX36-3)/IGS電源(PPX36-3)
        │ Ethernet                                          │ Ethernet
        └──────────────► ネットワークハブ ◄──────────────────┘
                              │ Ethernet
                              ▼
                            PC1 ◄──────USB3.0──────  RAMScope(GT170)
                                                            │
                                                      FCAN×2 (RAM/CANモニタ用プローブ)
                                                            ▼
                                                      供試体 Assy（恒温槽内）
```

- **RAMScope のみ PC1 に USB3.0 直結**。他機器はすべて Ethernet 経由でネットワークハブに接続。
- RAMScope から供試体へは **FCAN×2**（RAMモニタ用プローブ／CANモニタ用プローブ）で接続。
- 案B（USB-Ethernet 変換機器）・案C（仲介PC+TCPサーバ）は不採用（USB3.0 直結で決着）。

> **XCP on Ethernet について（参考）**：もし将来的に ECU 側のキャリブレーション・
> 測定を XCP プロトコルで行いたい要件が出てきた場合は、本ドキュメントの
> RAMScopeVP API とは全く別の実装（XCP クライアントライブラリ、または
> 対応 ASAM XCP ドライバ）が必要になる。現時点のスコープ外。
