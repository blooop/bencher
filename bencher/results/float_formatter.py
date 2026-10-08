# from https://stackoverflow.com/questions/22989372/how-to-format-a-floating-number-to-maximum-fixed-width-in-python

from __future__ import annotations


class FormatFloat:
    def __init__(self, width: int = 8) -> None:
        self.width = width
        self.maxnum = int("9" * (width - 1))  # 9999999
        self.minnum = -int("9" * (width - 2))  # -999999

    def __call__(self, x: float) -> str:
        # for small numbers
        # if -999,999 < given < 9,999,999:
        if self.minnum < x < self.maxnum:
            o = f"{x:{self.width - 1}}"

            # converting int to float without adding zero
            if "." not in o:
                o += "."

            # float longer than 8 will need rounding to fit width
            elif len(o) > self.width:
                o = str(round(x, self.width - 1 - str(x).index(".")))
                if len(o) < self.width:
                    o += (self.width - len(o)) * "0"

        else:
            # for exponents
            # added a loop for super large numbers or negative as "-" is another char
            # Added max(max_char, 5) to account for max length of less
            #     than 5, was having too much fun
            # TODO: can i come up with a threshold value for these up front,
            #     so that i dont have to do this calc for every value??
            for n in range(max(self.width, 5) - 5, 0, -1):
                fill = f".{n}e"
                o = f"{x:{fill}}".replace("+0", "+")

                # if all good stop looping
                if len(o) == self.width:
                    break
            else:
                raise ValueError(f"Number is too large to fit in {self.width} characters", x)
        return o
