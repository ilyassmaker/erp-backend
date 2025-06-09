# erp_app/utils.py - Fixed version with all 7 features

from .ml.prediction import predict_statut_risque
from .models import Facture, Commande, Person, RelancePaiement
from django.db.models import Sum, Count
from django.core.exceptions import ObjectDoesNotExist
import logging

logger = logging.getLogger(__name__)


def predire_risque_facture(client_id):
    """
    Calcule les features au niveau client et renvoie:
        {'risque': score_label, 'niveau': 'faible'/'modéré'/'élevé'}
    
    Features attendues par le modèle:
    - 6 features numériques: montant_total, nb_relances, delai_paiement,
      nb_commandes_client, total_achats_client, moyenne_retard_client
    - 1 feature catégorielle: type_client
    """
    try:
        # Vérifier que le client existe
        client = Person.objects.get(id=client_id, type='client')
    except ObjectDoesNotExist:
        logger.error(f"Client avec ID {client_id} n'existe pas")
        raise ValueError(f"Client avec ID {client_id} n'existe pas")
    
    # 1) Récupère toutes les factures du client avec prefetch pour optimiser
    factures = Facture.objects.filter(
        commande__client_id=client_id
    ).prefetch_related('paiement_set', 'relances')
    
    # Si pas de factures, retourner risque faible par défaut
    if not factures.exists():
        logger.info(f"Client {client_id} n'a aucune facture, risque faible par défaut")
        return {'label': 2, 'niveau': 'faible'}
    
    # 2) Calculer montant_total
    montant_total = float(
        factures.aggregate(total=Sum('montant_total'))['total'] or 0
    )
    
    # 3) Calculer nb_relances - total des relances pour ce client
    nb_relances = RelancePaiement.objects.filter(
        facture__commande__client_id=client_id
    ).count()
    
    # 4) Calculer delai_paiement - délai moyen entre facture et premier paiement
    delai_list = []
    for facture in factures:
        premier_paiement = facture.paiement_set.order_by('date_paiement').first()
        if premier_paiement:
            delai = (premier_paiement.date_paiement - facture.date_facture).days
            delai_list.append(max(0, delai))  # Éviter les délais négatifs
    
    delai_paiement = sum(delai_list) / len(delai_list) if delai_list else 0
    
    # 5) Calculer nb_commandes_client
    nb_commandes_client = Commande.objects.filter(client_id=client_id).count()
    
    # 6) Calculer total_achats_client (identique à montant_total dans ce contexte)
    total_achats_client = montant_total
    
    # 7) Calculer moyenne_retard_client (identique à delai_paiement dans ce contexte)
    moyenne_retard_client = delai_paiement
    
    # 8) Type client - IMPORTANT: cette feature était manquante!
    type_client = 'client'  # Toujours 'client' dans ce contexte
    
    # Préparer les features dans l'ordre exact attendu par le modèle
    feats = {
        'montant_total': montant_total,
        'nb_relances': nb_relances,
        'delai_paiement': delai_paiement,
        'nb_commandes_client': nb_commandes_client,
        'total_achats_client': total_achats_client,
        'moyenne_retard_client': moyenne_retard_client,
        'type_client': type_client  # AJOUT DE LA FEATURE MANQUANTE
    }
    
    logger.debug(f"Features calculées pour client {client_id}: {feats}")
    
    try:
        label = predict_statut_risque(feats)
    except Exception as e:
        logger.error(f"Erreur lors de la prédiction pour client {client_id}: {str(e)}")
        raise
    
    # Mapping label→niveau
    niveau_map = {0: 'élevé', 1: 'modéré', 2: 'faible'}
    niveau = niveau_map.get(label, 'modéré')
    
    result = {'label': label, 'niveau': niveau}
    logger.info(f"Prédiction pour client {client_id}: {result}")
    
    return result


def categoriser_risque(score):
    """
    Catégorise un score de risque en niveau textuel
    
    Args:
        score: float entre 0 et 1
        
    Returns:
        str: 'faible', 'modéré' ou 'élevé'
    """
    if score < 0.3:
        return 'faible'
    elif score < 0.7:
        return 'modéré'
    else:
        return 'élevé'