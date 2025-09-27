def build_model(x: int):

    mo = [0]

    if x < 3:
        mo.append(False)
    elif x == 3:
        mo.append(None)
    else:
        mo.append(True)

    return mo
