# Script Django corrigé pour éviter stock négatif lors de la génération de commandes
# Enregistre dans create_orders_purchases_no_negative_stock.py et exécute :
# python manage.py shell < create_orders_purchases_no_negative_stock.py

import os, random
from datetime import date, timedelta
from decimal import Decimal

# Initialisation Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_project.settings')
import django; django.setup()

from erp_app.models import (
    Person, Produit,
    Commande, LigneCommande,
    Achat, LigneAchat,
    CompteBancaire, Paiement
)

# Récupère ou crée le compte bancaire
compte, _ = CompteBancaire.objects.get_or_create(
    numero_compte="BP123456789",
    defaults={"nom_banque": "Banque Populaire", "solde": Decimal('0.00')}
)

def old_date():
    return date.today() - timedelta(days=random.randint(60, 120))

# Fonction pour choisir un produit avec stock suffisant
def choix_produit_disponible():
    prods = list(Produit.objects.filter(stock__gte=1))
    return random.choice(prods) if prods else None

# Génération des commandes (clients)
for client in Person.objects.filter(type="client"):
    for _ in range(4):
        cmd = Commande.objects.create(
            client=client,
            date_commande=old_date(),
            statut=random.choice(["en attente", "en cours", "livrée", "annulée"])
        )
        total = Decimal('0.00')
        # 2 lignes de commande (quantité <= stock)
        for _ in range(2):
            prod = choix_produit_disponible()
            if not prod:
                continue  # plus de stock disponible
            max_q = prod.stock
            qty = random.randint(1, max_q)
            LigneCommande.objects.create(
                commande=cmd,
                produit=prod,
                quantite=qty,
                prix_unitaire=prod.prix_vente
            )
            total += Decimal(qty) * prod.prix_vente

        # Paiement sur facture auto-créée
        fac = cmd.facture
        pay_amount = random.choice([Decimal('0.00'), total, (total / Decimal('2')).quantize(Decimal('0.01'))])
        if pay_amount > 0:
            Paiement.objects.create(
                facture=fac,
                montant=pay_amount,
                methode=random.choice(["virement", "espèce", "chèque"]),
                compte_bancaire=compte
            )

# Génération des achats (fournisseurs) — augmente le stock, pas de risque de négatif
for fournisseur in Person.objects.filter(type="fournisseur"):
    for _ in range(4):
        ach = Achat.objects.create(
            fournisseur=fournisseur,
            date_achat=old_date(),
            statut=random.choice(["en attente", "en cours", "livrée", "annulée"])
        )
        total = Decimal('0.00')
        for _ in range(2):
            prod = random.choice(list(Produit.objects.all()))
            qty = random.randint(1, 5)
            LigneAchat.objects.create(
                achat=ach,
                produit=prod,
                quantite=qty,
                prix_unitaire=prod.prix_achat
            )
            total += Decimal(qty) * prod.prix_achat

        fac = ach.facture
        pay_amount = random.choice([Decimal('0.00'), total, (total / Decimal('2')).quantize(Decimal('0.01'))])
        if pay_amount > 0:
            Paiement.objects.create(
                facture=fac,
                montant=pay_amount,
                methode=random.choice(["virement", "espèce", "chèque"]),
                compte_bancaire=compte
            )

# Affichage récapitulatif
print("✅ Génération terminée :")
print(f"- Commandes : {Commande.objects.count()}")
print(f"- Achats     : {Achat.objects.count()}")
print(f"- Paiements  : {Paiement.objects.count()}")