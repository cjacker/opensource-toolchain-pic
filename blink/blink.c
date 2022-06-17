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

