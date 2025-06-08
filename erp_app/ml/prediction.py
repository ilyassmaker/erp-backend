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
