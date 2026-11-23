# Model 1

Baseline exchange-rate regression from the Model 1 design slide in `final_master_presentation.html`. The design slide writes the outcome as the log real effective exchange rate. This procedure enters the treated monthly change stored in `cleaned/replication_cleaned/country_month.csv`.

One regression for each World Governance Indicators (WGI) dimension. Country fixed effects. Standard errors clustered by country.

## Equation

\[
\Delta \log REER_{it}
= \alpha_i
+ \beta_1 GPR^{z}_{it}
+ \beta_2 WGI_{i,t-1}
+ \beta_3 \bigl(WGI_{i,t-1} \times GPR^{z}_{it}\bigr)
+ \boldsymbol{\gamma}^{\mathsf T}\mathbf{X}_{i,t-1}
+ \varepsilon_{it}
\]

\(i\) is the country and \(t\) is the month. \(\alpha_i\) is a country fixed effect. \(WGI\) is one governance score. The six scores are estimated in separate regressions: voice and accountability, political stability, government effectiveness, regulatory quality, rule of law, and control of corruption.

\(GPR^{z}\) is the stored column `gpr_z`. It equals the country GPR score minus that country's mean, divided by that country's sample standard deviation. The mean and the standard deviation use every month in the file from January 2000 through December 2023. The divisor is the number of those months minus one. The regression uses the stored column in the current month. Recomputing that standardization from `gpr` matches `gpr_z` up to the rounding already stored in the file.

The lagged WGI score stays in its original units. The interaction is that lagged score times current-month `gpr_z`. The product is not standardized, and the lagged score is not centered. The GPR coefficient is the association at a lagged WGI score of zero.

\(\mathbf{X}_{i,t-1}\) is the lagged control vector below. A lag is the previous calendar month for the same country. If that month's value is blank, the current month is left out of the regression.

WGI, the financial-development change, and the debt/GDP change are annual values repeated on every month of the calendar year. Their one-month lag is therefore the current year's value from February through December, and the previous year's value in January.

## Variables

| Role | Column | How it enters |
| --- | --- | --- |
| Outcome: treated log REER | `d_log_reer` | Monthly change in log REER, current month |
| WGI | `wgi_va`, `wgi_pv`, `wgi_ge`, `wgi_rq`, `wgi_rl`, `wgi_cc` | Lagged one month. One column per regression |
| Treated financial development | `d_financial_development` | Annual change, lagged one month |
| Treated debt/GDP | `d_public_debt_gdp` | Annual change, lagged one month |
| Treated policy rate | `d_policy_rate` | Monthly change, lagged one month |
| Treated inflation | `d_inflation` | Monthly change, lagged one month |
| Treated log oil price | `d_log_oil` | Monthly change in log WTI, lagged one month |
| Treated log global EPU | `d_log_gepu` | Monthly change in log global EPU, lagged one month |
| WGI × GPR | lagged `wgi_*` × `gpr_z` | Lagged WGI in its original units, times `gpr_z`. The product is not standardized |
| Standardized GPR | `gpr_z` | Stored column, current month |
| Log VIX | `vix` | Natural log of the level, lagged one month |

`vix` enters only when it is positive. In this file it is positive in every month.

## Sample

Every country-month in `cleaned/replication_cleaned/country_month.csv` with a non-missing outcome and a non-missing value for every entered regressor. The six WGI scores are blank in the same months, so all six regressions use the same 6,583 country-months.

The window is February 2002 through January 2022.

- WGI is blank for the calendar year 2001. January 2002 would need that blank year, so the first usable lagged 2002 score is February 2002.
- The financial-development change is filled for 2001 through 2021. January 2022 still uses the 2021 change. February 2022 would need the 2022 change, which is blank.

Twenty-five countries contribute all 240 months in that window. Türkiye contributes 238 months, from April 2002. Indonesia contributes 197 months, from September 2005 through January 2022. Japan contributes 148 months: May 2006 through May 2013, and November 2016 through January 2022. Those shorter spans are months in which the lagged policy-rate change is blank. Ukraine has no policy rate in the file, so it contributes no months.

Countries in the regression: Belgium, Brazil, Canada, Chile, China, Colombia, Denmark, Finland, France, Germany, Hungary, India, Indonesia, Italy, Japan, Korea, Malaysia, Mexico, Netherlands, Philippines, Poland, Portugal, South Africa, Spain, Sweden, Thailand, Türkiye, and the United States. Korea and Türkiye are the names stored in the file.

## Estimator

Ordinary least squares with a full set of country indicators. The reported slopes are the within-country associations.

Standard errors are clustered by country. For each country, form the score from that country's residuals and regressors, and add the outer product of the score to the meat of the sandwich. Multiply the sandwich by

\[
\frac{G}{G-1}\times\frac{N-1}{N-k}
\]

where \(G\) is the number of countries, \(N\) is the number of country-months, and \(k\) is the number of estimated coefficients, including the intercept and the country indicators. \(p\)-values use a two-sided \(t\) distribution with \(G-1\) degrees of freedom. \*\*\* \(p<0.01\), \*\* \(p<0.05\), \* \(p<0.10\).

The regression is `output/run_model1.py`. It writes `output/model1_results.csv`.

## Estimates

6,583 country-months, 28 countries, February 2002–January 2022. Parentheses are country-clustered standard errors. Within \(R^2\) is the fit after removing country means of the outcome. The \(R^2\) column includes those country means.

Standardized GPR and WGI × GPR have \(p>0.10\) in every column. The lagged regulatory-quality score is the governance coefficient with \(p<0.10\). The lagged policy-rate change, the lagged log oil-price change, lagged log VIX, and the lagged debt/GDP change clear that threshold in every column.

|  | Voice and accountability | Political stability | Government effectiveness | Regulatory quality | Rule of law | Control of corruption |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| WGI, lagged | 0.001901 (0.002566) | 0.000100 (0.001268) | 0.000598 (0.001085) | 0.002496* (0.001417) | 0.001699 (0.003091) | −0.000356 (0.001365) |
| GPR, standardized | −0.000017 (0.000177) | −0.000150 (0.000159) | −0.000144 (0.000251) | −0.000140 (0.000323) | −0.000102 (0.000206) | −0.000103 (0.000199) |
| WGI × GPR | −0.000181 (0.000166) | 0.000005 (0.000232) | −0.000010 (0.000238) | −0.000032 (0.000317) | −0.000086 (0.000212) | −0.000073 (0.000203) |
| Policy rate, lagged change | 0.001676*** (0.000398) | 0.001646*** (0.000403) | 0.001639*** (0.000411) | 0.001629*** (0.000406) | 0.001664*** (0.000393) | 0.001642*** (0.000407) |
| Inflation, lagged change | 0.001218 (0.001164) | 0.001192 (0.001141) | 0.001190 (0.001127) | 0.001205 (0.001125) | 0.001215 (0.001169) | 0.001193 (0.001129) |
| Log oil price, lagged change | 0.008591* (0.004499) | 0.008639* (0.004513) | 0.008673* (0.004477) | 0.008524* (0.004483) | 0.008608* (0.004511) | 0.008661* (0.004498) |
| Log VIX, lagged | 0.002546** (0.001034) | 0.002585** (0.001042) | 0.002596** (0.001067) | 0.002526** (0.001048) | 0.002579** (0.001049) | 0.002609** (0.001075) |
| Log global EPU, lagged change | −0.000658 (0.001269) | −0.000673 (0.001258) | −0.000670 (0.001269) | −0.000655 (0.001263) | −0.000672 (0.001272) | −0.000671 (0.001270) |
| Financial development, lagged change | 0.020165 (0.013569) | 0.021173 (0.014347) | 0.021487 (0.014326) | 0.020176 (0.014059) | 0.020919 (0.014009) | 0.021193 (0.014401) |
| Debt/GDP, lagged change | −0.000287*** (0.000087) | −0.000290*** (0.000090) | −0.000291*** (0.000092) | −0.000279*** (0.000092) | −0.000284*** (0.000088) | −0.000292*** (0.000092) |
| Observations | 6,583 | 6,583 | 6,583 | 6,583 | 6,583 | 6,583 |
| Countries | 28 | 28 | 28 | 28 | 28 | 28 |
| Within \(R^2\) | 0.0117 | 0.0114 | 0.0114 | 0.0118 | 0.0115 | 0.0114 |
| \(R^2\) | 0.0139 | 0.0136 | 0.0136 | 0.0140 | 0.0137 | 0.0136 |
