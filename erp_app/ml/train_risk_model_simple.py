# erp_app/ml/train_risk_model_simple.py

import pandas as pd
import joblib
from collections import Counter
from pathlib import Path

from sklearn.model_selection import train_test_split, StratifiedKFold, GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix

# 1) Définir les chemins
ROOT = Path().resolve()  # répertoire racine du projet (là où est manage.py)
ML_DIR = ROOT / "erp_app" / "ml"
CSV_PATH = ROOT / "factures_training_dataset_v3.csv"  # chemin vers ton CSV
MODEL_OUT = ML_DIR / "model_risque_facture_simple.joblib"

# 2) Charger le dataset
print(f"Chargement du dataset depuis: {CSV_PATH}")
df = pd.read_csv(CSV_PATH)

# 3) Vérifier la répartition initiale des statuts
initial_counts = Counter(df["statut_final_facture"])
print("Distribution initiale des statuts de facture :", initial_counts)

# Vérifier présence de la classe 'impayée'
if initial_counts.get("impayée", 0) == 0:
    raise ValueError(
        "Le dataset ne contient aucune facture impayée. "
        "Merci de régénérer le CSV avec des statuts 'impayée'."
    )

# 4) Encoder le label
df["label"] = df["statut_final_facture"].map({"impayée": 0, "partielle": 1, "payée": 2})

# 5) Sélection des features
num_feats = [
    "montant_total", "nb_relances", "delai_paiement",
    "nb_commandes_client", "total_achats_client", "moyenne_retard_client"
]
cat_feats = ["type_client"]  # toujours 'client'

# 6) Préprocessing des colonnes
num_pipe = Pipeline([
    ("imputer", SimpleImputer(strategy="median")),
    ("scaler", StandardScaler())
])
cat_pipe = Pipeline([
    ("ohe", OneHotEncoder(handle_unknown="ignore"))
])
preprocessor = ColumnTransformer([
    ("num", num_pipe, num_feats),
    ("cat", cat_pipe, cat_feats)
])

# 7) Pipeline avec gestion du déséquilibre
pipeline = Pipeline([
    ("preproc", preprocessor),
    ("clf", RandomForestClassifier(class_weight="balanced_subsample", random_state=42))
])

# 8) Split train/test
X = df[num_feats + cat_feats]
y = df["label"]
X_train, X_test, y_train, y_test = train_test_split(
    X, y, stratify=y, test_size=0.2, random_state=42
)
print("Répartition des classes (train) :", Counter(y_train))

# 9) GridSearchCV pour optimiser quelques hyper-paramètres
param_grid = {
    "clf__n_estimators": [100, 200],
    "clf__max_depth": [None, 10],
    "clf__min_samples_split": [2, 5]
}
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
grid = GridSearchCV(pipeline, param_grid, cv=cv, scoring="f1_weighted", n_jobs=-1, verbose=1)
grid.fit(X_train, y_train)

print("Meilleur score CV :", grid.best_score_)
print("Meilleurs params   :", grid.best_params_)

# 10) Évaluation finale
best = grid.best_estimator_
y_pred = best.predict(X_test)
unique_labels = sorted(set(y_test))
label_names = {0: "impayée", 1: "partielle", 2: "payée"}
target_names = [label_names[lbl] for lbl in unique_labels]
print(classification_report(y_test, y_pred, labels=unique_labels, target_names=target_names))
print("Confusion matrix:\n", confusion_matrix(y_test, y_pred, labels=unique_labels))

# 11) Sauvegarder le modèle
joblib.dump(best, MODEL_OUT)
print("✅ Modèle sauvegardé dans", MODEL_OUT)
