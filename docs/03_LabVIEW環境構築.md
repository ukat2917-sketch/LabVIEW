# 03. LabVIEW 環境構築

> **本章の役割**：VIを作り始める前に、開発PCと試験用PCの実行環境を同じ前提へ揃える。
> RAMScope固有のDLL配置、エラー193、CLFN疎通、VIフォルダ詳細は[10](./10_RAMScope実装方針.md)を参照する。

## 3.1 採用する基本構成

| 項目 | 採用構成 |
|---|---|
| LabVIEW | 64bit版 |
| TestStand | 使用するLabVIEW Adapterと互換のある版 |
| 一般計測器 | NI-VISA、計装ドライバ、またはSCPI |
| RAMScope | RAMScopeVP API 64bit版をCLFNで直接呼び出す |
| RAMScope API DLL | `RAMScopeVP_API_x64.dll` |
| RAMScope接続 | USB3.0 |
| RAMScope C/C++ランタイム | Visual C++ 2013 Redistributable x64 |

32bit LabVIEW、32bit RAMScope API DLL、32bit PowerShellを本構成へ混在させない。

## 3.2 開発PCへインストールするソフトウェア

| ソフトウェア | 用途 | 必須条件 |
|---|---|---|
| LabVIEW 64bit | VI開発・デバッグ | TestStandと互換のある版 |
| TestStand | シーケンス、条件、結果、Cleanup | LabVIEW Adapterを有効化 |
| NI-VISA | Ethernet、USB-TMC、GPIB等 | 使用LabVIEWと互換のある版 |
| NI-XNET | NI製CAN IFを採用する場合 | CAN方式確定後に導入 |
| 各機器の計装ドライバ | オシロ、ロガー、電源等 | メーカー仕様に従う |
| RAMScopeVP / RAMScopeVP API | GT170ドライバ、API、PGT設定 | 64bit APIを含む構成 |
| Visual C++ 2013 Redistributable x64 | RAMScopeの`120`系依存DLLを提供 | RAMScope API利用時に必要 |
| Visual C++ 2015-2022 Redistributable x64 | 他コンポーネントが要求する場合 | VC++2013の代替ではない |

Visual C++ RedistributableはRAMScopeのUSBドライバではなく、RAMScope DLLが使用するMicrosoft C/C++共通ライブラリをWindowsへ提供する。

```text
LabVIEW 64bit
  → RAMScopeVP_API_x64.dll
    → msvcr120 / msvcp120 / mfc120系のx64ランタイム
```

## 3.3 ドライバとバージョン

- LabVIEW、TestStand、Run-Time Engine、DLLのbit数を一致させる。
- 古いLabVIEW用ソースVIは、新しいLabVIEWで開けても実機確認する。
- 開いたドライバVIは再保存またはMass Compileし、壊れた依存VIを確認する。
- パスワード保護VI、外部DLL、ActiveX、.NET依存は対応版とbit数を個別確認する。
- SCPI対応機器は計装ドライバが使えない場合にVISA Write / Readを代替候補とする。

## 3.4 機器接続の事前確認

### Ethernet / VISA機器

1. 固定IPを設定する。
2. PCと同一サブネットへ接続する。
3. `ping`またはメーカー接続ツールで疎通する。
4. NI MAXでVISAリソースを確認する。
5. 対応機器では`*IDN?`を実行する。
6. 確定したVISAリソース名を条件ファイルへ記録する。

### CANインタフェース

- NI-XNETはNI MAXでインタフェースを確認し、DBCをDatabase Editorへ登録する。
- USB-CANはメーカーのテストツールで送受信を確認する。
- CANalyzer COMはCANalyzerの起動状態、Measurement、System Variableを確認する。
- 最終方式は[09](./09_CAN通信の実装.md)で決定する。

### RAMScope

RAMScopeはNI MAXやVISAで確認しない。

```text
1. RAMScopeVPを正規インストーラで導入
2. WindowsデバイスマネージャーでUSBドライバを確認
3. 純正RAMScopeVPでGT170の接続確認
4. PGTツールでプローブ構成を設定
5. Test-RAMScopeDll.ps1でDLLと関数を確認
6. RS_DLL_GT150DeviceInit.vi / RAMScope_Connect.viで確認
```

確認済みパス：

```text
C:\DTSinsight\RAMScopeVP\app\RAMScopeVP_API(64bit)\RAMScopeVP_API_x64.dll
C:\DTSinsight\RAMScopeVP_API\header\RAMScopeVP.h
```

x86ランタイム混在対策は[10](./10_RAMScope実装方針.md)を正とする。

## 3.5 LabVIEWプロジェクト構成

```text
AutoTestSystem\
├─ AutoTestSystem.lvproj
├─ 00_Common\
│  ├─ Status.ctl
│  ├─ TestError.ctl
│  ├─ Error_To_TestStatus.vi
│  └─ Log_Append.vi
├─ 10_Oscilloscope\
├─ 20_Logger\
├─ 30_RAMScope\
│  ├─ 00_Common\
│  │  ├─ RAMScope_Code_To_Error.vi
│  │  ├─ RAMScope_Channel.ctl
│  │  ├─ RAMScope_Meas_Config.ctl
│  │  ├─ RAMScope_Module_Log_Config.ctl
│  │  ├─ RAMScope_Module_Info.ctl
│  │  ├─ RAMScope_Channel_Value.ctl
│  │  ├─ RAMScope_Packet.ctl
│  │  ├─ RAMScope_Byte_Order.ctl
│  │  └─ 数値⇔U8変換VI
│  ├─ 10_DLL_Wrapper\
│  │  └─ RS_DLL_* 薄いDLLラッパ12個
│  ├─ 20_Data_Conversion\
│  │  ├─ Build_MEASINFO_170_Raw.vi
│  │  ├─ Build_CHINFO_170_Raw.vi
│  │  ├─ Build_LOGINFO_Raw.vi
│  │  ├─ Parse_SYSINFO_Array.vi
│  │  └─ RAMScope_Parse_Buffer.vi
│  ├─ 30_Public\
│  │  ├─ RAMScope_Connect.vi
│  │  ├─ RAMScope_Init.vi
│  │  ├─ RAMScope_Set_Cond.vi
│  │  ├─ RAMScope_Log_Start.vi
│  │  ├─ RAMScope_Read.vi
│  │  ├─ RAMScope_Release.vi
│  │  ├─ RAMScope_Log_Stop.vi
│  │  └─ RAMScope_Close.vi
│  └─ 40_PoC\
│     └─ PoC_RAMScope_Main.vi
├─ 40_HV_Power\
├─ 50_LV_Power\
├─ 60_CAN\
└─ 90_TypeDefs\
```

`RAMScope_Config.vi`、公開用`RAMScope_Parse_Buffer.vi`、`RAMScope_Context.ctl`は作成しない。

### 作成手順

1. ディスク上にプロジェクトルートとサブフォルダを作る。
2. `.lvproj`をルートへ保存する。
3. 各実フォルダを自動更新フォルダとして追加する。
4. VIとtypedefを対応フォルダへ保存する。
5. 仮想フォルダと実フォルダを混同しない。
6. 旧`20_Parser`を作成済みの場合は`20_Data_Conversion`へ名称変更する。

### 複数プロジェクトから共用する場合

- RAMScope VI実体はメインプロジェクトの`30_RAMScope`へ1セットだけ置く。
- 案件ごとにコピーしない。
- 別PCへ展開するときは参照先を含むフォルダ構成を維持する。

## 3.6 開発PCでのビルド

1. ビルド仕様からアプリケーションEXEを作成する。
2. スタートアップVIを指定する。
3. 動的呼び出しVIはAlways Includedへ追加する。
4. 64bitでビルドする。
5. 外部DLLはEXEへ自動埋め込みされない前提で配置を設計する。

### RAMScope DLL

試験用PCにもRAMScopeVPの正規インストーラを使用する。

- API DLLを起点とした相対配置を維持する。
- x86版`mfc120jpn.dll`、`mfc120u.dll`、`msvcp120.dll`、`msvcr120.dll`を64bit APIフォルダへ混在させない。
- `PGTMgrVP.dll`、`PGTMgrVP_ENG.dll`、`utillc.dll`、`pgtlib`を一律削除しない。
- CLFN絶対パスを使う場合は開発PCと試験PCで同じパスを用意する。

## 3.7 試験用PCへ導入するもの

| 項目 | 内容 |
|---|---|
| LabVIEW Run-Time Engine 64bit | ビルドに使用したLabVIEWと互換のある版 |
| NI-VISA | VISA機器を使用する場合 |
| NI-XNET / メーカーCANドライバ | 採用CAN方式に応じる |
| 各機器のドライバ | 接続IFとメーカー仕様に従う |
| RAMScopeVP / API | 正規インストーラでUSBドライバ、API、PGTツールを導入 |
| Visual C++ 2013 Redistributable x64 | RAMScopeのx64依存を満たす |
| ビルド成果物 | EXE単体ではなく生成フォルダ一式 |

## 3.8 完了条件

### 共通

- [ ] LabVIEW、TestStand、Run-Time Engineの版とbit数が整合
- [ ] プロジェクトの実フォルダとツリーが一致
- [ ] Ethernet機器の疎通とVISAリソースを確認
- [ ] 採用CANインタフェースの基本送受信を確認

### RAMScope

- [ ] LabVIEWとPowerShellが64bit
- [ ] `RAMScopeVP_API_x64.dll`を使用
- [ ] Visual C++ 2013 Redistributable x64が利用可能
- [ ] ベンダー相対配置を維持
- [ ] x86版`120`系ランタイムを64bit APIフォルダへ混在させていない
- [ ] `Test-RAMScopeDll.ps1`のHandleが非ゼロ
- [ ] DeviceInit関数を名前で解決可能
