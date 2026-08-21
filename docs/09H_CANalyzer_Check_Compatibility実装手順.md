# 09H. CANalyzer Check Compatibility 実装手順

**最終整理日：2026-08-21**

> **本章の役割**：作成・差分修正・Focused As-Built Reviewを完了した `CANalyzer_Check_Compatibility.vi` について、第三者がLabVIEW画面を見ながら同じVIを再構築できる粒度で、最終As-Builtに一致する作成手順を記録する。
>
> CANalyzer全体のレイヤ構成と呼出順は [`09_CAN通信の実装.md`](./09_CAN通信の実装.md) を正とする。本章は同章 `20_Service` に属する `CANalyzer_Check_Compatibility.vi` の個別作成手順であり、同じ詳細手順を他章へ複製しない。
>
> 記述粒度は [`00A_LabVIEW実装資料の記述ルール.md`](./00A_LabVIEW実装資料の記述ルール.md) と [`00B_LabVIEW学習型VI設計ルール.md`](./00B_LabVIEW学習型VI設計ルール.md) に従い、仕様根拠と確認状態は [`00C_一次資料とバージョン基準.md`](./00C_一次資料とバージョン基準.md) に従う。

---

# 0. 実現したい機能とVIの責務

`CANalyzer_Check_Compatibility.vi` は、callerがすでに取得している **CANalyzer Application ActiveX Ref** を借用し、この自動試験システムが必要とする最小runtime capabilityを **read-only** で確認するService VIである。

Version文字列だけで互換性を決めると、未知Versionでも必要なProperty / Methodが動く環境を誤って拒否したり、逆にVersion名だけ一致して実際の機能が使えない環境を通したりする。そのため、次の2種類を分離して判定する。

```text
Version情報
  → 既知Versionかどうかを判定する補助情報

Capability Probe
  → 実際に必要なActiveX機能が使用できるかを確認する本体
```

さらにKnown SysVar ReadはConfigurationに依存するため、Compatibility Probeを2段階へ分ける。

```text
Phase 1: Configuration-independent
  Version / System / Measurement / Running

Phase 2: Configuration-dependent
  System / Measurement / Running
  → Resolve SysVar
  → Read SysVar
  → Expected Typeへ変換
```

Phase 1成功だけでは最終Compatibilityを確定しない。Phase 1 onlyでは `Compatibility Status = Unknown` を返し、Phase 2まで成功した場合だけVersion情報を使って `Compatible / Compatible with Warning / Unknown` を決定する。

本VIはCompatibility確認だけを行い、次は行わない。

- CANalyzer Applicationの起動・終了
- Configuration Open / Path Verify
- Measurement Start / Stop
- System Variable Write
- Session Registry Create / Update / Remove
- caller-owned Application RefのClose
- TestStand側Policyの決定

初期Vertical Sliceでは、Session ID発行前のbootstrap処理であるため `CANalyzer_Execute_Command.vi` は使用しない。上位の `CANalyzer_Open.vi` をNon-reentrantにして本VIをその内部Serviceとして呼ぶ。

---

# 0.1 入力データの実体

本VIの主入力は、callerが所有する `CANalyzer.IApplication10` ActiveX Refである。本VIはこのRefから必要な子Refを一時取得する。

```text
Application Ref  ← caller-owned / borrowed
├─ Version Ref       ← temporary
├─ System Ref        ← temporary
├─ Measurement Ref   ← temporary
└─ System Ref
    └─ Resolve SysVar
        └─ Variable Ref ← temporary
```

`Known Version Full Names[]` は、CANalyzer Applicationから取得したVersion FullNameとの **完全一致** にだけ使用する。Type Library VersionをApplication Versionとして扱わない。

Phase 2の `Probe Namespace` と `Probe Variable Name` はtrim後の文字列を実際のResolveに使用する。trim前文字列をValidationだけに使ってResolveへ元文字列を渡す構成にはしない。

---

# 0.2 出力データモデル

Compatibility判定は1個のBooleanへ潰さず、次の情報を分けて返す。

```text
Compatibility Status
├─ Unknown
├─ Compatible
├─ Compatible with Warning
└─ Unsupported

Capability Probe Passed?
Version Recognized?
Version String
Failed Capability
error out
```

`Compatibility Status` は互換性の意味、`Capability Probe Passed?` はmandatory probeの通過有無、`Failed Capability` は診断位置を表す。これにより「Versionは不明だがProbeは通った」と「必須機能が欠けている」を区別できる。

---

# 0.3 前提条件・異常条件

| 条件 | 意味 | 処理 |
|---|---|---|
| `error in.status = True` | 上流エラーあり | ActiveX処理を行わずoriginal errorを返す |
| Version取得失敗 | Version情報だけ取得不可 | mandatory probeは継続する |
| System / Measurement / Running失敗 | 基本必須Capability不足 | `Unsupported`, `-710101` |
| Phase 2でNamespace trim後empty | caller入力不正 | `Unknown`, `-710113` |
| Phase 2でVariable Name trim後empty | caller入力不正 | `Unknown`, `-710113` |
| Resolve / Read / Type Conversion失敗 | Configuration確認後の必須Capability不足 | `Unsupported`, `-710101` |
| Cleanupのみ失敗 | operation自体は成功 | Cleanup Errorを返す |
| OperationとCleanupの両方失敗 | 主原因と二次失敗が存在 | Operation Errorを優先する |

---

# 0.4 処理アルゴリズム

LabVIEW関数名へ落とす前の処理は次のとおり。

```text
if incoming error:
    安全な既定出力を返す
    original errorを返す
    return

Versionを取得する
取得できなければVersion Stringを空にする
Version FullNameがKnown Version配列へ完全一致するか調べる
Version系エラーはmandatory probeへ伝搬させない

Phase 1:
    Systemを取得
    Measurementを取得
    Runningを読む
    どれか失敗したらUnsupportedへ正規化
    temporary refsをcleanup

if Phase 2 disabled:
    Status = Unknown
    Probe Passed = True
    return

Probe Namespace / Variable Nameをtrimして検証
入力不正なら-710113を返す

Phase 2:
    Systemを再取得
    Measurementを再取得
    Runningを再確認
    Known SysVarをResolve
    SysVarをRead
    Expected Typeへ変換
    どれか失敗したらUnsupported / -710101へ正規化

Phase 2成功後:
    Version String empty       → Unknown
    Known Version exact match  → Compatible
    Versionあり、未登録        → Compatible with Warning

取得したtemporary refsをcleanup
Operation ErrorとCleanup Errorを
Operation Error > Cleanup Error の優先順位で統合
```

---

# 0.5 LabVIEW構造の選定理由

| 必要なロジック | LabVIEW構造 | 選定理由 |
|---|---|---|
| 上流エラー時に全処理を止める | ケースストラクチャ（Case Structure） | original errorを保護してActiveX副作用を防ぐ |
| Optional Version failureを必須Probeと分離 | 独立したerror chain + Case Structure | Version取得失敗だけでSystem等をskipさせない |
| Phase 2実行有無 | Case Structure | Configuration-dependent処理を明示的に分ける |
| Namespace / Variable入力検証 | Trim Whitespace + Empty String比較 + Case Structure | 空白だけの入力をCapability不足と誤分類しない |
| Version既知判定 | 一次元配列を検索（Search 1D Array） | FullName完全一致を明確に実装できる |
| ActiveX参照の寿命管理 | Close Reference + path別cleanup | caller-owned Refを閉じずtemporary Refだけ解放する |
| Cleanupをoperation errorから独立 | エラーをクリア（Clear Errors）を使うcleanup chain | operation failure時もCloseを実行できる |
| 最終error優先順位 | Case StructureまたはSelect相当 | `Operation Error > Cleanup Error`を明示できる |

---

# 1. 入出力

## 1.1 Controls

| 端子名 | 方向 | 型 | 用途 |
|---|---|---|---|
| `CANalyzer.IApplication10` | 入力 | CANalyzer `IApplication10` ActiveX Refnum | caller-owned Application Ref。借用のみ |
| `Enable Configuration-Dependent Probe?` | 入力 | Boolean | False=Phase 1 only、True=Phase 2まで実行 |
| `Probe Namespace` | 入力 | String | Phase 2で読むKnown SysVarのNamespace |
| `Probe Variable Name` | 入力 | String | Phase 2で読むKnown SysVar名 |
| `CANalyzer_Value_Type` | 入力 | `CANalyzer_Value_Type.ctl` | Phase 2で期待するSysVar型 |
| `Known Version Full Names[]` | 入力 | String一次元配列 | Version FullName完全一致用一覧 |
| `エラー入力 (エラーなし)` | 入力 | error cluster | 前段エラー |

## 1.2 Indicators

| 端子名 | 方向 | 型 | 用途 |
|---|---|---|---|
| `CANalyzer_Compatibility_Status` | 出力 | `CANalyzer_Compatibility_Status.ctl` | Unknown / Compatible / Compatible with Warning / Unsupported |
| `Capability Probe Passed?` | 出力 | Boolean | mandatory probeが全て通過したときTrue |
| `Version Recognized?` | 出力 | Boolean | Version Stringが既知一覧と完全一致したときTrue |
| `Version String` | 出力 | String | Version FullName。取得失敗時は空文字 |
| `Failed Capability` | 出力 | String | 失敗箇所。成功時は空文字 |
| `エラー出力` | 出力 | error cluster | normalized operation errorまたはcleanup error |

Connector Paneは現行As-Builtを維持する。全7入力・6出力を割り当て、端子の物理位置だけを理由に再配置しない。

---

# 2. 配置する関数およびSubVI等

| 数 | 日本語名 | 英語名 | 配置場所・追加方法 | 用途 |
|---:|---|---|---|---|
| 必要数 | ケースストラクチャ | Case Structure | プログラミング → ストラクチャ | incoming error、各failure、Phase 2 gate、final status |
| 1 | 名前でバンドル解除 | Unbundle By Name | プログラミング → クラスタ、クラス、バリアント | `error in.status`、error code/source取得 |
| 1以上 | 名前でバンドル | Bundle By Name | プログラミング → クラスタ、クラス、バリアント | normalized error生成 |
| 1 | 一次元配列を検索 | Search 1D Array | プログラミング → 配列 | Version FullName完全一致 |
| 2 | 空白文字を削除 | Trim Whitespace | プログラミング → 文字列 | Namespace / Variable Name正規化 |
| 必要数 | 空文字列/パス? | Empty String/Path? | プログラミング → 文字列 | Version/Probe入力のempty判定 |
| 必要数 | 等しい? / 等しくない? | Equal? / Not Equal? | プログラミング → 比較 | 検索indexとVersion判定 |
| 必要数 | 文字列にフォーマット | Format Into String | プログラミング → 文字列 | normalized error.source生成 |
| pathごと | エラーをクリア | Clear Errors | プログラミング → ダイアログ&ユーザインタフェース等からQuick Drop検索 | cleanup専用error chain開始 |
| pathごと | リファレンスを閉じる | Close Reference | 接続 → ActiveX、またはプログラミング → アプリケーション制御 | temporary ActiveX Ref解放 |
| 1 | `CAN_AX_Get_Version.vi` | SubVI | `60_CAN\10_ActiveX_Wrapper` | Application → Version Ref |
| 1 | `CAN_AX_Get_Version_FullName.vi` | SubVI | `60_CAN\10_ActiveX_Wrapper` | Version Ref → FullName |
| Phaseごと | `CAN_AX_Get_System.vi` | SubVI | `60_CAN\10_ActiveX_Wrapper` | Application → System Ref |
| Phaseごと | `CAN_AX_Get_Measurement.vi` | SubVI | `60_CAN\10_ActiveX_Wrapper` | Application → Measurement Ref |
| Phaseごと | `CAN_AX_Get_Measurement_Running.vi` | SubVI | `60_CAN\10_ActiveX_Wrapper` | Measurement → Running |
| 1 | `CANalyzer_Resolve_SysVar.vi` | SubVI | `60_CAN\20_Service` | System + trimmed names → Variable Ref |
| 1 | `CAN_AX_Read_Variable_Value.vi` | SubVI | `60_CAN\10_ActiveX_Wrapper` | Variable Ref → Variant |
| 1 | `CANalyzer_Variant_To_Value.vi` | SubVI | `60_CAN\20_Service` | Variant → Expected Value Type |

関数がパレットで見つからない場合は `Ctrl + Space` のクイックドロップ（Quick Drop）で英語名を検索する。

---

# 3. 配線順

# 3.1 STEP 1: Incoming Error Guard

1. `エラー入力 (エラーなし)` を名前でバンドル解除（Unbundle By Name）へ接続し、`status` を取り出す。
2. `status` Booleanを最外周ケースストラクチャ（Case Structure）のselectorへ接続する。
3. True caseではActiveX SubVIを一切配置・実行しない。
4. True caseから次を出力する。

| 出力 | 値 |
|---|---|
| `CANalyzer_Compatibility_Status` | `Unknown` |
| `Capability Probe Passed?` | False |
| `Version Recognized?` | False |
| `Version String` | `""` |
| `Failed Capability` | `""` |
| `エラー出力` | original `error in` |

5. False caseだけに以降の処理を配置する。`Use default if unwired`へ依存せず、全出力トンネルを明示配線する。

---

# 3.2 STEP 2: Optional Version Probeをmandatory chainから分離する

Version取得は補助情報であり、Version failureだけでSystem / Measurement / Runningを止めてはいけない。このためVersion用error chainをmandatory probe用error chainから分離する。

1. `CANalyzer.IApplication10` を `CAN_AX_Get_Version.vi` のApplication Ref入力へ接続する。
2. Version用error chainはFalse caseへ入った時点のno-error状態から開始する。
3. `CAN_AX_Get_Version.vi` のVersion Ref出力を `CAN_AX_Get_Version_FullName.vi` のVersion Ref入力へ接続する。
4. FullName取得結果を一時値 `Version String Candidate` として扱う。
5. 取得したVersion Refをリファレンスを閉じる（Close Reference）へ接続する。Application Refは接続しない。
6. Version Get / FullName / Version Ref CloseのどこかでVersion系errorが発生しても、そのerrorをPhase 1 mandatory chainへ接続しない。
7. Version取得成功時は `Version String = Version String Candidate`、取得失敗時は `Version String = ""` とする。
8. `Version String = ""` の場合は `Version Recognized? = False` とする。

**重要**：Version取得失敗を `Unsupported` や `-710101` に変換しない。

---

# 3.3 STEP 3: Version FullNameを完全一致で判定する

1. `Version String` が空でないcaseだけでVersion recognitionを行う。
2. `Known Version Full Names[]` を一次元配列を検索（Search 1D Array）のarray入力へ接続する。
3. `Version String` をelement入力へ接続する。
4. Search結果indexとI32定数 `-1` を比較する。
5. `index != -1` を `Version Recognized?` として扱う。
6. Known Version配列がempty、またはVersion StringがemptyならFalseを返す。

Contains、Match Pattern、部分一致だけで `Compatible` を判定しない。

---

# 3.4 STEP 4: Phase 1 System capability

1. mandatory probe用error chainはVersion errorからではなく、False caseへ入った時点のoriginal incoming no-errorから開始する。
2. `CANalyzer.IApplication10` を `CAN_AX_Get_System.vi` のApplication Refへ接続する。
3. mandatory error chainを `CAN_AX_Get_System.vi.error in` へ接続する。
4. `CAN_AX_Get_System.vi.error out.status` がTrueかをCase Structureで判定する。
5. failure時は `Failed Capability = "System"` とし、`CANalyzer_Compatibility_Status = Unsupported`、`Capability Probe Passed? = False` を返す。
6. 元errorのcode/sourceを取り出し、#3.10の共通パターンで `-710101` へ正規化する。
7. System Refを取得できたsuccess pathだけ次へ進む。

---

# 3.5 STEP 5: Phase 1 Measurement capability

1. `CANalyzer.IApplication10` を `CAN_AX_Get_Measurement.vi` のApplication Refへ接続する。
2. System成功後のmandatory error chainを `CAN_AX_Get_Measurement.vi.error in` へ接続する。
3. Measurement failureを専用Caseで判定する。
4. failure時は `Failed Capability = "Measurement"`、Status=`Unsupported`、Probe=False、error=`-710101` とする。
5. System Refを取得済みの場合はfailure cleanupでSystem RefをCloseする。
6. success時だけMeasurement Refを次へ渡す。

---

# 3.6 STEP 6: Phase 1 Running capability

1. Measurement Refを `CAN_AX_Get_Measurement_Running.vi` のMeasurement Refへ接続する。
2. Measurement成功後のmandatory error chainを同SubVIの`error in`へ接続する。
3. Running Booleanの値そのものはCompatibility failure条件にしない。ここで確認するのは `Running` Propertyを正常に読めることである。
4. `CAN_AX_Get_Measurement_Running.vi.error out.status=True` の場合だけRunning capability failureとする。
5. failure時は `Failed Capability = "Running"`、Status=`Unsupported`、Probe=False、error=`-710101` とする。
6. failure後はMeasurement Ref、System Refの順でcleanupする。

---

# 3.7 STEP 7: Phase 1 temporary refsを解放し、Phase 2 gateへ進む

Phase 1で取得したSystem / Measurement RefはPhase 2へ持ち越さない。Phase 2ではConfiguration確認後の状態を再確認するため再取得する。

1. Phase 1成功後、Measurement Ref → System Refの順でCloseする。
2. Closeはoperation errorとは独立したcleanup error chainで実行する。
3. `Enable Configuration-Dependent Probe?` をCase Structureのselectorへ接続する。
4. False caseでは次を返す。

| 出力 | 値 |
|---|---|
| `CANalyzer_Compatibility_Status` | `Unknown` |
| `Capability Probe Passed?` | True |
| `Version Recognized?` | Version判定結果 |
| `Version String` | Version取得結果 |
| `Failed Capability` | `""` |
| `エラー出力` | Phase 1 operation/cleanup統合結果 |

**Phase 1成功だけで `Compatible` または `Compatible with Warning` を返さない。**

5. True caseではPhase 2入力検証へ進む。

---

# 3.8 STEP 8: Phase 2 Probe入力をtrimして検証する

1. `Probe Namespace` を空白文字を削除（Trim Whitespace）へ接続し、出力を `Trimmed Namespace` とする。
2. `Probe Variable Name` を別のTrim Whitespaceへ接続し、出力を `Trimmed Variable Name` とする。
3. `Trimmed Namespace` がemptyの場合は本処理へ進まず次を返す。

```text
Status = Unknown
Capability Probe Passed? = False
Failed Capability = Probe Input
error.code = -710113
error.source = CANalyzer_Check_Compatibility.vi / Invalid Probe Namespace
```

4. Namespaceが有効な場合だけVariable Nameを検証する。
5. `Trimmed Variable Name` がemptyの場合は次を返す。

```text
Status = Unknown
Capability Probe Passed? = False
Failed Capability = Probe Input
error.code = -710113
error.source = CANalyzer_Check_Compatibility.vi / Invalid Probe Variable Name
```

6. 以降のResolveには元の入力ではなく `Trimmed Namespace` / `Trimmed Variable Name` を使用する。

入力不正はCANalyzer capability failureではないため `Unsupported` / `-710101` に変換しない。

---

# 3.9 STEP 9: Phase 2でSystem / Measurement / Runningを再確認する

Phase 2はConfiguration-dependent probeの直前状態を確認する。Phase 1 Refを再利用せず、Application Refから再取得する。

1. `CANalyzer.IApplication10` → `CAN_AX_Get_System.vi.Application Ref` と接続する。
2. success時のSystem RefをPhase 2 System Refとして扱う。
3. System failureは `Failed Capability = "System"`、Status=`Unsupported`、Probe=False、error=`-710101` とする。
4. `CANalyzer.IApplication10` → `CAN_AX_Get_Measurement.vi.Application Ref` と接続する。
5. Measurement failureは `Failed Capability = "Measurement"`、Status=`Unsupported`、Probe=False、error=`-710101` とする。
6. Measurement Ref → `CAN_AX_Get_Measurement_Running.vi.Measurement Ref` と接続する。
7. Running Property read failureは `Failed Capability = "Running"`、Status=`Unsupported`、Probe=False、error=`-710101` とする。
8. 各failure pathでは、その時点までに取得済みのtemporary Refだけをcleanupする。

---

# 3.10 STEP 10: mandatory capability errorを `-710101` へ正規化する

System、Measurement、Running、Resolve SysVar、Read SysVar、Type Conversionのfailureは同じpublic contractへ揃える。

1. 元error clusterからcodeとsourceを名前でバンドル解除（Unbundle By Name）で取り出す。
2. 文字列にフォーマット（Format Into String）へ次を接続する。

```text
Format:
CANalyzer_Check_Compatibility.vi / Required Capability Missing
Capability=%s
OriginalCode=%d
OriginalSource=%s
```

3. `%s`へ正確なCapability名を接続する。
4. `%d`へ元error codeを接続する。
5. 最後の`%s`へ元error sourceを接続する。
6. 名前でバンドル（Bundle By Name）で最終error clusterを作る。

| field | 値 |
|---|---|
| `status` | True |
| `code` | I32 `-710101` |
| `source` | Format Into String出力 |

Capability名は次の文字列へ固定する。

```text
System
Measurement
Running
Resolve SysVar
Read SysVar
Type Conversion
```

旧名称 `Probe Resolve`、`Probe Read`、`Probe Type Conversion` は使用しない。

---

# 3.11 STEP 11: Known SysVarをResolveする

1. Phase 2 System Refを `CANalyzer_Resolve_SysVar.vi.System Ref` へ接続する。
2. `Trimmed Namespace` を `Namespace` へ接続する。
3. `Trimmed Variable Name` を `Variable Name` へ接続する。
4. Phase 2 Running成功後のerror chainを `CANalyzer_Resolve_SysVar.vi.error in` へ接続する。
5. Resolve成功時のVariable Refを `Probe Variable Ref` として扱う。
6. Resolve failure時は後段Read / Type Conversionを実行しない。
7. Resolve failure時は次を返す。

```text
Status = Unsupported
Capability Probe Passed? = False
Failed Capability = Resolve SysVar
error.code = -710101
```

8. normalized sourceの `Capability=` も `Resolve SysVar` とする。
9. failure pathではMeasurement Ref / System Refを取得済みならcleanupする。Variable Refを取得できていないpathでは無効Refを無理にCloseしない。

---

# 3.12 STEP 12: Known SysVarをreadする

1. `Probe Variable Ref` を `CAN_AX_Read_Variable_Value.vi.Variable Ref` へ接続する。
2. Resolve成功後のerror chainを `CAN_AX_Read_Variable_Value.vi.error in` へ接続する。
3. 出力Variantを `Probe Value Variant` として扱う。
4. Read failure時はType Conversionへ進まない。
5. Read failure時は次を返す。

```text
Status = Unsupported
Capability Probe Passed? = False
Failed Capability = Read SysVar
error.code = -710101
```

6. normalized sourceの `Capability=` も `Read SysVar` とする。
7. failure pathではVariable Ref → Measurement Ref → System Refの順でcleanupする。

SysVar値そのものの期待値比較は行わない。ここで確認するのは「Resolveできる」「Readできる」である。

---

# 3.13 STEP 13: Variantを期待型へ変換する

1. `Probe Value Variant` を `CANalyzer_Variant_To_Value.vi.Variant` 入力へ接続する。
2. `CANalyzer_Value_Type` を同SubVIのExpected Value Type入力へ接続する。
3. Read成功後のerror chainを同SubVIの`error in`へ接続する。
4. 変換後Value自体はCompatibility判定に使用しなくてよい。変換可能であることを確認する。
5. Type Conversion failure時は次を返す。

```text
Status = Unsupported
Capability Probe Passed? = False
Failed Capability = Type Conversion
error.code = -710101
```

6. `CANalyzer_Variant_To_Value.vi` が `-710106` 等を返しても、最終codeは `-710101` へ正規化し、元code/sourceはnormalized sourceへ保持する。
7. normalized sourceの `Capability=` も `Type Conversion` とする。
8. failure pathではVariable Ref → Measurement Ref → System Refの順でcleanupする。

---

# 3.14 STEP 14: Phase 2成功後の最終Compatibilityを決める

Phase 2 mandatory probesが全て成功した場合だけ最終Compatibilityを決定する。

| 条件 | `CANalyzer_Compatibility_Status` | `Capability Probe Passed?` |
|---|---|---:|
| `Version String = ""` | `Unknown` | True |
| Version Stringあり + `Version Recognized? = True` | `Compatible` | True |
| Version Stringあり + `Version Recognized? = False` | `Compatible with Warning` | True |

成功時は `Failed Capability = ""`、operation errorはNo Errorとする。

---

# 3.15 STEP 15: temporary Refをcleanupする

Ref所有権は次のとおり固定する。

| Ref | Owner | 本VIでClose |
|---|---|---|
| Application Ref | caller | **しない** |
| Version Ref | 本VI temporary | FullName取得後にClose |
| Phase 1 System Ref | 本VI temporary | Phase 1終了時にClose |
| Phase 1 Measurement Ref | 本VI temporary | Phase 1終了時にClose |
| Phase 2 System Ref | 本VI temporary | path終了時にClose |
| Phase 2 Measurement Ref | 本VI temporary | path終了時にClose |
| Variable Ref | 本VI temporary | Read/Convert後またはfailure cleanupでClose |

Phase 2で複数Refを取得済みの場合のClose順は次とする。

```text
Variable Ref
  ↓
Measurement Ref
  ↓
System Ref
```

取得できていないRefを無条件Closeしない。pathごとに取得済みRefだけをCloseする。

---

# 3.16 STEP 16: Cleanup ErrorをOperation Errorと独立させる

operation errorをClose Referenceへそのまま入れると、一般的なerror-in動作によってcleanup処理がskipされる可能性がある。したがってcleanup用error chainをoperation chainから分離する。

1. operation処理で確定したerror clusterを `Operation Error` として保持する。
2. エラーをクリア（Clear Errors）またはNo Error clusterを使い、cleanup専用error chainをNo Error状態から開始する。
3. 取得済みRefをClose順に接続する。
4. 最後のClose Referenceのerror outを `Cleanup Error` とする。
5. 最終errorは次の優先順位で選択する。

```text
Operation Error.status = True
  → Final Error = Operation Error

Operation Error.status = False
  → Final Error = Cleanup Error
```

これにより4ケースは次になる。

| Operation | Cleanup | `error out` |
|---|---|---|
| success | success | No Error |
| success | failure | Cleanup Error |
| failure | success | Operation Error |
| failure | failure | Operation Error |

Cleanup Errorで `-710101` や `-710113` を上書きしない。一方、operation成功時のClose-only errorを捨てない。

---

# 3.17 STEP 17: forbidden side effectがないことを確認する

本VIへ次のSubVI / 処理を配置しない。

| 禁止項目 |
|---|
| `CAN_AX_Open_Configuration.vi` |
| `CAN_AX_Start_Measurement.vi` |
| `CAN_AX_Stop_Measurement.vi` |
| `CAN_AX_Write_Variable_Value.vi` |
| `CAN_AX_Quit_Application.vi` |
| Application RefのClose Reference |
| Session Registry Create / Update / Remove |

---

# 4. 単体テスト・Static Acceptance

実機を使わない静的ReviewではBlock Diagram上の分岐とerror mappingを追跡する。実機Runtime確認時は同じケースを、実際に発生可能な条件へ置き換えて確認する。

| Case | 条件 | 期待結果 |
|---:|---|---|
| 1 | incoming error | Unknown / Probe=False / original error / ActiveX処理なし |
| 2 | Version failure + Phase 1 mandatory PASS + Phase 2=False | Unknown / Probe=True / Version=`""` / Recognized=False / error=False |
| 3 | System failure | Unsupported / Failed=`System` / `-710101` |
| 4 | Measurement failure | Unsupported / Failed=`Measurement` / `-710101` |
| 5 | Running Property read failure | Unsupported / Failed=`Running` / `-710101` |
| 6 | Namespace trim後empty | Unknown / Failed=`Probe Input` / `-710113` / Invalid Probe Namespace |
| 7 | Variable trim後empty | Unknown / Failed=`Probe Input` / `-710113` / Invalid Probe Variable Name |
| 8 | Resolve failure | Unsupported / Failed=`Resolve SysVar` / `-710101` |
| 9 | Read failure | Unsupported / Failed=`Read SysVar` / `-710101` |
| 10 | Type Conversion failure | Unsupported / Failed=`Type Conversion` / `-710101` |
| 11 | Phase 2 PASS + Version Stringあり + 未登録Version | Compatible with Warning / Probe=True / no error |
| 12 | Phase 2 PASS + Known Version exact match | Compatible / Probe=True / no error |
| 13 | Phase 2 PASS + Version取得不可 | Unknown / Probe=True / no error |
| 14 | operation success + cleanup failure | final error = Cleanup Error |
| 15 | operation failure + cleanup failure | final primary error = Operation Error |

推奨プローブ位置：

- Version optional chainのerror outとmandatory chain開始error
- `Version String` / `Version Recognized?`
- Phase 1 System / Measurement / Running各error out
- `Trimmed Namespace` / `Trimmed Variable Name`
- Resolve / Read / Type Conversion各error out
- `Operation Error`
- `Cleanup Error`
- 最終 `error out`

---

# 5. Error Codeと診断文字列

## 5.1 Required Capability Missing

```text
status = True
code   = -710101
source = CANalyzer_Check_Compatibility.vi / Required Capability Missing
         Capability=<Capability Name>
         OriginalCode=<original code>
         OriginalSource=<original source>
```

Capability Nameは次へ固定する。

```text
System
Measurement
Running
Resolve SysVar
Read SysVar
Type Conversion
```

## 5.2 Invalid Probe Configuration

Namespace不正：

```text
status = True
code   = -710113
source = CANalyzer_Check_Compatibility.vi / Invalid Probe Namespace
```

Variable Name不正：

```text
status = True
code   = -710113
source = CANalyzer_Check_Compatibility.vi / Invalid Probe Variable Name
```

どちらも `Compatibility Status = Unknown`、`Capability Probe Passed? = False`、`Failed Capability = Probe Input` とする。

---

# 6. Source / Version / Verified by / State

| 項目 | 記録 |
|---|---|
| Source | 対象PCに登録されたCANalyzer Type Library、既存Wrapper Connector Pane、NI LabVIEW ActiveX / Close Reference一般仕様、本リポジトリ確定設計 |
| Version | CANalyzer 12.0 Type Library Version 1.3bを実装確認時の型情報として使用。Application Version判定にはType Library Versionを流用しない |
| Symbol | `CANalyzer_Check_Compatibility.vi`、`CAN_AX_Get_Version.vi`、`CAN_AX_Get_Version_FullName.vi`、`CAN_AX_Get_System.vi`、`CAN_AX_Get_Measurement.vi`、`CAN_AX_Get_Measurement_Running.vi`、`CANalyzer_Resolve_SysVar.vi`、`CAN_AX_Read_Variable_Value.vi`、`CANalyzer_Variant_To_Value.vi` |
| Signature | 本章 #1 の7 Inputs / 6 Outputs、Phase 2 SysVar Readはread-only |
| Verified by | Nigel AI Read-Only Focused As-Built Review + Final Closure Spot Check、人手修正後の完全Close確認 |
| State | **As-Built Confirmed / Design Alignment PASS / P0=0 / P1=0** |

CANalyzer Application VersionのKnown Version一覧は実機運用で採用値を与える。Type Library Version `1.3b` をApplication Version文字列として比較しない。

---

# 7. 作成完了チェックリスト

- [ ] incoming error時はActiveX処理を実行しない。
- [ ] Version probe errorがPhase 1 mandatory probeを止めない。
- [ ] Version判定はFullName完全一致である。
- [ ] Phase 1 System / Measurement / Runningが個別にfailure判定される。
- [ ] Phase 1 only成功時のStatusは `Unknown` である。
- [ ] Phase 2入力はtrim後に検証し、trim後文字列をResolveへ渡す。
- [ ] Phase 2でもSystem / Measurement / Runningを再確認する。
- [ ] Resolve / Read / Type Conversionが個別にfailure判定される。
- [ ] mandatory failureは `-710101` に正規化する。
- [ ] Failed Capabilityとnormalized sourceのCapability名が一致する。
- [ ] Invalid Namespace / Variable Nameは `-710113` とし、`Unsupported`にしない。
- [ ] Application RefをCloseしない。
- [ ] temporary Refを取得済みpathだけCloseする。
- [ ] Cleanup error chainをoperation errorから独立させる。
- [ ] operation成功 + cleanup失敗でCleanup Errorが外へ出る。
- [ ] operation失敗 + cleanup失敗でOperation Errorが優先される。
- [ ] SysVar Write / Start / Stop / Configuration Open / Registry変更を行わない。
- [ ] Connector Paneの7 Inputs / 6 Outputsを維持する。
- [ ] `CANalyzer_Value_Type.ctl` と `CANalyzer_Compatibility_Status.ctl` のtypedef linkを人手で確認する。
- [ ] Broken Run ArrowがないことをLabVIEW上で確認する。

---

# 8. As-Built Notes

2026-08-21時点の最終Closureでは、次を確認済みとする。

- Optional Version error isolation：CLOSED
- Phase 1 System / Measurement / Running failure handling：CLOSED
- Phase 1 success Status=`Unknown`：CLOSED
- Invalid Namespace / Variable source分離：CLOSED
- trimmed Namespace / Variable usage：CLOSED
- Resolve / Read / Type Conversion failure separation：CLOSED
- `-710101` normalization：CLOSED
- Capability名 `Resolve SysVar / Read SysVar / Type Conversion`：CLOSED
- Connector Pane：CLOSED
- Cleanup error isolation / final priority `Operation Error > Cleanup Error`：CLOSED
- Application Ref ownership：CLOSED
- Final Compatibility mapping：CLOSED

**最終状態：`CANalyzer_Check_Compatibility.vi` = AS-BUILT CONFIRMED。**
