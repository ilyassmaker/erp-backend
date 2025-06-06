# ⚙️ ERP Backend - Django REST API

This is the backend of the ERP system, built with **Django** and **Django REST Framework**, powering all the business logic and data handling for:

- ✅ Clients & Fournisseurs
- ✅ Produits & Stocks
- ✅ Commandes & Achats
- ✅ Factures automatiques
- ✅ Paiements partiels
- ✅ Transactions de trésorerie
- ✅ Relance automatique des impayés

---

## 🚀 Tech Stack

- 🐍 Django 5+
- 🧩 Django REST Framework
- 🧠 PostgreSQL or SQLite
- 📄 ReportLab (PDF generation)
- 📬 CORS / JWT / API token ready

---

## 📦 Installation (dev)

```bash
# 1. Clone le repo
git clone git@github.com:ilyassmaker/erp-backend.git
cd erp-backend

# 2. Crée un environnement virtuel
python -m venv venv
source venv/bin/activate

# 3. Installe les dépendances
pip install -r requirements.txt

# 4. Applique les migrations
python manage.py migrate

# 5. Lance le serveur local
python manage.py runserver
