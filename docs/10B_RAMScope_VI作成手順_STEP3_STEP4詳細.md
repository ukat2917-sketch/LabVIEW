# 10B. RAMScope VI作成手順：STEP 3 / STEP 4 詳細

本章は、[10A_RAMScope実装手順_DLL準備とCLFN疎通確認.md](./10A_RAMScope実装手順_DLL準備とCLFN疎通確認.md) の
「STEP 3：エラー変換を共通化」と「STEP 4：後続VIを1イベント1VIで作成」を、
LabVIEW上で実際に作業できる粒度まで分解した手順書である。

関数プロトタイプ・構造体・定数の正本は、次を参照する。

- [10_RAMScope実装方針.md](./10_RAMScope実装方針.md)
- [reference/RAMScopeVP.h](./reference/RAMScopeVP.h)
- [reference/GTHard.h](./reference/GTHard.h)

---

## 10B.1 最初に整理する名称

今回、最初に作成した `RAMScopeGT150DeviceInit()` を1個だけ呼ぶVIは、
役割上は **`RAMScope_Connect.vi`** とする。

```text
RAMScope_Connect.vi
  └─ RAMScopeGT150DeviceInit()

RAMScope_Init.vi
  ├─ RAMScopeGT150AllInit()
  └─ RAMScopeGT150GetSysInfo()
```

したがって、既に作成済みの最小VIはそのまま流用できるが、
保存名は `RAMScope_Connect.vi` とし、後段へ
`RAMScope_Code_To_Error.vi` と `Error_To_TestStatus.vi` を追加する。

> **結論**：既に作成したDeviceInitのVIは、CLFN設定をやり直す必要はない。
> エラー変換処理と共通出力を追加すれば `RAMScope_Connect.vi` として完成する。

---

## 10B.2 全RAMScope VIの共通構成

### 10B.2.1 共通入出力

通常の操作VIは、次の端子を共通で持たせる。

| 区分 | 端子 | 型 | 用途 |
|------|------|----|------|
| 入力 | `error in` | 標準error cluster | 前段エラーの受け取り |
| 出力 | `実行結果ステータス` | `Status.ctl` | TestStandの継続・中断判定 |
| 出力 | `エラー情報` | `TestError.ctl` | 機器名・コード・メッセージ等の記録 |
| 出力 | `error out` | 標準error cluster | 後段VIとTestStandへの伝播 |
| デバッグ出力 | `API ReturnCode` | I32 | PoC中のAPI戻り値確認。量産後は任意 |

API固有の入力・出力は、上記へ追加する。

### 10B.2.2 通常VIのブロック構成

`RAMScope_Close.vi` 以外は、前段にエラーがあればAPIを呼び出さない。

```text
error in
   │
   ▼
Case Structure（error in.status）
   ├─ True : CLFNを実行せず、error inをそのまま出力
   └─ False: CLFN実行
                  │
                  ├─ CLFN error out
                  └─ API ReturnCode
                         │
                         ▼
              RAMScope_Code_To_Error.vi
                         │
                         ▼
              Error_To_TestStatus.vi
                 ├─ Status.ctl
                 ├─ TestError.ctl
                 └─ error out
```

### 10B.2.3 CLFN共通設定

| 項目 | 共通設定 |
|------|----------|
| DLL | `RAMScopeVP_API_x64.dll` |
| Calling convention | `C` |
| Thread | 最初は `Run in UI thread` |
| Error checking | PoC中は `Maximum` |
| Cの`long` | LabVIEWではI32 |
| Cの`unsigned long` / `DWORD` | LabVIEWではU32 |
| `long*` | I32 / Pointer to Value |
| 構造体・配列ポインタ | 事前確保した配列 / Array Data Pointer |

---

# STEP 3：エラー変換を共通化

## 10B.3 `RAMScope_Code_To_Error.vi` の作成

RAMScope APIは標準error clusterではなく、関数の戻り値としてI32の結果コードを返す。
このVIは、その生コードを標準error clusterへ変換する専用アダプタである。

### 10B.3.1 フロントパネル

| 端子 | 種別 | 型 | 説明 |
|------|------|----|------|
| `API ReturnCode` | 入力 | I32 | CLFNの戻り値 |
| `Function Name` | 入力 | String | 例：`RAMScopeGT150DeviceInit` |
| `error in` | 入力 | error cluster | CLFN自身のerror out、または前段エラー |
| `error out` | 出力 | error cluster | APIコードを反映した標準エラー |

コネクタペインは、左側に3入力、右側に`error out`を配置する。

### 10B.3.2 ブロックダイアグラム

1. `error in` を `Unbundle By Name` し、`status` を取得する。
2. `status` をCase Structureへ接続する。
3. `True`ケースでは、既存エラーを優先して `error in` をそのまま `error out` へ渡す。
4. `False`ケースでは、`API ReturnCode == 0` を比較する。
5. 戻り値が`0`の場合は、`error in`をそのまま出力する。
6. 戻り値が`0以外`の場合は、次のerror clusterを作る。

```text
status = True
code   = API ReturnCode
source = "RAMScope <Function Name> failed. ReturnCode=0xXXXXXXXX (decimal)"
```

7. 16進表示は `Format Into String` の `%08X` を使う。
8. I32コードを16進表示するときは、ビット列を保持するためU32へ `Type Cast` してから整形する。
9. `Bundle By Name` で `status / code / source` を設定し、`error out`へ出力する。

### 10B.3.3 動作確認

| 入力 | 期待結果 |
|------|----------|
| `error in.status=False`, ReturnCode=`0` | `error out.status=False` |
| `error in.status=False`, ReturnCode=`0x30100001` | `error out.status=True`、codeに同値 |
| `error in.status=True` | 元のエラーを変更せずそのまま出力 |

> 標準error clusterの`code`はI32である。
> `TestError.ctl`でコードをU32保持する場合は、負数表示になり得るコードを数値変換せず、
> `Type Cast`でビット列を保持して格納する。

---

## 10B.4 各VIでのエラー変換接続

各RAMScope VIでは、CLFNの直後を次の順で接続する。

```text
CLFN error out ───────────────┐
                              ▼
CLFN API ReturnCode ──▶ RAMScope_Code_To_Error.vi
                              │
                              ▼
                   Error_To_TestStatus.vi
                       ├─ 実行結果ステータス
                       ├─ エラー情報
                       └─ error out
```

`Error_To_TestStatus.vi` の `機器名` 入力には、固定文字列 `RAMScope` を渡す。

複数のCLFNを持つVIでは、APIごとに `RAMScope_Code_To_Error.vi` を挟み、
標準error clusterを次のAPIへ直列で渡す。`Error_To_TestStatus.vi` はVIの最後に1回だけ呼ぶ。

---

# STEP 4：後続VIを1イベント1VIで作成

## 10B.5 `RAMScope_Connect.vi`

### 10B.5.1 既存VIの流用

今回作成済みの `RAMScopeGT150DeviceInit()` 最小VIを「別名で保存」し、
`RAMScope_Connect.vi` とする。

```c
long RAMScopeGT150DeviceInit(long *pUnitNum, long *kind);
```

### 10B.5.2 入出力

| 端子 | 型 | 説明 |
|------|----|------|
| `error in` | error cluster | 前段エラー |
| `UnitNum` | I32 | 接続台数 |
| `kind` | I32 | `0=GT150 / 1=GT12x / 2=GT17x` |
| `API ReturnCode` | I32 | DeviceInit戻り値 |
| `実行結果ステータス` | `Status.ctl` | 共通出力 |
| `エラー情報` | `TestError.ctl` | 共通出力 |
| `error out` | error cluster | 共通出力 |

### 10B.5.3 追加作業

1. 既存のCLFN配線を維持する。
2. CLFNの標準`error out`と`API ReturnCode`を `RAMScope_Code_To_Error.vi` へ接続する。
3. `Function Name`には `RAMScopeGT150DeviceInit` を設定する。
4. 変換後のerror clusterを `Error_To_TestStatus.vi` へ接続する。
5. `機器名`には `RAMScope` を設定する。
6. `Status.ctl / TestError.ctl / error out`をコネクタペインへ割り当てる。

> つまり、既に作成したVIについては、主な追加作業はエラー変換チェーンの接続である。

実機接続後は、成功時に `UnitNum >= 1` かつ `kind = 2` であることを確認する。
正式な成功コードはAPI仕様書・実機結果で確定する。

---

## 10B.6 `RAMScope_Init.vi`

`RAMScope_Init.vi` は `DeviceInit` ではなく、次の2関数を順番に呼ぶ。

```c
long RAMScopeGT150AllInit(long UnitNo);
long RAMScopeGT150GetSysInfo(long UnitNo, SYSINFO *pSysInfo);
```

### 10B.6.1 入出力

| 端子 | 型 | 説明 |
|------|----|------|
| `error in` | error cluster | 前段エラー |
| `MdlNo_RAM` | I32 | RAMモニタモジュール番号。未検出時は`-1` |
| `MdlNo_CAN` | I32 | CANモジュール番号。未検出時は`-1` |
| `Endian_RAM` | I32 | RAMモジュールのエンディアン情報 |
| `SYSINFO Raw` | U8配列 | PoC用。必要に応じて非公開出力にする |
| `実行結果ステータス` | `Status.ctl` | 共通出力 |
| `エラー情報` | `TestError.ctl` | 共通出力 |
| `error out` | error cluster | 共通出力 |

### 10B.6.2 `AllInit` の作成

1. CLFNを配置し、関数名を `RAMScopeGT150AllInit` にする。
2. `UnitNo`をI32 / Valueで追加し、定数`0`を接続する。
3. 戻り値をI32に設定する。
4. 戻り値を `RAMScope_Code_To_Error.vi` へ接続する。
5. `Function Name`には `RAMScopeGT150AllInit` を設定する。
6. 変換後のerror clusterが正常な場合だけ、次の`GetSysInfo`を実行する。

### 10B.6.3 `GetSysInfo` のCLFN設定

`SYSINFO`は60バイト、配列要素数は16である。

```text
60 byte × 16 = 960 byte
```

1. `Initialize Array`でU8の`0`を960要素確保する。
2. CLFNの関数名を `RAMScopeGT150GetSysInfo` にする。
3. `UnitNo`：I32 / Value / `0`。
4. `pSysInfo`：Array / U8 / Array Data Pointer。
5. 戻り値：I32。
6. API戻り値を `RAMScope_Code_To_Error.vi` へ接続する。
7. `Function Name`には `RAMScopeGT150GetSysInfo` を設定する。

### 10B.6.4 SYSINFOの解析

For Loopを16回実行し、各ループで60バイトを切り出す。

```text
開始位置 = ループ番号 × 60
長さ     = 60
```

各レコードの主要オフセット：

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

1. 各4バイトを `Array Subset` で切り出す。
2. `Type Cast`でI32へ変換する。
3. `module_type == 0x00` のレコードを探し、`module`を `MdlNo_RAM` とする。
4. 同じレコードの`endian`を `Endian_RAM` とする。
5. `module_type == 0x02` のレコードを探し、`module`を `MdlNo_CAN` とする。
6. 初期値は`-1`にする。
7. `MdlNo_RAM == -1`のままなら「RAMモニタモジュール未検出」として自前エラーを生成する。

最後に1回だけ `Error_To_TestStatus.vi` を呼ぶ。

---

## 10B.7 `RAMScope_Config.vi`

```c
long RAMScopeGT150PGT_SetMdlConfig(long UnitNo, long *SlotErr);
```

### 10B.7.1 入出力

| 端子 | 型 | 説明 |
|------|----|------|
| `MdlNo_RAM` | I32 | `RAMScope_Init.vi`の出力 |
| `error in` | error cluster | 前段エラー |
| `SlotErr` | I32[16] | PoC・ログ用 |
| 共通3出力 | 各共通型 | Status / TestError / error out |

### 10B.7.2 作成手順

1. `Initialize Array`でI32の`0`を16要素確保する。
2. CLFNの関数名を `RAMScopeGT150PGT_SetMdlConfig` にする。
3. `UnitNo`：I32 / Value / `0`。
4. `SlotErr`：Array / I32 / Array Data Pointer。
5. 戻り値：I32。
6. API戻り値を `RAMScope_Code_To_Error.vi` へ接続する。
7. API戻り値が正常なら、`Index Array`で `SlotErr[MdlNo_RAM]` を取り出す。
8. `SlotErr[MdlNo_RAM] != 0` の場合も、`RAMScope_Code_To_Error.vi` でエラー化する。
9. Function Nameは `RAMScopeGT150PGT_SetMdlConfig/SlotErr` とする。
10. 最後に `Error_To_TestStatus.vi` を呼ぶ。

> `PGTMgrVP.dll`等が使用する既存のPGT設定を暗黙に読み込むため、
> `endian`やプローブ固有設定をこのVIの引数として渡す必要はない。

---

## 10B.8 `RAMScope_Set_Cond.vi`

このVIは、1つの「測定条件設定イベント」として、次の3関数を直列に呼ぶ。

```c
long RAMScopeGT170SetMeasCond(long UnitNo, long MdlNo, MEASINFO_170 *pMeasInfo);
long RAMScopeGT170SetMeasCh(long UnitNo, long MdlNo, long ChNum, CHINFO_170 *pChInfo);
long RAMScopeGT150SetLoggingInfo(long UnitNo, LOGINFO *pLogInfo);
```

### 10B.8.1 推奨入力

| 端子 | 型 | 説明 |
|------|----|------|
| `MdlNo_RAM` | I32 | RAMモジュール番号 |
| `MeasPeri` | I32 | 測定周期の数値部分 |
| `MeasUnit` | Enum | `usec=1 / msec=2` |
| `RAM Channel List` | 型定義クラスタ配列 | 各チャンネルのaddress等 |
| `LogSize` | I32 | 初期値`1` |
| `BufferSize` | I32 | 初期値`1` |
| `error in` | error cluster | 前段エラー |

推奨するチャンネル型定義 `RAMScope_Channel.ctl`：

| 要素 | 型 | 初期値 |
|------|----|--------|
| `Enable` | Boolean | True |
| `Core` | U32 | 0 |
| `Address` | U32 | 試験条件 |
| `Size` | U32 | API仕様に従う |
| `Signed` | Boolean | 対象変数に合わせる |
| `Speed` | U32 | 0 |

### 10B.8.2 MEASINFO_170の作成

1. `Initialize Array`でU8の`0`を72要素確保する。
2. I32値を4バイトのU8配列へ `Type Cast` し、`Replace Array Subset`で埋める。

| 値 | オフセット | 設定 |
|----|-----------|------|
| `DummyInterval` | 0 | `100` |
| `MeasPeri` | 4 | 入力値 |
| `MeasUnit` | 8 | Enum値`1`または`2` |
| `MeasPeri_reserve[0]` | 12 | `0` |
| `MeasPeri_reserve[1]` | 16 | `0` |

3. CLFNの`pMeasInfo`へU8[72]をArray Data Pointerで渡す。
4. API戻り値をエラー変換する。
5. エラーがあれば以降の2関数を実行しない。

### 10B.8.3 CHINFO_170配列の作成

RAM用 `CHINFO_170` は1要素24バイトである。

```text
CHINFO_RAM170 = DWORD × 6 = 24 byte
```

チャンネル数を`N`とする。

1. `Array Size`で`N`を取得する。
2. `N < 1`または`N > 2048`の場合は自前エラーにする。
3. U8配列を `N × 24` 要素で確保する。
4. For Loopで各チャンネルを24バイトへ変換する。

| フィールド | オフセット | 型 |
|-----------|-----------|----|
| `enable` | 0 | U32 |
| `core` | 4 | U32 |
| `address` | 8 | U32 |
| `size` | 12 | U32 |
| `sign` | 16 | U32 |
| `speed` | 20 | U32 |

5. `Enable=True`をU32の`1`、Falseを`0`へ変換する。
6. `Signed=True`をU32の`1`、Falseを`0`へ変換する。
7. CLFNの`ChNum`には`N`を渡す。
8. `pChInfo`にはU8配列をArray Data Pointerで渡す。
9. API戻り値をエラー変換する。

### 10B.8.4 LOGINFOの作成

`LOGINFO`は136バイトである。

```text
long × 2 + (long × 2) × 16 = 136 byte
```

1. U8配列を136要素でゼロ初期化する。
2. 次を埋める。

| フィールド | オフセット |
|-----------|-----------|
| `logDevice` | 0 |
| `limitHddSize` | 4 |
| `mdl[0].logSize` | 8 |
| `mdl[0].BuffSize` | 12 |
| `mdl[i].logSize` | `8 + i × 8` |
| `mdl[i].BuffSize` | `12 + i × 8` |

3. `logDevice=0`、`limitHddSize=0`を設定する。
4. 16スロットすべてに、最初は`LogSize=1`、`BufferSize=1`を設定する。
5. CLFNの`pLogInfo`へArray Data Pointerで渡す。
6. API戻り値をエラー変換する。
7. 最後に `Error_To_TestStatus.vi` を1回呼ぶ。

---

## 10B.9 `RAMScope_Log_Start.vi`

```c
long RAMScopeGT150MeasStart(long UnitNo);
```

### 作成手順

1. `RAMScope_Connect.vi`をテンプレートとして「別名で保存」する。
2. DeviceInitのCLFNを削除し、`RAMScopeGT150MeasStart`へ置換する。
3. `UnitNo`：I32 / Value / 固定値`0`。
4. 戻り値：I32。
5. Function Nameを `RAMScopeGT150MeasStart`としてエラー変換する。
6. 最後に `Error_To_TestStatus.vi` を呼ぶ。
7. VI内部に待ち時間を入れない。

> `MeasStart`には`MdlNo`引数はない。入力は`UnitNo=0`のみである。

---

## 10B.10 `RAMScope_Read.vi`

```c
long RAMScopeGT150GetBufferData(
    long UnitNo,
    long MdlNo,
    void *pData,
    long *pDataNum,
    long *pLostDataNum);
```

### 10B.10.1 入出力

| 端子 | 型 | 説明 |
|------|----|------|
| `MdlNo_RAM` | I32 | RAMモジュール番号 |
| `Channel Count` | I32 | 設定済みチャンネル数`N` |
| `Max Packets` | I32 | 1回で受け取る最大パケット数 |
| `error in` | error cluster | 前段エラー |
| `Raw Bytes` | U8配列 | 取得した生データ |
| `DataNum` | I32 | 実際の取得パケット数 |
| `LostDataNum` | I32 | 取りこぼし数 |
| 共通3出力 | 各共通型 | Status / TestError / error out |

### 10B.10.2 バッファ確保

RAMパケット1個のサイズ：

```text
PacketSize = 4 × ChannelCount + 12
```

1. `Channel Count > 0`を確認する。
2. `Max Packets > 0`を確認する。
3. I64で `PacketSize × Max Packets` を計算し、過大値やオーバーフローをチェックする。
4. `Initialize Array`でU8の`0`を必要バイト数だけ確保する。
5. `pDataNum`へは、呼び出し前に`Max Packets`を書き込む。
6. `pLostDataNum`の初期値は`0`にする。

### 10B.10.3 CLFN設定

| 引数 | 設定 |
|------|------|
| `UnitNo` | I32 / Value / `0` |
| `MdlNo` | I32 / Value / `MdlNo_RAM` |
| `pData` | Array / U8 / Array Data Pointer |
| `pDataNum` | I32 / Pointer to Value |
| `pLostDataNum` | I32 / Pointer to Value |
| 戻り値 | I32 |

1. API戻り値をエラー変換する。
2. 正常時は、`DataNum × PacketSize`の長さへRaw Bytesを切り詰めて出力する。
3. `LostDataNum > 0`はバッファ不足・ポーリング周期不足の兆候としてログへ残す。
4. このVIでは解析しない。解析は `RAMScope_Parse_Buffer.vi`へ分離する。

---

## 10B.11 `RAMScope_Parse_Buffer.vi`

このVIはDLLを呼ばない純粋なデータ変換VIである。
実機なしでもダミーデータで単体試験できる。

### 10B.11.1 入出力

| 端子 | 型 | 説明 |
|------|----|------|
| `Raw Bytes` | U8配列 | `RAMScope_Read.vi`の出力 |
| `DataNum` | I32 | パケット数 |
| `Channel Count` | I32 | チャンネル数`N` |
| `Endian` | I32 | `0=Big / 1=Little` |
| `error in` | error cluster | 前段エラー |
| `Values` | I32 2次元配列 | `[packet][channel]` |
| `Flags` | U32配列 | 各パケットのフラグ |
| `Timestamp Raw` | U64配列 | 20ns単位の生値 |
| `Timestamp Sec` | DBL配列 | 秒換算値 |
| 共通3出力 | 各共通型 | Status / TestError / error out |

### 10B.11.2 解析手順

1. `PacketSize = 4 × N + 12`を計算する。
2. `ExpectedBytes = PacketSize × DataNum`を計算する。
3. `Array Size(Raw Bytes) >= ExpectedBytes`を確認する。
4. 不足していれば自前エラーを生成する。
5. For Loopを`DataNum`回実行する。
6. 各パケットの開始位置を `packet index × PacketSize` とする。
7. チャンネル値を4バイトずつ、N個読み出してI32へ変換する。
8. Flagは `開始位置 + 4 × N` から4バイト読み出し、U32へ変換する。
9. Timestampは `開始位置 + 4 × N + 4` から8バイト読み出し、U64へ変換する。
10. `Timestamp Sec = Timestamp Raw × 20e-9`で秒へ変換する。
11. `Endian=0`の場合は、各数値をType Castする前にバイト順を反転する。
12. 最後に `Error_To_TestStatus.vi` を呼ぶ。

### 10B.11.3 単体テスト

最低限、次のダミーパケットを用意する。

- `Channel Count=1`、`DataNum=1`
- Channel値が既知のI32
- Flagが既知のU32
- Timestampが既知のU64
- 入力配列不足時にエラーになること
- Big/Little切替時に期待値が一致すること

---

## 10B.12 `RAMScope_Log_Stop.vi`

```c
long RAMScopeGT150MeasStop(long UnitNo);
```

### 作成手順

1. `RAMScope_Log_Start.vi`を「別名で保存」する。
2. 関数名を `RAMScopeGT150MeasStop`へ変更する。
3. `UnitNo=0`を渡す。
4. Function Nameも `RAMScopeGT150MeasStop`へ変更する。
5. API戻り値をエラー変換する。
6. 最後に `Error_To_TestStatus.vi` を呼ぶ。

> `MeasStop`にも`MdlNo`引数はない。

---

## 10B.13 `RAMScope_Release.vi`

```c
long RAMScopeGT150ReleaseBufferData(long UnitNo);
```

### 作成手順

1. `RAMScope_Log_Stop.vi`を「別名で保存」する。
2. 関数名を `RAMScopeGT150ReleaseBufferData`へ変更する。
3. `UnitNo=0`を渡す。
4. Function Nameを同じ関数名へ変更する。
5. API戻り値をエラー変換する。
6. 最後に `Error_To_TestStatus.vi` を呼ぶ。

ベンダー簡易サンプルでは省略されているため、次を実機で比較して要否を確定する。

```text
A: MeasStop → ReleaseBufferData → DeviceExit
B: MeasStop → DeviceExit
```

確定するまではVIを作成し、TestStand側で有効・無効を切り替えられるようにする。

---

## 10B.14 `RAMScope_Close.vi`

```c
long RAMScopeGT150DeviceExit(void);
```

`RAMScope_Close.vi` はCleanupで使用するため、前段にエラーがあっても必ず呼び出す。
通常VIの「error inがTrueならスキップ」パターンを使わない。

### 10B.14.1 入出力

| 端子 | 型 | 説明 |
|------|----|------|
| `error in` | error cluster | 試験中に発生した元エラー |
| 共通3出力 | 各共通型 | Status / TestError / error out |
| `DeviceExit ReturnCode` | I32 | PoC用 |

### 10B.14.2 作成手順

1. CLFNの関数名を `RAMScopeGT150DeviceExit` にする。
2. 引数は追加しない。
3. 戻り値をI32にする。
4. CLFNの`error in`には、元の`error in`ではなく「エラーなし」のクラスタ定数を接続する。
   これにより、前段エラーがあってもDeviceExitを実行する。
5. CLFN error outとAPI戻り値を `RAMScope_Code_To_Error.vi`へ接続する。
6. `Merge Errors`を使用し、入力順を次にする。

```text
第1入力：元の error in
第2入力：DeviceExitで発生したエラー
```

7. 元エラーが存在する場合は元エラーを優先して保持する。
8. 元エラーがなく、DeviceExitだけ失敗した場合はDeviceExitエラーを出力する。
9. Merge後のerror clusterを `Error_To_TestStatus.vi`へ渡す。

> Cleanup処理では「元エラーを消さない」「終了処理も可能な限り実行する」の両方を満たす。

---

## 10B.15 `RAMScope_Flow_Test.vi`

TestStandへ入れる前に、LabVIEW単体で次を直列実行する。

```text
RAMScope_Connect.vi
  → RAMScope_Init.vi
  → RAMScope_Config.vi
  → RAMScope_Set_Cond.vi
  → RAMScope_Log_Start.vi
  → Wait（フロー試験VIのみ）
  → RAMScope_Read.vi（必要回数ループ）
  → RAMScope_Parse_Buffer.vi
  → RAMScope_Log_Stop.vi
  → RAMScope_Release.vi（要否検証中）
  → RAMScope_Close.vi
```

### 実機未接続時

- `RAMScope_Connect.vi`でAPIエラーになること
- 後続の通常VIはCLFNを実行せず、同じエラーを伝播すること
- `RAMScope_Close.vi`だけはCleanupとして実行されること
- LabVIEWがクラッシュしないこと

### 実機接続時

- `UnitNum >= 1`
- `kind = 2`
- `MdlNo_RAM`が実機構成と一致
- `MdlNo_CAN`が実機構成と一致
- `SlotErr[MdlNo_RAM] = 0`
- `LostDataNum = 0`を維持できること
- 測定値・Timestampが純正RAMScope表示と一致すること

---

## 10B.16 TestStandへの配置

| TestStand区分 | VI | 備考 |
|--------------|----|------|
| Setup | `RAMScope_Connect.vi` | 接続・機種確認 |
| Setup | `RAMScope_Init.vi` | 初期化・モジュール番号取得 |
| Setup | `RAMScope_Config.vi` | PGT設定適用 |
| Setup | `RAMScope_Set_Cond.vi` | 試験条件を入力 |
| Main | `RAMScope_Log_Start.vi` | 計測開始 |
| Main | `RAMScope_Read.vi` | ポーリング |
| Main | `RAMScope_Parse_Buffer.vi` | 取得値変換・判定 |
| Main | `RAMScope_Log_Stop.vi` | 計測停止 |
| Main/Cleanup前 | `RAMScope_Release.vi` | 要否確定後に配置 |
| Cleanup | `RAMScope_Close.vi` | 前段エラーに関係なく実行 |

TestStand側で管理するもの：

- Wait時間
- Readのポーリング周期
- タイムアウト
- リトライ回数
- 測定周期・チャンネル一覧
- Setup失敗時のCleanup遷移

---

## 10B.17 作成順序チェックリスト

### STEP 3

- [ ] `RAMScope_Code_To_Error.vi`を作成
- [ ] ReturnCode=`0`の正常テスト
- [ ] ReturnCode=`0x30100001`の異常テスト
- [ ] 前段エラー優先テスト
- [ ] `Error_To_TestStatus.vi`へ接続

### STEP 4

- [ ] 既存DeviceInit VIを `RAMScope_Connect.vi`として保存
- [ ] `RAMScope_Connect.vi`へエラー変換を追加
- [ ] `RAMScope_Init.vi`を作成
- [ ] `RAMScope_Config.vi`を作成
- [ ] `RAMScope_Set_Cond.vi`を作成
- [ ] `RAMScope_Log_Start.vi`を作成
- [ ] `RAMScope_Read.vi`を作成
- [ ] `RAMScope_Parse_Buffer.vi`を作成・単体試験
- [ ] `RAMScope_Log_Stop.vi`を作成
- [ ] `RAMScope_Release.vi`を作成
- [ ] `RAMScope_Close.vi`をCleanup専用構成で作成
- [ ] `RAMScope_Flow_Test.vi`で通し確認
