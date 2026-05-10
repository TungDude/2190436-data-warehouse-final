# Project: DW/Big Data Implementation (20%)

**Coexist between Traditional DE & Modern DE (Big Data)**

- 2190436 Data Warehousing
- 2190518 Big Data & Data Engineering
- 17 Mar 2026 (2025/2)

---

## Slide 2 — Objective: Full DW pipeline on AWS + Big Data

**Coexist between Traditional DE & Modern DE (Big Data)**

Pipeline stages:

| Stage | AWS services |
|---|---|
| Data Sources | Amazon RDS / S3 (Parquet, SQL, JSON, CSV) |
| Data Storage / ETL | Amazon RDS, Amazon S3, AWS Glue, EMR, ElastiCache |
| Front-End | Amazon QuickSight |

Analytics maturity referenced (Hindsight → Insight → Foresight): Diagnostic → Predictive Analytics → Prescriptive Analytics → Optimization.

---

## Slide 3 — You can choose your own data source

- It can be public or private data.
- For example:
  - COVID-19
  - PM2.5
  - Scrape data from web by yourselves
  - https://data.go.th/
  - https://www.kaggle.com/datasets
  - https://data.world/

---

## Slide 4 — Score overview (Total 20%)

| # | Component | Weight |
|---|---|---:|
| 1 | Data source | 2% |
| 2 | DW | 4% |
| 3 | Big Data | 4% |
| 4 | Automate Workflow | 1% |
| 5 | BI | 4% |
| 6 | Presentation 2 videos | 5% (2.5% × 2) |

---

## Slide 5 — Project Details

### 1) Data Collection & Source DB [2%]

- Load data into a source database.
- Use interesting & realistic datasets.
- Prefer multiple data sources (not just one CSV).
- Data integration / joins are encouraged.

### 2) Data Warehouse & ETL [4%]

- Design DW using 4-step dimensional modeling.
- Implement ETL with Amazon Glue.
- Include ≥ **1 fact table** with conformed bus matrix (no aggregate fact).
- All dimension tables must implement SCD.
- Design correctness and DW techniques will be evaluated.

---

## Slide 6 — Project Details (cont.)

### 3) Big Data Component [4%]

Include one Big Data technology **with justification**, e.g.

- Spark → large data (Volume)
- Data Lake → multiple formats (Variety)
- KV database → fast lookup, infrequent updates

### 4) Automatic Workflow [1%]

Schedule pipelines using Glue Scheduler and/or Airflow.

### 5) BI Dashboard [4%]

- Create **≥ 2 dashboards** (e.g., Overview → Detail).
- Implement using Amazon QuickSight.

---

## Slide 7 — Project Details (cont.)

### 6) Presentation [5%] (2 videos)

- **Video 1 (≤15 min) — Data Warehouse Designer / Data Engineer**
  - Data preparation, DW design, ETL architecture, and demo Glue ETL running.
- **Video 2 (≤10 min) — Business Analyst**
  - DW overview, QuickSight dashboards, key business insights.

---

## Slide 8 — More Details

- Maximum 4 students per group (can be 1, 2, 3 students per group, **CANNOT be 5!**).
- By **Fri 8th May 2026**, the following items must be submitted on MyCourseVille:
  - Google Drive Link to all your resources (BI project, overall diagram, data source files, etc.)
    - Set sharing to **Anyone with link**.
  - YouTube Video Link for Video 1 (15 mins)
    - Set visibility to **Public**.
  - YouTube Video Link for Video 2 (10 mins)
    - Set visibility to **Public**.

---

## Slide 9 — FAQ

**Q1: Do we need to use the provided AWS services?**

A: Yes. You should use the AWS services provided for the course because the instructors (admins) can access your assigned AWS project account to review and grade your work.

**Q2: For DW [4%] and Big Data [4%], what is the main evaluation criterion?**

A: The score will be based on **(1) effort and (2) techniques** used. For example, a very simple workflow (e.g., Data Source → Change Schema → Target Data) would receive fewer points compared to a more complex and well-designed pipeline with multiple processing steps. More sophisticated implementations will receive higher scores.
