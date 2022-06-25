SRC=blink.c

CC=sdcc
FAMILY=pic14

# Add your part model here.
PROC=16f877a
#PROC=16f1823

SRCS = blink.c

target = blink

all: $(target).hex

OBJECTS = $(notdir $(SRCS:.c=.o))
vpath %.c $(sort $(dir $(SRCS)))

%.o: %.c Makefile
	$(CC) --use-non-free -m$(FAMILY) -p$(PROC) -Dpic$(PROC) -c $< -o $@

$(target).hex: $(OBJECTS)
	$(CC) --use-non-free -m$(FAMILY) -p$(PROC) -Dpic$(PROC) $^ -o $@

flash: $(target).hex
	 pk2cmd -P pic$(PROC) -M -R -T -F $(target).hex

clean:
	rm -f $(SRC:.c=.asm) $(SRC:.c=.cod) $(SRC:.c=.hex) $(SRC:.c=.lst) $(SRC:.c=.o)

.PHONY: all clean
