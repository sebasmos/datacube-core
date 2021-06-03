import lark
import numpy

from datacube.utils.masking import valid_data_mask


def formula_parser():
    return lark.Lark("""
                ?expr: or_clause | comparison_clause | shift

                ?or_clause: or_clause "|" and_clause -> or_
                          | or_clause "^" and_clause -> xor
                          | and_clause
                ?and_clause: and_clause "&" term -> and_
                           | term
                ?term: "not" term -> not_
                     | "(" expr ")"

                ?comparison_clause: eq | ne | le | ge | lt | gt

                eq: expr "==" expr
                ne: expr "!=" expr
                le: expr "<=" expr
                ge: expr ">=" expr
                lt: expr "<" expr
                gt: expr ">" expr

                ?shift: shift "<<" sum -> lshift
                      | shift ">>" sum -> rshift
                      | sum

                ?sum: sum "+" product -> add
                    | sum "-" product -> sub
                    | product

                ?product: product "*" atom -> mul
                        | product "/" atom -> truediv
                        | product "//" atom -> floordiv
                        | product "%" atom -> mod
                        | atom

                ?atom: "-" subatom -> neg
                     | "+" subatom -> pos
                     | "~" subatom -> inv
                     | subatom "**" atom -> pow
                     | subatom

                ?subatom: NAME -> var_name
                        | FLOAT -> float_literal
                        | INT -> int_literal
                        | "(" expr ")"


                %import common.FLOAT
                %import common.INT
                %import common.WS_INLINE
                %import common.CNAME -> NAME

                %ignore WS_INLINE
                """, start='expr')


@lark.v_args(inline=True)
class FormulaEvaluator(lark.Transformer):
    from operator import not_, or_, and_, xor
    from operator import eq, ne, le, ge, lt, gt
    from operator import add, sub, mul, truediv, floordiv, neg, pos, inv, mod, pow, lshift, rshift

    float_literal = float
    int_literal = int


@lark.v_args(inline=True)
class MaskEvaluator(lark.Transformer):
    # the result of an expression is nodata whenever any of its subexpressions is nodata
    from operator import or_

    # pylint: disable=invalid-name
    and_ = _xor = or_
    eq = ne = le = ge = lt = gt = or_
    add = sub = mul = truediv = floordiv = mod = pow = lshift = rshift = or_

    def not_(self, value):
        return value

    neg = pos = inv = not_

    @staticmethod
    def float_literal(value):
        return False

    @staticmethod
    def int_literal(value):
        return False


def evaluate_type(formula, env, parser, evaluator):
    """
    Evaluates the type of the output of a formula given a parser,
    a corresponding evaluator class, and an environment.
    The environment is a dict-like object (such as an `xarray.Dataset`) that maps variable names to values.
    """
    @lark.v_args(inline=True)
    class TypeEvaluator(evaluator):
        def var_name(self, key):
            return numpy.array([], dtype=env[key.value].dtype)

    return TypeEvaluator().transform(parser.parse(formula))

def evaluate_data(formula, env, parser, evaluator):
    """
    Evaluates a formula given a parser, a corresponding evaluator class, and an environment.
    The environment is a dict-like object (such as an `xarray.Dataset`) that maps variable names to values.
    """
    @lark.v_args(inline=True)
    class DataEvaluator(evaluator):
        def var_name(self, key):
            return env[key.value]

    return DataEvaluator().transform(parser.parse(formula))


def evaluate_nodata_mask(formula, env, parser, evaluator):
    """
    Evaluates the nodata mask for a formula given a parser, a corresponding evaluator class, and an environment.
    The environment is a dict-like object (such as an `xarray.Dataset`) that maps variable names to values.
    """
    @lark.v_args(inline=True)
    class NodataMaskEvaluator(evaluator):
        def var_name(self, key):
            # pylint: disable=invalid-unary-operand-type
            return ~valid_data_mask(env[key.value])

    return NodataMaskEvaluator().transform(parser.parse(formula))
