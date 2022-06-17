SRC=blink.gcb

MAKEHEX=makehex.sh

all: $(SRC:.gcb=.hex)

$(SRC:.gcb=.hex): $(SRC)
	makehex.sh $^

clean:
	rm -f $(SRC:.gcb=.hex) $(SRC:.gcb=.lst) $(SRC:.gcb=.asm) $(SRC:.gcb=.html)

.PHONY: all clean
