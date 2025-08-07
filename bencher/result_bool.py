import bencher as bch
import numpy as np

class ResultBool(bch.ResultBase):
    """A result type for boolean results that averages over repeats for bar plots."""

    def reduce(self, data, **kwargs):
        # If data is boolean or 0/1, take the mean (success rate)
        arr = np.asarray(data)
        return arr.mean()

    def to_bar(self, data, **kwargs):
        # For bar plots, show the mean (success rate)
        return self.reduce(data, **kwargs)
