# Ch3 - Retail Sales

_Total slides: 73_

---

## Cover

Ch3: Retail Sales
2190436 Data Warehousing
Peerapon Vateekul, Ph.D.
Department of Computer Engineering,
Faculty of Engineering, Chulalongkorn University
peerapon.v@chula.ac.th

*— Slide 1 —*

---

## Outlines

- Part1: 4-Step Dimensional Design Process
- Part2: Design Techniques
- Part3: A Case Study in Retail Sales
*— Slide 2 —*

---

## PART1: 4-STEP DESIGN

*— Slide 3 —*

---

## Star Schema (recap)

Sale Fact Table = Actions StoreKey StoreName Province Region Country StoreSize 201 (PK) CU BKK Central TH Small ProductKey ProductName Brand Flavor ProductCategory 25 (PK) Green tea Oishi No sugar Beverage DateKey Date Day Month Year DoW IsWeekEnd IsHoliday 134 (PK) 21/01/2020 20 Jan 2020 Tuesday WeekDay Non-Holiday StoreKey ProductKey DateKey Unit_sold TotalSale TotalProfit 201 (PK) 25 (PK) 134 (PK) 400 12,000 2,000 Foreign Keys Measures Grain, granularity: Daily sale per each product/store Date_Dim Product_Dim Store_Dim Dimensions = Factors Time_key day-of-week month quarter year holiday_flag Time_key product_key store_key dollars_sold units_sold dollars_cost Total_sales Product_key description brand category Store_key store_name address floor_plan_type Sales Fact Date Dimension Product Dimension Store Dimension

*— Slide 4 —*

---

## Four-Step Dimensional Design Process

- “4-Step Design” is a thinking process to design dimensional
modeling, where the output is a star schema: fact & dimension tables.

*— Slide 5 —*

---

## Four-Step Dimensional Design Process (cont.)

- Step 0 – Gather requirements
- Step 1 – choose the business process
  - “What is the process are you interested in?”
- Step 2 – declare the grain
  - “How do we describe a single row in the fact table (grain)?”
  - What is the event or transaction used in the analysis?
- Step 3 – identify dimensions
  - “How would users describe the data that results from the business process?”
  - “Who, What, Where, When, Why, and How?” associated with event
- Step 4 – Identify facts
  - “What is the process measuring?”
- Step 5 – Finish up the design (fill details)
*— Slide 6 —*

---

## Step 1 - Identify the Business Process(Activities)

- “What is the process are you interested in?”
- A business process is a low-level activity performed by organization.
- It can refer to as process, event, action, or transaction.
- For example:
  - Process: POS retail sales transaction (the retail sale process)
  - Taking orders, invoicing, receiving payments, handling service calls, registering students,
performing a medical procedure, or processing claims

- It is NOT department or function.
- For example:
  - A single dimensional model of “order process” should be published ONCE rather than
building separate models for different departments (sales & marketing).

- Business Process
- Grain
3 • Dimensions 4 • Facts

*— Slide 7 —*

---

## All Electronics Case Study: Sale Transactions

- A big electronics retail store in California
*— Slide 8 —*

---

## Step 2 - Identify the Grain (Level of Activities)

- “How do we describe a single row in the fact table (grain)?”
- What is the event or transaction used in the analysis?
- Transaction business process is the most common. This kind of fact table is called
“Transaction Fact Table”.

- Atomic grain refers to the lowest level that data is captured in the business process.
- Preferably it should be at the most atomic level possible since it provides maximum analytic
flexibility.

- Example grain declarations include:
  - An individual line item on a customer’s retail sales ticket as measured by a scanner device (each item)
  - A line item on a bill received from a doctor (each bill)
  - An individual boarding pass to get on a flight (each flight)
  - A daily snapshot of the inventory levels for each product in a warehouse (inventory level)
  - A monthly snapshot for each bank account (monthly balance)
- Business Process
- Grain
3 • Dimensions 4 • Facts

*— Slide 9 —*

---

## All Electronics Source (OLTP)

- Main tables: Employees, Customers, Items, Suppliers
- Table[Purchases]: TransID = (CustID, EmpID, Date)
- Table[Item_sold]: There are many items sold in one purchase.
- Granularity is a level of details, where atomic is the most detail level.
- In the receipt, there are two granularity levels: purchase and item levels
*— Slide 10 —*

---

## Step 3 - Identify the Dimensions (Factors)

- “How would users describe the data that results from the business process?”
- Provide “who, what, when, why, and how” associated a business process event (each row in
fact table).

- For example, product, customer, employee, facility
- A dimension table is a descriptor (textual data) for DW.
- (1) Identify Primary Dimensions à (2) Add Additional Dimensions
- A grain identifies the primary dimensions of the fact table.
- If these dimensions are not enough for the analysis, more additional dimensions can be
added, only if they take only one value under each combination of the primary dimensions.

- If this is violated, the grain statement must be revised.
- Business Process
- Grain
3 • Dimensions 4 • Facts

*— Slide 11 —*

---

## TBD

Step5 TBD Step5 TBD Step5 TBD Step4 Step 3 - Identify the Dimensions (cont.) Sketch the design

*— Slide 12 —*

---

## Step 4 - Identify the Facts (Measures)

- “What is the process measuring?”
- Typical facts are numeric additive figures.
- For example, quantity ordered, dollar cost amount
- Must be true (conform) to the grain defined in step 2.
- Facts (measures) that belong to a different grain belong in a separate fact table.
- Tip! Percentages and ratios, such as gross margin, are non-additive. The numerator
and denominator should be stored in the fact table.

- Business Process
- Grain
3 • Dimensions 4 • Facts

*— Slide 13 —*

---

## Step 4 - Identify the Facts (cont.)

TBD Step5 TBD Step5 TBD Step5

- “The fact must be true to the grain”
- An individual item in the transaction
- “Transaction Fact Table”
*— Slide 14 —*

---

## Step 5 – Finish Up the Design (Fill Details)

*— Slide 15 —*

---

## Exercise

- Hotel Analysis
*— Slide 16 —*

---

## PART2: DESIGN TECHNIQUES

*— Slide 17 —*

---

## Outline

1. Degenerate dimension 2. Factless fact table 3. Multiple role-playing dimension 4. Aggregated fact table 5. Should DateDim store “time”? 6. Measures

*— Slide 18 —*

---

## Outline

1. Degenerate dimension 2. Factless fact table 3. Multiple role-playing dimension 4. Aggregated fact table 5. Should DateDim store “time”? 6. Measures

*— Slide 19 —*

---

## AllElectronics Source (OLTP) • In any transactions, there is always a control number referring to each transaction (activity).

- In the sale process, “TransID” is a control number considering as “receipt/billing id.”
*— Slide 20 —*

---

## DW Design Version1

*— Slide 21 —*

---

## 1) Degenerate Dimensions (DD)

- Add the column “TransID”
  - Is it a measure (fact)?
  - Does it have its own dimension table?
- Degenerate Dimensions (DD) – (Page 50)
  - Dimension keys without corresponding dimension tables
  - Mostly refer to a natural key (PK) in the source DB
  - Typically, a control number, e.g., order, ticket, check numbers, etc.
  - Tracking back to the original DB source
  - Use for filtering or grouping together related fact table rows
TransID is a control number referring to each bill (sale activity)

*— Slide 22 —*

---

## Outline

1. Degenerate dimension 2. Factless fact table 3. Multiple role-playing dimension 4. Aggregated fact table 5. Should DateDim store “time”? 6. Measures

*— Slide 23 —*

---

## 2) Factless fact table • Traditional DW query: What is the total sale for each product key?

select ProductKey, sum( Total ) as TotalSale from Purchase_Fact group by ProductKey

*— Slide 24 —*

---

## 2) Factless fact table (cont.) • What is the number of buyers for each product?

  - Do we need any measures (facts) to answer this question?
- Factless fact table is a fact table that does not have any measures.
select ProductKey, count( CustomerKey ) as TotalBuyers from Purchase_Fact group by ProductKey

*— Slide 25 —*

---

## 2) Factless fact table (cont.)

- Factless fact table is used for two situations:
  - To summarize the set of possible
occurrences (how many?)

- The number of buyers for each product in 2008
  - To track events
- The list of buyers for each product in 2008
- Another Example:
  - How many students attended a particular
class on a particular day?

  - How many classes on average does a student
attend on a given day? AttendanceFact StudentKey (PK) ClassKey (PK) DateKey (PK)

*— Slide 26 —*

---

## Outline

1. Degenerate dimension 2. Factless fact table 3. Multiple role-playing dimension 4. Aggregated fact table 5. Should DateDim store “time”? 6. Measures

*— Slide 27 —*

---

## 3) Multiple Role-Playing Dimension

Example1 Example2

- How many roles does EmplyeeDim play in
WorkingActivityFact?

  - Each working activity
- How many roles does DateDim play in
InventoryFact?

  - Each product lot ordered to the inventory
WorkingActivityFact EmployeeKey (PK) SupervisorKey (PK) TaskKey (PK) WorkingDateKey (PK) EmployeeDim EmployeeKey (PK) InventoryFact ProductKey (PK) OrderDateKey (PK) ReceiveDateKey (PK) DateDim DateKey (PK) Dimensional role-playing occurs when a single dimension needs to be part of the same fact table many times.

*— Slide 28 —*

---

## 3) Multiple Role-Playing Dimension (cont.)

How can we join 2 FKs to the same table?

- Use “table alias”
select T1.DateKey as OrderDateKey , T2.DateKey as ReceiveDateKey from DateDim as T1, DateDim as T2 Example2 } How many roles does DateDim play in InventoryFact? InventoryFact ProductKey (PK) OrderDateKey (PK) ReceiveDateKey (PK) DateDim DateKey (PK)

*— Slide 29 —*

---

## Outline

1. Degenerate dimension 2. Factless fact table 3. Multiple role-playing dimension 4. Aggregated fact table 5. Should DateDim store “time”? 6. Measures

*— Slide 30 —*

---

## Need for Aggregation

- Business process: sale analysis
  - Question1: daily analysis at the transaction level
  - Question2: month analysis for each store
- This monthly report is used very often as an overview for the whole business, so it
must be very fast for any dynamic queries.

- Sizes of typical tables:
  - Customer dimension: 100 customers per day / store (shop)
  - Date dimension: 5 years x 365 days = 1,825 days
  - Store dimension: 300 stores reporting daily sales
  - Production dimension: 40,000 products in each store (about 4,000 sales
in each store daily)

  - Maximum number of base fact table records: 2 hundred thousand
millions (lowest level of detail)!!!

- A query involving 1 brand, all stores, 1 year: retrieve/summarize
over 7 million rows in fact table! TransactionSaleFact CustomerKey (PK) StoreKey (PK) DateKey (PK) ProductKey (PK) Measure1 Measure2 Base Fact Table

*— Slide 31 —*

---

## 4) Aggregated fact table (cont.)

- Business process: sale analysis
  - Question1: daily analysis at the transaction level
  - Question2: month analysis for each store (must be queried very fast)
TransactionSaleFact CustomerKey (PK) StoreKey (PK) DateKey (PK) ProductKey (PK) Measure1 Measure2 StoreSaleFact StoreKey (PK) MonthKey (PK) ProductKey (PK) Sum(Measure1) Sum(Measure2) Base Fact Table Aggregated Fact Table

*— Slide 32 —*

---

## 4) Aggregated fact table (cont.)

- Aggregated fact tables are a table containing summary or aggregated data from the base fact table.
- Aggregate tables contain data that has been summarized up to different level along the dimension
hierarchies.

  - Month à Year
  - Product à Brand
- So, the different is in granularity.
  - Fact tables store data in more detail.
  - Aggregated tables has higher granularity
- Created for performance reasons (query faster)
*— Slide 33 —*

---

## 4) Aggregated fact table (cont.)

TransactionSaleFact CustomerKey StoreKey DateKey ProductKey Measure1 Measure2 StoreMonthlySaleFact StoreKey MonthKey ProductCategoryKey Sum(Measure1) Sum(Measure2) base Fact Table Aggregated Fact Table 1. Lost dimension (CustomerDim) 2. Shrunken dimension (Month, ProductCategory) 3. Metrics are accumulated over the base table

*— Slide 34 —*

---

## 4) Aggregated fact table (cont.):

Shrunken Dimension

- Do we need to separate ProductCategoryDim into a new dimension?
- Answer: Yes, we need to create a new dimension.
  - The description of each category is different from each product.
  - The main reason is that each product category has “no product information”, so {ProductID,
ProductName} are missing! ProductCategoryKey ProductCategoryKey (PK) ProductDim ProductKey (PK)

*— Slide 35 —*

---

## 4) Aggregated fact table (cont.):

Shrunken Dimension

- Do we need to separate MonthDim into a new dimension?
- Answer: No, we may not need to.
  - They have a close relationship and share almost the same description.
  - However, there is no “Date” data (e.g., 2015/01/01) at month level and this
information cannot be missing in DateDim.

  - Tip, assign a special date code for each month. For example, the date for Jan2015 is “2015/01/00”.
- Anyways, separated MonthDim is still more preferred since all date-level variables will be
missing, such as isHoliday, isWeekDay, DayOfWeek, etc. MonthDim MonthKey DateDim DateKey

*— Slide 36 —*

---

## www.eng.chula.ac.th Example

StoreDim StoreKey ProductDim ProductKey StoreDim StoreKey TransactionSaleFact CustomerKey StoreKey DateKey ProductKey Measure1 Measure2 DateDim DateKey

*— Slide 37 —*

---

## www.eng.chula.ac.th Example (cont.)

StoreDim StoreKey ProductDim ProductKey StoreDim StoreKey TransactionSaleFact CustomerKey StoreKey DateKey ProductKey Measure1 Measure2 DateDim DateKey StoreSaleFact StoreKey MonthKey ProductCategoryKey Sum(Measure1) Sum(Measure2) MonthDim MonthKey ProductCategoryKey ProductCategoryKey

*— Slide 38 —*

---

## Fact Constellation Schema

- A constellation schema has multiple fact tables. It is also
known as galaxy schema. Dollars Units Price District Fact Table District_ID PRODUCT_KEY PERIOD_KEY Dollars Units Price Region Fact Table Region_ID PRODUCT_KEY PERIOD_KEY PERIOD KEY Store Dimension Time Dimension Product Dimension STORE KEY PRODUCT KEY PERIOD KEY Dollars Units Price Period Desc Year Quarter Month Day Current Flag Sequence Fact Table PRODUCT KEY Store Description City State District ID District Desc. Region_ID Region Desc. Regional Mgr. Product Desc. Brand Color Size Manufacturer STORE KEY

*— Slide 39 —*

---

## Outline

1. Degenerate dimension 2. Factless fact table 3. Multiple role-playing dimension 4. Aggregated fact table 5. Should DateDim store “time”? 6. Measures

*— Slide 40 —*

---

## Should DateDim store “time”?

- Combined Date Time dimension vs. Separate Day and Time dimensions (sec.)
- Kimball suggests to have a separate day dimension from the time-of-day dimension to prevent the
table from growing too large.

- Moreover, the descriptions for date and time are different.
- Compare #rows in total
  - Combine: (24 hrs/day)*(365days) à 8,760 rows/year
  - Separate:
- DateDim (day): 365 rows à 365 rows/year
- TimeDim (sec.): 24 hours/day à fixed
*— Slide 41 —*

---

## Outline

1. Degenerate dimension 2. Factless fact table 3. Multiple role-playing dimension 4. Aggregated fact table 5. Should DateDim store “time”? 6. Measures

*— Slide 42 —*

---

## 6) Measures

- Additive measures:
  - fact measures which can be aggregated (sum) across ALL dimensions and their
hierarchy

  - For example, sale amount
- Semi-Additive measures:
  - fact measures which can be aggregated (sum) across all dimensions and their hierarchy
except the time dimension

- Non-additive measures:
  - fact measures which cannot be aggregated (sum) across all/any dimensions and their
hierarchy

  - For example, percentage or grades (A, B+, B, …)
*— Slide 43 —*

---

## Additive/Non-Additive Measure (cont.)

Date (PK) Customer (PK) Product (PK) Unit Sold %Profit 2016/01/01 John Red Bull 4 25% 2016/01/01 John Pepsi 2 50% 2016/01/01 Mary Coke 3 50% 2016/01/01 Mary Pepsi 2 30% 2016/01/02 John Red Bull 6 20% 2016/01/02 Mary Red Bull 4 50% What are the total items sold by date (by customer, by product)? What is the total percentage of profits by date (by customer, by product)? Numerator & Denominator

*— Slide 44 —*

---

## Semi-additive Measure (Snapshot)

- For example, stock levels:
  - Assume 1,000 (qty of Item A) on Monday
  - Sell 200 (qty of Item A) on Tuesday, so the remaining item is 800.
  - Further sell 300 (qty of Item A) on Wednesday so the remaining item is 500.
  - By basic math On Thursday, we should be left with 500 (qty of Item A, assuming no inventory has
flown in)

  - To obtain current stock level, we cannot aggregate (sum) the Stock sales across time dimension
hierarchy.

  - If done, we will have inappropriate outcomes
- Qty on Monday + Tuesday + Wednesday = 1,000+800+500 = 2,300. It actually should be 500 items left instead of
2,300 items.

*— Slide 45 —*

---

## Semi-additive Measure (cont.)

Date (PK) Product (PK) Store (PK) Qty on Hand Monday Red Bull Chula 100 Tuesday Red Bull Chula 50 Monday Pepsi Chula 150 Tuesday Pepsi Chula 100 Monday Red Bull KU 80 Tuesday Red Bull KU 60

*— Slide 46 —*

---

## Semi-additive Measure (cont.)

- On Tuesday, what is the quantity of “Red Bull” in all branches?
  - 50 + 60 = 110. Can we sum the measure over “StoreDim”?
- On Tuesday, what is the quantity of all products at “Chula”?
  - 50 + 100 = 150. Can we sum the measure over “ProductDim”?
- At Chula, what is the quantity of remaining “Red Bull”?
  - 100 + 50 = 150. Is this correct? So, can we sum the measure over “DateDim”?
Date (PK) Product (PK) Store (PK) Qty on Hand Monday Red Bull Chula 100 Tuesday Red Bull Chula 50 Monday Pepsi Chula 150 Tuesday Pepsi Chula 100 Monday Red Bull KU 80 Tuesday Red Bull KU 60

*— Slide 47 —*

---

## Exercise

- Flight Activity Analysis
- Pizza Restaurant Analysis
- Hospital Analysis
*— Slide 48 —*

---

## PART3: CASE STUDY

*— Slide 49 —*

---

## Business Scenario

- A large grocery chain
- 100 grocery stores across 5 states
- Each store has many product
departments

  - grocery, frozen foods, dairy, meat,
produce, bakery, floral, and health/beauty aids

- Approximately 60,000 individual
products, where stock keeping unit (SKU) is PK.

- Source DB: The point-of-sale (POS)
system scans product at the cash register Sample cash register receipt

*— Slide 50 —*

---

## Business Objective

- Main objective: maximizing profit
- Pricing & promotions
  - What is the suitable price?
  - Which promotion is effective?
- Promotions:
  - Including temporary price reductions, ads
in newspapers, displays in the grocery store, and coupons.

  - A big reduction can create a surge in the
volume of product sale.

  - Unfortunately, such a big price reduction
usually is not sustainable because some products probably are being sold at a loss. Sample cash register receipt

*— Slide 51 —*

---

## 4-Step Design

- Objective: Better understand
customer purchases as captured by POS system

- Step1: Select the Business Process
  - POS retail transactions
- Step2: Declare the Grain
  - Atomic: an individual product on a POS
transaction Sample cash register receipt

*— Slide 52 —*

---

## 4-Step Design (cont.)

- Step3: Identify the dimensions
  - Primary dim à Additional dim
  - Date, Product, Store, Promotion,
Cashier, Method of Payment

  - No customer info in a bill
  - POS transaction ticket (DD)
Sample cash register receipt

*— Slide 53 —*

---

## 4-Step Design (cont.)

- Step4: Identify the Facts
  - The facts must be true to the grain.
  - All of these measures are additive (sum).
  - “Transaction fact table” expresses the context of transactions.
*— Slide 54 —*

---

## 4-Step Design (cont.) • How to estimate #rows in fact table?

- Solution1: estimate #rows of each dimension
- Solution2: estimate from measure, e.g.,
  - The gross revenue = $2 billion per year
  - An average sale of an item for each bill = $2
  - So, approximately 1 billion transaction line items (rows) per year
*— Slide 55 —*

---

## More about Facts (Measures)

- Should a calculated derived fact (gross profit) be
stored in the DW database?

- Yes, to eliminate the possibility of user calculation errors.
- Should a ratio or percentage be stored in the DW
database?

- No, it is non-additive.
- The numerator and denominator should be stored in the
fact instead.

*— Slide 56 —*

---

## Dimensions

- Date
- Store
- Cashier
- Product
- Promotion
- Payment Method
*— Slide 57 —*

---

## Date Dimension

- Unlike most of the other dimensions, it can be built in
advance.

- Dimensional models always need an explicit date
dimensions.

*— Slide 58 —*

---

## Date Dimension (cont.)

- Flags and indicators as textual attributes
*— Slide 59 —*

---

## Date Dimension (cont.)

- Current and relative date attributes (optional)
- Most date attributes are static (not change).
- While some can be added non-static date attributes for showing the
most recent report (current status)

  - Attributes that can change over time
  - IsCurrentDay, IsCurrentMonth, IsPeriod60Days
*— Slide 60 —*

---

## Date Dimension (cont.)

- Smart Key (optional)
- PK of Date Dim is usually a surrogate key, a sequence of nonmeaningful integers.
- More commonly, PK of Date Dim is a meaningful integer formatted
‘yyyymmdd’ called “smart key” (not surrogate key).

- Although it would negatively affect query performance, the yyyymmdd is
useful for partitioning fact tables (no need to join between Fact and Date Dim).

*— Slide 61 —*

---

## Product Dimension

- The product dimension may have 300,000 or more rows.
- It typically has more than one hierarchy.
- Merchandise hierarchy
  - SKU (each product) à Brand à Subcategory à Category à Department
- Package type: Bag, Box, Can
*— Slide 62 —*

---

## Product Dimension (cont.)

- “Source” Attributes with Embedded Meaning
- Source operational product codes often have embedded meaning.
- All embedded meanings should be extracted and stored in a
dimension.

- For example,
- Product Code = ‘78-001234-90’
- Assume ‘78’ refers to ‘manufacturer code’
- In this case, ‘manufacturer name’ should be stored in Product Dim.
*— Slide 63 —*

---

## Product Dimension (cont.)

- Numeric values as (1) “Dim Attributes” or
(2) “Fact Measures”

- Should the product list price store in Fact or Dim?
- Answer: Both locations
- Calculation Fact • compute profit
- Filtering/Grouping Dim • List products whose price > $200
*— Slide 64 —*

---

## Store Dimension

- It is a primary geographic dimension.
- Hierarchies (conceptual view):
  - Store Name à Zip Code à City à State
  - Store Name à District à Region
- Dates within dimensions
- Such as, open date, remodel date, etc.
- To get descriptions, these date attributes must join to Date
Dim.

- Date Dim:
  - Multi-role playing in this dimension (Store Dim)
  - Outrigger
*— Slide 65 —*

---

## Promotion Dimension

- It is often called “causal dimension” since it describes factors
causing a change in product sales.

- Is the promotion effective?
- To answer this question, background in financial area is required:
- lift, time shifting, cannibalization, market growth
*— Slide 66 —*

---

## Promotion Dimension (cont.)

- Typically, many sale transactions include products
that are not being promoted (do not on sale)

- What should be the value of “PromotionKey” of
these products?

- Can PK be null?
- Null Foreign Keys
- Solution: assign special codes in dimension tables.
- For example, 0 = no promotion condition
- Nulls as Metrics in Fact Table
- Should we assign a code for “null value”?
- No, we generally leave it; otherwise, the fact
calculation will be incorrect. Null Value NO

*— Slide 67 —*

---

## Other Dimensions

- Should we have “Billing Dimension”?
- Yes, if there are some attributes left
over from the existing dimensions. Sample cash register receipt

*— Slide 68 —*

---

## Final Design & Query

*— Slide 69 —*

---

## Fact Table Surrogate Keys

- A surrogate key for fact table is optional since it doesn’t relate to the
query performance (like a set of dimension surrogate keys).

- However, it still has some benefits in the ETL process:
  - Immediate unique identification
  - Backing out or resuming a bulk load
  - Replacing updates with inserts plus deletes
  - Using the fact table surrogate key as a parent in a parent/child schema
P. 102 in Book Ed. 3 71

*— Slide 70 —*

---

## Centipede Fact Tables with Too Many Dimensions

P. 108 in Book Ed. 3 72

*— Slide 71 —*

---

## Centipede Fact Tables with Too Many

Dimensions (cont.)

- In Centipede Fact table, it will lead to
significantly increase fact table disk space requirements since the relationship is captured in fact table.

- A very large number of dimensions
typically are a sign that several dimensions are not completely independent and should be combined into a single dimension.

- It is a dimensional modeling mistake to
represent elements of a single hierarchy as separate dimensions in the fact table. P. 108 in Book Ed. 3 A perfectly correlated attributes, such as the levels of a hierarchy, should be part of the same dimension.

*— Slide 72 —*

---

## Appendix: Cannibalization

Boon Rawd Bewery Group ThaiBev Group

*— Slide 73 —*

---
