# Ch4 - Procurement (Slowly Changing Dimension)

_Total slides: 22_

---

## Cover

Slowly-changing dimension (SCD)
Chapter 4: Procurement
Peerapon Vateekul, Ph.D.
Based on the presentation of
Assoc. Prof. Kitsana Waiyamai, Ph.D.

*— Slide 1 —*

---

## Outlines

n Procurement Process n Change in Product Dimension n Slowly Changing Dimensions (SCD) n 7 types of SCD n Multiple vs. Single Fact Tables

*— Slide 2 —*

---

## Procurement

n Procurement is an acquisition process of goods, services or works from an external source. n Effective procurement of products at the right price for resale is important to the business. n The following list are common analytics requirements: n Which products are most frequently purchased? n How many vendors supply these products? n Combining the demand across the enterprise, can we negotiate favorable prices by consolidating suppliers, single sourcing, or making guaranteed buys? n How are your vendor performing? On-time delivery performance? Percent back ordered?

*— Slide 3 —*

---

## The data stored in dimensions originally comes from the

legacy (old) systems. Changes that occur in the legacy system must be reflected in the data warehouse:

- If a new product is being sold, it must be added to
the product dimension in the warehouse.

- If a product changes, we need to reflect the
changes in the product dimension in the warehouse

- If a product is deleted, …
Managing dimensions

*— Slide 4 —*

---

## o Ancronym : SCDs

o While dimension table attributes are relatively static, they are not fixed forever. Dimension attributes change rather slowly, over time. o Need to track change, without full-blown normalized structure; without making every dimension time-dependent o For each attribute in our dimension tables, we must specify a strategy to handle change o Techniques for dealing with dimensions change : q Type 0: Retain Original (No change) q Type 1 q Type 2 q Type 3 q Hybrid approaches Slowly Changing Dimensions

*— Slide 5 —*

---

## o Overwrite the old attribute value in the dimension row replacing it with the current value.

o Example : Before After o The attribute always reflects the most recent assignment. o The rows in the fact table still reference same product key. Type 1 : Overwrite the Value

*— Slide 6 —*

---

## Type 2: Add New Row

q Create a new dimension record with a new surrogate key value q Commonly used approach q e.g. suppose a customer moves § We may still want to associate the sales to the customer’s old address § In this case we create a new customer record with the customer’s new field values § This new customer record will have a new surrogate key § Old facts are not altered

*— Slide 7 —*

---

## o Create a new dimension row reflecting the new attribute.

o Example : o Two different product surrogate keys for the same SKU number. o Adding a dimension row is the primary technique for accurately tracking SCD attributes o The fact table is left untouched again. o Response perfectly partition or segment history to account for the change. Type 2 : Add a Dimension Row

*— Slide 8 —*

---

## o Could also use the “most recent row indicator” to tell us which

of the two rows is the current (surrogate key or update date) o Could include an effective date stamp to refer to the moment when the attribute values in the row becomes valid or invalid in the case of expiration dates. o Including effective and expiration date attributes, only suitable for a precise time slice item, e.g., homework o Cannot use this technique in a new version of products, e.g., IntelliKidz 1.0 and IntelliKidz 2.0 Type 2 : Add a Dimension Row (cont’)

*— Slide 9 —*

---

## Type 2 : Add a Dimension Row (cont’)

Advantage o It support analysis using historically accurate attributes. Disadvantage o Accelerated dimension table growth, resulting in a large number of surrogate keys, which is not good for a join operation

*— Slide 10 —*

---

## Type1 Attributes in Type2 Dimensions

n Attribute “Introduction” is SCD1 (overwrite). n 2012-12-15 à 2012-01-01

*— Slide 11 —*

---

## o Add a new dimension column containing the old attribute

value o Example Before After o Overwrite the old value with the new one Type 3 : Add New Column

*— Slide 12 —*

---

## o Management can use either value for analysis

o Both the current and prior descriptions can be regarded as true at the same time. o Allows for observing new and historical fact data by either the new or prior attribute values o Advantage : o More appropriate when there is a need to associate new attribute values with old fact history o Disadvantage : o Inappropriate to track numerous intermediate attribute values used less frequently Type 3 : Add New Column (cont’)

*— Slide 13 —*

---

## n Multiple prior value attributes (instead of pairs)

n Use frequently to deal with sale organization. n It’s like type 3 but something difference because we add more than two columns Multiple Type 3 Attributes (Predictable Changes)

*— Slide 14 —*

---

## n Unpredicted attribute changes (not every year) AND

associate the change AND able to report all the history data n Sometimes, this is referred to as “SCD6” (2 + 3 + 1) n SCD2 = add a new row to capture a change n SCD3 = add a new column to track the current assignment n SCD1 = use each row at a time Hybrid Slowly Changing Dimension (Unpredictable Changes): SCD6

*— Slide 15 —*

---

## n Dual Type 1 and Type 2 Dimensions

n In SCD6, ProductDim is extremely large, so it is tedious to query the current data. Hybrid Slowly Changing Dimension SCD7 (Dual Type 1 & 2)

*— Slide 16 —*

---

## SCD Recap

*— Slide 17 —*

---

## Other Types

n In Chapter 6 Customer Relationship Management (CRM) n Customer Dimension n Rapidly Change Dimension (RCD) n SCD4 Add Mini-Dimension n SCD5 (4 + 1)

*— Slide 18 —*

---

## Multiple vs. Single Fact Tables

(Transaction Type Fact Table) n Procurement transaction types: n Purchase requisitions n Purchase orders n Shipping notification n Shipping receipts (into warehouse) n Shipping payment (to vendor) 1) Purchasing system 2) Warehousing system 3) Accounting system Should we redesign and create multiple fact tables?

*— Slide 19 —*

---

## Multiple vs. Single Fact Tables (cont.)

n In one order, there can be many shipments. n In one order, there can be many payments. n There are many different in these transactions: n Source systems, level of granularities, dims, measures

*— Slide 20 —*

---

## Multiple vs. Single Fact Tables (cont.)

n Notice: there is no single procurement system to source all the procurement transactions. n No simple formula on this issue n 1) Are there really multiple unique business process? n Separate control number n 2) Are multiple source systems involved? n Three separate source systems: purchasing, warehousing, and accounting systems. n 3) What is the dimensionality of the facts? n Each transaction type uses a different set of dimensions

*— Slide 21 —*

---

## No Contract Term Dimension - Different set of dimension tables

*— Slide 22 —*

---
