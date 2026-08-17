# 09A. CANalyzer ActiveXラッパ実装実績

**最終整理日：2026-08-17**

> **本章の役割**：[`09_CAN通信の実装.md`](./09_CAN通信の実装.md) を設計正本とし、2026-08-17時点でLabVIEW上から実際のCANalyzer Type Libraryを確認しながら作成したActiveX Wrapper、Service、最小PoCの実装手順・確認結果を記録する。
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
| Service | 一部手動作成 | Static wiring confirmed |
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

## 2.2 CANalyzer ActiveX Member選択

`CANalyzer.ISystem3`、`CANalyzer.INamespaces2`、`CANalyzer.INamespace`等の型端子自体は生成できたが、以下は成立しなかった。

- `ISystem3.Namespaces` Property選択
- `INamespaces2.Item` Method選択
- それに続くString index配線
- `INamespace`出力確定

したがって、CANalyzer Type Libraryに依存するProperty / Invoke NodeのMember選択は手動実装とした。

## 2.3 `.ctl` / typedef

`.ctl`新規作成はCoding Agentで未対応だった。

また、人手作成済みの`CANalyzer_SysVar_Value.ctl`、`CANalyzer_Value_Type.ctl`を既存typedefとして利用する処理も成立しなかった。

## 2.4 既存VIの差分編集

既存`CANalyzer_Variant_To_Value.vi`へerror正規化処理だけを追加するProbeも実施したが、既存配線・トンネル・cluster端子の解決に失敗し、HOLDとなった。

### 現時点の分担

```text
人手
├─ .ctl / typedef作成
├─ CANalyzer ActiveX Wrapper
├─ 既存typedefを使うService VI
├─ 既存SubVIを組み合わせるComposite VI
└─ 既存VIの差分修正

Coding Agent
├─ 設計レビュー
├─ 手順レビュー
├─ テスト観点整理
└─ LabVIEW標準Primitiveだけで完結する新規VIの限定的検討
```

---

# 3. CANalyzer 12.0で確認済みのActiveX型経路

## 3.1 Application

```text
Application (CANalyzer.Application.1)
→ CANalyzer.IApplication10
```

## 3.2 System

```text
IApplication10.System
→ Variant
→ Variant To Data(type = CANalyzer.ISystem3)
→ ISystem3
```

## 3.3 Measurement

```text
IApplication10.Measurement
→ Variant
→ Variant To Data(type = CANalyzer.IMeasurement5)
→ IMeasurement5
```

`IMeasurement5`では以下を確認済み。

```text
Running : Property → Boolean
Start   : Method
Stop    : Method
```

## 3.4 System Variable

```text
ISystem3.Namespaces
→ Variant
→ Variant To Data(type = CANalyzer.INamespaces2)
→ INamespaces2.Item(index : String)
→ INamespace
→ INamespace.Variables
→ Variant
→ Variant To Data(type = CANalyzer.IVariables3)
→ IVariables3.Item(index : String)
→ IVariable
→ IVariable.Value
```

`IVariable.Value`のRead戻りはVariant。

## 3.5 Version

```text
IApplication10.Version
→ Variant
→ Variant To Data(type = CANalyzer.IVersion2)
→ IVersion2
```

`IVersion2`で確認済みのProperty：

- `Application`
- `Build`
- `FullName`
- `major`
- `minor`
- `Name`
- `Parent`
- `Patch`

`FullName`の戻り値はString。

## 3.6 Configuration

```text
IApplication10.Configuration
→ Variant
→ Variant To Data(type = CANalyzer.IConfiguration16)
→ IConfiguration16
```

`IConfiguration16`で確認済みのProperty：

- `Path`
- `FullName`
- `Name`
- `Modified`
- `ReadOnly`
- その他

`Path`と`FullName`はいずれもString。

`IConfiguration16`のInvoke Methodで確認できたもの：

```text
CompileAndVerify
Save
SaveAs
```

Configuration Openは`IConfiguration16`ではなく`IApplication10.Open`を使用する。

```text
IApplication10.Open
├─ config     : String
├─ autoSave   : Boolean
└─ promptUser : Boolean
```

`IApplication10.Quit`は引数なし。

---

# 4. 10_ActiveX_Wrapper 実装済みVI

以下は手動作成済み。

```text
60_CAN\10_ActiveX_Wrapper\
├─ CAN_AX_Open_Application.vi
├─ CAN_AX_Get_System.vi
├─ CAN_AX_Get_Measurement.vi
├─ CAN_AX_Get_Measurement_Running.vi
├─ CAN_AX_Start_Measurement.vi
├─ CAN_AX_Stop_Measurement.vi
├─ CAN_AX_Get_Namespace.vi
├─ CAN_AX_Get_Variables.vi
├─ CAN_AX_Get_Variable_Item.vi
├─ CAN_AX_Read_Variable_Value.vi
├─ CAN_AX_Write_Variable_Value.vi
├─ CAN_AX_Get_Version.vi
├─ CAN_AX_Get_Version_FullName.vi
├─ CAN_AX_Get_Configuration.vi
├─ CAN_AX_Get_Configuration_Path.vi
├─ CAN_AX_Open_Configuration.vi
└─ CAN_AX_Quit_Application.vi
```

Connector Paneは原則として、主入力を左上、`error in`を左下、主出力を右上、`error out`を右下へ配置する。

---

# 5. Wrapper個別手順

既に`09_CAN通信の実装.md`に概念手順があるVIについては、本章では今回確認した実型と実配線を上書きせず補完する。

## 5.1 `CAN_AX_Open_Application.vi`

### 入出力

```text
Input
Open New Instance? : Boolean
error in

Output
Application Ref : CANalyzer.IApplication10
error out
```

### 配線

```text
CANalyzer.IApplication10型Automation Refnum
        ↓
Automation Open
        ↑
Open New Instance?
        ↑
error in
        ↓
Application Ref
error out
```

Application RefはこのVIではCloseしない。

---

## 5.2 `CAN_AX_Get_System.vi`

```text
Application Ref : IApplication10
        ↓
Property Node : System
        ↓
Variant
        ↓
Variant To Data
 type = CANalyzer.ISystem3
        ↓
System Ref : ISystem3
```

`IApplication10.System`は直接`ISystem3`を返さずVariantを返すため、`Variant To Data`が必要。

---

## 5.3 `CAN_AX_Get_Measurement.vi`

```text
Application Ref : IApplication10
        ↓
Property Node : Measurement
        ↓
Variant
        ↓
Variant To Data
 type = CANalyzer.IMeasurement5
        ↓
Measurement Ref : IMeasurement5
```

---

## 5.4 `CAN_AX_Get_Measurement_Running.vi`

```text
Measurement Ref : IMeasurement5
        ↓
Property Node : Running
        ↓
Running : Boolean
```

---

## 5.5 `CAN_AX_Start_Measurement.vi`

```text
Measurement Ref : IMeasurement5
        ↓
Invoke Node : Start
        ↓
error out
```

Running待ちはWrapper内へ入れない。

---

## 5.6 `CAN_AX_Stop_Measurement.vi`

```text
Measurement Ref : IMeasurement5
        ↓
Invoke Node : Stop
        ↓
error out
```

---

## 5.7 `CAN_AX_Get_Namespace.vi`

### 入出力

```text
Input
System Ref : CANalyzer.ISystem3
Namespace  : String
error in

Output
Namespace Ref : CANalyzer.INamespace
error out
```

### 配線

```text
System Ref
  ↓
ISystem3.Namespaces
  ↓ Variant
Variant To Data
 type = CANalyzer.INamespaces2
  ↓
INamespaces2.Item(index = Namespace)
  ↓
Namespace Ref : INamespace
```

`INamespaces2`はVI内部の一時Refなので、`Item`実行後にClose Referenceする。

error順序：

```text
error in
→ Namespaces
→ Variant To Data
→ Item
→ Close INamespaces2
→ error out
```

Ref所有権：

```text
System Ref     : Closeしない
INamespaces2   : VI内部でClose
Namespace Ref  : Closeせず出力
```

---

## 5.8 `CAN_AX_Get_Variables.vi`

```text
Namespace Ref : INamespace
        ↓
Property Node : Variables
        ↓
Variant
        ↓
Variant To Data
 type = CANalyzer.IVariables3
        ↓
Variables Ref : IVariables3
```

Namespace Ref、Variables RefともこのVIではCloseしない。

---

## 5.9 `CAN_AX_Get_Variable_Item.vi`

```text
Variables Ref : IVariables3
Variable Name : String
        ↓
Invoke Node : Item
 index = Variable Name
        ↓
Variable Ref : IVariable
```

入力Ref、出力RefともこのVIではCloseしない。

---

## 5.10 `CAN_AX_Read_Variable_Value.vi`

```text
Variable Ref : IVariable
        ↓
Property Node : Value（Read）
        ↓
Value Variant : Variant
```

型変換はService側で行う。

---

## 5.11 `CAN_AX_Write_Variable_Value.vi`

```text
Variable Ref : IVariable
Value Variant : Variant
        ↓
Property Node : Value（Write）
        ↓
error out
```

Variable Refは呼出元所有なのでCloseしない。

---

## 5.12 `CAN_AX_Get_Version.vi`

```text
Application Ref : IApplication10
        ↓
Property Node : Version
        ↓
Variant
        ↓
Variant To Data
 type = CANalyzer.IVersion2
        ↓
Version Ref : IVersion2
```

---

## 5.13 `CAN_AX_Get_Version_FullName.vi`

```text
Version Ref : IVersion2
        ↓
Property Node : FullName
        ↓
Version Full Name : String
```

---

## 5.14 `CAN_AX_Get_Configuration.vi`

```text
Application Ref : IApplication10
        ↓
Property Node : Configuration
        ↓
Variant
        ↓
Variant To Data
 type = CANalyzer.IConfiguration16
        ↓
Configuration Ref : IConfiguration16
```

---

## 5.15 `CAN_AX_Get_Configuration_Path.vi`

今回の実装では`IConfiguration16.Path`を採用した。

```text
Configuration Ref : IConfiguration16
        ↓
Property Node : Path
        ↓
Path : String
```

`Path`と`FullName`の意味差、特にファイル名を含む完全パスとしてどちらを採用すべきかは、実CANalyzer Configurationを開いた実値確認で最終確定する。

---

## 5.16 `CAN_AX_Open_Configuration.vi`

### 入力

```text
Application Ref     : CANalyzer.IApplication10
Configuration Path  : String
AutoSave?           : Boolean
Prompt User?        : Boolean
error in
```

### 配線

```text
Application Ref
        ↓
Invoke Node : IApplication10.Open
├─ config     ← Configuration Path
├─ autoSave   ← AutoSave?
└─ promptUser ← Prompt User?
        ↓
error out
```

Wrapperでは`autoSave`、`promptUser`を固定しない。運用値は上位Serviceで決める。

---

## 5.17 `CAN_AX_Quit_Application.vi`

```text
Application Ref : IApplication10
        ↓
Invoke Node : Quit
        ↓
error out
```

`Quit`は引数なし。

Application RefのCloseは別途Cleanup側で行う。

---

# 6. Phase 3 最小Open / Close PoC

`PoC_CANalyzer_01_Open_Close.vi`を手動作成した。

```text
Open New Instance?
        ↓
CAN_AX_Open_Application.vi
        ↓ Application Ref
CAN_AX_Get_System.vi
        ↓ System Ref
Close Reference（System Ref）
        ↓
Close Reference（Application Ref）
        ↓
error out
```

Application Refは`CAN_AX_Get_System.vi`と最後のCloseへ分岐する。

error順序：

```text
error in
→ CAN_AX_Open_Application.vi
→ CAN_AX_Get_System.vi
→ Close System Ref
→ Close Application Ref
→ error out
```

静的配線は完了。実行確認は環境条件に応じて別途実施する。

---

# 7. 20_Service 実装済みVI

## 7.1 `CANalyzer_Resolve_SysVar.vi`

### 目的

`System Ref`、`Namespace`、`Variable Name`から最終`Variable Ref`を解決する。

### 入出力

```text
Input
System Ref     : CANalyzer.ISystem3
Namespace      : String
Variable Name  : String
error in

Output
Variable Ref   : CANalyzer.IVariable
error out
```

### 配線

```text
System Ref + Namespace
        ↓
CAN_AX_Get_Namespace.vi
        ↓ Namespace Ref
CAN_AX_Get_Variables.vi
        ↓ Variables Ref
CAN_AX_Get_Variable_Item.vi ← Variable Name
        ↓ Variable Ref ─────────→ 出力
        ↓
Close Reference（Variables Ref）
        ↓
Close Reference（Namespace Ref）
        ↓
error out
```

Ref所有権：

```text
System Ref     : 入力なのでCloseしない
Namespace Ref  : Resolver内部でClose
Variables Ref  : Resolver内部でClose
Variable Ref   : Closeせず呼出元へ返す
```

Close順は子から親の逆順で`Variables Ref → Namespace Ref`。

---

## 7.2 `CANalyzer_Value_To_Variant.vi`

### 既存typedef

`CANalyzer_Value_Type.ctl`

```text
Boolean
I32
U32
DBL
String
```

`CANalyzer_SysVar_Value.ctl`

```text
Value Type      : CANalyzer_Value_Type.ctl
Boolean Value   : Boolean
Numeric Value   : DBL
String Value    : String
```

### 基本構造

```text
CANalyzer_SysVar_Value
        ↓
Unbundle By Name
├─ Value Type
├─ Boolean Value
├─ Numeric Value
└─ String Value
        ↓
Case Structure（Value Type）
├─ Boolean
├─ I32
├─ U32
├─ DBL
└─ String
        ↓
To Variant
        ↓
Value Variant
```

### Boolean

```text
Boolean Value
→ To Variant
```

### DBL

```text
Numeric Value(DBL)
→ To Variant
```

### String

```text
String Value
→ To Variant
```

### I32

`Numeric Value`はDBLのため、変換前に以下を確認する。

```text
-2147483648 <= Numeric Value <= 2147483647
AND
Numeric Valueが整数値
```

整数判定は、丸めた値と元の値が一致することを利用する。

正常時：

```text
Numeric Value
→ I32変換
→ To Variant
```

不正時：

```text
error code = -710106
```

### U32

```text
0 <= Numeric Value <= 4294967295
AND
Numeric Valueが整数値
```

正常時：

```text
Numeric Value
→ U32変換
→ To Variant
```

不正時：

```text
error code = -710106
```

範囲外値や小数値を先にI32/U32へ強制変換しない。

---

## 7.3 `CANalyzer_Variant_To_Value.vi`

### 目的

`Value Variant`を`Expected Value Type`へ変換し、`CANalyzer_SysVar_Value` Clusterへ格納する。

### 入出力

```text
Input
Value Variant       : Variant
Expected Value Type : CANalyzer_Value_Type.ctl
error in

Output
Value               : CANalyzer_SysVar_Value.ctl
error out
```

### 変換Case

```text
Expected Value Type
        ↓
Case Structure
├─ Boolean → Variant To Data(Boolean)
├─ I32     → Variant To Data(I32) → DBL化 → Numeric Value
├─ U32     → Variant To Data(U32) → DBL化 → Numeric Value
├─ DBL     → Variant To Data(DBL) → Numeric Value
└─ String  → Variant To Data(String) → String Value
```

各Caseでは`Bundle By Name`で以下を明示的に構成する。

```text
Value Type      = Expected Value Type
Boolean Value   = 対象型がBooleanの場合のみ取得値、それ以外False
Numeric Value   = 対象数値型の取得値、それ以外0
String Value    = 対象型がStringの場合のみ取得値、それ以外空文字
```

### 既存errorの扱い

VI全体の外側に`error in.status` Case Structureを設ける。

```text
error in.status = True
→ Variant To Dataを実行しない
→ error inをerror outへそのまま伝播
→ Valueは安全な初期値

error in.status = False
→ Expected Value Type Caseを実行
```

### Variant変換失敗の共通正規化

当初は各Value Type Case内で`-710106`へ正規化していたが、重複を避けるため、型別Caseの外側へ共通化した。

```text
Expected Value Type Case
        ↓
Variant To Dataのerror out
        ↓
Unbundle By Name
├─ status
├─ code
└─ source
        ↓
Case Structure（status）
├─ False
│   ├─ 変換済みValueをそのまま出力
│   └─ errorをそのまま出力
│
└─ True
    ├─ Value = 安全な初期値
    └─ errorを次へ正規化
```

正規化後error：

```text
status = True
code   = -710106
source =
  CANalyzer_Variant_To_Value.vi
  Expected Value Type=%s
  Original Error Code=%d
  Original Error Source=%s
```

Format Into Stringへ以下を接続する。

```text
%s ← Expected Value Type
%d ← Variant To Dataの元error.code
%s ← Variant To Dataの元error.source
```

これによりBoolean / I32 / U32 / DBL / Stringごとにerror正規化処理を複製せず、1か所で管理する。

### 変換失敗時の安全値

```text
Value Type      = Expected Value Type
Boolean Value   = False
Numeric Value   = 0
String Value    = ""
```

`error out.status=True`のため、呼出元はこのValueを正常値として扱わない。

---

# 8. 今日時点の実装到達点

2026-08-17終了時点：

```text
ActiveX Wrapper
  ↓ 完成
PoC_CANalyzer_01_Open_Close.vi
  ↓ 静的実装完了
CANalyzer_Resolve_SysVar.vi
  ↓ 完成
CANalyzer_Value_To_Variant.vi
  ↓ 完成
CANalyzer_Variant_To_Value.vi
  ↓ 型変換 + 共通error正規化構造まで作成
次
  ↓
PoC_CANalyzer_02_SysVar_Read_Write.vi
```

次回はPhase 6のSysVar Read / Write PoCから再開する。

テスト予定値：

```text
Namespace      = ID03AD5D62
Variable Name  = CORE_SVS_OPE_MODE_COM
Value Type     = I32
Numeric Value  = 2
```

PoC予定フロー：

```text
CAN_AX_Open_Application.vi
↓
CAN_AX_Get_System.vi
↓
CANalyzer_Resolve_SysVar.vi
↓
CAN_AX_Read_Variable_Value.vi
↓
CANalyzer_Variant_To_Value.vi
↓ Read Before
CANalyzer_Value_To_Variant.vi
↓
CAN_AX_Write_Variable_Value.vi
↓
CAN_AX_Read_Variable_Value.vi
↓
CANalyzer_Variant_To_Value.vi
↓ Read After
Close Variable Ref
↓
Close System Ref
↓
Close Application Ref
```

`CANalyzer_Resolve_SysVar.vi`内部でNamespace Ref / Variables RefをCloseするため、PoC側では再度Closeしない。

---

# 9. 未確認・次回確認事項

以下はまだ実CANalyzer環境での実行確認を完了していない。

- 起動済みCANalyzerへの`Open New Instance? = False`実動作
- `Open New Instance? = True`の実際の新規Instance挙動
- Measurement Start / Stop / Runningの実動作
- `IConfiguration16.Path`と`FullName`の実値差
- `IApplication10.Open`によるConfiguration Open実動作
- SysVar Read / Write
- Write後Read Back一致
- 不正Namespace / Variable Name時のerror内容
- CAPL側への値反映
- CAN Interfaceを使用した実CAN通信
- Application Quit / Ownership安全性

実CAN通信、CAPL、CAN Interfaceを使う確認は実験PCで行う。

---

# 10. 次回の再開位置

次回は以下から再開する。

```text
Phase 6
PoC_CANalyzer_02_SysVar_Read_Write.vi
```

その後、設計正本`09_CAN通信の実装.md`のPhase順に、Measurement待ち、Session Registry、ActiveX直列化、Public SysVar API、Process Detect / Compatibility / Configuration / Ownershipへ進む。
