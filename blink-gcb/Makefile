TARGET=16f690
#TARGET=16f1823
#TARGET=cnano_18f57q43
#TARGET=18f45k20

SRC=blink.gcb

MAKEHEX=makehex.sh

all: $(SRC:.gcb=.hex)

$(SRC:.gcb=.hex): $(SRC)
	makehex.sh $^

flash: $(SRC:.gcb=.hex)
ifeq ($(MCU_TYPE), cnano_18f57q43)
	pymcuprog write -p /usr/share/pymcuprog-packs/pic18f57q43 -f blink.hex
else
# using a-p-prog with arduino to program
#pp3 -t $(TARGET) blink.hex -c /dev/ttyUSB0
	pk2cmd -P pic$(TARGET) -M -F blink.hex -T
endif

clean:
	rm -f $(SRC:.gcb=.hex) $(SRC:.gcb=.lst) $(SRC:.gcb=.asm) $(SRC:.gcb=.html)

.PHONY: all clean
