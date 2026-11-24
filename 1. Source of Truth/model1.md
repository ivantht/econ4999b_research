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
