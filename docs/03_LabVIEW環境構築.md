# 03. LabVIEW 環境構築

> **本章の役割**：VIを作り始める前に、開発PCと試験用PCの実行環境を同じ前提へ揃える。
>
> 操作手順は[00A](./00A_LabVIEW実装資料の記述ルール.md)に従い、対象、操作場所、入力値、確認結果を明記する。RAMScope固有のDLL配置、エラー193、CLFN疎通、VIフォルダ詳細は[10](./10_RAMScope実装方針.md)を正とする。

## 3.1 採用する基本構成

### 採用理由

自動試験で使用するLabVIEW、TestStand、Run-Time Engine、外部DLLは、同一プロセス内で読み込まれるコンポーネントのbit数を一致させる必要がある。RAMScopeVP APIの64bit版を使用するため、本システム全体を64bitへ統一する。

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

| ソフトウェア | 用途 | 必須条件 | 確認方法 |
|---|---|---|---|
| LabVIEW 64bit | VI開発・デバッグ | TestStandと互換のある版 | LabVIEWのAbout画面で版とbit数を確認 |
| TestStand | シーケンス、条件、結果、Cleanup | LabVIEW Adapterを有効化 | Configure → Adaptersで確認 |
| NI-VISA | Ethernet、USB-TMC、GPIB等 | 使用LabVIEWと互換のある版 | NI MAXで機器を確認 |
| NI-XNET | NI製CAN IFを採用する場合 | CAN方式確定後に導入 | NI MAXでインタフェースを確認 |
| 各機器の計装ドライバ | オシロ、ロガー、電源等 | メーカー仕様に従う | サンプルVIまたはVI Treeで確認 |
| RAMScopeVP / RAMScopeVP API | GT170ドライバ、API、PGT設定 | 64bit APIを含む構成 | 純正アプリとAPIフォルダを確認 |
| Visual C++ 2013 Redistributable x64 | RAMScopeの`120`系依存DLLを提供 | RAMScope API利用時に必要 | インストール済みアプリとDLL疎通で確認 |
| Visual C++ 2015-2022 Redistributable x64 | 他コンポーネントが要求する場合 | VC++2013の代替ではない | 対象コンポーネント仕様で確認 |

Visual C++ RedistributableはRAMScopeのUSBドライバではなく、RAMScope DLLが使用するMicrosoft C/C++共通ライブラリをWindowsへ提供する。

```text
LabVIEW 64bit
  → RAMScopeVP_API_x64.dll
    → msvcr120 / msvcp120 / mfc120系のx64ランタイム
```

## 3.3 ドライバとバージョン

1. LabVIEW、TestStand、Run-Time Engine、DLLの版とbit数を一覧化する。
2. 古いLabVIEW用ソースVIを開いた場合は、壊れた実行矢印と依存VIを確認する。
3. 必要に応じて再保存またはMass Compileを実行する。
4. パスワード保護VI、外部DLL、ActiveX、.NET依存は、対応版とbit数を個別に確認する。
5. SCPI対応機器で計装ドライバが使用できない場合だけ、VISA Write / VISA Readを代替候補とする。

完了時に次を記録する。

```text
LabVIEW版 / bit数
TestStand版 / Adapter設定
Run-Time Engine版 / bit数
外部DLL版 / bit数
ドライバ入手元と確認日
```

## 3.4 機器接続の事前確認

### 3.4.1 Ethernet / VISA機器

1. 機器の前面パネルまたはメーカー設定ツールで固定IPを設定する。
2. PCと同一サブネットへ接続する。
3. Windowsのコマンドプロンプトで`ping <IPアドレス>`を実行する。
4. NI MAXで対象機器またはVISAリソースを確認する。
5. 対応機器ではVISA Test Panelから`*IDN?`を送信する。
6. 応答文字列、VISAリソース名、確認日を条件ファイルまたは環境記録へ保存する。

### 3.4.2 CANインタフェース

| 方式 | 事前確認 |
|---|---|
| NI-XNET | NI MAXでインタフェースを確認し、DBCをDatabase Editorへ登録 |
| メーカーUSB-CAN | メーカーのテストツールで代表Tx/Rxを確認 |
| CANalyzer COM | CANalyzerの起動、cfg、Measurement、System Variableを確認 |
| RAMScope CAN | RAM計測PoC後に第9章と第10章へ従って確認 |

最終方式は[09](./09_CAN通信の実装.md)で決定する。

### 3.4.3 RAMScope

RAMScopeはNI MAXやVISAで確認しない。次の順で、どの段階まで成功したかを記録する。

```text
1. RAMScopeVPを正規インストーラで導入
2. WindowsデバイスマネージャーでUSBドライバを確認
3. 純正RAMScopeVPでGT170の接続確認
4. PGTツールでプローブ構成を設定
5. Test-RAMScopeDll.ps1でDLLロードと関数解決を確認
6. RS_DLL_GT150DeviceInit.viでDLL関数の実呼び出しを確認
7. RAMScope_Connect.viで公開API層を確認
```

確認済みパス：

```text
C:\DTSinsight\RAMScopeVP\app\RAMScopeVP_API(64bit)\RAMScopeVP_API_x64.dll
C:\DTSinsight\RAMScopeVP_API\header\RAMScopeVP.h
```

x86ランタイム混在対策、PowerShellの合格条件、DeviceInitの観測結果は[10](./10_RAMScope実装方針.md)を正とする。

## 3.5 LabVIEWプロジェクト構成

### なぜ実フォルダを分けるのか

DLL呼び出し、データ変換、公開API、PoCを同じフォルダへ置くと、TestStandから呼ぶVIと内部VIを区別しにくい。責務ごとに実フォルダを分け、プロジェクトエクスプローラとディスク上の構造を一致させる。

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

1. Windowsエクスプローラでプロジェクトルートを作成する。
2. 上記の実フォルダをディスク上へ作成する。
3. LabVIEWで新規プロジェクトを作成し、`.lvproj`をルートへ保存する。
4. プロジェクトエクスプローラの`マイコンピュータ`を右クリックし、対象の実フォルダを自動更新フォルダとして追加する。
5. VIとtypedefを対応する実フォルダへ保存する。
6. プロジェクトエクスプローラ上の表示とWindowsエクスプローラ上の実体が一致することを確認する。
7. 旧`20_Parser`を作成済みの場合は、Windows上の実フォルダ名とプロジェクト参照を`20_Data_Conversion`へ変更する。

### 複数プロジェクトから共用する場合

- RAMScope VI実体はメインプロジェクトの`30_RAMScope`へ1セットだけ置く。
- 案件ごとにコピーしない。
- 別プロジェクトでは既存VIを参照し、同名コピーを作らない。
- 別PCへ展開するときは参照先を含むフォルダ構成を維持する。

## 3.6 開発PCでのビルド

1. プロジェクトエクスプローラのビルド仕様を右クリックし、新規アプリケーションEXEを作成する。
2. スタートアップVIを指定する。
3. 動的呼び出しVIを使用する場合はAlways Includedへ追加する。
4. ターゲットが64bitであることを確認してビルドする。
5. 生成フォルダ内のEXE、support files、設定ファイルを一覧化する。
6. 外部DLLはEXEへ自動埋め込みされない前提で、試験PC上の配置を確認する。

### RAMScope DLL

試験用PCにもRAMScopeVPの正規インストーラを使用する。

- API DLLを起点とした相対配置を維持する。
- x86版`mfc120jpn.dll`、`mfc120u.dll`、`msvcp120.dll`、`msvcr120.dll`を64bit APIフォルダへ混在させない。
- `PGTMgrVP.dll`、`PGTMgrVP_ENG.dll`、`utillc.dll`、`pgtlib`を一律削除しない。
- CLFN絶対パスを使う場合は開発PCと試験PCで同じパスを用意する。

## 3.7 試験用PCへ導入するもの

| 項目 | 内容 | 確認結果として残すもの |
|---|---|---|
| LabVIEW Run-Time Engine 64bit | ビルドに使用したLabVIEWと互換のある版 | 版、bit数 |
| NI-VISA | VISA機器を使用する場合 | NI MAXの認識結果 |
| NI-XNET / メーカーCANドライバ | 採用CAN方式に応じる | 代表Tx/Rx結果 |
| 各機器のドライバ | 接続IFとメーカー仕様に従う | 機種識別結果 |
| RAMScopeVP / API | 正規インストーラでUSBドライバ、API、PGTツールを導入 | 純正アプリとDLL疎通結果 |
| Visual C++ 2013 Redistributable x64 | RAMScopeのx64依存を満たす | DLLロード結果 |
| ビルド成果物 | EXE単体ではなく生成フォルダ一式 | 配置先とファイル一覧 |

## 3.8 完了条件

### 共通

- [ ] LabVIEW、TestStand、Run-Time Engineの版とbit数が整合
- [ ] プロジェクトの実フォルダとツリーが一致
- [ ] Ethernet機器の疎通とVISAリソースを確認
- [ ] 採用CANインタフェースの基本送受信を確認
- [ ] 開発PCと試験PCの差分を記録

### RAMScope

- [ ] LabVIEWとPowerShellが64bit
- [ ] `RAMScopeVP_API_x64.dll`を使用
- [ ] Visual C++ 2013 Redistributable x64が利用可能
- [ ] ベンダー相対配置を維持
- [ ] x86版`120`系ランタイムを64bit APIフォルダへ混在させていない
- [ ] `Test-RAMScopeDll.ps1`のHandleが非ゼロ
- [ ] DeviceInit関数を名前で解決可能
- [ ] 開発PCと試験PCで同じ疎通結果を再現
