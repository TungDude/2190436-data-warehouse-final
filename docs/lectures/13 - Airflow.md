# Airflow

_Total slides: 23_

---

## Cover

2190436 Data Warehousing (Year 4)

2190518 Data Engineering and Big Data (Year 3)

Workflow Management with Airflow

Prof. Peerapon Vateekul, Ph.D.

Department of Computer Engineering, Faculty of Engineering, Chulalongkorn University

peerapon.v@chula.ac.th

Credit to Prof. Natawut's slide

*— Slide 1 —*

---

## Content

- Motivation
- What is Apache Airflow?
- Operators & Examples
- Use Cases
- Hands-on Lab

*— Slide 2 —*

---

## Motivation

Credit to Prof. Natawut's slide

*— Slide 3 —*

---

## Medallion Architecture?

- Lakehouse design pattern organizing data into bronze (raw), silver (cleaned), and gold (aggregated) layers for progressive data quality refinement.

Reference: https://www.databricks.com/blog/what-is-medallion-architecture

*— Slide 4 —*

---

## Medallion Architecture? (cont.)

- Bronze (Raw Layer) [Raw Data]
  - Raw data from sources (Kafka, logs, DB)
  - No cleaning, no transformation
  - Used for audit & replay
- Silver (Processed Layer) [ETL]
  - Cleaned and structured data
  - Handle missing, duplicates, schema
  - Ready for analytics
- Gold (Business Layer) [Data Analytics]
  - Aggregated & summarized data
  - Used for dashboards, BI, ML
  - High business value

*— Slide 5 —*

---

## Medallion Architecture? (cont.)

- Requires schedulers and involves multiple data pipeline workflows -> "DataOps"
- Workflow management (Airflow) is needed!

*— Slide 6 —*

---

## What is Apache Airflow?

Credit to Prof. Natawut's slide

*— Slide 7 —*

---

## Apache Airflow

- Open-source workflow management platform for data engineering pipelines (originally developed at Airbnb in 2014)
- Follows the principle of "configuration as code"
  - Uses Directed Acyclic Graphs (DAGs) to define and orchestrate workflows
  - Tasks and dependencies are defined in Python (often within a single file)
  - DAGs can be triggered by schedules (time-based) or external events
  - Handles task scheduling and execution automatically
- Provides a web-based UI for monitoring and managing workflows

*— Slide 8 —*

---

## Airflow Components

- DAG (Directed Acyclic Graph): A workflow (pipeline) composed of tasks with defined dependencies
- Task: Basic unit of execution (instance of an operator with unique ID)
- Operator: Template for tasks (e.g., Bash, Python, Email, Sensors, TaskFlow)
- Others: Hooks, XComs, Triggers, Pools, Variables

*— Slide 9 —*

---

## Example DAG

- Task1 (hello) uses an operator (a predefined task).
- Task2 (airflow) creates an ad-hoc task.
- DAG with 2 tasks

*— Slide 10 —*

---

## Operators & Examples

Credit to Prof. Natawut's slide

*— Slide 11 —*

---

## Airflow Common Operators

- BashOperator - executes a bash command
- PythonOperator - calls an arbitrary Python function
- EmailOperator - sends an email
- SimpleHttpOperator - sends an HTTP request
- MySqlOperator, SqliteOperator, PostgresOperator, MsSqlOperator, OracleOperator, JdbcOperator, etc. - executes a SQL command
- Sensor - an Operator that waits (polls) for a certain time, file, database row, S3 key, etc.
- Other specific operators: DockerOperator, HiveOperator, S3FileTransformOperator, PrestoToMySqlTransfer, SlackAPIOperator, etc.

*— Slide 12 —*

---

## Example 1: Simple BashOperator

```python
from airflow.utils.dates import days_ago
from airflow import DAG
from airflow.operators.bash import BashOperator

# declare a DAG
with DAG(dag_id='dsde_simplebash', start_date=days_ago(1)):

    # declare a TASK
    echo = BashOperator(task_id='echo_template',
        bash_command='echo "run_id = {{ run_id }} and ds = {{ ds }}"')
```

- `run_id`: a unique identifier for each DAG run
- `ds`: an execution date, e.g., 2026-04-21

The exit code of the program/script will determine the result of the task execution:

- 0 - Success
- 99 - Skipped
- Something else - Failed

*— Slide 13 —*

---

## Example 2: Task Dependency

```python
from airflow.utils.dates import days_ago
from airflow import DAG
from airflow.operators.bash import BashOperator

# declare a DAG
with DAG(dag_id='dsde_simplebash_2', start_date=days_ago(1)):

    # declare 2 TASKS
    echo = BashOperator(task_id='echo_template',
        bash_command='echo "run_id = {{ run_id }} and ds = {{ ds }}"')
    echo2 = BashOperator(task_id='echo_template_2',
        bash_command='echo "[2] run_id = {{ run_id }} and ds = {{ ds }}"')

    # declare dependency
    echo >> echo2
```

*— Slide 14 —*

---

## Example 3: Concurrent Tasks

```python
from airflow.utils.dates import days_ago
from airflow import DAG

from airflow.operators.bash import BashOperator
from airflow.operators.dummy import DummyOperator

# 'with' enables DAG to become context managers; automatically assign new operators to that DAG
with DAG('concurrent_dag', start_date=days_ago(1)) as dag:
    start = DummyOperator(task_id='start_task')
    ping = BashOperator(task_id='cp_check', bash_command='curl https://www.eng.chula.ac.th')
    ping2 = BashOperator(task_id='eng_check', bash_command='curl https://www.eng.chula.ac.th')
    ping3 = BashOperator(task_id='inform_status', bash_command='echo "CP website still works!"')

    # creating DAG dependencies can be a long flow or multiple short flows
    # start >> [ping, ping2] >> inform
    start >> [ping, ping2]
    ping >> inform
    ping2 >> inform
```

*— Slide 15 —*

---

## Example 4: PythonOperator

```python
from airflow.utils.dates import days_ago
from airflow import DAG

from airflow.operators.bash import BashOperator
from airflow.operators.dummy import DummyOperator
from airflow.operators.python import PythonOperator

def show_status(web1, web2):
    print('All websites are running!')
    print('web1 = ', web1)
    print('web2 = ', web2)
    print('---- DONE ----')

# 'with' enables DAG to become context managers; automatically assign new operators to that DAG
with DAG('python_operator', start_date=days_ago(1)) as dag:
    start = DummyOperator(task_id='start_task')
    ping = BashOperator(task_id='cp_check', bash_command='curl https://www.cp.eng.chula.ac.th')
    ping2 = BashOperator(task_id='eng_check', bash_command='curl https://www.eng.chula.ac.th')
    inform = PythonOperator(task_id='inform_status', python_callable=show_status,
        op_args=[ping.output, ping2.output])

    # creating DAG dependencies can be a long flow or multiple short flows
    # start >> [ping, ping2] >> inform
    start >> [ping, ping2]
    ping >> inform
    ping2 >> inform
```

*— Slide 16 —*

---

## Example 5: PythonBranchOperator

```python
from airflow import DAG
from airflow.operators.python import BranchPythonOperator
from airflow.operators.dummy import DummyOperator
from datetime import datetime

def _choose_best_model(accuracy):
    if accuracy > 0.8:
        return 'accurate'
    return 'inaccurate'

with DAG('branch_oper', start_date=datetime(2021, 1, 1), catchup=False) as dag:
    choose_best_model = BranchPythonOperator(task_id='choose_best_model',
        python_callable=_choose_best_model, op_args=[0.75])

    accurate = DummyOperator(task_id='accurate')
    inaccurate = DummyOperator(task_id='inaccurate')

    choose_best_model >> [accurate, inaccurate]
```

Diagram: Training ML model A/B/C feed into `Choose Best ML`, which branches to either `is accurate` or `is inaccurate`.

*— Slide 17 —*

---

## Use Cases

Credit to Prof. Natawut's slide

*— Slide 18 —*

---

## Use Cases

- ETL Pipelines that extract data from multiple sources and run Spark jobs or any other data transformations
- Collecting Sensor data and move to Data Lake/Data warehouse
- Training machine learning models
- Orchestrating automated testing
- Report generation

*— Slide 19 —*

---

## Hands-on Lab

Credit to Prof. Natawut's slide

*— Slide 20 —*

---

## EC2+Kafka vs. Amazon MSK

| Our Lab: EC2 + Airflow | Amazon Managed Workflows for Apache Airflow (MWAA) (not free) |
|---|---|
|  | A managed service for Apache Airflow that makes it easy for data engineers and data scientists to execute data processing workflows on AWS |

*— Slide 21 —*

---

## Code 1: test_dag.py

```python
import pendulum
from airflow import DAG

from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator

def show_status(web1, web2):
    print('All websites are running!')
    print('web1 = ', web1)
    print('web2 = ', web2)
    print('---- DONE ----')

# 'with' enables DAG to become context managers; automatically assign new operators to that DAG
with DAG('test_dag', start_date=pendulum.now()) as dag:
    start = EmptyOperator(task_id='start_task')
    ping = BashOperator(task_id='cp_check', bash_command='curl https://www.cp.eng.chula.ac.th')
    ping2 = BashOperator(task_id='eng_check', bash_command='curl https://www.eng.chula.ac.th')
    inform = PythonOperator(task_id='inform_status', python_callable=show_status,
        op_args=[ping.output, ping2.output])

    # creating DAG dependencies can be a long flow or multiple short flows
    # start >> [ping, ping2] >> inform
    start >> [ping, ping2]
    ping >> inform
    ping2 >> inform
```

DAG diagram: `start_task` -> `cp_check` and `eng_check` (both BashOperator) -> `inform_status` (PythonOperator).

*— Slide 22 —*

---

## Code 2: test_dag_cron.py

```python
import pendulum
from airflow import DAG

from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator

def show_status(web1, web2):
    print('All websites are running!')
    print('web1 = ', web1)
    print('web2 = ', web2)
    print('---- DONE ----')

# 'with' enables DAG to become context managers; automatically assign new operators to that DAG
with DAG('test_dag', start_date=pendulum.now('utc').add(days=-1), schedule_interval='*/5 * * * *', catchup=False) as dag:
    start = EmptyOperator(task_id='start_task')
    ping = BashOperator(task_id='cp_check', bash_command='curl https://www.cp.eng.chula.ac.th')
    ping2 = BashOperator(task_id='eng_check', bash_command='curl https://www.eng.chula.ac.th')
    inform = PythonOperator(task_id='inform_status', python_callable=show_status,
        op_args=[ping.output, ping2.output])

    # creating DAG dependencies can be a long flow or multiple short flows
    # start >> [ping, ping2] >> inform
    start >> [ping, ping2]
    ping >> inform
    ping2 >> inform
```

Cron preset reference table:

| Preset | Meaning | Cron |
|---|---|---|
| `@once` | Schedule once and only once | n/a |
| `@hourly` | Run once an hour at the beginning of the hour | `0 * * * *` |
| `@daily` | Run once a day at midnight | `0 0 * * *` |
| `@weekly` | Run once a week at midnight on Sunday morning | `0 0 * * 0` |
| `@monthly` | Run once a month at midnight on the first day of month | `0 0 1 * *` |
| `@yearly` | Run once a year at midnight on January 1 | `0 0 1 1 *` |

*— Slide 23 —*
