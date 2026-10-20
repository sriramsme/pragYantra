import math
from math import comb, perm
from typing import Dict, Union, List, Callable, Tuple
import numpy as np
import matplotlib.pyplot as plt
from scipy import integrate
from scipy.optimize import newton
from ..entity_models import CARDINAL, DATE

def add(items:List[CARDINAL]):
    """
    Returns the sum of a and b.
    """
    return sum([int(item.value) for item in items])

def subtract(a: CARDINAL, b: CARDINAL):
    """
    Returns the difference between a and b.
    """
    return a.value - b.value

def multiply(items:List[CARDINAL]):
    """
    Returns the product of a and b.
    """
    return np.prod([item.value for item in items])

def divide(a: CARDINAL, b: CARDINAL) -> float:
    """
    Returns the quotient of a divided by b.
    """
    if b.value == 0:
        return "Error: Division by zero"
    return a.value / b.value

def square_root(a: CARDINAL) -> float:
    """
    Returns the square root of a.
    """
    if a.value < 0:
        return "Error: Negative input for square root"
    return a.value ** 0.5

def percentage(part: CARDINAL, whole: CARDINAL) -> float:
    """
    Returns the percentage of part with respect to whole.
    """
    if whole.value == 0:
        return "Error: Whole is zero"
    return (part.value / whole.value) * 100


def sine(x: CARDINAL) -> float:
    """
    Returns the sine of x (x in radians).
    """
    return math.sin(x.value)

def cosine(x: CARDINAL) -> float:
    """
    Returns the cosine of x (x in radians).
    """
    return math.cos(x.value)

def tangent(x: CARDINAL) -> float:
    """
    Returns the tangent of x (x in radians).
    """
    return math.tan(x.value)

def inverse_sine(x: CARDINAL) -> float:
    """
    Returns the inverse sine (arcsin) of x.
    """
    if x.value < -1 or x.value > 1:
        return "Error: Input out of range for arcsin"
    return math.asin(x.value)

def inverse_cosine(x: CARDINAL) -> float:
    """
    Returns the inverse cosine (arccos) of x.
    """
    if x.value < -1 or x.value > 1:
        return "Error: Input out of range for arccos"
    return math.acos(x.value)

def inverse_tangent(x: CARDINAL) -> float:
    """
    Returns the inverse tangent (arctan) of x.
    """
    return math.atan(x.value)

def natural_log(x: CARDINAL) -> float:
    """
    Returns the natural logarithm (ln) of x.
    """
    if x.value <= 0:
        return "Error: Non-positive input for ln"
    return math.log(x.value)

def common_log(x: CARDINAL) -> float:
    """
    Returns the common logarithm (log base 10) of x.
    """
    if x.value <= 0:
        return "Error: Non-positive input for log base 10"
    return math.log10(x.value)

def exponential(x: CARDINAL) -> float:
    """
    Returns e raised to the power of x.
    """
    return math.exp(x.value)

def power(x: CARDINAL, y: CARDINAL) -> float:
    """
    Returns x raised to the power of y.
    """
    return math.pow(x.value, y.value)

def factorial(n: CARDINAL) -> int:
    """
    Returns the factorial of n.
    """
    if n.value < 0:
        return "Error: Factorial of negative number"
    return math.factorial(int(n.value))

def sinh(x: CARDINAL) -> float:
    """
    Returns the hyperbolic sine of x.
    """
    return math.sinh(x.value)

def cosh(x: CARDINAL) -> float:
    """
    Returns the hyperbolic cosine of x.
    """
    return math.cosh(x.value)

def tanh(x: CARDINAL) -> float:
    """
    Returns the hyperbolic tangent of x.
    """
    return math.tanh(x.value)

def inverse_sinh(x: CARDINAL) -> float:
    """
    Returns the inverse hyperbolic sine (arsinh) of x.
    """
    return math.asinh(x.value)

def inverse_cosh(x: CARDINAL) -> float:
    """
    Returns the inverse hyperbolic cosine (arcosh) of x.
    """
    if x.value < 1:
        return "Error: Input less than 1 for arcosh"
    return math.acosh(x.value)

def inverse_tanh(x: CARDINAL) -> float:
    """
    Returns the inverse hyperbolic tangent (artanh) of x.
    """
    if x.value <= -1 or x.value >= 1:
        return "Error: Input out of range for artanh"
    return math.atanh(x.value)

def degrees_to_radians(degrees: CARDINAL) -> float:
    """
    Converts degrees to radians.
    """
    return math.radians(degrees.value)

def radians_to_degrees(radians: CARDINAL) -> float:
    """
    Converts radians to degrees.
    """
    return math.degrees(radians.value)

def reciprocal(x: CARDINAL) -> float:
    """
    Returns the reciprocal of x.
    """
    if x.value == 0:
        return "Error: Division by zero"
    return 1 / x.value

def modulus(a: CARDINAL, b: CARDINAL) -> float:
    """
    Returns the modulus of a and b.
    """
    if b.value == 0:
        return "Error: Division by zero"
    return a.value % b.value

def absolute_value(x: CARDINAL) -> float:
    """
    Returns the absolute value of x.
    """
    return abs(x.value)

def pi() -> float:
    """
    Returns the value of pi (π).
    """
    return math.pi

def mean(data: List[CARDINAL]) -> float:
    """
    Returns the mean of the data.
    """
    return np.mean([d.value for d in data])

def median(data: List[CARDINAL]) -> float:
    """
    Returns the median of the data.
    """
    return np.median([d.value for d in data])

def standard_deviation(data: List[CARDINAL]) -> float:
    """
    Returns the standard deviation of the data.
    """
    return np.std([d.value for d in data])

def variance(data: List[CARDINAL]) -> float:
    """
    Returns the variance of the data.
    """
    return np.var([d.value for d in data])

def future_value(pv: CARDINAL, rate: CARDINAL, n: CARDINAL) -> float:
    """
    Calculates the future value of an investment.
    """
    return pv.value * (1 + rate.value) ** n.value

def present_value(fv: CARDINAL, rate: CARDINAL, n: CARDINAL) -> float:
    """
    Calculates the present value of a future amount.
    """
    return fv.value / (1 + rate.value) ** n.value

def amortization_schedule(principal: CARDINAL, rate: CARDINAL, periods: CARDINAL) -> List[Tuple[int, float, float, float]]:
    """
    Generates an amortization schedule for a loan.
    """
    rate_per_period = rate.value / 12
    schedule = []
    for period in range(1, periods.value + 1):
        interest = principal.value * rate_per_period
        principal_payment = (principal.value / periods.value) + interest
        principal.value -= principal_payment
        schedule.append((period, principal_payment, interest, principal.value))
    return schedule

def net_present_value(cash_flows: List[CARDINAL], discount_rate: CARDINAL) -> float:
    """
    Calculates the net present value (NPV) of a series of cash flows.
    """
    npv = sum(cash_flow.value / (1 + discount_rate.value) ** i for i, cash_flow in enumerate(cash_flows))
    return npv

def internal_rate_of_return(cash_flows: List[CARDINAL]) -> float:
    """
    Calculates the internal rate of return (IRR) for a series of cash flows.
    """
    irr = newton(lambda r: net_present_value(cash_flows, CARDINAL(value=r)), 0.1)
    return irr

def bond_price(face_value: CARDINAL, coupon_rate: CARDINAL, periods: CARDINAL, yield_rate: CARDINAL) -> float:
    """
    Calculates the price of a bond.
    """
    coupon_payment = face_value.value * coupon_rate.value
    price = sum(coupon_payment / (1 + yield_rate.value) ** t for t in range(1, periods.value + 1))
    price += face_value.value / (1 + yield_rate.value) ** periods.value
    return price

def depreciation(cost: CARDINAL, salvage: CARDINAL, life: CARDINAL) -> float:
    """
    Calculates the depreciation of an asset using the straight-line method.
    """
    return (cost.value - salvage.value) / life.value

def cash_flow_analysis(cash_flows: List[CARDINAL]) -> Dict[str, float]:
    """
    Analyzes a series of cash flows and returns key metrics.
    """
    return {
        'total_cash_flows': sum(cash_flow.value for cash_flow in cash_flows),
        'average_cash_flow': np.mean([cf.value for cf in cash_flows]),
        'net_present_value': net_present_value(cash_flows, CARDINAL(value=0.1)),  # Assumes 10% discount rate for NPV
        'internal_rate_of_return': internal_rate_of_return(cash_flows)
    }


def days_between_dates(date1: DATE, date2: DATE) -> int:
    """
    Calculates the number of days between two dates.
    """
    return (date2.date - date1.date).days

def scientific_constant(name: str) -> Union[float, str]:
    """
    Returns the value of a commonly used scientific constant.
    """
    constants = {
        'speed_of_light': 299792458,  # in meters per second
        'gravitational_constant': 6.67430e-11,  # in m^3 kg^-1 s^-2
        'planck_constant': 6.62607015e-34,  # in m^2 kg / s
        'boltzmann_constant': 1.380649e-23  # in J/K
    }
    return constants.get(name, "Error: Unknown constant")

def combinations(n: CARDINAL, k: CARDINAL) -> Union[int, str]:
    """
    Calculates the number of combinations (n choose k).
    """
    if k.value > n.value:
        return "Error: k cannot be greater than n"
    return comb(n.value, k.value)

def permutations(n: CARDINAL, k: CARDINAL) -> Union[int, str]:
    """
    Calculates the number of permutations (n P k).
    """
    if k.value > n.value:
        return "Error: k cannot be greater than n"
    return perm(n.value, k.value)

### ADDED ALL FUNCTIONS UP UNTIL THIS POINT TO CONTEXT FILE###

# def plot_function(func: Callable[[np.ndarray], np.ndarray], x_range: List[CARDINAL]) -> None:
#     """
#     Plots the function func over the range x_range.
#     """
#     x = np.linspace(x_range[0].value, x_range[1].value, 400)
#     y = func(x)
#     plt.plot(x, y)
#     plt.xlabel('x')
#     plt.ylabel('f(x)')
#     plt.title('Function Plot')
#     plt.grid(True)
#     plt.show()

# def solve_equation(func: Callable[[float], float], x_guess: CARDINAL) -> float:
#     """
#     Solves the equation func(x) = 0 starting from x_guess.
#     """
#     from scipy.optimize import fsolve
#     return fsolve(func, x_guess.value)[0]

# def calculate_derivative(func: Callable[[float], float], x: CARDINAL, h: float = 1e-5) -> float:
#     """
#     Calculates the derivative of func at x using numerical differentiation.
#     """
#     return (func(x.value + h) - func(x.value - h)) / (2 * h)

# def calculate_integral(func: Callable[[float], float], x_range: List[CARDINAL]) -> float:
#     """
#     Calculates the integral of func over the range x_range.
#     """
#     return integrate.quad(func, x_range[0].value, x_range[1].value)[0]

# def matrix_operations(matrix1: np.ndarray, matrix2: np.ndarray, operation: str) -> Union[np.ndarray, str]:
#     """
#     Performs matrix operations: addition, subtraction, or multiplication.
#     """
#     if operation == 'add':
#         return np.add(matrix1, matrix2)
#     elif operation == 'subtract':
#         return np.subtract(matrix1, matrix2)
#     elif operation == 'multiply':
#         return np.dot(matrix1, matrix2)
#     else:
#         return "Error: Unsupported operation"
