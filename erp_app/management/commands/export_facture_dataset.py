import csv
from django.core.management.base import BaseCommand
from django.db.models import Sum, Count, Avg, F
from erp_app.models import Facture, Paiement, RelancePaiement, Person, Commande
from datetime import timedelta

class Command(BaseCommand):
    help = 'Exporte un dataset ligne par ligne pour entraîner le modèle de prédiction de risque facture'

    def add_arguments(self, parser):
        parser.add_argument('--output', default='factures_training_dataset.csv', help='Chemin du fichier CSV à générer')

    def handle(self, *args, **options):
        path = options['output']

        fieldnames = [
            'id_facture', 'montant_total', 'nb_relances', 'delai_paiement', 'client_id',
            'nb_commandes_client', 'total_achats_client', 'moyenne_retard_client', 'type_client',
            'statut_final_facture'
        ]

        with open(path, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            factures = Facture.objects.select_related('commande__client').all()
            for facture in factures:
                if not facture.commande:
                    continue  # On ne prend que les factures liées aux commandes (clients)

                client = facture.commande.client

                # Nombre de relances associées à cette facture
                nb_relances = facture.relances.count()

                # Délai entre date facture et date du premier paiement (s'il existe)
                paiements = facture.paiement_set.order_by('date_paiement')
                if paiements.exists():
                    delai_paiement = (paiements.first().date_paiement - facture.date_facture).days
                else:
                    delai_paiement = None  # Peut être imputé ou ignoré

                # Nombre total de commandes client
                nb_commandes_client = Commande.objects.filter(client=client).count()

                # Total des achats du client
                total_achats_client = Facture.objects.filter(commande__client=client).aggregate(
                    total=Sum('montant_total'))['total'] or 0

                # Moyenne de retard (en jours) sur ses factures précédentes
                retards = []
                for f in Facture.objects.filter(commande__client=client):
                    p = f.paiement_set.order_by('date_paiement').first()
                    if p:
                        retard = (p.date_paiement - f.date_facture).days
                        retards.append(retard)
                moyenne_retard_client = sum(retards)/len(retards) if retards else 0

                # Type de client
                type_client = client.type if client else 'inconnu'

                writer.writerow({
                    'id_facture': facture.id,
                    'montant_total': facture.montant_total,
                    'nb_relances': nb_relances,
                    'delai_paiement': delai_paiement if delai_paiement is not None else '',
                    'client_id': client.id,
                    'nb_commandes_client': nb_commandes_client,
                    'total_achats_client': total_achats_client,
                    'moyenne_retard_client': round(moyenne_retard_client, 2),
                    'type_client': type_client,
                    'statut_final_facture': facture.statut
                })

        self.stdout.write(self.style.SUCCESS(f"✅ Dataset généré avec succès : {path}"))
