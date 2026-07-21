# 10. RAMScope GT170 実装ガイド

> **本ページと`docs/10_RAMScope/`配下をRAMScope実装の正本セットとする。**
>
> 本版は、2026-07-18に[00A](./00A_LabVIEW実装資料の記述ルール.md)と[00B](./00B_LabVIEW学習型VI設計ルール.md)で、ページに掲載されていた全VI作成手順を監査した版である。
>
> 監査前の文章は[99_監査前_第10章全文.md](./10_RAMScope/99_監査前_第10章全文.md)へ内容を変えず保存した。元文章を失わず、現在使用する手順だけを以下の一本道へ整理する。

**最終整理日：2026-07-18**

---

## 10.1 この章の読み方

RAMScopeのVIを作成するときは、次の順番で読む。

```text
00  00A・00B監査結果と現行仕様
  ↓
01  RAMScope_Code_To_Error.vi
  ↓
02  薄いDLL Wrapper 12個
  ↓
03  typedef・数値変換・構造体Builder
  ↓
04  SYSINFO / Buffer Parser
  ↓
05  公開API 8個
  ↓
06  PoC・ファイル保存・TestStand
```

| No. | 詳細ページ | 内容 |
|---:|---|---|
| 00 | [00_00A_00B監査結果と現行補正.md](./10_RAMScope/00_00A_00B監査結果と現行補正.md) | 全VI監査結果、確定仕様、共通説明と個別手順の境界 |
| 01 | [01_RAMScope_Code_To_Error_VI作成手順.md](./10_RAMScope/01_RAMScope_Code_To_Error_VI作成手順.md) | API ReturnCodeを標準error clusterへ変換するVI |
| 02 | [02_DLLラッパVI_全12個_CLFN配線手順.md](./10_RAMScope/02_DLLラッパVI_全12個_CLFN配線手順.md) | 12個それぞれのCプロトタイプ、Parameters、左端子、右端子、事前確保、テスト |
| 03 | [03_構造体Builder_VI作成手順.md](./10_RAMScope/03_構造体Builder_VI作成手順.md) | MEASINFO、CHINFO、LOGINFO Builderと数値変換 |
| 04 | [04_Parser_VI作成手順.md](./10_RAMScope/04_Parser_VI作成手順.md) | SYSINFO Parser、Buffer Parser、データモデルとループ構造 |
| 05 | [05_Public_API_8個_監査済み作成手順.md](./10_RAMScope/05_Public_API_8個_監査済み作成手順.md) | Connect、Init、Set Cond、Start、Read、Release、Stop、Close |
| 06 | [06_PoC_ロギング_TestStand.md](./10_RAMScope/06_PoC_ロギング_TestStand.md) | 最小PoC、TDMS保存、Cleanup、TestStand引渡し |
| 99 | [99_監査前_第10章全文.md](./10_RAMScope/99_監査前_第10章全文.md) | 監査前の第10章全文。実装時は参照しない |

詳細ページ間で記述が競合する場合は、`00`の現行補正、次に`05`の公開API、次に各個別手順の順で優先する。ベンダー一次資料と実測結果が最優先である。

---

## 10.2 実装の一本道

```text
STEP 0  環境準備とDLL疎通
  ↓
STEP 1  RAMScope_Code_To_Error.vi
  ↓
STEP 2  薄いDLL Wrapper 12個
  ↓
STEP 3  typedef 7個
  ↓
STEP 4  数値⇔U8変換VI 5個
  ↓
STEP 5  MEASINFO / CHINFO / LOGINFO Builder
  ↓
STEP 6  SYSINFO / Buffer Parser
  ↓
STEP 7  公開API 8個
  ↓
STEP 8  PoC_RAMScope_Main.vi
  ↓
STEP 9  GT170実機通し試験
  ↓
STEP 10 TestStand組込み
```

各VIをLabVIEW単体で作成し、単体試験に合格してから次へ進む。TestStandから`RS_DLL_*`、Builder、Parserを直接呼ばない。

---

## 10.3 全VIに適用する作成手順

複雑なVIは次の10項目で説明する。

```text
0. 実現したい機能とVIの責務
1. 入力データの実体
2. 出力データモデル
3. 前提条件・異常条件
4. 処理アルゴリズム
5. LabVIEW構造の選定理由
6. 入出力
7. 配置する関数およびSubVI等
8. 配線順
9. 単体テスト
```

単純なDLL Wrapperでは節を統合してよい。ただし、共通説明だけで個別VIの手順を置き換えてはならない。各Wrapperに次を必ず残す。

- Cプロトタイプ。
- CLFN Parametersの引数順、Type、Data Type、PassまたはArray Format。
- CLFN左端子へ接続する入力値・Pointer初期値。
- CLFN右端子から取得する値。
- DLL出力配列の型と事前確保サイズ。
- `Function Name`へ接続する文字列全文。
- `RAMScope_Code_To_Error.vi`までのerror cluster配線。
- True／False両Caseの全出力。
- 正常、既存エラー、境界または実機確認待ちの単体テスト。

---

## 10.4 レイヤ構成

```text
TestStand
  → RAMScope_* Public API
      → Builder / Parser / Common
          → RS_DLL_* Thin Wrapper
              → CLFN
                  → RAMScopeVP_API_x64.dll
```

| レイヤ | 責務 |
|---|---|
| `RS_DLL_*` | C関数1個を呼び、API ReturnCodeと標準error clusterを返す |
| Builder | LabVIEWの意味付き設定をDLL用U8配列へ変換する |
| Parser | DLLのU8配列を意味付きクラスタへ変換する |
| `RAMScope_*` | 下位VIを1イベントとして接続しStatus/TestErrorを返す |
| PoC | TestStandなしで順序、データ、Cleanupを検証する |
| TestStand | 条件、待ち、反復、レポート、Cleanupを管理する |

BuilderとParserはDLLを呼ばない純粋処理VIとする。実機なしのダミーデータ試験で、DLL問題と変換ロジック問題を分離する。

---

## 10.5 現在の確定事項

- LabVIEW 2026 Q1 64bitを使用する。
- `RAMScopeVP_API_x64.dll`をCLFNから呼ぶ。
- WindowsのC言語`long`は64bit DLLでも32bitなのでLabVIEWではI32とする。
- `0x30100001`は下位DLL非対応関数であり、未接続エラーと断定しない。
- GT170 RAM用`CHINFO_RAM170`は6個のU32、1チャンネル24byteである。
- CHINFO順は`enable / core / address / size / sign / speed`である。
- `size`は`0=1byte`、`1=2byte`、`2=4byte`である。
- `sign`は`0=unsigned`、`1=signed`である。
- `core`と`speed`は現行仕様では`0`を使用する。
- SYSINFOの`endian`は`0=Big Endian`、`1=Little Endian`である。
- `module_type`は`0x00=RAM`、`0x02=CAN`、`0x03=Analog`、`0x0E=Power Communication`、`0x0F=Disconnected`である。
- 測定Packetはチャンネルごとに4byte、Flag 4byte、Timestamp 8byteである。
- `Packet Size = 4 × ChNum + 12`である。
- Timestampは64bit countで、`1 count=20ns`である。
- `Timestamp Seconds = DBL(Timestamp Raw) × 20e-9`である。
- `RAMScopeGT150SetMdlConfig`ではなく、推奨された`RAMScopeGT150PGT_SetMdlConfig`を使用する。
- `ReleaseBufferData`は測定中に呼ばず、`MeasStop`成功後のアイドル状態で呼ぶ。

---

## 10.6 現在の未確定事項

- GT170接続時の`DeviceInit`正常ReturnCode、`UnitNum`、`kind`。
- AllInit以降のGT170実機通し動作。
- 1byte／2byte signed値が4byte Packetへ格納される際の正式な符号拡張仕様。
- RAMScopeVP API全体のスレッドセーフ性。
- 既存RAMScopeコンフィグファイルの正式読込API。
- 内部保存データ回収用`GetMeasNum`、`GetBlockNum`等の正式プロトタイプ。

未確定値を推測したCLFNやPublic APIへ固定しない。

---

## 10.7 全VI監査チェックリスト

- [ ] 欲しい機能とVIの責務が書かれている。
- [ ] 入力データの実体と出力データモデルが書かれている。
- [ ] 前提条件と異常条件が擬似コードまたは判定式で示されている。
- [ ] Case、For、While、Shift Registerの採用理由が書かれている。
- [ ] ストラクチャを先に配置し、selectorまたはNを接続してから内部処理を書く順番である。
- [ ] Case名が`True／Falseケース（selector条件：意味）`で書かれている。
- [ ] 全Caseのデータ出力、件数、Boolean、error、シフトレジスタ右内側が配線されている。
- [ ] error生成でBundle By Nameの基準クラスタ、status、code、source、出力トンネルが書かれている。
- [ ] Format String全文、プレースホルダ順、値、型、接続先が書かれている。
- [ ] Forループの反復対象、N、自動指標付けの有効／無効が書かれている。
- [ ] Shift Registerの保持対象、初期値、現在値引継ぎ、右外側出力が書かれている。
- [ ] DLL Wrapperは各VI個別にプロトタイプ、Parameters、左右端子、事前確保、Function Nameを持つ。
- [ ] 共通説明を理由に個別VIの作成手順を削除していない。
- [ ] 正常、境界、異常、既存error inの単体テストが書かれている。
