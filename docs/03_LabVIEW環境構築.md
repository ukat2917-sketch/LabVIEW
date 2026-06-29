# 03. LabVIEW 環境構築

VI を作り始める前に、開発 PC に必要なソフト・ドライバを準備し、各機器との通信を確認する。

## 3.1 必要なソフトウェア

| ソフト | 用途 | 備考 |
|--------|------|------|
| **LabVIEW**（推奨：最新の対応バージョン） | VI 開発・機器制御 | TestStand と互換のバージョンを選ぶ |
| **TestStand** | 試験フロー管理 | LabVIEW Adapter を有効化 |
| **NI-VISA** | Ethernet/USB/GPIB 機器との汎用通信 | SCPI 機器（オシロ・電源）制御の基盤 |
| **NI-XNET** | CAN 通信（NI ハードウェア使用時） | dbc 対応。[08](./08_CAN通信の実装.md) 参照 |
| **NI-DAQmx** | （必要時）DAQ デバイス | 本構成では必須でない |
| 各機器の **計装ドライバ（Instrument Driver）** | 機器固有の制御 VI | NI Instrument Driver Network 等から入手 |
| RAMScope 用 **API / マックシステムズ製ドライバ** | RAM 計測・CAN | [09](./09_RAMScope実装方針.md) 参照 |

> **バージョン整合性に注意**：LabVIEW・TestStand・各ドライバはビット数（32/64bit）と
> バージョンの互換性がある。TestStand から呼ぶ VI のビット数と LabVIEW Runtime を一致させること。

## 3.2 ドライバの探し方・入手方針

機器制御 VI は、可能な限り次の優先順位で用意する。

1. **NI 認定の Plug and Play 計装ドライバ**（機器メーカー提供の LabVIEW VI 群）
   - 横河 DLM5058、AMETEK PPX シリーズ等は計装ドライバが提供されている場合がある。
2. **IVI ドライバ**（クラス互換が必要な場合）
3. **SCPI コマンドを VISA で直接送信**（ドライバが無い／不足する場合）
   - Ethernet（TCPIP/LXI）機器は `VISA Write` / `VISA Read` で SCPI コマンドを送受信できる。
4. メーカー専用 API / DLL（RAMScope など）

## 3.3 機器接続の事前確認手順

VI を作る前に、まず **手動で通信が通ること** を確認する。

### (1) ネットワーク疎通確認
1. 各機器に固定 IP を設定（[01](./01_システム概要と構成.md) の IP 表）。
2. PC のコマンドプロンプトで `ping <機器IP>` が通ることを確認。

### (2) NI-MAX での確認（VISA 機器）
1. **NI MAX（Measurement & Automation Explorer）** を起動。
2. `Devices and Interfaces` → `Network Devices` で対象機器を追加。
3. VISA リソース名（例：`TCPIP0::192.168.0.11::inst0::INSTR`）を確認。
4. `Open VISA Test Panel` から `*IDN?` を送信し、機器の識別文字列が返ることを確認。
   - 返答があれば SCPI 通信は OK。
5. VISA リソース名を [01](./01_システム概要と構成.md) の表に記録する。

### (3) CAN インタフェースの確認
- NI-XNET 使用時：NI MAX に XNET インタフェースが見えること、dbc を登録できることを確認。
- USB-CAN（Contec 等）使用時：付属ドライバのテストツールで送受信できることを確認。
- 詳細は [08_CAN通信の実装.md](./08_CAN通信の実装.md)。

### (4) RAMScope の確認
- API / ドライバの動作確認は [09_RAMScope実装方針.md](./09_RAMScope実装方針.md) を参照。

## 3.4 プロジェクト構成（推奨フォルダ構成）

LabVIEW プロジェクト（`.lvproj`）を作成し、以下のように整理する。

```
TestSystem.lvproj
├─ 00_Common/          … 共通サブVI（エラー処理、ログ書込、型定義）
│    ├─ Status.ctl     … 実行結果ステータス（型定義 Enum）
│    ├─ TestError.ctl  … エラー情報クラスタ（型定義）
│    └─ Log_Append.vi  … 共通ログ追記VI
├─ 10_Oscilloscope/    … DLM5058 関連VI
├─ 20_Logger/          … MX100 関連VI
├─ 30_RAMScope/        … GT170 関連VI
├─ 40_HV_Power/        … 高圧模擬/負荷 RZ-X 関連VI
├─ 50_LV_Power/        … 低圧/IGS PPX36-3 関連VI
├─ 60_CAN/             … CAN 送受信VI
└─ 90_TypeDefs/        … 共有型定義
```

> **型定義（.ctl）を必ず使う**：ステータスやエラー情報のクラスタは「型定義」にしておくと、
> 後から項目を追加しても全 VI に変更が伝播し、保守が容易になる。
