# 10A. RAMScope 実装手順：DLL準備・CLFN疎通確認

本章は、[10_RAMScope実装方針.md](./10_RAMScope実装方針.md) に整理した API 関数仕様を、
実際の LabVIEW VI へ実装する前段の**作業手順書**としてまとめたものである。

特に、2026-07-14 に確認した次の問題を再発防止事項として反映する。

- 64bit版 `RAMScopeVP_API_x64.dll` 自体は存在し、対象関数もエクスポートされている
- それでも LabVIEW の CLFN から関数を認識できない
- PowerShell の DLL ロード確認でエラー `193 (0xC1)` が発生する
- 64bit API フォルダ内に 32bit版の Visual C++ 2013 ランタイム DLL が混在していた
- 該当する 32bit ランタイムを隔離し、x64 ランタイムを利用可能にした後、DLL と関数の認識に成功した

---

## 10A.1 適用範囲

対象構成は次のとおり。

| 項目 | 対象 |
|------|------|
| RAMScope | GT170 |
| API | RAMScopeVP API 64bit版 |
| API DLL | `RAMScopeVP_API_x64.dll` |
| LabVIEW | 64bit版 |
| 呼び出し方式 | Call Library Function Node（CLFN） |
| TestStand | Setup / Main / Cleanup から 1イベント1VI で呼び出す |

本章は、最初の疎通確認関数として次を使用する。

```c
long RAMScopeGT150DeviceInit(long *pUnitNum, long *kind);
```

GT170 を使用する場合でも、接続・初期化・終了などのライフサイクル管理には
`RAMScopeGT150*` の共通関数を使用する。

---

## 10A.2 本システムの実装ルール

RAMScope 系 VI も、[05_VI設計方針と共通仕様.md](./05_VI設計方針と共通仕様.md) と
[06_VIの作り方_手順.md](./06_VIの作り方_手順.md) の共通ルールに従う。

### 10A.2.1 1イベント1VI

| イベント | VI名 |
|----------|------|
| デバイス接続 | `RAMScope_Connect.vi` |
| API・ハードウェア初期化 | `RAMScope_Init.vi` |
| プローブ構成適用 | `RAMScope_Config.vi` |
| 測定条件設定 | `RAMScope_Set_Cond.vi` |
| 計測開始 | `RAMScope_Log_Start.vi` |
| データ取得 | `RAMScope_Read.vi` |
| 計測停止 | `RAMScope_Log_Stop.vi` |
| バッファ解放 | `RAMScope_Release.vi` |
| デバイス終了 | `RAMScope_Close.vi` |

### 10A.2.2 エラー経路を2系統に分ける

CLFN の標準 `error in / error out` と、RAMScope API の戻り値は別物である。

```text
CLFN error out
  └─ DLL未検出、関数未検出、呼び出し失敗など LabVIEW 側のエラー

RAMScope API 戻り値
  └─ デバイス未接続、設定不正、状態遷移不正など API 側の結果コード
```

したがって、`error out` が「エラーなし」でも、RAMScope API の戻り値が異常コードになる場合がある。

RAMScope API の戻り値は次の順で変換する。

```text
CLFN戻り値(I32)
  → RAMScope_Code_To_Error.vi
  → Error_To_TestStatus.vi
  → Status.ctl / TestError.ctl / error out
```

### 10A.2.3 TestStand 側の配置

```text
Setup
  RAMScope_Connect.vi
  RAMScope_Init.vi
  RAMScope_Config.vi
  RAMScope_Set_Cond.vi

Main
  RAMScope_Log_Start.vi
  RAMScope_Read.vi
  RAMScope_Log_Stop.vi
  RAMScope_Release.vi（要否は実機検証で確定）

Cleanup
  RAMScope_Close.vi
```

待ち時間、繰り返し条件、タイムアウト、異常時の分岐は TestStand 側で管理する。

---

## 10A.3 必要ファイルと配置

### 10A.3.1 使用したパス

```text
API DLL:
C:\DTSinsight\RAMScopeVP\app\RAMScopeVP_API(64bit)\RAMScopeVP_API_x64.dll

ヘッダ:
C:\DTSinsight\RAMScopeVP_API\header\RAMScopeVP.h
```

### 10A.3.2 ベンダーマニュアルに従う相対配置

`RAMScopeVP_API_x64.dll` を起点として、関連ファイルの相対位置を維持する。

```text
RAMScopeVP_API(64bit)\
├─ RAMScopeVP_API_x64.dll
├─ UtilLCServer.exe
├─ utillc.dll
├─ PGTMgrServer.exe
├─ PGTMgrVP.dll
├─ PGTMgrVP_ENG.dll
├─ GT170_x64.dll
├─ GT170USB_x64.dll
└─ pgtlib\
     ├─ PGT10xX0x.dll
     └─ PGT10xX0x_ENG.dll
```

注意点：

- `RAMScopeVP_API_x64.dll` は任意のフォルダへ配置可能
- `UtilLCServer.exe`、`PGTMgrServer.exe`、`GT170_x64.dll`、`GT170USB_x64.dll` は API DLL と同じフォルダ
- `utillc.dll` は `UtilLCServer.exe` と同じフォルダ
- `PGTMgrVP.dll` / `PGTMgrVP_ENG.dll` は `PGTMgrServer.exe` と同じフォルダ
- `PGT10xX0x*.dll` は API DLL フォルダ直下の `pgtlib` フォルダに格納
- 「64bit フォルダにあるファイルを一律で削除・移動する」運用は禁止

---

## 10A.4 Visual C++ ランタイムの考え方

### 10A.4.1 役割

Visual C++ Redistributable は RAMScope の USB ドライバではない。
RAMScope の DLL が内部で使用する Microsoft C/C++ 共通ライブラリを Windows へ提供する。

```text
64bit LabVIEW
  → RAMScopeVP_API_x64.dll
    → Visual C++ ランタイム
```

### 10A.4.2 今回確認したランタイム世代

問題が発生したフォルダには、次の `120` 系 DLL が存在していた。

```text
mfc120jpn.dll
mfc120u.dll
msvcp120.dll
msvcr120.dll
```

`120` 系は Visual C++ 2013（v12）世代である。
Visual C++ 2015-2022（v14）をインストールしても、Visual C++ 2013 の代替にはならない。

本構成では、次を前提条件とする。

> **Visual C++ 2013 Redistributable（x64）が利用可能であること。**

既にインストール済みの場合は再インストール不要。
未導入、破損、または x86 版しかない場合は x64 版を導入する。

Visual C++ 2015-2022 Redistributable（x64）は、他コンポーネントが要求する場合に導入するが、
今回の `120` 系依存関係に対する直接の代替ではない。

---

## 10A.5 既知事象：CLFN が関数を認識しない

### 10A.5.1 現象

- CLFN で `RAMScopeVP_API_x64.dll` を指定しても `RAMScopeGT150DeviceInit` を認識できない
- `GetProcAddress` で関数アドレスを取得できない
- DLL ロード時に次のエラーが発生する

```text
Error 193 (0xC1)
%1 は有効な Win32 アプリケーションではありません。
```

### 10A.5.2 確認結果

静的な PE 解析では次を確認した。

```text
DLL                : RAMScopeVP_API_x64.dll
Architecture       : x64
Named exports      : 182
Function           : RAMScopeGT150DeviceInit
Ordinal            : 14
```

したがって、DLL 本体とエクスポート関数は存在していた。

一方、同じフォルダには次の x86 DLL が混在していた。

```text
mfc120jpn.dll
mfc120u.dll
msvcp120.dll
msvcr120.dll
```

DLL ローダーは対象 DLL と同じフォルダにある同名依存 DLL を優先的に解決する場合がある。
そのため、x64 プロセスがローカルの x86 ランタイムを読み込もうとして、エラー193になった可能性が高い。

### 10A.5.3 対策

次の4ファイルだけを、復元可能なバックアップフォルダへ隔離する。

```text
mfc120jpn.dll
mfc120u.dll
msvcp120.dll
msvcr120.dll
```

移動先例：

```text
C:\DTSinsight\RAMScopeVP\app\RAMScopeVP_API(64bit)\_x86_runtime_backup
```

PowerShell 例：

```powershell
$root = "C:\DTSinsight\RAMScopeVP\app\RAMScopeVP_API(64bit)"
$backup = Join-Path $root "_x86_runtime_backup"

New-Item -ItemType Directory -Path $backup -Force | Out-Null

@(
    "mfc120jpn.dll",
    "mfc120u.dll",
    "msvcp120.dll",
    "msvcr120.dll"
) | ForEach-Object {
    $source = Join-Path $root $_
    if (Test-Path -LiteralPath $source) {
        Move-Item -LiteralPath $source -Destination $backup -Force
    }
}
```

### 10A.5.4 移動してはいけないファイル

次のファイルは、ベンダー指定の相対配置を維持する。

```text
PGTMgrVP.dll
PGTMgrVP_ENG.dll
utillc.dll
pgtlib\*.dll
```

これらはサーバー EXE や PGT 構成と連携する可能性があるため、
「x86 と判定された DLL を一律で隔離する」対策は行わない。

---

## 10A.6 LabVIEW 実装前の DLL 疎通確認

CLFN を作成する前に、64bit PowerShell から DLL と関数を確認する。

本リポジトリのスクリプトを使用する。

```powershell
powershell.exe -ExecutionPolicy Bypass `
  -File .\scripts\Test-RAMScopeDll.ps1 `
  -DllPath "C:\DTSinsight\RAMScopeVP\app\RAMScopeVP_API(64bit)\RAMScopeVP_API_x64.dll" `
  -ExportName "RAMScopeGT150DeviceInit" `
  -ExportOrdinal 14
```

### 10A.6.1 合格条件

```text
PowerShell 64-bit : True
Loaded module path: 指定した RAMScopeVP_API_x64.dll
Handle            : 0x0 以外
Name Found        : True
Ordinal Found     : True
名前と序数の Address が一致
```

### 10A.6.2 実測結果

```text
PowerShell 64-bit : True
Loaded module path: C:\DTSinsight\RAMScopeVP\app\RAMScopeVP_API(64bit)\RAMScopeVP_API_x64.dll
Handle            : 非ゼロ
Name Found        : True
Ordinal Found     : True
```

DLL と `RAMScopeGT150DeviceInit` の認識に成功した。

### 10A.6.3 注意

`Handle: 0x0` は必ずロード失敗である。
表示上「DLLロード成功」と出ていても、ハンドルが `0x0` の場合は成功扱いしない。
無効なハンドルへ `GetProcAddress` を実行すると、二次的にエラー127が発生し、
「関数が存在しない」と誤判定する可能性がある。

---

## 10A.7 `RAMScope_Connect.vi` の作成

### 10A.7.1 ヘッダ定義

`RAMScopeVP.h` の定義：

```c
typedef long (*RAMScopeGT150DeviceInitPtr)(long *pUnitNum, long *kind);
```

実質的な関数プロトタイプ：

```c
long RAMScopeGT150DeviceInit(long *pUnitNum, long *kind);
```

Windows の `long` は 32bit であるため、LabVIEW では I32 を使用する。
64bit DLL だからといって I64 にしない。

### 10A.7.2 CLFN 設定

| 項目 | 設定 |
|------|------|
| Library name or path | `RAMScopeVP_API_x64.dll` のパス |
| Function name | `RAMScopeGT150DeviceInit` |
| Calling convention | C |
| Thread | 最初は UI thread |
| Error checking | PoC 中は Maximum |
| 戻り値 | Numeric / Signed 32-bit Integer / Value |
| `pUnitNum` | Numeric / Signed 32-bit Integer / Pointer to Value |
| `kind` | Numeric / Signed 32-bit Integer / Pointer to Value |

CLFN の表示プロトタイプが次になればよい。

```c
int32_t RAMScopeGT150DeviceInit(int32_t *pUnitNum, int32_t *kind);
```

### 10A.7.3 ブロックダイアグラム

```text
error in
  ───────────────────────────────┐
                                 ▼
I32 0 → pUnitNum ────────────── CLFN ──→ pUnitNum indicator
I32 0 → kind     ────────────────┤    └→ kind indicator
                                 ├─────→ ReturnCode indicator
error out ◀──────────────────────┘
```

- `pUnitNum` と `kind` の入力には I32 の `0` を接続する
- 右側端子から API が書き込んだ値を取得する
- 標準 `error in / error out` を必ず配線する
- API 戻り値を `RAMScope_Code_To_Error.vi` へ渡す

### 10A.7.4 戻り値と error out の扱い

次の状態は矛盾しない。

```text
CLFN error out : エラーなし
API ReturnCode : 異常コード
```

これは「LabVIEW から DLL 関数を呼び出すことには成功したが、RAMScope API 内部では処理結果が異常」
という意味である。

---

## 10A.8 実機未接続での PoC 結果

RAMScope 実機を接続していない状態で `RAMScopeGT150DeviceInit` を呼び出し、次を確認した。

```text
DeviceInit completed
Return code : 806354945
Return hex  : 0x30100001
Unit count  : 0
Device kind : 0
```

この結果から確定できること：

- DLL ロード成功
- エクスポート関数解決成功
- 引数の型とポインタ渡しでクラッシュしない
- 関数の実呼び出し成功
- 接続デバイス数は 0

`0x30100001` の正式な意味は、ベンダーのエラーコード表で確認する。
本章では「実機未接続時に観測したコード」として記録し、
コード値だけから意味を断定しない。

---

## 10A.9 実装の段階

### STEP 0：環境準備

- [ ] 64bit LabVIEW を使用
- [ ] 64bit RAMScope API DLL を使用
- [ ] ベンダー指定の相対配置を維持
- [ ] Visual C++ 2013 Redistributable（x64）が利用可能
- [ ] 64bit API フォルダ内に x86 版 `mfc120*` / `msvc*120` を混在させない

### STEP 1：DLL 疎通確認

- [ ] `Test-RAMScopeDll.ps1` を実行
- [ ] DLL Handle が非ゼロ
- [ ] 名前検索 `Found=True`
- [ ] 序数14検索 `Found=True`
- [ ] 名前と序数のアドレスが一致

### STEP 2：最小 `RAMScope_Connect.vi`

- [ ] CLFN を1個だけ配置
- [ ] `error in / error out` を配線
- [ ] `pUnitNum` / `kind` を I32 Pointer to Value に設定
- [ ] API 戻り値を I32 で取得
- [ ] 実機なしでもクラッシュせず戻ることを確認

### STEP 3：エラー変換を共通化

- [ ] `RAMScope_Code_To_Error.vi` を作成
- [ ] `Error_To_TestStatus.vi` へ接続
- [ ] `Status.ctl` / `TestError.ctl` / 標準 error cluster を出力

### STEP 4：後続 VI を1イベント1VIで作成

- [ ] `RAMScope_Init.vi`
- [ ] `RAMScope_Config.vi`
- [ ] `RAMScope_Set_Cond.vi`
- [ ] `RAMScope_Log_Start.vi`
- [ ] `RAMScope_Read.vi`
- [ ] `RAMScope_Parse_Buffer.vi`
- [ ] `RAMScope_Log_Stop.vi`
- [ ] `RAMScope_Release.vi`
- [ ] `RAMScope_Close.vi`

各関数のプロトタイプ、構造体、呼び出し順序は
[10_RAMScope実装方針.md](./10_RAMScope実装方針.md) を正とする。

### STEP 5：TestStand なしのフローテスト

```text
Connect
  → Init
  → Config
  → Set_Cond
  → Log_Start
  → Read
  → Log_Stop
  → Release（要否確認）
  → Close
```

### STEP 6：TestStand へ組み込み

- Setup / Main / Cleanup へ VI を配置
- API 戻り値を TestStand の判定へ反映
- Cleanup で `RAMScope_Close.vi` を必ず実行
- 待ち時間、リトライ、タイムアウトを TestStand 側で明示管理

---

## 10A.10 トラブルシュート表

| 症状 / コード | 主な確認事項 | 対応 |
|----------------|--------------|------|
| `193 (0xC1)` | x64/x86 不一致、ローカルに同名 x86 依存 DLL | PowerShell と LabVIEW のbit数確認。x86版 `mfc120*` / `msvc*120` を隔離 |
| `126` | DLL本体または依存 DLL 不足 | ベンダー指定相対配置、VC++ 2013 x64、GT170 DLL、サーバー EXE を確認 |
| `127` | 関数名不一致、または無効ハンドルで検索 | 先に DLL Handle が非ゼロか確認。エクスポート名を完全一致で指定 |
| Handle `0x0` | DLL ロード失敗 | 成功表示を信用せず Load error を確認 |
| CLFN `error out` は正常、ReturnCode は異常 | API 内部の処理結果エラー | ReturnCode を別経路で判定。実機接続・状態・設定を確認 |
| LabVIEW がクラッシュ | 引数型、ポインタ、配列サイズ、呼び出し規約不一致 | ヘッダ定義と CLFN 設定を再照合。UI thread と Maximum checking で PoC |
| UnitNum `0` | 接続デバイスなし、USBドライバ、電源、排他使用 | 実機電源・USB・デバイスマネージャー・純正アプリ終了を確認 |

---

## 10A.11 完了条件

### DLL・CLFN PoC 完了

- [x] `RAMScopeVP_API_x64.dll` を x64 プロセスでロード可能
- [x] `RAMScopeGT150DeviceInit` を名前で認識
- [x] 序数14でも認識
- [x] 名前と序数で同じ関数アドレスを取得
- [x] PowerShell から実呼び出し可能
- [x] LabVIEW CLFN のプロトタイプ設定を確定
- [x] `error in / error out` を含む最小 VI の配線を確定

### 残確認

- [ ] GT170 実機接続時の `ReturnCode` / `UnitNum` / `kind`
- [ ] 正常終了コードと全エラーコードの正式な意味
- [ ] `AllInit` 以降の実機フロー
- [ ] 長時間ポーリング時の安定性
- [ ] `ReleaseBufferData` の必須性
- [ ] TestStand Setup / Main / Cleanup の通し試験

---

## 10A.12 変更履歴

| 日付 | 内容 |
|------|------|
| 2026-07-14 | x86版 VC++ 2013 ランタイム混在による DLL ロードエラー193、関数未認識の切り分け結果を反映。PowerShell疎通スクリプトと CLFN 最小構成を追加 |
