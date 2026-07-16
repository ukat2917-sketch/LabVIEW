# 10. RAMScope GT170 実装ガイド

> **本章をRAMScope実装の唯一の正本とする。**
>
> DLL準備、CLFN、共通エラー変換、薄いDLLラッパ、typedef、数値変換、構造体生成、Parser、公開API、最小PoCまでを上から順に実施する。
>
> 関数プロトタイプの一次情報は`docs/reference/RAMScopeVP.h`、ハードウェア定数は`docs/reference/GTHard.h`、呼び出し例は`docs/reference/samp_simple.cpp`を優先する。
>
> LabVIEWの関数名は、NI公式の日本語版LabVIEWプログラミングリファレンスを基準に、**日本語名（英語名）**の順で併記する。LabVIEWのバージョンによってパレット階層や末尾の「関数」表記が異なる場合は、`Ctrl + Space`でクイックドロップ（Quick Drop）を開き、表中の英語名で検索する。

**最終整理日：2026-07-16**

---

# 10.1 この章の使い方

## 10.1.1 実装の一本道

```text
STEP 0  環境準備とDLL疎通
  ↓
STEP 1  RAMScope_Code_To_Error.vi
  ↓
STEP 2  1関数1VIの薄いDLLラッパ12個
  ↓
STEP 3  typedefと数値⇔U8変換VI
  ↓
STEP 4  MEASINFO / CHINFO / LOGINFO Builder
  ↓
STEP 5  SYSINFO / 測定バッファ Parser
  ↓
STEP 6  1イベント1VIの公開API
  ↓
STEP 7  PoC_RAMScope_Main.viでRAM計測単体確認
  ↓
STEP 8  CAN方式確定・CAN単体PoC
  ↓
STEP 9  TestStand組み込み
```

RAMScopeは最初からTestStandへ組み込まない。各レイヤを単体確認してから次へ進む。

## 10.1.2 VI作成手順の統一書式

本章で新規作成するVIは、原則として次の順番で説明する。

```text
1. 入出力
2. 配置する関数およびSubVI等
3. 配線順
4. 単体テスト
```

「配置する」「接続する」だけで終わらせず、次を明記する。

- 関数の日本語名と英語名
- 関数パレット上の配置場所
- ケースストラクチャの条件
- Forループの自動指標付け
- シフトレジスタの追加方法、初期値、左右端子の役割
- 全入力と全出力の接続先
- 異常ケースの安全な初期出力

## 10.1.3 状態表記

| 表記 | 意味 |
|---|---|
| **確定** | ヘッダ、外部仕様書、または再現可能な実測で確認済み |
| **PoC済み** | 最小条件で動作確認済み |
| **実機確認待ち** | VI構成は作成できるが、GT170接続時の確認が未完了 |
| **未確定** | 推測で実装へ固定しない |

---

# 10.2 採用構成とフォルダ構成

## 10.2.1 なぜこの構成を採用するのか

RAMScopeVP APIはLabVIEW用VIではなく、C言語用DLL APIである。LabVIEWから使用するには、C関数、構造体、ポインタ、生バイト列、API独自ReturnCodeを、LabVIEWの数値、配列、クラスタ、標準error clusterへ変換する必要がある。

すべてを1個の巨大なVIへ入れると、DLL呼び出し、構造体変換、データ解析、試験フローのどこで失敗したかを切り分けにくい。そこで、責務ごとにレイヤを分ける。

| RAMScope実装で発生する問題 | 必要な仕組み | 配置先・主なVI |
|---|---|---|
| C関数をLabVIEWから呼ぶ | CLFN設定を1関数単位で隔離 | `10_DLL_Wrapper\RS_DLL_*` |
| CLFNエラーとAPI ReturnCodeが別経路 | 2系統を標準error clusterへ統合 | `RAMScope_Code_To_Error.vi` |
| API入力がC構造体ポインタ | LabVIEW設定値をC互換U8配列へ組み立てる | `Build_*_Raw.vi` |
| API出力が構造体や生バッファ | U8配列をLabVIEWクラスタや数値へ解析 | `Parse_*` |
| Endianと符号を扱う | 数値とU8配列の変換を共通部品化 | `U8x4_To_U32.vi`等 |
| TestStandからCLFN単位では扱いにくい | 接続、初期化、読出し等へまとめる | `30_Public\RAMScope_*` |
| TestStand組み込み前に下位層を検証したい | LabVIEW単体PoCを用意 | `PoC_RAMScope_Main.vi` |

```text
TestStand
  ↓
30_Public                 試験イベント単位へまとめる
  ↓
20_Data_Conversion        C構造体とLabVIEWデータ型の差を吸収する
00_Common
  ↓
10_DLL_Wrapper            DLL関数を1個だけ呼ぶ
  ↓
RAMScopeVP_API_x64.dll
```

## 10.2.2 採用構成

| 項目 | 採用内容 |
|---|---|
| 対象機器 | RAMScope GT170 |
| 接続 | USB3.0 |
| LabVIEW | 64bit版 |
| API | RAMScopeVP API 64bit版 |
| API DLL | `RAMScopeVP_API_x64.dll` |
| 呼び出し | ライブラリ関数呼び出しノード（Call Library Function Node） |
| Calling Convention | `C` |
| DLL状態管理 | API内部のグローバル状態。セッションハンドルは返らない |
| C/C++ランタイム | Visual C++ 2013 Redistributable x64 |

## 10.2.3 正式なフォルダ構成

```text
30_RAMScope\
├─ 00_Common\
│  ├─ RAMScope_Code_To_Error.vi
│  ├─ RAMScope_Channel.ctl
│  ├─ RAMScope_Meas_Config.ctl
│  ├─ RAMScope_Module_Log_Config.ctl
│  ├─ RAMScope_Module_Info.ctl
│  ├─ RAMScope_Channel_Value.ctl
│  ├─ RAMScope_Packet.ctl
│  ├─ RAMScope_Byte_Order.ctl
│  ├─ I32_To_LE_U8x4.vi
│  ├─ U32_To_LE_U8x4.vi
│  ├─ U8x4_To_I32.vi
│  ├─ U8x4_To_U32.vi
│  └─ U8x8_To_U64.vi
│
├─ 10_DLL_Wrapper\
│  ├─ RS_DLL_GT150DeviceInit.vi
│  ├─ RS_DLL_GT150DeviceExit.vi
│  ├─ RS_DLL_GT150AllInit.vi
│  ├─ RS_DLL_GT150GetSysInfo.vi
│  ├─ RS_DLL_GT150PGT_SetMdlConfig.vi
│  ├─ RS_DLL_GT170SetMeasCond.vi
│  ├─ RS_DLL_GT170SetMeasCh.vi
│  ├─ RS_DLL_GT150SetLoggingInfo.vi
│  ├─ RS_DLL_GT150MeasStart.vi
│  ├─ RS_DLL_GT150GetBufferData.vi
│  ├─ RS_DLL_GT150ReleaseBufferData.vi
│  └─ RS_DLL_GT150MeasStop.vi
│
├─ 20_Data_Conversion\
│  ├─ Build_MEASINFO_170_Raw.vi
│  ├─ Build_CHINFO_170_Raw.vi
│  ├─ Build_LOGINFO_Raw.vi
│  ├─ Parse_SYSINFO_Array.vi
│  └─ RAMScope_Parse_Buffer.vi
│
├─ 30_Public\
│  ├─ RAMScope_Connect.vi
│  ├─ RAMScope_Init.vi
│  ├─ RAMScope_Set_Cond.vi
│  ├─ RAMScope_Log_Start.vi
│  ├─ RAMScope_Read.vi
│  ├─ RAMScope_Release.vi
│  ├─ RAMScope_Log_Stop.vi
│  └─ RAMScope_Close.vi
│
├─ 40_PoC\
│  └─ PoC_RAMScope_Main.vi
│
├─ 50_CAN\
└─ 90_TestStand\
```

`RAMScope_Context.ctl`はPoC完了まで作成しない。`UnitNo`、`MdlNo_RAM`、`MdlNo_CAN`、`Endian_RAM`、`Channel List`を個別配線する。

## 10.2.4 レイヤ責務

| レイヤ | 責務 | 含めないもの |
|---|---|---|
| `00_Common` | typedef、バイト変換、APIコード変換 | DLL呼び出し、機器状態遷移 |
| `10_DLL_Wrapper` | 1個のCLFNで1関数だけ呼ぶ | Builder、Parser、複数API制御、Status生成 |
| `20_Data_Conversion` | C構造体互換U8配列生成、生バイト列解析 | DLL呼び出し、測定開始・停止 |
| `30_Public` | ラッパと変換VIを接続し1イベントを完結 | TestStand固有変数への直接依存 |
| `40_PoC` | 公開APIを順に呼び実機単体確認 | 本番試験シナリオ |
| TestStand | 条件、順序、Wait、Loop、分岐、レポート、Cleanup | `RS_DLL_*`の直接呼び出し |

---

# 10.3 環境準備・DLL疎通

## 10.3.1 必要ソフトウェア

- LabVIEW 64bit
- RAMScopeVP / RAMScopeVP API 64bit版
- RAMScope USBドライバ
- PGTツール
- Visual C++ 2013 Redistributable x64

Visual C++ 2015-2022 Redistributable x64は、別コンポーネントが要求する場合だけ追加する。Visual C++ 2013の代替ではない。

確認済みパス：

```text
C:\DTSinsight\RAMScopeVP\app\RAMScopeVP_API(64bit)\RAMScopeVP_API_x64.dll
C:\DTSinsight\RAMScopeVP_API\header\RAMScopeVP.h
```

## 10.3.2 DLL相対配置

API DLLを起点としたベンダー指定の相対位置を維持する。

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
```

## 10.3.3 エラー193対策

64bit APIフォルダへx86版VC++2013ランタイムが混在すると、エラー193になる可能性がある。

```text
mfc120jpn.dll
mfc120u.dll
msvcp120.dll
msvcr120.dll
```

上記ファイルが実際にx86であることを確認できた場合のみ、復元可能なバックアップへ移動する。`PGTMgrVP.dll`、`PGTMgrVP_ENG.dll`、`utillc.dll`、`pgtlib`は移動しない。

## 10.3.4 PowerShell疎通合格条件

```text
PowerShell 64-bit : True
Handle            : 0x0以外
Name Found        : True
Ordinal Found     : True
Name Address      : Ordinal Address
```

実機未接続時に観測した`0x30100001`は正式定義未確認であり、「未接続エラー」と断定しない。

---

# 10.4 APIライフサイクルと型

## 10.4.1 呼び出し順

```text
DeviceInit
  → AllInit
  → GetSysInfo
  → Parse_SYSINFO
  → PGT_SetMdlConfig
  → SetMeasCond
  → SetMeasCh
  → SetLoggingInfo
  → MeasStart
  → GetBufferData
  → MeasStop
  → ReleaseBufferData（要否検証中）
  → DeviceExit
```

## 10.4.2 C型とLabVIEW型

| C型 | LabVIEW |
|---|---|
| `long` | I32 |
| `long *` | I32 / Pointer to Value |
| `unsigned long` / `DWORD` | U32 |
| 構造体ポインタ | U8一次元配列 / Array Data Pointer |
| `long[]` | I32一次元配列 / Array Data Pointer |

Windowsの`long`は64bit DLLでも32bit。I64へ変更しない。

## 10.4.3 使用構造体サイズ

| 構造体 | サイズ |
|---|---:|
| `SYSINFO` | 60byte × 16 = 960byte |
| `MEASINFO_170` | 72byte |
| RAM用`CHINFO_170` | 24byte × ChNum |
| `LOGINFO` | 136byte |

RAM測定パケットの現行作業定義：

```text
Channel Data = 4byte × ChNum
Flag         = 4byte
Timestamp    = 8byte
Packet Size  = 4 × ChNum + 12
```

---

# 10.5 LabVIEW共通作業ルール

## 10.5.1 関数名とパレット位置

| 日本語名 | 英語名 | 関数パレットの目安 |
|---|---|---|
| ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| Forループ | For Loop | プログラミング → ストラクチャ |
| シフトレジスタ | Shift Register | Forループ枠を右クリック → シフトレジスタを追加 |
| 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 名前でバンドル | Bundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 配列サイズ | Array Size | プログラミング → 配列 |
| 指標配列 | Index Array | プログラミング → 配列 |
| 部分配列 | Array Subset | プログラミング → 配列 |
| 配列初期化 | Initialize Array | プログラミング → 配列 |
| 部分配列置換 | Replace Array Subset | プログラミング → 配列 |
| 配列連結追加 | Build Array | プログラミング → 配列 |
| 1D配列検索 | Search 1D Array | プログラミング → 配列 |
| 数値結合 | Join Numbers | プログラミング → 数値 → データ操作 |
| 数値分割 | Split Number | プログラミング → 数値 → データ操作 |
| 型変換 | Type Cast | プログラミング → 数値 → データ操作 |
| 文字列にフォーマット | Format Into String | プログラミング → 文字列 |
| バイト配列から文字列 | Byte Array To String | プログラミング → 文字列 → 文字列/配列/パス変換 |
| 等しい? | Equal? | プログラミング → 比較 |
| 等しくない? | Not Equal? | プログラミング → 比較 |
| 以上? | Greater Or Equal? | プログラミング → 比較 |
| 以下? | Less Or Equal? | プログラミング → 比較 |
| 選択 | Select | プログラミング → 比較 |
| 複合演算 | Compound Arithmetic | プログラミング → ブール |
| NOT | Not | プログラミング → ブール |
| 倍精度浮動小数点に変換 | To Double Precision Float | プログラミング → 数値 → 変換 |
| 加算 | Add | プログラミング → 数値 |
| 減算 | Subtract | プログラミング → 数値 |
| 乗算 | Multiply | プログラミング → 数値 |

## 10.5.2 通常VIのエラーガード

```text
error in
  → 名前でバンドル解除（status）
  → ケースストラクチャ
      True : 実処理を呼ばず、元エラーと安全な初期出力を返す
      False: 実処理を実行
```

全ケースの出力トンネルを配線し、`Use default if unwired`へ依存しない。

## 10.5.3 シフトレジスタの基本

シフトレジスタは、Forループの前回反復で作った値を次の反復へ渡すための左右一組の端子である。

追加方法：

1. Forループの枠を右クリックする。
2. `シフトレジスタを追加（Add Shift Register）`を選択する。
3. ループの左枠と右枠へ対になった端子が追加されたことを確認する。

```text
左外側端子 : ループ開始前の初期値を接続
左内側端子 : 前回反復までの値を受け取る
右内側端子 : 今回反復後の値を接続
右外側端子 : 全反復終了後の最終値を取得
```

本章では、累積配列、error cluster、検出済みモジュール番号、重複判定配列などを保持するために使用する。

## 10.5.4 ローカル検証エラーコード

| コード | 用途 |
|---:|---|
| `-700101` | U8x4変換VIの入力サイズ不正 |
| `-700102` | U8x8変換VIの入力サイズ不正 |
| `-700111` | CHINFOチャンネル数不正 |
| `-700112` | LOGINFOモジュール番号または重複不正 |
| `-700120` | SYSINFOサイズ不正 |
| `-700130` | Buffer Parser入力不正 |
| `-700131` | Raw Buffer不足 |

## 10.5.5 U8配列の単体テスト表示設定

U8配列のバイト値を16進数で確認するときは、配列枠ではなく**配列内の数値セル**を右クリックして設定する。

```text
表示形式 → 16進数
表示項目 → 基数
```

LabVIEW上では`0x78`ではなく`x78`と表示される。資料上の`0x78`とLabVIEW表示の`x78`は同じ値を表す。

出力数値も16進数で確認する場合は、出力表示器で同じ設定を行う。

### 3要素配列を作る方法

4要素配列から3要素へ減らす場合：

1. 配列の指標表示を`3`にして4番目の要素を表示する。
2. 4番目の数値セルを右クリックする。
3. `データ操作 → 要素を削除`を選ぶ。
4. 指標表示を`0`へ戻す。
5. 配列サイズ（Array Size）を一時接続し、実サイズが`3`であることを確認する。

表示行数を3行へ縮めても、実際の配列要素数は変わらない。

---

# 10.6 `RAMScope_Code_To_Error.vi`

## 10.6.1 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `API ReturnCode` | 入力 | I32 |
| `Function Name` | 入力 | String |
| `error in` | 入力 | error cluster |
| `error out` | 出力 | error cluster |

## 10.6.2 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所 |
|---:|---|---|---|
| 1 | 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 2 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 1 | 等しい? | Equal? | プログラミング → 比較 |
| 1 | 型変換 | Type Cast | プログラミング → 数値 → データ操作 |
| 1 | 文字列にフォーマット | Format Into String | プログラミング → 文字列 |
| 1 | 名前でバンドル | Bundle By Name | プログラミング → クラスタ、クラス、バリアント |

## 10.6.3 配線順

1. `error in`を名前でバンドル解除へ接続し、`status`を取り出す。
2. `status`を外側ケースストラクチャへ接続する。
3. 外側Trueでは`error in`をそのまま`error out`へ接続する。
4. 外側Falseで`API ReturnCode == 0`を判定し、内側ケースストラクチャへ接続する。
5. 内側Trueでは正常な`error in`をそのまま出力する。
6. 内側Falseでは`API ReturnCode`を型変換でU32として解釈する。
7. 文字列にフォーマットへ次を設定する。

```text
RAMScope %s failed. ReturnCode=0x%08X (%d)
```

8. `%s`へ`Function Name`、`%08X`へU32変換値、`%d`へ元のI32 ReturnCodeを接続する。
9. 名前でバンドルへ正常クラスタを接続し、`status=True`、`code=API ReturnCode`、`source=生成文字列`を設定する。
10. 名前でバンドル出力を`error out`へ接続する。

## 10.6.4 単体テスト

| error in | ReturnCode | 期待結果 |
|---|---:|---|
| 正常 | 0 | 正常クラスタ |
| 正常 | `806354945` | sourceに`0x30100001` |
| code=1234の既存エラー | 任意 | 1234を保持 |
| 正常 | -1 | sourceに`0xFFFFFFFF` |

---

# 10.7 薄いDLLラッパ12個

## 10.7.1 CLFN共通設定

| 項目 | 設定 |
|---|---|
| Library | `RAMScopeVP_API_x64.dll`のフルパス |
| Calling Convention | `C` |
| Thread | PoC中は`Run in UI thread` |
| Error checking | PoC中は`Maximum` |
| Return | Numeric / Signed 32-bit Integer / Value |

通常ラッパは`error in.status=True`でCLFNをスキップする。`DeviceExit`だけはCleanup用なので前段エラーがあっても呼ぶ。

## 10.7.2 CLFN一覧

| VI | 関数 | CLFN入力 | 初期化・出力 |
|---|---|---|---|
| `RS_DLL_GT150DeviceInit.vi` | `RAMScopeGT150DeviceInit` | I32 Pointer ×2 | 左へ0、右からUnitNum/kind |
| `RS_DLL_GT150DeviceExit.vi` | `RAMScopeGT150DeviceExit` | なし | ReturnCode |
| `RS_DLL_GT150AllInit.vi` | `RAMScopeGT150AllInit` | UnitNo I32 | ReturnCode |
| `RS_DLL_GT150GetSysInfo.vi` | `RAMScopeGT150GetSysInfo` | UnitNo、U8 Pointer | U8[960]を事前確保 |
| `RS_DLL_GT150PGT_SetMdlConfig.vi` | `RAMScopeGT150PGT_SetMdlConfig` | UnitNo、I32 Pointer | I32[16]を事前確保 |
| `RS_DLL_GT170SetMeasCond.vi` | `RAMScopeGT170SetMeasCond` | UnitNo、MdlNo、U8[72] | Builder出力 |
| `RS_DLL_GT170SetMeasCh.vi` | `RAMScopeGT170SetMeasCh` | UnitNo、MdlNo、ChNum、U8[`24×ChNum`] | Builder出力 |
| `RS_DLL_GT150SetLoggingInfo.vi` | `RAMScopeGT150SetLoggingInfo` | UnitNo、U8[136] | Builder出力 |
| `RS_DLL_GT150MeasStart.vi` | `RAMScopeGT150MeasStart` | UnitNo | ReturnCode |
| `RS_DLL_GT150GetBufferData.vi` | `RAMScopeGT150GetBufferData` | UnitNo、MdlNo、U8 buffer、DataNum Pointer、Lost Pointer | Raw/DataNum/LostDataNum |
| `RS_DLL_GT150ReleaseBufferData.vi` | `RAMScopeGT150ReleaseBufferData` | UnitNo | ReturnCode |
| `RS_DLL_GT150MeasStop.vi` | `RAMScopeGT150MeasStop` | UnitNo | ReturnCode |

各CLFNの戻り値とCLFN error outを`RAMScope_Code_To_Error.vi`へ接続する。

---

# 10.8 typedef作成

## 10.8.1 共通手順

1. プロジェクトエクスプローラで`30_RAMScope\00_Common`を右クリックする。
2. `新規 → タイプ定義`を選ぶ。
3. 制御器エディタが開いたことを確認する。
4. クラスタ型の場合は、制御器パレットからクラスタを配置する。
5. 列挙体型の場合は、制御器パレットから列挙体を配置する。
6. 必要な数値、文字列、Boolean、配列をクラスタ内へ配置する。
7. 数値制御器を右クリックし、`表現形式`をI32、U32、U64、DBLへ合わせる。
8. フィールド名を設定する。
9. `.ctl`として保存する。
10. プロジェクトエクスプローラ上へ作成した`.ctl`が表示されることを確認する。

`新規 → タイプ定義`から作成した場合、後からType Def.へ切り替える操作は不要。

## 10.8.2 型一覧

| typedef | 主なフィールド |
|---|---|
| `RAMScope_Byte_Order.ctl` | `Little Endian`、`Big Endian` |
| `RAMScope_Meas_Config.ctl` | DummyInterval I32、MeasPeri I32、MeasUnit I32 |
| `RAMScope_Channel.ctl` | Name、Enable、Core、Address、Size、Sign、Speed、Scale、Offset、Unit |
| `RAMScope_Module_Log_Config.ctl` | MdlNo I32、LogSize I32、BufferSize I32 |
| `RAMScope_Module_Info.ctl` | SYSINFO解析結果 |
| `RAMScope_Channel_Value.ctl` | 1チャンネルのRaw値、実値、工学値 |
| `RAMScope_Packet.ctl` | Channel Values、Flag、Timestamp |

## 10.8.3 `RAMScope_Channel.ctl`配列の作り方

`RAMScope_Channel.ctl`は1チャンネル分のクラスタであり、配列型ではない。`Channel List`入力は、このctlを要素に持つ一次元配列として作成する。

1. 対象VIのフロントパネルへ空の配列枠を配置する。
2. プロジェクトエクスプローラから`RAMScope_Channel.ctl`を配列枠の内側へドラッグする。
3. 配列全体のラベルを`Channel List`へ変更する。
4. ブロックダイアグラムで太いピンク色の配列ワイヤになることを確認する。
5. 単体テストで1要素を使う場合は、配列内クラスタを右クリックし、`データ操作 → 要素を挿入`を実行する。
6. 配列サイズ（Array Size）へ接続し、1要素なら`ChNum=1`になることを確認する。

```text
RAMScope_Channel.ctl          = 1チャンネル分
Channel List                 = RAMScope_Channel.ctlの一次元配列
ChNum                        = Array Size(Channel List)
CHINFO_170 Rawの必要バイト数 = 24 × ChNum
```

---

# 10.9 数値⇔U8変換VI

## 10.9.1 `U8x4_To_U32.vi`

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Bytes` | 入力 | U8一次元配列 |
| `Byte Order` | 入力 | `RAMScope_Byte_Order.ctl` |
| `error in` | 入力 | error cluster |
| `Value` | 出力 | U32 |
| `error out` | 出力 | error cluster |

### 2. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所 |
|---:|---|---|---|
| 1 | 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 3 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 1 | 配列サイズ | Array Size | プログラミング → 配列 |
| 1 | 等しい? | Equal? | プログラミング → 比較 |
| 1 | 指標配列 | Index Array | プログラミング → 配列 |
| 6 | 数値結合 | Join Numbers | プログラミング → 数値 → データ操作 |
| 1 | 文字列にフォーマット | Format Into String | プログラミング → 文字列 |
| 1 | 名前でバンドル | Bundle By Name | プログラミング → クラスタ、クラス、バリアント |

### 3. 配線順

1. `error in`を名前でバンドル解除へ接続し、`status`を外側ケースストラクチャへ接続する。
2. 外側TrueでU32定数`0`を`Value`へ、`error in`を`error out`へ接続する。
3. 外側Falseで`Bytes`を配列サイズへ接続する。
4. 配列サイズ出力とI32定数`4`を等しい?へ接続し、結果を2個目のケースストラクチャへ接続する。
5. サイズ不正のFalseケースでは、U32定数`0`を`Value`へ接続する。
6. 同ケースへ文字列にフォーマットを置き、次を設定する。

```text
U8x4_To_U32.vi: Input size must be 4. Actual=%d
```

7. `%d`へ配列サイズ出力を接続する。
8. 名前でバンドルへ`error in`を基準クラスタとして接続し、`status=True`、`code=-700101`、`source=生成文字列`を設定する。
9. 名前でバンドル出力を`error out`へ接続する。
10. サイズ正常のTrueケースで指標配列を4出力へ広げる。
11. 4個のindex端子へ上から`0`、`1`、`2`、`3`を接続する。
12. 出力を上から`b0`、`b1`、`b2`、`b3`としてByte Orderケースへ渡す。
13. Little Endianケースでは次の順で数値結合する。

```text
低位16bit: high=b1, low=b0
高位16bit: high=b3, low=b2
U32      : high=高位16bit, low=低位16bit
```

14. Big Endianケースでは次の順で数値結合する。

```text
高位16bit: high=b0, low=b1
低位16bit: high=b2, low=b3
U32      : high=高位16bit, low=低位16bit
```

15. Byte Orderの両ケースで変換値を`Value`へ、正常なerror clusterを`error out`へ接続する。

### 4. 単体テスト

事前に`Bytes`配列内セルと`Value`表示器を16進数表示へ変更し、基数を表示する。

| Bytes | Byte Order | 期待Value |
|---|---|---|
| `x78 x56 x34 x12` | Little Endian | `x12345678` |
| `x12 x34 x56 x78` | Big Endian | `x12345678` |
| `xFF xFF xFF xFF` | Little Endian | `xFFFFFFFF` |
| 3要素 | 任意 | Value=0、code=`-700101` |
| 既存エラー | 任意 | 既存エラー保持、Value=0 |

## 10.9.2 `U8x4_To_I32.vi`

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Bytes` | 入力 | U8一次元配列 |
| `Byte Order` | 入力 | `RAMScope_Byte_Order.ctl` |
| `error in` | 入力 | error cluster |
| `Value` | 出力 | I32 |
| `error out` | 出力 | error cluster |

### 2. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所 |
|---:|---|---|---|
| 1 | `U8x4_To_U32.vi` | SubVI | `30_RAMScope\00_Common` |
| 1 | 型変換 | Type Cast | プログラミング → 数値 → データ操作 |
| 1 | I32数値定数 | I32 Numeric Constant | プログラミング → 数値 |

### 3. 配線順

1. ブロックダイアグラム左側へ`U8x4_To_U32.vi`を配置する。
2. `Bytes`入力をSubVIの`Bytes`へ接続する。
3. `Byte Order`入力をSubVIの`Byte Order`へ接続する。
4. `error in`をSubVIの`error in`へ接続する。
5. 型変換をSubVIの右側へ配置する。
6. SubVIのU32 `Value`を型変換の入力`x`へ接続する。
7. I32数値定数`0`を作り、右クリックして表現形式がI32であることを確認する。
8. I32定数を型変換の型指定入力`type`へ接続する。
9. 型変換のI32出力を本VIの`Value`へ接続する。
10. SubVIの`error out`を本VIの`error out`へ接続する。

通常の数値変換ではなく型変換を使用する。これにより32bitのビット列を変えずに符号付きI32として解釈する。

### 4. 単体テスト

| Bytes | Byte Order | 期待Value | 期待error |
|---|---|---:|---|
| `xFF xFF xFF xFF` | Little Endian | `-1` | 正常 |
| `x00 x00 x00 x80` | Little Endian | `-2147483648` | 正常 |
| `x7F xFF xFF xFF` | Big Endian | `2147483647` | 正常 |
| 3要素 | 任意 | 0 | code=`-700101` |
| 既存エラー | 任意 | 0 | 既存エラー保持 |

## 10.9.3 `U8x8_To_U64.vi`

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Bytes` | 入力 | U8一次元配列 |
| `Byte Order` | 入力 | `RAMScope_Byte_Order.ctl` |
| `error in` | 入力 | error cluster |
| `Value` | 出力 | U64 |
| `error out` | 出力 | error cluster |

### 2. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所 |
|---:|---|---|---|
| 1 | 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 3 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 1 | 配列サイズ | Array Size | プログラミング → 配列 |
| 1 | 等しい? | Equal? | プログラミング → 比較 |
| 2 | 部分配列 | Array Subset | プログラミング → 配列 |
| 2 | `U8x4_To_U32.vi` | SubVI | `30_RAMScope\00_Common` |
| 2 | 数値結合 | Join Numbers | プログラミング → 数値 → データ操作 |
| 1 | 文字列にフォーマット | Format Into String | プログラミング → 文字列 |
| 1 | 名前でバンドル | Bundle By Name | プログラミング → クラスタ、クラス、バリアント |

### 3. 配線順

1. `error in`を名前でバンドル解除へ接続し、`status`を外側ケースストラクチャへ接続する。
2. 外側TrueではU64定数`0`を`Value`へ、`error in`を`error out`へ接続する。
3. 外側Falseで`Bytes`を配列サイズへ接続する。
4. 配列サイズ出力とI32定数`8`を等しい?へ接続し、結果をサイズ判定ケースへ接続する。
5. サイズ不正のFalseケースでU64定数`0`を`Value`へ接続する。
6. 文字列にフォーマットへ次を設定し、`%d`へ実サイズを接続する。

```text
U8x8_To_U64.vi: Input size must be 8. Actual=%d
```

7. 名前でバンドルへ`error in`を接続し、`status=True`、`code=-700102`、`source=生成文字列`を設定する。
8. 名前でバンドル出力を`error out`へ接続する。
9. サイズ正常のTrueケースへ部分配列を2個配置する。
10. 1個目の部分配列へ`Bytes`、index=`0`、length=`4`を接続し、`First4`を作る。
11. 2個目の部分配列へ`Bytes`、index=`4`、length=`4`を接続し、`Last4`を作る。
12. `U8x4_To_U32.vi`を2個横に配置する。
13. `First4`を1個目SubVIの`Bytes`へ、`Last4`を2個目SubVIの`Bytes`へ接続する。
14. `Byte Order`を両SubVIの`Byte Order`へ分岐して接続する。
15. `error in`を1個目SubVIへ、1個目の`error out`を2個目SubVIの`error in`へ直列接続する。
16. Byte Orderを3個目のケースストラクチャへ接続する。
17. Little Endianケースでは数値結合へ`high=Last4のU32`、`low=First4のU32`を接続する。
18. Big Endianケースでは数値結合へ`high=First4のU32`、`low=Last4のU32`を接続する。
19. 両ケースの数値結合出力を`Value`へ接続する。
20. 2個目SubVIの`error out`を本VIの`error out`へ接続する。

### 4. 単体テスト

| Bytes | Byte Order | 期待Value |
|---|---|---|
| `x32 x00 x00 x00 x00 x00 x00 x00` | Little Endian | 50 |
| `x00 x00 x00 x00 x00 x00 x00 x32` | Big Endian | 50 |
| `x78 x56 x34 x12 xEF xCD xAB x90` | Little Endian | `x90ABCDEF12345678` |
| 7要素 | 任意 | Value=0、code=`-700102` |
| 既存エラー | 任意 | 既存エラー保持、Value=0 |

## 10.9.4 `U32_To_LE_U8x4.vi`

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Value` | 入力 | U32 |
| `error in` | 入力 | error cluster |
| `Bytes` | 出力 | U8一次元配列 |
| `error out` | 出力 | error cluster |

### 2. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所 |
|---:|---|---|---|
| 1 | 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 1 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 3 | 数値分割 | Split Number | プログラミング → 数値 → データ操作 |
| 1 | 配列連結追加 | Build Array | プログラミング → 配列 |
| 1 | 配列定数 | Array Constant | プログラミング → 配列 |

### 3. 配線順

1. `error in`を名前でバンドル解除へ接続し、`status`をケースストラクチャへ接続する。
2. Trueケースへ空の配列定数を配置する。
3. 配列定数の中へU8数値定数を入れ、U8一次元配列型にする。
4. 空U8配列を`Bytes`へ、`error in`を`error out`へ接続する。
5. Falseケースへ数値分割を3個配置する。
6. `Value`を1個目の数値分割へ接続する。
7. 1個目の上側出力`most significant half`を`High Word`、下側出力`least significant half`を`Low Word`として扱う。
8. `Low Word`を2個目の数値分割へ接続する。
9. 2個目の上側出力を`b1`、下側出力を`b0`として扱う。
10. `High Word`を3個目の数値分割へ接続する。
11. 3個目の上側出力を`b3`、下側出力を`b2`として扱う。
12. 配列連結追加を4入力へ広げる。
13. 上から`b0`、`b1`、`b2`、`b3`を接続する。
14. 配列連結追加のU8一次元配列を`Bytes`へ接続する。
15. `error in`を変更せず`error out`へ接続する。

### 4. 単体テスト

| Value | 期待Bytes |
|---:|---|
| `x12345678` | `x78 x56 x34 x12` |
| `x00000064` | `x64 x00 x00 x00` |
| `xFFFFFFFF` | `xFF xFF xFF xFF` |
| 既存エラー | 空配列、既存エラー保持 |

## 10.9.5 `I32_To_LE_U8x4.vi`

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Value` | 入力 | I32 |
| `error in` | 入力 | error cluster |
| `Bytes` | 出力 | U8一次元配列 |
| `error out` | 出力 | error cluster |

### 2. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所 |
|---:|---|---|---|
| 1 | 型変換 | Type Cast | プログラミング → 数値 → データ操作 |
| 1 | U32数値定数 | U32 Numeric Constant | プログラミング → 数値 |
| 1 | `U32_To_LE_U8x4.vi` | SubVI | `30_RAMScope\00_Common` |

### 3. 配線順

1. 型変換をブロックダイアグラム左側へ配置する。
2. I32 `Value`を型変換の`x`へ接続する。
3. U32数値定数`0`を作り、型変換の`type`へ接続する。
4. 型変換のU32出力を`U32_To_LE_U8x4.vi`の`Value`へ接続する。
5. `error in`をSubVIの`error in`へ接続する。
6. SubVIの`Bytes`を本VIの`Bytes`へ接続する。
7. SubVIの`error out`を本VIの`error out`へ接続する。

### 4. 単体テスト

| Value | 期待Bytes |
|---:|---|
| 100 | `x64 x00 x00 x00` |
| -1 | `xFF xFF xFF xFF` |
| `-2147483648` | `x00 x00 x00 x80` |
| 既存エラー | 空配列、既存エラー保持 |

---

# 10.10 構造体Builder

## 10.10.1 `Build_MEASINFO_170_Raw.vi`

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Meas Config` | 入力 | `RAMScope_Meas_Config.ctl` |
| `error in` | 入力 | error cluster |
| `MEASINFO_170 Raw` | 出力 | U8一次元配列 |
| `error out` | 出力 | error cluster |

### 2. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所 |
|---:|---|---|---|
| 2 | 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 1 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 2 | 配列初期化 | Initialize Array | プログラミング → 配列 |
| 3 | `I32_To_LE_U8x4.vi` | SubVI | `30_RAMScope\00_Common` |
| 3 | 部分配列置換 | Replace Array Subset | プログラミング → 配列 |

### 3. 配線順

1. `error in`を1個目の名前でバンドル解除へ接続し、`status`をケースストラクチャへ接続する。
2. Trueケースへ配列初期化を配置する。
3. U8定数`0`を`element`、I32定数`72`を`dimension size`へ接続する。
4. U8[72]を`MEASINFO_170 Raw`へ、`error in`を`error out`へ接続する。
5. Falseケースへ2個目の配列初期化を配置し、同じくU8[72]のゼロ配列を作成する。
6. `Meas Config`を2個目の名前でバンドル解除へ接続し、`DummyInterval`、`MeasPeri`、`MeasUnit`を表示する。
7. `I32_To_LE_U8x4.vi`を3個横に配置する。
8. `DummyInterval`を1個目、`MeasPeri`を2個目、`MeasUnit`を3個目の`Value`へ接続する。
9. `error in`を1個目SubVIへ、1個目の`error out`を2個目へ、2個目を3個目へ直列接続する。
10. 部分配列置換を3個直列に配置する。
11. U8[72]を1個目の`array`へ接続し、index=`0`、`new element/subarray=DummyInterval Bytes`とする。
12. 1個目の出力配列を2個目へ接続し、index=`4`、`new element/subarray=MeasPeri Bytes`とする。
13. 2個目の出力配列を3個目へ接続し、index=`8`、`new element/subarray=MeasUnit Bytes`とする。
14. 3個目の出力配列を`MEASINFO_170 Raw`へ接続する。
15. 3個目SubVIの`error out`を本VIの`error out`へ接続する。
16. offset 12～71はゼロのまま残す。

### 4. 単体テスト

入力：

```text
DummyInterval = 100
MeasPeri      = 100
MeasUnit      = 2
```

期待出力：

```text
index 0..3   = x64 x00 x00 x00
index 4..7   = x64 x00 x00 x00
index 8..11  = x02 x00 x00 x00
index 12..71 = x00
Array Size   = 72
error out    = 正常
```

## 10.10.2 `Build_CHINFO_170_Raw.vi`

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Channel List` | 入力 | `RAMScope_Channel.ctl`一次元配列 |
| `error in` | 入力 | error cluster |
| `ChNum` | 出力 | I32 |
| `CHINFO_170 Raw` | 出力 | U8一次元配列 |
| `error out` | 出力 | error cluster |

`Channel List`は`RAMScope_Channel.ctl`単体ではなく、10.8.3で作成した一次元配列を使用する。

### 2. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所・追加方法 |
|---:|---|---|---|
| 1 | 配列サイズ | Array Size | プログラミング → 配列 |
| 2 | 以上? / 以下? | Greater Or Equal? / Less Or Equal? | プログラミング → 比較 |
| 1 | 複合演算 | Compound Arithmetic | プログラミング → ブール |
| 3 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 1 | Forループ | For Loop | プログラミング → ストラクチャ |
| 2 | シフトレジスタ | Shift Register | Forループ枠を右クリック → シフトレジスタを追加 |
| 2 | 配列初期化 | Initialize Array | プログラミング → 配列 |
| 2 | 乗算 | Multiply | プログラミング → 数値 |
| 2 | 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 6 | `U32_To_LE_U8x4.vi` | SubVI | `30_RAMScope\00_Common` |
| 1 | 配列連結追加 | Build Array | プログラミング → 配列 |
| 1 | 部分配列置換 | Replace Array Subset | プログラミング → 配列 |
| 1 | 文字列にフォーマット | Format Into String | プログラミング → 文字列 |
| 1 | 名前でバンドル | Bundle By Name | プログラミング → クラスタ、クラス、バリアント |

### 3. 配線順

#### A. ChNum算出と入力範囲判定

1. `Channel List`を配列サイズへ接続する。
2. 配列サイズ出力を`ChNum`出力へ直接接続する。
3. `ChNum`を以上?へ接続し、もう一方へI32定数`1`を接続する。
4. `ChNum`を以下?へ接続し、もう一方へI32定数`2048`を接続する。
5. 2個のBoolean出力を複合演算へ接続し、演算をANDにする。
6. AND出力をチャンネル数判定ケースストラクチャへ接続する。

#### B. チャンネル数不正のFalseケース

1. Falseケースへ配列初期化を配置する。
2. U8定数`0`を`element`へ接続する。
3. I32定数`0`を`dimension size`へ接続する。
4. 配列初期化の空U8一次元配列を`CHINFO_170 Raw`出力トンネルへ接続する。
5. 文字列にフォーマットを配置し、次を設定する。

```text
Build_CHINFO_170_Raw.vi: Channel count must be 1..2048. ChNum=%d
```

6. `%d`へ`ChNum`を接続する。
7. 名前でバンドルへ`error in`を基準クラスタとして接続する。
8. Boolean定数Trueを`status`へ接続する。
9. I32定数`-700111`を`code`へ接続する。
10. 文字列にフォーマット出力を`source`へ接続する。
11. 名前でバンドル出力を`error out`出力トンネルへ接続する。
12. `ChNum`はケース外で出力へ接続済みなので、Falseケース内に追加トンネルは作らない。

#### C. TrueケースへForループを配置する

1. Trueケース内へForループを配置する。
2. Forループの`N`端子は未配線にする。
3. `Channel List`をForループ左枠へ接続する。
4. 作成された入力トンネルを右クリックし、`指標付けを有効（Enable Indexing）`にする。
5. トンネルに`[]`記号が表示されることを確認する。
6. ループ外では`Channel List`配列、ループ内では1反復につき`RAMScope_Channel.ctl`単体が出力される。
7. `N`端子を未配線にしているため、ForループはChannel Listの要素数と同じ回数実行される。

#### D. CHINFO出力バッファ用シフトレジスタを追加する

1. Forループ枠を右クリックし、`シフトレジスタを追加（Add Shift Register）`を選ぶ。
2. 左右の枠へ対になった端子が追加されたことを確認する。
3. Trueケース内かつForループ外で、`ChNum`とI32定数`24`を乗算し、`Total Byte Size`を作る。
4. 配列初期化を配置する。
5. U8定数`0`を`element`へ、`Total Byte Size`を`dimension size`へ接続する。
6. U8[`24 × ChNum`]のゼロ配列を、CHINFO出力バッファ用シフトレジスタの左外側端子へ接続する。

```text
左外側端子 : ループ開始前のゼロ配列
左内側端子 : 前回反復までに書き込んだ配列
右内側端子 : 今回反復で更新した配列
右外側端子 : 全反復終了後の完成配列
```

#### E. error cluster用シフトレジスタを追加する

1. Forループ枠をもう一度右クリックし、2本目のシフトレジスタを追加する。
2. `error in`をerror cluster用シフトレジスタの左外側端子へ接続する。

```text
左外側端子 : ループ開始時のerror in
左内側端子 : 前回反復までのerror
右内側端子 : 今回反復後のerror
右外側端子 : ループ全体終了後のerror out
```

#### F. 各反復の先頭で既存エラーを確認する

1. error用シフトレジスタの左内側端子を名前でバンドル解除へ接続する。
2. 要素を`status`へ変更する。
3. `status`をループ内ケースストラクチャへ接続する。
4. Trueケースでは、CHINFO配列用左内側端子を右内側端子へそのまま接続する。
5. 同ケースで、error用左内側端子を右内側端子へそのまま接続する。
6. Falseケースに1チャンネル分の変換処理を作る。

#### G. 1チャンネル分を24バイトへ変換する

1. 自動指標付けトンネルのループ内出力を2個目の名前でバンドル解除へ接続する。
2. `Enable`、`Core`、`Address`、`Size`、`Sign`、`Speed`を表示する。
3. `U32_To_LE_U8x4.vi`を6個横に配置する。
4. 各フィールドを対応するSubVIの`Value`へ接続する。
5. error用シフトレジスタの左内側端子を1個目SubVIの`error in`へ接続する。
6. 1個目SubVIの`error out`を2個目の`error in`へ接続し、6個目まで直列接続する。
7. 配列連結追加を6入力へ広げる。
8. 配列連結追加を右クリックし、`入力を連結（Concatenate Inputs）`を有効にする。
9. 次の順で各U8[4]を接続し、`Current Channel Bytes` U8[24]を作る。

```text
Enable Bytes
Core Bytes
Address Bytes
Size Bytes
Sign Bytes
Speed Bytes
```

#### H. 今回の24バイトを累積バッファへ書き込む

1. Forループの反復端子`i`とI32定数`24`を乗算し、`Write Index`を作る。
2. 部分配列置換を配置する。
3. CHINFO配列用シフトレジスタの左内側端子を`array`へ接続する。
4. `Write Index`を`index`へ接続する。
5. `Current Channel Bytes`を`new element/subarray`へ接続する。
6. 更新後の配列をCHINFO配列用シフトレジスタの右内側端子へ接続する。
7. 6個目の`U32_To_LE_U8x4.vi`の`error out`をerror用シフトレジスタの右内側端子へ接続する。

各反復の書込位置：

```text
i=0 → index 0～23
i=1 → index 24～47
i=2 → index 48～71
```

#### I. Forループ終了後の出力を接続する

1. CHINFO配列用シフトレジスタの右外側端子を`CHINFO_170 Raw`出力トンネルへ接続する。
2. error用シフトレジスタの右外側端子を`error out`出力トンネルへ接続する。
3. チャンネル数判定ケースのTrue/False両方で`CHINFO_170 Raw`と`error out`のトンネルが配線済みであることを確認する。

### 4. 単体テスト

| Channel List | 期待ChNum | 期待Array Size | 期待error |
|---|---:|---:|---|
| 1要素 | 1 | 24 | 正常 |
| 2要素 | 2 | 48 | 正常 |
| 0要素 | 0 | 0 | code=`-700111` |
| 2049要素 | 2049 | 0 | code=`-700111` |
| 既存エラー | 要素数 | `24×ChNum`の初期ゼロ配列 | 既存エラー保持 |

2チャンネルのAddressを異なる値にした確認例：

```text
Channel 0 Address = x12345678
Channel 1 Address = xABCDEF01

CHINFO Raw index 8..11  = x78 x56 x34 x12
CHINFO Raw index 32..35 = x01 xEF xCD xAB
```

## 10.10.3 `Build_LOGINFO_Raw.vi`

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `LogDevice` | 入力 | I32 |
| `LimitHddSize` | 入力 | I32 |
| `Module Log Configs` | 入力 | `RAMScope_Module_Log_Config.ctl`一次元配列 |
| `error in` | 入力 | error cluster |
| `LOGINFO Raw` | 出力 | U8一次元配列 |
| `error out` | 出力 | error cluster |

### 2. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所・追加方法 |
|---:|---|---|---|
| 2 | 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 3以上 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 2 | 配列初期化 | Initialize Array | プログラミング → 配列 |
| 1 | Forループ | For Loop | プログラミング → ストラクチャ |
| 3 | シフトレジスタ | Shift Register | Forループ枠を右クリック → シフトレジスタを追加 |
| 4 | `I32_To_LE_U8x4.vi` | SubVI | `30_RAMScope\00_Common` |
| 5 | 部分配列置換 | Replace Array Subset | プログラミング → 配列 |
| 1 | 指標配列 | Index Array | プログラミング → 配列 |
| 2 | 以上? / 以下? | Greater Or Equal? / Less Or Equal? | プログラミング → 比較 |
| 1 | NOT | Not | プログラミング → ブール |
| 1 | 複合演算 | Compound Arithmetic | プログラミング → ブール |
| 2 | 乗算 / 加算 | Multiply / Add | プログラミング → 数値 |
| 1 | 文字列にフォーマット | Format Into String | プログラミング → 文字列 |
| 1 | 名前でバンドル | Bundle By Name | プログラミング → クラスタ、クラス、バリアント |

### 3. 配線順

#### A. 外側エラーガード

1. `error in`を1個目の名前でバンドル解除へ接続し、`status`を外側ケースストラクチャへ接続する。
2. 外側Trueへ配列初期化を配置する。
3. U8定数`0`とI32定数`136`を接続し、U8[136]ゼロ配列を作る。
4. U8[136]を`LOGINFO Raw`へ、元の`error in`を`error out`へ接続する。

#### B. 初期配列とヘッダを作る

1. 外側Falseへ1個目の配列初期化を配置し、U8[136]ゼロ配列を作る。
2. 2個目の配列初期化へBoolean定数FalseとI32定数`16`を接続し、`Seen Boolean[16]`を作る。
3. `I32_To_LE_U8x4.vi`を2個配置する。
4. `LogDevice`を1個目、`LimitHddSize`を2個目の`Value`へ接続する。
5. `error in`を1個目SubVIへ、1個目の`error out`を2個目SubVIへ接続する。
6. 部分配列置換を2個直列に配置する。
7. U8[136]を1個目の`array`へ、LogDevice Bytesを`new element/subarray`へ、I32定数`0`を`index`へ接続する。
8. 1個目の出力配列を2個目の`array`へ、LimitHddSize Bytesを`new element/subarray`へ、I32定数`4`を`index`へ接続する。
9. 2個目の出力を`Header Written LOGINFO`として扱う。

#### C. Forループと3本のシフトレジスタ

1. Forループを配置する。
2. `Module Log Configs`をForループ左枠へ接続し、自動指標付けを有効にする。
3. `N`端子は未配線にする。
4. Forループ枠を右クリックし、シフトレジスタを3本追加する。
5. 1本目の左外側へ`Header Written LOGINFO`を接続する。
6. 2本目の左外側へ`Seen Boolean[16]`を接続する。
7. 3本目の左外側へ2個目`I32_To_LE_U8x4.vi`の`error out`を接続する。

```text
シフトレジスタ1 : 累積LOGINFO U8[136]
シフトレジスタ2 : Seen Boolean[16]
シフトレジスタ3 : error cluster
```

#### D. 各反復の既存エラー確認

1. errorシフトレジスタの左内側端子を名前でバンドル解除へ接続する。
2. `status`をループ内ケースストラクチャへ接続する。
3. Trueケースでは、LOGINFO、Seen、errorの3本を左内側から右内側へそのまま接続する。
4. Falseケースにモジュール設定処理を作る。

#### E. MdlNoの範囲と重複を判定する

1. 自動指標付けされた1要素を2個目の名前でバンドル解除へ接続する。
2. `MdlNo`、`LogSize`、`BufferSize`を表示する。
3. `MdlNo >= 0`と`MdlNo <= 15`を作る。
4. Seenシフトレジスタの左内側を指標配列へ接続し、indexへ`MdlNo`を接続する。
5. `Seen[MdlNo]`をNOTへ接続する。
6. 範囲内判定2個とNOT出力を複合演算ANDへ接続する。
7. AND出力を有効/無効判定ケースストラクチャへ接続する。

#### F. 有効Trueケース

1. `MdlNo × 8`を計算する。
2. I32定数`8`を加えて`Log index`を作る。
3. I32定数`12`を加えて`Buffer index`を作る。
4. `I32_To_LE_U8x4.vi`を2個配置する。
5. `LogSize`を1個目、`BufferSize`を2個目の`Value`へ接続する。
6. errorシフトレジスタ左内側を1個目SubVIへ、1個目の`error out`を2個目SubVIへ接続する。
7. 部分配列置換を2個直列に配置する。
8. 累積LOGINFO左内側を1個目の`array`へ、Log Bytesを`new element/subarray`へ、Log indexを`index`へ接続する。
9. 1個目出力を2個目の`array`へ、Buffer Bytesを`new element/subarray`へ、Buffer indexを`index`へ接続する。
10. Seen配列更新用の部分配列置換へSeen左内側を接続する。
11. Boolean定数Trueを`new element/subarray`へ、MdlNoを`index`へ接続する。
12. 更新LOGINFOを1本目右内側、更新Seenを2本目右内側、2個目SubVIの`error out`を3本目右内側へ接続する。

#### G. 無効Falseケース

1. 累積LOGINFO左内側を1本目右内側へ変更せず接続する。
2. Seen左内側を2本目右内側へ変更せず接続する。
3. 文字列にフォーマットへ次を設定する。

```text
Build_LOGINFO_Raw.vi: MdlNo must be 0..15 and must not be duplicated. MdlNo=%d
```

4. `%d`へMdlNoを接続する。
5. 名前でバンドルへerror左内側を基準クラスタとして接続する。
6. `status=True`、`code=-700112`、`source=生成文字列`を設定する。
7. 名前でバンドル出力を3本目右内側へ接続する。

#### H. Forループ終了後

1. LOGINFOシフトレジスタの右外側を`LOGINFO Raw`へ接続する。
2. errorシフトレジスタの右外側を`error out`へ接続する。
3. Seen右外側は本VIの出力にはしない。

### 4. 単体テスト

入力例：

```text
LogDevice    = 1
LimitHddSize = 0
Module Log Configs[0]
  MdlNo      = 0
  LogSize    = 100
  BufferSize = 200
```

期待出力：

```text
index 0..3   = x01 x00 x00 x00
index 4..7   = x00 x00 x00 x00
index 8..11  = x64 x00 x00 x00
index 12..15 = xC8 x00 x00 x00
Array Size   = 136
error out    = 正常
```

| 条件 | 期待結果 |
|---|---|
| MdlNo=16 | code=`-700112` |
| 同じMdlNoを2回指定 | code=`-700112` |
| 既存エラー | U8[136]ゼロ配列、既存エラー保持 |

---

# 10.11 Parser

## 10.11.1 `Parse_SYSINFO_Array.vi`

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `SYSINFO Raw` | 入力 | U8一次元配列 |
| `Byte Order` | 入力 | `RAMScope_Byte_Order.ctl` |
| `error in` | 入力 | error cluster |
| `Module List` | 出力 | `RAMScope_Module_Info.ctl`一次元配列 |
| `MdlNo_RAM` | 出力 | I32 |
| `MdlNo_CAN` | 出力 | I32 |
| `Endian_RAM` | 出力 | I32 |
| `RAM Module Found?` | 出力 | Boolean |
| `CAN Module Found?` | 出力 | Boolean |
| `error out` | 出力 | error cluster |

### 2. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所・追加方法 |
|---:|---|---|---|
| 2 | 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 複数 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 1 | 配列サイズ | Array Size | プログラミング → 配列 |
| 複数 | 等しい? / 以上? | Equal? / Greater Or Equal? | プログラミング → 比較 |
| 1 | 等しくない? | Not Equal? | プログラミング → 比較 |
| 1 | Forループ | For Loop | プログラミング → ストラクチャ |
| 4 | シフトレジスタ | Shift Register | Forループ枠を右クリック → シフトレジスタを追加 |
| 1 | 乗算 | Multiply | プログラミング → 数値 |
| 12以上 | 部分配列 | Array Subset | プログラミング → 配列 |
| 11 | `U8x4_To_I32.vi` | SubVI | `30_RAMScope\00_Common` |
| 1 | 1D配列検索 | Search 1D Array | プログラミング → 配列 |
| 1 | バイト配列から文字列 | Byte Array To String | プログラミング → 文字列 → 文字列/配列/パス変換 |
| 1 | 名前でバンドル | Bundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 複数 | 複合演算 | Compound Arithmetic | プログラミング → ブール |
| 2 | 文字列にフォーマット / 名前でバンドル | Format Into String / Bundle By Name | プログラミング → 文字列 / クラスタ |

### 3. 配線順

#### A. 外側エラーガード

1. `error in`を1個目の名前でバンドル解除へ接続する。
2. `status`を外側ケースストラクチャへ接続する。
3. Trueケースで空の`RAMScope_Module_Info.ctl`一次元配列を`Module List`へ接続する。
4. I32定数`-1`を`MdlNo_RAM`と`MdlNo_CAN`へ接続する。
5. I32定数`0`を`Endian_RAM`へ接続する。
6. Boolean定数Falseを`RAM Module Found?`と`CAN Module Found?`へ接続する。
7. `error in`を`error out`へ接続する。

#### B. SYSINFOサイズ判定

1. 外側Falseで`SYSINFO Raw`を配列サイズへ接続する。
2. 配列サイズ出力とI32定数`960`を等しい?へ接続する。
3. Boolean出力をサイズ判定ケースへ接続する。
4. サイズ不正Falseケースでは、Aと同じ安全値を各出力へ接続する。
5. 文字列にフォーマットへ次を設定し、実サイズを接続する。

```text
Parse_SYSINFO_Array.vi: SYSINFO Raw size must be 960. Actual=%d
```

6. 名前でバンドルへ`error in`を接続し、`status=True`、`code=-700120`、`source=生成文字列`を設定して`error out`へ接続する。

#### C. Forループとシフトレジスタ

1. サイズ正常TrueケースへForループを配置する。
2. Forループの`N`端子へI32定数`16`を接続する。
3. Forループ枠を右クリックし、シフトレジスタを4本追加する。
4. 1本目左外側へI32定数`-1`を接続し、MdlNo_RAM用とする。
5. 2本目左外側へI32定数`-1`を接続し、MdlNo_CAN用とする。
6. 3本目左外側へI32定数`0`を接続し、Endian_RAM用とする。
7. 4本目左外側へ`error in`を接続し、error用とする。

#### D. 各60バイトレコードを切り出す

1. 反復端子`i`とI32定数`60`を乗算し、`Record Start`を作る。
2. 部分配列へ`SYSINFO Raw`、index=`Record Start`、length=`60`を接続する。
3. 出力を`Record U8[60]`として扱う。
4. errorシフトレジスタ左内側を2個目の名前でバンドル解除へ接続し、`status`をループ内ケースへ接続する。
5. status=Trueケースでは4本のシフトレジスタを変更せず右へ渡し、空の`RAMScope_Module_Info.ctl`定数をループ出力へ接続する。
6. status=Falseケースに以下の解析処理を作る。

#### E. 11個のI32フィールドを解析する

Recordから以下の4バイトを部分配列で切り出す。

| フィールド | index | length |
|---|---:|---:|
| module | 0 | 4 |
| module_type | 4 | 4 |
| probe_id | 8 | 4 |
| interface_id | 12 | 4 |
| version | 16 | 4 |
| addinfo | 20 | 4 |
| endian | 24 | 4 |
| probe_version | 28 | 4 |
| security_id_req | 32 | 4 |
| security_id_size | 36 | 4 |
| flash_enable | 40 | 4 |

1. `U8x4_To_I32.vi`を11個配置する。
2. 各4バイト配列を対応するSubVIの`Bytes`へ接続する。
3. `Byte Order`を11個のSubVIへ分岐して接続する。
4. errorシフトレジスタ左内側をmodule変換の`error in`へ接続する。
5. module変換からflash_enable変換までerror clusterを直列接続する。

#### F. name[16]を文字列へ変換する

1. Recordへ部分配列を接続し、index=`44`、length=`16`で`Name Bytes`を取得する。
2. Name Bytesを1D配列検索へ接続する。
3. 検索要素へU8定数`0`を接続する。
4. 検索結果をケースストラクチャへ接続する。
5. `-1`ケースではName Bytes全体をバイト配列から文字列へ接続する。
6. Defaultケースでは部分配列へName Bytes、index=`0`、length=`検索結果`を接続する。
7. NULLより前の部分配列をバイト配列から文字列へ接続する。

#### G. Module Infoクラスタを作る

1. `RAMScope_Module_Info.ctl`定数を名前でバンドルへ接続する。
2. `Record Index`へForループ反復端子`i`を接続する。
3. 11個の解析値を対応フィールドへ接続する。
4. Name文字列を`Name`へ接続する。
5. `module_type != 0x0F`を作り、`Connected?`へ接続する。
6. 名前でバンドル出力をForループ右枠へ接続し、自動指標付けを有効にする。
7. ループ終了後、この配列を`Module List`へ接続する。

#### H. RAM/CANモジュール番号を保持する

1. `module_type == 0x00`を作る。
2. MdlNo_RAMシフトレジスタ左内側とI32定数`-1`を等しい?へ接続する。
3. 2条件を複合演算ANDへ接続する。
4. RAM判定ケースTrueで`module`をMdlNo_RAM右内側、`endian`をEndian_RAM右内側へ接続する。
5. RAM判定FalseでMdlNo_RAMとEndian_RAMの左内側を右内側へそのまま接続する。
6. `module_type == 0x02`を作る。
7. MdlNo_CAN左内側と`-1`を等しい?へ接続する。
8. 2条件をANDへ接続する。
9. CAN判定Trueで`module`をMdlNo_CAN右内側へ接続する。
10. CAN判定FalseでMdlNo_CAN左内側を右内側へ接続する。
11. flash_enable変換の`error out`をerror右内側へ接続する。

#### I. Forループ終了後の出力

1. MdlNo_RAM右外側を`MdlNo_RAM`へ接続する。
2. MdlNo_CAN右外側を`MdlNo_CAN`へ接続する。
3. Endian_RAM右外側を`Endian_RAM`へ接続する。
4. `MdlNo_RAM >= 0`を`RAM Module Found?`へ接続する。
5. `MdlNo_CAN >= 0`を`CAN Module Found?`へ接続する。
6. error右外側を`error out`へ接続する。

### 4. 単体テスト

ダミーSYSINFOを作るときは、未使用レコードの`module_type`を`0x0F`へ設定する。全960バイトをゼロのままにすると、未使用レコードもRAMモジュールとして誤検出する可能性がある。

```text
Record 0
  module      = 0
  module_type = 0x00
  endian      = 0
  name        = "RAM0"

Record 1
  module      = 1
  module_type = 0x02
  name        = "CAN0"

Record 2～15
  module_type = 0x0F
```

期待出力：

```text
Array Size(Module List) = 16
MdlNo_RAM               = 0
MdlNo_CAN               = 1
Endian_RAM              = 0
RAM Module Found?       = True
CAN Module Found?       = True
error out               = 正常
```

| 条件 | 期待結果 |
|---|---|
| SYSINFO Rawが959要素 | code=`-700120`、MdlNo=-1 |
| RAMモジュールなし | RAM Found=False、Parser自体は正常 |
| 既存エラー | 安全値、既存エラー保持 |

## 10.11.2 `RAMScope_Parse_Buffer.vi`

### 1. 入出力

| 端子 | 方向 | 型 |
|---|---|---|
| `Raw Buffer` | 入力 | U8一次元配列 |
| `DataNum` | 入力 | I32 |
| `Channel List` | 入力 | `RAMScope_Channel.ctl`一次元配列 |
| `Byte Order` | 入力 | `RAMScope_Byte_Order.ctl` |
| `error in` | 入力 | error cluster |
| `Packets` | 出力 | `RAMScope_Packet.ctl`一次元配列 |
| `Parsed Packet Count` | 出力 | I32 |
| `Unused Byte Count` | 出力 | I32 |
| `error out` | 出力 | error cluster |

### 2. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所・追加方法 |
|---:|---|---|---|
| 2以上 | 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 複数 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ |
| 3以上 | 配列サイズ | Array Size | プログラミング → 配列 |
| 複数 | 加算、減算、乗算 | Add, Subtract, Multiply | プログラミング → 数値 |
| 複数 | 以上?、等しい? | Greater Or Equal?, Equal? | プログラミング → 比較 |
| 複数 | 複合演算 | Compound Arithmetic | プログラミング → ブール |
| 2 | Forループ | For Loop | プログラミング → ストラクチャ |
| 2 | シフトレジスタ | Shift Register | 各Forループ枠を右クリック → シフトレジスタを追加 |
| 複数 | 部分配列 | Array Subset | プログラミング → 配列 |
| 複数 | `U8x4_To_U32.vi` | SubVI | `30_RAMScope\00_Common` |
| 1 | `U8x8_To_U64.vi` | SubVI | `30_RAMScope\00_Common` |
| 2 | 名前でバンドル | Bundle By Name | プログラミング → クラスタ、クラス、バリアント |
| 1 | 型変換 | Type Cast | プログラミング → 数値 → データ操作 |
| 2 | 倍精度浮動小数点に変換 | To Double Precision Float | プログラミング → 数値 → 変換 |
| 1 | 選択 | Select | プログラミング → 比較 |
| 2 | 文字列にフォーマット / 名前でバンドル | Format Into String / Bundle By Name | プログラミング → 文字列 / クラスタ |

### 3. 配線順

#### A. 外側エラーガード

1. `error in`を名前でバンドル解除へ接続し、`status`を外側ケースストラクチャへ接続する。
2. 外側Trueへ空の`RAMScope_Packet.ctl`一次元配列を接続する。
3. I32定数`0`を`Parsed Packet Count`と`Unused Byte Count`へ接続する。
4. 元の`error in`を`error out`へ接続する。

#### B. サイズ計算と入力検証

1. 外側Falseで`Channel List`を配列サイズへ接続し、`ChNum`を作る。
2. I32定数`4`とChNumを乗算し、I32定数`12`を加算して`Packet Size`を作る。
3. `Packet Size × DataNum`で`Expected Byte Count`を作る。
4. `Raw Buffer`を配列サイズへ接続し、`Actual Byte Count`を作る。
5. `Actual Byte Count - Expected Byte Count`を`Unused Byte Count`へ接続する。
6. `ChNum >= 1`と`DataNum >= 0`をANDへ接続する。
7. AND出力を基本入力判定ケースへ接続する。
8. 基本入力不正Falseケースでは空Packets、count=0、Unused=0を出力する。
9. 文字列にフォーマットへChNumとDataNumを入れ、名前でバンドルによりcode=`-700130`を生成する。
10. 基本入力正常Trueケースで`Actual Byte Count >= Expected Byte Count`を判定する。
11. Raw不足Falseケースでは空Packets、count=0を出力し、code=`-700131`を生成する。
12. Raw十分Trueケースで`DataNum == 0`を判定する。
13. DataNum=0のTrueケースでは空Packets、count=0、計算済みUnused、正常errorを出力する。
14. DataNum>0のFalseケースへパケット解析処理を作る。

#### C. 外側Forループでパケットを繰り返す

1. 外側Forループを配置し、N端子へ`DataNum`を接続する。
2. Forループ枠を右クリックし、error cluster用シフトレジスタを追加する。
3. 左外側端子へ正常系ケースへ入ってきたerror clusterを接続する。
4. 反復端子`i × Packet Size`で`Packet Start`を作る。
5. error左内側を名前でバンドル解除へ接続し、`status`をパケット処理ケースへ接続する。
6. status=Trueケースでは空のPacketクラスタをループ出力へ接続し、error左内側を右内側へ接続する。
7. status=Falseケースにチャンネル、Flag、Timestamp解析を作る。

#### D. 内側Forループでチャンネル値を解析する

1. 内側Forループを外側Forループのstatus=Falseケースへ配置する。
2. `Channel List`を内側Forループ左枠へ接続し、自動指標付けを有効にする。
3. `N`端子は未配線にする。
4. 内側Forループ枠を右クリックし、error cluster用シフトレジスタを追加する。
5. 左外側端子へ外側errorシフトレジスタの左内側を接続する。
6. 内側反復端子`j × 4`へPacket Startを加算し、`Value Start`を作る。
7. 部分配列へRaw Buffer、index=`Value Start`、length=`4`を接続する。
8. 4バイト配列を`U8x4_To_U32.vi`へ接続する。
9. Byte OrderをSubVIへ接続する。
10. 内側error左内側をSubVIの`error in`へ接続する。
11. 自動指標付けされたChannelクラスタを名前でバンドル解除へ接続する。
12. `Name`、`Address`、`Sign`、`Scale`、`Offset`、`Unit`を取り出す。
13. Raw U32を1個目の倍精度浮動小数点に変換へ接続し、符号なしDBLを作る。
14. Raw U32を型変換の`x`へ接続し、型指定へI32定数`0`を接続する。
15. 型変換出力I32を2個目の倍精度浮動小数点に変換へ接続し、符号ありDBLを作る。
16. `Sign == 0`を作る。
17. 選択へ`selector=Sign == 0`、True入力=符号なしDBL、False入力=符号ありDBLを接続する。
18. 選択出力を`Value`として、`Value × Scale + Offset`を計算する。
19. `RAMScope_Channel_Value.ctl`定数を名前でバンドルへ接続する。
20. Channel Index、Name、Address、Raw U32、Value、Engineering Value、Unitを接続する。
21. 名前でバンドル出力を内側Forループ右枠へ接続し、自動指標付けで`Channel Values`配列を作る。
22. `U8x4_To_U32.vi`の`error out`を内側errorシフトレジスタ右内側へ接続する。
23. 内側ループ後のerror右外側を後続Flag解析の`error in`へ渡す。

#### E. FlagとTimestampを解析する

1. `Packet Start + 4 × ChNum`で`Flag Start`を作る。
2. 部分配列へRaw Buffer、Flag Start、length=`4`を接続する。
3. Flag Bytesを`U8x4_To_U32.vi`へ接続する。
4. Byte Orderを接続し、内側ループ後errorを`error in`へ接続する。
5. `Flag Start + 4`で`Timestamp Start`を作る。
6. 部分配列へRaw Buffer、Timestamp Start、length=`8`を接続する。
7. Timestamp Bytesを`U8x8_To_U64.vi`へ接続する。
8. Byte Orderを接続し、Flag変換の`error out`をTimestamp変換の`error in`へ接続する。
9. 現行作業仮定として`Timestamp Raw × 20e-9`を計算し、Timestamp Secondsを作る。

#### F. Packetクラスタを作る

1. `RAMScope_Packet.ctl`定数を名前でバンドルへ接続する。
2. Packet Indexへ外側Forループ反復端子`i`を接続する。
3. Channel Values、Flag、Timestamp Raw、Timestamp Secondsを接続する。
4. Packetクラスタを外側Forループ右枠へ接続し、自動指標付けで`Packets`を作る。
5. Timestamp変換の`error out`を外側errorシフトレジスタ右内側へ接続する。

#### G. Forループ終了後と全出力

1. 外側Forループ後のPacketsを`Packets`出力へ接続する。
2. Packetsを配列サイズへ接続し、`Parsed Packet Count`へ接続する。
3. 外側errorシフトレジスタ右外側を`error out`へ接続する。
4. Bで計算した`Unused Byte Count`を出力へ接続する。
5. すべての異常ケースで`Packets`、`Parsed Packet Count`、`Unused Byte Count`、`error out`の4出力が配線済みであることを確認する。

### 4. 単体テスト

Channel Listを2要素にする。

```text
Channel 0
  Name="Unsigned"
  Sign=0
  Scale=1.0
  Offset=0.0

Channel 1
  Name="Signed"
  Sign=1
  Scale=1.0
  Offset=0.0
```

Raw Buffer：

```text
x01 x00 x00 x00                    Channel 0 = 1
xFE xFF xFF xFF                    Channel 1 = -2
xA5 x00 x00 x00                    Flag = xA5
x32 x00 x00 x00 x00 x00 x00 x00  Timestamp = 50
```

入力：

```text
DataNum    = 1
Byte Order = Little Endian
```

期待出力：

```text
Packets[0].Channel Values[0].Value = 1
Packets[0].Channel Values[1].Value = -2
Packets[0].Flag                    = xA5
Packets[0].Timestamp Raw           = 50
Parsed Packet Count                = 1
Unused Byte Count                  = 0
error out                          = 正常
```

| 条件 | 期待結果 |
|---|---|
| Channel Listが空 | code=`-700130` |
| DataNum=-1 | code=`-700130` |
| Raw BufferがExpectedより1byte短い | code=`-700131` |
| DataNum=0 | 空Packets、count=0、正常 |
| 既存エラー | 空Packets、count=0、既存エラー保持 |

---

# 10.12 公開API

全公開APIは末尾で`Error_To_TestStatus.vi`を1回呼び、`Status.ctl`、`TestError.ctl`、標準error clusterを出力する。

## 10.12.1 `RAMScope_Connect.vi`

```text
RS_DLL_GT150DeviceInit.vi
  → Error_To_TestStatus.vi
```

## 10.12.2 `RAMScope_Init.vi`

```text
RS_DLL_GT150AllInit.vi
  → RS_DLL_GT150GetSysInfo.vi
  → Parse_SYSINFO_Array.vi
  → RAM Module Found?判定
  → RS_DLL_GT150PGT_SetMdlConfig.vi
  → SlotErr判定
  → Error_To_TestStatus.vi
```

`RAMScope_Config.vi`は作成しない。PGT設定は`RAMScope_Init.vi`へ統合する。

## 10.12.3 `RAMScope_Set_Cond.vi`

```text
Build_MEASINFO_170_Raw.vi
  → RS_DLL_GT170SetMeasCond.vi

Build_CHINFO_170_Raw.vi
  → RS_DLL_GT170SetMeasCh.vi

Build_LOGINFO_Raw.vi
  → RS_DLL_GT150SetLoggingInfo.vi
```

## 10.12.4 `RAMScope_Log_Start.vi`

`RS_DLL_GT150MeasStart.vi`だけを呼ぶ。

## 10.12.5 `RAMScope_Read.vi`

```text
Packet Size = 4 × ChNum + 12
Buffer Byte Size = Packet Size × Max DataNum

RS_DLL_GT150GetBufferData.vi
  → RAMScope_Parse_Buffer.vi
  → Error_To_TestStatus.vi
```

## 10.12.6 `RAMScope_Release.vi`

`RS_DLL_GT150ReleaseBufferData.vi`だけを呼ぶ実験用公開API。要否確定後に残すか廃止する。

## 10.12.7 `RAMScope_Log_Stop.vi`

`RS_DLL_GT150MeasStop.vi`だけを呼ぶ。

## 10.12.8 `RAMScope_Close.vi`

前段エラーがあってもDeviceExitを実行し、元エラーと終了エラーを統合する。

---

# 10.13 最小PoC

```text
RAMScope_Connect.vi
  → RAMScope_Init.vi
  → RAMScope_Set_Cond.vi
  → RAMScope_Log_Start.vi
  → Wait
  → RAMScope_Read.vi
  → RAMScope_Log_Stop.vi
  → RAMScope_Close.vi
```

Cleanup経路では、計測中ならStopし、Release候補を実行してからCloseする。

## 10.13.1 合格条件

- DeviceInitが成功しUnitNum/kindを取得
- AllInit、GetSysInfo、PGT_SetMdlConfigが成功
- MdlNo_RAMを取得
- MEASINFO=72byte
- CHINFO=`24×ChNum`byte
- LOGINFO=136byte
- SetMeasCond、SetMeasCh、SetLoggingInfoが成功
- MeasStart、GetBufferData、MeasStopが成功
- 既知RAM変数と解析値が一致
- LostDataNumを記録
- 正常・異常の両方でDeviceExitまで実行
- 複数回再接続・再測定が可能

---

# 10.14 TestStandへの引き渡し

RAMScope単体PoCと採用CAN方式の単体PoCが完了してからTestStandへ組み込む。

```text
Setup
  RAMScope_Connect.vi
  RAMScope_Init.vi
  RAMScope_Set_Cond.vi

Main
  RAMScope_Log_Start.vi
  Loop:
    RAMScope_Read.vi
    Wait
  RAMScope_Log_Stop.vi

Cleanup
  RAMScope_Log_Stop.vi（計測中のみ）
  RAMScope_Release.vi（採用時のみ）
  RAMScope_Close.vi
```

TestStandから`RS_DLL_*`を直接呼ばない。

---

# 10.15 トラブルシュート

| 症状 | 主な確認 | 対応 |
|---|---|---|
| エラー193 | x64/x86不一致 | x86ランタイム隔離、VC++2013 x64確認 |
| エラー126 | 依存DLL不足 | ベンダー相対配置を確認 |
| エラー127 | 関数名、無効Handle | Handle非ゼロ、関数名完全一致 |
| LabVIEWクラッシュ | 引数型、配列サイズ | ヘッダとCLFN再照合 |
| U8変換値が逆 | Byte Order | Little/Bigの数値結合順を確認 |
| 同じバイトが4回出る | 指標配列index | `0,1,2,3`を接続 |
| 16進数入力が`4E`等へ変わる | 10進入力後に表示だけ変更 | 16進表示へ変更後に値を再入力 |
| 3要素試験にならない | 表示行数と実要素数を混同 | `データ操作 → 要素を削除`後、Array Sizeで確認 |
| Channel ListをArray Sizeへ接続できない | ctl単体を置いている | 配列枠の要素として`RAMScope_Channel.ctl`を配置 |
| CHINFOが2次元 | 配列連結追加 | `入力を連結`を有効化 |
| シフトレジスタが見つからない | 関数パレットを探している | Forループ枠を右クリックして追加 |
| Buffer不足 | Buffer Byte Size | `(4×ChNum+12)×MaxDataNum`を確認 |
| 値と変数名がずれる | Channel List順序 | BuilderとParserへ同一配列を渡す |

---

# 10.16 未確定事項

- `0x30100001`のベンダー正式定義
- GT170接続時のDeviceInit正常値
- AllInit以降の実機通し動作
- `Size`、`Sign`、`Speed`コードの正式定義
- `Endian_RAM`コードとByte Orderの正式マッピング
- Timestamp単位の実機確定
- 既存RAMScopeコンフィグファイルの正式読込仕様
- `ReleaseBufferData`の必須性と呼び出し位置
- APIのスレッドセーフ性
- CANの最終方式

未確定事項は公開APIへ推測で固定しない。

---

# 10.17 現在の作業チェックリスト

## 完了済み

- [x] x64 DLLロード
- [x] DeviceInit関数解決
- [x] x86版VC++2013ランタイム混在によるエラー193を解消
- [x] `RAMScope_Code_To_Error.vi`の4パターン試験
- [x] 薄いDLLラッパ12個を作成
- [x] `U8x4_To_U32.vi`のLittle Endian正常試験

## 次に作成・確認

- [ ] `U8x4_To_U32.vi`のBig Endian、3要素、既存エラー試験
- [ ] `U8x4_To_I32.vi`
- [ ] `U8x8_To_U64.vi`
- [ ] `U32_To_LE_U8x4.vi`
- [ ] `I32_To_LE_U8x4.vi`
- [ ] 残りtypedef
- [ ] Builder 3個
- [ ] Parser 2個
- [ ] 公開API 8個
- [ ] `PoC_RAMScope_Main.vi`

---

# 10.18 参照した公式資料

- NI LabVIEWプログラミングリファレンス：配列サイズ（Array Size）
- NI LabVIEWプログラミングリファレンス：指標配列（Index Array）
- NI LabVIEWプログラミングリファレンス：型変換（Type Cast）
- NI LabVIEWプログラミングリファレンス：Forループ（For Loop）
- NI LabVIEWプログラミングリファレンス：シフトレジスタ（Shift Register）
- NI LabVIEWプログラミングリファレンス内の各関数ページ
- `docs/reference/RAMScopeVP.h`
- `docs/reference/GTHard.h`
- `docs/reference/samp_simple.cpp`
