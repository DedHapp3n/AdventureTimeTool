def dice_expression(dice_count, keep_mode=""):
    try:
        count = max(1, int(dice_count))
    except Exception:
        count = 1
    if count == 1:
        return "1d20"
    if keep_mode in {"kh1", "kl1"}:
        return f"{count}d20{keep_mode}"
    return f"{count}d20"


def advantage_dice_expression(advantages, disadvantages):
    try:
        net = int(advantages) - int(disadvantages)
    except Exception:
        net = 0
    if net > 0:
        return dice_expression(1 + net, "kh1")
    if net < 0:
        return dice_expression(1 + abs(net), "kl1")
    return "1d20"
