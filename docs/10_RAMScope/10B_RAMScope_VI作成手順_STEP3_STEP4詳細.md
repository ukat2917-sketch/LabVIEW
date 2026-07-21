# 10B. RAMScope VI作成手順：共通エラー変換・各VI詳細

> **本章の役割**： [10A](./10A_RAMScope実装手順_DLL準備とCLFN疎通確認.md) のDLL疎通と`RAMScope_Connect.vi` PoC完了後に、共通エラー変換と後続VIをLabVIEW上で作成する。
>
> 関数プロトタイプ・構造体・定数は [10](./10_RAMScope実装方針.md) とメーカー提供ヘッダを正とする。
> TestStandへの配置は [11](./11_TestStandシーケンス構築手順.md)、Cleanupは [12](./12_異常系処理とシャットダウン設計.md) を参照する。

**最終整理日：2026-07-14**

---

## 10B.1 この章で作るもの

```text
30_RAMScope\
├─ RAMScope_Code_To_Error.vi
├─ RAMScope_Connect.vi          ← 10Aで作成したDeviceInit VIを仕上げる
├─ RAMScope_Init.vi             ← AllInit + GetSysInfo
├─ RAMScope_Config.vi           ← PGT_SetMdlConfig
├─ RAMScope_Set_Cond.vi         ← SetMeasCond + SetMeasCh + SetLoggingInfo
├─ RAMScope_Log_Start.vi
├─ RAMScope_Read.vi
├─ RAMScope_Parse_Buffer.vi
├─ RAMScope_Log_Stop.vi
├─ RAMScope_Release.vi
├─ RAMScope_Close.vi
└─ RAMScope_Flow_Test.vi
```

最初に作成した`RAMScopeGT150DeviceInit`の最小VIは`RAMScope_Connect.vi`である。`RAMScope_Init.vi`は別VIとして作る。

---

## 10B.2 全VIの共通ルール

### 共通出力

| 端子 | 型 | 用途 |
|------|----|------|
| `実行結果ステータス` | `Status.ctl` | TestStandの継続・中断判定 |
| `エラー情報` | `TestError.ctl` | 機器名・コード・メッセージ・時刻 |
| `error out` | error cluster | 後段VIへの標準エラー伝播 |
| `API ReturnCode` | I32 | PoC・ログ用。量産後の公開は任意 |

### 通常VI

```text
error in
  → Case Structure
      ├─ errorあり：CLFNを呼ばず元エラーを伝播
      └─ errorなし：CLFNを実行
           → RAMScope_Code_To_Error.vi
           → Error_To_TestStatus.vi
```

### 複数CLFNを持つVI

各APIの直後に`RAMScope_Code_To_Error.vi`を置き、変換後の標準error clusterを次のCLFNへ直列で渡す。`Error_To_TestStatus.vi`はVIの最後に1回だけ呼ぶ。

### Cleanup VI

`RAMScope_Close.vi`は前段エラーがあってもDeviceExitを呼び、元エラーとCloseエラーを`Merge Errors`で統合する。

### CLFN共通設定

| 項目 | 設定 |
|------|------|
| DLL | `RAMScopeVP_API_x64.dll` |
| Calling Convention | C |
| Thread | PoC中はRun in UI thread |
| Error checking | PoC中はMaximum |
| `long` | I32 |
| `unsigned long` / `DWORD` | U32 |
| `long*` | Pointer to Value |
| 配列・構造体 | 事前確保した配列をArray Data Pointerで渡す |

---

# STEP 3：エラー変換を共通化

## 10B.3 `RAMScope_Code_To_Error.vi`

RAMScope APIの戻り値を標準error clusterへ変換する。

### フロントパネル

| 端子 | 方向 | 型 |
|------|------|----|
| `API ReturnCode` | 入力 | I32 |
| `Function Name` | 入力 | String |
| `error in` | 入力 | error cluster |
| `error out` | 出力 | error cluster |

### コネクタペイン

- 左上：`API ReturnCode`
- 左中：`Function Name`
- 左下：`error in`
- 右下：`error out`

### ブロックダイアグラム

1. `error in`を`Unbundle By Name`し、`status`を取得する。
2. `status`をCase Structureへ接続する。
3. `True`ケースでは元の`error in`をそのまま出力する。
4. `False`ケースでは`API ReturnCode == 0`を判定する。
5. `0`ならエラーなしのまま出力する。
6. `0以外`なら次のクラスタを作る。

```text
status = True
code   = API ReturnCode
source = "RAMScope <Function Name> failed. ReturnCode=0xXXXXXXXX (<decimal>)"
```

7. 16進表示は、I32をU32へ`Type Cast`してから`Format Into String`の`%08X`で整形する。
8. `Bundle By Name`で`status / code / source`を設定する。

### 単体テスト

| error in | ReturnCode | 期待結果 |
|----------|------------|----------|
| 正常 | `0` | error out正常 |
| 正常 | `0x30100001` | error out.status=True |
| エラーあり | 任意 | 元エラーを変更しない |

## 10B.4 `Error_To_TestStatus.vi`へ接続

```text
CLFN error out ───────────────┐
                               ▼
API ReturnCode ──→ RAMScope_Code_To_Error.vi
                               │
                               ▼
                    Error_To_TestStatus.vi
                       ├─ Status.ctl
                       ├─ TestError.ctl
                       └─ error out
```

`Error_To_TestStatus.vi`の機器名には固定文字列`RAMScope`を渡す。

---

# STEP 4：各VIを作成する

## 10B.5 `RAMScope_Connect.vi`

```c
long RAMScopeGT150DeviceInit(long *pUnitNum, long *kind);
```

### 既存VIの流用

10Aで作成済みのDeviceInit最小VIを`RAMScope_Connect.vi`として保存する。CLFN設定は変更しない。

### 入出力

| 端子 | 型 |
|------|----|
| `error in` | error cluster |
| `UnitNum` | I32 |
| `kind` | I32 |
| `API ReturnCode` | I32 |
| `実行結果ステータス` | `Status.ctl` |
| `エラー情報` | `TestError.ctl` |
| `error out` | error cluster |

### 追加作業

1. CLFNの`error out`とReturnCodeを`RAMScope_Code_To_Error.vi`へ接続する。
2. Function Nameに`RAMScopeGT150DeviceInit`を渡す。
3. 変換後のerror clusterを`Error_To_TestStatus.vi`へ接続する。
4. 機器名に`RAMScope`を渡す。
5. 共通出力をコネクタペインへ割り当てる。

実機接続時は`UnitNum >= 1`、`kind = 2`を期待するが、正式な成功値は実機結果で確定する。

---

## 10B.6 `RAMScope_Init.vi`

```c
long RAMScopeGT150AllInit(long UnitNo);
long RAMScopeGT150GetSysInfo(long UnitNo, SYSINFO *pSysInfo);
```

### 入出力

| 端子 | 型 | 説明 |
|------|----|------|
| `error in` | error cluster | 前段エラー |
| `MdlNo_RAM` | I32 | 未検出時`-1` |
| `MdlNo_CAN` | I32 | 未検出時`-1` |
| `Endian_RAM` | I32 | RAMモジュールのEndian |
| `SYSINFO Raw` | U8配列 | PoC用 |
| 共通3出力 | 共通型 | Status / TestError / error out |

### `AllInit`

1. CLFNを配置する。
2. Function Nameを`RAMScopeGT150AllInit`にする。
3. `UnitNo`をI32 / Valueで追加し、定数`0`を接続する。
4. 戻り値をI32にする。
5. ReturnCodeとCLFN error outを`RAMScope_Code_To_Error.vi`へ接続する。

### `GetSysInfo`

`SYSINFO`は60バイト、16要素で合計960バイト。

1. `Initialize Array`でU8の0を960要素確保する。
2. Function Nameを`RAMScopeGT150GetSysInfo`にする。
3. `UnitNo`：I32 / Value / `0`。
4. `pSysInfo`：Array / U8 / Array Data Pointer。
5. 戻り値：I32。
6. `AllInit`の変換後error clusterをCLFNへ接続する。
7. ReturnCodeを`RAMScope_Code_To_Error.vi`で変換する。

### SYSINFO解析

For Loopを16回実行し、60バイトずつ解析する。

| フィールド | オフセット | 型 |
|-----------|-----------|----|
| `module` | 0 | I32 |
| `module_type` | 4 | I32 |
| `probe_id` | 8 | I32 |
| `interface_id` | 12 | I32 |
| `version` | 16 | I32 |
| `addinfo` | 20 | I32 |
| `endian` | 24 | I32 |
| `probe_version` | 28 | I32 |
| `security_id_req` | 32 | I32 |
| `security_id_size` | 36 | I32 |
| `flash_enable` | 40 | I32 |
| `name[16]` | 44 | U8[16] |

1. `module_type == 0x00`なら`module`を`MdlNo_RAM`へ保存する。
2. 同じレコードの`endian`を`Endian_RAM`へ保存する。
3. `module_type == 0x02`なら`module`を`MdlNo_CAN`へ保存する。
4. 初期値を`-1`にする。
5. RAMモジュールが見つからなければ自前エラーを作る。
6. 最後に`Error_To_TestStatus.vi`を1回呼ぶ。

---

## 10B.7 `RAMScope_Config.vi`

```c
long RAMScopeGT150PGT_SetMdlConfig(long UnitNo, long *SlotErr);
```

### 入出力

| 端子 | 型 |
|------|----|
| `MdlNo_RAM` | I32 |
| `error in` | error cluster |
| `SlotErr` | I32[16] |
| 共通3出力 | 共通型 |

### 作成手順

1. I32の0を16要素`Initialize Array`する。
2. Function Nameを`RAMScopeGT150PGT_SetMdlConfig`にする。
3. `UnitNo`：I32 / Value / `0`。
4. `SlotErr`：Array / I32 / Array Data Pointer。
5. 戻り値：I32。
6. API ReturnCodeをエラー変換する。
7. API正常時に`SlotErr[MdlNo_RAM]`を取り出す。
8. SlotErrが0以外なら、同じ`RAMScope_Code_To_Error.vi`へ渡してエラー化する。
9. Function Nameは`RAMScopeGT150PGT_SetMdlConfig/SlotErr`等、判別できる文字列にする。
10. 最後に`Error_To_TestStatus.vi`を1回呼ぶ。

PGTツールの既存設定をAPIが読み込むため、`endian`や非公開プローブ情報をVI入力にしない。

---

## 10B.8 `RAMScope_Set_Cond.vi`

次の3関数を直列に呼ぶ。

```c
long RAMScopeGT170SetMeasCond(long UnitNo, long MdlNo, MEASINFO_170 *pMeasInfo);
long RAMScopeGT170SetMeasCh(long UnitNo, long MdlNo, long ChNum, CHINFO_170 *pChInfo);
long RAMScopeGT150SetLoggingInfo(long UnitNo, LOGINFO *pLogInfo);
```

### 推奨入力

| 端子 | 型 |
|------|----|
| `MdlNo_RAM` | I32 |
| `MeasPeri` | I32 |
| `MeasUnit` | Enum：usec=1 / msec=2 |
| `RAM Channel List` | `RAMScope_Channel.ctl`配列 |
| `LogSize` | I32。初期PoCは1 |
| `BufferSize` | I32。初期PoCは1 |
| `error in` | error cluster |

### `RAMScope_Channel.ctl`

| 要素 | 型 | 初期値 |
|------|----|--------|
| `Enable` | Boolean | True |
| `Core` | U32 | 0 |
| `Address` | U32 | 試験条件 |
| `Size` | U32 | API仕様に従う |
| `Signed` | Boolean | 対象変数に合わせる |
| `Speed` | U32 | 0 |

### MEASINFO_170

U8配列72要素をゼロ初期化し、I32値を4バイトにType Castして`Replace Array Subset`で埋める。

| 値 | オフセット |
|----|-----------|
| `DummyInterval=100` | 0 |
| `MeasPeri` | 4 |
| `MeasUnit` | 8 |
| `reserve[0]=0` | 12 |
| `reserve[1]=0` | 16 |

`pMeasInfo`へArray Data Pointerで渡し、ReturnCodeを変換する。エラーなら後続APIを呼ばない。

### CHINFO_170

RAM用1要素は24バイト。

| フィールド | オフセット | 型 |
|-----------|-----------|----|
| `enable` | 0 | U32 |
| `core` | 4 | U32 |
| `address` | 8 | U32 |
| `size` | 12 | U32 |
| `sign` | 16 | U32 |
| `speed` | 20 | U32 |

1. チャンネル数`N`を取得する。
2. `1 <= N <= 2048`を確認する。
3. U8配列を`N * 24`要素確保する。
4. For Loopで各クラスタを24バイトへ変換する。
5. BooleanはU32の0/1へ変換する。
6. `ChNum=N`を渡す。
7. `pChInfo`へArray Data Pointerで渡す。
8. ReturnCodeを変換する。

### LOGINFO

U8配列136要素をゼロ初期化する。

| フィールド | オフセット |
|-----------|-----------|
| `logDevice` | 0 |
| `limitHddSize` | 4 |
| `mdl[i].logSize` | `8 + i * 8` |
| `mdl[i].BuffSize` | `12 + i * 8` |

1. `logDevice=0`、`limitHddSize=0`を設定する。
2. 16スロットすべてにLogSizeとBufferSizeを設定する。
3. `pLogInfo`へArray Data Pointerで渡す。
4. ReturnCodeを変換する。
5. 最後に`Error_To_TestStatus.vi`を1回呼ぶ。

---

## 10B.9 `RAMScope_Log_Start.vi`

```c
long RAMScopeGT150MeasStart(long UnitNo);
```

1. `RAMScope_Connect.vi`を別名保存してテンプレートにする。
2. CLFNを`RAMScopeGT150MeasStart`へ変更する。
3. `UnitNo`：I32 / Value / `0`。
4. 戻り値：I32。
5. Function Nameも同じ関数名へ変更する。
6. ReturnCodeをエラー変換する。
7. 最後に`Error_To_TestStatus.vi`を呼ぶ。
8. VI内部に試験待ち時間を入れない。

`MeasStart`に`MdlNo`引数はない。

---

## 10B.10 `RAMScope_Read.vi`

```c
long RAMScopeGT150GetBufferData(
    long UnitNo,
    long MdlNo,
    void *pData,
    long *pDataNum,
    long *pLostDataNum
);
```

### 入出力

| 端子 | 型 |
|------|----|
| `MdlNo_RAM` | I32 |
| `Channel Count` | I32 |
| `Max Packets` | I32 |
| `error in` | error cluster |
| `Raw Bytes` | U8配列 |
| `DataNum` | I32 |
| `LostDataNum` | I32 |
| 共通3出力 | 共通型 |

### バッファ確保

```text
PacketSize = 4 * ChannelCount + 12
BufferBytes = PacketSize * MaxPackets
```

1. `Channel Count > 0`を確認する。
2. `Max Packets > 0`を確認する。
3. I64でBufferBytesを計算し、オーバーフローと過大値を確認する。
4. U8の0をBufferBytes要素確保する。
5. `pDataNum`の入力側へ`Max Packets`を設定する。
6. `pLostDataNum`の初期値を0にする。

### CLFN

| 引数 | 設定 |
|------|------|
| `UnitNo` | I32 / Value / `0` |
| `MdlNo` | I32 / Value / `MdlNo_RAM` |
| `pData` | Array / U8 / Array Data Pointer |
| `pDataNum` | I32 / Pointer to Value |
| `pLostDataNum` | I32 / Pointer to Value |
| 戻り値 | I32 |

正常時は`DataNum * PacketSize`へRaw Bytesを切り詰める。`LostDataNum > 0`はバッファ不足またはポーリング不足として記録する。

このVIではデータ解析を行わない。

---

## 10B.11 `RAMScope_Parse_Buffer.vi`

DLLを呼ばない純粋な変換VIとして作る。

### 入出力

| 端子 | 型 |
|------|----|
| `Raw Bytes` | U8配列 |
| `DataNum` | I32 |
| `Channel Count` | I32 |
| `Endian` | I32。0=Big / 1=Little |
| `error in` | error cluster |
| `Values` | I32 2次元配列 |
| `Flags` | U32配列 |
| `Timestamp Raw` | U64配列 |
| `Timestamp Sec` | DBL配列 |
| 共通3出力 | 共通型 |

### 解析

1. `PacketSize = 4 * N + 12`を計算する。
2. `ExpectedBytes = PacketSize * DataNum`を計算する。
3. Raw Bytesが不足していれば自前エラーにする。
4. For LoopをDataNum回実行する。
5. 各パケットからI32のチャンネル値をN個取得する。
6. `4 * N`位置からFlagをU32で取得する。
7. `4 * N + 4`位置からTimestampをU64で取得する。
8. `Timestamp Sec = Timestamp Raw * 20e-9`で変換する。
9. Big Endianの場合はType Cast前にバイト順を反転する。
10. 最後に`Error_To_TestStatus.vi`を呼ぶ。

### 単体テスト

- N=1、DataNum=1の既知パケット
- 複数チャンネル、複数パケット
- 入力不足
- Big / Little切替
- 既知Timestamp

---

## 10B.12 `RAMScope_Log_Stop.vi`

```c
long RAMScopeGT150MeasStop(long UnitNo);
```

1. `RAMScope_Log_Start.vi`を別名保存する。
2. Function Nameを`RAMScopeGT150MeasStop`へ変更する。
3. `UnitNo=0`を渡す。
4. エラー変換のFunction Nameも更新する。
5. ReturnCodeを変換する。
6. 最後に`Error_To_TestStatus.vi`を呼ぶ。

`MeasStop`にも`MdlNo`引数はない。

---

## 10B.13 `RAMScope_Release.vi`

```c
long RAMScopeGT150ReleaseBufferData(long UnitNo);
```

1. `RAMScope_Log_Stop.vi`を別名保存する。
2. Function Nameを`RAMScopeGT150ReleaseBufferData`へ変更する。
3. `UnitNo=0`を渡す。
4. ReturnCodeを変換する。
5. 最後に`Error_To_TestStatus.vi`を呼ぶ。

ベンダー簡易サンプルでは省略されている。VIは作成し、次を実機比較する。

```text
A: MeasStop → ReleaseBufferData → DeviceExit
B: MeasStop → DeviceExit
```

要否確定まではTestStandで有効・無効を切り替えられるようにする。

---

## 10B.14 `RAMScope_Close.vi`

```c
long RAMScopeGT150DeviceExit(void);
```

Cleanup専用のため、前段エラーがあっても実行する。

### 作成手順

1. Function Nameを`RAMScopeGT150DeviceExit`にする。
2. 引数は追加しない。
3. 戻り値をI32にする。
4. CLFNの`error in`へエラーなしクラスタを接続する。
5. CLFN error outとReturnCodeを`RAMScope_Code_To_Error.vi`へ接続する。
6. `Merge Errors`へ次の順で接続する。

```text
第1入力：元のerror in
第2入力：DeviceExitで発生したerror
```

7. Merge後のerror clusterを`Error_To_TestStatus.vi`へ渡す。

元エラーを消さず、終了処理も可能な範囲で実行する。

---

# STEP 5：LabVIEW単体Flow Test

## 10B.15 `RAMScope_Flow_Test.vi`

```text
RAMScope_Connect.vi
  → RAMScope_Init.vi
  → RAMScope_Config.vi
  → RAMScope_Set_Cond.vi
  → RAMScope_Log_Start.vi
  → Wait（Flow Test内だけ）
  → Loop:
       RAMScope_Read.vi
       RAMScope_Parse_Buffer.vi
  → RAMScope_Log_Stop.vi
  → RAMScope_Release.vi（要否検証）
  → RAMScope_Close.vi
```

### 実機未接続

- ConnectでAPIエラーになる。
- 後続の通常VIはCLFNを呼ばずエラーを伝播する。
- CloseだけはCleanupとして実行される。
- LabVIEWがクラッシュしない。

### 実機接続

- `UnitNum >= 1`
- `kind = 2`
- `MdlNo_RAM` / `MdlNo_CAN`が実構成と一致
- `SlotErr[MdlNo_RAM] = 0`
- 測定開始・読み出し・停止が通る
- `LostDataNum = 0`を維持できる
- 値とTimestampが純正RAMScope表示または既知信号と一致する
- Close後に再接続できる

---

# STEP 6：TestStandへ移行

## 10B.16 配置

| TestStand | VI |
|-----------|----|
| Setup | Connect / Init / Config / Set_Cond |
| Main | Log_Start / Read / Parse_Buffer / Log_Stop / Release候補 |
| Cleanup | 必要ならLog_Stop / Release候補 / Close |

具体的な変数、ポーリング、状態フラグ、レポートは [11](./11_TestStandシーケンス構築手順.md) に従う。

---

## 10B.17 完了チェック

### 共通

- [ ] `RAMScope_Code_To_Error.vi`の正常・異常・前段エラー試験が通る
- [ ] 全VIに共通3出力がある
- [ ] 通常VIは前段エラーでCLFNをスキップする
- [ ] Closeは前段エラーでも実行する

### 各VI

- [ ] Connect
- [ ] Init
- [ ] Config
- [ ] Set_Cond
- [ ] Log_Start
- [ ] Read
- [ ] Parse_Buffer
- [ ] Log_Stop
- [ ] Release
- [ ] Close
- [ ] Flow_Test

### 実機

- [ ] 連続試験
- [ ] 長時間ポーリング
- [ ] USB切断
- [ ] 異常中断からCleanup
- [ ] 再接続
- [ ] Releaseあり/なし比較
