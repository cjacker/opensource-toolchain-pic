#TARGET=16f690
#TARGET=16f877a
TARGET=16f1823
#TARGET=cnano_18f57q43
#TARGET=18f45k20

SRC=blink.jal

JALV2=jalv2

all: $(SRC:.jal=.hex)

$(SRC:.jal=.hex): $(SRC)
	jalv2 $^ -s /opt/jallib/lib

flash: $(SRC:.jal=.hex)
	pk2cmd -P pic$(TARGET) -M -R -T -F blink.hex

clean:
	rm -f $(SRC:.jal=.hex) $(SRC:.jal=.cod) $(SRC:.jal=.asm)

.PHONY: all clean
