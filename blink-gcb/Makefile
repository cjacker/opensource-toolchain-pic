SRC=blink.gcb

MAKEHEX=makehex.sh

all: $(SRC:.gcb=.hex)

$(SRC:.gcb=.hex): $(SRC)
	makehex.sh $^

flash_16f1823_with_arduino:
	pp3 -t 16f1823 blink.hex -c /dev/ttyUSB0

flash_curiosity_nano_18f57q43:
	pymcuprog write -p /usr/share/pymcuprog-packs/pic18f57q43 -f blink.hex
	
clean:
	rm -f $(SRC:.gcb=.hex) $(SRC:.gcb=.lst) $(SRC:.gcb=.asm) $(SRC:.gcb=.html)

.PHONY: all clean
