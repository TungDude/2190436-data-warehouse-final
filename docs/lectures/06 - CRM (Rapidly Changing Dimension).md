# Ch6 - CRM (Rapidly Changing Dimension)

_Total slides: 24_

---

## Cover

Chapter 6: Customer Relationship Management (CRM)
Rapidly Change Dimension
Peerapon Vateekul, Ph.D.
Dept. of Computer Engineering, Faculty of Engineering, Chulalongkorn University
peerapon.v@chula.ac.th
Thanks to
Associate Professor Kitsana Waiyamai, Ph.D.

*— Slide 1 —*

---

## Outlines

- Part1: Rapidly Change Dimension (RCD)
  - Dimension Outrigger
  - Mini-dimension
- Part2: Multi-Valued Dimension (MVD)
*— Slide 2 —*

---

## Part1: Outrigger & Mini-dimension

*— Slide 3 —*

---

## SCD (Recap)

*— Slide 4 —*

---

## Rapidly Changing Dimensions

- Multi-million customer dimension present unique
challenges that warrant special treatment:

  - 1) Millions of rows,
  - 2) hundreds of attributes
  - 3) with rapid change
- How can we track all changes? SCD2?
*— Slide 5 —*

---

## Customer Dimension:

Name and Address Parsing

*— Slide 6 —*

---

## Common Customer Attributes

- Low-cardinality attribute set
(commonly low correlation)

  - For example, country/region
statistics

  - Solution: dimension outriggers
- Large changing customer
dimensions

  - For example, age, income
  - Solution: mini-dimensions
77 provinces Demographics

*— Slide 7 —*

---

## 1) Dimension Outriggers

- A dimension normalization resulting in a snowflake schema
  - To separate low-cardinality columns
  - To link it back to the original dimension
- Assume, there are 150 demographic/sociological attributes!
  - They should be normalized to a separated outrigger table to avoid repeating
this large block of data.

  - When should be separated? (1) different grains (country vs. customer)
(2) different sources, (3) significant in the space savings Millions of customers 77 provinces

*— Slide 8 —*

---

## 2) Mini-dimensions

- Single technique to handle browsing-performance & change
tracking problems

- Separate out frequently analyzed or frequently changing attributes
into a separate dimension, called mini-dimension

- For example, “Customer Demographics:” age, income, marital
status, etc.

  - They are often changed and from the same source of customers.
Demographics (Frequent Changes)

*— Slide 9 —*

---

## mini-dimensions (cont.)

Static Rapid change (mini dimension) Track current state

*— Slide 10 —*

---

## mini-dimensions (cont.)

DemographicKey AGE GENDER INCOME LEVEL 1 20-24 M < 20000 2 20-24 M 20K-24999 3 20-24 M 25K-29999 18 25-29 M 20K-24999 10 25-29 M 25K-29999

*— Slide 11 —*

---

## mini-dimensions (cont.)

- A mini-dimension cannot be itself allowed to
grow very large.

- 5 demographic attributes
- Each attribute can take 10 distinct values
- How many rows in mini-dimension? 10,0000
*— Slide 12 —*

---

## mini-dimensions (cont.)

- Multiple mini-dimensions
  - Different sources
  - Different update frequencies
- Drawback: Bigger fact!
*— Slide 13 —*

---

## SCD4 Add Mini-Dimension (Ch5)

Rapid change (mini dimension)

*— Slide 14 —*

---

## SCD5 Mini-Dimension with Outrigger (Ch5)

- Mini-Dimension (Type 4) + Outrigger (Type 1)
Mini-dimension Outrigger

*— Slide 15 —*

---

## Part2: Multi-Valued Dimension (MVD)

*— Slide 16 —*

---

## Multivalued Dimensions (MVD)

- Declaring grain of the fact table is one of the important
design decisions

- Grain declares the exact meaning of a single fact record
- If the grain of the fact table is clear, choosing dimensions
becomes easy

*— Slide 17 —*

---

## Multivalued Dimensions (cont.)

- Grain: a transaction of each customer (account)
- What if one account can associate to many customers and one customer
can have multiple accounts?

- Is the relationship between CustomerDim and Fact still “1-to-M”?
*— Slide 18 —*

---

## Bridge Tables

- Account to Customer BRIDGE table, also called
helper or associative table. account_id Fact Table account_id Account Dimension Accountrelated attributes account_id customer_id weight Bridge Table customer_id Customer Dimension Customerrelated attributes

- Weights for each account sum to 1
- Allows for proper allocation of facts
when using Customer dimension

*— Slide 19 —*

---

## Bridge Tables (cont.)

*— Slide 20 —*

---

## MVD: Healthcare Example

- Dimensions
  - Calendar Date (of incurred charges)
  - Patient
  - Doctor (usually called ‘provider’)
  - Location
  - Service Performed
  - Diagnosis
  - Payer (insurance co., employer, self)
- In many healthcare situations, there may be multiple values for
diagnosis

- Really sick people having 10 different diagnoses!!
- How to model the Diagnosis Dimension?
*— Slide 21 —*

---

## MVD: Healthcare Example (cont.)

- There are many diagnoses in one visit.
*— Slide 22 —*

---

## MVD: Healthcare Example (cont.)

Helper Table Approach

  - “DiagnosisGroup Helper Table”
  - The Diagnosis key in the fact table is changed to be a Diagnosis Group key
There is still M-to-M All relationships are 1-to-M

*— Slide 23 —*

---

## Star vs. Snowflake schemas

- Star schema is a dimension model that
all dimension tables directly connect to fact tables.

- Snowflake schema is a dimension
model that some dimension tables may not directly connect to fact tables. Star schema Snowflake schema

*— Slide 24 —*

---
