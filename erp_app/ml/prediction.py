# erp_app/ml/prediction.py - Fixed version

import numpy as np
from sklearn.linear_model import LinearRegression
from erp_app.models import VenteHistorique
import joblib
import os
import logging

logger = logging.getLogger(__name__)

# Fonction existante pour prédiction de ventes
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


# Chemin vers le modèle entraîné
MODEL_PATH = os.path.join(os.path.dirname(__file__), "model_risque_facture_simple.joblib")

# Charger le modèle une seule fois au démarrage
try:
    MODEL = joblib.load(MODEL_PATH)
    logger.info(f"Modèle de risque chargé depuis {MODEL_PATH}")
except Exception as e:
    logger.error(f"Erreur lors du chargement du modèle: {e}")
    MODEL = None

# Les 7 features dans l'ordre exact attendu par le modèle
# 6 numériques + 1 catégorielle
NUMERICAL_FEATURES = [
    "montant_total",
    "nb_relances",
    "delai_paiement",
    "nb_commandes_client",
    "total_achats_client",
    "moyenne_retard_client"
]

CATEGORICAL_FEATURES = ["type_client"]

ALL_FEATURES = NUMERICAL_FEATURES + CATEGORICAL_FEATURES


def predict_statut_risque(feature_dict):
    """
    feature_dict: dict contenant les 7 clés (6 numériques + 1 catégorielle)
    Retourne: int label prédit (0=impayée, 1=partielle, 2=payée)
    
    Mapping des labels:
    - 0: risque élevé (impayée)
    - 1: risque modéré (partielle)
    - 2: risque faible (payée)
    """
    if MODEL is None:
        raise RuntimeError("Le modèle n'est pas chargé. Vérifiez le fichier model_risque_facture_simple.joblib")
    
    # Vérifier que toutes les features sont présentes
    missing_features = set(ALL_FEATURES) - set(feature_dict.keys())
    if missing_features:
        raise ValueError(f"Features manquantes: {missing_features}")
    
    # Créer le vecteur de features dans l'ordre exact
    # Important: l'ordre doit correspondre exactement à celui utilisé lors de l'entraînement
    feature_values = []
    
    # D'abord les features numériques
    for feat in NUMERICAL_FEATURES:
        value = feature_dict[feat]
        # S'assurer que c'est un nombre
        try:
            value = float(value)
        except (TypeError, ValueError):
            logger.warning(f"Valeur non numérique pour {feat}: {value}, utilisation de 0")
            value = 0.0
        feature_values.append(value)
    
    # Puis la feature catégorielle
    feature_values.append(feature_dict['type_client'])
    
    # Créer un DataFrame pour maintenir les noms de colonnes
    # (nécessaire pour que le ColumnTransformer fonctionne correctement)
    import pandas as pd
    X = pd.DataFrame([feature_values], columns=ALL_FEATURES)
    
    logger.debug(f"Features pour prédiction: {X.to_dict('records')[0]}")
    
    try:
        # Faire la prédiction
        prediction = MODEL.predict(X)[0]
        prediction_int = int(prediction)
        
        # Optionnel: obtenir les probabilités
        if hasattr(MODEL, 'predict_proba'):
            probas = MODEL.predict_proba(X)[0]
            logger.debug(f"Probabilités: impayée={probas[0]:.2f}, partielle={probas[1]:.2f}, payée={probas[2]:.2f}")
        
        logger.info(f"Prédiction: {prediction_int} ({'impayée' if prediction_int == 0 else 'partielle' if prediction_int == 1 else 'payée'})")
        
        return prediction_int
        
    except Exception as e:
        logger.error(f"Erreur lors de la prédiction: {str(e)}")
        raise