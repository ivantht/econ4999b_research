# Datasets in Beirne and Renzhi (ADB WP 820, November 2025)

Sample: 29 economies, monthly, 2000:M1–2023:M12. Belgium, Brazil, Canada, Chile, China, Colombia, Germany, Denmark, Spain, Finland, France, Hungary, Indonesia, India, Italy, Japan, Korea, Mexico, Malaysia, the Netherlands, the Philippines, Poland, Portugal, Sweden, Thailand, Türkiye, Ukraine, the United States, South Africa.

The paper does not release code or a frozen vintage. Files below are the public sources named in Section II, downloaded on 8 November 2026.

| Variable in the paper | What they say they use | File / series used here |
| --- | --- | --- |
| Geopolitical risk | Country GPR index, Caldara and Iacoviello (2022), standardized by country | `raw/gpr_export.xls`, columns `GPRC_*`. https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls |
| Capital-flow volatility | Standard deviation of portfolio inflows over a 3-month window. OECD Monthly Capital Flow Dataset (de Crescenzio and Lepers) | `raw/oecd_capital_flows.xlsx`, sheet `panel`, column `port_inf` (billion USD). https://www.oecd.org/daf/inv/investment-policy/oecd-monthly-capital-flow-dataset.xlsx |
| Real stock prices | Real stock-price index. OECD MEI, IMF IFS, BIS | OECD MEI `SPASTT01`, measure `IXOB` (2015=100), deflated by the IMF CPI. Missing countries filled with IMF IFS `FPE_IX` |
| 10-year bond yield | Long-term government bond yield | OECD MEI `IRLTLT01`, measure `ST`. Missing countries filled with IMF IFS `FIGB_PA` |
| Real effective exchange rate | REER index | BIS broad real effective exchange rate, `WS_EER` `M.R.B.*`, then logged |
| Policy rate | Central-bank policy rate, IMF IFS and BIS | BIS `WS_CBPOL`. Euro-area members use the BIS euro-area series `XM` |
| Real industrial production | Real industrial production index, logged | IMF IFS `AIP_IX` |
| Inflation | Year-on-year CPI | IMF IFS `PCPI_PC_CP_A_PT` |
| Oil price | WTI, logged | EIA Cushing monthly spot price, `RWTCm` |
| VIX | CBOE VIX. Equation (2) uses the log; Table 1 reports the level | Monthly mean of daily VIX close, `raw/vix_history.csv` |
| Global EPU | Baker, Bloom, and Davis global EPU, logged in equation (2) | `GEPU_current` in `raw/epu_all_country.xlsx` |
| Financial development | IMF Financial Development Index | IMF `FD_FD_IX` (annual, repeated within the year) |
| Central bank independence | Romelli (2022) | Romelli CBIE, June 2025 update, `raw/cbi_2025.xlsx` (the 2022 file ends in 2017) |
| Public debt / GDP | IMF WEO general government gross debt | WEO April 2025, `GGXWDG_NGDP` |

Controls other than GPR are lagged one month. GPR enters contemporaneously and is standardized within country. Regressions are country fixed effects, estimated as the within estimator. That is equation (2) and Tables 2 and 3. The panel SVAR in Figures 2 and 3 is not replicated.

Run `python replication/build_and_replicate.py`. Results are written to `replication/output/`.
