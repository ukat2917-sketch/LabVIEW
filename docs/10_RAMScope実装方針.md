# 10. RAMScope（GT170）実装方針

RAMScope（GT170、CAM モジュール付）で **RAM の計測** と **CAN 操作** を LabVIEW から行うための
実装方式を比較・選定する。

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

**呼び出しライフサイクル（確定）：**

```
[オフライン]
    ↓ RAMScopeGT150DeviceInit()    ← USB 接続・ハードウェア検出
[アイドル]
    ↓ RAMScopeGT150AllInit()       ← API + ハードウェア初期化（設定を全クリア）
[アイドル]                            ※ DeviceInit 後に必ず呼ぶ。呼ぶたびに設定リセット
    ↓ RAMScopeGT150GetSysInfo()    ← モジュール構成確認（任意。アイドルのみ可）
    ↓ RAMScopeGT170SetMeasCond()   ← 測定条件設定（GT170 固有）
    ↓ RAMScopeGT170SetMeasCh()     ← チャネル設定（GT170 固有）
    ↓ [計測開始]                   ← 未確認（仕様書の続きページで確認）
[測定中]
    ↓ [データ読み出し]             ← 未確認
    ↓ [計測停止]                   ← 未確認
[アイドル]
    ↓ RAMScopeGT150DeviceExit()    ← 接続を破棄
[オフライン]
```

> GT150_IF 共通関数（`DeviceInit` / `AllInit` / `GetSysInfo` / `DeviceExit`）は
> **GT170 でも必須**。これらはライフサイクル管理であり、GT170 固有の測定関数は
> `AllInit` 完了後（アイドル状態）でないと呼べない。

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
```

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
| **CAN シナリオ** | **`RAMScopeGT170ScenarioSendCond()`** | 6.40 |
| **CAN シナリオ** | **`RAMScopeGT170ScenarioSendStart()`** | 6.41 |
| **CAN シナリオ** | **`RAMScopeGT170ScenarioSendStop()`** | 6.42 |
| アナログ入力 | `RAMScopeGT170SetAdcRange()` | 6.44 |

> **CAN 操作は RAMScopeVP API で確定**（`RAMScopeGT170SendCANDataFrame` / `ScenarioSend*`）。
> 10.6 の「未確定事項」から除去。

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
- 測定開始・停止関数（`RAMScopeGT150Meas*` 相当）
- データ読み出し関数（RAM 値取得）
- 呼び出し規約（`__stdcall` か `__cdecl` か）

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

| VI | TestStand の配置 | ラップする API | 入出力 |
|----|-----------------|----------------|--------|
| `RAMScope_Connect.vi` | Setup (1回) | `RAMScopeGT150DeviceInit()` | out: kind（機種確認用）・Status・TestError |
| `RAMScope_Init.vi` | Setup (Connect直後) | `RAMScopeGT150AllInit(UnitNo=0)` + `RAMScopeGT150GetSysInfo(UnitNo=0, pSysInfo[16])` | out: SYSINFO配列（モジュール構成確認）・Status・TestError |
| `RAMScope_Set_Cond.vi` | Setup (条件設定) | `RAMScopeGT170SetMeasCond()` + `RAMScopeGT170SetMeasCh()` | in: 測定条件パラメータ（TestStand変数）/ out: Status・TestError |
| `RAMScope_Log_Start.vi` | Main | 計測開始 API（**仕様書続きページで確認**） | out: Status・TestError |
| `RAMScope_Read.vi` | Main（ポーリング） | データ読み出し API（**仕様書続きページで確認**） | out: **RAM 値（配列）**・Status・TestError |
| `RAMScope_Log_Stop.vi` | Main | 計測停止 API（**仕様書続きページで確認**） | out: Status・TestError |
| `RAMScope_Close.vi` | Cleanup（最後段） | `RAMScopeGT150DeviceExit()` | out: Status・TestError |
| `CAN_Send.vi`（RAMScope 経由） | Main | `RAMScopeGT170SendCANDataFrame()` | [09](./09_CAN通信の実装.md) の入出力に整合 |
| `CAN_Scenario_Start.vi` | Main | `RAMScopeGT170ScenarioSendCond()` + `RAMScopeGT170ScenarioSendStart()` | in: シナリオ設定 / out: Status・TestError |
| `CAN_Scenario_Stop.vi` | Main | `RAMScopeGT170ScenarioSendStop()` | out: Status・TestError |

> **ハンドルなし構造**：`DeviceInit` はセッションハンドルを返さない（グローバル状態管理）。
> VISA のようなリファレンス引き回しは不要。VI 間でつなぐのはエラークラスタのみ。
>
> **AllInit の注意**：呼ぶたびに全測定設定がクリアされる。再試験で条件を変えたい場合は
> `AllInit` → `SetMeasCond/Ch` を再度実行すること。

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
| **CAN 操作 API** | ✅ **確定**：`RAMScopeGT170SendCANDataFrame()` / `ScenarioSend*()` あり |
| 接続・切断 API | ✅ `RAMScopeGT150DeviceInit` / `DeviceExit` 確定（プロトタイプ・エラーコード済） |
| GT170 機能一覧 | ✅ 測定設定・トリガ・RAM 書込・CAN・アナログの関数名確定 |

### 残課題（仕様書の追加ページ確認）

| 確認項目 | 仕様書の場所 | 状況 |
|----------|-------------|------|
| `DeviceInit` プロトタイプ・エラーコード | 6.2 章 | ✅ 確定 |
| `DeviceExit` プロトタイプ・エラーコード | 6.3 章 | ✅ 確定 |
| `AllInit` プロトタイプ・エラーコード・タイミング | 6.4 章 | ✅ 確定 |
| `GetSysInfo` プロトタイプ・SYSINFO 構造体定義 | 6.5 章 | ✅ 確定 |
| GT170 固有関数一覧（測定設定・トリガ・CAN 等） | 6.1.2 章 | ✅ 確定 |
| **測定開始関数**のプロトタイプ | 仕様書の測定開始章 | ⬜ 未確認 |
| **測定停止関数**のプロトタイプ | 仕様書の測定停止章 | ⬜ 未確認 |
| **データ読み出し関数**（バッファ構造含む） | 仕様書の読み出し章 | ⬜ 未確認 |
| `RAMScopeGT170SetMeasCond` の引数・構造体 | 6.13 章 | ⬜ 未確認 |
| `RAMScopeGT170SetMeasCh` の引数 | 6.15 章 | ⬜ 未確認 |
| `RAMScopeGT170SendCANDataFrame` の引数詳細 | 6.39 章 | ⬜ 未確認 |
| **呼び出し規約**（`__stdcall` か `__cdecl` か） | 仕様書冒頭・任意の関数宣言行 | ⬜ 未確認 |
| DLL の **ビット数**（32 / 64bit） | `dumpbin /headers` で確認 | ⬜ 未確認 |
