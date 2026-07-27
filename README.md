# Ledger — Autonomous Document Intelligence Agent

<div align="center">

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/Python-3.12+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Latest-green)
![React](https://img.shields.io/badge/React-19-blue)
![TypeScript](https://img.shields.io/badge/TypeScript-5.x-blue)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED)
![LLM](https://img.shields.io/badge/AI-Multi%20Agent-purple)
![OCR](https://img.shields.io/badge/OCR-Document%20AI-orange)

### Enterprise Autonomous Document Processing & Decision Intelligence Platform

**Capture • Understand • Validate • Extract • Automate**

---

</div>

# Table of Contents

- Overview
- Problem Statement
- Solution
- Key Features
- System Architecture
- AI Agent Architecture
- Document Processing Pipeline
- Supported Documents
- OCR Engine
- Information Extraction
- Validation Engine
- Workflow Automation
- Technology Stack
- Repository Structure
- Security
- Installation
- Docker Deployment
- Environment Variables
- API Documentation
- Monitoring
- Performance
- Roadmap
- License

---

# Overview

Ledger is an enterprise-grade Autonomous Document Intelligence platform that automates the ingestion, understanding, validation, extraction, and processing of business documents using Artificial Intelligence.

The platform combines OCR, Large Language Models, computer vision, semantic understanding, and workflow automation to transform unstructured documents into structured, validated business data.

Ledger eliminates manual document processing while maintaining enterprise governance, auditability, and security.

---

# Problem Statement

Organizations process thousands of business documents every day.

Examples include:

- Invoices
- Purchase Orders
- Bank Statements
- Contracts
- Tax Documents
- HR Forms
- Insurance Claims
- Shipping Documents
- Receipts
- Vendor Agreements

Traditional document processing suffers from:

- Manual data entry
- Human errors
- Slow turnaround
- High operational costs
- Inconsistent validation
- Limited auditability
- Poor scalability

---

# Solution

Ledger introduces an autonomous multi-agent architecture that understands documents similarly to a human analyst.

Instead of only extracting text, Ledger:

- Understands document type
- Extracts structured information
- Validates business rules
- Detects anomalies
- Flags missing information
- Routes documents automatically
- Produces structured datasets
- Maintains complete audit history

---

# Key Features

## Intelligent Document Classification

Automatically identifies document types.

Supported documents include:

- Invoice
- Purchase Order
- Receipt
- Contract
- Salary Slip
- Tax Invoice
- Bank Statement
- Passport
- Aadhaar
- PAN Card
- Shipping Bill
- Delivery Challan
- Utility Bill

---

## OCR Engine

Supports:

- Scanned PDFs
- Images
- Multi-page documents
- Handwritten text (basic)
- Printed text
- Tables
- Signatures
- Stamps

Supported formats

- PDF
- PNG
- JPG
- TIFF
- DOCX

---

## AI Information Extraction

Automatically extracts:

Invoices

- Invoice Number
- Invoice Date
- Vendor
- GST Number
- Total Amount
- Tax
- Currency
- Line Items

Contracts

- Parties
- Effective Date
- Expiry Date
- Payment Terms
- Clauses
- Obligations

Bank Statements

- Transactions
- Account Number
- Balance
- Debit
- Credit

---

## Semantic Understanding

Ledger does more than OCR.

It understands:

- Document context
- Business entities
- Relationships
- Financial terminology
- Legal terminology
- Dates
- Currency
- Addresses

---

## Validation Engine

Every extracted field is validated.

Checks include:

- Required Fields
- Duplicate Detection
- Date Validation
- Currency Validation
- Tax Validation
- Business Rules
- Vendor Verification
- Purchase Order Matching

---

## Confidence Scoring

Every extracted value receives an AI confidence score.

Example

| Field | Confidence |
|--------|------------|
| Invoice Number | 99.8% |
| GST Number | 99.4% |
| Vendor Name | 98.9% |
| Tax Amount | 96.8% |

Low-confidence fields are automatically routed for human review.

---

## Human-in-the-Loop

If confidence falls below configured thresholds:

```
AI Extraction

↓

Validation

↓

Confidence Score

↓

Human Review

↓

Approval

↓

ERP Update
```

---

## Workflow Automation

Automated workflows include:

- Invoice Approval
- Vendor Verification
- Purchase Order Matching
- Finance Approval
- HR Onboarding
- Contract Review
- Claims Processing
- Document Archiving

---

# Multi-Agent Architecture

Ledger uses specialized AI agents.

```
Document Upload

↓

Classification Agent

↓

OCR Agent

↓

Layout Analysis Agent

↓

Entity Extraction Agent

↓

Validation Agent

↓

Decision Agent

↓

Workflow Agent

↓

Human Review (Optional)

↓

Business System
```

Each agent performs a specialized task, enabling higher accuracy and easier extensibility.

---

# Document Processing Pipeline

```
Upload

↓

OCR

↓

Document Classification

↓

Layout Detection

↓

Entity Extraction

↓

Business Rule Validation

↓

Confidence Scoring

↓

Human Approval

↓

ERP / Database

↓

Audit Logging
```

---

# Technology Stack

## Frontend

- React 19
- TypeScript
- Vite
- Tailwind CSS
- React Query
- Zustand
- PDF.js
- AG Grid

---

## Backend

- FastAPI
- Python 3.12
- SQLAlchemy
- Pydantic
- AsyncIO
- Celery

---

## AI Components

- OpenAI
- Claude
- Gemini
- Local LLMs
- OCR Engine
- Layout Detection Models
- Embedding Models

---

## Storage

- PostgreSQL
- Redis
- Object Storage (S3 / MinIO)

---

## Infrastructure

- Docker
- Nginx
- Prometheus
- Grafana
- OpenTelemetry

---

# Repository Structure

```
ledger/

├── frontend/
├── backend/
├── agents/
├── ocr/
├── extraction/
├── validation/
├── workflows/
├── storage/
├── monitoring/
├── docs/
├── tests/
├── docker/
├── README.md
└── LICENSE
```

---

# High-Level Architecture

```
            User

             │

             ▼

      React Web Portal

             │

             ▼

      FastAPI Backend

             │

     Document Manager

             │

             ▼

     Multi-Agent Engine

             │

 ┌───────────┼─────────────┐

 ▼           ▼             ▼

 OCR     Extraction    Validation

             │

             ▼

      Workflow Engine

             │

             ▼

 ERP / CRM / Database

             │

             ▼

 Monitoring & Audit
```

---

# Security

Enterprise Security Features

- JWT Authentication
- OAuth2
- RBAC
- Encrypted Storage
- Document Encryption
- Secure File Upload
- Audit Logging
- Virus Scanning
- API Rate Limiting

---

# API Endpoints

## Authentication

```
POST /api/v1/auth/login

POST /api/v1/auth/logout
```

---

## Documents

```
POST /api/v1/documents/upload

GET /api/v1/documents

GET /api/v1/documents/{id}

DELETE /api/v1/documents/{id}
```

---

## Extraction

```
POST /api/v1/extract

GET /api/v1/extract/{id}
```

---

## Validation

```
POST /api/v1/validate

GET /api/v1/confidence
```

---

## Workflow

```
POST /api/v1/workflows/run

GET /api/v1/workflows/history
```

---

## Administration

```
GET /api/v1/users

GET /api/v1/audit

GET /api/v1/system
```

---

# Environment Variables

```env
DATABASE_URL=

REDIS_URL=

JWT_SECRET=

SECRET_KEY=

OPENAI_API_KEY=

ANTHROPIC_API_KEY=

GOOGLE_API_KEY=

OCR_ENGINE=tesseract

OBJECT_STORAGE_ENDPOINT=

OBJECT_STORAGE_BUCKET=

ENABLE_AUDIT=true

ENABLE_OCR=true

ENABLE_HUMAN_REVIEW=true
```

---

# Installation

Clone Repository

```bash
git clone https://github.com/your-org/ledger.git
```

Backend

```bash
cd backend

pip install -r requirements.txt
```

Frontend

```bash
cd frontend

npm install
```

Run Backend

```bash
uvicorn app.main:app --reload
```

Run Frontend

```bash
npm run dev
```

---

# Docker Deployment

```bash
docker compose up --build
```

Services

- Frontend
- Backend
- PostgreSQL
- Redis
- Object Storage
- Worker
- Nginx

---

# Monitoring

Integrated with:

- Prometheus
- Grafana
- Loki
- OpenTelemetry
- Jaeger

Metrics

- Documents Processed
- OCR Accuracy
- Extraction Accuracy
- Validation Failures
- Human Review Rate
- Workflow Duration
- Agent Latency
- API Performance

---

# Performance Targets

| Metric | Target |
|---------|---------|
| OCR Processing | < 5 sec/document |
| Information Extraction | < 3 sec |
| End-to-End Processing | < 10 sec |
| Concurrent Documents | 2,000+ |
| Availability | 99.9% |

---

# Future Roadmap

## Version 1.1

- Intelligent Table Extraction
- Signature Verification
- Invoice-to-PO Matching
- Document Templates

## Version 1.2

- Knowledge Graph Extraction
- Contract Risk Analysis
- AI Document Summaries
- Multi-language Support

## Version 2.0

- Autonomous Document Agents
- Cross-Document Reasoning
- Enterprise Knowledge Graph
- Agentic Workflow Automation
- Self-Learning Validation Rules
- Regulatory Compliance Assistant
- Voice-Based Document Queries

---

# License

This project is licensed under the MIT License.

---

# Contributors

Ledger is a production-ready autonomous document intelligence platform designed for enterprise document automation, AI-assisted decision support, and workflow orchestration.

---

<div align="center">

# Ledger

### **From Documents to Decisions**

**OCR • AI Extraction • Validation • Workflow Automation • Enterprise Intelligence**

</div>
