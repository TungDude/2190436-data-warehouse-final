# Spark Basic

_Total slides: 40_

---

## Cover

2190436 Data Warehousing (Year 4)
2190518 Data Engineering and Big Data (Year 3)

Apache Spark

Prof. Peerapon Vateekul, Ph.D.
Department of Computer Engineering,
Faculty of Engineering, Chulalongkorn University
peerapon.v@chula.ac.th

*— Slide 1 —*

---

## Content

- Introduction to Apache Spark
- How does Spark work?
- Spark MLlib & ML

*— Slide 2 —*

---

## Introduction to Apache Spark

Section divider.

*— Slide 3 —*

---

## What is Apache Spark?

- Apache Spark is a fast and general-purpose cluster computing system
- In-memory processing on distributed dataset on distributed memory/disk
- Automatically rebuilt on failure
- Provides high-level APIs in Java, Scala, Python and R
- Rich set of higher-level tools
  - SparkSQL
  - MLlib
  - ML
  - Graphx
  - SparkStreaming
  - More
- Core foundation for modern data platforms (e.g., Databricks, cloud-native analytics stacks)

*— Slide 4 —*

---

## Speed

- Run up to 100x faster than Hadoop MapReduce in memory
- Apache Spark has an advanced DAG execution engine that supports cyclic data flow and in-memory computing

Reference: https://spark.apache.org/

*— Slide 5 —*

---

## Ease of use

- Write applications quickly in Java, Scala, Python and R
- Spark offers over 80 high-level operators that make it easy to build parallel apps
- can use it interactively from the Scala, Python and R shells

Languages illustrated: Python, Scala.

*— Slide 6 —*

---

## Generality

- Combine SQL, Streaming and complex analytics
- Spark powers a stack of libraries including SQL and DataFrames, MLlib for machine learning, GraphX, and Spark Streaming
- You can combine these libraries seamlessly in the same application

*— Slide 7 —*

---

## Run everywhere

- Spark can run on
  - Hadoop(Yarn)
  - Mesos
  - Spark Standalone
  - On the cloud
- Spark can access data source from
  - HDFS
  - Cassandra
  - Hbase
  - S3
  - Hive
  - Any Hadoop data source

*— Slide 8 —*

---

## Community

- Spark is fully open source
- Since 2009
  - built by a wide set of developers from over 200 companies
  - more than 1000 developers have contributed to Spark
- Since 2010
  - Spark has become one of the most active projects in Big Data.
  - Spark has actually taken over Hadoop MapReduce and every other engine that we are aware of in terms of number of people contributing to it.

*— Slide 9 —*

---

## Compare to Hadoop

Diagram comparing Spark to Hadoop architectures.

*— Slide 10 —*

---

## Compared to standalone R, Python

Diagram contrasting two execution models across Node 1-4 over HDFS:

- Standalone R, Python: data is pulled to a single Compute step then merged from HDFS.
- Spark: compute runs in parallel on each node (Node 1, Node 2, Node 3, Node 4) directly over HDFS.

*— Slide 11 —*

---

## Conclusion

Section summary slide.

*— Slide 12 —*

---

## How does Spark work?

Section divider.

*— Slide 13 —*

---

## Apache Spark in this session

- Apache Spark Core (SparkContext)
  - RDD
- Apache Spark SQL (SparkSession)
  - DataFrame
- Apache Spark MLlib & ML
  - MLlib : machine learning for Spark RDD
    - will not add new features
    - May be deprecated in future release (Spark 2.2)
    - May be removed in future release (Spark 3.0)
  - ML : machine learning for Spark Dataframe
    - "Spark ML" is not an official name but occasionally used to refer to the MLlib DataFrame-based API
    - DataFrames provide a more user-friendly API than RDDs

*— Slide 14 —*

---

## Resilient Distributed Datasets (RDDs)

- Immutable representation of data
- Operations on one RDD creates a new one
- Memory caching layer that stores data in a distributed, fault-tolerant cache
- Created by parallel transformations on data in stable storage
- Lazy materialization

Diagram: Resilient Distributed Datasets (RDD) shown as RAM blocks across COM 1, COM 2, COM 3, COM 4, COM ...

*— Slide 15 —*

---

## Operations

- Spark has certain operations which can be performed on RDD
- 1) Transformation (from RDD to RDD):
  - Transformation refers to the operation applied on a RDD to create new RDD
  - Lazy operations to build RDDs from other RDDs
  - When perform transform operation, it will only store the step of transformation
  - filter, groupBy, map, flatmap
- 2) Action (from RDD to output):
  - Actions refer to an operation which also applies on RDD, that instructs Spark to perform computation on all steps of transformation and action then send the result (output) back to driver
  - Return a result or write it to storage
  - take, collect, reduce
- Example pyspark transformation and action operations :
  - https://www.analyticsvidhya.com/blog/2016/10/using-pyspark-to-perform-transformations-and-actions-on-rdd/
  - http://spark.apache.org/docs/latest/programming-guide.html#transformations
  - http://spark.apache.org/docs/latest/api/python/pyspark.html

*— Slide 16 —*

---

## Operations

- Python :

```python
data = sc.textFile("File Path")
rdd1 = data.map(lambda x : x.split(","))
rdd2 = rdd1.map(lambda x : tuple(x))
rdd3 = rdd2.groupByKey()
rdd4 = rdd3.mapValues(list)

count = rdd4.count()        # Action
result = rdd4.collect()     # Action
```

Diagram: Data goes through a chain of Transform steps, then two Action branches produce two Results.

*— Slide 17 —*

---

## Operations

- Python :

```python
data = sc.textFile("File Path")
rdd1 = data.map(lambda x : x.split(","))
rdd2 = rdd1.map(lambda x : tuple(x))
rdd3 = rdd2.groupByKey()
rdd4 = rdd3.mapValues(list)
rdd4.cache()

count = rdd4.count()        # Action
result = rdd4.collect()     # Action

rdd4.unpersist()
```

Diagram: Same Transform chain as before, but `rdd4.cache()` stores the result so both Action branches reuse the cached data.

*— Slide 18 —*

---

## Basic Spark Operation: RDD - Transformation

| Operation | Description |
|---|---|
| `map(f, preservesPartitioning=False)` | Return a new RDD by applying a function to each element of this RDD. |
| `flatMap(f, preservesPartitioning=False)` | Return a new RDD by first applying a function to all elements of this RDD, and then flattening the results. |
| `filter(f)` | Return a new RDD containing only the elements that satisfy a predicate. |
| `sample(withReplacement, fraction, seed=None)` | Return a sampled subset of this RDD. |
| `union(other)` | Return the union of this RDD and another one. |
| `intersection(other)` | Return the intersection of this RDD and another one. The output will not contain any duplicate elements, even if the input RDDs did. |
| `distinct(numPartitions=None)` | Return a new RDD containing the distinct elements in this RDD. |
| `zip(other)` | Zips this RDD with another one, returning key-value pairs with the first element in each RDD second element in each RDD, etc. Assumes that the two RDDs have the same number of partitions and the same number of elements in each partition. |
| `zipWithUniqueId()` | Zips this RDD with generated unique Long ids. |
| `reduceByKey(func, numPartitions=None)` | Merge the values for each key using an associative and commutative reduce function. This will also perform the merging locally on each mapper before sending results to a reducer, similarly to a "combiner" in MapReduce. |

http://spark.apache.org/docs/latest/api/python/pyspark.html#pyspark.RDD

*— Slide 19 —*

---

## Basic Spark Operation: RDD - Transformation

Input: `[1,2,3,4,5]`

```python
rdd.map(lambda x : x + 1)
```

Output: `[2,3,4,5,6]`

Map: input 1 -> output 1

*— Slide 20 —*

---

## Basic Spark Operation: RDD - Transformation

Input: `[i love u, u love him]`

```python
rdd.flatMap(lambda x : x.split(" "))
```

Output: `[I, love, u, u, love, him]`

flatMap: input 1 -> output n (0, n)

*— Slide 21 —*

---

## Basic Spark Operation: RDD - Transformation

Input: `[I, love, u, u, love, him]`

```python
rdd.filter(lambda x : len(x) > 1)
```

Output: `[love, love, him]`

*— Slide 22 —*

---

## Basic Spark Operation: RDD - Transformation

Input: `[I, love, u, u, love, him]`

```python
rdd.distinct()
```

Output: `[I, love, u, him]`

*— Slide 23 —*

---

## Basic Spark Operation: RDD - Transformation

Input: `[love, love, him]`

```python
rdd.zipWithUniqueId()
```

Output: `[(love,1), (love,2), (him,3)]`

*— Slide 24 —*

---

## Basic Spark Operation: RDD - Transformation

Inputs: `[A, B, C]`, `[1, 2, 3]`

```python
rdd1.zip(rdd2)
```

Output: `[(A,1), (B,2), (C,3)]`

*— Slide 25 —*

---

## Basic Spark Operation: RDD - Transformation

Input: `[(A,2), (A,1), (B,1), (A,1)]`

```python
rdd.reduceByKey(lambda x,y: x+y)
```

Output: `[(A,4), (B,1)]`

*— Slide 26 —*

---

## Basic Spark Operation: RDD - Action

| Operation | Description |
|---|---|
| `reduce(f)` | Reduces the elements of this RDD using the specified commutative and associative binary operator. Currently reduces partitions locally. |
| `collect()` | Return a list that contains all of the elements in this RDD. |
| `take(num)` | Take the first num elements of the RDD. |
| `top(num, key=None)` | Get the top N elements from an RDD. |
| `count()` | Return the number of elements in this RDD. |
| `saveAsTextFile(path, compressionCodecClass=None)` | Save this RDD as a text file, using string representations of elements. |
| `countByKey()` | Count the number of elements for each key, and return the result to the master as a dictionary. |

http://spark.apache.org/docs/latest/api/python/pyspark.html#pyspark.RDD

*— Slide 27 —*

---

## Basic Spark Operation: RDD - Action

Input: `[(A,2), (A,1), (B,1), (A,1)]`

```python
rdd.countByKey()
```

Output: `[(A,3), (B,1)]`

*— Slide 28 —*

---

## Basic Spark Operation: DataFrame

| Operation | Description |
|---|---|
| `printSchema()` | Prints out the schema in the tree format. |
| `show(n=20, truncate=True)` | Prints the first n rows to the console. |
| `selectExpr(*expr)` | Projects a set of SQL expressions and returns a new DataFrame. This is a variant of select() that accepts SQL expressions. |
| `withColumn(colName, col)` | Returns a new DataFrame by adding a column or replacing the existing column that has the same name. |
| `withColumnRenamed(existing, new)` | Returns a new DataFrame by renaming an existing column. This is a no-op if schema doesn't contain the given column name. |
| `sample(withReplacement, fraction, seed=None)` | Returns a sampled subset of this DataFrame. |
| `union(other), intersect(other)` | Return a new DataFrame containing union of rows in this frame and another frame. Return a new DataFrame containing rows only in both this frame and another frame. |
| `groupBy(*cols)` | Groups the DataFrame using the specified columns, so we can run aggregation on them. See GroupedData for all the available aggregate functions. |
| `createOrReplaceTempView(name)` | Creates or replaces a local temporary view with this DataFrame. |
| `count()` | Returns the number of rows in this DataFrame. |
| `columns` | Returns all column names as a list. |

http://spark.apache.org/docs/latest/api/python/pyspark.sql.html

*— Slide 29 —*

---

## Basic Spark Operation (cont.): DataFrame

| Operation | Description |
|---|---|
| `select(*cols)` | Projects a set of expressions and returns a new DataFrame. |
| `drop(*cols)` | Returns a new DataFrame that drops the specified column. This is a no-op if schema doesn't contain the given column name(s). |
| `dropDuplicates(subset=None)` | Return a new DataFrame with duplicate rows removed, optionally only considering certain columns. |
| `dropna(how='any', thresh=None, subset=None)` | Returns a new DataFrame omitting rows with null values. DataFrame.dropna() and DataFrameNaFunctions.drop() are aliases of each other. |
| `fillna(value, subset=None)` | Replace null values, alias for na.fill(). DataFrame.fillna() and DataFrameNaFunctions.fill() are aliases of each other. |
| `filter(condition), where(condition)` | Filters rows using the given condition. where() is an alias for filter(). |
| `collect()` | Returns all the records as a list of Row. |
| `rdd` | Returns the content as an pyspark.RDD of Row. |

http://spark.apache.org/docs/latest/api/python/pyspark.sql.html

*— Slide 30 —*

---

## Basic Spark Operation: DataFrame

Input:

| Name | Gender | Salary |
|---|---|---|
| A | M | 24,000 |
| B | M | 25,000 |
| C | F | 36,000 |

Create new column:

```python
df.withColumn("SalaryK", df["Salary"] / 1000)
```

Output:

| Name | Gender | Salary | SalaryK |
|---|---|---|---|
| A | M | 24,000 | 24 |
| B | M | 25,000 | 25 |
| C | F | 36,000 | 36 |

*— Slide 31 —*

---

## Basic Spark Operation: DataFrame

Input:

| Name | Gender | Salary |
|---|---|---|
| A | M | 24,000 |
| B | M | 25,000 |
| C | F | 36,000 |

Replace:

```python
df.withColumn("Salary", df["Salary"] / 1000)
```

Output:

| Name | Gender | Salary |
|---|---|---|
| A | M | 24 |
| B | M | 25 |
| C | F | 36 |

*— Slide 32 —*

---

## Basic Spark Operation: DataFrame

Input:

| Name | Gender | Salary |
|---|---|---|
| A | M | 24 |
| B | M | 25 |
| C | F | 36 |

Just rename, no compute:

```python
df.withColumnRenamed("Salary", "SalaryK")
```

Output:

| Name | Gender | SalaryK |
|---|---|---|
| A | M | 24 |
| B | M | 25 |
| C | F | 36 |

*— Slide 33 —*

---

## Basic Spark Operation: DataFrame

Input:

| Name | Gender | Salary |
|---|---|---|
| A | M | 24 |
| B | M | 25 |
| C | F | 36 |

```python
df.filter(df["SalaryK"] > 30)
df.where(df["SalaryK"] > 30)
```

Output:

| Name | Gender | SalaryK |
|---|---|---|
| A | M | 24 |
| B | M | 25 |
| C | F | 36 |

*— Slide 34 —*

---

## Basic Spark Operation: DataFrame

Input:

| Name | Gender | Salary |
|---|---|---|
| A | M | 24 |
| B | M | 25 |
| C | F | 36 |

```python
df.select("Gender", "SalaryK")
```

Output:

| Gender | SalaryK |
|---|---|
| M | 24 |
| M | 25 |
| F | 36 |

*— Slide 35 —*

---

## Spark ML

Section divider.

*— Slide 36 —*

---

## Basic Spark RDD Operation: Spark ML

Diagram of the ML training/prediction pipeline:

- Training Data -> Estimator (Classifier) -- Train model (fit) --> Model (Trained Classifier)
- Testing Data -> Model -- Predict (transform) --> Test Result

*— Slide 37 —*

---

## Basic Spark Operation: Abstract Class Estimator (Spark ML)

| Operation | Description |
|---|---|
| `fit(dataset, params=None)` | Fits a model to the input dataset with optional parameters. **Parameters:** `dataset` - input dataset, which is an instance of `pyspark.sql.DataFrame`; `params` - an optional param map that overrides embedded params. If a list/tuple of param maps is given, this calls fit on each param map and returns a list of models. **Returns:** fitted model(s). |

Other method in Specific Estimator use to assign parameter for specific algorithm.

Example : DecisionTreeClassifier

- `fit(dataset, params=None)`
- `setFeaturesCol(value)`
- `setLabelCol(value)`
- `setImpurity(value)`
- `setMaxBins(value)`
- `setMaxDepth(value)`
- `setMinInfoGain(value)`
- `setMinInstancesPerNode(value)`
- `setSeed(value)`

http://spark.apache.org/docs/latest/api/python/pyspark.ml.html
http://spark.apache.org/docs/latest/api/python/pyspark.mllib.html

*— Slide 38 —*

---

## Basic Spark Operation: Abstract Class Model (Spark ML)

| Operation | Description |
|---|---|
| `transform(dataset, params=None)` | Transforms the input dataset with optional parameters. **Parameters:** `dataset` - input dataset, which is an instance of `pyspark.sql.DataFrame`; `params` - an optional param map that overrides embedded params. |
| `save(path)` | Save this ML instance to the given path, a shortcut of `write().save(path)`. |

Other method in Specific Model use to get some value and knowledge for specific algorithm.

http://spark.apache.org/docs/latest/api/python/pyspark.ml.html
http://spark.apache.org/docs/latest/api/python/pyspark.mllib.html

*— Slide 39 —*

---

## Spark ML API

Reference slide pointing to the Spark ML API.

*— Slide 40 —*
