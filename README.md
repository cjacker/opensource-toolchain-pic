# opensource toolchain for 8bit PIC MCU

PIC (usually pronounced as "pick") is a family of microcontrollers made by Microchip Technology, derived from the PIC1650 originally developed by General Instrument's Microelectronics Division. The name PIC initially referred to Peripheral Interface Controller, and is currently expanded as Programmable Intelligent Computer. The first parts of the family were available in 1976; by 2013 the company had shipped more than twelve billion individual parts, used in a wide variety of embedded systems. 

PIC micro chips are designed with a Harvard architecture, and are offered in various device families. The baseline and mid-range families use 8-bit wide data memory, and the high-end families use 16-bit data memory. The latest series, PIC32MZ is a 32-bit MIPS-based microcontroller. Instruction words are in sizes of 12-bit (PIC10 and PIC12), 14-bit (PIC16) and 24-bit (PIC24 and dsPIC). The binary representations of the machine instructions vary by family and are shown in PIC instruction listings.

This tutorial focus on 8-bit PIC mcu. aka PIC12/PIC16/PIC18 series.

By the way, MicroChip seems do not care about "opensource" at all, it even does not provide a 'free' and 'full-feature' and 'close-source' compiler for 8-bit PIC. the offcial mplabX IDE use XC8 compiler, and with a free license, you won't get the best optimization, that means you have to buy a pro license.

And nowaday, MicroChip acquired ATMEL and already add AVR support to XC8, I have no idea what will happen to AVR eco-system in future. I really do not recommend PIC today if you have other choices.

Anyway, here is tutorial about opensource toolchain of 8-bit PIC, if you wish to get a feel of PIC MCU. Note the PIC related sources of SDCC and gputils are un-maintained now, this tutorial is only for hobby project, do not use it in product.


# Hardware prerequist

* a PIC12/PIC16/PIC18 dev board
  - If you need to buy new one, I recommend to check the list and sdcc as reference to choose the PIC MCU model opensource toolchain supported.
  - 'Curiosity nano PIC board' from Microchip have an nEDBG debuger on board, it can be used with 'pymcuprog', but usually these new models are lack of opensource compiler support.
  - In this tutorial, I use PIC16F1823(1825) and PIC18F45K20 as example, also use curiosity nano DM164150 with PIC18F57Q43 to demo 'pymcuprog'
* Arduino uno or nano as programmer
* [Optional] PICKIT2 as programmer
  - **NOTE:** NOT PICKIT3 and above, there is no opensource tool at all.

# Toolchain overview

* Compiler: gputils/SDCC and naken_asm
* SDK: shipped with SDCC or baremetal
* Programming tool: a-p-prog with arduino, pk2cmd with PICKIT2, pymcuprog with nEDBG
* Debugger: NO opensource solution

# Compiler

Most Linux distributions shipped SDCC in their repositories. You can install it by yum or apt.

If you really want to build it yourself, at least you need make/bison/flex/libtool/g++/boost development package/zlib development package/etc. installed, and the building process is really simple:
```
./configure --prefix=<where you want to install SDCC>
make
make install
```
If the `prefix` does not set to standard dir (such as '/usr' or '/usr/local'), you need add the `<prefix>/bin` dir to PATH env.

# SDK

The essential headers with pre-defined registers and libs already shipped with SDCC. Generally it divided into two sets: 'pic14' and 'pic16'.
It's a little bit confusing about the 'pic14' and 'pic16' name. Acctually, 'pic14' means '14bit instruction set' and 'pic16' means '16bit instruction set'. thus PIC12 and PIC16 series MCU should use 'pic14' sdk set and PIC18 series should use 'pic16' sdk set.

Here is example code to blink led connect to RC0 of PIC16F1823 breakout board. Usually to blink a led with all sort of MCUs should follow below steps:
- Setup config bits correctly, such as watchdog timer, etc.
- Config specific pin as digital output.
- Toggle the pin and delay some time in a loop

```
// blink.c
// blink the led connect to RC0 of PIC16F1823

#include <pic14regs.h>

#define LED PORTCbits.RC0

// disable watchdog,
unsigned int __at (_CONFIG1) __configword = _WDTE_OFF;

// just delay a number of for loop
void delay(unsigned int count)
{
  unsigned int i;
  for (i = 0; i < count; i++)
    __asm nop __endasm;
}

void main(void)
{
  // portc as digital
  ANSELC = 0;
  // portc as output
  TRISC = 0;
  // or just set rc0 as output
  // TRISC0 = 0;
  // led on
  LED = 1;

  while (1) {
    // toggle led
    LED = ~LED;
    // delay some times
    delay(3000);
  }
}
```

Build it as:
```
sdcc --use-non-free -mpic14 -p16f1823 blink.c
```

Because some PIC header files have a special Microchip license, the arg '--use-non-free' is essential to build PIC codes.

the 'pic14regs.h' header have some macros defined to find the correct header should used with pic model specified by '-p' arg, it can be replaced by '#include <pic14/pic16f1823.h>'.

There are some warning messages when building blink demo code, looks like:

```
blink.asm:93:Message[1304] Page selection not needed for this device. No code generated.
blink.asm:150:Message[1304] Page selection not needed for this device. No code generated.
blink.asm:152:Message[1304] Page selection not needed for this device. No code generated.
message: Using default linker script "/usr/share/gputils/lkr/16f1823_g.lkr".
warning: Relocation symbol "_cinit" [0x0000] has no section. (pass 0)
warning: Relocation symbol "_cinit" [0x0004] has no section. (pass 0)
warning: Relocation symbol "_cinit" [0x0018] has no section. (pass 0)
warning: Relocation symbol "_cinit" [0x001C] has no section. (pass 0)
warning: Relocation symbol "_cinit" [0x0000] has no section. (pass 0)
warning: Relocation symbol "_cinit" [0x0004] has no section. (pass 0)
warning: Relocation symbol "_cinit" [0x0018] has no section. (pass 0)
warning: Relocation symbol "_cinit" [0x001C] has no section. (pass 0)
```

These msgs are generated by 'gputils' and can be ignored.

After build successfully, a 'blink.hex' file will be generated in currect dir.

# Programming

## using Arduino PIC programmer

## using pk2cmd with PICKIT2

## using pymcuprog with nEDGB onboard debugger

# Debug

There is no opensource debug solution exist for PIC.

