from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from erp_app.models import Facture, RelancePaiement

class Command(BaseCommand):
    help = 'Crée des relances automatiques pour les factures impayées à échéance proche'

    def handle(self, *args, **options):
        aujourd_hui = timezone.now().date()
        dans_3_jours = aujourd_hui + timedelta(days=3)

        factures_a_relancer = Facture.objects.filter(
            montant_total__gt=0,
            statut__in=['en attente', 'en cours'],
        ).exclude(
            relances__date_relance__gte=aujourd_hui
        )

        nb_relances = 0

        for facture in factures_a_relancer:
            # Simule une date d'échéance à 30 jours après la facture
            date_echeance = facture.date_facture + timedelta(days=30)
            if date_echeance <= dans_3_jours:
                RelancePaiement.objects.create(
                    facture=facture,
                    statut='envoyée',
                    note=f"Relance générée automatiquement le {aujourd_hui} (échéance le {date_echeance})"
                )
                nb_relances += 1

        self.stdout.write(self.style.SUCCESS(
            f"✅ {nb_relances} relances créées pour les factures en retard ou à échéance proche."
        ))
