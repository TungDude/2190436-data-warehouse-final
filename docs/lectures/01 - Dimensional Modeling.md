# Dimensional Modeling

_Total slides: 43_

---

## Cover

Dimensional Modeling
2190436 Data Warehousing (Year 4)
2190518 Data Engineering and Big Data (Year 3)
Prof. Peerapon Vateekul, Ph.D.
Department of Computer Engineering,
Faculty of Engineering, Chulalongkorn University
peerapon.v@chula.ac.th

*— Slide 1 —*

---

## Outline

- Recap of Introduction to Data Warehousing
- Data Warehouse Components
  - Data Warehouse (ETL) vs. Data Lake (ELT)
- Dimensional Modeling
*— Slide 2 —*

---

## RECAP OF INTRO TO DW

Database, Data Warehouse, and Business Intelligence, Machine Learning

*— Slide 3 —*

---

## What is Data Warehouse?

- A database specifically
designed for data analysis

*— Slide 4 —*

---

## What is Data Warehouse? (cont.)

- DW is a database specifically designed for OLAP (analytics).
- The design technique is called “Dimension Modeling”.
- It allows denormalization (duplication).
- DW exists with DB, and it comes after DB.
DB (OLTP)

- Fast write
- Normalization
- Simple queries
DW (OLAP)

- Fast read
- Dimensional modeling
- Complex queries
*— Slide 5 —*

---

## Database (DB) and Data Warehouse (DW)

- We transform Databases (OLTP) to Data Warehouse (OLAP) by subjects using star-schema concept.
Product Line Product Type Product Customer Type Customer Order Line Sales Area Sales Rep Order Header Sales Staff Order Fact Products Customer Time Orders OLTP System (frequent writing, slow long query) Orders OLAP System (fast analytical query)

*— Slide 6 —*

---

## Data engineering: data acquisition, cleansing and storing à “data pipeline”

Data Pipeline DB (OLTP)

- Fast write
- Normalization
- Simple queries
DW (OLAP)

- Fast read
- Dimensional modeling
- Complex queries
ETL (Extract-Transform-Load) DE a.k.a. “data pipeline”

*— Slide 7 —*

---

## About this course (50%:50%)

2190436 Data Warehousing

- DW design
2190518 Data Engineering and Big Data

- Data Pipeline, Data Lake
- Big Data Processing (Spark)
- Data Ingestion, Workflow Automation
DW DE Big Data

*— Slide 8 —*

---

## About the class (cont.)

- Books
  - Ralph Kimball and Margy Ross, The Data Warehouse Toolkit: The Definitive Guide to Dimensional
Modeling (Third Edition). John Wiley & Sons, 2013.

  - http://www.kimballgroup.com/
*— Slide 9 —*

---

## Conclusion

Big Data = raw materials → DE (ETL) = processing → DW = showroom (for analytics)

- DW is a database for reporting and analysis. It is suitable
for a complex query. [Data]

  - Main class objective: Be able to design DW similar to DB class
- DE aims to design and build systems that move, transform,
and serve data at scale. [Data Pipeline (ETL)]

- Big Data refers to complex data characterized by the 4 Vs:
Volume, Velocity, Variety, and Veracity. [Data Lake (ELT), Big Data Processing]

- BI is a process of managing data and analyzing it in order
to help in a decision process. [What happened? Why?] DW DE Big Data

*— Slide 10 —*

---

## DATA WAREHOUSE COMPONENTS

*— Slide 11 —*

---

## Goals of Data Warehouse (Centralized Data)

- Make information easily accessible and
understandable

  - Support endless combination (slicing and dicing)
  - Minimal waiting time
- Present information consistently
  - Data must be carefully assembled and cleaned from a
variety of sources around the organization

- Do not interfere with local processing at sources
  - Information copied at warehouse can modify,
annotate, summarize, etc.

- Serve as a foundation for improving decision
making DB DW ETL = Extract Transform Load

*— Slide 12 —*

---

## More about DW

- Stored a collection of diverse data
  - Data integration
  - Single repository of information
- Subject-oriented
  - Used for decision-support, analysis, data mining, etc.
- Optimized differently from transactional-oriented database
- Large volume of data
- Non-volatile (update infrequent; not often)
  - Historical data
  - May be append-only
*— Slide 13 —*

---

## Components of Data Warehouse

1) Operational Source Systems 2) Data Staging Area 3) Data Presentation Area 4) Data Access Tools DB Server DW Server Data Staging Server (optional) Analytics Server

*— Slide 14 —*

---

## 2) Data Staging Area

- The data staging area is both a storage area and a set of processes
referred to as extract-transformation-load (ETL)

  - Extraction
- Reading and understanding the source data and copying the data needed for the DW into the
staging area for further manipulation

  - Transformation
- Cleansing the data
  - Correct misspellings, resolve domain conflicts, deal with missing elements, parse into standard
formats

- Combining data from multiple sources
  - Load
- Replicating the dimension tables and fact tables
*— Slide 15 —*

---

## ETL Tools

*— Slide 16 —*

---

## ETL Tools (cont.)

*— Slide 17 —*

---

## 3) Data Presentation Area (Data Warehouse)

- Data Mart is a small DW supporting a single business process.
- All data marts must be built using common dimensions (conformation).
Sales Staff Order Fact Products Customer Time Orders Data Mart Sales Orders HR Global Data Warehouse

*— Slide 18 —*

---

## 3) Data Presentation Area (DW) – (cont.)

- DW can be implemented in (1) RDBMS, (2) Cube, or (3) Columnar DB (Modern DW).
- An online analytical processing (OLAP) cube is multidimensional database, whose physical
implementation differs from relational database. Tip! Think of it as “array”.

- OLAP cube is faster and more suitable for DW design (dimensional modeling) than “relational
database”.

  - Techniques: index, pre-calculation, aggregation, etc. to make it faster
- ROLAP (Relational OLAP cube)
- MOLAP (Multi-dimensional OLAP cube)
- HOLAP (Hybrid OLAP cube)
- Multi-Dimensional eXpressions (MDX)
*— Slide 19 —*

---

## DW Storage

1) Traditional DBMS 2) Cube 3) Columnar DB

*— Slide 20 —*

---

## 4) Data Access Tools

Data Warehouse

*— Slide 21 —*

---

## https://www.grazitti.com/blog/data-lake-vs-data-warehousewhich-one-should-you-go-for/

*— Slide 22 —*

---

## ETL

When to use ELT? • When you need to store data fast

- When you need raw historical data for
future analysis

- When you need a flexible data
integration process ELT

*— Slide 23 —*

---

## ETL

ELT External table

*— Slide 24 —*

---

## DL & DW can be used together.

25 https://hectorv.com/category/data-engineering/

*— Slide 25 —*

---

## DIMENSIONAL MODELING

*— Slide 26 —*

---

## Dimensional Modeling

- Dimensional Modeling is how to design DW in order to make
the data suitable for analysis.

  - Know What? Status called “Measures (Facts)”
  - Know Why? Factors, Causes called “Dimensions”
*— Slide 27 —*

---

## Dimensional Modeling (cont.)

- If you were a CEO for 7-11, then …
- What measure (facts) can be used to identify your business status?
  - Total sale, total receipts, total profit
  - Average spending per receipt (ATV: average transaction value)
- Which factors (dimensions) do you want to analyze?
  - Date Period
  - Store Location
  - Product
*— Slide 28 —*

---

## Dimensional Modeling Components

- Types of tables in DW
1. Fact Tables 2. Dimension Tables

- Types of schema in DW
1. Star schema 2. Snowflake schema Sales Staff Order Fact Products Customer Time Order Star Schema

*— Slide 29 —*

---

## Star Schema

Time_key day-of-week month quarter year holiday_flag Time_key product_key store_key dollars_sold units_sold dollars_cost Total_sales Product_key description brand category Store_key store_name address floor_plan_type Sales Fact Date Dimension Product Dimension Store Dimension

*— Slide 30 —*

---

## Star Schema (cont.)

StoreKey StoreName Province Region Country StoreSize 201 (PK) CU BKK Central TH Small ProductKey ProductName Brand Flavor ProductCategory 25 (PK) Green tea Oishi No sugar Beverage DateKey Date Day Month Year DoW IsWeekEnd IsHoliday 134 (PK) 21/01/2020 20 Jan 2020 Tuesday WeekDay Non-Holiday Date_Dim Product_Dim Store_Dim Dimensions Sale Fact Table StoreKey ProductKey DateKey Unit_sold TotalSale TotalProfit 201 (PK) 25 (PK) 134 (PK) 400 12,000 2,000 Foreign Keys Measures Grain, granularity: Daily sale per each product/store Time_key day-of-week month quarter year holiday_flag Time_key product_key store_key dollars_sold units_sold dollars_cost Total_sales Product_key description brand category Store_key store_name address floor_plan_type Sales Fact Date Dimension Product Dimension Store Dimension

*— Slide 31 —*

---

## Surrogate Key

- It is just a sequence of integers.
- It is not a PK in the source DB (a natural key).
- It is generated in DW.
- It is just used to join between a fact table and dimensions.
- Why? (Benefits)
  - Efficiency (speed and space)
  - An operational code
- Key = 888 means “Date to be determined”
- Key = 999 means “Date not applicable (missing)”
  - Data Partitioning
- An order of data can be determined from the sequence (key).
*— Slide 32 —*

---

## Star vs. Snowflake schemas

- Star schema is a dimension model that all
dimension tables directly connect to fact tables.

- Snowflake schema is a dimension model
that some dimension tables may not directly connect to fact tables. Star schema Snowflake schema

*— Slide 33 —*

---

## 1) Fact Table

StoreKey StoreName Province Region Country StoreSize 201 (PK) CU BKK Central TH Small ProductKey ProductName Brand Flavor ProductCategory 25 (PK) Green tea Oishi No sugar Beverage DateKey Date Day Month Year DoW IsWeekEnd IsHoliday 134 (PK) 21/01/2020 20 Jan 2020 Tuesday WeekDay Non-Holiday Date_Dim Product_Dim Store_Dim Dimensions Sale Fact Table StoreKey ProductKey DateKey Unit_sold TotalSale TotalProfit 201 (PK) 25 (PK) 134 (PK) 400 12,000 2,000 Foreign Keys Measures Grain, granularity: Daily sale per each product/store Time_key day-of-week month quarter year holiday_flag Time_key product_key store_key dollars_sold units_sold dollars_cost Total_sales Product_key description brand category Store_key store_name address floor_plan_type Sales Fact Date Dimension Product Dimension Store Dimension

*— Slide 34 —*

---

## Fact Table

- Is the primary table in a dimensional model
- Facts are numeric measurements (values) that represent a specific business
aspect or activity

- The “best” facts are numeric, continuously valued and additive.
- Facts can be computed or derived at run-time (metrics).
- Have two or more foreign keys(FK) that connect to the dimension table’s
primary keys

  - Satisfy referential integrity
- Generally, it has own primary key (called a composite or concatenated key)
made up of a subset of the foreign keys

- Express the many-to-many relationships between dimensions
Daily Sales Fact Table Date Key(FK) Product Key(FK) Store Key(FK) Unit Sold Total Sale Total Profit Sample Fact Table

*— Slide 35 —*

---

## Grain or Granularity

- Grain refers to each row in the fact table.
- A level of details associated with measurements in the fact table.
- For example, grain definitions can include the following items:
- A line item on a grocery receipt
- A monthly snapshot of a bank account statement
- A single airline ticket purchased on a day
- Atomic is the lowest granularity.
- There are no more lower details of measures.
- For example, “total sale” and “item sale”, which one is atomic data?
Daily Sales Fact Table Date Key(FK) Product Key(FK) Store Key(FK) Unit Sold Total Sale Total Profit Sample Fact Table

*— Slide 36 —*

---

## 2) Dimension Tables

StoreKey StoreName Province Region Country StoreSize 201 (PK) CU BKK Central TH Small ProductKey ProductName Brand Flavor ProductCategory 25 (PK) Green tea Oishi No sugar Beverage DateKey Date Day Month Year DoW IsWeekEnd IsHoliday 134 (PK) 21/01/2020 20 Jan 2020 Tuesday WeekDay Non-Holiday Date_Dim Product_Dim Store_Dim Dimensions Sale Fact Table StoreKey ProductKey DateKey Unit_sold TotalSale TotalProfit 201 (PK) 25 (PK) 134 (PK) 400 12,000 2,000 Foreign Keys Measures Grain, granularity: Daily sale per each product/store Time_key day-of-week month quarter year holiday_flag Time_key product_key store_key dollars_sold units_sold dollars_cost Total_sales Product_key description brand category Store_key store_name address floor_plan_type Sales Fact Date Dimension Product Dimension Store Dimension

*— Slide 37 —*

---

## Dimension Tables

- Are integral companions to a fact table
- Contain the textual descriptors of the business
- Have many columns or attributes
- Defined by single primary key (PK)
- Aim to minimize the use of codes in our dimension
tables by replacing them with more verbose textual attributes

  - Operational codes often have intelligence
embedded in them

- Typically, they are highly denormalized
Product Dimension Table Product Key(PK) Product Description SKU Number(Natural key) Brand Description Category Description Department Description Package Type Description Package Size Fat Content Description Diet Type Description Weight Weight Units of Measure Storage Type Shelf Life Type Shelf Width Shelf Height Shelf Depth … and many more Sample dimension Table

*— Slide 38 —*

---

## Dimension Table Characteristics

- Describes Business Entities
- Contains Attributes That Provide Context to Numeric Data
- Presents Data Organized into Hierarchies
- Contains member names, hierarchy definition and other attributes
*— Slide 39 —*

---

## Dimension Hierarchies

- Dimensions can be organized into hierarchies
  - E.g., Time dimension:
- days ® weeks ® quarters
  - E.g., Product dimension:
- product ® product line ® brand
*— Slide 40 —*

---

## Conventional Date Dimension

Attribute Value Date 12/25/1999 Day of month 25 Name of day Saturday Week of year 51 Week of month 4 Month of year 12 Name of month December Quarter of year 4 Year 1990

*— Slide 41 —*

---

## CONCLUSION

*— Slide 42 —*

---

## Conclusion

- Recap about data warehousing & our class
- Data warehouse components
  - DB à ETL à DW (Cube) à Analysis
  - Data Warehouse (ETL) vs. Data Lake (ELT)
- Dimensional Modeling
  - Fact, Dimensions
  - Star schema & snowflake schema
*— Slide 43 —*

---
