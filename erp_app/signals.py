# erp_app/signals.py
from datetime import date, timedelta

from django.db.models.signals import post_save, post_delete
from django.dispatch           import receiver
from django.db.models          import Sum

from .models import (
    Commande,
    Achat,
    Facture,
    LigneCommande,
    LigneAchat,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _refresh_facture_statut(facture: Facture):
    """Recalcule montant_paye, statut et éventuelle date d'échéance."""
    total_paye = facture.paiement_set.aggregate(total=Sum("montant"))["total"] or 0
    reste      = facture.montant_total - total_paye

    facture.montant_paye = total_paye

    if reste <= 0:
        facture.statut = "payée"
        facture.date_echeance_restant = None
    else:
        facture.statut = "partielle" if total_paye > 0 else "impayée"
        # si aucune échéance définie, proposer +7 jours
        if not facture.date_echeance_restant:
            facture.date_echeance_restant = date.today() + timedelta(days=7)

    facture.save(update_fields=["montant_paye", "statut", "date_echeance_restant"])


# ---------------------------------------------------------------------------
# Commande → Facture
# ---------------------------------------------------------------------------

@receiver(post_save, sender=Commande)
def create_or_update_facture_commande(sender, instance, **kwargs):
    facture, _ = Facture.objects.get_or_create(commande=instance)

    lignes = LigneCommande.objects.filter(commande=instance)
    facture.montant_total = sum((l.prix_unitaire or 0) * (l.quantite or 0) for l in lignes)
    facture.commande_lignes.set(lignes)
    facture.save(update_fields=["montant_total"])

    _refresh_facture_statut(facture)


@receiver([post_save, post_delete], sender=LigneCommande)
def update_facture_on_lignecommande_change(sender, instance, **kwargs):
    try:
        facture = Facture.objects.get(commande=instance.commande)
    except Facture.DoesNotExist:
        return

    lignes = LigneCommande.objects.filter(commande=instance.commande)
    facture.montant_total = sum((l.prix_unitaire or 0) * (l.quantite or 0) for l in lignes)
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
def create_or_update_facture_achat(sender, instance, **kwargs):
    facture, _ = Facture.objects.get_or_create(achat=instance)

    lignes = LigneAchat.objects.filter(achat=instance)
    facture.montant_total = sum((l.prix_unitaire or 0) * (l.quantite or 0) for l in lignes)
    facture.achat_lignes.set(lignes)
    facture.save(update_fields=["montant_total"])

    _refresh_facture_statut(facture)


@receiver([post_save, post_delete], sender=LigneAchat)
def update_facture_on_ligneachat_change(sender, instance, **kwargs):
    try:
        facture = Facture.objects.get(achat=instance.achat)
    except Facture.DoesNotExist:
        return

    lignes = LigneAchat.objects.filter(achat=instance.achat)
    facture.montant_total = sum((l.prix_unitaire or 0) * (l.quantite or 0) for l in lignes)
    facture.achat_lignes.set(lignes)
    facture.save(update_fields=["montant_total"])

    _refresh_facture_statut(facture)


@receiver(post_delete, sender=Achat)
def delete_facture_achat(sender, instance, **kwargs):
    Facture.objects.filter(achat=instance).delete()


# ---------------------------------------------------------------------------
# Gestion de stock automatique
# ---------------------------------------------------------------------------

@receiver(post_save, sender=LigneCommande)
def diminuer_stock(sender, instance, created, **kwargs):
    if created:
        produit = instance.produit
        produit.stock -= int(instance.quantite)
        produit.save(update_fields=["stock"])


@receiver(post_save, sender=LigneAchat)
def augmenter_stock(sender, instance, created, **kwargs):
    if created:
        produit = instance.produit
        produit.stock += int(instance.quantite)
        produit.save(update_fields=["stock"])
