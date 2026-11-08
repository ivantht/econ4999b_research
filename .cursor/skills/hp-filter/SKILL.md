---
name: hp-filter
description: >-
  Decompose one macro series into trend and cycle with the
  Hodrick-Prescott filter. Use when the user asks for an HP filter,
  HP detrending, or a smooth trend with lambda 1600, 100, or 129600.
---

# HP filter

This is the Hodrick-Prescott decomposition from Econ 5140 (Jenny Xu), slides 21–25.

Decompose one measure at a time. Run each country separately, in time order. Leave `input/` unchanged. Do not fill a missing value with zero. Do not join another series onto the row.

## Decomposition

Take the log of the level. If the series is already a log, do not log it again. Minimize

`sum_t (log(Y_t) - ytrend_t)^2 + λ sum_t [(ytrend_{t+1} - ytrend_t) - (ytrend_t - ytrend_{t-1})]^2`

subject to `y_t + ytrend_t = log(Y_t)`.

`y_t` is the cyclical component. `ytrend_t` is the growth trend.

## Lambda

- Large `λ` keeps the trend’s growth rate smooth. As `λ → ∞`, the trend is the constant-growth linear trend.
- `λ = 0` sets the trend equal to the data and the cycle to zero.
- Quarterly data: `λ = 1600`. Fluctuations of about eight years or longer stay in the trend.
- Annual data: `λ = 100`.
- Monthly `year_month` series: the lecture does not give a `λ`. Use the Ravn–Uhlig scaling `λ = 1600 × 3^4 = 129600`, and say that this value is not from the lecture.

## Gaps

A gap breaks the filter. Do not interpolate. Report the gap and filter only contiguous stretches.

Return `ytrend_t` and `y_t`.
