# Redis

_Total slides: 32_

---

## Cover

2190436 Data Warehousing (Year 4)
2190518 Data Engineering and Big Data (Year 3)

Redis

Prof. Peerapon Vateekul, Ph.D.
Department of Computer Engineering,
Faculty of Engineering, Chulalongkorn University
peerapon.v@chula.ac.th

*— Slide 1 —*

---

## What is Redis?

REmote DIctionary Server

an open source, advanced key-value store.

Memory-based, very fast read and write (> 100,000 records/sec)

*— Slide 2 —*

---

## Key-Value?

- Redis keeps key-value pairs
  - Every item is stored as key + value
- Keys are unique identifiers
- Values can be different data structures

Example

| KEY | VALUE |
|---|---|
| firstname | Kawin |
| lastname | Rakdee |
| country | Thailand |

*— Slide 3 —*

---

## Keys

- Redis keys are binary safe.
  - this means that you can use any binary sequence as a key, from strings to files such as JPEG
- Maximum size is 512 MB
- But very big keys are not a good idea

*— Slide 4 —*

---

## Redis Value Data Types

- Be able to support various data types called "rich data structure database"
  - String — Basic data type, including numeric, boolean. They are all treated as "String".
  - Lists
  - Sets
  - Sorted/Scored Sets
  - Hashes

(Lists, Sets, Sorted/Scored Sets, and Hashes are Collection Types.)

*— Slide 5 —*

---

## Redis Value Data Types

(Continued — section divider)

*— Slide 6 —*

---

## 1) Value Data Type: String

| Key | Value | |
|---|---|---|
| page:index | `<html><head>...` | -> Files |
| message_id | 123 | -> Integers |
| name:123 | Kawin | -> String |

All of the above are string data type.

*— Slide 7 —*

---

## JPEG as strings?

A JPEG image stored in Redis can also be viewed in string format.

*— Slide 8 —*

---

## Value Data Type: Strings (cont.)

- The Redis String type is the simplest type of value you can associate with a Redis key.
- The maximum size is 512 MB, like keys.

*— Slide 9 —*

---

## Data operations: String

Basic operations are SET GET and DEL

- `SET <key> <value>` -> creates the key-value data
- `GET <key>` -> returns the value of the key
- `DEL <key>` -> removes the key-value data from the database

*— Slide 10 —*

---

## Data operations: String (cont.)

There are also operations that works on strings that can be read as an integer such as

- `INCR <key>` -> increases the value by 1
- `INCRBY <key> <x>` -> increases the value by x
- `DECR <key>` -> decreases the value by 1
- `DECRBY <key> <x>` -> decreases the value by x

*— Slide 11 —*

---

## Data operations: String (cont.)

| Commands | KEY1 | VALUE |
|---|---|---|
| `SET post:1:likes 1` | post:1:likes | 1 |
| `INCR post:1:likes` | post:1:likes | 2 |
| `INCRBY post:1:likes 10` | post:1:likes | 12 |
| `DECR post:1:likes` | post:1:likes | 11 |
| `DECRBY post:1:likes 10` | post:1:likes | 1 |
| `DEL post:1:likes` | post:1:likes | NULL |

*— Slide 12 —*

---

## 2) Value Data Type: Lists

Visual: `a  a  b  c  d`

- Lists are sequence of strings
- Ordered by insertion order
- Allow duplication
- Is implemented as a linked list

*— Slide 13 —*

---

## Data operations: Lists (cont.)

- `LPUSH, RPUSH <key> <value>` -> push in value
- `LPOP, RPOP <key>` -> pop left or right values

*— Slide 14 —*

---

## Data operations: Lists (cont.)

- `LLEN <key>` -> get the length of the list
- `LINDEX <key> a` -> return value in index a
- `LRANGE <key> a b` -> return values from index a to b

*— Slide 15 —*

---

## Data operations: Lists (cont.)

- `LREM <key> <a> <b>` -> removes b, a times
  - if a<0 starts from the back of the list
  - if a=0 removes all b

Example list: `mylist  a  b  b  c  b`

| Command | Effect |
|---|---|
| `LREM mylist 1 b` | removes first `b` |
| `LREM mylist 0 b` | removes all `b` |
| `LREM mylist -2 b` | removes last 2 `b` from the back |

*— Slide 16 —*

---

## Value Data Type: Lists (cont.)

- Sample usages:
  - Timeline of a social network
    - LPUSH to add new items
    - LRANGE to retrieve most recently added items
  - LPUSH+LRANGE together to always keep top/latest N
    - Useful for logging of recent user actions / errors
  - Queue of jobs

*— Slide 17 —*

---

## 3) Value Data Type: Sets

Visual: `a  b  c  d  e`

- Unordered collection
- Does not allow duplicates

*— Slide 18 —*

---

## Data operations: Sets

- `SADD <key> <value>` -> adds member value to set
- `SREM <key> <value>` -> removes value from set
- `SMOVE <key_a> <key_b> <value>` -> move value from set of key_a to set of key_b

*— Slide 19 —*

---

## Data operations: Sets (cont.)

- `SCARD <key>` -> returns number of members in set
- `SISMEMBER <key> <value>` -> check if value is in set
- `SMEMBERS <key>` -> returns all members of the set

*— Slide 20 —*

---

## Data operations: Sets (cont.)

- `SINTER/SUNION <key1> <key2> <key3> ...`
  -> returns all members of the intersection/union of value of key1, key2, key3 and so on

*— Slide 21 —*

---

## Value Data Type: Sets (cont.)

- Sample usages:
  - Tracking unique IPs (just use SADD every view, then use SCARD whenever you want)
  - Tagging: Use a set for each tag (each member is a picture ID). You can easily get all pictures that have 3 different tags using SINTER
  - Storing relations (i.e. followers, friends etc.) — the key represents the User ID, the value (set members) is the unique users they follow.

*— Slide 22 —*

---

## 4) Value Data Type: Sorted Sets

Visual: `E:4  D:5  A:6  C:6  B:20`

- Similar to sets but each member has a "score" that are used to sort

*— Slide 23 —*

---

## Data operations: Sorted Sets

- Uses Z instead of S, for example
  - SADD => ZADD
  - SCARD => ZCARD
  - E.g. `ZADD <key> <score> <value>`
  - `ZADD sorted 6 C`

Key: `sorted`
Value: `E:4  D:5  A:6  C:6  B:20`

*— Slide 24 —*

---

## Data operations: Sorted Sets (cont.)

Additional operations includes score

- `ZSCORE <key> <member>` -> returns score of the member
- `ZRANK <key> <member>` -> returns index of the member
- `ZRANGE <key> <start> <stop>` -> returns member from index a to b

Sorted set: `E:4  D:5  A:6  C:6  B:20`

| Command | Result |
|---|---|
| `ZSCORE sorted D` | 5 |
| `ZRANK sorted D` | 1 |
| `ZRANGE sorted 2 3` | A, C |

*— Slide 25 —*

---

## Value Data Type: Sorted Sets (cont.)

- Sample usages:
  - Maintain a leader board of a game, get top X etc.
  - In general, any top something. Such as top posts by pageviews etc.
  - Search text statistics

*— Slide 26 —*

---

## 5) Value Data Type: Hash

- Hashes stores a mapping of keys to value
- Therefore it can also be called a map
- Usually used to store objects

| Key | Field | Value |
|---|---|---|
| user:13 | name | Bob |
| user:13 | age | 29 |
| user:13 | gender | m |
| user:13 | active | 1 |

*— Slide 27 —*

---

## Data operations: Hash

- `HSET <key> hkey1 hvalue1` -> stores one hash of hkey1:hvalue1
- `HMSET <key> hkey1 hvalue1 hkey2 hvalue2 ...` -> stores a set of hash of hkey1:hvalue1 hkey2:hvalue2 ...
- `HGET <key> hkey` -> returns value of the hkey in hash

| Key | Field | Value |
|---|---|---|
| product:1 | created_at | 102374657 |
| product:1 | product_id | 1 |
| product:1 | name | Twinkies |
| product:1 | available | 10 |

*— Slide 28 —*

---

## Data operations: Hash (cont.)

- `HLEN hash` -> returns length of the hash
- `HKEYS hash` -> returns all keys of the hash
- `HGETALL hash` -> returns all key and value pairs

*— Slide 29 —*

---

## Value Data Type: Hash (cont.)

- Sample usages:
  - Saving properties of a business object (very similar to plain DB table)
  - Saving sessions

*— Slide 30 —*

---

## Scaling Redis

- Persistence (auto-save)
  - Redis provides two mechanisms to deal with persistence: Redis database snapshots (RDB) and append-only files (AOF).
  - Redis usually executes data in-memory, so this feature will automatically save data in the memory to disk.
- Replication (copying data)
  - A Redis instance known as the master, ensures that one or more instances known as the slaves, become exact copies of the master. Clients can connect to the master or to the slaves. Slaves are read only by default.
- Partitioning (balancing data)
  - Breaking up data and distributing it across different hosts in a cluster.
  - Can be implemented in different layers:
    - Client: Partitioning on client-side code.
    - Proxy: An extra layer that proxies all redis queries and performs partitioning (i.e. Twemproxy).
    - Query Router: instances will make sure to forward the query to the right node. (i.e Redis Cluster).
- Failover (auto-recovery)
  - Manual
  - Automatic with Redis Sentinel (for master-slave topology)
  - Automatic with Redis Cluster (for cluster topology)

*— Slide 31 —*

---

## AWS Key-Value Database

| Feature | 1) Redis | 2) ElastiCache | 3) DynamoDB |
|---|---|---|---|
| Type | Engine | Managed Service | Database |
| Storage | Memory (RAM) | Memory (RAM) | Disk (SSD) |
| Speed | Ultra-fast | Ultra-fast | Fast |
| Persistence | Limited | Optional | Full |
| Scaling | Manual | Managed | Automatic |
| Use Case | Cache | Production cache | Main database |

*— Slide 32 —*
