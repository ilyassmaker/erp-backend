from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal

from erp_app.models import (
    Person,
    Produit,
    Commande,
    LigneCommande,
    Facture,
    Paiement,
    RelancePaiement,
)


class Command(BaseCommand):
    help = "Crée des clients de démonstration avec des factures impayées pour tester le niveau de risque"

    def handle(self, *args, **options):
        self.stdout.write("Création des données de risque …")

        produit, _ = Produit.objects.get_or_create(
            nom="Produit Démo",
            defaults={"prix_achat": 50, "prix_vente": 100, "stock": 1000},
        )

        client_moderate, _ = Person.objects.get_or_create(
            nom="Ilyas Borz",
            defaults={"type": "client", "email": "ilyas@example.com", "telephone": "0000"},
        )

        client_high, _ = Person.objects.get_or_create(
            nom="Aujiss",
            defaults={"type": "client", "email": "wajih@example.com", "telephone": "0000"},
        )

        self._create_moderate_risk(client_moderate, produit)
        self._create_high_risk(client_high, produit)

        self.stdout.write(self.style.SUCCESS("✅ Données de risque créées"))

    def _create_moderate_risk(self, client, produit):
        today = timezone.now().date()

        # Facture payée rapidement
        cmd1 = Commande.objects.create(client=client, statut="livrée")
        old_date1 = today - timedelta(days=45)
        Commande.objects.filter(pk=cmd1.pk).update(date_commande=old_date1)
        LigneCommande.objects.create(commande=cmd1, produit=produit, quantite=2, prix_unitaire=produit.prix_vente)
        fac1 = cmd1.facture
        Facture.objects.filter(pk=fac1.pk).update(date_facture=old_date1 + timedelta(days=1))
        fac1.refresh_from_db()
        fac1.montant_total = Decimal(2) * produit.prix_vente
        fac1.save(update_fields=["montant_total"])
        pay1 = Paiement.objects.create(
            facture=fac1,
            montant=fac1.montant_total,
            methode="virement",
            paiement_complet=True,
        )
        Paiement.objects.filter(pk=pay1.pk).update(date_paiement=fac1.date_facture + timedelta(days=5))

        # Facture partiellement payée avec une relance
        cmd2 = Commande.objects.create(client=client, statut="livrée")
        old_date2 = today - timedelta(days=30)
        Commande.objects.filter(pk=cmd2.pk).update(date_commande=old_date2)
        LigneCommande.objects.create(commande=cmd2, produit=produit, quantite=2, prix_unitaire=produit.prix_vente)
        fac2 = cmd2.facture
        Facture.objects.filter(pk=fac2.pk).update(date_facture=old_date2 + timedelta(days=1))
        fac2.refresh_from_db()
        fac2.montant_total = Decimal(2) * produit.prix_vente
        fac2.save(update_fields=["montant_total"])
        pay2 = Paiement.objects.create(
            facture=fac2,
            montant=fac2.montant_total / Decimal("2"),
            methode="virement",
            paiement_complet=False,
            date_echeance_solde=fac2.date_facture + timedelta(days=30),
        )
        Paiement.objects.filter(pk=pay2.pk).update(date_paiement=fac2.date_facture + timedelta(days=20))
        rel = RelancePaiement.objects.create(facture=fac2, numero=1, statut="envoyée")
        RelancePaiement.objects.filter(pk=rel.pk).update(date_relance=fac2.date_facture + timedelta(days=40))

    def _create_high_risk(self, client, produit):
        today = timezone.now().date()
        delays = [90, 75, 60]

        for d in delays:
            cmd = Commande.objects.create(client=client, statut="livrée")
            old_date = today - timedelta(days=d)
            Commande.objects.filter(pk=cmd.pk).update(date_commande=old_date)
            LigneCommande.objects.create(
                commande=cmd,
                produit=produit,
                quantite=2,
                prix_unitaire=produit.prix_vente,
            )
            fac = cmd.facture
            Facture.objects.filter(pk=fac.pk).update(date_facture=old_date + timedelta(days=1))
            fac.refresh_from_db()
            fac.montant_total = Decimal(2) * produit.prix_vente
            fac.save(update_fields=["montant_total"])
            # Plusieurs relances, aucun paiement
            for r in range(3):
                rel = RelancePaiement.objects.create(
                    facture=fac,
                    numero=r + 1,
                    statut="envoyée",
                )
                RelancePaiement.objects.filter(pk=rel.pk).update(
                    date_relance=fac.date_facture + timedelta(days=20 + r * 7)
                )
        # fin de la boucle

