# 09A. CANalyzer ActiveXラッパ実装実績

**最終整理日：2026-08-17**

> **本章の役割**：[`09_CAN通信の実装.md`](./09_CAN通信の実装.md) を設計正本とし、2026-08-17時点でLabVIEW上から実際のCANalyzer Type Libraryを確認しながら作成したActiveX Wrapperと最小PoCの実装手順・確認結果を記録する。
>
> 本章では、Type Libraryで確認できた事実と、まだ実行確認していない事項を分離する。CANalyzer固有API名、Interface名、引数は推測で補わない。

---

# 1. 実装環境と確認状態

| 項目 | 内容 | State |
|---|---|---|
| LabVIEW | 2026 Q3 64bit | Confirmed |
| TestStand | 2026 Q3 64bit | Confirmed |
| CANalyzer Type Library | `CANalyzer 12.0 Type Library Version 1.3b` | Confirmed |
| Application COM Object | `Application (CANalyzer.Application.1)` | Confirmed |
| ProgID | `CANalyzer.Application` | Confirmed |
| LabVIEW Project | `C:\LabVIEW work\SVS_AutoTestSystem\SVS_AutoSystem.lvproj` | Confirmed |
| CAN実装ルート | `C:\LabVIEW work\SVS_AutoTestSystem\60_CAN\` | Confirmed |
| ActiveX Wrapper | 手動作成 | Static wiring confirmed |
| 実CAN通信 | 未実施 | 実験PC確認待ち |
| SysVar実値Read / Write | 未実施 | 実験PC確認待ち |
| Measurement実動作 | 未実施 | 実験PC確認待ち |

**Source**：対象PCに登録されたCANalyzer 12.0 Type Library

**Verified by**：LabVIEW 2026 Q3のAutomation Refnum / Property Node / Invoke Node / Variant To Dataを使用した手動確認

---

# 2. Coding Agentの確認済み制約

LabVIEW Coding Agentについて、CANalyzer実装前にCapability Probeを実施した。

## 2.1 既存ユーザーVIのSubVI配置

既存の手動作成WrapperをSubVIとして配置するProbeでは、`Unsupported SubVI`となり生成できなかった。

したがって、現時点では次をCoding Agent主体で生成しない。

- 既存Wrapperを組み合わせるService VI
- 既存Wrapperを組み合わせるPublic VI
- 既存Wrapperを組み合わせるPoC

## 2.2 ActiveX Property / Invoke Member選択

`CAN_AX_Get_Namespace.vi`相当のCapability Probeでは、以下のCANalyzer型端子自体は生成可能だった。

- `CANalyzer.ISystem3`
- `CANalyzer.INamespaces2`
- `CANalyzer.INamespace`

一方、Coding Agentでは以下が成立しなかった。

- `ISystem3.Namespaces` Propertyの選択
- `INamespaces2.Item` Methodの選択
- Member確定後の配線完了

したがって、**CANalyzer固有のProperty Node / Invoke Nodeを使用するWrapperは人手で作成する。**

## 2.3 `.ctl` / typedef

Coding Agentでは`.ctl`の新規作成およびtypedef構築が未対応だった。

したがって、`00_Common`のtypedef / ctlも人手作成とする。

---

# 3. ActiveX Wrapper共通実装ルール

保存先：

```text
60_CAN\10_ActiveX_Wrapper\
```

共通ルール：

1. CANalyzer固有ActiveX型は`10_ActiveX_Wrapper`内に閉じ込める。
2. `error in` / `error out`を直列配線する。
3. 入力されたActiveX RefはWrapper内でCloseしない。
4. 呼び出し側へ返すActiveX RefはWrapper内でCloseしない。
5. Wrapper内部だけで取得する一時RefはWrapper内でCloseする。
6. Property / Method / Interface名はType Library実値を使用する。
7. Connector Paneは主入力を左上、`error in`を左下、主出力を右上、`error out`を右下とする基本配置へ統一する。
8. VariantからCOM Interfaceへ変換する場合は`Variant To Data`を使用する。

---

# 4. Type Libraryで確認したActiveX型経路

2026-08-17時点のCANalyzer 12.0環境で確認した主経路は以下。

```text
CANalyzer.Application
  ↓ Automation Open
IApplication10
  ├─ System
  │    ↓ Variant
  │  ISystem3
  │    ↓ Namespaces
  │  Variant
  │    ↓ cast
  │  INamespaces2
  │    ↓ Item(index: String)
  │  INamespace
  │    ↓ Variables
  │  Variant
  │    ↓ cast
  │  IVariables3
  │    ↓ Item(index: String)
  │  IVariable
  │    ↓ Value
  │  Variant
  │
  ├─ Measurement
  │    ↓ Variant
  │  IMeasurement5
  │    ├─ Running
  │    ├─ Start
  │    └─ Stop
  │
  ├─ Version
  │    ↓ Variant
  │  IVersion2
  │    └─ FullName
  │
  └─ Configuration
       ↓ Variant
     IConfiguration16
       └─ Path
```

---

# 5. `CAN_AX_Open_Application.vi`

## 5.1 目的

CANalyzer ApplicationのAutomation Refを取得する。

## 5.2 入出力

| 端子名 | 方向 | 型 |
|---|---|---|
| `Open New Instance?` | 入力 | Boolean |
| `error in` | 入力 | error cluster |
| `Application Ref` | 出力 | `CANalyzer.IApplication10` |
| `error out` | 出力 | error cluster |

## 5.3 配置・配線

1. CANalyzer Type Libraryから`Application (CANalyzer.Application.1)`を指定したAutomation Refnumを配置する。
2. オートメーションを開く（Automation Open）へ型Refnumを接続する。
3. `Open New Instance?`をAutomation Openへ接続する。
4. `error in` / `error out`を直列接続する。
5. Automation Open出力を`Application Ref`として返す。
6. このVI内ではApplication RefをCloseしない。

**Type Library実値**：`IApplication10`

**State**：手動実装済み

---

# 6. `CAN_AX_Get_System.vi`

## 6.1 目的

ApplicationからSystem Interfaceを取得する。

## 6.2 入出力

| 端子名 | 方向 | 型 |
|---|---|---|
| `Application Ref` | 入力 | `CANalyzer.IApplication10` |
| `error in` | 入力 | error cluster |
| `System Ref` | 出力 | `CANalyzer.ISystem3` |
| `error out` | 出力 | error cluster |

## 6.3 配線順

```text
Application Ref : IApplication10
  ↓ Property: System
Variant
  ↓ Variant To Data
CANalyzer.ISystem3
  ↓
System Ref
```

`IApplication10.System`の戻り値はVariantであるため、`Variant To Data`で`ISystem3`へ変換する。

**State**：手動実装済み

---

# 7. Measurement Wrapper

## 7.1 `CAN_AX_Get_Measurement.vi`

```text
Application Ref : IApplication10
  ↓ Property: Measurement
Variant
  ↓ Variant To Data
CANalyzer.IMeasurement5
  ↓
Measurement Ref
```

`IApplication10.Measurement`の戻り値はVariant。

**確認済みInterface**：`IMeasurement5`

**State**：手動実装済み

## 7.2 `CAN_AX_Get_Measurement_Running.vi`

```text
Measurement Ref : IMeasurement5
  ↓ Property: Running
Boolean
```

| 出力 | 型 | 意味 |
|---|---|---|
| `Running` | Boolean | 停止=False、実行=True |

**State**：手動実装済み

## 7.3 `CAN_AX_Start_Measurement.vi`

```text
Measurement Ref : IMeasurement5
  ↓ Invoke Method: Start
```

Start後のRunning待ちはWrapperへ入れない。

**State**：手動実装済み

## 7.4 `CAN_AX_Stop_Measurement.vi`

```text
Measurement Ref : IMeasurement5
  ↓ Invoke Method: Stop
```

Stop後のRunning待ちはWrapperへ入れない。

**State**：手動実装済み

---

# 8. System Variable Wrapper

## 8.1 `CAN_AX_Get_Namespace.vi`

### 入出力

| 端子名 | 方向 | 型 |
|---|---|---|
| `System Ref` | 入力 | `CANalyzer.ISystem3` |
| `Namespace` | 入力 | String |
| `error in` | 入力 | error cluster |
| `Namespace Ref` | 出力 | `CANalyzer.INamespace` |
| `error out` | 出力 | error cluster |

### 配線順

```text
System Ref : ISystem3
  ↓ Property: Namespaces
Variant
  ↓ Variant To Data
INamespaces2
  ↓ Invoke Method: Item
index = Namespace String
  ↓
INamespace
  ↓
Namespace Ref
```

`INamespaces2`はWrapper内部だけで使用する一時Refのため、`Item`実行後にClose Referenceする。

```text
error in
  ↓
Namespaces
  ↓
Variant To Data
  ↓
Item
  ↓
Close Reference (INamespaces2)
  ↓
error out
```

参照所有権：

- `System Ref`：Closeしない
- `INamespaces2`：VI内部でClose
- `Namespace Ref`：Closeせず呼出側へ返す

**State**：手動実装済み

## 8.2 `CAN_AX_Get_Variables.vi`

```text
Namespace Ref : INamespace
  ↓ Property: Variables
Variant
  ↓ Variant To Data
CANalyzer.IVariables3
  ↓
Variables Ref
```

入力`Namespace Ref`、出力`Variables Ref`ともWrapper内ではCloseしない。

**State**：手動実装済み

## 8.3 `CAN_AX_Get_Variable_Item.vi`

```text
Variables Ref : IVariables3
Variable Name : String
  ↓ Invoke Method: Item
index = Variable Name
  ↓
CANalyzer.IVariable
  ↓
Variable Ref
```

`IVariables3.Item`の`index`はString。

**State**：手動実装済み

## 8.4 `CAN_AX_Read_Variable_Value.vi`

```text
Variable Ref : IVariable
  ↓ Property: Value (Read)
Variant
  ↓
Value Variant
```

WrapperではI32等へ変換せずVariantのまま返す。

**State**：手動実装済み

## 8.5 `CAN_AX_Write_Variable_Value.vi`

```text
Variable Ref : IVariable
Value Variant : Variant
  ↓ Property: Value (Write)
```

`Variable Ref`は呼出元所有のためCloseしない。

**State**：手動実装済み

---

# 9. Version Wrapper

## 9.1 `CAN_AX_Get_Version.vi`

```text
Application Ref : IApplication10
  ↓ Property: Version
Variant
  ↓ Variant To Data
CANalyzer.IVersion2
  ↓
Version Ref
```

Type Library上で`IVersion2`に以下のPropertyが存在することを確認した。

- `Application`
- `Build`
- `FullName`
- `major`
- `minor`
- `Name`
- `Parent`
- `Patch`

**State**：手動実装済み

## 9.2 `CAN_AX_Get_Version_FullName.vi`

```text
Version Ref : IVersion2
  ↓ Property: FullName
String
  ↓
Version Full Name
```

`FullName`の戻り値はString。

**State**：手動実装済み

---

# 10. Configuration Wrapper

## 10.1 `CAN_AX_Get_Configuration.vi`

```text
Application Ref : IApplication10
  ↓ Property: Configuration
Variant
  ↓ Variant To Data
CANalyzer.IConfiguration16
  ↓
Configuration Ref
```

**State**：手動実装済み

## 10.2 `CAN_AX_Get_Configuration_Path.vi`

```text
Configuration Ref : IConfiguration16
  ↓ Property: Path
String
  ↓
Path
```

`IConfiguration16.Path`と`IConfiguration16.FullName`はいずれもStringであることを確認済み。

現時点では`Path`を`CAN_AX_Get_Configuration_Path.vi`で採用している。ただし、**PathとFullNameの実値上の意味の違いは未実行確認**。Expected / Actual Configuration比較にどちらを正式採用するかは実値確認後に確定する。

**State**：手動実装済み、意味差は実機確認待ち

## 10.3 `CAN_AX_Open_Configuration.vi`

`IConfiguration16`のInvoke Method一覧では以下を確認した。

- `CompileAndVerify`
- `Save`
- `SaveAs`

Configurationを開くMethodは`IConfiguration16`側では確認できなかった。

`IApplication10`のInvoke Method一覧を確認し、`Open`を確認した。

### Type Library実値

```text
IApplication10.Open
  config      : String
  autoSave    : Boolean
  promptUser  : Boolean
```

### VI入力

| 端子名 | 型 |
|---|---|
| `Application Ref` | `CANalyzer.IApplication10` |
| `Configuration Path` | String |
| `AutoSave?` | Boolean |
| `Prompt User?` | Boolean |
| `error in` | error cluster |

出力は`error out`のみ。

Wrapperでは`autoSave`、`promptUser`を固定せず入力端子として公開する。運用上の既定値はService側で決定する。

**State**：手動実装済み

---

# 11. `CAN_AX_Quit_Application.vi`

`IApplication10`のInvoke Method一覧から`Quit`を確認した。

```text
Application Ref : IApplication10
  ↓ Invoke Method: Quit
```

`Quit`に追加引数はない。

Application RefのCloseはこのVIの責務に含めない。Quit後のClose ReferenceはCleanup側で実施する。

**State**：手動実装済み

---

# 12. 実装済みActiveX Wrapper一覧

| VI | Type Library実値 | 状態 |
|---|---|---|
| `CAN_AX_Open_Application.vi` | `Application (CANalyzer.Application.1)` → `IApplication10` | 実装済み |
| `CAN_AX_Get_System.vi` | `IApplication10.System` → Variant → `ISystem3` | 実装済み |
| `CAN_AX_Get_Measurement.vi` | `IApplication10.Measurement` → Variant → `IMeasurement5` | 実装済み |
| `CAN_AX_Get_Measurement_Running.vi` | `IMeasurement5.Running` | 実装済み |
| `CAN_AX_Start_Measurement.vi` | `IMeasurement5.Start` | 実装済み |
| `CAN_AX_Stop_Measurement.vi` | `IMeasurement5.Stop` | 実装済み |
| `CAN_AX_Get_Namespace.vi` | `ISystem3.Namespaces` → `INamespaces2.Item` → `INamespace` | 実装済み |
| `CAN_AX_Get_Variables.vi` | `INamespace.Variables` → Variant → `IVariables3` | 実装済み |
| `CAN_AX_Get_Variable_Item.vi` | `IVariables3.Item` → `IVariable` | 実装済み |
| `CAN_AX_Read_Variable_Value.vi` | `IVariable.Value` Read → Variant | 実装済み |
| `CAN_AX_Write_Variable_Value.vi` | Variant → `IVariable.Value` Write | 実装済み |
| `CAN_AX_Get_Version.vi` | `IApplication10.Version` → Variant → `IVersion2` | 実装済み |
| `CAN_AX_Get_Version_FullName.vi` | `IVersion2.FullName` → String | 実装済み |
| `CAN_AX_Get_Configuration.vi` | `IApplication10.Configuration` → Variant → `IConfiguration16` | 実装済み |
| `CAN_AX_Get_Configuration_Path.vi` | `IConfiguration16.Path` → String | 実装済み、意味差確認待ち |
| `CAN_AX_Open_Configuration.vi` | `IApplication10.Open(config, autoSave, promptUser)` | 実装済み |
| `CAN_AX_Quit_Application.vi` | `IApplication10.Quit` | 実装済み |

---

# 13. Connector Pane

上記WrapperはConnector Pane設定まで実施済み。

基本配置：

```text
左上：主入力               右上：主出力
左下：error in             右下：error out
```

入力が複数あるVIでは主入力の下へ追加入力を並べる。

---

# 14. 最小Open / Close PoC

作成先：

```text
60_CAN\40_PoC\PoC_CANalyzer_01_Open_Close.vi
```

構成：

```text
Open New Instance?
  ↓
CAN_AX_Open_Application.vi
  ↓ Application Ref
  ├───────────────→ 最後のClose Reference
  ↓
CAN_AX_Get_System.vi
  ↓ System Ref
Close Reference (System Ref)
  ↓
Close Reference (Application Ref)
  ↓
error out
```

error clusterの順序：

```text
error in
  ↓
CAN_AX_Open_Application.vi
  ↓
CAN_AX_Get_System.vi
  ↓
Close Reference (System Ref)
  ↓
Close Reference (Application Ref)
  ↓
error out
```

参照は子から親の順でCloseする。

```text
System Ref
  ↓ Close
Application Ref
  ↓ Close
```

**State**：ブロックダイアグラム作成済み。実行結果は未記録。

---

# 15. 現時点の到達点

```text
Application取得
  ↓
System取得
  ↓
Measurement Interface取得
  ↓
Running / Start / Stop Member確認

System
  ↓
Namespaces
  ↓
Namespace
  ↓
Variables
  ↓
Variable
  ↓
Value Read / Write

Application
  ↓
Version / FullName

Application
  ↓
Configuration / Path
  ↓
Open(config, autoSave, promptUser)

Application
  ↓
Quit
```

ActiveX Wrapperの主要なType Library依存箇所は手動実装済み。

---

# 16. 次に実装する内容

次の実装対象は、`09_CAN通信の実装.md`の設計に従いService層へ進む。

優先順：

1. `CANalyzer_Resolve_SysVar.vi`
2. `CANalyzer_Value_To_Variant.vi`
3. `CANalyzer_Variant_To_Value.vi`
4. `PoC_CANalyzer_02_SysVar_Read_Write.vi`

`CANalyzer_Resolve_SysVar.vi`では次のWrapperを順に使用する。

```text
System Ref
  ↓
CAN_AX_Get_Namespace.vi
  ↓ Namespace Ref
CAN_AX_Get_Variables.vi
  ↓ Variables Ref
CAN_AX_Get_Variable_Item.vi
  ↓ Variable Ref
```

Resolver内部で`Namespace Ref`と`Variables Ref`をCloseし、`Variable Ref`だけを呼出側へ返す。

実CAN通信、SysVar値、Measurement動作、Configuration Path / FullNameの意味差は、CANalyzerライセンスとCAN Interfaceが利用可能な実験PCで確認する。
