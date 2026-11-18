// Box.asm - Nand2Tetris Capstone, Part C
// Author : Vansh Nibhoria (Roll No. 2501730240, K = 40)
//
// Box parameters (K = 40):
//   start row = 40  -> base address = SCREEN + 32*40 = 16384 + 1280 = 17664
//   height    = 20 rows (rows 40..59)
//   width     = 16 * ((40 mod 4) + 1) = 16 pixels = exactly 1 word per row
//
// Behaviour: loop forever. If ANY key is pressed (KBD != 0) paint the box
// black (-1 = 1111111111111111); otherwise paint it white (0).
// Each screen row is 32 words, so the next row is address + 32.

(MAIN)
    @KBD
    D=M                 // D = keyboard buffer
    @BLACK
    D;JNE               // any key pressed -> black
    @color
    M=0                 // no key -> white
    @PAINT
    0;JMP

(BLACK)
    @color
    M=-1                // all 16 pixels set

(PAINT)
    @17664              // SCREEN + 32*40
    D=A
    @addr
    M=D                 // addr = first word of the box

    @20
    D=A
    @count
    M=D                 // count = 20 rows left

(ROW)
    @color
    D=M                 // D = pattern to write
    @addr
    A=M                 // A = current screen word
    M=D                 // draw / clear this row

    @32
    D=A
    @addr
    M=D+M               // addr += 32 (next row, same column)

    @count
    M=M-1               // one row done
    D=M
    @ROW
    D;JGT               // more rows? repeat

    @MAIN
    0;JMP               // poll the keyboard again
