# ATLAS-OPS

## Autonomous Payment Operations Platform

ATLAS-OPS is a backend application built using FastAPI, PostgreSQL, Redis, and Docker to simulate end-to-end payment transaction workflows. The platform demonstrates concepts such as transaction processing, fraud detection, payment gateway routing, idempotency handling, and transaction status tracking.

---

## Features

- Process payment transactions through REST APIs
- Track transaction status and payment outcomes
- Prevent duplicate transaction processing using Redis-based idempotency handling
- Perform fraud detection before transaction execution
- Evaluate payment gateway health for routing decisions
- Redirect transactions to alternative gateways when the primary gateway is unavailable
- Generate AI-powered explanations for failed transactions
- Store transaction data using PostgreSQL
- Containerized development environment using Docker

---

## System Workflow

1. User submits a payment transaction.
2. System generates and validates an idempotency key.
3. Redis checks whether the transaction has already been processed.
4. Fraud detection module evaluates the transaction.
5. Gateway health evaluation determines the most suitable gateway.
6. Transaction is routed for processing.
7. If the selected gateway is unavailable, fallback routing is performed.
8. Transaction status is stored in PostgreSQL.
9. If the transaction fails, an AI-generated explanation is returned.

---

## Tech Stack

### Backend
- FastAPI
- Python

### Database
- PostgreSQL

### Cache
- Redis

### Containerization
- Docker

### AI / Machine Learning
- Scikit-learn
- Gemini API

---

## API Endpoints

### Transactions

#### Create Transaction
```http
POST /transactions
```

Creates a new payment transaction.

#### Get Transaction Status

```http
GET /transactions/{transaction_id}
```

Returns the current status of a transaction.

---

### Gateway Services

#### Check Gateway Health

```http
GET /gateways/health
```

Returns gateway availability information.

---

### Transaction Explanations

#### Generate Failure Explanation

```http
GET /transactions/{transaction_id}/explanation
```

Returns an AI-generated explanation for failed transactions.

---

## Database

PostgreSQL is used to store:

- Transaction records
- Payment status information
- Gateway details
- Fraud detection results

---

## Redis Usage

Redis is used for idempotency handling.

When a transaction request is received:

- A unique idempotency key is generated.
- Redis stores the processed request.
- Repeated requests with the same key return the previous result.
- Duplicate transaction execution is prevented.

---

## Running Locally

### Prerequisites

- Python 3.10+
- PostgreSQL
- Redis
- Docker (optional)

### Clone Repository

```bash
git clone https://github.com/tailormst/Atlas_OPS.git
cd Atlas_OPS
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Configure Environment

Create a `.env` file and add:

```env
DATABASE_URL=
REDIS_URL=
GEMINI_API_KEY=
```

### Run Application

```bash
uvicorn app.main:app --reload
```

Application runs at:

```text
http://localhost:8000
```

---

## Learning Outcomes

Through this project, I gained practical experience with:

- FastAPI backend development
- REST API design
- PostgreSQL database integration
- Redis caching and idempotency handling
- Payment workflow simulation
- Fraud detection concepts
- Payment gateway routing
- Docker-based development workflows

---

## Future Improvements

- Integration with real payment gateways
- Authentication and authorization
- Monitoring dashboards
- Advanced fraud detection models
- Transaction analytics and reporting

---

## Author

**Mohammed Saifuddin Tailor**

GitHub: https://github.com/tailormst
