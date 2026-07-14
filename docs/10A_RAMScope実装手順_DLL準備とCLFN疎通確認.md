# 10A. RAMScope 実装手順：環境準備・DLL疎通・DeviceInitラッパPoC

> **本章の役割**：RAMScope VIを量産する前に、64bit DLLを正しくロードし、
> `RAMScopeGT150DeviceInit`をLabVIEWから呼べる状態まで確認する。
>
> 本章で作るVIは公開APIではなく、最初の薄いDLLラッパ`RS_DLL_GT150DeviceInit.vi`とする。
> 本章完了後は [10B](./10B_RAMScope_VI作成手順_STEP3_STEP4詳細.md) で、他のDLLラッパ、公開API、最小PoCを作成する。
> API関数・構造体の確認は [10](./10_RAMScope実装方針.md) を参照する。

**最終整理日：2026-07-14**

---

## 10A.1 適用構成

| 項目 | 使用するもの |
|------|--------------|
| RAMScope | GT170 |
| 接続 | USB3.0 |
| LabVIEW | 64bit版 |
| PowerShell | 64bitプロセス |
| API | RAMScopeVP API 64bit版 |
| API DLL | `RAMScopeVP_API_x64.dll` |
| CLFN | Call Library Function Node |
| C/C++ランタイム | Visual C++ 2013 Redistributable x64 |

この章では最小疎通関数として次を使用する。

```c
long RAMScopeGT150DeviceInit(long *pUnitNum, long *kind);
```

GT170でも接続・初期化・終了の共通処理には`RAMScopeGT150*`関数を使用する。

---

# STEP 0：必要ソフトとファイルを準備する

## 10A.2 必要ソフトウェア

- LabVIEW 64bit
- RAMScopeVP / RAMScopeVP API 64bit版
- RAMScope USBドライバ
- PGTツール
- Visual C++ 2013 Redistributable x64

Visual C++ 2015-2022 Redistributable x64は、別コンポーネントが要求する場合に導入する。
ただし、Visual C++ 2013の代替ではない。

## 10A.3 確認済みパス

```text
API DLL:
C:\DTSinsight\RAMScopeVP\app\RAMScopeVP_API(64bit)\RAMScopeVP_API_x64.dll

ヘッダ:
C:\DTSinsight\RAMScopeVP_API\header\RAMScopeVP.h
```

環境差がある場合は実際のインストール先へ読み替える。

## 10A.4 ベンダー指定の相対配置

`RAMScopeVP_API_x64.dll`を起点として、関連ファイルの相対位置を維持する。

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

### 配置ルール

- `UtilLCServer.exe`、`PGTMgrServer.exe`、`GT170_x64.dll`、`GT170USB_x64.dll`はAPI DLLと同じフォルダへ置く。
- `utillc.dll`は`UtilLCServer.exe`と同じフォルダへ置く。
- `PGTMgrVP.dll`、`PGTMgrVP_ENG.dll`は`PGTMgrServer.exe`と同じフォルダへ置く。
- PGTライブラリはAPI DLLフォルダ直下の`pgtlib`へ置く。
- 「64bitフォルダにあるx86ファイルをすべて削除する」という対応は禁止する。

---

## 10A.5 Visual C++ 2013 Redistributable x64の役割

Visual C++ RedistributableはRAMScopeのUSBドライバではない。
RAMScopeのDLLが内部で使用するMicrosoft C/C++共通ライブラリをWindowsへ提供する。

```text
LabVIEW 64bit
  → RAMScopeVP_API_x64.dll
    → Visual C++ 2013 x64ランタイム
```

今回問題になったファイル：

```text
mfc120jpn.dll
mfc120u.dll
msvcp120.dll
msvcr120.dll
```

`120`はVisual C++ 2013世代を表す。正しいx64版がWindowsから利用可能であることを確認する。

---

## 10A.6 既知事象：CLFNが関数を認識しない

### 現象

- CLFNでDLLを指定しても`RAMScopeGT150DeviceInit`を選択・認識できない。
- `GetProcAddress`で関数アドレスを取得できない。
- DLLロード時にエラー193が発生する。

```text
Error 193 (0xC1)
%1 は有効な Win32 アプリケーションではありません。
```

### 確認結果

```text
DLL          : RAMScopeVP_API_x64.dll
Architecture : x64
Function     : RAMScopeGT150DeviceInit
Ordinal      : 14
```

DLL本体と関数は存在していた。一方、API DLLと同じフォルダにx86版の次のランタイムが混在していた。

```text
mfc120jpn.dll
mfc120u.dll
msvcp120.dll
msvcr120.dll
```

x64プロセスがローカルのx86 DLLを依存DLLとして読み込もうとし、エラー193になった可能性が高い。

### 対策

1. Visual C++ 2013 Redistributable x64を利用可能にする。
2. 次の4ファイルがx86であり、64bit APIフォルダへ混在している場合だけ、復元可能なフォルダへ隔離する。

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

PowerShell例：

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

### 移動してはいけないファイル

```text
PGTMgrVP.dll
PGTMgrVP_ENG.dll
utillc.dll
pgtlib\*.dll
```

これらは32bitヘルパープロセスやPGT構成で使用される可能性がある。
x86と表示されたことだけを理由に隔離しない。

---

# STEP 1：PowerShellでDLLと関数を確認する

## 10A.7 疎通スクリプト

```powershell
powershell.exe -ExecutionPolicy Bypass `
  -File .\scripts\Test-RAMScopeDll.ps1 `
  -DllPath "C:\DTSinsight\RAMScopeVP\app\RAMScopeVP_API(64bit)\RAMScopeVP_API_x64.dll" `
  -ExportName "RAMScopeGT150DeviceInit" `
  -ExportOrdinal 14
```

### 合格条件

```text
PowerShell 64-bit : True
Loaded module path: 指定したRAMScopeVP_API_x64.dll
Handle            : 0x0以外
Name Found        : True
Ordinal Found     : True
Name Address      : Ordinal Address
```

### 重要な判定

- `Handle=0x0`は必ずロード失敗。
- 画面に「OK」と表示されてもハンドルが0なら成功扱いしない。
- 無効なハンドルで`GetProcAddress`を呼ぶとエラー127になり、関数が存在しないように見える。

### 実測結果

対策後、次を確認済み。

```text
PowerShell 64-bit : True
Handle            : 非ゼロ
Name Found        : True
Ordinal Found     : True
Address           : 名前と序数で一致
```

---

# STEP 2：最小`RS_DLL_GT150DeviceInit.vi`を作る

## 10A.8 ヘッダ定義

```c
typedef long (*RAMScopeGT150DeviceInitPtr)(long *pUnitNum, long *kind);
```

実質的な関数：

```c
long RAMScopeGT150DeviceInit(long *pUnitNum, long *kind);
```

Windowsの`long`は32bitである。64bit DLLでもI64にはしない。

## 10A.9 CLFN設定

| 項目 | 設定 |
|------|------|
| Library name or path | `RAMScopeVP_API_x64.dll`のフルパス |
| Function name | `RAMScopeGT150DeviceInit` |
| Calling Convention | C |
| Thread | Run in UI thread |
| Error checking | Maximum |
| 戻り値 | Numeric / Signed 32-bit Integer / Value |
| `pUnitNum` | Numeric / Signed 32-bit Integer / Pointer to Value |
| `kind` | Numeric / Signed 32-bit Integer / Pointer to Value |

表示プロトタイプ：

```c
int32_t RAMScopeGT150DeviceInit(
    int32_t *pUnitNum,
    int32_t *kind
);
```

## 10A.10 最小配線

```text
error in ─────────────────────────────────────┐
                                               ▼
I32 0 → pUnitNum ─────────────────────────── CLFN ─→ UnitNum
I32 0 → kind ──────────────────────────────────┤  └→ kind
                                               └────→ API ReturnCode
error out ◀────────────────────────────────────────
```

- `pUnitNum`と`kind`の入力側へI32の0を接続する。
- 右側端子からDLLが書き込んだ値を取得する。
- 標準`error in / error out`を配線する。
- この段階ではReturnCodeを表示し、関数呼び出しが成立することを優先する。

### VI名

最小疎通で作成したCLFNは、次の薄いDLLラッパとして保存する。

```text
RS_DLL_GT150DeviceInit.vi
```

公開APIの`RAMScope_Connect.vi`は [10B](./10B_RAMScope_VI作成手順_STEP3_STEP4詳細.md) で作成し、
このラッパを内部から呼び出す。

## 10A.11 実機未接続PoC

実機を接続していない状態で次を観測した。

```text
DeviceInit completed
Return code : 806354945
Return hex  : 0x30100001
Unit count  : 0
Device kind : 0
```

ここから確定できること：

- DLLロード成功
- 関数解決成功
- 引数の型とポインタ渡しでクラッシュしない
- 関数の実呼び出し成功
- 接続デバイス数は0

`0x30100001`の正式定義は未確認である。
実機未接続時の観測コードとして記録し、意味を断定しない。

---

## 10A.12 トラブルシュート

| 症状 | 確認 | 対応 |
|------|------|------|
| エラー193 | x64/x86不一致、ローカルx86依存DLL | PowerShell/LabVIEW/DLLのbit数確認。対象4ファイルだけ隔離 |
| エラー126 | DLL本体または依存DLL不足 | ベンダー相対配置、VC++2013 x64、GT170 DLLを確認 |
| エラー127 | 関数名不一致、または無効ハンドル | 先にHandle非ゼロを確認。関数名を完全一致 |
| Handle `0x0` | DLLロード失敗 | Load errorを確認。GetProcAddress結果を評価しない |
| CLFN errorなし、ReturnCode異常 | API内部結果エラー | ReturnCodeを別経路で評価する |
| LabVIEWクラッシュ | 引数型、配列サイズ、ポインタ、関数設定 | ヘッダとCLFNを再照合。UI thread / Maximumで再試験 |
| UnitNum `0` | 機器未接続、電源、USBドライバ、排他使用 | 実機・デバイスマネージャー・純正アプリ終了を確認 |

---

## 10A.13 本章の完了条件

- [x] x64 PowerShellでDLLをロードできる
- [x] DLL Handleが非ゼロ
- [x] `RAMScopeGT150DeviceInit`を名前で取得できる
- [x] 序数14でも取得できる
- [x] 名前と序数のアドレスが一致する
- [x] PowerShellから関数を実呼び出しできる
- [x] LabVIEWのCLFNプロトタイプが確定している
- [x] DeviceInitの最小配線ができている
- [x] 実機未接続時でもクラッシュせずReturnCodeを返す
- [ ] 作成済みVIを`RS_DLL_GT150DeviceInit.vi`として整理する

次に [10B](./10B_RAMScope_VI作成手順_STEP3_STEP4詳細.md) で、
`RAMScope_Code_To_Error.vi`、残りのDLLラッパ、公開API、`PoC_RAMScope_Main.vi`を作成する。
