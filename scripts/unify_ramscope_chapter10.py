from pathlib import Path
import re

DOC = Path("docs/10_RAMScope実装方針.md")
TEMP_PATHS = [
    Path("scripts/unify_ramscope_chapter10.py"),
    Path(".github/workflows/unify-ramscope-chapter10.yml"),
    Path("scripts/extract_ch10_structure.py"),
    Path(".github/workflows/extract-ch10-structure.yml"),
    Path("docs/ch10-structure.txt"),
]

text = DOC.read_text(encoding="utf-8")


def split_top_sections(src: str):
    pat = re.compile(r"(?m)^## 10\.(\d+)(?!\.)\s+.*$")
    matches = list(pat.finditer(src))
    if not matches:
        raise RuntimeError("Top-level chapter 10 sections were not found")
    prefix = src[: matches[0].start()]
    result = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(src)
        result[int(match.group(1))] = src[match.start():end].rstrip() + "\n"
    return prefix, result


def body(section: str) -> str:
    return section.split("\n", 1)[1].lstrip("\n") if "\n" in section else ""


def split_13_parts(section: str):
    pat = re.compile(r"(?m)^#{2,3}\s+10\.13\.(\d+)(?!\.)\s+.*$")
    matches = list(pat.finditer(section))
    result = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(section)
        result[int(match.group(1))] = section[match.start():end].rstrip() + "\n"
    return result


def exact_subsection(section: str, number: str) -> str:
    start_re = re.compile(rf"(?m)^###\s+10\.13\.{re.escape(number)}\s+.*$")
    start = start_re.search(section)
    if not start:
        raise RuntimeError(f"Subsection 10.13.{number} was not found")
    next_re = re.compile(r"(?m)^###\s+10\.13\.\d+(?:\.\d+)+\s+.*$")
    next_match = next_re.search(section, start.end())
    end = next_match.start() if next_match else len(section)
    return section[start.start():end].rstrip() + "\n"


def replace_required(src: str, pattern: str, replacement: str, flags=0, label="target") -> str:
    compiled = re.compile(pattern, flags)
    result, count = compiled.subn(replacement, src, count=1)
    if count != 1:
        raise RuntimeError(f"Expected one replacement for {label}, got {count}")
    return result


prefix, sections = split_top_sections(text)
required = set(range(1, 14))
missing = sorted(required.difference(sections))
if missing:
    raise RuntimeError(f"Missing top-level sections: {missing}")

parts13 = split_13_parts(sections[13])
for num in range(1, 12):
    if num not in parts13:
        raise RuntimeError(f"Missing 10.13.{num}")

mods13 = {num: exact_subsection(parts13[3], f"3.{num}") for num in range(1, 7)}

# Header and chapter policy: the unified procedure, not a later appendix, is the source of truth.
prefix = prefix.replace("**最終整理日：2026-07-22**", "**最終整理日：2026-07-23**")
prefix = prefix.replace(
    "> 既存の`PoC_RAMScope_Main.vi`は通信確認用PoCとして維持する。測定停止後の保存ログ回収、TDMS保存および欠落検証は、別構成の`PoC_RAMScope_Logging_Main.vi`で検証する。ロギング機能の追加・修正対象は10.13を正本とする。",
    "> 本章は環境準備からctl、共通VI、薄いDLL Wrapper、公開API、TDMS保存VI、通信確認PoC、ロギングPoCまでを一つの作成順で説明する。既存VIのロギング対応も各VIの既存手順へ統合し、後段の修正付録を正本としない。",
)

sections[2] = sections[2].replace(
    "本章では既存ファイルを維持しつつ、10.13で確定したロギング用Wrapper、公開API、TDMS保存VIおよび専用PoCを追加する。通信確認用PoCとロギング用PoCは統合しない。",
    "本章では既存ファイルとロギング追加ファイルを完成時の構成として同じ作成順へ並べる。通信確認用PoCとロギング用PoCは別VIとするが、作成手順は10.5の一本化フローを正本とする。",
)

# 10.5: master sequence + confirmed logging specification + existing audit content.
logging_specs = body(parts13[2])
logging_specs = logging_specs.replace("10.13.2.1", "10.5.3.1").replace("10.13.2.2", "10.5.3.2").replace("10.13.2.3", "10.5.3.3")
old5 = body(sections[5])
old5 = replace_required(
    old5,
    r"(?ms)\| `-700120` \| `Parse_SYSINFO_Array\.vi`.*?\| `-700160` \| `RAMScope_Read\.vi` \| MaxDataNumまたは計算Bufferサイズ不正 \|",
    """| `-700120` | `Parse_SYSINFO_Array.vi` | SYSINFO Rawが960byteではない |
| `-700140` | `RAMScope_Init.vi` | RAMモジュール未検出 |
| `-700141` | `RAMScope_Init.vi` | PGT SlotErr非ゼロ |
| `-700150` | `RAMScope_Set_Cond.vi` | Builder出力サイズ不正 |
| `-700160` | `RAMScope_Parse_Buffer.vi` | Channel Sizeが0、1、2以外 |
| `-700161` | `RAMScope_Parse_Buffer.vi` | ChNum、DataNumまたはRaw Buffer長が不正 |
| `-700162` | `RAMScope_Read.vi` | AvailableDataNumが負数 |
| `-700163` | `RAMScope_Read.vi` | 必要Bufferサイズが不正または上限超過 |
| `-700164` | `RAMScope_Read.vi` | DataNumが要求範囲外 |
| `-700165` | `RAMScope_Read.vi` | Parsed Packet CountとDataNumが不一致 |
| `-700170` | `RAMScope_Get_Log_Summary.vi` | MeasNumが負数 |
| `-700171` | `RAMScope_Get_Block_Count.vi` | MeasNoが負数 |
| `-700172` | `RAMScope_Get_Block_Count.vi` | BlockNumが負数 |
| `-700173`～`-700177` | `RAMScope_Read_Logging_Block.vi` | 入力、件数、Bufferサイズ、Parser整合性が不正 |
| `-700178` | `RAMScope_File_Log_Open.vi` | 既存ファイル上書き禁止 |
| `-700180` | `RAMScope_File_Log_Append.vi` | Packet件数とDataNumが不一致 |""",
    flags=re.M | re.S,
    label="local error code table",
)

master5 = r'''## 10.5 一本化した作成順・確定仕様・監査結果

### 10.5.1 一本化方針

本章では「通信確認用の既存手順」と「ロギング対応の修正手順」を分けない。各ファイルは、最初からロギング対応を含む最終形で作成または修正する。

```text
環境確認
  → ctlを最終形で作成
  → 共通変換・Builder・Parserを作成
  → 薄いDLL WrapperをAPI呼出順で作成
  → 公開APIを機器操作順で作成
  → TDMS保存VIを作成
  → 通信確認PoCを回帰確認
  → ロギングPoCを作成
  → 結合試験・TestStand組込み
```

- `RAMScope_Packet.ctl`は、後からFlag項目を追加するのではなく、10.6の最終フィールドで作成する。
- `RAMScope_Parse_Buffer.vi`と`RAMScope_Read.vi`は、旧版を作成してからロギング用に直すのではなく、10.10と10.11の最終アルゴリズムで作成する。
- 追加Wrapperと追加公開APIは別付録へ置かず、既存ファイルと同じレイヤの作成順へ組み込む。
- `PoC_RAMScope_Main.vi`は通信確認用として残し、`PoC_RAMScope_Logging_Main.vi`は別VIとして作る。

### 10.5.2 完成までの一連の作成順

#### Phase 0：環境とCLFN疎通

1. 10.4に従って64bit環境、DLL配置、依存DLL、DeviceInitのCLFN疎通を確認する。
2. `RAMScope_Code_To_Error.vi`を作り、以降のWrapperで共通使用する。

#### Phase 1：ctlを最終形で作成

3. `RAMScope_Byte_Order.ctl`
4. `RAMScope_Meas_Config.ctl`
5. `RAMScope_Channel.ctl`
6. `RAMScope_Module_Log_Config.ctl`
7. `RAMScope_Module_Info.ctl`
8. `RAMScope_Channel_Value.ctl`
9. `RAMScope_Packet.ctl`。Flag Raw、Status、Skip、Log Trigger、Dummy、Event Bits、Data Lost、Timestampを最初から含める。
10. `RAMScope_PoC_State.ctl`
11. `RAMScope_Logging_PoC_State.ctl`

#### Phase 2：共通変換・Builder・Parser

12. `U8x4_To_U32.vi`、`U8x4_To_I32.vi`、`U8x8_To_U64.vi`
13. `U32_To_LE_U8x4.vi`、`I32_To_LE_U8x4.vi`
14. `Build_MEASINFO_170_Raw.vi`、`Build_CHINFO_170_Raw.vi`、`Build_LOGINFO_Raw.vi`
15. `Parse_SYSINFO_Array.vi`
16. `RAMScope_Parse_Buffer.vi`を10.10の最終仕様で作成する。Size別復号、Flag分解、I64サイズ検証を含める。

#### Phase 3：薄いDLL WrapperをAPI呼出順で作成

17. 接続・初期化：`DeviceInit`、`AllInit`、`GetSysInfo`、`PGT_SetMdlConfig`
18. 条件設定：`SetMeasCond`、`SetMeasCh`、`SetLoggingInfo`
19. 測定開始・オンライン読出し：`MeasStart`、`GetBufferDataNum`、`GetBufferData`
20. 停止後ログ列挙：`MeasStop`、`GetGapTime`、`GetMeasNum`、`GetBlockNum`
21. 保存ログ読出し：`GetLoggingDataNum`、`GetLoggingData`
22. 後処理：`ReleaseBufferData`、`DeviceExit`

全WrapperはC関数1個をCLFNで1回だけ呼ぶ。通常Wrapperは既存error時にDLLを呼ばず、安全値と元errorを返す。

#### Phase 4：公開APIを機器操作順で作成

23. `RAMScope_Connect.vi`
24. `RAMScope_Init.vi`
25. `RAMScope_Set_Cond.vi`
26. `RAMScope_Log_Start.vi`
27. `RAMScope_Read.vi`
28. `RAMScope_Log_Stop.vi`
29. `RAMScope_Get_Log_Summary.vi`
30. `RAMScope_Get_Block_Count.vi`
31. `RAMScope_Read_Logging_Block.vi`
32. `RAMScope_Release.vi`
33. `RAMScope_Close.vi`

#### Phase 5：TDMSとPoC

34. `RAMScope_File_Log_Open.vi`
35. `RAMScope_File_Log_Write_Metadata.vi`
36. `RAMScope_File_Log_Append.vi`
37. `RAMScope_File_Log_Close.vi`
38. 既存`PoC_RAMScope_Main.vi`で通信・オンライン読出しの回帰確認を行う。
39. `PoC_RAMScope_Logging_Main.vi`を作成し、Stop後のMeasNo／BlockNo列挙、1Block単位のRead→Parse→Append、Cleanupを確認する。
40. TestStand組込み、TDMS再読込、MF4変換前提のメタデータ確認を行う。

### 10.5.3 ロギング対応で確定したAPI・Packet仕様

''' + logging_specs + r'''

### 10.5.4 監査結果と既存仕様

''' + old5
sections[5] = master5.rstrip() + "\n"

# 10.6: integrate final ctl definitions into the ctl section.
packet_ctl = mods13[1]
packet_ctl = re.sub(r"(?m)^### 10\.13\.3\.1 .*?$", "### 10.6.6 `RAMScope_Packet.ctl`の最終作成手順", packet_ctl, count=1)
logging_state = r'''
### 10.6.7 `RAMScope_Logging_PoC_State.ctl`の作成手順

#### 0. 責務

ロギングPoCで、どのCleanupが必要か、保存ログ取得がどこまで完了したかを1本の状態クラスタで保持する。

#### 1. フィールド

```text
Connected?             Boolean False
File Open?             Boolean False
Measurement Started?   Boolean False
Stopped?               Boolean False
Log Summary Read?      Boolean False
Logging Retrieved?     Boolean False
Released?              Boolean False
```

#### 2. 作成順

1. 新規カスタム制御器へClusterを配置する。
2. 上記Booleanを記載順で配置し、既定値をすべてFalseにする。
3. typedefへ変更する。
4. `30_RAMScope\00_Common\RAMScope_Logging_PoC_State.ctl`として保存する。
5. 通信確認用`RAMScope_PoC_State.ctl`は変更せず、ロギングPoCだけで使用する。

#### 3. 更新元

| フィールド | Trueへ更新する条件 |
|---|---|
| Connected? | `RAMScope_Connect.vi`正常終了 |
| File Open? | `RAMScope_File_Log_Open.vi`正常終了 |
| Measurement Started? | `RAMScope_Log_Start.vi`正常終了 |
| Stopped? | 通常またはCleanupのStop成功 |
| Log Summary Read? | `RAMScope_Get_Log_Summary.vi`正常終了 |
| Logging Retrieved? | 全MeasNo／BlockNoのReadとAppendが正常終了 |
| Released? | `RAMScope_Release.vi`正常終了 |

#### 4. 単体確認

Bundle By Nameで1項目だけ更新しても、他項目が入力クラスタの値を維持することを確認する。
'''
sections[6] = sections[6].rstrip() + "\n\n---\n\n" + packet_ctl.strip() + "\n\n---\n\n" + logging_state.strip() + "\n"

# 10.8: existing and logging wrappers in one layer. Replace GetBufferData with its final procedure.
sec8 = sections[8]
sec8 = sec8.replace("## 10.8 薄いDLLラッパVI 12個", "## 10.8 薄いDLLラッパVI 18個")
sec8 = sec8.replace("本書は薄いDLL Wrapper 12個の監査済み索引である。", "本節は既存12個とロギング追加6個、合計18個の薄いDLL Wrapperを同じ規則で作成する。")
sec8 = sec8.replace("#### 2. 12個の個別手順", "#### 2. 既存12個と追加6個の作成順")
sec8 = sec8.replace("### 10.8.2 各Wrapperの省略しない作成手順", "### 10.8.2 既存Wrapperの省略しない作成手順")
get_buffer_final = mods13[3]
get_buffer_final = re.sub(r"(?m)^### 10\.13\.3\.3 .*?$", "### 12. `RS_DLL_GT150GetBufferData.vi`（最終仕様）", get_buffer_final, count=1)
sec8 = replace_required(
    sec8,
    r"(?ms)^### 12\. `RS_DLL_GT150GetBufferData\.vi`.*?(?=^### 13\.)",
    get_buffer_final.rstrip() + "\n\n",
    label="GetBufferData wrapper section",
)
new_wrappers = body(parts13[4]).replace("10.13.4", "10.8.3")
wrapper_order = r'''
### 10.8.0 全18 Wrapperの機器操作順

```text
接続・初期化
  DeviceInit → AllInit → GetSysInfo → PGT_SetMdlConfig
条件設定
  SetMeasCond → SetMeasCh → SetLoggingInfo
開始・オンライン読出し
  MeasStart → GetBufferDataNum → GetBufferData
停止後保存ログ
  MeasStop → GetGapTime → GetMeasNum → GetBlockNum
  → GetLoggingDataNum → GetLoggingData
後処理
  ReleaseBufferData → DeviceExit
```

この順序はMain VIの呼出順を示す。各Wrapper自体は前後の機器操作を内包しない。
'''
sec8 = sec8.replace("### 10.8.1 現行補正と一覧", wrapper_order.strip() + "\n\n### 10.8.1 現行補正と一覧", 1)
sec8 = sec8.rstrip() + "\n\n---\n\n### 10.8.3 ロギング取得用Wrapperの作成手順\n\n" + new_wrappers.strip() + "\n"
sections[8] = sec8

# 10.10: replace the older Parse_Buffer procedure with the final integrated procedure.
sec10 = sections[10]
parser_final = mods13[2]
parser_final = re.sub(r"(?m)^### 10\.13\.3\.2 .*?$", "### 5. `RAMScope_Parse_Buffer.vi`（オンライン・保存ログ共通の最終仕様）", parser_final, count=1)
sec10 = replace_required(
    sec10,
    r"(?ms)^### 5\. `RAMScope_Parse_Buffer\.vi`.*?(?=^### 7\. 公開APIでの接続)",
    parser_final.rstrip() + "\n\n---\n\n",
    label="Parse Buffer section",
)
sections[10] = sec10

# 10.11: all 11 public APIs in one section. Replace Read and append the 3 logging APIs.
sec11 = sections[11]
sec11 = re.sub(r"(?m)^## 10\.11 .*?$", "## 10.11 公開API 11個", sec11, count=1)
sec11 = sec11.replace(
    "本節では、通信確認と基本測定に使用する既存`RAMScope_*`公開API 8個を、00Aの再現可能な配線手順と00Bの設計理由の両方で説明する。停止後保存ログ取得用の追加公開API 3個は10.13.5で説明する。",
    "本節では通信確認用8個と停止後保存ログ取得用3個、合計11個の`RAMScope_*`公開APIを機器操作順で説明する。",
)
sec11 = sec11.replace(
    "既存8個と追加3個の全公開APIは最後に`Error_To_TestStatus.vi`を1回だけ呼び、",
    "全11個の公開APIは最後に`Error_To_TestStatus.vi`を1回だけ呼び、",
)
read_final = mods13[4]
read_final = re.sub(r"(?m)^### 10\.13\.3\.4 .*?$", "#### `RAMScope_Read.vi`（GetBufferDataNum対応の最終仕様）", read_final, count=1)
read_pattern = re.compile(r"(?ms)^#### \d+\. `RAMScope_Read\.vi`.*?(?=^#### \d+\. `RAMScope_)")
sec11, count = read_pattern.subn(read_final.rstrip() + "\n\n", sec11, count=1)
if count != 1:
    raise RuntimeError(f"Expected one RAMScope_Read public API replacement, got {count}")

set_cond_note = """

> **ロギング対応を含む最終順序**：`SetMeasCond → SetMeasCh → SetLoggingInfo`を固定する。SetMeasCondまたはSetMeasChは内部Bufferを再構成するため、保存用`logSize`と表示用`BuffSize`を設定するSetLoggingInfoを最後に実行する。
"""
sec11 = replace_required(
    sec11,
    r"(?m)^(#### \d+\. `RAMScope_Set_Cond\.vi`.*)$",
    r"\1" + set_cond_note,
    label="Set Cond heading",
)
release_note = """

> **ロギング対応を含む呼出位置**：通信確認PoCではStop後に呼ぶ。ロギングPoCでは`Log Stop → 全MeasNo／BlockNo取得 → TDMS Append完了 → Release`の順とし、保存ログ取得前にBufferを破棄しない。
"""
sec11 = replace_required(
    sec11,
    r"(?m)^(#### \d+\. `RAMScope_Release\.vi`.*)$",
    r"\1" + release_note,
    label="Release heading",
)
new_public = body(parts13[5]).replace("10.13.5", "10.11.9")
public_order = r'''
### 10.11.0 全11公開APIの呼出順

```text
Connect → Init → Set Cond → Log Start → Read → Log Stop
→ Get Log Summary → Get Block Count → Read Logging Block
→ Release → Close
```

`Read`は測定中の表示Buffer、`Read Logging Block`はStop後の保存Bufferを扱う。両者は同じ`RAMScope_Parse_Buffer.vi`を使用する。
'''
sec11 = sec11.replace("---\n\n#### 1.", "---\n\n" + public_order.strip() + "\n\n---\n\n#### 1.", 1)
sec11 = sec11.rstrip() + "\n\n---\n\n### 10.11.9 停止後保存ログ取得用の追加公開API\n\n" + new_public.strip() + "\n"
sections[11] = sec11

# 10.12: TDMS is now a normal top-level implementation stage, not a logging appendix.
tdms = body(parts13[6]).replace("10.13.6", "10.12")
sections[12] = "## 10.12 LabVIEW側TDMS保存VI\n\n" + tdms.strip() + "\n"

# 10.13: both PoCs and TestStand in one sequence, while keeping the two PoCs as separate VIs.
comm_poc = body(sections[12])  # this currently refers to the overwritten section, so use the saved original below
# Recover original 10.12 from the source sections mapping before overwrite by re-splitting original text.
_, original_sections = split_top_sections(text)
comm_poc = body(original_sections[12])
logging_poc = body(parts13[7]).replace("10.13.7", "10.13.2")
completion = body(parts13[8]).replace("10.13.8", "10.13.4")
teststand = body(parts13[9]).replace("10.13.9", "10.13.3")
sections[13] = (
    "## 10.13 通信確認PoC・ロギングPoC・TestStand\n\n"
    "### 10.13.1 `PoC_RAMScope_Main.vi`\n\n"
    + comm_poc.strip()
    + "\n\n---\n\n### 10.13.2 `PoC_RAMScope_Logging_Main.vi`\n\n"
    + logging_poc.strip()
    + "\n\n---\n\n### 10.13.3 TestStand組込み順\n\n"
    + teststand.strip()
    + "\n\n---\n\n### 10.13.4 2つのPoCの完成条件\n\n"
    + completion.strip()
    + "\n"
)

# 10.14: verification only. The implementation order remains solely in 10.5.
actual_checks = body(parts13[10]).replace("10.13.10", "10.14.2")
sections[14] = r'''## 10.14 単体試験・実機PoC・完了判定

### 10.14.1 レイヤ別の合格順

```text
ctl既定値とtypedef反映
  → 共通変換・Builder・Parser単体試験
  → WrapperのCLFN設定と安全値バイパス
  → 公開APIの入力／戻り値検証
  → TDMS Open／Metadata／Append／Close
  → 通信確認PoC回帰
  → ロギングPoC結合
  → TDMS再読込
  → MF4変換前提確認
```

作成順は10.5.2だけを正本とし、本節では合否判定だけを扱う。

### 10.14.2 実機PoCで最終確認する項目

''' + actual_checks.strip() + r'''

### 10.14.3 完了条件

- [ ] 10.5.2の全Phaseが順番どおり完了している。
- [ ] 既存通信PoCがロギング追加後も回帰試験に合格する。
- [ ] ロギングPoCが全BlockをRead→Parse→Appendし、Release前に保存を完了する。
- [ ] API ReturnCode、ローカルerror、Packet Status、LostDataNumを別情報として追跡できる。
- [ ] TDMS再読込で全チャンネル長、Block数、Packet数、メタデータが一致する。
- [ ] 次フェーズのMF4変換に必要なName、Address、Size、Sign、Scale、Offset、Unit、Time、Flagを保持できる。
'''

# Compose in the new top-level order.
new_text = prefix
for number in range(1, 15):
    new_text += sections[number].rstrip() + "\n\n"

# Remove stale cross-references left by the former logging appendix.
replacements = {
    "10.13を正本": "10.5.2を正本",
    "10.13.3.1": "10.6.6",
    "10.13.3.2": "10.10",
    "10.13.3.3": "10.8",
    "10.13.3.4": "10.11",
    "10.13.3.5": "10.11",
    "10.13.3.6": "10.11",
    "10.13.4": "10.8.3",
    "10.13.5": "10.11.9",
    "10.13.6": "10.12",
    "10.13.7": "10.13.2",
    "10.13.8": "10.13.4",
    "10.13.9": "10.13.3",
    "10.13.10": "10.14.2",
    "10.13.11": "10.5.2",
}
for old, new in replacements.items():
    new_text = new_text.replace(old, new)

# Assertions: the former separate logging-modification appendix must be gone.
if "## 10.13.3 既存ctlと既存VIの修正" in new_text:
    raise RuntimeError("Former separate modification appendix still exists")
if "ロギング機能の追加・修正対象は10.13" in new_text:
    raise RuntimeError("Stale chapter policy remains")
if "## 10.12 `PoC_RAMScope_Main.vi`" in new_text:
    raise RuntimeError("Old top-level PoC section was not renumbered")

DOC.write_text(new_text.rstrip() + "\n", encoding="utf-8", newline="\n")
for path in TEMP_PATHS:
    path.unlink(missing_ok=True)
