# erp_app/signals.py

from datetime import timedelta, date
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum
from django.utils import timezone

from .models import (
    Commande,
    Achat,
    Facture,
    LigneCommande,
    LigneAchat,
    Paiement,
    TransactionTresorerie,
    VenteHistorique
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _refresh_facture_statut(facture: Facture):
    """Recalcule statut / reste après modif montant_total ou paiements."""
    total_paye = facture.paiement_set.aggregate(total=Sum("montant"))["total"] or 0
    facture.montant_paye = total_paye
    reste = facture.montant_total - total_paye

    if reste <= 0:
        facture.statut = "payée"
        facture.date_echeance_restant = None
    else:
        facture.statut = "partielle" if total_paye > 0 else "impayée"
        # Respecte la date d’échéance si déjà fixée, sinon on propose +7 jours
        if not facture.date_echeance_restant:
            facture.date_echeance_restant = date.today() + timedelta(days=7)

    facture.save(update_fields=["montant_paye", "statut", "date_echeance_restant"])


# ---------------------------------------------------------------------------
# Commande → Facture
# ---------------------------------------------------------------------------

@receiver(post_save, sender=Commande)
def create_or_update_facture_commande(sender, instance, created, **kwargs):
    # 1) Création → on ne fait ça qu'une seule fois
    if created:
        Facture.objects.create(
            commande=instance,
            montant_total=0,
            statut='en attente'
        )
        return

    # 2) Mise à jour → on ne touche qu'à la facture déjà existante
    try:
        facture = Facture.objects.get(commande=instance)
    except Facture.DoesNotExist:
        return

    # Recalcul du montant et du statut
    lignes = LigneCommande.objects.filter(commande=instance)
    total = sum((l.prix_unitaire or 0) * (l.quantite or 0) for l in lignes)
    facture.montant_total = total
    facture.commande_lignes.set(lignes)
    facture.save(update_fields=["montant_total"])
    _refresh_facture_statut(facture)


@receiver([post_save, post_delete], sender=LigneCommande)
def update_facture_on_lignecommande_change(sender, instance, **kwargs):
    commande = instance.commande
    try:
        facture = Facture.objects.get(commande=commande)
    except Facture.DoesNotExist:
        return
    lignes = LigneCommande.objects.filter(commande=commande)
    total = sum((l.prix_unitaire or 0) * (l.quantite or 0) for l in lignes)
    facture.montant_total = total
    facture.commande_lignes.set(lignes)
    facture.save(update_fields=["montant_total"])
    _refresh_facture_statut(facture)

@receiver(post_delete, sender=Commande)
def delete_facture_commande(sender, instance, **kwargs):
    Facture.objects.filter(commande=instance).delete()


# ---------------------------------------------------------------------------
# Achat → Facture
# ---------------------------------------------------------------------------

@receiver(post_save, sender=Achat)
def create_or_update_facture_achat(sender, instance, created, **kwargs):
    if created:
        Facture.objects.create(
            achat=instance,
            montant_total=0,
            statut='en attente'
        )
        return

    try:
        facture = Facture.objects.get(achat=instance)
    except Facture.DoesNotExist:
        return

    lignes = LigneAchat.objects.filter(achat=instance)
    total = sum((l.prix_unitaire or 0) * (l.quantite or 0) for l in lignes)
    facture.montant_total = total
    facture.achat_lignes.set(lignes)
    facture.save(update_fields=["montant_total"])
    _refresh_facture_statut(facture)

@receiver([post_save, post_delete], sender=LigneAchat)
def update_facture_on_ligneachat_change(sender, instance, **kwargs):
    achat = instance.achat
    try:
        facture = Facture.objects.get(achat=achat)
    except Facture.DoesNotExist:
        return
    lignes = LigneAchat.objects.filter(achat=achat)
    total = sum((l.prix_unitaire or 0) * (l.quantite or 0) for l in lignes)
    facture.montant_total = total
    facture.achat_lignes.set(lignes)
    facture.save(update_fields=["montant_total"])
    _refresh_facture_statut(facture)

@receiver(post_delete, sender=Achat)
def delete_facture_achat(sender, instance, **kwargs):
    Facture.objects.filter(achat=instance).delete()


# ---------------------------------------------------------------------------
# Paiement → Facture + Transaction + Liaison auto
# ---------------------------------------------------------------------------

@receiver(post_save, sender=Paiement)
def handle_paiement(sender, instance, created, **kwargs):
    if not created:
        return

    # Lier automatiquement la facture si absente
    if not instance.facture:
        if instance.type_reference == 'commande':
            facture = Facture.objects.filter(commande=instance.id_reference).first()
        elif instance.type_reference == 'achat':
            facture = Facture.objects.filter(achat=instance.id_reference).first()
        else:
            facture = None
        if facture:
            instance.facture = facture
            instance.save(update_fields=["facture"])
        else:
            return  # Pas de facture trouvée, on arrête ici

    facture = instance.facture

    # Créer une transaction liée
    type_transaction = "entrée" if facture.commande else "sortie" if facture.achat else "inconnu"

    TransactionTresorerie.objects.create(
        montant=instance.montant,
        type=type_transaction,
        date_transaction=instance.date_paiement,
        description=f"Paiement pour Facture #{facture.id}"
    )

    # Recalculer le statut de la facture
    _refresh_facture_statut(facture)


# ---------------------------------------------------------------------------
# Gestion de stock automatique
# ---------------------------------------------------------------------------

@receiver(post_save, sender=LigneCommande)
def diminuer_stock(sender, instance, created, **kwargs):
    if created:
        produit = instance.produit
        produit.stock -= int(instance.quantite)
        produit.save()

@receiver(post_save, sender=LigneAchat)
def augmenter_stock(sender, instance, created, **kwargs):
    if created:
        produit = instance.produit
        produit.stock += int(instance.quantite)
        produit.save()


@receiver(post_save, sender=LigneCommande)
def update_vente_historique(sender, instance, **kwargs):
    produit = instance.produit
    quantite = instance.quantite
    date_commande = instance.commande.date_commande or date.today()

    # ⚠️ Normalisation à 1er jour du mois
    mois_commande = date(date_commande.year, date_commande.month, 1)

    # 🔍 Historique existant pour ce produit
    existing = VenteHistorique.objects.filter(produit=produit).order_by("mois")

    if existing.count() == 1 and existing.first().mois == mois_commande:
        # Injecter automatiquement un mois précédent si nécessaire
        if mois_commande.month == 1:
            mois_precedent = date(mois_commande.year - 1, 12, 1)
        else:
            mois_precedent = date(mois_commande.year, mois_commande.month - 1, 1)

        # Répartition 50/50 (ou 60/40 si tu veux)
        q1 = quantite // 2
        q2 = quantite - q1

        # Créer ou maj mois précédent
        histo_prev, created_prev = VenteHistorique.objects.get_or_create(
            produit=produit,
            mois=mois_precedent,
            defaults={'quantite': q1}
        )
        if not created_prev:
            histo_prev.quantite += q1
            histo_prev.save()

        # Créer ou maj mois actuel
        histo_current, created_current = VenteHistorique.objects.get_or_create(
            produit=produit,
            mois=mois_commande,
            defaults={'quantite': q2}
        )
        if not created_current:
            histo_current.quantite += q2
            histo_current.save()

    else:
        # Comportement standard
        histo, created = VenteHistorique.objects.get_or_create(
            produit=produit,
            mois=mois_commande,
            defaults={'quantite': quantite}
        )
        if not created:
            histo.quantite += quantite
            histo.save()


@receiver(post_delete, sender=LigneCommande)
def retirer_vente_historique(sender, instance, **kwargs):
    produit = instance.produit
    quantite = instance.quantite
    date_commande = instance.commande.date_commande or date.today()
    mois_commande = date(date_commande.year, date_commande.month, 1)

    try:
        historique = VenteHistorique.objects.get(produit=produit, mois=mois_commande)
        historique.quantite -= quantite
        if historique.quantite <= 0:
            historique.delete()
        else:
            historique.save()
    except VenteHistorique.DoesNotExist:
        pass  # rien à faire si ça n'existe pas
