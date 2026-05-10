# Ch5 - Order Management (Junk Dimension)

_Total slides: 3_

---

## Cover

Chapter 5: Order Management
Junk Dimension
Peerapon Vateekul, Ph.D.
Dept. of Computer Engineering, Faculty of Engineering, Chulalongkorn University
peerapon.v@chula.ac.th

*— Slide 1 —*

---

## Order Management Process

- The order line transaction is usually complex and related to
many flags and indicators:

  - For example, PaymentType, OrderType, Commission
  - Are they related to each other?
  - What if there are 20 indicators? How should we handle them?
CommissionCredit Key CommissionCredit 1 Commissionable 2 Non-Commissionable OrderTypeKey OrderType 1 Inbound 2 Outbound PaymentTypeKey PaymentType 1 Cash 2 Credit

*— Slide 2 —*

---

## Junk Dimension

- After identifying fields that are obviously related to dimensions, and numeric
measures, we have left with a number of miscellaneous indicators and flags, each of which on a small range of discrete values.

- A junk dimension is a grouping of low-cardinality (#rows) dimensions.
OrderIndicatorDim = Combine 3 small indicator tables: PaymentType + OrderType + Commission

*— Slide 3 —*

---
