// blink.c
// blink the led, connect to RC0 of PIC16F1823, connect to RD0 of PIC16F877A

//#include <pic14regs.h>

#if defined(pic16f877a)
	#include <pic14/pic16f877a.h>
	unsigned int __at (_CONFIG) __configword = _FOSC_HS & _WDT_OFF & _LVP_OFF;
	#define LED RD0
#elif defined(pic16f1823)
	#include <pic14/pic16f1823.h>
	unsigned int __at (_CONFIG1) __configword = _WDTE_OFF;
	#define LED PORTCbits.RC0
#endif

// not accurate, just delay some time
void delay(unsigned int count)
{
  unsigned int i;
  for (i = 0; i < count; i++)
    __asm nop __endasm;
}

void main(void)
{
#if defined(pic16f1823)
  // portc as digital
  ANSELC = 0;
  // portc as output
  TRISC = 0;
  // or just set rc0 as output
  // TRISC0 = 0;
#endif

#if defined(pic16f877a)
  // portd as output
  TRISD0 = 0;
#endif

  // led on
  LED = 1;

  while (1) {
    // toggle led
    LED = ~LED;
    // delay a while
    delay(3000);
  }
}

