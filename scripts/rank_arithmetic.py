"""Exact pooled-gap comparison; standalone DAX generator and arithmetic emulator."""
from dataclasses import dataclass
import math

SOURCE_LIMIT = 9_469_257
BASE = 1 << 15
MAX_DENOMINATOR = (SOURCE_LIMIT // 2) * (SOURCE_LIMIT - SOURCE_LIMIT // 2)
INPUTS = ('_a', '_n', '_b', '_m', '_c', '_p', '_d', '_q')


def validate_counts(counts):
    """Require two (focal No, focal known, peer No, peer known) tuples."""
    if len(counts) != 8 or any(type(x) is not int for x in counts):
        raise ValueError('Require eight whole-number counts')
    for a, n, b, m in (counts[:4], counts[4:]):
        if not (0 <= a <= n and 0 <= b <= m and n > 0 and m > 0
                and n + m <= SOURCE_LIMIT):
            raise ValueError('Counts outside the disjoint accepted-population domain')


@dataclass(frozen=True)
class Instruction:
    name: str
    operation: str
    arguments: tuple


class ArithmeticPlan:
    """Straight-line scalar instructions shared by emulation and DAX emission."""

    def __init__(self):
        self.instructions = []
        self.signs = []
        numerators, denominators = [], []
        for a, n, b, m in (INPUTS[:4], INPUTS[4:]):
            numerator = self.emit('sub', self.emit('mul', a, m), self.emit('mul', b, n))
            self.signs.append(self.emit('sign', numerator))
            numerators.append(self.emit('abs', numerator))
            denominators.append(self.emit('mul', n, m))
        self.left = self.product(numerators[0], denominators[1])
        self.right = self.product(numerators[1], denominators[0])

    def emit(self, operation, *arguments):
        name = f'_ra{len(self.instructions)}'
        self.instructions.append(Instruction(name, operation, arguments))
        return name

    def split(self, value):
        digits = []
        for _ in range(2):
            high = self.emit('floorbase', value)
            digits.append(self.emit('sub', value, self.emit('mul', high, BASE)))
            value = high
        return digits + [value]

    def product(self, left, right):
        x, y = self.split(left), self.split(right)
        carry, digits = 0, []
        for k in range(5):
            total = carry
            for i in range(3):
                j = k - i
                if 0 <= j < 3:
                    total = self.emit('add', total, self.emit('mul', x[i], y[j]))
            carry = self.emit('floorbase', total)
            digits.append(self.emit('sub', total, self.emit('mul', carry, BASE)))
        return digits + [carry]

    def evaluate(self, counts, *, binary64=False):
        """Emulate every arithmetic op as integers or IEEE-754 binary64.

        Division by BASE is exact in both modes; binary64 mode deliberately
        promotes all other arithmetic too, a stronger precision stress test.
        """
        validate_counts(counts)
        cast = float if binary64 else int
        values = dict(zip(INPUTS, map(cast, counts)))
        for instruction in self.instructions:
            args = [values[x] if isinstance(x, str) else cast(x)
                    for x in instruction.arguments]
            op = instruction.operation
            if op == 'add':
                result = args[0] + args[1]
            elif op == 'sub':
                result = args[0] - args[1]
            elif op == 'mul':
                result = args[0] * args[1]
            elif op == 'abs':
                result = abs(args[0])
            elif op == 'sign':
                result = (args[0] > 0) - (args[0] < 0)
            elif op == 'floorbase':
                result = math.floor(args[0] / BASE) if binary64 else args[0] // BASE
            else:
                raise ValueError(f'Unknown instruction: {op}')
            values[instruction.name] = cast(result)
        s, t = (values[x] for x in self.signs)
        if s != t:
            return int((s > t) - (s < t))
        for left, right in zip(reversed(self.left), reversed(self.right)):
            x, y = values[left], values[right]
            if x != y:
                return int(s * ((x > y) - (x < y)))
        return 0

    def dax(self):
        """Return a scalar expression; caller binds INPUTS to whole counts.

        Domain validation belongs to the caller; this is not model authoring.
        """
        lines = []
        operators = {'add': '+', 'sub': '-', 'mul': '*'}
        for item in self.instructions:
            args = list(map(str, item.arguments))
            if item.operation in operators:
                expression = f'{args[0]} {operators[item.operation]} {args[1]}'
            elif item.operation == 'floorbase':
                expression = f'INT({args[0]} / {BASE})'
            else:
                expression = f'{item.operation.upper()}({args[0]})'
            lines.append(f'VAR {item.name} = {expression}')
        magnitude = '0'
        for left, right in zip(self.left, self.right):
            magnitude = f'IF({left} == {right}, {magnitude}, IF({left} > {right}, 1, -1))'
        s, t = self.signs
        lines.append(f'RETURN IF({s} == {t}, {s} * ({magnitude}), IF({s} > {t}, 1, -1))')
        return '\n'.join(lines)


def compare_gaps(*counts, binary64=False):
    """Return -1/0/1 for a/n-b/m versus c/p-d/q; no rounded rates."""
    return ArithmeticPlan().evaluate(counts, binary64=binary64)


if __name__ == '__main__':
    print(ArithmeticPlan().dax())
