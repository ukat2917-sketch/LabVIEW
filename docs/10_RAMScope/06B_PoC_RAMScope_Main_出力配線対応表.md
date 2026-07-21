# 10-06B. `PoC_RAMScope_Main.vi` 出力配線対応表

**最終整理日：2026-07-21**

> 本書は、`PoC_RAMScope_Main.vi`の各出力を、どのPublic VIのどの端子から接続するかを示す。
>
> [06A_PoC_RAMScope_Main_VI詳細作成手順.md](./06A_PoC_RAMScope_Main_VI詳細作成手順.md)の「6. 主な入出力」およびClose Caseの出力配線について、本書を優先する。

---

## 1. 出力は2種類に分ける

```text
途中のPublic VIから直接保持する出力
  UnitNum / kind
  Module List / MdlNo_RAM / MdlNo_CAN / Endian_RAM
  Raw Buffer / DataNum / LostDataNum / Packets

Cleanup完了後に最後のClose Caseで確定する出力
  Final State / Status / TestError / error out
```

途中の値を、最後のClose Caseまで順番に通過させる必要はない。各Public VIの出力ワイヤを分岐し、その場でPoCの出力表示器へ直接接続する。

LabVIEWの出力表示器端子はブロックダイアグラムの任意位置へ置けるため、対応するPublic VIの近くへ配置してよい。ローカル変数は使用せず、元端子から直接ワイヤを引く。

---

## 2. 全出力の接続元

| PoC出力 | 接続元 | 配線方法 | 注意 |
|---|---|---|---|
| `UnitNum` | `RAMScope_Connect.vi / UnitNum` | Connect出力ワイヤを分岐して表示器へ接続 | `UnitNo`制御器とは別物 |
| `kind` | `RAMScope_Connect.vi / kind` | Connect出力から直接接続 | 機種コード |
| `Module List` | `RAMScope_Init.vi / Module List` | Init出力から直接接続 | `RAMScope_Module_Info.ctl[]` |
| `MdlNo_RAM` | `RAMScope_Init.vi / MdlNo_RAM` | 3方向へ分岐 | PoC出力、Set Cond入力、Read入力 |
| `MdlNo_CAN` | `RAMScope_Init.vi / MdlNo_CAN` | Init出力から直接接続 | 現PoCでは表示・記録用 |
| `Endian_RAM` | `RAMScope_Init.vi / Endian_RAM` | Init出力から直接接続 | 0=Big、1=Littleのコード |
| `Raw Buffer` | `RAMScope_Read.vi / Raw Buffer` | Read出力から直接接続 | U8一次元配列 |
| `DataNum` | `RAMScope_Read.vi / DataNum` | Read出力から直接接続 | 実際に取得したPacket数 |
| `LostDataNum` | `RAMScope_Read.vi / LostDataNum` | Read出力から直接接続 | 欠落Packet数 |
| `Packets` | `RAMScope_Read.vi / Packets` | Read出力から直接接続 | 解析済みPacket配列 |
| `Final State` | Close CaseのState出力トンネル | Case外で表示器へ接続 | Cleanup Stop/Release反映後のState |
| `Status` | Close CaseのStatus出力トンネル | Case外で表示器へ接続 | True/False両Caseで生成 |
| `TestError` | Close CaseのTestError出力トンネル | Case外で表示器へ接続 | True/False両Caseで生成 |
| `error out` | Close Caseのerror出力トンネル | Case外で表示器へ接続 | Cleanup完了後の最終error |

---

## 3. `UnitNum`と`UnitNo`を混同しない

```text
UnitNum
  = RAMScope_Connect.viが返す接続Unit数
  = PoCの出力表示器

UnitNo
  = 各APIへ渡す対象Unit番号
  = 現仕様では通常I32 0
  = PoCの入力制御器または内部定数
```

したがって、画面上の`UnitNo`制御器を`UnitNum`出力へ流用しない。

### 配線

1. `RAMScope_Connect.vi / UnitNum`出力ワイヤを右クリックする。
2. `作成 → 表示器`を選ぶ。
3. 表示器名を`UnitNum`とする。
4. `RAMScope_Connect.vi / kind`も同様に`kind`表示器へ接続する。
5. `UnitNo`は別のI32制御器またはI32定数`0`として、Init、Set Cond、Start、Read、Stop、Releaseへ分岐する。

---

## 4. Init出力の配線

`RAMScope_Init.vi`の出力は、同VIの直後でPoC表示器へ接続する。

```text
RAMScope_Init.vi
├─ Module List ─────────────→ PoC Module List
├─ MdlNo_RAM ─┬────────────→ PoC MdlNo_RAM
│             ├────────────→ RAMScope_Set_Cond.vi / MdlNo_RAM
│             └────────────→ RAMScope_Read.vi / MdlNo_RAM
├─ MdlNo_CAN ───────────────→ PoC MdlNo_CAN
└─ Endian_RAM ──────────────→ PoC Endian_RAM
```

### `Endian_RAM`と`Byte Order`

現在のPoC入力には`Byte Order`が別に存在する。

```text
Byte Order制御器
  → RAMScope_Init.vi / Byte Order
  → RAMScope_Read.vi / Byte Order

RAMScope_Init.vi / Endian_RAM
  → PoC Endian_RAM表示器
```

`Endian_RAM` I32コードを`RAMScope_Read.vi / Byte Order`へ直接接続してはならない。自動設定する場合は、次の明示的な変換を追加する。

```text
Endian_RAM=0 → Big Endian
Endian_RAM=1 → Little Endian
```

この変換を追加していない現在のPoCでは、Readへは入力制御器`Byte Order`を接続する。

---

## 5. Read出力の配線

`RAMScope_Read.vi`の右側へ、次の4表示器を配置する。

```text
RAMScope_Read.vi
├─ Raw Buffer ─────→ Raw Buffer表示器
├─ DataNum ────────→ DataNum表示器
├─ LostDataNum ────→ LostDataNum表示器
└─ Packets ────────→ Packets表示器
```

### 配線順

1. `RAMScope_Read.vi / Raw Buffer`をU8一次元配列表示器へ接続する。
2. `DataNum`をI32表示器へ接続する。
3. `LostDataNum`をI32表示器へ接続する。
4. `Packets`を`RAMScope_Packet.ctl[]`表示器へ接続する。
5. これらのワイヤをStop、Release、Cleanup、Close Caseへ通さない。

Readが前段エラーでスキップされた場合は、`RAMScope_Read.vi`が定義した安全出力、空配列および0がそのままPoC出力になる。

---

## 6. 最後のClose Caseに必要な4出力

Close Case Structureには、右側へ次の4個の出力トンネルを作る。

```text
上から推奨順：
1. Final State     RAMScope_PoC_State.ctl
2. Status          Status.ctl
3. TestError       TestError.ctl
4. Final Error     error cluster
```

TrueケースとFalseケースの両方で、4トンネルをすべて配線する。

---

## 7. Falseケース（Connected?=False：DeviceInit未成功）

### 7.1 配置するもの

- `Error_To_TestStatus.vi`
- 文字列定数`RAMScope`
- `RAMScope_Close.vi`は配置しない

### 7.2 配線順

作業領域：Close CaseのFalseケース。

1. KのCleanup Release Caseから出たStateを、Close Case左側のState入力トンネルへ接続する。
2. 同じStateワイヤを、Close Case右側の`Final State`出力トンネルへそのまま接続する。
3. Kから出た最終errorをClose Case左側のerror入力トンネルへ接続する。
4. `Error_To_TestStatus.vi`をFalseケース内へ配置する。
5. 手順3の入力errorを`Error_To_TestStatus.vi / error in`へ接続する。
6. 文字列定数へ全文`RAMScope`を入力する。
7. 文字列定数`RAMScope`を`Error_To_TestStatus.vi / Device Name`へ接続する。
8. `Error_To_TestStatus.vi / Status`をClose Case右側の`Status`出力トンネルへ接続する。
9. `Error_To_TestStatus.vi / TestError`を`TestError`出力トンネルへ接続する。
10. `Error_To_TestStatus.vi / error out`を`Final Error`出力トンネルへ接続する。

### 見取り図

```text
K出力State ─────────────────────────→ Final Stateトンネル

K出力error
  → Error_To_TestStatus.vi
      Device Name = "RAMScope"
      ├─ Status ────────────────────→ Statusトンネル
      ├─ TestError ─────────────────→ TestErrorトンネル
      └─ error out ─────────────────→ Final Errorトンネル
```

Falseケースで入力errorをFinal Errorへ直接接続するだけでは、StatusとTestErrorが作られず、Case Structureの出力トンネルが未配線になる。

---

## 8. Trueケース（Connected?=True：DeviceExitが必要）

### 8.1 配置するもの

- `RAMScope_Close.vi`
- `Clear Errors`は配置しない

### 8.2 配線順

1. Close Case左側のState入力を、右側の`Final State`出力トンネルへそのまま接続する。
2. Kから出た最終errorを`RAMScope_Close.vi / error in`へ接続する。
3. `RAMScope_Close.vi / Status`をClose Caseの`Status`出力トンネルへ接続する。
4. `RAMScope_Close.vi / TestError`を`TestError`出力トンネルへ接続する。
5. `RAMScope_Close.vi / error out`を`Final Error`出力トンネルへ接続する。

```text
K出力State ─────────────────────────→ Final Stateトンネル

K出力error
  → RAMScope_Close.vi
      ├─ Status ────────────────────→ Statusトンネル
      ├─ TestError ─────────────────→ TestErrorトンネル
      └─ error out ─────────────────→ Final Errorトンネル
```

`RAMScope_Close.vi`内部でOriginal Errorを保持しながらDeviceExitを試すため、このCaseではClear Errorsを追加しない。

---

## 9. Case外からPoC出力へ接続する

Close Caseの右側で、4本をPoCの最終出力へ接続する。

```text
Close Case.Final State → PoC Final State
Close Case.Status      → PoC Status
Close Case.TestError   → PoC TestError
Close Case.Final Error → PoC error out
```

Status、TestError、error outをTrueケース内の`RAMScope_Close.vi`から直接PoC表示器へ接続してはならない。Falseケースでも同じ出力型を生成する必要があるため、必ずCase Structureの出力トンネルを経由する。

---

## 10. 完成時の全出力見取り図

```text
RAMScope_Connect.vi
├─ UnitNum ─────────────────────────────→ PoC UnitNum
└─ kind ────────────────────────────────→ PoC kind

RAMScope_Init.vi
├─ Module List ─────────────────────────→ PoC Module List
├─ MdlNo_RAM ───────────────────────────→ PoC MdlNo_RAM
├─ MdlNo_CAN ───────────────────────────→ PoC MdlNo_CAN
└─ Endian_RAM ──────────────────────────→ PoC Endian_RAM

RAMScope_Read.vi
├─ Raw Buffer ──────────────────────────→ PoC Raw Buffer
├─ DataNum ─────────────────────────────→ PoC DataNum
├─ LostDataNum ─────────────────────────→ PoC LostDataNum
└─ Packets ─────────────────────────────→ PoC Packets

Cleanup後State/error
  → Close Case
      ├─ Final State ───────────────────→ PoC Final State
      ├─ Status ────────────────────────→ PoC Status
      ├─ TestError ─────────────────────→ PoC TestError
      └─ Final Error ───────────────────→ PoC error out
```

---

## 11. 画面確認チェックリスト

- [ ] `UnitNum`はConnect出力であり、`UnitNo`制御器ではない。
- [ ] `kind`表示器がConnect出力へ接続されている。
- [ ] `Module List`、`MdlNo_RAM`、`MdlNo_CAN`、`Endian_RAM`がInit出力へ接続されている。
- [ ] `MdlNo_RAM`はSet CondとReadにも分岐している。
- [ ] Raw Buffer、DataNum、LostDataNum、PacketsはRead出力へ直接接続されている。
- [ ] Close CaseにState、Status、TestError、errorの4出力トンネルがある。
- [ ] Close CaseのFalseケースに`Error_To_TestStatus.vi`がある。
- [ ] FalseケースのDevice Nameは文字列全文`RAMScope`である。
- [ ] Close CaseのTrueケースに`RAMScope_Close.vi`がある。
- [ ] True/False両ケースで4出力トンネルがすべて配線されている。
- [ ] Final State、Status、TestError、error outはCase外の各PoC出力へ接続されている。
