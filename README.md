# opensource toolchain for 8bit PIC MCU

PIC (usually pronounced as "pick") is a family of microcontrollers made by Microchip Technology, derived from the PIC1650 originally developed by General Instrument's Microelectronics Division. The name PIC initially referred to Peripheral Interface Controller, and is currently expanded as Programmable Intelligent Computer. The first parts of the family were available in 1976; by 2013 the company had shipped more than twelve billion individual parts, used in a wide variety of embedded systems. 

PIC micro chips are designed with a Harvard architecture, and are offered in various device families. The baseline and mid-range families use 8-bit wide data memory, and the high-end families use 16-bit data memory. The latest series, PIC32MZ is a 32-bit MIPS-based microcontroller. Instruction words are in sizes of 12-bit (PIC10 and PIC12), 14-bit (PIC16) and 24-bit (PIC24 and dsPIC). The binary representations of the machine instructions vary by family and are shown in PIC instruction listings.

For more info, please refer to: https://en.wikipedia.org/wiki/PIC_microcontrollers

This tutorial focus on 8-bit PIC mcu. aka PIC12/PIC16/PIC18 series.

By the way, MicroChip seems do not care about "opensource" at all, it even does not provide a 'free' and 'full-feature' and 'close-source' compiler for 8-bit PIC. the offcial mplabX IDE use XC8 compiler, and with a free license you won't get the best optimizations, that means you have to buy a pro license.

Anyway, here is tutorial about opensource toolchain of 8-bit PIC, if you wish to get a feel of PIC MCU. 

# Hardware prerequist

* a PIC12/PIC16/PIC18 dev board
  - If you need to buy new one, I recommend to check the list that the opensource toolchain can supported.
  - 'Curiosity nano PIC board' from Microchip have an nEDBG debuger on board, it can be programmed with 'pymcuprog'.
  - In this tutorial, I use PIC16F1823(1825) and PIC18F45K20 as example, also use curiosity nano DM164150 with PIC18F57Q43 to demo 'pymcuprog'
* [PICKIT 2 or 3](https://en.wikipedia.org/wiki/PICkit) as programmer, prefer PICKIT2.
* Arduino uno or nano as programmer

# Toolchain overview

* Compiler: gputils/SDCC for C and gcbasic for basic
  - Since gputils and the PIC part of SDCC is un-maintained now, I recommend gcbasic for PIC development.
* SDK: integrated with Compiler
* Programming tool: pk2cmd-minus (improved pk2cmd) with PICKIT2, pymcuprog with nEDBG, a-p-prog/zeppp with arduino (only LVP)
* Debugger: NO opensource ICE solution

# Compiler

## SDCC

Most Linux distributions shipped SDCC in their repositories. You can install it by yum or apt.

If you really want to build it yourself, at least you need make/bison/flex/libtool/g++/boost development package/zlib development package/etc. installed, and the building process is really simple:
```
./configure --prefix=<where you want to install SDCC>
make
make install
```
If the `prefix` does not set to standard dir (such as '/usr' or '/usr/local'), you need add the `<prefix>/bin` dir to PATH env.

## GCBASIC

[Greate Cow BASIC](http://gcbasic.sourceforge.net/Typesetter/index.php/Home) is a robust and fully functional compiler and assembler for Microchip PIC or Atmel AVR 8-bit microcontroller. It seems have active development and better support than SDCC PIC part, and also support more PIC MCU model than SDCC by default.

GCBASIC can be downloaded from https://sourceforge.net/projects/gcbasic/files/GCBasic%20-%20Linux%20Distribution/

The 'GCB@Syn.rar' password is 'GCB', as mentioned in FAQ:

>Why is the rar File for Linux encrypted?
>
>There are software portals that do nothing other than catalog and provide free software for download. That's not really a big deal, but they are often out of date and offer ancient versions. In addition, they earn advertising revenue that does not benefit the project. Btw. the password is GCB 

To build gcbasic, you need to have freebasic installed. Build and install gcbasic as

```
cd GreatCowBASIC
cat gcbasic-0.99.01-build-fix.patch|patch -p1
cd sources/linuxbuild
./install.sh build
sudo ./install.sh install
```

A patch needed to build gcbasic successfully, the patch 'gcbasic-0.99.01-build-fix.patch' provided in this repo.

After installation, you should have `gcbasic` command on your PATH.

By the way, the source file suffix of gcbasic is 'gcb', it can not be detect automatically as basic source file by editors. for example, you can add

```
autocmd BufNewFile,BufRead *.gcb set syntax=basic
```

to `~/.vimrc`.


# SDK

## SDCC

The essential headers with pre-defined registers and libs already shipped with SDCC. Generally it divided into two sets: 'pic14' and 'pic16'.
It's a little bit confusing about the 'pic14' and 'pic16' name. Actually, 'pic14' means '14bit instruction set' and 'pic16' means '16bit instruction set'. thus PIC12 and PIC16 series MCU should use 'pic14' sdk set and PIC18 series should use 'pic16' sdk set.

Here is example code to blink led connect to RC0 of PIC16F1823 breakout board. Usually to blink a led with all sort of MCUs should follow below steps:
- Setup config bits correctly, such as freq and watchdog timer, etc.
- Config specific pin as digital output.
- Toggle the pin and delay some time in a loop.

```
// blink.c
// blink the led connect to RC0 of PIC16F1823

#include <pic14regs.h>

#define LED PORTCbits.RC0

// disable watchdog timer
unsigned int __at (_CONFIG1) __configword = _WDTE_OFF;

// not accurate, just delay some time
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
    // delay a while
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

By the way, it's not neccesary to look into the codes seriously at this time. every PIC model had it's own register set, although most of them are identical and most of the codes can be re-used, but the code you write for a model more likely is not compatible with other models, it always require some major or minor changes to work.


## GCBASIC

Below is a gcbasic example to blink led connected to F.3:

```basic
' Curiosity Nano DM164150 with PIC18F57Q43
' onboard LED connect to PortF.3

' ----- Configuration
#CHIP 18f57q43
' Comment out above line and uncomment this line to build for 16F1823
'#CHIP 16f1823

Do Forever

    'Lighten LED for 100ms
    PulseOut PortF.3, 100 ms
    ' Comment out above line and uncomment this line for 16F1823 (LED to RC0)
    'PulseOut PortC.0, 100 ms

    'Then wait 900 milliseconds after LED goes off:
    Wait 900 ms

Loop
```

Build it as:

```
makehex.sh blink.gcb
```

A 'blink.hex' will be generated in currect dir.

# Programming

## using pk2cmd-minus with PICKIT2 or PICKIT3

pk2cmd is the official open-source program tool work with PICKIT2, updates by [Miklós Márton](https://github.com/martonmiklos/pk2cmd) to add support for PICkit3, the support for SPI-type MSB1st -family PICs is based on work by [bequest333](https://www.eevblog.com/forum/microcontrollers/pic16f18857-programming-with-pickit2/). 

**['pk2cmd minus' developed by kair](http://kair.us/projects/pickitminus/) has support for [1066 parts](http://kair.us/projects/pickitminus/pk2cmdminus_supported_devices.txt), supports nearly all, if not all, 8-bit PIC microcontrollers.**

For more info, please refer to http://kair.us/projects/pickitminus/.

I make a fork to improve the installation process and other minor changes:

```
git clone https://github.com/cjacker/pk2cmd-minus
cd pk2cmd-minus
make
sudo make install
```

Then you should have 'pk2cmd' and 'pk2-device-file-editor' in your PATH, other resources will be installed to proper dir automatically.

To run 'pk2-device-file-editor', you should have mono and mono-basic installed.


If you want to build it from [the upstream source code](http://kair.us/projects/pickitminus/):

```
mkdir build && cd build
wget http://kair.us/projects/pickitminus/PK2CMD_SourceV1_23_00.zip
wget https://raw.githubusercontent.com/cjacker/opensource-toolchain-pic/main/pk2_devicefile_osfile_paths.patch
wget https://raw.githubusercontent.com/cjacker/opensource-toolchain-pic/main/60-pickit.rules

unzip PK2CMD_SourceV1_23_00.zip

# apply global database file path patch
cat pk2_devicefile_osfile_paths.patch | patch -p1 -d PK2CMD_SourceV1_23_00

cd PK2CMD_SourceV1_23_00/pk2cmd/pk2cmd
make linux
cd ../../../

# install cmd
sudo install -m0755 PK2CMD_SourceV1_23_00/pk2cmd/pk2cmd/pk2cmd /usr/bin

sudo mkdir -p /usr/share/pk2

# install device database
sudo install -m0644 PK2CMD_SourceV1_23_00/pk2cmd/pk2cmd/PK2DeviceFile.dat /usr/share/pk2/

# install adapter firmware
sudo cp PK2CMD_SourceV1_23_00/pk2cmd/release/*.hex /usr/share/pk2/

# install udev rule to avoid using sudo
sudo install -m0644 60-pickit.rules /etc/udev/rules.d/
```

If you want to edit the 'PK2DeviceFile.dat' to add new devices, you can use [device file editor](https://sites.google.com/site/pk2devicefileeditor/) created by dougy83.

If you don't mind to use the prebuilt binary of pk2cmd-minus, you can use http://kair.us/projects/pickitminus/pk2cmd-x86_64.AppImage directly.



**To be written.**


## using zeppp with Arduino as PIC programmer

[ZEPPP](https://github.com/battlecoder/zeppp) is a PIC programmer that requires only an Arduino-compatible board and a small command-line PC utility (CLI) to read, write, erase and verify several LVP-capable PIC microcontrollers via ICSP (In-Circuit Serial Programming).

Currently ZEPPP supports the following PIC devices:

* 16F87, 16F88
* 16F627A, 16F628A, 16F648A
* 16F873A, 16F874A, 16F876A, 16F877A
* 16F870, 16F871, 16F872, 16F873, 16F874, 16F876, 16F877
* 16F882, 16F883, 16F884, 16F886, 16F887
  + Calibration word and PGM block writes not yet supported in this family of microcontrollers.

And can work with all the memory areas from the supported PICs (Program memory, EEPROM, Config words and User IDs).

Here I make a fork to fix some issues, prepare a UNO or NANO and upload 'ZEPPP' sketch to it, you need to have 'arduino-cli' installed:

```
git clone https://github.com/battlecoder/zeppp.git
# to support PIC16F887
git checkout experimental/PIC16F88X

cd zeppp/ZEPPP
make upload TARGET=nano -f Makefile.linux
```

If you use Arduino UNO, change 'TARGET=nano' to 'TARGET=uno'.

If you want to build ZEPPP-cli instead of using pre-built 'zeppp-cli.jar':

```
cd ZEPPP-cli
mvn clean package
```

Then wire it up as:

```
+--------------+      +--------------+       +----------------+
|              |      |    Arduino   |       |      PIC       |
|              |      |        (5V)  +-------+ (VCC)          |
|              |      |              |       |                |
|              |      |        (GND) +-------+ (GND)          |
|              | USB  |              |       |                |
|      PC      +------+        (D6)  +-------+ (MCLR)         |
|              |      |              |       |                |
|              |      |        (D7)  +-------+ (PGD)          |
|              |      |              |       |                |
|              |      |        (D8)  +-------+ (PGC)          |
|              |      |              |       |                |
|              |      |        (D9)  +-------+ (PGM)          |
|              |      |              |       |                |
+--------------+      +--------------+       +----------------+
```

**NOTE:** if the target is not 5V voltage tolarence, you should supply the power seperately.

Then program it:
```
java -jar zeppp-cli.jar -c /dev/ttyUSB0 -wait 2000 -i blink.hex -p -va
```

For more usage of zeppp-cli, please refer to https://github.com/battlecoder/zeppp.


## using a-p-prog with Arduino as PIC programmer

[a-p-prog](https://github.com/jaromir-sukuba/a-p-prog) is a 8-bit PIC programmer built around AVR/Arduino platform, if you have a Arduino UNO or NANO, then you can use it as 8bit PIC programmer.

It support a lot of 8-bit LVP PIC models and very easy to build.

Here I make a fork to improve the usablity and add PIC16F1823 support, you can download and built it yourself:

```
git clone https://github.com/cjacker/a-p-prog.git
cd /a-p-prog/sw
make -f Makefile.linux
sudo make install PREFIX=/usr -f Makefile.linux
```

`pp3` programmer and the device database will be installed.

Then prepare a UNO or NANO and upload the 'pp' sketch to it, you need to have 'arduino-cli' installed:

```
cd fw/pp
make upload TARGET=uno -f Makefile.linux
```

For Arduino NANO, change 'TARGET=uno' to 'TARGET=nano'.

If you do not have 'arduino-cli' installed, you can use arduino IDE to open the 'pp.ino' and upload it.

Before wire it up to the target PIC development board to program, you need to **make sure**:

* Check the datasheet to identify which pin is the 'ICSPDAT', 'ICSPCLK' and 'MCLR' pin.
  - ISCPDAT (data) also called 'PGD' pin
  - ICSPCLK (clock) also called 'PGC' pin
  - MCLR is the RESET pin

* Check the datasheet to find out Whether the target MCU is 5v voltage tolerance or not.
  - If the target is NOT 5v tolerance, you should **NOT** wire up the VCC line to Arduino, and should supply power seperately to the target board.
  - You also need to use 1K resistors between Arduino and PIC target board.

Since PIC16F1823 is 5v voltage tolerance, we can use the 5v pin of Arduino to supply power directly. 

Wire it up as:
```
+--------------+      +--------------+       +----------------+
|              |      |    Arduino   |       |   PIC16F1823   |
|              |      |        (5V)  +-------+ (VCC)          |
|              |      |              |       |                |
|              |      |        (GND) +-------+ (GND)    (RC0) +-------(Resistor)---+
|              | USB  |              |       |                |                    |
|      PC      +------+        (A3)  +-------+ (MCLR)         |                    |
|              |      |              |       |                |                  (LED)
|              |      |        (A1)  +-------+ (PGD)          |                    |
|              |      |              |       |          (GND) +--------------------+
|              |      |        (A0)  +-------+ (PGC)          |
|              |      |              |       |                |
+--------------+      +--------------+       +----------------+

```

And program it:
```
pp3 -c /dev/ttyUSB0 -t 16f1823 blink.hex
```

The output looks like:
```
PP programmer, version 0.99
Sleeping for 2000 ms while arduino bootloader expires
Device ID: 2720
Programming FLASH (4096 B in 128 pages)
Programming config
Verifying FLASH (4096 B in 128 pages)
Verifying config
```

After programming successfully, the LED should blink.

## using pymcuprog with Curiosity Nano PIC board

These years, MicroChip officially provide some Curiosity Nano boards of PIC or AVR, it has an onboard nEDBG debugger integrated and can be used as programmer and debugger with MPLABX directly. 

With such a board, you do NOT need to buy a PICKIT, it can be programmed with 'pymcuprog' directly.

I have a DM164150 CNANO baord with PIC18F57Q43, and it can not supported by SDCC (device headers is not include in SDCC), thus I use the gcbasic to build a blink demo for it (refer to above gcbasic section for example code).

After 'blink.hex' generated, '[pymcuprog](https://github.com/microchip-pic-avr-tools/pymcuprog)' from MicroChip can be used to program it.

The installation of pymcuprog is very simple:
```
pip install pymcuprog
```

After pymcuprog installed, connect Curiosity Nano PIC board to PC via USB cable and run:

```
pymcuprog ping
```

The output looks like:
```
Connecting to anything possible
Connected to nEDBG CMSIS-DAP from Microchip (serial number MCHP3290041800001449)
Debugger firmware version 1.22.73
Debugger hardware revision 0
Device mounted: 'pic18f57q43'
No device specified.  Using on-board target (pic18f57q43)
Unable to start session: Unable to setup stack using the given packpath: 'None'
```

Note the last line **Unable to start session: Unable to setup stack using the given packpath: 'None'**, you have to install MPLABX IDE and find the corresponding pack of your MCU from it. for 'pic18f57q43', the pack located at `/opt/microchip/mplabx/v6.00/packs/Microchip/PIC18F-Q_DFP/1.13.211/scripts/pic18f57q43`.

Re-run with this packpath:

```
pymcuprog ping -p /opt/microchip/mplabx/v6.00/packs/Microchip/PIC18F-Q_DFP/1.13.211/scripts/pic18f57q43 
```

the output looks like:

```
Connecting to anything possible
Connected to nEDBG CMSIS-DAP from Microchip (serial number MCHP3290041800001449)
Debugger firmware version 1.22.73
Debugger hardware revision 0
Device mounted: 'pic18f57q43'
No device specified.  Using on-board target (pic18f57q43)
Pinging device...
Ping response: 74C0
Done.
```

Program it:

```
pymcuprog write -p /opt/microchip/mplabx/v6.00/packs/Microchip/PIC18F-Q_DFP/1.13.211/scripts/pic18f57q43 -f blink.hex  
```

The output as:
```
Connecting to anything possible
Connected to nEDBG CMSIS-DAP from Microchip (serial number MCHP3290041800001449)
Debugger firmware version 1.22.73
Debugger hardware revision 0
Device mounted: 'pic18f57q43'
No device specified.  Using on-board target (pic18f57q43)
Pinging device...
Ping response: 74C0
Writing from hex file...
Writing flash...
Writing flash...
Writing flash...
Writing config_words...
Done.
```

## other program solutions

There are a lot of opensource (both hardware and software) program solutions for PIC, list some of them here for your reference:
* http://hyvatti.fi/~jaakko/pic/picprog.html
* http://usbpicprog.org/
* https://github.com/rweather/ardpicprog


# Debug

There isn't opensource debug software exist for PIC. you can use 'mdb' - the official pic debugger program of Microchip shipped with MPLABX IDE from command line, it's not opensource, please find out the usage by yourself.

And you can also have a try of [picsim](https://github.com/lcgamboa/picsim) and [picsimlab](https://github.com/lcgamboa/picsimlab) with very limited hardware support.
