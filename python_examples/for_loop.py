NUMBERS = [1, 2, 3, 4]


def n_sum(n: int):
    total = 0
    for i in range(n):
        total += i
    total += 4000
    return total

if __name__ == "__main__":
    for n in NUMBERS:
        n_sum(n)