# 🌍 AI-Driven MSME Export Lead Matchmaker

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![React](https://img.shields.io/badge/React-Vite-61DAFB?logo=react)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)

---

# 📌 Project Overview

**AI-Driven MSME Lead Matchmaker** addresses a critical gap in global Business-to-Business (B2B) trade by connecting Indian Micro, Small and Medium Enterprises (MSMEs) with international buyers.

Traditional export portals require vendors to maintain digital profiles and frequently log into web platforms, creating a significant barrier for many small businesses. This project eliminates that barrier through an **Admin-managed AI-powered matchmaking system**.

The platform automatically processes unstructured buyer inquiries using **Natural Language Processing (NLP)**, predicts the required product category using **Machine Learning**, and intelligently assigns the inquiry to the most suitable MSME vendor. The selected vendor receives instant notifications via **SMS** and **Email**, requiring little to no technical interaction.

---

# ✨ Core Features

- 🤖 AI-powered NLP classification of export inquiries
- 📊 TF-IDF (Bigram) + Logistic Regression based category prediction
- ⚖️ Least-Leads-First intelligent load balancing algorithm
- 📱 Automated SMS notifications using Twilio API
- 📧 HTML Email notifications using SMTP
- 🖥️ Modern React Admin Dashboard
- 📂 Bulk upload and processing of buyer inquiries
- 🏭 Vendor directory management
- 📈 Persistent vendor workload tracking

---

# 🛠️ Tech Stack

### Frontend
- React.js
- Vite
- CSS

### Backend
- Python
- FastAPI
- Pandas

### Machine Learning
- Scikit-learn
- TF-IDF Vectorizer
- Logistic Regression

### Communication APIs
- Twilio SMS API
- SMTP Email

---

# 📊 Dataset

The system uses two primary datasets:

### Buyer Inquiry Dataset

**`b2b_export_inquiries.csv`**

Contains:

- Inquiry Text
- Buyer Country
- Product Category (Training Label)

---

### MSME Vendor Registry

**`msme_vendor_registry.csv`**

Contains:

- Vendor Details
- Contact Information
- Product Category
- Vendor Location

---

# ⚙️ Workflow

1. Admin uploads Buyer Inquiry CSV.
2. FastAPI preprocesses the inquiry.
3. NLP extracts textual features using TF-IDF.
4. Logistic Regression predicts the product category.
5. Vendors are filtered based on category.
6. Least-Leads-First algorithm selects the optimal vendor.
7. SMS notification is sent to the MSME.
8. HTML email is sent to the buyer.
9. Vendor workload database is updated.

---

# 📈 Results

- ✅ Successfully classified unstructured buyer inquiries.
- ✅ Automated vendor selection using intelligent routing.
- ✅ Achieved uniform lead distribution through persistent load balancing.
- ✅ Integrated Twilio SMS notifications.
- ✅ Integrated SMTP-based HTML Email notifications.
- ✅ Built a responsive React Admin Dashboard.

---

# 🚀 Installation

## Prerequisites

- Python 3.11+
- Node.js
- npm

---

## Clone Repository

```bash
git clone https://github.com/Viswa-S-2105/AI-Driven-MSME-Lead-Matchmaker.git

cd AI-Driven-MSME-Lead-Matchmaker
```

---

## Backend Setup

Create Virtual Environment

```bash
python -m venv .venv
```

Activate

### Windows

```bash
.venv\Scripts\activate
```

### Linux / macOS

```bash
source .venv/bin/activate
```

Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Environment Variables

Rename

```
.env.example
```

to

```
.env
```

Fill in:

- Twilio SID
- Twilio Auth Token
- Twilio Phone Number
- SMTP Email
- SMTP App Password

---

## Frontend Setup

```bash
cd frontend

npm install

npm run dev
```

---

## Start Backend

```bash
uvicorn main:app --reload
```

---

Open

```
http://localhost:5173
```

---

# 💻 Usage

1. Upload MSME Vendor Registry.
2. Upload Buyer Inquiry CSV.
3. Process inquiries.
4. Review AI predicted category.
5. Vendor receives SMS.
6. Buyer receives Email.

---

# 📂 Repository Structure

```
AI-Driven-MSME-Lead-Matchmaker
│
├── .venv/
│
├── frontend/
│   ├── dist/
│   ├── node_modules/
│   ├── public/
│   ├── src/
│   │   ├── assets/
│   │   ├── App.jsx
│   │   ├── BatchTransactionProcessing.jsx
│   │   ├── BuyerDirectory.jsx
│   │   ├── ConfirmModal.jsx
│   │   ├── Dashboard.jsx
│   │   ├── PostTransactionAudits.jsx
│   │   ├── VendorDirectory.jsx
│   │   ├── index.css
│   │   └── main.jsx
│   │
│   ├── .env.development
│   ├── .gitignore
│   ├── eslint.config.js
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   ├── README.md
│   └── vite.config.js
│
├── uploads/
│   └── .gitkeep
│
├── .env
├── .env.example
├── app.py
├── main.py
├── requirements.txt
│
├── b2b_export_inquiries.csv
├── expanded_inquiries.csv
├── master_buyers_db.csv
├── master_vendors_db.csv
├── msme_vendor_registry.csv
├── port_transactions.csv
│
└── README.md
```

---

# 👥 Authors

- **Gokul K**
- **Jeffin Solomon Asir J S**
- **Dhanush T**
- **Viswa S**

**College of Engineering, Guindy**  
**Anna University, Chennai**

---

# 🔮 Future Work

- Replace TF-IDF with Transformer-based language models (BERT).
- Deploy using Docker and Kubernetes.
- Integrate PostgreSQL instead of CSV storage.
- Add multilingual NLP support.
- Cloud deployment on AWS or Azure.
- Upgrade to production Twilio messaging for full Unicode SMS support.
