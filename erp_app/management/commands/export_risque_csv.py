import csv
from django.core.management.base import BaseCommand
from erp_app.models import Person, Facture

class Command(BaseCommand):
    help = 'Génère un CSV de données pour entraîner le modèle de risque facture'

    def add_arguments(self, parser):
        parser.add_argument('--output', default='facture_training.csv', help='Chemin du fichier CSV')

    def handle(self, *args, **options):
        path = options['output']
        fieldnames = ['client_id', 'nb_factures', 'nb_impayes', 'ratio_impayes']
        with open(path, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for client in Person.objects.filter(type='client'):
                factures = Facture.objects.filter(commande__client=client)
                nb_factures = factures.count()
                nb_impayes = factures.filter(statut__in=['impayée', 'partielle']).count()
                ratio = nb_impayes / nb_factures if nb_factures else 0
                writer.writerow({
                    'client_id': client.id,
                    'nb_factures': nb_factures,
                    'nb_impayes': nb_impayes,
                    'ratio_impayes': ratio,
                })
        self.stdout.write(self.style.SUCCESS(f'Données exportées dans {path}'))
