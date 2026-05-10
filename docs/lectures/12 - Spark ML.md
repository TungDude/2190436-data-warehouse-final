# Spark ML

_Total slides: 33_

---

## Cover

2190436 Data Warehousing (Year 4)
2190518 Data Engineering and Big Data (Year 3)

Prof. Peerapon Vateekul, Ph.D.
Department of Computer Engineering,
Faculty of Engineering, Chulalongkorn University
peerapon.v@chula.ac.th

*— Slide 1 —*

---

## Outlines

- Introduction to Spark ML
  - Overview
  - What is Spark?
  - Spark Machine Learning(ML) API
  - Comparison between Spark ML and Spark Mllib
  - Why Use Spark ML
- Coding with Spark ML
  - Programming Languages Supported by Spark ML
  - Components of a Spark ML Pipeline
  - Spark ML Pipelines
- Algorithms in Spark ML
- Summary

*— Slide 2 —*

---

## Introduction to Spark ML

Section divider.

*— Slide 3 —*

---

## What is Spark?

- General purpose distributed system.
  - With a really nice API including Python.
- Apache project (one of the most active).
- Much faster than Hadoop Map/Reduce.
- Good when data is too big for a single machine.
- Built on top of two abstractions for distributed data: RDDs & Datasets

*— Slide 4 —*

---

## Spark Machine Learning (ML) API

- The APIs for machine learning algorithms are standardized by Spark ML.
- With this, it is easy to combine various algorithms in a single workflow or pipeline.
- The key concepts related to Spark ML API are listed below.
- The first concept is of an ML dataset.
- Spark machine learning utilizes the Spark SQL DataFrame as a dataset.
- It can contain various types of data types; for example, a dataset can contain different columns that store feature vectors, predictions, true labels, and text.

*— Slide 5 —*

---

## Spark Machine Learning (ML) API (cont.)

- An estimator (e.g., fit, transform, predict, etc.) is another algorithm that can produce a transformer fitting on a DataFrame. For instance, a learning algorithm can train on a dataset and produce a model.
- A pipeline specifies an ML workflow by chaining various transformers and estimators together.

*— Slide 6 —*

---

## Comparison between Spark ML and Spark MLlib

- A few key features of Spark ML and Spark MLlib are represented in a tabular format below this table.

| Spark ML | Spark MLlib |
|---|---|
| Built on top of Spark DataFrame | Built on top of Spark RDD |
| Use pipeline to make combining multiple algorithms easy | Combining multiple algorithms is difficult |
| Can leverage catalyst engine optimization for SQL | Currently, supports more algorithms than Spark ML |

*— Slide 7 —*

---

## Why Use Spark ML

- Apart from the reasons mentioned in the previous section, there are several other reasons to use Spark ML over Spark MLlib.
- The sections below cover this in some detail.
  - 1. Solution to Machine Learning Scaling Challenges.
  - 2. Easy Data Transformation Enabled by DataFrame.
  - 3. Higher Speed of Execution Enabled by DataFrame.
  - 4. Ease of Creating Pipelines.
  - 5. The Future of Spark Machine Learning.

*— Slide 8 —*

---

## Why Use Spark ML — 1. Solution to Machine Learning Scaling Challenges

- There are certain machine learning scaling challenges Spark ML tends to solve, that cannot be effectively solved by other libraries including Spark MLlib.
- These challenges are showcased in the figure below.
- The size of circle is directly proportional to the size of the challenge.
- It is easy to see that we have classified hyper-parameter tuning as the most challenging task.

(Figure: Challenges with scaling machine learning capabilities.)

*— Slide 9 —*

---

## Why Use Spark ML — 2. Easy Data Transformation Enabled by DataFrame

- Spark ML is easy to use for common data transformation tasks such as projection, filtering, aggregation and joining.
- We explain this with the help of an example below.

(Figure: Dataset for analysis and Python code to calculate average age by department.)

*— Slide 10 —*

---

## Why Use Spark ML — 3. Higher Speed of Execution Enabled by DataFrame

- As introduced in section 2.1. DataFrames leverage the Catalyst Engine Optimization of SQLContext to perform operations in DataFrame objects.
- You will see that Spark DF (DataFrame) API for Python performs the aggregation five times faster than the Python RDD API, whereas the Scala DF API performs the same operation almost twice as fast as the Scala API for RDDs.

(Figure: Run time comparison between different APIs for performing the same task.)

*— Slide 11 —*

---

## Why Use Spark ML — 4. Ease of Creating Pipelines

- A practical ML pipeline often involves a sequence of data pre-processing, feature extraction, model fitting, and validation stages.
- Though there are many libraries we can use for each stage, connecting the dots is not as easy as it may look, especially with large-scale datasets.

(Figure: A typical Spark ML pipeline.)

*— Slide 12 —*

---

## Why Use Spark ML — 5. The Future of Spark Machine Learning

- Apart from the obvious technical benefits that Spark ML has, there is another important reason to shift from Spark MLlib to Spark ML.
- Spark MLlib has been of great importance in scalable enabling machine learning on Spark.
- However, time has come when MLlib has to be put on the back burner.
- As of the current version of Spark, MLlib is now in maintenance mode.
- A snapshot of the announcement posted on the official Spark website is shown in.
- Databricks is a unified data + AI platform built on top of Apache Spark that helps teams process data, build analytics, and develop AI/ML models—all in one place.

*— Slide 13 —*

---

## Coding with Spark ML

Section divider.

*— Slide 14 —*

---

## Programming Languages Supported by Spark ML

- As of now three languages are supported by the API – Python, Scala, R and JAVA.

*— Slide 15 —*

---

## Components of a Spark ML Pipeline

- (1) DataFrame:
  - Spark ML uses DataFrame rather than regular RDD as they hold a variety of data types (e.g., feature vectors, true labels, and predictions).
- (2) Transformer:
  - a transformer converts a DataFrame into another DataFrame usually by appending columns. (since Spark DataFrame is immutable, it actually creates a new DataFrame).
  - The implement method for a transformer is "transform()".
- (3) Estimator:
  - An Estimator is an algorithm which can be fit on a DataFrame to produce a Transformer.
  - Implements method fit() taking a DataFrame and a model (also a transformer) as input.

*— Slide 16 —*

---

## Components of a Spark ML Pipeline (cont.)

- (4) Pipeline:
  - Chains multiple Transformers and Estimators each as a stage to specify an ML workflow.
  - These stages are run in order, and the input DataFrame is transformed as it passes through each stage.
- (5) Parameter:
  - All Transformers and Estimators now share a common API for specifying parameters.
- (6) Evaluator:
  - Evaluate model performance.
  - The Evaluator can be a RegressionEvaluator for regression problems, a BinaryClassificationEvaluator for binary data, or a MulticlassClassificationEvaluator for multiclass problems.

*— Slide 17 —*

---

## Components of a Spark ML Pipeline (cont.)

(Figure: A generic flow of machine learning components.
a) Pipeline of machine learning components.
b) Reusing the pipeline on Test phase.)

*— Slide 18 —*

---

## Spark ML Pipelines (cont.)

- Consist of different stages (estimators or transformers)
- Themselves are an estimator

(Figure: Train and Test/Inference flow diagrams.)

*— Slide 19 —*

---

## Two main types of pipeline stages

(Figure: Diagram contrasting Transformer and Estimator stages within a Spark ML pipeline.)

*— Slide 20 —*

---

## Pipelines are estimators

Train:

```python
pipeline.fit(X_train, y_train)
```

*— Slide 21 —*

---

## Pipeline Models are transformers

Test/Inference:

```python
pred = pipeline.transform(X_test)
```

*— Slide 22 —*

---

## Example Step 1: Feature transformations

(Figure: Example illustrating feature transformation stages applied to input data.)

*— Slide 23 —*

---

## Example Step 2: Train a classifier on the transformed data

(Figure: Example illustrating fitting a classifier on the transformed feature data.)

*— Slide 24 —*

---

## Example Step 3: Train a classifier on the transformed data

(Figure: Continued example showing classifier training on the transformed data.)

*— Slide 25 —*

---

## Algorithms in Spark ML

Section divider.

*— Slide 26 —*

---

## Algorithms Supported by Spark ML

- Machine learning with SparkML is scalable and easy.
- Classification:
  - Logistic regression, Decision Tree Classifier, Random Forest Classifier, Gradient-Boosted Tree Classifier, Multilayer Perceptron Classifier, One-vs-Rest Classifier (a.k.a. One-vs-All), Naive Bayes.
- Regression:
  - Linear Regression, Generalized Linear Regression, Available Families, Decision Tree Regression, Random Forest Regression, Gradient-Boosted Tree Regression, Survival Regression, Isotonic Regression.

*— Slide 27 —*

---

## Algorithms Supported by Spark ML (Cont.)

- Machine learning with SparkML is scalable and easy.
- Clustering
  - K-Means, Latent Dirichlet Allocation (LDA), Bisecting K-Means, Gaussian Mixture Model (GMM).
- Collaborative filtering
  - Explicit Vs. Implicit Feedback, Scaling of the Regularization Parameter.
- Apart from machine learning algorithm Spark also offers tools for several different functions such as:
  - Featurization: feature extraction, transformation, dimensionality reduction, and selection
  - Pipelines: tools for constructing, evaluating, and tuning ML Pipelines
  - Persistence: saving and load algorithms, models, and Pipelines
  - Utilities: linear algebra, statistics, data handling, etc.

*— Slide 28 —*

---

## Algorithms Supported by Spark ML (Cont.)

- Few examples of (1) Feature Extractors, (2) Feature Transformers and (3) Feature Selectors are as follows:
- (1) Feature Extractors
  - TF-IDF
  - Word2Vec
  - CountVectorizer
- (2) Feature Selectors
  - VectorSlicer
  - Rformula
  - ChiSqSelector

*— Slide 29 —*

---

## Algorithms Supported by Spark ML (Cont.)

- (3) Feature Transformers
  - Tokenizer, StopWordsRemover, n-gram, Binarizer, PCA, PolynomialExpansion
  - Discrete Cosine Transform (DCT)
  - StringIndexer, IndexToString, OneHotEncoder, VectorIndexer, Normalizer
  - StandardScaler, MinMaxScaler, MaxAbsScaler, Bucketizer, ElementwiseProduct
  - SQLTransformer, VectorAssembler,
  - QuantileDiscretizer

*— Slide 30 —*

---

## Conclusion

Section divider.

*— Slide 31 —*

---

## Summary

- The scalable machine learning library of Spark is ML.
- Spark ML includes the Spark SQL DataFrame to support ML data types.
- A transformer consists of learned models and feature transformers.
- Workflows in Spark ML are represented through pipelines.

*— Slide 32 —*

---

## Reference

- https://yurongfan.wordpress.com/2017/01/10/introduction-of-a-big-data-machine-learning-tool-sparkml/
- https://www.simplilearn.com/spark-ml-programming-tutorial-video
- https://yurongfan.wordpress.com/2017/01/10/introduction-of-a-big-data-machine-learning-tool-sparkml/

*— Slide 33 —*
