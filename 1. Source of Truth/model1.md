Model 1

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

where \(G\) is the number of countries, \(N\) is the number of country-months, and \(k\) is the number of estimated coefficients, including the intercept and the country indicators. \(p\)-values use a two-sided \(t\) distribution with \(G-1\) degrees of freedom.  \(p<0.01\),  \(p<0.05\),  \(p<0.10\).

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

## Quarterly outcome timings

Three ways to date the outcome on one row of `cleaned/data_for_quarter_model.csv`. The row is country \(i\) in calendar quarter \(t\). The regressors below are the same in all three. One regression for each WGI dimension uses one `wgi_*_lag1q` column and its matching `wgi_*_lag1q_x_gpr_z`. These timings are separate from the monthly regression estimated above.

| Role | Quarterly column | Quarter |
| --- | --- | --- |
| GPR, standardized | `gpr_z` | \(t\) |
| WGI | `wgi_va_lag1q`, `wgi_pv_lag1q`, `wgi_ge_lag1q`, `wgi_rq_lag1q`, `wgi_rl_lag1q`, or `wgi_cc_lag1q` | \(t-1\) |
| WGI × GPR | the matching `wgi_*_lag1q_x_gpr_z` | WGI from \(t-1\), GPR from \(t\) |
| Policy rate | `d_policy_rate_lag1q` | \(t-1\) |
| Inflation | `d_inflation_lag1q` | \(t-1\) |
| Log oil price | `d_log_oil_lag1q` | \(t-1\) |
| Log VIX | `ln_vix_lag1q` | \(t-1\) |
| Log global EPU | `d_log_gepu_lag1q` | \(t-1\) |
| Financial development | `d_financial_development_lag1q` | \(t-1\) |
| Debt/GDP | `d_public_debt_gdp_lag1q` | \(t-1\) |

`gpr_z` is the mean of the three monthly within-country z-scores. Each `d_*_lag1q` change is the previous quarter's stored change: sums of three monthly changes for the policy rate, inflation, log oil, and log global EPU, and the repeated annual change for financial development and debt/GDP. `ln_vix_lag1q` is the previous quarter's mean of the three monthly log VIX levels. WGI lags are the previous quarter's annual score in its original units. A lag is the previous calendar quarter for the same country. A blank previous quarter stays blank.

### 1. Previous-quarter outcome

| Role | Quarterly column | Quarter | How it is built |
| --- | --- | --- | --- |
| Outcome | `d_log_reer_lag1q` | \(t-1\) | Previous calendar quarter's `d_log_reer` for the same country. That value is the sum of its three monthly log changes. Blank if that quarter's change is blank. |

On the `2002-Q2` row, the outcome and the controls are `2002Q1`. `gpr_z` is `2002Q2`. This pairs current GPR with the previous quarter's log-REER change.

### 2. Next-quarter outcome

| Role | Quarterly column | Quarter | How it is built |
| --- | --- | --- | --- |
| Outcome | next row's `d_log_reer` | \(t+1\) | Following calendar quarter's `d_log_reer` for the same country. That value is the sum of its three monthly log changes. There is no stored lead column. `2023-Q4` has no next quarter. Blank if that next change is blank. |

On the `2002-Q2` row, the outcome is the `2002Q3` log change, `gpr_z` is `2002Q2`, and the controls remain `2002Q1`. The GPR and outcome quarters match the lead correlation in `Correlation_GPR_REER.md`. The controls are two quarters before the outcome.

### 3. Current-quarter outcome

| Role | Quarterly column | Quarter | How it is built |
| --- | --- | --- | --- |
| Outcome | `d_log_reer` | \(t\) | Sum of the three monthly log changes in the row's own quarter. |

On the `2002-Q2` row, the outcome and `gpr_z` are both `2002Q2`. The controls are `2002Q1`. This is the same-quarter GPR and log-REER pair from the quarterly correlation in `Correlation_GPR_REER.md`, with the lagged controls from Model 1.

## Quarterly estimates

`output/run_model1_quarterly.py` estimates the three quarterly timings above. Each timing is estimated on every complete country-quarter and again on emerging economies. Country fixed effects and country-clustered standard errors use the same sandwich factor and \(t_{G-1}\) \(p\)-values as the monthly regression. The results are `output/model1_quarterly_results.csv`.

A country-quarter enters when the chosen outcome and every regressor are filled. The lagged controls are available from 2002Q2 through 2022Q1. On those rows the current, previous-quarter, and next-quarter log-REER changes are also filled, so the three timings use the same 2,193 country-quarters. The full sample has 28 countries. The emerging sample has 1,104 country-quarters and 14 countries. Ukraine has no policy rate, so it contributes no quarters. The six WGI regressions in each block use the same rows.

Quarters named below are the dates of the regression rows. For the next-quarter outcome, the log-REER change is the following quarter, so the last outcome quarter is 2022Q2. Parentheses are country-clustered standard errors. \(p<0.01\), \(p<0.05\), \(p<0.10\).

### Previous-quarter outcome, full sample

|  | Voice and accountability | Political stability | Government effectiveness | Regulatory quality | Rule of law | Control of corruption |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| WGI, lagged | 0.005112 (0.005696) | 0.000272 (0.002896) | 0.003006 (0.003122) | 0.008837* (0.004799) | 0.002941 (0.007351) | 0.002123 (0.004847) |
| GPR, standardized | −0.001503 (0.001048) | −0.000986 (0.000792) | −0.001589 (0.001421) | −0.002177 (0.001479) | −0.001444 (0.001123) | −0.001646 (0.001119) |
| WGI x GPR | 0.001362 (0.000905) | 0.001504 (0.001207) | 0.000952 (0.001128) | 0.001672 (0.001274) | 0.001133 (0.001023) | 0.001300 (0.000897) |
| Policy rate, lagged change | −0.002408* (0.001205) | −0.002475* (0.001234) | −0.002471* (0.001261) | −0.002493* (0.001272) | −0.002427* (0.001214) | −0.002445* (0.001264) |
| Inflation, lagged change | −0.002165** (0.000867) | −0.002197** (0.000877) | −0.002203** (0.000892) | −0.002166** (0.000891) | −0.002178** (0.000860) | −0.002217** (0.000881) |
| Log oil price, lagged change | 0.027225*** (0.009507) | 0.027314*** (0.009497) | 0.027406*** (0.009479) | 0.026927*** (0.009503) | 0.027237*** (0.009522) | 0.027210*** (0.009478) |
| Log VIX, lagged | −0.004150 (0.003090) | −0.003910 (0.003007) | −0.003833 (0.002980) | −0.004171 (0.002947) | −0.003941 (0.003002) | −0.004023 (0.003053) |
| Log global EPU, lagged change | −0.014494*** (0.004639) | −0.014458*** (0.004642) | −0.014481*** (0.004631) | −0.014400*** (0.004617) | −0.014506*** (0.004654) | −0.014476*** (0.004616) |
| Financial development, lagged change | 0.011596 (0.029448) | 0.016394 (0.030649) | 0.016829 (0.030914) | 0.011976 (0.029833) | 0.014719 (0.030239) | 0.015276 (0.030426) |
| Debt/GDP, lagged change | −0.000547** (0.000207) | −0.000568** (0.000215) | −0.000573** (0.000224) | −0.000527** (0.000216) | −0.000556** (0.000218) | −0.000565** (0.000217) |
| Observations | 2,193 | 2,193 | 2,193 | 2,193 | 2,193 | 2,193 |
| Countries | 28 | 28 | 28 | 28 | 28 | 28 |
| Quarters | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 |
| Within \(R^2\) | 0.0546 | 0.0541 | 0.0541 | 0.0555 | 0.0541 | 0.0542 |
| \(R^2\) | 0.0598 | 0.0593 | 0.0592 | 0.0607 | 0.0593 | 0.0594 |

### Previous-quarter outcome, emerging economies

|  | Voice and accountability | Political stability | Government effectiveness | Regulatory quality | Rule of law | Control of corruption |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| WGI, lagged | 0.005750 (0.006145) | 0.000242 (0.003345) | 0.011134** (0.004274) | 0.014876** (0.006670) | 0.002724 (0.008121) | 0.006221 (0.006619) |
| GPR, standardized | −0.001298 (0.001314) | −0.001047 (0.001200) | −0.001059 (0.001732) | −0.002397 (0.001832) | −0.001377 (0.001188) | −0.001611 (0.001182) |
| WGI x GPR | 0.001412 (0.002083) | 0.001310 (0.001517) | −0.000958 (0.002809) | 0.002847 (0.002256) | 0.001649 (0.002133) | 0.002510 (0.001593) |
| Policy rate, lagged change | −0.003087*** (0.000892) | −0.003140*** (0.000916) | −0.003213*** (0.000911) | −0.003197*** (0.000952) | −0.003106*** (0.000907) | −0.003125*** (0.000920) |
| Inflation, lagged change | −0.001887* (0.001012) | −0.001939* (0.001008) | −0.001930* (0.001043) | −0.001892* (0.001031) | −0.001920* (0.000999) | −0.001964* (0.001015) |
| Log oil price, lagged change | 0.042265*** (0.013286) | 0.042476*** (0.013199) | 0.043575*** (0.012940) | 0.042283*** (0.013042) | 0.042307*** (0.013369) | 0.042341*** (0.013122) |
| Log VIX, lagged | −0.009689** (0.003994) | −0.009183** (0.003748) | −0.008206* (0.004029) | −0.009270** (0.003719) | −0.009290** (0.003738) | −0.009330** (0.003763) |
| Log global EPU, lagged change | −0.027760*** (0.007240) | −0.027900*** (0.007319) | −0.028126*** (0.007241) | −0.027657*** (0.007271) | −0.027868*** (0.007337) | −0.027847*** (0.007297) |
| Financial development, lagged change | 0.055116 (0.054324) | 0.064184 (0.057063) | 0.071684 (0.057930) | 0.055660 (0.055813) | 0.061236 (0.056931) | 0.063459 (0.057103) |
| Debt/GDP, lagged change | −0.001693*** (0.000282) | −0.001746*** (0.000299) | −0.001895*** (0.000340) | −0.001720*** (0.000284) | −0.001733*** (0.000311) | −0.001752*** (0.000292) |
| Observations | 1,104 | 1,104 | 1,104 | 1,104 | 1,104 | 1,104 |
| Countries | 14 | 14 | 14 | 14 | 14 | 14 |
| Quarters | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 |
| Within \(R^2\) | 0.1138 | 0.1132 | 0.1154 | 0.1163 | 0.1132 | 0.1140 |
| \(R^2\) | 0.1188 | 0.1182 | 0.1204 | 0.1212 | 0.1182 | 0.1190 |

### Next-quarter outcome, full sample

|  | Voice and accountability | Political stability | Government effectiveness | Regulatory quality | Rule of law | Control of corruption |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| WGI, lagged | 0.003581 (0.006466) | −0.000138 (0.004209) | −0.003172 (0.004252) | 0.004910 (0.004174) | 0.002659 (0.008082) | −0.001517 (0.003502) |
| GPR, standardized | −0.001234 (0.002135) | −0.001114 (0.001499) | −0.001544 (0.002530) | −0.001325 (0.002496) | −0.001081 (0.002118) | −0.000897 (0.001955) |
| WGI x GPR | 0.000860 (0.001663) | 0.001864 (0.001991) | 0.000929 (0.001783) | 0.000669 (0.001853) | 0.000537 (0.001704) | 0.000288 (0.001352) |
| Policy rate, lagged change | 0.003865** (0.001613) | 0.003825** (0.001628) | 0.003870** (0.001666) | 0.003800** (0.001647) | 0.003848** (0.001610) | 0.003828** (0.001643) |
| Inflation, lagged change | −0.001382** (0.000652) | −0.001416** (0.000664) | −0.001412** (0.000672) | −0.001382* (0.000676) | −0.001382** (0.000647) | −0.001405** (0.000674) |
| Log oil price, lagged change | −0.006156 (0.004141) | −0.006060 (0.004134) | −0.006234 (0.004234) | −0.006306 (0.004222) | −0.006155 (0.004149) | −0.006055 (0.004206) |
| Log VIX, lagged | 0.009695** (0.003512) | 0.009883*** (0.003537) | 0.009869*** (0.003500) | 0.009717*** (0.003467) | 0.009839*** (0.003505) | 0.009950*** (0.003554) |
| Log global EPU, lagged change | 0.005723* (0.002815) | 0.005776* (0.002825) | 0.005694* (0.002833) | 0.005773* (0.002834) | 0.005707* (0.002814) | 0.005700* (0.002827) |
| Financial development, lagged change | 0.048300 (0.031928) | 0.052345 (0.032328) | 0.049335 (0.031444) | 0.048909 (0.032247) | 0.050341 (0.032175) | 0.050870 (0.032393) |
| Debt/GDP, lagged change | −0.000628*** (0.000197) | −0.000635*** (0.000190) | −0.000645*** (0.000195) | −0.000624*** (0.000207) | −0.000634*** (0.000195) | −0.000653*** (0.000199) |
| Observations | 2,193 | 2,193 | 2,193 | 2,193 | 2,193 | 2,193 |
| Countries | 28 | 28 | 28 | 28 | 28 | 28 |
| Quarters | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 |
| Within \(R^2\) | 0.0196 | 0.0200 | 0.0195 | 0.0196 | 0.0193 | 0.0192 |
| \(R^2\) | 0.0235 | 0.0239 | 0.0235 | 0.0236 | 0.0232 | 0.0231 |

### Next-quarter outcome, emerging economies

|  | Voice and accountability | Political stability | Government effectiveness | Regulatory quality | Rule of law | Control of corruption |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| WGI, lagged | 0.004255 (0.006305) | 0.000502 (0.005466) | −0.000133 (0.006471) | 0.006670 (0.005887) | 0.003794 (0.008297) | 0.001338 (0.005077) |
| GPR, standardized | −0.002187 (0.002234) | −0.002110 (0.001859) | −0.001984 (0.003087) | −0.002203 (0.002806) | −0.002286 (0.002110) | −0.002316 (0.002141) |
| WGI x GPR | −0.000436 (0.002690) | 0.000767 (0.002995) | −0.001024 (0.004213) | −0.000228 (0.003095) | −0.001588 (0.003361) | −0.000800 (0.002764) |
| Policy rate, lagged change | 0.004241** (0.001734) | 0.004171** (0.001760) | 0.004176** (0.001805) | 0.004149** (0.001782) | 0.004216** (0.001718) | 0.004182** (0.001774) |
| Inflation, lagged change | −0.001361* (0.000674) | −0.001398* (0.000678) | −0.001387* (0.000683) | −0.001368* (0.000683) | −0.001357* (0.000669) | −0.001388* (0.000688) |
| Log oil price, lagged change | −0.005897 (0.005746) | −0.005723 (0.005745) | −0.005778 (0.006243) | −0.005787 (0.005924) | −0.005867 (0.005699) | −0.005776 (0.005831) |
| Log VIX, lagged | 0.012200* (0.005964) | 0.012334* (0.005881) | 0.012342** (0.005680) | 0.012334** (0.005681) | 0.012443* (0.005892) | 0.012380* (0.005856) |
| Log global EPU, lagged change | 0.016520*** (0.003460) | 0.016517*** (0.003526) | 0.016519*** (0.003521) | 0.016575*** (0.003493) | 0.016427*** (0.003471) | 0.016486*** (0.003489) |
| Financial development, lagged change | 0.103220 (0.064522) | 0.107563 (0.063433) | 0.107033 (0.061813) | 0.103697 (0.063819) | 0.105702 (0.064642) | 0.106899 (0.064036) |
| Debt/GDP, lagged change | −0.001221*** (0.000336) | −0.001240*** (0.000313) | −0.001260*** (0.000310) | −0.001242*** (0.000333) | −0.001240*** (0.000315) | −0.001257*** (0.000323) |
| Observations | 1,104 | 1,104 | 1,104 | 1,104 | 1,104 | 1,104 |
| Countries | 14 | 14 | 14 | 14 | 14 | 14 |
| Quarters | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 |
| Within \(R^2\) | 0.0351 | 0.0348 | 0.0347 | 0.0353 | 0.0350 | 0.0347 |
| \(R^2\) | 0.0382 | 0.0379 | 0.0379 | 0.0384 | 0.0382 | 0.0379 |

## Next-quarter control outcomes, emerging economies

Each table keeps the emerging next-quarter regression above: country fixed effects, country-clustered standard errors, GPR in quarter \(t\), and WGI and the remaining controls in quarter \(t-1\). The outcome is the following quarter's value of the named control. That control's lagged value is omitted. The next-quarter REER change is not a regressor. Rows stay inside the 1,104 country-quarters of that REER regression. Results are `output/model1_quarterly_emerging_next_control_outcomes.csv`.

Log oil, log VIX, and log global EPU take the same value for every country in a quarter. Quarters named in the tables are the regression rows. The outcome is the following quarter.

### Policy rate, next-quarter change

Following quarter's `d_policy_rate`, the sum of its three monthly changes.

|  | Voice and accountability | Political stability | Government effectiveness | Regulatory quality | Rule of law | Control of corruption |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| WGI, lagged | −0.389032** (0.161770) | −0.198403 (0.152947) | 0.076486 (0.165621) | −0.228748 (0.148598) | −0.375742* (0.204706) | −0.003806 (0.145622) |
| GPR, standardized | 0.017457 (0.061562) | 0.069644 (0.063187) | −0.082880 (0.068004) | −0.021963 (0.052484) | 0.027336 (0.056409) | 0.024738 (0.055742) |
| WGI x GPR | 0.067892 (0.042564) | 0.139931* (0.064904) | 0.337660* (0.160602) | 0.139615 (0.081446) | 0.162425* (0.078429) | 0.171521* (0.092412) |
| Inflation, lagged change | 0.092294*** (0.018121) | 0.094162*** (0.018768) | 0.094410*** (0.018873) | 0.095365*** (0.019917) | 0.092296*** (0.017900) | 0.095046*** (0.019817) |
| Log oil price, lagged change | 0.402357** (0.137244) | 0.402241** (0.134262) | 0.396302** (0.136594) | 0.386628** (0.139032) | 0.399211** (0.135353) | 0.388475** (0.136777) |
| Log VIX, lagged | −0.217348* (0.101049) | −0.224936** (0.101992) | −0.212489* (0.099334) | −0.231526* (0.109649) | −0.236711** (0.099987) | −0.236434* (0.113264) |
| Log global EPU, lagged change | −0.118833* (0.064296) | −0.119587* (0.062399) | −0.119712* (0.061959) | −0.115538* (0.062917) | −0.110398* (0.062226) | −0.113013* (0.061503) |
| Financial development, lagged change | 0.467761 (1.630003) | 0.275994 (1.570929) | 0.202660 (1.572172) | 0.253562 (1.469550) | 0.285664 (1.690966) | 0.173013 (1.543617) |
| Debt/GDP, lagged change | 0.015069 (0.009749) | 0.019452* (0.010796) | 0.019509* (0.010838) | 0.018038 (0.011829) | 0.016327* (0.009090) | 0.018488 (0.011548) |
| Observations | 1,104 | 1,104 | 1,104 | 1,104 | 1,104 | 1,104 |
| Countries | 14 | 14 | 14 | 14 | 14 | 14 |
| Quarters | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 |
| Within \(R^2\) | 0.0573 | 0.0572 | 0.0623 | 0.0534 | 0.0577 | 0.0550 |
| \(R^2\) | 0.0683 | 0.0682 | 0.0733 | 0.0645 | 0.0687 | 0.0660 |

### Inflation, next-quarter change

Following quarter's `d_inflation`, the sum of its three monthly changes.

|  | Voice and accountability | Political stability | Government effectiveness | Regulatory quality | Rule of law | Control of corruption |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| WGI, lagged | −1.106448 (0.765033) | −0.138650 (0.228564) | −0.178669 (0.169452) | −0.858876** (0.389422) | −1.219354 (0.917519) | −0.463635 (0.500297) |
| GPR, standardized | 0.105553 (0.083090) | 0.183897* (0.092177) | 0.058877 (0.058807) | 0.122674* (0.065659) | 0.123146 (0.075206) | 0.141930* (0.072102) |
| WGI x GPR | 0.015956 (0.059922) | 0.156904 (0.101264) | 0.237808 (0.179899) | 0.032198 (0.123481) | 0.142885 (0.140350) | 0.109281 (0.147595) |
| Policy rate, lagged change | 0.046061 (0.078753) | 0.059886 (0.066619) | 0.066764 (0.064008) | 0.066801 (0.062385) | 0.048891 (0.082434) | 0.064426 (0.063719) |
| Log oil price, lagged change | 0.799448*** (0.260160) | 0.785364*** (0.248377) | 0.753194*** (0.248836) | 0.773848*** (0.238468) | 0.801355*** (0.265430) | 0.777010*** (0.250285) |
| Log VIX, lagged | −0.285661* (0.150520) | −0.351871* (0.190937) | −0.359121 (0.204990) | −0.345430* (0.188978) | −0.338570* (0.159696) | −0.344765* (0.189493) |
| Log global EPU, lagged change | 0.141255 (0.146531) | 0.149445 (0.146829) | 0.152458 (0.148263) | 0.141594 (0.144844) | 0.164534 (0.148932) | 0.154003 (0.144855) |
| Financial development, lagged change | 4.038299 (2.867604) | 3.000587 (3.313190) | 2.745639 (3.404378) | 3.316838 (3.257427) | 3.484888 (3.145223) | 2.929158 (3.343079) |
| Debt/GDP, lagged change | 0.059304*** (0.013207) | 0.071604*** (0.021433) | 0.073217*** (0.022607) | 0.067874*** (0.021133) | 0.061674*** (0.014170) | 0.069836*** (0.021156) |
| Observations | 1,104 | 1,104 | 1,104 | 1,104 | 1,104 | 1,104 |
| Countries | 14 | 14 | 14 | 14 | 14 | 14 |
| Quarters | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 |
| Within \(R^2\) | 0.0570 | 0.0417 | 0.0412 | 0.0464 | 0.0544 | 0.0420 |
| \(R^2\) | 0.0638 | 0.0486 | 0.0482 | 0.0533 | 0.0612 | 0.0490 |

### Log oil price, next-quarter change

Following quarter's `d_log_oil`, the sum of its three monthly log changes.

|  | Voice and accountability | Political stability | Government effectiveness | Regulatory quality | Rule of law | Control of corruption |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| WGI, lagged | −0.048981 (0.031747) | −0.010728 (0.020716) | −0.090484*** (0.022916) | −0.040403* (0.021492) | −0.017580 (0.026966) | −0.008684 (0.014616) |
| GPR, standardized | −0.016094* (0.008169) | −0.015847* (0.008635) | −0.018323** (0.007520) | −0.008915 (0.009090) | −0.015195* (0.007909) | −0.014544* (0.007758) |
| WGI x GPR | −0.008306 (0.007215) | −0.002853 (0.007380) | 0.008781 (0.018777) | −0.016605 (0.012790) | −0.009249 (0.008551) | −0.006014 (0.008854) |
| Policy rate, lagged change | −0.004479 (0.004534) | −0.004151 (0.004387) | −0.003245 (0.004321) | −0.003881 (0.004293) | −0.004201 (0.004392) | −0.004105 (0.004347) |
| Inflation, lagged change | −0.006211 (0.006777) | −0.005878 (0.006852) | −0.006000 (0.007169) | −0.005880 (0.006869) | −0.005919 (0.006764) | −0.005765 (0.006885) |
| Log VIX, lagged | 0.051628*** (0.009438) | 0.048186*** (0.008568) | 0.040832*** (0.009632) | 0.047833*** (0.009144) | 0.048389*** (0.008077) | 0.047752*** (0.008093) |
| Log global EPU, lagged change | 0.088170*** (0.004219) | 0.089181*** (0.003947) | 0.091620*** (0.004580) | 0.088228*** (0.004113) | 0.089000*** (0.003961) | 0.089057*** (0.003925) |
| Financial development, lagged change | 0.892393** (0.369719) | 0.827611** (0.349045) | 0.758168** (0.348701) | 0.848160** (0.359597) | 0.840606** (0.358564) | 0.826527** (0.347659) |
| Debt/GDP, lagged change | −0.000068 (0.001609) | 0.000440 (0.001486) | 0.001555 (0.001624) | 0.000322 (0.001515) | 0.000299 (0.001502) | 0.000473 (0.001456) |
| Observations | 1,104 | 1,104 | 1,104 | 1,104 | 1,104 | 1,104 |
| Countries | 14 | 14 | 14 | 14 | 14 | 14 |
| Quarters | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 |
| Within \(R^2\) | 0.0374 | 0.0350 | 0.0431 | 0.0365 | 0.0352 | 0.0349 |
| \(R^2\) | 0.0375 | 0.0351 | 0.0432 | 0.0366 | 0.0353 | 0.0350 |

### Log VIX, next quarter

Following quarter's `ln_vix`, the mean of its three monthly logs.

|  | Voice and accountability | Political stability | Government effectiveness | Regulatory quality | Rule of law | Control of corruption |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| WGI, lagged | 0.079337 (0.055848) | 0.095869 (0.079556) | −0.155570*** (0.043567) | 0.018747 (0.090721) | 0.046433 (0.088133) | 0.083670 (0.100672) |
| GPR, standardized | 0.029022 (0.021245) | 0.030333 (0.018124) | 0.028631 (0.031514) | 0.033659 (0.037449) | 0.029606 (0.023075) | 0.026862 (0.024507) |
| WGI x GPR | 0.049920** (0.022198) | 0.002007 (0.037827) | −0.002006 (0.037672) | −0.012148 (0.045822) | 0.043542 (0.039092) | 0.021116 (0.031104) |
| Policy rate, lagged change | −0.024919** (0.009925) | −0.024057** (0.010048) | −0.023270** (0.010065) | −0.025055** (0.009859) | −0.024745** (0.010036) | −0.024992** (0.010192) |
| Inflation, lagged change | 0.014321* (0.007506) | 0.014128* (0.007887) | 0.013826 (0.008038) | 0.013703 (0.008323) | 0.013734* (0.007346) | 0.013305 (0.008090) |
| Log oil price, lagged change | −0.040714** (0.015911) | −0.042895** (0.017620) | −0.056035*** (0.015555) | −0.042117** (0.015705) | −0.043018** (0.015144) | −0.042489** (0.015630) |
| Log global EPU, lagged change | 0.117658*** (0.011780) | 0.114954*** (0.011553) | 0.116658*** (0.012084) | 0.115523*** (0.012148) | 0.116191*** (0.012118) | 0.115684*** (0.012399) |
| Financial development, lagged change | −1.391671* (0.662087) | −1.256122* (0.640384) | −1.349040* (0.643689) | −1.250438* (0.637932) | −1.280891* (0.655484) | −1.240872* (0.617479) |
| Debt/GDP, lagged change | 0.017597*** (0.004313) | 0.016501*** (0.004369) | 0.017753*** (0.003936) | 0.016386*** (0.004013) | 0.017044*** (0.004462) | 0.016499*** (0.004158) |
| Observations | 1,104 | 1,104 | 1,104 | 1,104 | 1,104 | 1,104 |
| Countries | 14 | 14 | 14 | 14 | 14 | 14 |
| Quarters | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 |
| Within \(R^2\) | 0.0638 | 0.0624 | 0.0653 | 0.0565 | 0.0592 | 0.0587 |
| \(R^2\) | 0.0639 | 0.0625 | 0.0654 | 0.0566 | 0.0593 | 0.0588 |

### Log global EPU, next-quarter change

Following quarter's `d_log_gepu`, the sum of its three monthly log changes.

|  | Voice and accountability | Political stability | Government effectiveness | Regulatory quality | Rule of law | Control of corruption |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| WGI, lagged | −0.024976* (0.011648) | 0.020568 (0.011921) | 0.025584 (0.015641) | −0.020290 (0.015411) | −0.032984 (0.019713) | −0.001711 (0.019492) |
| GPR, standardized | −0.028346*** (0.008241) | −0.036347*** (0.007745) | −0.024659* (0.012590) | −0.015077 (0.008724) | −0.028621*** (0.007308) | −0.027057*** (0.007692) |
| WGI x GPR | −0.012568 (0.012690) | −0.030006*** (0.009029) | −0.009668 (0.023047) | −0.034732*** (0.011380) | −0.029127** (0.010011) | −0.022033* (0.011267) |
| Policy rate, lagged change | −0.003450 (0.006073) | −0.002728 (0.006121) | −0.003747 (0.006160) | −0.003303 (0.006265) | −0.003563 (0.006124) | −0.003435 (0.006163) |
| Inflation, lagged change | 0.003022 (0.002994) | 0.003491 (0.003086) | 0.003286 (0.003043) | 0.003368 (0.003007) | 0.003110 (0.003166) | 0.003460 (0.003023) |
| Log oil price, lagged change | −0.038805*** (0.006657) | −0.041681*** (0.006355) | −0.036553*** (0.006834) | −0.038482*** (0.006382) | −0.038111*** (0.006981) | −0.039243*** (0.006340) |
| Log VIX, lagged | −0.029419*** (0.006814) | −0.032864*** (0.006199) | −0.031090*** (0.006684) | −0.032567*** (0.005840) | −0.030059*** (0.005824) | −0.032336*** (0.005829) |
| Financial development, lagged change | −0.584360*** (0.115095) | −0.653342*** (0.114598) | −0.610894*** (0.113174) | −0.619455*** (0.112823) | −0.599995*** (0.107743) | −0.634320*** (0.112854) |
| Debt/GDP, lagged change | −0.004357*** (0.001040) | −0.004379*** (0.001019) | −0.004292*** (0.001170) | −0.004202*** (0.001094) | −0.004432*** (0.000968) | −0.004055*** (0.001092) |
| Observations | 1,104 | 1,104 | 1,104 | 1,104 | 1,104 | 1,104 |
| Countries | 14 | 14 | 14 | 14 | 14 | 14 |
| Quarters | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 |
| Within \(R^2\) | 0.0208 | 0.0248 | 0.0203 | 0.0226 | 0.0225 | 0.0214 |
| \(R^2\) | 0.0210 | 0.0249 | 0.0204 | 0.0227 | 0.0227 | 0.0215 |

### Financial development, next-quarter change

Following quarter's `d_financial_development`, that year's annual change. The 2022 change is blank, so rows dated 2021Q4 and 2022Q1 drop out.

|  | Voice and accountability | Political stability | Government effectiveness | Regulatory quality | Rule of law | Control of corruption |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| WGI, lagged | 0.013018*** (0.003413) | 0.002970 (0.004409) | −0.011329 (0.006466) | 0.007324 (0.008142) | 0.009926 (0.009174) | −0.000366 (0.010511) |
| GPR, standardized | 0.001002 (0.000969) | 0.001025 (0.002071) | 0.000422 (0.001169) | 0.000087 (0.001604) | 0.001129 (0.001170) | 0.000887 (0.001362) |
| WGI x GPR | 0.002876* (0.001593) | 0.000384 (0.002232) | 0.001037 (0.003034) | 0.002143 (0.002947) | 0.003055 (0.001927) | 0.001922 (0.002190) |
| Policy rate, lagged change | −0.001778* (0.000886) | −0.001967** (0.000844) | −0.001886** (0.000867) | −0.002014** (0.000854) | −0.001861* (0.000871) | −0.001970** (0.000845) |
| Inflation, lagged change | −0.000231 (0.000775) | −0.000204 (0.000784) | −0.000198 (0.000808) | −0.000224 (0.000788) | −0.000213 (0.000777) | −0.000236 (0.000804) |
| Log oil price, lagged change | −0.007551** (0.003133) | −0.007361** (0.003149) | −0.008546** (0.003347) | −0.007376** (0.003102) | −0.007620** (0.003243) | −0.007335** (0.003133) |
| Log VIX, lagged | −0.006617 (0.004166) | −0.005609 (0.004278) | −0.006310 (0.004503) | −0.005489 (0.004331) | −0.005827 (0.004124) | −0.005441 (0.004193) |
| Log global EPU, lagged change | −0.000081 (0.001928) | −0.000061 (0.001896) | 0.000113 (0.001931) | 0.000010 (0.001925) | −0.000130 (0.001941) | 0.000006 (0.001912) |
| Debt/GDP, lagged change | 0.000261 (0.000382) | 0.000109 (0.000379) | 0.000231 (0.000390) | 0.000127 (0.000361) | 0.000195 (0.000401) | 0.000106 (0.000381) |
| Observations | 1,076 | 1,076 | 1,076 | 1,076 | 1,076 | 1,076 |
| Countries | 14 | 14 | 14 | 14 | 14 | 14 |
| Quarters | 2002-Q2 to 2021-Q3 | 2002-Q2 to 2021-Q3 | 2002-Q2 to 2021-Q3 | 2002-Q2 to 2021-Q3 | 2002-Q2 to 2021-Q3 | 2002-Q2 to 2021-Q3 |
| Within \(R^2\) | 0.0327 | 0.0176 | 0.0268 | 0.0199 | 0.0236 | 0.0173 |
| \(R^2\) | 0.0531 | 0.0382 | 0.0473 | 0.0405 | 0.0442 | 0.0380 |

### Debt/GDP, next-quarter change

Following quarter's `d_public_debt_gdp`, that year's annual change.

|  | Voice and accountability | Political stability | Government effectiveness | Regulatory quality | Rule of law | Control of corruption |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| WGI, lagged | −2.090922 (1.660405) | −0.165615 (1.525351) | 3.806397*** (0.811908) | 0.074534 (2.020154) | −2.579787 (2.183060) | 0.016123 (1.808253) |
| GPR, standardized | −0.423891* (0.208424) | −0.626967** (0.229208) | −0.015355 (0.354363) | −0.105250 (0.379618) | −0.441089 (0.250858) | −0.391716 (0.264490) |
| WGI x GPR | −1.026543*** (0.276017) | −0.769525** (0.316207) | −1.068993* (0.555193) | −0.803463 (0.462781) | −0.868296 (0.539311) | −0.423985 (0.388104) |
| Policy rate, lagged change | −0.177289 (0.270041) | −0.168502 (0.274784) | −0.216445 (0.277438) | −0.180798 (0.286879) | −0.194258 (0.266088) | −0.182019 (0.286218) |
| Inflation, lagged change | −0.158776* (0.074124) | −0.136347 (0.083958) | −0.137097 (0.084017) | −0.133018 (0.087215) | −0.157414** (0.069733) | −0.133657 (0.090496) |
| Log oil price, lagged change | −2.131252*** (0.549718) | −2.215971*** (0.502762) | −1.760508*** (0.455729) | −2.156660*** (0.505106) | −2.086153*** (0.546030) | −2.171461*** (0.510139) |
| Log VIX, lagged | 2.015656** (0.760193) | 1.843904** (0.753864) | 1.955586** (0.715993) | 1.830879** (0.718576) | 1.871025** (0.730670) | 1.846118** (0.725885) |
| Log global EPU, lagged change | −0.119049 (0.336167) | −0.039139 (0.331693) | −0.103770 (0.341595) | −0.063868 (0.327608) | −0.043227 (0.323711) | −0.051627 (0.333777) |
| Financial development, lagged change | −0.860667 (7.886956) | −4.848629 (7.988997) | −1.974284 (6.922929) | −4.351625 (7.382035) | −2.763077 (8.449511) | −4.370046 (8.015303) |
| Observations | 1,104 | 1,104 | 1,104 | 1,104 | 1,104 | 1,104 |
| Countries | 14 | 14 | 14 | 14 | 14 | 14 |
| Quarters | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 |
| Within \(R^2\) | 0.0960 | 0.0783 | 0.1142 | 0.0710 | 0.0855 | 0.0677 |
| \(R^2\) | 0.1525 | 0.1359 | 0.1695 | 0.1290 | 0.1426 | 0.1259 |

### Current-quarter outcome, full sample

|  | Voice and accountability | Political stability | Government effectiveness | Regulatory quality | Rule of law | Control of corruption |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| WGI, lagged | 0.004916 (0.007027) | −0.000352 (0.003967) | 0.001392 (0.003697) | 0.006588 (0.004278) | 0.002837 (0.008362) | −0.002455 (0.003912) |
| GPR, standardized | −0.000263 (0.001300) | −0.000957 (0.000977) | −0.001278 (0.001746) | −0.000455 (0.001847) | −0.000305 (0.001433) | −0.000619 (0.001307) |
| WGI x GPR | −0.000991 (0.001137) | −0.000343 (0.001574) | 0.000262 (0.001419) | −0.000680 (0.001733) | −0.001047 (0.001434) | −0.000499 (0.001163) |
| Policy rate, lagged change | 0.001209 (0.001288) | 0.001160 (0.001340) | 0.001167 (0.001355) | 0.001108 (0.001345) | 0.001149 (0.001282) | 0.001156 (0.001337) |
| Inflation, lagged change | 0.001166 (0.000936) | 0.001119 (0.000915) | 0.001112 (0.000905) | 0.001162 (0.000894) | 0.001161 (0.000950) | 0.001128 (0.000902) |
| Log oil price, lagged change | 0.007106 (0.005411) | 0.007219 (0.005437) | 0.007276 (0.005379) | 0.006985 (0.005424) | 0.007171 (0.005419) | 0.007308 (0.005431) |
| Log VIX, lagged | 0.011838*** (0.003943) | 0.011945*** (0.003994) | 0.011935*** (0.003927) | 0.011716*** (0.003906) | 0.011932*** (0.003960) | 0.012056*** (0.004106) |
| Log global EPU, lagged change | −0.002529 (0.003282) | −0.002474 (0.003313) | −0.002447 (0.003306) | −0.002402 (0.003290) | −0.002508 (0.003272) | −0.002491 (0.003299) |
| Financial development, lagged change | 0.077536* (0.041381) | 0.079496* (0.042542) | 0.080536* (0.042011) | 0.076989* (0.042404) | 0.079308* (0.042320) | 0.079810* (0.042983) |
| Debt/GDP, lagged change | −0.000844*** (0.000255) | −0.000853*** (0.000260) | −0.000845*** (0.000264) | −0.000822*** (0.000267) | −0.000847*** (0.000263) | −0.000859*** (0.000268) |
| Observations | 2,193 | 2,193 | 2,193 | 2,193 | 2,193 | 2,193 |
| Countries | 28 | 28 | 28 | 28 | 28 | 28 |
| Quarters | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 |
| Within \(R^2\) | 0.0202 | 0.0195 | 0.0195 | 0.0203 | 0.0199 | 0.0197 |
| \(R^2\) | 0.0241 | 0.0234 | 0.0235 | 0.0242 | 0.0238 | 0.0236 |

### Current-quarter outcome, emerging economies

|  | Voice and accountability | Political stability | Government effectiveness | Regulatory quality | Rule of law | Control of corruption |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| WGI, lagged | 0.004849 (0.007324) | 0.000536 (0.005313) | 0.008634* (0.004719) | 0.008639 (0.006834) | 0.001595 (0.009010) | −0.001328 (0.006965) |
| GPR, standardized | −0.001179 (0.001569) | −0.002151 (0.001437) | −0.001069 (0.002007) | 0.000117 (0.002210) | −0.001477 (0.001425) | −0.001301 (0.001508) |
| WGI x GPR | −0.003992* (0.002086) | −0.002391 (0.002473) | −0.001114 (0.003692) | −0.004068 (0.003321) | −0.006249** (0.002626) | −0.003611* (0.002005) |
| Policy rate, lagged change | 0.001728 (0.001469) | 0.001619 (0.001526) | 0.001492 (0.001545) | 0.001538 (0.001548) | 0.001613 (0.001448) | 0.001577 (0.001535) |
| Inflation, lagged change | 0.001458 (0.001051) | 0.001431 (0.001053) | 0.001421 (0.001041) | 0.001477 (0.001034) | 0.001462 (0.001048) | 0.001456 (0.001038) |
| Log oil price, lagged change | 0.009736 (0.010494) | 0.009812 (0.010532) | 0.010893 (0.010484) | 0.010014 (0.010394) | 0.009962 (0.010487) | 0.009989 (0.010497) |
| Log VIX, lagged | 0.016212** (0.006500) | 0.015961** (0.006545) | 0.016584** (0.006228) | 0.015834** (0.006308) | 0.016334** (0.006539) | 0.016011** (0.006695) |
| Log global EPU, lagged change | −0.006254 (0.005347) | −0.006030 (0.005338) | −0.006197 (0.005296) | −0.006069 (0.005287) | −0.006257 (0.005321) | −0.006128 (0.005354) |
| Financial development, lagged change | 0.126132 (0.082845) | 0.123863 (0.083201) | 0.131938 (0.081498) | 0.120988 (0.082595) | 0.127095 (0.084417) | 0.124838 (0.084520) |
| Debt/GDP, lagged change | −0.001888*** (0.000387) | −0.001909*** (0.000414) | −0.001974*** (0.000387) | −0.001881*** (0.000408) | −0.001915*** (0.000412) | −0.001891*** (0.000422) |
| Observations | 1,104 | 1,104 | 1,104 | 1,104 | 1,104 | 1,104 |
| Countries | 14 | 14 | 14 | 14 | 14 | 14 |
| Quarters | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 | 2002-Q2 to 2022-Q1 |
| Within \(R^2\) | 0.0370 | 0.0353 | 0.0360 | 0.0366 | 0.0374 | 0.0357 |
| \(R^2\) | 0.0406 | 0.0389 | 0.0396 | 0.0402 | 0.0410 | 0.0393 |


## Annual estimates, emerging economies

The regression reads `cleaned/replication_cleaned/country_month.csv`. Each treated series is the twelve-month mean this year minus the twelve-month mean last year. GPR, WGI, the interaction, and log VIX stay in the same year. Results are `output/model1_annual_emerging_mean_diff_results.csv`.

| Role | Column | Timing | How the year is built |
| --- | --- | --- | --- |
| Outcome | `reer` | Change from the previous year | Mean of the twelve monthly \(\ln(\text{reer})\) values, minus the previous year's mean. |
| GPR, standardized | `gpr_z` | Same year | Mean of the twelve monthly within-country z-scores. |
| WGI | `wgi_va`, `wgi_pv`, `wgi_ge`, `wgi_rq`, `wgi_rl`, or `wgi_cc` | Same year | That year's score, repeated on every month. One column per regression. |
| WGI × GPR | same-year WGI × same-year mean `gpr_z` | Same year | Product in original units. Not centered. |
| Policy rate | `policy_rate` | Change from the previous year | First difference of the twelve-month mean. |
| Inflation | `inflation` | Change from the previous year | First difference of the twelve-month mean. |
| Log oil price | `oil_price` | Change from the previous year | First difference of the twelve-month mean of the monthly log. |
| Log VIX | `vix` | Same year | Mean of the twelve monthly \(\ln(\text{VIX})\) values. |
| Log global EPU | `gepu` | Change from the previous year | First difference of the twelve-month mean of the monthly log. |
| Financial development | `financial_development` | Change from the previous year | This year's level minus last year's level. |
| Debt/GDP | `public_debt_gdp` | Change from the previous year | This year's level minus last year's level. |

273 country-years, 14 emerging economies, 2002–2021. Indonesia contributes 2007–2021 and Turkiye contributes 2004–2021. Ukraine contributes no years. Parentheses are country-clustered standard errors. \(p<0.01\), \(p<0.05\), \(p<0.10\).

|  | Voice and accountability | Political stability | Government effectiveness | Regulatory quality | Rule of law | Control of corruption |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| WGI | 0.028816 (0.018889) | 0.005083 (0.013886) | 0.020594 (0.013411) | 0.040749* (0.019382) | 0.029233 (0.022479) | 0.031395* (0.017337) |
| GPR, standardized | −0.014448** (0.006108) | −0.015417** (0.006285) | −0.015169** (0.005194) | −0.015632** (0.005447) | −0.014760** (0.005135) | −0.016072*** (0.004732) |
| WGI × GPR | 0.004611 (0.005699) | 0.000715 (0.006387) | −0.002368 (0.007443) | −0.002189 (0.005651) | 0.003578 (0.007775) | 0.006505 (0.006265) |
| Policy rate, annual change | 0.003099 (0.002792) | 0.002805 (0.002931) | 0.002583 (0.002974) | 0.002334 (0.002812) | 0.003026 (0.002718) | 0.002755 (0.002820) |
| Inflation, annual change | −0.010637** (0.003671) | −0.010939** (0.003697) | −0.010955** (0.003655) | −0.010717** (0.003649) | −0.010812** (0.003743) | −0.010946** (0.003685) |
| Log oil price, annual change | 0.072929*** (0.020902) | 0.073958*** (0.021034) | 0.076385*** (0.020178) | 0.073049*** (0.021448) | 0.072820*** (0.021816) | 0.073807*** (0.021376) |
| Log VIX | −0.021193** (0.008441) | −0.018459** (0.008042) | −0.015582* (0.008313) | −0.018941** (0.007474) | −0.018853** (0.007540) | −0.019438** (0.007515) |
| Log global EPU, annual change | 0.053405*** (0.012444) | 0.054584*** (0.013024) | 0.051887*** (0.013073) | 0.053738*** (0.012244) | 0.053982*** (0.011902) | 0.054188*** (0.012367) |
| Financial development, annual change | −0.040139 (0.228658) | −0.002835 (0.236941) | 0.015873 (0.242448) | −0.027066 (0.232313) | −0.020631 (0.237631) | −0.006944 (0.244660) |
| Debt/GDP, annual change | −0.003143*** (0.000905) | −0.003513*** (0.001086) | −0.003685*** (0.001074) | −0.003485*** (0.001051) | −0.003278*** (0.001058) | −0.003443*** (0.001027) |
| Observations | 273 | 273 | 273 | 273 | 273 | 273 |
| Countries | 14 | 14 | 14 | 14 | 14 | 14 |
| Years | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 |
| Within \(R^2\) | 0.2660 | 0.2581 | 0.2615 | 0.2693 | 0.2631 | 0.2647 |
| \(R^2\) | 0.2872 | 0.2795 | 0.2828 | 0.2904 | 0.2844 | 0.2860 |

## Annual estimates without debt/GDP, emerging economies

Same emerging country-years, country fixed effects, and country-clustered standard errors as the annual REER regression above. The debt/GDP annual change is omitted. GPR, WGI, the interaction, and the other controls stay. Results are `output/model1_annual_emerging_no_debt_results.csv`.

|  | Voice and accountability | Political stability | Government effectiveness | Regulatory quality | Rule of law | Control of corruption |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| WGI | 0.037967* (0.020954) | 0.004957 (0.017267) | 0.013671 (0.012287) | 0.044452* (0.021595) | 0.039526 (0.025253) | 0.034155* (0.017757) |
| GPR, standardized | −0.012486 (0.007320) | −0.010154 (0.007141) | −0.016129** (0.006704) | −0.016689** (0.007115) | −0.012026* (0.006679) | −0.014044** (0.006088) |
| WGI × GPR | 0.011081 (0.006321) | 0.006885 (0.007191) | 0.008028 (0.008114) | 0.006278 (0.008130) | 0.011258 (0.010872) | 0.012724 (0.009409) |
| Policy rate, annual change | 0.003400 (0.002865) | 0.003015 (0.003151) | 0.002894 (0.003246) | 0.002569 (0.003071) | 0.003335 (0.002838) | 0.002994 (0.003068) |
| Inflation, annual change | −0.010558** (0.003577) | −0.010956*** (0.003575) | −0.011016*** (0.003547) | −0.010756*** (0.003540) | −0.010833** (0.003642) | −0.010986*** (0.003580) |
| Log oil price, annual change | 0.087206*** (0.021889) | 0.091274*** (0.021621) | 0.093488*** (0.020825) | 0.090413*** (0.021861) | 0.088312*** (0.023206) | 0.090879*** (0.021522) |
| Log VIX | −0.033459*** (0.009314) | −0.030332*** (0.009764) | −0.028087*** (0.008886) | −0.030822*** (0.008282) | −0.030572*** (0.008432) | −0.031508*** (0.008574) |
| Log global EPU, annual change | 0.053155*** (0.013406) | 0.054582*** (0.014048) | 0.051721*** (0.014007) | 0.053754*** (0.013185) | 0.054352*** (0.012803) | 0.054039*** (0.013202) |
| Financial development, annual change | −0.072068 (0.207365) | −0.016090 (0.218081) | −0.006571 (0.220869) | −0.047144 (0.213373) | −0.045127 (0.220984) | −0.023472 (0.226893) |
| Observations | 273 | 273 | 273 | 273 | 273 | 273 |
| Countries | 14 | 14 | 14 | 14 | 14 | 14 |
| Years | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 |
| Within \(R^2\) | 0.2420 | 0.2269 | 0.2274 | 0.2384 | 0.2365 | 0.2342 |
| \(R^2\) | 0.2639 | 0.2493 | 0.2497 | 0.2604 | 0.2585 | 0.2563 |

## REER on debt/GDP only, emerging economies

The outcome is the annual REER change from the emerging regression above. The only regressor is the debt/GDP annual change. Country fixed effects and country-clustered standard errors match that regression, on the same 273 country-years. Results are `output/model1_annual_emerging_debt_only_results.csv`.

|  | Debt/GDP only |
| --- | ---: |
| Debt/GDP, annual change | −0.005052*** (0.001297) |
| Observations | 273 |
| Countries | 14 |
| Years | 2002 to 2021 |
| Within \(R^2\) | 0.0912 |
| \(R^2\) | 0.1174 |

Countries: Brazil, Chile, China, Colombia, Hungary, India, Indonesia, Malaysia, Mexico, Philippines, Poland, South Africa, Thailand, Turkiye.

## Control outcomes, emerging economies

Each table keeps the emerging country-years, country fixed effects, and country-clustered standard errors from the annual REER regression above. The named series is the outcome and is omitted from the regressors. The change in mean log REER is not a regressor. GPR, WGI, and the interaction stay in the same year. Results are `output/model1_annual_emerging_control_outcomes.csv`.

Log oil, log VIX, and log global EPU take the same value for every country in a year.

### Policy rate, annual change

First difference of the twelve-month mean of `policy_rate`.

|  | Voice and accountability | Political stability | Government effectiveness | Regulatory quality | Rule of law | Control of corruption |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| WGI | −0.554123 (0.712689) | −0.034815 (0.319980) | 0.637011 (0.397722) | 0.866533* (0.411049) | −0.625357 (1.007766) | 0.145618 (0.497562) |
| GPR, standardized | 0.019093 (0.207190) | 0.087037 (0.259956) | 0.081867 (0.284510) | 0.098263 (0.294001) | 0.010340 (0.205216) | 0.036104 (0.259248) |
| WGI x GPR | −0.072129 (0.166080) | 0.058249 (0.225449) | −0.082108 (0.342722) | −0.186408 (0.270173) | −0.136974 (0.252425) | −0.074477 (0.215639) |
| Inflation, annual change | 0.517320*** (0.141106) | 0.526360*** (0.149413) | 0.523455*** (0.149455) | 0.527059*** (0.149003) | 0.521368*** (0.140906) | 0.527043*** (0.150097) |
| Log oil price, annual change | −0.177292 (0.444936) | −0.190079 (0.441392) | −0.114072 (0.442528) | −0.221290 (0.434744) | −0.178871 (0.438835) | −0.202179 (0.440207) |
| Log VIX | −1.219456*** (0.395674) | −1.284253** (0.445874) | −1.205103** (0.457282) | −1.291062** (0.464402) | −1.252647** (0.431298) | −1.286851** (0.450023) |
| Log global EPU, annual change | 0.670298 (0.588546) | 0.663980 (0.596618) | 0.590320 (0.562908) | 0.635072 (0.594059) | 0.647933 (0.584505) | 0.650438 (0.578906) |
| Financial development, annual change | −6.889284 (6.452952) | −7.621085 (6.745220) | −7.040642 (6.872286) | −8.047225 (7.093645) | −7.164661 (6.495633) | −7.639246 (6.847040) |
| Debt/GDP, annual change | −0.021665 (0.030348) | −0.013102 (0.033547) | −0.018449 (0.033918) | −0.014497 (0.035401) | −0.020867 (0.029434) | −0.014836 (0.035840) |
| Observations | 273 | 273 | 273 | 273 | 273 | 273 |
| Countries | 14 | 14 | 14 | 14 | 14 | 14 |
| Years | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 |
| Within \(R^2\) | 0.4406 | 0.4375 | 0.4412 | 0.4435 | 0.4402 | 0.4377 |
| \(R^2\) | 0.4491 | 0.4461 | 0.4498 | 0.4520 | 0.4488 | 0.4463 |

### Inflation, annual change

First difference of the twelve-month mean of `inflation`.

|  | Voice and accountability | Political stability | Government effectiveness | Regulatory quality | Rule of law | Control of corruption |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| WGI | −0.864080** (0.389191) | −0.231757 (0.300325) | −0.055462 (0.361548) | −0.589185 (0.508321) | −0.699527 (0.434603) | −0.132243 (0.336777) |
| GPR, standardized | 0.029920 (0.219052) | 0.091948 (0.246442) | 0.012057 (0.203882) | −0.003585 (0.242370) | 0.129390 (0.219965) | 0.106118 (0.193175) |
| WGI x GPR | 0.025174 (0.205667) | 0.052365 (0.210780) | 0.278964 (0.307791) | 0.274101 (0.340642) | 0.448992 (0.324240) | 0.237819 (0.318720) |
| Policy rate, annual change | 0.688105*** (0.079829) | 0.702731*** (0.078615) | 0.703535*** (0.077164) | 0.708569*** (0.078645) | 0.694061*** (0.082916) | 0.703716*** (0.077556) |
| Log oil price, annual change | 1.883089** (0.668224) | 1.869096** (0.676349) | 1.877526** (0.697663) | 1.893601** (0.676020) | 1.921244** (0.671646) | 1.885639** (0.677060) |
| Log VIX | 0.782410 (0.508601) | 0.751495 (0.486797) | 0.736036 (0.493030) | 0.737760 (0.494468) | 0.687801 (0.479511) | 0.722943 (0.479616) |
| Log global EPU, annual change | 1.301958** (0.548974) | 1.260790** (0.558823) | 1.279073** (0.558107) | 1.297480** (0.574689) | 1.355252** (0.546191) | 1.302353** (0.548265) |
| Financial development, annual change | 5.885819 (6.535655) | 5.079116 (6.686212) | 4.938501 (6.822244) | 5.276373 (6.883188) | 5.062535 (6.564643) | 4.974945 (6.752101) |
| Debt/GDP, annual change | −0.007480 (0.035438) | 0.001382 (0.031772) | 0.004866 (0.031937) | 0.003243 (0.032371) | 0.001854 (0.030673) | 0.003368 (0.032089) |
| Observations | 273 | 273 | 273 | 273 | 273 | 273 |
| Countries | 14 | 14 | 14 | 14 | 14 | 14 |
| Years | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 |
| Within \(R^2\) | 0.4610 | 0.4560 | 0.4560 | 0.4580 | 0.4602 | 0.4561 |
| \(R^2\) | 0.4646 | 0.4597 | 0.4597 | 0.4617 | 0.4638 | 0.4598 |

### Log oil price, annual change

First difference of the twelve-month mean of the monthly log of `oil_price`.

|  | Voice and accountability | Political stability | Government effectiveness | Regulatory quality | Rule of law | Control of corruption |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| WGI | 0.047555 (0.065230) | −0.000499 (0.043868) | −0.185201** (0.068955) | 0.018150 (0.107562) | 0.088048 (0.092527) | 0.014677 (0.098949) |
| GPR, standardized | 0.022020 (0.028781) | −0.008056 (0.052749) | 0.023934 (0.028713) | 0.045402* (0.024912) | 0.010093 (0.035423) | 0.011902 (0.035962) |
| WGI x GPR | −0.016021 (0.035268) | −0.044213 (0.046920) | −0.039621 (0.059442) | −0.091569 (0.078781) | −0.074009 (0.071666) | −0.061333 (0.065358) |
| Policy rate, annual change | −0.004555 (0.011106) | −0.004846 (0.010814) | −0.002862 (0.010810) | −0.005680 (0.010715) | −0.004557 (0.010956) | −0.005157 (0.010794) |
| Inflation, annual change | 0.036372*** (0.011472) | 0.035692*** (0.011545) | 0.035044*** (0.011575) | 0.036155*** (0.011673) | 0.036771*** (0.011487) | 0.036024*** (0.011588) |
| Log VIX | 0.017441 (0.043432) | 0.018925 (0.040268) | −0.006980 (0.040912) | 0.018282 (0.041160) | 0.023599 (0.042666) | 0.019687 (0.042092) |
| Log global EPU, annual change | −0.366456*** (0.052604) | −0.367283*** (0.054554) | −0.333911*** (0.059477) | −0.368721*** (0.053409) | −0.373968*** (0.052542) | −0.368412*** (0.052579) |
| Financial development, annual change | −0.868880 (0.744604) | −0.847799 (0.764609) | −0.971607 (0.766143) | −0.813415 (0.739975) | −0.831540 (0.766278) | −0.824884 (0.766492) |
| Debt/GDP, annual change | −0.026375*** (0.004945) | −0.027472*** (0.004490) | −0.025414*** (0.004781) | −0.027478*** (0.004827) | −0.026654*** (0.004790) | −0.027075*** (0.004594) |
| Observations | 273 | 273 | 273 | 273 | 273 | 273 |
| Countries | 14 | 14 | 14 | 14 | 14 | 14 |
| Years | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 |
| Within \(R^2\) | 0.3123 | 0.3139 | 0.3294 | 0.3165 | 0.3176 | 0.3137 |
| \(R^2\) | 0.3133 | 0.3148 | 0.3303 | 0.3174 | 0.3185 | 0.3146 |

### Log VIX

Mean of the twelve monthly logs of `vix`.

|  | Voice and accountability | Political stability | Government effectiveness | Regulatory quality | Rule of law | Control of corruption |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| WGI | 0.136706 (0.097715) | 0.085898 (0.111784) | −0.187693** (0.078851) | 0.061995 (0.138961) | 0.053914 (0.096274) | 0.094547 (0.158447) |
| GPR, standardized | 0.046760 (0.043700) | 0.037241 (0.055709) | 0.032182 (0.049258) | 0.024720 (0.067886) | 0.053069 (0.048576) | 0.037442 (0.048726) |
| WGI x GPR | 0.137287*** (0.043373) | 0.002647 (0.060317) | −0.029346 (0.047951) | 0.024779 (0.087241) | 0.117228 (0.080276) | 0.061435 (0.058875) |
| Policy rate, annual change | −0.033752*** (0.011099) | −0.036628*** (0.011022) | −0.034085*** (0.009832) | −0.037468*** (0.010458) | −0.035709*** (0.011001) | −0.036790*** (0.010243) |
| Inflation, annual change | 0.016281 (0.011004) | 0.016054 (0.010573) | 0.015489 (0.010728) | 0.015926 (0.010894) | 0.014728 (0.010609) | 0.015479 (0.010473) |
| Log oil price, annual change | 0.018790 (0.046342) | 0.021171 (0.044400) | −0.007870 (0.046386) | 0.020669 (0.046044) | 0.026404 (0.047023) | 0.022064 (0.046556) |
| Log global EPU, annual change | 0.402921*** (0.038988) | 0.415296*** (0.033242) | 0.420683*** (0.035502) | 0.411595*** (0.036447) | 0.422693*** (0.036353) | 0.412347*** (0.036256) |
| Financial development, annual change | −1.278995* (0.720076) | −0.985816 (0.740221) | −1.109928 (0.782626) | −1.022665 (0.776757) | −1.072704 (0.717939) | −0.994912 (0.720666) |
| Debt/GDP, annual change | 0.024411*** (0.006479) | 0.021074*** (0.006582) | 0.020951*** (0.005870) | 0.021257*** (0.006068) | 0.022558*** (0.006670) | 0.021454*** (0.006167) |
| Observations | 273 | 273 | 273 | 273 | 273 | 273 |
| Countries | 14 | 14 | 14 | 14 | 14 | 14 |
| Years | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 |
| Within \(R^2\) | 0.2650 | 0.2385 | 0.2498 | 0.2333 | 0.2424 | 0.2369 |
| \(R^2\) | 0.2657 | 0.2392 | 0.2506 | 0.2341 | 0.2432 | 0.2376 |

### Log global EPU, annual change

First difference of the twelve-month mean of the monthly log of `gepu`.

|  | Voice and accountability | Political stability | Government effectiveness | Regulatory quality | Rule of law | Control of corruption |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| WGI | 0.026177 (0.070791) | −0.033610 (0.057643) | 0.087706* (0.046651) | −0.002670 (0.052434) | 0.019359 (0.067052) | 0.007498 (0.061494) |
| GPR, standardized | 0.006092 (0.022415) | −0.009366 (0.029551) | 0.010198 (0.018778) | 0.021238 (0.025515) | −0.007354 (0.025566) | −0.000461 (0.022207) |
| WGI x GPR | −0.030591 (0.019605) | −0.022655 (0.024879) | −0.004974 (0.038575) | −0.052507 (0.041661) | −0.085031 (0.051775) | −0.052434 (0.045621) |
| Policy rate, annual change | 0.009682 (0.010206) | 0.009525 (0.010454) | 0.008498 (0.009719) | 0.009219 (0.010377) | 0.009260 (0.009929) | 0.009338 (0.010056) |
| Inflation, annual change | 0.014138** (0.005160) | 0.013547** (0.005351) | 0.013699** (0.005368) | 0.014011** (0.005544) | 0.014549** (0.005127) | 0.014004** (0.005266) |
| Log oil price, annual change | −0.206019*** (0.031335) | −0.206662*** (0.031763) | −0.191607*** (0.033970) | −0.208534*** (0.032052) | −0.209767*** (0.031628) | −0.207354*** (0.031458) |
| Log VIX | 0.210265*** (0.021173) | 0.208881*** (0.018464) | 0.214104*** (0.021270) | 0.205890*** (0.018897) | 0.211914*** (0.020140) | 0.207078*** (0.019136) |
| Financial development, annual change | 0.208549 (0.512931) | 0.195590 (0.506198) | 0.268304 (0.532982) | 0.214213 (0.520487) | 0.239220 (0.513740) | 0.205288 (0.517886) |
| Debt/GDP, annual change | 0.000259 (0.003863) | 0.000002 (0.003789) | 0.000142 (0.003845) | −0.000014 (0.003638) | −0.000357 (0.003912) | 0.000133 (0.003547) |
| Observations | 273 | 273 | 273 | 273 | 273 | 273 |
| Countries | 14 | 14 | 14 | 14 | 14 | 14 |
| Years | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 |
| Within \(R^2\) | 0.2165 | 0.2176 | 0.2201 | 0.2166 | 0.2242 | 0.2172 |
| \(R^2\) | 0.2187 | 0.2198 | 0.2223 | 0.2188 | 0.2264 | 0.2194 |

### Financial development, annual change

This year's `financial_development` level minus last year's level.

|  | Voice and accountability | Political stability | Government effectiveness | Regulatory quality | Rule of law | Control of corruption |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| WGI | 0.014197** (0.004719) | 0.001858 (0.005284) | −0.011336 (0.007582) | 0.011442 (0.009910) | 0.010925 (0.010330) | 0.002281 (0.011441) |
| GPR, standardized | 0.001612 (0.001916) | −0.000268 (0.005152) | −0.000371 (0.002261) | −0.000569 (0.003074) | 0.001755 (0.002462) | 0.000690 (0.003174) |
| WGI x GPR | 0.006790** (0.002771) | −0.001246 (0.004600) | 0.002769 (0.006248) | 0.003718 (0.007073) | 0.005834 (0.005252) | 0.002096 (0.006703) |
| Policy rate, annual change | −0.001494 (0.001172) | −0.001685 (0.001166) | −0.001553 (0.001215) | −0.001784 (0.001234) | −0.001577 (0.001170) | −0.001689 (0.001183) |
| Inflation, annual change | 0.000960 (0.001010) | 0.000841 (0.001048) | 0.000810 (0.001063) | 0.000870 (0.001077) | 0.000837 (0.001031) | 0.000824 (0.001063) |
| Log oil price, annual change | −0.007334 (0.006327) | −0.007353 (0.006649) | −0.008541 (0.006687) | −0.007026 (0.006410) | −0.007183 (0.006645) | −0.007152 (0.006674) |
| Log VIX | −0.010021* (0.005593) | −0.007642 (0.005581) | −0.008654 (0.005842) | −0.007813 (0.005756) | −0.008281 (0.005379) | −0.007696 (0.005411) |
| Log global EPU, annual change | 0.003131 (0.007598) | 0.003015 (0.007669) | 0.004110 (0.007962) | 0.003271 (0.007833) | 0.003684 (0.007797) | 0.003162 (0.007854) |
| Debt/GDP, annual change | 0.000498 (0.000650) | 0.000182 (0.000614) | 0.000293 (0.000634) | 0.000274 (0.000583) | 0.000364 (0.000666) | 0.000227 (0.000617) |
| Observations | 273 | 273 | 273 | 273 | 273 | 273 |
| Countries | 14 | 14 | 14 | 14 | 14 | 14 |
| Years | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 |
| Within \(R^2\) | 0.0516 | 0.0277 | 0.0367 | 0.0354 | 0.0368 | 0.0277 |
| \(R^2\) | 0.0717 | 0.0483 | 0.0571 | 0.0558 | 0.0572 | 0.0483 |

### Debt/GDP, annual change

This year's `public_debt_gdp` level minus last year's level.

|  | Voice and accountability | Political stability | Government effectiveness | Regulatory quality | Rule of law | Control of corruption |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| WGI | −2.910935* (1.586543) | 0.035916 (1.484307) | 1.878921 (1.245239) | −1.062460 (2.174671) | −3.140353 (2.204953) | −0.801847 (1.991271) |
| GPR, standardized | −0.624035 (0.607020) | −1.497756* (0.709597) | 0.260538 (0.678467) | 0.303285 (0.713253) | −0.834130 (0.625902) | −0.588952 (0.593257) |
| WGI x GPR | −2.058312*** (0.520711) | −1.756118** (0.656457) | −2.821481** (1.005788) | −2.429884* (1.147022) | −2.342931* (1.311225) | −1.806300 (1.097640) |
| Policy rate, annual change | −0.095849 (0.162676) | −0.059924 (0.173200) | −0.084526 (0.183764) | −0.067478 (0.187041) | −0.094278 (0.161095) | −0.069308 (0.190007) |
| Inflation, annual change | −0.024880 (0.116855) | 0.004734 (0.109008) | 0.016587 (0.109536) | 0.011228 (0.112542) | 0.006293 (0.104314) | 0.011786 (0.112731) |
| Log oil price, annual change | −4.541756*** (0.919746) | −4.928350*** (0.873920) | −4.641457*** (0.930729) | −4.982589*** (0.927218) | −4.726294*** (0.945088) | −4.958683*** (0.904190) |
| Log VIX | 3.901915*** (1.119567) | 3.379419** (1.142695) | 3.393721*** (1.006046) | 3.409246*** (1.046641) | 3.575198*** (1.115119) | 3.505880*** (1.098681) |
| Log global EPU, annual change | 0.079352 (1.179793) | 0.000672 (1.208056) | 0.045192 (1.222780) | −0.004458 (1.166608) | −0.112878 (1.240982) | 0.043333 (1.152230) |
| Financial development, annual change | 10.157086 (12.218032) | 3.772513 (12.281885) | 6.090857 (12.460434) | 5.761382 (11.674087) | 7.473452 (12.915348) | 4.800914 (12.540989) |
| Observations | 273 | 273 | 273 | 273 | 273 | 273 |
| Countries | 14 | 14 | 14 | 14 | 14 | 14 |
| Years | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 |
| Within \(R^2\) | 0.3205 | 0.2937 | 0.2972 | 0.2889 | 0.3056 | 0.2788 |
| \(R^2\) | 0.3532 | 0.3277 | 0.3310 | 0.3231 | 0.3391 | 0.3135 |
