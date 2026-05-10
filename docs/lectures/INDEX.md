# Lecture Index

Reference index for the 14 lecture markdown files in this directory. Read this
file first when you need to look up anything taught in class — it points to the
right lecture without scanning every file.

## Course

- 2190436 Data Warehousing
- 2190518 Data Engineering and Big Data
- Instructor: Prof. Peerapon Vateekul, Chulalongkorn University

## Quick Lookup by Topic

| If you need to know about… | Go to |
|---|---|
| What a data warehouse is, OLTP vs OLAP, ETL vs ELT, star vs snowflake, fact/dim basics, surrogate keys | `01 - Dimensional Modeling.md` |
| 4-step dimensional design process, degenerate dimensions, factless fact tables, role-playing dimensions, retail-sales case study | `02 - Retail Sales.md` |
| Fact table types (transaction / periodic snapshot / accumulating snapshot), conformed dimensions, value chain, bus matrix | `03 - Inventory (Fact Tables and Conformed Dimension).md` |
| Slowly Changing Dimensions (SCD Type 1 / 2 / 3, hybrid), single vs multiple fact tables, contract-term modeling | `04 - Procurement (Slowly Changing Dimension).md` |
| Junk dimensions, order management process modeling | `05 - Order Management (Junk Dimension).md` |
| Rapidly Changing Dimensions, outriggers, mini-dimensions (SCD4/5), multi-valued dimensions, bridge tables | `06 - CRM (Rapidly Changing Dimension).md` |
| The 4 Vs of Big Data, data lake vs data warehouse, big-data analytics process, infrastructure / storage / processing layers, Hadoop vs Spark overview | `07 - Intro to Big Data.md` |
| NoSQL types (key-value, document, column-store, graph) and when to use each | `08 - NoSQL.md` |
| Hive (SQL on Hadoop), HiveQL vs MapReduce, Tez, managed vs external tables, columnar storage, Parquet vs ORC | `09 - Hive.md` |
| Redis (key-value store) — string / list / set / sorted set / hash data types, common commands, scaling (persistence, replication, partitioning, failover), AWS key-value comparison | `10 - Redis.md` |
| Apache Spark fundamentals — RDDs, transformations vs actions, DataFrames, Spark vs Hadoop, PySpark basics | `11 - Spark Basic.md` |
| Spark ML pipelines (Estimator, Transformer, Pipeline), DataFrame ML API, supported algorithms, Spark ML vs MLlib | `12 - Spark ML.md` |
| Apache Airflow — DAGs, operators (Bash / Python / Branch), scheduling, medallion architecture, EC2 vs MWAA | `13 - Airflow.md` |
| Apache Kafka — topics, partitions, producers, brokers/replicas, consumers and consumer groups, decoupled pipelines, EC2 vs MSK | `14 - Kafka.md` |

## Lecture-by-Lecture Summary

### Midterm (DW design — Kimball-style dimensional modeling)

- **`01 - Dimensional Modeling.md`** (43 slides) — Course intro, DW vs DB,
  ETL vs ELT, data warehouse components (sources / staging / presentation /
  access), DW storage options (RDBMS / cube / columnar), star vs snowflake,
  facts and dimensions, grain, surrogate keys.
- **`02 - Retail Sales.md`** (73 slides) — The canonical Kimball 4-step design
  process (business process → grain → dimensions → facts), retail-sales case
  study, design techniques: degenerate dimensions, factless fact tables,
  role-playing dimensions.
- **`03 - Inventory (Fact Tables and Conformed Dimension).md`** (47 slides) —
  Three fact-table types (transaction / periodic snapshot / accumulating
  snapshot) using inventory as the worked example, plus conformed dimensions
  and the enterprise bus matrix.
- **`04 - Procurement (Slowly Changing Dimension).md`** (22 slides) — SCD
  patterns (Type 1 overwrite, Type 2 add row, Type 3 add column, hybrid
  Type 1+2 attributes), and when to use multiple vs single fact tables.
- **`05 - Order Management (Junk Dimension).md`** (3 slides) — Short module
  introducing junk dimensions in an order-management context.
- **`06 - CRM (Rapidly Changing Dimension).md`** (24 slides) — Outriggers,
  mini-dimensions for rapidly changing attributes (SCD4 / SCD5), and
  multi-valued dimensions handled via bridge tables.

### Final (Big Data, NoSQL, processing engines, orchestration, streaming)

- **`07 - Intro to Big Data.md`** (24 slides) — Big Data definition (4 Vs),
  data lake vs data warehouse revisit, end-to-end big-data analytics process,
  infrastructure / NoSQL storage / processing engines (Hadoop on disk vs
  Spark in-memory) / analytics-and-viz layers.
- **`08 - NoSQL.md`** (31 slides) — The four NoSQL families: key-value
  (Redis-style), document (Mongo-style), column-store (Cassandra/HBase), and
  graph (Neo4j) — characteristics, examples, and selection criteria.
- **`09 - Hive.md`** (18 slides) — SQL-on-Hadoop with Hive, HiveQL
  compilation to MapReduce vs Tez, managed vs external tables, row-based vs
  column-based storage, Parquet vs ORC.
- **`10 - Redis.md`** (32 slides) — Deep dive on Redis as a KV store: all
  five value types (String, List, Set, Sorted Set, Hash) with command
  reference, plus scaling (persistence, replication, partitioning, failover)
  and an AWS KV-store comparison.
- **`11 - Spark Basic.md`** (40 slides) — Apache Spark fundamentals: why
  Spark, Spark vs Hadoop, RDD model, transformations vs actions, DataFrame
  API basics, PySpark coding patterns.
- **`12 - Spark ML.md`** (33 slides) — Spark's ML pipeline API: Estimators,
  Transformers, Pipelines, DataFrame-based ML vs the older MLlib RDD API,
  example feature-transform → classifier flow, supported algorithms.
- **`13 - Airflow.md`** (23 slides) — Workflow orchestration with Apache
  Airflow: DAGs, common operators (Bash, Python, Branch), scheduling and
  cron presets, medallion architecture pattern, EC2 self-managed vs Amazon
  MWAA.
- **`14 - Kafka.md`** (30 slides) — Streaming with Apache Kafka: topics,
  partitions, producers / brokers / consumers, consumer groups, decoupled
  pipelines, log aggregation / shipping / event-driven use cases, EC2
  self-managed vs Amazon MSK.

## How to Use This Index

1. Start here — scan the **Quick Lookup by Topic** table for the keyword
   you care about.
2. Open the matching lecture file. Each lecture is faithfully transcribed
   slide-by-slide with `## Slide-Title` headings and `*— Slide N —*`
   markers, so you can search within a file or jump to a specific slide.
3. If a topic spans multiple lectures (e.g., SCDs appear in lectures 04 and
   06; data lake vs DW appears in 01 and 07), read both — the later
   lectures tend to extend or revisit ideas from earlier ones.

## Source

These markdown files were extracted from PDF slide decks under
`slides/midterm/` (lectures 01–06) and `slides/final/` (lectures 07–14).
The PDFs remain the authoritative source — the markdown is for fast text
search and reference.
