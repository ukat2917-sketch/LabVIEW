# 02. 機器Adapter / API要求

**最終整理日:** 2026-09-03  
**State:** Draft. Native API名は一次資料で確認済みのものだけ確定扱いとする。

---

## 1. 共通Adapter契約

外注・内製を問わず、TestStandへベンダー固有APIを直接公開しない。LabVIEW公開APIは最低限次を提供する。

| Category | Common API | Requirement |
|---|---|---|
| Lifecycle | `Initialize / Connect` | 接続、Version取得、Session生成 |
| Lifecycle | `Close` | Resource解放。複数回呼び出しても安全であること |
| Configuration | `Configure` | 試験条件を機器設定へ変換 |
| Runtime | `Arm` | Trigger/Recorder/DAQ開始準備 |
| Runtime | `Start` | Output / Measurement / Monitor開始 |
| Runtime | `Stop` | 正常停止 |
| Runtime | `GetStatus` | 実状態・Fault取得。Cached状態だけを真実源にしない |
| Data | `ReadSelectedValues` | TestStand判定に必要な小数信号取得 |
| Sync | `InsertMarker` | Event IDを機器Dataへ残す。非対応時はHost Event Timelineへ記録 |
| Safety | `GoSafe` | Output Off、安全Setpoint、停止処理 |
| Trace | `GetVersionSnapshot` | Driver/Firmware/Config/Project等のVersion記録 |

Recorder対応機器は`ConfigureRecording / StartRecording / StopRecording / GetRecordingArtifact`を追加する。

Calibration対応機器は`ReadCalibration / WriteCalibration / VerifyCalibration`を追加する。

---

# 2. Chroma

## 2.1 対象

- `62180D-600D` ×2
- `63206A-150-600`
- `63804` ×2
- `61830`または`61845`

モデル毎に公式LabVIEW/IVI DriverまたはRemote Programming Manualを確認し、使える公式Driverがある場合はそれをWrapperする。公式Driverで不足する機能だけVISA/SCPIへ降りる。

## 2.2 必須機能

| Requirement | Priority | Notes |
|---|---:|---|
| Open/Close Session | 必須 | VISA/IVI resourceをAdapter内部へ隠蔽 |
| Reset/Clear/Status Clear | 必須 | 初期状態固定 |
| Operation Mode設定 | 必須 | Source/Load、AC/DC、CC/CV/CP等はモデル依存 |
| Voltage/Current/Power/Frequency Setpoint | 必須 | 対象機種に応じて有効化 |
| Ramp/Slew設定 | 必須 | 最大負荷遷移時の安全性確保 |
| Output/Load ON/OFF | 必須 | Cleanupで必ずOFF可能 |
| Measured V/I/P Readback | 必須 | Commanded valueだけで判定しない |
| Protection/Fault取得 | 必須 | OVP/OCP/OPP/OTP等 |
| Fault Clear | 必須 | 再試験前の復旧 |
| Trigger/Sequence | 要確認 | Hardware同期・Transient機能をモデル別確認 |
| Parallel / Multi-unit制御 | 要確認 | 62180D ×2の最大負荷運転条件確認 |
| Get Model/Firmware/Driver Version | 必須 | Run Manifestへ保存 |

## 2.3 外注前に入手する正本

- 各型式のLabVIEW/IVI Driver一式
- Remote Programming / SCPI Manual
- Parallel operation / master-slave仕様
- Trigger仕様

---

# 3. Yokogawa WT5000

WT5000は電力計測の主要Source of Truthとする。

## 必須機能

```text
Connect / Close
Configure Wiring
Configure Element / Range
Configure Update Rate
Configure Harmonic (必要時)
Configure Trigger (使用可能なら)
Start / Stop Acquisition
Read Numeric Values
Read Harmonic Values
Read Waveform (使用する場合)
Read Status / Error
Get Model / Firmware / Driver Version
```

最低でも電圧、電流、有効電力、周波数、必要な効率計算用値を取得できること。

**未確定:** LabVIEW公式Driverの実VI名・Connector Pane、WT5000 timestamp/triggerの実仕様。対象PCへ入れるDriver一式とCommunication Interface Manualを確認して確定する。

---

# 4. Yokogawa SMARTDAC+ GM10 / GX20 と MX100 Legacy

温度DAQの詳細正本は[`06_温度DAQ_SMARTDAC+_GX_GM_MX100比較と仕様.md`](./06_温度DAQ_SMARTDAC+_GX_GM_MX100比較と仕様.md)とする。

## 4.1 採用候補

- **第一候補:** SMARTDAC+ `GM10 + GX90XA`
- **Alternative:** `GX20 + GX90XA`。Local displayが必要な場合
- **Legacy:** MX100。既設流用時のみ優先度を上げる

MX100は2019-03-31販売終了で、メーカー推奨代替はSMARTDAC+ GM。新規設備の標準温度DAQとしてはSMARTDAC+を優先する。

IS8000統合では`/MB1` Modbus/TCPを第一候補とし、GM10はYokogawaがIS8000用通信設定ファイルを提供するため統合リスクが低い。

## 4.2 入手済みLabVIEW Driver

`yokogawa_gx_series.zip`から次を確認済み。

```text
Driver: Yokogawa GX/GP/GM Series LabVIEW Plug and Play
Revision: 4.2.1
Supported: GX10 / GP10 / GX20 / GP20 / GM10
Tested: GM10 / GX20
Interfaces: LAN / RS-232C / RS-422A / USB / Bluetooth
VISA: 5.0 or later
Source code: Available
Certified: No
NI Supported: No
```

LabVIEW 2016時代のDriverであるため、LabVIEW 2026 Q3 64bitでMass Compile/Connector Pane/ExampleをPoCする。

## 4.3 Native Driverで確認済みの主要VI

```text
Initialize.vi
Close.vi
Revision Query.vi

Configure Channel (TC Normal).vi
Configure Channel (RTD Normal).vi
Configure Burnout RJC.vi
Configure AI Filter.vi
Configure AI Moving Average.vi
Configure Interval.vi
Configure Scan Group.vi
Configure Master Scan Interval Group.vi

Configure Data Save.vi
Configure Memory.vi
Configure Record Data (Display).vi
Configure Record Data (Event).vi

Data/Low Level/Initiate.vi
Data/Low Level/Abort.vi
Read Measurement Data (Analog NChan).vi
Read Measurement Data (Unit NChan).vi

Write Display Message.vi
Get Internal Dir.vi
```

Native Connector Pane/型は対象LabVIEWでDriver Helpを開いて確定する。

## 4.4 Project Public API

```text
SMARTDAC_Connect.vi
SMARTDAC_Get_Version.vi
SMARTDAC_Configure_Temperature_Channels.vi
SMARTDAC_Configure_Scan.vi
SMARTDAC_Configure_Burnout_RJC.vi
SMARTDAC_Configure_Recording.vi
SMARTDAC_Start.vi
SMARTDAC_Read_Selected_Values.vi
SMARTDAC_Write_Event_Marker.vi
SMARTDAC_Get_Status.vi
SMARTDAC_Stop.vi
SMARTDAC_Get_Recording_Artifact.vi
SMARTDAC_Close.vi
```

Public API名はGM10/GX20共通とし、TestStandがHardware model差を直接扱わない。

## 4.5 初期Module候補

一般温度用途:

```text
GX90XA-10-U2
10ch Universal Input
TC / RTD / DCV / DI
Shortest scan: 100 ms
```

Noise耐性優先では`GX90XA-10-T1`、高速特殊用途では`GX90XA-04-H0`を比較する。

## 4.6 Ownership

第一候補:

```text
Setup:
LabVIEW GX/GM Driver → Configure / Verify → Session Close

Runtime:
IS8000 /MB1 → GM10 Modbus/TCP → Temperature acquisition

Cleanup/Artifact:
IS8000 Stop → 必要ならLabVIEW再接続 → Native artifact確認
```

LabVIEW DriverとIS8000が同一GM10へ常時同時アクセスする構成は、競合/負荷PoC前に標準としない。

## 4.7 必須機能

```text
Connect / Close
Get Model / Firmware / Driver Revision
Get Module / Channel Inventory
Configure TC / RTD / DCV Channel
Configure Range / Scaling / Unit / Tag
Configure Burnout / RJC
Configure Scan Interval
Configure Native Recording
Start / Stop
Read N Channel Values + Data Status
Write Event Marker (Native recording使用時)
Get Recording Artifact
Get Status / Error
```

SMARTDAC+ Modbus acquisitionの精密同期は別途PoCし、DL950/SL2000等の高精度同期と同一Classとして扱わない。

---

# 4A. Yokogawa DLM5000

## 4A.1 採用機種

**本Projectのオシロスコープは`Yokogawa DLM5000`シリーズで一旦Fixする。**

- 他シリーズを前提としたAdapterは設計しない。
- 詳細型式、Channel数、搭載Option、Firmwareは設備確定時にManifest/Configurationへ固定する。
- Native API名はDLM5000用の公式Driver Help / Communication Interface Manual / 対象PC上の実Driverを確認してから確定する。
- 制御経路は`LabVIEW Direct Driver/VISA`と`IS8000経由`をPoC比較し、最終的に主経路を1つへFreezeする。

## 4A.2 必須要求機能

| Requirement | Priority | Notes |
|---|---:|---|
| Connect / Close | 必須 | Session/ReferenceはAdapter内部へ隠蔽 |
| Get Model / Serial / Firmware / Driver Version | 必須 | Run Manifestへ保存 |
| Channel Enable/Disable | 必須 | 使用Channelだけ有効化 |
| Vertical設定 | 必須 | Range/Scale、Offset、Coupling、Probe/Attenuation等。実APIは一次資料で確定 |
| Horizontal設定 | 必須 | Timebase、Sample Rate、Record Length等 |
| Trigger設定 | 必須 | Source、Type、Level、Slope、Mode等 |
| External Trigger I/O | 要確認 | Cross-recorder hardware sync候補 |
| Arm / Single / Run / Stop | 必須 | TestStand Sequenceから制御 |
| Wait Acquisition Complete / Triggered State | 必須 | Software wait固定値に依存しない |
| Waveform Read | 必須 | 指定Channel、Timebase/scale metadata込み |
| Measurement/Statistic Read | 推奨 | 判定用Scalarを全波形再演算せず取得できる場合利用 |
| Save Waveform Artifact | 必須 | Native formatまたはVendor-supported waveform artifact |
| Save Setup | 推奨 | Run再現性確保 |
| Save Screen Image | Option | エビデンス用途 |
| Get Trigger/Acquisition Timestamp | 要確認 | Sync設計の重要PoC項目 |
| Get Status / Error | 必須 | Acquisition/Trigger/Storage Errorを取得 |

## 4A.3 公開API候補

Native VI名ではなくProject側の安定した公開責務として次を要求する。

```text
DLM5000_Connect.vi
DLM5000_Get_Version.vi
DLM5000_Configure_Channel.vi
DLM5000_Configure_Timebase.vi
DLM5000_Configure_Trigger.vi
DLM5000_Arm.vi
DLM5000_Start.vi
DLM5000_Wait_Acquisition.vi
DLM5000_Read_Waveform.vi
DLM5000_Read_Measurements.vi
DLM5000_Save_Artifact.vi
DLM5000_Get_Status.vi
DLM5000_Stop.vi
DLM5000_Close.vi
```

上記は外注/Project公開API候補名であり、Yokogawa Native API名ではない。

## 4A.4 未確定

- DLM5000公式LabVIEW Driverの実Connector Pane / LabVIEW 2026 Q3互換性
- Communication Interface Manual revision
- VISA transport / Ethernet / USB等の採用Interface
- Waveform transfer data type / block size / throughput
- Native waveform file formatと外部指定可能な保存Path/File name
- External Trigger端子、Trigger Out、時刻基準
- IS8000からの設定/記録/波形取得範囲
- Hardware Trigger時のWT5000/SMARTDAC+/RAMScope/CANalyzer/INCAとの相関方法

---

# 5. CANalyzer

CANalyzerは既存本編のActiveX設計を流用する。Project固有の別実装を新規に作らない。

## 5.1 確認済み型モデル

既存[`../../09A_CANalyzer_ActiveXラッパ実装実績.md`](../../09A_CANalyzer_ActiveXラッパ実装実績.md)では、CANalyzer 12.0 Type Libraryについて次が確認済み。

```text
CANalyzer.Application
→ IApplication10
   ├─ System        → ISystem3
   ├─ Measurement   → IMeasurement5
   ├─ Version       → IVersion2
   └─ Configuration → IConfiguration16
```

`IMeasurement5`の`Running / Start / Stop`、Configuration Open、SysVar Read/Write、Version取得等は既存Wrapperを流用する。

## 5.2 Session管理

ActiveX RefをTestStandへ公開せず、[`../../09B_CANalyzer_Session_Registry設計.md`](../../09B_CANalyzer_Session_Registry設計.md)のSession ID方式を流用する。

## 5.3 本Projectで追加確認する機能

| Requirement | Status |
|---|---|
| Measurement Start / Stop | 既存資産流用 |
| Configuration Open / Verify | 既存資産流用 |
| SysVar Read / Write | 既存資産流用 |
| Version Snapshot | 既存資産流用 |
| CAN Recording Start / Stop | Project PoC必要 |
| MF4出力Path取得 | Project PoC必要 |
| Event / Sync Marker挿入 | Project PoC必要 |
| Trigger/Hardware timestamp利用 | Project PoC必要 |

CANalyzer側の高帯域記録はCANalyzer自身に任せ、LabVIEWへ全CAN Frameを逐次転送しない案を第一候補とする。

---

# 6. RAMScope

RAMScopeの接続、測定条件、ロギング、Buffer取得、Parser、TDMS PoCは[`../../10_RAMScope実装方針.md`](../../10_RAMScope実装方針.md)を流用する。

## 6.1 本Projectで追加したい機能

入手した`RAMScope-EX/EXG ハードウェア制御用API外部仕様書 Rev.5.0`では、ターゲットRAMの読み込み/書き換えがAPI基本機能に含まれる。また次のAPIが仕様書に存在する。

```text
RAMScopeGT150MemoryRead()
RAMScopeGT150MemoryWrite()
RAMScopeGT150ContinualyMemoryRead()
RAMScopeGT150ContinualyMemoryWrite()

RAMScopeGT170ScenarioWriteStart()
RAMScopeGT170ScenarioWriteStop()
```

`MemoryWrite`および`ContinualyMemoryWrite`は測定中にも発行可能で、測定中は測定周期末に書換処理される仕様が記載されている。

GT17xのScenario Writeは複数Stepの自動RAM書換えに利用可能だが、仕様書上PROライセンスが必要。

### Project公開API候補

```text
RAMScope_Read_Memory.vi
RAMScope_Write_Memory.vi
RAMScope_Read_Multiple_Memory.vi
RAMScope_Write_Multiple_Memory.vi
RAMScope_Scenario_Write_Start.vi
RAMScope_Scenario_Write_Stop.vi
```

さらに上位にSafetyを含むCalibration Serviceを置く。

```text
RAMScope_Write_Calibration.vi
  → Validate
  → Read Before
  → Write
  → Readback
  → Verify
  → Audit Event
```

## 6.2 bit数のSource Conflict

**要解消。**

- 既存本編は実装対象として`RAMScopeVP_API_x64.dll`を採用している。
- 入手したAPI仕様書 Rev.5.0には`32bit native library / 64bit OSではWOW64`という記載がある。

本Projectでは既存本編を勝手に32bitへ戻さない。対象PCへ導入する実際のRAMScope I.K. package、同梱header、DLL PE bitness、Exportを再確認してSource Authorityを決める。

この確認はIS8000 User Libraryへ直接組み込めるかどうかにも影響する。

---

# 7. IS8000

IS8000は**User Library SDK**と**Control API**を別レイヤとして扱う。

## 7.1 IS8000SDK User Library

標準非対応機器をIS8000のDAQ Sourceへ追加する用途。

入手済みSDK/Help/Sampleから、少なくとも次の責務を持つInterface群を利用する設計とする。

```text
ICommunicator
IDevice / IDeviceFactory
IDataAcquisition / IDataAcquisitionFactory
IRecordableDataAcquisition
IDaqChannel / IDaqChannelManager
INumericMonitorAcquisition (推奨)
```

RAMScopeをIS8000へ取り込む場合は、RAMScope Service/User LibraryがこれらInterfaceを実装する。

SMARTDAC+ GM10はUser Library新規開発ではなく、`/MB1` Modbus/TCP経路を第一候補とする。

## 7.2 IS8000 Control API

外部ApplicationからIS8000を操作するgRPC API。User Applicationには`IS8000SDK.dll`は不要。

入手済み`IS8000Control`のproto/help/sampleから、本Projectでは最低限次をWrapperする。

```text
IS8000 Start / RPC Connect
GetFunctionList
GetDataSourceList
AddDeviceDataSource
RemoveDataSource
CreateTabWindow / CloseTabWindow
GetDataAcquisitionList
Monitor channel settings
SetSaveFolder
OpenNotificationStream
Start / RecStart / Hold / Stop / Divide
OpenWaveformStream / CloseWaveformStream
ChangeWaveformRecordingType
LoadProject / SaveProject
GetLastError
Close
```

`OpenNotificationStream`でRecording開始/停止成立を観測できるため、Host command送信時刻だけより良いRuntime Eventとして利用する。

## 7.3 Modbus/TCP `/MB1`

Projectでは温度DAQ用に次を要求する。

```text
GM10 Modbus/TCP Data Source追加
Temperature channel mapping
Polling/recording interval設定
Channel name/unit/status保持
IS8000 recordingへのChannel inclusion確認
Modbus communication error/status取得
```

GM10用Read fileはYokogawa標準提供物を優先し、独自file作成は必要差分だけに限定する。

## 7.4 未確定

- IS8000 recordingの対象VersionでのMF4 artifact仕様
- Recording file nameの外部指定可否
- Recorder内部の絶対時刻基準
- SMARTDAC+ Modbus channelのtimestamp/polling model
- DLM5000を標準Data Sourceとして扱える範囲とControl APIでの設定可能範囲
- RAMScope User Libraryとのbitness/性能整合

---

# 8. INCA / ETK

`INCA Tool-API Documentation.chm`を入手済み。INCAはETK高速計測・Recorder・Calibrationをメーカー機能へ任せる構成を第一候補とする。

CHMのexact member auditは別途実施し、Project文書では未確認のnative Method名を推測で確定しない。

## 8.1 必須要求機能

```text
Connect to INCA Application
Get Opened Experiment / Workspace context
Get Device / Hardware state
Initialize Hardware
Start Measurement
Stop Measurement
Read Selected Measurement Value

Read Calibration Value
Write Calibration Value
Readback / Verify Calibration

Configure Recording Metadata
Start Recorder
Insert Sync/Event Marker
Stop Recorder
Get Recording File Path

Get INCA Version
Disconnect / Cleanup
```

## 8.2 設計方針

- TestStand判定に必要な少数SignalだけTool API経由でLabVIEWへ取得する。
- ETK高速Raw DataはINCA Recorderへ任せる。
- CalibrationはINCAがA2LとPhysical Conversionを扱う前提で、LabVIEWは安全Wrapperを提供する。
- Writeは`Before → Write → Readback → Verify → Audit`を1操作として扱う。
- MF4/Recorder Headerへ`Run ID`等を残せるかを対象VersionでPoCする。

---

# 9. Adapter共通Error Model

全Adapterはベンダーエラーを失わずに、共通結果へ正規化する。

```text
Vendor Code
Vendor Message
Adapter Error Code
Severity
Retryable?
Safe-State Required?
Timestamp
Operation
Device ID
```

Public APIは既存`Status.ctl / TestError.ctl / error cluster`思想を流用する。ベンダー生ReferenceやException ObjectをTestStandへ公開しない。
