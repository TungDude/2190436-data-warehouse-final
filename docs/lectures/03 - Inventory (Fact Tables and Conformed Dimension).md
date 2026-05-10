# Ch3 - Inventory (Fact Tables and Conformed Dimension)

_Total slides: 47_

---

## Cover

Fact-Tables and Conformed Dimension
Chapter 3: Inventory
Peerapon Vateekul, Ph.D.
Dept. of Computer Engineering, Faculty of Engineering, Chulalongkorn University
peerapon.v@chula.ac.th
Thanks to
Associate Professor Kitsana Waiyamai, Ph.D.

*— Slide 1 —*

---

## Outlines

- Types of fact tables
- Enterprise DW Design
  - Top-down VS Bottom-up
- DW bus architecture and matrix
- Conformed dimensions
- Drill-across
- Outer Join
*— Slide 2 —*

---

## Part1: Types of Fact Tables

*— Slide 3 —*

---

## 7-Eleven:

- A grocery retailer with many stores
- Warehouses & Stores
Retailer Issues Purchase Order Deliveries at Retailer Warehouse Retailer Warehouse Inventory Deliveries at Retail Store Retail Store Inventory Retail Store Sales Retailer issues purchase order to product manufacturer

*— Slide 4 —*

---

## Retailer Issues

Purchase Order Deliveries at Retailer Warehouse Retailer Warehouse Inventory Deliveries at Retail Store Retail Store Inventory Retail Store Sales Products are delivered to retailer's warehouse

*— Slide 5 —*

---

## Retailer Issues

Purchase Order Deliveries at Retailer Warehouse Retailer Warehouse Inventory Deliveries at Retail Store Retail Store Inventory Retail Store Sales Products are held in inventory

*— Slide 6 —*

---

## Retailer Issues

Purchase Order Deliveries at Retailer Warehouse Retailer Warehouse Inventory Deliveries at Retail Store Retail Store Inventory Retail Store Sales Delivery is made to individual stores

*— Slide 7 —*

---

## Retailer Issues

Purchase Order Deliveries at Retailer Warehouse Retailer Warehouse Inventory Deliveries at Retail Store Retail Store Inventory Retail Store Sales Retail store inventory

*— Slide 8 —*

---

## Retailer Issues

Purchase Order Deliveries at Retailer Warehouse Retailer Warehouse Inventory Deliveries at Retail Store Retail Store Inventory Retail Store Sales Sale of products

*— Slide 9 —*

---

## Value Chain Integration

- Aim to monitor the performance
  - For each process and overall
- Each process has unique:
  - Metrics, time interval, granularity, and dim.
- Management of the value chain
  - Low-level: analyze only their local data marts
  - High-level: need to look across the business (enterprise DW)
Retailer Issues Purchase Order Deliveries at Retailer Warehouse Retailer Warehouse Inventory Deliveries at Retail Store Retail Store Inventory Retail Store Sales

*— Slide 10 —*

---

## Model

Transaction Type Fact Periodic Snapshot Fact Accumulating Snapshot Fact Different types of fact tables

*— Slide 11 —*

---

## Periodic Snapshot Fact

Store inventory periodic snapshot schema qBusiness process = retail inventory analysis qOptimized inventory levels qMaking sure the right product is in the right store at the right time minimizes out-of-stocks (measure). qReduces overall inventory carrying costs. The retailer needs the ability to analyze daily quantity-on-hand inventory levels by product and store. qCapture events or measures (snapshots) in a period of time qIt is the most common type of fact tables.

*— Slide 12 —*

---

## Enhanced inventory periodic snapshot

*— Slide 13 —*

---

## Report

- Daily stock report of each product in every store
*— Slide 14 —*

---

## Transaction Type Fact

qInventory transaction fact records every transaction that affects inventory qBusiness process = to record every transaction that affects inventory qFocus on activities for each transaction type

*— Slide 15 —*

---

## Receive product

Place product into inspection hold Release product from inspection hold Return product to vendor due to inspection failure Place product in bin Authorize product for sale Pick product from bin Package product for shipment Ship product to customer Receive product from customer Return product to inventory from customer return Remove product from inventory Inventory Transaction Types

*— Slide 16 —*

---

## Warehouse inventory transaction model

- Add Transaction Type Dimension
- Still Keep Date Dimension
Transaction Type Fact

*— Slide 17 —*

---

## • How many times have we placed a product into an inventory bin on the same day we

picked the product from the same bin at a different time?

  - Transaction types: place products and pick product from bin
  - Dimensions: DateDim (same day)
- How many separate shipments did we receive from a given vendor, and when did we
get them?

  - Transaction types: receive product
  - Dimensions: VendorDim, DateDim
- On which products have we had more than one round of inspection failures that
caused return of the product to the vendor?

  - Transaction types: return product to vendor
  - Dimensions: VendorDim, ProductDim
Transaction Type Fact

*— Slide 18 —*

---

## Inventory_Trans Star

*— Slide 19 —*

---

## Report

- Cost for each transaction type on different warehouses
- Sale amount for each transaction type on different vendors and products
*— Slide 20 —*

---

## AccumulatingSnapshot Fact • We place one row in the fact table for a shipment of a particular product to the warehouse

  - Update until the product leaves the warehouse (product life cycle)
  - Multiple set of dates and measures at different product statuses
  - Suitable for short life cycles (not for tracking customer bank activity)
*— Slide 21 —*

---

## Accumulating snapshot!

Multiple date stamp Another dimensions

*— Slide 22 —*

---

## Date dimension characteristics

- Use surrogate numeric instead of date
- Surrogate key for special condition
  - Not applicable / Corrupted / Hasn’t happen yet
*— Slide 23 —*

---

## AccumulatingSnapshot Fact (cont.)

*— Slide 24 —*

---

## Inventory_Accumulating Star

*— Slide 25 —*

---

## Date

Store Product Page 70 Figure 3.2, with attributes excluded A star schema for store inventory Store Inventory Snapshot 1st Periodic snapshot fact table

*— Slide 26 —*

---

## Date

Warehouse Product Vendor Inventory Transaction Type Page 74 Figure 3.4, with attributes excluded A star schema for warehouse inventory transactions Inventory Transaction facts 2nd Transaction type fact table

*— Slide 27 —*

---

## Date Received

Warehouse Product Vendor Warehouse Inventory Accumulating facts Date inspected Date placed in inventory Date of last return Page 76 Figure 3.5, with attributes excluded A star schema to track inventory events Note the multiple roles for the Date dimension 3rd Accumulating snapshot fact table

*— Slide 28 —*

---

## Inventory Facts

- Inventory Periodic Snapshot
  - every time interval
- Inventory Transaction Type
  - every transaction that has impact on inventory levels
as products move through the warehouse

- Inventory Accumulating Snapshot
  - each product delivery and update until the product
leaves the warehouse (life cycle)

*— Slide 29 —*

---

## Characteristic Transaction

Grain Periodic Snapshot Grain Accumulating Snapshot Grain Time Period Point in time Regular Predictable Time Indeterminate Time span, Short-lived Grain One row Per transaction event One row per period One row per life Fact tabled loads Insert Insert Insert and update Fact row update Not revisited Not revisited Revisited whenever activity Date dimension Transaction End-of-period (weekly, month) Multiple dates Measures Transaction Activity Performance for predefined time interval Performance over finite lifetime

*— Slide 30 —*

---

## Comparison

- The periodic snapshot would be chosen for longrunning, continuously replenished inventory
scenarios.

- The accumulating snapshot model would be
used for finite inventory situations with a definite begin and end (short).

*— Slide 31 —*

---

## Part2: Enterprise DW Design

Bottom-up

*— Slide 32 —*

---

## Data Mart and Data Warehouse

- Data Mart is a subset of enterprise DW.
- In one company, there are many data marts, but one DW.
Sales Staff Order Fact Products Customer Time Orders Data Mart Sales Orders HR Global Data Warehouse

*— Slide 33 —*

---

## Enterprise DW Design

- Bottom-up
  - Proposed by Ralph Kimball
  - Create data marts first and, then, a comprehensive DW
  - Business solutions can be answered quickly.
- Top-down
  - Proposed by Bill Inmon
  - Create a comprehensive DW first and, then, data marts
  - It is robust, but the cost of project is very high.
*— Slide 34 —*

---

## Sharing dimensions among

business processes

*— Slide 35 —*

---

## Data Warehouse Bus Matrix

- The tool we use to create, document, and communicate the bus architecture
is the data warehouse bus matrix.

- Find common dimensions, called “conformed dimension”
  - Common dimensions for different processes should be the same
Front Back

*— Slide 36 —*

---

## Conformed Dimensions

- Conformed dimension is a dimension that means the
same thing for every data mart in the same enterprise

  - Consistent dimension keys
  - Consistent attribute names
  - Consistent attribute values
- Dimension tables are not conformed if the attributes are
labeled differently or contain different values.

- Bottom-up data warehousing approach
- Drill-across between data marts requires common
dimension tables (analysis across data marts)

*— Slide 37 —*

---

## Conformed Dimensions (cont.)

- If any dimension occurs in two data marts, they must be
exactly the same dimension, or one must be a subset of the other.

  - Case1: At the same level of detail, but one represents only a
subset of rows

  - Case2: Subset of attributes if they are strict subset of that
atomic dimension

*— Slide 38 —*

---

## Case1: subset dim. with same level of detail

- The fact table joined to this subset dimension must
limited to the same subset of products

  - Cannot use the overall (corporate) product dimension
Pkey Pname 1 Sony TV 2 Toshiba Laptop 3 Watch 4 Microwave Pkey Pname 3 Watch 10 AIIZ Shirt 11 Guess Jeans ProductDim (Appliance) ProductDim (Apparel) Sharing

- Same level (grain)
- Same code (key)
- Same value
- Same att. name
*— Slide 39 —*

---

## Case2: subset dim. with subset level of detail

- For example, product dim and brand dim – different granularity
- Hierarchy: product à brand à subcategory à category à department
- Hierarchy must be conformed!
Sharing

- Different level (grain)
- Different code (key)
- Same value
- Same att. name
*— Slide 40 —*

---

## Case2: subset dim. with subset level of

detail (cont.)

- For example, daily sales and monthly sales dimensions (both row
and column dimension subsetting) – different granularity

- Tip: the month dimension may consist of the month-end daily rows
with the exclusion of irrelevant month-columns. Sharing

- Different level (grain)
- Different code (key)
- Same value
- Same att. name
*— Slide 41 —*

---

## Case2: subset dim. with subset level of

detail (cont.) – Bus Matrix

*— Slide 42 —*

---

## Dimension-focused Queries

- Standard OLAP queries are fact-focused
  - Query touches one fact table and its associated dimensions
- Some types of analysis are dimension-focused
  - Bring together data from different fact tables that have a
dimension in common

  - Common dimension used to coordinate facts
  - Sometimes referred to as “drilling across”
*— Slide 43 —*

---

## Drill-Across Example

- Data mart1:
  - CustomerSupport Fact
  - Dimensions: Date, Customer, Product, ServiceRep
  - Measure: CallCount
- Data mart2:
  - Sale Fact
  - Dimensions: Date, Customer, Product, Store
  - Measure: TotalSale
- Question: How does frequency of support calls by California customers
affect their purchases of Product X?

- Drill-across between CustomerSupport and Sale
- Step 1: Query CustomerSupport fact – Query result has schema (Customer SSN, CallCount)
- Step 2: Query Sales fact
  - Query result has schema (Customer SSN, TotalSale)
- Step 3: Combine query results
*— Slide 44 —*

---

## Inner Join

Customer CallCount Napat 20 Ton 30 Siwat 50 Customer TotalSale Napat $100 Ton $200 Tat $50 CustomerSupportFact SaleFact select * from CustomerSupportFact C inner join SaleFact S on C.Customer = S.Customer; Customer CallCount TotalSale Napat 20 $100 Ton 30 $200

*— Slide 45 —*

---

## Outer Join

Customer CallCount Napat 20 Ton 30 Siwat 50 Customer TotalSale Napat $100 Ton $200 Tat $50 CustomerSupportFact SaleFact select * from CustomerSupportFact C outer join SaleFact S on C.Customer = S.Customer; Customer CallCount TotalSale Napat 20 $100 Ton 30 $200 Siwat 50 Tat $50

*— Slide 46 —*

---

## Thank you

& Any questions

*— Slide 47 —*

---
