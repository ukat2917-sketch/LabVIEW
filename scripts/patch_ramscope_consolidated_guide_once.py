from pathlib import Path

main_path = Path("docs/10_RAMScope実装方針.md")
rules_path = Path("docs/00A_LabVIEW実装資料の記述ルール.md")
learning_path = Path("docs/00B_LabVIEW学習型VI設計ルール.md")
workflow_path = Path(".github/workflows/patch-ramscope-consolidated-guide-once.yml")
script_path = Path("scripts/patch_ramscope_consolidated_guide_once.py")

text = main_path.read_text(encoding="utf-8")

old_close = '''#### 8. `RAMScope_Close.vi`

##### 0～5. 設計

前段エラーがあってもDeviceExitを試み、最初のエラーを失わないCleanup VI。DeviceExit Wrapperは元errorを保持したまま内部でClear Errors後にCLFNを実行する。

##### 6～8. 配線順

1. 本VIの`error in`を`Original Error`として分岐・保持する。
2. 同じ`error in`を`RS_DLL_GT150DeviceExit.vi`へ接続する。
3. Wrapperの`DeviceExit error`とOriginal Errorを2入力のCaseまたはMerge Errors相当処理へ接続する。
4. `Original Error.status=True`ならOriginal Errorを最終errorへ接続する。
5. `Original Error.status=False`ならDeviceExit errorを最終errorへ接続する。
6. 最終errorを`Error_To_TestStatus.vi`へ接続する。
7. Device Name=`RAMScope`とし、Status、TestError、error outを出力する。

##### 9. テスト

正常Close、既存エラー付きClose、DeviceExitエラー、二重Close、Close後の再Connectを確認する。
'''

new_close = '''#### 8. `RAMScope_Close.vi`

##### 0～5. 設計

前段エラーがあってもDeviceExitを試み、最初のエラーを失わないCleanup VIである。正式方式はエラーをマージ（Merge Errors）へ固定する。Case Structureまたは他の相当処理を選択肢として残さない。

##### 6～8. 配線順

1. 本VIの`error in`を2方向へ分岐する。
2. 1本目を`Original Error`として、エラーをマージ（Merge Errors）の**上側1個目のerror入力**へ接続する。
3. 2本目を`RS_DLL_GT150DeviceExit.vi / error in`へ接続する。
4. Wrapperの`DeviceExit error`をMerge Errorsの**下側2個目のerror入力**へ接続する。
5. Merge Errors出力を`Final Error`として`Error_To_TestStatus.vi / error in`へ接続する。
6. 文字列定数へ全文`RAMScope`を入力し、同SubVIの`Device Name`へ接続する。
7. `Error_To_TestStatus.vi / Status`を本VIの`Status`出力へ接続する。
8. 同SubVIの`TestError`を本VIの`TestError`出力へ接続する。
9. 同SubVIの`error out`を本VIの`error out`へ接続する。

```text
Original Error ───────────────→ Merge Errors 上側入力1
error in → DeviceExit Wrapper → Merge Errors 下側入力2
Merge Errors出力              → Error_To_TestStatus.vi
```

上側と下側を逆にしない。両方にエラーがある場合も、前段で最初に発生したOriginal Errorを保持する。

##### 9. テスト

正常Close、既存エラー付きClose、DeviceExitエラー、両方エラー、二重Close、Close後の再Connectを確認する。詳細な配置場所、全端子および期待結果は直後の`10.11.9`を使用する。
'''

old_poc_close = '''#### L. Closeの要否を判定する

1. Kの出力Stateから`Connected?`をUnbundle By Nameで取り出す。
2. `Connected?`をClose Case Structureのselectorへ接続する。

##### Falseケース（Connected?=False：DeviceInit未成功）

1. `RAMScope_Close.vi`を配置しない。
2. 入力errorを最終error出力へそのまま接続する。

##### Trueケース（Connected?=True：DeviceExitが必要）

1. `RAMScope_Close.vi`を配置する。
2. KのMerge Errors出力を`RAMScope_Close.vi / error in`へ接続する。
3. CloseのStatus、TestError、error outをPoCの最終出力へ接続する。

`RAMScope_Close.vi`は前段エラーを保持したままDeviceExitを試すため、このCase内ではClear Errorsを配置しない。

#### M. Final Stateを出力する

1. Close CaseのState入力ワイヤをCase右側のState出力トンネルへ接続する。
2. 両Caseで同じState型を接続する。
3. Case外のStateワイヤを`Final State`表示器へ接続する。
'''

new_poc_close = '''#### L. Closeの要否を判定し、最終4出力を作る

1. Kの出力Stateから`Connected?`を名前でバンドル解除（Unbundle By Name）で取り出す。
2. `Connected?`をClose Case Structureのselectorへ接続する。
3. Close Case右側へ、次の4個の出力トンネルを作る。

```text
Final State : RAMScope_PoC_State.ctl
Status      : Status.ctl
TestError   : TestError.ctl
Final Error : error cluster
```

##### Falseケース（Connected?=False：DeviceInit未成功）

1. `RAMScope_Close.vi`を配置しない。
2. Kの出力Stateを`Final State`出力トンネルへそのまま接続する。
3. `Error_To_TestStatus.vi`を配置する。
4. KのMerge Errors出力を`Error_To_TestStatus.vi / error in`へ接続する。
5. 文字列定数へ全文`RAMScope`を入力し、同SubVIの`Device Name`へ接続する。
6. 同SubVIの`Status`をClose Caseの`Status`出力トンネルへ接続する。
7. 同SubVIの`TestError`を`TestError`出力トンネルへ接続する。
8. 同SubVIの`error out`を`Final Error`出力トンネルへ接続する。

```text
K出力State ─────────────────────────→ Final State
K出力error → Error_To_TestStatus.vi ─┬→ Status
                                      ├→ TestError
                                      └→ Final Error
```

##### Trueケース（Connected?=True：DeviceExitが必要）

1. `RAMScope_Close.vi`を配置する。
2. Kの出力Stateを`Final State`出力トンネルへそのまま接続する。
3. KのMerge Errors出力を`RAMScope_Close.vi / error in`へ接続する。
4. Closeの`Status`をClose Caseの`Status`出力トンネルへ接続する。
5. Closeの`TestError`を`TestError`出力トンネルへ接続する。
6. Closeの`error out`を`Final Error`出力トンネルへ接続する。
7. このCase内にはエラークリア（Clear Errors）を配置しない。

```text
K出力State ───────────────────→ Final State
K出力error → RAMScope_Close.vi ─┬→ Status
                                 ├→ TestError
                                 └→ Final Error
```

#### M. Close Case外からPoCの最終出力へ接続する

1. Close Caseの`Final State`出力をPoCの`Final State`表示器へ接続する。
2. Close Caseの`Status`出力をPoCの`Status`表示器へ接続する。
3. Close Caseの`TestError`出力をPoCの`TestError`表示器へ接続する。
4. Close Caseの`Final Error`出力をPoCの`error out`表示器およびコネクタペーン端子へ接続する。
5. True／False両ケースで4個の出力トンネルがすべて配線されていることを確認する。
'''

old_wait = '''#### F. WaitとRead

1. `RAMScope_Log_Start.vi / error out`を`RAMScope_Read.vi / error in`へ接続する前に、待機（Wait (ms)）を必要なデータフローへ組み込む。
2. `RAMScope_Read.vi`からRaw Buffer、DataNum、LostDataNum、Packetsを各表示器へ接続する。
3. `State After Start`は変更せず、Stop後の状態更新位置まで引く。
'''

new_wait = '''#### F. フラットシーケンスでLog Start後のWaitを保証し、Readを実行する

作業領域：`RAMScope_Set_Cond.vi`の右側から`RAMScope_Read.vi`の左側。

1. フラットシーケンスストラクチャ（Flat Sequence Structure）を配置する。
2. シーケンス枠を右クリックし、`後にフレームを追加（Add Frame After）`を選び、2フレームにする。
3. Frame 0へ`RAMScope_Log_Start.vi`を配置する。
4. `RAMScope_Set_Cond.vi / error out`をFrame 0左側のerror入力トンネルへ接続し、同VIの`error in`へ接続する。
5. `UnitNo` I32を`RAMScope_Log_Start.vi / UnitNo`へ接続する。
6. `RAMScope_Log_Start.vi / error out`をFrame 0右側のerrorトンネルへ接続し、Frame 1へ通す。
7. Frame 1へ待機（Wait (ms)）を配置する。
8. フロントパネル入力`Wait Time` U32を`Wait (ms) / milliseconds to wait`へ接続する。
9. Frame 1へ入ったerror wireを処理せず右側トンネルへ通し、シーケンス外へ出す。
10. シーケンス右側のerror wireを`RAMScope_Read.vi / error in`へ接続する。
11. `RAMScope_Read.vi / Raw Buffer`、`DataNum`、`LostDataNum`、`Packets`を、それぞれ同名のPoC表示器へ直接接続する。
12. `State After Start`は変更せず、通常Log Stop後の状態更新位置まで右方向へ引く。

```text
Set Cond error
  → Flat Sequence Frame 0：Log Start
  → Flat Sequence Frame 1：Wait (ms)
  → RAMScope_Read.vi
```

Waitにはerror端子がないため、フラットシーケンスのフレーム順で`Log Start完了 → Wait完了 → Read開始`を保証する。
'''

layer_old = '''TestStand または PoC_RAMScope_Main.vi
  → RAMScope_* 公開API
      → Builder / Parser / Common
→ RS_DLL_* 薄いラッパ
    → CLFN
        → RAMScopeVP_API_x64.dll'''

layer_new = '''TestStand または PoC_RAMScope_Main.vi
  → RAMScope_* 公開API
      → Builder / Parser / Common
          → RS_DLL_* 薄いラッパ
              → CLFN
                  → RAMScopeVP_API_x64.dll'''

for old, new, label in [
    (old_close, new_close, "public Close summary"),
    (old_poc_close, new_poc_close, "PoC Close cases"),
    (old_wait, new_wait, "PoC Wait sequence"),
    (layer_old, layer_new, "layer diagram"),
]:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one match, found {count}")
    text = text.replace(old, new)

main_path.write_text(text, encoding="utf-8")

for path in (rules_path, learning_path):
    value = path.read_text(encoding="utf-8")
    value = value.replace("**最終整理日：2026-07-16**", "**最終整理日：2026-07-21**", 1)
    path.write_text(value, encoding="utf-8")

if workflow_path.exists():
    workflow_path.unlink()
if script_path.exists():
    script_path.unlink()
