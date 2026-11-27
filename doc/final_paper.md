---
title: "Can Institutions Buffer for Emerging Market Exchange Rates Movement under Geopolitical Shocks?"
author:
  - "Chun Wai Tsui"
  - "Hiu Tong Tsoi"
  - "Wing Sum Chan"
date: "November 2026"
date-format: "MMMM YYYY"
abstract: |
  [Summarize the research question, methods, preliminary findings, and limitations.]
format:
  html:
    css: final_paper.css
    number-sections: true
    toc: false
    format-links: false
  pdf:
    documentclass: article
    fontsize: 10pt
    papersize: letter
    geometry: margin=1.2in
    number-sections: true
    tbl-cap-location: top
    fig-cap-location: bottom
    include-in-header:
      text: |
        \renewcommand{\and}{\\}
---

# Introduction

## Situation

Geopolitical risk encompasses threats or events involving armed conflict, terrorism, and tensions between states. This paper examines whether institutional quality changes the association between geopolitical risk and the real effective exchange rate (REER), and whether exports or capital-flow volatility may be relevant transmission channels.

[Introduce the setting and explain why exchange rates and institutions matter for emerging markets.]

## Complication

The presentation motivates the question with the experiences of Kazakhstan and Georgia following the Russia-Ukraine war. This comparison is illustrative and does not by itself establish the effect of institutional quality.

[Explain the uncertainty or research gap that makes the question important.]

## Question

[State the central research question and identify the proposed export and capital-flow-volatility channels.]

## Answer

[Summarize the models, the verified findings for each channel, the contribution, and the paper's structure.]

# Literature Review and Hypotheses

## Related Literature

The presentation identifies the country-specific geopolitical risk index of Caldara and Iacoviello (2022) as the measure of geopolitical risk and the Worldwide Governance Indicators (WGI) as a proxy for institutional quality.

[Review the relevant literature on geopolitical risk, institutions, exchange rates, exports, and capital flows. Verify and add citations.]

## Hypotheses

[Develop testable hypotheses for institutional buffering and each proposed channel, explaining their theoretical basis and expected signs.]

# Statistics

## Stylized Facts

[Present descriptive statistics, patterns, tables, and figures for the key variables and samples. Identify their sources and periods.]

## Variable Interpretation and Relevance

[Explain what each key variable measures, including whether an increase in REER represents appreciation under the data source's convention. Briefly connect the observed patterns to the findings without implying causality.]

: Description of variables {#tbl-variables}

| Variable          | Description                                                        |
|:------------------|:-------------------------------------------------------------------|
| $GPR_{i,t}^{z}$   | Country-standardized geopolitical risk.                            |
| $WGI_{i,t-1}$     | Lagged governance indicator.                                       |
| $y_{i,t}^{j}$     | Log REER or capital-flow volatility, depending on the specification. |

# Data and Methodology

## Data

The presentation uses the real effective exchange rate, country-specific geopolitical risk, and WGI measures. It also examines export measures and capital-flow volatility. Its reported samples differ across specifications; for example, the full-sample exchange-rate model is described as covering 27 countries, while one export specification covers five.

[Document data sources, definitions, transformations, sample periods, country coverage, and missing observations for each specification.]

## Methodology

The presentation's emerging-economy subsample specification relates the outcome to standardized geopolitical risk, lagged institutional quality, their interaction, lagged controls, and country fixed effects:

$$
\begin{aligned}
y_{i,t}^{j}
  ={}& \beta_1 GPR_{i,t}^{z} + \beta_2 WGI_{i,t-1} \\
     &+ \beta_3(WGI_{i,t-1} \times GPR_{i,t}^{z})
     + \gamma'X_{i,t-1} + \delta_i + \varepsilon_{i,t}.
\end{aligned}
$$ {#eq-subsample}

Here, $y_{i,t}^{j}$ is either capital-flow volatility or the log REER, $GPR_{i,t}^{z}$ is standardized within country over the months used in the regression, $WGI_{i,t-1}$ is the lagged, uncentered governance score, $X_{i,t-1}$ denotes lagged controls, and $\delta_i$ denotes country fixed effects. The interaction coefficient describes how the GPR association changes with a one-point increase in WGI; the GPR coefficient is the association at a WGI score of zero.

The presentation also describes nominal- and real-export specifications in which fitted export measures enter a real-exchange-rate equation, as well as a capital-flow-volatility specification. Figure 1 summarizes these proposed channels; it is not evidence that the channels are causal.

```{=latex}
\begin{figure}[htbp]
  \centering
  \fbox{\parbox[c][0.55in][c]{0.25\textwidth}{\centering
    Geopolitical risk\\and institutional quality}}
  \quad$\longrightarrow$\quad
  \fbox{\parbox[c][0.55in][c]{0.23\textwidth}{\centering
    Export measures}}
  \quad$\longrightarrow$\quad
  \fbox{\parbox[c][0.55in][c]{0.23\textwidth}{\centering
    Real effective\\exchange rate}}

  \vspace{0.2in}
  \fbox{\parbox[c][0.55in][c]{0.32\textwidth}{\centering
    Geopolitical risk\\and institutional quality}}
  \quad$\longrightarrow$\quad
  \fbox{\parbox[c][0.55in][c]{0.32\textwidth}{\centering
    Capital-flow volatility}}
  \caption{Proposed relationships and transmission channels}
  \label{fig:channels}
\end{figure}
```

```{=html}
<figure class="channels-figure">
  <div class="channel-row">
    <div class="channel-box"><span>Geopolitical risk<br>and institutional quality</span></div>
    <span class="channel-arrow" aria-hidden="true">&rarr;</span>
    <div class="channel-box">Export measures</div>
    <span class="channel-arrow" aria-hidden="true">&rarr;</span>
    <div class="channel-box"><span>Real effective<br>exchange rate</span></div>
  </div>
  <div class="channel-row">
    <div class="channel-box"><span>Geopolitical risk<br>and institutional quality</span></div>
    <span class="channel-arrow" aria-hidden="true">&rarr;</span>
    <div class="channel-box">Capital-flow volatility</div>
  </div>
  <figcaption>Figure 1: Proposed relationships and transmission channels</figcaption>
</figure>
```

[Specify each model, its controls, estimation method, standard errors, and identification limitations. Verify the proposed channel interpretation.]

# Findings

## Channel 1: Exchange Rate and Exports

**Significant result overview.** [Summarize verified significant results first, or state clearly if none are found.]

The presentation reports that, in the full-sample exchange-rate model, the GPR coefficient at average WGI is approximately zero and the interaction does not provide evidence of a general buffering effect. It also reports associations between WGI and export measures. These results are preliminary and should not be interpreted as causal without further supporting analysis.

**Theoretical explanation.** [Explain how institutional quality and geopolitical shocks could affect the real exchange rate directly or through exports.]

**Empirical model.** [Identify each outcome, explanatory variables, interactions, controls, sample, and estimation method used to test the relationship.]

**Result analysis.** [Report and interpret verified coefficients, uncertainty, significance, and limitations; distinguish associations from causal effects.]

**Connection to the main topic.** [Explain what the results imply for institutional buffering of emerging-market exchange rates.]

## Channel 2: Capital-flow Volatility

**Significant result overview.** [Summarize verified significant results first, or state clearly if none are found.]

The presentation reports mixed country patterns for capital-flow volatility. These results are preliminary and require verification.

**Theoretical explanation.** [Explain why institutions and geopolitical shocks may be related to capital-flow volatility and exchange-rate stability.]

**Empirical model.** [Identify the outcome, explanatory variables, interactions, controls, sample, and estimation method used to test the relationship.]

**Result analysis.** [Report and interpret verified coefficients, uncertainty, significance, and limitations; distinguish associations from causal effects.]

**Connection to the main topic.** [Explain how the evidence relates to institutional buffering of emerging-market exchange rates.]

## Subsample Checks

The presentation ranks ten emerging economies by their 2000--2021 average score for each WGI dimension and compares the top and bottom three. It then removes China, reranks the remaining nine, and re-estimates the groups. The presentation reports that the exchange-rate interactions vary across governance dimensions and that most volatility interactions in the ten-country comparison are not statistically significant.

[Verify estimates, sample sizes, standard errors, significance levels, and robustness checks against the underlying results before reporting them. The presentation contains inconsistent significance labels for the real-export rule-of-law estimate.]

# Conclusion

[Restate the research problem and question, the hypotheses and proposed channels, the data and methods, and the verified findings for both channels. Conclude with implications, limitations, and directions for future research, including sample differences and uncertainty around the proposed channels.]

# References {.unnumbered}

1. Caldara, D., & Iacoviello, M. (2022). [Complete and verify reference details.]
2. [Add the WGI source and other cited literature using a consistent reference style.]

# Appendices {.unnumbered}

[Include supplementary material if needed.]
