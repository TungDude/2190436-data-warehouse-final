# NoSQL

_Total slides: 31_

---

## Cover

INTRODUCTION TO NoSQL

Prof. Peerapon Vateekul, Ph.D.
Department of Computer Engineering, Faculty of Engineering, Chulalongkorn University
peerapon.v@chula.ac.th

2190436 Data Warehousing (Year 4)
2190518 Data Engineering and Big Data (Year 3)

*— Slide 1 —*

---

## Outlines

- What is NoSQL?
- Why NoSQL?
- Types of NoSQL
  - Key-Value databases
  - Document databases
  - Column-Store databases
  - Graph databases

*— Slide 2 —*

---

## What is NoSQL?

- NoSQL means Not Only SQL, implying that when designing a software solution or product, there are more than one storage mechanism that could be used based on the needs.
- NoSQL does not have a prescriptive definition, but we can make a set of common observations, such as:
  - Not using the relational model (ACID)
  - Scalability (Distributed System)
  - Schema-less (Variety, Flexibility)

*— Slide 3 —*

---

## WHY NoSQL?

- Dynamic Schemas (Variety, Flexibility)
  - NoSQL databases are built to allow the insertion of data without predefined schema
- Auto-Sharding (Scalability)
  - NoSQL databases usually support auto-sharding, meaning that they natively and automatically spread data across an arbitrary number of servers
- Replication (Tolerance)
  - Most NoSQL databases also support automatic database replication to maintain availability in the event of outages
- Integrated Caching (Availability)
  - Many NoSQL database technologies have excellent integrated caching capabilities, keeping frequently-used data in system memory as much as possible

*— Slide 4 —*

---

## Types of NoSQL

1. Key-Value databases
2. Document databases
3. Column-Store databases
4. Graph databases

*— Slide 5 —*

---

## 1) Key-Value databases

- Data is stored in a key-value pairs, where attribute is the KEY and content is the VALUE.
- Data can only be queried and retrieved using the keys only.
- We can use tricks, e.g., enumerated keys, to implement range queries.

*— Slide 6 —*

---

## Key-Value databases (cont.)

Diagram illustrating key-value pair storage structure.

*— Slide 7 —*

---

## Key-Value databases (cont.)

Table A:

| Key | Value |
|---|---|
| Post:16082015:220030:Bank | {"Im so sleepy"....} |
| Post:18092015:120010:Lucky | {"This burger is good"....} |
| Post:18092014:133005:Pang | {"Yummy, good pizza"....} |

In the Key-Value database, if we use a proper designed key, data can be queried easier.

A key pattern is "Post:Day:Time:Name"

In Redis database, to query "all posts in July 2024" from Table A:

```
> KEYS Post:??072024:*
```

*— Slide 8 —*

---

## Key-Value databases (cont.)

- Key-Value databases are well suited to applications that have frequent small reads and writes along with simple data models.
- Key-Value stores provide high scalability.

Criteria
- Caching data from relational databases to improve performance
- Tracking transient attributes in a web application, such as a shopping cart
- Storing configuration and user data information for mobile applications
- Storing data from sensors (IoT)

Use cases: Caching & IoT

*— Slide 9 —*

---

## Key-Value databases (cont.)

Key-value based software:

- Redis
- Amazon DynamoDB
- Memcached
- Hazelcast

*— Slide 10 —*

---

## 2) Document databases

Section divider for Document databases.

*— Slide 11 —*

---

## Document databases

- Designed for storing, retrieving, and managing document-oriented information, also known as semi-structured data.
- Can store the data that have the different set of data fields (columns).
- Each document is assigned a unique key, which is used to retrieve the document.
- Most of the databases available under this category use XML, JSON

*— Slide 12 —*

---

## Document databases (cont.)

```json
{
  "created_at": "Tue Mar 21 20:50:14 +0000 2006",
  "text": "just setting up my twttr",
  "user": {
    "name": "Jack Dorsey",
    "screen_name": "jack"
  }
},
{
  "created_at": "Sun Feb 09 23:25:34 +0000 2014",
  "id": 432656548536401920,
  "text": "POST statuses/update. Great way to start. https://t.co/9S8YO69xzf (disclaimer, this was not posted via the API).",
  "user": {
    "name": "TwitterDev",
    "screen_name": "TwitterDev",
    "description": "Developers and Platform Relations @Twitter. We are developers advocates. We can't answer all your questions, but we listen to all of them!",
    "url": "https://t.co/66w26cua1O"
  }
}
```

*— Slide 13 —*

---

## Document databases (cont.)

In MongoDB, to query documents that contain specific properties:

```
db.collectionName.find({properties})
```

For example, to query documents (records) whose gender is male from collection (table) "players":

```
db.players.find({gender: "male"})
```

Note: Key in MongoDB is automatically generated, so users won't know the key, but can use other properties to search in value.

*— Slide 14 —*

---

## Document databases (cont.)

- Application that requires the ability to store varying attributes along with large amounts of data
- Application that stored data in standard formats like JSON, XML.

Criteria
- Back-end support for websites with high volumes of reads and writes
- Applications that use JSON data structures such as twitter data (X)

Use cases

*— Slide 15 —*

---

## Document databases (cont.)

Document-based software:

- MongoDB
- Couchbase
- CouchDB
- Amazon DocumentDB
- Microsoft Azure DocumentDB

*— Slide 16 —*

---

## 3) Column-Store databases

- Designed for storing data tables as sections of columns of data associated with a row key.
- All columns are treated individually, and values of single column are stored together.
- Having stored data in wide-Column-Stores offer very high performance and a highly scalable architecture.

*— Slide 17 —*

---

## Column-Store databases (cont.)

On a disk, the row store database will store data like this:

Diagram showing rows 1-5 each stored as contiguous blocks of (Key, Value, C1, C2, C3) on disk.

*— Slide 18 —*

---

## Column-Store databases (cont.)

So, if you want only data in column 2:

Diagram showing that with row store layout, the disk must read all data across all rows even when only column 2 is needed.

*— Slide 19 —*

---

## Column-Store databases (cont.)

But in Column-Store database, it will store data like this:

Diagram showing data laid out by column: Column 0 (Key) R1-R5, Column 1 R1-R5, Column 2 R1-R5, Column 3 R1-R5.

*— Slide 20 —*

---

## Column-Store databases (cont.)

So, if you want only data in column 2:

Diagram showing only Column 2 (R1-R5) is read from disk; just the column 2 size is loaded.

*— Slide 21 —*

---

## Column-Store databases (cont.)

| id | name | address | gender | age |
|---|---|---|---|---|
| 1 | Bob | USA | Male | 16 |
| 2 | Lucy | Brazil | Female | 50 |
| 3 | Dum | Thailand | Male | 38 |

Table A has a 10 GB data with:
- column id : 1 GB
- column name : 2 GB
- column address : 5 GB
- column gender : 0.5 GB
- column age : 1.5 GB

- If a query only uses column age (e.g., compute an average), at most 1.5 GB of data will be processed by a Column-Store
- In a row store, the full 10 GB will be processed

Less Data = Faster!!!

*— Slide 22 —*

---

## Column-Store databases (cont.)

- Large volumes of data, read performance, and high availability
- Applications that require the ability to always aggregate or query on column

Criteria
- Security analytics using network traffic and log data model
- Big Science data, e.g., bioinformatics using genetic and proteomic data
- Stock market analysis using trade data

Use cases

*— Slide 23 —*

---

## Column-Store databases (cont.)

Column-Store based software:

- Cassandra
- HBase (Hadoop)
- Google Cloud Bigtable
- Amazon Redshift

*— Slide 24 —*

---

## 4) Graph databases

Section divider for Graph databases.

*— Slide 25 —*

---

## Graph databases (cont.)

- Graph databases use edges and nodes to represent and store the data.
- Nodes are represented as objects
- Edges act as relations among these nodes
- Every node and edge can store additional properties.
- The relationship between nodes is not calculated at query time, but is actually persisted as a relationship.
- Nodes can have different types of relationships between them.

*— Slide 26 —*

---

## Graph databases (cont.)

Diagram illustrating a graph with nodes and edges representing entities and their relationships.

*— Slide 27 —*

---

## Graph databases (cont.)

An example of mobile users that can be stored in graph databases.

Node Data:

| number | age | gender | rnCode | promotion | noOfCall | noOfReceive |
|---|---|---|---|---|---|---|
| 089-1000000 | 23 | male | AIS | 703 B | 19 | 19 |
| 089-1000001 | 20 | female | AIS | 422 B | 13 | 6 |
| 089-1000002 | 25 | male | DTAC | 574 B | 11 | 4 |
| 089-1000003 | 26 | female | AIS | 514 B | 20 | 1 |
| 089-1000004 | 20 | female | DTAC | 449 B | 9 | 20 |

Edge Data:

| a_number | b_number | startDate | startTime | callDay | duration |
|---|---|---|---|---|---|
| 089-1000038 | 089-1000060 | 20160108 | 20.52 | Sunday | 327 |
| 089-1000170 | 089-1000141 | 20160114 | 6.16 | Friday | 560 |
| 089-1000000 | 089-1000134 | 20160121 | 21.1 | Sunday | 197 |
| 089-1000153 | 089-1000188 | 20160110 | 1.36 | Wednesday | 202 |
| 089-1000190 | 089-1000065 | 20160114 | 17.3 | Saturday | 300 |

*— Slide 28 —*

---

## Graph databases (cont.)

For example, in Neo4J graph database, there are many functions to manage the data such as:

Return all nodes that match with the property:

```
MATCH (n:Node {property})
Return n
```

Ex:

```
MATCH (n:Node:{name: "Tomas"})
return n
```

Return all relations that match with the type and we can add the condition in the function:

```
MATCH (n:Node) -[r:type]-> (m:Node)
WHERE condition
Return r
```

Ex:

```
(n:Node) -[r:Call]-> (m:Node)
WHERE r.startTime > 12.00 AND r.duration < 60
return r
```

*— Slide 29 —*

---

## Graph databases (cont.)

- Problems that lend themselves to representations as networks of connected entities are well suited for graph databases.
- Application that need to focus on relations of entities.

Criteria
- Network and IT infrastructure management
- Recommending products and services
- Social networking

Use cases

*— Slide 30 —*

---

## Graph databases (cont.)

Graph-based software:

- Neo4j
- OrientDB
- Amazon Neptune
- Virtuoso
- ArangoDB

*— Slide 31 —*
