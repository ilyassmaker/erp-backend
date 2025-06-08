from rest_framework import serializers
from .models import (
    Person, Produit, Achat, LigneAchat, Commande, LigneCommande, Facture,
    Paiement, CompteBancaire, TransactionTresorerie, RelancePaiement
)


class PersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = '__all__'


class ProduitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Produit
        fields = '__all__'


class LigneAchatSerializer(serializers.ModelSerializer):
        
    quantite = serializers.IntegerField()
    produit_nom = serializers.CharField(source='produit.nom', read_only=True)

    class Meta:
        model = LigneAchat
        fields = ['id', 'produit', 'produit_nom', 'quantite', 'prix_unitaire']


class AchatSerializer(serializers.ModelSerializer):
    fournisseur_nom = serializers.CharField(source='fournisseur.nom', read_only=True)
    lignes = LigneAchatSerializer(many=True, read_only=True)

    class Meta:
        model = Achat
        fields = ['id', 'fournisseur', 'fournisseur_nom', 'date_achat', 'statut', 'lignes']

    def create(self, validated_data):
        lignes_data = self.context['request'].data.get('lignes', [])
        achat = Achat.objects.create(
            fournisseur=validated_data['fournisseur'],
            statut=validated_data.get('statut', 'en attente')
        )
        for ligne_data in lignes_data:
            LigneAchat.objects.create(
                achat=achat,
                produit_id=int(ligne_data.get('produit')),
                quantite=ligne_data.get('quantite'),
                prix_unitaire=ligne_data.get('prix_unitaire')
            )
        return achat


class LigneCommandeSerializer(serializers.ModelSerializer):
    produit_nom = serializers.CharField(source='produit.nom', read_only=True)

    def validate(self, data):
        produit = data['produit']
        quantite = data['quantite']
        if produit.stock < quantite:
            raise serializers.ValidationError("Stock insuffisant pour ce produit.")
        return data

    class Meta:
        model = LigneCommande
        fields = ['id', 'commande', 'produit', 'produit_nom', 'quantite', 'prix_unitaire']



class CommandeSerializer(serializers.ModelSerializer):
    client_nom = serializers.CharField(source='client.nom', read_only=True)
    lignes = LigneCommandeSerializer(many=True, read_only=True, source='lignecommande_set')

    class Meta:
        model = Commande
        fields = ['id', 'client', 'client_nom', 'date_commande', 'statut', 'lignes']

    def create(self, validated_data):
        lignes_data = self.context['request'].data.get('lignes', [])
        commande = Commande.objects.create(
            client=validated_data['client'],
            statut=validated_data.get('statut', 'en attente'),
            date_commande=validated_data.get('date_commande', date.today())
        )
        for ligne_data in lignes_data:
            LigneCommande.objects.create(
                commande=commande,
                produit_id=ligne_data.get('produit'),
                quantite=ligne_data.get('quantite'),
                prix_unitaire=ligne_data.get('prix_unitaire')
            )
        return commande


class FactureSerializer(serializers.ModelSerializer):
    client_nom = serializers.SerializerMethodField()
    fournisseur_nom = serializers.SerializerMethodField()
    montant_paye = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    reste_a_payer = serializers.SerializerMethodField()
    date_echeance_restant = serializers.DateField(read_only=True)
    statut_paiement = serializers.SerializerMethodField()

    class Meta:
        model = Facture
        fields = [
            'id', 'commande', 'achat', 'client_nom', 'fournisseur_nom',
            'montant_total', 'montant_paye', 'reste_a_payer', 'date_echeance_restant',
            'statut_paiement', 'date_facture'
        ]

    def get_client_nom(self, obj):
        return obj.commande.client.nom if obj.commande and obj.commande.client else None

    def get_fournisseur_nom(self, obj):
        return obj.achat.fournisseur.nom if obj.achat and obj.achat.fournisseur else None

    def get_reste_a_payer(self, obj):
        return max(obj.montant_total - obj.montant_paye, 0)

    def get_statut_paiement(self, obj):
        return obj.statut

class PaiementSerializer(serializers.ModelSerializer):
    paiement_complet    = serializers.BooleanField()
    date_echeance_solde = serializers.DateField(allow_null=True, required=False)


    def validate(self, data):
        facture = data.get('facture') or self.instance.facture
        montant = data.get('montant') or self.instance.montant
        if montant <= 0:
            raise serializers.ValidationError("Le montant doit être strictement positif.")
        if facture:
            reste = facture.montant_total - facture.montant_paye
            if montant > reste:
                raise serializers.ValidationError(
                    f"Le montant dépasse le reste à payer ({reste} DH)."
                )

        if (
            not data.get("paiement_complet")
            and not data.get("date_echeance_solde")
        ):
            raise serializers.ValidationError(
                "Pour un paiement partiel, 'date_echeance_solde' est obligatoire."
            )
            
        return data

    class Meta:
        model = Paiement
        fields = '__all__'


class CompteBancaireSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompteBancaire
        fields = '__all__'


class TransactionTresorerieSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionTresorerie
        fields = '__all__'


class RelancePaiementSerializer(serializers.ModelSerializer):
    class Meta:
        model = RelancePaiement
        fields = ['id', 'facture', 'date_relance', 'statut', 'numero', 'note']
