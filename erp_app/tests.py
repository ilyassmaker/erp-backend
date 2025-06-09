from datetime import date
from django.test import TestCase, override_settings
from django.db.models import Sum, F

from .models import Commande, Facture, Produit, LigneCommande, Person

import os
from .utils import predire_risque_facture, categoriser_risque, MODEL_PATH
from .serializers import PaiementSerializer

TEST_DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}


@override_settings(DATABASES=TEST_DATABASES)
class PaiementSerializerTest(TestCase):
    def setUp(self):
        self.facture = Facture.objects.create(montant_total=100)

    def test_partial_payment_without_due_date_invalid(self):
        data = {
            'facture': self.facture.pk,
            'montant': 50,
            'paiement_complet': False,
        }
        serializer = PaiementSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)

    def test_partial_payment_with_due_date_valid(self):
        data = {
            'facture': self.facture.pk,
            'montant': 50,
            'paiement_complet': False,
            'date_echeance_solde': date.today(),
        }
        serializer = PaiementSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)


from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

# Create your tests here.
from .models import Person


class PersonModelTest(TestCase):
    """Tests for the Person model"""

    def test_str_representation(self):
        person = Person.objects.create(
            type="client",
            nom="Alice",
            email="alice@example.com",
            telephone="123456",
        )
        self.assertEqual(str(person), "Alice (Client)")


class PersonAPITest(TestCase):
    """Tests for the Person API endpoints"""

    def setUp(self):
        self.client = APIClient()

    def test_create_and_filter_persons(self):
        url = "/api/persons/"

        payload = {
            "type": "client",
            "nom": "Alice",
            "email": "alice@example.com",
            "telephone": "123456",
        }
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Person.objects.count(), 1)

        Person.objects.create(
            type="fournisseur",
            nom="Bob",
            email="bob@example.com",
            telephone="987654",
        )

        response = self.client.get(url + "?type=client")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 1)


class RisqueClientTest(TestCase):
    def setUp(self):
        self.client_obj = Person.objects.create(
            type='client', nom='Client Test', email='a@b.com', telephone='123'
        )
        self.produit = Produit.objects.create(
            nom="Test produit", 
            description="desc", 
            prix_vente=100, 
            prix_achat=50, 
            stock=100
        )

    def test_predire_risque_facture(self):
        # Création de deux commandes distinctes
        commande1 = Commande.objects.create(client=self.client_obj, statut='livrée')
        commande2 = Commande.objects.create(client=self.client_obj, statut='livrée')

        # Lignes de commande associées
        LigneCommande.objects.create(commande=commande1, produit=self.produit, quantite=1, prix_unitaire=100)
        LigneCommande.objects.create(commande=commande2, produit=self.produit, quantite=1, prix_unitaire=100)

        # Récupération des factures créées automatiquement
        facture1 = Facture.objects.get(commande=commande1)
        facture2 = Facture.objects.get(commande=commande2)

        # Calcul des montants totaux
        total1 = commande1.lignecommande_set.aggregate(
            total=Sum(F('quantite') * F('prix_unitaire'))
        )['total'] or 0
        total2 = commande2.lignecommande_set.aggregate(
            total=Sum(F('quantite') * F('prix_unitaire'))
        )['total'] or 0

        facture1.montant_total = total1
        facture1.save(update_fields=['montant_total'])
        facture2.montant_total = total2
        facture2.save(update_fields=['montant_total'])

        # Test de la prédiction
        proba = predire_risque_facture(self.client_obj.id)
        self.assertIsNotNone(proba)
        self.assertTrue(0 <= proba <= 1)
