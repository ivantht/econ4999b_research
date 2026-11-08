---
name: remove-cyclicality
description: >-
  Remove the business-cycle component of one macro series with a
  constant-growth log trend (linear detrending). Use when the user asks
  to adjust for cyclicality, linearly detrend, or separate trend and
  cycle without the Hodrick-Prescott filter.
---

# Remove cyclicality

This is linear detrending from Econ 5140 (Jenny Xu), slides 15–20. It is not the HP filter.

Decompose one measure at a time. Run each country separately, in time order. Leave `input/` unchanged. Do not fill a missing value with zero. Do not join another series onto the row.

## Decomposition

A level series splits in logs:

`log(Y_t) = log(Ytrend_t) + y_t`

`y_t` is the cyclical component. Because `log(1 + x) ≈ x` for small `x`, `y_t` is approximately the percentage gap `(Y_t - Ytrend_t) / Ytrend_t`.

1. Take the log of the level. If the series is already a log, do not log it again.
2. Fit a constant growth rate: `log(Ytrend_t) = log(Ytrend_s) + (t - s) log(1 + g)`. Estimate `g` by a linear regression of `log(Y_t)` on a time index.
3. The cycle is `y_t = log(Y_t) - log(Ytrend_t)`.

Return both the log trend and `y_t`. The cyclically adjusted series is the trend.

## Limit

A straight trend treats medium-term changes in the growth rate as business-cycle movements, so the cycle looks large and persistent.
