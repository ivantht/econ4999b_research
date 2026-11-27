help me plot a time series graph of 

1) capital_flow for each emerging economies in C:\Users\ASUS\econ4999b_research\cleaned\capital_flow.csv

[emerging_capital_flow.html](../output/emerging_capital_flow.html)

2) capital_flow_volaitility for each emerging ecnoomies in C:\Users\ASUS\econ4999b_research\cleaned\replication_cleaned\country_month.csv

[emerging_capital_flow_volatility.html](../output/emerging_capital_flow_volatility.html)

3) profolio_inflow for each emerging economies in C:\Users\ASUS\econ4999b_research\cleaned\replication_cleaned\country_month.csv

[emerging_portfolio_inflow.html](../output/emerging_portfolio_inflow.html)

run model 1 annual regression in C:\Users\ASUS\econ4999b_research\1. Source of Truth\model1.md but replacing the LHS by

1) capital_flow for each emerging economies in C:\Users\ASUS\econ4999b_research\cleaned\capital_flow.csv
2) profolio_inflow for each emerging economies in C:\Users\ASUS\econ4999b_research\cleaned\replication_cleaned\country_month.csv

## Formula and data

This is the annual emerging regression in `model1.md` ("Annual estimates, emerging economies"). The right-hand side, country fixed effects, and country-clustered standard errors stay. The outcome is that year's mean. It replaces the change in mean log REER. The regression is `output/run_model1_annual_capital_flow.py`. It reproduces the published voice-and-accountability REER column before the outcome is replaced.

\[
\bar y_{it}
= \alpha_i
+ \beta_1 \overline{GPR}^{z}_{it}
+ \beta_2 WGI_{it}
+ \beta_3 \bigl(WGI_{it} \times \overline{GPR}^{z}_{it}\bigr)
+ \boldsymbol{\gamma}^{\mathsf T}\mathbf{X}_{it}
+ \varepsilon_{it}
\]

\(i\) is the country and \(t\) is the calendar year. \(\bar y_{it}\) is the mean of the outcome in year \(t\). \(\alpha_i\) is a country fixed effect. One regression uses one WGI score. The six scores are voice and accountability, political stability, government effectiveness, regulatory quality, rule of law, and control of corruption. The six scores are blank in the same months, so the six regressions use the same country-years. The interaction is that year's WGI score times that year's mean `gpr_z`. The product is not centered.

\(\overline{GPR}^{z}_{it}\) is the mean of the twelve monthly `gpr_z` values. Log VIX is the mean of the twelve monthly logs of `vix`. Each other control is the twelve-month mean in year \(t\) minus the twelve-month mean in year \(t-1\). Financial development and debt/GDP are annual levels repeated within the year, so their means are those annual levels. A control year stays in only when year \(t\) and year \(t-1\) are consecutive and every required control month is observed. The outcome needs only its own observations in year \(t\). The window is 2002–2021. Standard errors are clustered by country, with the sandwich factor and \(t_{G-1}\) \(p\)-values in `model1.md`.

| Role | Column | File | Timing |
| --- | --- | --- | --- |
| GPR, standardized | `gpr_z` | `cleaned/replication_cleaned/country_month.csv` | Mean of the twelve months in year \(t\) |
| WGI | `wgi_va`, `wgi_pv`, `wgi_ge`, `wgi_rq`, `wgi_rl`, or `wgi_cc` | same file | That year's score |
| WGI × GPR | WGI × mean `gpr_z` | same file | Both from year \(t\) |
| Policy rate | `policy_rate` | same file | Change in the twelve-month mean |
| Inflation | `inflation` | same file | Change in the twelve-month mean |
| Log oil price | `oil_price` | same file | Change in the twelve-month mean of the monthly log |
| Log VIX | `vix` | same file | Mean of the twelve monthly logs, year \(t\) |
| Log global EPU | `gepu` | same file | Change in the twelve-month mean of the monthly log |
| Financial development | `financial_development` | same file | This year's level minus last year's level |
| Debt/GDP | `public_debt_gdp` | same file | This year's level minus last year's level |

The right-hand side is complete for 273 country-years and 14 emerging economies: Brazil, Chile, China, Colombia, Hungary, India, Indonesia, Malaysia, Mexico, Philippines, Poland, South Africa, Thailand, and Turkiye. Indonesia is 2007–2021 and Turkiye is 2004–2021. Ukraine has no policy rate, so it stays out.

### 1. Capital flow

\[
\bar y_{it}=\overline{\text{capital flow}}_{it}
\]

The outcome is the mean of the four quarterly `usd_millions` values in year \(t\), in million US dollars. The file is `cleaned/capital_flow.csv`. Turkey is Turkiye. A year stays in when all four quarters of that year are observed.

Joined to the complete right-hand side, this is 173 country-years and 9 economies: Chile, Hungary, India, Indonesia, Mexico, Philippines, South Africa, Thailand, and Turkiye. Indonesia is 2007–2021 and Turkiye is 2004–2021. Brazil, China, Colombia, Malaysia, and Poland have no capital-flow row. Argentina, Egypt, Peru, South Korea, Tunisia, Ukraine, and Vietnam are in the capital-flow file and do not meet the emerging right-hand side.

173 country-years, 9 emerging economies, 2002–2021. Parentheses are country-clustered standard errors. \(p<0.01\), \(p<0.05\), \(p<0.10\). A coefficient is in million US dollars of that year's mean quarterly flow. Results are `output/model1_annual_emerging_capital_flow_results.csv`.

|  | Voice and accountability | Political stability | Government effectiveness | Regulatory quality | Rule of law | Control of corruption |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| WGI | −3347.326951 (2458.707233) | −1785.972179 (1844.872651) | −9688.263026*** (2795.929876) | −3928.131569 (2862.649953) | −1984.391212 (2612.477115) | −4832.585786 (3274.338513) |
| GPR, standardized | 1607.626642 (906.758393) | 2084.382883*** (418.757497) | 908.882210 (975.652866) | 2103.547221 (1424.367924) | 1861.818081* (936.155164) | 1693.752900* (757.676516) |
| WGI × GPR | 944.139907 (1957.526152) | 374.546656 (885.780400) | 1009.594146 (1634.821888) | −824.013734 (1823.579588) | 303.068071 (788.202867) | −143.194594 (936.106195) |
| Policy rate, annual change | −209.970158 (128.169047) | −191.251012 (199.853703) | −73.724249 (185.833695) | −138.521548 (216.385133) | −201.320676 (154.149144) | −185.212870 (204.752678) |
| Inflation, annual change | −16.915312 (151.370138) | 12.929848 (133.554498) | 12.720095 (142.864772) | −3.238294 (146.546076) | 10.201480 (148.419488) | 18.652919 (146.509993) |
| Log oil price, annual change | −2006.867001** (782.278529) | −2171.793945** (888.270417) | −3272.418656*** (962.518863) | −2069.297896** (875.961861) | −2019.180681* (917.295660) | −1825.197397* (870.442492) |
| Log VIX | 811.179610 (1226.027742) | 522.972534 (1235.035593) | −471.188021 (875.594884) | 695.886143 (1227.445034) | 464.832030 (1177.041961) | 755.037452 (1146.563102) |
| Log global EPU, annual change | −254.874790 (740.799866) | −392.409647 (821.739309) | 294.429186 (917.037969) | −375.622887 (845.296734) | −165.090422 (741.476547) | −104.825687 (795.636022) |
| Financial development, annual change | −1299.955487 (14523.019722) | −3419.718460 (18270.790097) | −2504.650895 (16542.408894) | 588.419465 (17609.191227) | −3505.922891 (16160.794023) | −386.375377 (17031.292617) |
| Debt/GDP, annual change | −50.199195 (92.974595) | −9.338087 (125.497605) | 40.631614 (144.787438) | −26.054172 (117.964687) | −23.883180 (102.090440) | −12.971805 (117.112096) |
| Observations | 173 | 173 | 173 | 173 | 173 | 173 |
| Countries | 9 | 9 | 9 | 9 | 9 | 9 |
| Years | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 |
| Within \(R^2\) | 0.1334 | 0.1053 | 0.2808 | 0.1289 | 0.0998 | 0.1260 |
| \(R^2\) | 0.6334 | 0.6216 | 0.6958 | 0.6316 | 0.6192 | 0.6303 |

can you help me calculate the correlation between countries' x and y?

y is defined as capital_flow, annual, in C:\Users\ASUS\econ4999b_research\cleaned\capital_flow.csv

x is defined as Standardized GPR, gpr_z, annual, in C:\Users\ASUS\econ4999b_research\cleaned\replication_cleaned\country_month.csv

Sample period:　2002–2021

format of table: 
each row is a country, do it for 14 emerging economies: Brazil, Chile, China, Colombia, Hungary, India, Indonesia, Malaysia, Mexico, Philippines, Poland, South Africa, Thailand, and Turkiye.

Correlation table
Pearson correlation of annual gpr_z (x) and annual capital flow (y), computed separately for each country.
For each calendar year, x is the average of the twelve monthly `gpr_z` values in `cleaned/replication_cleaned/country_month.csv`. y is the average of the four quarterly `usd_millions` values in `cleaned/capital_flow.csv`. Turkey in that file is Turkiye.
A year is kept only when x is observed in all twelve months and y is observed in all four quarters. Each available correlation uses 2002 through 2021 (20 years).
A positive correlation means years with a higher average GPR line up with a higher average quarterly capital flow.
Brazil, China, Colombia, Malaysia, and Poland have no capital-flow row, so their correlation is blank.

Country          Correlation    Years
Brazil                  —           0
Chile               0.347          20
China                   —           0
Colombia                —           0
Hungary             0.540          20
India               0.530          20
Indonesia           0.614          20
Malaysia                —           0
Mexico              0.264          20
Philippines         0.176          20
Poland                  —           0
South Africa        0.196          20
Thailand           -0.657          20
Turkiye             0.214          20


help me calculate correlation between the countries' annual correlation between gpr and capital inflow, and average WGI
Across the 14 emerging economies.
also plot the corresponind scatter plot for me.

Correlation between the annual GPR–capital-flow correlation and average WGI
Across the nine emerging economies that have a capital-flow series. Pearson correlation between the country's annual correlation and that country's average WGI score.
The annual correlation is the country figure in the table above. The WGI average is the mean of the available annual values from January 2000 through December 2023. WGI is blank in 2001, so each average uses 2000 and 2002 through 2023 (23 years).
Brazil, China, Colombia, Malaysia, and Poland have no capital-flow row, so they are not in this correlation.
A positive correlation means economies with a higher average WGI tend to have a higher annual correlation between standardized GPR and capital flow.

WGI measure                       Correlation
Voice and accountability                0.524
Political stability                     0.265
Government effectiveness                0.114
Regulatory quality                      0.058
Rule of law                             0.172
Control of corruption                   0.124

Charts: [output/correlation_annual_gpr_capital_flow_and_wgi_emerging.html](../output/correlation_annual_gpr_capital_flow_and_wgi_emerging.html)

### 2. Portfolio inflow

\[
\bar y_{it}=\overline{\text{portfolio inflow}}_{it}
\]

The outcome is the mean of the twelve monthly `portfolio_inflow` values in year \(t\), in billion US dollars. The column is in `cleaned/replication_cleaned/country_month.csv`. A year stays in when all twelve months of that year are observed.

Joined to the complete right-hand side, this is 212 country-years and the same 14 economies. The shorter spans are Chile 2003–2021, China 2014–2021, Colombia 2015–2021, Hungary 2008–2021, Indonesia 2011–2021, Malaysia 2012–2021, Mexico 2009–2021, Philippines 2005–2021, Poland 2004–2021, and Thailand 2005–2021. Brazil, India, and South Africa are 2002–2021. Turkiye remains 2004–2021.

212 country-years, 14 emerging economies, 2002–2021. Parentheses are country-clustered standard errors. \(p<0.01\), \(p<0.05\), \(p<0.10\). A coefficient is in billion US dollars of that year's mean monthly inflow. Results are `output/model1_annual_emerging_portfolio_inflow_results.csv`.

|  | Voice and accountability | Political stability | Government effectiveness | Regulatory quality | Rule of law | Control of corruption |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| WGI | 0.934876 (0.874832) | 1.226822 (0.855889) | 1.923105 (1.118081) | 1.725260 (1.030246) | 2.598045* (1.411635) | 2.539607* (1.392159) |
| GPR, standardized | 0.619373 (0.523082) | 0.397482 (0.854314) | 0.133355 (0.454592) | 0.694941 (1.022871) | 0.462183 (0.691834) | 0.432294 (0.719731) |
| WGI × GPR | −2.427059* (1.269293) | −0.151867 (0.376015) | 0.690866 (1.109308) | −0.916175 (0.980759) | −1.174755 (1.008202) | 0.063206 (0.430781) |
| Policy rate, annual change | 0.053779 (0.048560) | 0.067564 (0.050326) | 0.062216 (0.057768) | 0.035734 (0.051976) | 0.075647* (0.041155) | 0.063800 (0.054694) |
| Inflation, annual change | −0.027537 (0.053114) | −0.047751 (0.048355) | −0.055844 (0.056936) | −0.032972 (0.047583) | −0.021311 (0.039785) | −0.050058 (0.052639) |
| Log oil price, annual change | 0.059050 (0.326338) | 0.197407 (0.441967) | 0.415696 (0.522862) | 0.144308 (0.398613) | 0.053016 (0.355709) | 0.199574 (0.447870) |
| Log VIX | 0.889952 (0.854225) | 0.517403 (0.580455) | 0.685866 (0.673051) | 0.424776 (0.659471) | 0.623299 (0.733402) | 0.286102 (0.557598) |
| Log global EPU, annual change | −1.291865** (0.547734) | −0.881117** (0.356134) | −0.887719* (0.417993) | −0.986116** (0.411313) | −1.414808** (0.611422) | −0.959567** (0.364814) |
| Financial development, annual change | 4.544375 (5.757638) | −0.544923 (4.108520) | 0.965310 (5.759646) | −0.022468 (3.812684) | 1.084183 (4.031983) | 0.763774 (4.855253) |
| Debt/GDP, annual change | −0.032081 (0.029057) | −0.002861 (0.047739) | −0.006713 (0.045339) | −0.002528 (0.036668) | 0.014201 (0.048315) | 0.008666 (0.046336) |
| Observations | 212 | 212 | 212 | 212 | 212 | 212 |
| Countries | 14 | 14 | 14 | 14 | 14 | 14 |
| Years | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 | 2002 to 2021 |
| Within \(R^2\) | 0.2437 | 0.0545 | 0.0655 | 0.0708 | 0.1032 | 0.0768 |
| \(R^2\) | 0.6558 | 0.5696 | 0.5746 | 0.5771 | 0.5918 | 0.5798 |

Correlation table
Pearson correlation of annual gpr_z (x) and annual portfolio inflow (y), computed separately for each country.
For each calendar year, x is the average of the twelve monthly `gpr_z` values. y is the average of the twelve monthly `portfolio_inflow` values. Both columns are in `cleaned/replication_cleaned/country_month.csv`.
A year is kept only when both series are observed in all twelve months. The window is 2002 through 2021. The Years column is the number of those years. Brazil, India, South Africa, and Turkiye use all 20 years. The shorter spans are Chile 2003–2021, China 2014–2021, Colombia 2015–2021, Hungary 2008–2021, Indonesia 2011–2021, Malaysia 2012–2021, Mexico 2009–2021, Philippines 2005–2021, Poland 2004–2021, and Thailand 2005–2021.
A positive correlation means years with a higher average GPR line up with a higher average monthly portfolio inflow.

Country          Correlation    Years
Brazil             -0.107          20
Chile              -0.287          19
China               0.716           8
Colombia           -0.620           7
Hungary            -0.583          14
India              -0.242          20
Indonesia           0.477          11
Malaysia           -0.401          10
Mexico             -0.226          13
Philippines        -0.236          17
Poland             -0.462          18
South Africa       -0.021          20
Thailand            0.274          17
Turkiye             0.084          20

Correlation between the annual GPR–portfolio-inflow correlation and average WGI
Across the 14 emerging economies. Pearson correlation between the country's annual correlation and that country's average WGI score.
The annual correlation is the country figure in the table above. The WGI average is the mean of the available annual values from January 2000 through December 2023. WGI is blank in 2001, so each average uses 2000 and 2002 through 2023 (23 years).
A positive correlation means economies with a higher average WGI tend to have a higher annual correlation between standardized GPR and portfolio inflow.

WGI measure                       Correlation
Voice and accountability               -0.633
Political stability                    -0.321
Government effectiveness               -0.401
Regulatory quality                     -0.546
Rule of law                            -0.478
Control of corruption                  -0.416

Charts: [output/correlation_annual_gpr_portfolio_inflow_and_wgi_emerging.html](../output/correlation_annual_gpr_portfolio_inflow_and_wgi_emerging.html)


