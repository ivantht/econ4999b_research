---
name: 3nf-data-cleaning
description: >-
  Clean macro series into third-normal-form (3NF) tables: one country
  entity and separate fact tables for exports, the FX rate, imports, GDP,
  inflation, debt/GDP, WGI, and capital flows. Use when the user asks to
  clean, normalize, or rebuild export, FX, import, or other country-panel
  series, or when writing files under cleaned/.
---

# 3NF data cleaning

Cleaning removes redundancy. It does not answer a research question. Leave `input/` unchanged. Write only normalized tables to `cleaned/`. Totals, FX-adjusted trade, joins across series, and regressions belong in a later analysis stage.

Each fact table stores one measure. Its key is only what that measure depends on. Do not copy a column onto a row when that column depends on a different key.

## Country

One shared entity, one row per country:

Chile, Indonesia, Malaysia, Peru, Philippines, South Africa, Thailand.

`country` columns: `country`. Later attributes, such as an ISO code, stay on this table. Do not repeat them on fact rows.

## Fact tables

Different time grains stay in different tables.

- `exports`: `country`, `year_month`, `category`, `value`. Categories: `food_agri`, `crude_ores`, `chemicals`, `fuels`, `machinery_transport`, `other_manuf_residual`. Key: country + month + category.
- `fx_rate`: `country`, `year_month`, `local_per_usd`. The rate depends on country and month. Do not copy it onto export or import rows.
- `imports`: `country`, `year_month`, `category`, `value`. Category: `oil_fuels`.
- GDP and inflation: `country`, `year_month`, `value`.
- Debt/GDP: `country`, `period`, `frequency`, `debt_gdp_pct`, `source`.
- WGI: `country`, `year`, `dimension`, `estimate`.
- Capital flow: `country`, `year`, `accounting_entry`, `usd_millions`.

Keep category as part of the trade key. Do not spread categories into separate columns. These category codes have no extra attributes, so do not add a category lookup table.

Do not put `local_per_usd`, GDP, inflation, or WGI on an export or import row.

## Checks

- One row per key.
- `input/` is unchanged.
- `cleaned/` contains only normalized tables, not summaries or cross-series joins.
- A blank source cell stays blank. Do not write zero.
