# Exact pooled-gap ordering arithmetic for F1

## Boundary and result

This is a standalone arithmetic design, generator and Python verification, **not a semantic model implementation or live DAX validation**. It addresses approved report-spec numerical-risk item 9 and the `reduced` / `ordered_keys` rational comparison in `sql/longitudinal_contract.sql`. No MCP, TMDL, model or report files are authored.

`scripts/rank_arithmetic.py` emits a scalar DAX expression with 102 local variables. Bind `_a,_n,_b,_m` to focal No, focal known, peer No, peer known for one pooled window; bind `_c,_p,_d,_q` similarly for a second window. Result -1/0/1 means first gap is smaller/equal/larger. Run from the project directory:

```sh
.venv/bin/python scripts/rank_arithmetic.py
```

The bindings must already be finite **Whole number** counts, nonblank, with positive known denominators, No between zero and known, and focal-known + peer-known <= 9,469,257 independently for each tuple. Python rejects invalid counts explicitly; generated DAX deliberately has this typed/domain precondition rather than silently coercing blanks, text, currency, fractions or undefined rates. Only compare eligible candidates. An integration must establish this domain before binding; undefined candidates must not become rational zero.

## Bounds for every selected population

Let T = 9,469,257. For any selected geography, received dates, company and product, focal and other-issue peer complaint sets are disjoint. Known flags are subsets of those complaints. Within one pooled window a complaint is counted once: distinct calendar months do not duplicate rows. Thus n,m >= 1, n+m <= T, 0 <= a <= n, 0 <= b <= m. Unknowns only reduce known counts. A selection cannot enlarge the frozen source. Overlapping *different* windows do not affect the bound for either window; the two compared tuples need not be disjoint from each other.

For N = a*m - b*n and D = n*m:

- 1 <= D <= floor(T²/4) = **22,416,707,033,012** < 2^45.
- Both a*m and b*n lie in [0,D]; consequently -D <= N <= D (not ±2D).
- Formation of N and D is exact in signed Int64; even binary64 represents every one of these integer intermediates exactly.
- GCD reduction is unnecessary: comparing unreduced fractions preserves exact equality and order.
- A naive cross-product |N1|*D2 is bounded by Dmax² = **502,508,754,203,889,664,057,792,144**, an **89-bit** unsigned magnitude. This bound is attained by equal maximal denominators with gaps 1. It is far outside Int64, though within DuckDB HUGEINT. The mathematical upper bound on a difference of two such nonnegative magnitudes is also Dmax²; neither large product is evaluated by the proposed DAX.

No minimum-volume assumption or approximate rate assumption is needed. The proof includes negative and zero pooled gaps, not only positive monthly elevations.

## Overflow-safe exact kernel

Set B = 32768 = 2^15. For nonnegative x < 2^45, decompose into three limbs:

```dax
VAR _high = INT(x / 32768)
VAR _low = x - _high * 32768
```

Repeat on `_high` once; final high is the third limb. Each limb is in [0,B-1]. For |N1|*D2 and |N2|*D1, perform grade-school 3×3 multiplication. For positions k=0..4, sum the applicable limb products plus carry, extract one digit with the same power-of-two division/subtraction, and retain the final carry as digit 5. Compare the resulting six digits lexicographically, highest first. Do **not** reconstruct a large product or subtract reconstructed products.

For a convolution position, at most three terms each <= (B-1)² occur. Inductively carry <= 3(B-1), so its total is <= 3(B-1)² + 3(B-1) = **3,221,127,168** < 2^32. Carry, multiplication by B, and digit subtraction are therefore all comfortably within Int64 and exact binary64 integer range. Six limbs cover 90 bits; each actual product is < B^6, so the last carry is a valid limb.

Compare numerator signs first. Unequal signs determine order directly. Equal positive signs use the magnitude comparison; equal negative signs reverse it. Equal zero signs return equality. All numerator products and differences remain below 2^45 in magnitude, so sign detection is exact. The generated nested IF compares the highest differing limb; it does not approximate the rational gap.

## Why division cannot round into a false limb

DAX `/` can return REAL even for INTEGER inputs. Here every dividend is an exactly represented integer below 2^45 (splitting), or below 2^32 (convolution). Dividing by B changes only the binary exponent; the quotient is an **exactly representable binary rational**, with at most 45 significant bits and no underflow/overflow. It cannot round to a neighboring integer. `INT` therefore returns the exact mathematical floor. Remainder is recovered by exact integer multiply/subtract.

This use of INT is structural digit extraction, **not rounding a ranking score**. There is no tolerance, fixed-decimal score, arbitrary decimal quotient, MOD, QUOTIENT, rate subtraction or floating-point equality of rational scores. MOD/QUOTIENT need no implementation-specific precision assumption because neither is emitted. Even promoting *all* the small arithmetic operations to IEEE-754 binary64 leaves them exact; this stronger case is separately emulated in tests. This argument does not permit currency bindings: currency has different multiplication/conversion rules.

## Rank integration contract, not implementation

Use the comparator only at the pooled-gap position of the approved descending tuple: elevated-month count, exact gap, window No, window complaints. Use direct Whole number comparison for the other positions. For each ending month, dense rank is one plus the number of **distinct strictly better tuple equivalence classes**, not the count of better rows. Two gaps are equivalent exactly when this comparator returns zero, including unreduced representations. Deduplicating by raw numerator/denominator without reduction or equivalence handling would be wrong. Labels never enter this equivalence relation. Preserve selected dates/company/product/geography, remove only issue filtering for peer formation, and compute the candidate population before queue-row focus. The arithmetic module intentionally performs none of that filter-context/model work.

## Evidence and reproduction

`tests/test_rank_arithmetic.py` checks independent `Fraction` order against integer emulation and all-binary64 emulation. It covers 38,416 exhaustive small-domain pairs; 10,000 seeded random full-domain pairs; 64 sign/extreme/unreduced-tie pairs; limb/power-of-two boundaries and carry chains; invalid counts; and a cancellation fixture where naive floating rate subtraction ties but the rational order is strict. The actual generated expression text is also evaluated in a restricted Python arithmetic harness for 165 fixtures, including the cancellation fixture. This harness checks emission consistency but is **not** a DAX parser or engine.

Both normal and optimized runs passed six new tests and all 19 existing review-contract tests in the existing project environment:

```sh
.venv/bin/python -m unittest discover -s tests -p test_rank_arithmetic.py -v
.venv/bin/python -m unittest discover -s tests -p 'test_*contract.py' -v
.venv/bin/python -O -m unittest discover -s tests -p test_rank_arithmetic.py -v
.venv/bin/python -O -m unittest discover -s tests -p 'test_*contract.py' -v
```

Machine-readable evidence: `outputs/rank_arithmetic_validation.json`.

## Microsoft grounding and remaining verification

Implementation references retrieved from official Microsoft Learn documentation on 2026-10-23:

- [Data types in Power BI](https://learn.microsoft.com/en-us/power-bi/connect-data/desktop-data-types): Int64 whole numbers, IEEE-754 approximate REAL, operator coercion tables, and INTEGER / INTEGER returning REAL.
- [INT](https://learn.microsoft.com/en-us/dax/int-function-dax): rounds down and returns a whole number.
- [DAX operators](https://learn.microsoft.com/en-us/dax/dax-operator-reference): arithmetic/comparison syntax, strict `==`, and BLANK coercion caveats.

Subsequent [live acceptance](../outputs/native_queue_acceptance_results.json) evaluates 104 integer-count comparisons against an independent Fraction oracle, including equal rational gaps, negative gaps and threshold-adjacent cases. Complete native-shaped queue identities, ranks and diagnostic ratios match canonical DuckDB output across four populations and minima 50/100/200. This supplements the bounded arithmetic proof and Python fixtures; it is not exhaustive engine testing of every possible count tuple. Native full-scope queue queries take about 19–21 seconds in the recorded development run. Actual slicer/focus interaction acceptance, confirmed clean-folder refresh and Gate D sign-off remain separate requirements.
