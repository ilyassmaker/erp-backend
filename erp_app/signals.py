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
    TransactionTresorerie
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
def create_or_update_facture_commande(sender, instance, **kwargs):
    facture, _ = Facture.objects.get_or_create(commande=instance)
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
def create_or_update_facture_achat(sender, instance, **kwargs):
    facture, _ = Facture.objects.get_or_create(achat=instance)
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