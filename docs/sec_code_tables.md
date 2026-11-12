# SEC Reg AB II CMBS asset data (Form ABS-EE, EX-102): official code tables and field definitions

Namespace: `http://www.sec.gov/edgar/document/absee/cmbs/assetdata`. Researched 2026-11-12. Every code list below is copied from the SEC's own XSD, and every one was checked against the SEC PDF spec. Nothing here was written from memory. Anything taken from CREFC is labeled **[SECONDARY: CREFC]**.

---

## 0. Sources

### Primary (SEC / CFR)

| Tag | Document | Where | What it gives |
|---|---|---|---|
| **[XSD]** | `eis_ABS_CMBSAssetData.xsd` inside the EDGAR ABS XML Technical Specification **v3.1** | Zip: https://www.sec.gov/files/absxml-31.zip, linked from https://www.sec.gov/submit-filings/technical-specifications (ABS, Version 3.1, dated Sept 18, 2023, EDGAR Release 23.3) | Every element name, its type, and an `<!-- Item 2(x)(n) - definition -->` comment above it. Every code type has `xs:enumeration` values plus a `<xs:documentation>` string of "code: meaning". This is what EDGAR validates against. PDF sec. 2 says the schema files define the "valid values," and sec. 3 says "These rules are enforced by the schema files and by EDGAR processing sub-systems." Sec. 3.2 says a schema violation "will cause the ABS-EE submission to be suspended." |
| **[SPEC-PDF]** | `EDGAR ABS XML Technical Specification.pdf`, same zip (footer dated March 2025) | Sec. 3.2 Data Type Constraints (p. 3-1); Sec. 3.4.3 Mapping of ABS CMBS Schema to Asset Data Types (pp. 3-8 onward); Sec. 4.3 Data Value Constraints for CMBS, 4.3.1 to 4.3.25 (pp. 4-9 to 4-18); Sec. 5.4 Unique Constraints for Repeatable Code Elements (p. 5-2) | The same code tables in prose form. Each code table in the XSD matches its PDF 4.3.x table. (`pdftotext -layout` scrambles a few tables, so I re-extracted them with `-raw` to check.) Every Item number shown in the PDF 3.4.3 table also matches the XSD element comment. |
| **[CFR]** | 17 CFR 229.1125, Appendix (Schedule AL), **Item 2. Commercial mortgages** | https://www.ecfr.gov/current/title-17/chapter-II/part-229/subpart-229.1100/section-229.1125 (fetched through the eCFR renderer API `https://www.ecfr.gov/api/renderer/v1/content/enhanced/current/title-17?part=229&section=229.1125`). Source notes: 79 FR 57316 (Sept 24, 2014), amended 81 FR 40512 (June 22, 2016) | The legal field titles and definitions. **It has no code lists.** The rule says "Provide the code that..." and the codes live only in the technical spec. The PDF says the same thing at sec. 3.4: "Schedule AL contains the complete title and description... filers should refer to Schedule AL." |
| **[HIST]** | Older versions of the same spec | absxml-1.4.zip (11/04/2016), absxml-1.5.zip (Dec 12, 2016, EDGAR 16.4), 1.6, 1.7, absxml-1.8.zip (03/11/2019), absxml-2.0.zip (09/20/2021), absxml-30.zip (Dec 19, 2022, EDGAR 22.4). All are under https://www.sec.gov/info/edgar/specifications/ except v3.0, which is at https://www.sec.gov/files/edgar/filer-information/specifications/absxml-30.zip | Used to see how the code lists changed over time (section 9). |
| **[REL]** | Reg AB II adopting release, Release No. 33-9638 | https://www.sec.gov/rules/final/2014/33-9638.pdf | Checked only for unit or format guidance. Footnote 247 (p. 101) records a commenter asking whether numbers should be "displayed as an integer or as a decimal". The release doesn't answer it in the rule. It does say the CMBS data points were "primarily based on the data template included in the CREFC Investor Reporting Package". |
| **[CFI]** | SEC Corp Fin Interpretations, Asset-Backed Securities | https://www.sec.gov/rules-regulations/staff-guidance/corporation-finance-interpretations-cfis/asset-backed-securities | The only Item 1125 interpretation is 325.01 (materiality of data errors, Mar 23, 2026). Nothing on codes or units. |

### Secondary (cross-check only)

| Tag | Document | Where |
|---|---|---|
| **[CREFC]** | CREFC Investor Reporting Package **v8.4**, published March 13, 2024 | https://www.crefc.org/common/Uploaded%20files/CREFC%20IRP%20v8.4_Final.pdf . Page numbers below are PDF page indexes: Overview note on percent formatting (p. 9); Delinquent Loan Status Report overview (p. 10); IRP Legend code tables (p. 24); Data Dictionary Schedule AL mapping notes (pp. 27 to 39); "Schedule AL File, Data Record Layout/Translate Table" (pp. 60 to 63); Delinquent Loan Status Report template notes (p. 68). |

---

## 1. Short answers

- **`paymentStatusLoanCode`** (Item 2(e)(17)): `0` Current, `1` 30-59 days delinquent, `2` 60-89, `3` 90+, `4` **Performing matured balloon**, `5` **Non performing matured balloon**, `A` payment not received but still in grace period or not yet due, `B` late payment but less than 30 days delinquent. No other values validate. Yes, 4 and 5 are the matured-balloon codes, and they split performing (4) from non-performing (5). The SEC never defines "performing" in this context. CREFC (secondary) does: 4 means the loan is past maturity without payoff and the borrower is still sending the monthly "assumed scheduled payment", and 5 means it's past maturity and that payment isn't coming. CREFC also says matured loans are kept out of the 30/60/90 buckets, so a matured, non-paying loan shows 5, not 1/2/3.
- **`liquidationPrepaymentCode`** (Item 2(i)(1)): codes 1 to 11 (table in section 3.3). Its date is **`liquidationPrepaymentDate`** (Item 2(i)(2)). Realized loss is **`realizedLossToTrustAmount`** (Item 2(h)). Prepayment premium is **`prepaymentPremiumYieldMaintenanceReceivedAmount`** (Item 2(i)(3)). All four sit at loan level (`assets`).
- **Special servicing**: there's no "in special servicing" flag and no transfer-reason code in Schedule AL. The fields are **`mostRecentSpecialServicerTransferDate`** (2(f)(2)), **`mostRecentMasterServicerReturnDate`** (2(f)(3)), and **`workoutStrategyCode`** (2(j), repeatable). `nonRecoverabilityIndicator` (2(e)(16)(ii)) is related.
- **Percent units: the SEC never says.** The schema type is a bare `decimal(20,8)`, and neither the rule nor the spec states a unit. The SEC's sample file uses fractions (rate `0.0417`, occupancy `0.999`). CREFC's Schedule AL template uses whole percents with 2 decimals (rate `4.38`, occupancy `88.50`). Your mixed data (`0.83` beside `93.9`) is legal under the schema. Section 2 has details.

---

## 2. Units convention for `*Percentage` fields (your question (a))

**What the primary sources say:**

1. [XSD]: every `*Percentage` / `*percentage` / `*Percent` element is `ns1:DECIMAL_TYPE20_8` (from `eis_Common.xsd`): `xs:decimal`, totalDigits 20, fractionDigits 8, range ±999999999999.99999999. No unit is given.
2. [SPEC-PDF] sec. 3.2: Decimal means "Valid characters are 0-9, and the minus sign. Cannot contain commas, dollar sign, or parentheses. May contain period and decimal places." No unit.
3. [CFR] Item 2(d)(20)/(21): "Provide the percentage of rentable space occupied by tenants." Item 2(c)(7): "Provide the rate of interest..." No unit.
4. [REL] fn. 247: a commenter asked the SEC to say "whether the number should be displayed as an integer or as a decimal." The final rule text never settles it.
5. **The SEC sample file** (`ABS Sample XML files/Sample_ABS_CMBS.xml` in the v3.1 zip) uses fractions throughout: `originalInterestRatePercentage` 0.0417, `servicerTrusteeFeeRatePercentage` 0.0002, `physicalOccupancySecuritizationPercentage` 0.999 / 0.94 / 0.839 / 0.812, and `mostRecentPhysicalOccupancyPercentage` with the same values. Treat this as illustration, not a rule. That same file has `armIndexCode` = `Z`, which isn't a valid enumeration, so the samples weren't validated against the schema.
6. **DSCR fields named `...Percentage` are ratios.** [CFR] 2(d)(28)(xv) to (xviii) say "Provide the **ratio** of ... net operating income to debt service." The SEC sample shows 1.9, 1.79 and so on, which means 1.90x and not 1.9%.

**[SECONDARY: CREFC]** IRP v8.4, Overview, p. 9: "The various CREFC schedules and Schedule AL use different formatting methodologies for numbers that are reported as percentages... an ARM margin of 2.5% would be reported as .025 on the Loan Set Up File (S25) and **2.50 in Schedule AL** (A36). Additionally, Schedule AL has a limit of 2 decimal places... a rate of 3.5326 would be rounded to 3.53." CREFC's Schedule AL layout (pp. 60 to 63) gives format examples of `4.38` for every interest-rate field, `88.50` for both occupancy fields, and `1.51` for DSCR.

**Where they conflict:**
- CREFC's "2 decimal places" limit **isn't in the SEC schema**, which allows 8 fraction digits. Your `0.0431` (4 decimals) proves at least one filer ignores CREFC on rates.
- The SEC sample implies fractions. CREFC implies whole percents. Your observed record (`mostRecentPhysicalOccupancyPercentage` 0.83, `physicalOccupancySecuritizationPercentage` 93.9) follows one convention for each field. Nothing primary makes either one wrong.
- **Bottom line:** no authoritative unit exists, so normalize per field, and probably per filer or servicer too. A value above 1.0 in an occupancy or interest-rate field can only be a whole percent: occupancy can't exceed 100%, and real CMBS coupons aren't above 100%. Values at or below 1.0 are ambiguous only near the bottom (an occupancy of 1.0 could mean 100% or 1%). That's my inference, not an SEC rule.

---

## 3. Code tables (all from [XSD] v3.1, matched against [SPEC-PDF] sec. 4.3)

Format: **tag** | parent | Schedule AL item, with the [CFR] caption | XSD type | PDF section.

### 3.1 `paymentStatusLoanCode`
`assets` | **Item 2(e)(17)** "Payment status of loan. Provide the code that indicates the payment status of the loan." | `PYMNT_STAT_LOAN_CODE_TYPE` | PDF 4.3.20 (p. 4-16)

| Code | Meaning (verbatim) |
|---|---|
| `0` | Current |
| `1` | 30-59 days delinquent |
| `2` | 60-89 days delinquent |
| `3` | 90+ days delinquent |
| `4` | Performing matured balloon |
| `5` | Non performing matured balloon. |
| `A` | Payment not received but still in grace period or not yet due. |
| `B` | Late payment but less than 30 days delinquent |

**[SECONDARY: CREFC]** The IRP Legend (p. 24) has a 9th code, `6` = "121+ Days Delinquent", and defines `3` there as "90-120 Days Delinquent." Data Dictionary (p. 36): "For Schedule AL Code 6 should be combined with and reported under Code 3. Hence in Schedule AL, Code 3 will be 90+ days delinquent." That's why `6` never shows up in EX-102 data. The Delinquent Loan Status Report definitions (p. 10) say matured performing loans are those "where the maturity date has passed without paying off and a monthly payment (assumed scheduled payment) is still being received from the borrower." Matured non-performing loans are the same, except the payment "is not being received." The template notes on p. 68 say: "The 30 to 59, 60 to 89 and 90+ Day Delinquent categories should not include Matured Loans (Performing/Non-Performing)."

### 3.2 `propertyTypeCode`
`property` | **Item 2(d)(7)** "Property type. Indicate the code that describes how the property is being used." | `PROPRTY_TYP_CODE_TYPE` | PDF 4.3.10 (p. 4-13)

| Code | Meaning (verbatim) |
|---|---|
| `CH` | Cooperative housing |
| `HC` | HealthCare |
| `IN` | Industrial |
| `LO` | Lodging |
| `MF` | Multifamily |
| `MH` | Mobile Home Park |
| `MU` | Mixed Use |
| `OF` | Office |
| `RT` | Retail |
| `SE` | Securities |
| `SS` | Self Storage |
| `WH` | Warehouse |
| `ZZ` | Missing Information |
| `98` | Other |

`CH` = Cooperative housing and `SE` = Securities, confirmed. **[SECONDARY: CREFC]** Data Dictionary, Property Type (p. 38): "If the property has been defeased, populated with 'SE'"; "For Schedule AL purposes code 'SF' should be reported as 'MF'." The defeasance dictionary entry (p. 30) says a fully defeased loan gets Property Status 3, Property Type SE, and Property Name "Defeased." **So in practice `SE` marks defeasance collateral (Treasuries), not real estate.** The primary [CFR] 2(d)(1) supports this: "If the property has been defeased, then populate with 'defeased.'" For history: XSD v1.4 (Nov 4 to Dec 12, 2016) spelled Other as `98.0` (section 9).

### 3.3 `liquidationPrepaymentCode` and related fields
`assets` | **Item 2(i)(1)** "Liquidation/Prepayment code. Indicate the code assigned to any unscheduled principal payments or liquidation proceeds received during the reporting period." | `LIQDTN_PRPYMNT_CODE_TYPE` | PDF 4.3.23 (p. 4-17)

| Code | Meaning (verbatim) |
|---|---|
| `1` | Partial liquidation(Curtailment) |
| `2` | Payoff Prior to Maturity |
| `3` | Disposition/Liquidation |
| `4` | Repurchase/Substitution |
| `5` | Full Payoff at Maturity |
| `6` | DPO |
| `7` | Liquidated-only for use for loans liquidated prior to 7/1/2006 |
| `8` | Payoff w/ Penalty |
| `9` | Payoff w/ Yield Maintenance |
| `10` | Curtailment w/ Penalty |
| `11` | Curtailment w/ Yield Maintenance |

[CFR] makes Item 2(i) conditional: "If a prepayment was received, provide..." The CREFC Legend (p. 24) matches all 11 codes.

Related exact tags, all in `assets` and all from [XSD] and [CFR]:

| Tag | Item | Type | Definition ([CFR]) |
|---|---|---|---|
| `liquidationPrepaymentDate` | 2(i)(2) | date MM-DD-YYYY | "the effective date on which an unscheduled principal payment or liquidation proceeds were received." |
| `prepaymentPremiumYieldMaintenanceReceivedAmount` | 2(i)(3) | decimal | "the amount received from a borrower during the reporting period in exchange for allowing a borrower to pay off a loan prior to the maturity or anticipated repayment date." |
| `realizedLossToTrustAmount` | 2(h) | decimal | "the difference between net proceeds (after liquidation expenses) and the scheduled or stated principal of the loan as of the beginning of the reporting period." |
| `unscheduledPrincipalCollectedAmount` | 2(e)(10) | decimal | "principal prepayments and other unscheduled payments of principal received on the loan during the reporting period." |
| `otherPrincipalAdjustmentAmount` | 2(e)(11) | decimal | "any other amounts that caused the principal balance of the loan to be decreased or increased during the reporting period..." |

### 3.4 Special servicing and workout fields
None of these are coded except `workoutStrategyCode`. All sit in `assets`.

| Tag | Item | Type | Definition ([CFR] wording) |
|---|---|---|---|
| `mostRecentSpecialServicerTransferDate` | 2(f)(2) | date | "Most recent special servicer transfer date. Provide the date the transfer letter, email, etc. provided by the master servicer is accepted by the special servicer." |
| `mostRecentMasterServicerReturnDate` | 2(f)(3) | date | "Most recent master servicer return date. Provide the date of the return letter, email, etc. provided by the special servicer which is accepted by the master servicer." |
| `workoutStrategyCode` | 2(j) | code, **repeatable** (`maxOccurs="unbounded"`, values must be unique within one asset) | "Workout strategy. Indicate the code that best describes the steps being taken to resolve the loan." |
| `nonRecoverabilityIndicator` | 2(e)(16)(ii) | boolean | "whether the master servicer/special servicer has ceased advancing principal and interest and/or servicing the loan." |
| `primaryServicerName` | 2(f)(1) | string(30) | name of the servicer. |

`workoutStrategyCode` values: `WRKOUT_STRAT_CODE_TYPE`, PDF 4.3.24 (p. 4-17)

| Code | Meaning (verbatim) |
|---|---|
| `1` | Modification |
| `2` | Foreclosure |
| `3` | Bankruptcy |
| `4` | Extension |
| `5` | Note sale |
| `6` | DPO |
| `7` | REO |
| `8` | Resolved |
| `9` | Pending return to master servicer |
| `10` | Deed-in-lieu of Foreclosure |
| `11` | Full Payoff |
| `12` | Reps and Warranties |
| `13` | TBD |
| `98` | Other |

The schema puts a uniqueness constraint `uniqueWorkoutStrategyCode` on this element, so one asset can carry several different codes ([SPEC-PDF] sec. 5.4).

**[SECONDARY: CREFC]** Data Dictionary (p. 34): the transfer date is "The date a loan becomes a 'specially serviced loan'... If the loan has had multiple transfers, this should be the last date transferred to special servicing." The return date is "The date a loan becomes a 'corrected mortgage loan'... If the loan has had multiple transfers, this should be the last date returned to the Master Servicer." CREFC's own reporting has a "Reason for SS Transfer" code (Data Dictionary, p. 39). **Schedule AL doesn't**, and it has no appraisal-reduction field either. I checked the full element list for both.

**Inference (not stated by SEC):** a loan is currently with the special servicer when `mostRecentSpecialServicerTransferDate` is populated and `mostRecentMasterServicerReturnDate` is either empty or earlier than the transfer date. Watch out for one-time misreports, and for the case where workout code 9 ("Pending return") is set while the loan hasn't been returned yet.

### 3.5 Modification fields

| Tag | Parent | Item | Type | Definition ([CFR]) |
|---|---|---|---|---|
| `modifiedIndicator` | assets | 2(c)(27) | boolean | "Modification indicator. Indicate yes or no whether the loan has been modified from its original terms." (cumulative, ever-modified) |
| `reportPeriodModificationIndicator` | assets | 2(e)(2) | boolean | "Modification indicator, reporting period. Indicate yes or no whether the loan was modified during the reporting period." |
| `lastModificationDate` | assets | 2(k)(1) | date | "the date of the most recent modification. A modification includes any material change to the loan document, excluding assumptions." |
| `modificationCode` | assets | 2(k)(2) | code, **repeatable** (unique per asset) | "the code that describes the type of loan modification." |
| `postModificationInterestPercentage` | assets | 2(k)(3) | decimal | new initial interest rate |
| `postModificationPaymentAmount` | assets | 2(k)(4) | decimal | new initial P&I payment |
| `postModificationMaturityDate` | assets | 2(k)(5) | date | new maturity date |
| `postModificationAmortizationPeriodAmount` | assets | 2(k)(6) | decimal (it's months, but typed decimal) | new amortization period in months |

[CFR] 2(k) applies "If the loan has been modified from its original terms," and the 2(k) fields describe "the most recent loan modification."

`modificationCode` values: `MOD_CODE_TYPE`, PDF 4.3.25 (p. 4-18)

| Code | Meaning (verbatim) |
|---|---|
| `1` | Maturity Date Extension |
| `2` | Amortization Change |
| `3` | Principal Write-off |
| `5` | Temporary Rate Reduction |
| `6` | Capitalization on Interest |
| `7` | Capitalization on Taxes |
| `8` | Combination |
| `10` | Forbearance (added in v3.1, effective Sept 18, 2023) |
| `98` | Other |

There's no code 4 or 9. **[SECONDARY: CREFC] numbering conflict:** in the CREFC Legend (p. 24), `4` = (Not Used), **`8` = Other, `9` = Combination**, `10` = Forbearance. CREFC Data Dictionary (p. 33): "For Schedule AL code 8 or 10 should be mapped to code 98 and code 9 should be mapped to 8." So an SEC `8` means Combination. A forbearance may show up as `98` (servicers following CREFC v8.4, which never updated this note after the SEC added 10) or as `10` (servicers following the SEC spec after Sept 2023). Treat both as possible.

### 3.6 `loanStructureCode`
`assets` | **Item 2(c)(15)** "Loan structure. Indicate the code that describes the type of loan structure including the seniority of participated mortgage loan components. The code relates to the loan within the securitization." | `LOAN_STCTR_CODE_TYPE` | PDF 4.3.4 (p. 4-10)

| Code | Meaning (verbatim) |
|---|---|
| `A1` | A Note; A/B Participation Structure |
| `A2` | A Note; A/B/C Participation Structure |
| `B1` | B Note; A/B Participation Structure |
| `B2` | B Note; A/B/C Participation Structure |
| `C2` | C Note; A/B/C Participation Structure |
| `MZ` | Mezzanine Financing |
| `PP` | Participated mortgage loan with pari passu debt outside trust |
| `WL` | Whole loan structure |

### 3.7 `paymentTypeCode`
`assets` | **Item 2(c)(16)** "Payment type. Indicate the code that describes the type or method of payment for a loan." | `PYMNT_TYP_CODE_TYPE` | PDF 4.3.5 (p. 4-10)

| Code | Meaning (verbatim) |
|---|---|
| `1` | fully Amortizing |
| `2` | amortizing Balloon |
| `3` | Interest Only/Balloon |
| `4` | Interest Only/Amortizing |
| `5` | Interest Only/Amortizing/Balloon |
| `6` | Principal Only |
| `7` | hyper Amortization |
| `98` | Other |

### 3.8 `interestAccrualMethodCode`
`assets` | **Item 2(c)(9)** "Interest accrual method. Provide the code that indicates the 'number of days' convention used to calculate interest." | `INTR_ACCRL_METH_CODE_TYPE` | PDF 4.3.1 (p. 4-9)

| Code | Meaning (verbatim) |
|---|---|
| `1` | 30/360 |
| `2` | Actual/365 |
| `3` | Actual/360 |
| `4` | Actual/Actual |
| `5` | Actual/366 |
| `6` | Simple |
| `7` | 78's |
| `98` | Other |

### 3.9 `originalInterestRateTypeCode`
`assets` | **Item 2(c)(10)** "Original interest rate type. Indicate whether the interest rate on the loan is fixed, adjustable, step or other." | `ORIG_INTR_RT_TYP_CODE_TYPE` | PDF 4.3.2 (p. 4-9)

| Code | Meaning (verbatim) |
|---|---|
| `1` | Fixed |
| `2` | ARM |
| `3` | Step |
| `4` | Other |

### 3.10 `lienPositionSecuritizationCode`
`assets` | **Item 2(c)(14)** "Lien position at securitization. Indicate the code that describes the lien position for the loan as of securitization." | `LIEN_PSTN_CODE_TYPE` | PDF 4.3.3 (p. 4-9)

| Code | Meaning (verbatim) |
|---|---|
| `1` | Primary |
| `2` | Secondary |
| `3` | Tertiary;etc |
| `98` | Other |
| `99` | Unknown |

### 3.11 `paymentFrequencyCode`
`assets` | **Item 2(c)(19)** "Payment frequency. Indicate the code that describes the frequency mortgage loan payments are required to be made." | `PYMNT_FREQ_CODE_TYPE` | PDF 4.3.6 (p. 4-10)

| Code | Meaning (verbatim) |
|---|---|
| `1` | monthly |
| `3` | quarterly |
| `6` | semi-annually |
| `12` | annually |
| `365` | daily |

`rateResetFrequencyCode` (2(c)(28)(xi), `RT_RST_FREQ_CODE_TYPE`, PDF 4.3.8) and `paymentResetFrequencyCode` (2(c)(28)(xii), `PY_RST_FREQ_CODE_TYPE`, PDF 4.3.9) use the same five values.

### 3.12 `servicingAdvanceMethodCode`
`assets` | **Item 2(e)(16)(i)** "Servicing advance methodology. Indicate the code that describes the manner in which principal and/or interest are advanced by the servicer." | `SRVC_ADV_METH_CODE_TYPE` | PDF 4.3.19 (p. 4-15/4-16)

| Code | Meaning (verbatim) |
|---|---|
| `1` | Scheduled Interest, Scheduled Principal |
| `2` | Actual Interest, Actual Principal |
| `3` | Scheduled Interest, Actual Principal |
| `98` | Other |
| `99` | Unknown |

### 3.13 Valuation source: `valuationSourceSecuritizationCode` and `mostRecentValuationSourceCode`
The exact tags are these two. **There's no tag named `valuationSourceCode`.**

`valuationSourceSecuritizationCode`: `property` | **Item 2(d)(15)** "Valuation source at securitization. Specify the code that identifies the source of the property valuation." | `VAL_SRC_SCRTZTN_CODE_TYPE` | PDF 4.3.11 (p. 4-13)

| Code | Meaning (verbatim) |
|---|---|
| `BPO` | Broker price opinion |
| `MAI` | Certified MAI appraisal |
| `MS` | Master servicer estimate |
| `Non-MAI` | Non-certified MAI appraisal |
| `98` | Other |
| `SS` | SS estimate |

`mostRecentValuationSourceCode`: `property` | **Item 2(d)(19)** "Most recent valuation source. Specify the code that identifies the source of the most recent property valuation." | `MST_RCNT_VAL_SRC_CODE_TYPE` | PDF 4.3.12 (p. 4-13/4-14). The values are the same: `98` Other, `BPO` "Broker Price Option" (the SEC's typo for Opinion), `MAI` Certified MAI Appraisal, `MS` Master Servicer Estimate, `Non-MAI` Non-certified MAI appraisal, `SS` SS Estimate. Codes are case-sensitive ([SPEC-PDF] 3.1), so it's `Non-MAI` exactly. The related value and date tags are `valuationSecuritizationAmount` (2(d)(14)), `valuationSecuritizationDate` (2(d)(16)), `mostRecentValuationAmount` (2(d)(17)), and `mostRecentValuationDate` (2(d)(18)).

### 3.14 `DefeasedStatusCode` (capital D)
`property` | **Item 2(d)(24)** "Defeasance status. Provide the code that indicates if a loan has or is able to be defeased." | `DFSNC_STAT_CODE_TYPE` | PDF 4.3.14 (p. 4-14)

| Code | Meaning (verbatim) |
|---|---|
| `F` | Full Defeasance |
| `IP` | Portion of Loan Previously Defeased |
| `N` | No Defeasance Occurred |
| `X` | Defeasance Not Allowable |

**[SECONDARY: CREFC]** (p. 30): "For Schedule AL map code P to code IP." Related tag: `defeasanceOptionStartDate` (2(d)(23)). The field is reported per property even though the definition is about the loan.

### 3.15 `propertyStatusCode`
`property` | **Item 2(d)(22)** "Property status. Provide the code that describes the status of the property." | `PROPRTY_STAT_CODE_TYPE` | PDF 4.3.13 (p. 4-14)

| Code | Meaning (verbatim) |
|---|---|
| `1` | In Foreclosure |
| `2` | REO |
| `3` | Defeased |
| `4` | Partial Release |
| `5` | Substituted |
| `6` | Same as at Securitization |

### 3.16 `netOperatingIncomeNetCashFlowSecuritizationCode` and `netOperatingIncomeNetCashFlowCode`
Both are `property`. Securitization: **Item 2(d)(28)(xii)**, `NET_OPRTNG_INCM_NET_CASH_FLW_SCRTZTN_CODE_TYPE`, PDF 4.3.15. Most recent: **Item 2(d)(28)(xiii)**, `NET_OPRTNG_INCM_NET_CASH_FLW_CODE_TYPE`, PDF 4.3.16. [CFR]: "Indicate the code that describes the method used to calculate [at securitization] net operating income or net cash flow."

| Code | Meaning (verbatim) |
|---|---|
| `CREFC` | Calculated using CREFC standard |
| `PSA` | Calculated using a definition given in the pooling and servicing agreement |
| `UW` | Calculated using the underwriting method |

### 3.17 `debtServiceCoverageSecuritizationCode` and `mostRecentDebtServiceCoverageCode`
Both are `property`. Securitization: **Item 2(d)(28)(xix)** "If there are multiple properties underlying the loan, indicate the code that describes how the debt service coverage ratio was calculated." `DEBT_SRVC_CVRG_CODE_TYPE`, PDF 4.3.17. Most recent: **Item 2(d)(28)(xx)** "Indicate the code that describes how the debt service coverage ratio was calculated for the most recent financial operating statement." `MST_RCNT_DEBT_SRVC_AMNT_CODE_TYPE`, PDF 4.3.18 (the PDF heading spells it `..._AMT_...`).

| Code | Meaning (verbatim, securitization version; most-recent wording differs only trivially) |
|---|---|
| `A` | Average - Not all properties received financials, servicer allocates debt service only to properties where financials are received. |
| `C` | Consolidated - All properties reported on one "rolled up" financial from the borrower |
| `F` | Full - All Statements Collected for all properties |
| `N` | None Collected - no financial statements were received |
| `P` | Partial - Not all properties received financials, servicer to leave empty |
| `W` | Worst Case - Not all properties received financial statements, servicer allocates 100% of Debt Service to all properties where financials are received |

There's a labeling slip in the XSD. The type used by `mostRecentDebtServiceCoverageCode` is named `MST_RCNT_DEBT_SRVC_AMNT_CODE_TYPE`, and its documentation cites "Item 2(d)(28)(xiv)" (which is most recent debt service *amount*). The element comment, the PDF 3.4.3 table and [CFR] all put this code field at **2(d)(28)(xx)**. The values themselves are clear.

The DSCR value tags (all `property`, all ratios per [CFR], see section 2) are `debtServiceCoverageNetOperatingIncomeSecuritizationPercentage` (xv), `mostRecentDebtServiceCoverageNetOperatingIncomePercentage` (xvi), `debtServiceCoverageNetCashFlowSecuritizationPercentage` (xvii), and `mostRecentDebtServiceCoverageNetCashFlowpercentage` (xviii, **lowercase p**).

### 3.18 `assetTypeNumber`
`assets` | **Item 2(a)(1)** "Asset number type. Identify the source of the asset number used to specifically identify each asset in the pool." | `STRING_100_TYPE`, **mandatory** (minOccurs=1).

**There's no code list.** It's free text up to 100 characters. The SEC sample uses `Prospectus Loan ID`, and the other SEC sample file uses the dummy `CONA`. **[SECONDARY: CREFC]** Data Dictionary (p. 27): "Used to Indentify the source of the Asset number. For all securitizations this should be 'Prospectus Loan ID'." CREFC Prospectus Loan ID (p. 39): "For a partial defeasance where the loan is bifurcated, the Prospectus Loan ID for the original/non-defeased loan is appended with an 'A', and the new/defeased loan is appended with a 'B'... In Schedule AL, this field is named Asset Number." `assetNumber` (2(a)(2)) is mandatory, string(25). [CFR] instruction to (a)(2): the number "should be the same number that will be used to identify the asset for all reports," and a replacement asset gets a new unique number.

### 3.19 Other coded fields, for completeness
- `armIndexCode` (2(c)(28)(i), `ARM_INDX_CODE_TYPE`, PDF 4.3.7): `A` 11 FHLB COFI (1 Month), `B` 11 FHLB COFI (6 Month), `C` 1 Year CMT Weekly Average Treasury, `D` 3 Year CMT Weekly Average Treasury, `E` 5 Year CMT Weekly Average Treasury, `F` Wall Street Journal Prime Rate, `G` 1 Month LIBOR, `H` 3 Month LIBOR, `I` 6 Month LIBOR, `J` National Mortgage Index Rate, `K` 30-Day Average SOFR Compounded in Advance, `L` 90-Day Average SOFR Compounded in Advance, `M` 180-Day Average SOFR Compounded in Advance, `N` 30-Day Average SOFR Compounded in Arrears, `O` 90-Day Average SOFR Compounded in Arrears, `P` 180-Day Average SOFR Compounded in Arrears, `Q` 1-Month Term SOFR, `R` 3-Month Term SOFR, `S` 6-Month Term SOFR, `98` Other. K to S were added in v3.0 (Dec 19, 2022).
- `assetSubjectDemandStatusCode` (2(g)(1), PDF 4.3.21): `0` Asset Pending Repurchase or Replacement (within cure period), `1` Asset was Repurchased or Replaced, `2` Demand in Dispute, `3` Demand Withdrawn, `4` Demand Rejected.
- `repurchaseReplacementReasonCode` (2(g)(5), PDF 4.3.22, **repeatable**): `1` Fraud, `2` Early Payment Default, `3` Other recourse obligation, `4` Reps/Warrants breach, `5` Servicer breach, `98` Other, `99` Unknown.

The full machine-extracted set of all 25 code types, verbatim, is in section 10.

---

## 4. Booleans, dates, structure (for the parser)

- Boolean: the literal `true` / `false` ([SPEC-PDF] 3.2; XSD `TRUE_FALSE_TYPE`).
- Date ("Date1"): **MM-DD-YYYY** ([SPEC-PDF] 3.2). The XSD pattern `\d{1,2}-\d{1,2}-\d{4}` also accepts 1-digit month or day.
- Tree: root `assetData` > `assets` (one per loan, repeatable) > `property` (repeatable, nested **inside** `assets` between `deferredInterestCollectedAmount` and `assetAddedIndicator`). Elements must appear in schema order ([SPEC-PDF] table 2-2).
- Repeatable code elements, each unique within one `assets`: `workoutStrategyCode`, `modificationCode`, `repurchaseReplacementReasonCode` ([XSD] `xs:unique` constraints; [SPEC-PDF] 5.4).
- `GroupID` is defined in [CFR] 2(a)(3) as an "alpha-numeric code," but the XSD types it as `INTEGER_TYPE_8_A`, so only integers validate.

## 5. Exact tag spellings that will trip a tag census

These come straight from the XSD, odd spellings included: `DefeasedStatusCode` (capital D), `GroupID`, `NumberPropertiesSecuritization`, `NumberProperties` (capital N), `netCashFlowFlowSecuritizationAmount` ("FlowFlow"), `mostRecentDebtServiceCoverageNetCashFlowpercentage` (lowercase p), `reportPeriodBeginningScheduleLoanBalanceAmount` ("Schedule", not "Scheduled"), `periodicPaymentAdjustmentMaximumPercent` (not "Percentage"), `yearLastRenovated` (no "Number"), `armMarginNumber` (decimal, not "Percentage"), `postModificationAmortizationPeriodAmount` (months, typed decimal). The repo file `config/sec_cmbs_schema_elements.csv` has all 153 (99 under `assets` including the `property` container, plus 54 under `property`).

## 6. Observed data vs spec

| Your observation | Spec says | Verdict |
|---|---|---|
| `paymentStatusLoanCode` 0, A, B, 1, 2, 3, 4, 5 | Exactly these 8 codes | Matches; you've seen every legal value. |
| `propertyTypeCode` OF RT LO IN MF SS MU CH MH SE WH 98 | 14 codes; you haven't seen `HC` or `ZZ` | Matches. CH = Cooperative housing, SE = Securities (defeased collateral per CREFC). |
| `loanStructureCode` WL, PP, A1, A2, B1 | 8 codes; not yet seen B2, C2, MZ | Matches. |
| NOI/NCF codes UW, CREFC | CREFC, PSA, UW | Matches. |
| DSCR codes C, F | A, C, F, N, P, W | Matches. |
| Rates as decimals (0.0431) | No unit in SEC sources; SEC sample uses fractions; CREFC template says whole percent with 2 decimals | Consistent with the SEC sample, **contradicts CREFC guidance** (4 decimals, fraction). Not a spec violation. |
| Occupancy 0.83 (most recent) vs 93.9 (securitization) in one record | No unit; SEC sample uses fractions for both; CREFC uses whole percent for both | **Internally inconsistent** within the filer, but not a schema violation. Neither convention is primary-source wrong. Normalize per field. |
| (Possible) `98.0` in old filings | v1.4 (Nov 4 to Dec 12, 2016) used `98.0` for Other in `propertyTypeCode`, `valuationSourceSecuritizationCode`, `armIndexCode` | I haven't verified that any filing actually used it. Map `98.0` to `98` if you see it. |
| (Possible) `modificationCode` 8 | SEC 8 = Combination | Someone mapping straight from CREFC could misuse 8 (CREFC 8 = Other). CREFC tells filers to remap. Can't be checked from SEC sources. |

Since EDGAR validates EX-102 against the XSD in force on the filing date, any accepted file **can't** carry a code outside that version's list. If your census finds one, suspect your parser or an older schema version first.

## 7. Schedule AL item to element map for the requested fields

| Element | Parent | Item |
|---|---|---|
| assetTypeNumber | assets | 2(a)(1) |
| interestAccrualMethodCode | assets | 2(c)(9) |
| originalInterestRateTypeCode | assets | 2(c)(10) |
| lienPositionSecuritizationCode | assets | 2(c)(14) |
| loanStructureCode | assets | 2(c)(15) |
| paymentTypeCode | assets | 2(c)(16) |
| paymentFrequencyCode | assets | 2(c)(19) |
| modifiedIndicator | assets | 2(c)(27) |
| propertyTypeCode | property | 2(d)(7) |
| valuationSourceSecuritizationCode | property | 2(d)(15) |
| mostRecentValuationSourceCode | property | 2(d)(19) |
| physicalOccupancySecuritizationPercentage | property | 2(d)(20) |
| mostRecentPhysicalOccupancyPercentage | property | 2(d)(21) |
| propertyStatusCode | property | 2(d)(22) |
| DefeasedStatusCode | property | 2(d)(24) |
| netOperatingIncomeNetCashFlowSecuritizationCode | property | 2(d)(28)(xii) |
| netOperatingIncomeNetCashFlowCode | property | 2(d)(28)(xiii) |
| debtServiceCoverageSecuritizationCode | property | 2(d)(28)(xix) |
| mostRecentDebtServiceCoverageCode | property | 2(d)(28)(xx) |
| reportPeriodModificationIndicator | assets | 2(e)(2) |
| servicingAdvanceMethodCode | assets | 2(e)(16)(i) |
| nonRecoverabilityIndicator | assets | 2(e)(16)(ii) |
| paymentStatusLoanCode | assets | 2(e)(17) |
| mostRecentSpecialServicerTransferDate | assets | 2(f)(2) |
| mostRecentMasterServicerReturnDate | assets | 2(f)(3) |
| realizedLossToTrustAmount | assets | 2(h) |
| liquidationPrepaymentCode | assets | 2(i)(1) |
| liquidationPrepaymentDate | assets | 2(i)(2) |
| prepaymentPremiumYieldMaintenanceReceivedAmount | assets | 2(i)(3) |
| workoutStrategyCode | assets | 2(j) |
| lastModificationDate | assets | 2(k)(1) |
| modificationCode | assets | 2(k)(2) |

## 8. What I could not verify from a primary SEC source

1. **Percent units.** No SEC rule, spec, release or interpretation states one. The only SEC data point is the sample XML, which is illustrative and doesn't fully validate (it contains `armIndexCode` Z).
2. **What "performing" vs "non performing" matured balloon means.** The SEC gives only the labels. The operational definition (still paying the assumed scheduled payment or not) comes from CREFC only.
3. **SE = defeasance collateral.** The SEC says only "Securities." Tying it to defeasance comes from CREFC, though [CFR] 2(d)(1) "populate with defeased" is consistent with it.
4. **A loan-level "currently specially serviced" status.** No such field exists. The transfer-date vs return-date rule in 3.4 is my inference.
5. **CREFC remaps** (payment status 6 to 3, modification code 9 to 8 and 8/10 to 98, defeasance P to IP, property type SF to MF, assetTypeNumber = "Prospectus Loan ID"). These are CREFC guidance to filers, not SEC requirements, so individual servicers may not follow them.
6. **Whether any filing actually contains `98.0`.** I only know the v1.4 schema allowed it.

## 9. Code-list version history ([HIST], verified by diffing the CMBS XSD in each zip)

| Spec version | Effective | CMBS XSD change |
|---|---|---|
| 1.4 | Nov 4, 2016 | "Other" spelled `98.0` in `ARM_INDX_CODE_TYPE` (alongside `98`), `PROPRTY_TYP_CODE_TYPE`, `VAL_SRC_SCRTZTN_CODE_TYPE`. `armMarginNumber` typed integer. |
| 1.5 | Dec 12, 2016 (EDGAR 16.4) | `98.0` changed to `98` in those three types; `armMarginNumber` changed to decimal (v1.5 PDF sec. 1.2). |
| 1.6, 1.7, 1.8, 2.0 | 2017 to Sept 2021 | CMBS XSD byte-identical to v1.5 (same MD5). |
| 3.0 | Dec 19, 2022 (EDGAR 22.4) | ARM index codes K to S (SOFR variants) added. |
| 3.1 | Sept 18, 2023 (EDGAR 23.3) | `MOD_CODE_TYPE` gains `10` Forbearance; ARM index K to P descriptions reworded. This is the current version. |

Payment status, liquidation/prepayment, workout, loan structure, payment type, accrual, NOI/NCF and DSCR code lists haven't changed since the CMBS asset-level regime began in Nov 2016.

## 10. All 25 code types, machine-extracted from the v3.1 XSD (verbatim)

The tables in section 3 were generated from the same parse.

| Type | Used by | Item | Codes |
|---|---|---|---|
| ARM_INDX_CODE_TYPE | armIndexCode | 2(c)(28)(i) | 98, A to S (see 3.19) |
| ASSET_SUBJ_DEMAND_STAT_CODE_TYPE | assetSubjectDemandStatusCode | 2(g)(1) | 0 to 4 |
| DEBT_SRVC_CVRG_CODE_TYPE | debtServiceCoverageSecuritizationCode | 2(d)(28)(xix) | A C F N P W |
| DFSNC_STAT_CODE_TYPE | DefeasedStatusCode | 2(d)(24) | F IP N X |
| INTR_ACCRL_METH_CODE_TYPE | interestAccrualMethodCode | 2(c)(9) | 1 to 7, 98 |
| LIEN_PSTN_CODE_TYPE | lienPositionSecuritizationCode | 2(c)(14) | 1 2 3 98 99 |
| LIQDTN_PRPYMNT_CODE_TYPE | liquidationPrepaymentCode | 2(i)(1) | 1 to 11 |
| LOAN_STCTR_CODE_TYPE | loanStructureCode | 2(c)(15) | A1 A2 B1 B2 C2 MZ PP WL |
| MOD_CODE_TYPE | modificationCode | 2(k)(2) | 1 2 3 5 6 7 8 10 98 |
| MST_RCNT_DEBT_SRVC_AMNT_CODE_TYPE | mostRecentDebtServiceCoverageCode | 2(d)(28)(xx) | A C F N P W |
| MST_RCNT_VAL_SRC_CODE_TYPE | mostRecentValuationSourceCode | 2(d)(19) | 98 BPO MAI MS Non-MAI SS |
| NET_OPRTNG_INCM_NET_CASH_FLW_CODE_TYPE | netOperatingIncomeNetCashFlowCode | 2(d)(28)(xiii) | CREFC PSA UW |
| NET_OPRTNG_INCM_NET_CASH_FLW_SCRTZTN_CODE_TYPE | netOperatingIncomeNetCashFlowSecuritizationCode | 2(d)(28)(xii) | CREFC PSA UW |
| ORIG_INTR_RT_TYP_CODE_TYPE | originalInterestRateTypeCode | 2(c)(10) | 1 2 3 4 |
| PROPRTY_STAT_CODE_TYPE | propertyStatusCode | 2(d)(22) | 1 to 6 |
| PROPRTY_TYP_CODE_TYPE | propertyTypeCode | 2(d)(7) | CH HC IN LO MF MH MU OF RT SE SS WH ZZ 98 |
| PY_RST_FREQ_CODE_TYPE | paymentResetFrequencyCode | 2(c)(28)(xii) | 1 3 6 12 365 |
| PYMNT_FREQ_CODE_TYPE | paymentFrequencyCode | 2(c)(19) | 1 3 6 12 365 |
| PYMNT_STAT_LOAN_CODE_TYPE | paymentStatusLoanCode | 2(e)(17) | 0 1 2 3 4 5 A B |
| PYMNT_TYP_CODE_TYPE | paymentTypeCode | 2(c)(16) | 1 to 7, 98 |
| REPRCH_RPLCMNT_REASN_CODE_TYPE | repurchaseReplacementReasonCode | 2(g)(5) | 1 to 5, 98, 99 |
| RT_RST_FREQ_CODE_TYPE | rateResetFrequencyCode | 2(c)(28)(xi) | 1 3 6 12 365 |
| SRVC_ADV_METH_CODE_TYPE | servicingAdvanceMethodCode | 2(e)(16)(i) | 1 2 3 98 99 |
| VAL_SRC_SCRTZTN_CODE_TYPE | valuationSourceSecuritizationCode | 2(d)(15) | BPO MAI MS Non-MAI 98 SS |
| WRKOUT_STRAT_CODE_TYPE | workoutStrategyCode | 2(j) | 1 to 13, 98 |

The two XSD files used by the parser are committed at `config/sec_schema/`. The spec zip is public at https://www.sec.gov/files/absxml-31.zip; CREFC IRP v8.4 is at the URL in section 0.
