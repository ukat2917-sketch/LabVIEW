/*****************************************************************************
									Copyright(c) 2017 DTS INSIGHT CORPORATION
Function：	RAMScopeVP API

Attention：

A Change History
 +------------------ Keyword (@xxx)
 |	  	  +--------- The System Version
 |	  	  | 	+--- New、Chg、Add、Del
 v	  	  v 	v
 No		 Ver  分類   年月日	    名前		 説明
-------+-----+----+-----------+-------------+----------------------------------
001     1.00  New  '17/06/02   DIST          New creation
****************************************************************************/
//#include "RAMScopeVP.h"
#pragma once

#include "GTHard.h"
// ============================================================================
// コンパイルスイッチ
// ============================================================================
//#define	GT_LEGACY_DEFINE		// 構造体定義をRAMScopeV.hに合わせる


// ============================================================================
//
//
// 構造体/共用体定義
//
//
// ============================================================================

// ----------------------------------------------------------------------------
// システム情報 (@GetSysInfo/GT150_IF)
// #SPC-D195-structSYSINFO-000#
// ----------------------------------------------------------------------------
#ifdef GT_LEGACY_DEFINE
typedef struct tag_system_info {
	long			module;
	long			module_type;
	long			probe_id;
	long			interface_id;
	long			version;
	long			addinfo;
	long			endian;
	long			probe_version;
	long			security_id_req;
	long			security_id_size;
	long			flash_enable;
	char			name[16];
} SYSINFO;
#else
typedef struct SYSINFO {
	long			module;
	long			module_type;
	long			probe_id;
	long			interface_id;
	long			version;
	long			addinfo;
	long			endian;
	long			probe_version;
	long			security_id_req;
	long			security_id_size;
	long			flash_enable;
	char			name[16];
} SYSINFO;
#endif

// ----------------------------------------------------------------------------
// プローブ設定 (@SetMdlConfig/GT150_IF)
// #SPC-D195-structMDLCFG-000#
// ----------------------------------------------------------------------------
#ifdef GT_LEGACY_DEFINE
typedef struct {
    struct
    {
		unsigned long	id[3];
		unsigned long	area[2][2];
    } nexus_jtag;
    struct
    {
		unsigned char	moe;
		unsigned char	mcd;
    } nexus_aux;
    struct
    {
		unsigned long	clk_high;
		unsigned long	clk_low;
	} serial;
    struct
    {
    } aud;
    struct
    {
    } aud_trace;
} MDLPSMCFG;

typedef struct tag_module_config {
	long			scan_cycle;
    long			jtag_clk;
	long			da_bit_width;
	long			da_ch_num;
	long			da_type;
	long			endian;
	long			ice_time_en;
	long			ice_time;
    MDLPSMCFG		psm;
} MDLCFG;
#else
typedef struct	MDLPSMCFG {
    struct
    {
		unsigned long	id[3];
		unsigned long	area[2][2];
    } nexus_jtag;
    struct
    {
		unsigned char	moe;
		unsigned char	mcd;
    } nexus_aux;
    struct
    {
		unsigned long	clk_high;
		unsigned long	clk_low;
	} serial;
}MDLPSMCFG;

typedef struct MDLCFG {
	long			scan_cycle;
    long			jtag_clk;
	long			da_bit_width;
	long			da_ch_num;
	long			da_type;
	long			endian;
	long			ice_time_en;
	long			ice_time;
    MDLPSMCFG		psm;
} MDLCFG;
#endif

// ----------------------------------------------------------------------------
// 測定条件 (@SetMeasCond/GT150_IF)
// #SPC-D195-structMEASINFO-000#
// ----------------------------------------------------------------------------
typedef	struct	MEAS_CAN_CH {
	long	Enable;
	long	Terminate;
	long	MonitorOnly;
	long	BaudRate;
	long	SmpCnt;
	long	Format;
} MEAS_CAN_CH;

#ifdef GT_LEGACY_DEFINE
typedef union uni_meas_info {
	struct tag_ram_info {
		long		MeasPeri;
		long		MeasUnit;
	} RAMINFO;
	struct tag_adc_info {
		long		DummyInterval;
		long		MeasPeri;
		long		MeasUnit;
	} ADCINFO;
	struct tag_can_info {
		long		DummyInterval;
		struct{
			long	Enable;
			long	Terminate;
			long	MonitorOnly;
			long	BaudRate;
			long	SmpCnt;
			long	Format;
		} Ch[2];
	} CANINFO;
	struct tag_trc_info {
	} TRCINFO;
} MEASINFO;
#else
typedef	struct MEAS_INFO_RAM {
	long	MeasPeri;
	long	MeasUnit;
} MEAS_INFO_RAM;

typedef	struct MEAS_INFO_ADC {
	long	DummyInterval;
	long	MeasPeri;
	long	MeasUnit;
} MEAS_INFO_ADC;

typedef	struct MEAS_INFO_CAN {
	long	DummyInterval;
	MEAS_CAN_CH		Ch[ 2];
} MEAS_INFO_CAN;

typedef union MEASINFO {
	MEAS_INFO_RAM		m_Ram;
	MEAS_INFO_ADC		m_Adc;
	MEAS_INFO_CAN		m_Can;
} MEASINFO;
#endif

// ----------------------------------------------------------------------------
// 測定条件拡張 (@SetMeasCondEx/GT150_IF)
// #SPC-D195-structMEASINFO_EX-000#
// ----------------------------------------------------------------------------
typedef	struct MEAS_INFO_RAM_EX {
	long		DummyInterval;
	long		MeasPeri;
	long		MeasUnit;
	long		ScanSyncEnable;
	long		ScanSyncMaster;
	char		reserved[44];
} MEAS_INFO_RAM_EX;

typedef	struct MEAS_INFO_ADC_EX {
	long		DummyInterval;
	long		MeasPeri;
	long		MeasUnit;
	long		ScanSyncEnable;
	long		ScanSyncMaster;
	char		reserved[44];
} MEAS_INFO_ADC_EX;

typedef	struct MEAS_INFO_CAN_EX {
	long		DummyInterval;
	MEAS_CAN_CH	Ch[ 2];
	char		reserved[12];
} MEAS_INFO_CAN_EX;

typedef union MEASINFO_EX {
	MEAS_INFO_RAM_EX	m_Ram;
	MEAS_INFO_ADC_EX	m_Adc;
	MEAS_INFO_CAN_EX	m_Can;
} MEASINFO_EX;

// ----------------------------------------------------------------------------
// 測定条件 (@SetMeasCond/GT170_IF)
// #SPC-D195-structMEASINFO_170-000#
// ----------------------------------------------------------------------------
typedef struct MEASINFO_RAM170 {
	long	DummyInterval;
	long	MeasPeri;
	long	MeasUnit;
	long	MeasPeri_reserve[2];
} MEASINFO_RAM170;

typedef struct MEASINFO_ADC170 {
	long	DummyInterval;
	long	MeasPeri;
	long	MeasUnit;
} MEASINFO_ADC170;

typedef struct MEAS_CAN_CH_170 {
	long	Enable;
	long	Terminate;
	long	MonitorOnly;
	long	BaudRate;
	long	BaudRateHigh;
	long	SmpCnt;
	long	SmpCntHigh;
	long	BusMode;
} MEAS_CAN_CH_170;

typedef struct MEASINFO_CAN170 {
	long			DummyInterval;
	long			isUseFDFormat;
	MEAS_CAN_CH_170	Ch[2];
} MEASINFO_CAN170;

typedef union MEASINFO_170 {
	MEASINFO_RAM170		RAM;
	MEASINFO_ADC170		ADC;
	MEASINFO_CAN170		CAN;
} MEASINFO_170;

// ----------------------------------------------------------------------------
// チャンネル情報 (@SetMeasCh/GT150_IF)
// #SPC-D195-structCHINFO-000#
// ----------------------------------------------------------------------------
#ifdef GT_LEGACY_DEFINE
typedef union uni_channel_info {
	struct {
		unsigned long	enable;
		unsigned long	phys_ch;
		unsigned long	address;
		unsigned long	size;
		unsigned long	speed;
	} RAM_TRC_CHINFO;
	struct {
		unsigned long	enable;
	} ADC_CHINFO;
	struct {
		unsigned long	enable;
		unsigned long	port_no;
		unsigned long	msg_id;
	} CAN_CHINFO;
} CHINFO;
#else
typedef	struct	CHINFO_RAM {
	unsigned long	enable;
	unsigned long	phys_ch;
	unsigned long	address;
	unsigned long	size;
	unsigned long	speed;
}CHINFO_RAM;

typedef	struct CHINFO_ADC {
	unsigned long	enable;
	unsigned long	type;
} CHINFO_ADC;

typedef union CHINFO {
	CHINFO_RAM		m_Ram;
	CHINFO_ADC		m_Adc;
} CHINFO;
#endif

// ----------------------------------------------------------------------------
// チャンネル情報 (@SetMeasCh/GT170_IF)
// #SPC-D195-structCHINFO_170-000#
// ----------------------------------------------------------------------------
typedef struct CHINFO_RAM170 {
	DWORD	enable;
	DWORD	core;
	DWORD	address;
	DWORD	size;
	DWORD	sign;
	DWORD	speed;
} CHINFO_RAM170;

typedef struct CHINFO_ADC170 {
	DWORD	enable;
	DWORD	magnification;
} CHINFO_ADC170;

typedef union CHINFO_170 {
	CHINFO_RAM170	RAM;
	CHINFO_ADC170	ADC;
} CHINFO_170;

// ----------------------------------------------------------------------------
// 容量設定 (@SetLoggingInfo/GT150_IF)
// #SPC-D195-structLOGINFO-000#
// ----------------------------------------------------------------------------
#ifdef GT_LEGACY_DEFINE
typedef struct tag_log_info {
	long			logDevice;
	long			limitHddSize;
	struct{
		long		logSize;
		long		BuffSize;
	}mdl[16];
} LOGINFO;
#else
typedef struct LOGINFO {
	long			logDevice;
	long			limitHddSize;
	struct{
		long		logSize;
		long		BuffSize;
	}mdl[16];
} LOGINFO;
#endif

// ----------------------------------------------------------------------------
// イベント設定 (@SetEventCond/GT150_IF)
// #SPC-D195-structEVENTINFO-000#
// ----------------------------------------------------------------------------
#ifdef GT_LEGACY_DEFINE
typedef struct tag_event_info {
	long			enable;
	long			mdlNo;
	long			event_type;
	union {
		struct {
			long	ch;
			long	data1;
			long	data2;
		} RAM_EVENTINFO;
		struct {
			long	ch;
			long	data1;
			long	data2;
		} ADC_EVENTINFO;
		struct {
			long	ch;
			long	id;
			long	endian;
			long	sig_len;
			long	sig_st_byte;
			long	sig_st_bit;
			long	sig_datatype;
			char	data1[8];
			char	data2[8];
		} CAN_EVENTINFO;
	} MDL_EVENTINFO;
} EVENTINFO;
#else
typedef	struct	EVENTINFO_RAM {
	long			ChNo;
	unsigned long	Data1;
	unsigned long	Data2;
}EVENTINFO_RAM;

typedef	struct	EVENTINFO_CAN {
	long			ChNo;
	long			CanID;
	long			Endian;
	long			SigLen;
	long			SigStartByte;
	long			SigStartBit;
	long			SigDataType;
	unsigned char	Data1[ 8];
	unsigned char	Data2[ 8];
}EVENTINFO_CAN;

typedef	union MDL_EVENTINFO {
	EVENTINFO_RAM	RAM;
	EVENTINFO_CAN	CAN;
} MDL_EVENTINFO;

typedef struct	EVENTINFO {
	long			Enable;
	long			MdlNo;
	long			EventType;
	MDL_EVENTINFO	MdlUnq;
} EVENTINFO;
#endif

// ----------------------------------------------------------------------------
// イベント設定 (@SetEventCond/GT170_IF)
// #SPC-D195-structEVENTINFO_170-000#
// ----------------------------------------------------------------------------
typedef union EV_DATA_4 {
	DWORD		ulData;
	long		slData;
} EV_DATA_4;

typedef union EV_DATA_8 {
	ULONGLONG	ullData;
	LONGLONG	sllData;
} EV_DATA_8;

typedef struct EVENTINFO_RAM170 {
	long		ChNo;
	EV_DATA_4	Data1;
	EV_DATA_4	Data2;
} EVENTINFO_RAM170;

typedef struct EVENTINFO_CAN170 {
	long			ChNo;
	unsigned long	CanID;
	long			Format;
	long			Endian;
	long			SigLen;
	long			SigStartByte;
	long			SigStartBit;
	long			SigSigned;
	EV_DATA_8		Data1;
	EV_DATA_8		Data2;
} EVENTINFO_CAN170;

typedef struct EVENTINFO_ADC170 {
	long		ChNo;
	long		Data1;
	long		Data2;
} EVENTINFO_ADC170;

typedef union MDL_EVENTINFO_170 {
	EVENTINFO_RAM170	RAM;
	EVENTINFO_CAN170	CAN;
	EVENTINFO_ADC170	ADC;
} MDL_EVENTINFO_170;

typedef struct EVENTINFO_170 {
	long				Enable;
	long				MdlNo;
	long				EventType;
	MDL_EVENTINFO_170	MdlUnq;
} EVENTINFO_170;

// ----------------------------------------------------------------------------
// ロギングトリガ設定 (@SetLoggingTriggerRange, Point/GT150_IF)
// #SPC-D195-structLOGTRG_INFO_R-000# #SPC-D195-structLOGTRG_INFO_P-000#
// ----------------------------------------------------------------------------
#ifdef GT_LEGACY_DEFINE
typedef struct tag_softtrg_info {
	long			relay;
	struct {
		long		ptn;
		long		relay;
	} GROUP[2];
} SOFTTRG_INFO;

typedef struct tag_logtrg_r_info {
	SOFTTRG_INFO	start;
	SOFTTRG_INFO	end;
} LOGTRG_INFO_R;

typedef struct tag_logtrg_p_info {
	unsigned long	preTrigSize;
	unsigned long	postTrigSize;
	SOFTTRG_INFO	trig;
} LOGTRG_INFO_P;
#else
typedef struct SOFTTRG_INFO {
	long			relay;
	struct {
		long		ptn;
		long		relay;
	} GROUP[2];
} SOFTTRG_INFO;

typedef struct LOGTRG_INFO_R {
	SOFTTRG_INFO	start;
	SOFTTRG_INFO	end;
} LOGTRG_INFO_R;

typedef struct LOGTRG_INFO_P {
	unsigned long	preTrigSize;
	unsigned long	postTrigSize;
	SOFTTRG_INFO	trig;
} LOGTRG_INFO_P;
#endif

// ----------------------------------------------------------------------------
// 外部信号設定 (@SetExternalTrigger/GT150_IF)
// #SPC-D195-structEXTTRG_INFO-000#
// ----------------------------------------------------------------------------
#ifdef GT_LEGACY_DEFINE
typedef struct tag_exttrg_info {
	struct {
		long		enable;
		long		mode;
	} TRGIN_INFO;
	struct {
		long		enable;
		long		mode;
		long		pulse;
		long		level;
	} TRGOUT_INFO;
} EXTTRG_INFO;
#else
typedef	struct	TRGIN_INFO {
	long		enable;
	long		mode;
} TRGIN_INFO;

typedef	struct TRGOUT_INFO {
		long		enable;
		long		mode;
		long		pulse;
		long		level;
} TRGOUT_INFO;

typedef struct EXTTRG_INFO {
	TRGIN_INFO	m_In;
	TRGOUT_INFO	m_Out;
} EXTTRG_INFO;
#endif

// ----------------------------------------------------------------------------
// 外部信号設定 (@SetExternalTrigger/GT170_IF)
// #SPC-D195-structEXTTRG_INFO_170-000#
// ----------------------------------------------------------------------------
typedef struct EXTTRG_IN_INFO {
	long			Mode;
	long			FilterTime;
} EXTTRG_IN_INFO;

typedef struct EXTTRG_OUT_INFO {
	long			Mode;
	long			Level;
	long			Cycle;
	SOFTTRG_INFO	Event;
} EXTTRG_OUT_INFO;

typedef struct EXTTRG_INFO_170 {
	EXTTRG_IN_INFO		ExtIn;
	EXTTRG_OUT_INFO		ExtOut;
} EXTTRG_INFO_170;

// ----------------------------------------------------------------------------
// 測定制御設定 (@SetMeasTrigger/GT170_IF)
// #SPC-D195-structMEASTRG_INFO_170-000#
// ----------------------------------------------------------------------------
typedef struct MEASTRG_CANBUS_COND {
	long				MdlNo;
	long				ChNo;
	long				Mode;
	long				ID;
	long				Format;
	long				WaitTime;
} MEASTRG_CANBUS_COND;

typedef struct MEASTRG_CANBUS_PARAM {
	MEASTRG_CANBUS_COND	Start;
	MEASTRG_CANBUS_COND	End;
} MEASTRG_CANBUS_PARAM;

typedef struct MEASTRG_LEVEL_PARAM {
	long				LeaderModule;
} MEASTRG_LEVEL_PARAM;

typedef union MEASTRG_INFO_170 {
	MEASTRG_LEVEL_PARAM		Level;
	MEASTRG_CANBUS_PARAM	CanBus;
} MEASTRG_INFO_170;

// ----------------------------------------------------------------------------
// メモリ編集 (@ContinuallyMemoryRead, Write / GT150_IF)
// #SPC-D195-structCONT_MEM_XX-000#
// ----------------------------------------------------------------------------
#ifdef GT_LEGACY_DEFINE
typedef struct cont_mem_wr {
	unsigned long 	Size;
	unsigned long	Address;
	char			Data[4];
} CONT_MEM_WR;
#else
typedef struct CONT_MEN_WR {
	unsigned long 	Size;
	unsigned long	Address;
	char			Data[4];
} CONT_MEM_WR;
#endif
typedef CONT_MEM_WR	CONT_MEM_RD;

// ----------------------------------------------------------------------------
// シナリオ書き込み (@ScenarioWriteStart / GT170_IF)
// #SPC-D195-structWRITE_SCENARIO-000#
// ----------------------------------------------------------------------------
typedef struct WRITE_SCENARIO_STEP {
	unsigned long		WriteValue;
	unsigned long		Count;
} WRITE_SCENARIO_STEP;

typedef struct WRITE_SCENARIO {
	long				Mode;
	long				Repeat;
	long				StartEvNo;
	long				StopEvNo;
	unsigned long		Address;
	unsigned long		Size;
	long				StepNum;
	WRITE_SCENARIO_STEP	Step[ 64];
} WRITE_SCENARIO;

// ----------------------------------------------------------------------------
// CAN送信 (@SendCANDataFrame/GT150_IF)
// #SPC-D195-structCANSENDDATA-000#
// ----------------------------------------------------------------------------
#ifdef GT_LEGACY_DEFINE
typedef struct tag_can_send_data {
	unsigned long	dlc;
	unsigned long	id;
	unsigned char	data[8];
} CANSENDDATA;
#else
typedef struct CANSENDDATA {
	unsigned long	dlc;
	unsigned long	id;
	unsigned char	data[8];
} CANSENDDATA;
#endif

// ----------------------------------------------------------------------------
// CAN送信 (@SendCANDataFrame/GT170_IF)
// #SPC-D195-structCANSEND_170_INFO-000#
// ----------------------------------------------------------------------------
typedef struct CANSEND_170_DATA {
	unsigned long	DataLength;
	unsigned long	CanId;
	unsigned char	Data[64];
} CANSEND_170_DATA;

typedef struct CANSEND_170_INFO {
	long				IdFormat;
	long				Count;
	CANSEND_170_DATA 	*pSendData;
} CANSEND_170_INFO;

// ----------------------------------------------------------------------------
// CANシナリオ送信 (@ScenarioSendSet/GT170_IF)
// #SPC-D195-structSEND_SCENARIO-000#
// ----------------------------------------------------------------------------
typedef struct SEND_SCENARIO_STEP {
	long				IdFormat;
	long				Count;
	long				WaitTime;
	CANSEND_170_DATA	SendData;
} SEND_SCENARIO_STEP;

typedef struct SEND_SCENARIO {
	long				Mode;
	long				Repeat;
	long				StartEvNo;
	long				StopEvNo;
	long				StepNum;
	SEND_SCENARIO_STEP	Step[ 64];
} SEND_SCENARIO;

// ============================================================================
//
//
// 関数一覧 [GT150_IF]
// #SPC-D195-FunctionList-GT150_IF-000#
//
//
// ============================================================================
// システム
typedef long	(*RAMScopeGT150DeviceInitPtr				)(long *pUnitNum, long *kind);
typedef long	(*RAMScopeGT150DeviceExitPtr				)(void);
typedef long	(*RAMScopeGT150AllInitPtr					)(long UnitNo);
typedef long	(*RAMScopeGT150GetSysInfoPtr				)(long UnitNo, SYSINFO *pSysInfo);
typedef long	(*RAMScopeGT150SetMdlConfigPtr				)(long UnitNo, long MdlNo, MDLCFG *pMdlCfg);
typedef long	(*RAMScopeGT150PGT_SetMdlConfigPtr			)(long UnitNo, long *SlotErr);
typedef long	(*RAMScopeGT150PGT_ModifyMdlConfigPtr		)(long UnitNo, long *SlotErr);

// 測定制御
typedef long	(*RAMScopeGT150MeasStartPtr					)(long UnitNo);
typedef long	(*RAMScopeGT150MeasStopPtr					)(long UnitNo);

// 測定設定
typedef long	(*RAMScopeGT150SetMeasCondPtr				)(long UnitNo, long MdlNo, MEASINFO *pMeasInfo);
typedef long	(*RAMScopeGT150SetMeasCondExPtr				)(long UnitNo, long MdlNo, MEASINFO_EX *pMeasInfoEx);
typedef long	(*RAMScopeGT150SetMeasChPtr					)(long UnitNo, long MdlNo, long ChNum, CHINFO *ChInfo);
typedef long	(*RAMScopeGT150SetLoggingInfoPtr			)(long UnitNo, LOGINFO *pLogInfo);
typedef long	(*RAMScopeGT150ReleaseBufferDataPtr			)(long UnitNo);

// イベント・ロギングトリガ・外部信号設定・測定制御設定
typedef long	(*RAMScopeGT150SetEventCondPtr				)(long UnitNo, EVENTINFO *EvtInfo);
typedef long	(*RAMScopeGT150SetLoggingTriggerRangePtr	)(long UnitNo, long Enable, LOGTRG_INFO_R *TrigInfo);
typedef long	(*RAMScopeGT150SetLoggingTriggerPointPtr	)(long UnitNo, long Enable, LOGTRG_INFO_P *TrigInfo);
typedef long	(*RAMScopeGT150SetExternalTriggerPtr		)(long UnitNo, long MdlNo, EXTTRG_INFO *TrigInfo);

// 測定データの取得
typedef long	(*RAMScopeGT150GetGapTimePtr				)(long UnitNo, unsigned long *pGapTime);
typedef long	(*RAMScopeGT150GetMeasNumPtr				)(long UnitNo, long *pMeasNum);
typedef long	(*RAMScopeGT150GetBlockNumPtr				)(long UnitNo, long MeasNo, long *pBlockNum);
typedef long	(*RAMScopeGT150GetBufferDataNumPtr			)(long UnitNo, long MdlNo, long *pDataNum);
typedef long	(*RAMScopeGT150GetBufferDataPtr				)(long UnitNo, long MdlNo, void *pData, long *pDataNum, long *pLostDataNum);
typedef long	(*RAMScopeGT150GetLoggingDataNumPtr			)(long UnitNo, long MdlNo, long MeasNo, long BlockNo, long *pDataNum);
typedef long	(*RAMScopeGT150GetLoggingDataPtr			)(long UnitNo, long MdlNo, long MeasNo, long BlockNo, void *pData, long *pDataNum, long *pLostDataNum);

// RAMモニタモジュール固有機能
typedef long	(*RAMScopeGT150MemoryReadPtr				)(long UnitNo, long MdlNo, unsigned long Address, long Size, long Count, char *Buffer, long Tmout);
typedef long	(*RAMScopeGT150MemoryWritePtr				)(long UnitNo, long MdlNo, unsigned long Address, long Size, long Count, char *Buffer, long Tmout);
typedef long	(*RAMScopeGT150ContinualyMemoryReadPtr		)(long UnitNo, long MdlNo, long Count, CONT_MEM_RD *Buffer, long Tmout);
typedef long	(*RAMScopeGT150ContinualyMemoryWritePtr		)(long UnitNo, long MdlNo, long Count, CONT_MEM_WR *Buffer, long Tmout);

// CANモジュール固有機能
typedef long	(*RAMScopeGT150SendCANDataFramePtr			)(long UnitNo, long MdlNo, unsigned long Channel, long Format, long Count, CANSENDDATA *pSendData);

// アナログ入力モジュール固有機能
typedef long	(*RAMScopeGT150SetAdcRangePtr				)(long UnitNo, long MdlNo, long ChNum, long *pRange);


// ============================================================================
//
//
// 関数一覧 [GT170_IF]
// #SPC-D195-FunctionList-GT170_IF-000#
//
//
// ============================================================================
// 測定設定
typedef long	(*RAMScopeGT170SetMeasCondPtr				)(long UnitNo, long MdlNo, MEASINFO_170 *pMeasInfo);
typedef long	(*RAMScopeGT170SetMeasChPtr					)(long UnitNo, long MdlNo, long ChNum, CHINFO_170 *pChInfo);

// イベント・ロギングトリガ・外部信号設定・測定制御設定
typedef long	(*RAMScopeGT170SetEventCondPtr				)(long UnitNo, EVENTINFO_170 *pEvtInfo);
typedef long	(*RAMScopeGT170SetExternalTriggerPtr		)(long UnitNo, long MdlNo, EXTTRG_INFO_170 *pExtTrgInfo);
typedef long	(*RAMScopeGT170SetMeasTriggerPtr			)(long UnitNo, long Mode, MEASTRG_INFO_170 *pMeasTrgInfo);

// RAMモニタモジュール固有機能
typedef long	(*RAMScopeGT170ScenarioWriteStartPtr		)(long UnitNo, long MdlNo, long ScenarioNum, WRITE_SCENARIO *pScenario);
typedef long	(*RAMScopeGT170ScenarioWriteStopPtr			)(long UnitNo, long MdlNo);

// CANモジュール固有機能
typedef long	(*RAMScopeGT170SendCANDataFramePtr			)(long UnitNo, long MdlNo, long ChNo, CANSEND_170_INFO *pSendInfo);
typedef long	(*RAMScopeGT170ScenarioSendSetPtr			)(long UnitNo, long MdlNo, long ChNo, long ScenarioNum, SEND_SCENARIO *pScenario);
typedef long	(*RAMScopeGT170ScenarioSendStartPtr			)(long UnitNo, long MdlNo);
typedef long	(*RAMScopeGT170ScenarioSendStopPtr			)(long UnitNo, long MdlNo);

// アナログ入力モジュール固有機能
typedef long	(*RAMScopeGT170SetAdcRangePtr				)(long UnitNo, long MdlNo, long ChNum, long *pRange);
