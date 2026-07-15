# 10B. RAMScope VI実装手順：DLLラッパ → データ変換 → 公開API → 最小PoC

> **本章の役割**：RAMScope単体の最小PoCを完成させるまでの実装順、フォルダ構成、各資料の役割を定義する。
>
> 詳細な作り方は10B-1から10B-4へ分離し、本章では同じ内容を重複記載しない。配置や名称が食い違う場合は、本章のフォルダ構成を正とする。
>
> 関数・構造体・定数は [10：RAMScope API技術リファレンス](./10_RAMScope実装方針.md) とメーカー提供ヘッダを正とする。

**最終整理日：2026-07-15**

---

# 1. 実装順序

```text
10A：DLL配置・x64疎通確認
  ↓
10B-1：RAMScope_Code_To_Error.vi
  ↓
10B-2：1関数1VIの薄いDLLラッパ12個
  ↓
10B-3：APIへ渡す構造体U8配列の生成
  ↓
10B-4：SYSINFO・測定バッファのParser
  ↓
30_Public：複数VIをつないだ公開API
  ↓
PoC_RAMScope_Main.viでRAM計測単体確認
  ↓
RAM計測PoC完了
  ↓
CAN方式確定・CAN単体PoC
  ↓
TestStand組み込み
```

RAMScopeは最初からTestStandへ組み込まない。DLL層、データ変換層、公開API層を単体で確認してから上位へ進む。

---

# 2. 正式なフォルダ構成

以下を現在の正本とする。

```text
30_RAMScope\
├─ 00_Common\
│  ├─ RAMScope_Code_To_Error.vi
│  │
│  ├─ RAMScope_Channel.ctl
│  ├─ RAMScope_Meas_Config.ctl
│  ├─ RAMScope_Module_Log_Config.ctl
│  ├─ RAMScope_Module_Info.ctl
│  ├─ RAMScope_Channel_Value.ctl
│  ├─ RAMScope_Packet.ctl
│  ├─ RAMScope_Byte_Order.ctl
│  │
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
├─ 20_Parser\
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
├─ 50_CAN\                         （RAM計測PoC後に作成）
└─ 90_TestStand\                   （RAM/CAN PoC後に必要時作成）
```

## 2.1 `20_Parser`という名称について

既存プロジェクトとの互換性を優先し、フォルダ名は`20_Parser`を維持する。ただし責務はParserだけではなく、次の**データ変換層**全体である。

- LabVIEW設定値 → C構造体互換U8配列を生成するBuilder
- DLLのU8出力 → LabVIEWクラスタへ変換するParser

将来フォルダを`20_Data_Conversion`へ変更する場合は、全資料とLabVIEWプロジェクトを同時に更新する。PoC途中で名称だけを変更しない。

## 2.2 `RAMScope_Context.ctl`の扱い

`RAMScope_Context.ctl`は現在の必須作成物から外す。

最小PoCでは、`UnitNo`、`MdlNo_RAM`、`MdlNo_CAN`、`Endian_RAM`、Channel Listを個別配線して動作を確認する。公開APIの端子が固まった後、配線数を減らす必要が明確になった場合のみContextへ統合する。

---

# 3. ctlが増えた理由と役割

追加されたctlは、同じ情報を重複保持するためではなく、入力設定と解析結果を型で分離するために使用する。

| ctl | 分類 | 役割 | 主な使用先 |
|---|---|---|---|
| `RAMScope_Channel.ctl` | 入力設定 | 監視RAM変数1個のアドレス、Size、Sign、Scale等 | CHINFO Builder、Buffer Parser |
| `RAMScope_Meas_Config.ctl` | 入力設定 | 測定周期、測定単位 | MEASINFO Builder |
| `RAMScope_Module_Log_Config.ctl` | 入力設定 | モジュールごとのLogSize、BufferSize | LOGINFO Builder |
| `RAMScope_Module_Info.ctl` | 解析結果 | SYSINFO 1レコード | SYSINFO Parser |
| `RAMScope_Channel_Value.ctl` | 解析結果 | 1パケット内の1チャンネル値 | Buffer Parser |
| `RAMScope_Packet.ctl` | 解析結果 | チャンネル値、Flag、Timestampを含む1パケット | Buffer Parser、公開Read |
| `RAMScope_Byte_Order.ctl` | 共通Enum | 測定バッファのLittle/Big Endian指定 | 数値変換VI、Buffer Parser |

### 型を分ける基準

- DLLへ渡す設定と、DLLから解析した結果を同じctlへ混在させない。
- 1つのctlは1つの概念だけを表す。
- BuilderとParserの双方で必要な`RAMScope_Channel.ctl`だけは共通入力として再利用する。
- ctlを増やすこと自体を目的にしない。使用先がないctlは作成しない。

---

# 4. レイヤごとの責務

| レイヤ | 責務 | やってはいけないこと |
|---|---|---|
| `00_Common` | typedef、byte変換、APIコード変換 | DLL関数の直接呼び出し、機器状態遷移 |
| `10_DLL_Wrapper` | CLFNでDLL関数を1個だけ呼ぶ | 複数APIの順序制御、構造体生成、Parser、TestStand判定 |
| `20_Parser` | 構造体U8配列の生成、生バイト列の解析 | DLLの直接呼び出し、測定開始・停止 |
| `30_Public` | DLLラッパとデータ変換VIを接続し、1イベントを完結 | TestStand固有変数への直接依存 |
| `40_PoC` | 公開APIを順番に呼び、実機単体で確認 | 本番試験ロジックの作り込み |
| `50_CAN` | 採用したCAN方式のラッパ、公開API、単体PoC | 方式未決定の候補を全て実装 |
| `90_TestStand` | Adapter上の単純化が必要な場合だけ薄いVIを配置 | DLLラッパの直接呼び出し、公開API処理の複製 |

---

# 5. 詳細資料の担当範囲

| 資料 | 担当範囲 |
|---|---|
| [10B-1](./10B1_RAMScope_Code_To_Error_VI作成手順.md) | API ReturnCodeを標準error clusterへ変換 |
| [10B-2](./10B2_RAMScope_DLLラッパVI_CLFN配線手順.md) | 12個のDLLラッパ、CLFN設定、端子配線、配列事前確保 |
| [10B-3](./10B3_RAMScope_構造体生成VI作成手順.md) | MEASINFO、CHINFO、LOGINFOのU8配列生成 |
| [10B-4](./10B4_RAMScope_Parser_VI作成手順.md) | SYSINFOと測定バッファの解析 |

詳細資料内のファイル配置が本章と異なる場合は、本章のフォルダ構成へ読み替える。

---

# 6. 構造体生成とParserの接続関係

```text
RAMScope_Meas_Config.ctl
  → Build_MEASINFO_170_Raw.vi
  → RS_DLL_GT170SetMeasCond.vi

RAMScope_Channel.ctl 配列
  ├→ Array Size → ChNum
  ├→ Build_CHINFO_170_Raw.vi
  │    → RS_DLL_GT170SetMeasCh.vi
  └→ RAMScope_Parse_Buffer.vi

RAMScope_Module_Log_Config.ctl 配列
  → Build_LOGINFO_Raw.vi
  → RS_DLL_GT150SetLoggingInfo.vi

RS_DLL_GT150GetSysInfo.vi
  → SYSINFO Raw U8[960]
  → Parse_SYSINFO_Array.vi
  → Module List / MdlNo_RAM / MdlNo_CAN / Endian_RAM

RS_DLL_GT150GetBufferData.vi
  → Raw Buffer / DataNum
  → RAMScope_Parse_Buffer.vi
  → RAMScope_Packet.ctl 配列
```

`Channel List`をCHINFO生成とBuffer解析の両方へ使用することで、設定したチャンネル順と解析順を一致させる。

---

# 7. 公開API構成

## 7.1 `RAMScope_Connect.vi`

```text
RS_DLL_GT150DeviceInit.vi
  → Error_To_TestStatus.vi
```

出力：`UnitNum`、`kind`、`API ReturnCode`、Status、TestError、error out。

## 7.2 `RAMScope_Init.vi`

```text
RS_DLL_GT150AllInit.vi
  → RS_DLL_GT150GetSysInfo.vi
  → Parse_SYSINFO_Array.vi
  → RS_DLL_GT150PGT_SetMdlConfig.vi
  → Error_To_TestStatus.vi
```

出力：`MdlNo_RAM`、`MdlNo_CAN`、`Endian_RAM`、Module List、SlotErr。

## 7.3 `RAMScope_Set_Cond.vi`

```text
Build_MEASINFO_170_Raw.vi
  → RS_DLL_GT170SetMeasCond.vi
  → Build_CHINFO_170_Raw.vi
  → RS_DLL_GT170SetMeasCh.vi
  → Build_LOGINFO_Raw.vi
  → RS_DLL_GT150SetLoggingInfo.vi
  → Error_To_TestStatus.vi
```

`ChNum`は`Channel List`の`Array Size`から自動算出し、操作者の別入力にしない。

## 7.4 `RAMScope_Log_Start.vi`

```text
RS_DLL_GT150MeasStart.vi
  → Error_To_TestStatus.vi
```

## 7.5 `RAMScope_Read.vi`

```text
Buffer Byte Sizeを算出
  → RS_DLL_GT150GetBufferData.vi
  → RAMScope_Parse_Buffer.vi
  → Error_To_TestStatus.vi
```

`ReleaseBufferData`は正式な要否が確定するまで内包しない。

## 7.6 `RAMScope_Release.vi`

`RS_DLL_GT150ReleaseBufferData.vi`だけを呼ぶ実験用公開API。A/B/C比較後に正式な呼び出し位置を決定する。

## 7.7 `RAMScope_Log_Stop.vi`

`RS_DLL_GT150MeasStop.vi`だけを呼ぶ。

## 7.8 `RAMScope_Close.vi`

前段エラーがあっても`RS_DLL_GT150DeviceExit.vi`を実行し、元エラーと終了エラーを統合する。

---

# 8. 最小PoCフロー

```text
RAMScope_Connect.vi
  ↓
RAMScope_Init.vi
  ↓
RAMScope_Set_Cond.vi
  ↓
RAMScope_Log_Start.vi
  ↓
Wait
  ↓
RAMScope_Read.vi
  ↓
RAMScope_Log_Stop.vi
  ↓
RAMScope_Close.vi
```

`RAMScope_Close.vi`は途中エラー時にも実行できるCleanup経路へ配置する。

## 8.1 完了条件

| 項目 | 完了条件 |
|---|---|
| 接続 | DeviceInitが成功し、UnitNumとkindを取得 |
| 初期化 | AllInit、GetSysInfo、PGT_SetMdlConfigが成功 |
| モジュール | RAMモジュール番号を取得 |
| 構造体生成 | MEASINFO=72byte、CHINFO=`24×ChNum`byte、LOGINFO=136byte |
| 設定 | SetMeasCond、SetMeasCh、SetLoggingInfoが成功 |
| 測定 | MeasStart → GetBufferData → MeasStopが成功 |
| Parser | 既知RAM変数と解析値が一致 |
| 損失 | LostDataNumを記録し、許容値を判断可能 |
| 終了 | 正常・異常の両方でDeviceExitまで実行 |
| 再実行 | 再接続・再測定が可能 |

---

# 9. 現在の未確定事項

- `0x30100001`のベンダー正式定義
- `Size`、`Sign`、`Speed`コードの正式定義
- `Endian_RAM`コードと`RAMScope_Byte_Order.ctl`の正式マッピング
- Timestamp単位の実機確定
- 既存RAMScopeコンフィグファイルの正式読込仕様
- `ReleaseBufferData`の必須性と呼び出し位置
- APIのスレッドセーフ性

未確定事項はBuilder、Parser、公開API内へ推測で固定せず、実機結果またはベンダー一次資料を得た時点で更新する。