"""
Contains functions can be used in MP-SPDZ circuits.
"""

from Compiler.library import print_ln, for_range
from Compiler.types import sint, sfix, Matrix, sfloat, Array
from Compiler.util import if_else
from Compiler.mpc_math import sqrt, exp2_fx, log2_fx


MAGIC_NUMBER = 999

# To enforce round to the nearest integer, instead of probabilistic truncation
# Ref: https://github.com/data61/MP-SPDZ/blob/e93190f3b72ee2d27837ca1ca6614df6b52ceef2/doc/machine-learning.rst?plain=1#L347-L353
sfix.round_nearest = True


def read_data(party_index: int, num_columns: int, num_rows: int) -> Matrix:
    """
    Read data from each party's input file to a Matrix in MP-SPDZ circuit.
    """
    data = Matrix(num_columns, num_rows, sint)
    # TODO: use @for_range_opt instead?
    for i in range(num_columns):
        for j in range(num_rows):
            data[i][j] = sint.get_input_from(party_index)
    return data


def print_data(data: Matrix):
    """
    Print the data in the Matrix.
    """
    num_columns = data.shape[0]
    num_rows = data.shape[1]
    for i in range(num_columns):
        for j in range(num_rows):
            print_ln("data[{}][{}]: %s".format(i, j), data[i][j].reveal())


def _mean(data: list[sint]) -> (float, int):
    total = sum(if_else(i != MAGIC_NUMBER, i, 0) for i in data)
    count = sum(if_else(i != MAGIC_NUMBER, 1, 0) for i in data)
    return total / count, count


def _variance(data: list[sint], use_bessels: bool) -> float:
    # calculate mean of the data excluding magic numbers
    mean, eff_size = _mean(data)

    # replace magic number w/ mean to skip magic number in for loop below
    data = Array.create_from(if_else(n != MAGIC_NUMBER, n, mean) for n in data)

    eff_data_sum = sfloat(0)
    for n in data:
        eff_data_sum += (n - mean) ** 2

    if use_bessels:
        eff_size -= 1

    return eff_data_sum / eff_size


# Top 5 functions to implement

def mean(data: list[sint]):
    return _mean(data)[0]


def median(data: list[sint]):
    # TODO: Check if Array.create_from is properly constrained // if I dont put reference, it's just from the mp-spdz doc itself
    data = Array.create_from(data)
    # TODO: Check if there's a need to use sint(0), can we just use 0? would that violate constraint?
    median_odd = sint(0)
    median_even = sint(0)
    data.sort()
    size = sum(if_else(i!= MAGIC_NUMBER, 1, 0) for i in data)

    # TODO: Check if for_range is any different than naive Python for-loop
    @for_range(len(data))
    def _(i):
        # TODO: Check if wrapping sint() makes sense/ properly constrained
        # TODO: Check why we cannot just use size.int_div(2) -> it returns wrong result, so now we use the method below instead.
        median_odd.update(median_odd+(size==2*sint(i)+size%2)*data[i])
        # TODO: Check if there's the need to use update: See example in Compiler.library.for_range(start, stop=None, step=None) in the mp-spdz doc itself
        median_even.update(median_even+(size==2*sint(i)+size%2)*data[i]/2+(size-2==2*sint(i)+size%2)*data[i]/2)
    # TODO: Check if size%2 is properly constrained
    return (size%2)*median_odd + (1-size%2)*median_even


def join(data1: Matrix, data2: Matrix, data1_column_index: int, data2_column_index: int) -> Matrix:
    """
    Join two matrices based on the matching index in the specified columns.

    :param data1: The first matrix
    :param data2: The second matrix
    :param data1_column_index: The column index in data1 to match with data2_column_index
    :param data2_column_index: The column index in data2 to match with data1_column_index

    For example, if data1 = [
        [0, 1, 2, 3],
        [152, 160, 170, 180]
    ], data2 = [
        [3, 0, 4],
        [50, 60, 70],
    ], data1_column_index = 0, data2_column_index = 0, then the output will be [
        [0, 1, 2, 3],
        [152, 160, 170, 180],
        [0, MAGIC_NUMBER, MAGIC_NUMBER, 3],
        [60, MAGIC_NUMBER, MAGIC_NUMBER, 50],
    ]
    """
    # E.g. [2, 4]
    num_columns_1 = data1.shape[0]
    num_rows_1 = data1.shape[1]

    # E.g. [2, 3]
    num_columns_2 = data2.shape[0]
    num_rows_2 = data2.shape[1]

    new_data = Matrix(num_columns_1 + num_columns_2, num_rows_1, sint)
    # Initialize the first part of the matrix with data1
    for i in range(num_columns_1):
        for j in range(num_rows_1):
            new_data[i][j] = data1[i][j]
    # Initialize the rest of the matrix with MAGIC_NUMBER
    for i in range(num_columns_2):
        for j in range(num_rows_1):
            new_data[num_columns_1 + i][j] = MAGIC_NUMBER

    # Check the matching index in data1 and data2
    for i in range(num_rows_1):
        # Find the corresponding index in data2[data2_column] for data1[data1_column][i]
        id_in_data1 = data1[data1_column_index][i]
        for j in range(num_rows_2):
            # Now checking if data2[data2_column][j] is the same as data1[data1_column][i]
            id_in_data2 = data2[data2_column_index][j]
            match = id_in_data1 == id_in_data2
            # If the match is found, set the entire row of data2[data2_column] to the new_data
            for k in range(num_columns_2):
                new_data[num_columns_1 + k][i] = if_else(
                    match,
                    data2[k][j],
                    new_data[num_columns_1 + k][i]
                )
    return new_data


def covariance(data1: list[sint], data2: list[sint]):
    n = len(data1)
    mean1, count = _mean(data1)
    mean2, _ = _mean(data2)
    data1 = Array.create_from(if_else(i!=MAGIC_NUMBER, i, mean1) for i in data1)
    data2 = Array.create_from(if_else(i!=MAGIC_NUMBER, i, mean2) for i in data2)
    # TODO: Check if there's a need to use sfloat(0), can we do something like 0.0
    x = sfloat(0)
    @for_range(n)
    def _(i):
        x.update(x+(data1[i]-mean1)*(data2[i]-mean2))
    return x/(count-1)


def correlation(data1: list[sint], data2: list[sint]):
    n = len(data1)
    mean1, count = _mean(data1)
    mean2, _ = _mean(data2)
    data1 = Array.create_from(if_else(i!=MAGIC_NUMBER, i, mean1) for i in data1)
    data2 = Array.create_from(if_else(i!=MAGIC_NUMBER, i, mean2) for i in data2)
    numerator = sfloat(0)
    denominator1 = sfloat(0)
    denominator2 = sfloat(0)
    @for_range(n)
    def _(i):
        numerator.update(numerator+(data1[i]-mean1)*(data2[i]-mean2))
        denominator1.update(denominator1+(data1[i]-mean1).square())
        denominator2.update(denominator2+(data2[i]-mean2).square())
    # Check if wrapping sfix() is properly constrainted.
    return numerator/(sqrt(sfix(denominator1))*sqrt(sfix(denominator2)))


def where(_filter: list[sint], data: list[sint]):
    n = len(data)
    data = Array.create_from(data)
    _filter = Array.create_from(_filter)
    res = sint.Array(n)
    @for_range(n)
    def _(i):
        res[i] = if_else(_filter[i], data[i], MAGIC_NUMBER)
    return res


def geometric_mean(data: list[sint]):
    log_sum = sum(if_else(i != MAGIC_NUMBER, log2_fx(i), 0) for i in data)
    num_log_sums = sum(if_else(i != MAGIC_NUMBER, 1, 0) for i in data)
    exponent = log_sum / num_log_sums

    return exp2_fx(exponent)


def mode(data: list[sint]):
    n = len(data)
    data = Array.create_from(data)
    freqs = sint.Array(n)

    # find frequency of each element in data
    for i, x in enumerate(data):
        freqs[i] = if_else(x == MAGIC_NUMBER, 0,
            sum(if_else(x == data[i], 1, 0) for x in data))

    # find the highest frequency
    highest_freq = sint(0)
    @for_range(n)
    def _(i):
        highest_freq.update(
            if_else(freqs[i].greater_than(highest_freq),
                freqs[i],
                highest_freq
        ))

    # get the first occurrence of the highest frequency element in data
    highest = sint(0)
    @for_range(n-1, -1, -1)
    def _(i):
        highest.update(if_else(freqs[i] == highest_freq,
            data[i],
            highest
        ))

    return highest


def variance(data: list[sint]):
    return _variance(data, True)


def linear_regression(xs: list[sint], ys: list[sint]):
    # zip(xs, ys) is a list of data points

    xs = Array.create_from(xs)
    ys = Array.create_from(ys)

    # calculate slope
    covar = covariance(xs, ys)
    var = variance(xs)
    slope = covar / var

    # calculate intercept
    x_mean = _mean(xs)[0]
    y_mean = _mean(ys)[0]
    intercept = y_mean - slope * x_mean

    res = sfix.Array(2)
    res.assign([slope, intercept])
    return res


def harmonic_mean(data: list[sint]):
    eff_size = sum(if_else(n != MAGIC_NUMBER, 1, 0) for n in data)
    eff_inv_total = sum(if_else(n != MAGIC_NUMBER, sfloat(1/n), 0) for n in data)
    eff_inv_mean = eff_inv_total / eff_size
    return 1 / eff_inv_mean


def pvariance(data: list[sint]):
    return _variance(data, False)


def pstdev(data: list[sint]):
    pvar = _variance(data, False)
    return sqrt(sfix(pvar))


def stdev(data: list[sint]):
    var = _variance(data, True)
    return sqrt(sfix(var))

