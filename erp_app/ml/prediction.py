import numpy as np
from sklearn.linear_model import LinearRegression
from erp_app.models import VenteHistorique

def predire_vente_mois_prochain(produit_id):
    ventes = VenteHistorique.objects.filter(produit_id=produit_id).order_by("mois")

    if ventes.count() < 2:
        return "Pas assez de données"

    # Création d'un index temporel mensuel : 0, 1, 2, ...
    X = np.arange(len(ventes)).reshape(-1, 1)
    y = np.array([v.quantite for v in ventes])

    model = LinearRegression()
    model.fit(X, y)

    # Prédiction pour le mois suivant
    mois_suivant = len(ventes)
    prediction = model.predict(np.array([[mois_suivant]]))[0]

    return round(prediction, 2)

# erp_app/ml/prediction.py

import joblib
import numpy as np
import os

# Chemin vers le modèle entraîné
MODEL_PATH = os.path.join(os.path.dirname(__file__), "model_risque_facture_simple.joblib")
MODEL = joblib.load(MODEL_PATH)

# Les 6 features dans l'ordre attendu
FEATURES = [
    "montant_total",
    "nb_relances",
    "delai_paiement",
    "nb_commandes_client",
    "total_achats_client",
    "moyenne_retard_client"
]

def predict_statut_risque(feature_dict):
    """
    feature_dict: dict contenant les 6 clés FEATURES
    Retourne: int label prédict (0=impayée,1=partielle,2=payée)
    """
    X = np.array([[feature_dict[f] for f in FEATURES]])
    return int(MODEL.predict(X)[0])
