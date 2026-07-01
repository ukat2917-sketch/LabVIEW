/*****************************************************************************
									Copyright(c) 2017 DTS INSIGHT CORPORATION

Function：Simple sample for RAMScopeVP API

Attention：Configuration module(GT170U01+GT171M01)

A Change History
+------------------ Keyword (@xxx)
|	  	  +--------- The System Version
|	  	  | 	+--- New、Chg、Add、Del
v	  	  v 	v
No		 Ver  分類   年月日	    名前		 説明
-------+-----+----+-----------+-------------+----------------------------------
001     1.00  New  '18/02/28   DIST          New creation
*******************************************************************************/

//==============================================================================
// include
//==============================================================================
#include "stdafx.h"
#include <Windows.h>

#include "GTHard.h"
#include "RAMScopeVP.h"
//==============================================================================
// global variable
//==============================================================================
long			GTPackData[1 * 1024 * 1024];
//==============================================================================
//
//	main
//
//==============================================================================
int _tmain(int argc, _TCHAR* argv[])
{
	HINSTANCE		Inst;
	long			GTUnitNum;
	long			GTKind;
	SYSINFO			GTSysinfo[NUM_MODULE_MAX];
	long			GTSlotErr[NUM_MODULE_MAX];
	MEASINFO_170	GTMeasInfo;
	CHINFO_170		GTChInfo[1];
	LOGINFO			GTLogInfo;
	long			GTDataNum;
	long			GTLostDataNum;

	RAMScopeGT150DeviceInitPtr			GT150DeviceInitFunc;		
	RAMScopeGT150DeviceExitPtr			GT150DeviceExitFunc;
	RAMScopeGT150AllInitPtr				GT150AllInitFunc;
	RAMScopeGT150GetSysInfoPtr			GT150GetSysInfoFunc;
	RAMScopeGT150PGT_SetMdlConfigPtr	GT150PGT_SetMdlConfigFunc;
	RAMScopeGT150PGT_ModifyMdlConfigPtr	GT150PGT_ModifyMdlConfigFunc;
	RAMScopeGT150MeasStartPtr			GT150MeasStartFunc;
	RAMScopeGT150MeasStopPtr			GT150MeasStopFunc;
	RAMScopeGT170SetMeasCondPtr			GT170SetMeasCondFunc;
	RAMScopeGT170SetMeasChPtr			GT170SetMeasChFunc;
	RAMScopeGT150SetLoggingInfoPtr		GT150SetLoggingInfoFunc;
	RAMScopeGT150GetBufferDataPtr		GT150GetBufferDataFunc;
	RAMScopeGT150GetLoggingDataPtr		GT150GetLoggingDataFunc;
	//----------------------------------------------------------------------
	//	Load DLL
	//----------------------------------------------------------------------
	Inst = ::LoadLibraryEx(L".\\RAMScopeVP_API.dll", 0, 0);
	if (Inst == NULL) {
		return -1;
	}
	//----------------------------------------------------------------------
	//	 Acquire address of an exported function 
	//----------------------------------------------------------------------
	GT150DeviceInitFunc				= (RAMScopeGT150DeviceInitPtr)			::GetProcAddress(Inst, "RAMScopeGT150DeviceInit");
	GT150DeviceExitFunc				= (RAMScopeGT150DeviceExitPtr)			::GetProcAddress(Inst, "RAMScopeGT150DeviceExit");
	GT150AllInitFunc				= (RAMScopeGT150AllInitPtr)				::GetProcAddress(Inst, "RAMScopeGT150AllInit");
	GT150GetSysInfoFunc				= (RAMScopeGT150GetSysInfoPtr)			::GetProcAddress(Inst, "RAMScopeGT150GetSysInfo");
	GT150PGT_SetMdlConfigFunc		= (RAMScopeGT150PGT_SetMdlConfigPtr)	::GetProcAddress(Inst, "RAMScopeGT150PGT_SetMdlConfig");
	GT150PGT_ModifyMdlConfigFunc	= (RAMScopeGT150PGT_ModifyMdlConfigPtr)	::GetProcAddress(Inst, "RAMScopeGT150PGT_ModifyMdlConfig");			
	GT150MeasStartFunc				= (RAMScopeGT150MeasStartPtr)			::GetProcAddress(Inst, "RAMScopeGT150MeasStart");
	GT150MeasStopFunc				= (RAMScopeGT150MeasStopPtr)			::GetProcAddress(Inst, "RAMScopeGT150MeasStop");
	GT170SetMeasCondFunc			= (RAMScopeGT170SetMeasCondPtr)			::GetProcAddress(Inst, "RAMScopeGT170SetMeasCond");
	GT170SetMeasChFunc				= (RAMScopeGT170SetMeasChPtr)			::GetProcAddress(Inst, "RAMScopeGT170SetMeasCh");
	GT150SetLoggingInfoFunc			= (RAMScopeGT150SetLoggingInfoPtr)		::GetProcAddress(Inst, "RAMScopeGT150SetLoggingInfo");
	GT150GetBufferDataFunc			= (RAMScopeGT150GetBufferDataPtr)		::GetProcAddress(Inst, "RAMScopeGT150GetBufferData");
	GT150GetLoggingDataFunc			= (RAMScopeGT150GetLoggingDataPtr)		::GetProcAddress(Inst, "RAMScopeGT150GetLoggingData");

	if ((GT150DeviceInitFunc == NULL)			||
		(GT150DeviceExitFunc == NULL)			||
		(GT150AllInitFunc == NULL)				||
		(GT150PGT_SetMdlConfigFunc == NULL)		||
		(GT150PGT_ModifyMdlConfigFunc == NULL)	||
		(GT150MeasStartFunc == NULL)			||
		(GT150MeasStopFunc == NULL)				||
		(GT170SetMeasCondFunc == NULL)			||
		(GT150SetLoggingInfoFunc == NULL)		||
		(GT150GetBufferDataFunc == NULL)		||
		(GT150GetLoggingDataFunc == NULL)		){
		::FreeLibrary(Inst);
		return -1;
	}
	//----------------------------------------------------------------------
	//	#SPC-D195-GT150DeviceInit-000#
	//	Device Open
	//----------------------------------------------------------------------
	if (GT150DeviceInitFunc(&GTUnitNum, &GTKind) != 0){
		::FreeLibrary(Inst);
		return -1;
	}
	//----------------------------------------------------------------------
	//	#SPC-D195-GT150AllInit-000#
	//	Device & API initialization
	//----------------------------------------------------------------------
	if (GT150AllInitFunc(0) != 0){
		GT150DeviceExitFunc();
		::FreeLibrary(Inst);
		return -1;
	}
	//----------------------------------------------------------------------
	//	#SPC-D195-GT150GetSysInfo-000#
	//	Acquire system information
	//----------------------------------------------------------------------
	if (GT150GetSysInfoFunc(0, GTSysinfo) != 0){
		GT150DeviceExitFunc();
		::FreeLibrary(Inst);
		return -1;
	}
	//----------------------------------------------------------------------
	//	#SPC-D195-GT150PGT_SetMdlConfig-000#	
	//				or
	//	#SPC-D195-GT150PGT_ModifyMdlConfig-000#
	//	Setting or Modify probe specific information 
	//	for RAM monitor module
	//----------------------------------------------------------------------
	if (GT150PGT_SetMdlConfigFunc(0, GTSlotErr) != 0){
	//if (GT150PGT_ModifyMdlConfigFunc(0, GTSlotErr) != 0){
		GT150DeviceExitFunc();
		::FreeLibrary(Inst);
		return -1;
	}
	//----------------------------------------------------------------------
	//	#SPC-D195-GT170SetMeasCond-000#
	//	Setting measurement conditions 
	//----------------------------------------------------------------------
	memset(&GTMeasInfo, 0, sizeof(MEASINFO_170));
	GTMeasInfo.RAM.DummyInterval = 100;
	GTMeasInfo.RAM.MeasPeri = 100;
	GTMeasInfo.RAM.MeasUnit = 2;
	if (GT170SetMeasCondFunc(0, 1, &GTMeasInfo) != 0){
		GT150DeviceExitFunc();
		::FreeLibrary(Inst);
		return -1;
	}
	//----------------------------------------------------------------------
	//	#SPC-D195-GT170SetMeasCh-000#
	//	Setting measurement channel
	//----------------------------------------------------------------------
	memset(GTChInfo, 0, sizeof(CHINFO_170)*1);
	GTChInfo[0].RAM.enable = 1;	
	GTChInfo[0].RAM.address = 0x1000;
	GTChInfo[0].RAM.size = 0;
	GTChInfo[0].RAM.sign = 0;
	if (GT170SetMeasChFunc(0, 1, 1, GTChInfo) != 0){
		GT150DeviceExitFunc();
		::FreeLibrary(Inst);
		return -1;
	}
	//----------------------------------------------------------------------
	//	#SPC-D195-GT150SetLoggingInfo-000#
	//	Setting logging information
	//----------------------------------------------------------------------
	memset(&GTLogInfo, 0, sizeof(LOGINFO));
	GTLogInfo.logDevice = 0;
	GTLogInfo.limitHddSize = 0;
	for (int i = 0; i < NUM_MODULE_MAX_170; i++){
		GTLogInfo.mdl[i].BuffSize = 1;
		GTLogInfo.mdl[i].logSize = 1;
	}
	if (GT150SetLoggingInfoFunc(0, &GTLogInfo) != 0){
		GT150DeviceExitFunc();
		::FreeLibrary(Inst);
		return -1;
	}
	//----------------------------------------------------------------------
	//	#SPC-D195-GT150MeasStart-000#
	//	Start measurement
	//----------------------------------------------------------------------
	if (GT150MeasStartFunc(0) != 0){
		GT150DeviceExitFunc();
		::FreeLibrary(Inst);
		return -1;
	}
	//----------------------------------------------------------------------
	//	#SPC-D195-GT150GetBufferData-000#
	//	Acquisition of latest measurement data
	//----------------------------------------------------------------------
	::Sleep(1000);
	GT150GetBufferDataFunc(0, 1, GTPackData, &GTDataNum, &GTLostDataNum);
	::Sleep(1000);
	//----------------------------------------------------------------------
	//	#SPC-D195-GT150MeasStop-000#
	//	Stop measurement
	//----------------------------------------------------------------------
	if (GT150MeasStopFunc(0) != 0){
		GT150DeviceExitFunc();
		::FreeLibrary(Inst);
		return -1;
	}
	//----------------------------------------------------------------------
	//	#SPC-D195-GT150GetLoggingData-000#
	//	Acquisition of held measurement data
	//----------------------------------------------------------------------
	GTDataNum = 100;
	GT150GetLoggingDataFunc(0, 1, 0, 0, GTPackData, &GTDataNum, &GTLostDataNum);
	//----------------------------------------------------------------------
	//	#SPC-D195-GT150DeviceExit-000#
	//	Device Exit
	//----------------------------------------------------------------------
	GT150DeviceExitFunc(); 
	//----------------------------------------------------------------------
	//	Free DLL
	//----------------------------------------------------------------------
	::FreeLibrary(Inst);

	return 0;
}
//--------------------------------<end of file>---------------------------------

