import os
import joblib
import numpy as np
from django.conf import settings
from .models import Facture

MODEL_PATH = os.path.join(settings.BASE_DIR, 'erp_app', 'ml', 'model_risque_facture.joblib')

def predire_risque_facture(client_id: int):
    """Retourne un score de risque de non-paiement pour un client.

    Si le modèle n'est pas disponible, ``None`` est renvoyé.
    """
    if not os.path.exists(MODEL_PATH):
        return None

    model = joblib.load(MODEL_PATH)

    factures = Facture.objects.filter(commande__client_id=client_id)
    nb_factures = factures.count()
    nb_impayes = factures.filter(statut__in=['impayée', 'partielle']).count()
    features = np.array([[nb_factures, nb_impayes]])

    if hasattr(model, 'predict_proba'):
        proba = model.predict_proba(features)[0, 1]
    else:
        proba = model.predict(features)[0]

    return float(proba)
