# 03. LabVIEW 環境構築

> **本章の役割**：VIを作り始める前に、開発PCと試験用PCの実行環境を同じ前提へ揃える。
> RAMScope固有のDLL配置・疎通確認は [10A](./10A_RAMScope実装手順_DLL準備とCLFN疎通確認.md) を続けて実施する。

## 3.1 採用する基本構成

本システムは次の構成を基準とする。

| 項目 | 採用構成 |
|------|----------|
| LabVIEW | **64bit版** |
| TestStand | 使用するLabVIEW Adapterと互換のある版 |
| 一般計測器 | NI-VISA、計装ドライバ、またはSCPI |
| RAMScope | **RAMScopeVP API 64bit版をCLFNで直接呼び出す** |
| RAMScope API DLL | `RAMScopeVP_API_x64.dll` |
| RAMScope接続 | USB3.0 |
| RAMScope C/C++ランタイム | Visual C++ 2013 Redistributable **x64** |

32bit LabVIEW、32bit RAMScope API DLL、32bit PowerShellを本構成へ混在させない。

## 3.2 開発PCへインストールするソフトウェア

| ソフトウェア | 用途 | 必須条件 |
|--------------|------|----------|
| LabVIEW 64bit | VI開発・デバッグ | TestStandと互換のある版 |
| TestStand | シーケンス、条件、結果、Cleanup | LabVIEW Adapterを有効化 |
| NI-VISA | Ethernet、USB-TMC、GPIB等の汎用通信 | 使用するLabVIEWと互換のある版 |
| NI-XNET | NI製CAN IFを採用する場合 | CAN方式確定後に導入 |
| 各機器の計装ドライバ | オシロ、ロガー、電源等 | メーカー仕様に従う |
| RAMScopeVP / RAMScopeVP API | GT170ドライバ、API、PGT設定 | **64bit APIを含む構成** |
| Visual C++ 2013 Redistributable x64 | RAMScopeの`120`系依存DLLを提供 | RAMScope API利用時に必要 |
| Visual C++ 2015-2022 Redistributable x64 | 他コンポーネントが要求する場合 | VC++2013の代替にはならない |

### Visual C++ Redistributableの位置付け

Visual C++ RedistributableはRAMScopeのUSBドライバではない。RAMScopeのDLLが内部で使用するMicrosoft C/C++共通ライブラリを提供する。

```text
LabVIEW 64bit
  → RAMScopeVP_API_x64.dll
    → msvcr120 / msvcp120 / mfc120 系のx64ランタイム
```

`120`系はVisual C++ 2013世代であり、Visual C++ 2015-2022だけを導入しても代用できない。

## 3.3 ドライバとバージョンの確認方針

- LabVIEW、TestStand、Run-Time Engine、DLLのbit数を一致させる。
- 古いLabVIEW用として配布されたソースVIは、新しいLabVIEWで開ける場合があるが、**動作を保証せず実機確認する**。
- 開いたドライバVIはMass Compileまたは通常保存で再コンパイルし、壊れた依存VIがないか確認する。
- パスワード保護VI、外部DLL、ActiveX、.NET依存がある場合は、対応版とbit数を個別確認する。
- 計装ドライバが動作しない場合でも、SCPI対応機器はVISA Write / Readによる直接実装を代替候補とする。

## 3.4 機器接続の事前確認

### 3.4.1 Ethernet / VISA機器

1. 機器へ固定IPを設定する。
2. PCと同一サブネットへ接続する。
3. `ping`またはメーカー接続ツールで疎通を確認する。
4. NI MAXでVISAリソースを確認する。
5. 対応機器では`*IDN?`を送信し、識別文字列が返ることを確認する。
6. 確定したVISAリソース名を試験条件または設定ファイルへ記録する。

### 3.4.2 CANインタフェース

- NI-XNETの場合は、NI MAXでインタフェースを確認し、dbcをDatabase Editorへ登録する。
- USB-CANの場合は、メーカーのテストツールで送受信を確認する。
- CANalyzer COMを使用する場合は、CANalyzerの事前起動、測定状態、System Variableを確認する。
- 最終方式は [09](./09_CAN通信の実装.md) を正とする。

### 3.4.3 RAMScope

RAMScopeはNI MAXやVISAで確認しない。次の順で確認する。

```text
1. RAMScopeVPを正規インストーラで導入
2. WindowsデバイスマネージャーでUSBドライバを確認
3. 純正RAMScopeVPでGT170の接続確認
4. PGTツールでプローブ構成を設定
5. Test-RAMScopeDll.ps1でDLLと関数を確認
6. RAMScope_Connect.viでDeviceInitを確認
```

実装時のAPI DLLとヘッダの確認済みパス：

```text
API DLL:
C:\DTSinsight\RAMScopeVP\app\RAMScopeVP_API(64bit)\RAMScopeVP_API_x64.dll

ヘッダ:
C:\DTSinsight\RAMScopeVP_API\header\RAMScopeVP.h
```

DLL配置、x86ランタイム混在対策、エラー193の切り分けは [10A](./10A_RAMScope実装手順_DLL準備とCLFN疎通確認.md) に集約する。

## 3.5 LabVIEWプロジェクト構成

推奨する実フォルダ構成：

```text
AutoTestSystem\
├─ AutoTestSystem.lvproj
├─ 00_Common\
│    ├─ Status.ctl
│    ├─ TestError.ctl
│    ├─ Error_To_TestStatus.vi
│    └─ Log_Append.vi
├─ 10_Oscilloscope\
├─ 20_Logger\
├─ 30_RAMScope\
│    ├─ RAMScope_Code_To_Error.vi
│    ├─ RAMScope_Connect.vi
│    ├─ RAMScope_Init.vi
│    ├─ RAMScope_Config.vi
│    ├─ RAMScope_Set_Cond.vi
│    ├─ RAMScope_Log_Start.vi
│    ├─ RAMScope_Read.vi
│    ├─ RAMScope_Parse_Buffer.vi
│    ├─ RAMScope_Log_Stop.vi
│    ├─ RAMScope_Release.vi
│    └─ RAMScope_Close.vi
├─ 40_HV_Power\
├─ 50_LV_Power\
├─ 60_CAN\
└─ 90_TypeDefs\
```

### 作成手順

1. ディスク上にプロジェクトルートとサブフォルダを作成する。
2. `.lvproj`をプロジェクトルートへ保存する。
3. 各実フォルダを「自動更新フォルダ」としてプロジェクトへ追加する。
4. VIと型定義を対応する実フォルダへ保存する。
5. プロジェクトツリー上の仮想フォルダとディスク上の実フォルダを混同しない。

### 複数プロジェクトから共用する場合

RAMScope VI群の実体はメインプロジェクトの`30_RAMScope`へ1セットだけ置き、別プロジェクトから「VIを選択」で参照する。

- VIを案件ごとにコピーしない。
- 修正元を1か所に保つ。
- 別PCへ展開するときは参照先を含むフォルダ構成を維持する。
- `Status.ctl`等を案件ごとに独立管理するか共用するかは、型の一貫性と配布単位で決める。

## 3.6 開発PCでのビルド

1. プロジェクトの「ビルド仕様」からアプリケーションEXEを作成する。
2. スタートアップVIを指定する。
3. 静的に配線されたサブVIは通常自動的に含まれる。
4. 動的呼び出しVIはAlways Includedへ追加する。
5. ターゲットを64bitでビルドする。
6. 外部DLLはEXE内部へ自動埋め込みされないことを前提に、実行PCで解決できる配置または正規インストールを用意する。

### RAMScope DLLの扱い

RAMScopeはUSBドライバ、PGT設定、サーバーEXE、補助DLLを使用するため、試験用PCには**RAMScopeVPの正規インストーラを実行する方式を優先**する。

DLLだけをEXEフォルダへ無造作にコピーしない。特に以下を守る。

- `RAMScopeVP_API_x64.dll`と関連ファイルの相対配置を維持する。
- x86版`mfc120jpn.dll`、`mfc120u.dll`、`msvcp120.dll`、`msvcr120.dll`を64bit APIフォルダへ混在させない。
- `PGTMgrVP.dll`、`PGTMgrVP_ENG.dll`、`utillc.dll`、`pgtlib`配下は一律削除・隔離しない。
- CLFNの絶対パスを使用する場合は、開発PCと試験用PCで同じパスを用意する。
- 将来相対パス化する場合は、LabVIEW Application Directory等から確実に組み立てる。

## 3.7 試験用PCへ導入するもの

| 項目 | 内容 |
|------|------|
| LabVIEW Run-Time Engine 64bit | ビルドに使用したLabVIEWと互換のある版 |
| NI-VISA | VISA機器を使用する場合 |
| NI-XNET / メーカーCANドライバ | 採用したCAN方式に応じて導入 |
| 各機器のドライバ | 接続IFとメーカー仕様に従う |
| RAMScopeVP / API | 正規インストーラでUSBドライバ、API、PGTツールを導入 |
| Visual C++ 2013 Redistributable x64 | RAMScopeのx64ランタイム依存を満たす |
| ビルド成果物 | EXE単体ではなく生成フォルダ一式 |

## 3.8 環境構築の完了条件

### 共通

- [ ] LabVIEW、TestStand、Run-Time Engineの版とbit数が整合している
- [ ] プロジェクトの実フォルダとツリー構成が一致している
- [ ] Ethernet機器の疎通とVISAリソースを確認した
- [ ] 採用CANインタフェースの基本送受信を確認した

### RAMScope

- [ ] LabVIEWとPowerShellが64bitである
- [ ] `RAMScopeVP_API_x64.dll`を使用している
- [ ] Visual C++ 2013 Redistributable x64が利用可能である
- [ ] ベンダー指定の相対配置を維持している
- [ ] x86版`120`系ランタイムを64bit APIフォルダへ混在させていない
- [ ] `Test-RAMScopeDll.ps1`がPASSする
- [ ] `RAMScope_Connect.vi`がクラッシュせずReturnCodeを返す

ここまで完了した後、[10B](./10B_RAMScope_VI作成手順_STEP3_STEP4詳細.md)の各VI作成へ進む。