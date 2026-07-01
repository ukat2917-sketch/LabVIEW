/*****************************************************************************
									Copyright(c) 2017 DTS INSIGHT CORPORATION
Function：	RAMScope Hardware

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
//#include "GTHard.h"
#pragma once

#define	TYPE_GTKIND_150				0
#define	TYPE_GTKIND_12x				1
#define	TYPE_GTKIND_170				2

#define	TYPE_RAMMONITOR_MODULE		0x00
#define	TYPE_CAN_MODULE				0x02
#define	TYPE_AD_MODULE				0x03
#define	TYPE_CTRL_USB_MODULE		0x0E
#define	TYPE_MODULE_DISCONNECT		0x0F

#define	NUM_MODULE_MAX				16
#define	NUM_MODULE_MAX_150			5
#define	NUM_MODULE_MAX_170			10

#define	NUM_CH_MAX_RAM150			1024
#define	NUM_CH_MAX_ADC150			6
#define	NUM_CH_MAX_RAM170			2048
#define	NUM_CH_MAX_ADC170			4
