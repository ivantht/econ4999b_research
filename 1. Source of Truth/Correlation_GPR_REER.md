can you help me calculate the correlation between countries' x and y?

y is defined as d_log_reer	Monthly change in log REER, current month
x is defined as Standardized GPR	gpr_z	The stored column, current month. It is gpr minus the country mean, divided by the country sample standard deviation, using every month in the file 
Sample period:　from January 2000 through December 2023

format of table: 
each row is a country, also indicate whether it is advanced or emering.

Correlation table
Pearson correlation of current-month gpr_z (x) and current-month d_log_reer (y), computed separately for each country.
Sample: January 2000 through December 2023, from cleaned/replication_cleaned/country_month.csv.
d_log_reer is blank in January 2000 because the change needs the previous month, so each correlation uses February 2000 through December 2023 (287 months). gpr_z is present in every month.
A positive correlation means months with higher standardized GPR line up with a rise in the log real effective exchange rate.

Country          Group         Correlation
Belgium          Advanced           -0.050
Canada           Advanced            0.009
Denmark          Advanced           -0.062
Finland          Advanced            0.032
France           Advanced           -0.049
Germany          Advanced           -0.011
Italy            Advanced            0.076
Japan            Advanced           -0.036
Korea            Advanced           -0.012
Netherlands      Advanced            0.020
Portugal         Advanced           -0.007
Spain            Advanced            0.032
Sweden           Advanced           -0.021
United States    Advanced           -0.024

Brazil           Emerging            0.070
Chile            Emerging            0.012
China            Emerging           -0.098
Colombia         Emerging           -0.002
Hungary          Emerging           -0.074
India            Emerging           -0.026
Indonesia        Emerging           -0.029
Malaysia         Emerging            0.086
Mexico           Emerging           -0.045
Philippines      Emerging           -0.053
Poland           Emerging           -0.030
South Africa     Emerging           -0.077
Thailand         Emerging            0.102
Turkiye          Emerging            0.043
Ukraine          Emerging           -0.064

Charts: [output/correlation_gpr_d_log_reer_by_country.html](../output/correlation_gpr_d_log_reer_by_country.html)

Annual correlation table
Pearson correlation of annual x and annual y, computed separately for each country.
For each calendar year, x is the average of the twelve monthly gpr_z values. y is the sum of the twelve monthly d_log_reer values, the change in log REER over that year.
A year is kept only when both series are observed in all twelve months. January 2000 has no d_log_reer, so 2000 is omitted. Each correlation uses 2001 through 2023 (23 years).
A positive correlation means years with a higher average GPR line up with a larger annual rise in log REER.

Country          Group         Correlation
Belgium          Advanced            0.042
Canada           Advanced            0.142
Denmark          Advanced           -0.131
Finland          Advanced            0.152
France           Advanced            0.214
Germany          Advanced            0.103
Italy            Advanced            0.432
Japan            Advanced           -0.073
Korea            Advanced            0.122
Netherlands      Advanced            0.205
Portugal         Advanced            0.123
Spain            Advanced            0.366
Sweden           Advanced           -0.021
United States    Advanced           -0.165

Brazil           Emerging            0.206
Chile            Emerging            0.049
China            Emerging           -0.390
Colombia         Emerging           -0.099
Hungary          Emerging            0.144
India            Emerging           -0.144
Indonesia        Emerging            0.400
Malaysia         Emerging           -0.029
Mexico           Emerging            0.028
Philippines      Emerging           -0.508
Poland           Emerging            0.226
South Africa     Emerging           -0.050
Thailand         Emerging            0.001
Turkiye          Emerging            0.076
Ukraine          Emerging           -0.252

Charts: [output/correlation_gpr_d_log_reer_annual_by_country.html](../output/correlation_gpr_d_log_reer_annual_by_country.html)

Correlation between the annual correlation and average WGI
Across the 29 countries, Pearson correlation between the country's annual correlation and that country's average WGI score.
The annual correlation is the country figure in the annual table above. The WGI average is the mean of the available annual values from January 2000 through December 2023. WGI is blank in 2001, so each average uses 2000 and 2002 through 2023 (23 years).
A positive correlation means countries with a higher average WGI tend to have a higher annual correlation between standardized GPR and the change in log REER.

WGI measure                       Correlation
Voice and accountability                0.431
Political stability                     0.365
Government effectiveness                0.225
Regulatory quality                      0.289
Rule of law                             0.299
Control of corruption                   0.255

Charts: [output/correlation_annual_gpr_reer_and_wgi.html](../output/correlation_annual_gpr_reer_and_wgi.html)

Correlation between the annual correlation and average WGI, emerging economies
Across the 15 emerging economies, Pearson correlation between the country's annual correlation and that country's average WGI score.
The countries are Brazil, Chile, China, Colombia, Hungary, India, Indonesia, Malaysia, Mexico, Philippines, Poland, South Africa, Thailand, Turkiye, Ukraine.
The annual correlation and the WGI average are the same figures used in the table above.
A positive correlation means emerging economies with a higher average WGI tend to have a higher annual correlation between standardized GPR and the change in log REER.

WGI measure                       Correlation
Voice and accountability                0.484
Political stability                     0.407
Government effectiveness                0.260
Regulatory quality                      0.360
Rule of law                             0.381
Control of corruption                   0.331

Charts: [output/correlation_annual_gpr_reer_and_wgi_emerging.html](../output/correlation_annual_gpr_reer_and_wgi_emerging.html)

Explore the correlation with quarterly data:
Compute correlation between quarterly GPR and quarterly change of log_reer, only for emerging economies.
put the correlation table below and plot the time series with x and y on the same plot for each country.
Also compute the correlation between 6 WGI measures with the quarterly correlation rate. put down the correlation table and generate scatter plots.

Quarterly correlation table
Pearson correlation of quarterly x and quarterly y, computed separately for each emerging economy.
For each calendar quarter, x is the average of the three monthly gpr_z values. y is the sum of the three monthly d_log_reer values, the change in log REER over that quarter.
A quarter is kept only when both series are observed in all three months. January 2000 has no d_log_reer, so 2000Q1 is omitted. Each correlation uses 2000Q2 through 2023Q4 (95 quarters).
A positive correlation means quarters with a higher average GPR line up with a larger quarterly rise in log REER.

Country          Group         Correlation
Brazil           Emerging            0.205
Chile            Emerging           -0.098
China            Emerging           -0.171
Colombia         Emerging            0.009
Hungary          Emerging           -0.042
India            Emerging           -0.040
Indonesia        Emerging            0.107
Malaysia         Emerging            0.089
Mexico           Emerging           -0.044
Philippines      Emerging           -0.230
Poland           Emerging            0.024
South Africa     Emerging           -0.103
Thailand         Emerging            0.073
Turkiye          Emerging            0.088
Ukraine          Emerging           -0.089

Charts: [output/correlation_gpr_d_log_reer_quarterly_emerging.html](../output/correlation_gpr_d_log_reer_quarterly_emerging.html)

Correlation between the quarterly correlation and average WGI, emerging economies
Across the 15 emerging economies, Pearson correlation between the country's quarterly correlation and that country's average WGI score.
The countries are Brazil, Chile, China, Colombia, Hungary, India, Indonesia, Malaysia, Mexico, Philippines, Poland, South Africa, Thailand, Turkiye, Ukraine.
The quarterly correlation is the country figure in the quarterly table above. The WGI average is the mean of the available annual values from January 2000 through December 2023. WGI is blank in 2001, so each average uses 2000 and 2002 through 2023 (23 years).
A positive correlation means emerging economies with a higher average WGI tend to have a higher quarterly correlation between standardized GPR and the change in log REER.

WGI measure                       Correlation
Voice and accountability                0.109
Political stability                     0.061
Government effectiveness               -0.006
Regulatory quality                      0.006
Rule of law                             0.051
Control of corruption                   0.027

Charts: [output/correlation_quarterly_gpr_reer_and_wgi_emerging.html](../output/correlation_quarterly_gpr_reer_and_wgi_emerging.html)

Explore quaterly correlation with GPR(t) and d_log_reer(t+1)

Quarterly lead correlation table
Pearson correlation of quarterly GPR(t) and quarterly d_log_reer(t+1), computed separately for each emerging economy.
For quarter t, x is the average of the three monthly gpr_z values. y is the sum of the three monthly d_log_reer values in quarter t+1, the change in log REER over the next quarter.
A pair is kept only when quarter t has standardized GPR in all three months and quarter t+1 has the log-REER change in all three months. 2023Q4 has no following quarter, so each correlation uses GPR from 2000Q1 through 2023Q3 and the log-REER change from 2000Q2 through 2023Q4 (95 quarters).
A positive correlation means a quarter with higher average GPR lines up with a larger rise in log REER in the next quarter.

Country          Group         Correlation
Brazil           Emerging            0.089
Chile            Emerging           -0.050
China            Emerging           -0.284
Colombia         Emerging           -0.125
Hungary          Emerging            0.004
India            Emerging           -0.094
Indonesia        Emerging            0.084
Malaysia         Emerging           -0.102
Mexico           Emerging            0.112
Philippines      Emerging           -0.304
Poland           Emerging            0.106
South Africa     Emerging            0.031
Thailand         Emerging            0.072
Turkiye          Emerging            0.127
Ukraine          Emerging           -0.084

Charts: [output/correlation_gpr_t_d_log_reer_t1_quarterly_emerging.html](../output/correlation_gpr_t_d_log_reer_t1_quarterly_emerging.html)

Correlation between the quarterly lead correlation and average WGI, emerging economies
Across the 15 emerging economies, Pearson correlation between the country's quarterly lead correlation and that country's average WGI score.
The countries are Brazil, Chile, China, Colombia, Hungary, India, Indonesia, Malaysia, Mexico, Philippines, Poland, South Africa, Thailand, Turkiye, Ukraine.
The quarterly lead correlation is the country figure in the quarterly lead table above. The WGI average is the mean of the available annual values from January 2000 through December 2023. WGI is blank in 2001, so each average uses 2000 and 2002 through 2023 (23 years).
A positive correlation means emerging economies with a higher average WGI tend to have a higher correlation between standardized GPR and the next quarter's change in log REER.

WGI measure                       Correlation
Voice and accountability                0.434
Political stability                     0.252
Government effectiveness                0.082
Regulatory quality                      0.220
Rule of law                             0.216
Control of corruption                   0.168

Charts: [output/correlation_quarterly_lead_gpr_reer_and_wgi_emerging.html](../output/correlation_quarterly_lead_gpr_reer_and_wgi_emerging.html)


