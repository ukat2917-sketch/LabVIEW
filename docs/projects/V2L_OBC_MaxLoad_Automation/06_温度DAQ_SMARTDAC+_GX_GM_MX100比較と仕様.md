# 06. 温度DAQ SMARTDAC+ GX/GM / MX100 比較と仕様

**最終整理日:** 2026-09-03  
**State:** Design proposal / 温度DAQ機種は未Freeze

---

## 1. 結論

本Projectで新規に温度DAQを選定する場合、**MX100を新規標準機として採用するより、SMARTDAC+系を採用する方が妥当**と判断する。

さらに、IS8000を統合計測の中核に置く場合は、SMARTDAC+の中でも次を推奨順とする。

1. **GM10 + GX90XA I/O module**: 自動試験設備の第一候補
2. **GX20 + GX90XA I/O module**: 現場でローカル画面・単体Recorder操作が必要な場合
3. **MX100**: 既存設備を流用する場合のLegacy候補。新規購入前提の標準機にはしない

理由は以下。

- MX100は2019-03-31で販売終了しており、Yokogawa自身がSMARTDAC+ GMを代替製品として案内している。
- IS8000のModbus/TCP通信機能 `/MB1` はGM10接続用の通信設定ファイルを標準提供している。
- GX10/GX20/GM10は共通のSMARTDAC+ I/O module群を利用できる。
- 今回入手したYokogawa GX/GP/GM Series LabVIEW DriverはGM10とGX20を実機Test済みとしている。
- 温度ロガーを自動試験設備に常設する用途では、画面を持たないGM10の方がSystem ControllerとしてのLabVIEW/TestStand/IS8000と責務分担しやすい。

GX20は不適という意味ではない。**IS8000を主UIとするならGM10、装置単体でもOperatorが画面確認・操作するならGX20**という使い分けを基本とする。

---

## 2. 比較表

| 項目 | SMARTDAC+ GM10 | SMARTDAC+ GX20 | MX100 |
|---|---|---|---|
| Product status | Current product | Current product | **Discontinued 2019-03-31** |
| 新規設備への推奨 | **◎** | ○ | △ Existing equipment only |
| 画面 | Headless / PC・Web中心 | Touch displayあり | PC中心 |
| 自動試験Rack適性 | **高い** | 中〜高 | 既存資産なら可 |
| IS8000標準連携 | **MB1でGM10用Read file提供** | MB1 + Modbus/TCPで構成可能。GM10より追加設定が増える | 標準連携の明示情報なし。Direct/APIまたは自作統合候補 |
| LabVIEW Driver | 今回入手したGX/GP/GM Driverで対応 | 同Driverで対応 | API/LabVIEW Driverあり。ただしLegacy |
| TC/RTD/DCV | GX90XAで対応 | GX90XAで対応 | MX110等で対応 |
| 最短Scan | Module依存。GX90XA-H0で1 ms | Module依存。GX90XA-H0で1 ms | 10 ms級。TC/RTDは構成依存 |
| 一般温度用途 | GX90XA-U2 10ch / 100 msが有力 | 同左 | MX110-UNV-M10等 |
| 多ch拡張 | GM10-2 multi-unitで最大420 I/O ch級 | GX20 large-memory + expansionで最大450 analog input級 | MXLOGGER構成で大規模化可能だがLegacy |
| Device local recording | あり | あり | あり/PC based運用中心 |
| Modbus/TCP | 対応 | 対応 | Legacy API中心 |
| 将来保守性 | **高い** | 高い | 低い |

※ Channel数・Scan intervalは本体型式、measurement mode、I/O module構成で制限が変わるため、設備BOM Freeze時に正式構成を確定する。

---

## 3. IS8000との統合性

### 3.1 IS8000での位置付け

IS8000 Ver.26.1.1.0の公式情報では、`/MB1` Modbus/TCP Communication optionによりModbus/TCP機器の接続・制御・データ収集が可能で、**GM10およびVZ20X用の通信設定ファイルがIS8000に付属**する。

GM10についてはYokogawa FAQでも、IS8000 Ver.23.2.1.0以降 + `/MB1` optionにより接続可能と説明されている。

GX10/GX20自身もModbus/TCP server modeをサポートするため技術的にはIS8000 MB1へ接続可能な構成を取れる。ただし、IS8000側でGM10のような標準Read fileが提供されることは今回確認できていないため、**GX20を採用した場合はModbus communication fileの作成・検証をProject作業として見込む**。

### 3.2 本Project推奨経路

```text
                        TestStand
                            │
                            ▼
                        LabVIEW
                  Setup / Run Orchestration
                     │              │
                     │              ▼ gRPC
                     │           IS8000
                     │              │
       Setup only    │              │ Modbus/TCP / MB1
                     ▼              ▼
                 SMARTDAC+ GM10 ───────── Temperature channels
                     │
                  GX90XA
                     │
               TC / RTD sensors
```

**Runtimeの温度Data acquisition ownerはIS8000を第一候補**とする。

LabVIEWのGX/GP/GM Driverは、主に次の用途へ使用する。

- Run前Channel/Range/TC/RTD/Burnout/Scan設定
- Version確認
- Native recording設定
- PoC / Maintenance
- IS8000未使用時のDirect acquisition fallback

IS8000 recording中にLabVIEW Driverから同一機器へ継続的に別Sessionでアクセスする設計は、競合・通信負荷を評価するまで標準としない。

推奨Ownershipは以下。

```text
Setup:
LabVIEW GX/GM Adapter → Configure → Verify → Session Close

Runtime:
IS8000 MB1 → GM10 Modbus/TCP → Temperature DAQ

Cleanup / Artifact:
IS8000 Stop → 必要ならLabVIEW再接続 → Native artifact確認
```

---

## 4. 今回入手したLabVIEW Driverの確認結果

Upload済み`yokogawa_gx_series.zip`のReadme/VI Listから以下を確認した。

| 項目 | 確認内容 |
|---|---|
| Driver Technology | LabVIEW Plug and Play, project-style |
| Driver Revision | `4.2.1` |
| Current Revision Date | 06/2018 |
| Supported Models | GX10, GP10, GX20, GP20, **GM10** |
| Models Tested | **GM10, GX20** |
| Interfaces | LAN, RS-232C, RS-422A, USB, Bluetooth |
| VISA | 5.0 or later |
| Source | Source Code Available = Yes |
| Certification | Certified = No / NI Supported = No |
| Driver作成環境の記載 | LabVIEW 2016 / Windows 7 Japanese Edition |

したがって、LabVIEW 2026 Q3で利用する場合は「DriverがあるからそのままProduction採用」とせず、Mass Compile / Broken VI / VISA互換 / Connector Pane / Example実行をPoCする。

---

## 5. LabVIEW Driverで確認できた主要VI

### 5.1 Lifecycle

```text
Public/Initialize.vi
Public/Close.vi
Public/Utility/Revision Query.vi
```

### 5.2 Temperature channel設定

```text
Configure Channel (TC Normal).vi
Configure Channel (TC Scale).vi
Configure Channel (RTD Normal).vi
Configure Channel (RTD Scale).vi
Configure Burnout RJC.vi
Configure AI Filter.vi
Configure AI Moving Average.vi
Configure Interval.vi
Configure Scan Group.vi
Configure Master Scan Interval Group.vi
```

### 5.3 Recording設定

```text
Configure Data Save.vi
Configure Memory.vi
Configure Record Data (Display).vi
Configure Record Data (Event).vi
```

### 5.4 DAQ / Read

```text
Data/Low Level/Initiate.vi
Data/Low Level/Abort.vi
Read Measurement Data (Analog 1Chan).vi
Read Measurement Data (Analog NChan).vi
Read Measurement Data (Unit 1Chan).vi
Read Measurement Data (Unit NChan).vi
Read Measurement Data.vi
```

### 5.5 Event / Artifact

```text
Action-Status/Write Display Message.vi
Data/Get Internal Dir.vi
```

`Write Display Message.vi`はDriver VI List上、DisplayへのMessage表示に加えDisplay data/Event dataへMessageを書き込む責務として記載されている。Native recordingを併用する場合のRun ID / Sync Event marker候補としてPoC対象にする。

---

## 6. Project Public Adapter仕様

Vendor VIをTestStandへ直接公開せず、次のProject APIへWrapperする。

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

`SMARTDAC`というPublic名称にして、GM10/GX20のどちらを採用してもTestStand I/O契約を変えない。

### 6.1 Temperature Channel Config入力

最低限次を持つ。

```text
Channel ID
Enabled
Sensor Type        # TC / RTD / DCV
TC Type            # K/J/T/N etc.
RTD Type           # Pt100 etc.
Range
Unit
Tag
Burnout Detect
RJC Mode
RJC External Value (使用時)
Filter / Moving Average
Alarm Low / High (使用時)
```

### 6.2 Read output

```text
Channel ID
Tag
Value
Unit
Data Status
Host Receive UTC
Host Monotonic Tick
Source Scan Interval
```

Device/native timestampを取得できる場合は別Fieldとして保持し、Host timestampで上書きしない。

---

## 7. I/O Module推奨

### 7.1 一般温度計測

第一候補:

```text
GX90XA-10-U2
10ch Universal Input
TC / RTD / DCV / DI
Shortest scan: 100 ms
```

OBC/DCDC最大負荷試験の筐体、半導体周辺、冷却水、コネクタ、磁性部品等の通常温度計測なら、100 ms級で十分かをまず要件確認する。熱電対自体の熱時定数を考えると、無条件に1 ms acquisitionへ寄せる必要はない。

### 7.2 ノイズ耐性優先

候補:

```text
GX90XA-10-T1
Electromagnetic relay scanner
10ch
Shortest scan: 1 s
```

Power Electronics設備のCommon-mode noise等で安定性を優先する温度点に比較検討する。

### 7.3 高速入力が必要な特殊点

候補:

```text
GX90XA-04-H0
4ch High-speed Universal Input
Shortest scan: 1 ms
```

高速電圧/接点/特殊な熱応答評価等、100 msでは不足するChannelだけに限定して採用する。

---

## 8. 時刻同期の扱い

**SMARTDAC+をIS8000へModbus/TCP接続しても、DL950/SL2000/WT5000で説明されている500 ns級の高精度同期クラスと同一とは扱わない。**

温度DAQは低帯域Sourceとして別Synchronization Classを与える。

Project PoCで次を測定する。

```text
SMARTDAC scan interval
IS8000 Modbus polling interval
Host/IS8000 receive timestamp
Native device time (取得可能なら)
Common event occurrence time
Observed offset / jitter
min / max / p95 / p99
```

温度Channelについて必要な同期許容値は試験Requirementから決め、Software/Modbus同期で満足できるかをPoCで判定する。

---

## 9. Native Recordingの位置付け

IS8000をPrimary recordingにしても、SMARTDAC+内部Recorderを**redundant artifact**として残す案を推奨する。

理由:

- PC/IS8000通信断時の温度Data保全
- Device側のData Status / Alarm / Event保存
- IS8000 Modbus dataとの照合
- Run後のData Integrity検証

Native recordingを有効化する場合、Run IDをBatch/Message/File metadataのどこへ残せるかをPoCする。

---

## 10. Acceptance Criteria

### 10.1 Driver compatibility

- [ ] LabVIEW 2026 Q3 64bitでDriver projectを開ける
- [ ] Mass Compile後にBroken VIが残らない
- [ ] VISA sessionをLANでOpen/Closeできる
- [ ] GM10またはGX20のModel/Firmware/Driver Revisionを取得できる
- [ ] 10回以上Connect/CloseしてResource leakがない

### 10.2 Temperature acquisition

- [ ] TC K等、対象SensorをChannel設定できる
- [ ] RJC / Burnout detectを設定できる
- [ ] Open TC時に異常Statusを検出できる
- [ ] 指定Scan intervalで連続取得できる
- [ ] N channel readでChannel/Tag/Unit/Statusの対応が崩れない
- [ ] 1時間以上の連続DAQで通信欠落を監視できる

### 10.3 IS8000 MB1 integration

- [ ] `/MB1` option有効化を確認
- [ ] GM10 Read fileまたは作成したModbus fileでData Sourceを追加できる
- [ ] 指定Temperature channelsがIS8000画面へ表示される
- [ ] IS8000 recording artifactへTemperature channelsが含まれることを実ファイルで確認
- [ ] Stop後artifactがflush完了する
- [ ] Run IDからIS8000 artifactとSMARTDAC native artifactを追跡できる

### 10.4 Sync / quality

- [ ] Temperature Dataの実Scan intervalを確認
- [ ] Modbus polling offset/jitterを測定
- [ ] Data Status / burnout / communication errorをManifestへ保存
- [ ] Network断後のRecovery policyを確認
- [ ] Native recordingが通信断中も継続するか確認

---

## 11. 現時点のDesign Decision

### Recommended

```text
Temperature DAQ Hardware:
SMARTDAC+ GM10 + GX90XA modules

Primary Runtime Data Path:
GM10 → Modbus/TCP → IS8000 MB1 → IS8000 recording/MF4

Configuration / Maintenance:
LabVIEW → Yokogawa GX/GP/GM LabVIEW Driver → GM10

Redundancy:
GM10 native recording (recommended)
```

### Alternative

```text
GX20 + GX90XA
```

Operatorが試験設備前でTemperature trendを確認したい、PC停止時にも本体画面を使いたい等の要求がある場合に選ぶ。

### Legacy

```text
MX100
```

既設資産を流用する価値はあるが、新規標準設備としてはSMARTDAC+へ移行する。

---

## 12. Freeze前にHuman/設備側で決める項目

- [ ] GM10 or GX20
- [ ] 必要Temperature channel数
- [ ] TC type / RTD type
- [ ] Target scan interval
- [ ] GX90XA module type / quantity
- [ ] IS8000 `/MB1` license有無
- [ ] Native recordingを常時有効化するか
- [ ] Temperature sync requirement
- [ ] 温度判定をTestStandへ何ms周期で返す必要があるか
- [ ] Local displayが必要か

---

## 13. Source

- Yokogawa IS8000 Integrated Software Platform, Modbus/TCP `/MB1` specification and GM10 integration information
  - https://tmi.yokogawa.com/jp/solutions/products/oscilloscopes/scopecorders/is8000-integrated-software-platform/
  - https://tmi.yokogawa.com/us/library/resources/faqs/why-cant-i-connect-my-gm10-to-is8000/
- Yokogawa SMARTDAC+ GX10/GX20 product/specifications
  - https://www.yokogawa.com/solutions/products-and-services/measurement/data-acquisition-products/panel-mount-recorders/touch-screen-gx10-gx20/
- Yokogawa SMARTDAC+ GM10 product/specifications
  - https://www.yokogawa.com/solutions/products-and-services/measurement/data-acquisition-products/data-logger/modular-gm10/
- Yokogawa MX100 discontinued product information
  - https://www.yokogawa.co.jp/solutions/discontinued/pc-based-mx100/
- Upload: `yokogawa_gx_series.zip`
  - `Yokogawa GX Series Readme.html`
  - `Yokogawa GX Series VI List.txt`
  - Public/Examples VIs
