from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random
from erp_app.models import Person, Produit, Commande, LigneCommande, Facture, Paiement, RelancePaiement
from django.db.models import Sum, DecimalField, ExpressionWrapper, F
from decimal import Decimal

class Command(BaseCommand):
    help = "Génère des factures, paiements et relances factices pour l'entraînement du modèle de risque"

    def handle(self, *args, **options):
        nb_clients = 500
        nb_factures_total = 10000

        clients = []
        for i in range(nb_clients):
            client = Person.objects.create(
                type="client",
                nom=f"Client {i}",
                email=f"client{i}@test.com",
                telephone="0600000000"
            )
            clients.append(client)

        produit = Produit.objects.create(
            nom="Produit X", prix_achat=100, prix_vente=200, stock=1000000
        )

        today = timezone.now().date()

        for i in range(nb_factures_total):
            client = random.choice(clients)
            commande = Commande.objects.create(
                client=client,
                date_commande=today - timedelta(days=random.randint(30, 90)),
                statut="livrée"
            )

            quantite = random.randint(1, 10)
            prix_unitaire = produit.prix_vente
            LigneCommande.objects.create(
                commande=commande,
                produit=produit,
                quantite=quantite,
                prix_unitaire=prix_unitaire
            )

            facture = Facture.objects.get(commande=commande)
            facture.date_facture = commande.date_commande + timedelta(days=1)

            montant_total = commande.lignecommande_set.aggregate(
                total=Sum(
                    ExpressionWrapper(
                        F("quantite") * F("prix_unitaire"),
                        output_field=DecimalField()
                    )
                )
            )["total"] or 0

            # 🔁 Logique réaliste basée sur fidélité du client
            nb_commandes_client = Commande.objects.filter(client=client).count()

            if nb_commandes_client > 15:
                statut_aleatoire = random.choices(
                    ["payée", "partielle", "impayée"], weights=[0.7, 0.25, 0.05], k=1
                )[0]
            elif nb_commandes_client > 5:
                statut_aleatoire = random.choices(
                    ["payée", "partielle", "impayée"], weights=[0.5, 0.35, 0.15], k=1
                )[0]
            else:
                statut_aleatoire = random.choices(
                    ["payée", "partielle", "impayée"], weights=[0.3, 0.45, 0.25], k=1
                )[0]

            # Paiement selon statut
            if statut_aleatoire in ["payée", "partielle"]:
                montant_paye = montant_total if statut_aleatoire == "payée" else montant_total * Decimal("0.5")
                date_paiement = facture.date_facture + timedelta(days=random.randint(2, 45))
                Paiement.objects.create(
                    facture=facture,
                    montant=montant_paye,
                    date_paiement=date_paiement,
                    paiement_complet=(statut_aleatoire == "payée"),
                    date_echeance_solde=(None if statut_aleatoire == "payée" else date_paiement + timedelta(days=15)),
                    methode="virement",
                    reference_paiement=f"REF-{i}"
                )

            facture.montant_total = montant_total
            facture.statut = statut_aleatoire
            facture.save()

            # Relances
            for rel in range(random.randint(0, 3)):
                RelancePaiement.objects.create(
                    facture=facture,
                    date_relance=facture.date_facture + timedelta(days=10 + rel * 7),
                    statut="envoyée",
                    note="Relance automatique générée pour test.",
                    numero=rel + 1
                )

        self.stdout.write(self.style.SUCCESS(
            f"✅ {nb_factures_total} factures générées pour l'entraînement ML."
        ))
