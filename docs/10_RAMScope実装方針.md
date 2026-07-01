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
   → 🔴 **確認済み：入手済み DLL（`RAMScopeVP_API.dll`/`GT170.dll`/`GT170USB.dll`）は全て 32bit**。
   　 開発環境の LabVIEW は 64bit のため **アーキテクチャ不一致**。詳細・対応方針は 10.6 章参照。
   　 現在 DTS インサイトへ 64bit ネイティブライブラリの提供を問い合わせ中。
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

**呼び出しライフサイクル（確定）：**

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
    ↓ RAMScopeGT150ReleaseBufferData(...)           ← バッファ解放
    ↓ RAMScopeGT150DeviceExit()                    ← 接続破棄
[オフライン]
```

> **GT170 での関数選択ルール**：
> - 測定条件・チャネル・トリガ設定：GT170専用版（`RAMScopeGT170*`）を使う
> - ライフサイクル・測定開始停止・バッファ解放：GT150共通版（`RAMScopeGT150*`）を使う
> - GT150_IF 共通関数は GT170 でも必須（ライフサイクル管理の主体）。

> **`SetMdlConfig` の注意**：`RAMScopeGT150SetMdlConfig()` は非推奨。
> **`RAMScopeGT150PGT_SetMdlConfig()`（PGT使用版）を使うこと**。
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

**MEASINFO_170 共用体・構造体定義（`SetMeasCond` 用、表 6-74〜6-76）：**

```c
/* 共用体：モジュール種別に応じたメンバを使う */
typedef union MEASINFO_170 {
    MEASINFO_RAM170  RAM;   /* RAMモニタモジュール用（module_type=0x0） */
    MEASINFO_ADC170  ADC;   /* アナログ入力モジュール用（module_type=0xE 相当） */
    MEASINFO_CAN170  CAN;   /* CAN モジュール用（module_type=0x2）（構造体定義は表6-77→未確認）*/
} MEASINFO_170;

/* RAM モニタモジュール用（表 6-75）*/
typedef struct MEASINFO_RAM170 {
    long DummyInterval;      /* [将来拡張用] ダミーパケット生成周期(usec)。常に 100 を指定 */
    long MeasPeri;           /* 測定周期：1〜999999 */
    long MeasUnit;           /* 測定周期の単位：1=usec / 2=msec */
    long MeasPeri_reserve;   /* [将来拡張用] 現版数では常に 1 を指定 */
} MEASINFO_RAM170;
/* サイズ = long×4 = 16 バイト */

/* アナログ入力モジュール用（表 6-76）*/
typedef struct MEASINFO_ADC170 {
    long DummyInterval;      /* ダミーパケット生成周期(usec)。常に 100 を指定 */
    long MeasPeri;           /* 測定周期：1〜999999 */
    long MeasUnit;           /* 測定周期の単位：1=usec / 2=msec */
} MEASINFO_ADC170;
/* サイズ = long×3 = 12 バイト */

/* CAN モジュール用（表 6-77）*/
typedef struct MEASINFO_CAN170 {
    long             DummyInterval;  /* [将来拡張用] ダミーパケット生成周期(usec)。常に 100 */
    char             isUseFDFormat;  /* パケットフォーマット：0=CAN 2.0B(GT150互換) / 1=CAN FD(推奨) */
    /* ← char の後に 3 バイトパディングが入る（Ch の 4 バイトアライン） */
    MEAS_CAN_CH_170  Ch[2];          /* 物理 Ch 毎の設定（Ch[0]=Ch1, Ch[1]=Ch2）*/
} MEASINFO_CAN170;
/* サイズ = 4(long) + 1(char) + 3(padding) + 32×2(Ch[2]) = 72 バイト */

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

> **MEASINFO_170 union サイズ（確定）：**
> - MEASINFO_RAM170 = 16 バイト
> - MEASINFO_ADC170 = 12 バイト
> - MEASINFO_CAN170 = **72 バイト**（最大）
> - **union サイズ = 72 バイト**（CLFN で確保する U8 配列のサイズ）

> **使い方例：**
> ```c
> /* RAM モニタの測定条件設定（module_type=0x0 のモジュールに対して発行）*/
> MEASINFO_170 info;
> memset(&info, 0, sizeof(info));
> info.RAM.DummyInterval    = 100;  // 固定
> info.RAM.MeasPeri         = 1000; // 1000 usec = 1ms 周期
> info.RAM.MeasUnit         = 1;    // 1=usec
> info.RAM.MeasPeri_reserve = 1;    // 固定
> RAMScopeGT170SetMeasCond(0, mdlNo_RAM, &info);
>
> /* CAN モジュールの測定条件設定（module_type=0x2 のモジュールに対して発行）*/
> memset(&info, 0, sizeof(info));
> info.CAN.DummyInterval    = 100;       // 固定
> info.CAN.isUseFDFormat    = 1;         // CAN FD フォーマット推奨
> info.CAN.Ch[0].Enable     = 1;         // Ch1 有効
> info.CAN.Ch[0].MonitorOnly= 1;         // モニタのみ（Ack なし）
> info.CAN.Ch[0].BaudRate   = 0x9;       // 500kbps（対象バスに合わせる）
> info.CAN.Ch[0].BusMode    = 0;         // CAN 2.0B（isUseFDFormat=0時は必ず0）
> RAMScopeGT170SetMeasCond(0, mdlNo_CAN, &info);
> ```

> **CLFN での union の扱い（確定）**：
> LabVIEW では **`Initialize Array`（U8 配列、72 要素）** を確保して各フィールドを
> バイト順に埋め（`Insert Into Array` / 直接配線）、`Array Data Pointer` で渡す。
> フィールドのオフセット計算は下記の通り（little-endian, 32bit long 前提）：
>
> | フィールド | オフセット | サイズ |
> |-----------|-----------|--------|
> | DummyInterval（RAM/ADC/CAN 共通先頭）| 0 | 4 |
> | RAM: MeasPeri | 4 | 4 |
> | RAM: MeasUnit | 8 | 4 |
> | RAM: MeasPeri_reserve | 12 | 4 |
> | CAN: isUseFDFormat | 4 | 1 |
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

**SYSINFO 構造体定義（`GetSysInfo` 用）：**

```c
typedef struct SYSINFO {
    long module;            /* モジュール番号 */
    long module_type;       /* モジュールタイプ: 0x0=RAMモニタ/光RAMモニタ, 0x2=CAN,
                               0xE=電源通信, 0xF=非接続 */
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

| カテゴリ | 関数名 | 章 |
|---------|--------|-----|
| 測定設定 | `RAMScopeGT170SetMeasCond()` | 6.13 |
| 測定設定 | `RAMScopeGT170SetMeasCh()` | 6.15 |
| トリガ設定 | `RAMScopeGT170SetEventCond()` | 6.19 |
| トリガ設定 | `RAMScopeGT170SetExternalTrigger()` | 6.23 |
| トリガ設定 | `RAMScopeGT170SetMeasTrigger()` | 6.24 |
| RAM 書き込み | `RAMScopeGT170ScenarioWriteStart()` | 6.36 |
| RAM 書き込み | `RAMScopeGT170ScenarioWriteStop()` | 6.37 |
| **CAN 送信** | **`RAMScopeGT170SendCANDataFrame()`** | 6.39 |
| **CAN シナリオ** | **`RAMScopeGT170ScenarioSendSet()`** | 6.40 |
| **CAN シナリオ** | **`RAMScopeGT170ScenarioSendStart()`** | 6.41 |
| **CAN シナリオ** | **`RAMScopeGT170ScenarioSendStop()`** | 6.42 |
| アナログ入力 | `RAMScopeGT170SetAdcRange()` | 6.44 |

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
| `.h` / サンプル | ❌ 未同梱。仕様書の関数宣言表から代替可能（10.4.1） |
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
| **`RAMScopeGT170SendCANDataFrame` 引数詳細** | 6.39 章（表6-221〜226）| ✅ プロトタイプ・`CANSEND_170_INFO/DATA`構造体・エラーコード確定 |
| **`RAMScopeGT170ScenarioSendSet` 引数詳細** | 6.40 章（表6-227〜232）| ✅ プロトタイプ・`SEND_SCENARIO`構造体・エラーコード確定（関数名誤り修正済み）|
| **`RAMScopeGT170ScenarioSendStart` 引数詳細** | 6.41 章（表6-233〜236）| ✅ プロトタイプ・エラーコード確定 |
| **`RAMScopeGT170ScenarioSendStop` 引数詳細** | 6.42 章（表6-237〜240）| ✅ プロトタイプ・エラーコード確定 |
| **呼び出し規約**（`__stdcall` か `__cdecl` か） | 仕様書冒頭・任意の関数宣言行 | ⬜ 未確認（32bit版でのみ必要。下記「重大な問題」参照）|
| DLL の **ビット数**（32 / 64bit） | Python スクリプトで PE ヘッダの Machine フィールドを直接確認 | 🔴 **確認済み：全て32bit**（下記参照）|

### 🔴 重大な問題：DLL が 32bit・LabVIEW が 64bit（アーキテクチャ不一致）

入手済みの DLL（`RAMScopeVP_API.dll` / `GT170.dll` / `GT170USB.dll`）を PE ヘッダの
`Machine` フィールドで確認したところ、**全て `0x014c`（x86 / 32bit）** であることが確認された。
一方、開発環境の LabVIEW は **64bit 版**であるため、このままでは CLFN が DLL を
ロードできない（**ビット数不一致でロードエラーになる**）。

**現状の対応：**
- ユーザーが **DTS インサイトへ問い合わせ、64bit ネイティブライブラリの提供を依頼済み**
  （DTS インサイト公式サイトに「64bit ネイティブライブラリは問い合わせにより入手可能」との記載あり）。
- 回答待ちのステータス。64bit 版 DLL が入手できれば、本問題は解消し、
  かつ **呼び出し規約の論点も消滅する**（x64 ABI には `__stdcall`/`__cdecl` の区別がないため）。

**回答が得られない・64bit版が提供されない場合の代替案：**
1. **32bit 版 LabVIEW を別途インストール**し、RAMScope 制御用 VI 群だけ 32bit LabVIEW で
   作成・実行する（TestStand からは 32bit 版シーケンスエディタ／別プロセス経由で呼び出す）。
   計測器ドライバが 32bit 専用というケースは珍しくなく、最も確実な方法。
2. 32bit DLL 専用の**仲介プロセス（サロゲート EXE）** を作成し、64bit LabVIEW とは
   named pipe / TCP 等の IPC で通信する方式（実装コストが高いため優先度低）。

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
USB3.0 接続を前提に設計する必要がある。** 上記 10.6 の代替案のうち：

- **案A（RAMScope だけ PC1 に USB3.0 直結）を第一候補として推奨**する。
  他機器（オシロ・ロガー・電源）は LAN 対応済みのためハブ経由、RAMScope のみ
  PC1 に USB3.0 ケーブルで直結する構成となる。物理的に RAMScope を PC1 の近くに
  設置できるかがレイアウト上の制約になる。
- 案B（USB-Ethernet 変換機器）・案C（仲介PC+TCPサーバ）は、PC1 と RAMScope を
  物理的に離す必要がある場合のみ検討（レイテンシ・実装コストの観点で優先度は低い）。

> **XCP on Ethernet について（参考）**：もし将来的に ECU 側のキャリブレーション・
> 測定を XCP プロトコルで行いたい要件が出てきた場合は、本ドキュメントの
> RAMScopeVP API とは全く別の実装（XCP クライアントライブラリ、または
> 対応 ASAM XCP ドライバ）が必要になる。現時点のスコープ外。
