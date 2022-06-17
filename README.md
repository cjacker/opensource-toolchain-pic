# opensource toolchain for 8bit pic MCU

PIC (usually pronounced as "pick") is a family of microcontrollers made by Microchip Technology, derived from the PIC1650 originally developed by General Instrument's Microelectronics Division. The name PIC initially referred to Peripheral Interface Controller, and is currently expanded as Programmable Intelligent Computer. The first parts of the family were available in 1976; by 2013 the company had shipped more than twelve billion individual parts, used in a wide variety of embedded systems. 

PIC micro chips are designed with a Harvard architecture, and are offered in various device families. The baseline and mid-range families use 8-bit wide data memory, and the high-end families use 16-bit data memory. The latest series, PIC32MZ is a 32-bit MIPS-based microcontroller. Instruction words are in sizes of 12-bit (PIC10 and PIC12), 14-bit (PIC16) and 24-bit (PIC24 and dsPIC). The binary representations of the machine instructions vary by family and are shown in PIC instruction listings.

This tutorial focus on 8-bit PIC mcu. aka PIC12/PIC16/PIC18 series.

By the way, MicroChip seems do not care about "opensource" at all, it even does not provide a 'free' and 'full-feature' and 'close-source' compiler for 8-bit PIC. the offcial mplabX IDE use XC8 compiler, and with a free license, you won't get the best optimization, that means you have to buy a pro license.

And nowaday, MicroChip acquired ATMEL and add AVR support to XC8, I have no idea what will happen to AVR eco-system in future.

I really do not recommend PIC today if you have other choices.

Anyway, here is tutorial about opensource toolchain of 8-bit PIC, if you wish to get a feel of PIC MCU.


# Hardware prerequist

* a PIC12/PIC16/PIC18 dev board
  - If you need to buy new one, I recommend take the list as reference to choose the PIC MCU model.
  - 'Curiosity nano PIC board' from Microchip have an nEDBG debuger on board, it can be used with 'pymcuprog', but usually these models are lack of opensource compiler support.
* Arduino uno or nano as programmer
* [Optional] PICKIT2 as programmer
  - **NOT** PICKIT3 and above, there is no opensource tool at all.

# Toolchain overview

* Compiler: gputils/SDCC and naken_asm
* SDK: shipped with SDCC or baremetal
* Programming tool: a-p-prog with arduino, pk2cmd with PICKIT2, pymcuprog with nEDBG
* Debugger: NO opensource solution

