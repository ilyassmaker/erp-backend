# erp_app/utils.py

from .ml.prediction import predict_statut_risque
from .models import Facture, Commande
from django.db.models import Sum

def predire_risque_facture(client_id):
    """
    Calcule les features au niveau client et renvoie:
        {'risque': score_label, 'niveau': 'faible'/'modéré'/'élevé'}
    """
    # 1) Récupère toutes les factures du client
    factures = Facture.objects.filter(commande__client_id=client_id)
    # 2) Construit les features agrégées
    montant_total = float(factures.aggregate(total=Sum('montant_total'))['total'] or 0)
    nb_relances = factures.aggregate(r=Sum('relances__count'))['r'] or 0
    # pour chaque facture, récupère premier paiement
    delai_list = []
    for f in factures:
        p = f.paiement_set.order_by('date_paiement').first()
        if p:
            delai_list.append((p.date_paiement - f.date_facture).days)
    delai_paiement = sum(delai_list)/len(delai_list) if delai_list else 0
    nb_commandes_client = Commande.objects.filter(client_id=client_id).count()
    total_achats_client = montant_total
    # moyenne des retards historiques
    retard_list = delai_list
    moyenne_retard_client = sum(retard_list)/len(retard_list) if retard_list else 0

    feats = {
        'montant_total': montant_total,
        'nb_relances': nb_relances,
        'delai_paiement': delai_paiement,
        'nb_commandes_client': nb_commandes_client,
        'total_achats_client': total_achats_client,
        'moyenne_retard_client': moyenne_retard_client,
    }
    label = predict_statut_risque(feats)
    # Mapping label→niveau
    niveau = {0: 'élevé', 1: 'modéré', 2: 'faible'}[label]
    return {'label': label, 'niveau': niveau}
