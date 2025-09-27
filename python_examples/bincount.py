def binarycount(bits):

    count = 0
    for i, bit in enumerate(bits):
        if bit == 1:
            count = count + 2**i
    
    return count