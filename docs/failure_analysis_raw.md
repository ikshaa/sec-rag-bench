# Failure Analysis Raw Dump

Total questions: 100  |  Failures: 21

## Failures by classification

- **RETRIEVAL MISS (correct chunk not in top-5)**: 20
- **RETRIEVED BUT NOT CITED (right chunk pulled, model cited wrong source)**: 1

## Each failure

### q_001 (factual) — RETRIEVAL MISS (correct chunk not in top-5)

**Question**: What is the address of Apple's principal executive offices?

**Expected source**: apple FY2023

**Expected snippet**: One Apple Park Way, Cupertino, California 95014...

**Retrieved** (company_year): apple_2024, netflix_2024, apple_2024, amazon_2023, apple_2023

**Metrics**: recall@5=0.0, citation=0.0, faithfulness=1.0, relevancy=0.9000179906204373

**Model answer**:
```
According to Apple's 2024 10-K filing, the address of Apple's principal executive offices is:

One Apple Park Way
Cupertino, California 95014 [3]
```

---

### q_002 (numerical) — RETRIEVAL MISS (correct chunk not in top-5)

**Question**: How much long-term debt did Tesla report at the end of fiscal 2023?

**Expected source**: tesla FY2023

**Expected snippet**: As of December 31, 2023, we and our subsidiaries had outstanding $4.68 billion in aggregate principal amount of indebtedness...

**Retrieved** (company_year): google_2023, tesla_2023, costco_2023, tesla_2024, costco_2024

**Metrics**: recall@5=0.0, citation=0.0, faithfulness=1.0, relevancy=0.0

**Model answer**:
```
I don't have enough information in the provided context to answer this question.

The Tesla 2023 10-K context provided [2] shows only the Consolidated Balance Sheet with current assets and the beginning of operating lease vehicles and solar energy systems information, but it does not include the debt section or long-term debt figures. The Tesla 2024 10-K context [4] shows similar current assets information but also does not contain the long-term debt details.

To find Tesla's long-term debt at t
```

---

### q_003 (multi_hop) — RETRIEVAL MISS (correct chunk not in top-5)

**Question**: How did Tesla's total indebtedness change between fiscal 2023 and 2024?

**Expected source**: tesla FYmultiple

**Expected snippet**: [2023]: As of December 31, 2023, we and our subsidiaries had outstanding $4.68 billion... [2024]: [look up during validation]...

**Retrieved** (company_year): tesla_2023, tesla_2024, tesla_2024, tesla_2024, tesla_2024

**Metrics**: recall@5=0.0, citation=0.0, faithfulness=0.8333333333333334, relevancy=0.0

**Model answer**:
```
I don't have enough information in the provided context to answer this question.

While the context shows that as of December 31, 2024, Tesla had outstanding indebtedness of $7.91 billion [2], the context does not provide the total indebtedness figure as of December 31, 2023. The 2023 10-K excerpt [1] only shows balance sheet items related to noncontrolling interests and total liabilities and equity, but does not break out the total debt amount for that year.

To answer how Tesla's total indebte
```

---

### q_009 (numerical) — RETRIEVAL MISS (correct chunk not in top-5)

**Question**: What was Tesla's gross profit for fiscal year 2023?

**Expected source**: tesla FY2023

**Expected snippet**: Gross profit
17,660...

**Retrieved** (company_year): tesla_2024, nvidia_2024, nvidia_2023, tesla_2023, nvidia_2023

**Metrics**: recall@5=0.0, citation=0.0, faithfulness=0.16666666666666666, relevancy=0.9837196995396681

**Model answer**:
```
Based on the context provided, I can see Tesla's gross profit figures from the 2024 10-K filing, which includes comparative years.

According to [1], Tesla's gross profit for fiscal year 2023 was:
- **Automotive segment: $16,519 million**
- **Energy generation and storage segment: $1,141 million**

The total gross profit for Tesla in fiscal year 2023 was approximately **$17,660 million** (or $17.66 billion) when combining both segments.
```

---

### q_031 (comparison) — RETRIEVAL MISS (correct chunk not in top-5)

**Question**: How did Tesla's automotive sales revenue change from 2023 to 2024?

**Expected source**: tesla FYmultiple

**Expected snippet**: Automotive sales $ 72,480 $ 78,509 $ 67,210 $ (6,029) (8) %...

**Retrieved** (company_year): tesla_2023, tesla_2024, tesla_2023, tesla_2024, tesla_2024

**Metrics**: recall@5=0.0, citation=0.0, faithfulness=0.8333333333333334, relevancy=0.8931475883685915

**Model answer**:
```
Based on the context provided, Tesla's automotive sales revenue decreased $6.03 billion, or 8%, in the year ended December 31, 2024 as compared to the year ended December 31, 2023. This decline was primarily due to lower average selling price on Tesla's vehicles driven by overall price reductions and attractive financing offers [5].
```

---

### q_039 (multi_hop) — RETRIEVAL MISS (correct chunk not in top-5)

**Question**: Which of Nvidia's competitors are specifically identified as competing in both the GPU/accelerated computing space AND the networking products space?

**Expected source**: nvidia FY2024

**Expected snippet**: Our current competitors include: suppliers and licensors of hardware and software for discrete and integrated GPUs... AMD, Huawei... and Intel... and networking products consisting of switches, network adapters (including DPUs), and cable solutions... AMD, Arista Networks, Broadcom, Cisco Systems......

**Retrieved** (company_year): nvidia_2023, nvidia_2024, nvidia_2024, nvidia_2024, nvidia_2023

**Metrics**: recall@5=0.0, citation=0.0, faithfulness=0.8333333333333334, relevancy=0.0

**Model answer**:
```
I don't have enough information in the provided context to answer this question.

While the context identifies that NVIDIA faces competition from companies providing GPUs, CPUs, DPUs, and other accelerated computing processors, as well as providers of semiconductor-based high-performance interconnect products (InfiniBand, Ethernet, Fibre Channel) [3], the sources do not specifically name which competitors operate in both spaces simultaneously. The context describes the types of products that com
```

---

### q_042 (comparison) — RETRIEVAL MISS (correct chunk not in top-5)

**Question**: Over the five-year period ending January 28, 2024, how did the cumulative total shareholder return on $100 invested in Nvidia common stock compare to equivalent investments in the S&P 500 Index and the Nasdaq 100 Index?

**Expected source**: nvidia FY2024

**Expected snippet**: 1/27/2019 1/26/2020 1/31/2021 1/30/2022 1/29/2023 1/28/2024 NVIDIA Corporation $ 100.00 $ 157.02 $ 326.26 $ 574.15 $ 512.40 $ 1,536.28 S&P 500 $ 100.00 $ 126.17 $ 144.83 $ 175.25 $ 163.63 $ 199.83 Nasdaq 100 $ 100.00 $ 136.15 $ 194.20 $ 218.68 $ 185.67 $ 268.13...

**Retrieved** (company_year): nvidia_2023, nvidia_2024, netflix_2024, netflix_2023, google_2023

**Metrics**: recall@5=0.0, citation=0.0, faithfulness=0.5714285714285714, relevancy=0.0

**Model answer**:
```
I don't have enough information in the provided context to answer this question.

While source [2] from NVIDIA's 2024 10-K describes a stock performance graph that compares cumulative total shareholder return for NVIDIA common stock, the S&P 500 Index, and the Nasdaq 100 Index for the five years ended January 28, 2024, the actual numerical results or values from that graph are not included in the provided context. The excerpt only explains the methodology (that $100 was invested on January 27, 2
```

---

### q_043 (numerical) — RETRIEVAL MISS (correct chunk not in top-5)

**Question**: By what percentage did Nvidia's revenue grow between fiscal years 2023 and 2024, and what was the change in gross margin over the same period?

**Expected source**: nvidia FY2024

**Expected snippet**: Jan 28, 2024 Jan 29, 2023 Change ($ in millions, except per share data) Revenue $ 60,922 $ 26,974 Up 126% Gross margin 72.7 % 56.9 % Up 15.8 pts...

**Retrieved** (company_year): nvidia_2024, nvidia_2023, nvidia_2023, costco_2023, nvidia_2023

**Metrics**: recall@5=0.0, citation=0.0, faithfulness=0.6666666666666666, relevancy=0.0

**Model answer**:
```
I don't have enough information in the provided context to answer this question.

While the context includes information about fiscal year 2024 [1] and fiscal year 2023 [5], it does not provide the total revenue figures for fiscal year 2024 that would be needed to calculate the percentage growth between these two years. The fiscal year 2023 revenue is stated as $26.97 billion [5], but the fiscal year 2024 total revenue is not provided in the given context.

Additionally, while the context mentio
```

---

### q_044 (comparison) — RETRIEVAL MISS (correct chunk not in top-5)

**Question**: How did Nvidia's cost structure as a percentage of revenue change between fiscal year 2023 and fiscal year 2024?

**Expected source**: nvidia FYmultiple

**Expected snippet**: Year Ended Jan 28, 2024 Jan 29, 2023 Revenue 100.0 % 100.0 % Cost of revenue 27.3 43.1 Gross profit 72.7 56.9 Operating expenses Research and development 14.2 27.2 Sales, general and administrative 4.4 9.1...

**Retrieved** (company_year): nvidia_2024, nvidia_2023, microsoft_2024, nvidia_2023, nvidia_2024

**Metrics**: recall@5=0.0, citation=0.0, faithfulness=1.0, relevancy=0.0

**Model answer**:
```
I don't have enough information in the provided context to answer this question.

While the context includes data on NVIDIA's cost structure as a percentage of revenue for fiscal years ended January 29, 2023 and January 30, 2022 [2], it does not contain the corresponding percentage breakdown for fiscal year 2024. The fiscal year 2024 10-K excerpt [1] and [5] discusses absolute revenue amounts and changes, but does not provide cost of revenue as a percentage of revenue for fiscal year 2024, which
```

---

### q_046 (numerical) — RETRIEVAL MISS (correct chunk not in top-5)

**Question**: How much commercial paper did Nvidia have outstanding as of the end of fiscal year 2024, and what is the maximum size of Nvidia's commercial paper program?

**Expected source**: nvidia FY2024

**Expected snippet**: We have a $575 million commercial paper program to support general corporate purposes. As of the end of fiscal year 2024, we had no commercial paper outstanding....

**Retrieved** (company_year): apple_2024, amazon_2024, nvidia_2024, amazon_2023, apple_2024

**Metrics**: recall@5=0.0, citation=0.0, faithfulness=1.0, relevancy=0.8035018306403648

**Model answer**:
```
Based on the context provided, as of January 28, 2024 (Nvidia's fiscal year end), Nvidia had **no commercial paper outstanding** [3].

The maximum size of Nvidia's commercial paper program is **$575 million** [3].
```

---

### q_049 (multi_hop) — RETRIEVAL MISS (correct chunk not in top-5)

**Question**: How did Nvidia's workforce gender composition change between the end of fiscal year 2023 and the end of fiscal year 2024?

**Expected source**: nvidia FYmultiple

**Expected snippet**: [2023]: As of the end of fiscal year 2023, our global workforce was 80% male, 19% female, and 1% not declared... [2024]: As of the end of fiscal year 2024, our global workforce was 79% male, 20% female, and 1% not declared......

**Retrieved** (company_year): nvidia_2023, nvidia_2024, nvidia_2023, nvidia_2024, netflix_2023

**Metrics**: recall@5=0.0, citation=0.0, faithfulness=1.0, relevancy=0.9785485415589411

**Model answer**:
```
Based on the provided context, Nvidia's workforce gender composition changed slightly between the end of fiscal year 2023 and the end of fiscal year 2024:

**Fiscal Year 2023:** [1]
- Male: 80%
- Female: 19%
- Not declared: 1%

**Fiscal Year 2024:** [2]
- Male: 79%
- Female: 20%
- Not declared: 1%

The changes show a decrease of 1 percentage point in the male workforce (from 80% to 79%) and an increase of 1 percentage point in the female workforce (from 19% to 20%), while the "not declared" cate
```

---

### q_055 (multi_hop) — RETRIEVAL MISS (correct chunk not in top-5)

**Question**: How did Nvidia's and Apple's fiscal 2024 total revenues compare, and which company reported higher revenue?

**Expected source**: multiple FY2024

**Expected snippet**: [Apple]: Total net sales $ 391,035 ... [Nvidia]: Revenue $ 60,922...

**Retrieved** (company_year): nvidia_2024, apple_2024, nvidia_2024, nvidia_2024, nvidia_2023

**Metrics**: recall@5=0.0, citation=0.0, faithfulness=0.8333333333333334, relevancy=0.0

**Model answer**:
```
I don't have enough information in the provided context to answer this question.

While the context includes details about NVIDIA's fiscal 2024 revenue by segment [3][4], it does not provide NVIDIA's total fiscal 2024 revenue figure. Additionally, the Apple context [2] discusses deferred revenue and segment information but does not include Apple's total fiscal 2024 revenue.

To answer this question, I would need the total revenue figures for both companies for fiscal year 2024.
```

---

### q_056 (comparison) — RETRIEVAL MISS (correct chunk not in top-5)

**Question**: Among Apple's product and service categories, which one grew the most and which one declined the most in net sales from fiscal 2023 to fiscal 2024?

**Expected source**: apple FY2024

**Expected snippet**: iPhone $ 201,183 — % $ 200,583 Mac 29,984 2 % 29,357 iPad 26,694 (6) % 28,300 Wearables, Home and Accessories 37,005 (7) % 39,845 Services 96,169 13 % 85,200...

**Retrieved** (company_year): apple_2023, costco_2024, apple_2024, nvidia_2024, apple_2024

**Metrics**: recall@5=0.0, citation=0.0, faithfulness=0.5, relevancy=0.903024856757351

**Model answer**:
```
Based on the context provided [5], comparing Apple's net sales by category from fiscal 2023 to fiscal 2024:

**Most Growth:** Services grew the most, increasing by 13% (from $85,200 million in 2023 to $96,169 million in 2024).

**Most Decline:** Wearables, Home and Accessories declined the most, decreasing by 7% (from $39,845 million in 2023 to $37,005 million in 2024).
```

---

### q_057 (numerical) — RETRIEVAL MISS (correct chunk not in top-5)

**Question**: What amount did the European Commission order Ireland to recover from Apple under the 2016 State Aid Decision?

**Expected source**: apple FY2023

**Expected snippet**: The recovery amount was calculated to be €13.1 billion, plus interest of €1.2 billion....

**Retrieved** (company_year): apple_2023, apple_2023, apple_2024, apple_2024, amazon_2023

**Metrics**: recall@5=0.0, citation=0.0, faithfulness=1.0, relevancy=0.8105806727338992

**Model answer**:
```
Based on the context provided, the European Commission ordered Ireland to calculate and recover additional taxes from Apple of €13.1 billion, plus interest of €1.2 billion, for the period June 2003 through December 2014 under the 2016 State Aid Decision [1][4].
```

---

### q_065 (factual) — RETRIEVAL MISS (correct chunk not in top-5)

**Question**: Which Microsoft product does Microsoft describe as being at the forefront of AI-powered software development?

**Expected source**: microsoft FY2024

**Expected snippet**: GitHub Copilot is at the forefront of AI-powered software development, giving developers a tool to write code easier and faster....

**Retrieved** (company_year): microsoft_2024, microsoft_2024, microsoft_2023, microsoft_2023, microsoft_2023

**Metrics**: recall@5=0.0, citation=0.0, faithfulness=0.75, relevancy=0.0

**Model answer**:
```
Based on the provided context, I don't have enough information in the provided context to answer this question.

While the context mentions that Microsoft offers "software development tools and services (including GitHub)" [5] and references AI capabilities across various products, it does not explicitly describe which specific Microsoft product Microsoft characterizes as being "at the forefront of AI-powered software development."
```

---

### q_078 (factual) — RETRIEVAL MISS (correct chunk not in top-5)

**Question**: What risk does Google identify related to its 'Google' trademark, and what consequence could result if this risk materializes?

**Expected source**: google FY2024

**Expected snippet**: there is a risk that the word "Google" could become so commonly used that it becomes synonymous with the word "search."...

**Retrieved** (company_year): google_2023, google_2024, google_2024, google_2023, google_2024

**Metrics**: recall@5=0.0, citation=0.0, faithfulness=1.0, relevancy=0.8977130807643482

**Model answer**:
```
Based on the context provided, Google identifies the following risk and consequence related to its 'Google' trademark:

**Risk:** There is a risk that the word "Google" could become so commonly used that it becomes synonymous with the word "search." Additionally, while some courts have ruled that "Google" is a protectable trademark, it is possible that other courts, particularly those outside of the U.S., may reach a different determination [3][4].

**Consequence:** If this risk materializes and
```

---

### q_081 (multi_hop) — RETRIEVAL MISS (correct chunk not in top-5)

**Question**: How did Google's YouTube ads revenue change from 2022 to 2024, and what was the total growth over that three-year period?

**Expected source**: google FYmultiple

**Expected snippet**: [Google 2023 10-K]: YouTube ads 29,243 31,510. [Google 2024 10-K]: YouTube ads 29,243 31,510 36,147...

**Retrieved** (company_year): google_2024, google_2023, google_2024, google_2023, google_2023

**Metrics**: recall@5=0.0, citation=0.0, faithfulness=0.75, relevancy=0.8781520607831719

**Model answer**:
```
Based on the provided context, I can tell you about YouTube ads revenue changes in two of the three years:

- From 2022 to 2023: YouTube ads revenues increased $2.3 billion [4]
- From 2023 to 2024: YouTube ads revenues increased $4.6 billion [1]

**Total growth from 2022 to 2024: $6.9 billion** ($2.3 billion + $4.6 billion)

Both years showed growth driven by brand advertising and direct response advertising products, with increased spending by advertisers [4][1].
```

---

### q_087 (multi_hop) — RETRIEVAL MISS (correct chunk not in top-5)

**Question**: How did Microsoft's and Netflix's basic earnings per share compare in fiscal 2024, and how did each company's basic EPS evolve across the three-year period reported in their fiscal 2024 filings?

**Expected source**: multiple FY2024

**Expected snippet**: [Microsoft]: Basic $ 11.86 $ 9.72 $ 9.70. [Netflix]: Basic earnings per share $ 20.28 $ 12.25 $ 10.10...

**Retrieved** (company_year): netflix_2023, apple_2023, nvidia_2024, netflix_2023, microsoft_2024

**Metrics**: recall@5=0.0, citation=0.0, faithfulness=0.42857142857142855, relevancy=0.0

**Model answer**:
```
I don't have enough information in the provided context to answer this question.

While the context includes Netflix's basic earnings per share data for 2023, 2022, and 2021 [1][4], it does not contain Microsoft's basic earnings per share figures. The Microsoft 2024 10-K excerpt [5] only shows the beginning of their earnings per share note and does not include the actual EPS calculations or data.

To answer your question, I would need:
1. Microsoft's basic EPS for fiscal 2024 and the prior two y
```

---

### q_088 (factual) — RETRIEVAL MISS (correct chunk not in top-5)

**Question**: What is Netflix's primary source of revenue, and how many operating segments does the company report?

**Expected source**: netflix FY2024

**Expected snippet**: We operate as one operating segment. Our revenues are primarily derived from monthly membership fees for services related to streaming content to our members....

**Retrieved** (company_year): netflix_2024, nvidia_2023, netflix_2024, tesla_2023, netflix_2023

**Metrics**: recall@5=0.0, citation=0.0, faithfulness=0.9166666666666666, relevancy=0.0

**Model answer**:
```
Based on the provided context:

**Primary Source of Revenue:**
Netflix's primary source of revenue is from providing access to its streaming service to members. According to the context, "The Company retains control over service delivery to its members" and revenue is recognized as members pay for access [1]. The company also earns revenue from "advertisements presented on its streaming service, consumer products, live events and various other sources," but these appear to be secondary revenue s
```

---

### q_095 (negation) — RETRIEVED BUT NOT CITED (right chunk pulled, model cited wrong source)

**Question**: Do Costco Executive members receive cashback as a cash payout, or in a different form?

**Expected source**: costco FY2023

**Expected snippet**: In most countries, the Company's Executive members qualify for a 2% reward on qualified purchases, subject to an annual maximum value, which does not expire and is redeemable at Costco warehouses....

**Retrieved** (company_year): costco_2023, costco_2024, costco_2024, costco_2024, costco_2023

**Metrics**: recall@5=1.0, citation=0.0, faithfulness=0.375, relevancy=0.973111153045728

**Model answer**:
```
Based on the provided context, Costco Executive members do not receive cashback as a cash payout. Instead, they receive it in a different form.

According to the context, "Executive members earn a 2% reward on qualified purchases (generally up to a maximum reward of $1,000 per year), redeemable at Costco warehouses" [2]. The rewards are specifically described as "Executive member 2% reward certificates" [5] that can be redeemed at Costco warehouses, rather than being paid out as cash.
```

---

### q_099 (multi_hop) — RETRIEVAL MISS (correct chunk not in top-5)

**Question**: In fiscal 2024, how did Google's YouTube ads revenue compare to Netflix's streaming revenue, and which was larger?

**Expected source**: multiple FY2024

**Expected snippet**: [Google]: YouTube ads ... 36,147. [Netflix]: Streaming revenues $ 39,000,966...

**Retrieved** (company_year): google_2024, google_2024, google_2023, google_2023, google_2023

**Metrics**: recall@5=0.0, citation=0.0, faithfulness=1.0, relevancy=0.0

**Model answer**:
```
I don't have enough information in the provided context to answer this question.

The context contains information about Google's YouTube ads revenue growth in fiscal 2024 (an increase of $4.6 billion from 2023 to 2024) [1], but it does not include any information about Netflix's streaming revenue. To answer your question comparing these two companies' revenues, I would need data from Netflix's financial filings, which is not provided in this context.
```

---
