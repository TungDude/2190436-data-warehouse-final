# Intro to Big Data

_Total slides: 24_

---

## Cover

Introduction to Big Data
2190436 Data Warehousing (Year 4)
2190518 Data Engineering and Big Data (Year 3)
Prof. Peerapon Vateekul, Ph.D.
Department of Computer Engineering,
Faculty of Engineering, Chulalongkorn University
peerapon.v@chula.ac.th

*— Slide 1 —*

---

## Outline

- Introduction to Big Data (recap)
- Data Lake
- Big Data Analytics (Processing)
  - 1) Infrastructure: Distributed System
  - 2) Big Data Storage: NoSQL
  - 3) Data Analytics: Spark vs. Hadoop
  - 4) Data Visualization

*— Slide 2 —*

---

## Big Data Explosion

What Happens in an Internet Minute? (SOURCE: INTEL)

- 204 million Emails sent
- 47,000 App downloads
- $83,000 In sales
- 20 million Photo views
- 3,000 Photo uploads
- 61,141 Hours of music
- 320 New twitter accounts
- 100,000 New tweets
- 1,300 New mobile users
- 100+ New Linkedin accounts
- 277,000 Logins
- 6 million Facebook views
- 2+ million Search queries
- 30 Hours of videos uploaded
- 1.3 million Video views

*— Slide 3 —*

---

## Big Data Explosion (cont.)

Diagram referencing the 4Vs of Big Data.

*— Slide 4 —*

---

## Big Data Explosion (cont.)

Diagram referencing the 4Vs of Big Data.

*— Slide 5 —*

---

## Data Lake: Unstructured Data

- With unstructured data, the schema is not known beforehand, so data warehouse storage cannot be designed in advance.

| Aspect | Data Warehousing (Design -> Store) | Data Lake (Store -> Design) |
|---|---|---|
| Purpose | BI, Reporting | Big Data, ML, Exploration |
| Data Types | Structured | Structured, Semi-structured, Unstructured |
| Schema | Schema-on-Write | Schema-on-Read |
| Processing | ETL (Extract-Transform-Load) | ELT (Extract-Load-Transform) |
| Storage Cost | Higher | Lower |
| Performance | Optimized for analytics | Depends on processing tools |
| Tools | Snowflake, Redshift, BigQuery | Hadoop, Spark, Databricks |

*— Slide 6 —*

---

## ETL (DW) vs. ELT (Data Lake)

| Aspect | ETL | ELT |
|---|---|---|
| Transform | Before load | After load |
| Data stored | Clean data | Raw + transformed |
| When schema applied? | Write | Read |
| Storage engine | Traditional DW | Cloud DW / Lake |
| Scalability | Limited | High |

*— Slide 7 —*

---

## Data Lake: Unstructured Data

Diagram of data lake architecture.

*— Slide 8 —*

---

## Data Lake: Unstructured Data

Diagram referencing the 4Vs of Big Data.

*— Slide 9 —*

---

## Big Data Analytics (Processing)

- It is a process of examining Big Data to uncover useful information and knowledge.
- More data means better decision!

Big Challenges:

- External Data
- Unstructured Data

*— Slide 10 —*

---

## Big Data Analytics Process

- 1: Infrastructure
- 2: Data Storage
- 3: Data Analytics
- 4: Data Visualization

*— Slide 11 —*

---

## 1) Infrastructure

- Vertical Scaling (Scale-up)
- Horizontal Scaling (Scale-out)

*— Slide 12 —*

---

## 2) Big Data Storage: NoSQL

Diagram of NoSQL database types.

*— Slide 13 —*

---

## 2) Big Data Storage: NoSQL (cont.)

- Redis
- Data Warehouse (Google BigQuery)
- Neo4j
- MongoDB

*— Slide 14 —*

---

## 3) Big Data Processing

Optimize model by parallelizing jobs and reducing iterations

*— Slide 15 —*

---

## Big Data Processing Comparison

| Topic | Hadoop (2010's) | Spark + Data Lake (2015-2020) | Serverless (Cloud) / Lakehouse (2020+) |
|---|---|---|---|
| Storage | HDFS | S3 / Data Lake | S3 (files); Iceberge / Delta (metadata; AWS Glue Data Catalog) |
| Compute | MapReduce | Spark (only compute engine!) | Trino = "read & analyze"; Spark = "build & process"; Flink = "real-time processing" |
| SQL | Hive | Hive / Spark SQL | Athena / BigQuery / Snowflake |

*— Slide 16 —*

---

## 3.1) What is Hadoop? (on disk)

- A scalable fault-tolerant distributed system for (1) data storage and (2) processing
- Completely written in java
- Open source & distributed under Apache license
- Two main components
  - Map/Reduce System
  - Hadoop Distributed File System (HDFS)

*— Slide 17 —*

---

## Hadoop Distribution

- Deployment
- Configuration
- Management
- Google Cloud Dataproc
- Google Cloud Storage (GCS)

*— Slide 18 —*

---

## Hadoop Distribution (cont.)

Reference to Cloudera and Hortonworks merger.

*— Slide 19 —*

---

## 3.2) Spark (in-memory)

- Apache Spark is a general-purpose cluster in-memory computing system (no data storage)
- Support Hadoop environment
- Provide high-level APIs in Java, Scala, and Python
- Provide optimized engine that supports general execution graphs
- Provide various level tools, e.g., SparkQL, SparkML
- If query using SQL, it also supports in-database.

*— Slide 20 —*

---

## Big Data Solution (cont.)

In-memory & Distributed Computing

- Resilient Distributed Datasets (RDD)
- RAM across COM 1, COM 2, COM 3, COM 4, COM …

*— Slide 21 —*

---

## Big Data Solution (cont.)

Diagram of PySpark architecture.

*— Slide 22 —*

---

## 4) Data Analytics & Data Visualization

*— Slide 23 —*

---

## 4) Search Engine (cont.)

- Open-source, broadly-distributed, readily scalable search engine
- Fast direct access to the data
- To achieve fast search responses because, instead of searching the text directly, it searches an index instead.

*— Slide 24 —*
