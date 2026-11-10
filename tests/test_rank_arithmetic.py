"""Independent Fraction oracle; no source files or model needed."""
import importlib.util
import math
from fractions import Fraction
from pathlib import Path
import random
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('rank_arithmetic', ROOT / 'scripts/rank_arithmetic.py')
module = importlib.util.module_from_spec(spec)
# dataclasses resolves annotations through the module registry
import sys
sys.modules[spec.name] = module
spec.loader.exec_module(module)
PLAN = module.ArithmeticPlan()


def oracle(counts):
    a, n, b, m, c, p, d, q = counts
    x, y = Fraction(a, n) - Fraction(b, m), Fraction(c, p) - Fraction(d, q)
    return (x > y) - (x < y)


def emitted_result(counts):
    """Execute generated scalar text in a restricted Python arithmetic harness.

    Only internally generated expressions are evaluated; not a DAX parser or
    engine validation. All input and intermediate arithmetic uses binary64.
    """
    env = dict(zip(module.INPUTS, map(float, counts)))
    env.update(INT=lambda x: float(math.floor(x)), ABS=abs,
               SIGN=lambda x: float((x > 0) - (x < 0)),
               IF=lambda condition, yes, no: yes if condition else no)
    for line in PLAN.dax().splitlines():
        if line.startswith('VAR '):
            name, expression = line[4:].split(' = ', 1)
            env[name] = float(eval(expression, {'__builtins__': {}}, env))
        else:
            return int(eval(line.removeprefix('RETURN '), {'__builtins__': {}}, env))
    raise RuntimeError('Missing RETURN')


class RankArithmeticTests(unittest.TestCase):
    def check_counts(self, counts, emitted=False):
        expected = oracle(counts)
        self.assertEqual(PLAN.evaluate(counts), expected, counts)
        self.assertEqual(PLAN.evaluate(counts, binary64=True), expected, counts)
        if emitted:
            self.assertEqual(emitted_result(counts), expected, counts)

    def test_signs_zero_extremes_and_unreduced_ties(self):
        cases = [(0, 1, 0, 1), (1, 1, 0, 1), (0, 1, 1, 1),
                 (1, 2, 1, 4), (2, 4, 2, 8), (0, 4_734_628, 0, 4_734_629),
                 (4_734_628, 4_734_628, 0, 4_734_629),
                 (0, 4_734_628, 4_734_629, 4_734_629)]
        for left in cases:
            for right in cases:
                self.check_counts(left + right, emitted=True)

    def test_limb_boundaries_and_carry_chains(self):
        values = {0, 1, module.MAX_DENOMINATOR}
        for power in range(1, 46):
            for offset in (-1, 0, 1):
                value = (1 << power) + offset
                if 0 <= value <= module.MAX_DENOMINATOR:
                    values.add(value)
        # Exercise the generic product kernel independently of pooled counts
        plan = module.ArithmeticPlan()
        plan.instructions = []
        digits = plan.product('_a', '_n')
        for x in values:
            for y in (0, 1, module.BASE - 1, module.MAX_DENOMINATOR):
                env = {'_a': x, '_n': y}
                for instruction in plan.instructions:
                    args = [env[z] if isinstance(z, str) else z for z in instruction.arguments]
                    op = instruction.operation
                    result = {'mul': lambda: args[0] * args[1],
                              'add': lambda: args[0] + args[1],
                              'sub': lambda: args[0] - args[1],
                              'floorbase': lambda: math.floor(float(args[0]) / module.BASE)}[op]()
                    self.assertLess(abs(result), 1 << 53)
                    env[instruction.name] = result
                self.assertTrue(all(0 <= env[z] < module.BASE for z in digits))
                self.assertEqual(sum(env[z] * module.BASE**i for i, z in enumerate(digits)), x * y)

    def test_near_equal_cancellation(self):
        k = module.SOURCE_LIMIT // 2
        counts = (k - 1, k, k - 2, k - 1, k - 2, k - 1, k - 3, k - 2)
        self.check_counts(counts, emitted=True)
        a, n, b, m, c, p, d, q = counts
        self.assertEqual(a / n - b / m, c / p - d / q)
        self.assertNotEqual(oracle(counts), 0)

    def test_exhaustive_small_domain(self):
        tuples = [(a, n, b, m) for n in range(1, 5) for m in range(1, 5)
                  for a in range(n + 1) for b in range(m + 1)]
        for left in tuples:
            for right in tuples:
                self.check_counts(left + right)

    def test_seeded_random_fraction_oracle(self):
        rng = random.Random(20261023)
        for i in range(10_000):
            counts = []
            for _ in range(2):
                total = rng.randint(2, module.SOURCE_LIMIT)
                n = rng.randint(1, total - 1)
                m = total - n
                counts.extend((rng.randint(0, n), n, rng.randint(0, m), m))
            self.check_counts(tuple(counts), emitted=i < 100)

    def test_reject_undefined_or_invalid_counts(self):
        for counts in [(0, 0, 0, 1) * 2, (2, 1, 0, 1) * 2,
                       (-1, 1, 0, 1) * 2, (0, module.SOURCE_LIMIT, 0, 1) * 2,
                       (False, 1, 0, 1) * 2, (0.0, 1, 0, 1) * 2, (0,)]:
            with self.assertRaises(ValueError):
                PLAN.evaluate(counts)


if __name__ == '__main__':
    unittest.main()
