# Kafka

_Total slides: 30_

---

## Cover

2190436 Data Warehousing (Year 4)
2190518 Data Engineering and Big Data (Year 3)

**Data Ingestion with Kafka**

Prof. Peerapon Vateekul, Ph.D.
Department of Computer Engineering,
Faculty of Engineering, Chulalongkorn University
peerapon.v@chula.ac.th

Credit to Prof. Natawut's slide

*— Slide 1 —*

---

## Content

- Motivation
- What is Apache Kafka?
- Kafka Architecture & Components
- Use Cases
- Hands-on Lab

*— Slide 2 —*

---

## Motivation

Credit to Prof. Natawut's slide

*— Slide 3 —*

---

## Typical Website Architecture

Diagram showing a typical website architecture with frontend, backend, and logging components.

*— Slide 4 —*

---

## What if your website has one million active users?

Need multiple servers & multiple logs.

Diagram showing a Load Balancing System distributing traffic across multiple servers, each generating its own logs.

*— Slide 5 —*

---

## Log consolidation is needed!

- A single backend may not be enough, so multiple backends are needed!
- There can be many backend systems!
- Thus, there are multiple frontends (logs; producers) & multiple backends (consumers)!
- Point-to-point data pipeline is problematic!

*— Slide 6 —*

---

## Using middleware (broker) to handle complexity called "Decoupled data pipeline"

Diagram illustrating how a middleware broker decouples producers from consumers, simplifying the data pipeline.

*— Slide 7 —*

---

## What is Kafka?

Credit to Prof. Natawut's slide

*— Slide 8 —*

---

## Kafka

- Popular event stream processing from LinkedIn
- Distributed publish-subscribe messaging system and a robust queue that can handle a high volume of data
- Kafka messages are persisted on the disk and replicated within the cluster to prevent data loss.
- The Kafka cluster stores streams of records in categories called topics
  - Each record consists of a key, a value, and a timestamp
- Kafka is very fast and guarantees zero downtime and zero data loss.

*— Slide 9 —*

---

## Kafka Basic Concept

- Kafka's components: (1) Producer, (2) Broker, (3) Consumer
- Publish-Subscribe Messaging System: Producers publish messages to topics, and consumers subscribe to those topics.

*— Slide 10 —*

---

## Kafka Topic

- Events or records are stored in "topics" (queue).
- Topic allows multi-producer and multi-consumer.
- A consumer keeps track of the current record being consumed with "offset" (event order id).
- A consumer auto commits offset periodically.

Notes:

- With a single producer, message order within a topic can be preserved.
- With multiple producers, ordering depends on arrival time (first-come, first-served).

*— Slide 11 —*

---

## Partition

- Partition is a disjoint subset of a topic.
- Smaller queues, faster ingestion from producers and faster delivery to consumers (via parallel processing).

Diagram: One topic with 4 partitions.

*— Slide 12 —*

---

## Kafka Architecture & Components

Credit to Prof. Natawut's slide

*— Slide 13 —*

---

## Kafka's Components

- 1) Producer
- 2) Broker
- 3) Consumer/Consumer Group
- 4) Topic
- 5) Partition
- 6) Replica

*— Slide 14 —*

---

## Component 1: Producer (2 producers & 3 partitions)

Diagram showing two producers writing to a topic divided into three partitions.

- Normally, each partition contains a different set of data (not duplicate); except when we set a replication factor: active & passive partitions.
- More partitions means more parallelism; however, the order can be destroyed!

*— Slide 15 —*

---

## Component 2: Broker with Replica — Kafka Architecture

Diagram of Kafka architecture with brokers and replicas.

- Replication factor = 2; there are 3 servers, so each partition is distributed into all servers.

*— Slide 16 —*

---

## Component 3: Consumer — Kafka Components

- Producers
  - The publisher of messages to one or more Kafka topics
  - Producers send data to Kafka brokers
  - Every time a producer publishes a message to a broker, the broker simply appends the message to the last segment partition
- Topics
  - A stream of messages belonging to a particular category is called a topic
  - One topic can be stored in many partitions
- Broker
  - Simple system responsible for maintaining the published data
- Consumers (Consumer Group, messaging load balancing)
  - Consumers read data from brokers
  - Consumers subscribe to one or more topics and consume published messages by pulling data from the brokers
  - Consumer Group, messaging load balancing

*— Slide 17 —*

---

## Consumer Group Example 1

Diagram showing a basic consumer group example with multiple consumers reading from a topic.

*— Slide 18 —*

---

## Consumer Group Example 2 (with Partitions)

- All consumers must send heartbeats every `heartbeat.interval.ms`
- A consumer who has been out of contact for `session.timeout.ms` will be kicked out of the group
- A group will be rebalanced if there is no consumer processes records within `max.poll.interval.ms`

*— Slide 19 —*

---

## Use Cases

Credit to Prof. Natawut's slide

*— Slide 20 —*

---

## 1) Log Aggregation

Diagram illustrating Kafka used for log aggregation across multiple sources.

*— Slide 21 —*

---

## 2) Log Shipping

Diagram illustrating Kafka used for log shipping between systems.

*— Slide 22 —*

---

## 3) Event Driven Processing (Stream Processing)

Diagram illustrating Kafka used for event-driven stream processing.

*— Slide 23 —*

---

## 4) Kafka @ Pinterest

- Real-time processing (speed path)
- Batch processing (batch path)

Diagram showing Pinterest's lambda-style architecture with both speed and batch paths fed by Kafka.

*— Slide 24 —*

---

## 5) Kafka in Gaming Industry

- Use multiple topics; each topic corresponds to a microservice.

*— Slide 25 —*

---

## Hands-on Lab

Credit to Prof. Natawut's slide

*— Slide 26 —*

---

## EC2 + Kafka vs. Amazon MSK

| Option | Description |
|---|---|
| Our Lab: EC2 + Kafka | Self-managed Kafka on EC2 |
| Amazon MSK | Managed Kafka service (not free) |

*— Slide 27 —*

---

## Lab 1: Simple Example

Mode 1: Streaming (iterator)

```python
for message in consumer:
    print('[{}:{}] {}'.format(...))
```

(2 s)

Mode 2: Polling

```python
results = consumer.poll(timeout_ms=1000)
# Polling and waiting max time 1 sec, then return "no message"
```

(3 s)

*— Slide 28 —*

---

## Lab 2: More Complex Example

2 Threads:

- Thread 1: consumer --> streaming
- Thread 2: monitor interval 10 sec --> counter & send to notification

*— Slide 29 —*

---

## Lab 3: Consumer Group

Example flow:

```
DCBA -> Partition 0: A, C
        Partition 1: B, D
```

Diagram showing how messages D, C, B, A are distributed across partitions and consumed by a consumer group.

*— Slide 30 —*
