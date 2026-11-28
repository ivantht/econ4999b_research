# Replication of Table 2, Column 1

An audit of whether the paper's positive, significant geopolitical-risk coefficient in the capital-flow-volatility equation can be reproduced from `cleaned/replication_cleaned/country_month.csv`.

The target is Table 2, column 1 of `how GRP affect FX and capital flow.md`: the outcome is capital-flow volatility, the regressor of interest is country-standardized GPR, the control set is the nine variables in equation (2) lagged one month, the estimator is country fixed effects, and standard errors are clustered by country. The paper reports a GPR coefficient of **+0.867 (0.382)**, significant at 5 percent, with N = 4,779 and R-squared = 0.058.

The answer is that **it cannot be reproduced.** The coefficient is negative in every specification that keeps the paper's stated method, and turns positive only in a cell that abandons two parts of it at once.

Program: `output/run_replication_scan.py`. Numbers: `output/replication_scan.csv`. Rendered tables: `output/replication_scan.html`.

## What was held fixed

Equation (2) as written. The outcome is `capital_flow_volatility`. The regressor of interest is GPR standardized by country. The controls are the policy rate, real industrial production, inflation, the oil price, the VIX, the global EPU index, financial development, central bank independence, and public debt to GDP, each lagged one month. Country fixed effects, standard errors clustered by country, two-sided *t* with *G* − 1 degrees of freedom.

Only three choices were varied: how the outcome is built, how GPR is standardized, and whether fixed effects are included.

## The outcome's construction

The panel stores capital-flow volatility as the standard deviation of portfolio inflows over the current and two prior months, requiring three observed months. The series was verified against the raw inflows: the stored column equals the sample standard deviation (denominator *n* − 1) of the three months in 6,481 of 6,481 recomputable cases.

Portfolio inflows are blank in 1,813 of 8,352 rows, and 17 of the 29 countries have at least one gap. The paper's Table 1 reports a minimum of exactly **0**, which no observed inflow series produces. That suggests the paper fills missing inflows with zero before taking the standard deviation.

| Construction | Values | Mean | SD | Min | Max | Est. N | R&sup2; | Within R&sup2; | GPR coefficient |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Three observed months (the stored column) | 6,481 | 8.86 | 21.54 | 0.003 | 412.4 | 4,720 | 0.544 | 0.0949 | −0.467 (0.388) |
| Missing inflow as zero, *n* − 1 | 8,352 | 6.91 | 19.34 | 0.000 | 412.4 | 6,031 | 0.546 | 0.1063 | −0.359 (0.374) |
| Missing inflow as zero, *n* | 8,352 | 5.64 | 15.79 | 0.000 | 336.7 | 6,031 | 0.546 | 0.1063 | −0.293 (0.305) |
| At least two observed months | 6,511 | 8.85 | 21.51 | 0.003 | 412.4 | 4,734 | 0.544 | 0.0945 | −0.461 (0.387) |
| **Paper, Table 2 column 1** | — | **7.22** | **19.62** | **0** | **528.4** | **4,779** | — | **0.058** | **+0.867 (0.382)** |

Zero-filling with denominator *n* − 1 matches the paper's mean most closely (6.91 against 7.22) and its standard deviation (19.34 against 19.62), and it is the only construction that produces a minimum of exactly zero. It is therefore the most plausible reading of the paper's outcome.

That construction does not fix the sign. The GPR coefficient moves from −0.467 to −0.359 and remains insignificant with *p* = 0.347. **The outcome's construction is not the source of the discrepancy.**

## Standardization and fixed effects

The paper says GPR is "standardized by country". Standardizing within country sets each country's mean to exactly zero, so adding country fixed effects on top removes almost nothing further. The four cells below are therefore closer to two distinct estimates than four.

| GPR standardization | Fixed effects | Est. N | R&sup2; | Within R&sup2; | GPR coefficient |
| --- | --- | ---: | ---: | ---: | ---: |
| By country | Yes | 4,720 | 0.544 | 0.0949 | −0.467 (0.388) |
| By country | No | 4,720 | 0.258 | 0.0949 | −0.496 (0.489) |
| Pooled | Yes | 4,720 | 0.551 | 0.1082 | −2.601*** (0.256) |
| Pooled | No | 4,720 | 0.366 | 0.1082 | **+5.938*** (0.650)** |

The only positive cell is the last one: pooled standardization with no fixed effects. That cell sets aside two parts of the stated method at once, and it is the wrong comparison for a further reason. Without fixed effects the coefficient is identified off cross-country differences in GPR levels, which is precisely the variation fixed effects exist to remove.

The paper's +0.867 falls between the two-by-country cells and the pooled-with-fixed-effects cell. No combination of the stated method lands there.

## Window

Narrowing the window is the only remaining lever that changes the sample without changing the specification.

| Window | Est. N | Countries | GPR coefficient |
| --- | ---: | ---: | ---: |
| 2000 to 2023 | 4,720 | 24 | −0.467 (0.388) |
| 2002 to 2023 | 4,508 | 24 | −0.685 (0.553) |
| 2000 to 2021 | 4,700 | 24 | −0.407 (0.319) |
| 2000 to 2019 | 4,155 | 24 | −0.183 (0.195) |

No window reverses the sign, and none reaches the paper's N. The within R-squared stays in a narrow band, from 0.0837 to 0.0958 across the four windows.

## Country coverage

Five emerging economies contribute no observations at all, because their industrial production series is empty in this panel. The paper states its baseline over 29 countries; **this panel supports at most 24.**

| Excluded country | Observations in the sample |
| --- | ---: |
| Indonesia | 0 |
| Philippines | 0 |
| South Africa | 0 |
| Thailand | 0 |
| Ukraine | 0 |

This is a coverage limit of the cleaned panel, not a modelling choice, and no window or construction setting recovers those countries.

## What the audit establishes

Three things, in decreasing order of confidence.

**The outcome's construction is settled.** The stored series is a three-month sample standard deviation of portfolio inflows requiring three observed months, verified on all 6,481 recomputable cells. Zero-filling missing inflows is the reading most consistent with the paper's summary statistics, and the parameterization above makes it explicit.

**The sign discrepancy is real and robust.** The GPR coefficient is negative in 11 of the 12 specifications, from −0.183 to −2.601, and positive only when both pooled standardization and the absence of fixed effects are imposed. It is not an artifact of the outcome, the window, or either modelling choice taken alone.

**The sample cannot be matched.** This panel supports 24 countries against the paper's 29, and no window reproduces N = 4,779. The five missing countries are absent for a data reason, so the gap is not closable by specification choices.

## One correction to earlier working notes

An intermediate result in this audit suggested that a within R-squared of 0.0570 matched the paper's 0.058 and could therefore be used to identify the paper's outcome construction. That inference should be withdrawn. Within R-squared varies smoothly from 0.0837 to 0.1082 across the settings tested here, so a value near 0.058 is not specific to one construction. The mean and standard deviation comparisons above remain informative because they separate the constructions by a wide margin; the R-squared comparison does not.

The overall R-squared of the pooled panel, 0.544, is not comparable to the paper's 0.058 at all. The two are different statistics: 0.544 includes the country means, which explain most of the variance of this outcome.

## Consequence for the Model 2 work

This audit bears directly on `model 2.md`. The GPR level term is insignificant there in both the monthly and quarterly runs, and this audit explains why: on this panel the within-country relationship between GPR and capital-flow volatility is close to zero at any frequency, and no specification that honors the paper's stated method produces a positive coefficient.

That does not undermine the institutional interaction question, which is where the Model 2 contribution lies. It does mean the baseline GPR coefficient in the paper should not be treated as a benchmark that the cleaned panel fails to hit by accident. On this data the baseline cannot be hit at all.
